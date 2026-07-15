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
// Seed/read fixtures from the acquire authority (__SR_ROOT), not the launch cwd.
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const { markedStdout, saveProgressOk } = require('./_marked_stdout.js')
const fs = require('fs')
const path = require('path')
const sr = require('../showrunner.js')

// pid-unique work item: the run-mode outcome envelope stages machine-global payload files derived
// from the work-item name (/tmp/showrunner-<wi>-fronthalf-*.json*), so a fixed name collides with
// a concurrent pytest suite on this machine (see _final_review_probe.js for the flake story).
// The pid-named files are reaped on a PASSING exit; a failing run keeps them as evidence.
const WI = `wi-pid${process.pid}`
const cleaned = new Set()
process.on('exit', (code) => {
  if (code !== 0) return
  for (const f of [`/tmp/showrunner-${WI}-fronthalf-outcome.json`,
                   `/tmp/showrunner-${WI}-fronthalf-outcome.json.payload`,
                   `/tmp/showrunner-${WI}-fronthalf-readout-tmp.json`]) {
    try { fs.rmSync(f, { force: true }) } catch (_) {}
  }
  for (const wi of cleaned) {
    for (const doc of ['plan', 'tasks']) {
      try { fs.rmSync(`/tmp/showrunner-${wi}-review-${doc}`, { recursive: true, force: true }) } catch (_) {}
    }
    try { fs.rmSync(`docs/superheroes/${wi}`, { recursive: true, force: true }) } catch (_) {}
  }
})

function receiptFromPrompt(prompt) {
  let ctx = { receiptArtifact: 'stub', receiptCoverageDecisionIds: [] }
  const m = String(prompt || '').match(/Prompt context: (\{.*\})/s)
  if (m) { try { ctx = JSON.parse(m[1]) } catch (_) {} }
  return {
    artifact: ctx.receiptArtifact || 'stub',
    chain: [
      { step: 'citation', evidence: 'reviewed citations' },
      { step: 'reachability', evidence: 'validated call path' },
      { step: 'missing-check', evidence: 'checked missing FRs' },
      { step: 'tooling', evidence: 'smoke passed' },
    ],
    coverageDecisionIds: ctx.receiptCoverageDecisionIds || [],
  }
}

function seedDocs(wi) {
  cleaned.add(wi)
  for (const doc of ['plan', 'tasks']) {
    try { fs.rmSync(`/tmp/showrunner-${wi}-review-${doc}`, { recursive: true, force: true }) } catch (_) {}
  }
  const dir = `docs/superheroes/${wi}`
  try {
    fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(`${dir}/plan.md`, '# Plan\n## Review coverage decisions\n')
    fs.writeFileSync(`${dir}/tasks.md`, '# Tasks\n## Review coverage decisions\n')
  } catch (_) {}
}

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
      return [{ ok: true, stdout: markedStdout({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', run_overrides_present: false }) }]
    }

    if (label === 'save phase progress') {
      return saveProgressOk()
    }
    if (label === 'save round state') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
    }

    // Dumb-pipe (courier) leaves are routed by the command in their prompt, regardless of the
    // descriptive label ('gather snapshot'/'read gate'/'check draft'/'append notify'). The generic
    // courier catch-all lives AFTER the named 'save phase progress' branch so it never swallows it.
    if (opts && opts.courier && typeof prompt === 'string') {
      if (prompt.includes('recover_entry.py')) {
        return markedStdout({
          checkpoint: null,
          world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
          generation: 1,
          root: globalThis.__SR_ROOT,
        })
      }
      if (prompt.includes('definition_doc.py read-gate')) {
        return [{ index: 0, ok: true, stdout: '{"review":"pending"}' }]
      }
      if (prompt.includes('front_half_usable.py')) {
        return [{ index: 0, ok: true, stdout: USABLE_SIGNALS }]
      }
      if (prompt.includes('front_half.py append-notify')) {
        return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
      }
      if (prompt.includes('loop_readout.py')) {
        return [{ index: 0, ok: true, stdout: '## stub readout\n\n- terminal: clean\n' }]
      }
      if (prompt.includes('review_convergence.py')) {
        const m = String(prompt).match(/^\d+\.\s(.*)$/m)
        const cmd = m ? m[1] : null
        const stdout = require('child_process').execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('review_handoff.py')) {
        if (prompt.includes(' write ')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, counts: { distinct: 0 } }) }]
        }
        if (prompt.includes(' read')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, reason: 'absent' }) }]
        }
      }
      if (prompt.includes('gate-for-terminal')) {
        throw new Error('gate-for-terminal dispatched as exec — must use JS twin')
      }
      return [{ index: 0, ok: true, stdout: '{"ok":true}' }, { index: 1, ok: true, stdout: '' }]
    }

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

    if (prompt.includes('gate-for-terminal')) {
      throw new Error('gate-for-terminal dispatched as cmdRunner — must use JS twin')
    }
    if (label.endsWith('-reviewer')) {
      return { findings: [], confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    if (label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'revise-doc') return { fixes: [], deferred: [] }

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
      seedDocs(WI)
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
      seedDocs(WI)
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
