// plugins/superheroes/lib/tests/showrunner_quick_route_smoke.js
// #25 quick discovery (PR 1 — the showrunner leg). The spine accepts a tasks-doc input artifact
// (route=quick) and starts the phase list at `workhorse`, skipping plan/review-plan/tasks/
// review-tasks. This pins: (A) the pure resolveIntake decider (route + fail-closed refuse matrix);
// (B) a fresh quick run records the skipped phases durably then enters the loop AT build (never at
// plan); (C) a missing/malformed tasks artifact REFUSES to launch (never falls back to/past full);
// (D) the full route is unchanged — it still gates on the spec and records no skips.
require('./_smoke_checkout_root.js')
const assert = require('assert')
global.log = () => {}

const CHECKOUT_ROOT = globalThis.__SR_ROOT
const sr = require('../showrunner.js')

// ---------------------------------------------------------------------------
// Part A — resolveIntake: the pure intake decider (no dispatch).
// ---------------------------------------------------------------------------
// spec present -> full route (byte-identical path), even if an explicit route says otherwise.
assert.deepStrictEqual(sr.resolveIntake({ spec_present: true, spec_gate: 'passed' }, null), { route: 'full' })
assert.deepStrictEqual(sr.resolveIntake({ spec_present: true }, 'quick'), { route: 'full' })
// tasks present + a real gate -> quick route, gate handed back for the startup check.
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

// ---------------------------------------------------------------------------
// Shared courier stub for the end-to-end showrunner() drives (Parts B–D).
// ---------------------------------------------------------------------------
const WORLD = { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }

function makeAgent(startupFacts, trace) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (prompt.includes('recover_entry')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify({
        checkpoint: null, world: WORLD, generation: 7, root: CHECKOUT_ROOT }) }]
    }
    if (label === 'read startup state') {
      return [{ ok: true, stdout: JSON.stringify(Object.assign({ ok: true }, startupFacts)) }]
    }
    if (label === 'record skipped phases') {
      trace.skipRecord = prompt
      return JSON.stringify({ ok: true })
    }
    if (label === 'read gate') {
      // buildPhase's FIRST leaf reads the tasks gate; a non-'passed' answer parks it immediately,
      // proving the loop reached `workhorse` without any front-half authoring.
      trace.buildEntered = true
      return 'pending'
    }
    if (label === 'save phase progress') {
      return JSON.stringify({ ok: true, journal_confirmed: true })
    }
    if (label === 'release lease') {
      trace.releases.push(prompt)
      return JSON.stringify({ ok: true, reason: 'lease released' })
    }
    throw new Error('unexpected agent leaf: ' + label + ' :: ' + String(prompt).slice(0, 80))
  }
}

const QUICK_FACTS = {
  spec_gate: 'unreadable', model_overrides: {}, doc_dir: '',
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
    global.agent = makeAgent({ spec_gate: 'unreadable', model_overrides: {}, doc_dir: '',
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
    global.agent = makeAgent({ spec_gate: 'unreadable', model_overrides: {}, doc_dir: '',
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
    global.agent = makeAgent({ spec_gate: 'pending', model_overrides: {}, doc_dir: '',
      engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
      spec_present: true, tasks_present: false, tasks_gate: null }, trace)
    const out = await sr.showrunner({ workItem: 'wi' })
    assert.strictEqual(out.phase, 'startup')
    assert.ok(/pending/.test(out.reason), 'full route parks on the unapproved spec gate')
    assert.ok(!trace.skipRecord, 'the full route records no skipped phases')
    assert.ok(!trace.buildEntered, 'an unapproved full-route run never builds')
  }

  console.log('ok: #25 quick-route intake — route decider, skips journaled, starts at build, fail-closed refuse, full unchanged')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
