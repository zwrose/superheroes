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

const LIB = 'plugins/superheroes/lib'
const MAX_ROUNDS = 3                 // per-task + final-review fix bound (plan: same bound as a task)

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function park(reason) { return { confidence: 'low', assumptions: [reason] } }
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
function exec(commands) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands)
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
async function execJson(cmd) {
  try {
    return await courier.runCourierJson('exec', cmd)
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// Like execJson but for commands whose stdout is a PLAIN STRING (e.g. read-gate prints `passed`).
// Retry once on an empty stdout; returns the trimmed string, or null after the retry.
async function execText(cmd) {
  try {
    return (await courier.runCourierText('exec', cmd)).trim()
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
  // execJson retries the courier ONCE on a dropped/garbled stdout before failing closed; null ->
  // the caller parks honestly (same fail-closed semantic as today, only a retry added before it).
  const parsed = await execJson(
    `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${baseArg()}`,
  )
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
    `python3 ${LIB}/definition_doc.py read-gate --doc tasks --work-item ${shq(workItem)} --root "${root}"`,
  )
  if (gate == null) return park('could not read the tasks gate — failing closed')
  if (gate !== 'passed') return park(`tasks gate not passed (${gate}) — refusing to build (UFR-1)`)
  // UFR-2: setup the content-addressed worktree/branch + persist this run's generation.
  const setup = await execJson(
    `python3 ${LIB}/build_entry.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
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
  const _taskResult = await execJson(`python3 ${LIB}/task_list_cli.py --work-item ${shq(workItem)}`)
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
        const r = await buildOneTask(workItem, generation, task, branch, validIds, wt)
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
    await recordFinalReviewClean(workItem)
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
  return agent(
    `In the build worktree at ${wt} (branch ${branch}), reset only uncommitted state: `
    + `git checkout -- . && git clean -fd . — do NOT touch any commit. `
    + `Return JSON {"ok":true} on success or {"ok":false,"error":"<reason>"}.`,
    { label: 'reset-uncommitted', schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
}

// Record build provenance once over HEAD = X (FR-9), via the existing prov_entry leaf.
// exec/parse fail -> {ok:false, error:'provenance leaf did not run'} so the caller's !p.ok parks.
async function writeProvenance(workItem) {
  // execJson retries the courier ONCE on a dropped/garbled stdout; null -> the SAME fail-closed
  // fallback as today ({ok:false} -> caller parks). A parseable {ok:false} is returned as-is (no retry).
  const r = await execJson(`python3 ${LIB}/prov_entry.py --step build --work-item ${shq(workItem)}`)
  if (r == null) return { ok: false, error: 'provenance leaf did not run' }
  return r
}

// Record final-review-clean. Caller does not check .ok today (preserve that), but stay fail-closed-safe.
async function recordFinalReviewClean(workItem) {
  // Caller does not branch on .ok today (preserve that), but stay fail-closed-safe + retry the courier.
  const r = await execJson(
    `python3 ${LIB}/build_state_cli.py record-final-review --work-item ${shq(workItem)} --clean true`,
  )
  if (r == null) return { ok: false }
  return r
}

// fenceOrPark: lease-fence acquire. CRITICAL fail-closed: an exec/parse failure must read as a LOST
// fence (false), NEVER as ok — a fence failure read as ok would let an unfenced write through (UFR-10).
async function fenceOrPark(workItem, generation) {
  // execJson retries the courier ONCE on a dropped/garbled stdout; null -> false (fence reads LOST),
  // preserving the CRITICAL fail-closed semantic (an exec/parse failure must NEVER read as ok — an
  // unfenced write would slip through, UFR-10). A parseable {ok:false} returns false the same.
  const f = await execJson(
    `python3 ${LIB}/fence_cli.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
  )
  return !!(f && f.ok)
}

// Build one task test-first (FR-3) with bounded recovery (UFR-3), then review it. `validIds` is the
// FULL enumeration's task ids (comma-joined) so the write-time trailer check scores every above-base
// commit against the whole task set — not just this task (an earlier task's commit is not "unmapped").
async function buildOneTask(workItem, generation, task, branch, validIds, wt) {
  let attempt = 1
  for (;;) {
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before build — park (UFR-10)' }
    }
    const worker = await agent(
      `In the build worktree at ${wt} (branch ${branch}), implement Task ${task.id} (${task.title}) TEST-FIRST: write the test(s), `
      + `run to observe FAIL, implement, run to observe PASS. Commit with a trailer line `
      + `"Task-Id: ${task.id}" on EVERY commit you make for this task. Return JSON `
      + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool}}.`,
      { label: 'worker', schema: { type: 'object', required: ['ok'] } })
    if (worker.ok) {
      // write-time trailer enforcement (UFR-7): every above-base commit must carry its Task-Id.
      // This is a per-built-task CORRECTNESS read (NOT the FR-4a per-iteration resume gather).
      // execJson retries the courier ONCE on a dropped/garbled stdout, then fails closed: a leaf that
      // can't run / returns unparseable output must NOT read as a clean trailer state — park (UFR-7).
      const chk = await execJson(
        `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${baseArg()}`,
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
      const jrnl = await execJson(
        `python3 ${LIB}/journal_entry.py --work-item ${shq(workItem)} --payload `
        + `${shq(JSON.stringify({ phase: 'workhorse', event: 'task_built', task: task.id, evidence: worker.evidence }))}`,
      )
      if (!(jrnl && jrnl.ok)) {
        return { parked: true, reason: 'task journal write failed (record-before-advance) — park' }
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
    const review = await agent(
      `Review Task ${task.id} (${task.title}) on branch ${branch}. Return JSON `
      + `{"verdicts":{"spec_compliance":"pass|fail","code_quality":"pass|fail"},`
      + `"findings":[{"severity","file","title","cannot_verify_from_diff"}]}.`,
      { label: 'review',
        schema: {
          type: 'object',
          required: ['verdicts'],
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
        } })
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
          `python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)} --append ${shq(JSON.stringify(d.minors))}`,
        )
      }
      // record-before-advance: record-reviewed must succeed before the task counts reviewed.
      // (Caller does not branch on .ok today; keep behavior — the exec call still records it. Route
      // through execJson so a dropped/garbled courier stdout is retried once; the record is idempotent.)
      await execJson(
        `python3 ${LIB}/build_state_cli.py record-reviewed --work-item ${shq(workItem)} --task ${shq(task.id)}`,
      )
      return { parked: false }
    }
    // d.action === 'review': fence, fix the blockers + cannot-verify items, then re-review (FR-6/UFR-5).
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before fix — park (UFR-10)' }
    }
    await agent(
      `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer `
      + `"Task-Id: ${task.id}": ${JSON.stringify((d.blocking || []).concat(d.cannot_verify || []))}`,
      { label: 'fixer', model: fixerModel })
    history.push({ round, findings: review.findings || [] })
    round += 1
  }
}

async function runFinalReview(workItem, generation, branch, wt) {
  // verify command via execJson (retry the courier once on a dropped/garbled stdout); on fail -> 'none'
  // (verify command unknown -> the verify_gate twin fails closed downstream; a missing verify command
  // already maps to a safe path).
  const _verify = await execJson(`python3 ${LIB}/verify_command_cli.py`)
  const verify = (_verify && _verify.command) || 'none'
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const reviewerModel = modelTierTwin.resolveModel('reviewer-deep', _overrides(), null)
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  // carried-forward Minors via execJson (retry the courier once on a dropped/garbled stdout); on fail -> [].
  const _minorsResult = await execJson(`python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)}`)
  const minors = Array.isArray(_minorsResult && _minorsResult.minors) ? _minorsResult.minors : []
  const runDir = `/tmp/workhorse-${workItem}-final-review`
  // The #104 shell resolves these caller leaves from global scope. #115: the reviewer RETURNS its
  // findings[] array (the panel holds it in memory + runs the merge/tally twins in-process) — no
  // findings-generalist.json. This is the single-reviewer code leg (legKind.panel:false), so the
  // shell compiles the raw returned findings; there is no synthesis leaf.
  globalThis.reviewerAgent = async (_r, _ctx, _rub, _rdir, round) => {
    const out = await agent(
      `In the build worktree at ${wt}, review the whole branch ${branch}; carried-forward Minor findings: ${JSON.stringify(minors)}. `
      + `Return ONLY a JSON object {"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if nothing to flag).`,
      { label: `reviewer:${round}`, model: reviewerModel,
        schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
    return (out && Array.isArray(out.findings)) ? out.findings : null
  }
  // recordDeferred writes the deferred-set (the channel the in-process tally reads) with one cheap
  // direct io-seam write — no genuine agent. (build_phase has no exec seam; the awaited io write below
  // is the bundle's cheap leaf-bash pipe, the equivalent of showrunner's exec for this leg.)
  globalThis.recordDeferred = async (report, verdict, rdir) => {
    const p = `${rdir}/deferred-set.json`
    let set = await io().readJson(p, {})
    for (const id of (report && report.fixed) || []) set[String(id)] = (verdict && verdict.gate) || 'resolved'
    await io().writeFile(p, JSON.stringify(set))
  }
  const fixStep = async (blockers) => {
    // Fence before the only branch-mutating final-review path (UFR-10: the module's fence-before-write
    // invariant). A lost lease -> null -> reviewPanel treats it as a fix failure -> halted -> phase parks.
    if (!(await fenceOrPark(workItem, generation))) return null
    await agent(`In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
      { label: 'final-fixer', model: fixerModel })
    return { fixed: blockers.map((b) => b.id || b.title) }
  }
  const verdict = await reviewPanel({
    reviewerSet: ['generalist'], context: { workItem, branch }, rubric: 'review-base',
    runKey: runDir, runDir, fixStep, maxRounds: MAX_ROUNDS,
    legKind: { panel: false, code: true }, verifyCommand: verify,
  })
  return { terminal: verdict && verdict.terminal }
}

module.exports = { buildPhase, shq, LIB, MAX_ROUNDS, park, ok }
module.exports.buildOneTask = buildOneTask
module.exports.reviewOneTask = reviewOneTask
module.exports.reviewLoop = reviewLoop
module.exports.fenceOrPark = fenceOrPark
module.exports.runFinalReview = runFinalReview
module.exports.resetUncommitted = resetUncommitted
module.exports.writeProvenance = writeProvenance
module.exports.recordFinalReviewClean = recordFinalReviewClean
module.exports.gatherState = gatherState
