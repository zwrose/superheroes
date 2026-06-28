// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (#86 review_panel_shell.js posture): the script
// forwards decisions; every judgment is a pure JS twin (in-process) or a #86 shell.
// #115 Task 12: front-half spine rewired — reconcile/phaseStep/gateForTerminal/usableDraft/
// authorModel are now in-process JS twin calls; zero decider agents on the front-half.
const { reviewPanel } = require('./review_panel_shell.js')
const { testPilotPhase } = require('./test_pilot_phase.js')
const { io, joinPath } = require('./io_seam.js')
const phaseStepTwin = require('./phase_step.js')
const recoverTwin = require('./recover.js')
const frontHalfTwin = require('./front_half.js')
const modelTierTwin = require('./model_tier.js')
// #115 Task 16: back-half twins — CI status + PR recover (prAction already via recoverTwin above)
const ciStatusTwin = require('./ci_status.js')

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
// #115: the reviewer leaf RETURNS a findings[] array (no findings-<name>.json write); the panel holds
// it in memory and runs the merge/synthesis-consume/tally twins in-process.
const FINDINGS_SCHEMA = { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } }
// the genuine synthesis leaf RETURNS per-finding keep/drop verdicts (loop_synthesis.consume reads them).
const SYNTH_VERDICTS_SCHEMA = { type: 'object', required: ['verdicts'], properties: { verdicts: { type: 'array' } } }

// Build the four caller-supplied leaf wrappers, closed over the resolved model tiers (FR-7/FR-8).
// (#115: mergeAgent is gone — the merge is the in-process panel_tally.compileFindings twin.)
function reviewCodeLeaves(tiers, opts) {
  opts = opts || {}
  const withModel = (model, opts) => (model ? Object.assign({ model }, opts) : opts)
  const target = opts.target || {}
  const targetSuffix = target.worktree || target.head
    ? `\n\nTarget worktree: ${target.worktree || procCwd()}\nExpected head: ${target.head || 'current HEAD'}`
    : ''

  const reviewerAgent = async (reviewer, context, rubric, runDir, round) => {
    const model = REVIEW_DEEP.has(reviewer) ? tiers.reviewerDeep : tiers.reviewer
    const out = await agent(
      `You are the ${reviewer}. Review the built change for work-item ${context} against the ` +
      `${rubric} rubric. Return ONLY a JSON object {"findings":[...]} whose findings array lists each ` +
      `finding ({file, line, title, severity, evidence}); return {"findings":[]} if nothing to flag.${targetSuffix}`,
      withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
    return (out && Array.isArray(out.findings)) ? out.findings : null   // non-array => "did not complete"
  }

  const synthesisLeaf = async (merged, context, rubric, runDir, round) => {
    const out = await agent(
      `You are the panel synthesis judge (eval/synthesis-leaf.md). For EACH merged finding below decide ` +
      `keep/drop + the rubric-justified severity (keep-on-uncertain; never decide the loop terminal). ` +
      `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} — one ` +
      `verdict per merged finding, keyed by its file::normalized-title identity.\n\n` +
      `Merged findings:\n${JSON.stringify(merged)}`,
      withModel(tiers.synthesis, { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA }))
    return (out && Array.isArray(out.verdicts)) ? out.verdicts : []
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
    // #115: write the deferred-set via the cheap exec dumb-pipe (not a genuine agent). record_deferred.py
    // (frozen) appends the deferred identities to deferred-set.json — the channel the in-process tally
    // reads — and prints the readout-enrichment extras (fixes + accumulated parentOrigin) to stdout.
    const out = await exec([
      `python3 plugins/superheroes/lib/record_deferred.py --run-dir ${shq(runDir)} ` +
      `--report ${shq(JSON.stringify(report || {}))}`,
    ])
    // Attach the computed extras to the fix report so #104's shared shell threads it
    // (report.extras -> tally -> readout). FR-6. Parse the cheap pipe's stdout (best-effort).
    let parsed = null
    try { parsed = JSON.parse((out && out[0] && out[0].stdout) || '') } catch (_) {}
    if (parsed && parsed.extras && report && typeof report === 'object') report.extras = parsed.extras
  }

  return { reviewerAgent, synthesisLeaf, fixStep, recordDeferred }
}

// Drive the shared loop with the code-review configuration + leaves (FR-1..FR-5, FR-7, FR-8).
async function runReviewCodePanel({ runDir, context, rubric, verifyCommand, leaves, worktree }) {
  globalThis.reviewerAgent = leaves.reviewerAgent
  globalThis.synthesisLeaf = leaves.synthesisLeaf
  globalThis.recordDeferred = leaves.recordDeferred
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

// the three caller-supplied doc-leg leaf wrappers the #104 shell expects (panel:true). Each is a
// single leaf (no fan-out). Set as globalThis.* before reviewPanel, exactly as runReviewCodePanel does.
// #115: the reviewer RETURNS a findings[] array (the panel holds it in memory); the merge is the
// in-process panel_tally.compileFindings twin (no docMergeAgent / front_half.py merge), and the
// synthesis leaf RETURNS its keep/drop verdicts (loop_synthesis.consume reads them).
async function docReviewerAgent(reviewer, context, rubric, runDir, round) {
  const out = await agent(
    `Run the ${reviewer} review of the ${context.docType} definition-doc at ${context.docPath} ` +
    `against the ${rubric} rubric (reframed to a ${context.docType} doc). Return ONLY a JSON object ` +
    `{"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if none).`,
    { label: reviewer, schema: FINDINGS_SCHEMA })
  return (out && Array.isArray(out.findings)) ? out.findings : null
}
async function docSynthesisLeaf(merged, context, rubric, runDir, round) {
  const out = await agent(
    `You are the panel synthesis judge for round ${round} of the ${context.docType} doc review. ` +
    `For each merged finding below and the doc at ${context.docPath}, per the synthesis-leaf prompt ` +
    `(plugins/superheroes/eval/synthesis-leaf.md) emit one keep/drop/severity verdict (keep-on-uncertain). ` +
    `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} keyed by ` +
    `each finding's file::normalized-title identity.\n\nMerged findings:\n${JSON.stringify(merged)}`,
    { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA })
  return (out && Array.isArray(out.verdicts)) ? out.verdicts : []
}
async function docRecordDeferred(report, _verdict, runDir) {
  // #115: write the deferred-set via the cheap exec dumb-pipe. fix-report.json is a transient hand-off
  // written first, then front_half.py record-deferred (frozen) appends the deferred identities to
  // deferred-set.json — the channel the in-process tally reads. Both run as cheap pipes.
  await io().writeFile(`${runDir}/fix-report.json`, JSON.stringify(report || {}))
  await exec([
    `python3 plugins/superheroes/lib/front_half.py record-deferred --run-dir ${shq(runDir)} ` +
    `--report ${shq(runDir + '/fix-report.json')}`,
  ])
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
  globalThis.reviewerAgent = docReviewerAgent
  globalThis.synthesisLeaf = docSynthesisLeaf
  globalThis.recordDeferred = docRecordDeferred
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
// #115 Task 12: usableDraft uses exec+JS twin (front_half.isUsableDraft, no LLM agent).
// authorModel is the in-process JS twin (model_tier.resolveModel, no agent dispatch).
// The --write-marker stamp is FOLDED into the author agent (FR-4 fold): the author's prompt
// instructs it to run front_half_usable.py --write-marker after authoring the doc, so there is
// no separate cmdRunner call — the author leaf handles its own completion stamp.
async function producePhase(phase, workItem) {
  const doc = phase                                    // 'plan' | 'tasks'
  // resume vs re-produce: a usable draft (content-bound completion signal + complete content) is kept.
  const draft = await usableDraft(workItem, doc)
  if (draft.usable) return { confidence: 'high', assumptions: [] } // FR-8 resume — do not re-author
  const model = authorModel()
  // FR-4 fold: the author leaf writes its own doc + stamps the completion marker (--write-marker) +
  // returns notify. Single-author docs are NOT return-don't-write (the author IS the side effect's input).
  const authored = await agent(
    `You are the author-only produce leaf (plugins/superheroes/eval/produce-leaf.md). Author the ` +
    `${doc} definition-doc for work-item ${workItem} from its approved parent, every section ` +
    `non-empty, no placeholder. After writing the doc, run the following command to stamp the ` +
    `content-bound completion marker (deterministic — do NOT skip it):\n\n` +
    selfContained(`python3 plugins/superheroes/lib/front_half_usable.py --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`) + `\n\n` +
    `Do NOT run review or record the review gate. Return ` +
    `{ status, notify } where notify is an array of any NOTIFY-class defaults you took, each ` +
    `{ identity, message }.`,
    { label: `produce-${doc}`, model,
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
  // Verify the author actually stamped the marker (UFR-4 guard). usableDraft re-reads via exec+twin.
  const after = await usableDraft(workItem, doc)
  if (!after.usable) return { confidence: 'low', assumptions: [`produce step yielded no usable ${doc} draft`] } // UFR-4
  return { confidence: 'high', assumptions: [] }
}

// the review phase: idempotent passed-gate skip, else run the panel-doc leg and map terminal->gate.
// #115 Task 12: gateForTerminal is now the in-process JS twin; the gate write goes through
// persistPhase (one exec: set-gate + journal + checkpoint) — not a cmdRunner agent dispatch.
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
  // gateForTerminal is the in-process JS twin (no agent dispatch).
  const gate = gateForTerminal(verdict && verdict.terminal)
  // Record gate + journal + checkpoint in one exec call (persistPhase, FR-4 persist order).
  const sideEffectCmd =
    `python3 plugins/superheroes/lib/definition_doc.py set-gate --doc ${shq(doc)} ` +
    `--work-item ${shq(workItem)} --review ${shq(gate)} --root "$(git rev-parse --show-toplevel)"`
  const pr = await persistPhase(workItem, {
    sideEffectCmd,
    journalPayload: { phase: `review-${doc}`, gate, confidence: 'high', assumptions: [] },
    step: -1,   // placeholder: the real step is written by recordCursor in runPhases; -1 signals review-doc context
    phase: `review-${doc}`,
  })
  if (!pr.ok) {
    // a failed durable gate write must NOT advance on un-recorded state (UFR-5) — park low-confidence,
    // mirroring reviewCodePhase's provenance-write guard.
    return { phaseResult: { confidence: 'low', assumptions: [`gate write did not record for ${doc}`] }, gate }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, gate }
}

// gateForTerminal: pure in-process JS twin. No agent dispatch.
function gateForTerminal(terminal) {
  return frontHalfTwin.gateForTerminal(terminal || 'unknown')
}

// usableDraft: exec runs front_half_usable.py --emit-signals, which computes the verdict
// Python-side at the IO boundary (calls front_half.is_usable_draft) and returns a small
// {usable, recorded, expected} signal — the large doc text never crosses the cheapest-model
// pipe (live-surfaced large-payload-transport limit). The frontHalfTwin.isUsableDraft JS twin
// stays for parity testing only; it is no longer called here on the live doc text.
async function usableDraft(workItem, doc) {
  const results = await exec([
    `python3 plugins/superheroes/lib/front_half_usable.py --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --root "$(git rev-parse --show-toplevel)" --emit-signals`,
  ])
  let signals = null
  try { signals = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  if (!signals) return { usable: false }   // IO failure -> fail closed (re-produce)
  return { usable: !!signals.usable }
}

// authorModel: pure in-process JS twin. Reads overrides from globalThis.__SR_OVERRIDES (set by
// Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS.author = 'opus').
function authorModel() {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  return modelTierTwin.resolveModel('author', overrides, null)
}
// the durable per-work-item NOTIFY ledger (under the gitignored docs dir — run-local state).
function notifyLedgerFor(workItem) { return `docs/superheroes/${workItem}/.notify.json` }
// appendNotify: IO accumulator write via exec (not cmdRunner). Returns false on failed durable write.
async function appendNotify(workItem, entries) {
  const results = await exec([
    `python3 plugins/superheroes/lib/front_half.py append-notify ` +
    `--ledger ${shq(notifyLedgerFor(workItem))} --entries ${shq(JSON.stringify(entries || []))}`,
  ])
  let out = null
  try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  return !!(out && out.ok)   // false on a failed durable write — the caller must not silently lose it
}

module.exports.producePhase = producePhase
module.exports.reviewDocPhase = reviewDocPhase
module.exports.notifyLedgerFor = notifyLedgerFor

// FR-7: compose the front-half run-outcome envelope (in-process via frontHalfTwin.renderRunOutcome)
// and return a parked result. Reads best-effort per-phase terminal records + the durable NOTIFY ledger.
// The ENVELOPE judgment is in-process (no front_half.py render-outcome agent); only the per-phase
// loop_readout RENDER stays an exec leaf (loop_readout.py --record <path>).
// #115 Task 18: rewired from 1 decider agent to 0 — envelope is the twin, readout stays exec.
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
  // recordOk guards UFR-6: if we cannot write the durable readout records, flag it in the reason.
  // (The readout records live in the per-phase run dirs and are written by renderAndPostReadout earlier;
  // the outcome JSON written here is the durable ENVELOPE artifact — a missing write flags UFR-6.)
  const outPath = `/tmp/showrunner-${workItem}-fronthalf-outcome.json`
  let recordOk = true
  try { await io().writeFile(outPath, JSON.stringify(outcome)) } catch (_) { recordOk = false }

  // exec-backed renderReadout: writes the record to a temp file and execs loop_readout.py --record.
  // Mirrors how renderAndPostReadout runs loop_readout.py (line ~896). Returns the stdout text.
  // Used only when recordOk (the write seam is available); if recordOk is false the loop body is
  // skipped (phase_records still embeds headers with no readout text — tolerable since UFR-6 fires).
  async function renderReadout(record) {
    const recPath = `/tmp/showrunner-${workItem}-fronthalf-readout-tmp.json`
    try { await io().writeFile(recPath, JSON.stringify(record || {})) } catch (_) { return '' }
    const text = await agent(
      `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
      selfContained(`python3 plugins/superheroes/lib/loop_readout.py --record ${shq(recPath)}`),
      { label: 'readout' })
    return typeof text === 'string' ? text : ''
  }

  // In-process envelope composition (no agent for the judgment — only the per-phase readout is exec).
  // If the durable outcome JSON could not be written, skip phase_records embed (no readout seam) and
  // surface UFR-6 in the fallback reason instead; the twin still composes the envelope shell.
  const rendered = recordOk
    ? frontHalfTwin.renderRunOutcome(outcome, renderReadout)
    : frontHalfTwin.renderRunOutcome({ ...outcome, phase_records: [], readout_record_ok: false })

  // rendered is a Promise when renderReadout is async (it is, above) — await it.
  const text = await rendered

  const reason = (typeof text === 'string' && text.trim())
    ? text
    : recordOk
      ? 'front-half complete: plan and tasks gated — parked at the front-half boundary, awaiting owner'
      : '⚠️ front-half complete (plan and tasks gated) but the run-outcome record could not be written ' +
        '— treat the durable readout as missing (UFR-6); awaiting owner'
  return { outcome: 'parked', phase: 'front-half-boundary', reason }
}

module.exports.frontHalfBoundary = frontHalfBoundary

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function safeRunKey(s) { return String(s).replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 120) || 'target' }

// selfContained: FR-5 — prefix a command with `cd <root> && ` so the leaf always runs from the
// correct repo root, regardless of the haiku leaf's cwd. Opt-in: only applies when globalThis.__SR_ROOT
// is set (threaded from args.root in the ENTRY). Commands already starting with `cd ` (e.g. the
// build-worktree inWorktree commands) are left untouched — the startsWith guard prevents double-cd.
// When __SR_ROOT is unset (most smokes, back-half runs not yet opted in) behavior is unchanged.
function selfContained(cmd) {
  var root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return cmd
  var trimmed = String(cmd).trimLeft ? String(cmd).trimLeft() : String(cmd).replace(/^\s+/, '')
  if (trimmed.startsWith('cd ')) return cmd   // already rooted (inWorktree or similar) — leave alone
  return 'cd ' + shq(root) + ' && ' + cmd
}

// cheapestModel: resolves the mechanical (cheapest) tier once and caches it. The `mechanical` tier
// is unconditionally `'haiku'` per DEFAULT_TIERS; resolving through model_tier.js keeps the twin
// parity contract intact and allows future overrides without changing the spine.
let _cheapestModelCache = null
function cheapestModel() {
  if (_cheapestModelCache === null) {
    _cheapestModelCache = require('./model_tier.js').DEFAULT_TIERS.mechanical
  }
  return _cheapestModelCache
}

// _parseExecResult: parse the leaf agent's response into a [{index,ok,stdout}] array.
// Handles all response shapes the leaf may produce:
//   1. Array (stub/pass-through) — returned as-is.
//   2. String — robust extraction tried in order:
//      (a) First fenced block ANYWHERE in the string (non-anchored match for prose-prefixed output).
//      (b) Whole trimmed string as-is (covers clean bare JSON array).
//      For each candidate, try JSON.parse directly; if that fails, slice from first '[' to last ']'
//      and JSON.parse that slice (handles prose before/after a bare JSON array).
//      The first candidate that yields an Array is returned.
//   3. Anything else / all candidates fail — synthetic per-command failure array (fail-closed).
// n = commands.length; used only for synthetic failure array sizing (must be >= 1).
function _parseExecResult(out, n) {
  var count = (n && n > 0) ? n : 1
  if (Array.isArray(out)) return out
  if (typeof out === 'string') {
    var trimmed = out.trim()
    // Build candidates to try, in priority order:
    // (a) content of the FIRST fenced block found anywhere (handles prose-prefixed fences).
    var candidates = []
    var fenceMatch = trimmed.match(/```(?:[a-zA-Z0-9]+)?\s*([\s\S]*?)```/)
    if (fenceMatch) candidates.push(fenceMatch[1].trim())
    // (b) whole trimmed string (handles clean bare JSON or prose-around-JSON via bracket slice).
    candidates.push(trimmed)
    for (var ci = 0; ci < candidates.length; ci++) {
      var candidate = candidates[ci]
      // Try direct parse first.
      try {
        var parsed = JSON.parse(candidate)
        if (Array.isArray(parsed)) return parsed
      } catch (_e1) { /* try bracket-slice fallback */ }
      // Slice from first '[' to last ']' to handle prose around a bare JSON array.
      var firstBracket = candidate.indexOf('[')
      var lastBracket = candidate.lastIndexOf(']')
      if (firstBracket >= 0 && lastBracket > firstBracket) {
        var slice = candidate.slice(firstBracket, lastBracket + 1)
        try {
          var sliced = JSON.parse(slice)
          if (Array.isArray(sliced)) return sliced
        } catch (_e2) { /* try next candidate */ }
      }
    }
  }
  // Synthetic per-command failure: callers can detect the failure and surface it clearly.
  var failures = []
  for (var i = 0; i < count; i++) {
    failures.push({ index: i, ok: false, stdout: 'exec: could not parse leaf result' })
  }
  return failures
}

// exec: the dumb-pipe executor. Dispatches ONE globalThis.agent whose prompt lists all fully-formed
// commands and asks the leaf to run each and return a JSON array of {index, ok, stdout}.
// The model is UNCONDITIONALLY forced to cheapestModel() — overriding __SR_LEAF_MODEL or any
// caller-supplied opts.model. This is a side-effect executor, not a genuine-LLM agent.
// FR-8 sandbox-safe: no fs, no child_process, no time/random globals, no process/bare-global refs.
async function exec(commands, opts) {
  var cmds = commands || []
  const cmdList = cmds.map(function(c, i) { return (i + 1) + '. ' + selfContained(c) }).join('\n')
  const prompt =
    'Run each of the following commands in order using the Bash tool. ' +
    'Return ONLY a raw JSON array and NOTHING else — no prose, no explanation, no markdown fences; ' +
    'your entire response must be valid for JSON.parse. ' +
    'Each element: {"index":<0-based>,"ok":<true|false>,"stdout":<string>}.\n\n' +
    cmdList
  const o = Object.assign({}, opts || {}, { model: cheapestModel(), label: 'exec' })
  const out = await globalThis.agent(prompt, o)
  return _parseExecResult(out, cmds.length)
}

// persistPhase: batches side-effect -> journal_entry -> checkpoint_entry into one exec call.
// Persist order (FR-4): side-effect first (when present), then journal, then checkpoint (cursor last).
// Every interpolated non-constant arg is shq()-quoted.
// Returns {ok: boolean} — ok is false if any command in the batch reported failure.
async function persistPhase(workItem, opts) {
  opts = opts || {}
  const sideEffectCmd = opts.sideEffectCmd || null
  const journalPayload = opts.journalPayload || {}
  const step = opts.step
  const phase = opts.phase

  const journalCmd =
    'python3 plugins/superheroes/lib/journal_entry.py ' +
    '--work-item ' + shq(workItem) + ' ' +
    '--payload ' + shq(JSON.stringify(journalPayload))

  const checkpointCmd =
    'python3 plugins/superheroes/lib/checkpoint_entry.py ' +
    '--work-item ' + shq(workItem) + ' ' +
    '--step ' + shq(String(step)) + ' ' +
    '--phase ' + shq(phase)

  const commands = sideEffectCmd
    ? [sideEffectCmd, journalCmd, checkpointCmd]
    : [journalCmd, checkpointCmd]

  const results = await exec(commands)
  return { ok: results.every(function(r) { return r && r.ok }) }
}

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
  const originalAgent = globalThis.agent
  globalThis.agent = async (prompt, opts) => originalAgent(targetCommandPrompt(prompt, worktree), opts)
  try {
    return await fn()
  } finally {
    globalThis.agent = originalAgent
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

// Reconcile-from-store: exec gathers the world snapshot via recover_entry.py --snapshot
// (IO: store, enforcer, lease, checkpoint, world read), then the JS twin decides (pure, in-process).
// generation is threaded from the Python snapshot (UFR-10).
async function reconcile(workItem) {
  const results = await exec([
    `python3 plugins/superheroes/lib/recover_entry.py --work-item ${shq(workItem)} --snapshot`,
  ])
  let snap = null
  try { snap = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  if (!snap) {
    // A failed/empty snapshot (IO error, store unusable before lease) -> fail closed.
    return { action: 'park_gate', reason: 'recover_entry snapshot failed (IO error)', generation: null }
  }
  // recover_entry emits an early_park when the cursor guard triggers (before snapshot).
  // In that case the snapshot fields are absent and {action, reason, generation} come directly.
  if (snap.action) return snap   // early park (cursor_gate or store/enforcer/lease failure)
  const decision = recoverTwin.reconcile(snap.checkpoint, snap.world)
  return Object.assign({}, decision, { generation: snap.generation })
}

async function showrunner({ workItem }) {
  // Progress-group the pre-loop leaves (reconcile / spec-gate / startup) under 'startup'; runPhases
  // re-stamps this per phase. Read by the bundle's agent wrapper (globalThis.__SR_PHASE).
  if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = 'startup'
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
  // Task 17: load model-tier overrides once at startup from the review-crew profile. The Python script
  // returns a {role:model} JSON map (or {} when the profile is absent/unreadable — the safe degenerate
  // path). We pass no --profile here (→ load_overrides(None) → {}); a throwaway run has no profile, so
  // {} is correct there; production uses the session-wide profile read elsewhere. Fail-safe: any exec
  // error or bad JSON yields {} so resolveModel falls back to DEFAULT_TIERS — startup never crashes.
  const _ovRes = await exec(['python3 plugins/superheroes/lib/model_tier_overrides.py'])
  let _ovMap = {}
  try { const _p = (_ovRes[0] && _ovRes[0].stdout) || ''; _ovMap = JSON.parse(_p) } catch (_) {}
  if (typeof globalThis !== 'undefined') {
    globalThis.__SR_OVERRIDES = (_ovMap && typeof _ovMap === 'object' && !Array.isArray(_ovMap)) ? _ovMap : {}
  }
  // 'continue' (from_step) or 'world_derive' (from_step 0) -> run the phase loop (Task 8).
  // lastGoodStep = the last *completed* phase index; resume at the next one (no re-run, FR-3).
  const fromStep = r.action === 'continue' && r.from_step != null ? Number(r.from_step) + 1 : 0
  // UFR-10 (#107): thread the lease generation recover_entry acquired into the workhorse build phase,
  // so the build can fence (renew-then-fence) at every branch-mutating boundary.
  const deps = { gateRead: gateReadFor(workItem), generation: r.generation }
  // FR-7 (#108)/FR-4 (#102)/Task-13a (#115): native front-half wiring. Three opt-in selectors
  // share the native authoring deps but differ on the boundary park:
  //   - env SUPERHEROES_FRONT_HALF=native: direct-node/smoke path (procEnv); keeps boundary park.
  //   - globalThis.SUPERHEROES_FRONT_HALF_NATIVE: Workflow-sandbox path (set by the ENTRY from
  //     args.frontHalf==='native'); procEnv is unavailable in the sandbox (FR-8), so the ENTRY
  //     injects this globalThis flag instead.
  //   - SUPERHEROES_BUNDLE_FULL_RUN true (preamble default + full-run ENTRY): no boundary park,
  //     proceeds into the back-half.
  const fullRun = !!globalThis.SUPERHEROES_BUNDLE_FULL_RUN
  const frontHalfNative = procEnv('SUPERHEROES_FRONT_HALF') === 'native' || !!globalThis.SUPERHEROES_FRONT_HALF_NATIVE
  if (frontHalfNative || fullRun) {
    deps.produce = producePhase                  // plan / tasks authoring (author-only)
    deps.reviewDoc = reviewDocPhase              // review-plan / review-tasks -> panel-doc leg
    if (!fullRun) deps.frontHalfBoundary = frontHalfBoundary   // front-half-only keeps the boundary park
  }
  return runPhases(workItem, fromStep, deps)
}

// readGate: IO read via exec (definition-doc on disk). A missing/malformed doc returns the
// 'unreadable' sentinel that phaseStep twin maps to park_unexpected_gate.
async function readGate(workItem, doc) {
  try {
    const results = await exec([
      `python3 plugins/superheroes/lib/definition_doc.py read-gate --doc ${shq(doc)} ` +
      `--work-item ${shq(workItem)} --root "$(git rev-parse --show-toplevel)" --json`,
    ])
    let out = null
    try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
    return (out && out.review) || 'unreadable'
  } catch (_) {
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

// phaseStep: pure in-process JS twin (phase_step.decide). No agent dispatch.
function phaseStep(phaseResult, gate) {
  return phaseStepTwin.decide(phaseResult, gate)
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
    // Progress-group every leaf dispatched during this phase under the phase name (read by the
    // bundle's agent wrapper). Purely cosmetic — no control-flow effect.
    if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = phase
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

// draft-PR: split IO from judgment (#115 Task 16).
// --emit-world reads the PR world (IO-only); recoverTwin.prAction decides adopt/create/gate in-process.
// On 'create': the full pr_entry.py path (ship_gate.decide + gh pr create + read-back) stays in Python.
// The {pr} capture happens before recordCursor persists it (FR-4 exactly-once preserved).
async function draftPRPhase(workItem) {
  const worldResults = await exec([
    `python3 plugins/superheroes/lib/pr_entry.py --step draft --work-item ${shq(workItem)} --emit-world`,
  ])
  let world = { pr: 'unknown' }  // fail-closed default
  if (worldResults[0] && worldResults[0].ok) {
    try { world = JSON.parse(worldResults[0].stdout) } catch (_) {}
  }
  const act = recoverTwin.prAction(world)
  if (act === 'gate') {
    return { phaseResult: { confidence: 'low', assumptions: ['PR read transient/merged — not creating a 2nd PR'] }, sideEffect: null }
  }
  if (act === 'adopt') {
    return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: world.pr } }
  }
  // 'create': ship_gate.decide + gh pr create + read-back stay in Python (irreducible IO + git/gh)
  const createResults = await exec([
    `python3 plugins/superheroes/lib/pr_entry.py --step draft --work-item ${shq(workItem)}`,
  ])
  let createOut = null
  if (createResults[0] && createResults[0].ok) {
    try { createOut = JSON.parse(createResults[0].stdout) } catch (_) {}
  }
  if (!createOut || !createOut.ok) {
    return { phaseResult: { confidence: 'low', assumptions: [createOut && createOut.reason || 'draft-PR gated'] }, sideEffect: null }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: createOut.pr } }
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
  // CI split (#115 Task 16): exec reads raw checks array (IO-only); ciStatusTwin classifies in-process.
  // green -> merge-ready; none -> merge-ready with carve-out; red -> park.
  // Fail-closed: exec error or {error} response -> park (never a false green).
  const ciResults = await exec([
    `python3 plugins/superheroes/lib/ship_phase.py --step ci --work-item ${shq(workItem)} --emit-checks`,
  ])
  if (!ciResults[0] || !ciResults[0].ok) {
    return park(workItem, pr, 'CI status could not be read')
  }
  let ciChecks = null
  try { ciChecks = JSON.parse(ciResults[0].stdout) } catch (_) {}
  // Fail-closed (Critical, #115 final review): a JSON.parse failure (ciChecks === null) means the
  // leaf returned garbled / non-JSON / truncated stdout — the read genuinely FAILED. Park; do NOT
  // coerce a parse-failure to [] (which would classify 'none' -> a false "merge-ready: no required
  // checks"). A genuinely-empty array [] still classifies to 'none' below (correct: no checks gate).
  if (ciChecks === null) {
    return park(workItem, pr, 'CI status could not be read')
  }
  if (!Array.isArray(ciChecks) && ciChecks.error) {
    return park(workItem, pr, ciChecks.error || 'CI status could not be read')
  }
  const checksArr = Array.isArray(ciChecks) ? ciChecks : []
  const ciRes = ciStatusTwin.classify(checksArr)
  if (ciRes.status === 'green') {
    return park(workItem, pr, 'merge-ready: CI green and branch up to date — awaiting owner merge', true)
  }
  if (ciRes.status === 'none') {
    return park(workItem, pr, 'merge-ready: no required checks gate this PR — confirm checks before merging', true)
  }
  const ciReason = ciRes.failing && ciRes.failing.length
    ? 'checks not green: ' + ciRes.failing.join(', ')
    : 'CI could not be made green'
  return park(workItem, pr, ciReason)
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
module.exports.exec = exec
module.exports.persistPhase = persistPhase
module.exports.cheapestModel = cheapestModel
module.exports.selfContained = selfContained
module.exports.authorModel = authorModel
