const assert = require('assert')

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(plan) {
  const labels = []
  let staleReads = 0
  let checkIdx = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head' })
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'check ship-readiness') {
      if (p.includes('--checks-only')) {
        staleReads += 1
        return jsonOut({ checks: [{ name: 'ci', bucket: 'pass', state: 'success' }] })
      }
      const checks = plan.checksSeq[Math.min(checkIdx++, plan.checksSeq.length - 1)]
      return jsonOut({
        ok: true,
        reconcile: { ok: true, head: '/wt-head', reason: 'in sync' },
        freshness: { decision: 'up_to_date' },
        integrated: false,
        checks: checks && checks.stale ? { stale: true, local: 'abc', remote: 'old' } : checks,
      })
    }
    if (label === 'prepare CI fix') return jsonOut({ action: 'fix', round: 1, reason: 'r', ok: true, read_back: true })
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      return jsonOut({
        ok: true,
        pushed: true,
        read_back: true,
        head: '/wt-head2',
        checks: [{ name: 'ci', bucket: 'pass', state: 'success' }],
        reason: 'fix pushed and rechecked',
      })
    }
    if (label === 'post readout') {
      if (plan.readoutFail) return jsonOut({ posted: false, recorded: false, error: 'disk full' })
      return jsonOut({ posted: true, recorded: true })
    }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), labels }
}

;(async () => {
  const { sr, labels } = run({
    checksSeq: [
      [{ name: 'ci', bucket: 'fail', state: 'failure' }],
      [{ name: 'ci', bucket: 'pass', state: 'success' }],
    ],
  })
  const out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'ready')
  const budget = labels.filter((l) => [
    'check ship-readiness',
    'prepare CI fix',
    'fix-ci',
    'push CI fix + recheck',
    'post readout',
  ].includes(l))
  assert.deepStrictEqual(budget, [
    'check ship-readiness',
    'prepare CI fix',
    'fix-ci',
    'push CI fix + recheck',
    'post readout',
  ])

  const failPost = run({ checksSeq: [[{ name: 'ci', bucket: 'pass', state: 'success' }]], readoutFail: true })
  const parked = await failPost.sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(parked.outcome, 'ready')
  assert.ok(/warning|deliver/i.test(parked.reason), 'post readout failure surfaces warning, not false advancing write success')

  console.log('ok: ship leaf budget')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
