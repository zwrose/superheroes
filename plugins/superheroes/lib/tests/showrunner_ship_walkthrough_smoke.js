// plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js
// Forged-ship DoD walkthrough: one run exercises catch-up, the fix-the-checks loop, return-to-draft,
// and the structured hand-back end-to-end with forged leaves.
const assert = require('assert')
function run(script) {
  let fi = 0, ci = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('--step freshness')) { const d = script.freshness[Math.min(fi++, script.freshness.length - 1)]; return { decision: d } }
    if (label === 'lib' && p.includes('--step freshen')) return { ok: true, head: '/wt-head2', conflict: false, reason: 'base integrated' }
    if (label === 'exec' && p.includes('--emit-checks')) { const c = script.checks[Math.min(ci++, script.checks.length - 1)]; return [{ index: 0, ok: true, stdout: JSON.stringify(c) }] }
    if (label === 'lib' && p.includes('--step ci-decide')) return script.ciDecide
    if (label === 'lib' && p.includes('--step ci-record')) return { ok: true }
    if (label === 'fix') return { fixed: true }
    if (label === 'lib' && p.includes('--step fix-push')) return { ok: true, head: '/wt-head3', pushed: true, reason: 'fix pushed' }
    if (label === 'lib' && p.includes('--step revert-draft')) return { ok: true, reason: 'reverted to draft' }
    if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // catch-up (sync->up_to_date) then fix-the-checks (red->fix->green) -> ready, FR-7 integration note.
  let sr = run({ freshness: ['sync', 'up_to_date'],
                 checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]],
                 ciDecide: { action: 'fix', round: 1, reason: 'r' } })
  let out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'ready', 'walkthrough catch-up + fix -> ready')

  // terminal: red -> revert_and_gate -> draft + hand-back park.
  sr = run({ freshness: ['up_to_date'], checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]],
             ciDecide: { action: 'revert_and_gate', round: 5, reason: 'cap' } })
  out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'parked', 'walkthrough terminal fail -> draft + parked')
  console.log('OK: forged-ship walkthrough catch-up+fix->ready, terminal->draft')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
