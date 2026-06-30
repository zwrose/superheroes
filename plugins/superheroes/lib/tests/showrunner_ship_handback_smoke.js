const assert = require('assert')
function run(capture) {
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'up_to_date' }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    if (label === 'lib' && (p.includes('readout_post') || p.includes('readout'))) { capture.ctxSeen = /--ctx/.test(p); return { posted: true } }
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

  // best-effort: even when delivery reports neither posted nor recorded, the run still reports ready,
  // and surfaces the undelivered warning (FR-6 / #118 carve-out: never ship-GATE on the hand-back).
  global.agent = (orig => async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'lib' && (p.includes('readout_post') || p.includes('readout'))) return { posted: false, recorded: false, error: 'disk full' }
    return orig(p, opts)
  })(global.agent)
  capture.ctxSeen = false
  delete require.cache[require.resolve('../showrunner.js')]
  const sr2 = require('../showrunner.js')
  const out2 = await sr2.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out2.outcome, 'ready', 'undelivered hand-back still reports ready (best-effort, not ship-gated)')
  assert.ok(/warning|deliver/i.test(out2.reason), 'undelivered hand-back is surfaced as a warning')
  console.log('OK: structured hand-back ctx + best-effort delivery')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
