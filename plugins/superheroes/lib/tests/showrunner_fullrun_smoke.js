// plugins/superheroes/lib/tests/showrunner_fullrun_smoke.js
// Drives runPhases (exported) with native authoring injected and frontHalfBoundary ABSENT,
// asserting it does NOT park at the front-half boundary at 'workhorse' but instead enters the
// build dep. The agent stub returns the lib-label cmdRunner shapes runPhases needs to advance
// (journal_entry/phase_step_cli/checkpoint_entry), mirroring showrunner_fronthalf_switch_smoke.js.
const assert = require('assert')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label !== 'lib') return null
  if (prompt.includes('journal_entry')) return { ok: true }
  if (prompt.includes('phase_step_cli')) return { action: 'proceed' }
  if (prompt.includes('checkpoint_entry')) return { ok: true, pr: null }
  return { ok: true }
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
  console.log('OK: full-run proceeds past the front-half boundary into build')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
