// plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js
require('./_smoke_checkout_root.js')
const assert = require('assert')
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(plan) {
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head' })
    if (opts && opts.courier && p.includes('fence_cli')) return JSON.stringify({ ok: plan.fence !== false })
    if (label === 'check ship-readiness') {
      if (plan.freshen === 'conflict') {
        return jsonOut({
          ok: false,
          fence: { ok: true },
          reconcile: { ok: true },
          freshness: { decision: 'conflict', reason: 'conflicts — aborted' },
          integrated: false,
          checks: { error: 'CI status could not be read' },
        })
      }
      const seq = plan.freshnessSeq || ['up_to_date']
      const decision = seq[0]
      if (decision === 'give_up_notify') {
        return jsonOut({
          ok: false,
          fence: { ok: true },
          reconcile: { ok: true },
          freshness: { decision: 'give_up_notify' },
          integrated: false,
          checks: { error: 'CI status could not be read' },
        })
      }
      if (decision === 'sync' && plan.fence === false) {
        return jsonOut({
          ok: false,
          fence: { ok: false, reason: 'lease lost' },
          reconcile: { ok: true },
          freshness: { decision: 'sync' },
          integrated: false,
          checks: { error: 'CI status could not be read' },
        })
      }
      const integrated = decision === 'sync' && plan.freshen === 'ok'
      return jsonOut({
        ok: true,
        fence: { ok: true },
        reconcile: { ok: true, head: integrated ? '/wt-head2' : '/wt-head', reason: 'in sync' },
        freshness: { decision: integrated ? 'up_to_date' : decision },
        integrated,
        checks: [{ name: 'ci', bucket: 'pass', state: 'success' }],
      })
    }
    if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  let sr = run({ freshnessSeq: ['sync', 'up_to_date'], freshen: 'ok', fence: true })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'sync then up_to_date + green -> ready')

  sr = run({ freshnessSeq: ['sync'], freshen: 'conflict', fence: true })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'freshen conflict -> parked')
  assert.ok(/conflict|resolve/i.test(out.reason), 'conflict park names the conflict')

  sr = run({ freshnessSeq: ['give_up_notify'], fence: true })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'give_up_notify -> parked (FR-2)')
  assert.ok(out.reason, 'give_up park carries a reason')

  sr = run({ freshnessSeq: ['sync'], freshen: 'ok', fence: false })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'lost fence -> parked before freshen')

  console.log('OK: catch-up sync->ready, conflict->park, give_up->park, lost-fence->park')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
