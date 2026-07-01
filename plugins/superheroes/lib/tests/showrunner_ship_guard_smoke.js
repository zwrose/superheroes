// plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js
const assert = require('assert')
function run(stub) {
  const calls = []
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    calls.push(p)
    const r = stub(label, p)
    if (r !== undefined) return r
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), calls }
}
function base(label, p) {
  if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
  if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
  if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
  return undefined
}
;(async () => {
  // UFR-2: an unreadable entry reconcile -> park, never ready. (Entry fence passes, reconcile fails.)
  let { sr } = run((label, p) => {
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: false, reason: 'remote head unreadable' }
    return base(label, p)
  })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'unreadable reconcile -> parked (UFR-2)')

  // S1 / UFR-4: the ENTRY reconcile is itself fenced — a lost lease parks BEFORE the reconcile push,
  // so reconcile-head never even runs.
  let calls
  ;({ sr, calls } = run((label, p) => {
    if (label === 'lib' && p.includes('fence_cli')) return { ok: false, reason: 'lease lost' }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'entry fence lost -> parked before the reconcile push (S1)')
  assert.ok(!calls.some((c) => c.includes('reconcile-head')), 'entry fence parks BEFORE reconcile-head runs')

  // UFR-4 at the SECOND boundary: entry fence ok, then the catch-up (sync) fence is lost -> park.
  let fenceCalls = 0
  ;({ sr } = run((label, p) => {
    if (label === 'lib' && p.includes('fence_cli')) { fenceCalls += 1; return { ok: fenceCalls === 1 } }  // entry ok, next lost
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'sync' }
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'lost fence before the sync push -> parked (UFR-4, second boundary)')

  // FR-8: across the whole ship path, no leaf ever issues `gh pr merge` / a merge.
  let merged = false
  ;({ sr } = run((label, p) => {
    if (/gh pr merge|--merge\b|pr merge/.test(p)) merged = true
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'up_to_date' }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')
  assert.strictEqual(merged, false, 'FR-8: the ship path never merges the PR')
  console.log('OK: UFR-2 reconcile-park, S1 entry-fence, UFR-4 second-boundary fence, FR-8 never-merge')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
