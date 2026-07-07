// Smoke: args-based front-half selector for Workflow-tool live runs (Task 13a, #115).
//
// Asserts BOTH halves of the feature:
//   (A) showrunner.js side — calls sr.showrunner({workItem:'wi'}) directly so the run-mode
//       deps-wiring block (lines ~512-518) is exercised. An inverted || -> && in line 513
//       would leave frontHalfBoundary un-injected and the assertion would fail.
//   (B) bundle ENTRY side — the regenerated bundle's ENTRY maps args.frontHalf==='native' to both
//       globals (text/structure assertion, not a full eval of the entry).
// usableDraft uses the small boundary signal {usable, recorded, expected} — verdict computed
// Python-side; the large doc text never crosses the cheapest-model pipe.
require('./_smoke_checkout_root.js')
const assert = require('assert')
const { markedStdout, saveProgressOk } = require('./_marked_stdout.js')
const fs = require('fs')
const path = require('path')
const sr = require('../showrunner.js')

// pid-unique work item: the run-mode outcome envelope stages machine-global payload files derived
// from the work-item name (/tmp/showrunner-<wi>-fronthalf-*.json*), so a fixed name collides with
// a concurrent pytest suite on this machine (see _final_review_probe.js for the flake story).
const WI = `wi-pid${process.pid}`

// ---------------------------------------------------------------------------
// Shared agent stub — handles all leaf dispatch that showrunner() reaches on
// the front-half path:
//   label 'exec'  -> exec() dumb-pipe stubs (recover_entry, definition_doc, front_half_usable)
//   label 'lib'   -> cmdRunner stubs (journal_entry, checkpoint_entry, render-outcome)
//   anything else -> null (build_phase 'tasks-gate' etc. — used to make a3 park at workhorse)
// ---------------------------------------------------------------------------
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// Small boundary signal: verdict computed Python-side at the IO boundary.
// The spine reads signals.usable directly; the large doc text never crosses the pipe.
const USABLE_SIGNALS = JSON.stringify({
  usable: true,
  recorded: 'sha:smoke',
  expected: 'sha:smoke',
})

function makeAgentStub() {
  return async function agent(prompt, opts) {
    const label = (opts && opts.label) || ''

    if (label === 'read startup state') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '' }) }]
    }

    // Dumb-pipe (courier) leaves are routed by the command in their prompt, regardless of the
    // descriptive label ('gather snapshot'/'read gate'/'check draft'/'append notify'). The generic
    // courier catch-all lives AFTER the named 'save phase progress' branch so it never swallows it.
    if (opts && opts.courier && typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
      // reconcile(): empty snapshot -> recoverTwin gets undefined checkpoint/world -> world_derive
      return markedStdout({
        checkpoint: null,
        world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
        generation: 1,
        root: globalThis.__SR_ROOT,
      })
    }
    if (opts && opts.courier && typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
      // readGate() for spec, plan, or tasks: always return 'passed'
      return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
    }
    if (opts && opts.courier && typeof prompt === 'string' && prompt.includes('front_half_usable.py')) {
      // usableDraft(): return a usable draft so producePhase short-circuits (no author agent)
      return [{ index: 0, ok: true, stdout: USABLE_SIGNALS }]
    }
    if (opts && opts.courier && typeof prompt === 'string' && prompt.includes('front_half.py append-notify')) {
      return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
    }

    if (label === 'save phase progress') {
      return saveProgressOk()
    }

    // Any other dumb-pipe leaf (e.g. definition_doc set-gate batched in persistPhase): return ok.
    if (opts && opts.courier) return [{ index: 0, ok: true, stdout: '{"ok":true}' }]

    if (label === 'lib') {
      if (typeof prompt === 'string' && prompt.includes('journal_entry')) return { ok: true }
      if (typeof prompt === 'string' && prompt.includes('checkpoint_entry')) return { ok: true, pr: null }
      if (typeof prompt === 'string' && prompt.includes('phase_step_cli')) {
        throw new Error('phase_step_cli dispatched as agent — must use JS twin')
      }
      if (typeof prompt === 'string' && prompt.includes('render-outcome')) {
        return 'front-half complete (smoke stub)'
      }
      return { ok: true }
    }

    // Everything else (e.g. 'tasks-gate' in buildPhase for a3): return null.
    // buildPhase will see gate='null', park with low-confidence -> workhorse parks (not boundary).
    return null
  }
}

async function main() {
  // --- PART A: showrunner.js side ---
  // Each sub-case calls sr.showrunner({workItem:'wi'}) directly, exercising the run-mode
  // deps-wiring block in showrunner() that the old runPhases() call bypassed.
  // Correctness guard: if line ~513 read '&&' instead of '||', frontHalfNative would be false
  // whenever the globalThis flag is set but the env is not (a1), and frontHalfBoundary would
  // never be injected -> the showrunner() call would NOT park at front-half-boundary -> a1 FAILS.

  // (a1) globalThis path: SUPERHEROES_FRONT_HALF_NATIVE=true, BUNDLE_FULL_RUN=false
  //      -> showrunner() must wire frontHalfBoundary -> park at 'front-half-boundary'.
  {
    const savedFull = globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    const savedNative = globalThis.SUPERHEROES_FRONT_HALF_NATIVE
    const savedEnv = process.env.SUPERHEROES_FRONT_HALF
    try {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = false
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = true
      delete process.env.SUPERHEROES_FRONT_HALF   // ensure env path is NOT the trigger
      global.agent = makeAgentStub()
      const result = await sr.showrunner({ workItem: WI })
      assert.strictEqual(result.outcome, 'parked',
        'a1: globalThis FRONT_HALF_NATIVE -> showrunner() parks')
      assert.strictEqual(result.phase, 'front-half-boundary',
        'a1: globalThis FRONT_HALF_NATIVE -> showrunner() parks at front-half-boundary')
    } finally {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = savedFull
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = savedNative
      if (savedEnv === undefined) delete process.env.SUPERHEROES_FRONT_HALF
      else process.env.SUPERHEROES_FRONT_HALF = savedEnv
    }
  }

  // (a2) env path: SUPERHEROES_FRONT_HALF='native' (no globalThis flag)
  //      -> showrunner() must wire frontHalfBoundary -> park at 'front-half-boundary'.
  //      (smoke runs under node directly, so process.env is available here — that's the env path)
  {
    const savedFull = globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    const savedNative = globalThis.SUPERHEROES_FRONT_HALF_NATIVE
    const savedEnv = process.env.SUPERHEROES_FRONT_HALF
    try {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = false
      delete globalThis.SUPERHEROES_FRONT_HALF_NATIVE   // ensure globalThis path is NOT the trigger
      process.env.SUPERHEROES_FRONT_HALF = 'native'
      global.agent = makeAgentStub()
      const result = await sr.showrunner({ workItem: WI })
      assert.strictEqual(result.outcome, 'parked',
        'a2: env SUPERHEROES_FRONT_HALF=native -> showrunner() parks')
      assert.strictEqual(result.phase, 'front-half-boundary',
        'a2: env SUPERHEROES_FRONT_HALF=native -> showrunner() parks at front-half-boundary')
    } finally {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = savedFull
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = savedNative
      if (savedEnv === undefined) delete process.env.SUPERHEROES_FRONT_HALF
      else process.env.SUPERHEROES_FRONT_HALF = savedEnv
    }
  }

  // (a3) full-run default: BUNDLE_FULL_RUN=true, no env/globalThis flag
  //      -> showrunner() does NOT wire frontHalfBoundary -> run proceeds past the boundary into
  //      workhorse (which parks on a null tasks-gate, NOT at front-half-boundary).
  {
    const savedFull = globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    const savedNative = globalThis.SUPERHEROES_FRONT_HALF_NATIVE
    const savedEnv = process.env.SUPERHEROES_FRONT_HALF
    try {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true
      delete globalThis.SUPERHEROES_FRONT_HALF_NATIVE
      delete process.env.SUPERHEROES_FRONT_HALF
      global.agent = makeAgentStub()
      const result = await sr.showrunner({ workItem: WI })
      assert.ok(result.phase !== 'front-half-boundary',
        'a3: full-run default does NOT park at front-half-boundary (proceeds into workhorse)')
    } finally {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = savedFull
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = savedNative
      if (savedEnv === undefined) delete process.env.SUPERHEROES_FRONT_HALF
      else process.env.SUPERHEROES_FRONT_HALF = savedEnv
    }
  }

  // --- PART B: bundle ENTRY side (text assertion on the generated bundle) ---
  {
    const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
    const text = fs.readFileSync(bundlePath, 'utf8')
    // Extract the ENTRY block (after the last module factory, inside the __SR_RUN gate).
    assert.ok(text.includes("frontHalf === 'native'"),
      "bundle ENTRY must contain frontHalf === 'native' selector")
    assert.ok(text.includes('SUPERHEROES_FRONT_HALF_NATIVE'),
      'bundle ENTRY must set globalThis.SUPERHEROES_FRONT_HALF_NATIVE')
    assert.ok(text.includes('SUPERHEROES_BUNDLE_FULL_RUN = !frontHalfNative'),
      'bundle ENTRY must set SUPERHEROES_BUNDLE_FULL_RUN = !frontHalfNative')
  }

  console.log('ok: args-based front-half selector (showrunner() wiring direct, globalThis, env, full-run default, bundle ENTRY)')
}

main().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
