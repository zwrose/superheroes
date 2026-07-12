// plugins/superheroes/lib/tests/showrunner_startup_engineprefs_smoke.js
// #221: the startup gather resolves engine preferences from an OUT-OF-REPO core.md. The shipped gather
// passed the repo ROOT into load_engine_prefs's store-base slot, so core.md resolved to a nonexistent
// <repo>/projects/<key>/config/core.md and EVERY run silently degraded to all-claude. The canned-answer
// startup smokes (showrunner_startup_fold / _engine_review) were blind to this — they stub the courier
// and never run the real Python. This smoke runs the REAL gather script (showrunner.startupStateScript)
// against a real out-of-repo fixture and asserts the owner's non-claude prefs round-trip; the adversarial
// control mutates the shipped script back to the (root, root) bug and asserts it degrades to all-claude
// (which also proves the fixture's core.md is genuinely OUT-OF-REPO — reachable only via the default store).
'use strict'
const assert = require('assert')
const cp = require('child_process')
const fs = require('fs')
const os = require('os')
const path = require('path')

const LIB = path.resolve(__dirname, '..')
global.log = () => {}
const sr = require('../showrunner.js')

// Build a fresh git repo + a separate out-of-repo store, and write core.md (carrying non-claude engine
// prefs) into the store via the REAL core_md write path. A fresh repo with no calibration evidence
// resolves to GLOBAL (out-of-repo) mode, so the write lands in the store, not in-repo.
function mkFixture() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'sr-ep-'))
  const repo = path.join(base, 'repo')
  const store = path.join(base, 'store')
  fs.mkdirSync(repo)
  fs.mkdirSync(store)
  cp.execFileSync('git', ['init', '-q', repo], { stdio: 'ignore' })
  const facts = {
    verifyCommand: 'npm test', stackTags: [], threatModel: 'x', patterns: '',
    enginePreferences: { reviewer: 'codex', implementation: 'cursor' },
  }
  cp.execFileSync('python3', [path.join(LIB, 'core_md.py'), 'write', '--cwd', repo, '--root', store, '--status', 'confirmed'],
    { input: JSON.stringify(facts), stdio: ['pipe', 'ignore', 'inherit'] })
  return { base, repo, store }
}

// Run a gather-script variant against the fixture (cwd = the repo, store-base = the env seam) and return
// the JSON it printed. Mirrors production: `python3 -c <script> <workItem> <repoRoot>`.
function runGather(script, repo, store) {
  const out = cp.execFileSync('python3', ['-c', script, 'wi', repo], {
    cwd: repo,
    env: Object.assign({}, process.env, { SUPERHEROES_STORE_ROOT: store }),
    encoding: 'utf8',
  })
  return JSON.parse(out)
}

;(async () => {
  // pyLibDir() is read at CALL time; plant the absolute real lib dir so `python3 -c` can import the
  // spine modules regardless of the fixture cwd (a fresh repo has no plugins/superheroes/lib under it).
  globalThis.__SR_LIB = LIB
  const script = sr.startupStateScript()

  // Call-site guard: the shipped gather must pass None (the default store), NOT the repo root.
  assert.ok(/load_engine_prefs\(root, None\)/.test(script),
    '#221: the shipped gather must pass None (the default store) into load_engine_prefs\'s store-base slot, not the repo root')

  const { base, repo, store } = mkFixture()
  try {
    // (1) The FIXED gather round-trips the owner's out-of-repo enginePreferences.
    const fixed = runGather(script, repo, store)
    assert.deepStrictEqual(
      { reviewer: fixed.engine_prefs.reviewer, implementation: fixed.engine_prefs.implementation },
      { reviewer: 'codex', implementation: 'cursor' },
      '#221: the startup gather must round-trip the owner\'s out-of-repo enginePreferences (was silently all-claude before the fix)')

    // (2) Adversarial control: the OLD (root, root) call — the exact regression — degrades to all-claude,
    //     proving the fixture's core.md is genuinely out-of-repo (only reachable via the default store).
    const buggy = script.replace('load_engine_prefs(root, None)', 'load_engine_prefs(root, root)')
    assert.notStrictEqual(buggy, script, 'the buggy control must actually differ from the shipped script')
    const degraded = runGather(buggy, repo, store)
    assert.deepStrictEqual(
      { reviewer: degraded.engine_prefs.reviewer, implementation: degraded.engine_prefs.implementation },
      { reviewer: 'claude', implementation: 'claude' },
      '#221: passing the repo root into the store-base slot silently degrades to all-claude (the shipped bug)')

    // ── A (persisted-record end-to-end): drive the WHOLE frozen-snapshot boundary with the REAL Python.
    // run_overrides.write persists a record with a frozenSnapshot -> the REAL startupStateScript gather
    // reads it and emits `frozen_snapshot` (+ `run_overrides_present`) over the courier boundary -> the
    // parsed JSON feeds sr.mergeFrozenSnapshot -> a builder model pin + a build engine pin are planted.
    // A key-name typo on EITHER side of the courier boundary (write's "frozenSnapshot" vs the gather's
    // `_rec.get("frozenSnapshot")`, or the emitted "frozen_snapshot" vs mergeFrozenSnapshot's read) makes
    // frozen_snapshot arrive null and the pin assertions below fail — the gap this smoke exists to close.
    const frozenSnapshot = {
      workItem: 'wi', version: sr.READOUT_VERSION,
      phases: [
        { phase: 'workhorse', role: 'builder', kind: 'build', engine: 'codex', model: 'opus',
          engineModel: 'gpt-5.6-sol', effort: 'high' },
      ],
    }
    // Persist through the REAL run_overrides.write, into the SAME store/cwd/root the gather reads with.
    const writeScript = [
      'import json, sys',
      'sys.path.insert(0, sys.argv[1])',
      'import run_overrides',
      'snap = json.loads(sys.argv[4])',
      'ok = run_overrides.write(sys.argv[2], sys.argv[3], {}, snap)',
      'print(json.dumps({"ok": ok}))',
    ].join('\n')
    const wrote = JSON.parse(cp.execFileSync('python3',
      ['-c', writeScript, LIB, 'wi', repo, JSON.stringify(frozenSnapshot)],
      { cwd: repo, env: Object.assign({}, process.env, { SUPERHEROES_STORE_ROOT: store }), encoding: 'utf8' }))
    assert.strictEqual(wrote.ok, true, 'run_overrides.write must persist the record')

    // The REAL gather now carries the frozen snapshot + the presence flag across the courier boundary.
    const withSnap = runGather(script, repo, store)
    assert.ok(withSnap.frozen_snapshot && Array.isArray(withSnap.frozen_snapshot.phases),
      'A: the gather output must carry frozen_snapshot with its phases array (courier boundary intact)')
    assert.strictEqual(withSnap.frozen_snapshot.phases[0].role, 'builder',
      'A: the persisted frozenSnapshot builder row round-trips through the gather')
    assert.strictEqual(withSnap.run_overrides_present, true,
      'D: run_overrides_present is true when a frozenSnapshot record existed on disk')

    // Feed the gather-parsed snapshot through the REAL merge and assert the planted pins.
    const merged = sr.mergeFrozenSnapshot(withSnap.frozen_snapshot,
      { builder: 'sonnet' }, { reviewer: 'claude', implementation: 'claude', effort: {} })
    assert.strictEqual(merged.overrides.builder, 'opus',
      'A: the frozen builder model (opus) is pinned end-to-end, winning over the config-derived value')
    assert.strictEqual(merged.enginePrefs.implementation, 'codex',
      'A: the frozen build engine (codex) is pinned onto the implementation engine-pref key')
    assert.strictEqual(merged.enginePrefs.effort.build, 'high',
      'A: the frozen build effort (high) is pinned onto the effort sub-map')

    // D control: a courier answer that DROPS frozen_snapshot but keeps run_overrides_present still lets
    // the merge no-op, and the presence flag is what tells the caller to narrate the silent revert.
    const dropped = Object.assign({}, withSnap, { frozen_snapshot: null })
    const droppedMerge = sr.mergeFrozenSnapshot(
      (dropped.frozen_snapshot && typeof dropped.frozen_snapshot === 'object') ? dropped.frozen_snapshot : null,
      { builder: 'sonnet' }, { reviewer: 'claude', implementation: 'claude', effort: {} })
    assert.strictEqual(droppedMerge.pinnedCount, 0, 'D: a dropped frozen_snapshot pins nothing')
    assert.strictEqual(dropped.run_overrides_present, true,
      'D: run_overrides_present stays true even when frozen_snapshot is dropped — the caller can detect the revert')
  } finally {
    fs.rmSync(base, { recursive: true, force: true })
    delete globalThis.__SR_LIB
  }

  console.log('ok: #221 startup gather round-trips out-of-repo engine prefs; A: persisted frozenSnapshot flows write->gather->merge->pins; D: run_overrides_present detectability')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack || ''); process.exit(1) })
