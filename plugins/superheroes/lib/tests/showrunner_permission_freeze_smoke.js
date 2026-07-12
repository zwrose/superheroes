// plugins/superheroes/lib/tests/showrunner_permission_freeze_smoke.js
// Task 12 + #402 (FR-8, UFR-9 wiring): the spine, at run start, freezes the current rules once and
// publishes the run identity for the composed-exact recorder, so evaluate()'s composed-exact set is
// populated for the run that composed the commands — and only that run.
//   (1) showrunner() calls permission_rules.freeze_run_rules(run_id, cwd) exactly ONCE at run start,
//       with the run_id = the lease generation reconcile() acquired (via the injectable seam), and
//       publishes globalThis.__SR_RUN so the courier chokepoint can record against that run_id.
//   (2) #402: the build phase NO LONGER records the builder-leaf PROMPT (dead weight per #333 — a
//       subagent prompt is never executed as a shell command). Composed-exact is re-aligned to executed
//       bytes at the courier chokepoint instead (see showrunner_composed_exact_smoke.js).
//   (3) both seams shell the SAME Python permission_rules helpers (byte-exact hashing lives in Python —
//       the JS side never re-implements the hash), and both are fail-open (a freeze/record error is
//       logged and the run proceeds — UFR-2).
// Run: node plugins/superheroes/lib/tests/showrunner_permission_freeze_smoke.js
require('./_smoke_checkout_root.js')
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// ---------------------------------------------------------------------------
// (1) showrunner() freezes the rules ONCE at run start with the reconcile generation as run_id.
// ---------------------------------------------------------------------------
async function freezeOnceAtRunStart() {
  const frozen = []
  const origFreeze = sr._freezeRunRules
  sr._freezeRunRules = (runId, cwd, workItem) => { frozen.push({ runId, cwd, workItem }) }

  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // reconcile()'s 'gather snapshot' exec -> a fresh world_derive snapshot with a generation.
    if (label === 'gather snapshot') {
      return markedStdout({
        root: '/repo', generation: 'GEN9', checkpoint: null,
        world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
      })
    }
    // readStartupState()'s courier -> spec NOT yet approved, so the run parks at the startup gate
    // immediately AFTER the run-start freeze has fired (freeze is threaded off the reconcile
    // generation, which is known before the startup gate is read).
    if (label === 'read startup state') {
      return JSON.stringify({ ok: true, spec_gate: 'pending', model_overrides: {}, doc_dir: '', engine_prefs: {} })
    }
    if (label === 'release lease') return JSON.stringify({ ok: true })
    if (opts && opts.courier) return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
    return null
  }
  let out
  try {
    out = await sr.showrunner({ workItem: 'wi-freeze' })
  } finally {
    sr._freezeRunRules = origFreeze
  }
  assert.strictEqual(out && out.outcome, 'parked', 'the run parks at the startup gate (spec pending)')
  assert.strictEqual(out.phase, 'startup', 'the park is at the startup gate — proving freeze fired at run start')

  assert.strictEqual(frozen.length, 1, 'freeze_run_rules is called exactly once at run start')
  assert.strictEqual(frozen[0].runId, 'GEN9', 'the freeze run_id is the reconcile lease generation')
  assert.ok(frozen[0].cwd, 'the freeze passes a cwd (the store is config-keyed off it)')
  assert.strictEqual(frozen[0].workItem, 'wi-freeze',
    'the freeze passes the work item (namespaces the per-run file — no cross-run collision)')
}

// ---------------------------------------------------------------------------
// (2) #402: the build phase NO LONGER records the builder-leaf PROMPT. Driving buildOneTask must not
//     feed the composed-exact recorder the (never-executed) builder prompt — that #333 dead-weight call
//     is gone. Composed-exact now rides the courier chokepoint (executed bytes), tested separately.
// ---------------------------------------------------------------------------
async function buildNeverRecordsTheBuilderPrompt() {
  const bp = require('../build_phase.js')
  const recorded = []
  // Observe the seam build_phase USED to call with the builder prompt (#333). If the dead-weight call
  // were still present, buildOneTask would push the builder prompt here.
  const origRecord = sr._recordComposed
  sr._recordComposed = (runId, command, workItem) => { recorded.push({ runId, command, workItem }) }

  const task = { id: '7', title: 'Do the thing' }
  const builderPrompt = bp.buildLeafPrompt({ wt: '/some/wt', branch: 'feat/x', task, workItem: 'wi-rec' })

  const savedRoot = globalThis.__SR_ROOT
  globalThis.__SR_ROOT = '/repo'
  // #402 review (test-005): prove buildOneTask actually REACHED the builder dispatch — the exact point the
  // removed #333 code recorded the prompt — so the negative assertion below is meaningful, not vacuously
  // satisfied by an early crash before that point.
  let reachedBuilderDispatch = false
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
    }
    if (label && label.startsWith('implement task')) { reachedBuilderDispatch = true; return { ok: true, signal: 'ok', evidence: {} } }
    if (opts && opts.courier) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '7' }) }]
    return { ok: true }
  }
  try {
    await bp.buildOneTask('wi-rec', 'GEN9', task, 'feat/x', '7', '/some/wt', 1)
  } catch (_e) {
    // buildOneTask may park on an unstubbed later sub-step in this minimal node harness — fine.
  } finally {
    sr._recordComposed = origRecord
    if (savedRoot !== undefined) globalThis.__SR_ROOT = savedRoot
    else delete globalThis.__SR_ROOT
  }

  assert.ok(reachedBuilderDispatch,
    'buildOneTask reached the builder dispatch (the removed #333 record site) — the negative check is not vacuous')
  assert.ok(!recorded.some((r) => r.command === builderPrompt),
    'the builder-leaf PROMPT is never registered as a composed-exact command (#333 dead weight removed)')
}

// ---------------------------------------------------------------------------
// (3) the default seams shell the SAME Python permission_rules helpers (no JS-side hashing) and are
//     fail-open: a runHelper error is swallowed and the run proceeds (UFR-2).
// ---------------------------------------------------------------------------
function defaultSeamsShellPythonAndFailOpen() {
  // The default freeze/record must be functions (the run-start + build wiring calls them).
  assert.strictEqual(typeof sr._freezeRunRules, 'function', '_freezeRunRules seam is exported')
  assert.strictEqual(typeof sr._recordComposed, 'function', '_recordComposed seam is exported')

  // Capture what the default seams shell — assert they invoke permission_rules.freeze_run_rules /
  // record_composed via the io() runHelper seam, never a JS re-implementation of the hash.
  const calls = []
  const savedIo = global.io
  global.io = Object.assign({}, savedIo, {
    runHelper: (cmd, args) => { calls.push({ cmd, args }); throw new Error('boom') },  // force an error
  })
  try {
    // fail-open: neither call may throw even though runHelper throws.
    assert.doesNotThrow(() => sr._freezeRunRules('GENX', '/cwd'), 'freeze seam is fail-open (UFR-2)')
    assert.doesNotThrow(() => sr._recordComposed('GENX', 'python3 -m pytest'), 'record seam is fail-open (UFR-2)')
  } finally { global.io = savedIo }

  assert.strictEqual(calls.length, 2, 'each default seam shells the Python helper exactly once')
  const joined = calls.map((c) => (c.args || []).join(' ')).join('\n')
  assert.ok(joined.includes('permission_rules'), 'the seams call the Python permission_rules module')
  assert.ok(joined.includes('freeze_run_rules'), 'the freeze seam calls freeze_run_rules')
  assert.ok(joined.includes('record_composed'), 'the record seam calls record_composed')
}

async function main() {
  await freezeOnceAtRunStart()
  await buildNeverRecordsTheBuilderPrompt()
  defaultSeamsShellPythonAndFailOpen()
  console.log('ok: spine freezes rules once at run start + never records the builder prompt (FR-8, UFR-9, #402)')
}

main().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
