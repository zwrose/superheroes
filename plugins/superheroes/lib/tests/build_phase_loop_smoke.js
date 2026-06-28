// plugins/superheroes/lib/tests/build_phase_loop_smoke.js
// FR-4a contract: build_state gather runs ONCE at entry (not per loop iteration).
// reconcile is now the in-process twin (build_progress.js), NOT an agent.
// A mutant that kept the per-iteration gather MUST fail test (1) below.
//
// Label convention (enforced by implementation):
//   'gather-entry'              -- the loop-entry/resume gather (must be ≤1 per continuous run)
//   'build_state_cli.py gather' -- the per-built-task trailer-check gather (UFR-7, one per task built)
// These labels are distinguishable so the smoke can pin the FR-4a property exactly.
const assert = require('assert')
global.log = () => {}
// reviewPanel uses parallel() — stub it to run all functions sequentially.
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // Exact-label first (labels are unique), so a short needle never shadows a longer script name
    // via substring; then a prompt-substring fallback. A function resp receives the prompt (capture).
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}
const bp = require('../build_phase.js')

// Shared BASE stubs: gate/setup/task_list.
const SETUP_STUBS = [
  ['read-gate --doc tasks', 'passed'],
  ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
]

// makeWorkerStubs: returns stubs for a SUCCESSFUL single-task build (fence + worker + trailer-check
// + journal + review clean + record-reviewed). The trailer-check gather uses label
// 'build_state_cli.py gather' (UFR-7 per-built-task correctness read — stays in place).
function makeWorkerStubs() {
  return [
    ['fence_cli.py', { ok: true }],
    ['worker', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['build_state_cli.py gather', { committed_task_ids: [], unmapped_commits: 0 }],
    ['journal_entry.py', { ok: true }],
    ['model_tier_resolve.py', { model: 'sonnet' }],
    ['record-reviewed', { ok: true }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['task_review_cli.py', { action: 'complete', blocking: [], minors: [], cannot_verify: [] }],
  ]
}

// makeFinalReviewStubs: stubs for final-review + provenance steps.
// verify_gate.py returns a 'pass' result so the round ends clean; reviewerAgent (set on globalThis
// to return []) provides zero findings -> tally -> terminal: 'clean'.
function makeFinalReviewStubs(provOk) {
  return [
    ['verify_command_cli.py', { command: 'none' }],
    ['model_tier_resolve.py --role reviewer-deep', { model: 'sonnet' }],
    ['model_tier_resolve.py --role fixer', { model: 'sonnet' }],
    ['minor_rollup_cli.py', { minors: [] }],
    // verify_gate.py is called by verifyAgent (label 'verify:r<round>') when legKind.code:true.
    // Match the prompt substring so it covers any round number.
    ['verify_gate.py', { result: 'pass' }],
    ['record-final-review', { ok: true }],
    ['prov_entry.py', provOk !== false ? { ok: true } : { ok: false, error: 'disk' }],
  ]
}

;(async () => {
  // ===========================================================================
  // (1) FR-4a CORE: a continuous 2-task run calls the loop-entry gather EXACTLY ONCE,
  //     NOT once per task. The per-task trailer-check (label 'build_state_cli.py gather')
  //     runs once per built task and is CORRECT to remain — it is NOT the per-iteration
  //     resume gather. A mutant that kept the per-iteration gather would set entryGathers=2
  //     and FAIL this assertion.
  // ===========================================================================
  let entryGathers = 0
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }, { id: '2', title: 'B' }] }],
    // Label 'gather-entry': loop-entry gather, counted here. Must appear EXACTLY ONCE.
    ['gather-entry', () => { entryGathers += 1; return { committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false } }],
    ...makeWorkerStubs(),
    ...makeWorkerStubs(),
    ...makeFinalReviewStubs(),
  ])
  globalThis.reviewerAgent = async () => ([])
  globalThis.recordDeferred = async () => {}
  let r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high', 'continuous 2-task run should complete')
  assert.strictEqual(entryGathers, 1,
    'FR-4a: loop-entry gather must be called EXACTLY ONCE on a continuous 2-task run (not per iteration)')

  // ===========================================================================
  // (2) Resume correctness: a fresh buildPhase invocation with task 1 already built+reviewed
  //     calls the entry gather ONCE (re-derives state), then forward-walks from task 2.
  // ===========================================================================
  let resumeEntryGathers = 0
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }, { id: '2', title: 'B' }] }],
    ['gather-entry', () => {
      resumeEntryGathers += 1
      // Task 1 already committed and reviewed; task 2 not yet built
      return { committed_task_ids: ['1'], unmapped_commits: 0, worktree_dirty: false,
               review_records: { '1': 'passed' }, final_review: null, provenance: 'absent' }
    }],
    ...makeWorkerStubs(),   // for task 2
    ...makeFinalReviewStubs(),
  ])
  globalThis.reviewerAgent = async () => ([])
  globalThis.recordDeferred = async () => {}
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high', 'resume run should complete (task 2 built, final review clean)')
  assert.strictEqual(resumeEntryGathers, 1,
    'resume correctness: entry gather is called ONCE to re-derive state after a park/crash')

  // ===========================================================================
  // (3) provenance written exactly once on a clean fresh single-task run (FR-9).
  // ===========================================================================
  let provWrites = 0
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }] }],
    ['gather-entry', { committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false }],
    ...makeWorkerStubs(),
    ['verify_command_cli.py', { command: 'none' }],
    ['model_tier_resolve.py --role reviewer-deep', { model: 'sonnet' }],
    ['model_tier_resolve.py --role fixer', { model: 'sonnet' }],
    ['minor_rollup_cli.py', { minors: [] }],
    ['verify_gate.py', { result: 'pass' }],
    ['record-final-review', { ok: true }],
    ['prov_entry.py', () => { provWrites += 1; return { ok: true } }],
  ])
  globalThis.reviewerAgent = async () => ([])
  globalThis.recordDeferred = async () => {}
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.strictEqual(provWrites, 1, 'provenance written exactly once (FR-9)')

  // ===========================================================================
  // (4) provenance write fails -> park (UFR-6).
  // ===========================================================================
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }] }],
    ['gather-entry', { committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false,
                       final_review: { clean: true }, provenance: 'absent' }],
    ...makeWorkerStubs(),
    ...makeFinalReviewStubs(false),
  ])
  globalThis.reviewerAgent = async () => ([])
  globalThis.recordDeferred = async () => {}
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low', 'provenance write failure parks (UFR-6)')

  // ===========================================================================
  // (5) entry reconcile says park (unmapped commit) -> park immediately.
  // ===========================================================================
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }] }],
    // unmapped_commits > 0 -> reconcile (twin) returns park
    ['gather-entry', { committed_task_ids: [], unmapped_commits: 1, worktree_dirty: false }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low', 'unmapped commit at entry should park')

  // ===========================================================================
  // (6) reset_uncommitted: entry reconcile says reset_uncommitted -> fence ok + reset ok
  //     -> re-gather + re-reconcile exactly once -> continue forward-walk (UFR-12).
  // ===========================================================================
  let resets = 0
  let reGathers = 0
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }] }],
    ['gather-entry', () => {
      reGathers += 1
      // First gather: dirty. After reset, second gather: clean.
      if (reGathers === 1) return { committed_task_ids: [], unmapped_commits: 0, worktree_dirty: true }
      return { committed_task_ids: [], unmapped_commits: 0, worktree_dirty: false }
    }],
    ['fence_cli.py', { ok: true }],
    ['reset-uncommitted', () => { resets += 1; return { ok: true } }],
    ...makeWorkerStubs(),
    ...makeFinalReviewStubs(),
  ])
  globalThis.reviewerAgent = async () => ([])
  globalThis.recordDeferred = async () => {}
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.strictEqual(resets, 1, 'reset ran once (UFR-12)')
  assert.strictEqual(reGathers, 2, 'after reset: re-gather exactly once (reset is a resume-like event)')

  // ===========================================================================
  // (7) reset fails -> park honestly (UFR-6), not a generic guard-bound park.
  // ===========================================================================
  global.agent = makeAgent([
    ...SETUP_STUBS,
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }] }],
    ['gather-entry', { committed_task_ids: [], unmapped_commits: 0, worktree_dirty: true }],
    ['fence_cli.py', { ok: true }],
    ['reset-uncommitted', { ok: false, error: 'dirty submodule' }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low', 'a failed reset parks (UFR-6)')
  assert.ok(/could not reset/i.test((r.assumptions || [])[0] || ''), 'honest reset-failure reason')

  console.log('ok: build_phase FR-4a in-memory loop (gather-once, resume-once, FR-9/UFR-6/UFR-12)')
})()
