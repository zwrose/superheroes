// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (the #86 review_panel_shell.js posture): the script
// forwards decisions; every judgement is a pure Python decider or a #86 shell.
const { reviewPanel } = require('./review_panel_shell.js')

const REVIEW_CODE_REVIEWERS = [
  'architecture-reviewer', 'code-reviewer', 'security-reviewer',
  'test-reviewer', 'premortem-reviewer',
]

// The slice's derisk: review-code's 5-reviewer panel, single-pass (maxRounds:1, no auto-fix).
// reviewerAgent / recordDeferred are the #86 caller-supplied leaf wrappers.
async function runReviewCodePanel({ runDir, context, rubric, reviewerAgent, recordDeferred }) {
  global.reviewerAgent = reviewerAgent
  global.recordDeferred = recordDeferred
  return reviewPanel({
    reviewerSet: REVIEW_CODE_REVIEWERS,
    context, rubric, runKey: runDir, runDir,
    fixStep: async () => ({}),   // defer-only stub; never reached at maxRounds:1
    maxRounds: 1,
  })
}

module.exports = { runReviewCodePanel, REVIEW_CODE_REVIEWERS }

// The plan/tasks doc-review panel (the five reviewers, unchanged by #34 — spec Assumptions).
const DOC_REVIEWERS = ['architecture-reviewer', 'code-reviewer', 'security-reviewer',
                       'test-reviewer', 'premortem-reviewer']

// the four caller-supplied doc-leg leaf wrappers the #104 shell expects (panel:true). Each is a
// single leaf (no fan-out). Set as global.* before reviewPanel, exactly as runReviewCodePanel does.
// NOTE: the findings filename is `findings-<full roster name>.json` — panel_tally reads the
// roster verbatim (findings_path), and the tally is given the full DOC_REVIEWERS names, so the
// reviewer write, the merge read, and the tally read MUST all use the same full names.
async function docReviewerAgent(reviewer, context, rubric, runDir, round) {
  await agent(
    `Run the ${reviewer} review of the ${context.docType} definition-doc at ${context.docPath} ` +
    `against the ${rubric} rubric (reframed to a ${context.docType} doc). Write findings to ` +
    `${runDir}/round-${round}/findings-${reviewer}.json (a JSON array; [] if none).`,
    { label: reviewer })
  return true
}
async function docMergeAgent(runDir, round, reviewerSet) {
  await cmdRunner(
    `python3 plugins/superheroes/lib/front_half.py merge --run-dir ${shq(runDir)} ` +
    `--round ${shq(String(round))} --roster ${shq((reviewerSet || []).join(','))}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, merged: {} } } })
  return { runDir, round }   // merged.json on disk is what the synthesis leaf + tally read
}
async function docSynthesisLeaf(merged, context, rubric, runDir, round) {
  await agent(
    `You are the panel synthesis judge for round ${round} of the ${context.docType} doc review. ` +
    `Read the merged findings at ${runDir}/round-${round}/merged.json and the doc at ${context.docPath}; ` +
    `per the synthesis-leaf prompt (plugins/superheroes/eval/synthesis-leaf.md) emit one ` +
    `keep/drop/severity verdict per merged finding (keep-on-uncertain) and write the JSON array to ` +
    `${runDir}/round-${round}/synthesis.json.`,
    { label: `synthesis:r${round}` })
  return { runDir, round }
}
async function docRecordDeferred(report, _verdict, runDir) {
  // fix-report.json is a transient hand-off read by record-deferred immediately below; per-round
  // overwrite is harmless (it is consumed before the next round writes it).
  require('fs').writeFileSync(`${runDir}/fix-report.json`, JSON.stringify(report || {}))
  await cmdRunner(
    `python3 plugins/superheroes/lib/front_half.py record-deferred --run-dir ${shq(runDir)} ` +
    `--report ${shq(runDir + '/fix-report.json')}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, deferred: {} } } })
}

// the doc-reviser fixStep: dispatch the doc-reviser leaf; return the resolved/deferred report
// (with extras.parentOrigin for a parent-traced / GATE finding), or null on failure (#104 -> halted).
async function docReviser(blockers, runDir, context) {
  const out = await agent(
    `You are the doc-reviser (fixStep) for the ${context.docType} doc at ${context.docPath}. ` +
    `Per plugins/superheroes/eval/doc-reviser-leaf.md, resolve these blocking findings with targeted ` +
    `revisions: ${JSON.stringify(blockers)}. Leave a parent-traced or GATE finding unresolved and ` +
    `name it in extras.parentOrigin. Return ONLY the report JSON ` +
    `{fixes, deferred:[{identity,severity}], extras:{parentOrigin?}}.`,
    { label: 'doc-reviser',
      schema: { type: 'object', properties: { fixes: { type: 'array' }, deferred: { type: 'array' },
                extras: { type: 'object' } } } })
  return out || null
}

// run the panel-doc leg: set the four global wrappers, then reviewPanel with the front-half wiring.
async function runReviewDocPanel({ workItem, docType, docPath, runDir }) {
  const context = { workItem, docType, docPath }
  global.reviewerAgent = docReviewerAgent
  global.mergeAgent = docMergeAgent
  global.synthesisLeaf = docSynthesisLeaf
  global.recordDeferred = docRecordDeferred
  return reviewPanel({
    reviewerSet: DOC_REVIEWERS, context, rubric: 'review-base', runKey: runDir, runDir,
    fixStep: (blockers, rd) => docReviser(blockers, rd, context),
    maxRounds: 7, legKind: { panel: true, code: false }, verifyCommand: 'none' })
}

module.exports.DOC_REVIEWERS = DOC_REVIEWERS
module.exports.runReviewDocPanel = runReviewDocPanel

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// JS<->Python bridge: run a lib command in a leaf, return its stdout JSON (schema-validated).
async function cmdRunner(cmd, { schema }) {
  return agent(
    `Run exactly this command and return ONLY its stdout JSON, unchanged:\n\n${cmd}`,
    { label: 'lib', schema },
  )
}

const RECONCILE_SCHEMA = {
  type: 'object', required: ['action'],
  properties: { action: { type: 'string' }, from_step: {}, reason: { type: 'string' } },
}

// Reconcile-from-store: the leaf runs a small python that ensures the store, reads the
// checkpoint + a world snapshot, and returns recover.reconcile(...)'s action.
async function reconcile(workItem) {
  return cmdRunner(
    `python3 plugins/superheroes/lib/recover_entry.py --work-item ${shq(workItem)}`,
    { schema: RECONCILE_SCHEMA },
  )
}

async function showrunner({ workItem }) {
  const r = await reconcile(workItem)
  if (r.action === 'park_gate' || r.action === 'gate') {
    return { outcome: 'parked', phase: 'reconcile', reason: r.reason || r.action }
  }
  // UFR-1: refuse to run if the spec hasn't been approved.
  const specGate = await readGate(workItem, 'spec')
  const startup = await phaseStep({ confidence: 'high', assumptions: [] }, specGate)
  if (startup.action !== 'proceed') {
    return { outcome: 'parked', phase: 'startup', reason: startup.reason }
  }
  // 'continue' (from_step) or 'world_derive' (from_step 0) -> run the phase loop (Task 8).
  // lastGoodStep = the last *completed* phase index; resume at the next one (no re-run, FR-3).
  const fromStep = r.action === 'continue' && r.from_step != null ? Number(r.from_step) + 1 : 0
  return runPhases(workItem, fromStep, { gateRead: gateReadFor(workItem) })
}

const READGATE_SCHEMA = { type: 'object', required: ['review'], properties: { review: { type: 'string' } } }

async function readGate(workItem, doc) {
  // A failed read-gate (missing/malformed doc -> non-zero exit + empty stdout, so cmdRunner can't
  // produce a valid object) must PARK, never crash the run: return an 'unreadable' sentinel that
  // phase_step.decide maps to park_unexpected_gate.
  try {
    const out = await cmdRunner(
      `python3 plugins/superheroes/lib/definition_doc.py read-gate --doc ${shq(doc)} ` +
      `--work-item ${shq(workItem)} --root "$(git rev-parse --show-toplevel)" --json`,
      { schema: READGATE_SCHEMA })
    return (out && out.review) || 'unreadable'
  } catch (e) {
    return 'unreadable'
  }
}

const REVIEWED = new Set(['review-plan', 'review-tasks', 'review-code'])
function gateReadFor(workItem) {
  return async (phase) => {
    if (!REVIEWED.has(phase)) return null            // authoring phase: no review gate
    if (phase === 'review-code') return null          // review-code's gate = the reviewPanel verdict (Task 10)
    const doc = phase === 'review-plan' ? 'plan' : 'tasks'
    return readGate(workItem, doc)
  }
}

const PHASES = ['plan', 'review-plan', 'tasks', 'review-tasks', 'build',
                'review-code', 'draft-PR', 'mark-ready', 'ship']

const DECIDE_SCHEMA = {
  type: 'object', required: ['action'],
  properties: { action: { type: 'string' }, reason: { type: 'string' } },
}

async function phaseStep(phaseResult, gate) {
  const pr = shq(JSON.stringify(phaseResult))
  const g = gate === null || gate === undefined ? '' : ` --gate ${shq(gate)}`
  return cmdRunner(
    `python3 plugins/superheroes/lib/phase_step_cli.py --result ${pr}${g}`,
    { schema: DECIDE_SCHEMA },
  )
}

// returns { ok } — a false ok means journal_entry caught a DurableWriteError (UFR-2).
async function appendPhaseRecord(workItem, phase, gate, phaseResult) {
  const payload = shq(JSON.stringify({ phase, gate,
    confidence: phaseResult.confidence, assumptions: phaseResult.assumptions || [] }))
  return cmdRunner(
    `python3 plugins/superheroes/lib/journal_entry.py --work-item ${shq(workItem)} --payload ${payload}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } },
  )
}

async function runPhases(workItem, fromStep, deps) {
  deps = deps || {}
  for (let i = fromStep; i < PHASES.length; i += 1) {
    const phase = PHASES[i]
    if (phase === 'ship') {                              // terminal: returns {outcome,phase,reason}
      return (deps.ship || shipPhase)(workItem, await loadPr(workItem))
    }
    let phaseResult, gate, sideEffect = null
    if (phase === 'review-code') {
      const r = await (deps.reviewCode || reviewCodePhase)(workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if (phase === 'build') {
      phaseResult = await (deps.build || buildPhase)(workItem); gate = null
    } else if (phase === 'draft-PR') {
      const r = await (deps.draftPR || draftPRPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if (phase === 'mark-ready') {
      const r = await (deps.markReady || markReadyPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else {
      phaseResult = await (deps.phaseLeaf || defaultPhaseLeaf)(phase, workItem)
      gate = await (deps.gateRead || (async () => null))(phase, workItem)
    }
    const rec = await appendPhaseRecord(workItem, phase, gate, phaseResult)
    if (!rec.ok) return { outcome: 'parked', phase, reason: 'durable write failed (DurableWriteError) — UFR-2' }
    const decision = await phaseStep(phaseResult, gate)
    if (decision.action !== 'proceed') return { outcome: 'parked', phase, reason: decision.reason }
    // FR-4/FR-3: persist the side effect + cursor BEFORE advancing. If that durable write fails, park
    // rather than advance — advancing on an unrecorded cursor would lose record-before-advance.
    const cur = await recordCursor(workItem, i, sideEffect)
    if (!cur.ok) return { outcome: 'parked', phase, reason: 'cursor not recorded (durable write failed) — FR-4' }
  }
  // Unreachable in normal operation — the 'ship' phase always returns first. Reaching here means
  // PHASES lacks 'ship' (an invariant violation), so park defensively rather than claim ready.
  return { outcome: 'parked', phase: 'ship', reason: 'phase loop ended without reaching ship (no ship phase?)' }
}

// #86 verdict -> the gate phase_step.decide consumes.
function verdictToGate(verdict) {
  return verdict && verdict.gate === 'clean' ? 'passed' : 'changes-requested'
}

// the review-code phase: run the single-pass panel, return a phase-result + its gate. On a clean
// verdict, record the review provenance (set_review_covers + review_result) the ship-gate reads.
async function reviewCodePhase(workItem) {
  const runDir = `/tmp/showrunner-${workItem}-review-code`
  const verdict = await runReviewCodePanel({
    runDir, context: workItem, rubric: 'review-base',
    reviewerAgent: defaultReviewerAgent, recordDeferred: async () => {},
  })
  const gate = verdictToGate(verdict)
  if (gate === 'passed') {
    // If the review provenance can't be recorded, parking now (low confidence) is correct: advancing
    // would later GATE permanently at the draft-PR ship-gate (no review evidence) with the cursor
    // already past this phase — a dead-end. A low-confidence park lets a resume retry it.
    const prov = await cmdRunner(`python3 plugins/superheroes/lib/prov_entry.py --step review --work-item ${shq(workItem)}`,
      { schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
    if (!prov.ok) {
      return { phaseResult: { confidence: 'low', assumptions: ['review provenance not recorded: ' + (prov.error || 'unknown')] }, gate }
    }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, gate }
}

async function defaultReviewerAgent(reviewer, _context, _rubric, _runDir, _round) {
  // dispatch one review-code reviewer leaf; returns true when it wrote its findings file.
  await agent(`Run the ${reviewer} review for this change and write its findings file.`, { label: reviewer })
  return true
}

// the thin build leaf: create the managed content-addressed worktree+branch (so draft-PR has a
// push target and the back-half reconcile has a branch), then one implementer makes the change.
async function buildPhase(workItem) {
  // build_entry.py: content_hash(approved tasks) -> branch -> buildtree.reclaim_or_create ->
  // record checkpoint.branch. Returns { branch }.
  // build_entry emits {branch} on success or {error} on a fail-closed setup failure — so the schema
  // does NOT require branch; a missing branch parks (low confidence) instead of crashing on setup.branch.
  const setup = await cmdRunner(
    `python3 plugins/superheroes/lib/build_entry.py --work-item ${shq(workItem)}`,
    { schema: { type: 'object', properties: { branch: { type: 'string' }, error: { type: 'string' } } } })
  if (!setup.branch) {
    return { confidence: 'low', assumptions: ['build setup failed: ' + (setup.error || 'no branch returned')] }
  }
  await agent(`Make the trivial throwaway change for ${workItem} on branch ${setup.branch} and commit it.`, { label: 'build' })
  // record build provenance over the shipped HEAD (the ship-gate reads it at draft-PR). If it can't be
  // recorded, park (low confidence) — advancing would dead-end at the ship-gate with no build evidence.
  const prov = await cmdRunner(`python3 plugins/superheroes/lib/prov_entry.py --step build --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
  if (!prov.ok) {
    return { confidence: 'low', assumptions: ['build provenance not recorded: ' + (prov.error || 'unknown')] }
  }
  return { confidence: 'high', assumptions: [] }
}

module.exports.verdictToGate = verdictToGate
module.exports.reviewCodePhase = reviewCodePhase
module.exports.buildPhase = buildPhase

const CKPT_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, pr: {} } }

// recordCursor writes lastGoodStep (+ any side effect: { pr } or { ready }) BEFORE the loop
// advances — so a crash resumes after this phase and never repeats an irreversible action (FR-4).
async function recordCursor(workItem, step, sideEffect) {
  const extra = sideEffect ? ` --json ${shq(JSON.stringify(sideEffect))}` : ''
  return cmdRunner(
    `python3 plugins/superheroes/lib/checkpoint_entry.py --work-item ${shq(workItem)} --step ${shq(String(step))}${extra}`,
    { schema: CKPT_SCHEMA })
}

async function loadPr(workItem) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/checkpoint_entry.py --work-item ${shq(workItem)} --read-pr`,
    { schema: { type: 'object', required: ['pr'], properties: { pr: {} } } })
  return out.pr
}

// draft-PR: pr_entry.py runs recover.pr_action (adopt/create exactly-once) + ship_gate.decide,
// returns { pr: {number,url,isDraft} }. The pr is recorded as the cursor side effect (FR-4).
async function draftPRPhase(workItem) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/pr_entry.py --step draft --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, pr: {}, reason: { type: 'string' } } } })
  if (!out.ok) return { phaseResult: { confidence: 'low', assumptions: [out.reason || 'draft-PR gated'] }, sideEffect: null }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: out.pr } }
}

// mark-ready: pr_entry.py world-reads isDraft (pr_phase.mark_ready_action), flips if needed,
// returns { ready: true }. Idempotent on resume (an already-ready PR -> skip).
async function markReadyPhase(workItem) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/pr_entry.py --step mark-ready --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, reason: { type: 'string' } } } })
  if (!out.ok) return { phaseResult: { confidence: 'low', assumptions: [out.reason || 'mark-ready gated'] }, sideEffect: null }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { ready: true } }
}

module.exports.recordCursor = recordCursor
module.exports.draftPRPhase = draftPRPhase
module.exports.markReadyPhase = markReadyPhase

async function shipPhase(workItem, pr) {
  // freshness.decide -> up_to_date | sync | give_up_notify | gate. For this slice only up_to_date
  // proceeds; the auto-sync of a behind branch is back-half deepening, so sync/give_up_notify/gate
  // all park (FR-11: not merge-ready unless up to date).
  const fresh = await cmdRunner(
    `python3 plugins/superheroes/lib/ship_phase.py --step freshness --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['decision'], properties: { decision: { type: 'string' } } } })
  if (fresh.decision !== 'up_to_date') {
    return park(workItem, pr, `branch not up to date with base (${fresh.decision})`)
  }
  // ship_phase.py --step ci returns 'green' (no failing checks) or a ci_loop.decide value
  // ('fix' | 'revert_and_gate'). The slice does not auto-fix CI, so anything but green parks.
  const ci = await cmdRunner(
    `python3 plugins/superheroes/lib/ship_phase.py --step ci --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['decision'], properties: { decision: { type: 'string' }, reason: { type: 'string' } } } })
  if (ci.decision !== 'green') {
    return park(workItem, pr, ci.reason || 'CI could not be made green')
  }
  return park(workItem, pr, 'merge-ready: CI green and branch up to date — awaiting owner merge', true)
}

// park posts the readout (scrubbed) to the PR; on a failed post it records to the store (UFR-4).
async function park(workItem, pr, reason, mergeReady) {
  const prNum = pr && pr.number ? ` --pr ${shq(String(pr.number))}` : ''
  const rPost = await cmdRunner(
    `python3 plugins/superheroes/lib/readout_post.py --work-item ${shq(workItem)} --reason ${shq(reason)}${prNum}`,
    { schema: { type: 'object', required: ['posted'], properties: { posted: {}, recorded: {}, error: { type: 'string' } } } })
  // UFR-4 detectability: if the readout reached neither the PR nor the store (e.g. a full disk failed
  // both the journal and the store fallback), the owner gets no 'your turn' signal — surface that in
  // the returned reason rather than reporting a clean park.
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered
    ? reason
    : `${reason} [warning: readout could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: mergeReady ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}

module.exports.shipPhase = shipPhase
module.exports.park = park

async function defaultPhaseLeaf(_phase, _workItem) {
  return { confidence: 'high', assumptions: [] }
}

module.exports.showrunner = showrunner
module.exports.cmdRunner = cmdRunner
module.exports.reconcile = reconcile
module.exports.runPhases = runPhases
module.exports.PHASES = PHASES
