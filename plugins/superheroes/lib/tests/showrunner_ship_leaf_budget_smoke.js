const assert = require('assert')

function setup(checks, options) {
  options = options || {}
  const labels = []
  global.agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/wt', expectedHead: 'head0' }) }]
    }
    if (label === 'lib' && _prompt.includes('fence_cli.py')) return { ok: true }
    if (label === 'exec' && _prompt.includes('rev-parse')) return [{ index: 0, ok: true, stdout: 'head0' }]
    if (label === 'check ship-readiness') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, fence: { ok: true }, integrated: false, checks }) }]
    }
    if (label === 'prepare CI fix') return [{ ok: true, stdout: JSON.stringify({ action: 'fix', ok: true, read_back: true }) }]
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, pushed: true, read_back: true, checks: [{ name: 'ci', bucket: 'pass', state: 'success' }] }) }]
    }
    if (label === 'post readout') {
      return [{ ok: true, stdout: JSON.stringify({ posted: !options.postFail, recorded: false, error: options.postFail ? 'post failed' : undefined }) }]
    }
    throw new Error('unexpected label=' + label)
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  const sr = require('../showrunner.js')
  return { sr, labels }
}

;(async () => {
  let { sr, labels } = setup([{ name: 'ci', bucket: 'fail', state: 'failure' }])
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready')
  assert.deepStrictEqual(labels.filter((l) => [
    'check ship-readiness',
    'prepare CI fix',
    'fix-ci',
    'push CI fix + recheck',
    'post readout',
  ].includes(l)), [
    'check ship-readiness',
    'prepare CI fix',
    'fix-ci',
    'push CI fix + recheck',
    'post readout',
  ])

  ;({ sr, labels } = setup([{ name: 'ci', bucket: 'pass', state: 'success' }], { postFail: true }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready')
  assert.ok(/warning/i.test(out.reason))
  console.log('ok: ship leaf budget labels')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
