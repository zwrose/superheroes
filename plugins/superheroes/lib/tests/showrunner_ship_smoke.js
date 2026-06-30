// plugins/superheroes/lib/tests/showrunner_ship_smoke.js
// #115 Task 16: ship CI step moved to exec IO (--emit-checks) + ciStatusTwin in-process classify.
// Pins the twin-not-agent boundary: the CI checks read goes via exec (label:'exec'), NOT via
// cmdRunner (label:'lib') — the twin classifies in-process, no decider agent.
const assert = require('assert')

// mode controls how the --emit-checks leaf responds:
//   'error'    -> exec reports the leaf failed (ok:false) — a subprocess-level read failure.
//   'sentinel' -> the leaf succeeded but ship_phase emitted the fail-closed {error:...} sentinel
//                 (a genuinely-FAILED gh read that --emit-checks must surface, not coerce to []).
//   'garbled'  -> the leaf returned non-JSON stdout (a garbled/truncated read) — must NOT classify
//                 as 'none'; ship must PARK. A mutant that coerces garbled->[]->'none' fails here.
//   otherwise  -> checksOrError is the raw checks array the leaf prints (JSON).
function run(checksOrError) {
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    // resolve build worktree (resolveBuildTarget): build_entry.py AND rev-parse BOTH dispatch via exec
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head-sha' }]
    // entry fence (the entry reconcile may push) + reconcile-head: in sync, no-op ok
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head-sha', reason: 'in sync' }
    // freshness stays as cmdRunner (lib)
    if (label === 'lib' && p.includes('freshness')) return { decision: 'up_to_date' }
    // NEW: ci checks read via exec (label:'exec'), prompt includes 'emit-checks'
    if (label === 'exec' && p.includes('emit-checks')) {
      if (checksOrError === 'error') return [{ index: 0, ok: false, stdout: '' }]
      // fail-closed sentinel the --emit-checks seam emits on a genuinely-failed gh read
      if (checksOrError === 'sentinel') return [{ index: 0, ok: true, stdout: JSON.stringify({ error: 'CI status could not be read' }) }]
      // garbled non-JSON stdout (truncated / non-JSON gh output) — a parse FAILURE
      if (checksOrError === 'garbled') return [{ index: 0, ok: true, stdout: 'not json at all <<<' }]
      return [{ index: 0, ok: true, stdout: JSON.stringify(checksOrError) }]
    }
    // CI-fix loop (red path): decide -> revert-to-draft so the existing `red -> parked` case still parks
    if (label === 'lib' && p.includes('--step ci-decide')) return { action: 'revert_and_gate', round: 5, reason: 'cap' }
    if (label === 'lib' && p.includes('--step revert-draft')) return { ok: true, reason: 'reverted to draft' }
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
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')

  // failing check -> parked
  sr = run([{ name: 'ci', bucket: 'fail', state: 'failure' }])
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'red -> parked')

  // no checks -> ready with carve-out (none)
  sr = run([])
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|confirm/i.test(out.reason), 'none reason names the carve-out')

  // exec error -> parked (fail-closed)
  sr = run('error')
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'exec error -> parked (fail-closed)')

  // ADVERSARIAL (#115 final review, Critical FIX 1): the --emit-checks leaf emitted the
  // fail-closed {error:...} sentinel (a genuinely-failed gh read). ship must PARK, never report
  // a false "merge-ready: no required checks". A mutant that classified {error} -> 'none' fails.
  sr = run('sentinel')
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', '{error} sentinel -> parked (fail-closed, not merge-ready)')

  // ADVERSARIAL (Critical FIX 1): the leaf returned GARBLED non-JSON stdout (truncated/garbled
  // read). A JSON.parse failure must PARK — NOT be coerced to []->'none'->merge-ready. A mutant
  // that coerces a parse-failure to [] (false 'none') fails this assertion.
  sr = run('garbled')
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'garbled non-JSON -> parked (parse-failure must not coerce to none)')

  // generation threaded: a green path still reaches 'ready' with the entry reconcile in place.
  sr = run([{ name: 'ci', bucket: 'pass', state: 'success' }])
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green + generation -> ready')

  // ADVERSARIAL: null generation -> park (fence fail-closed, UFR-4).
  // shipFenceOrPark returns false immediately when generation == null (no fence_cli call).
  // resolveBuildTarget resolves (build_entry.py + rev-parse stubs in run()), then the fence
  // short-circuits and shipPhase parks.
  sr = run([{ name: 'ci', bucket: 'pass', state: 'success' }])
  out = await sr.shipPhase('wi', { number: 7 })   // no generation -> fence fail-closed
  assert.strictEqual(out.outcome, 'parked', 'null generation -> parked (fence fail-closed)')
  assert.ok(/lease lost|reconcil|UFR-4/i.test(out.reason), 'null-generation parks at the entry fence')

  // ADVERSARIAL: null worktree -> park (no mutation against repo root).
  // build_entry.py returns outcome:'created' -> resolveBuildTarget returns null -> shipPhase parks
  // before touching any git mechanics.
  function runNoWorktree() {
    global.agent = async (p, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'created' }) }]
      // readout_post (park posts a readout)
      if (label === 'lib' && (p.includes('readout') || p.includes('readout_post') || p.includes('pr_comment'))) return { posted: true }
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

  console.log('OK: ship green->ready, red->park, none->ready-with-carve-out, error/sentinel/garbled->park(fail-closed), generation-threaded->ready, null-generation->park(fence-fail-closed), null-worktree->park(no-repo-root-mutation)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
