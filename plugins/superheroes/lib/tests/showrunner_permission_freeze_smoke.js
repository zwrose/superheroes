// plugins/superheroes/lib/tests/showrunner_permission_freeze_smoke.js
// Task 12 (FR-8, UFR-9 wiring): the spine, at run start, freezes the current rules once and records
// each command it composes for a leaf, so evaluate()'s composed-exact set (Task 4) is populated for
// the run that composed them — and only that run.
//   (1) showrunner() calls permission_rules.freeze_run_rules(run_id, cwd) exactly ONCE at run start,
//       with the run_id = the lease generation reconcile() acquired (via the injectable seam).
//   (2) the build phase, at the point it composes a leaf command, calls
//       permission_rules.record_composed(run_id, command) with that same run_id.
//   (3) both seams shell the SAME Python permission_rules helpers (byte-exact hashing lives in Python —
//       the JS side never re-implements the hash), and both are fail-open (a freeze/record error is
//       logged and the run proceeds — UFR-2).
// Run: node plugins/superheroes/lib/tests/showrunner_permission_freeze_smoke.js
require('./_smoke_checkout_root.js')
const assert = require('assert')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// ---------------------------------------------------------------------------
// (1) showrunner() freezes the rules ONCE at run start with the reconcile generation as run_id.
// ---------------------------------------------------------------------------
async function freezeOnceAtRunStart() {
  const frozen = []
  const origFreeze = sr._freezeRunRules
  sr._freezeRunRules = (runId, cwd) => { frozen.push({ runId, cwd }) }

  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // reconcile()'s 'gather snapshot' exec -> a fresh world_derive snapshot with a generation.
    if (label === 'gather snapshot') {
      return [{ index: 0, ok: true, stdout: JSON.stringify({
        root: '/repo', generation: 'GEN9', checkpoint: null, world: {},
      }) }]
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
}

// ---------------------------------------------------------------------------
// (2) the build phase records each composed leaf command against the run's generation.
// ---------------------------------------------------------------------------
async function buildRecordsComposedLeafCommands() {
  const bp = require('../build_phase.js')
  const recorded = []
  const origRecord = sr._recordComposed
  sr._recordComposed = (runId, command) => { recorded.push({ runId, command }) }

  // Drive the REAL leaf-command composition: buildOneTask composes the leaf command via
  // buildLeafPrompt, then dispatches it. We only need to reach (and pass) that composition point —
  // the record must have fired by the time the dispatch returns. Stub the fence (needs __SR_ROOT +
  // a 'fence lease' ok) and the dispatch; let the task park on a later unstubbed sub-step (fine).
  const task = { id: '7', title: 'Do the thing' }
  const expectedPrompt = bp.buildLeafPrompt({ wt: '/some/wt', branch: 'feat/x', task })

  const savedRoot = globalThis.__SR_ROOT
  globalThis.__SR_ROOT = '/repo'
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      // execJson('fence lease') and the trailer 'check trailers' gather both ride exec: a 'fence
      // lease' batch must read ok:true; anything else returns a benign empty batch.
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
    }
    if (label && label.startsWith('implement task')) return { ok: true, signal: 'ok', evidence: {} }
    if (opts && opts.courier) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '7' }) }]
    return { ok: true }
  }
  try {
    await bp.buildOneTask('wi-rec', 'GEN9', task, 'feat/x', '7', '/some/wt', 1)
  } catch (_e) {
    // buildOneTask may park on an unstubbed later sub-step in this minimal harness — fine.
    // The record must have already fired at the leaf-command composition point regardless.
  } finally {
    sr._recordComposed = origRecord
    if (savedRoot !== undefined) globalThis.__SR_ROOT = savedRoot
    else delete globalThis.__SR_ROOT
  }

  assert.ok(recorded.length >= 1, 'the build phase records at least one composed leaf command')
  const hit = recorded.find((r) => r.command === expectedPrompt)
  assert.ok(hit, 'the recorded command is byte-exactly the composed leaf command')
  assert.strictEqual(hit.runId, 'GEN9', 'the composed command is recorded against the run generation')
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
  await buildRecordsComposedLeafCommands()
  defaultSeamsShellPythonAndFailOpen()
  console.log('ok: spine freezes rules once at run start + records each composed leaf command (FR-8, UFR-9)')
}

main().catch((e) => { console.error('FAIL:', e.message, e.stack); process.exit(1) })
