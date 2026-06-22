// plugins/superheroes/lib/tests/showrunner_ship_smoke.js
const assert = require('assert')
global.agent = async (p) => {
  if (p.includes('freshness')) return { decision: 'up_to_date' }
  if (p.includes('ship_phase') && p.includes('ci')) return { decision: 'revert_and_gate', reason: 'CI-fix round cap reached' }
  if (p.includes('readout') || p.includes('pr_comment')) return { ok: true }
  throw new Error('unexpected agent: ' + p.slice(0, 40))
}
global.log = () => {}
const sr = require('../showrunner.js')
;(async () => {
  const out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'parked')
  assert.ok(/CI/.test(out.reason))
  console.log('OK: ship parks (not merge-ready) when CI cannot go green')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
