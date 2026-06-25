// plugins/superheroes/lib/tests/showrunner_workhorse_wire_smoke.js
const assert = require('assert')
global.log = () => {}
// Stub the Python bridge so the spine can record the phase + decide AFTER the workhorse leaf
// without reaching the real lib. The workhorse leaf is the `build` dep below; once it returns
// low confidence the spine parks at this phase, so we never need any later phase's lib call.
global.agent = async (prompt) => {
  if (prompt.includes('journal_entry.py')) return { ok: true }      // appendPhaseRecord
  if (prompt.includes('phase_step_cli.py')) return { action: 'park_low', reason: 'stop here' } // phaseStep -> park
  return {}
}
const sr = require('../showrunner.js')
;(async () => {
  let got = null
  const deps = {
    phaseLeaf: async () => ({ confidence: 'high', assumptions: [] }),
    gateRead: async () => null,
    build: async (wi, gen) => { got = { wi, gen }; return { confidence: 'low', assumptions: ['stop here'] } },
    generation: 7,
  }
  const idx = sr.PHASES.indexOf('workhorse')
  await sr.runPhases('wi', idx, deps)
  assert.deepStrictEqual(got, { wi: 'wi', gen: 7 }, 'workhorse phase must call build(workItem, generation)')
  console.log('ok: showrunner wires build_phase with the threaded generation')
})()
