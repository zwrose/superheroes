// plugins/superheroes/lib/tests/showrunner_quick_route_smoke.js
// #25 quick discovery (PR 1 — the showrunner leg). The spine accepts a tasks-doc input artifact
// (route=quick) and starts the phase list at `workhorse`, skipping plan/review-plan/tasks/
// review-tasks. This pins: (A) the pure resolveIntake decider (route + fail-closed refuse matrix);
// (B) a fresh quick run records the skipped phases durably then enters the loop AT build (never at
// plan); (C) a missing/malformed tasks artifact REFUSES to launch (never falls back to/past full);
// (D) the full route is unchanged — it still gates on the spec and records no skips.
require('./_smoke_checkout_root.js')
const assert = require('assert')
const { markedStdout, saveProgressOk } = require('./_marked_stdout.js')
global.log = () => {}

const CHECKOUT_ROOT = globalThis.__SR_ROOT
const sr = require('../showrunner.js')

// ---------------------------------------------------------------------------
// Part A — resolveIntake: the pure intake decider (no dispatch).
// ---------------------------------------------------------------------------
// spec present, UNDECLARED -> full route (byte-identical path).
assert.deepStrictEqual(sr.resolveIntake({ spec_present: true, spec_gate: 'passed' }, null), { route: 'full' })
// A DECLARED route that agrees with the artifact is honored.
assert.deepStrictEqual(sr.resolveIntake({ spec_present: true, spec_gate: 'passed' }, 'full'), { route: 'full' })
assert.deepStrictEqual(
  sr.resolveIntake({ spec_present: false, tasks_present: true, tasks_gate: 'passed' }, 'quick'),
  { route: 'quick', action: 'gate', gate: 'passed' })
// A DECLARED route that CONFLICTS with the artifact -> fail-closed REFUSE, never a silent override.
// (a) declared quick + a spec present: refuse under the declared route (was silently 'full').
{
  const out = sr.resolveIntake({ spec_present: true, spec_gate: 'passed' }, 'quick')
  assert.strictEqual(out.route, 'quick')
  assert.strictEqual(out.action, 'refuse')
  assert.ok(/declared the 'quick' route/.test(out.reason) && /spec is present/.test(out.reason), out.reason)
}
// (b) declared full + a spec-less tasks doc: refuse under the declared route (was silently 'quick').
{
  const out = sr.resolveIntake({ spec_present: false, tasks_present: true, tasks_gate: 'passed' }, 'full')
  assert.strictEqual(out.route, 'full')
  assert.strictEqual(out.action, 'refuse')
  assert.ok(/declared the 'full' route/.test(out.reason) && /only a tasks doc/.test(out.reason), out.reason)
}
// tasks present + a real gate, UNDECLARED -> quick route, gate handed back for the startup check.
assert.deepStrictEqual(
  sr.resolveIntake({ spec_present: false, tasks_present: true, tasks_gate: 'passed' }, null),
  { route: 'quick', action: 'gate', gate: 'passed' })
assert.deepStrictEqual(
  sr.resolveIntake({ spec_present: false, tasks_present: true, tasks_gate: 'pending' }, null),
  { route: 'quick', action: 'gate', gate: 'pending' })
// tasks present but malformed / unreadable / gate-less -> fail-closed REFUSE.
for (const g of ['malformed', 'unreadable', null]) {
  const out = sr.resolveIntake({ spec_present: false, tasks_present: true, tasks_gate: g }, null)
  assert.strictEqual(out.route, 'quick')
  assert.strictEqual(out.action, 'refuse')
  assert.ok(/fail-closed intake/.test(out.reason), 'malformed tasks artifact refuses: ' + out.reason)
}
// no artifact + declared quick -> REFUSE (never a silent fall-back to the full path).
{
  const out = sr.resolveIntake({ spec_present: false, tasks_present: false }, 'quick')
  assert.strictEqual(out.action, 'refuse')
  assert.ok(/never falling back to the full path/.test(out.reason), out.reason)
}
// no artifact + no declaration -> full (today's no-spec world; parks at the spec gate downstream).
assert.deepStrictEqual(sr.resolveIntake({ spec_present: false, tasks_present: false }, null), { route: 'full' })
// declared full + no artifact -> full (no conflict; parks at the spec gate downstream, fail-closed).
assert.deepStrictEqual(sr.resolveIntake({ spec_present: false, tasks_present: false }, 'full'), { route: 'full' })

// ---------------------------------------------------------------------------
// Shared courier stub for the end-to-end showrunner() drives (Parts B–D).
// ---------------------------------------------------------------------------
const WORLD = { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }

// opts.checkpoint: null (fresh) or a resume cursor object (reconciles to action:'continue').
// opts.skipRecordFails: the skipped-phase journal write reports a failed durable write.
function makeAgent(startupFacts, trace, opts) {
  opts = opts || {}
  return async (prompt, agopts) => {
    const label = (agopts && agopts.label) || ''
    if (prompt.includes('recover_entry')) {
      return markedStdout({
        checkpoint: opts.checkpoint || null, world: WORLD, generation: 7, root: CHECKOUT_ROOT })
    }
    if (label === 'read startup state') {
      return [{ ok: true, stdout: markedStdout(Object.assign({ ok: true }, startupFacts)) }]
    }
    if (label === 'record skipped phases') {
      trace.skipRecord = prompt
      // opts.skipRecordFails simulates a failed durable journal write (recordSkippedPhases -> false).
      return JSON.stringify(opts.skipRecordFails ? { ok: false } : { ok: true })
    }
    if (label === 'read gate') {
      // buildPhase's FIRST leaf reads the tasks gate (--json); a non-'passed' answer parks it
      // immediately, proving the loop reached `workhorse` without any front-half authoring.
      trace.buildEntered = true
      return '{"review": "pending"}'
    }
    // #434: a park seeds a resume-continuing per-leg idem nonce before the save.
    if (label === 'phase leg seed') return markedStdout({ ok: true, max: 0 })
    if (label === 'save phase progress') {
      return saveProgressOk({ checkpoint_confirmed: false })
    }
    if (label === 'release lease') {
      trace.releases.push(prompt)
      return JSON.stringify({ ok: true, reason: 'lease released' })
    }
    throw new Error('unexpected agent leaf: ' + label + ' :: ' + String(prompt).slice(0, 80))
  }
}

const QUICK_FACTS = {
  spec_gate: 'unreadable', model_overrides: {}, doc_dir: '', run_overrides_present: false,
  engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
  spec_present: false, tasks_present: true, tasks_gate: 'passed',
}

;(async () => {
  // -------------------------------------------------------------------------
  // Part B — fresh quick run: skips recorded, loop enters AT build (workhorse).
  // -------------------------------------------------------------------------
  delete globalThis.__SR_ROUTE
  globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true
  {
    const trace = { releases: [] }
    global.agent = makeAgent(QUICK_FACTS, trace)
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.ok(trace.skipRecord, 'a fresh quick run records the skipped phases')
    assert.ok(trace.skipRecord.includes('--event-type phases_skipped'),
      'skip record journals a phases_skipped event')
    assert.ok(trace.skipRecord.includes('"skipped"') &&
      trace.skipRecord.includes('plan') && trace.skipRecord.includes('review-tasks'),
      'skip record names the skipped front-half phases')
    assert.ok(trace.buildEntered, 'the loop entered the build phase (workhorse)')
    assert.strictEqual(out.outcome, 'parked')
    assert.strictEqual(out.phase, 'workhorse', 'quick run starts at build, not plan')
    assert.ok(/tasks gate not passed/.test(out.reason), out.reason)
    assert.ok(trace.releases.length >= 1, 'a terminal park releases the held lease')
  }

  // -------------------------------------------------------------------------
  // Part C — fail-closed intake: declared quick, no tasks artifact -> REFUSE.
  // -------------------------------------------------------------------------
  {
    globalThis.__SR_ROUTE = 'quick'
    const trace = { releases: [] }
    global.agent = makeAgent({ spec_gate: 'unreadable', model_overrides: {}, doc_dir: '', run_overrides_present: false,
      engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
      spec_present: false, tasks_present: false, tasks_gate: null }, trace)
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.strictEqual(out.outcome, 'parked')
    assert.strictEqual(out.phase, 'startup')
    assert.ok(/refusing to launch/.test(out.reason), out.reason)
    assert.ok(!trace.skipRecord, 'a refused launch records no skipped phases')
    assert.ok(!trace.buildEntered, 'a refused launch never enters the build phase')
    delete globalThis.__SR_ROUTE
  }

  // -------------------------------------------------------------------------
  // Part D — fail-closed intake: tasks artifact present but MALFORMED -> REFUSE.
  // -------------------------------------------------------------------------
  {
    const trace = { releases: [] }
    global.agent = makeAgent({ spec_gate: 'unreadable', model_overrides: {}, doc_dir: '', run_overrides_present: false,
      engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
      spec_present: false, tasks_present: true, tasks_gate: 'malformed' }, trace)
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.strictEqual(out.phase, 'startup')
    assert.ok(/fail-closed intake/.test(out.reason), out.reason)
    assert.ok(!trace.buildEntered, 'a malformed tasks artifact never builds')
  }

  // -------------------------------------------------------------------------
  // Part E — full route unchanged: gates on the spec, records NO skips.
  // -------------------------------------------------------------------------
  {
    const trace = { releases: [] }
    global.agent = makeAgent({ spec_gate: 'pending', model_overrides: {}, doc_dir: '', run_overrides_present: false,
      engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
      spec_present: true, tasks_present: false, tasks_gate: null }, trace)
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.strictEqual(out.phase, 'startup')
    assert.ok(/pending/.test(out.reason), 'full route parks on the unapproved spec gate')
    assert.ok(!trace.skipRecord, 'the full route records no skipped phases')
    assert.ok(!trace.buildEntered, 'an unapproved full-route run never builds')
  }

  // -------------------------------------------------------------------------
  // Part F — fail-closed durable-write: a quick run whose skipped-phase record
  // fails to write REFUSES to launch, rather than build on a silently-absent
  // skip. This is the honesty guarantee #25 adds — an unrecorded skip must park.
  // -------------------------------------------------------------------------
  {
    delete globalThis.__SR_ROUTE
    const trace = { releases: [] }
    global.agent = makeAgent(QUICK_FACTS, trace, { skipRecordFails: true })
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.ok(trace.skipRecord, 'the run attempted the skip record')
    assert.strictEqual(out.outcome, 'parked')
    assert.strictEqual(out.phase, 'startup')
    assert.ok(/unrecorded skip/.test(out.reason), out.reason)
    assert.ok(!trace.buildEntered, 'a failed skip record never proceeds into build')
    assert.ok(trace.releases.length >= 1, 'the fail-closed park releases the held lease')
  }

  // -------------------------------------------------------------------------
  // Part G — quick-route RESUME: a run resuming from a durable cursor rides the
  // cursor (past the skipped front half) and does NOT re-record the skip — the
  // `!_resuming` guard. A checkpoint with lastGoodStep reconciles to 'continue'
  // (fromStep = cursor+1); lastGoodStep 3 resumes at `workhorse` (index 4).
  // -------------------------------------------------------------------------
  {
    const trace = { releases: [] }
    global.agent = makeAgent(QUICK_FACTS, trace, { checkpoint: { lastGoodStep: 3 } })
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.ok(!trace.skipRecord, 'a resume does not re-record the skipped phases')
    assert.ok(trace.buildEntered, 'the resume rides the cursor into the build phase')
    assert.strictEqual(out.phase, 'workhorse', 'resume re-enters at the cursor, not the front half')
  }

  // -------------------------------------------------------------------------
  // Part H — declared-vs-artifact CONFLICT refuses end-to-end, under the DECLARED
  // route (here 'full' over a spec-less tasks doc). Pins that the startup refuse
  // handler fires for a refuse carrying route:'full', not only route:'quick'.
  // -------------------------------------------------------------------------
  {
    globalThis.__SR_ROUTE = 'full'
    const trace = { releases: [] }
    global.agent = makeAgent(QUICK_FACTS, trace)   // tasks present, no spec -> derived quick
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.strictEqual(out.outcome, 'parked')
    assert.strictEqual(out.phase, 'startup')
    assert.ok(/declared the 'full' route/.test(out.reason), out.reason)
    assert.ok(!trace.skipRecord, 'a conflict refuse records no skipped phases')
    assert.ok(!trace.buildEntered, 'a conflict refuse never builds')
    delete globalThis.__SR_ROUTE
  }

  console.log('ok: #25 quick-route intake — route decider, skips journaled, starts at build, fail-closed refuse (missing/malformed/unrecorded/declared-conflict), resume rides the cursor, full unchanged')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
