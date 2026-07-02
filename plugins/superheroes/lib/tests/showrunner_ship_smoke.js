// plugins/superheroes/lib/tests/showrunner_ship_smoke.js
const assert = require('assert')
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function run(checksOrError) {
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: '/wt-head-sha' })
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'check ship-readiness') {
      if (checksOrError === 'error') return jsonOut({ ok: false, reconcile: { ok: false }, freshness: {}, checks: {} })
      if (checksOrError === 'sentinel') {
        return jsonOut({
          ok: true,
          reconcile: { ok: true },
          freshness: { decision: 'up_to_date' },
          integrated: false,
          checks: { error: 'CI status could not be read' },
        })
      }
      if (checksOrError === 'garbled') {
        return jsonOut({ ok: false, reconcile: { ok: true }, freshness: { decision: 'gate' }, checks: null })
      }
      return jsonOut({
        ok: true,
        reconcile: { ok: true, head: '/wt-head-sha', reason: 'in sync' },
        freshness: { decision: 'up_to_date' },
        integrated: false,
        checks: checksOrError,
      })
    }
    if (label === 'prepare CI fix') return jsonOut({ action: 'revert_and_gate', round: 5, reason: 'cap', ok: true, read_back: true })
    if (label === 'lib' && p.includes('--step revert-draft')) return { ok: true, reason: 'reverted to draft' }
    if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  let sr = run([{ name: 'ci', bucket: 'pass', state: 'success' }])
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')

  sr = run([{ name: 'ci', bucket: 'fail', state: 'failure' }])
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'red -> parked')

  sr = run([])
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|confirm/i.test(out.reason), 'none reason names the carve-out')

  sr = run('error')
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'unreadable readiness -> parked (fail-closed)')

  sr = run('sentinel')
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', '{error} sentinel -> parked (fail-closed, not merge-ready)')

  sr = run('garbled')
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'garbled readiness -> parked')

  sr = run([{ name: 'ci', bucket: 'pass', state: 'success' }])
  out = await sr.shipPhase('wi', { number: 7 })
  assert.strictEqual(out.outcome, 'parked', 'null generation -> parked (fence fail-closed)')
  assert.ok(/lease lost|reconcil|UFR-4/i.test(out.reason), 'null-generation parks at the entry fence')

  function runNoWorktree() {
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'resolve review target') return jsonOut({ ok: false, error: 'fresh worktree created' })
      if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
      throw new Error('unexpected agent (runNoWorktree): label=' + label + ' prompt=' + p.slice(0, 80))
    }
    global.log = () => {}
    delete require.cache[require.resolve('../showrunner.js')]
    return require('../showrunner.js')
  }
  const srNW = runNoWorktree()
  const outNW = await srNW.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(outNW.outcome, 'parked', 'null worktree -> parked (no mutation against repo root)')
  assert.ok(/worktree/i.test(outNW.reason), 'null-worktree park names the worktree')

  console.log('OK: ship green->ready, red->park, none->ready-with-carve-out, error/sentinel/garbled->park(fail-closed), null-generation->park(fence-fail-closed), null-worktree->park(no-repo-root-mutation)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
