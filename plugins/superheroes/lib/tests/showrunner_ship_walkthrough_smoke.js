const assert = require('assert')

function run(script) {
  let checksIndex = 0
  global.agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/wt', expectedHead: 'head0' }) }]
    }
    if (label === 'lib' && _prompt.includes('fence_cli.py')) return { ok: true }
    if (label === 'exec' && _prompt.includes('rev-parse')) return [{ index: 0, ok: true, stdout: 'head0' }]
    if (label === 'check ship-readiness') {
      const checks = script.checks[Math.min(checksIndex, script.checks.length - 1)]
      return [{ ok: true, stdout: JSON.stringify({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, fence: { ok: true }, integrated: true, checks }) }]
    }
    if (label === 'prepare CI fix') return [{ ok: true, stdout: JSON.stringify(script.ciDecide) }]
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      checksIndex += 1
      const checks = script.checks[Math.min(checksIndex, script.checks.length - 1)]
      return [{ ok: true, stdout: JSON.stringify({ ok: true, pushed: true, read_back: true, checks }) }]
    }
    if (label === 'lib' && _prompt.includes('revert-draft')) return { ok: true, reason: 'reverted to draft' }
    if (label === 'post readout') return [{ ok: true, stdout: JSON.stringify({ posted: true, recorded: false }) }]
    throw new Error('unexpected label=' + label)
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}

;(async () => {
  let sr = run({
    checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]],
    ciDecide: { action: 'fix', ok: true, read_back: true },
  })
  let out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'ready')

  sr = run({
    checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]],
    ciDecide: { action: 'revert_and_gate', ok: true, read_back: true },
  })
  out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'parked')
  console.log('OK: forged-ship walkthrough folded labels')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
