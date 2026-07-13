// Smoke: #397 FR-10/FR-11 / UFR-1 — doc-review park composes a decision list into the
// `parked` event payload and discloses a review_park.py dispatch failure on assumptions.
'use strict'
require('./_smoke_checkout_root.js')
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const test = require('node:test')
const sr = require('../showrunner.js')
const { saveProgressOk } = require('./_marked_stdout.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}

const SFX = `-pid${process.pid}`
const WI = `wi-park${SFX}`

const BLOCKER = [{
  file: 'plan.md', line: 1, title: 'unauth write path', severity: 'Critical',
  docSection: 'Architecture', summary: 'the write path skips auth', evidence: 'e',
}]

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

function makeAgent({ parkComposerMode = 'real' } = {}) {
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
      if (prompt.includes('review_handoff.py') && prompt.includes(' write ')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, counts: { distinct: 0 } }) }]
      }
      if (prompt.includes('review_park.py')) {
        if (parkComposerMode === 'reject') throw new Error('courier transport rejected')
        if (parkComposerMode === 'non-json') {
          return [{ index: 0, ok: true, stdout: 'not json' }]
        }
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd, 'review_park dispatch must be a numbered exec command')
        const stdout = execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('gate-for-terminal')) {
        throw new Error('gate-for-terminal dispatched as exec — must use JS twin')
      }
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (prompt.includes('gate-for-terminal')) {
      throw new Error('gate-for-terminal dispatched as cmdRunner — must use JS twin')
    }
    if (label.endsWith('-reviewer')) {
      return { findings: BLOCKER, confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    if (label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'revise-doc') return null
    return null
  }
  fn.savePrompts = () => savePrompts
  return fn
}

function seedPlanDoc(docsDir) {
  fs.mkdirSync(docsDir, { recursive: true })
  fs.writeFileSync(path.join(docsDir, 'plan.md'), '# Plan\n## Review coverage decisions\n')
}

function cleanRunDir() {
  try { fs.rmSync(`/tmp/showrunner-${WI}-review-plan`, { recursive: true, force: true }) } catch (_) {}
}

function cleanLegacyFixture() {
  try { fs.rmSync(`docs/superheroes/${WI}`, { recursive: true, force: true }) } catch (_) {}
}

function parseParkPayloadFromSavePrompt(prompt) {
  const m = String(prompt).match(/--terminal-park-payload '([^']*(?:''[^']*)*)'/)
  assert.ok(m, 'save prompt must carry --terminal-park-payload')
  return JSON.parse(m[1].replace(/''/g, "'"))
}

async function drivePlanPark(parkComposerMode) {
  cleanRunDir()
  cleanLegacyFixture()
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-park-'))
  seedPlanDoc(docsDir)
  globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
  const agent = makeAgent({ parkComposerMode })
  globalThis.agent = agent
  const idx = sr.PHASES.indexOf('review-plan')
  const loopOut = await sr.runPhases(WI, idx, {
    reviewDoc: (doc, wi) => sr.reviewDocPhase(doc, wi, { runId: 'run-park' }),
  })
  return { loopOut, agent, docsDir }
}

test('doc-review park carries a non-empty decision list in the parked payload', async () => {
  try {
    const { loopOut, agent } = await drivePlanPark('real')
    assert.strictEqual(loopOut.outcome, 'parked')
    assert.strictEqual(loopOut.phase, 'review-plan')
    const savePrompt = agent.savePrompts().find((p) => p.includes('--terminal-park-payload'))
    assert.ok(savePrompt, 'journal-only park save must include terminal-park-payload')
    const payload = parseParkPayloadFromSavePrompt(savePrompt)
    assert.strictEqual(payload.doc, 'plan')
    assert.ok(Array.isArray(payload.decisions) && payload.decisions.length >= 1,
      'doc-review park payload must carry blocking decisions')
    assert.ok(payload.decisions[0].statement, 'decision must include a statement')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1: review_park dispatch failure uses minimal fallback payload on parked event', async () => {
  try {
    const { agent } = await drivePlanPark('non-json')
    const savePrompt = agent.savePrompts().find((p) => p.includes('--terminal-park-payload'))
    assert.ok(savePrompt, 'park must still journal with terminal-park-payload on dispatch failure')
    const payload = parseParkPayloadFromSavePrompt(savePrompt)
    assert.deepStrictEqual(payload.decisions, [])
    assert.match(payload.note || '', /could not be composed/)
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1: rejected review_park dispatch discloses on phaseResult.assumptions', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-park-'))
  try {
    cleanRunDir()
    cleanLegacyFixture()
    seedPlanDoc(docsDir)
    globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
    globalThis.agent = makeAgent({ parkComposerMode: 'reject' })
    const r = await sr.reviewDocPhase('plan', WI, { runId: 'run-park' })
    assert.strictEqual(r.gate, 'changes-requested')
    const assumptions = (r.phaseResult && r.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /decision list could not be composed/.test(a)),
      'review_park dispatch failure must surface on phaseResult.assumptions',
    )
    assert.ok(r.persist && r.persist.parkPayload, 'persist must carry fallback parkPayload')
    assert.deepStrictEqual(r.persist.parkPayload.decisions, [])
    assert.match(r.persist.parkPayload.note || '', /could not be composed/)
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})
