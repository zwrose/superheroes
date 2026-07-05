// plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js
require('./_smoke_checkout_root.js')
const assert = require('assert')
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(stub) {
  const calls = []
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    calls.push(label + ':' + p.slice(0, 40))
    const r = stub(label, p)
    if (r !== undefined) return r
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), calls }
}
function base(label, p) {
  if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head' })
  if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
  return undefined
}
;(async () => {
  let { sr } = run((label, p) => {
    if (label === 'fence lease') return JSON.stringify({ ok: true })
    if (label === 'check ship-readiness') {
      return jsonOut({ ok: false, reconcile: { ok: false, reason: 'remote head unreadable' }, freshness: {}, checks: {} })
    }
    return base(label, p)
  })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'unreadable reconcile -> parked (UFR-2)')

  let calls
  ;({ sr, calls } = run((label, p) => {
    if (label === 'fence lease') return JSON.stringify({ ok: false, reason: 'lease lost' })
    if (label === 'check ship-readiness') return jsonOut({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, checks: [] })
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'entry fence lost -> parked before the reconcile push (S1)')
  assert.ok(!calls.some((c) => c.startsWith('check ship-readiness')), 'entry fence parks BEFORE check ship-readiness runs')

  ;({ sr } = run((label, p) => {
    if (label === 'fence lease') return JSON.stringify({ ok: true })
    if (label === 'check ship-readiness') {
      return jsonOut({
        ok: false,
        fence: { ok: false, reason: 'lease lost' },
        reconcile: { ok: true },
        freshness: { decision: 'sync' },
        checks: { error: 'CI status could not be read' },
      })
    }
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'lost fence before catch-up -> parked (UFR-4)')

  let merged = false
  ;({ sr } = run((label, p) => {
    if (/gh pr merge|--merge\b|pr merge/.test(p)) merged = true
    if (label === 'fence lease') return JSON.stringify({ ok: true })
    if (label === 'check ship-readiness') {
      return jsonOut({
        ok: true,
        reconcile: { ok: true },
        freshness: { decision: 'up_to_date' },
        integrated: false,
        checks: [{ name: 'ci', bucket: 'pass', state: 'success' }],
      })
    }
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')
  assert.strictEqual(merged, false, 'FR-8: the ship path never merges the PR')
  console.log('OK: UFR-2 reconcile-park, S1 entry-fence, UFR-4 catch-up fence, FR-8 never-merge')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
