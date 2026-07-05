// Smoke (#211 Phase 4a — the DRIFT GUARD): the Python deciders that now own the review loop's
// decisions must be a FAITHFUL PORT of the in-memory JS helpers they replaced. Over a shared
// multi-round on-disk `round-records.json`, drive BOTH:
//   - the OLD in-memory path — the pure decision helpers still exported from review_panel_shell.js
//     (resumeRound / buildPreviousDimensionState → roundPolicy.planRound / confirmationReady /
//     carryForwardDimension for the schedule; tallyTerminalInMemory for the terminal), and
//   - the NEW decider path — review_loop_plan.py {entry-bootstrap, plan-round, tally-round} via the
//     real Python verbs,
// and assert identical decisions: resume round + markers, the per-dimension schedule + carried +
// enterConfirmation, and the terminal + reason + gate + breaker verdict + recurrence keys +
// uncertified flag + certification. The ride-DOWN scalars (gate / present-blocking / uncertified
// reason / missing) are fed identically to both sides, so any divergence is a PORT bug. Both paths
// coexist here (PR 3 deletes the in-memory oracle once the decider path is the only path).
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const shell = require('../review_panel_shell.js')
const roundPolicy = require('../review_round_policy.js')
const { defaultIo } = require('../io_seam.js')

const PY = path.join(__dirname, '..', 'review_loop_plan.py')
const ROSTER = ['code-reviewer', 'security-reviewer']

function runDecider(args) {
  const { execFileSync } = require('child_process')
  const out = execFileSync('python3', [PY, ...args], { encoding: 'utf8' })
  return JSON.parse(out)
}

// A durable skeleton round (the shape summarize_record persists). Findings carry only identity/class.
function rec(round, { kind = 'baseline', dims, findings = [], changedSubjects = ['Code'],
  coverage = [], confirmationPending = false } = {}) {
  const dimObj = {}
  for (const [name, spec] of Object.entries(dims)) {
    dimObj[name] = Object.assign({ dimension: name, status: 'run', confidence: 'high',
      tier: 'reviewer-deep', subjects: ['Code'], findings: spec.findings || [],
      hasFindings: (spec.findings || []).length > 0 }, spec)
  }
  return { schemaVersion: 2, round, kind, confirmationPending, changedSubjects,
    coverageDecisions: coverage, tokenUsage: { available: true }, carriedFindings: [],
    findings, dimensions: dimObj }
}

function writeRecords(records) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'equiv-'))
  fs.writeFileSync(path.join(dir, 'round-records.json'), JSON.stringify(records))
  return dir
}

// ── plan-round equivalence: schedule + carried + enterConfirmation ──
function assertPlanEquivalent(records, round, changedSubjects, justMarked, label) {
  const dir = writeRecords(records)
  const recordsPath = path.join(dir, 'round-records.json')
  // NEW: the decider.
  const decided = runDecider(['plan-round', '--path', recordsPath, '--round', String(round),
    '--dimensions', JSON.stringify(ROSTER),
    ...(changedSubjects !== undefined ? ['--changed-subjects', JSON.stringify(changedSubjects)] : []),
    ...(justMarked ? ['--just-marked'] : [])])
  // OLD: the in-memory oracle.
  const enterConfirmation = shell.confirmationReady(records, round, justMarked)
  const plan = roundPolicy.planRound({ round, dimensions: ROSTER, changedSubjects,
    previous: shell.buildPreviousDimensionState(records), confirmation: enterConfirmation })
  const carried = {}
  for (const [name, sched] of Object.entries(plan.dimensions || {})) {
    if (sched.action === 'skip') carried[name] = shell.carryForwardDimension(records, name, sched)
  }
  assert.strictEqual(decided.enterConfirmation, enterConfirmation, `${label}: enterConfirmation`)
  assert.strictEqual(decided.roundKind, plan.roundKind, `${label}: roundKind`)
  assert.deepStrictEqual(decided.dimensions, plan.dimensions || {}, `${label}: schedule`)
  assert.deepStrictEqual(decided.carried, carried, `${label}: carried`)
}

// ── tally-round equivalence: terminal + reason + breaker + certification + uncertified ──
function assertTallyEquivalent(records, round, scalars, label) {
  const dir = writeRecords(records)
  const recordsPath = path.join(dir, 'round-records.json')
  const deferredPath = path.join(dir, 'deferred-set.json')
  const deferredSet = scalars.deferredSet || {}
  fs.writeFileSync(deferredPath, JSON.stringify(deferredSet))
  const args = ['tally-round', '--path', recordsPath, '--round', String(round),
    '--roster', JSON.stringify(ROSTER), '--max-rounds', String(scalars.maxRounds || 7),
    '--gate', scalars.gate, '--confidence', scalars.confidence || 'high',
    '--missing', JSON.stringify(scalars.missing || []),
    '--present-blocking', String(scalars.presentBlocking || 0),
    '--deferred-path', deferredPath, '--fix-status', scalars.fixStatus || 'completed']
  if (scalars.verifyResult != null) args.push('--verify-result', String(scalars.verifyResult))
  if (scalars.enterConfirmation) args.push('--enter-confirmation')
  if (scalars.uncertifiedReason) args.push('--uncertified-reason', scalars.uncertifiedReason)
  const decided = runDecider(args)
  const oracle = shell.tallyTerminalInMemory({ records, round, roster: ROSTER,
    maxRounds: scalars.maxRounds || 7, gate: scalars.gate, confidence: scalars.confidence || 'high',
    presentBlocking: scalars.presentBlocking || 0, deferredSet, fixStatus: scalars.fixStatus || 'completed',
    verifyResult: scalars.verifyResult != null ? scalars.verifyResult : null,
    enterConfirmation: !!scalars.enterConfirmation, uncertifiedReason: scalars.uncertifiedReason || null,
    missing: scalars.missing || [] })
  assert.strictEqual(decided.terminal, oracle.terminal, `${label}: terminal`)
  assert.strictEqual(decided.reason, oracle.reason, `${label}: reason`)
  assert.strictEqual(!!decided.uncertified, !!oracle.uncertified, `${label}: uncertified flag`)
  assert.deepStrictEqual(decided.breaker, oracle.breaker, `${label}: breaker verdict + detail`)
  assert.strictEqual(decided.presentDeferred, oracle.presentDeferred, `${label}: present-deferred`)
  assert.deepStrictEqual(decided.certification, oracle.certification, `${label}: certification`)
}

function main() {
  const CRIT = { file: 'a.py', line: 1, title: 'unbounded loop', severity: 'Critical',
    dimension: 'Code', classKey: 'Code::bug::unbounded loop' }
  const cleanDims = { 'code-reviewer': {}, 'security-reviewer': {} }

  // entry-bootstrap equivalence (resume round + markers).
  {
    const records = [rec(1, { dims: cleanDims }),
      rec(2, { kind: 'confirmation', dims: cleanDims, confirmationPending: true })]
    const dir = writeRecords(records)
    const decided = runDecider(['entry-bootstrap', '--path', path.join(dir, 'round-records.json'),
      '--dimensions', JSON.stringify(ROSTER)])
    assert.strictEqual(decided.round, shell.resumeRound(records), 'entry: resume round')
    assert.strictEqual(decided.markedRound, 2, 'entry: marked round')
    assert.strictEqual(decided.confirmationPending, true, 'entry: confirmationPending')
  }

  // plan-round: baseline (round 1), intermediate skip (round 2 over changedSubjects), resume-confirmation.
  assertPlanEquivalent([], 1, undefined, false, 'plan baseline')
  assertPlanEquivalent(
    [rec(1, { dims: { 'code-reviewer': { findings: [CRIT] }, 'security-reviewer': { findings: [] } },
      findings: [CRIT] })], 2, ['Code'], false, 'plan intermediate skip')
  assertPlanEquivalent(
    [rec(1, { dims: cleanDims, confirmationPending: true })], 2, ['Code'], false, 'plan resume-confirmation')
  assertPlanEquivalent(
    [rec(1, { dims: cleanDims, confirmationPending: true })], 2, ['Code'], true, 'plan just-marked')

  // tally-round: clean+cert, blocking→continue, recurring→breaker halt, cannot-certify+named reason,
  // confirmation-owed, verify-fail, deferred blocker.
  assertTallyEquivalent([rec(1, { dims: cleanDims })], 1, { gate: 'clean' }, 'tally clean')
  assertTallyEquivalent(
    [rec(1, { dims: { 'code-reviewer': { findings: [CRIT] }, 'security-reviewer': {} }, findings: [CRIT] })],
    1, { gate: 'blocking', presentBlocking: 1 }, 'tally blocking')
  assertTallyEquivalent(
    [rec(1, { dims: { 'code-reviewer': { findings: [CRIT] } }, findings: [CRIT] }),
      rec(2, { dims: { 'code-reviewer': { findings: [CRIT] } }, findings: [CRIT] })],
    2, { gate: 'blocking', presentBlocking: 1 }, 'tally recurring-halt')
  assertTallyEquivalent([rec(1, { dims: cleanDims })], 1,
    { gate: 'cannot-certify', confidence: 'low', presentBlocking: 0,
      uncertifiedReason: 'code-reviewer: receipt-missing — uncertifiable', missing: ['x'] }, 'tally named-reason')
  assertTallyEquivalent(
    [rec(1, { dims: cleanDims, confirmationPending: true }),
      rec(2, { kind: 'intermediate', dims: cleanDims })],
    2, { gate: 'clean', enterConfirmation: false }, 'tally confirmation-owed')
  assertTallyEquivalent([rec(1, { dims: cleanDims })], 1,
    { gate: 'clean', verifyResult: 'fail' }, 'tally verify-fail')

  // synthesisUnverified asymmetry (the subtle #211 parity branch): a no-location finding synthesis
  // could not verify is EXCLUDED from the CURRENT round's breaker + present-deferred but KEPT for
  // prior-round recurrence. present-blocking still counts it (rides down from the live answer). The
  // deepStrictEqual on breaker + presentDeferred pins that decider and oracle filter it identically —
  // this kills the mutant where the decider drops the filter or applies it to recurrence too.
  const UNVER = Object.assign({}, CRIT, { file: null, line: null, synthesisUnverified: true })
  assertTallyEquivalent(
    [rec(1, { dims: { 'code-reviewer': { findings: [CRIT] } }, findings: [CRIT] }),
      rec(2, { dims: { 'code-reviewer': { findings: [UNVER] } }, findings: [UNVER] })],
    2, { gate: 'blocking', presentBlocking: 1 }, 'tally synthesisUnverified asymmetry')

  // deferred-set skip path: a present blocker whose identity is deferred — decider and oracle must
  // agree on present-deferred, the terminal, and the breaker input once the deferred blocker is skipped.
  const circuitBreaker = require('../circuit_breaker.js')
  assertTallyEquivalent(
    [rec(1, { dims: { 'code-reviewer': { findings: [CRIT] }, 'security-reviewer': {} }, findings: [CRIT] })],
    1, { gate: 'clean', presentBlocking: 1, deferredSet: { [circuitBreaker.findingIdentity(CRIT)]: 'Critical' } },
    'tally deferred-skip')

  console.log('ok: the review-loop deciders are behavior-equivalent to the in-memory oracle (#211 Phase 4a)')
}

main()
