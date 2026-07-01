// plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js
const assert = require('assert')
function run(plan) {
  // plan: { freshnessSeq: [...decisions], freshen: 'ok'|'conflict', fence: true|false }
  let fi = 0
  let fenceCalls = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('fence_cli')) {
      fenceCalls += 1
      // entry fence (call 1) always passes; the loop fence honors plan.fence so the lost-fence
      // case tests the IN-LOOP fence (before the sync freshen), not the entry fence.
      if (fenceCalls === 1) return { ok: true }
      return { ok: plan.fence !== false }
    }
    if (label === 'lib' && p.includes('--step freshness')) { const d = plan.freshnessSeq[Math.min(fi++, plan.freshnessSeq.length - 1)]; return { decision: d } }
    if (label === 'lib' && p.includes('--step freshen')) {
      if (plan.freshen === 'conflict') return { ok: false, head: '/wt-head', conflict: true, reason: 'conflicts — aborted' }
      return { ok: true, head: '/wt-head2', conflict: false, reason: 'base integrated' }
    }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // sync once -> integrated -> up_to_date -> green -> ready (FR-1)
  let sr = run({ freshnessSeq: ['sync', 'up_to_date'], freshen: 'ok', fence: true })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'sync then up_to_date + green -> ready')

  // conflict on freshen -> park, never ready (UFR-1)
  sr = run({ freshnessSeq: ['sync'], freshen: 'conflict', fence: true })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'freshen conflict -> parked')
  assert.ok(/conflict|resolve/i.test(out.reason), 'conflict park names the conflict')

  // give_up_notify -> park (FR-2)
  sr = run({ freshnessSeq: ['give_up_notify'], fence: true })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'give_up_notify -> parked (FR-2)')
  assert.ok(out.reason, 'give_up park carries a reason')

  // lost fence before a sync push -> park before mutation (UFR-4)
  sr = run({ freshnessSeq: ['sync'], freshen: 'ok', fence: false })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'lost fence -> parked before freshen')

  console.log('OK: catch-up sync->ready, conflict->park, give_up->park, lost-fence->park')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
