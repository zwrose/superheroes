// plugins/superheroes/lib/tests/showrunner_phaseloop_smoke.js
const assert = require('assert')
// Stub the seams: phase leaf returns an assumption on the 2nd phase; decide forwards.
let phaseCalls = 0
global.agent = async (prompt) => {
  if (prompt.includes('phase_step_cli.py')) {
    // echo the decision the python decider would make for the captured phase_result
    return prompt.includes('["boom"]')
      ? { action: 'park_assumption', reason: 'assumption' }
      : { action: 'proceed', reason: 'ok' }
  }
  if (prompt.includes('journal')) return { ok: true }
  if (prompt.includes('PHASE_LEAF')) {
    phaseCalls += 1
    return phaseCalls === 2
      ? { confidence: 'high', assumptions: ['boom'] }
      : { confidence: 'high', assumptions: [] }
  }
  throw new Error('unexpected agent: ' + prompt.slice(0, 40))
}
global.log = () => {}
const sr = require('../showrunner.js')
;(async () => {
  const out = await sr.runPhases('wi', 0, { phaseLeaf: async () => agent('PHASE_LEAF') })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.reason, 'assumption')
  console.log('OK: park_assumption on the 2nd phase')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
