require('./_smoke_checkout_root.js')
const assert = require('assert')
const sr = require('../showrunner.js')
const { markedStdout, saveProgressOk } = require('./_marked_stdout.js')

const CHECKOUT_ROOT = globalThis.__SR_ROOT
const WORLD = { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }

// A canned agent that drives showrunner() down the QUICK route far enough to plant the frozen-fold
// globals (§ showrunner.js: __SR_OVERRIDES / __SR_ENGINE_PREFS are set from mergeFrozenSnapshot BEFORE
// the build phase). recover_entry → read startup state → record skipped phases → read gate (pending
// parks at workhorse). The startup facts (incl. frozen_snapshot + run_overrides_present) ride the
// 'read startup state' answer — the exact consumer literal `startupFacts.frozen_snapshot`.
function driveAgent(startupFacts, trace) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (String(prompt).includes('recover_entry')) {
      return markedStdout({ checkpoint: null, world: WORLD, generation: 7, root: CHECKOUT_ROOT })
    }
    if (label === 'read startup state') {
      return [{ ok: true, stdout: markedStdout(Object.assign({ ok: true }, startupFacts)) }]
    }
    if (label === 'record skipped phases') { trace.recorded = true; return JSON.stringify({ ok: true }) }
    if (label === 'read gate') { trace.buildEntered = true; return '{"review": "pending"}' }
    if (label === 'save phase progress') return saveProgressOk({ checkpoint_confirmed: false })
    if (label === 'release lease') { trace.released = true; return JSON.stringify({ ok: true, reason: 'lease released' }) }
    throw new Error('unexpected agent leaf: ' + label + ' :: ' + String(prompt).slice(0, 80))
  }
}

function resetFoldGlobals() {
  delete globalThis.__SR_OVERRIDES
  delete globalThis.__SR_ENGINE_PREFS
  delete globalThis.__SR_DOC_DIRS
  delete globalThis.__SR_ROUTE
  delete globalThis.__SR_PHASE
}

;(async () => {
  const savedAgent = global.agent
  const savedLog = global.log
  try {
    // -------------------------------------------------------------------------
    // Part 1 — folded reads: the gate + overrides ride the ONE 'read startup state' gather.
    // -------------------------------------------------------------------------
    {
      const labels = []
      global.log = () => {}
      global.agent = async (_prompt, opts) => {
        labels.push(opts.label)
        if (opts.label === 'read world-snapshot') return [{ ok: true, stdout: JSON.stringify({ ok: true, snapshot: {} }) }]
        if (opts.label === 'read startup state') {
          return [{ ok: true, stdout: markedStdout({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', run_overrides_present: false }) }]
        }
        return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      const facts = await sr.readStartupState('wi')
      assert.strictEqual(facts.spec_gate, 'passed')
      assert.deepStrictEqual(facts.model_overrides, {})
      assert.deepStrictEqual(labels.filter((x) => x === 'read startup state'), ['read startup state'])
      console.log('ok: startup folded reads')
    }

    // -------------------------------------------------------------------------
    // Part 2 — narrator-hop closure (APPLIED): a current-version frozen_snapshot with one concrete
    // row rides the gather; the showrunner consumer literal `startupFacts.frozen_snapshot` folds its
    // pins onto __SR_OVERRIDES / __SR_ENGINE_PREFS. This exercises the write->gather->consume->pin
    // wiring end-to-end (mergeFrozenSnapshot is unit-tested; the SHOWRUNNER hop that reads the literal
    // and plants the globals was not).
    // -------------------------------------------------------------------------
    {
      resetFoldGlobals()
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true
      const logs = []
      global.log = (m) => logs.push(String(m))
      const FROZEN = {
        workItem: 'wi', version: sr.READOUT_VERSION,
        phases: [
          { phase: 'workhorse', role: 'builder', kind: 'build', engine: 'codex', model: 'opus',
            engineModel: 'gpt-5.6-sol', effort: 'high' },
        ],
      }
      const trace = {}
      global.agent = driveAgent({
        spec_gate: 'unreadable', model_overrides: {}, doc_dir: '',
        engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
        spec_present: false, tasks_present: true, tasks_gate: 'passed',
        run_overrides_present: true, frozen_snapshot: FROZEN,
      }, trace)
      const out = await sr.showrunner({ workItem: 'wi' })
      assert.strictEqual(out.phase, 'workhorse', 'the quick drive reaches the build phase (consumer ran first)')
      assert.ok(globalThis.__SR_OVERRIDES && globalThis.__SR_OVERRIDES.builder === 'opus',
        'APPLIED: the frozen row model pins onto __SR_OVERRIDES.builder (consumer literal frozen_snapshot exercised)')
      assert.ok(globalThis.__SR_ENGINE_PREFS && globalThis.__SR_ENGINE_PREFS.implementation === 'codex',
        'APPLIED: the frozen row engine pins onto __SR_ENGINE_PREFS.implementation')
      assert.strictEqual(globalThis.__SR_ENGINE_PREFS.effort.build, 'high',
        'APPLIED: the frozen row effort pins onto __SR_ENGINE_PREFS.effort.build')
      assert.ok(!logs.some((l) => /NOT applied/.test(l)),
        'APPLIED: a pinning snapshot must NOT emit the no-apply narrator line')
      console.log('ok: frozen snapshot applied — pins reach the dispatch globals')
    }

    // -------------------------------------------------------------------------
    // Part 3 — narrator-hop closure (NO-APPLY): run_overrides_present is true (a frozenSnapshot record
    // was on disk) but the gather carried NO frozen_snapshot (dropped in transit). The consumer must
    // dispatch on live config AND narrate the drop loudly rather than silently reverting.
    // -------------------------------------------------------------------------
    {
      resetFoldGlobals()
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true
      const logs = []
      global.log = (m) => logs.push(String(m))
      const trace = {}
      global.agent = driveAgent({
        spec_gate: 'unreadable', model_overrides: {}, doc_dir: '',
        engine_prefs: { reviewer: 'claude', implementation: 'claude', effort: {} },
        spec_present: false, tasks_present: true, tasks_gate: 'passed',
        run_overrides_present: true, frozen_snapshot: null,
      }, trace)
      const noApplyResult = await sr.showrunner({ workItem: 'wi' })
      assert.ok(logs.some((l) => /frozen readout snapshot present but NOT applied/.test(l)),
        'NO-APPLY: a present-on-disk record with a dropped snapshot must emit the loud no-apply narrator line')
      assert.strictEqual(noApplyResult.outcome, 'parked',
        'NO-APPLY: unknown confirmed snapshot state parks for a fresh preflight')
      assert.ok(/fresh preflight confirmation required/.test(noApplyResult.reason),
        'NO-APPLY: the park reason names the required recovery')
      assert.ok(!(globalThis.__SR_OVERRIDES && globalThis.__SR_OVERRIDES.builder),
        'NO-APPLY: nothing pins before the run parks')
      console.log('ok: frozen snapshot dropped in transit — parks for fresh preflight')
    }

    console.log('ok: startup fold + narrator-hop closure')
  } finally {
    resetFoldGlobals()
    delete globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    global.agent = savedAgent
    global.log = savedLog
  }
})().catch((e) => { console.error('FAIL:', (e && e.message) || e); process.exit(1) })
