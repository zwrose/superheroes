require('./_smoke_checkout_root.js')
const assert = require('assert')
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(capture, opts) {
  const integrated = !!(opts && opts.integrated)
  global.agent = async (p, o) => {
    const label = (o && o.label) || ''
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head' })
    if (o && o.courier && p.includes('fence_cli')) return JSON.stringify({ ok: true })
    if (label === 'check ship-readiness') {
      return jsonOut({
        ok: true,
        reconcile: { ok: true, head: '/wt-head', reason: 'in sync' },
        freshness: { decision: 'up_to_date' },
        integrated,
        checks: [{ name: 'ci', bucket: 'pass', state: 'success' }],
      })
    }
    if (label === 'post readout') {
      capture.ctxSeen = /--ctx/.test(p)
      capture.ctxText = p
      return jsonOut({ posted: true, recorded: true })
    }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  const capture = {}
  const sr = run(capture)
  const out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready via structured hand-back')
  assert.ok(capture.ctxSeen, 'hand-back posts a STRUCTURED ctx (--ctx), not a one-line reason (FR-6)')
  assert.ok(
    !/integration|post-review|check-vetted/i.test(capture.ctxText || ''),
    'no integration note when not integrated (FR-7 iff)'
  )

  const capture2 = {}
  const sr2 = run(capture2, { integrated: true })
  const out2 = await sr2.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out2.outcome, 'ready', 'integrated run -> ready')
  assert.ok(capture2.ctxSeen, 'integrated hand-back posts --ctx (FR-6)')
  assert.ok(
    capture2.ctxText && /integration|post-review|check-vetted/i.test(capture2.ctxText),
    'FR-7: integration note present in readout_post --ctx payload when integrated=true'
  )

  global.agent = (orig => async (p, o) => {
    const label = (o && o.label) || ''
    if (label === 'post readout') return jsonOut({ posted: false, recorded: false, error: 'disk full' })
    return orig(p, o)
  })(global.agent)
  delete require.cache[require.resolve('../showrunner.js')]
  const sr3 = require('../showrunner.js')
  const out3 = await sr3.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out3.outcome, 'ready', 'undelivered hand-back still reports ready (best-effort, not ship-gated)')
  assert.ok(/warning|deliver/i.test(out3.reason), 'undelivered hand-back is surfaced as a warning')
  console.log('OK: structured hand-back ctx + FR-7 integration note + best-effort delivery')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
