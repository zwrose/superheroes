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
    // exec batches; return ok for any batch (journal, checkpoint, set-gate, etc.)
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  if (label === 'lib') {
    // phase_step_cli.py must NOT be dispatched (it is now the in-process JS twin).
    if (p.includes('phase_step_cli')) throw new Error('phase_step_cli dispatched as agent — must use JS twin')
    if (p.includes('journal_entry')) return { ok: true }
    if (p.includes('checkpoint_entry') && p.includes('--read-pr')) return { pr: PR }
    if (p.includes('checkpoint_entry')) return { ok: true }
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
    // NO frontHalfBoundary -> the loop runs the full pipeline into ship (the real shipPhase)
  }
  const out = await sr.runPhases('wi', 0, deps)
  assert.strictEqual(out.outcome, 'ready', 'full pipeline must reach a ready-for-review outcome')
  assert.strictEqual(out.phase, 'ship')
  console.log('OK: full pipeline reaches a ready-for-review outcome (phaseStep is JS twin)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
