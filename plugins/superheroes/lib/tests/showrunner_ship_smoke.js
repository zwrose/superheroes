// plugins/superheroes/lib/tests/showrunner_ship_smoke.js
const assert = require('assert')
function run(ciDecision, ciReason) {
  global.agent = async (p) => {
    if (p.includes('freshness')) return { decision: 'up_to_date' }
    if (p.includes('ship_phase') && p.includes('ci')) return { decision: ciDecision, reason: ciReason }
    if (p.includes('readout') || p.includes('pr_comment') || p.includes('readout_post')) return { posted: true }
    throw new Error('unexpected agent: ' + p.slice(0, 40))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  let sr = run('green')
  let out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')

  sr = run('red', 'a required check failed')
  out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'parked', 'red -> parked')

  sr = run('none')
  out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|confirm/i.test(out.reason), 'none reason names the carve-out')
  console.log('OK: ship green->ready, red->park, none->ready-with-carve-out')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
