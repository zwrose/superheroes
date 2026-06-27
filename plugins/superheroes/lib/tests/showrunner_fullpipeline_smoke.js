// plugins/superheroes/lib/tests/showrunner_fullpipeline_smoke.js
const assert = require('assert')
const PR = { number: 1, url: 'https://github.com/o/r/pull/1', isDraft: true }
global.log = () => {}
global.agent = async (p) => {
  if (p.includes('journal_entry')) return { ok: true }              // appendPhaseRecord
  if (p.includes('phase_step_cli')) return { action: 'proceed' }    // phaseStep decider
  if (p.includes('checkpoint_entry') && p.includes('--read-pr')) return { pr: PR }   // loadPr
  if (p.includes('checkpoint_entry')) return { ok: true }           // recordCursor
  if (p.includes('ship_phase') && p.includes('freshness')) return { decision: 'up_to_date' }
  if (p.includes('ship_phase') && p.includes('ci')) return { decision: 'green' }     // green -> ready
  if (p.includes('readout_post')) return { posted: true }
  throw new Error('unexpected agent cmd: ' + p.slice(0, 70))
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
  console.log('OK: full pipeline reaches a ready-for-review outcome (canned agents)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
