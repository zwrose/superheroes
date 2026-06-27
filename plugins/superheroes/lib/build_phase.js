// plugins/superheroes/lib/build_phase.js
// The native "workhorse" build phase (#87). CONTROL FLOW ONLY (CONVENTIONS §10.1): every judgement
// is a pure Python decider behind a *_cli.py bridge; this module detects events and sequences them.
// It makes NO PR/merge/force-push (FR-10).
const { reviewPanel } = require('./review_panel_shell.js')
const { io } = require('./io_seam.js')

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
  const tasks = (await cmdRunner(`python3 ${LIB}/task_list_cli.py --work-item ${shq(workItem)}`,
    { label: 'task-list', schema: { type: 'object' } })).tasks || []
  if (tasks.length === 0) { log('no tasks to build'); return ok() }
  // Reconcile-driven loop: reality (commits + records) wins; any ambiguity parks. Bounded by a
  // guard so a non-progressing reconcile can never spin forever.
  const validIds = tasks.map((t) => t.id).join(',')
  let lastAction = 'none'      // last reconcile action + gathered state, for guard-bound diagnosability
  let lastState = {}
  for (let guard = 0; guard < tasks.length * 4 + 8; guard += 1) {
    const state = await cmdRunner(
      `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}`,
      { label: 'build_state_cli.py gather', schema: { type: 'object' } })
    lastState = state
    const d = await cmdRunner(
      `python3 ${LIB}/build_progress_cli.py --state ${shq(JSON.stringify({ ...state, task_list: tasks }))}`,
      { label: 'build_progress_cli.py', schema: { type: 'object', required: ['action'] } })
    lastAction = d.action
    if (d.action === 'complete') return ok()
    if (d.action === 'park') return park(d.reason || 'build_progress parked')
    if (d.action === 'reset_uncommitted') {
      // Fence before any worktree mutation (UFR-10: the plan requires a fence before every
      // commit/RESET), and park honestly if the reset itself fails (UFR-6).
      if (!(await fenceOrPark(workItem, generation))) return park('lease lost before reset — park (UFR-10)')
      const rr = await resetUncommitted(wt, branch)
      if (!rr.ok) return park('could not reset uncommitted changes: ' + (rr.error || 'unknown'))
      continue
    }
    if (d.action === 'build_task') {
      const r = await buildOneTask(workItem, generation, d.resume_at, branch, validIds, wt)
      if (r.parked) return park(r.reason); continue
    }
    if (d.action === 'review_task') {
      const r = await reviewOneTask(workItem, generation, d.resume_at, branch, wt)
      if (r.parked) return park(r.reason); continue
    }
    if (d.action === 'final_review') {
      const fr = await runFinalReview(workItem, generation, branch, wt)
      // UFR-4 fail-closed intent: only a 'clean' terminal advances. Parking on
      // 'clean-with-skips'/'halted'/'cannot-certify' is deliberate — a skipped blocker must park.
      if (fr.terminal !== 'clean') return park('whole-branch final review did not reach clean: ' + fr.terminal)
      await recordFinalReviewClean(workItem); continue
    }
    if (d.action === 'write_provenance') {
      const p = await writeProvenance(workItem)
      if (!p.ok) return park('provenance not recorded: ' + (p.error || 'unknown')); continue
    }
    return park('unexpected reconcile action: ' + d.action)
  }
  return park('build loop exceeded its guard bound without completing (last action: ' + lastAction
    + ', committed: ' + ((lastState.committed_task_ids || []).length)
    + ', unmapped: ' + (lastState.unmapped_commits || 0) + ')')
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
      const chk = await cmdRunner(
        `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}`,
        { label: 'build_state_cli.py gather', schema: { type: 'object' } })
      if ((chk.unmapped_commits || 0) > 0) {
        return { parked: true, reason: 'a commit lacks its Task-Id trailer — park (UFR-7)' }
      }
      await cmdRunner(
        `python3 ${LIB}/journal_entry.py --work-item ${shq(workItem)} --payload `
        + `${shq(JSON.stringify({ phase: 'workhorse', event: 'task_built', task: task.id, evidence: worker.evidence }))}`,
        { label: 'journal_entry.py', schema: { type: 'object', required: ['ok'] } })
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
      if ((d.minors || []).length) {
        await cmdRunner(
          `python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)} --append ${shq(JSON.stringify(d.minors))}`,
          { label: 'minor_rollup_cli.py', schema: { type: 'object' } })
      }
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
  const minors = (await cmdRunner(
    `python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)}`,
    { label: 'minor_rollup_cli.py', schema: { type: 'object' } })).minors || []
  const runDir = `/tmp/workhorse-${workItem}-final-review`
  // The #104 shell resolves these caller leaves from global scope (showrunner.js:13-15).
  global.reviewerAgent = async (_r, _ctx, _rub, _rdir, round) => {
    await agent(
      `In the build worktree at ${wt}, review the whole branch ${branch}; carried-forward Minor findings: ${JSON.stringify(minors)}. `
      + `Write findings-generalist.json into round-${round}/.`,
      { label: `reviewer:${round}`, model: reviewerModel })
    return true
  }
  global.recordDeferred = async (report, verdict, rdir) => {
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
