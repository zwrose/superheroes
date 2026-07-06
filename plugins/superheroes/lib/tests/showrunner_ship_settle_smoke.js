// Ship-phase CI settle-wait (the live-run settle-poll deferred from #120; 0.10.0
// qualification finding: pending-as-red dispatched a CI fixer at checks that were merely
// running). Pending -> ONE bounded settle leaf -> settled checks re-enter the loop; a
// still-pending settle parks honestly; a red result still routes to the fixer.
require('./_smoke_checkout_root.js')
const assert = require('assert')

function run(plan) {
  const labels = []
  global.agent = async (_prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/wt', expectedHead: 'head0' }) }]
    }
    if (opts && opts.courier && _prompt.includes('fence_cli.py')) return JSON.stringify({ ok: true })
    if (label === 'check ship-readiness') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, fence: { ok: true }, integrated: false, checks: plan.firstChecks }) }]
    }
    if (label === 'wait for CI to settle') {
      assert.ok(_prompt.includes('ci_settle_cli.py'), 'settle leaf runs the settle CLI')
      assert.ok(_prompt.includes('--timeout-sec 540'), 'settle budget is pinned under the 600s Bash leaf ceiling')
      return [{ ok: true, stdout: JSON.stringify(plan.settle) }]
    }
    if (label === 'prepare CI fix') {
      return [{ ok: true, stdout: JSON.stringify({ action: 'fix', ok: true, read_back: true }) }]
    }
    if (label === 'fix-ci') return { fixed: true }
    if (label === 'push CI fix + recheck') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, pushed: true, read_back: true, checks: [{ name: 'ci', bucket: 'pass' }] }) }]
    }
    if (label === 'post readout') return [{ ok: true, stdout: JSON.stringify({ posted: true, recorded: false }) }]
    throw new Error('unexpected label=' + label)
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), labels }
}

;(async () => {
  // pending -> settle -> green -> ready handback; the fixer is NEVER dispatched.
  let { sr, labels } = run({
    firstChecks: [{ name: 'validate', bucket: 'pending' }],
    settle: { settled: true, waited_sec: 42.0, checks: [{ name: 'validate', bucket: 'pass' }] },
  })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'pending -> settle -> green -> ready')
  assert.ok(labels.includes('wait for CI to settle'), 'settle leaf dispatched')
  assert.ok(!labels.includes('fix-ci'), 'no fixer at running checks')

  // pending -> settle budget exhausted (still pending) -> honest park, no fixer.
  ;({ sr, labels } = run({
    firstChecks: [{ name: 'validate', bucket: 'pending' }],
    settle: { settled: false, waited_sec: 900.0, checks: [{ name: 'validate', bucket: 'pending' }] },
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'unsettled -> parked')
  assert.ok(/still pending after the settle wait/.test(out.reason), 'park names the settle wait')
  assert.ok(out.reason.includes('validate'), 'park names the checks still pending AFTER the wait (fresh classification)')
  assert.ok(!labels.includes('fix-ci'), 'no fixer on an unsettled park')

  // pending -> settle resolves RED -> fixer path engages (fix -> green -> ready).
  ;({ sr, labels } = run({
    firstChecks: [{ name: 'validate', bucket: 'pending' }],
    settle: { settled: true, waited_sec: 61.0, checks: [{ name: 'validate', bucket: 'fail' }] },
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'pending -> settled red -> fix -> ready')
  assert.ok(labels.includes('fix-ci'), 'settled-red routes to the fixer')

  console.log('ok: ship settle-wait (pending waits, unsettled parks, settled-red fixes)')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
