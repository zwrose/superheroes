// Smoke: reviewPanel honors a PRELOADED setup gather (fold 2, #141). The shared shell used to enter
// each round by firing load-summary + coverage-load (+ the tally's deferred-set read) as their own
// courier leaves. The doc/code legs now run ONE review_setup_gather.py leaf up front and hand the
// result to reviewPanel as `preloaded`, so round 1 must NOT re-fire those reads — while a run WITHOUT
// preloaded still falls back to the unfolded reads (backward compat for the standalone shell + tests).
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { defaultIo } = require('../io_seam.js')
const circuitBreaker = require('../circuit_breaker.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}
globalThis.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
globalThis.recordDeferred = async () => {}
globalThis.agent = async () => null

function receipt(runId, round) {
  return { artifact: `${runId}:round-${round}`, chain: [
    { step: 'citation', evidence: 'c' }, { step: 'reachability', evidence: 'r' },
    { step: 'missing-check', evidence: 'm' }, { step: 'tooling', evidence: 't' }],
    coverageDecisionIds: [] }
}

// spy on every runHelper invocation (records the argv as a joined string)
const calls = []
globalThis.io = Object.assign({}, defaultIo, {
  async runHelper(cmd, args) { calls.push((args || []).join(' ')); return defaultIo.runHelper(cmd, args) },
})

function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'setup-gather-')) }
function base(dir) {
  return {
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: [], changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  }
}
function emptyPreload() {
  return {
    ok: true,
    memory: { ok: true, state: 'missing', records: [], contentHash: defaultIo.contentHash(''), extras: null },
    deferredSet: {},
    coverage: { ok: true, decisions: [], contentHash: defaultIo.contentHash('') },
  }
}

async function main() {
  globalThis.reviewerAgent = async (_r, _c, _rub, runDir, round) =>
    ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } })

  // (1) preloaded: round 1 fires NO load-summary and NO coverage-load leaf.
  {
    const dir = freshDir()
    fs.mkdirSync(dir, { recursive: true })
    calls.length = 0
    const v = await reviewPanel({ ...base(dir), preloaded: emptyPreload() })
    assert.strictEqual(v.terminal, 'clean', `preloaded clean run must converge (got ${v.terminal})`)
    assert.ok(!calls.some((c) => c.includes('load-summary')), 'preloaded: no load-summary leaf on round 1')
    assert.ok(!calls.some((c) => c.includes('coverage_decisions.py') && c.includes('load')),
      'preloaded: no coverage-load leaf on round 1')
  }

  // (2) NO preloaded: the unfolded reads still fire (backward compat).
  {
    const dir = freshDir()
    calls.length = 0
    const v = await reviewPanel({ ...base(dir) })
    assert.strictEqual(v.terminal, 'clean')
    assert.ok(calls.some((c) => c.includes('load-summary')), 'no preloaded: load-summary fires')
    assert.ok(calls.some((c) => c.includes('coverage_decisions.py') && c.includes('load')),
      'no preloaded: coverage-load fires')
  }

  // (3) the preloaded deferred-set is used by the round-1 tally (a preloaded-deferred finding does
  // not block) — proving the round-1 tally reuses the gathered set instead of re-reading disk.
  {
    const dir = freshDir()
    fs.mkdirSync(dir, { recursive: true })
    // disk deferred-set is EMPTY; only the preload carries the deferral.
    const finding = { file: 'a.py', line: 1, title: 'Deferred Bug', severity: 'Critical', evidence: 'e' }
    const id = circuitBreaker.findingIdentity(finding)
    globalThis.reviewerAgent = async (_r, _c, _rub, runDir, round) =>
      ({ findings: [finding], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } })
    const pre = emptyPreload(); pre.deferredSet = { [id]: 'Critical' }
    const v = await reviewPanel({ ...base(dir), preloaded: pre })
    assert.ok(v.terminal === 'clean' || v.terminal === 'clean-with-skips',
      `a preloaded-deferred blocker must not re-block (got ${v.terminal}/${v.reason})`)
  }

  console.log('ok: reviewPanel honors the preloaded setup gather (fold 2, #141)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
