// Smoke: args-based front-half selector for Workflow-tool live runs (Task 13a, #115).
//
// Asserts BOTH halves of the feature:
//   (A) showrunner.js side — calls sr.showrunner({workItem:'wi'}) directly so the run-mode
//       deps-wiring block (lines ~512-518) is exercised. An inverted || -> && in line 513
//       would leave frontHalfBoundary un-injected and the assertion would fail.
//   (B) bundle ENTRY side — the regenerated bundle's ENTRY maps args.frontHalf==='native' to both
//       globals (text/structure assertion, not a full eval of the entry).
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const sr = require('../showrunner.js')

// ---------------------------------------------------------------------------
// Shared agent stub — handles all leaf dispatch that showrunner() reaches on
// the front-half path:
//   label 'exec'  -> exec() dumb-pipe stubs (recover_entry, definition_doc, front_half_usable)
//   label 'lib'   -> cmdRunner stubs (journal_entry, checkpoint_entry, render-outcome)
//   anything else -> null (build_phase 'tasks-gate' etc. — used to make a3 park at workhorse)
// ---------------------------------------------------------------------------
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// A minimal usable-draft signals blob: text has valid frontmatter + non-empty body,
// recorded === expected (both truthy) so front_half.isUsableDraft returns true.
const USABLE_SIGNALS = JSON.stringify({
  text: '---\nfrontmatter\n---\n# Body\n\ncontent',
  recorded: 'sha:smoke',
  expected: 'sha:smoke',
  sections: [],
})

function makeAgentStub() {
  return async function agent(prompt, opts) {
    const label = (opts && opts.label) || ''

    if (label === 'exec') {
      // exec() dispatches as a batch; each result is {index, ok, stdout}.
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        // reconcile(): empty snapshot -> recoverTwin gets undefined checkpoint/world -> world_derive
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        // readGate() for spec, plan, or tasks: always return 'passed'
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('front_half_usable.py')) {
        // usableDraft(): return a usable draft so producePhase short-circuits (no author agent)
        return [{ index: 0, ok: true, stdout: USABLE_SIGNALS }]
      }
      if (typeof prompt === 'string' && prompt.includes('front_half.py append-notify')) {
        return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
      }
      // Any other exec batch: return ok (e.g. definition_doc set-gate batched in persistPhase)
      return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
    }

    if (label === 'lib') {
      // cmdRunner stubs: journal_entry, checkpoint_entry, render-outcome
      if (typeof prompt === 'string' && prompt.includes('journal_entry')) return { ok: true }
      if (typeof prompt === 'string' && prompt.includes('checkpoint_entry')) return { ok: true, pr: null }
      if (typeof prompt === 'string' && prompt.includes('phase_step_cli')) {
        throw new Error('phase_step_cli dispatched as agent — must use JS twin')
      }
      if (typeof prompt === 'string' && prompt.includes('render-outcome')) {
        // Return a plain string so frontHalfBoundary uses it as the park reason
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
      const result = await sr.showrunner({ workItem: 'wi' })
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
      const result = await sr.showrunner({ workItem: 'wi' })
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
      const result = await sr.showrunner({ workItem: 'wi' })
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
