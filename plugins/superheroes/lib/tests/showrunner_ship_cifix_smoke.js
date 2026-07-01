const assert = require('assert')

function run(plan) {
  const counts = { checks: 0 }
  global.agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/wt', expectedHead: 'head0' }) }]
    }
    if (label === 'lib' && _prompt.includes('fence_cli.py')) return { ok: true }
    if (label === 'exec' && _prompt.includes('rev-parse')) return [{ index: 0, ok: true, stdout: 'head0' }]
    if (label === 'check ship-readiness') {
      const checks = plan.checksSeq[Math.min(counts.checks, plan.checksSeq.length - 1)]
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
      const checks = plan.checksSeq[Math.min(++counts.checks, plan.checksSeq.length - 1)]
      return [{ ok: true, stdout: JSON.stringify({ ok: true, pushed: true, read_back: true, checks }) }]
    }
    if (label === 'lib' && _prompt.includes('revert-draft')) {
      return { ok: plan.revertDraft !== 'fail', reason: plan.revertDraft === 'fail' ? 'gh timeout' : 'reverted to draft' }
    }
    if (label === 'post readout') return [{ ok: true, stdout: JSON.stringify({ posted: true, recorded: false }) }]
    throw new Error('unexpected label=' + label)
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}

;(async () => {
  let sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]], ciDecide: { action: 'fix', ok: true, read_back: true } })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready')

  sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: { action: 'revert_and_gate', ok: true, read_back: true } })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked')

  sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: { action: 'fix', ok: true, read_back: true }, fixPush: 'dirty' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked')

  sr = run({ checksSeq: [[]] })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready')
  assert.ok(/no required checks/i.test(out.reason))

  console.log('OK: ship cifix folded labels')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
