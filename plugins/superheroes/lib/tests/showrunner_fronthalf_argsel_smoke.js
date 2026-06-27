// Smoke: args-based front-half selector for Workflow-tool live runs (Task 13a, #115).
//
// Asserts BOTH halves of the feature:
//   (A) showrunner.js side — globalThis.SUPERHEROES_FRONT_HALF_NATIVE + SUPERHEROES_BUNDLE_FULL_RUN=false
//       wires deps.frontHalfBoundary (parks); the existing env selector still works the same way;
//       full-run default (no flags) wires no boundary.
//   (B) bundle ENTRY side — the regenerated bundle's ENTRY maps args.frontHalf==='native' to both
//       globals (text/structure assertion, not a full eval of the entry).
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'exec') {
    return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
  }
  if (label === 'lib') {
    if (prompt.includes('journal_entry')) return { ok: true }
    if (prompt.includes('checkpoint_entry')) return { ok: true, pr: null }
    if (prompt.includes('phase_step_cli')) throw new Error('phase_step_cli dispatched as agent — must use JS twin')
    return { ok: true }
  }
  return null
}

async function main() {
  // --- PART A: showrunner.js side ---

  // (a1) args-based selector: globalThis flags set (as the ENTRY would set them for args.frontHalf==='native')
  //      -> wires frontHalfBoundary and parks.
  {
    const savedFull = globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    const savedNative = globalThis.SUPERHEROES_FRONT_HALF_NATIVE
    try {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = false
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = true
      const seen = []
      const deps = {
        produce: async (phase) => { seen.push('produce:' + phase); return { confidence: 'high', assumptions: [] } },
        reviewDoc: async (doc) => { seen.push('reviewDoc:' + doc); return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' } },
        frontHalfBoundary: async () => ({ outcome: 'parked', phase: 'front-half-boundary', reason: 'boundary' }),
        build: async () => { seen.push('build'); return { confidence: 'high', assumptions: [] } },
      }
      const result = await sr.runPhases('wi', 0, deps)
      assert.strictEqual(result.phase, 'front-half-boundary', 'a1: globalThis FRONT_HALF_NATIVE parks at boundary')
      assert.ok(!seen.includes('build'), 'a1: build NOT reached when FRONT_HALF_NATIVE=true')
    } finally {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = savedFull
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = savedNative
    }
  }

  // (a2) existing env selector still works (regression guard): SUPERHEROES_FRONT_HALF=native via procEnv.
  {
    const savedFull = globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    const savedNative = globalThis.SUPERHEROES_FRONT_HALF_NATIVE
    const origEnv = process.env.SUPERHEROES_FRONT_HALF
    try {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = false
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = false
      process.env.SUPERHEROES_FRONT_HALF = 'native'
      const seen = []
      const deps = {
        produce: async (phase) => { seen.push('produce:' + phase); return { confidence: 'high', assumptions: [] } },
        reviewDoc: async (doc) => { seen.push('reviewDoc:' + doc); return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' } },
        frontHalfBoundary: async () => ({ outcome: 'parked', phase: 'front-half-boundary', reason: 'boundary' }),
        build: async () => { seen.push('build'); return { confidence: 'high', assumptions: [] } },
      }
      const result = await sr.runPhases('wi', 0, deps)
      assert.strictEqual(result.phase, 'front-half-boundary', 'a2: env selector still parks at boundary')
      assert.ok(!seen.includes('build'), 'a2: build NOT reached with env selector')
    } finally {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = savedFull
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = savedNative
      if (origEnv === undefined) delete process.env.SUPERHEROES_FRONT_HALF
      else process.env.SUPERHEROES_FRONT_HALF = origEnv
    }
  }

  // (a3) default (no flags, full-run): showrunner's run-mode block does NOT inject frontHalfBoundary
  //      into deps when SUPERHEROES_BUNDLE_FULL_RUN=true + no env/globalThis flag.
  //      We probe this by calling runPhases directly WITHOUT frontHalfBoundary in deps and fromStep=4
  //      (workhorse/build); since no boundary dep is present, runPhases proceeds to build (throws STOP).
  //      If the args-selector incorrectly injected a boundary, we'd park instead of throw.
  {
    const savedFull = globalThis.SUPERHEROES_BUNDLE_FULL_RUN
    const savedNative = globalThis.SUPERHEROES_FRONT_HALF_NATIVE
    const origEnv = process.env.SUPERHEROES_FRONT_HALF
    try {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true
      delete globalThis.SUPERHEROES_FRONT_HALF_NATIVE
      delete process.env.SUPERHEROES_FRONT_HALF
      const seen = []
      // No frontHalfBoundary in deps -> runPhases must NOT park; it reaches build (which throws STOP).
      const deps = {
        build: async () => { seen.push('build'); throw new Error('STOP') },
      }
      try { await sr.runPhases('wi', 4, deps) } catch (e) {
        assert.ok(e.message === 'STOP', 'a3: full-run reached build (no boundary park)')
      }
      assert.ok(seen.includes('build'), 'a3: full-run default reaches build, not a boundary park')
    } finally {
      globalThis.SUPERHEROES_BUNDLE_FULL_RUN = savedFull
      globalThis.SUPERHEROES_FRONT_HALF_NATIVE = savedNative
      if (origEnv === undefined) delete process.env.SUPERHEROES_FRONT_HALF
      else process.env.SUPERHEROES_FRONT_HALF = origEnv
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

  console.log('ok: args-based front-half selector (globalThis flags, env path, full-run default, bundle ENTRY)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
