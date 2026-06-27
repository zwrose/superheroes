// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (the #86 review_panel_shell.js posture): the script
// forwards decisions; every judgement is a pure Python decider or a #86 shell.
const { reviewPanel } = require('./review_panel_shell.js')
const { testPilotPhase } = require('./test_pilot_phase.js')
const { io, joinPath } = require('./io_seam.js')

// `process` is absent in the Workflow runtime sandbox (only the io seam is injected). Guard the two
// node-only globals the spine touches so a bare `process.*` reference can't crash the live run: under
// node (smokes) these forward to the real process; under the bundle they degrade safely ('.' / undefined,
// so the bundle's globalThis.SUPERHEROES_BUNDLE_FULL_RUN drives full-run, not the env selector).
function procCwd() { return (typeof process !== 'undefined' && process.cwd) ? process.cwd() : '.' }
function procEnv(name) { return (typeof process !== 'undefined' && process.env) ? process.env[name] : undefined }

const REVIEW_CODE_REVIEWERS = [
  'architecture-reviewer', 'code-reviewer', 'security-reviewer',
  'test-reviewer', 'premortem-reviewer',
]

const REVIEW_DEEP = new Set(['security-reviewer', 'architecture-reviewer'])
const ADVANCE_TERMINALS = new Set(['clean', 'clean-with-skips'])

const FIX_REPORT_SCHEMA = {
  type: 'object',
  properties: { fixed: { type: 'array' }, deferred: { type: 'array' } },
}
const CONFIG_SCHEMA = {
  type: 'object', required: ['verifyCommand'],
  properties: { verifyCommand: { type: 'string' }, tiers: { type: 'object' } },
}
const PROV_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } }
const OK_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {} } }
const RECORD_DEFERRED_SCHEMA = { type: 'object', required: ['ok'],
  properties: { ok: {}, extras: {}, parentOrigin: {}, deferred: {} } }   // extras rides onto report.extras

// Build the five caller-supplied leaf wrappers, closed over the resolved model tiers (FR-7/FR-8).
function reviewCodeLeaves(tiers, opts) {
  opts = opts || {}
  const withModel = (model, opts) => (model ? Object.assign({ model }, opts) : opts)
  const target = opts.target || {}
  const targetSuffix = target.worktree || target.head
    ? `\n\nTarget worktree: ${target.worktree || procCwd()}\nExpected head: ${target.head || 'current HEAD'}`
    : ''

  const reviewerAgent = async (reviewer, context, rubric, runDir, round) => {
    const model = REVIEW_DEEP.has(reviewer) ? tiers.reviewerDeep : tiers.reviewer
    await agent(
      `You are the ${reviewer}. Review the built change for work-item ${context} against the ` +
      `${rubric} rubric, and write your findings array to ` +
      `${runDir}/round-${round}/findings-${reviewer}.json ([] if nothing to flag).${targetSuffix}`,
      withModel(model, { label: `${reviewer}:r${round}` }))
    return true
  }

  const mergeAgent = async (runDir, round, reviewerSet) => {
    await agent(
      `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
      `python3 plugins/superheroes/lib/merge_findings.py --run-dir ${shq(runDir)} ` +
      `--round ${shq(String(round))} --roster ${shq(reviewerSet.join(','))}`,
      { label: `merge:r${round}` })
    return true
  }

  const synthesisLeaf = async (merged, context, rubric, runDir, round) => {
    await agent(
      `You are the panel synthesis judge (eval/synthesis-leaf.md). For EACH merged finding in ` +
      `${runDir}/round-${round}/merged.json decide keep/drop + the rubric-justified severity ` +
      `(keep-on-uncertain; never decide the loop terminal). Write the verdict array to ` +
      `${runDir}/round-${round}/synthesis.json.`,
      withModel(tiers.synthesis, { label: `synthesis:r${round}` }))
    return true
  }

  // the code-fixer (fixStep): attempt every blocking finding, commit fixes, tag upstream-traced blockers.
  const fixStep = async (blockers, runDir) => {
    const out = await agent(
      `You are the code-fixer. For each blocking finding below, attempt a real fix and COMMIT it to ` +
      `the change under review. If a finding traces to an upstream phase (plan, tasks, or build) rather ` +
      `than the code under review, leave it unresolved and tag its originating phase. Never edit the ` +
      `review-loop machinery (refused edits surface as findings, not applied). Return ONLY a JSON object ` +
      `{"fixed": [<titles>], "deferred": [{"id", "severity", "parentOrigin"?}]}.\n\n` +
      `Blocking findings:\n${JSON.stringify(blockers)}${targetSuffix}`,
      withModel(tiers.fixer, { label: 'code-fixer', schema: FIX_REPORT_SCHEMA }))
    return out || null   // null report => the shell treats it as a fix failure -> the core decides halted
  }

  const recordDeferred = async (report, _verdict, runDir) => {
    const out = await cmdRunner(
      `python3 plugins/superheroes/lib/record_deferred.py --run-dir ${shq(runDir)} ` +
      `--report ${shq(JSON.stringify(report || {}))}`,
      { schema: RECORD_DEFERRED_SCHEMA })
    // Attach the computed readout-enrichment extras (fixes + accumulated parentOrigin) to the fix
    // report so #104's shared shell threads it (report.extras -> tally -> readout). FR-6.
    if (out && out.extras && report && typeof report === 'object') report.extras = out.extras
  }

  return { reviewerAgent, mergeAgent, synthesisLeaf, fixStep, recordDeferred }
}

// Drive the shared loop with the code-review configuration + leaves (FR-1..FR-5, FR-7, FR-8).
async function runReviewCodePanel({ runDir, context, rubric, verifyCommand, leaves, worktree }) {
  global.reviewerAgent = leaves.reviewerAgent
  global.mergeAgent = leaves.mergeAgent
  global.synthesisLeaf = leaves.synthesisLeaf
  global.recordDeferred = leaves.recordDeferred
  return withTargetCommandPrompts(worktree, () => reviewPanel({
    reviewerSet: REVIEW_CODE_REVIEWERS,
    context, rubric, runKey: runDir, runDir,
    fixStep: leaves.fixStep,
    maxRounds: 7,
    legKind: { panel: true, code: true },
    verifyCommand,
  }))
}

module.exports = { REVIEW_CODE_REVIEWERS }

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
  await io().writeFile(`${runDir}/fix-report.json`, JSON.stringify(report || {}))
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

function docPathFor(workItem, doc) { return `docs/superheroes/${workItem}/${doc}.md` }
function runDirFor(workItem, phase) { return `/tmp/showrunner-${workItem}-${phase}` }

// the produce phase: author the doc author-only (resume a usable draft; re-produce otherwise).
async function producePhase(phase, workItem) {
  const doc = phase                                    // 'plan' | 'tasks'
  // resume vs re-produce: a usable draft (content-bound completion signal + complete content) is kept.
  const draft = await usableDraft(workItem, doc)
  if (draft.usable) return { confidence: 'high', assumptions: [] } // FR-8 resume — do not re-author
  const authored = await agent(
    `You are the author-only produce leaf (plugins/superheroes/eval/produce-leaf.md). Author the ` +
    `${doc} definition-doc for work-item ${workItem} from its approved parent, every section ` +
    `non-empty, no placeholder. Do NOT run review or record the review gate. Return ` +
    `{ status, notify } where notify is an array of any NOTIFY-class defaults you took, each ` +
    `{ identity, message }.`,
    { label: `produce-${doc}`, model: await authorModel(),
      schema: { type: 'object', properties: { status: {}, notify: { type: 'array' } } } })
  if (authored == null) {
    return { confidence: 'low', assumptions: [`produce step failed for ${doc}`] } // UFR-4
  }
  // surface any produce-phase NOTIFY default in the durable ledger the boundary reads (UFR-2): a
  // produce phase has no #104 loop record to ride, so it is named via the ledger, not the extras seam.
  if (authored.notify && authored.notify.length) {
    const ok = await appendNotify(workItem, authored.notify.map(
      (n) => ({ phase: doc, identity: n && n.identity, message: n && n.message })))
    if (!ok) {
      // a NOTIFY default that can't be durably recorded must NOT be silently lost (UFR-2): park and
      // name it. No marker is stamped yet, so a resume re-produces and retries the NOTIFY.
      return { confidence: 'low', assumptions: ['produce NOTIFY default not durably recorded: ' +
               authored.notify.map((n) => (n && n.message) || '').join('; ')] }
    }
  }
  // stamp the content-bound completion signal deterministically (engine, not the LLM) — the body hash,
  // so a crash before this leaves the marker absent/stale and the next entry re-produces (UFR-4).
  await cmdRunner(
    `python3 plugins/superheroes/lib/front_half_usable.py --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`,
    { schema: { type: 'object', properties: { wrote: {} } } })
  const after = await usableDraft(workItem, doc)
  if (!after.usable) return { confidence: 'low', assumptions: [`produce step yielded no usable ${doc} draft`] } // UFR-4
  return { confidence: 'high', assumptions: [] }
}

// the review phase: idempotent passed-gate skip, else run the panel-doc leg and map terminal->gate.
async function reviewDocPhase(doc, workItem) {
  const existing = await readGate(workItem, doc)
  if (existing === 'passed') {
    // cursor-lost re-entry guard (gate written, recordCursor failed): never re-run the panel and
    // risk overwriting a correct passed (FR-8 passed-gate skip).
    return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' }
  }
  const runDir = runDirFor(workItem, `review-${doc}`)
  const verdict = await runReviewDocPanel({ workItem, docType: doc, docPath: docPathFor(workItem, doc), runDir })
  // persist the #104 terminal record so the front-half boundary can embed its readout (FR-7).
  try { await io().writeFile(`${runDir}/terminal-record.json`, JSON.stringify(verdict || {})) } catch (_) {}
  const gate = await gateForTerminal(verdict && verdict.terminal)
  const sg = await cmdRunner(
    `python3 plugins/superheroes/lib/definition_doc.py set-gate --doc ${shq(doc)} ` +
    `--work-item ${shq(workItem)} --review ${shq(gate)} --root "$(git rev-parse --show-toplevel)"`,
    { schema: { type: 'object', properties: { review: {}, status: {} } } })
  if (!sg || sg.review !== gate) {
    // a failed durable gate write must NOT advance on un-recorded state (UFR-5) — park low-confidence,
    // mirroring reviewCodePhase's provenance-write guard.
    return { phaseResult: { confidence: 'low', assumptions: [`gate write did not record for ${doc}`] }, gate }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, gate }
}

// thin front_half.py / registry decider bridges.
async function gateForTerminal(terminal) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/front_half.py gate-for-terminal --terminal ${shq(terminal || 'unknown')}`,
    { schema: { type: 'object', required: ['gate'], properties: { gate: { type: 'string' } } } })
  return (out && out.gate) || 'changes-requested'
}
async function usableDraft(workItem, doc) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/front_half_usable.py --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --root "$(git rev-parse --show-toplevel)"`,
    { schema: { type: 'object', required: ['usable'], properties: { usable: {} } } })
  return { usable: !!(out && out.usable) }
}
async function authorModel() {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/model_tier_resolve.py --role author`,
    { schema: { type: 'object', properties: { model: {} } } })
  return (out && out.model) || undefined
}
// the durable per-work-item NOTIFY ledger (under the gitignored docs dir — run-local state).
function notifyLedgerFor(workItem) { return `docs/superheroes/${workItem}/.notify.json` }
async function appendNotify(workItem, entries) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/front_half.py append-notify ` +
    `--ledger ${shq(notifyLedgerFor(workItem))} --entries ${shq(JSON.stringify(entries || []))}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {} } } })
  return !!(out && out.ok)   // false on a failed durable write — the caller must not silently lose it
}

module.exports.producePhase = producePhase
module.exports.reviewDocPhase = reviewDocPhase
module.exports.notifyLedgerFor = notifyLedgerFor

// FR-7: compose the front-half run-outcome envelope (embedding each phase's #104 readout via
// front_half render-outcome) and return a parked result. Reads best-effort per-phase terminal records
// + the durable NOTIFY ledger; render_run_outcome tolerates missing records.
async function frontHalfBoundary(workItem) {
  // The io() seam is async (it shares one contract with the bundle's Promise-returning leaf-bash io),
  // so await every read BEFORE building the outcome literal — embedding an un-awaited Promise would
  // serialize as "{}" and silently drop the durable readout records (the bug this fix class closes).
  const notify = await io().readJson(notifyLedgerFor(workItem), [])
  const planRec = await io().readJson(`${runDirFor(workItem, 'review-plan')}/terminal-record.json`, null)
  const tasksRec = await io().readJson(`${runDirFor(workItem, 'review-tasks')}/terminal-record.json`, null)
  const outcome = {
    completed_phases: ['plan', 'review-plan', 'tasks', 'review-tasks'],
    docs: { plan: docPathFor(workItem, 'plan'), tasks: docPathFor(workItem, 'tasks') },
    notify,
    phase_records: [
      { phase: 'review-plan', record: planRec },
      { phase: 'review-tasks', record: tasksRec },
    ],
    readout_record_ok: true,
  }
  const outPath = `/tmp/showrunner-${workItem}-fronthalf-outcome.json`
  let recordOk = true
  try { await io().writeFile(outPath, JSON.stringify(outcome)) } catch (_) { recordOk = false }
  // render-outcome prints TEXT (not JSON); call the leaf directly (no cmdRunner schema). If the
  // outcome record could not be written, render has nothing to read -> flag UFR-6 in the reason.
  const rendered = recordOk
    ? await agent(
        `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
        `python3 plugins/superheroes/lib/front_half.py render-outcome --outcome ${shq(outPath)}`,
        { label: 'lib' })
    : null
  const reason = (typeof rendered === 'string' && rendered.trim())
    ? rendered
    : recordOk
      ? 'front-half complete: plan and tasks gated — parked at the front-half boundary, awaiting owner'
      : '⚠️ front-half complete (plan and tasks gated) but the run-outcome record could not be written ' +
        '— treat the durable readout as missing (UFR-6); awaiting owner'
  return { outcome: 'parked', phase: 'front-half-boundary', reason }
}

module.exports.frontHalfBoundary = frontHalfBoundary

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function safeRunKey(s) { return String(s).replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 120) || 'target' }
function inWorktree(cmd, worktree) {
  return worktree ? `cd ${shq(worktree)} && ${cmd}` : cmd
}
function targetCommandPrompt(prompt, worktree) {
  if (!worktree || typeof prompt !== 'string') return prompt
  if (!prompt.startsWith('Run exactly this')) return prompt
  // The cmdRunner shape is "Run exactly this …:\n\n<cmd>"; split on the FIRST blank-line boundary
  // so a multi-line command (which may itself contain a blank line) is wrapped whole, not just its tail.
  const idx = prompt.indexOf('\n\n')
  if (idx < 0) return prompt
  const prefix = prompt.slice(0, idx + 2)
  const cmd = prompt.slice(idx + 2)
  if (!cmd.trim() || cmd.trim().startsWith('cd ')) return prompt
  return `${prefix}${inWorktree(cmd, worktree)}`
}
async function withTargetCommandPrompts(worktree, fn) {
  if (!worktree) return fn()
  const originalAgent = global.agent
  global.agent = async (prompt, opts) => originalAgent(targetCommandPrompt(prompt, worktree), opts)
  try {
    return await fn()
  } finally {
    global.agent = originalAgent
  }
}

// JS<->Python bridge: run a lib command in a leaf, return its stdout JSON (schema-validated).
async function cmdRunner(cmd, { schema }) {
  // The command prints ONE JSON object to stdout. The leaf must map each top-level key of that
  // object to the SAME-named StructuredOutput field — NOT stuff the whole JSON text into one field
  // (a live-only derailment: that is schema-valid-but-wrong, e.g. action="{...the whole blob...}",
  // which then mis-routes the deciders). Spell the mapping out so the leaf can't collapse it.
  return agent(
    `Use the Bash tool to run exactly this command. It prints ONE JSON object to stdout. Return that ` +
    `object via StructuredOutput by copying each of its top-level keys to the same-named output field, ` +
    `values exactly as printed. Do NOT put the whole JSON into a single field, do NOT stringify or nest ` +
    `it, and do NOT add commentary or extra fields:\n\n${cmd}`,
    { label: 'lib', schema },
  )
}

const RECONCILE_SCHEMA = {
  type: 'object', required: ['action'],
  properties: { action: { type: 'string' }, from_step: {}, reason: { type: 'string' },
    generation: {} },   // UFR-10: the lease generation recover_entry acquired, threaded to the build
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
  // UFR-10 (#107): thread the lease generation recover_entry acquired into the workhorse build phase,
  // so the build can fence (renew-then-fence) at every branch-mutating boundary.
  const deps = { gateRead: gateReadFor(workItem), generation: r.generation }
  // FR-7 (#108)/FR-4 (#102): native front-half wiring. Two opt-in selectors share the native
  // authoring deps but differ on the boundary park: env SUPERHEROES_FRONT_HALF=native keeps the
  // front-half-only boundary (parks at workhorse); the bundle's SUPERHEROES_BUNDLE_FULL_RUN runs
  // the full live run (no boundary -> proceeds into the back-half).
  const fullRun = !!globalThis.SUPERHEROES_BUNDLE_FULL_RUN   // set by the bundle preamble (Task 4)
  if (procEnv('SUPERHEROES_FRONT_HALF') === 'native' || fullRun) {
    deps.produce = producePhase                  // plan / tasks authoring (author-only)
    deps.reviewDoc = reviewDocPhase              // review-plan / review-tasks -> panel-doc leg
    if (!fullRun) deps.frontHalfBoundary = frontHalfBoundary   // front-half-only keeps the boundary park
  }
  return runPhases(workItem, fromStep, deps)
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

const PHASES = ['plan', 'review-plan', 'tasks', 'review-tasks', 'workhorse',
                'review-code', 'draft-PR', 'test-pilot', 'mark-ready', 'ship']

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

async function defaultTestPilotPhase(workItem, generation) {
  return testPilotPhase(workItem, generation, testPilotDeps(workItem, generation))
}

function testPilotDeps(workItem, generation) {
  const runDir = joinPath(io().tmpdir(), `showrunner-${workItem}-test-pilot`)
  // writeJson is async (the io() seam is async — see io_seam.js) and lazily ensures runDir, so every
  // call site must await it. Lazy mkdirp keeps the dir-create on the same awaited path as the write.
  const writeJson = async (name, value) => {
    const p = joinPath(runDir, `${name}.json`)
    await io().mkdirp(runDir)
    await io().writeFile(p, JSON.stringify(value || {}))
    return p
  }
  const jsonCommand = (cmd, schema) => cmdRunner(cmd, { schema: schema || { type: 'object' } })
  const cli = (cmd, schema) => jsonCommand(cmd, schema || { type: 'object' })
  const keyFor = (branch) => encodeURIComponent(branch || workItem).replace(/~/g, '%7E')

  return {
    resolveContext: async () => cli(
      `python3 plugins/superheroes/lib/test_pilot_context_cli.py resolve ` +
      `--work-item ${shq(workItem)}${generation != null ? ` --generation ${shq(String(generation))}` : ''}`,
      { type: 'object' }),

    decideApplicability: async (context) => {
      const diff = await writeJson('applicability-diff', context.diff || {})
      const detectors = await writeJson('applicability-detectors', context.detectors || {})
      const profile = await writeJson('applicability-profile', context.profile || {})
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_applicability_cli.py decide ` +
        `--diff-json ${shq(diff)} --detectors-json ${shq(detectors)} --profile-json ${shq(profile)}`,
        { type: 'object', required: ['verdict'] })
    },

    derivePlan: async (context) => agent(
      `You are the test-pilot plan leaf for work-item ${workItem}. Derive a browser test plan for ` +
      `the current branch head ${context.head}. Return ONLY JSON ` +
      `{"records":[{"branch":${JSON.stringify(context.branch)},"steps":[{"id","instruction","expected","scenarioIds":[]}]}],` +
      `"coverageRationale":"..."}. Use concise stable step ids; include scenarioIds when seed scenarios are needed.`,
      { label: 'test-pilot-plan', schema: { type: 'object', required: ['records'], properties: { records: { type: 'array' } } } }),

    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records || [] }),

    prepareArtifacts: async ({ plan, records, context }) => {
      const pr = context.pr && context.pr.number
      if (!pr) return { action: 'park', reason: 'test-pilot artifacts require a draft PR number' }
      const planPath = await writeJson('plan-artifact', { key: keyFor(context.branch), records })
      const resultsPath = await writeJson('results-artifact-initial', { key: keyFor(context.branch), records: [], coverageRationale: plan.coverageRationale })
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_artifacts_cli.py ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(context.branch))}`,
        { type: 'object' })
    },

    resolveServer: async (context) => {
      const profile = await writeJson('server-profile', context.profile || {})
      const detection = await writeJson('server-detection', context.detectors || {})
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py resolve ` +
        `--profile-json ${shq(profile)} --detection-json ${shq(detection)} --work-item ${shq(workItem)}`,
        { type: 'object' })
    },

    withManagedServer: async (serverContext, run) => {
      const launchPath = await writeJson('server-launch-context', serverContext)
      const launched = await cli(
        `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py launch ` +
        `--context-json ${shq(launchPath)}`,
        { type: 'object' })
      if (!launched || launched.verdict === 'park' || launched.action === 'park' || launched.ok === false) {
        return launched
      }
      try {
        const outcome = await run(launched)
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', outcome || {})
        return cli(
          `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
      } catch (err) {
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', { action: 'exception', reason: err && err.message ? err.message : String(err) })
        await cli(
          `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
        throw err
      }
    },

    seedRecords: async (records) => {
      const recordsPath = await writeJson('seed-records', records)
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_seed_cli.py prepare --records-json ${shq(recordsPath)}`,
        { type: 'object' })
    },

    runBrowserPass: async (browserContext) => agent(
      `Run the test-pilot browser pass for work-item ${workItem}. Stay within baseUrl/allowedOrigins and return ONLY JSON ` +
      `{"source":"browser","baseUrl":${JSON.stringify(browserContext.baseUrl)},"steps":[{"id","status","notes","browserExecuted":true,"failureType"?,"summary"?}]}. ` +
      `Browser context: ${JSON.stringify(browserContext)}`,
      { label: 'test-pilot-browser', schema: { type: 'object' } }),

    aggregateResults: async (rawResults) => {
      const raw = await writeJson('browser-raw', rawResults)
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_results_cli.py aggregate --raw-json ${shq(raw)}`,
        { type: 'object' })
    },

    budgetCheck: async (_phase, payload) => {
      const counts = await writeJson('budget-counts', payload && payload.counts ? payload.counts : {
        browserPasses: payload && typeof payload.browserPasses === 'number'
          ? payload.browserPasses
          : (payload && payload.rerunScope ? 1 : 0),
        browserFixBatches: payload && payload.fixBatchHistory ? payload.fixBatchHistory.length : 0,
      })
      const out = await cli(
        `python3 plugins/superheroes/lib/test_pilot_budget_cli.py decide --counts-json ${shq(counts)}`,
        { type: 'object' })
      return out.action === 'within_budget' ? { ok: true } : { ok: false, reason: out.reason || 'test-pilot budget exceeded' }
    },

    retryDecide: async (passResult, history, changedFiles, dependencyMap) => {
      const passPath = await writeJson('retry-pass', passResult)
      const histPath = await writeJson('retry-history', history || [])
      const depPath = dependencyMap ? await writeJson('retry-deps', dependencyMap) : null
      const changed = (changedFiles || []).map((f) => ` --changed-file ${shq(f)}`).join('')
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_retry_cli.py decide --pass-json ${shq(passPath)} ` +
        `--history-json ${shq(histPath)}${changed}${depPath ? ` --dependency-json ${shq(depPath)}` : ''}`,
        { type: 'object' })
    },

    dispatchFixBatch: async (failures, details) => agent(
      `Fix the app bugs found by native test-pilot for work-item ${workItem}. Commit fixes locally. ` +
      `Return ONLY JSON {"ok":true,"commitShas":["..."],"changedFiles":["..."],"head":"..."}. ` +
      `Failures: ${JSON.stringify(failures)} Details: ${JSON.stringify(details)}`,
      { label: 'test-pilot-fixer', schema: { type: 'object' } }),

    reviewCode: (wi, opts) => reviewCodePhase(wi, Object.assign({}, opts, {
      runDir: opts.runDir || `/tmp/showrunner-${wi}-review-code-${safeRunKey(opts.runDirSuffix || `${opts.cycle || 1}-${opts.expectedHead || 'head'}`)}`,
    })),

    restoreBaseline: async (records, details) => {
      const recordsPath = await writeJson('restore-records', records)
      const out = await cli(
        `python3 plugins/superheroes/lib/test_pilot_seed_cli.py restore-baseline --records-json ${shq(recordsPath)}`,
        { type: 'object' })
      if (out.action === 'park' || out.ok === false) return out
      return Object.assign({}, out, { baseline: { head: details.head, restored: true, status: out.status } })
    },

    ensureFinalArtifacts: async (payload) => {
      const pr = payload.context.pr && payload.context.pr.number
      if (!pr) return { action: 'park', reason: 'final results artifact requires a PR number' }
      const planPath = await writeJson('final-plan-artifact', { key: keyFor(payload.context.branch), records: payload.records })
      const resultsPath = await writeJson('final-results-artifact', Object.assign({ key: keyFor(payload.context.branch) }, payload.aggregated || {}))
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_artifacts_cli.py ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(payload.context.branch))}`,
        { type: 'object' })
    },

    publishReady: async (_wi, head, payload) => {
      const statusPath = await writeJson('publish-status', {
        branch: payload.context.branch,
        store: payload.context.store,
        generation,
      })
      const storeArg = payload.context.store ? ` --store ${shq(payload.context.store)}` : ''
      const generationArg = generation ? ` --generation ${shq(String(generation))}` : ''
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_publish_cli.py publish --work-item ${shq(workItem)} ` +
        `--head ${shq(head)} --status-json ${shq(statusPath)} --expected-branch ${shq(payload.context.branch)} ` +
        `${storeArg}${generationArg}`,
        { type: 'object' })
    },

    writeStatus: async (status) => {
      const statusPath = await writeJson('status-write', status)
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_status_cli.py write --work-item ${shq(workItem)} --status-json ${shq(statusPath)}`,
        { type: 'object', required: ['ok'] })
    },
  }
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
    // FR-7: the native front-half ends at its boundary — park before entering the back-half
    // (the 'workhorse' build phase, renamed from 'build' in #107), on a FRESH run AND on a RESUME
    // (a resume re-enters at the build cursor, so the boundary must be checked at that phase, not
    // merely after review-tasks).
    if (deps.frontHalfBoundary && phase === 'workhorse') {
      return deps.frontHalfBoundary(workItem)
    }
    if (phase === 'ship') {                              // terminal: returns {outcome,phase,reason}
      return (deps.ship || shipPhase)(workItem, await loadPr(workItem))
    }
    let phaseResult, gate, sideEffect = null
    if (phase === 'review-code') {
      const r = await (deps.reviewCode || reviewCodePhase)(workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if (phase === 'workhorse') {
      phaseResult = await (deps.build || buildPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'draft-PR') {
      const r = await (deps.draftPR || draftPRPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if (phase === 'test-pilot') {
      phaseResult = await (deps.testPilot || defaultTestPilotPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'mark-ready') {
      const r = await (deps.markReady || markReadyPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if ((phase === 'review-plan' || phase === 'review-tasks') && deps.reviewDoc) {
      const doc = phase === 'review-plan' ? 'plan' : 'tasks'
      const r = await deps.reviewDoc(doc, workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if ((phase === 'plan' || phase === 'tasks') && deps.produce) {
      phaseResult = await deps.produce(phase, workItem); gate = null
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
    const cur = await recordCursor(workItem, i, phase, sideEffect)
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

// Render the loop's uniform readout (from its own verdict record, which carries parentOrigin via the
// extras channel) and post it at the park (no PR yet -> readout_post records to the store). FR-6/UFR-1.
async function renderAndPostReadout(workItem, runDir, verdict) {
  const recPath = `${runDir}/terminal-record.json`
  try { await io().writeFile(recPath, JSON.stringify(verdict || {})) } catch (_) {}
  const text = await agent(
    `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/loop_readout.py --record ${shq(recPath)}`,
    { label: 'readout' })
  await cmdRunner(
    `python3 plugins/superheroes/lib/readout_post.py --work-item ${shq(workItem)} --reason ${shq(String(text))}`,
    { schema: { type: 'object', required: ['posted'], properties: { posted: {}, recorded: {}, error: { type: 'string' } } } })
}

// the review-code phase: drive the shared loop, map its terminal to advance/park, stamp covers on a
// pure `clean` (X'), and surface the readout at a park. Returns { phaseResult, gate } for runPhases.
async function reviewCodePhase(workItem, opts) {
  opts = opts || {}
  const runDir = opts.runDir || (opts.runDirSuffix
    ? `/tmp/showrunner-${workItem}-review-code-${safeRunKey(opts.runDirSuffix)}`
    : `/tmp/showrunner-${workItem}-review-code`)
  const initialHead = opts.expectedHead || null
  if (opts.expectedHead) {
    const actual = await resolveHead(opts.worktree || null, opts.ref || 'HEAD')
    if (!actual || actual !== opts.expectedHead) {
      return { phaseResult: { confidence: 'low', assumptions: [`review-code target head mismatch: expected ${opts.expectedHead}, got ${actual || 'unknown'}`] }, gate: 'changes-requested' }
    }
  }
  const targetWorktree = opts.worktree || null
  // premortem-002: the fixer is a freeform subagent that receives the target worktree only as a TEXT
  // hint (withTargetCommandPrompts retargets just the "Run exactly this" cmdRunner prompts). If it
  // commits to the showrunner CWD instead of the target tree, the target HEAD never advances, the
  // expectedHead checks still pass (both = pre-fix HEAD), and a stale `clean` covers-stamp would
  // publish unmodified code. Snapshot CWD HEAD so we can detect that divergence after the loop.
  const cwdHeadBefore = (targetWorktree && opts.expectedHead) ? await resolveHead(null, opts.ref || 'HEAD') : null
  const cfg = await cmdRunner(
    inWorktree(`python3 plugins/superheroes/lib/review_code_config.py --root "$(git rev-parse --show-toplevel)"`, targetWorktree),
    { schema: CONFIG_SCHEMA })
  const leaves = reviewCodeLeaves((cfg && cfg.tiers) || {}, {
    target: { worktree: opts.worktree, head: opts.expectedHead },
  })
  const verdict = await runReviewCodePanel({
    runDir, context: workItem, rubric: 'review-base',
    verifyCommand: (cfg && cfg.verifyCommand) || 'none', leaves, worktree: targetWorktree,
  })
  const terminal = (verdict && verdict.terminal) || 'halted'
  const finalHead = opts.expectedHead
    ? await resolveHead(opts.worktree || null, opts.ref || 'HEAD')
    : null
  if (opts.expectedHead && !finalHead) {
    return { phaseResult: { confidence: 'low', assumptions: ['review-code final target head could not be resolved'] }, gate: 'changes-requested', terminal, head: null, changed: false }
  }
  // #104's advance/park mapping, read off the terminal (plan Key decision 2).
  if (!ADVANCE_TERMINALS.has(terminal)) {
    await renderAndPostReadout(workItem, runDir, verdict)   // names parentOrigin at the review-phase park
    return { phaseResult: { confidence: 'high', assumptions: [`review-code ${terminal}`] }, gate: 'changes-requested', terminal, head: finalHead, changed: !!(initialHead && finalHead && initialHead !== finalHead) }
  }
  // premortem-002 fail-closed: an advancing terminal means we're about to certify the target HEAD. If
  // the CWD advanced while the target HEAD did not, the fixer's commits landed outside the shipped tree
  // — refuse to advance/stamp rather than certify (and ship) code the fixes never touched.
  if (targetWorktree && opts.expectedHead) {
    const cwdHeadAfter = await resolveHead(null, opts.ref || 'HEAD')
    const cwdMoved = cwdHeadBefore && cwdHeadAfter && cwdHeadBefore !== cwdHeadAfter
    const targetMoved = initialHead && finalHead && initialHead !== finalHead
    if (cwdMoved && !targetMoved) {
      return { phaseResult: { confidence: 'low', assumptions: ['review-code fixes landed outside the target worktree (cwd HEAD advanced, target HEAD did not) — refusing to stamp coverage'] }, gate: 'changes-requested', terminal, head: finalHead, changed: false }
    }
  }
  // FR-9: stamp covers = X' ONLY on a pure `clean`; `clean-with-skips` advances with NO stamp and so
  // later parks at the ship gate. prov_entry resolves the build-branch tip (= X' after the fixer's commits).
  if (terminal === 'clean') {
    const targetArgs = opts.worktree || opts.expectedHead
      ? ` --worktree ${shq(opts.worktree || procCwd())}${finalHead ? ` --head ${shq(finalHead)}` : ''}`
      : ''
    const prov = await cmdRunner(
      `python3 plugins/superheroes/lib/prov_entry.py --step review --work-item ${shq(workItem)}${targetArgs}`,
      { schema: PROV_SCHEMA })
    if (!prov.ok) {
      // UFR-2: the covers-stamp write failed -> park (low confidence), do NOT assert ship-ready.
      return { phaseResult: { confidence: 'low', assumptions: ['review covers stamp not recorded: ' + (prov.error || 'unknown')] }, gate: 'changes-requested' }
    }
  }
  return {
    phaseResult: { confidence: 'high', assumptions: [] },
    gate: 'passed',
    terminal,
    head: finalHead,
    changed: !!(initialHead && finalHead && initialHead !== finalHead),
    reviewCoverageHead: terminal === 'clean' ? (finalHead || undefined) : undefined,
    verifyPassedHead: finalHead || undefined,
  }
}

async function resolveHead(worktree, ref) {
  const cmd = worktree
    ? `git -C ${shq(worktree)} rev-parse ${shq(ref || 'HEAD')}`
    : `git rev-parse ${shq(ref || 'HEAD')}`
  try {
    const out = await agent(
      `Run exactly this command and return ONLY its stdout, unchanged:\n\n${cmd}`,
      { label: 'lib' })
    const text = String(out || '').trim()
    return text || null
  } catch (_) {
    return null
  }
}

// the native "workhorse" build phase (#87) — implement the approved tasks doc task-by-task with a
// per-task review + bounded fix loop, one whole-branch final review, and provenance written once.
// All of that orchestration lives in build_phase.js; the spine just delegates, threading the lease
// generation reconcile() acquired so the build can fence every branch-mutating boundary (UFR-10).
const buildPhase = (workItem, generation) => require('./build_phase.js').buildPhase(workItem, generation)

module.exports.verdictToGate = verdictToGate
module.exports.reviewCodePhase = reviewCodePhase
module.exports.runReviewCodePanel = runReviewCodePanel
module.exports.buildPhase = buildPhase

const CKPT_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, pr: {} } }

// recordCursor writes lastGoodStep + lastGoodPhase (+ any side effect: { pr } or { ready }) BEFORE the loop
// advances — so a crash resumes after this phase and never repeats an irreversible action (FR-4).
async function recordCursor(workItem, step, phase, sideEffect) {
  const extra = sideEffect ? ` --json ${shq(JSON.stringify(sideEffect))}` : ''
  return cmdRunner(
    `python3 plugins/superheroes/lib/checkpoint_entry.py --work-item ${shq(workItem)} ` +
    `--step ${shq(String(step))} --phase ${shq(phase)}${extra}`,
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
module.exports.testPilotPhase = testPilotPhase
module.exports.defaultTestPilotPhase = defaultTestPilotPhase
module.exports.testPilotDeps = testPilotDeps

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
  // ship_phase.py --step ci returns 'green' (all required checks pass), 'red' (some check is
  // failing/pending/errored), or 'none' (no required checks gate the PR). green -> merge-ready;
  // red (or any non-green/none) -> park with the reason; none -> merge-ready WITH the
  // no-required-checks carve-out (the owner confirms checks before merging).
  const ci = await cmdRunner(
    `python3 plugins/superheroes/lib/ship_phase.py --step ci --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['decision'], properties: { decision: { type: 'string' }, reason: { type: 'string' } } } })
  if (ci.decision === 'green') {
    return park(workItem, pr, 'merge-ready: CI green and branch up to date — awaiting owner merge', true)
  }
  if (ci.decision === 'none') {
    return park(workItem, pr, 'merge-ready: no required checks gate this PR — confirm checks before merging', true)
  }
  return park(workItem, pr, ci.reason || 'CI could not be made green')
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
