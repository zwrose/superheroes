// plugins/superheroes/lib/tests/showrunner_fullpipeline_smoke.js
// #115 Task 12: phaseStep is the JS twin (in-process). appendPhaseRecord (journal_entry) and
// recordCursor (checkpoint_entry) still use cmdRunner (lib) until their conversion.
// ship-phase IO (freshness, ci, readout_post) remain cmdRunner (lib) — back-half, out of scope.
const assert = require('assert')
const PR = { number: 1, url: 'https://github.com/o/r/pull/1', isDraft: true }
global.log = () => {}
global.agent = async (p, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'exec') {
    // ship CI now reads raw checks via exec (--emit-checks); the JS twin classifies in-process.
    // Return a real GREEN check array so the pipeline reaches a merge-ready outcome. (A bare '' here
    // is NOT valid JSON and — post #115 fail-closed fix — would PARK as an unreadable CI read, so
    // the emit-checks batch must echo parseable JSON, not the empty-stdout used for fire-and-forget
    // journal/checkpoint/set-gate batches below.)
    if (p.includes('emit-checks')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    }
    // resolveBuildTarget (Task 7): build_entry.py needs path+outcome; rev-parse needs a sha.
    if (p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head-sha' }]
    // other exec batches (journal, checkpoint, set-gate, etc.); stdout unused.
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  if (label === 'lib') {
    // phase_step_cli.py must NOT be dispatched (it is now the in-process JS twin).
    if (p.includes('phase_step_cli')) throw new Error('phase_step_cli dispatched as agent — must use JS twin')
    if (p.includes('journal_entry')) return { ok: true }
    if (p.includes('checkpoint_entry') && p.includes('--read-pr')) return { pr: PR }
    if (p.includes('checkpoint_entry')) return { ok: true }
    // Task 7: fence_cli and reconcile-head must be checked before the generic ship_phase+ci guard
    // below ('reconcile' contains the substring 'ci', which would otherwise match the wrong branch).
    if (p.includes('fence_cli')) return { ok: true }
    if (p.includes('reconcile-head')) return { ok: true, head: '/wt-head-sha', reason: 'in sync' }
    if (p.includes('ship_phase') && p.includes('freshness')) return { decision: 'up_to_date' }
    if (p.includes('ship_phase') && p.includes('ci')) return { decision: 'green' }
    if (p.includes('readout_post')) return { posted: true }
    return { ok: true }
  }
  throw new Error('unexpected agent: label=' + label + ' ' + p.slice(0, 50))
}
const sr = require('../showrunner.js')
;(async () => {
  const ok = { confidence: 'high', assumptions: [] }
  const deps = {
    produce: async () => ok,                                            // plan / tasks (native authoring)
    reviewDoc: async () => ({ phaseResult: ok, gate: 'passed' }),        // review-plan / review-tasks
    build: async () => ok,                                              // workhorse
    reviewCode: async () => ({ phaseResult: ok, gate: 'passed' }),      // review-code
    draftPR: async () => ({ phaseResult: ok, sideEffect: { pr: PR } }), // draft-PR
    testPilot: async () => ok,                                         // test-pilot
    markReady: async () => ({ phaseResult: ok, sideEffect: { ready: true } }), // mark-ready
    gateRead: async () => null,
    generation: 5, // Task 7: shipPhase is fail-closed on null generation (UFR-4); must supply one.
    // NO frontHalfBoundary -> the loop runs the full pipeline into ship (the real shipPhase)
  }
  const out = await sr.runPhases('wi', 0, deps)
  assert.strictEqual(out.outcome, 'ready', 'full pipeline must reach a ready-for-review outcome')
  assert.strictEqual(out.phase, 'ship')
  console.log('OK: full pipeline reaches a ready-for-review outcome (phaseStep is JS twin)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
