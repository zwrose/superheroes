// Smoke: #394 — the whole-branch final-review leg (legKind.panel:false) schedules its ONE honest
// dispatch tier, so a post-baseline round with prior findings does NOT arm the cheap-first escalation
// into a byte-identical re-dispatch. The escalation MUST still fire on the per-task panel legs
// (legKind.panel:true), where the reviewerAgent genuinely honors opts.tier and cheap->deep is a real
// upgrade. Drives reviewPanel through a baseline round -> fix -> post-baseline round, counting the
// reviewer dispatches in the post-baseline round. Reviewer leaves return a BARE findings[] array (the
// build_phase whole-branch leg's legacy-array shape — the exact input _shapeReviewerResult stamps
// confidence 'low' at tier 'reviewer', arming the escalation branch). Local gate (CI runs pytest, not
// JS). Run: node plugins/superheroes/lib/tests/showrunner_final_review_tier_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
global.recordDeferred = async () => {}
// The panel:false leg is code:true (verifyCommand 'none'); verifyAgent's dumb courier answers a
// skipped verify. No other agent() call happens on these paths.
global.agent = async (_prompt, opts) => {
  if (opts && opts.label === 'run verify') return { result: 'skipped' }
  return null
}

function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'finalrev394-')) }

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Critical', evidence: 'x' }]

// A reviewerAgent that returns a bare findings[] array (legacy-array shape) and records every
// dispatch's (round, tier, escalatedFrom) so the test can count re-dispatches per round.
function trackingReviewer(dispatches, findingsByRound) {
  return async (_r, _c, _rub, _runDir, round, opts) => {
    dispatches.push({ round, tier: (opts || {}).tier, escalatedFrom: (opts || {}).escalatedFrom })
    const f = findingsByRound[round]
    return Array.isArray(f) ? f : BLOCKER
  }
}

function dispatchesForRound(dispatches, round) { return dispatches.filter((d) => d.round === round) }

async function main() {
  // 1) The whole-branch final-review leg (panel:false) declares dispatchTier 'reviewer-deep'. A
  //    post-baseline round (round 2) whose prior round had findings is scheduled CHEAP by the round
  //    policy, but the leg's declared tier overrides it to reviewer-deep -> _shapeReviewerResult
  //    stamps the findings-bearing answer 'high' -> the escalation branch never arms -> exactly ONE
  //    reviewer dispatch, at reviewer-deep, and its findings become the round record.
  {
    const dir = freshDir()
    const dispatches = []
    global.reviewerAgent = trackingReviewer(dispatches, { 1: BLOCKER, 2: BLOCKER })
    await reviewPanel({
      reviewerSet: ['generalist'], context: { workItem: 'wi', branch: 'b' }, rubric: 'review-base',
      runKey: dir, runDir: dir,
      fixStep: async () => ({ fixed: ['a.py::bug'], changedSubjects: ['Code'], coverageDecisions: [] }),
      maxRounds: 2, legKind: { panel: false, code: true, dispatchTier: 'reviewer-deep' }, verifyCommand: 'none',
    })
    const r2 = dispatchesForRound(dispatches, 2)
    assert.strictEqual(r2.length, 1, `panel:false post-baseline round must dispatch the reviewer exactly ONCE, got ${r2.length}: ${JSON.stringify(r2)}`)
    assert.strictEqual(r2[0].tier, 'reviewer-deep', `the single dispatch must be scheduled at reviewer-deep (its honest tier), got ${r2[0].tier}`)
    assert.strictEqual(r2[0].escalatedFrom, undefined, 'the single dispatch must NOT be an escalation re-dispatch')
    // Baseline round unchanged: exactly one deep dispatch.
    const r1 = dispatchesForRound(dispatches, 1)
    assert.strictEqual(r1.length, 1, `baseline round dispatches the reviewer once, got ${r1.length}`)
    assert.strictEqual(r1[0].tier, 'reviewer-deep', 'baseline round is deep')
  }

  // 2) Control — the per-task panel legs (panel:true, NO dispatchTier) keep cheap-first escalation.
  //    The same post-baseline round is scheduled CHEAP ('reviewer'); a findings-bearing legacy array
  //    is stamped 'low' and escalates to reviewer-deep: TWO dispatches in the post-baseline round.
  {
    const dir = freshDir()
    const dispatches = []
    global.reviewerAgent = trackingReviewer(dispatches, { 1: BLOCKER, 2: BLOCKER })
    await reviewPanel({
      reviewerSet: ['code'], context: {}, rubric: 'review-base',
      runKey: dir, runDir: dir,
      fixStep: async () => ({ fixed: ['a.py::bug'], changedSubjects: ['Code'], coverageDecisions: [] }),
      maxRounds: 2, legKind: { panel: true, code: false },
    })
    const r2 = dispatchesForRound(dispatches, 2)
    assert.strictEqual(r2.length, 2, `panel:true post-baseline round must keep cheap-first escalation (2 dispatches), got ${r2.length}: ${JSON.stringify(r2)}`)
    assert.strictEqual(r2[0].tier, 'reviewer', 'first dispatch is the cheap tier')
    assert.strictEqual(r2[1].tier, 'reviewer-deep', 'escalated dispatch is reviewer-deep')
    assert.strictEqual(r2[1].escalatedFrom, 'reviewer', 'the second dispatch is a cheap->deep escalation')
  }

  console.log('ok: #394 final-review leg schedules its honest deep tier; per-task panels keep cheap-first escalation')
}

main().catch((e) => { console.error('FAIL:', e && e.stack || e); process.exit(1) })
