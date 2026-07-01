// plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js
const assert = require('assert')
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(script) {
  let ci = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head' })
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'check ship-readiness') {
      const integrated = script.freshness && script.freshness[0] === 'sync'
      const checks = script.checks[Math.min(ci++, script.checks.length - 1)]
      return jsonOut({
        ok: true,
        reconcile: { ok: true, head: '/wt-head', reason: 'in sync' },
        freshness: { decision: 'up_to_date' },
        integrated,
        checks,
      })
    }
    if (label === 'prepare CI fix') return jsonOut(script.ciDecide)
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      return jsonOut({ ok: true, pushed: true, read_back: true, head: '/wt-head3', checks: script.checks[1] || [{ name: 'ci', bucket: 'pass', state: 'success' }], reason: 'fix pushed' })
    }
    if (label === 'lib' && p.includes('--step revert-draft')) return { ok: true, reason: 'reverted to draft' }
    if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  let sr = run({ freshness: ['sync', 'up_to_date'],
                 checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]],
                 ciDecide: { action: 'fix', round: 1, reason: 'r', ok: true, read_back: true } })
  let out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'ready', 'walkthrough catch-up + fix -> ready')

  sr = run({ freshness: ['up_to_date'], checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]],
             ciDecide: { action: 'revert_and_gate', round: 5, reason: 'cap', ok: true, read_back: true } })
  out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'parked', 'walkthrough terminal fail -> draft + parked')
  console.log('OK: forged-ship walkthrough catch-up+fix->ready, terminal->draft')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
