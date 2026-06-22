// plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js
const assert = require('assert')
global.parallel = (thunks) => Promise.all(thunks.map((t) => t()))
global.agent = async (p) => {
  if (p.includes('panel_tally')) return { gate: 'blocking', confidence: 'high', findings: [{ severity: 'Important' }], terminal: 'halted' }
  if (p.includes('phase_step_cli.py')) return p.includes('changes-requested')
    ? { action: 'park_changes_requested', reason: 'review requested changes' }
    : { action: 'proceed', reason: 'ok' }
  if (p.includes('journal')) return { ok: true }
  return { confidence: 'high', assumptions: [] }       // phase leaves
}
global.log = () => {}
const sr = require('../showrunner.js')
;(async () => {
  const gate = sr.verdictToGate({ gate: 'blocking', terminal: 'halted' })
  assert.strictEqual(gate, 'changes-requested')
  console.log('OK: blocking panel verdict maps to changes-requested')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
