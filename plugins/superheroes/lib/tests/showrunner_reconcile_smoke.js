// plugins/superheroes/lib/tests/showrunner_reconcile_smoke.js
const assert = require('assert')
// Stub the cmdRunner-level lib calls by intercepting agent() (the only IO seam).
const responses = { reconcile: { action: 'park_gate', reason: 'wedged store' } }
global.agent = async (prompt) => {
  if (prompt.includes('recover_entry')) return responses.reconcile
  throw new Error('unexpected agent call: ' + prompt.slice(0, 40))
}
global.log = () => {}
const { showrunner } = require('../showrunner.js')
;(async () => {
  const out = await showrunner({ workItem: 'wi' })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.reason, 'wedged store')
  console.log('OK: reconcile park_gate -> parked')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
