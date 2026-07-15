// plugins/superheroes/lib/build_phase.js
// The native "workhorse" build phase (#87). CONTROL FLOW ONLY: this module detects events and
// sequences them — it makes NO judgement inline. #115: every judgement is an in-process parity-locked
// JS twin (model_tier / worker_recovery / task_review / build_progress.reconcile); every IO/side-effect
// runs through the exec(raw)+in-process-parse dumb pipe, parsed deterministically and fail-closed (the
// old "trust-the-leaf-JSON" *_cli.py bridge is gone). It makes NO PR/merge/force-push (FR-10).
// FR-4a (#115): build state lives in memory during a continuous run. build_state gather /
// build_progress.reconcile are called ONLY on entry/resume (not per loop iteration).
const { reviewPanel, verifyAgent: shellVerifyAgent } = require('./review_panel_shell.js')
const { io } = require('./io_seam.js')
const modelTierTwin = require('./model_tier.js')
const courier = require('./courier_exec.js')
// #115 increment B: the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (no leaf — judgments live in twins, called in-process). Pure
// deciders with no IO, so a top-level require is safe (no load-time cycle).
const workerRecoveryTwin = require('./worker_recovery.js')
const taskReviewTwin = require('./task_review.js')
// #160/#276: circuit_breaker.isBlocking is the single, case-normalized, FAIL-CLOSED blocking predicate
// the task_review twin's partition also reads. Used here to synthesize the per-task review's two
// verdicts from an external engine's findings-only result and to filter whole-branch blockers for the
// final-review fixer (below). Pure module, safe to require at top level (no load-time cycle).
const circuitBreaker = require('./circuit_breaker.js')
const panelTally = require('./panel_tally.js')
// #38 Task 11: the engine-axis resolver twin + the spine leaf wrapper that dispatches external
// engines (codex|cursor) for the write (build|fix) and read (review) roles.
const engineDispatch = require('./engine_dispatch.js')
const enginePrefTwin = require('./engine_pref.js')

// #170: compose the spine CODE root (plugin-cache lib dir, or the repo-relative default) at
// CALL time — never a module-load const, since the bundle ENTRY plants __SR_LIB after factories.
const { libPath, libRoot } = require('./lib_root.js')
const MAX_ROUNDS = 3                 // per-task + final-review fix bound (plan: same bound as a task)

// #375: the reserved Task-Id the WHOLE-BRANCH final-review fix commits carry. A whole-branch fix
// serves no single task, so it has no numeric task id; before this, the native (default-Claude) fixer
// committed with NO trailer and the external fixer minted the work-item SLUG — neither is in the numeric
// valid_ids, so the spine's OWN fix commits failed the spine's OWN UFR-7 resume gate, every time, by
// construction. Both fix paths now mint THIS value: the native/default path via the inline nativeAgentCall
// prompt at the dispatch site, and the external path via the _implDispatch `taskId` (engine_adapter.
// commit_result stamps it). The build-gather (build_state.py FINAL_REVIEW_TASK_ID) accepts it. The value
// MUST stay byte-equal to the Python constant — build_phase_finalreview_trailer_smoke.js pins JS===Python
// so the fixer and the gate cannot drift apart again (the two-SSOT-sides-one-value invariant #375 demands).
const FINAL_REVIEW_TASK_ID = 'final-review'

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// #150: task-scoped leaf labels for the /workflows progress view (spaces, not kebab-case).
function implementTaskLabel(task, taskCount) {
  return `implement task ${task.id} of ${taskCount}`
}

function fixTaskLabel(task) {
  return `fix task ${task.id}`
}

function reviewTaskLabel(task, round) {
  return `review task ${task.id}:r${round}`
}
function park(reason) { return { confidence: 'low', assumptions: [reason], parkReason: reason } }
function ok(extras) {
  const r = { confidence: 'high', assumptions: [] }
  if (extras && extras.handoffSummary) r.handoffSummary = extras.handoffSummary
  return r
}

// FR-8: the configured base (--base) arg, threaded into EVERY build_state_cli gather so the entry
// gather and the per-task UFR-7 check measure against the same base. Extracted to one helper so the
// two call sites can't drift (the live bug: the per-task check omitted --base and parked off a
// non-main base). Empty string when globalThis.__SR_BASE is unset -> byte-identical to today.
function baseArg() {
  const b = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  return b ? ` --base ${shq(b)}` : ''
}

// Reuse the spine's proven exec primitive (lazy require avoids a load-time cycle: showrunner's
// build_phase reference is itself lazy, and deferring keeps build_phase's require surface unchanged
// for the smokes). One exec, no duplication, no front-half change.
let _execFn = null
function exec(commands, label) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands, label)
}

// Run ONE command via the exec dumb-pipe and parse its JSON stdout. The cheap haiku courier
// occasionally drops/garbles a command's stdout even though it ran (live: a journal_entry.py leaf
// returned stdout:"" with ok:true, so JSON.parse("") threw and the build fail-closed-parked); retry
// ONCE on an empty or unparseable stdout before failing closed. Build-path commands are idempotent /
// harmless to repeat (journal append, gate set, provenance, lease renew, gather/read).
// Returns the parsed object, or null after the retry (the caller fails closed on null — same
// park/false/fallback it produces today). A clean {"ok":true} on the first call returns immediately
// (one exec, no behavior change); a parseable {"ok":false} (a REAL durable-write failure) is returned
// as-is on the first call — it is NOT a courier-drop, so it is NOT retried.
// `label` is the cosmetic display purpose (defaults to 'exec'); dumb-pipe routing rides the courier's
// `courier: true` marker, so a descriptive label never loosens the cheapest-model pinning.
async function execJson(cmd, label, opts) {
  try {
    return await courier.runCourierJson(label || 'exec', cmd, opts)
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// build_progress.reconcile via the module (NOT a destructured load-time binding) so reconcileState
// calls THROUGH the module export — keeps the twin the single source AND makes it spy-able in smokes
// (a testability improvement; the FR-4a entry-once property is re-asserted by spying reconcile).
function _reconcile(...a) { return require('./build_progress.js').reconcile(...a) }

// model_tier overrides: mirror showrunner.js's authorModel — read from globalThis.__SR_OVERRIDES
// (set by the Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS).
function _overrides() { return (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null }

// engine prefs: mirror _overrides — read from globalThis.__SR_ENGINE_PREFS (planted by the Task-12
// startup pipe; absent in test/throwaway runs -> both 'claude' -> the native agent() path, UNCHANGED).
function _enginePrefs() {
  const p = (typeof globalThis !== 'undefined' && globalThis.__SR_ENGINE_PREFS) || null
  return (p && typeof p === 'object') ? p : { reviewer: 'claude', implementation: 'claude', effort: {} }
}

// FR-9 effort overrides: the effort sub-map keyed by role_kind {review,build,fix} lives INSIDE the
// engine-prefs object (NOT the model-tier __SR_OVERRIDES map). resolveEffort reads this map; absent -> null.
function _effortOverrides() {
  const p = _enginePrefs()
  return (p && p.effort && typeof p.effort === 'object' && !Array.isArray(p.effort)) ? p.effort : null
}

// #115 increment B: cmdRunner is gone. The IO/side-effect leaves are ported to exec(raw)+in-process
// -parse (increment A); the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (above) — no JS<->Python bridge remains in this module.

// FR-4a: gather authoritative git state (entry/resume only, NOT per loop iteration).
// Ported to exec(raw)+in-process-parse: the leaf runs the command and returns its raw stdout; the
// spine JSON.parses it here (the leaf can no longer derail by mis-copying fields — the live bug).
// Returns the parsed state object on success; NULL on exec-fail / parse-fail (the caller parks
// honestly); or {__error: <reason>} when the leaf emitted a STRUCTURED base-resolution error on
// stdout (C-I3) so the caller can park with THAT specific reason instead of the generic one.
// FR-8: thread configurable base (--base) when globalThis.__SR_BASE is set; absent -> _base() detection.
async function gatherState(workItem, branch, validIds, wt) {
  let parsed = null
  try {
    parsed = await courier.runCourierJson(
      'gather build state',
      `python3 ${libPath('build_state_cli.py')} gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${baseArg()}`,
      {},
    )
  } catch (_) {
    parsed = null
  }
  if (parsed == null) return null
  // Structured fail-closed signal: the leaf could not resolve --base. Surface the SPECIFIC reason
  // (C-I3) rather than collapsing to the generic "could not gather authoritative git state" park.
  if (parsed && typeof parsed === 'object' && typeof parsed.error === 'string') {
    return { __error: parsed.error }
  }
  return parsed
}

// FR-4a: derive the starting action + resume_at from authoritative state using the in-process twin.
// Returns the reconcile decision object ({action, resume_at?, reason?}). Calls THROUGH the module
// export (_reconcile) so the twin stays the single source and is spy-able in smokes.
function reconcileState(taskList, state) {
  return _reconcile(
    taskList,
    state.committed_task_ids || [],
    state.unmapped_commits || 0,
    state.review_records || {},
    !!(state.worktree_dirty),
    state.final_review || null,
    state.provenance || null)
}

async function buildPhase(workItem, generation) {
  const root = '$(git rev-parse --show-toplevel)'
  // UFR-1: refuse unless the tasks gate is passed. Read via `read-gate --json` ({"review": "..."}
  // — produced by definition_doc.py; showrunner.js readGate is the other JS consumer of the field)
  // so a FENCED-but-correct courier answer parses: the plain-string mode byte-compared a fenced
  // 'passed' and false-parked (run 9, wf_b69571d9). Extraction is STRICT — the whole answer must
  // BE the JSON, bare or in one fence (extractJsonStrict); the permissive extractJson brace-slice
  // would let an answer that merely QUOTES {"review":"passed"} in prose OPEN the gate, and this
  // gate must only ever fail closed. NOTE this is deliberately STRICTER than showrunner.js
  // readGate's bare JSON.parse-or-'unreadable' (which guards a skip decision, not a build).
  const gateOut = await execJson(
    `python3 ${libPath('definition_doc.py')} read-gate --doc tasks --work-item ${shq(workItem)} --root "${root}" --json`,
    'read gate',
    { extract: 'strict' },
  )
  if (gateOut == null) return park('could not read the tasks gate — failing closed')
  const gate = (gateOut && typeof gateOut.review === 'string') ? gateOut.review : null
  if (gate == null) return park('could not read the tasks gate — failing closed')
  // Clamp the untrusted courier-provided value at this sink: the reason flows into journal
  // entries, readouts, and PR comments downstream.
  if (gate !== 'passed') return park(`tasks gate not passed (${String(gate).slice(0, 80)}) — refusing to build (UFR-1)`)
  // UFR-2: setup the content-addressed worktree/branch + persist this run's generation.
  const setup = await execJson(
    `python3 ${libPath('build_entry.py')} --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
    'prepare build',
  )
  if (setup == null) return park('build setup failed: no branch')
  if (!setup.branch) return park('build setup failed: ' + (setup.error || 'no branch'))
  const branch = setup.branch
  // The build branch is checked out in a SEPARATE managed build worktree (build_entry -> buildtree);
  // every git read/write below must operate there, not in the showrunner's main checkout.
  const wt = setup.path
  // UFR-8: zero executable tasks -> finish without building.
  // With exec+JSON.parse the BUG-2 string-recovery is structurally moot, but KEEP the
  // typeof===string JSON.parse recovery + Array.isArray guard as defense-in-depth (BUG-3).
  const _taskResult = await execJson(`python3 ${libPath('task_list_cli.py')} --work-item ${shq(workItem)}`, 'read tasks')
  if (_taskResult == null) return park('task-list command did not run — failing closed')
  let tasks = _taskResult.tasks
  if (typeof tasks === 'string') {
    try { tasks = JSON.parse(tasks) } catch (_) { tasks = null }
  }
  if (!Array.isArray(tasks)) return park('task-list returned non-array tasks — schema mismatch, failing closed')
  // Silent-zero guard: if the doc has raw task headings but the parser returned nothing,
  // the format is wrong (e.g. em-dash in an old doc not yet re-authored). Park explicitly
  // instead of silently finishing (which would be a UFR-8 bypass — building nothing when
  // there are tasks to build). raw_task_heading_count===0 is the genuine empty case.
  const rawHeadingCount = typeof _taskResult.raw_task_heading_count === 'number' ? _taskResult.raw_task_heading_count : 0
  if (tasks.length === 0 && rawHeadingCount > 0) {
    return park('tasks doc present but no parseable ### Task N: headings — format mismatch, refusing to build nothing')
  }
  if (tasks.length === 0) { log('no tasks to build'); return ok() }

  const validIds = tasks.map((t) => t.id).join(',')

  // FR-4a: gather authoritative git state ONCE at entry (not per iteration).
  // A fresh invocation (after park/crash) re-gathers here — resume correctness preserved.
  // gatherState returns null on exec/parse failure — park honestly (fail closed; never walk on a
  // mis-read or absent git state — the live bug that mis-reported a clean tree as dirty).
  let state = await gatherState(workItem, branch, validIds, wt)
  if (state && state.__error) return park(state.__error)
  if (!state) return park('could not gather authoritative git state — failing closed')

  // Handle entry-level non-forward reconcile actions before entering the forward-walk.
  // reset_uncommitted: fence, reset, then re-gather + re-reconcile ONCE (a reset is resume-like).
  let d = reconcileState(tasks, state)
  if (d.action === 'park') return park(d.reason || 'build_progress parked at entry')
  if (d.action === 'reset_uncommitted') {
    if (!(await fenceOrPark(workItem, generation))) return park('lease lost before reset — park (UFR-10)')
    const rr = await resetUncommitted(wt, branch)
    if (!rr.ok) return park('could not reset uncommitted changes: ' + (rr.error || 'unknown'))
    // Re-gather + re-reconcile after reset (ground truth mutated).
    state = await gatherState(workItem, branch, validIds, wt)
    if (state && state.__error) return park(state.__error)
    if (!state) return park('could not gather authoritative git state — failing closed')
    d = reconcileState(tasks, state)
    if (d.action === 'park') return park(d.reason || 'build_progress parked after reset')
    // If the SECOND reconcile is STILL reset_uncommitted, the reset did not fully clean the worktree.
    // Park honestly — bounded, fail-closed — rather than fall through into a dirty forward-walk
    // (#115 final review FIX 4 / UFR-12). One reset attempt only; a still-dirty tree is the owner's.
    if (d.action === 'reset_uncommitted') return park('worktree still dirty after reset — park (UFR-12)')
  }

  // FR-4a forward-walk: in-memory state for the continuous run.
  // Seed from the entry gather; advance only on confirmed durable success.
  const builtTaskIds = new Set(state.committed_task_ids || [])
  const reviewRecords = Object.assign({}, state.review_records || {})
  // Track whether THIS walk built or reviewed any task. If it did, the branch HEAD changed, so the
  // ENTRY gather's final_review.clean / provenance are STALE — the whole-branch final review must
  // RE-RUN over the new HEAD and provenance must be RE-WRITTEN. A pure resume (nothing built this
  // walk) keeps the skip optimization (the entry state is fresh). (#115 final review FIX 3 / FR-4a.)
  let didWork = false
  // Determine the starting index from the entry reconcile's resume_at.
  const resumeTaskId = d.resume_at ? d.resume_at.id : null

  // Forward-walk states that are already-past (handled after all-tasks-built+reviewed):
  // final_review, write_provenance, complete are processed after the task loop.
  // If the entry action indicates we're already past the task loop, skip it.
  const pastTaskLoop = (d.action === 'final_review' || d.action === 'write_provenance' || d.action === 'complete')

  if (!pastTaskLoop) {
    // Guard: bound so a non-progressing forward-walk can't spin forever.
    const MAX_GUARD = tasks.length * 4 + 8
    let guard = 0
    // Find the start index (resume from the first un-built or un-reviewed task).
    let startIdx = 0
    if (resumeTaskId !== null) {
      const idx = tasks.findIndex((t) => t.id === resumeTaskId)
      if (idx >= 0) startIdx = idx
    }

    for (let i = startIdx; i < tasks.length; i += 0) {
      guard += 1
      if (guard > MAX_GUARD) {
        return park('build loop exceeded its guard bound without completing (last task: '
          + (tasks[i] ? tasks[i].id : '?') + ')')
      }
      const task = tasks[i]
      const isBuilt = builtTaskIds.has(task.id)
      const isReviewed = reviewRecords[task.id] === 'passed'

      if (isBuilt && isReviewed) {
        // Already done in memory; advance.
        i += 1; continue
      }
      if (!isBuilt) {
        // Build the task (fence, dispatch worker, commit, journal, then review).
        const r = await buildOneTask(workItem, generation, task, branch, validIds, wt, tasks.length)
        if (r.parked) return park(r.reason)
        // On confirmed success (buildOneTask only returns !parked when journal+review both passed):
        builtTaskIds.add(task.id)
        reviewRecords[task.id] = 'passed'
        didWork = true                 // HEAD moved this walk -> entry final_review/provenance stale
        i += 1; continue
      }
      if (isBuilt && !isReviewed) {
        // Task implemented but not reviewed (e.g. after a crash mid-review): review it.
        const r = await reviewOneTask(workItem, generation, task, branch, wt)
        if (r.parked) return park(r.reason)
        reviewRecords[task.id] = 'passed'
        didWork = true                 // a review (with its possible fix commits) also moves HEAD
        i += 1; continue
      }
    }
  }

  // All tasks built+reviewed. Run the whole-branch final review.
  // Skip ONLY on a pure resume (didWork === false): the entry final_review.clean then covers the
  // current HEAD. If this walk built/reviewed anything, HEAD moved — the entry's final_review.clean
  // is STALE, so RE-RUN the whole-branch final review over the new HEAD (#115 final review FIX 3).
  const alreadyFinalClean = !didWork && state.final_review && state.final_review.clean
  let handoffSummary = null
  if (!alreadyFinalClean) {
    const fr = await runFinalReview(workItem, generation, branch, wt)
    // #381 terminal routing. The whole-branch final review runs ONE review pass + ONE fix pass
    // (maxRounds:1; the fix pass dispatches inside runFinalReview after the cap halt) and is NOT the
    // branch's gate — review-code (5 specialist panels, circuit breaker, verify gate, confirmation
    // rounds) is the strictly stronger gate that runs next and vets the (deliberately unvetted) fix
    // batch. So:
    //   - 'clean'          → advance (stamp coverage, then provenance), unchanged.
    //   - round-cap halt   → the single review pass surfaced blockers at the one-pass cap, the fix
    //                        batch LANDED, and the post-fix verify (if configured) is green —
    //                        runFinalReview only lets haltKind 'round-cap' survive when all three
    //                        hold. Journal the handoff (open findings + fix-pass facts, auditable)
    //                        and HAND OFF to review-code, stamping coverage + advancing exactly like
    //                        the clean path.
    //   - everything else  → PARK, fail-closed, unchanged: verify red pre- OR post-fix (haltKind
    //                        'verify-fail'), a failed fix dispatch / lost fence ('fix-failed'),
    //                        breaker recurrence/no-progress or a confirmation-cap park ('other'),
    //                        no review obtainable / cannot-certify, clean-with-skips. Only the
    //                        finding-churn park is removed; process failures still fail closed. The
    //                        routing keys on the STRUCTURED haltKind field, never on the prose reason.
    // #279: carry the verdict's reason into the park/handoff so the owner sees WHY, not a bare terminal.
    // #381: an uncertified verdict parks fail-closed regardless of haltKind — only a certified
    // round-cap handoff proceeds (haltKind 'round-cap' AND NOT uncertified).
    if (fr.uncertified || (fr.terminal !== 'clean' && fr.haltKind !== 'round-cap')) {
      const detail = fr.reason ? ' (' + fr.reason + ')' : ''
      // #375: this is a whole-branch final-review park — the operator resolves it by fixing the
      // branch and relaunching. Name the reserved trailer so any HAND fix commits they add carry an
      // identity the UFR-7 resume gate accepts (whole-branch fixes serve no single task); without this
      // the relaunch fail-closes on those untrailered commits and needs history-rewriting archaeology.
      return park('whole-branch final review did not reach clean: ' + fr.terminal + detail
        + ` — if you fix the branch by hand before relaunching, trailer each whole-branch fix commit`
        + ` with "Task-Id: ${FINAL_REVIEW_TASK_ID}" so the resume passes the UFR-7 provenance gate`)
    }
    if (fr.haltKind === 'round-cap') {
      // Auditable handoff record (best-effort/fail-open), THEN stamp + advance like the clean path.
      const journalResult = await journalFinalReviewHandoff(workItem, branch, fr)
      handoffSummary = buildHandoffSummary(fr, journalResult)
    }
    // recordFinalReviewClean stamps `final_review.clean`. Under #381 its semantics are: "branch scan +
    // one fix pass completed; the branch gate is review-code" — written on BOTH a clean terminal and a
    // round-cap handoff, so the resume router (build_progress twins), build_state gather, and run_watch
    // all continue to read the same stamp and resume forward-walk correctly past this leg.
    const coverage = await recordFinalReviewClean(workItem)
    if (!(coverage && coverage.ok === true && coverage.read_back === true)) {
      return park('final review coverage stamp failed read-back')
    }
  }

  // Write provenance if absent (FR-9): idempotent, only after final review clean. Same staleness
  // guard: a walk that did work must RE-WRITE provenance over the new HEAD (don't trust the entry's).
  const alreadyProv = !didWork && state.provenance && state.provenance !== 'absent'
  if (!alreadyProv) {
    const p = await writeProvenance(workItem)
    if (!p.ok) return park('provenance not recorded: ' + (p.error || 'unknown'))
  }

  return handoffSummary ? ok({ handoffSummary }) : ok()
}

// Reset ONLY uncommitted/untracked changes; never discard a commit (UFR-12). Returns {ok,error?}
// so a failed reset parks honestly (UFR-6) rather than spinning to the guard bound.
async function resetUncommitted(wt, branch) {
  // dumb pipe (fixed git commands, echo ok): courier:true so the bundle preamble pins it to the
  // cheapest model (#118 — an unmarked label inherits the session model).
  return agent(
    `In the build worktree at ${wt} (branch ${branch}), reset only uncommitted state: `
    + `git checkout -- . && git clean -fd . — do NOT touch any commit. `
    + `Return JSON {"ok":true} on success or {"ok":false,"error":"<reason>"}.`,
    { label: 'reset-uncommitted', courier: true, schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
}

// Record build provenance once over HEAD = X (FR-9), via the existing prov_entry leaf.
// exec/parse fail -> {ok:false, error:'provenance leaf did not run'} so the caller's !p.ok parks.
async function writeProvenance(workItem) {
  // execJson retries the courier ONCE on a dropped/garbled stdout; null -> the SAME fail-closed
  // fallback as today ({ok:false} -> caller parks). A parseable {ok:false} is returned as-is (no retry).
  const r = await execJson(`python3 ${libPath('prov_entry.py')} --step build --work-item ${shq(workItem)}`, 'write provenance')
  if (r == null) return { ok: false, error: 'provenance leaf did not run' }
  return r
}

// Stamp `final_review.clean`. #381: the stamp means "branch scan + one fix pass completed; the branch
// gate is review-code" — it is written on a clean terminal AND on a round-cap handoff (blockers found
// at the one-pass cap, handed to review-code), never on a process-failure park. The stamp shape is
// unchanged, so the resume router (build_progress twins), build_state gather, and run_watch read it
// exactly as before. Caller checks .ok/.read_back for the stamp; stay fail-closed-safe on a throw.
async function recordFinalReviewClean(workItem) {
  try {
    return await courier.runCourierJson(
      'stamp build coverage',
      `python3 ${libPath('build_state_cli.py')} record-final-review --work-item ${shq(workItem)} --clean true`,
      { require: ['ok', 'read_back'], retryRealFailure: false },
    )
  } catch (_e) {
    return { ok: false, read_back: false }
  }
}

// fenceOrPark: lease-fence acquire. CRITICAL fail-closed: an exec/parse failure must read as a LOST
// fence (false), NEVER as ok — a fence failure read as ok would let an unfenced write through (UFR-10).
function _checkoutRoot() {
  const r = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT)
    ? String(globalThis.__SR_ROOT) : null
  return (r && r.trim()) ? r : null
}
async function fenceOrPark(workItem, generation) {
  const root = _checkoutRoot()
  if (!root) return false
  const f = await execJson(
    `python3 ${libPath('fence_cli.py')} --work-item ${shq(workItem)} --generation ${shq(String(generation))} --root ${shq(root)}`,
    'fence lease',
  )
  return !!(f && f.ok)
}

async function recordTaskBuilt(workItem, taskId) {
  try {
    return await courier.runCourierJson(
      'record task built',
      `python3 ${libPath('build_state_cli.py')} record-built --work-item ${shq(workItem)} --task ${shq(taskId)}`,
      { require: ['ok', 'read_back', 'task'], retryRealFailure: false },
    )
  } catch (_e) {
    return null
  }
}

async function recordTaskReviewed(workItem, taskId) {
  try {
    return await courier.runCourierJson(
      'record task reviewed',
      `python3 ${libPath('build_state_cli.py')} record-reviewed --work-item ${shq(workItem)} --task ${shq(taskId)}`,
      { require: ['ok', 'read_back', 'task'], retryRealFailure: false },
    )
  } catch (_e) {
    return null
  }
}

// UFR-4 run-time write preflight — cache the verdict for the whole run so we probe the host's
// autoMode.allow grant ONCE (not per task). null = not yet probed. The probe runs the engine's OWN
// write command inside the worktree; a denied/failed grant -> the impl role falls open to Claude.
let _writeAuthOk = null
let _writeAuthNotified = false
async function _implWriteAuthorized(engine, wt) {
  if (_writeAuthOk !== null) return _writeAuthOk
  const v = await execJson(
    `python3 ${libPath('engine_authz.py')} test-dispatch --engine ${shq(engine)} --cwd ${shq(wt)}`, 'check write auth')
  _writeAuthOk = !!(v && v.ok === true)
  if (!_writeAuthOk && !_writeAuthNotified) {
    _writeAuthNotified = true
    try { log(`build: ${engine} is not authorized to write in this run (autoMode.allow not granted) — the implementation role falls open to Claude for the whole run (UFR-4)`) } catch (_) {}
  }
  return _writeAuthOk
}

// Route the write role (build|fix) to the chosen implementation engine. claude -> the existing agent()
// path, BYTE-UNCHANGED. external -> dispatchExternal; on ANY non-success reset uncommitted edits (UFR-2)
// and fall open to the native agent() (UFR-1). preSHA/commit-discipline live inside dispatchExternal.
async function _implDispatch({ workItem, roleKind, taskId, prompt, wt, branch, nativeAgentCall, model }) {
  const engine = enginePrefTwin.resolveEngine(roleKind, _enginePrefs())
  if (engine === 'claude') return nativeAgentCall()
  // UFR-4: before the FIRST external WRITE, confirm the host grants this engine write authority.
  // Denied -> fall open to Claude for the whole run (build AND fixes) + one notice. Read roles skip this.
  if (!(await _implWriteAuthorized(engine, wt))) return nativeAgentCall()
  // FR-9: effort override comes from the engine-prefs effort sub-map (keyed by role_kind), NOT the
  // model-tier _overrides() map (keyed by role->model — resolveEffort could never match it).
  const effort = enginePrefTwin.resolveEffort(engine, roleKind, _effortOverrides())
  // #309: write roles get the HIGH ceiling (resolveTimeout(_,'build'|'fix')); the owner `timeout`
  // override on __SR_ENGINE_PREFS wins. #308: thread the caller's resolved model as a dispatch FACT —
  // the adapter's policy map decides what cursor runs (owner policy 2026-07-09: composer for work
  // roles; only the fable/author-plan exception maps a premium id), and the readout shows the same.
  const timeoutSeconds = enginePrefTwin.resolveTimeout(_enginePrefs(), roleKind)
  // #309: PAIR the high ceiling with the byte-activity stall monitor — the write idle window
  // (resolveIdle(_,'build'|'fix') = 600s, owner `idleTimeout` override wins, clamped ≤ ceiling).
  const idleSeconds = enginePrefTwin.resolveIdle(_enginePrefs(), roleKind)
  const tierRole = roleKind === 'build' ? 'builder' : 'fixer'
  const engineModel = enginePrefTwin.resolveEngineModel(engine, tierRole, model, _enginePrefs())
  const res = await engineDispatch.dispatchExternal({
    engine, roleKind, effort, prompt, cwd: wt, schema: { type: 'object', required: ['ok'] },
    taskId, workItem, model, engineModel, timeoutSeconds, idleSeconds,
  })
  if (res && res.ok) return res
  // UFR-2: a failed/stalled external write left only uncommitted edits -> discard, then redo on Claude.
  await resetUncommitted(wt, branch)
  try { log(`build: ${engine} ${roleKind} did not complete (${(res && res.reason) || 'unknown'}) — falling open to Claude`) } catch (_) {}
  return nativeAgentCall()
}

// #222: the mode-aware ABSOLUTE tasks-doc path. Reuses showrunner.docPathFor (the single source of
// truth — docDirFor reads the startup-planted __SR_DOC_DIRS, honoring out-of-repo storage, and falls
// back to the in-repo default when unplanted). Resolved at CALL time via the same lazy showrunner
// require as exec() above, so the pointer the worker gets is byte-identical to the spine's own.
function _tasksDocPath(workItem) {
  return require('./showrunner.js').docPathFor(workItem, 'tasks')
}

// #275: the build leaf's structured-output schema. Constrain `ok` to a boolean and `signal` to the
// three recovery signals so schema-validated output retries a stringy shape AT THE SOURCE — the #219
// live escape was every build leaf returning `ok` as the string "false"/"true" past an untyped
// {required:['ok']} schema, and "false" is truthy in JS. `evidence` is left unconstrained (it is not
// consumed here, and the leaf sometimes emits it as a JSON string — don't force needless retries on it).
const BUILD_LEAF_SCHEMA = {
  type: 'object',
  required: ['ok'],
  properties: {
    ok: { type: 'boolean' },
    // Reference the canonical token (CONVENTIONS §11) rather than re-typing the string —
    // worker_recovery.js is the home of the plan_wrong signal, already required in this file.
    signal: { enum: ['ok', 'needs_context', workerRecoveryTwin.PLAN_WRONG] },
  },
}

// #222: the per-task build prompt. Carries the ABSOLUTE tasks-doc pointer so the worker implements the
// task's real definition (not the one-line title) and never sweeps the owner's filesystem hunting for
// the doc — the out-of-repo-storage blind-build defect where a bare-main build worktree gave the worker
// nothing to anchor to (which also tripped repeated macOS TCC dialogs, live run 8). `retryNote` is
// appended ONLY on a re-dispatch so a needs_context retry is genuinely different from the first prompt.
// `deniedNote` (FR-1 finality) carries forward the actions a prior attempt reported the permission
// timeout denied — a re-dispatched fresh leaf is a re-attempt of the SAME step, so it must not retry the
// denied action in any rewording. Appended AFTER retryNote so it rides every subsequent dispatch.
function buildTaskPrompt(task, branch, wt, docPath, retryNote, deniedNote) {
  return (
    `In the build worktree at ${wt} (branch ${branch}), implement Task ${task.id} (${task.title}) TEST-FIRST: `
    + `write the test(s), run to observe FAIL, implement, run to observe PASS. The task's full definition is `
    + `Task ${task.id} in ${docPath} — Read it before writing code; implement THAT, not the title. Never search `
    + `the filesystem outside the build worktree and the given doc path. Commit with a trailer line `
    + `"Task-Id: ${task.id}" on EVERY commit you make for this task. Put the Task-Id: ${task.id} trailer in the `
    + `FINAL paragraph of the commit message with no blank line between it and any other trailer (e.g. `
    + `Co-Authored-By). ${workerContractTail()}`
    + (retryNote || '')
    + (deniedNote || '')
  )
}

// #357: the worker OUTPUT CONTRACT tail — the timeout-proceed contract, the deniedAction honesty
// clause, and the verdict-JSON demand that `engine_adapter.parse_result`'s build|fix branch REQUIRES.
// One shared tail for every external write-role worker prompt: the fix dispatches shipped WITHOUT it
// (they ended at the findings array), so external fix leaves did the work, ended with prose, and every
// fix dispatch parsed `unreadable` — the configured fix engine could never genuinely land its work.
function workerContractTail() {
  return (
    `${require('./showrunner.js').TIMEOUT_PROCEED_CONTRACT} If the 15-minute timeout `
    + `fired on ANY substantive step (not a verification probe — an actual implementation/commit action), set `
    + `"deniedAction" to a short description of what you could not do; otherwise omit it or set it `
    + `to null — never fabricate a completed step you were denied. Return JSON `
    + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool},"deniedAction":"<string or null>"}.`
  )
}

// #357: pure builders for the EXTERNAL fix-dispatch prompts (task-level + whole-branch), exported for
// the contract drift-guard tests. The native fix call keeps its original prompt (the native path never
// parses stdout for the verdict); the external path MUST state the contract it is parsed against.
function fixTaskPrompt(task, branch, wt, findingsJson) {
  return (
    `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with `
    + `trailer "Task-Id: ${task.id}" (put Task-Id: ${task.id} in the FINAL paragraph of the commit message `
    + `with no blank line before other trailers such as Co-Authored-By): ${findingsJson} `
    + workerContractTail()
  )
}

function fixBranchPrompt(branch, wt, blockersJson) {
  // #375: this is the EXTERNAL (codex|cursor) whole-branch fix-dispatch prompt (the native/default path
  // runs the inline nativeAgentCall prompt at the dispatch site, NOT this one). A whole-branch final-review
  // fix serves no single task, so it carries the RESERVED sentinel Task-Id. On the external path the commit
  // is stamped by engine_adapter.commit_result from the _implDispatch `taskId` (= FINAL_REVIEW_TASK_ID), so
  // the trailer clause below is DEFENSIVE redundancy — harmless if the engine folds its own message. The
  // load-bearing native-path instruction lives in the inline prompt beside the taskId; keep the two in sync.
  return (
    `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: `
    + `${blockersJson} `
    + `Commit with a trailer line "Task-Id: ${FINAL_REVIEW_TASK_ID}" on EVERY commit you make (put `
    + `Task-Id: ${FINAL_REVIEW_TASK_ID} in the FINAL paragraph of the commit message with no blank line `
    + `before other trailers such as Co-Authored-By). `
    + workerContractTail()
  )
}

// FR-1 finality memory: the action(s) a prior attempt of THIS step reported the permission timeout
// denied are FINAL — a fresh re-dispatch of the same work is a re-attempt, not a distinct step, so the
// worker must not re-enter the denied action in any rewording. One tight sentence naming each denied
// action so the worker works around them and reports honestly instead of re-hitting the permission wait.
function buildDeniedNote(deniedActions) {
  if (!deniedActions || !deniedActions.length) return ''
  return (
    ` FINAL — the following action(s) were already denied by the permission timeout in this step and are `
    + `FINAL; do NOT re-attempt them in any form or rewording — work around them and report honestly: `
    + deniedActions.join('; ') + '.'
  )
}

// #222: genuine added context on a needs_context re-dispatch — the worker signalled it lacked context,
// so escalate: name the absolute doc path again and instruct it to Read that exact section. Before this
// the recovery twin re-dispatched the byte-identical prompt and never added anything (UFR-3 retry).
function buildRetryNote(task, docPath) {
  return (
    ` RETRY — you signalled you were missing context. The full definition of Task ${task.id} is in ${docPath}: `
    + `open it with Read and implement that checkbox section exactly. Do not proceed from the title, and do not `
    + `search the filesystem outside the build worktree and that doc path.`
  )
}

// #149 Task 11/12: the SINGLE object-arg composer for the spine's leaf prompt — used by BOTH
// production (buildOneTask, below) and the permission smokes, so the dispatched bytes and the bytes
// tests reconstruct for the FR-8 composed-exact hash can never drift (one composer, zero re-encoding).
// Delegates to buildTaskPrompt; threads `deniedNote` (FR-1 finality) through so the production caller's
// denial-memory suffix rides the same source of truth. `deniedNote` defaults to '' — a smoke that omits
// it composes byte-identically to a first-attempt dispatch.
function buildLeafPrompt({ wt, branch, task, workItem, docPath, retryNote, deniedNote }) {
  return buildTaskPrompt(task, branch, wt, docPath || _tasksDocPath(workItem), retryNote || '', deniedNote || '')
}

// UFR-6/UFR-8 dual-carrier denial recording (premortem-001), extracted from buildOneTask's loop so
// the loop body stays control flow. Returns a park result to return, or null (nothing denied / both
// carriers rode). The denial is written to TWO independent carriers the ship gate (ship_gate.decide)
// both consult; EITHER gates the PR to a draft, REGARDLESS of whether the leaf still reports ok:true:
//   1. the run's journal `permission_denied` event (step `build:<id>`, detail = the denied action) —
//      best-effort/fail-open but courier-RETRIED, written FIRST so it survives even if carrier 2 fails
//      and the task then parks (a resume skips this already-committed leaf, so carrier 2 stays empty).
//      ship_gate.journal_build_denials folds these `build:` events in as the second gate signal.
//   2. the prov_entry build-denial provenance entry (ship_gate.record_build_denial) — fail-CLOSED
//      (record-before-advance): a dropped courier (null) or durable-write failure (ok!==true) PARKs
//      the task, never silently promoting a tainted build to a ready PR.
// Ordering (journal first) narrows the loss window to a CORRELATED double failure: writing the durable
// journal event before carrier 2's park closes any SINGLE-carrier failure. RESIDUAL (transport-
// inherent, cannot be closed by ordering): if the courier drops/garbles BOTH writes in the same window,
// both durable carriers stay empty — and because the resume forward-walk skips the already-committed
// leaf, that denial is never re-earned. For exactly that double-drop, the fail-closed PARK REASON below
// names the denied action, so the disclosure still reaches the resuming owner through the park channel
// even when neither durable carrier landed.
async function recordBuildDenialIfAny(worker, workItem, task, generation, deniedActions) {
  if (!(worker && worker.deniedAction)) return null
  const denied = String(worker.deniedAction)
  // Carrier 1 (journal) FIRST — best-effort + fail-open, courier-retried.
  try {
    await execJson(
      `python3 ${libPath('journal_entry.py')} --work-item ${shq(workItem)} `
      + `--event-type permission_denied --step ${shq('build:' + task.id)} `
      + `--detail ${shq(denied)}`,
      'journal build denial',
    )
  } catch (_e) { /* fail-open: a readout-disclosure journal write never derails the build (UFR-2) */ }
  // Carrier 2 (provenance) — fail-CLOSED. The park on a failed provenance write STAYS: even though
  // carrier 1 may have ridden, parking here keeps record-before-advance honest for the provenance path.
  const denialRec = await execJson(
    `python3 ${libPath('prov_entry.py')} --step build-denial --work-item ${shq(workItem)} `
    + `--denied-step ${shq('build:' + task.id)} --denied-command ${shq(denied)}`,
    'record build denial',
  )
  if (!(denialRec && denialRec.ok === true)) {
    // Name the denied action in the park reason: on a correlated double-drop this is the only surviving
    // disclosure of the denial, and it reaches the resuming owner through the park channel.
    return { parked: true,
             reason: `build-denial record write failed for denied action '${denied}' `
                     + `(record-before-advance) — park (UFR-6/UFR-8)` }
  }
  // FR-1 finality: remember this denial so any subsequent re-dispatch (needs_context/escalate) is told
  // the action is FINAL and must not be re-attempted — carried into the next attempt's prompt.
  deniedActions.push(denied)
  return null
}

// Build one task test-first (FR-3) with bounded recovery (UFR-3), then review it. `validIds` is the
// FULL enumeration's task ids (comma-joined) so the write-time trailer check scores every above-base
// commit against the whole task set — not just this task (an earlier task's commit is not "unmapped").
async function buildOneTask(workItem, generation, task, branch, validIds, wt, taskCount) {
  const docPath = _tasksDocPath(workItem)   // #222: anchor the worker to the real task definition
  let attempt = 1
  // FR-1 finality: actions a prior attempt reported the permission timeout denied. Accumulated across
  // attempts and threaded into EVERY subsequent dispatch so a fresh re-dispatched leaf never re-attempts
  // the denied action (re-dispatching denied work under a new leaf is a re-attempt, not a distinct step).
  const deniedActions = []
  for (;;) {
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before build — park (UFR-10)' }
    }
    // #222: after the first attempt, add genuine context (re-state the doc path + a Read instruction)
    // so a needs_context retry is NOT the identical prompt the recovery twin used to re-dispatch.
    // FR-1: also thread any prior-attempt denied actions so the fresh leaf works around them, never re-tries them.
    // Compose via buildLeafPrompt — the SINGLE source-of-truth composer the smokes also use — so the
    // dispatched bytes provably equal what the FR-8 record_composed hash covers (no parallel inline path).
    const prompt = buildLeafPrompt({
      wt, branch, task, docPath,
      retryNote: attempt > 1 ? buildRetryNote(task, docPath) : '',
      deniedNote: buildDeniedNote(deniedActions),
    })
    // #402 (absorbs #333): the builder-leaf PROMPT is NOT recorded for FR-8 — it is dispatched to a
    // subagent, never executed as a shell command, so hashing it matched 0 executed commands ever. FR-8
    // composed-exact is now re-aligned to EXECUTED bytes: the spine registers each dumb-pipe leaf's exact
    // shell command at the single dispatch chokepoint (courier_exec.recordComposedFromPrompt, wired from
    // the bundle preamble's agent wrapper) BEFORE it dispatches. A builder leaf's improvised shell
    // commands stay under FR-5 (worktree-confined) / FR-6 (routine family) — never pre-registered here.
    // Pin the native builder's model EXPLICITLY (mirrors the per-task reviewer's resolveModel beside it,
    // fixed pre-#160). Before this, buildOneTask called agent() with NO `model` option, so the dispatch
    // silently rode the bundle preamble's __safeSmartDefault() Opus floor — policy-correct for a smart
    // leaf, but IMPLICIT: the preflight readout's builder row (model_tier role) then disagreed with the
    // dispatch (readout showed the tier's model, dispatch showed the safeSmartDefault fallthrough), and a
    // per-run builder-model override could never REACH the dispatch (no `model` option existed to carry
    // it). resolveModel('builder') defaults to the same opus (no behavior change in the default config)
    // AND makes the readout row + dispatch share one source (NFR-Accuracy) + lets an override land here.
    const builderModel = modelTierTwin.resolveModel('builder', _overrides(), null)
    const worker = await _implDispatch({
      workItem, roleKind: 'build', taskId: task.id, wt, branch,
      prompt, model: builderModel,   // #308: same tier the readout's builder row promises
      nativeAgentCall: () => agent(
        prompt,
        { label: implementTaskLabel(task, taskCount), model: builderModel, schema: BUILD_LEAF_SCHEMA }),
    })
    // UFR-6/UFR-8: a substantive build step the 15-min timeout denied taints the build evidence.
    // Record it on both carriers (recordBuildDenialIfAny); a failed fail-closed carrier parks here.
    const denialPark = await recordBuildDenialIfAny(worker, workItem, task, generation, deniedActions)
    if (denialPark) return denialPark
    // #275: fail-closed on the leaf's `ok`. A model that emits `ok` as the STRING "false" (observed
    // live — every leaf of the #219 run returned a stringy `ok` with signal:"plan_wrong") must NOT
    // read as success: "false" is truthy in JS, so a plain `if (worker.ok)` ran the success branch on
    // an explicit refusal and recorded built:passed for zero commits. Only a genuine boolean `true`
    // advances; anything else falls through to the recovery twin (which parks immediately on
    // plan_wrong, UFR-3). `worker` can be null (agent() returns null on a dead/skipped subagent), so
    // guard the deref — a null result must fall through to bounded recovery, never crash the run.
    // Scope: this is type-strictness on the NATIVE leaf only. It does NOT catch an EXTERNAL-engine
    // refusal: engine_adapter.py parse_result coerces any parseable external stdout to a genuine
    // boolean `ok:true` UPSTREAM of this gate (build|fix branch), so an external {ok:false,plan_wrong}
    // never reaches here as a falsy value — that refusal-laundering is tracked separately (#288).
    if (worker && worker.ok === true) {
      // write-time trailer enforcement (UFR-7): every above-base commit must carry its Task-Id.
      // This is a per-built-task CORRECTNESS read (NOT the FR-4a per-iteration resume gather).
      // execJson retries the courier ONCE on a dropped/garbled stdout, then fails closed: a leaf that
      // can't run / returns unparseable output must NOT read as a clean trailer state — park (UFR-7).
      const chk = await execJson(
        `python3 ${libPath('build_state_cli.py')} gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${baseArg()}`,
        'check trailers',
      )
      if (chk == null) return { parked: true, reason: 'could not verify commit trailers — failing closed (UFR-7)' }
      // A structured base-resolution error (C-I3) must park with its specific reason, not slip past
      // the unmapped check below (where {error} has no unmapped_commits and would read as clean).
      if (typeof chk.error === 'string') return { parked: true, reason: chk.error }
      if ((chk.unmapped_commits || 0) > 0) {
        return { parked: true, reason: 'a commit lacks its Task-Id trailer — park (UFR-7)' }
      }
      // record-before-advance: journal must succeed before the task counts as built. Guard the .ok
      // explicitly (defense-in-depth for invariant #4): a failed journal must NOT advance into the
      // review loop — park honestly (#115 final review FIX 8). The FR-4a forward-walk no longer
      // self-heals a missed journal per-iteration, so this guard is the advance fence.
      // execJson retries the courier ONCE on a dropped/garbled stdout (the OBSERVED live failure: the
      // courier returned stdout:"" though the journal wrote, so JSON.parse("") threw and the build
      // parked). null after the retry -> jrnl = {ok:false} so the guard parks (a missed journal must
      // NOT advance); a parseable {"ok":false} (a real durable-write failure) is returned without a
      // retry and parks the same.
      const built = await recordTaskBuilt(workItem, task.id)
      if (!(built && built.ok === true && built.read_back === true)) {
        return { parked: true, reason: 'task built record write failed (record-before-advance) — park' }
      }
      return reviewLoop(workItem, generation, task, branch, wt)
    }
    // #115 increment B: bounded recovery decided in-process via the worker_recovery twin (no leaf).
    // #275: `worker` may be null (dead/skipped subagent) — a null signal defaults to needs_context
    // (bounded retry → escalate → park), never a crash.
    const rec = workerRecoveryTwin.decide(attempt, (worker && worker.signal) || 'needs_context')
    if (rec.action === 'park') return { parked: true, reason: rec.reason }
    attempt += 1                                   // retry_with_context / escalate -> re-dispatch
  }
}

// A committed-but-unreviewed task (UFR-7) is taken up at review without rebuilding.
async function reviewOneTask(workItem, generation, task, branch, wt) {
  return reviewLoop(workItem, generation, task, branch, wt)
}

// #160: the per-task reviewer's bespoke two-verdict schema — the shape the task_review twin consumes.
// `findings` is REQUIRED (not just a declared property): for codex this schema is enforced via
// --output-schema, and the engine adapter's review parse (parse_result role='review') treats a missing
// findings list as 'unreadable' — so a schema-conformant clean external review that omitted findings
// would needlessly fall open to Claude, defeating the reviewer-engine preference on clean tasks. Both
// engines are therefore required to emit the findings array the parse layer depends on (matching the
// whole-branch review's external schema). Harmless for the native path — the native reviewer already
// emits findings, and reviewLoop reads `review.findings || []` either way.
const REVIEW_TASK_SCHEMA = {
  type: 'object',
  required: ['verdicts', 'findings'],
  properties: {
    verdicts: {
      type: 'object',
      required: ['spec_compliance', 'code_quality'],
      properties: {
        spec_compliance: { enum: ['pass', 'fail'] },
        code_quality: { enum: ['pass', 'fail'] },
      },
    },
    // #276: constrain finding items so structured-output validation corrects severity-vocabulary
    // drift AT THE SOURCE. `severity` is the canonical rubric tier enum (SSOT §11, guarded by
    // test_ssot_drift) — the live escape was reviewers emitting a foreign scale (`blocker`/`critical`
    // /`high`) that the blocking partition then demoted to Minor. Required so every finding carries a
    // gating severity; the task_review twin still fails closed on anything that slips past.
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity'],
        properties: {
          severity: { enum: ['Critical', 'Important', 'Minor', 'Nit'] },
          file: { type: 'string' },
          title: { type: 'string' },
          cannot_verify_from_diff: { type: 'boolean' },
        },
      },
    },
  },
}

// #276: the whole-branch final-review reviewer's findings schema — same canonical severity-tier enum
// (SSOT §11, guarded by test_ssot_drift) as REVIEW_TASK_SCHEMA, so a branch reviewer emitting a
// foreign scale (`high`/`blocker`/lowercase `critical`) is corrected at the structured-output source
// instead of slipping past the fail-closed fixer filter. Shared across the native + external dispatch
// sites in runFinalReview's reviewerAgent.
// #307: the finding item MUST declare every field the reviewerAgent prompt asks for
// ({file,line,title,severity,evidence}). Under codex's OpenAI-strict `--output-schema` (staged through
// engine_dispatch.strictify), an object with `additionalProperties:false` lets the engine emit ONLY the
// declared keys — a `severity`-only item would force codex to drop file/line, and reviewPanel's
// compileFindings discards any finding missing file/line, so a codex whole-branch review would report a
// false clean and a defective branch would ship. The extra fields stay Anthropic-permissive here (no
// `additionalProperties:false`, no `required` beyond none) so the native path is unconstrained;
// strictify tightens them for codex, where they come back as explicit null when unset.
const FINAL_REVIEW_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          title: { type: 'string' },
          severity: { enum: ['Critical', 'Important', 'Minor', 'Nit'] },
          evidence: { type: 'string' },
        },
      },
    },
  },
}

// #160: dispatch ONE per-task review, honoring enginePreferences.reviewer AND the model-tier policy —
// mirroring the whole-branch final review beside it (runFinalReview's reviewerAgent). Before this, the
// per-task reviewer called agent() with NO model + NO engine resolution, so a project configured
// `reviewer: codex` never routed the per-task review to codex (it silently rode the bundle's Opus
// safety floor, bypassing enginePreferences.reviewer entirely — found live). The per-task review runs
// at the LIGHTER `reviewer` tier / regular `review` effort — the whole-branch review is the deep one
// (reviewer-deep / review-deep). Returns the bespoke {verdicts, findings} shape the task_review twin
// consumes.
async function taskReviewAgent(workItem, task, branch, wt, round) {
  const reviewerModel = modelTierTwin.resolveModel('reviewer', _overrides(), null)
  // #222: give the per-task reviewer the same absolute tasks-doc pointer the worker got, so its
  // spec_compliance verdict is judged against the real task definition (not the one-line title — which
  // made "spec_compliance: pass" unfalsifiable in out-of-repo storage), and it never sweeps the
  // filesystem for the doc either.
  const docPath = _tasksDocPath(workItem)
  const prompt =
    `In the build worktree at ${wt}, review Task ${task.id} (${task.title}) on branch ${branch}. The task's full `
    + `definition is Task ${task.id} in ${docPath} — Read it and judge spec_compliance against THAT, not the title. `
    + `Never search the filesystem outside the build worktree and the given doc path. Return JSON `
    + `{"verdicts":{"spec_compliance":"pass|fail","code_quality":"pass|fail"},`
    + `"findings":[{"severity":"Critical|Important|Minor|Nit","file","title","cannot_verify_from_diff"}]}. `
    + `severity MUST be one of Critical, Important, Minor, Nit (no other scale) — a blocker is Critical or Important.`
  const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
  if (rEngine !== 'claude') {
    // regular per-task review effort ('review'/high); the whole-branch review dispatches 'review-deep'.
    const eff = enginePrefTwin.resolveEffort(rEngine, 'review', _effortOverrides())
    // #308: thread the reviewer tier as a dispatch fact (the adapter's owner-policy map keeps a
    // cursor reviewer on composer; the readout shows the same map's truth).
    // #309: read roles get the moderate ceiling; the owner `timeout` override still wins.
    const res = await engineDispatch.dispatchExternal({
      workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
      schema: REVIEW_TASK_SCHEMA, taskId: task.id,
      model: reviewerModel,
      engineModel: enginePrefTwin.resolveEngineModel(rEngine, 'reviewer', reviewerModel, _enginePrefs()),
      timeoutSeconds: enginePrefTwin.resolveTimeout(_enginePrefs(), 'review'),
      idleSeconds: enginePrefTwin.resolveIdle(_enginePrefs(), 'review'),   // #309 read stall monitor
    })
    // The engine adapter's review parse yields {findings} only (parse_result role_kind='review'
    // discards verdicts), so synthesize the two required verdicts from the findings. The task_review
    // twin uses the verdicts ONLY as a completeness guard — their pass/fail value is unused; the real
    // decision rides the findings' blocking severities — so this is behavior-identical to a native
    // two-verdict review that returned the same findings. An unreadable external review (null / no
    // findings array) falls open to the native Claude reviewer below (UFR-7 parity with runFinalReview).
    if (res && Array.isArray(res.findings)) {
      const v = res.findings.some((f) => f && circuitBreaker.isBlocking(f.severity)) ? 'fail' : 'pass'
      return { verdicts: { spec_compliance: v, code_quality: v }, findings: res.findings }
    }
  }
  return agent(prompt, { label: reviewTaskLabel(task, round), model: reviewerModel, schema: REVIEW_TASK_SCHEMA })
}

// The bespoke two-verdict review + bounded fix loop (FR-4..7, UFR-4/5). Never uses reviewPanel.
async function reviewLoop(workItem, generation, task, branch, wt) {
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  const history = []
  let round = 1
  // #115 runaway fix: bound the loop so it can NEVER run away. `reRequests` parks after MAX_ROUNDS
  // consecutive incomplete-verdict reviews (the live runaway: a reviewer returning a non-object
  // verdicts shape made the twin re_request forever). `iter`/MAX_ITER is a defense-in-depth overall
  // guard (mirrors buildPhase's MAX_GUARD) so any future unbounded path parks honestly too.
  let reRequests = 0
  let iter = 0
  const MAX_ITER = MAX_ROUNDS * 3 + 2
  for (;;) {
    iter += 1
    if (iter > MAX_ITER) return { parked: true, reason: 'review loop exceeded its iteration guard — park' }
    // #160: engine- + model-tier-aware per-task review (see taskReviewAgent) — honors
    // enginePreferences.reviewer + the reviewer model tier, mirroring the whole-branch review.
    const review = await taskReviewAgent(workItem, task, branch, wt, round)
    // #115 runaway fix: defensively recover a stringified `verdicts` (a leaf can still derail and emit
    // it as JSON-in-a-string despite the pinned schema — same nested-structure-stringification family
    // as the exec/fence mangles, and mirrors build_phase's existing task-list string recovery). The
    // twin reads `verdicts[k]` on a string as undefined -> re_request, which fed the runaway.
    let verdicts = review.verdicts || {}
    if (typeof verdicts === 'string') { try { verdicts = JSON.parse(verdicts) } catch (_) { verdicts = {} } }
    // #115 increment B: the bespoke two-verdict decision is decided in-process via the task_review
    // twin (no leaf). Same shape: {action, blocking, minors, cannot_verify, reason}.
    const d = taskReviewTwin.decide(verdicts, review.findings || [], round, MAX_ROUNDS, history)
    if (d.action === 'park') return { parked: true, reason: d.reason }
    if (d.action === 're_request') {              // both verdicts required (FR-5) -> re-review
      reRequests += 1
      if (reRequests >= MAX_ROUNDS) {
        return { parked: true, reason: `reviewer did not return both verdicts after ${MAX_ROUNDS} attempts — park` }
      }
      continue
    }
    if (d.action === 'complete') {
      if (Array.isArray(d.minors) && d.minors.length) {
        // append the carried-forward Minors (result unused — best-effort accumulator write). Route
        // through execJson so a dropped/garbled courier stdout is retried once (the write is idempotent).
        await execJson(
          `python3 ${libPath('minor_rollup_cli.py')} --work-item ${shq(workItem)} --append ${shq(JSON.stringify(d.minors))}`,
          'append minors',
        )
      }
      // record-before-advance: record-reviewed must succeed before the task counts reviewed.
      // (Caller does not branch on .ok today; keep behavior — the exec call still records it. Route
      // through execJson so a dropped/garbled courier stdout is retried once; the record is idempotent.)
      const reviewed = await recordTaskReviewed(workItem, task.id)
      if (!(reviewed && reviewed.ok === true && reviewed.read_back === true)) {
        return { parked: true, reason: 'task reviewed record write failed (record-before-advance) — park' }
      }
      return { parked: false }
    }
    // d.action === 'review': fence, fix the blockers + cannot-verify items, then re-review (FR-6/UFR-5).
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before fix — park (UFR-10)' }
    }
    const _fixFindings = JSON.stringify((d.blocking || []).concat(d.cannot_verify || []))
    await _implDispatch({
      workItem, roleKind: 'fix', taskId: task.id, wt, branch, model: fixerModel,  // #308
      prompt: fixTaskPrompt(task, branch, wt, _fixFindings),   // #357: external prompt states the contract
      nativeAgentCall: () => agent(
        `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer `
        + `"Task-Id: ${task.id}" (put Task-Id: ${task.id} in the FINAL paragraph of the commit message with no blank line before other trailers such as Co-Authored-By): ${_fixFindings}`,
        { label: fixTaskLabel(task), model: fixerModel }),
    })
    history.push({ round, findings: review.findings || [] })
    round += 1
  }
}

// #381: the cap decider's presentBlocking counts RAW dimension findings (including citation-less
// blockers that compileFindings drops from verdict.findings). The manual post-cap fix/handoff path
// must consume the SAME durable worklist the gate/breaker saw — read it from round-records.json
// (the panel persists dimension findings there before the cap halt returns), mirroring the panel's
// own fix leg which dispatches from the on-disk worklist rather than the compiled verdict.
async function capBlockingWorklist(runDir, verdict) {
  const round = (verdict && verdict.round) || 1
  const path = `${runDir}/round-records.json`
  let raw
  try {
    raw = await io().readText(path)
  } catch (_e) {
    return { ok: false, reason: 'round-memory-unreadable' }
  }
  let records
  try {
    records = JSON.parse(raw)
  } catch (_e) {
    return { ok: false, reason: 'round-memory-corrupt' }
  }
  if (!Array.isArray(records)) {
    return { ok: false, reason: 'round-memory-corrupt' }
  }
  const rec = records.find((r) => r && r.round === round) || records[records.length - 1]
  if (!rec || !rec.dimensions) {
    return { ok: true, blockers: [] }
  }
  const blockers = panelTally.blockingFindingsFromDimensionResults(rec.dimensions)
    .filter((f) => circuitBreaker.isBlocking(f.severity))
  return { ok: true, blockers }
}

function capOpenFindingsSummary(blockers) {
  return (blockers || []).slice(0, 50).map((f) => ({
    file: (f && f.file) || null,
    line: (f && (f.line !== undefined ? f.line : null)),
    title: (f && f.title) || '',
    severity: (f && f.severity) || '',
  }))
}

// reviewerAgent returns findings[] for the common path; when the leaf also reports confidence
// (smoke harness / external engines), ride the shaped object through so the panel gate sees it.
function _branchReviewerPayload(out) {
  if (!out || !Array.isArray(out.findings)) return null
  return out.confidence ? out : out.findings
}

async function runFinalReview(workItem, generation, branch, wt) {
  const script = [
    'import json, subprocess, sys',
    'verify = "none"',
    'minors = []',
    'v = subprocess.run(["python3", sys.argv[1] + "/verify_command_cli.py"], capture_output=True, text=True)',
    'if v.returncode == 0:',
    '    try: verify = json.loads(v.stdout or "{}").get("command", "none")',
    '    except Exception: verify = "none"',
    'm = subprocess.run(["python3", sys.argv[1] + "/minor_rollup_cli.py", "--work-item", sys.argv[2]], capture_output=True, text=True)',
    'if m.returncode == 0:',
    '    try: minors = json.loads(m.stdout or "{}").get("minors", [])',
    '    except Exception: minors = []',
    'if not isinstance(minors, list): minors = []',
    'print(json.dumps({"ok": True, "verify_command": verify, "minors": minors}))',
  ].join('\n')
  let folded = null
  try {
    folded = await courier.runCourierJson(
      'read verify + minors',
      `python3 -c ${shq(script)} ${shq(libRoot())} ${shq(workItem)}`,
      { require: ['ok', 'verify_command', 'minors'] },
    )
  } catch (_) {
    folded = null
  }
  const verify = (folded && folded.verify_command) || 'none'
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const reviewerModel = modelTierTwin.resolveModel('reviewer-deep', _overrides(), null)
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  const minors = Array.isArray(folded && folded.minors) ? folded.minors : []
  const runDir = `/tmp/workhorse-${workItem}-final-review`
  await io().mkdirp(runDir)
  // The #104 shell resolves these caller leaves from global scope. #115: the reviewer RETURNS its
  // findings[] array (the panel holds it in memory + runs the merge/tally twins in-process) — no
  // findings-generalist.json. This is the single-reviewer code leg (legKind.panel:false), so the
  // shell compiles the raw returned findings; there is no synthesis leaf.
  globalThis.reviewerAgent = async (_r, _ctx, _rub, _rdir, round) => {
    const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
    const prompt =
      `In the build worktree at ${wt}, review the whole branch ${branch}; carried-forward Minor findings: ${JSON.stringify(minors)}. `
      + `Return ONLY a JSON object {"findings":[{"file","line","title","severity":"Critical|Important|Minor|Nit","evidence"}]} ({"findings":[]} if nothing to flag). `
      + `severity MUST be one of Critical, Important, Minor, Nit (no other scale) — a blocker is Critical or Important.`
    if (rEngine !== 'claude') {
      // depth-aware effort: the whole-branch final review runs at the reviewer-deep model tier
      // (reviewerModel above), so it dispatches codex at 'review-deep' (xhigh) to match — FR-9.
      const eff = enginePrefTwin.resolveEffort(rEngine, 'review-deep', _effortOverrides())
      // #308: thread the reviewer-deep tier as a dispatch fact (the adapter's owner-policy map
      // keeps a cursor deep-reviewer on composer; the readout shows the same map's truth).
      // #309: read roles get the moderate ceiling (review-deep shares it); owner `timeout` wins.
      const res = await engineDispatch.dispatchExternal({
        workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
        schema: FINAL_REVIEW_SCHEMA,
        model: reviewerModel,
        engineModel: enginePrefTwin.resolveEngineModel(rEngine, 'reviewer-deep', reviewerModel, _enginePrefs()),
        timeoutSeconds: enginePrefTwin.resolveTimeout(_enginePrefs(), 'review-deep'),
        idleSeconds: enginePrefTwin.resolveIdle(_enginePrefs(), 'review-deep'),   // #309 read stall monitor
      })
      // UFR-7: an unreadable/incomplete external review -> null -> the shell re-runs on Claude, never
      // recorded clean. dispatchExternal returns {findings} on success or {ok:false} on failure.
      if (res && Array.isArray(res.findings)) return res.findings
      const out = await agent(prompt, { label: `branch-reviewer:r${round}`, model: reviewerModel,
        schema: FINAL_REVIEW_SCHEMA })
      return _branchReviewerPayload(out)
    }
    const out = await agent(prompt, { label: `branch-reviewer:r${round}`, model: reviewerModel,
      schema: FINAL_REVIEW_SCHEMA })
    return _branchReviewerPayload(out)
  }
  // recordDeferred writes the deferred-set (the channel the in-process tally reads) with one cheap
  // direct io-seam write — no genuine agent. (build_phase has no exec seam; the awaited io write below
  // is the bundle's cheap leaf-bash pipe, the equivalent of showrunner's exec for this leg.)
  globalThis.recordDeferred = async (report, verdict, rdir) => {
    const p = `${rdir}/deferred-set.json`
    // Deliberate degrade: a courier prose-flake on deferred-set reads as {} — worst case a
    // deferred finding re-blocks or gets re-reviewed (waste, not corruption).
    let set = await io().readJson(p, {})
    for (const id of (report && report.fixed) || []) set[String(id)] = (verdict && verdict.gate) || 'resolved'
    // #410: io.writeFile now THROWS on a persistently-unverified courier write. This deferred-set write
    // is deliberately degrade-tolerant (above) — a transport flake here is "waste, not corruption" — so
    // swallow the throw rather than let it propagate to runFixStep, which would mislabel a round whose
    // fix ALREADY succeeded as a failed fix step and discard it (review_panel_shell runFixStep catch).
    try { await io().writeFile(p, JSON.stringify(set)) }
    catch (_) { try { log(`recordDeferred: deferred-set write failed for ${p} (degraded — findings may re-block, under-count is fail-closed)`) } catch (__) {} }
  }
  // Populated after reviewPanel returns on a round-cap halt; fixStep reads it when dispatching.
  let capBlockers = []
  const fixStep = async (_fixContext, verdict, runDir) => {
    // #381: consume the cap decider's raw blocking worklist (round-records), not verdict.findings
    // (the compiled set that drops citation-less blockers). Fall back to compiled findings only when
    // the durable record is absent (resume/degrade paths).
    let blockers
    if (capBlockers.length) {
      blockers = capBlockers.slice()
    } else {
      const wl = await capBlockingWorklist(runDir, verdict)
      if (!wl.ok) return null
      blockers = wl.blockers
    }
    if (!blockers.length) {
      blockers = (verdict && verdict.findings || []).filter((f) => circuitBreaker.isBlocking(f.severity))
    }
    // Fence before the only branch-mutating final-review path (UFR-10: the module's fence-before-write
    // invariant). A lost lease -> null -> reviewPanel treats it as a fix failure -> halted -> phase parks.
    if (!(await fenceOrPark(workItem, generation))) return null   // UFR-10 fence — UNCHANGED
    // The whole-branch final review has NO per-task id in scope. #375: use the RESERVED sentinel as
    // the fix dispatch's task id — engine_adapter.commit_result stamps `Task-Id: final-review`, which
    // the build-gather accepts. (It used to pass `workItem` (the slug), which is not in the numeric
    // valid_ids, so the external fixer's own commits failed the spine's own UFR-7 resume gate.)
    await _implDispatch({
      workItem, roleKind: 'fix', taskId: FINAL_REVIEW_TASK_ID, wt, branch, model: fixerModel,  // #308/#375
      prompt: fixBranchPrompt(branch, wt, JSON.stringify(blockers)),   // #357: contract stated
      nativeAgentCall: () => agent(
        // #375: the DEFAULT fixer is native Claude (engine fails open to 'claude'), and _implDispatch
        // runs THIS prompt on the native path — not fixBranchPrompt (that is the external-dispatch
        // prompt only). So the sentinel trailer instruction MUST be stated here too, or the common
        // (default-engine) final-review fix commit carries no trailer and the resume fail-closes on
        // UFR-7 — the exact #375 bug. Mirror the per-task native fix prompt's trailer clause.
        `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings and `
        + `commit with a trailer line "Task-Id: ${FINAL_REVIEW_TASK_ID}" on EVERY commit you make (put `
        + `Task-Id: ${FINAL_REVIEW_TASK_ID} in the FINAL paragraph of the commit message with no blank `
        + `line before other trailers such as Co-Authored-By): ${JSON.stringify(blockers)}`,
        { label: 'fix-branch', model: fixerModel }),
    })
    // Always return the {fixed, deferred} REPORT shape (never the raw dispatch result / undefined):
    // a truthy report so runFixStep does NOT treat it as a fix-failure, and recordDeferred can read .fixed.
    // This preserves the exact contract of the real build_phase.js:504-511 (`return { fixed: [...] }`).
    return { fixed: blockers.map((b) => b.id || b.title), deferred: [] }
  }
  // #381: the whole-branch final review runs ONE review pass + ONE fix pass, no re-review loop.
  // maxRounds:1 caps the panel at a single review round; a round that surfaces blockers halts at
  // the cap (haltKind 'round-cap') BEFORE the panel's own fix leg runs (the fix leg only fires on a
  // 'continue' terminal, and cap 1 makes a blocking round terminal). The one fix pass is dispatched
  // BELOW, after the panel returns — then the caller proceeds to review-code (the strictly stronger
  // branch gate: 5 specialist panels, circuit breaker, confirmation rounds) rather than parking on
  // the weakest instrument's expected finding-churn. MAX_ROUNDS (and the per-task review loops that
  // use it) are deliberately untouched.
  const verdict = await reviewPanel({
    reviewerSet: ['generalist'], context: { workItem, branch }, rubric: 'review-base',
    runKey: runDir, runDir, fixStep, maxRounds: 1,
    // #396: root the whole-branch verify gate in the BUILD worktree (the tree under review), not the
    // hosting session's cwd. Without this the per-round verify runs the project's verify command in
    // the launching session's directory — false red (a broken session tree parks a good branch) and,
    // worse, false green (the branch's changes are never in the tested tree). verifyCwd threads to
    // verifyAgent's --cwd; the #382 post-cap fix-pass verify below is rooted the same way.
    // #394: this single-generalist leg's reviewerAgent (above) is tier-blind — it ALWAYS dispatches
    // at the reviewer-deep model + review-deep effort. Declaring dispatchTier makes the scheduled
    // run-tier tell that truth, so a post-baseline (resumed) round with prior findings no longer arms
    // the cheap-first escalation into a byte-identical re-dispatch that discards the first (already
    // deep) answer. The per-task panel legs keep their honest cheap-first escalation.
    legKind: { panel: false, code: true, dispatchTier: 'reviewer-deep' }, verifyCommand: verify, verifyCwd: wt,
  })
  // haltKind is the STRUCTURED cap-halt discriminator (review_loop_plan.tally-round → the shell's
  // verdict). At the decider it means "round cap reached with blockers present, verify not red"; the
  // block below then executes the owner-ratified ONE FIX PASS, so by the time haltKind reaches the
  // caller, 'round-cap' means "blockers surfaced at the cap AND the fix batch landed AND the post-fix
  // verify (if configured) is green" — the ONLY kind the caller hands off to review-code. Every other
  // halt kind (verify-fail pre- or post-fix, fix-failed/fence-lost, breaker 'other') and every
  // non-halt non-clean terminal parks. Routing keys on this field, never on prose.
  let haltKind = verdict && verdict.haltKind
  let reason = verdict && verdict.reason
  let fixPass = null
  // #381: load the cap worklist once from round-records (same raw blocking source the decider
  // counted). Only needed on a certified round-cap halt — uncertified caps park with no fix dispatch.
  if (verdict && verdict.haltKind === 'round-cap' && !verdict.uncertified) {
    const wl = await capBlockingWorklist(runDir, verdict)
    if (!wl.ok) {
      haltKind = 'other'
      reason = wl.reason
    } else {
      capBlockers = wl.blockers
    }
  }
  if (verdict && verdict.terminal === 'halted' && haltKind === 'round-cap' && !verdict.uncertified) {
    // Fail closed: the decider stamped round-cap only when presentBlocking > 0; an empty derived
    // worklist means the fix/handoff path disagrees with the gate — park, never stamp-and-advance.
    if (capBlockers.length === 0) {
      haltKind = 'other'
      reason = 'round-cap with empty blocking worklist — inconsistent with cap decider (fail closed)'
        + (reason ? ' — cap halt was: ' + reason : '')
    } else {
    // The ONE fix pass (#381, owner-ratified: "single review AND single fix pass, just no loop — not
    // advisory only"). Reuse the panel's own fixStep closure verbatim: fence-before-write (UFR-10),
    // _implDispatch (external engine + UFR-2 fall-open), the {fixed,deferred} report contract. A lost
    // fence returns null; a thrown dispatch is caught — both downgrade to 'fix-failed' (park). The fix
    // batch is deliberately UNVETTED by this leg (no re-review — that is the loop being removed);
    // review-code, the next phase, is the gate that vets it.
    let fixReport = null
    try { fixReport = await fixStep(null, verdict, runDir) } catch (_e) { fixReport = null }
    if (!fixReport) {
      haltKind = 'fix-failed'
      reason = 'one-pass fix batch did not complete (fix dispatch failed or fence lost)'
        + (reason ? ' — cap halt was: ' + reason : '')
    } else {
      // Deferred-set recording, exactly as the shell's runFixStep would have done (advisory skip-set;
      // a failed write degrades the audit trail, never the run — same deliberate-degrade contract).
      try { await recordDeferred(fixReport, verdict, runDir) } catch (_e) { /* advisory by contract */ }
      // Post-fix verify, ONCE (the fix changed the tree — the round's pre-fix verify result is stale).
      // Reuse the shell's verifyAgent leaf (round-stamped file authoritative, anti-fabrication
      // fail-closed); round 2 stamps a distinct verify-result-r2.json (cap 1 → no real round 2 exists).
      // No verify configured ('none') → skipped without a dispatch, green by the spec's "if configured".
      let postVerify = 'skipped'
      if (verify && String(verify).trim().toLowerCase() !== 'none') {
        // #396: root the post-fix verify in the build worktree too (same seam, same shellVerifyAgent).
        try { postVerify = await shellVerifyAgent(verify, runDir, ((verdict.round || 1) + 1), io(), wt) }
        catch (_e) { postVerify = 'fail' }
      }
      if (postVerify === 'pass' || postVerify === 'skipped') {
        // Fix landed + verify green → the handoff stands; the caller journals + proceeds.
        fixPass = { dispatched: true, fixed: (fixReport.fixed || []), postVerify }
      } else {
        haltKind = 'verify-fail'   // post-fix red verify PARKS — never swallowed into the handoff
        reason = 'post-fix verify ' + (postVerify === 'timeout' ? 'timed out' : 'failed')
          + ' after the one-pass fix batch — cannot hand off'
      }
    }
    }
  }
  // openFindings is a COMPACT summary (no evidence bodies) the caller journals on a round-cap handoff
  // so the still-open findings review-code will vet stay auditable — a summary, not a prose wall.
  // Built from the SAME cap worklist the fix batch consumed (raw blocking set), not verdict.findings.
  if (!capBlockers.length) {
    capBlockers = (verdict && verdict.findings || []).filter((f) => circuitBreaker.isBlocking(f.severity))
  }
  const openFindings = capOpenFindingsSummary(capBlockers)
  return { terminal: verdict && verdict.terminal, reason, haltKind, fixPass,
           openFindings, openFindingsCount: capBlockers.length,
           uncertified: !!(verdict && verdict.uncertified) }
}

// #381 handoff audit: on a round-cap handoff (the whole-branch final review found blockers at the
// one-pass cap, dispatched the one fix pass, and hands the branch to review-code), journal the
// still-open findings + the fix-pass facts so they are auditable — a COMPACT summary
// (file/line/title/severity, no evidence walls), clamped in count.
// Best-effort/fail-OPEN like the readout-disclosure journal (UFR-2): the auditable breadcrumb never
// gates the handoff, and execJson already retries once on a dropped courier stdout. The proceed
// decision is the caller's; this only records why the branch advanced with findings still open.
// Returns {ok} or {ok:false, error} so the caller can surface a failed write on the phase record
// (handoffSummary) without failing closed — review-code re-vets downstream.
function buildHandoffSummary(fr, journalResult) {
  const fixPass = (fr && fr.fixPass) || null
  const summary = {
    openFindingsCount: (fr && fr.openFindingsCount) || 0,
    openFindings: (fr && fr.openFindings) || [],
    reason: (fr && fr.reason) || '',
    fixDispatched: !!(fixPass && fixPass.dispatched),
    fixFixed: (fixPass && fixPass.fixed) || [],
    postFixVerify: (fixPass && fixPass.postVerify) || 'none',
    handoff: 'review-code',
    handoffJournalOk: !!(journalResult && journalResult.ok),
  }
  if (!summary.handoffJournalOk) {
    summary.handoffJournalError = (journalResult && journalResult.error)
      || 'final_review_handoff journal write failed'
  }
  return summary
}

async function journalFinalReviewHandoff(workItem, branch, fr) {
  const fixPass = (fr && fr.fixPass) || null
  const summary = {
    branch,
    open_findings_count: (fr && fr.openFindingsCount) || 0,
    open_findings: (fr && fr.openFindings) || [],
    reason: (fr && fr.reason) || '',
    fix_dispatched: !!(fixPass && fixPass.dispatched),
    fix_fixed: (fixPass && fixPass.fixed) || [],
    post_fix_verify: (fixPass && fixPass.postVerify) || 'none',
    handoff: 'review-code',
  }
  const detail = `whole-branch final review reached the one-pass cap with `
    + `${summary.open_findings_count} open finding(s); one fix pass dispatched `
    + `(post-fix verify: ${summary.post_fix_verify}) — handing off to review-code (unvetted by this leg)`
  try {
    const r = await execJson(
      `python3 ${libPath('journal_entry.py')} --work-item ${shq(workItem)} `
      + `--event-type final_review_handoff --step ${shq('final_review')} `
      + `--detail ${shq(detail)} --payload ${shq(JSON.stringify(summary))}`,
      'journal final-review handoff')
    if (r == null) {
      return { ok: false, error: 'final_review_handoff journal write did not run (courier/exec failed)' }
    }
    if (r.ok !== true) {
      return { ok: false, error: r.error || r.reason || 'final_review_handoff journal write failed' }
    }
    return { ok: true }
  } catch (e) {
    return { ok: false,
             error: (e && e.message) ? String(e.message) : 'final_review_handoff journal write failed' }
  }
}

// Exported to pin label formats in CI (showrunner_workhorse_label_smoke.js) — no runtime consumers.
module.exports = { buildPhase, shq, MAX_ROUNDS, park, ok, implementTaskLabel, fixTaskLabel, reviewTaskLabel }
module.exports.buildTaskPrompt = buildTaskPrompt
module.exports.fixTaskPrompt = fixTaskPrompt
module.exports.fixBranchPrompt = fixBranchPrompt
module.exports.workerContractTail = workerContractTail
module.exports.buildDeniedNote = buildDeniedNote
module.exports.buildLeafPrompt = buildLeafPrompt
module.exports.buildOneTask = buildOneTask
module.exports.reviewOneTask = reviewOneTask
module.exports.reviewLoop = reviewLoop
module.exports.fenceOrPark = fenceOrPark
module.exports.runFinalReview = runFinalReview
module.exports.resetUncommitted = resetUncommitted
module.exports.writeProvenance = writeProvenance
module.exports.recordFinalReviewClean = recordFinalReviewClean
module.exports.gatherState = gatherState
module.exports.FINAL_REVIEW_TASK_ID = FINAL_REVIEW_TASK_ID   // #375: SSOT-pinned to build_state.py
