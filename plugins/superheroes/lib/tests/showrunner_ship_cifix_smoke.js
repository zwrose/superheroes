const assert = require('assert')
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(plan) {
  const counts = { ci: 0, stale: 0 }
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head' })
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'check ship-readiness') {
      if (p.includes('--checks-only')) {
        counts.stale += 1
        const c = plan.checksSeq[Math.min(counts.ci, plan.checksSeq.length - 1)]
        return jsonOut({ checks: (c && c.stale && counts.stale < 6) ? c : [{ name: 'ci', bucket: 'pass', state: 'success' }] })
      }
      const c = plan.checksSeq[Math.min(counts.ci++, plan.checksSeq.length - 1)]
      return jsonOut({
        ok: true,
        reconcile: { ok: true, head: '/wt-head', reason: 'in sync' },
        freshness: { decision: 'up_to_date' },
        integrated: false,
        checks: c,
      })
    }
    if (label === 'prepare CI fix') {
      return jsonOut({
        action: plan.ciDecide,
        round: 1,
        reason: 'r',
        ok: plan.ciRecord !== 'fail',
        read_back: plan.ciRecord !== 'fail',
      })
    }
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      if (plan.fixPush === 'dirty') {
        return jsonOut({ ok: false, pushed: false, read_back: false, checks: { error: 'x' }, reason: 'crashed fixer' })
      }
      const next = plan.checksSeq[Math.min(counts.ci, plan.checksSeq.length - 1)]
      return jsonOut({ ok: true, pushed: true, read_back: true, head: '/wt-head2', checks: next, reason: 'fix pushed' })
    }
    if (label === 'lib' && p.includes('--step revert-draft')) {
      return plan.revertDraft === 'fail' ? { ok: false, reason: 'gh timeout' } : { ok: true, reason: 'reverted to draft' }
    }
    if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), counts }
}
;(async () => {
  let { sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]], ciDecide: 'fix', fixPush: 'ok' })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'red->fix->green -> ready')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'revert_and_gate', fixPush: 'ok' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate -> parked')
  assert.ok(/pass|draft|check/i.test(out.reason), 'park reason explains the checks could not pass')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'fix', fixPush: 'dirty' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'dirty fix-push -> parked (no false ready)')
  assert.ok(/no false ready|could not push|park/i.test(out.reason), 'dirty fix-push park is honest (UFR-6)')

  ;({ sr, counts } = run({ checksSeq: [[]], ciDecide: 'fix', fixPush: 'ok' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|did not run|confirm/i.test(out.reason), 'none names the honest carve-out (UFR-3)')

  ;({ sr, counts } = run({ checksSeq: [{ stale: true, local: 'abc', remote: 'old' }], ciDecide: 'fix', fixPush: 'ok' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'stale rollup -> never ready (FR-5)')
  assert.ok(/did not complete|confirm CI/i.test(out.reason), 'stale -> honest "checks did not complete" hand-back')
  assert.ok(counts.stale >= 1, 'stale path re-waited (continue), not early-exit')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'revert_and_gate', revertDraft: 'fail' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate + failed draft-flip -> parked')
  assert.ok(/could NOT be returned to draft|set it to draft/i.test(out.reason), 'failed draft-flip surfaced honestly (P4)')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'fix', ciRecord: 'fail' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'ci-record durable-write fail -> parked before push (UFR-5)')
  assert.ok(/record the CI-fix round|durable write/i.test(out.reason), 'park names the failed write-ahead')

  console.log('OK: cifix red->fix->ready, revert->park, dirty->park, none->honest-ready, stale->never-green, revert-fail->honest, record-fail->park')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
