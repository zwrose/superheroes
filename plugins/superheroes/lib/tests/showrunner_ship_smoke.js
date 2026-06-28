// plugins/superheroes/lib/tests/showrunner_ship_smoke.js
// #115 Task 16: ship CI step moved to exec IO (--emit-checks) + ciStatusTwin in-process classify.
// Pins the twin-not-agent boundary: the CI checks read goes via exec (label:'exec'), NOT via
// cmdRunner (label:'lib') — the twin classifies in-process, no decider agent.
const assert = require('assert')

function run(checksOrError) {
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    // freshness stays as cmdRunner (lib)
    if (label === 'lib' && p.includes('freshness')) return { decision: 'up_to_date' }
    // NEW: ci checks read via exec (label:'exec'), prompt includes 'emit-checks'
    if (label === 'exec' && p.includes('emit-checks')) {
      if (checksOrError === 'error') return [{ index: 0, ok: false, stdout: '' }]
      return [{ index: 0, ok: true, stdout: JSON.stringify(checksOrError) }]
    }
    // readout_post stays as cmdRunner (lib)
    if (label === 'lib' && (p.includes('readout') || p.includes('readout_post') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // green checks -> ready
  let sr = run([{ name: 'ci', bucket: 'pass', state: 'success' }])
  let out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')

  // failing check -> parked
  sr = run([{ name: 'ci', bucket: 'fail', state: 'failure' }])
  out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'parked', 'red -> parked')

  // no checks -> ready with carve-out (none)
  sr = run([])
  out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|confirm/i.test(out.reason), 'none reason names the carve-out')

  // exec error -> parked (fail-closed)
  sr = run('error')
  out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'parked', 'exec error -> parked (fail-closed)')

  console.log('OK: ship green->ready, red->park, none->ready-with-carve-out, error->park(fail-closed)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
