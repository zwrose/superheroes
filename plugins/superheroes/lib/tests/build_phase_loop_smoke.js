require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_loop_smoke.js
// FR-4a contract: build_state gather runs ONCE at entry (not per loop iteration).
// reconcile is the in-process twin (build_progress.js), NOT an agent.
//
// #115 increment A: the IO leaves (read-gate, build_entry, task_list, gather, fence, journal,
// record-reviewed, record-final-review, prov_entry, verify_command, minor_rollup) are ported to
// exec(raw)+in-process-parse — they all route through the single 'exec' label, returning the exec
// array shape [{index,ok,stdout}] with stdout a JSON STRING (read-gate is a PLAIN STRING). The stub
// inspects the exec PROMPT (which lists "N. <command>") to choose the stdout. model_tier is now an
// in-process twin (no leaf) — its routes are gone.
//
// FR-4a re-assertion: the old smoke counted the 'gather-entry' label (now gone — all gathers are the
// identical 'exec' command). The loop-entry property is re-asserted by SPYING build_progress.reconcile
// (the twin called once at entry, twice on a dirty->reset re-reconcile). build_phase calls reconcile
// THROUGH the module (require('./build_progress.js').reconcile via _reconcile), so the spy takes effect.
const assert = require('assert')
const { routeMatches } = require('./_task_leaf_route.js')
global.log = () => {}
// reviewPanel uses parallel() — stub it to run all functions sequentially.
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }
function makeAgent(routes) {
  function routeMatchesLocal(label, needle) {
    if (routeMatches(label, needle)) return true
    if (needle === 'verify:r' && label.startsWith('verify:r')) return true
    if (String(needle).endsWith(':') && label.startsWith(needle)) return true
    return false
  }
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label.startsWith('branch-reviewer:')) {
      for (const [needle, resp] of routes) {
        if (typeof needle === 'string' && needle.startsWith('branch-reviewer')) {
          return typeof resp === 'function' ? resp(prompt) : resp
        }
      }
      return { findings: [] }
    }
    if (label === 'gather build state') {
      for (const [needle, resp] of routes) {
        if (needle === 'exec' && typeof resp === 'function') {
          const raw = resp('build_state_cli.py gather')
          const row = Array.isArray(raw) ? raw[0] : raw
          const stdout = (row && row.stdout != null) ? row.stdout : '{}'
          return [{ ok: true, stdout }]
        }
      }
    }
    // Exact/prefix label match first (labels are unique; `needle:` prefixes route per-round labels),
    // then a prompt-substring fallback. A function resp receives the prompt (capture).
    for (const [needle, resp] of routes) {
      if (routeMatchesLocal(label, needle)) return typeof resp === 'function' ? resp(prompt) : resp
    }
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    if (opts && opts.courier) { for (const [needle, resp] of routes) if (needle === 'exec') return typeof resp === 'function' ? resp(prompt) : resp }
    return ''
  }
}
const bp = require('../build_phase.js')
const bpg = require('../build_progress.js')

// reconcileSpy: install a counting spy around build_progress.reconcile (the FR-4a entry property).
// Returns { calls(), restore() }. build_phase calls reconcile through the module export, so the spy
// is observed. Always restore() in a finally so a failing assert doesn't leak the spy.
function reconcileSpy() {
  const orig = bpg.reconcile
  let n = 0
  bpg.reconcile = (...a) => { n += 1; return orig(...a) }
  return { calls: () => n, restore: () => { bpg.reconcile = orig } }
}

// execStub(map): a single 'exec' route. `map(prompt)` -> raw stdout STRING for the listed command.
// gather defaults are supplied per-test via the map; everything else returns the standard {ok:true}.
function execStub(map) {
  return ['exec', (prompt) => [{ index: 0, ok: true, stdout: map(prompt) }]]
}

// standardLeaf: the stdout for the non-gather IO leaves common to a clean build (fence/journal/
// record-reviewed/minor-rollup/record-final-review/verify_command/prov). prov can be made to fail.
function standardLeaf(p, { provOk = true } = {}) {
  if (p.includes('read-gate')) return 'passed'
  if (p.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' })
  if (p.includes('fence_cli.py')) return JSON.stringify({ ok: true })
  if (p.includes('journal_entry.py')) return JSON.stringify({ ok: true })
  if (p.includes('record-reviewed')) return JSON.stringify({ ok: true })
  if (p.includes('record-final-review')) return JSON.stringify({ ok: true })
  if (p.includes('minor_rollup_cli.py')) return JSON.stringify({ minors: [] })
  if (p.includes('verify_command_cli.py')) return JSON.stringify({ command: 'pytest -q' })
  if (p.includes('prov_entry.py')) return provOk ? JSON.stringify({ ok: true }) : JSON.stringify({ ok: false, error: 'disk' })
  return '{}'
}

// SMART agent routes shared by a clean build: worker + task reviewer + verdict decider, plus the
// whole-branch final-review verify gate (label 'verify:r<round>') which the panel runs as a leaf.
// reviewerAgent/recordDeferred are set on globalThis below.
const SMART_STUBS = [
  ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
  // #115 increment B: task_review is now an in-process TWIN (no leaf). The reviewer returns clean
  // verdicts + no findings, so the real twin decides 'complete' in-process — no stub route needed.
  ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
  ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
  ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
  ['read verify + minors', [{ ok: true, stdout: JSON.stringify({ ok: true, verify_command: 'none', minors: [] }) }]],
  ['branch-reviewer:', { findings: [] }],
  ['stamp build coverage', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true }) }]],
  ['run verify', { command: 'none', returncode: 0, timedOut: false }],
]

;(async () => {
  // ===========================================================================
  // (1) FR-4a CORE: a continuous 2-task run calls the loop-entry reconcile EXACTLY ONCE.
  //     A mutant that re-gathered+re-reconciled per task would bump reconcileCalls above 1.
  //     (The per-task trailer-check gather is a separate exec command and does NOT call reconcile.)
  // ===========================================================================
  {
    const spy = reconcileSpy()
    try {
      global.agent = makeAgent([
        execStub((p) => {
          if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }, { id: '2', title: 'B' }] })
          if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false })
          return standardLeaf(p)
        }),
        ...SMART_STUBS,
      ])
      globalThis.reviewerAgent = async () => ([])
      globalThis.recordDeferred = async () => {}
      const r = await bp.buildPhase('wi', 5)
      assert.strictEqual(r.confidence, 'high', 'continuous 2-task run should complete')
      assert.strictEqual(spy.calls(), 1,
        'FR-4a: entry reconcile must run EXACTLY ONCE on a continuous 2-task run (not per iteration)')
    } finally { spy.restore() }
  }

  // ===========================================================================
  // (2) Resume correctness: a fresh buildPhase invocation with task 1 already built+reviewed
  //     reconciles ONCE (re-derives state), then forward-walks from task 2.
  // ===========================================================================
  {
    const spy = reconcileSpy()
    try {
      global.agent = makeAgent([
        execStub((p) => {
          if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }, { id: '2', title: 'B' }] })
          if (p.includes('build_state_cli.py gather')) {
            return JSON.stringify({ committed_task_ids: ['1'], unmapped_commits: 0, worktree_dirty: false,
                                    review_records: { '1': 'passed' }, final_review: null, provenance: 'absent' })
          }
          return standardLeaf(p)
        }),
        ...SMART_STUBS,
      ])
      globalThis.reviewerAgent = async () => ([])
      globalThis.recordDeferred = async () => {}
      const r = await bp.buildPhase('wi', 5)
      assert.strictEqual(r.confidence, 'high', 'resume run should complete (task 2 built, final review clean)')
      assert.strictEqual(spy.calls(), 1,
        'resume correctness: entry reconcile runs ONCE to re-derive state after a park/crash')
    } finally { spy.restore() }
  }

  // ===========================================================================
  // (3) provenance written exactly once on a clean fresh single-task run (FR-9).
  // ===========================================================================
  {
    let provWrites = 0
    global.agent = makeAgent([
      execStub((p) => {
        if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
        if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false })
        if (p.includes('prov_entry.py')) { provWrites += 1; return JSON.stringify({ ok: true }) }
        return standardLeaf(p)
      }),
      ...SMART_STUBS,
    ])
    globalThis.reviewerAgent = async () => ([])
    globalThis.recordDeferred = async () => {}
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'high')
    assert.strictEqual(provWrites, 1, 'provenance written exactly once (FR-9)')
  }

  // ===========================================================================
  // (4) provenance write fails -> park (UFR-6).
  //     The entry carries final_review.clean=true + provenance:'absent', BUT an un-built task. The
  //     walk BUILDS the task -> didWork=true -> the entry final_review is STALE -> final review MUST
  //     RE-RUN. Then provenance fails -> park.
  // ===========================================================================
  {
    global.agent = makeAgent([
      execStub((p) => {
        if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
        if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false, final_review: { clean: true }, provenance: 'absent' })
        return standardLeaf(p, { provOk: false })
      }),
      ...SMART_STUBS,
    ])
    globalThis.reviewerAgent = async () => ([])
    globalThis.recordDeferred = async () => {}
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'low', 'provenance write failure parks (UFR-6)')
  }

  // ===========================================================================
  // (4b) FIX 3 REGRESSION: entry has final_review.clean=true (STALE — points at the pre-build HEAD)
  //      AND an un-built task. The walk MUST build the task, then RE-RUN the whole-branch final
  //      review (NOT skip on the stale entry state), and only THEN write provenance.
  // ===========================================================================
  {
    let workerBuilt = 0, finalReviewRan = 0, recordFinalReviews = 0, provWrites4b = 0
    global.agent = makeAgent([
      execStub((p) => {
        if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
        if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false, final_review: { clean: true }, provenance: 'absent' })
        if (p.includes('prov_entry.py')) { provWrites4b += 1; return JSON.stringify({ ok: true }) }
        return standardLeaf(p)
      }),
      ['implement-task', () => { workerBuilt += 1; return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }],
      ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
      ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
      ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
      ['read verify + minors', [{ ok: true, stdout: JSON.stringify({ ok: true, verify_command: 'none', minors: [] }) }]],
      ['branch-reviewer:r1', { findings: [] }],
      ['stamp build coverage', () => { recordFinalReviews += 1; return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true }) }] }],
      ['run verify', () => { finalReviewRan += 1; return { command: 'none', returncode: 0, timedOut: false } }],
    ])
    globalThis.reviewerAgent = async () => ([])
    globalThis.recordDeferred = async () => {}
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'high', 'stale-final-review + un-built task: build + re-review + prov -> high')
    assert.strictEqual(workerBuilt, 1, 'FIX 3: the un-built task IS built (didWork=true)')
    assert.ok(finalReviewRan >= 1, 'FIX 3: whole-branch final review RE-RUNS (NOT skipped on stale entry state)')
    assert.strictEqual(recordFinalReviews, 1, 'FIX 3: a fresh final-review-clean is recorded over the new HEAD')
    assert.strictEqual(provWrites4b, 1, 'FIX 3: provenance is RE-WRITTEN over the new HEAD (entry provenance not trusted)')
  }

  // ===========================================================================
  // (5) entry reconcile says park (unmapped commit) -> park immediately.
  // ===========================================================================
  {
    global.agent = makeAgent([
      execStub((p) => {
        if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
        if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 1, worktree_dirty: false })
        return standardLeaf(p)
      }),
    ])
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'low', 'unmapped commit at entry should park')
  }

  // ===========================================================================
  // (6) reset_uncommitted: entry reconcile says reset_uncommitted -> fence ok + reset ok
  //     -> re-gather + re-reconcile exactly once -> continue forward-walk (UFR-12).
  //     reconcile is called TWICE here (entry + after reset). reset-uncommitted is a SMART agent leaf.
  // ===========================================================================
  {
    const spy = reconcileSpy()
    let resets = 0, gathers = 0
    try {
      global.agent = makeAgent([
        execStub((p) => {
          if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
          if (p.includes('build_state_cli.py gather')) {
            gathers += 1
            // First gather: dirty. After reset, second gather: clean. (The per-built-task trailer
            // gather is also this command — but it returns clean too, so it never re-triggers reset.)
            return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: gathers === 1 })
          }
          return standardLeaf(p)
        }),
        ['reset-uncommitted', () => { resets += 1; return { ok: true } }],
        ...SMART_STUBS,
      ])
      globalThis.reviewerAgent = async () => ([])
      globalThis.recordDeferred = async () => {}
      const r = await bp.buildPhase('wi', 5)
      assert.strictEqual(r.confidence, 'high')
      assert.strictEqual(resets, 1, 'reset ran once (UFR-12)')
      assert.strictEqual(spy.calls(), 2, 'after reset: reconcile runs exactly twice (entry + re-reconcile)')
    } finally { spy.restore() }
  }

  // ===========================================================================
  // (7) reset fails -> park honestly (UFR-6), not a generic guard-bound park.
  // ===========================================================================
  {
    global.agent = makeAgent([
      execStub((p) => {
        if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
        if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: true })
        return standardLeaf(p)
      }),
      ['reset-uncommitted', { ok: false, error: 'dirty submodule' }],
    ])
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'low', 'a failed reset parks (UFR-6)')
    assert.ok(/could not reset/i.test((r.assumptions || [])[0] || ''), 'honest reset-failure reason')
  }

  // ===========================================================================
  // (8) FIX 4: reset reports ok BUT the re-gather is STILL dirty -> the re-reconcile is again
  //     reset_uncommitted. The code must PARK honestly (worktree still dirty after reset, UFR-12),
  //     NOT fall through into a dirty forward-walk.
  // ===========================================================================
  {
    let workerDispatched = 0
    global.agent = makeAgent([
      execStub((p) => {
        if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
        // BOTH gathers report dirty -> reconcile twin returns reset_uncommitted both times.
        if (p.includes('build_state_cli.py gather')) return JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, worktree_dirty: true })
        return standardLeaf(p)
      }),
      ['reset-uncommitted', { ok: true }],   // reset "succeeds" but doesn't actually clean the tree
      ['implement-task', () => { workerDispatched += 1; return { ok: true, signal: 'ok', evidence: {} } }],
    ])
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'low', 'FIX 4: a still-dirty tree after reset parks (UFR-12)')
    assert.ok(/still dirty after reset/i.test((r.assumptions || [])[0] || ''),
      'FIX 4: park reason names the still-dirty worktree (UFR-12)')
    assert.strictEqual(workerDispatched, 0, 'FIX 4: NO forward-walk worker dispatch over a dirty tree')
  }

  // ===========================================================================
  // (9) FAIL-CLOSED: the entry gather leaf FAILS to run (ok:false) -> park (the live bug class:
  //     never walk on an absent/mis-read git state).
  // ===========================================================================
  {
    global.agent = makeAgent([
      ['exec', (p) => {
        if (p.includes('build_state_cli.py gather')) return [{ index: 0, ok: false, stdout: 'leaf crashed' }]
        const stdout = p.includes('task_list_cli.py')
          ? JSON.stringify({ tasks: [{ id: '1', title: 'A' }] })
          : standardLeaf(p)
        return [{ index: 0, ok: true, stdout }]
      }],
    ])
    const r = await bp.buildPhase('wi', 5)
    assert.strictEqual(r.confidence, 'low', 'a failed entry gather leaf must park (fail closed)')
    assert.ok(/gather authoritative git state/i.test((r.assumptions || [])[0] || ''), 'honest gather fail-closed reason')
  }

  console.log('ok: build_phase FR-4a in-memory loop (reconcile-once, resume-once, FR-9/UFR-6/UFR-12, stale-final-review, double-dirty-park, exec fail-closed)')
})()
