// Smoke: #397 FR-2 / UFR-1 — plan-review terminal writes plan-handoff.json from non-blocking
// findings and discloses a write failure on phaseResult.assumptions instead of failing silently.
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
const WI = `wi-handoff${SFX}`

const NONBLOCKING = [
  { file: 'plan.md', line: 1, title: 'no named unit test', severity: 'Minor',
    docSection: 'Components & interfaces', summary: 'add a unit test for option A' },
  { file: 'plan.md', line: 2, title: 'No Named Unit Test', severity: 'Minor',
    docSection: 'Components & interfaces', summary: 'dup, reworded case' },
  { file: 'plan.md', line: 3, title: 'two literals for retry', severity: 'Minor',
    docSection: 'Data flow', summary: 'retry constant appears twice' },
]

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

function makeAgent({ handoffMode = 'real' } = {}) {
  const handoffCalls = []
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'save phase progress') return saveProgressOk()
    if (label === 'save round state') return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (opts && opts.courier) {
      if (prompt.includes('read-gate')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
      }
      if (prompt.includes('review_handoff.py') && prompt.includes(' write ')) {
        handoffCalls.push(prompt)
        if (handoffMode === 'reject') throw new Error('courier transport rejected')
        if (handoffMode === 'non-ok') {
          return [{ index: 0, ok: false, stdout: JSON.stringify({ ok: false, reason: 'stub fail' }) }]
        }
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd, 'handoff write must be a numbered exec command')
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
      return { findings: NONBLOCKING, confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    if (label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'revise-doc') return { fixes: [], deferred: [] }
    return null
  }
  fn.handoffCalls = () => handoffCalls
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

async function drivePlanReview(docsDir, handoffMode) {
  cleanRunDir()
  cleanLegacyFixture()
  seedPlanDoc(docsDir)
  globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
  const agent = makeAgent({ handoffMode })
  globalThis.agent = agent
  const r = await sr.reviewDocPhase('plan', WI, { runId: 'run-handoff' })
  return { result: r, agent, docsDir }
}

test('plan-review terminal writes plan-handoff.json with distinct non-blocking counts', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-plan-handoff-'))
  try {
    const { result, agent } = await drivePlanReview(docsDir, 'real')
    assert.strictEqual(result.gate, 'passed', 'non-blocking-only panel must pass')
    assert.ok(agent.handoffCalls().length >= 1, 'must invoke review_handoff.py write')
    const handoffPath = path.join(docsDir, 'plan-handoff.json')
    assert.ok(fs.existsSync(handoffPath), 'plan-handoff.json must exist in planted docs dir')
    const data = JSON.parse(fs.readFileSync(handoffPath, 'utf8'))
    assert.strictEqual(data.counts.distinct, 2, 'two same-identity entries collapse to 2 distinct')
    assert.strictEqual(data.workItem, WI)
  } finally {
    delete globalThis.__SR_DOC_DIRS
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1: non-ok handoff write discloses on phaseResult.assumptions', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-plan-handoff-'))
  try {
    const { result } = await drivePlanReview(docsDir, 'non-ok')
    const assumptions = (result.phaseResult && result.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /plan-handoff\.json write may have failed/.test(a)),
      'hand-off write failure must surface on phaseResult.assumptions',
    )
  } finally {
    delete globalThis.__SR_DOC_DIRS
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1 guard: rejected handoff dispatch still returns terminal result with disclosure', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-plan-handoff-'))
  try {
    const { result } = await drivePlanReview(docsDir, 'reject')
    assert.ok(result && result.gate, 'phase must still return its terminal gate (not abort)')
    const assumptions = (result.phaseResult && result.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /plan-handoff\.json write may have failed/.test(a)),
      'reject path must disclose on phaseResult.assumptions',
    )
  } finally {
    delete globalThis.__SR_DOC_DIRS
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})
