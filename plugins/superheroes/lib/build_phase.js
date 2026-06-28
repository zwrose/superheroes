// plugins/superheroes/lib/build_phase.js
// The native "workhorse" build phase (#87). CONTROL FLOW ONLY (CONVENTIONS §10.1): every judgement
// is a pure Python decider behind a *_cli.py bridge; this module detects events and sequences them.
// It makes NO PR/merge/force-push (FR-10).
// FR-4a (#115): build state lives in memory during a continuous run. build_state gather /
// build_progress.reconcile are called ONLY on entry/resume (not per loop iteration).
const { reviewPanel } = require('./review_panel_shell.js')
const { io } = require('./io_seam.js')
const { reconcile } = require('./build_progress.js')

const LIB = 'plugins/superheroes/lib'
const MAX_ROUNDS = 3                 // per-task + final-review fix bound (plan: same bound as a task)

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function park(reason) { return { confidence: 'low', assumptions: [reason] } }
function ok() { return { confidence: 'high', assumptions: [] } }

// JS<->Python bridge: run a lib command in a leaf, return its stdout JSON. Forwards the caller's
// label (so real-run records AND smokes can distinguish calls — unlike showrunner's fixed 'lib').
async function cmdRunner(cmd, opts = {}) {
  // Map each top-level key of the command's stdout JSON to the same-named StructuredOutput field —
  // never collapse the whole JSON into one field (a schema-valid-but-wrong live-only derailment).
  return agent(
    `Use the Bash tool to run exactly this command. It prints ONE JSON object to stdout. Return that ` +
    `object via StructuredOutput by copying each of its top-level keys to the same-named output field, ` +
    `values exactly as printed. Do NOT put the whole JSON into a single field, do NOT stringify or nest ` +
    `it, and do NOT add commentary or extra fields:\n\n${cmd}`,
    { label: opts.label || 'lib', schema: opts.schema })
}

// FR-4a: gather authoritative git state (entry/resume only, NOT per loop iteration).
// Label 'gather-entry' is distinguishable from the per-built-task trailer-check gather
// (label 'build_state_cli.py gather') so smokes can pin the once-at-entry property exactly.
async function gatherState(workItem, branch, validIds, wt) {
  return cmdRunner(
    `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}`,
    { label: 'gather-entry', schema: { type: 'object' } })
}

// FR-4a: derive the starting action + resume_at from authoritative state using the in-process twin.
// Returns the reconcile decision object ({action, resume_at?, reason?}).
function reconcileState(taskList, state) {
  return reconcile(
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
  // UFR-1: refuse unless the tasks gate is passed (read-gate prints a plain string, not JSON).
  const gate = String(await agent(
    `Run exactly this and return only stdout: python3 ${LIB}/definition_doc.py read-gate `
    + `--doc tasks --work-item ${shq(workItem)} --root "${root}"`, { label: 'tasks-gate' })).trim()
  if (gate !== 'passed') return park(`tasks gate not passed (${gate}) — refusing to build (UFR-1)`)
  // UFR-2: setup the content-addressed worktree/branch + persist this run's generation.
  const setup = await cmdRunner(
    `python3 ${LIB}/build_entry.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
    { label: 'build-setup', schema: { type: 'object', properties: { branch: { type: 'string' }, path: { type: 'string' }, error: { type: 'string' } } } })
  if (!setup.branch) return park('build setup failed: ' + (setup.error || 'no branch'))
  const branch = setup.branch
  // The build branch is checked out in a SEPARATE managed build worktree (build_entry -> buildtree);
  // every git read/write below must operate there, not in the showrunner's main checkout.
  const wt = setup.path
  // UFR-8: zero executable tasks -> finish without building.
  // BUG-2 fix: pin tasks as array in schema so StructuredOutput enforces shape.
  // BUG-3 fix: defensively recover a JSON string; non-array after recovery -> park.
  const _taskResult = await cmdRunner(`python3 ${LIB}/task_list_cli.py --work-item ${shq(workItem)}`,
    { label: 'task-list', schema: { type: 'object', properties: { tasks: { type: 'array' }, raw_task_heading_count: { type: 'number' } }, required: ['tasks'] } })
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
  let state = await gatherState(workItem, branch, validIds, wt)

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
async function writeProvenance(workItem) {
  return cmdRunner(
    `python3 ${LIB}/prov_entry.py --step build --work-item ${shq(workItem)}`,
    { label: 'prov_entry.py', schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
}

async function recordFinalReviewClean(workItem) {
  return cmdRunner(
    `python3 ${LIB}/build_state_cli.py record-final-review --work-item ${shq(workItem)} --clean true`,
    { label: 'record-final-review', schema: { type: 'object', required: ['ok'] } })
}

async function fenceOrPark(workItem, generation) {
  const f = await cmdRunner(
    `python3 ${LIB}/fence_cli.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
    { label: 'fence', schema: { type: 'object', required: ['ok'] } })
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
      const chk = await cmdRunner(
        `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}`,
        { label: 'build_state_cli.py gather', schema: { type: 'object' } })
      if ((chk.unmapped_commits || 0) > 0) {
        return { parked: true, reason: 'a commit lacks its Task-Id trailer — park (UFR-7)' }
      }
      // record-before-advance: journal must succeed before the task counts as built. Guard the .ok
      // explicitly (defense-in-depth for invariant #4): a failed journal must NOT advance into the
      // review loop — park honestly (#115 final review FIX 8). The FR-4a forward-walk no longer
      // self-heals a missed journal per-iteration, so this guard is the advance fence.
      const jrnl = await cmdRunner(
        `python3 ${LIB}/journal_entry.py --work-item ${shq(workItem)} --payload `
        + `${shq(JSON.stringify({ phase: 'workhorse', event: 'task_built', task: task.id, evidence: worker.evidence }))}`,
        { label: 'journal_entry.py', schema: { type: 'object', required: ['ok'] } })
      if (!(jrnl && jrnl.ok)) {
        return { parked: true, reason: 'task journal write failed (record-before-advance) — park' }
      }
      return reviewLoop(workItem, generation, task, branch, wt)
    }
    const rec = await cmdRunner(
      `python3 ${LIB}/worker_recovery_cli.py --attempt ${attempt} --signal ${shq(worker.signal || 'needs_context')}`,
      { label: 'worker_recovery_cli.py', schema: { type: 'object', required: ['action'] } })
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
  const fixerModel = (await cmdRunner(
    `python3 ${LIB}/model_tier_resolve.py --role fixer --context code`,
    { label: 'model_tier_resolve.py', schema: { type: 'object' } })).model
  const history = []
  let round = 1
  for (;;) {
    const review = await agent(
      `Review Task ${task.id} (${task.title}) on branch ${branch}. Return JSON `
      + `{"verdicts":{"spec_compliance":"pass|fail","code_quality":"pass|fail"},`
      + `"findings":[{"severity","file","title","cannot_verify_from_diff"}]}.`,
      { label: 'review', schema: { type: 'object', required: ['verdicts'] } })
    const d = await cmdRunner(
      `python3 ${LIB}/task_review_cli.py --verdicts ${shq(JSON.stringify(review.verdicts || {}))} `
      + `--findings ${shq(JSON.stringify(review.findings || []))} --round ${round} `
      + `--max-rounds ${MAX_ROUNDS} --history ${shq(JSON.stringify(history))}`,
      { label: 'task_review_cli.py', schema: { type: 'object', required: ['action'] } })
    if (d.action === 'park') return { parked: true, reason: d.reason }
    if (d.action === 're_request') continue        // both verdicts required (FR-5) -> re-review
    if (d.action === 'complete') {
      if (Array.isArray(d.minors) && d.minors.length) {
        await cmdRunner(
          `python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)} --append ${shq(JSON.stringify(d.minors))}`,
          { label: 'minor_rollup_cli.py', schema: { type: 'object' } })
      }
      // record-before-advance: record-reviewed must succeed before the task counts reviewed.
      await cmdRunner(
        `python3 ${LIB}/build_state_cli.py record-reviewed --work-item ${shq(workItem)} --task ${shq(task.id)}`,
        { label: 'record-reviewed', schema: { type: 'object', required: ['ok'] } })
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
  const verify = (await cmdRunner(`python3 ${LIB}/verify_command_cli.py`,
    { label: 'verify_command_cli.py', schema: { type: 'object', required: ['command'] } })).command || 'none'
  const reviewerModel = (await cmdRunner(
    `python3 ${LIB}/model_tier_resolve.py --role reviewer-deep`,
    { label: 'model_tier_resolve.py --role reviewer-deep', schema: { type: 'object' } })).model
  const fixerModel = (await cmdRunner(
    `python3 ${LIB}/model_tier_resolve.py --role fixer --context code`,
    { label: 'model_tier_resolve.py --role fixer', schema: { type: 'object' } })).model
  const _minorsResult = await cmdRunner(
    `python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)}`,
    { label: 'minor_rollup_cli.py', schema: { type: 'object' } })
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

module.exports = { buildPhase, cmdRunner, shq, LIB, MAX_ROUNDS, park, ok }
module.exports.buildOneTask = buildOneTask
module.exports.reviewOneTask = reviewOneTask
module.exports.reviewLoop = reviewLoop
module.exports.fenceOrPark = fenceOrPark
module.exports.runFinalReview = runFinalReview
module.exports.resetUncommitted = resetUncommitted
module.exports.writeProvenance = writeProvenance
module.exports.recordFinalReviewClean = recordFinalReviewClean
