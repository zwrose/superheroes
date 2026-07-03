require('./_smoke_checkout_root.js')
const assert = require('assert')

function run(plan) {
  const counts = { checks: 0 }
  global.agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/wt', expectedHead: 'head0' }) }]
    }
    if (label === 'exec' && _prompt.includes('fence_cli.py')) return JSON.stringify({ ok: true })
    if (label === 'check ship-readiness') {
      const checks = plan.checksSeq[Math.min(counts.checks, plan.checksSeq.length - 1)]
      counts.checks += 1
      return [{ ok: true, stdout: JSON.stringify({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, fence: { ok: true }, integrated: false, checks }) }]
    }
    if (label === 'prepare CI fix') {
      return [{ ok: true, stdout: JSON.stringify(plan.ciDecide || { action: 'fix', ok: true, read_back: true }) }]
    }
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      if (plan.fixPush === 'dirty') {
        return [{ ok: true, stdout: JSON.stringify({ ok: false, pushed: false, read_back: false, reason: 'crashed fixer' }) }]
      }
      const checks = plan.checksSeq[Math.min(counts.checks, plan.checksSeq.length - 1)]
      counts.checks += 1
      return [{ ok: true, stdout: JSON.stringify({ ok: true, pushed: true, read_back: true, checks }) }]
    }
    if (label === 'exec' && _prompt.includes('revert-draft')) {
      return { ok: plan.revertDraft !== 'fail', reason: plan.revertDraft === 'fail' ? 'gh timeout' : 'reverted to draft' }
    }
    if (label === 'post readout') return [{ ok: true, stdout: JSON.stringify({ posted: true, recorded: false }) }]
    throw new Error('unexpected label=' + label)
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), counts }
}

;(async () => {
  let { sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]], ciDecide: { action: 'fix', ok: true, read_back: true } })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'red->fix->green -> ready')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: { action: 'revert_and_gate', ok: true, read_back: true } }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate -> parked')
  assert.ok(/pass|draft|check/i.test(out.reason), 'park reason explains the checks could not pass')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: { action: 'fix', ok: true, read_back: true }, fixPush: 'dirty' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'dirty fix-push -> parked (no false ready)')
  assert.ok(/no false ready|could not push|park/i.test(out.reason), 'dirty fix-push park is honest (UFR-6)')

  ;({ sr, counts } = run({ checksSeq: [[]], ciDecide: { action: 'fix', ok: true, read_back: true } }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|did not run|confirm/i.test(out.reason), 'none names the honest carve-out (UFR-3)')

  ;({ sr, counts } = run({ checksSeq: [{ stale: true, local: 'abc', remote: 'old' }], ciDecide: { action: 'fix', ok: true, read_back: true } }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'stale rollup -> never ready (FR-5)')
  assert.ok(/did not complete|confirm CI/i.test(out.reason), 'stale -> honest "checks did not complete" hand-back')
  assert.ok(counts.checks >= 2, 'stale path re-waited (continue), not early-exit')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: { action: 'revert_and_gate', ok: true, read_back: true }, revertDraft: 'fail' }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate + failed draft-flip -> parked')
  assert.ok(/could NOT be returned to draft|set it to draft/i.test(out.reason), 'failed draft-flip surfaced honestly (P4)')

  ;({ sr, counts } = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: { action: 'fix', ok: false, read_back: false } }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'ci-record durable-write fail -> parked before push (UFR-5)')
  assert.ok(/record the CI-fix round|durable write/i.test(out.reason), 'park names the failed write-ahead')

  console.log('OK: cifix red->fix->ready, revert->park, dirty->park, none->honest-ready, stale->never-green, revert-fail->honest, record-fail->park')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
