// Smoke: reviewPanel honors a PRELOADED setup gather (fold 2, #141; #211 decision shape). The doc/code
// legs run ONE review_setup_gather.py leaf up front (the resume DECISION + round-1 plan + coverage +
// deferred — no records ride up, #211) and hand it to reviewPanel as `preloaded`, so round 1 must NOT
// re-fire the gather. A run WITHOUT preloaded self-gathers (one review_setup_gather.py leaf, coverage
// folded — no separate coverage-load leaf). The tally reads the deferred set from DISK.
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
  // #211 decision shape: resume DECISION + round-1 plan (schedule + coverage folds separately here) +
  // deferred + coverage — never records.
  return {
    ok: true,
    resume: { ok: true, state: 'missing', round: 1, contentHash: defaultIo.contentHash(''),
      extras: null, confirmationPending: false, markedRound: null, roundCount: 0 },
    plan: { ok: true, round: 1, roundKind: 'baseline', enterConfirmation: false,
      escalationPolicy: 'deep-only', dimensions: { code: { action: 'run', tier: 'reviewer-deep' } },
      carried: {}, latestCoverageDecisionIds: [] },
    deferredSet: {},
    coverage: { ok: true, decisions: [], contentHash: defaultIo.contentHash('') },
  }
}

async function main() {
  globalThis.reviewerAgent = async (_r, _c, _rub, runDir, round) =>
    ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } })

  // (1) preloaded: round 1 fires NO setup-gather leaf (and NO separate coverage-load leaf).
  {
    const dir = freshDir()
    fs.mkdirSync(dir, { recursive: true })
    calls.length = 0
    const v = await reviewPanel({ ...base(dir), preloaded: emptyPreload() })
    assert.strictEqual(v.terminal, 'clean', `preloaded clean run must converge (got ${v.terminal})`)
    assert.ok(!calls.some((c) => c.includes('review_setup_gather.py')), 'preloaded: no setup-gather leaf on round 1')
    assert.ok(!calls.some((c) => c.includes('coverage_decisions.py') && c.includes('load')),
      'preloaded: no separate coverage-load leaf on round 1 (folded)')
  }

  // (2) NO preloaded: the shell self-gathers via ONE review_setup_gather.py leaf (coverage folded in,
  // so no separate coverage-load leaf on round 1).
  {
    const dir = freshDir()
    calls.length = 0
    const v = await reviewPanel({ ...base(dir) })
    assert.strictEqual(v.terminal, 'clean')
    assert.ok(calls.some((c) => c.includes('review_setup_gather.py') && c.includes('gather')),
      'no preloaded: the shell self-gathers (review_setup_gather.py)')
    assert.ok(!calls.some((c) => c.includes('coverage_decisions.py') && c.includes('load')),
      'no preloaded: coverage is folded into the round-1 gather (no separate load leaf)')
  }

  // (3) the deferred set is read from DISK by the tally decider — a disk-deferred blocker does not
  // re-block (the gather reads the same disk, so preloaded == disk in practice).
  {
    const dir = freshDir()
    fs.mkdirSync(dir, { recursive: true })
    const finding = { file: 'a.py', line: 1, title: 'Deferred Bug', severity: 'Critical', evidence: 'e' }
    const id = circuitBreaker.findingIdentity(finding)
    fs.writeFileSync(path.join(dir, 'deferred-set.json'), JSON.stringify({ [id]: 'Critical' }))
    globalThis.reviewerAgent = async (_r, _c, _rub, runDir, round) =>
      ({ findings: [finding], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } })
    const v = await reviewPanel({ ...base(dir) })
    assert.ok(v.terminal === 'clean' || v.terminal === 'clean-with-skips',
      `a disk-deferred blocker must not re-block (got ${v.terminal}/${v.reason})`)
  }

  console.log('ok: reviewPanel honors the preloaded setup gather (fold 2, #141; #211 decision shape)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
