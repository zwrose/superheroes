// plugins/superheroes/lib/tests/showrunner_fullrun_smoke.js
// #115 Task 12: phaseStep is now the JS twin (in-process, no phase_step_cli.py dispatch).
// runPhases calls phase_step.decide() directly — no 'lib' label agent for phase_step_cli.
// #118: the per-phase tail is ONE 'save phase progress' courier (phase_progress_entry.py save) —
// journal_entry/checkpoint_entry never ride separate leaves.
require('./_smoke_checkout_root.js')
const assert = require('assert')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'save phase progress') {
    return JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  }
  if (label === 'exec') {
    // exec batches commands; return ok for any batch
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  if (label === 'lib') {
    if (prompt.includes('journal_entry') || prompt.includes('checkpoint_entry')) {
      throw new Error('journal_entry/checkpoint_entry must not ride separate cmdRunner leaves (#118 tail)')
    }
    // phase_step_cli.py must NOT be dispatched as an agent (it is now the in-process JS twin).
    if (prompt.includes('phase_step_cli')) throw new Error('phase_step_cli dispatched as agent — must use JS twin instead')
    return { ok: true }
  }
  return null
}
const sr = require('../showrunner.js')
;(async () => {
  let enteredBuild = false
  const deps = {
    produce: async () => ({ confidence: 'high', assumptions: [] }),
    reviewDoc: async () => ({ phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' }),
    // NO frontHalfBoundary -> must not park at the boundary
    build: async () => { enteredBuild = true; throw new Error('STOP_AT_BUILD') },
    gateRead: async () => null,
  }
  try { await sr.runPhases('wi', 0, deps) } catch (e) { if (e.message !== 'STOP_AT_BUILD') throw e }
  assert.ok(enteredBuild, 'full-run mode must proceed into the build phase, not park at the boundary')
  console.log('OK: full-run proceeds past the front-half boundary into build (phaseStep is JS twin)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
