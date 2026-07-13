// Smoke: #397 FR-14 — accepted doc findings survive a re-review of unchanged content; UFR-1 on record leg.
'use strict'
require('./_smoke_checkout_root.js')
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { execSync, execFileSync } = require('child_process')
const test = require('node:test')
const sr = require('../showrunner.js')
const { saveProgressOk } = require('./_marked_stdout.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}

const SFX = `-pid${process.pid}`
const WI = `wi-acc${SFX}`

const BLOCKER = [{
  file: 'plan.md', line: 1, title: 'unauth write path', severity: 'Critical',
  docSection: 'Architecture', summary: 'the write path skips auth', evidence: 'e',
}]

const PLAN_DOC = `# Plan

## Architecture

The write path authenticates every request.

## Data flow

Records are append-only.
`

function receiptFromPrompt(prompt) {
  let ctx = { receiptArtifact: 'stub', receiptCoverageDecisionIds: [] }
  const m = String(prompt || '').match(/Prompt context: (\{.*\})/s)
  if (m) { try { ctx = JSON.parse(m[1]) } catch (_) {} }
  return {
    artifact: ctx.receiptArtifact || 'stub',
    chain: [
      { step: 'citation', evidence: 'reviewed citations' },
      { step: 'reachability', evidence: 'validated call path' },
      { step: 'missing-check', evidence: 'checked missing FRs' },
      { step: 'tooling', evidence: 'smoke passed' },
    ],
    coverageDecisionIds: ctx.receiptCoverageDecisionIds || [],
  }
}

function extractExecCommand(prompt) {
  const m = String(prompt).match(/^\d+\.\s(.*)$/m)
  return m ? m[1] : null
}

function seedPlanDoc(docsDir) {
  fs.mkdirSync(docsDir, { recursive: true })
  fs.writeFileSync(path.join(docsDir, 'plan.md'), PLAN_DOC)
}

function cleanRunDir() {
  try { fs.rmSync(`/tmp/showrunner-${WI}-review-plan`, { recursive: true, force: true }) } catch (_) {}
}

function cleanLegacyFixture() {
  try { fs.rmSync(`docs/superheroes/${WI}`, { recursive: true, force: true }) } catch (_) {}
}

function seedRoundRecords(runDir) {
  fs.mkdirSync(runDir, { recursive: true })
  fs.writeFileSync(path.join(runDir, 'round-records.json'), JSON.stringify([{
    round: 1,
    findings: BLOCKER,
  }]))
}

function recordAcceptanceViaPython(docsDir) {
  const blockersPath = path.join(docsDir, 'open-blockers.json')
  fs.writeFileSync(blockersPath, JSON.stringify(BLOCKER))
  const cmd = [
    'python3', path.join(__dirname, '..', 'review_acceptance.py'), 'record',
    '--docs-dir', docsDir,
    '--doc', 'plan',
    '--findings', blockersPath,
    '--doc-path', path.join(docsDir, 'plan.md'),
  ]
  execFileSync(cmd[0], cmd.slice(1), { encoding: 'utf8', cwd: globalThis.__SR_ROOT || process.cwd() })
}

function makeBaseAgent({ synthesisMode = 'same', recordMode = 'real' } = {}) {
  const savePrompts = []
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'save phase progress') {
      savePrompts.push(String(prompt))
      return saveProgressOk({ checkpoint_confirmed: false })
    }
    if (label === 'save round state') {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (opts && opts.courier) {
      if (prompt.includes('read-gate')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
      }
      if (prompt.includes('review_acceptance.py') && prompt.includes(' record ')) {
        if (recordMode === 'fail') {
          return [{ index: 0, ok: false, stderr: 'simulated write error' }]
        }
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd, 'review_acceptance record dispatch must be a numbered exec command')
        const stdout = execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('review_acceptance.py') && prompt.includes(' candidates')) {
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd)
        const stdout = execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('review_handoff.py') && prompt.includes('collect-blocking')) {
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd)
        const stdout = execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('review_convergence.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, doc: 'plan', outcome: 'accepted-pass' }) }]
      }
      if (prompt.includes('definition_doc.py') && prompt.includes('set-gate')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, review: 'passed' }) }]
      }
      if (prompt.includes('review_park.py') || prompt.includes('review_handoff.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label.endsWith('-reviewer')) {
      return { findings: BLOCKER, confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    if (label.startsWith('synthesis')) {
      if (synthesisMode === 'same') {
        return {
          verdicts: [{
            id: 'plan.md::unauth write path',
            action: 'same',
            reason: 'same concern the owner accepted',
            severity: 'Critical',
          }],
        }
      }
      return { verdicts: [{ id: 'plan.md::unauth write path', action: 'keep', reason: 'still applies', severity: 'Critical' }] }
    }
    if (label === 'revise-doc') return { fixes: [], deferred: [], changedSubjects: [] }
    return null
  }
  fn.savePrompts = () => savePrompts
  return fn
}

test('FR-14: accepted finding does not re-block on re-review of unchanged doc', async () => {
  cleanRunDir()
  cleanLegacyFixture()
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-acc-'))
  try {
    seedPlanDoc(docsDir)
    recordAcceptanceViaPython(docsDir)
    globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
    globalThis.agent = makeBaseAgent({ synthesisMode: 'same' })
    const runDir = `/tmp/showrunner-${WI}-review-plan`
    const verdict = await sr.runReviewDocPanel({
      workItem: WI,
      docType: 'plan',
      docPath: `${docsDir}/plan.md`,
      runDir,
      runtimeDeferred: new Map(),
    })
    assert.ok(verdict, 're-review should return a verdict')
    assert.strictEqual(verdict.terminal, 'clean',
      `accepted finding should allow clean pass (got ${verdict.terminal}: ${verdict.reason || ''})`)
    assert.strictEqual(verdict.gate, 'clean')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    delete globalThis.loadAcceptanceCandidates
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1: ledger record failure does not block gate-approval write', async () => {
  cleanRunDir()
  cleanLegacyFixture()
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-acc-'))
  const runDir = `/tmp/showrunner-${WI}-review-plan`
  try {
    seedPlanDoc(docsDir)
    seedRoundRecords(runDir)
    globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
    globalThis.agent = makeBaseAgent({ recordMode: 'fail' })
    const r = await sr.approveDocReviewGate('plan', WI, { runId: 'run-acc' })
    assert.strictEqual(r.gate, 'passed', 'gate approval must still target passed')
    assert.ok(r.persist && r.persist.sideEffectCmd.includes('set-gate'),
      'persist must chain set-gate passed')
    const assumptions = (r.phaseResult && r.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /acceptance record could not be written/.test(a)),
      'ledger failure must disclose on phaseResult.assumptions',
    )
    // Execute the side effect through the stubbed courier path — set-gate succeeds.
    const agent = globalThis.agent
    const gateRes = await agent('1. ' + r.persist.sideEffectCmd, { courier: true })
    assert.ok(gateRes && gateRes[0] && gateRes[0].ok, 'set-gate must succeed despite ledger failure')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})
