// plugins/superheroes/lib/build_phase.js
// The native "workhorse" build phase (#87). CONTROL FLOW ONLY: this module detects events and
// sequences them — it makes NO judgement inline. #115: every judgement is an in-process parity-locked
// JS twin (model_tier / worker_recovery / task_review / build_progress.reconcile); every IO/side-effect
// runs through the exec(raw)+in-process-parse dumb pipe, parsed deterministically and fail-closed (the
// old "trust-the-leaf-JSON" *_cli.py bridge is gone). It makes NO PR/merge/force-push (FR-10).
// FR-4a (#115): build state lives in memory during a continuous run. build_state gather /
// build_progress.reconcile are called ONLY on entry/resume (not per loop iteration).
const { reviewPanel } = require('./review_panel_shell.js')
const { io } = require('./io_seam.js')
const modelTierTwin = require('./model_tier.js')
const courier = require('./courier_exec.js')
// #115 increment B: the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (no leaf — judgments live in twins, called in-process). Pure
// deciders with no IO, so a top-level require is safe (no load-time cycle).
const workerRecoveryTwin = require('./worker_recovery.js')
const taskReviewTwin = require('./task_review.js')
// #160: the blocking-severity set (Critical/Important) — the single source of truth the task_review
// twin's partition also reads. Used to synthesize the per-task review's two verdicts from an external
// engine's findings-only result (below). Pure module, safe to require at top level (no load-time cycle).
const circuitBreaker = require('./circuit_breaker.js')
// #38 Task 11: the engine-axis resolver twin + the spine leaf wrapper that dispatches external
// engines (codex|cursor) for the write (build|fix) and read (review) roles.
const engineDispatch = require('./engine_dispatch.js')
const enginePrefTwin = require('./engine_pref.js')

// #170: compose the spine CODE root (plugin-cache lib dir, or the repo-relative default) at
// CALL time — never a module-load const, since the bundle ENTRY plants __SR_LIB after factories.
const { libPath, libRoot } = require('./lib_root.js')
const MAX_ROUNDS = 3                 // per-task + final-review fix bound (plan: same bound as a task)

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
function ok() { return { confidence: 'high', assumptions: [] } }

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
async function execJson(cmd, label) {
  try {
    return await courier.runCourierJson(label || 'exec', cmd)
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// Like execJson but for commands whose stdout is a PLAIN STRING (e.g. read-gate prints `passed`).
// Retry once on an empty stdout; returns the trimmed string, or null after the retry.
async function execText(cmd, label) {
  try {
    return (await courier.runCourierText(label || 'exec', cmd)).trim()
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
  // UFR-1: refuse unless the tasks gate is passed. read-gate prints a PLAIN STRING (e.g. 'passed'),
  // NOT JSON — execText returns the trimmed raw stdout (no JSON.parse), retrying the courier ONCE on
  // an empty stdout (a courier-drop) before failing closed. null -> park (fail closed on exec-fail).
  const gate = await execText(
    `python3 ${libPath('definition_doc.py')} read-gate --doc tasks --work-item ${shq(workItem)} --root "${root}"`,
    'read gate',
  )
  if (gate == null) return park('could not read the tasks gate — failing closed')
  if (gate !== 'passed') return park(`tasks gate not passed (${gate}) — refusing to build (UFR-1)`)
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
  if (!alreadyFinalClean) {
    const fr = await runFinalReview(workItem, generation, branch, wt)
    // UFR-4 fail-closed intent: only a 'clean' terminal advances. Parking on
    // 'clean-with-skips'/'halted'/'cannot-certify' is deliberate — a skipped blocker must park.
    if (fr.terminal !== 'clean') return park('whole-branch final review did not reach clean: ' + fr.terminal)
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

  return ok()
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

// Record final-review-clean. Caller does not check .ok today (preserve that), but stay fail-closed-safe.
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
async function _implDispatch({ workItem, roleKind, taskId, prompt, wt, branch, nativeAgentCall }) {
  const engine = enginePrefTwin.resolveEngine(roleKind, _enginePrefs())
  if (engine === 'claude') return nativeAgentCall()
  // UFR-4: before the FIRST external WRITE, confirm the host grants this engine write authority.
  // Denied -> fall open to Claude for the whole run (build AND fixes) + one notice. Read roles skip this.
  if (!(await _implWriteAuthorized(engine, wt))) return nativeAgentCall()
  // FR-9: effort override comes from the engine-prefs effort sub-map (keyed by role_kind), NOT the
  // model-tier _overrides() map (keyed by role->model — resolveEffort could never match it).
  const effort = enginePrefTwin.resolveEffort(engine, roleKind, _effortOverrides())
  const res = await engineDispatch.dispatchExternal({
    engine, roleKind, effort, prompt, cwd: wt, schema: { type: 'object', required: ['ok'] },
    taskId, workItem,
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
    + `Co-Authored-By). ${require('./showrunner.js').TIMEOUT_PROCEED_CONTRACT} If the 15-minute timeout `
    + `fired on ANY substantive step (not a verification probe — an actual implementation/commit action), set `
    + `"deniedAction" to a short description of what you could not do; otherwise omit it or set it `
    + `to null — never fabricate a completed step you were denied. Return JSON `
    + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool},"deniedAction":"<string or null>"}.`
    + (retryNote || '')
    + (deniedNote || '')
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
    // Task 12 (FR-8): register the command the spine just composed for this leaf against the run's
    // generation (the run_id), so the enforcer allows the leaf to run it byte-for-byte without a
    // prompt — and only within the run that composed it. Recorded per attempt (a retry's prompt is a
    // NEW composed command). The seam is fail-open (UFR-2): a record error never derails the build.
    try { require('./showrunner.js')._recordComposed(generation, prompt, workItem) } catch (_e) { /* fail-open */ }
    const worker = await _implDispatch({
      workItem, roleKind: 'build', taskId: task.id, wt, branch,
      prompt,
      nativeAgentCall: () => agent(
        prompt,
        { label: implementTaskLabel(task, taskCount), schema: { type: 'object', required: ['ok'] } }),
    })
    // UFR-6/UFR-8: a substantive build step the 15-min timeout denied taints the build evidence.
    // Record it on both carriers (recordBuildDenialIfAny); a failed fail-closed carrier parks here.
    const denialPark = await recordBuildDenialIfAny(worker, workItem, task, generation, deniedActions)
    if (denialPark) return denialPark
    if (worker.ok) {
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
    const rec = workerRecoveryTwin.decide(attempt, worker.signal || 'needs_context')
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
    findings: { type: 'array' },
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
    + `"findings":[{"severity","file","title","cannot_verify_from_diff"}]}.`
  const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
  if (rEngine !== 'claude') {
    // regular per-task review effort ('review'/high); the whole-branch review dispatches 'review-deep'.
    const eff = enginePrefTwin.resolveEffort(rEngine, 'review', _effortOverrides())
    const res = await engineDispatch.dispatchExternal({
      workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
      schema: REVIEW_TASK_SCHEMA, taskId: task.id,
    })
    // The engine adapter's review parse yields {findings} only (parse_result role_kind='review'
    // discards verdicts), so synthesize the two required verdicts from the findings. The task_review
    // twin uses the verdicts ONLY as a completeness guard — their pass/fail value is unused; the real
    // decision rides the findings' blocking severities — so this is behavior-identical to a native
    // two-verdict review that returned the same findings. An unreadable external review (null / no
    // findings array) falls open to the native Claude reviewer below (UFR-7 parity with runFinalReview).
    if (res && Array.isArray(res.findings)) {
      const v = res.findings.some((f) => f && circuitBreaker.BLOCKING.has(f.severity)) ? 'fail' : 'pass'
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
      workItem, roleKind: 'fix', taskId: task.id, wt, branch,
      prompt: `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer "Task-Id: ${task.id}" (put Task-Id: ${task.id} in the FINAL paragraph of the commit message with no blank line before other trailers such as Co-Authored-By): ${_fixFindings}`,
      nativeAgentCall: () => agent(
        `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer `
        + `"Task-Id: ${task.id}" (put Task-Id: ${task.id} in the FINAL paragraph of the commit message with no blank line before other trailers such as Co-Authored-By): ${_fixFindings}`,
        { label: fixTaskLabel(task), model: fixerModel }),
    })
    history.push({ round, findings: review.findings || [] })
    round += 1
  }
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
      + `Return ONLY a JSON object {"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if nothing to flag).`
    if (rEngine !== 'claude') {
      // depth-aware effort: the whole-branch final review runs at the reviewer-deep model tier
      // (reviewerModel above), so it dispatches codex at 'review-deep' (xhigh) to match — FR-9.
      const eff = enginePrefTwin.resolveEffort(rEngine, 'review-deep', _effortOverrides())
      const res = await engineDispatch.dispatchExternal({
        workItem, engine: rEngine, roleKind: 'review', effort: eff, prompt, cwd: wt,
        schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } },
      })
      // UFR-7: an unreadable/incomplete external review -> null -> the shell re-runs on Claude, never
      // recorded clean. dispatchExternal returns {findings} on success or {ok:false} on failure.
      if (res && Array.isArray(res.findings)) return res.findings
      const out = await agent(prompt, { label: `branch-reviewer:r${round}`, model: reviewerModel,
        schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
      return (out && Array.isArray(out.findings)) ? out.findings : null
    }
    const out = await agent(prompt, { label: `branch-reviewer:r${round}`, model: reviewerModel,
      schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
    return (out && Array.isArray(out.findings)) ? out.findings : null
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
    await io().writeFile(p, JSON.stringify(set))
  }
  const fixStep = async (_fixContext, verdict, _runDir) => {
    const blockers = (verdict && verdict.findings || []).filter((f) => f.severity === 'Critical' || f.severity === 'Important')
    // Fence before the only branch-mutating final-review path (UFR-10: the module's fence-before-write
    // invariant). A lost lease -> null -> reviewPanel treats it as a fix failure -> halted -> phase parks.
    if (!(await fenceOrPark(workItem, generation))) return null   // UFR-10 fence — UNCHANGED
    // The whole-branch final review has NO per-task id in scope (mirror the real 504-511 closure):
    // use the work-item as the fix dispatch's task id for the trailer/journal.
    await _implDispatch({
      workItem, roleKind: 'fix', taskId: workItem, wt, branch,
      prompt: `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
      nativeAgentCall: () => agent(
        `In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
        { label: 'fix-branch', model: fixerModel }),
    })
    // Always return the {fixed, deferred} REPORT shape (never the raw dispatch result / undefined):
    // a truthy report so runFixStep does NOT treat it as a fix-failure, and recordDeferred can read .fixed.
    // This preserves the exact contract of the real build_phase.js:504-511 (`return { fixed: [...] }`).
    return { fixed: blockers.map((b) => b.id || b.title), deferred: [] }
  }
  const verdict = await reviewPanel({
    reviewerSet: ['generalist'], context: { workItem, branch }, rubric: 'review-base',
    runKey: runDir, runDir, fixStep, maxRounds: MAX_ROUNDS,
    legKind: { panel: false, code: true }, verifyCommand: verify,
  })
  return { terminal: verdict && verdict.terminal }
}

// Exported to pin label formats in CI (showrunner_workhorse_label_smoke.js) — no runtime consumers.
module.exports = { buildPhase, shq, MAX_ROUNDS, park, ok, implementTaskLabel, fixTaskLabel, reviewTaskLabel }
module.exports.buildTaskPrompt = buildTaskPrompt
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
