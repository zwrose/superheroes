const assert = require('assert')
function run(capture, opts) {
  // opts.freshnessSeq: if provided, drives a catch-up loop (integrated path); otherwise direct up_to_date
  const freshnessSeq = (opts && opts.freshnessSeq) || null
  let fi = 0
  let fenceCalls = 0
  global.agent = async (p, o) => {
    const label = (o && o.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('fence_cli')) {
      fenceCalls += 1
      return { ok: true }
    }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) {
      if (freshnessSeq) { const d = freshnessSeq[Math.min(fi++, freshnessSeq.length - 1)]; return { decision: d } }
      return { decision: 'up_to_date' }
    }
    if (label === 'lib' && p.includes('--step freshen')) return { ok: true, head: '/wt-head2', conflict: false, reason: 'base integrated' }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    if (label === 'lib' && (p.includes('readout_post') || p.includes('readout'))) {
      capture.ctxSeen = /--ctx/.test(p)
      capture.ctxText = p
      return { posted: true }
    }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // case 1: non-integrated path (up_to_date without sync) — ctx present but no integration note
  const capture = {}
  const sr = run(capture)
  const out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready via structured hand-back')
  assert.ok(capture.ctxSeen, 'hand-back posts a STRUCTURED ctx (--ctx), not a one-line reason (FR-6)')
  assert.ok(
    !/integration|post-review|check-vetted/i.test(capture.ctxText || ''),
    'no integration note when not integrated (FR-7 iff)'
  )

  // case 2: integrated path (sync -> freshen -> up_to_date) — FR-7 integration note MUST appear in ctx
  // A mutant deleting `if (info.integrated)` in shipHandback would drop the note and fail this assertion.
  const capture2 = {}
  const sr2 = run(capture2, { freshnessSeq: ['sync', 'up_to_date'] })
  const out2 = await sr2.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out2.outcome, 'ready', 'integrated run (sync->up_to_date) -> ready')
  assert.ok(capture2.ctxSeen, 'integrated hand-back posts --ctx (FR-6)')
  assert.ok(
    capture2.ctxText && /integration|post-review|check-vetted/i.test(capture2.ctxText),
    'FR-7: integration note present in readout_post --ctx payload when integrated=true'
  )

  // case 3: best-effort: even when delivery reports neither posted nor recorded, the run still reports ready,
  // and surfaces the undelivered warning (FR-6 / #118 carve-out: never ship-GATE on the hand-back).
  global.agent = (orig => async (p, o) => {
    const label = (o && o.label) || ''
    if (label === 'lib' && (p.includes('readout_post') || p.includes('readout'))) return { posted: false, recorded: false, error: 'disk full' }
    return orig(p, o)
  })(global.agent)
  capture.ctxSeen = false
  delete require.cache[require.resolve('../showrunner.js')]
  const sr3 = require('../showrunner.js')
  const out3 = await sr3.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out3.outcome, 'ready', 'undelivered hand-back still reports ready (best-effort, not ship-gated)')
  assert.ok(/warning|deliver/i.test(out3.reason), 'undelivered hand-back is surfaced as a warning')
  console.log('OK: structured hand-back ctx + FR-7 integration note + best-effort delivery')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
