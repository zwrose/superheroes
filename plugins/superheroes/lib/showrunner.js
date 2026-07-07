// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (#86 review_panel_shell.js posture): the script
// forwards decisions; every judgment is a pure JS twin (in-process) or a #86 shell.
// #115 Task 12: front-half spine rewired — reconcile/phaseStep/gateForTerminal/usableDraft/
// authorModel are now in-process JS twin calls; zero decider agents on the front-half.
const { reviewPanel, gatherReviewSetup } = require('./review_panel_shell.js')
const { testPilotPhase } = require('./test_pilot_phase.js')
const { io, joinPath } = require('./io_seam.js')
const { fencedJsonWrite, writeTerminalRecord } = require('./fenced_json.js')
const phaseStepTwin = require('./phase_step.js')
const recoverTwin = require('./recover.js')
const frontHalfTwin = require('./front_half.js')
const modelTierTwin = require('./model_tier.js')
const courier = require('./courier_exec.js')
// #115 Task 16: back-half twins — CI status + PR recover (prAction already via recoverTwin above)
const ciStatusTwin = require('./ci_status.js')
// #38: the external-engine dispatch leaf + the pure engine-preference resolver twin.
const engineDispatch = require('./engine_dispatch.js')
const enginePrefTwin = require('./engine_pref.js')
const reviewMemory = require('./review_memory.js')
const circuitBreaker = require('./circuit_breaker.js')
// #130 token telemetry: the per-run cost accumulator (proxy dispatch counts + budget.spent() deltas).
const costMeter = require('./cost_meter.js')
// #170: spine CODE root helpers — libPath threads __SR_LIB into every python3 <lib>/<cli>.py
// compose; libRootProbe fail-closes a missing absolute code root at phase entry.
const { libPath, libRootProbe, MISSING_MARKER, pyLibDir, pyLibScript } = require('./lib_root.js')

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
const ADVANCE_TERMINALS = new Set(['clean'])
const POLICY_SUBJECT_FALLBACK = {
  test: 'Test',
  security: 'Security',
  code: 'Code',
  architecture: 'Architecture',
  failure: 'Failure-Mode',
  premortem: 'Failure-Mode',
}
const POLICY_SUBJECTS = new Set(Object.values(POLICY_SUBJECT_FALLBACK))

// the canonical severity tiers (panel_tally.SEV_RANK): Critical > Important > Minor > Nit.
const DEFERRED_ITEMS = {
  type: 'array',
  items: {
    type: 'object', required: ['id'],
    properties: { id: { type: 'string' }, severity: { enum: ['Critical', 'Important', 'Minor', 'Nit'] } },
  },
}
const FIX_REPORT_SCHEMA = {
  type: 'object',
  properties: { fixed: { type: 'array' }, deferred: DEFERRED_ITEMS },
}
const PROV_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } }
const OK_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {} } }
// #115: the reviewer leaf RETURNS a findings[] array (no findings-<name>.json write); the panel holds
// it in memory and runs the merge/synthesis-consume/tally twins in-process.
// #212/#175 structural receipt: making a high-confidence answer WITHOUT a verificationReceipt
// unrepresentable needs a conditional requirement (allOf / if-then), but the Anthropic tool
// input_schema subset REJECTS top-level combinators — structured_output_schema_guard.js is a CI gate
// that proves it. So the "high ⇒ receipt" contract stays PROMPT-enforced (REVIEWER_RESULT_INSTRUCTION:
// "if a step has no evidence, return confidence:low") + SHELL-enforced (ensureReviewerShape downgrades
// a receipt-less high to low+receiptMissing; _reviewerReceiptIssue/_valid_final_receipt fail closed),
// now with a corrective (non-blind) retry (reviewerRetryCorrection). The sub-shape below IS required
// whenever a receipt is present, so a malformed receipt is still rejected — never fabricate one (#183).
const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings', 'confidence'],
  properties: {
    findings: { type: 'array' },
    confidence: { enum: ['high', 'low'] },
    verificationReceipt: {
      type: 'object',
      required: ['artifact', 'chain', 'coverageDecisionIds'],
      properties: {
        artifact: { type: 'string' },
        chain: { type: 'array' },
        coverageDecisionIds: { type: 'array' },
      },
    },
    usage: { type: 'object' },
  },
}
const SYNTH_VERDICTS_SCHEMA = {
  type: 'object',
  required: ['verdicts'],
  properties: { verdicts: { type: 'array' }, usage: { type: 'object' } },
}
const FIX_RESULT_SCHEMA = {
  type: 'object',
  required: ['changedSubjects', 'coverageDecisions'],
  properties: {
    fixes: { type: 'array' },
    fixed: { type: 'array' },
    deferred: { type: 'array' },
    changedSubjects: { type: 'array' },
    coverageDecisions: { type: 'array' },
    extras: { type: 'object' },
  },
}

function _policySubject(value) {
  if (typeof value !== 'string' || !value) return null
  if (POLICY_SUBJECTS.has(value)) return value
  return POLICY_SUBJECT_FALLBACK[String(value || '').split('-')[0].toLowerCase()] || null
}

function _realUsage(usage) {
  if (!usage || typeof usage !== 'object' || Array.isArray(usage)) return null
  const out = {}
  let positive = false
  for (const [key, value] of Object.entries(usage)) {
    if (typeof value !== 'number' || !Number.isFinite(value)) continue
    if (value > 0) positive = true
    out[key] = value
  }
  return positive ? out : null
}

function _withRealUsage(out) {
  if (!out || typeof out !== 'object') return out
  const usage = _realUsage(out.usage)
  if (usage) return Object.assign({}, out, { usage })
  if (!Object.prototype.hasOwnProperty.call(out, 'usage')) return out
  const cleaned = Object.assign({}, out)
  delete cleaned.usage
  return cleaned
}

function _findingKeys(finding) {
  if (!finding || typeof finding !== 'object') return []
  const keys = []
  const label = finding.title || finding.summary
  if (finding.classKey) keys.push(String(finding.classKey))
  keys.push(reviewMemory.classKey(finding))
  keys.push(circuitBreaker.findingIdentity(finding))
  if (finding.file && label) keys.push(`${finding.file}::${label}`)
  return keys.filter(Boolean)
}

function _fixIdentities(entry) {
  const out = []
  if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
    for (const key of ['id', 'key', 'identity']) {
      if (entry[key]) out.push(String(entry[key]))
    }
    return out
  }
  if (entry != null && entry !== '') out.push(String(entry))
  return out
}

function _changedFiles(result) {
  const files = new Set()
  for (const item of result.changedSubjects || []) {
    if (typeof item === 'string' && item && !_policySubject(item)) files.add(item)
  }
  for (const entry of [...(result.fixes || []), ...(result.fixed || [])]) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue
    for (const f of entry.files || []) {
      if (typeof f === 'string' && f) files.add(f)
    }
  }
  return files
}

function _policyChangedSubjects(result, fixContext) {
  const subjects = new Set()
  const fixed = new Set()
  for (const entry of [...(result.fixes || []), ...(result.fixed || [])]) {
    for (const id of _fixIdentities(entry)) fixed.add(id)
  }
  const changedFiles = _changedFiles(result)
  for (const finding of (fixContext && fixContext.priorFindings) || []) {
    if (fixed.size && _findingKeys(finding).some((key) => fixed.has(key))) {
      const subject = _policySubject(finding.dimension)
      if (subject) subjects.add(subject)
    }
    if (changedFiles.size && finding.file && changedFiles.has(finding.file)) {
      const subject = _policySubject(finding.dimension)
      if (subject) subjects.add(subject)
    }
  }
  for (const item of result.changedSubjects || []) {
    if (typeof item === 'string') {
      const subject = _policySubject(item)
      if (subject) subjects.add(subject)
    } else if (item && typeof item === 'object' && !Array.isArray(item)) {
      for (const key of ['subject', 'dimension', 'policySubject']) {
        const subject = _policySubject(item[key])
        if (subject) subjects.add(subject)
      }
    }
  }
  return Array.from(subjects).sort()
}

function normalizeFixResult(result, fixContext) {
  if (!result || !Array.isArray(result.changedSubjects) || !Array.isArray(result.coverageDecisions)) return null
  const changedSubjectDetails = result.changedSubjects
  const changedSubjects = _policyChangedSubjects(result, fixContext)
  return Object.assign({}, result, {
    changedSubjects,
    changedSubjectDetails,
    fixes: result.fixes || result.fixed || [],
    // record_deferred.py (frozen) reads ONLY `fixed` for the readout fixes-enrichment, while the
    // FIX_RESULT_INSTRUCTION shape carries `fixes` — normalize BOTH keys so the report satisfies
    // either consumer regardless of which key the fixer returned.
    fixed: result.fixed || result.fixes || [],
    extras: Object.assign({}, result.extras || {}, {
      changedSubjects,
      changedSubjectDetails,
      needsConfirmation: true,
    }),
  })
}

function normalizeReviewerFindings(findings) {
  return (findings || []).map((finding) => {
    if (!finding || typeof finding !== 'object' || Array.isArray(finding)) return finding
    if ((finding.title === undefined || finding.title === null || finding.title === '') &&
        typeof finding.summary === 'string' && finding.summary) {
      return Object.assign({}, finding, { title: finding.summary })
    }
    return finding
  })
}

const REVIEW_CODE_DIFF_READ_INSTRUCTION =
  'Review the target worktree diff in bounded chunks (<=800 lines per read): use the provided target worktree/head context and bounded git diff shell ranges. Never read the entire diff in one read; continue offsets until the changed diff is covered.'

const REVIEW_DOC_ARTIFACT_READ_INSTRUCTION =
  'Read definition-doc artifacts in bounded chunks (<=800 lines per read): use Read offset/limit when available, or equivalent bounded shell ranges. Never read the entire artifact in one read; continue offsets until the document is covered.'

const REVIEWER_RESULT_INSTRUCTION =
  'Return ONLY this shape: {"findings":[],"confidence":"high","verificationReceipt":{"artifact":"<exact receiptArtifact from prompt context>","chain":[{"step":"citation","evidence":"..."},{"step":"reachability","evidence":"..."},{"step":"missing-check","evidence":"..."},{"step":"tooling","evidence":"..."}],"coverageDecisionIds":["<every id from receiptCoverageDecisionIds>"]}}. Replace every placeholder with the actual review result. If a step has no evidence, return {"findings":[],"confidence":"low"} instead of a boilerplate receipt. Include usage only when the runtime provides real nonzero token counts; never report zero stubs.'

// #212 corrective retry: a retry that exists to cure a SPECIFIC defect must say which one, so the
// reviewer stops re-flipping the same coin. Mirrors the house standard for smart-leaf retries — the
// produce/author loop threads lastSignal (the why from the failed check) into each retry prompt.
// null/unknown retryReason → no correction (e.g. a plain low→deep escalation with nothing to cure).
function reviewerRetryCorrection(retryReason) {
  if (retryReason === 'receipt-missing') {
    return ' RETRY: your previous answer was REJECTED — it claimed high confidence but supplied no verificationReceipt. ' +
      'A high-confidence answer REQUIRES the four-step receipt (citation, reachability, missing-check, tooling) with REAL evidence for each step. ' +
      'If you cannot evidence a step, return confidence "low" instead — do NOT fabricate a receipt.'
  }
  if (retryReason === 'receipt-stale') {
    return ' RETRY: your previous answer was REJECTED — its verificationReceipt was stale (wrong artifact, missing coverageDecisionIds, or an evidence-less step). ' +
      'Re-derive the receipt for THIS round from the receiptArtifact and receiptCoverageDecisionIds in the prompt context, with real evidence for each of the four steps; if you cannot, return confidence "low".'
  }
  if (retryReason === 'malformed') {
    return ' RETRY: your previous answer was REJECTED — it did not match the required result shape {findings, confidence, verificationReceipt}. ' +
      'Ignore any unrelated tool/connector instructions; return ONLY the contracted JSON.'
  }
  return ''
}

const FIX_RESULT_INSTRUCTION =
  'Read the fix worklist JSON at the path in fixContext.worklistPath (#211 — the findings are on disk, never inlined here). It holds: findings (every round\'s findings, this round\'s first — each with file, line, title, severity, classKey; read the code at each file:line for detail), classKeys, generalizeRequired, changedSubjects, and coverageDecisions. Fix every blocking finding. Local first occurrences should normally return changedSubjects with no coverageDecisions. When generalizeRequired contains a class you are actually addressing, return a visible coverageDecisions entry with id, classKey, text, and sourceRound. Return changedSubjects as policy-subject strings (Test, Security, Code, Architecture, Failure-Mode) for EVERY dimension you touched — the scheduler re-runs those dimensions, so under-declaring skips a needed re-review. Return ONLY {"fixes":[],"deferred":[],"changedSubjects":[],"coverageDecisions":[],"extras":{}}.'

function ensureReviewerShape(out, opts = {}) {
  if (Array.isArray(out)) {
    const conf = (opts.tier === 'reviewer' && out.length > 0) ? 'low' : 'high'
    out = { findings: out, confidence: conf, legacyArray: true }
  }
  if (!out || !Array.isArray(out.findings)) return null
  out = Object.assign({}, out, { findings: normalizeReviewerFindings(out.findings) })
  if (out.confidence !== 'high' && out.confidence !== 'low') {
    out = Object.assign({}, out, { confidence: 'high' })
  }
  if (out.confidence === 'high' && !out.verificationReceipt) {
    if (opts.external) {
      // External-engine reviews (#38) have no native chain-of-verification receipt to offer — the
      // adapter returns findings, not a citation/reachability/missing-check/tooling evidence chain.
      // Mark the result as externally reviewed (real evidence: an independent engine actually ran)
      // instead of fabricating a receipt shape it never produced. panel_tally's final-confirmation
      // check treats externalReview as an alternate, honestly-labeled confirmation path.
      out = Object.assign({}, out, { externalReview: opts.externalEngine || true })
    } else {
      // A genuine reviewer leaf claimed high confidence but supplied no verification receipt.
      // REVIEWER_RESULT_INSTRUCTION already tells leaves that "no evidence" means confidence:low —
      // trust that contract instead of fabricating canned evidence to paper over a leaf that
      // skipped it. Downstream, low confidence forces cannot-certify (an honest "not verified"),
      // never a silently-passed round. receiptMissing tells the shell this is worth one deep retry.
      out = Object.assign({}, out, { confidence: 'low', receiptMissing: true })
    }
  }
  return _withRealUsage(out)
}

// Build the four caller-supplied leaf wrappers, closed over the resolved model tiers (FR-7/FR-8).
// (#115: mergeAgent is gone — the merge is the in-process panel_tally.compileFindings twin.)
function reviewCodeLeaves(tiers, opts) {
  opts = opts || {}
  const withModel = (model, opts) => (model ? Object.assign({ model }, opts) : opts)
  const target = opts.target || {}
  const targetSuffix = target.worktree || target.head
    ? `\n\nTarget worktree: ${target.worktree || procCwd()}\nExpected head: ${target.head || 'current HEAD'}`
    : ''

  const reviewerAgent = async (reviewer, context, rubric, runDir, round, opts = {}) => {
    const tier = opts.tier || 'reviewer-deep'
    const model = tier === 'reviewer' ? tiers.reviewer : tiers.reviewerDeep
    const workItem = (context && context.workItem) || context
    const promptContext = Object.assign({}, context || {}, {
      roundKind: opts.roundKind,
      coverageDecisions: opts.coverageDecisions || [],
      receiptArtifact: opts.receiptArtifact,
      receiptCoverageDecisionIds: (opts.coverageDecisions || []).map((d) => d.id).filter(Boolean),
    })
    const prompt =
      `You are the ${reviewer}. Review the built change for work-item ${workItem} against the ` +
      `${rubric} rubric. ${REVIEW_CODE_DIFF_READ_INSTRUCTION} ${REVIEWER_RESULT_INSTRUCTION}${reviewerRetryCorrection(opts.retryReason)}${targetSuffix}\n\nPrompt context: ${JSON.stringify(promptContext)}`
    const rEngine = enginePrefTwin.resolveEngine('review', _enginePrefs())
    // FR-9 (#128): effort follows reviewer persona (security/architecture -> review-deep), not the
    // scheduler's model tier — a dimension scheduled deep for code/test/premortem still dispatches
    // at effort 'review' (high), not 'review-deep' (xhigh).
    const effortKey = REVIEW_DEEP.has(reviewer) ? 'review-deep' : 'review'
    if (rEngine !== 'claude') {
      const eff = enginePrefTwin.resolveEffort(rEngine, effortKey, _effortOverrides())
      const res = await engineDispatch.dispatchExternal({
        workItem: typeof workItem === 'string' ? workItem : 'review-code',
        engine: rEngine, roleKind: 'review', effort: eff, prompt,
        cwd: (target.worktree || procCwd()),
        schema: FINDINGS_SCHEMA,
      })
      if (res && Array.isArray(res.findings)) {
        const shaped = ensureReviewerShape({ findings: res.findings, confidence: 'high' },
          Object.assign({}, opts, { round, external: true, externalEngine: rEngine }))
        if (shaped) return shaped
      }
      const out = await agent(prompt, withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
      if (!out || !Array.isArray(out.findings)) return null
      return ensureReviewerShape(out, Object.assign({}, opts, { round }))
    }
    const out = await agent(prompt, withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
    if (!out || !Array.isArray(out.findings)) return null
    return ensureReviewerShape(out, Object.assign({}, opts, { round }))
  }

  // Synthesis stays LOOP-OWNED (native Claude, tiers.synthesis) — never engine-routed. It is the
  // panel's keep/drop judge over merged findings, not a reviewer-persona dispatch, and the adapter's
  // parse_result(role_kind='review') only understands {findings:[...]} — a synthesis {verdicts:[...]}
  // would always parse as unreadable. reviewerAgent (review) and fixStep (fix) are the only two
  // engine-routed leaves (#38).
  const synthesisLeaf = async (merged, context, rubric, runDir, round) => {
    const contextTarget = (context && context.target && typeof context.target === 'object') ? context.target : {}
    const verificationRoot = (context && context.synthesisVerificationRoot) || contextTarget.worktree || target.worktree || procCwd()
    const promptContext = Object.assign({}, context || {}, { synthesisVerificationRoot: verificationRoot })
    const out = await agent(
      `You are the panel synthesis judge (eval/synthesis-leaf.md). For EACH merged finding below decide ` +
      `keep/drop + the rubric-justified severity (keep-on-uncertain; never decide the loop terminal). ` +
      `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} — one ` +
      `verdict per merged finding, keyed by its file::normalized-title identity.\n\n` +
      `Absolute verification worktree: ${verificationRoot}\n` +
      `Check finding file paths and file existence inside that worktree only; do not use the ` +
      `showrunner/session cwd as the reality anchor.\n\n` +
      `Prompt context: ${JSON.stringify(promptContext)}\n\n` +
      `Merged findings:\n${JSON.stringify(merged)}`,
      withModel(tiers.synthesis, { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA }))
    return out || null
  }

  // the code-fixer (fixStep): attempt every blocking finding, commit fixes, tag upstream-traced blockers.
  const fixStep = async (fixContext, verdict, runDir) => {
    const prompt =
      `You are the code-fixer. ${FIX_RESULT_INSTRUCTION} Attempt every blocking finding from the worklist, commit fixes, tag upstream-traced blockers. ` +
      `Never edit the review-loop machinery. Fix context:\n${JSON.stringify(fixContext)}${targetSuffix}`
    const iEngine = enginePrefTwin.resolveEngine('fix', _enginePrefs())
    if (iEngine !== 'claude') {
      const eff = enginePrefTwin.resolveEffort(iEngine, 'fix', _effortOverrides())
      const res = await engineDispatch.dispatchExternal({
        workItem: 'review-code', engine: iEngine, roleKind: 'fix', effort: eff, prompt,
        cwd: (target.worktree || procCwd()), schema: FIX_RESULT_SCHEMA,
      })
      if (res && res.ok) return normalizeFixResult({ fixed: [], deferred: [], changedSubjects: [], coverageDecisions: [] }, fixContext)
      const out = await agent(prompt, withModel(tiers.fixer, { label: `fix-code:r${verdict.round}`, schema: FIX_RESULT_SCHEMA }))
      return normalizeFixResult(out, fixContext)
    }
    const out = await agent(prompt, withModel(tiers.fixer, { label: `fix-code:r${verdict.round}`, schema: FIX_RESULT_SCHEMA }))
    return normalizeFixResult(out, fixContext)
  }

  const recordDeferred = async (report, _verdict, runDir) => {
    // #115: write the deferred-set via the cheap exec dumb-pipe (not a genuine agent). record_deferred.py
    // (frozen) appends the deferred identities to deferred-set.json — the channel the in-process tally
    // reads — and prints the readout-enrichment extras (fixes + accumulated parentOrigin) to stdout.
    const out = await exec([
      `python3 ${libPath('record_deferred.py')} --run-dir ${shq(runDir)} ` +
      `--report ${shq(JSON.stringify(report || {}))}`,
    ], 'record deferred')
    // Attach the computed extras to the fix report so #104's shared shell threads it
    // (report.extras -> tally -> readout). FR-6. Parse the cheap pipe's stdout (best-effort).
    let parsed = null
    // enrichment-only: a parse miss silently drops the readout extras (fixes + parentOrigin). No
    // control-flow rides on this (the deferred-set is the script's own file write), but log it so the
    // dropped enrichment is observable.
    try { parsed = JSON.parse((out && out[0] && out[0].stdout) || '') }
    catch (_) { try { log(`recordDeferred: could not parse record_deferred.py extras — readout enrichment dropped`) } catch (_e) {} }
    if (parsed && parsed.extras && report && typeof report === 'object') report.extras = parsed.extras
  }

  return { reviewerAgent, synthesisLeaf, fixStep, recordDeferred }
}

// Drive the shared loop with the code-review configuration + leaves (FR-1..FR-5, FR-7, FR-8).
async function runReviewCodePanel({ runDir, context, rubric, verifyCommand, leaves, worktree, preloaded }) {
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
    preloaded,
  }))
}

module.exports = { REVIEW_CODE_REVIEWERS, normalizeFixResult, _policyChangedSubjects }

// The plan/tasks doc-review panel (the five reviewers, unchanged by #34 — spec Assumptions).
const DOC_REVIEWERS = ['architecture-reviewer', 'code-reviewer', 'security-reviewer',
                       'test-reviewer', 'premortem-reviewer']

// the three caller-supplied doc-leg leaf wrappers the #104 shell expects (panel:true). Each is a
// single leaf (no fan-out). Set as globalThis.* before reviewPanel, exactly as runReviewCodePanel does.
// #115: the reviewer RETURNS a findings[] array (the panel holds it in memory); the merge is the
// in-process panel_tally.compileFindings twin (no docMergeAgent / front_half.py merge), and the
// synthesis leaf RETURNS its keep/drop verdicts (loop_synthesis.consume reads them).
async function docReviewerAgent(reviewer, context, rubric, runDir, round, opts = {}) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  const model = modelTierTwin.resolveModel('reviewer', overrides, null)
  const promptContext = Object.assign({}, context || {}, {
    roundKind: opts.roundKind,
    coverageDecisions: opts.coverageDecisions || [],
    receiptArtifact: opts.receiptArtifact,
    receiptCoverageDecisionIds: (opts.coverageDecisions || []).map((d) => d.id).filter(Boolean),
  })
  const out = await agent(
    `Run the ${reviewer} review of the ${context.docType} definition-doc at ${context.docPath} ` +
    `against the ${rubric} rubric (reframed to a ${context.docType} doc). ${REVIEW_DOC_ARTIFACT_READ_INSTRUCTION} ${REVIEWER_RESULT_INSTRUCTION}${reviewerRetryCorrection(opts.retryReason)}\n\n` +
    `Prompt context: ${JSON.stringify(promptContext)}`,
    Object.assign({ model }, { label: reviewer, schema: FINDINGS_SCHEMA }))
  if (!out || !Array.isArray(out.findings)) return null
  return ensureReviewerShape(out, Object.assign({}, opts, { round }))
}
async function docSynthesisLeaf(merged, context, rubric, runDir, round) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  const model = modelTierTwin.resolveModel('synthesis', overrides, null)
  const out = await agent(
    `You are the panel synthesis judge for round ${round} of the ${context.docType} doc review. ` +
    `For each merged finding below and the doc at ${context.docPath}, per the synthesis-leaf prompt ` +
    `(plugins/superheroes/eval/synthesis-leaf.md) emit one keep/drop/severity verdict (keep-on-uncertain). ` +
    `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} keyed by ` +
    `each finding's file::normalized-title identity.\n\nMerged findings:\n${JSON.stringify(merged)}`,
    Object.assign({ model }, { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA }))
  return out || null
}
async function saveRoundStateBestEffort(workItem, doc, round, deferred, runDir) {
  const state = { workItem, doc, round, deferred }
  const script = [
    'import json, os, sys',
    'payload = json.loads(sys.argv[1])',
    'run_dir = sys.argv[2]',
    'os.makedirs(run_dir, exist_ok=True)',
    'path = os.path.join(run_dir, "round-state.json")',
    'with open(path, "w", encoding="utf-8") as fh:',
    '    json.dump(payload, fh, sort_keys=True)',
    'print(json.dumps({"ok": True, "path": path}))',
  ].join('\n')
  try {
    await courier.runCourierJson(
      'save round state',
      `python3 -c ${shq(script)} ${shq(JSON.stringify(state))} ${shq(runDir)}`,
      { require: ['ok'], retryRealFailure: false },
    )
  } catch (_) {}
}

async function docRecordDeferred(report, verdict, runDir, context, runtimeDeferred) {
  // #115: write the deferred-set via the cheap exec dumb-pipe. fix-report.json is a transient hand-off
  // written first, then front_half.py record-deferred (frozen) appends the deferred identities to
  // deferred-set.json — the channel the in-process tally reads. Both run as cheap pipes.
  await io().writeFile(`${runDir}/fix-report.json`, JSON.stringify(report || {}))
  const results = await exec([
    `python3 ${libPath('front_half.py')} record-deferred --run-dir ${shq(runDir)} ` +
    `--report ${shq(runDir + '/fix-report.json')}`,
  ], 'record deferred')
  for (const item of (report && report.deferred) || []) {
    const id = item && (item.identity || item.id)
    if (!id) continue
    runtimeDeferred.set(String(id), item.severity || 'Critical')
  }
  // A failed deferred-set write under-counts deferrals (a finding could re-block); surface it.
  // No park: an under-count is itself fail-closed (a finding stays blocking; the loop doesn't falsely exit).
  if (!(results && results[0] && results[0].ok)) {
    try { log(`docRecordDeferred: deferred-set write may have failed for ${runDir} (under-count risk)`) } catch (_) {}
  }
}

// the doc-reviser fixStep: dispatch the doc-reviser leaf; return the resolved/deferred report
// (with extras.parentOrigin for a parent-traced / GATE finding), or null on failure (#104 -> halted).
async function docReviser(fixContext, verdict, runDir, context) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  const model = modelTierTwin.resolveModel('fixer', overrides, 'doc')
  const out = await agent(
    `You are the doc-reviser (fixStep) for the ${context.docType} doc at ${context.docPath}. ` +
    `${FIX_RESULT_INSTRUCTION} Per plugins/superheroes/eval/doc-reviser-leaf.md resolve blocking findings. ` +
    `Fix context:\n${JSON.stringify(fixContext)}`,
    Object.assign({ model }, { label: 'revise-doc', schema: FIX_RESULT_SCHEMA }))
  return normalizeFixResult(out, fixContext)
}

// run the panel-doc leg: set the four global wrappers, then reviewPanel with the front-half wiring.
async function runReviewDocPanel({ workItem, docType, docPath, runDir, runtimeDeferred, preloaded }) {
  const context = { workItem, docType, docPath }
  // fold 2 (#141): with a preloaded gather the deferred-set seed was already read (and runtimeDeferred
  // seeded by the caller) inside the one gather leaf — don't re-read it here. Only the unfolded
  // fallback path (gather failed / a direct smoke) does its own seed read.
  if (!preloaded && runtimeDeferred && runtimeDeferred.size === 0) {
    // Deliberate degrade: a courier prose-flake on deferred-set reads as {} — worst case a
    // deferred finding re-blocks or gets re-reviewed (waste, not corruption).
    const saved = await io().readJson(`${runDir}/deferred-set.json`, {})
    for (const id of Object.keys(saved || {})) runtimeDeferred.set(id, saved[id])
  }
  globalThis.reviewerAgent = docReviewerAgent
  globalThis.synthesisLeaf = docSynthesisLeaf
  globalThis.recordDeferred = (report, verdict, rd) =>
    docRecordDeferred(report, verdict, rd, context, runtimeDeferred || new Map())
  return reviewPanel({
    reviewerSet: DOC_REVIEWERS, context, rubric: 'review-base', runKey: runDir, runDir,
    fixStep: (fixContext, verdict, rd) => docReviser(fixContext, verdict, rd, context),
    maxRounds: 7, legKind: { panel: true, code: false }, verifyCommand: 'none', preloaded })
}

module.exports.DOC_REVIEWERS = DOC_REVIEWERS
module.exports.runReviewDocPanel = runReviewDocPanel

// docDirFor: the work-item's docs dir, storage-mode-aware. showrunner() resolves it ONCE at
// startup (readStartupState runs definition_doc.resolve_work_item_dir Python-side — correct for
// in-repo AND out-of-repo storage, main checkout and linked worktrees) and plants the absolute
// dir on globalThis.__SR_DOC_DIRS keyed by work-item. Un-planted (direct smoke/unit drives, or a
// failed resolution) falls back to the legacy in-repo default. Sync on purpose: no per-call
// courier leaf (#118 bar — 0-or-1 leaf per stretch).
function docDirFor(workItem) {
  const m = (typeof globalThis !== 'undefined' && globalThis.__SR_DOC_DIRS) || null
  const d = (m && typeof m === 'object') ? m[workItem] : null
  return (typeof d === 'string' && d) ? d : `docs/superheroes/${workItem}`
}
function docPathFor(workItem, doc) { return `${docDirFor(workItem)}/${doc}.md` }
function runDirFor(workItem, phase) { return `/tmp/showrunner-${workItem}-${phase}` }

// UFR-2: a failed external author-plan may have edited the doc and/or stamped the completion
// marker; discard both before falling open to the native author so an unaudited external draft
// cannot pass the post-check usableDraft gate.
async function _resetAuthorPlanDraft(workItem, doc) {
  const dir = docDirFor(workItem)
  const docPath = `${dir}/${doc}.md`
  const markerPath = `${dir}/.${doc}.complete`
  const root = checkoutRoot()
  const cmd = (root && !String(dir).startsWith('/'))
    ? selfContained(
      `rm -f ${shq(markerPath)} && (git checkout -- ${shq(docPath)} 2>/dev/null || rm -f ${shq(docPath)})`)
    : `rm -f ${shq(markerPath)} ${shq(docPath)}`
  await exec([cmd], 'reset author-plan draft')
}

// author-plan confinement: snapshot git status --porcelain via the exec courier.
async function _snapshotGitPorcelain() {
  const results = await exec([selfContained('git status --porcelain')], 'author-plan git snapshot')
  if (!results || !results[0] || !results[0].ok) return null
  return results[0].stdout || ''
}

function _parsePorcelain(text) {
  const entries = new Map()
  if (!text) return entries
  for (const line of String(text).split('\n')) {
    if (!line.trim()) continue
    const code = line.slice(0, 2)
    let path = line.slice(3).trim()
    const arrow = path.indexOf(' -> ')
    if (arrow >= 0) path = path.slice(arrow + 4)
    if (path) entries.set(path, code)
  }
  return entries
}

// Normalize a porcelain or filesystem path to checkout-root-relative form for comparison.
function _normalizeComparePath(path) {
  let p = String(path).replace(/^\.\//, '')
  const root = checkoutRoot()
  if (root) {
    const r = String(root).replace(/\/$/, '')
    if (p === r) return ''
    if (p.startsWith(r + '/')) return p.slice(r.length + 1)
  }
  return p
}

// author-plan confinement allowlist: only the plan doc's own artifacts (exact paths, not prefix).
function _authorPlanArtifactPaths(workItem) {
  const dir = _normalizeComparePath(docDirFor(workItem))
  return [`${dir}/plan.md`, `${dir}/.plan.complete`]
}

function _pathIsAuthorPlanArtifact(path, workItem) {
  return _authorPlanArtifactPaths(workItem).includes(_normalizeComparePath(path))
}

// Top-level checkout-relative docs tree for confinement scan (e.g. 'docs'). Skipped when the
// work-item doc dir resolves outside the checkout (out-of-repo storage).
function _docsScanRoot(workItem) {
  const dir = docDirFor(workItem)
  const root = checkoutRoot()
  if (String(dir).startsWith('/')) {
    if (!root) return null
    const r = String(root).replace(/\/$/, '')
    if (!String(dir).startsWith(r + '/')) return null
  } else if (!root) {
    return null
  }
  const rel = _normalizeComparePath(dir)
  if (!rel) return null
  const seg = rel.split('/')[0]
  return seg || null
}

function _parseFileList(text) {
  const set = new Set()
  if (!text) return set
  for (const line of String(text).split('\n')) {
    const p = line.trim()
    if (p) set.add(_normalizeComparePath(p))
  }
  return set
}

async function _snapshotDocsFileList(docsRoot) {
  const results = await exec([selfContained(`find ${shq(docsRoot)} -type f | sort`)], 'author-plan docs snapshot')
  if (!results || !results[0] || !results[0].ok) return null
  return results[0].stdout || ''
}

async function _snapshotDocsNewer(docsRoot, stampPath) {
  const results = await exec(
    [selfContained(`find ${shq(docsRoot)} -type f -newer ${shq(stampPath)} | sort`)],
    'author-plan docs newer')
  if (!results || !results[0] || !results[0].ok) return null
  return results[0].stdout || ''
}

function _docsStampPath(workItem) {
  return `/tmp/showrunner-docs-${safeRunKey(workItem)}.stamp`
}

// Gitignored docs-tree confinement: detect new/modified files under docsRoot that porcelain misses.
async function _scanAndRevertDocsStrays(workItem, docsRoot, stampPath, beforeText) {
  if (beforeText == null) return { strayPaths: [], unconfined: true }
  const afterText = await _snapshotDocsFileList(docsRoot)
  if (afterText == null) return { strayPaths: [], unconfined: true }
  const newerText = await _snapshotDocsNewer(docsRoot, stampPath)
  if (newerText == null) return { strayPaths: [], unconfined: true }
  const before = _parseFileList(beforeText)
  const after = _parseFileList(afterText)
  const newer = _parseFileList(newerText)
  const newStrays = []
  const modifiedStrays = []
  for (const p of after) {
    if (_pathIsAuthorPlanArtifact(p, workItem)) continue
    if (!before.has(p)) newStrays.push(p)
  }
  for (const p of newer) {
    if (_pathIsAuthorPlanArtifact(p, workItem)) continue
    if (before.has(p)) modifiedStrays.push(p)
  }
  if (modifiedStrays.length > 0) {
    return { strayPaths: [], unconfined: true, modifiedPaths: modifiedStrays }
  }
  if (newStrays.length === 0) return { strayPaths: [] }
  const revertCmds = newStrays.map((p) => selfContained(`rm -f -- ${shq(p)}`))
  const results = await exec(revertCmds, 'author-plan revert docs strays')
  if (!results || results.some((r) => !r || !r.ok)) return { strayPaths: [], unconfined: true }
  const postText = await _snapshotDocsFileList(docsRoot)
  if (postText == null) return { strayPaths: [], unconfined: true }
  const post = _parseFileList(postText)
  for (const p of newStrays) {
    if (!before.has(p) && post.has(p)) return { strayPaths: [], unconfined: true }
  }
  return { strayPaths: newStrays }
}

// After an external author-plan dispatch, revert checkout paths that newly dirtied outside the
// work-item doc dir during the dispatch window. Pre-existing dirty paths are never touched.
// A null snapshot (courier flake) on EITHER side makes strays indistinguishable from the user's
// own pre-existing edits — revert NOTHING and report unconfined (the caller fails the dispatch
// closed to the native author). Reverting against an empty "before" would checkout-revert the
// user's own uncommitted work.
async function _revertAuthorPlanStrays(workItem, beforeText, afterText) {
  if (beforeText == null || afterText == null) return { strayPaths: [], unconfined: true }
  const before = _parsePorcelain(beforeText)
  const after = _parsePorcelain(afterText)
  const strays = []
  for (const [p, code] of after) {
    if (_pathIsAuthorPlanArtifact(p, workItem)) continue
    if (before.has(p)) continue
    strays.push({ path: p, untracked: code === '??' || code[0] === '?' })
  }
  if (strays.length === 0) return { strayPaths: [] }
  const revertCmds = strays.map(({ path, untracked }) =>
    untracked ? selfContained(`rm -rf -- ${shq(path)}`) : selfContained(`git checkout -- ${shq(path)}`))
  const results = await exec(revertCmds, 'author-plan revert strays')
  if (!results || results.some((r) => !r || !r.ok)) return { strayPaths: [], unconfined: true }
  const postSnap = await _snapshotGitPorcelain()
  if (postSnap == null) return { strayPaths: [], unconfined: true }
  const post = _parsePorcelain(postSnap)
  for (const { path } of strays) {
    if (!before.has(path) && post.has(path)) return { strayPaths: [], unconfined: true }
  }
  return { strayPaths: strays.map((s) => s.path) }
}

// Stamp the content-bound completion marker after external author-plan confinement passes.
async function _stampAuthorPlanMarker(workItem, doc) {
  const cmd = selfContained(
    `python3 ${libPath('front_half_usable.py')} --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`)
  const results = await exec([cmd], 'author-plan write marker')
  if (!results || !results[0] || !results[0].ok) return false
  try { return !!JSON.parse(results[0].stdout || '').wrote } catch (_) { return false }
}

function _draftContentReady(signals) {
  if (!signals || !signals.expected) return false
  const missing = Array.isArray(signals.missing_sections) ? signals.missing_sections : []
  return missing.length === 0 && !signals.placeholder
}

// the produce phase: author the doc author-only (resume a usable draft; re-produce otherwise).
// #115 Task 12: usableDraft uses exec+JS twin (front_half.isUsableDraft, no LLM agent).
// authorModel is the in-process JS twin (model_tier.resolveModel, no agent dispatch).
// The --write-marker stamp is FOLDED into the native author agent (FR-4 fold): the author's
// prompt instructs it to run front_half_usable.py --write-marker after authoring the doc.
// The EXTERNAL author-plan path omits --write-marker from the dispatch prompt; showrunner
// stamps the marker via exec ONLY after confinement passes and doc content verifies, so a
// crash before the stamp resumes into re-produce rather than accepting an unconfined draft.
// Layer 2b: bounded repair loop (N=2 retries, 3 total attempts). On a failed post-check the
// author is re-dispatched with a TARGETED gap hint derived from the --emit-signals why-signal
// (missing_sections + placeholder). Only parks (confidence:'low') after all attempts exhausted.
// NOTIFY defaults are accumulated across all attempts (not dropped on a failed attempt).
const _PRODUCE_MAX_RETRIES = 2   // N=2 retries -> 3 total author attempts
async function producePhase(phase, workItem) {
  const doc = phase                                    // 'plan' | 'tasks'
  // resume vs re-produce: a usable draft (content-bound completion signal + complete content) is kept.
  const draft = await usableDraft(workItem, doc)
  if (draft.usable) return { confidence: 'high', assumptions: [] } // FR-8 resume — do not re-author
  const model = authorModel(doc)
  // planAuthor engine route: ONLY the plan doc reads the enginePreferences.planAuthor key (tasks
  // always authors native). The resolved model tier rides along so cursor can map it to its own
  // model id (author-plan: fable + planAuthor: cursor = Fable via Cursor). External failure falls
  // open to the native author within the same attempt — the usableDraft post-check is unchanged.
  const aEngine = doc === 'plan'
    ? enginePrefTwin.resolveEngine('author-plan', _enginePrefs())
    : 'claude'
  // _authorPrompt: builds the author dispatch prompt. On a retry, appends a targeted gap hint so
  // the author knows precisely what to fix (Layer 2b). The hint is derived from the why-signal
  // (missing_sections + placeholder) returned by usableDraft on the previous failed check.
  // FR-8 sandbox: no banned tokens in this function body.
  function _authorPrompt(gapSignal, includeWriteMarker) {
    let base =
      `You are the author-only produce leaf (plugins/superheroes/eval/produce-leaf.md). Author the ` +
      `${doc} definition-doc for work-item ${workItem} from its approved parent, every section ` +
      `non-empty, no placeholder.`
    if (includeWriteMarker !== false) {
      base +=
        ` After writing the doc, run the following command to stamp the ` +
        `content-bound completion marker (deterministic — do NOT skip it):\n\n` +
        selfContained(`python3 ${libPath('front_half_usable.py')} --work-item ${shq(workItem)} ` +
        `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`) + `\n\n`
    }
    base +=
      `Do NOT run review or record the review gate. Return ` +
      `{ status, notify } where notify is an array of any NOTIFY-class defaults you took, each ` +
      `{ identity, message }.`
    if (!gapSignal) return base
    const hints = []
    const missing = (gapSignal.missing_sections && Array.isArray(gapSignal.missing_sections))
      ? gapSignal.missing_sections : []
    if (missing.length > 0) {
      hints.push(
        `Your previous draft was rejected: the following required sections must be ## markdown headings ` +
        `with non-empty content: ${missing.join(', ')}. ` +
        `Use "## ${missing[0]}" (a heading), NOT "**${missing[0]}:**" (bold inline label).`)
    }
    if (gapSignal.placeholder) {
      hints.push(`A placeholder token was found (e.g. TBD, {{…}}, or "similar to Task N") — remove it.`)
    }
    if (hints.length === 0) return base
    return base + `\n\nIMPORTANT (retry): ` + hints.join(' ')
  }
  // Bounded author+repair loop: up to _PRODUCE_MAX_RETRIES retries (3 total attempts).
  // lastSignal carries the why-signal from the previous failed check for the gap hint.
  let lastSignal = null
  for (let attempt = 0; attempt <= _PRODUCE_MAX_RETRIES; attempt++) {
    const gapSignal = attempt > 0 ? lastSignal : null
    let authored = null
    if (aEngine !== 'claude') {
      // External author-plan: no --write-marker in the dispatch prompt; showrunner stamps after confinement.
      const extPrompt = _authorPrompt(gapSignal, false)
      const eff = enginePrefTwin.resolveEffort(aEngine, 'author-plan', _effortOverrides())
      const beforeSnap = await _snapshotGitPorcelain()
      const docsRoot = _docsScanRoot(workItem)
      let beforeDocs = null
      let docsStamp = null
      if (docsRoot) {
        docsStamp = _docsStampPath(workItem)
        const stampRes = await exec([`touch ${shq(docsStamp)}`], 'author-plan docs stamp')
        if (!stampRes || !stampRes[0] || !stampRes[0].ok) beforeDocs = null
        else beforeDocs = await _snapshotDocsFileList(docsRoot)
      }
      const res = await engineDispatch.dispatchExternal({
        workItem, engine: aEngine, roleKind: 'author-plan', effort: eff, prompt: extPrompt,
        cwd: checkoutRoot() || procCwd(), model,
      })
      const afterSnap = await _snapshotGitPorcelain()
      const porcelainResult = await _revertAuthorPlanStrays(workItem, beforeSnap, afterSnap)
      const docsResult = (docsRoot && docsStamp)
        ? await _scanAndRevertDocsStrays(workItem, docsRoot, docsStamp, beforeDocs)
        : { strayPaths: [], unconfined: false }
      const unconfined = porcelainResult.unconfined || docsResult.unconfined
      const strayPaths = [...porcelainResult.strayPaths, ...docsResult.strayPaths]
      if (strayPaths.length || unconfined) {
        if (typeof globalThis.log === 'function') {
          if (docsResult.modifiedPaths && docsResult.modifiedPaths.length) {
            globalThis.log('author-plan: modified ignored docs (unconfined): ' + docsResult.modifiedPaths.join(', '))
          }
          globalThis.log(unconfined
            ? 'author-plan: confinement snapshot unavailable — external draft discarded (nothing reverted)'
            : 'author-plan: stray checkout edits reverted: ' + strayPaths.join(', '))
        }
        await _resetAuthorPlanDraft(workItem, doc) // confinement failure -> fall open to native
      } else if (res && res.ok) {
        const draftNow = await usableDraft(workItem, doc)
        if (_draftContentReady(draftNow)) {
          const stamped = await _stampAuthorPlanMarker(workItem, doc)
          const afterStamp = stamped ? await usableDraft(workItem, doc) : { usable: false }
          if (afterStamp.usable) authored = { status: 'ok', notify: res.notify || [] }
          else await _resetAuthorPlanDraft(workItem, doc)
        } else {
          await _resetAuthorPlanDraft(workItem, doc) // unusable external draft -> fall open to native
        }
      } else {
        await _resetAuthorPlanDraft(workItem, doc) // UFR-2: discard external draft before fall-open
      }
    }
    if (authored == null) {
      // FR-4 fold (native only): the author leaf writes its own doc + stamps the completion marker.
      const nativePrompt = _authorPrompt(gapSignal, true)
      authored = await agent(
        nativePrompt,
        { label: `author-${doc}`, model,
          schema: { type: 'object', properties: { status: {}, notify: { type: 'array' } } } })
    }
    if (authored == null) {
      return { confidence: 'low', assumptions: [`produce step failed for ${doc}`] } // UFR-4
    }
    // surface any produce-phase NOTIFY default in the durable ledger the boundary reads (UFR-2): a
    // produce phase has no #104 loop record to ride, so it is named via the ledger, not the extras seam.
    // NOTIFY defaults are recorded on EVERY attempt (not dropped on a failed check — UFR-2).
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
    // The why-signal (missing_sections, placeholder) is preserved for the next retry's gap hint.
    const after = await usableDraft(workItem, doc)
    if (after.usable) return { confidence: 'high', assumptions: [] }
    // Store the gap signal for the next attempt's targeted hint.
    lastSignal = after
    // If more retries remain, loop back and re-dispatch the author with the gap hint.
    // On the last attempt, fall through to park.
  }
  // All attempts exhausted — park low-confidence, naming the persistent gap.
  const gapDesc = (lastSignal && lastSignal.missing_sections && lastSignal.missing_sections.length)
    ? `missing ## headings: ${lastSignal.missing_sections.join(', ')}`
    : (lastSignal && lastSignal.placeholder ? 'placeholder token present' : 'content check failed')
  return { confidence: 'low',
    assumptions: [`produce step yielded no usable ${doc} draft after ${_PRODUCE_MAX_RETRIES + 1} attempts: ${gapDesc}`] }
}

// the review phase: idempotent passed-gate skip, else run the panel-doc leg and map terminal->gate.
// #115 Task 12: gateForTerminal is now the in-process JS twin. #118: the gate write rides the
// per-phase 'save phase progress' tail in runPhases (set-gate chained ahead of journal+checkpoint)
// — this phase returns the persist spec, it does not dispatch the write itself.
async function reviewDocPhase(doc, workItem, opts) {
  opts = opts || {}
  const runId = opts.runId || `review-${doc}-${workItem}`
  const lease = opts.lease || undefined
  const existing = await readGate(workItem, doc)
  if (existing === 'passed') {
    // cursor-lost re-entry guard (gate written, tail persist failed): never re-run the panel and
    // risk overwriting a correct passed (FR-8 passed-gate skip).
    return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' }
  }
  const runDir = runDirFor(workItem, `review-${doc}`)
  const docPath = docPathFor(workItem, doc)
  // fold 2 (#141; #211 decision shape): ONE gather leaf does the run-dir mkdir + deferred-set seed +
  // resume DECISION + round-1 plan + entry coverage read (no records ride up). Seed runtimeDeferred
  // from it and hand it to the panel as `preloaded`. A gather transport failure -> null: fall back to
  // a plain mkdir and let the panel read its own entry state (correct, just unfolded).
  const setup = await gatherReviewSetup({
    runDir, reviewerSet: DOC_REVIEWERS, context: { workItem, docType: doc, docPath },
    legKind: { panel: true, code: false }, ioApi: io(),
  })
  if (!setup) await io().mkdirp(runDir)
  const deferred = new Map()
  if (setup) for (const id of Object.keys(setup.deferredSet || {})) deferred.set(id, setup.deferredSet[id])
  const verdict = await runReviewDocPanel({
    workItem,
    docType: doc,
    docPath,
    runDir,
    runtimeDeferred: deferred,
    preloaded: setup || undefined,
  })
  await saveRoundStateBestEffort(
    workItem,
    doc,
    (verdict && verdict.round) || 1,
    Array.from(deferred.entries()).map(([id, severity]) => ({ id, severity })),
    runDir,
  )
  // persist the #104 terminal record so the front-half boundary can embed its readout (FR-7).
  // The record is composed PYTHON-SIDE from the run's on-disk state (round-records.json +
  // review-telemetry.json); only the small verdict scalars ride inline (self-verified), so the
  // ~14KB evidence-bodied verdict never crosses a courier writeFile — the payload-stage-failed
  // park class (live 2026-07-02, run wf_94c879e0-747). Overwrite is finalize's job: the record
  // is durable for crash-resume, not append-only (the lease serializes live sessions).
  // gateForTerminal is the in-process JS twin (no agent dispatch).
  const gate = gateForTerminal(verdict && verdict.terminal)
  // The set-gate fence hash is computed PYTHON-SIDE at write time ('current' sentinel), never
  // from a courier read: in the sandbox a readText of a missing/odd file answers PROSE (live
  // 2026-07-02, 4 consecutive runs), and contentHash(prose) poisons the fence into a permanent
  // 'stale' park. The runtime makes no decision between its old re-read and the write, so the
  // sentinel loses only same-window concurrent-edit detection (the lease excludes that) —
  // and definition_doc.py resolves + hashes the SAME file it edits (doc-dir aware), so no
  // runtime-resolved hash can disagree with the write target.
  const reviewedHash = 'current'
  // #118 "Every phase" tail: gate + journal + checkpoint land in ONE 'save phase progress' leaf,
  // dispatched by runPhases' tail with the REAL step index — NOT persisted here (the old
  // step:-1 pre-persist plus runPhases' journal/cursor writes was the FR-6 double-journal, and
  // the transient step:-1 checkpoint could regress a crash-resume to phase 0). This phase hands
  // the tail its set-gate side-effect command + journal payload; a failed persist parks there
  // (UFR-5 — the run never advances on an un-recorded gate).
  const leaseArg = lease ? ` --lease ${shq(lease)}` : ''
  const sideEffectCmd =
    `python3 ${libPath('definition_doc.py')} set-gate --doc ${shq(doc)} ` +
    `--work-item ${shq(workItem)} --review ${shq(gate)} --root "$(git rev-parse --show-toplevel)" ` +
    `--expected-hash ${shq(reviewedHash)} --run-id ${shq(runId)}${leaseArg}`
  const persist = {
    sideEffectCmd,
    journalPayload: { phase: `review-${doc}`, gate, confidence: 'high', assumptions: [], runId, lease },
  }
  const recPath = `${runDir}/terminal-record.json`
  const recWrite = await writeTerminalRecord(recPath, verdict || {}, { runId, lease, runDir })
  if (verdict && verdict.reason === 'round-memory-unreadable') {
    return {
      phaseResult: {
        confidence: 'low',
        assumptions: ['round-memory-unreadable'],
        parkReason: 'round-memory-unreadable',
      },
      gate: null,
      runtimeDeferredIds: Array.from(deferred.keys()),
    }
  }
  if (!recWrite.ok) {
    if (gate === 'passed') {
      return {
        phaseResult: { confidence: 'high', assumptions: [] },
        gate,
        persist,
        runtimeDeferredIds: Array.from(deferred.keys()),
      }
    }
    return {
      phaseResult: {
        confidence: 'low',
        assumptions: [`terminal-record.json ${recWrite.reason || 'write-failed'} for ${doc}`],
        parkReason: `terminal-record.json ${recWrite.reason || 'write-failed'} for ${doc}`,
      },
      gate,
      runtimeDeferredIds: Array.from(deferred.keys()),
    }
  }
  // #212: on a non-passed gate, name the terminal + the panel's honest reason on parkDetail so the
  // workflow park survives the phase-layer flatten (phase_step threads it into the changes-requested
  // reason). A passed gate proceeds — no park detail.
  const phaseResult = { confidence: 'high', assumptions: [] }
  if (gate !== 'passed') {
    phaseResult.parkDetail = `${(verdict && verdict.terminal) || 'cannot-certify'}: ${(verdict && verdict.reason) || 'review not certified'}`
  }
  return {
    phaseResult,
    gate,
    persist,
    runtimeDeferredIds: Array.from(deferred.keys()),
  }
}

// gateForTerminal: pure in-process JS twin. No agent dispatch.
function gateForTerminal(terminal) {
  return frontHalfTwin.gateForTerminal(terminal || 'unknown')
}

// usableDraft: exec runs front_half_usable.py --emit-signals, which computes the verdict
// Python-side at the IO boundary (calls front_half.is_usable_draft) and returns a small
// {usable, recorded, expected, missing_sections, placeholder} signal — the large doc text
// never crosses the cheapest-model pipe (live-surfaced large-payload-transport limit).
// The frontHalfTwin.isUsableDraft JS twin stays for parity testing only; it is no longer
// called here on the live doc text.
// Layer 2a: the why-signal fields (missing_sections, placeholder) are forwarded so the
// produce repair loop (producePhase) can craft a targeted gap hint for re-prompting.
async function usableDraft(workItem, doc) {
  const results = await exec([
    `python3 ${libPath('front_half_usable.py')} --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --root "$(git rev-parse --show-toplevel)" --emit-signals`,
  ], 'check draft')
  let signals = null
  try { signals = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  if (!signals) return { usable: false }   // IO failure -> fail closed (re-produce)
  return {
    usable: !!signals.usable,
    expected: signals.expected || '',
    missing_sections: Array.isArray(signals.missing_sections) ? signals.missing_sections : [],
    placeholder: !!signals.placeholder,
  }
}

// authorModel: pure in-process JS twin. Reads overrides from globalThis.__SR_OVERRIDES (set by
// Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS.author = 'opus').
// The plan doc resolves the split `author-plan` role (own override, e.g. fable, else exactly
// `author`); tasks stays on `author` — plan authoring alone can be raised without moving tasks.
function authorModel(doc) {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  return modelTierTwin.resolveModel(doc === 'plan' ? 'author-plan' : 'author', overrides, null)
}

// #38: read globalThis.__SR_ENGINE_PREFS (planted once at startup — see showrunner()'s startup pipe).
// Absent/malformed -> the safe degenerate default (both roles on claude, no effort overrides).
function _enginePrefs() {
  const p = (typeof globalThis !== 'undefined' && globalThis.__SR_ENGINE_PREFS) || null
  return (p && typeof p === 'object') ? p : { reviewer: 'claude', implementation: 'claude', effort: {} }
}

// FR-9 effort overrides: the role_kind-keyed effort sub-map INSIDE __SR_ENGINE_PREFS (NOT the model-tier
// __SR_OVERRIDES map, which is keyed by role->model). resolveEffort reads this; absent -> null -> default.
function _effortOverrides() {
  const p = _enginePrefs()
  return (p && p.effort && typeof p.effort === 'object' && !Array.isArray(p.effort)) ? p.effort : null
}
// the durable per-work-item NOTIFY ledger (next to the docs — run-local state, never committed).
// Rides docDirFor, so it lands in the project store for an out-of-repo-calibrated project.
function notifyLedgerFor(workItem) { return `${docDirFor(workItem)}/.notify.json` }
// appendNotify: IO accumulator write via exec (not cmdRunner). Returns false on failed durable write.
async function appendNotify(workItem, entries) {
  const results = await exec([
    `python3 ${libPath('front_half.py')} append-notify ` +
    `--ledger ${shq(notifyLedgerFor(workItem))} --entries ${shq(JSON.stringify(entries || []))}`,
  ], 'append notify')
  let out = null
  try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  return !!(out && out.ok)   // false on a failed durable write — the caller must not silently lose it
}

module.exports.producePhase = producePhase
module.exports.reviewDocPhase = reviewDocPhase
module.exports.notifyLedgerFor = notifyLedgerFor
module.exports.docPathFor = docPathFor

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
  // Overwrite mode with NO lease: this envelope is composed fresh from the durable per-phase
  // records on every boundary pass, so last-writer-wins between duplicate runs is accepted —
  // both writers derive near-identical content from the same records (see fenced_json.js).
  const outPath = `/tmp/showrunner-${workItem}-fronthalf-outcome.json`
  const runId = `fronthalf-${workItem}`
  const outcomeWrite = await fencedJsonWrite(outPath, outcome, { overwrite: true, runId })
  let recordOk = !!outcomeWrite.ok

  // exec-backed renderReadout: writes the record to a temp file and execs loop_readout.py --record.
  // Mirrors how renderAndPostReadout runs loop_readout.py (line ~896). Returns the stdout text.
  // Used only when recordOk (the write seam is available); if recordOk is false the loop body is
  // skipped (phase_records still embeds headers with no readout text — tolerable since UFR-6 fires).
  async function renderReadout(record) {
    const recPath = `/tmp/showrunner-${workItem}-fronthalf-readout-tmp.json`
    try { await io().writeFile(recPath, JSON.stringify(record || {})) } catch (_) { return '' }
    // dumb-pipe render via the courier (pinned cheapest + one-shot retry; rootedCommand = FR-5).
    try {
      const text = await courier.runCourierText(
        'readout',
        `python3 ${libPath('loop_readout.py')} --record ${shq(recPath)}`)
      return typeof text === 'string' ? text : ''
    } catch (_e) {
      return ''
    }
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
  var root = checkoutRoot()
  if (!root) return cmd
  var trimmed = String(cmd).trimLeft ? String(cmd).trimLeft() : String(cmd).replace(/^\s+/, '')
  if (trimmed.startsWith('cd ')) return cmd   // already rooted (inWorktree or similar) — leave alone
  return 'cd ' + shq(root) + ' && ' + cmd
}

// checkoutRoot: the acquire-authority repo root threaded from recover_entry's snapshot (UFR-10).
// Planted on globalThis.__SR_ROOT after reconcile; bundle ENTRY may preset it from args.root.
function checkoutRoot(explicit) {
  if (explicit && String(explicit).trim()) return String(explicit)
  const r = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT)
    ? String(globalThis.__SR_ROOT) : null
  return (r && r.trim()) ? r : null
}

function fenceCliCmd(workItem, generation, root, extra) {
  const r = checkoutRoot(root)
  if (!r) return null
  return `python3 ${libPath('fence_cli.py')} --work-item ${shq(workItem)} ` +
    `--generation ${shq(String(generation))} --root ${shq(r)}${extra || ''}`
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
// `label` is a purely-cosmetic display purpose (e.g. 'read gate', 'prepare build') so the progress
// view names each leaf by what it does; it defaults to 'exec'. Dumb-pipe routing rides the structural
// `courier: true` marker (the bundle preamble's __isDumb pins cheapest off it, independent of the
// label), so a descriptive label never loosens the cheapest-model contract.
// FR-8 sandbox-safe: no fs, no child_process, no time/random globals, no process/bare-global refs.
async function exec(commands, label) {
  var cmds = commands || []
  const cmdList = cmds.map(function(c, i) { return (i + 1) + '. ' + selfContained(c) }).join('\n')
  const prompt =
    'Run each of the following commands in order using the Bash tool. ' +
    'Return ONLY a raw JSON array and NOTHING else — no prose, no explanation, no markdown fences; ' +
    'your entire response must be valid for JSON.parse. ' +
    'Each element: {"index":<0-based>,"ok":<true|false>,"stdout":<string>}. ' +
    'The "stdout" value MUST be the command\'s COMPLETE raw stdout, copied verbatim as a single JSON ' +
    'string (JSON-escape quotes/newlines as needed). Do NOT parse it, extract a field from it, summarize ' +
    'it, pretty-print it, or change it in any way — even when the stdout is itself a JSON object, return ' +
    'that object byte-for-byte as the string value, never a parsed/abbreviated version of it.\n\n' +
    cmdList
  const o = { model: cheapestModel(), label: label || 'exec', courier: true }
  const out = await globalThis.agent(prompt, o)
  return _parseExecResult(out, cmds.length)
}

// execJson/execText: run ONE command via the courier dumb-pipe (pinned to the cheapest model by the
// bundle preamble via the `courier: true` marker) and parse its stdout. Mirrors build_phase.js's
// helpers: the courier retries ONCE on a dropped/garbled stdout (FR-8), returns null after the retry
// so the caller fails closed, and returns a parseable {"ok":false} (a REAL failure) as-is without
// retry. `label` is the cosmetic display purpose (defaults to 'exec'); routing rides `courier: true`.
async function execJson(cmd, label) {
  try {
    return await courier.runCourierJson(label || 'exec', cmd)
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}
async function execText(cmd, label) {
  try {
    return (await courier.runCourierText(label || 'exec', cmd)).trim()
  } catch (e) {
    if (e instanceof courier.CourierTransportError) return null
    throw e
  }
}

// persistPhase: one 'save phase progress' courier — the optional side-effect command chained (&&)
// before phase_progress_entry.py save, which writes journal + checkpoint and read-back-confirms both.
// Persist order (FR-4): side-effect first (when present), then journal, then checkpoint (cursor last).
// Every interpolated non-constant arg is shq()-quoted.
// opts.journalOnly (#118 "save phase progress" on a PARK): record the journal entry (+ chained
// side-effect) durably but leave the checkpoint cursor untouched — a parked phase did not complete,
// so advancing lastGoodStep would make the resume skip it. Still ONE courier leaf.
// Returns {ok: boolean} — ok is false if any command in the batch reported failure.
async function persistPhase(workItem, opts) {
  opts = opts || {}
  const sideEffectCmd = opts.sideEffectCmd || null
  const record = opts.record || opts.journalPayload || {}
  const step = opts.step
  const phase = opts.phase
  const journalOnly = !!opts.journalOnly
  const side = journalOnly ? null : (opts.sideEffect || null)
  const sideArg = side ? ` --json ${shq(JSON.stringify(side))}` : ''
  const joArg = journalOnly ? ' --journal-only' : ''
  // #130: fold this phase's cost telemetry into the SAME durable write (no new leaf — #118). The
  // phase_cost event is written best-effort inside phase_progress_entry.py, only when the phase
  // record is freshly applied (so a resume never double-counts). Absent when there's nothing to
  // record (no dispatches, unmeasured) or when the caller did not opt in (recordCost).
  const costBody = opts.recordCost ? phaseCostPayload(phase) : null
  const costArg = costBody ? ` --cost-payload ${shq(JSON.stringify(costBody))}` : ''
  // #130: on a park (journalOnly), fold a `parked` terminal marker into this same save so the run is
  // classifiable as parked (parkFromPhases journals nothing) — carrying its already-folded cost.
  const parkArg = (journalOnly && opts.parkReason) ? ` --terminal-park ${shq(String(opts.parkReason))}` : ''
  const saveCmd =
    `python3 ${libPath('phase_progress_entry.py')} save --work-item ${shq(workItem)} ` +
    `--step ${shq(String(step))} --phase ${shq(phase)} --payload ${shq(JSON.stringify(record))}${sideArg}${joArg}${costArg}${parkArg}`
  const cmd = sideEffectCmd ? `${sideEffectCmd} && ${saveCmd}` : saveCmd
  // #170: the SECOND (and last) libRoot probe site — the once-per-phase durable write covers the long
  // back half, where a plugin-cache eviction after startup would otherwise surface as a raw python
  // file-not-found. In dev/dogfood (relative libRoot) libRootProbe() is empty, so this is byte-identical.
  const probedCmd = `${libRootProbe()}${cmd}`
  const required = journalOnly
    ? ['ok', 'journal_confirmed']
    : ['ok', 'journal_confirmed', 'checkpoint_confirmed']
  try {
    const res = await courier.runCourierMarkedJson(
      'save phase progress',
      probedCmd,
      { require: required, retryRealFailure: false },
    )
    // Map the libRoot-missing marker to the SAME named park reason reconcile uses, before the
    // save-result read-back check — the back half fails closed with a descriptive cause, not a
    // generic read-back mismatch.
    if (res && typeof res.reason === 'string' && res.reason.indexOf(MISSING_MARKER) >= 0) {
      return { ok: false, error: 'spine code root missing (libRoot)' }
    }
    const confirmed = res && res.ok && res.journal_confirmed &&
      (journalOnly || res.checkpoint_confirmed)
    return confirmed
      ? { ok: true, recovered: false }
      : { ok: false, error: (res && res.reason) || 'phase progress read-back mismatch' }
  } catch (e) {
    if (e instanceof courier.CourierTransportError) {
      return { ok: false, error: 'phase progress save transport failed (courier): ' + e.reason }
    }
    return { ok: false, error: 'phase progress save transport failed (courier)' }
  }
}

// #130: the phase_cost payload for a completed phase — the proxy dispatch counts (× resolved model)
// + the budget-derived output-token delta. Folded into the phase's ONE durable write (the save leaf
// for a normal phase, the readout_post hand-back for ship) so it rides no new courier leaf (#118).
// Returns null when there is nothing worth recording (no dispatches, unmeasured).
function phaseCostPayload(phase) {
  try {
    const body = costMeter.take(phase)
    return costMeter.isEmpty(body) ? null : body
  } catch (_e) { return null }
}

function inWorktree(cmd, worktree) {
  return worktree ? `cd ${shq(worktree)} && ${cmd}` : cmd
}
function targetCommandPrompt(prompt, worktree) {
  if (!worktree || typeof prompt !== 'string') return prompt
  if (!prompt.startsWith('Run exactly this')) return prompt
  // The courier shape is "Run exactly this …:\n\n<cmd>"; split on the FIRST blank-line boundary
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
// #118 residual: ONLY the test-pilot per-op leaves (testPilotDeps' cli/jsonCommand) still ride this
// StructuredOutput pipe — every spine site is ported to courier_exec/exec. It is a dumb pipe, so it
// is pinned to the cheapest model here AND marked courier:true for the bundle preamble's
// unconditional pin (the live 2026-07-02 run showed unmarked cmdRunner leaves inheriting the
// session model at ~41k tokens per command echo).
// FR-5 (cwd-rooting): wrap the command with selfContained() so the courier leaf always runs from
// the repo root when globalThis.__SR_ROOT is set. selfContained is a no-op when __SR_ROOT is unset
// (smoke/test backward-compat) and skips commands already starting with `cd ` (no double-cd).
async function cmdRunner(cmd, { schema, label }) {
  // The command prints ONE JSON object to stdout. The leaf must map each top-level key of that
  // object to the SAME-named StructuredOutput field — NOT stuff the whole JSON text into one field
  // (a live-only derailment: that is schema-valid-but-wrong, e.g. action="{...the whole blob...}",
  // which then mis-routes the deciders). Spell the mapping out so the leaf can't collapse it.
  return agent(
    `Use the Bash tool to run exactly this command. It prints ONE JSON object to stdout. Return that ` +
    `object via StructuredOutput by copying each of its top-level keys to the same-named output field, ` +
    `values exactly as printed. Do NOT put the whole JSON into a single field, do NOT stringify or nest ` +
    `it, and do NOT add commentary or extra fields:\n\n${selfContained(cmd)}`,
    { label: label || 'lib', schema, courier: true, model: cheapestModel() },
  )
}

// Reconcile-from-store: exec gathers the world snapshot via recover_entry.py --snapshot
// (IO: store, enforcer, lease, checkpoint, world read), then the JS twin decides (pure, in-process).
// generation is threaded from the Python snapshot (UFR-10).
async function reconcile(workItem) {
  const preRoot = checkoutRoot()
  const rootFlag = preRoot ? ` --root ${shq(preRoot)}` : ''
  const snapCmd =
    `${libRootProbe()}python3 ${libPath('recover_entry.py')} --work-item ${shq(workItem)} --snapshot${rootFlag}`
  let _snapStdout = ''
  try {
    _snapStdout = await courier.runCourierMarkedText('gather snapshot', snapCmd)
  } catch (_e) {
    return { action: 'park_gate', reason: 'recover_entry snapshot failed (IO error)', generation: null }
  }
  // #170 fail-closed probe: an ABSOLUTE spine code root that vanished mid-run (e.g. plugin-cache
  // eviction) short-circuits the compose to MISSING_MARKER instead of a file-not-found python error —
  // park with a NAMED reason so the readout says exactly what's wrong. Relative (dev) libRoot never
  // emits the marker.
  if (_snapStdout.indexOf(MISSING_MARKER) >= 0) {
    return { action: 'park_gate', reason: 'spine code root missing (libRoot)', generation: null }
  }
  let snap = null
  try { snap = JSON.parse(_snapStdout) } catch (_) {}
  if (!snap) {
    // A failed/empty snapshot (IO error, store unusable before lease) -> fail closed.
    return { action: 'park_gate', reason: 'recover_entry snapshot failed (IO error)', generation: null }
  }
  // recover_entry emits an early_park when the cursor guard triggers (before snapshot).
  // In that case the snapshot fields are absent and {action, reason, generation} come directly.
  if (snap.action) return snap   // early park (cursor_gate or store/enforcer/lease failure)
  if (!snap.root || typeof snap.root !== 'string' || !String(snap.root).trim()) {
    return {
      action: 'park_gate',
      reason: 'recover_entry snapshot missing checkout root',
      generation: snap.generation ?? null,
    }
  }
  if (typeof globalThis !== 'undefined') globalThis.__SR_ROOT = String(snap.root)
  const decision = recoverTwin.reconcile(snap.checkpoint, snap.world)
  return Object.assign({}, decision, { generation: snap.generation, root: snap.root })
}

// releaseLease: CAS-release the work-item ref-lease at EVERY terminal exit of the run — parks
// and hand-backs alike — so a relaunch never waits out DEFAULT_TTL (live 2026-07-02: each park
// cost 30 minutes). Only fires when THIS run acquired (generation threaded from reconcile; a
// lease-held park carries none). Best-effort: a failed release leaves the TTL as the backstop,
// and the generation precondition means a superseded holder's lease is never deleted.
// This is a state-changing single command, so it rides a DEDICATED hardened courier (NOT the
// permissive batch exec): a strict prompt forbidding extra commands + require(['ok']) so a
// freestyling courier's chatty answer is rejected and retried rather than accepted. Live
// 2026-07-02 the park-path release rode the batch exec and the courier improvised ~10 unscripted
// Bash calls, "manually" releasing the lease itself — the misbehaving-courier class #138 hardened
// for WRITES, now closed for this exec leaf too.
async function releaseLease(workItem, generation, root) {
  if (generation == null) return
  const cmd = fenceCliCmd(workItem, generation, root, ' --release')
  if (!cmd) return
  try {
    await courier.runCourierJson(
      'release lease',
      cmd,
      { require: ['ok'], retryRealFailure: false, strict: true },
    )
  } catch (_) { /* TTL backstop */ }
}

// Park from runPhases: persist the journal (caller already did) then release the lease before
// returning — same release-on-park path reconcile/startup use. Belt-and-braces with showrunner()'s
// finally (a second release no-ops when the lease is already gone).
async function parkFromPhases(workItem, generation, root, phase, reason) {
  await releaseLease(workItem, generation, root)
  return { outcome: 'parked', phase, reason }
}

// #25 quick discovery — the showrunner's INTAKE contract. Discovery (the architect session) always
// produces the run's input artifact; the ROUTE decides which one: full = spec (today), quick = the
// tasks doc, built from `workhorse` on (plan/review-plan/tasks/review-tasks skipped). This is the
// spine leg only — PR 2 owns the-architect's route recommendation, quick-mode task authoring, the
// alignment probe, and the gate wiring that launches a quick run.
//
// resolveIntake: PURE decider over the startup facts (spec/tasks presence + gates) and the launch's
// explicit route (globalThis.__SR_ROUTE, threaded from args.route). Returns the route plus, for the
// quick route, either the tasks gate to check or a fail-closed REFUSE — a missing or malformed tasks
// artifact never silently falls back to (or past) the full path. Byte-identical to today on the full
// route: an absent explicit route with no tasks artifact resolves to 'full', so the spec-gate startup
// path is unchanged.
//   facts:    { spec_present, tasks_present, spec_gate, tasks_gate } (from readStartupState)
//   explicit: the launch-declared route ('quick' | 'full' | null)
//   returns:  { route:'full' }
//           | { route:'quick', action:'gate', gate:<tasks_gate> }
//           | { route:<declared|'quick'>, action:'refuse', reason:<why> }
function resolveIntake(facts, explicit) {
  facts = facts || {}
  const specPresent = !!facts.spec_present
  const tasksPresent = !!facts.tasks_present
  // The route the on-disk artifacts SUPPORT: spec present ⇒ full (spec-anchored); else a tasks doc
  // alone ⇒ quick; else neither ⇒ null (no input artifact resolved yet).
  const derived = specPresent ? 'full' : (tasksPresent ? 'quick' : null)
  const declared = (explicit === 'quick' || explicit === 'full') ? explicit : null
  // A DECLARED route that conflicts with what the artifacts support is a fail-closed REFUSE — never
  // silently overridden in EITHER direction. Declared 'quick' over a present spec would run the full
  // route unattended (regenerating tasks.md over the architect's quick doc and building off a
  // maybe-stale spec); declared 'full' over a spec-less tasks doc would skip the exact front half the
  // launch asked for. Both are fail-open against the launch's stated intent — refuse and name what to
  // reconcile, rather than pick a route the owner did not choose.
  if (declared && derived && declared !== derived) {
    const artifact = derived === 'full'
      ? 'a spec is present on disk (the full route)'
      : 'only a tasks doc — no spec — is present on disk (the quick route)'
    return { route: declared, action: 'refuse',
      reason: `launch declared the '${declared}' route but ${artifact} — refusing to launch ` +
        `(fail-closed intake); reconcile the route with the on-disk artifact before relaunching` }
  }
  // No conflict below (the declared route agrees with the artifacts, or nothing was declared).
  // Spec present ⇒ full route (spec-anchored, byte-identical to pre-#25).
  if (specPresent) return { route: 'full' }
  const declaredQuick = explicit === 'quick'
  if (!tasksPresent) {
    // No tasks artifact. A launch that DECLARED quick must refuse (fail-closed intake — never fall
    // back to the full path, and never fall past tasks into an empty build). Otherwise this is the
    // pre-#25 no-spec world: the full route parks at the spec startup gate (unreadable), unchanged.
    if (declaredQuick) {
      return { route: 'quick', action: 'refuse',
        reason: 'quick-route launch declared, but no tasks artifact was found where the tasks phase writes it ' +
          '— refusing to launch (fail-closed intake), never falling back to the full path' }
    }
    return { route: 'full' }
  }
  // Tasks artifact present, no spec ⇒ quick route. Validate it is well-formed BEFORE gating: a doc
  // whose review gate can't be parsed (malformed frontmatter, missing gates line, or unreadable) is
  // a fail-closed refuse — the run never builds off an artifact it can't verify the owner approved.
  const g = facts.tasks_gate
  if (g == null || g === 'malformed' || g === 'unreadable') {
    return { route: 'quick', action: 'refuse',
      reason: 'quick-route tasks artifact is malformed or missing its review gate (' + String(g) + ') ' +
        '— refusing to launch (fail-closed intake)' }
  }
  return { route: 'quick', action: 'gate', gate: g }
}

// #25 quick discovery — record, DURABLY and honestly, the front-half phases the quick route skips so
// they are never silently absent from the run's audit trail (journal) or its live readout (run_watch
// renders the phases_skipped event). A structured, non-secret payload (fixed phase names + route),
// written AS-IS via the generic journal_entry.py seam. Returns false on a failed durable write so the
// caller fails closed — an unrecorded skip must not proceed (the run's durable-write discipline).
async function recordSkippedPhases(workItem, skipped, entryPhase) {
  const payload = { route: 'quick', skipped: skipped || [], entryPhase: entryPhase || 'workhorse' }
  const out = await execJson(
    `python3 ${libPath('journal_entry.py')} --work-item ${shq(workItem)} ` +
    `--event-type phases_skipped --payload ${shq(JSON.stringify(payload))}`,
    'record skipped phases')
  return !!(out && out.ok)
}

async function showrunner({ workItem }) {
  // Progress-group the pre-loop leaves (reconcile / spec-gate / startup) under 'startup'; runPhases
  // re-stamps this per phase. Read by the bundle's agent wrapper (globalThis.__SR_PHASE).
  if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = 'startup'
  const r = await reconcile(workItem)
  if (r.action === 'park_gate' || r.action === 'gate') {
    await releaseLease(workItem, r.generation, r.root)
    return { outcome: 'parked', phase: 'reconcile', reason: r.reason || r.action }
  }
  // UFR-1 / #25 intake: refuse to run unless the route's input artifact is approved. resolveIntake
  // (pure) picks the route from the durable artifact state (spec present ⇒ full, else tasks ⇒ quick)
  // and the launch-declared route; on the quick route it either hands back the tasks gate to check or
  // fail-closes (missing/malformed tasks artifact ⇒ refuse, never a silent fall-back to/past full).
  const startupFacts = await readStartupState(workItem)
  const _explicitRoute = (typeof globalThis !== 'undefined' && globalThis.__SR_ROUTE) || null
  const intake = resolveIntake(startupFacts || {}, _explicitRoute)
  const route = intake.route
  // A fail-closed refuse parks regardless of which route it carries — a declared-vs-artifact conflict
  // refuses under the DECLARED route (which may be 'full'), so this is not gated on route === 'quick'.
  if (intake.action === 'refuse') {
    await releaseLease(workItem, r.generation, r.root)
    return { outcome: 'parked', phase: 'startup', reason: intake.reason }
  }
  // Full route ⇒ the spec gate (byte-identical to pre-#25); quick route ⇒ the owner-approved tasks
  // gate. The startup decider (phase_step) proceeds only on a `passed` gate; anything else parks.
  const startupGate = route === 'quick' ? intake.gate : ((startupFacts && startupFacts.spec_gate) || 'unreadable')
  const startup = await phaseStep({ confidence: 'high', assumptions: [] }, startupGate)
  if (startup.action !== 'proceed') {
    await releaseLease(workItem, r.generation, r.root)
    return { outcome: 'parked', phase: 'startup', reason: startup.reason }
  }
  const _ovMap = (startupFacts && startupFacts.model_overrides) || {}
  // Config-derived model-tier map (the resolve-live baseline). The frozen-snapshot fork below
  // (FR-8) merges the frozen pins over this before it is planted on globalThis.
  const _ovConfig = (_ovMap && typeof _ovMap === 'object' && !Array.isArray(_ovMap)) ? _ovMap : {}
  // Plant the startup-resolved, storage-mode-aware docs dir for docDirFor (docPathFor /
  // notifyLedgerFor). Best-effort: an absent/empty doc_dir (resolution failed, or an older canned
  // response) plants nothing and the legacy in-repo fallback stays in force.
  const _docDir = (startupFacts && typeof startupFacts.doc_dir === 'string' && startupFacts.doc_dir) || null
  if (_docDir && typeof globalThis !== 'undefined') {
    globalThis.__SR_DOC_DIRS = Object.assign({}, globalThis.__SR_DOC_DIRS, { [workItem]: _docDir })
  }
  // #38 engine preferences, #118 startup fold: the per-role engine prefs ride the SAME
  // 'read startup state' gather (previously a third startup courier leaf, engine_pref_load.py —
  // the one the #118 matrix does not allow: startup is the deliberately-TWO-leaf stretch).
  // Fail-safe: an absent/malformed (or courier-stringified) value yields both-"claude" + empty
  // effort map, so the review/build leaves take the byte-unchanged agent() path.
  const _epParsed = _coerceObj((startupFacts && startupFacts.engine_prefs) || null)
  let _epMap = { reviewer: 'claude', implementation: 'claude', planAuthor: 'claude', effort: {} }
  if (_epParsed && typeof _epParsed === 'object' && !Array.isArray(_epParsed)) {
    // Carry the whole object — reviewer/implementation/planAuthor AND the FR-9 effort sub-map
    // (keyed by role_kind), so resolveEffort can source the owner's effort override from
    // __SR_ENGINE_PREFS.effort (NOT from the model-tier __SR_OVERRIDES map, which is keyed by
    // role->model).
    _epMap = {
      reviewer: _epParsed.reviewer || 'claude',
      implementation: _epParsed.implementation || 'claude',
      planAuthor: _epParsed.planAuthor || 'claude',
      effort: (_epParsed.effort && typeof _epParsed.effort === 'object' && !Array.isArray(_epParsed.effort)) ? _epParsed.effort : {},
    }
  }
  // FR-8 / UFR-2 (second clause): the pin-or-resolve fork. The frozen preflight-readout snapshot for
  // this work-item (read off the control-plane store on the SAME startup gather — no new leaf) pins
  // each role's confirmed engine/model/effort; mergeFrozenSnapshot folds those pins over the
  // config-derived maps (a pinned role wins; an unpinned role keeps the resolve-live value). When no
  // snapshot is present (the rollback state), the merge returns the config-derived maps unchanged, so
  // the seed is byte-equivalent to pre-readout. Both globals are planted from the merged result.
  const _frozenSnapshot = _coerceObj((startupFacts && startupFacts.frozen_snapshot) || null)
  const _merged = mergeFrozenSnapshot(
    (_frozenSnapshot && typeof _frozenSnapshot === 'object' && !Array.isArray(_frozenSnapshot)) ? _frozenSnapshot : null,
    _ovConfig, _epMap)
  if (typeof globalThis !== 'undefined') {
    globalThis.__SR_OVERRIDES = _merged.overrides
    globalThis.__SR_ENGINE_PREFS = _merged.enginePrefs
  }
  // 'continue' (from_step) or 'world_derive' (from_step 0) -> run the phase loop (Task 8).
  // lastGoodStep = the last *completed* phase index; resume at the next one (no re-run, FR-3).
  // #25: a FRESH quick run starts at `workhorse` (plan/review-plan/tasks/review-tasks skipped — the
  // tasks doc IS the input artifact). A resume rides the durable cursor unchanged (it already points
  // past the skipped phases, so route need not survive resume for the cursor); the full route's fresh
  // start stays 0 (byte-identical).
  const _resuming = r.action === 'continue' && r.from_step != null
  const _workhorseStep = PHASES.indexOf('workhorse')
  const fromStep = _resuming
    ? Number(r.from_step) + 1
    : (route === 'quick' ? _workhorseStep : 0)
  // UFR-10 (#107): thread the lease generation recover_entry acquired into the workhorse build phase,
  // so the build can fence (renew-then-fence) at every branch-mutating boundary.
  const deps = { gateRead: gateReadFor(workItem), generation: r.generation, root: r.root }
  // FR-7 (#108)/FR-4 (#102)/Task-13a (#115): native front-half wiring. Three opt-in selectors
  // share the native authoring deps but differ on the boundary park:
  //   - env SUPERHEROES_FRONT_HALF=native: direct-node/smoke path (procEnv); keeps boundary park.
  //   - globalThis.SUPERHEROES_FRONT_HALF_NATIVE: Workflow-sandbox path (set by the ENTRY from
  //     args.frontHalf==='native'); procEnv is unavailable in the sandbox (FR-8), so the ENTRY
  //     injects this globalThis flag instead.
  //   - SUPERHEROES_BUNDLE_FULL_RUN true (preamble default + full-run ENTRY): no boundary park,
  //     proceeds into the back-half.
  // #25: the quick route skips the whole front half (fromStep starts at `workhorse`), so the native
  // authoring/boundary deps are irrelevant — and the boundary MUST NOT be wired, or it would fire at
  // `workhorse` and park a quick run immediately. The full route wires them exactly as pre-#25.
  const fullRun = !!globalThis.SUPERHEROES_BUNDLE_FULL_RUN
  const frontHalfNative = procEnv('SUPERHEROES_FRONT_HALF') === 'native' || !!globalThis.SUPERHEROES_FRONT_HALF_NATIVE
  if (route !== 'quick' && (frontHalfNative || fullRun)) {
    deps.produce = producePhase                  // plan / tasks authoring (author-only)
    deps.reviewDoc = reviewDocPhase              // review-plan / review-tasks -> panel-doc leg
    if (!fullRun) deps.frontHalfBoundary = frontHalfBoundary   // front-half-only keeps the boundary park
  }
  // #25: on a FRESH quick entry, durably record the skipped front-half phases before entering the
  // loop — honest in the journal + readout, never silently absent. A failed durable write fails
  // closed (park at startup) rather than proceed on an unrecorded skip (the run's durable-write
  // discipline). A resume WITH a cursor does not re-record; a relaunch that re-enters the build from
  // scratch (parked before its first checkpoint, so no cursor) re-asserts the skip — honest and
  // harmless (no consumer counts these; run_readout reads the route from state, not the event tally).
  if (route === 'quick' && !_resuming) {
    const recorded = await recordSkippedPhases(workItem, PHASES.slice(0, _workhorseStep), 'workhorse')
    if (!recorded) {
      await releaseLease(workItem, r.generation, r.root)
      return { outcome: 'parked', phase: 'startup',
        reason: 'quick-route skipped-phase record could not be written durably — refusing to launch on an unrecorded skip' }
    }
  }
  try {
    return await runPhases(workItem, fromStep, deps)
  } finally {
    // Every runPhases exit is terminal for THIS run — phaseStep park, boundary park, or the
    // ship hand-back ('ready') — and a crash unwinds through here too. Release the lease so
    // the relaunch (or the owner's next run) never waits out the TTL.
    await releaseLease(workItem, r.generation, r.root)
  }
}

// readGate: IO read via exec (definition-doc on disk). A missing/malformed doc returns the
// 'unreadable' sentinel that phaseStep twin maps to park_unexpected_gate.
async function readGate(workItem, doc) {
  try {
    const results = await exec([
      `python3 ${libPath('definition_doc.py')} read-gate --doc ${shq(doc)} ` +
      `--work-item ${shq(workItem)} --root "$(git rev-parse --show-toplevel)" --json`,
    ], 'read gate')
    let out = null
    try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
    return (out && out.review) || 'unreadable'
  } catch (_) {
    return 'unreadable'
  }
}

// #221: the startup-state gather script, extracted so a Node smoke can run the REAL Python against an
// out-of-repo fixture (the canned-answer smokes were blind to the actual engine-prefs resolution —
// exactly how the load_engine_prefs store-base bug shipped). pyLibDir() is read at CALL time, so a
// smoke can point sys.path at the real lib dir by planting an absolute __SR_LIB before calling this.
function startupStateScript() {
  return [
    'import json, os, sys',
    `sys.path.insert(0, ${pyLibDir()})`,
    'import definition_doc, model_tier_overrides',
    'wi = sys.argv[1]',
    'root = sys.argv[2]',
    'spec_gate = "unreadable"',
    'doc_dir = ""',
    // #25 intake facts: which input artifact discovery produced decides the route (spec ⇒ full,
    // tasks ⇒ quick). Read presence + gate for BOTH from the SAME mode-aware, spec-anchored resolver
    // the tasks phase writes through, so the showrunner reads exactly the doc a quick run built off.
    'spec_present = False',
    'tasks_present = False',
    'tasks_gate = None',
    'try:',
    '    d = definition_doc.resolve_work_item_dir(wi, root=root, cwd=root)',
    '    doc_dir = d',   // the storage-mode-aware docs dir — planted on __SR_DOC_DIRS (docDirFor)
    '    spec_present = os.path.isfile(os.path.join(d, "spec.md"))',
    '    tasks_present = os.path.isfile(os.path.join(d, "tasks.md"))',
    '    if spec_present:',
    '        try:',
    '            spec_gate = definition_doc.read_gate(os.path.join(d, "spec.md"))',
    '        except Exception:',   // present but unparseable — same "unreadable" the full path saw pre-#25
    '            spec_gate = "unreadable"',
    '    if tasks_present:',
    '        try:',
    '            tasks_gate = definition_doc.read_gate(os.path.join(d, "tasks.md"))',
    '        except Exception:',   // present but its review gate can't be parsed — fail-closed marker
    '            tasks_gate = "malformed"',
    'except Exception:',
    '    pass',
    'try:',
    '    overrides = model_tier_overrides.load_overrides(None) or {}',
    'except Exception:',
    '    overrides = {}',
    'if not isinstance(overrides, dict):',
    '    overrides = {}',
    // #118 startup fold: the engine-prefs read (previously its own engine_pref_load.py exec leaf,
    // the third startup courier) rides the same gather. Fail-open like engine_pref_load.py: ANY
    // failure yields the degenerate both-'claude' map.
    '_ep_degenerate = {"reviewer": "claude", "implementation": "claude", "effort": {}}',
    'try:',
    '    import engine_pref',
    // #221: the SECOND arg is the store-base override (the ~/.claude/superheroes test seam), NOT the
    // repo root. `root` here IS the repo root — passing it resolves core.md to a nonexistent
    // <repo>/projects/<key>/config/core.md, so the deliberate fail-open silently degraded every run
    // to all-claude. Pass None so core.md resolves at the real store; the repo root rides `cwd` (arg 1).
    '    engine_prefs = engine_pref.load_engine_prefs(root, None)',
    '    if not isinstance(engine_prefs, dict):',
    '        engine_prefs = _ep_degenerate',
    'except Exception:',
    '    engine_prefs = _ep_degenerate',
    // FR-8: the frozen preflight-readout snapshot + accepted per-run overrides ride the SAME startup
    // gather (no new startup leaf — respect the #118 two-leaf budget). run_overrides.read is itself
    // fail-open; any failure here degrades to no-overrides/no-snapshot, so the run resolves live
    // exactly as it does pre-readout (the rollback state).
    'frozen_overrides = {}',
    'frozen_snapshot = None',
    'try:',
    '    import run_overrides',
    '    _rec = run_overrides.read(wi, root)',
    '    if isinstance(_rec, dict):',
    '        _fo = _rec.get("overrides")',
    '        frozen_overrides = _fo if isinstance(_fo, dict) else {}',
    '        frozen_snapshot = _rec.get("frozenSnapshot")',
    'except Exception:',
    '    frozen_overrides = {}',
    '    frozen_snapshot = None',
    'print(json.dumps({"ok": True, "spec_gate": spec_gate, "model_overrides": overrides, "doc_dir": doc_dir, "engine_prefs": engine_prefs, "spec_present": spec_present, "tasks_present": tasks_present, "tasks_gate": tasks_gate, "frozen_overrides": frozen_overrides, "frozen_snapshot": frozen_snapshot}))',
  ].join('\n')
}

async function readStartupState(workItem) {
  const script = startupStateScript()
  try {
    return await courier.runCourierJson(
      'read startup state',
      `python3 -c ${shq(script)} ${shq(workItem)} "$(git rev-parse --show-toplevel)"`,
      // doc_dir is REQUIRED: the Python side always emits it (empty string on a failed
      // resolution), so an absent field means a mangled courier response — retry rather than
      // silently planting nothing (which would mis-route the NOTIFY ledger + review doc paths
      // to the in-repo fallback on an out-of-repo-calibrated project mid-run).
      // engine_prefs is NOT required: an older canned response without it degrades to the safe
      // both-'claude' default (the same fail-open engine_pref_load.py had), never a retry.
      { require: ['ok', 'spec_gate', 'model_overrides', 'doc_dir'] },
    )
  } catch (_) {
    return { ok: true, spec_gate: 'unreadable', model_overrides: {}, doc_dir: '', engine_prefs: null }
  }
}

// Pure pin-or-resolve fork (FR-8, UFR-2 second clause). Fold the frozen snapshot's pinned per-role
// values over the config-derived model-tier + engine-pref maps: a role the snapshot PINS wins; a
// role it left unavailable (no pin) keeps the config-derived resolve-live value. Behavior-preserving
// when no snapshot is present — the config-derived maps are returned unchanged (the rollback state).
// The frozen snapshot rows carry {role, engine?, model?, effort?} (preflight_readout's row shape);
// only a row explicitly `overridden` seeds a pin, so a merely-rendered (non-overridden) row never
// silently pins the config-derived value it merely echoed.
function mergeFrozenSnapshot(frozen, baseOverrides, baseEnginePrefs) {
  const overrides = (baseOverrides && typeof baseOverrides === 'object' && !Array.isArray(baseOverrides))
    ? Object.assign({}, baseOverrides) : {}
  const src = (baseEnginePrefs && typeof baseEnginePrefs === 'object' && !Array.isArray(baseEnginePrefs))
    ? baseEnginePrefs : {}
  const enginePrefs = Object.assign({}, src)
  enginePrefs.effort = (src.effort && typeof src.effort === 'object' && !Array.isArray(src.effort))
    ? Object.assign({}, src.effort) : {}
  const rows = (frozen && Array.isArray(frozen.phases)) ? frozen.phases : []
  const _engineRoleKind = { review: 'reviewer', build: 'implementation', fix: 'implementation',
    'author-plan': 'planAuthor' }
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    if (!row.overridden) continue                 // only an accepted override seeds a pin
    const role = row.role
    // Pin the model onto the model-tier override map (resolveModel reads __SR_OVERRIDES[role]).
    if (typeof role === 'string' && typeof row.model === 'string' && row.model.trim()) {
      overrides[role] = row.model
    }
    // Pin the engine onto the engine-pref map (resolveEngine reads __SR_ENGINE_PREFS by role_key).
    const kind = row.kind === 'review-deep' ? 'review'
      : (row.kind === 'build' || row.kind === 'fix' || row.kind === 'review' ? row.kind : null)
    const epKey = kind && Object.prototype.hasOwnProperty.call(_engineRoleKind, kind)
      ? _engineRoleKind[kind] : null
    if (epKey && typeof row.engine === 'string' && row.engine.trim()) {
      enginePrefs[epKey] = row.engine
    }
    // Pin the effort onto the effort sub-map (resolveEffort reads __SR_ENGINE_PREFS.effort[role_kind]).
    // The effort sub-map is keyed by role_kind (review/review-deep/build/fix), not the role name.
    if (kind && typeof row.effort === 'string' && row.effort.trim()) {
      const effortKind = row.kind === 'review-deep' ? 'review-deep' : kind
      enginePrefs.effort[effortKind] = row.effort
    }
  }
  return { overrides, enginePrefs }
}

async function readDefinitionDraft(workItem, doc) {
  const label = doc === 'plan' ? 'read plan draft' : 'read tasks draft'
  const script = [
    'import json, os, sys',
    `sys.path.insert(0, ${pyLibDir()})`,
    'import definition_doc',
    'wi = sys.argv[1]',
    'doc = sys.argv[2]',
    'root = sys.argv[3]',
    'd = definition_doc.resolve_work_item_dir(wi, root=root, cwd=root)',
    'p = os.path.join(d, f"{doc}.md")',
    'exists = os.path.isfile(p)',
    'gate = definition_doc.read_gate(p) if exists else "unreadable"',
    'print(json.dumps({"ok": True, "path": p, "docType": doc, "gate": gate, "exists": exists}))',
  ].join('\n')
  return courier.runCourierJson(
    label,
    `python3 -c ${shq(script)} ${shq(workItem)} ${shq(doc)} "$(git rev-parse --show-toplevel)"`,
    { require: ['ok', 'path', 'docType'] },
  )
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

// Boundary coercion: parse a value the courier may have stringified (#115 "parse facts at boundary").
// Applies to known nested-object fields in the resolveContext result. If the value is a string that
// JSON-parses to a dict, array, or null, return the parsed result. Otherwise return the value unchanged
// so downstream consumers (writeJson, _is_object guards) still fail-closed on non-parseable strings.
// Arrays are included because allowedOrigins is a JSON array (e.g. '["http://localhost:3000"]') and
// must coerce back to an array; a non-container parse result (number, bool) stays as the original string.
const _coerceObj = (v) => {
  if (typeof v !== 'string') return v
  try {
    const p = JSON.parse(v)
    if (p === null || (typeof p === 'object')) return p
  } catch (_) { /* fall through */ }
  return v
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
    resolveContext: async () => {
      // FIX B: resolve build worktree (same way review-code does) + thread configurable base.
      // resolveBuildTarget is defined later in this file but testPilotDeps is called after module
      // load, so the forward reference resolves correctly at call time.
      // Fail-closed: an unresolvable build worktree must PARK, never silently run the context CLI
      // against the showrunner's OWN tree. Without --worktree, test_pilot_context_cli falls back to
      // the showrunner checkout, whose diff misclassifies applicability (typically 'not_applicable')
      // and SKIPS test-pilot with no park/log — a silent fail-open. Throwing here is caught by
      // resolveApplicabilityAndSetup -> a low-confidence park (mirrors reviewCodePhase's null-resolver
      // park; honors the profile invariant "unresolvable -> fail-closed PARK, never act on the wrong tree").
      const target = await resolveBuildTarget(workItem).catch(() => null)
      if (!target || !target.worktree) {
        throw new Error('could not resolve the build worktree for test-pilot — refusing to run against the showrunner tree')
      }
      const wtArg = ` --worktree ${shq(target.worktree)}`
      // FR-8: mirror the __SR_BASE pattern from shipPhase / draftPRPhase.
      const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
      const baseArg = _srBase ? ` --base ${shq(_srBase)}` : ''
      const raw = await courier.runCourierJson(
        'read test context',
        `python3 ${libPath('test_pilot_context_cli.py')} resolve ` +
        `--work-item ${shq(workItem)}${generation != null ? ` --generation ${shq(String(generation))}` : ''}` +
        `${wtArg}${baseArg}`,
        { require: ['head'] },
      )
      // FIX A: coerce nested fields the cheap courier may have stringified (same class as verify_gate).
      // Strings, head, branch, workItem stay as-is; only known object/null fields are coerced.
      if (raw && typeof raw === 'object') {
        for (const field of ['diff', 'detectors', 'profile', 'pr', 'browserTool', 'allowedOrigins', 'store']) {
          if (field in raw) raw[field] = _coerceObj(raw[field])
        }
      }
      return raw
    },

    derivePlan: async (context) => agent(
      `You are the test-pilot plan leaf for work-item ${workItem}. Derive a browser test plan for ` +
      `the current branch head ${context.head}. Return ONLY JSON ` +
      `{"records":[{"branch":${JSON.stringify(context.branch)},"steps":[{"id","instruction","expected","scenarioIds":[]}]}],` +
      `"coverageRationale":"..."}. Use concise stable step ids; include scenarioIds when seed scenarios are needed.`,
      { label: 'plan-tests', schema: { type: 'object', required: ['records'], properties: { records: { type: 'array' } } } }),

    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records || [] }),

    prepareTestRun: async ({ plan, records, context }) => {
      const pr = context.pr && context.pr.number
      if (!pr) return { action: 'park', reason: 'test-pilot artifacts require a draft PR number' }
      const planPath = await writeJson('plan-artifact', { key: keyFor(context.branch), records })
      const resultsPath = await writeJson('results-artifact-initial', { key: keyFor(context.branch), records: [], coverageRationale: plan.coverageRationale })
      const profilePath = await writeJson('server-profile', context.profile || {})
      const detectionPath = await writeJson('server-detection', context.detectors || {})
      const recordsPath = await writeJson('seed-records', records)
      const manifestPath = await writeJson('prepare-run-manifest', {
        artifacts: [
          'python3', libPath('test_pilot_artifacts_cli.py'), 'ensure',
          '--plan-json', planPath, '--results-json', resultsPath, '--pr', String(pr),
          '--key', keyFor(context.branch),
        ],
        server: [
          'python3', libPath('test_pilot_server_config_cli.py'), 'resolve',
          '--profile-json', profilePath, '--detection-json', detectionPath,
          '--work-item', workItem,
        ],
        seed: [
          'python3', libPath('test_pilot_seed_cli.py'), 'prepare',
          '--records-json', recordsPath,
        ],
      })
      const script = [
        'import json, subprocess, sys',
        'manifest = json.load(open(sys.argv[1], encoding="utf-8"))',
        'def run(argv):',
        '    try:',
        '        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)',
        '    except subprocess.TimeoutExpired:',
        '        raise RuntimeError("command timed out")',
        '    if proc.returncode != 0:',
        '        raise RuntimeError(proc.stderr or proc.stdout or "command failed")',
        '    return json.loads(proc.stdout or "{}")',
        'try:',
        '    artifactResult = run(manifest["artifacts"])',
        '    serverContext = run(manifest["server"])',
        '    seedResult = run(manifest["seed"])',
        '    print(json.dumps({"ok": True, "artifactResult": artifactResult, "serverContext": serverContext, "seedResult": seedResult}))',
        'except Exception as exc:',
        '    print(json.dumps({"ok": False, "reason": str(exc)}))',
      ].join('\n')
      const out = await courier.runCourierJson(
        'prepare test run',
        `python3 -c ${shq(script)} ${shq(manifestPath)}`,
        { require: ['ok', 'artifactResult', 'serverContext', 'seedResult'], retryRealFailure: false },
      )
      if (!out || !out.ok) return { action: 'park', reason: (out && out.reason) || 'test-pilot preparation failed' }
      return out
    },

    prepareArtifacts: async ({ plan, records, context }) => {
      const pr = context.pr && context.pr.number
      if (!pr) return { action: 'park', reason: 'test-pilot artifacts require a draft PR number' }
      const planPath = await writeJson('plan-artifact', { key: keyFor(context.branch), records })
      const resultsPath = await writeJson('results-artifact-initial', { key: keyFor(context.branch), records: [], coverageRationale: plan.coverageRationale })
      return cli(
        `python3 ${libPath('test_pilot_artifacts_cli.py')} ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(context.branch))}`,
        { type: 'object' })
    },

    resolveServer: async (context) => {
      const profile = await writeJson('server-profile', context.profile || {})
      const detection = await writeJson('server-detection', context.detectors || {})
      return cli(
        `python3 ${libPath('test_pilot_server_config_cli.py')} resolve ` +
        `--profile-json ${shq(profile)} --detection-json ${shq(detection)} --work-item ${shq(workItem)}`,
        { type: 'object' })
    },

    withManagedServer: async (serverContext, run) => {
      const launchPath = await writeJson('server-launch-context', serverContext)
      const launched = await cli(
        `python3 ${libPath('test_pilot_server_config_cli.py')} launch ` +
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
          `python3 ${libPath('test_pilot_server_config_cli.py')} finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
      } catch (err) {
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', { action: 'exception', reason: err && err.message ? err.message : String(err) })
        await cli(
          `python3 ${libPath('test_pilot_server_config_cli.py')} finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
        throw err
      }
    },

    seedRecords: async (records) => {
      const recordsPath = await writeJson('seed-records', records)
      return cli(
        `python3 ${libPath('test_pilot_seed_cli.py')} prepare --records-json ${shq(recordsPath)}`,
        { type: 'object' })
    },

    runBrowserPass: async (browserContext) => agent(
      `Run the test-pilot browser pass for work-item ${workItem}. Stay within baseUrl/allowedOrigins and return ONLY JSON ` +
      `{"source":"browser","baseUrl":${JSON.stringify(browserContext.baseUrl)},"steps":[{"id","status","notes","browserExecuted":true,"failureType"?,"summary"?}]}. ` +
      `Browser context: ${JSON.stringify(browserContext)}`,
      { label: 'browser-pass', schema: { type: 'object' } }),

    dispatchFixBatch: async (failures, details) => agent(
      `Fix the app bugs found by native test-pilot for work-item ${workItem}. Commit fixes locally. ` +
      `Return ONLY JSON {"ok":true,"commitShas":["..."],"changedFiles":["..."],"head":"..."}. ` +
      `Failures: ${JSON.stringify(failures)} Details: ${JSON.stringify(details)}`,
      { label: 'fix-app-bug', schema: { type: 'object' } }),

    reviewCode: (wi, opts) => reviewCodePhase(wi, Object.assign({}, opts, {
      runDir: opts.runDir || `/tmp/showrunner-${wi}-review-code-${safeRunKey(opts.runDirSuffix || `${opts.cycle || 1}-${opts.expectedHead || 'head'}`)}`,
    })),

    restoreBaseline: async (records, details) => {
      const recordsPath = await writeJson('restore-records', records)
      const out = await cli(
        `python3 ${libPath('test_pilot_seed_cli.py')} restore-baseline --records-json ${shq(recordsPath)}`,
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
        `python3 ${libPath('test_pilot_artifacts_cli.py')} ensure ` +
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
      return courier.runCourierJson(
        'publish tested head',
        `python3 ${libPath('test_pilot_publish_cli.py')} publish --work-item ${shq(workItem)} ` +
        `--head ${shq(head)} --status-json ${shq(statusPath)} --expected-branch ${shq(payload.context.branch)} ` +
        `${storeArg}${generationArg}`,
        { require: ['ok', 'read_back'], retryRealFailure: false },
      )
    },

    writeStatus: async (status) => {
      if (status.milestone) {
        await writeJson(`milestone-${status.milestone}`, status)
        return { ok: true, read_back: true }
      }
      const statusPath = await writeJson('status-write', status)
      return courier.runCourierJson(
        'write test status',
        `python3 ${libPath('test_pilot_status_cli.py')} write --work-item ${shq(workItem)} --status-json ${shq(statusPath)}`,
        { require: ['ok', 'read_back'], retryRealFailure: false },
      )
    },
  }
}

async function runPhases(workItem, fromStep, deps) {
  deps = deps || {}
  for (let i = fromStep; i < PHASES.length; i += 1) {
    const phase = PHASES[i]
    // Progress-group every leaf dispatched during this phase under the phase name (read by the
    // bundle's agent wrapper). Purely cosmetic — no control-flow effect.
    if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = phase
    // #130: baseline the output-token cursor at the phase boundary; the phase's cost payload
    // (folded into its persist / hand-back write) diffs the budget delta against this mark.
    costMeter.mark(phase)
    // FR-7: the native front-half ends at its boundary — park before entering the back-half
    // (the 'workhorse' build phase, renamed from 'build' in #107), on a FRESH run AND on a RESUME
    // (a resume re-enters at the build cursor, so the boundary must be checked at that phase, not
    // merely after review-tasks).
    if (deps.frontHalfBoundary && phase === 'workhorse') {
      return deps.frontHalfBoundary(workItem)
    }
    if (phase === 'ship') {                              // terminal: returns {outcome,phase,reason}
      // #130: ship's cost + terminal marker fold into its hand-back readout_post leaf (park() /
      // shipHandback take('ship') and pass --cost-payload + --terminal), so ship rides no new leaf.
      return (deps.ship || shipPhase)(workItem, await loadPr(workItem), deps.generation)
    }
    let phaseResult, gate, sideEffect = null, persist = null
    if (phase === 'review-code') {
      const r = await (deps.reviewCode || reviewCodePhase)(workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if (phase === 'workhorse') {
      phaseResult = await (deps.build || buildPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'draft-PR') {
      const r = await (deps.draftPR || draftPRPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if (phase === 'test-pilot') {
      phaseResult = await (deps.testPilot || defaultTestPilotPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'mark-ready') {
      const r = await (deps.markReady || markReadyPhase)(workItem, deps.generation); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if ((phase === 'review-plan' || phase === 'review-tasks') && deps.reviewDoc) {
      const doc = phase === 'review-plan' ? 'plan' : 'tasks'
      const r = await deps.reviewDoc(doc, workItem); phaseResult = r.phaseResult; gate = r.gate; persist = r.persist || null
    } else if ((phase === 'plan' || phase === 'tasks') && deps.produce) {
      phaseResult = await deps.produce(phase, workItem); gate = null
    } else {
      phaseResult = await (deps.phaseLeaf || defaultPhaseLeaf)(phase, workItem)
      gate = await (deps.gateRead || (async () => null))(phase, workItem)
    }
    // #118 "Every phase" tail: journal + cursor (+ set-gate at review phases, chained first — FR-4
    // persist order) land in ONE read-back-confirmed 'save phase progress' leaf. The advance/park
    // decision is the in-process twin, derived BEFORE the persist; a park still records the journal
    // entry (and any set-gate side effect) durably but leaves the cursor untouched (journalOnly),
    // so a resume re-enters the parked phase instead of skipping it.
    const decision = await phaseStep(phaseResult, gate)
    const proceed = decision.action === 'proceed'
    const saved = await persistPhase(workItem, {
      sideEffectCmd: (persist && persist.sideEffectCmd) || null,
      journalPayload: (persist && persist.journalPayload) ||
        { phase, gate, confidence: phaseResult.confidence, assumptions: phaseResult.assumptions || [] },
      step: i, phase, sideEffect,
      journalOnly: !proceed,
      recordCost: true,     // #130: fold this phase's cost telemetry into the save leaf
      // #130: on a park, fold a `parked` terminal marker into the same save so token_trend/run_watch
      // can classify the run (parkFromPhases journals nothing of its own).
      parkReason: !proceed ? (phaseResult.parkReason || decision.reason) : null,
    })
    // FR-4/UFR-2: a failed durable phase-progress write must never advance (and never park silently
    // on unrecorded state) — park naming the durable-write failure.
    if (!saved.ok) {
      return parkFromPhases(workItem, deps.generation, deps.root, phase,
        `phase progress not recorded (${saved.error || 'durable write failed'}) — UFR-2/FR-4`)
    }
    if (!proceed) {
      return parkFromPhases(workItem, deps.generation, deps.root, phase,
        phaseResult.parkReason || decision.reason)
    }
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
async function renderAndPostReadout(workItem, runDir, verdict, opts) {
  opts = opts || {}
  const recPath = `${runDir}/terminal-record.json`
  const runId = opts.runId || `review-code-${workItem}`
  const lease = opts.lease || undefined
  // Composed Python-side from the run's on-disk state (round-records.json + review-telemetry.json)
  // so the evidence-bodied verdict never crosses a courier writeFile (payload-stage-failed class).
  const recWrite = await writeTerminalRecord(recPath, verdict || {}, { runId, lease, runDir })
  if (!recWrite.ok) return { ok: false, reason: recWrite.reason || 'terminal-record-write-failed' }
  // FR-5 (cwd-rooting): courier_exec's rootedCommand pins the loop_readout.py call to the repo
  // root when __SR_ROOT is set — same as renderReadout in frontHalfBoundary. The render is a dumb
  // pipe (run a command, echo stdout), so it rides the courier: pinned cheapest + one-shot retry.
  let text = ''
  try {
    text = await courier.runCourierText(
      'readout',
      `python3 ${libPath('loop_readout.py')} --record ${shq(recPath)}`)
  } catch (_e) {
    text = ''   // transport drop: post the bare park reason path below (best-effort render)
  }
  try {
    await courier.runCourierJson(
      'post readout',
      `python3 ${libPath('readout_post.py')} --work-item ${shq(workItem)} --reason ${shq(String(text))}`,
      { require: ['posted'], retryRealFailure: false },
    )
  } catch (_e) {
    // best-effort: a courier transport failure must not abort review-code parking
  }
  return { ok: true }
}
module.exports.renderAndPostReadout = renderAndPostReadout

// the review-code phase: drive the shared loop, map its terminal to advance/park, stamp covers on a
// pure `clean` (X'), and surface the readout at a park. Returns { phaseResult, gate } for runPhases.
async function reviewCodePhase(workItem, opts) {
  opts = opts || {}
  const runDir = opts.runDir || (opts.runDirSuffix
    ? `/tmp/showrunner-${workItem}-review-code-${safeRunKey(opts.runDirSuffix)}`
  : `/tmp/showrunner-${workItem}-review-code`)
  // fold 2 (#141; #211 decision shape): ONE gather leaf does the run-dir mkdir + resume DECISION +
  // round-1 plan + entry coverage read (no records ride up; the code leg has no deferred-set seed —
  // doc-only — but the round-1 tally still folds via the gathered deferredSet). Gather failure ->
  // null: fall back to a plain mkdir + the panel's own reads.
  const coverageDecisionPath = joinPath(runDir, 'review-coverage-decisions.json')
  const setup = await gatherReviewSetup({
    runDir, reviewerSet: REVIEW_CODE_REVIEWERS, context: { workItem, coverageDecisionPath },
    legKind: { panel: true, code: true }, ioApi: io(),
  })
  if (!setup) await io().mkdirp(runDir)
  // FIX A: when opts.worktree is absent, resolve the build worktree via resolveBuildTarget (the
  // stubbable seam). Explicit opts.worktree always wins (loop-smoke + targeted-smoke pass it). On
  // a production call (runPhases -> reviewCodePhase(workItem) with no opts), resolution runs and
  // fails CLOSED on error — never fall back to reviewing root (that IS the original bug).
  let resolvedWorktree = opts.worktree || null
  let resolvedHead = opts.expectedHead || null
  let resolvedConfig = null
  let cwdHeadBefore = null
  let resolvedViaGather = false
  if (!opts.worktree) {
    const resolver = opts.resolveTarget || resolveBuildTarget
    const resolved = await resolver(workItem)
    if (!resolved) {
      return {
        phaseResult: { confidence: 'low', assumptions: ['review-code: could not resolve the build worktree — refusing to review the showrunner tree'] },
        gate: 'changes-requested',
      }
    }
    resolvedWorktree = resolved.worktree
    resolvedHead = resolved.expectedHead
    // #118 review-code entry fold: 'resolve review target' is the stretch's ONE gather — it also
    // carries the review config and the CWD head, so no separate config / rev-parse leaves fire on
    // the production path. A resolver stub that omits them (older seam) falls back below.
    resolvedConfig = _coerceObj(resolved.config)
    cwdHeadBefore = resolved.cwdHead || null
    resolvedViaGather = true
  }
  const initialHead = resolvedHead || null
  // The head re-check only fires when the head was supplied EXTERNALLY (opts.expectedHead —
  // test-pilot stabilization / smokes): it verifies the tree is where the caller believes. When the
  // gather just read the head itself, re-reading the same value is a redundant leaf (matrix fold).
  if (resolvedHead && !resolvedViaGather) {
    const actual = await resolveHead(resolvedWorktree || null, opts.ref || 'HEAD')
    if (!actual || !sameHead(actual, resolvedHead)) {
      return { phaseResult: { confidence: 'low', assumptions: [`review-code target head mismatch: expected ${resolvedHead}, got ${actual || 'unknown'}`] }, gate: 'changes-requested' }
    }
  }
  const targetWorktree = resolvedWorktree || null
  // premortem-002: the fixer is a freeform subagent that receives the target worktree only as a TEXT
  // hint (withTargetCommandPrompts retargets just the "Run exactly this" courier prompts). If it
  // commits to the showrunner CWD instead of the target tree, the target HEAD never advances, the
  // expectedHead checks still pass (both = pre-fix HEAD), and a stale `clean` covers-stamp would
  // publish unmodified code. Snapshot CWD HEAD so we can detect that divergence after the loop
  // (carried by the gather on the production path; read here for the explicit-worktree branch).
  if (cwdHeadBefore == null && targetWorktree && resolvedHead) {
    cwdHeadBefore = await resolveHead(null, opts.ref || 'HEAD')
  }
  const cfg = (resolvedConfig && typeof resolvedConfig === 'object') ? resolvedConfig
    : await execJson(
        inWorktree(`python3 ${libPath('review_code_config.py')} --root "$(git rev-parse --show-toplevel)"`, targetWorktree), 'read review config')
  const leaves = reviewCodeLeaves((cfg && cfg.tiers) || {}, {
    target: { worktree: resolvedWorktree, head: resolvedHead },
  })
  const verdict = await runReviewCodePanel({
    runDir,
    context: { workItem, target: { worktree: resolvedWorktree, head: resolvedHead }, coverageDecisionPath, synthesisVerificationRoot: targetWorktree },
    rubric: 'review-base',
    verifyCommand: (cfg && cfg.verifyCommand) || 'none', leaves, worktree: targetWorktree,
    preloaded: setup || undefined,
  })
  const terminal = (verdict && verdict.terminal) || 'halted'
  const finalHead = resolvedHead
    ? await resolveHead(resolvedWorktree || null, opts.ref || 'HEAD')
    : null
  if (resolvedHead && !finalHead) {
    return { phaseResult: { confidence: 'low', assumptions: ['review-code final target head could not be resolved'] }, gate: 'changes-requested', terminal, head: null, changed: false }
  }
  // #104's advance/park mapping, read off the terminal (plan Key decision 2).
  if (!ADVANCE_TERMINALS.has(terminal)) {
    const readout = await renderAndPostReadout(workItem, runDir, verdict)
    if (!readout || !readout.ok) {
      return {
        phaseResult: { confidence: 'low', assumptions: [`review-code readout failed: ${(readout && readout.reason) || 'unknown'}`] },
        gate: 'changes-requested', terminal, head: finalHead,
        changed: !!(initialHead && finalHead && !sameHead(initialHead, finalHead)),
      }
    }
    // #212: name the terminal + the panel's honest reason on parkDetail so the workflow park reads
    // e.g. "review requested changes — cannot-certify: premortem-reviewer returned no verification
    // receipt after retry (receipt-missing — uncertifiable)" instead of the bare flatten. Empty
    // assumptions → phase_step routes this to park_changes_requested (not park_assumption).
    const parkDetail = `${terminal}: ${(verdict && verdict.reason) || 'review not certified'}`
    return { phaseResult: { confidence: 'high', assumptions: [], parkDetail }, gate: 'changes-requested', terminal, head: finalHead, changed: !!(initialHead && finalHead && !sameHead(initialHead, finalHead)) }
  }
  // premortem-002 fail-closed: an advancing terminal means we're about to certify the target HEAD. If
  // the CWD advanced while the target HEAD did not, the fixer's commits landed outside the shipped tree
  // — refuse to advance/stamp rather than certify (and ship) code the fixes never touched.
  if (targetWorktree && resolvedHead) {
    const cwdHeadAfter = await resolveHead(null, opts.ref || 'HEAD')
    const cwdMoved = cwdHeadBefore && cwdHeadAfter && !sameHead(cwdHeadBefore, cwdHeadAfter)
    const targetMoved = initialHead && finalHead && !sameHead(initialHead, finalHead)
    if (cwdMoved && !targetMoved) {
      return { phaseResult: { confidence: 'low', assumptions: ['review-code fixes landed outside the target worktree (cwd HEAD advanced, target HEAD did not) — refusing to stamp coverage'] }, gate: 'changes-requested', terminal, head: finalHead, changed: false }
    }
  }
  // FR-9: stamp covers = X' ONLY on a pure `clean`; every other terminal already parked above.
  // prov_entry resolves the build-branch tip (= X' after the fixer's commits).
  if (terminal === 'clean') {
    const targetArgs = resolvedWorktree || resolvedHead
      ? ` --worktree ${shq(resolvedWorktree || procCwd())}${finalHead ? ` --head ${shq(finalHead)}` : ''}`
      : ''
    let prov = null
    try {
      prov = await courier.runCourierJson(
        'stamp review coverage',
        `python3 ${libPath('prov_entry.py')} --step review --work-item ${shq(workItem)}${targetArgs}`,
        { require: ['ok'], retryRealFailure: false },
      )
    } catch (_) {
      prov = { ok: false, error: 'unreadable' }
    }
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
    changed: !!(initialHead && finalHead && !sameHead(initialHead, finalHead)),
    reviewCoverageHead: terminal === 'clean' ? (finalHead || undefined) : undefined,
    verifyPassedHead: finalHead || undefined,
  }
}

// resolveHead: dumb-pipe git rev-parse via the exec courier (pinned cheapest, one-shot retry).
// Production review-code resolves heads inside the folded 'resolve review target' gather; this
// remains for the explicit-worktree branch (test-pilot stabilization) and post-loop head checks.
async function resolveHead(worktree, ref) {
  const cmd = worktree
    ? `git -C ${shq(worktree)} rev-parse ${shq(ref || 'HEAD')}`
    : `git rev-parse ${shq(ref || 'HEAD')}`
  try {
    const out = await execText(cmd, 'resolve head')
    // Boundary normalization (finding #15, run a743e55a): a terse courier ABBREVIATED
    // rev-parse stdout to 7 chars in relay; the raw string then failed equality against
    // a full-sha read of the SAME commit and the outside-worktree guard false-parked a
    // clean run. Prefer the sha-shaped hex run (extracts the sha from fenced/prose
    // answers too); fall back to the first token of the first non-empty line so
    // non-hex refs still resolve. sameHead() below absorbs full-vs-abbreviated reads.
    const raw = String(out || '').trim()
    // Line-anchored: only a line that IS a hex token counts (review: first-hex-anywhere
    // could manufacture a head from an error message's incidental hex — fail-open).
    for (const l of raw.split('\n')) {
      const t = l.trim().replace(/^`+|`+$/g, '')
      if (/^[0-9a-f]{7,40}$/.test(t)) return t
    }
    const line = (raw.split('\n').find((l) => l.trim()) || '').trim()
    return line ? line.split(/\s+/)[0] : null
  } catch (_) {
    return null
  }
}

// sameHead: prefix-tolerant head equality — two honest reads of one commit may differ
// in LENGTH (full vs abbreviated relay, finding #15); a real move differs in CONTENT.
// Null/empty never equals anything (fail-closed at the call sites).
function sameHead(a, b) {
  if (!a || !b) return false
  const x = String(a), y = String(b)
  if (x === y) return true
  // Prefix tolerance is for sha ABBREVIATION only: require >=7 overlap (git's abbrev
  // floor) so stray short fallback tokens never spuriously prefix-match (review nit).
  if (Math.min(x.length, y.length) < 7) return false
  return x.startsWith(y) || y.startsWith(x)
}

// the native "workhorse" build phase (#87) — implement the approved tasks doc task-by-task with a
// per-task review + bounded fix loop, one whole-branch final review, and provenance written once.
// All of that orchestration lives in build_phase.js; the spine just delegates, threading the lease
// generation reconcile() acquired so the build can fence every branch-mutating boundary (UFR-10).
const buildPhase = (workItem, generation) => require('./build_phase.js').buildPhase(workItem, generation)

// Resolve the build worktree + expected head for review-code. Mirrors build_phase.js's execJson
// pattern (cheap exec dumb-pipe, NOT a genuine agent) so the call is deterministic + stubbable.
// Runs build_entry.py WITHOUT --generation (idempotent: reclaim_or_create returns REUSED for an
// existing clean worktree; lockGeneration is only set when --generation is passed).
// #118 review-code entry fold: the same gather also reads the review config (review_code_config.py
// in the target worktree) and the CWD head — the whole entry stretch is this ONE leaf. Both extras
// are best-effort (null on failure): config falls back to {verifyCommand:'none'} downstream, and a
// missing cwdHead only re-adds the explicit-branch rev-parse leaf.
// Returns {worktree, expectedHead, config, cwdHead} or null on any failure (caller parks on null).
async function resolveBuildTarget(workItem) {
  const script = [
    'import json, subprocess, sys',
    'wi = sys.argv[1]',
    'setup = None',
    'for _ in range(2):',
    '    try:',
    `        r = subprocess.run(["python3", ${pyLibScript('build_entry.py')}, "--work-item", wi], capture_output=True, text=True, timeout=120)`,
    '    except subprocess.TimeoutExpired:',
    '        continue',
    '    if r.returncode != 0: continue',
    '    try: setup = json.loads((r.stdout or "").strip() or "{}"); break',
    '    except Exception: continue',
    'if not setup or setup.get("error") or not setup.get("path"):',
    '    print(json.dumps({"ok": False, "error": "missing build worktree"})); raise SystemExit(0)',
    'if str(setup.get("outcome", "")).lower() == "created":',
    '    print(json.dumps({"ok": False, "error": "fresh worktree created"})); raise SystemExit(0)',
    'wt = setup["path"]',
    'head = None',
    'for _ in range(2):',
    '    try:',
    '        r = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)',
    '    except subprocess.TimeoutExpired:',
    '        continue',
    '    if r.returncode == 0 and (r.stdout or "").strip():',
    '        head = r.stdout.strip(); break',
    'if not head:',
    '    print(json.dumps({"ok": False, "error": "missing target head"})); raise SystemExit(0)',
    'cfg = None',
    'try:',
    `    r = subprocess.run(["python3", ${pyLibScript('review_code_config.py')}, "--root", wt], capture_output=True, text=True, timeout=60, cwd=wt)`,
    '    if r.returncode == 0:',
    '        cfg = json.loads((r.stdout or "").strip() or "null")',
    'except Exception:',
    '    cfg = None',
    'cwd_head = None',
    'try:',
    '    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)',
    '    if r.returncode == 0 and (r.stdout or "").strip():',
    '        cwd_head = r.stdout.strip()',
    'except Exception:',
    '    cwd_head = None',
    'print(json.dumps({"ok": True, "worktree": wt, "expectedHead": head, "config": cfg, "cwdHead": cwd_head}))',
  ].join('\n')
  let setup = null
  try {
    setup = await courier.runCourierJson(
      'resolve review target',
      `python3 -c ${shq(script)} ${shq(workItem)}`,
      { require: ['ok'] },
    )
  } catch (_) {
    setup = null
  }
  if (!setup || setup.error || !setup.worktree) return null   // fail-closed: no usable worktree
  return {
    worktree: setup.worktree,
    expectedHead: setup.expectedHead,
    config: setup.config != null ? setup.config : null,
    cwdHead: setup.cwdHead || null,
  }
}

module.exports.verdictToGate = verdictToGate
module.exports.reviewCodePhase = reviewCodePhase
module.exports.resolveBuildTarget = resolveBuildTarget
module.exports.runReviewCodePanel = runReviewCodePanel
module.exports.buildPhase = buildPhase

// loadPr: read the checkpointed PR before the ship phase — a dumb-pipe read via the exec courier
// (pinned cheapest + one-shot retry, #118). The cursor itself is written by the per-phase
// persistPhase tail; there is no separate checkpoint_entry write leaf anymore.
async function loadPr(workItem) {
  const out = await execJson(
    `python3 ${libPath('checkpoint_entry.py')} --work-item ${shq(workItem)} --read-pr`, 'read pr')
  return (out && out.pr !== undefined) ? out.pr : null
}

// draft-PR: one folded courier leaf returning {ok, pr, read_back, reason?}.
async function draftPRPhase(workItem) {
  const _srBaseForPR = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const _prBaseArg = _srBaseForPR ? ` --base ${shq(_srBaseForPR)}` : ''
  let out = null
  try {
    out = await courier.runCourierJson(
      'open draft PR',
      `python3 ${libPath('pr_entry.py')} --step draft --work-item ${shq(workItem)}${_prBaseArg}`,
      { require: ['ok', 'read_back'], retryRealFailure: false },
    )
  } catch (_e) {
    // courier transport failure (dropped/garbled stdout twice) — park, never crash the run; a PR the
    // first attempt may have created is re-adopted idempotently by pr_entry on the next run.
    out = null
  }
  if (!out || !out.ok || !out.pr || !out.read_back) {
    return {
      phaseResult: { confidence: 'low', assumptions: [(out && out.reason) || 'draft-PR gated'] },
      sideEffect: null,
    }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: out.pr } }
}

// fill-dod: the "build/ship legs fill it" leg from issue #228's own design — the draft-PR
// step seeds the disposition table skeleton; a MODEL leaf PROPOSES dispositions from the
// run's real evidence, and the deterministic splice CLI (dod_fill_cli.py) holds the pen
// (PR #251 review: a model rewriting the full body at a certification boundary risked
// truncating the stubbed-seams disclosure, clobbering concurrent edits, and fabricating
// evidence — the CLI touches only matching table cells, mechanically verifies deferred
// issues resolve and path-shaped evidence exists, and read-back-confirms the write).
// Honesty contract unchanged: a row the model cannot evidence is omitted, stays blank,
// and the (unchanged, fail-closed) gate parks with the same honest reason.
async function proposeDodDispositions(workItem, prNumber) {
  const absRoot = checkoutRoot()
  try {
    const raw = await agent(
      `You are the DoD disposition-proposal leg for work-item ${workItem} (issue #228). ` +
      `Draft PR #${prNumber} carries a "DoD dispositions" table seeded from the spec's ` +
      `Definition-of-done section. Propose dispositions from REAL run evidence and return ` +
      `them as JSON — you do NOT edit the PR yourself; a deterministic splice tool applies ` +
      `your rows and mechanically verifies them.\n` +
      `Work from the repo root at ${absRoot} (run every command from there).\n` +
      `Steps:\n` +
      `1. Spec: run python3 ${libPath('definition_doc.py')} path --work-item ${shq(workItem)} ` +
      `--doc spec --root ${shq(absRoot)} and read the Definition-of-done bullets from that file.\n` +
      `2. Current table: gh pr view ${shq(String(prNumber))} --json body.\n` +
      `3. Evidence, per bullet — use only what actually exists: the PR diff ` +
      `(gh pr diff ${shq(String(prNumber))}), the head branch (gh pr view ${shq(String(prNumber))} --json headRefName), ` +
      `the build/final-review records (python3 ${libPath('build_state_cli.py')} gather ` +
      `--work-item ${shq(workItem)} --branch <that headRefName>), the test-pilot status record ` +
      `(test-pilot-status.json under the control-plane store for this work-item), and CI check state.\n` +
      `4. For each bullet you can HONESTLY disposition: "done" needs a concrete evidence ` +
      `pointer (command output, record path, diff line); "deferred" needs an ALREADY-FILED ` +
      `issue number (#NNN) plus a one-line reason. NEVER invent evidence or issue numbers — ` +
      `deferred issues are mechanically resolved against GitHub and path-shaped evidence is ` +
      `existence-checked, so a fabricated row is rejected and the gate parks.\n` +
      `COMPLETENESS IS THE JOB: propose a row for EVERY Definition-of-done bullet. The table ` +
      `has one row per bullet and the gate parks on ANY undisposed bullet, so one bullet you ` +
      `skip fails the entire run — do NOT stop after the first bullet you evidence.\n` +
      `Structural bullets — a line-count claim ("exactly one additional line", "N lines added"), ` +
      `a scope claim ("no file other than X is modified", "only these paths change") — are ` +
      `ALWAYS evidenceable from the diff: gh pr diff ${shq(String(prNumber))} shows every hunk, ` +
      `and gh pr diff ${shq(String(prNumber))} --name-only lists every changed path. Read the ` +
      `diff and cite the exact hunk / path list; NEVER drop a structural bullet as "no evidence" ` +
      `without having actually run the diff. Omission is a LAST RESORT after you have genuinely ` +
      `checked the diff and records and found no honest evidence — it parks the run, so treat a ` +
      `dropped bullet as a failure, not a shortcut.\n` +
      `Return ONLY JSON {"ok": true, "rows": [{"bullet": "<bullet text exactly as it appears ` +
      `in the spec/table>", "disposition": "done"|"deferred", "detail": "<evidence pointer or ` +
      `#NNN + reason>"}]} — one entry per bullet you can evidence (ok=false with "reason" if you ` +
      `could not read the spec or PR). If you genuinely cannot evidence a bullet, OMIT it.`,
      { label: 'fill-dod', schema: { type: 'object', required: ['ok'] } })
    // Boundary coercion (#115 class, observed live in run wf_a9654118: the leaf returned
    // ok:'true' and rows as a JSON STRING). ok must compare against the string form too —
    // 'false' is truthy, so a plain truthiness check would read a refusal as consent.
    const obj = _coerceObj(raw)
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null
    const rows = _coerceObj(obj.rows)
    return {
      ok: obj.ok === true || obj.ok === 'true',
      rows: Array.isArray(rows) ? rows : [],
    }
  } catch (_e) {
    return null   // proposal failure -> the gate re-run below is skipped; the original park stands
  }
}

// mark-ready: gate courier leaf; on a DoD-table park (gate === 'dod', pr_entry's machine
// field — never the reason string, CONVENTIONS §11): fence the lease (UFR-4 — the splice
// is a PR-mutating boundary), ONE proposal leaf, ONE deterministic splice, ONE gate
// re-decide. DoD-less runs (quick route, dispositions already filled) pay no extra leaf.
async function markReadyPhase(workItem, generation) {
  const gate = async () => {
    try {
      return await courier.runCourierJson(
        'mark PR ready',
        `python3 ${libPath('pr_entry.py')} --step mark-ready --work-item ${shq(workItem)}`,
        { require: ['ok', 'read_back'], retryRealFailure: false },
      )
    } catch (_e) {
      return null   // courier transport failure — park, never crash the run
    }
  }
  let out = await gate()
  if (out && !out.ok && out.gate === 'dod' && out.pr != null) {
    // Settle CI BEFORE the proposal leaf (finding #12, run fdfad511: the fixture's
    // "green CI" DoD bullet is undissposable while the draft PR's checks are still
    // running — a fast spine reaches this gate ~2 min after opening the PR, the leaf
    // honestly omits the bullet, and the run parks on a race, not a defect). Pending
    // is WAIT, not FIX (#11); the settle CLI returns immediately when nothing is
    // pending, so the common case costs one instant leaf. Best-effort: a settle
    // transport failure or exhausted budget falls through to the proposal — the leaf
    // then evidences what it can and the gate stays honest.
    // The settle CLI reads the PR head's checks via ship_phase --emit-checks, whose
    // stale guard compares the local head at cwd to the remote PR head — from the
    // checkout root (base branch) that ALWAYS reads stale and short-circuits without
    // waiting (PR #261 review finding). Resolve the build worktree first, exactly
    // like the ship loop; if it cannot be resolved, skip the wait (best-effort).
    try {
      const target = await resolveBuildTarget(workItem).catch(() => null)
      const wt = target && target.worktree
      if (wt) {
        await courier.runCourierJson(
          'wait for CI to settle',
          `python3 ${libPath('ci_settle_cli.py')} --work-item ${shq(workItem)} --worktree ${shq(wt)} --timeout-sec 540`,
          { require: ['settled'], retryRealFailure: false },
        )
      }
    } catch (_e) { /* best-effort wait — the propose leaf re-reads check state itself */ }
    const proposed = await proposeDodDispositions(workItem, out.pr)
    if (proposed && proposed.ok && Array.isArray(proposed.rows) && proposed.rows.length) {
      // UFR-4: the splice mutates the PR — fence the lease generation first, park on loss.
      const fenced = generation == null ? true : await shipFenceOrPark(workItem, generation, checkoutRoot())
      if (!fenced) {
        return { phaseResult: { confidence: 'low', assumptions: ['lease lost before the DoD disposition splice — park (UFR-4)'] }, sideEffect: null }
      }
      let spliced = null
      try {
        const rowsPath = joinPath(io().tmpdir(), `showrunner-${workItem}-dod-rows.json`)
        await io().writeFile(rowsPath, JSON.stringify(proposed.rows))
        spliced = await courier.runCourierJson(
          'splice DoD dispositions',
          `python3 ${libPath('dod_fill_cli.py')} --pr ${shq(String(out.pr))} --rows ${shq(rowsPath)} --root .`,
          { require: ['ok'], retryRealFailure: false },
        )
      } catch (_e) {
        spliced = null   // splice transport failure -> original honest park stands
      }
      if (spliced && spliced.ok) {
        const retry = await gate()
        out = retry || out   // a transport failure on the re-decide keeps the specific DoD park reason
      }
    }
  }
  if (!out || !out.ok || !out.read_back) {
    return { phaseResult: { confidence: 'low', assumptions: [(out && out.reason) || 'mark-ready gated'] }, sideEffect: null }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { ready: true } }
}

module.exports.draftPRPhase = draftPRPhase
module.exports.markReadyPhase = markReadyPhase
module.exports.testPilotPhase = testPilotPhase
module.exports.defaultTestPilotPhase = defaultTestPilotPhase
module.exports.testPilotDeps = testPilotDeps

// renew-then-fence the lease generation immediately before a branch-/PR-mutating boundary (UFR-4).
// Fail-closed: a null generation or a lost/unreadable lease returns false -> the caller parks BEFORE
// any mutation. Mirrors build_phase.js's fenceOrPark; #118 folds this seam spine-wide.
async function shipFenceOrPark(workItem, generation, root) {
  if (generation == null) return false
  const cmd = fenceCliCmd(workItem, generation, root)
  if (!cmd) return false
  const out = await execJson(cmd, 'fence lease')
  return !!(out && out.ok)
}
module.exports.shipFenceOrPark = shipFenceOrPark

function parseCiChecks(checks) {
  if (checks == null) return { error: 'CI status could not be read' }
  if (!Array.isArray(checks) && checks.stale) return { stale: true }
  if (!Array.isArray(checks) && checks.error) return { error: checks.error || 'CI status could not be read' }
  return { checks: Array.isArray(checks) ? checks : [] }
}

async function checkShipReadiness(workItem, worktree, baseName, generation, checksOnly, root) {
  const baseArg = baseName ? ` --base ${shq(baseName)}` : ''
  const wtArg = worktree ? ` --worktree ${shq(worktree)}` : ''
  const genArg = generation != null ? ` --generation ${shq(String(generation))}` : ''
  const checksArg = checksOnly ? ' --checks-only' : ''
  const r = checkoutRoot(root)
  const rootArg = r ? ` --root ${shq(r)}` : ''
  return courier.runCourierJson(
    'check ship-readiness',
    `python3 ${libPath('ship_phase.py')} --step ship-readiness --work-item ${shq(workItem)}` +
    `${baseArg}${wtArg}${genArg}${checksArg}${rootArg}`,
    { require: checksOnly ? ['checks'] : ['ok', 'reconcile', 'freshness', 'checks'] },
  )
}

async function prepareCiFix(workItem, failing) {
  return courier.runCourierJson(
    'prepare CI fix',
    `python3 ${libPath('ship_phase.py')} --step prepare-ci-fix --work-item ${shq(workItem)} --failing ${shq(JSON.stringify(failing || []))}`,
    { require: ['action', 'read_back'], retryRealFailure: false },
  )
}

async function pushCiFixRecheck(workItem, worktree) {
  const wtArg = worktree ? ` --worktree ${shq(worktree)}` : ''
  return courier.runCourierJson(
    'push CI fix + recheck',
    `python3 ${libPath('ship_phase.py')} --step push-ci-fix-recheck --work-item ${shq(workItem)}${wtArg}`,
    { require: ['read_back', 'checks'], retryRealFailure: false },
  )
}

async function postReadout(workItem, pr, args) {
  const prNum = pr && pr.number ? ` --pr ${shq(String(pr.number))}` : ''
  // #130: the ship hand-back is the run's terminal leaf. Fold the terminal marker (completed vs
  // parked — the durable signal token_trend.py buckets on) and ship's cost telemetry into it, so
  // ship rides no new courier leaf (#118). Both are best-effort inside readout_post.py.
  const termArg = args.terminal ? ` --terminal ${shq(args.terminal)}` : ''
  const costArg = args.costBody ? ` --cost-payload ${shq(JSON.stringify(args.costBody))}` : ''
  const cmd = args.ctx
    ? `python3 ${libPath('readout_post.py')} --work-item ${shq(workItem)}${prNum}${termArg}${costArg} --ctx ${shq(JSON.stringify(args.ctx))}`
    : `python3 ${libPath('readout_post.py')} --work-item ${shq(workItem)} --reason ${shq(args.reason || '')}${prNum}${termArg}${costArg}`
  try {
    return await courier.runCourierJson('post readout', cmd, { require: ['posted'], retryRealFailure: false })
  } catch (_e) {
    return { posted: false, recorded: false, error: 'courier transport failed' }
  }
}

// ── Native back-half seam map (for #118 courier-surface collapse, which sequences AFTER #120) ──
// shipPhase orchestrates four SEPARABLE per-stretch seams, each with the same shape:
//   world-read → renew-then-fence(generation) → mutate (git/gh leaf) → read-back-confirm.
//   1. entry reconcile  — ship_phase.py --step reconcile-head  (idempotent push-reconcile)
//   2. catch-up stretch — ship_phase.py --step freshen          (merge base / conflict-abort / push)
//   3. ci-fix stretch   — ship_phase.py --step {ci,ci-decide,ci-record,fix-push,revert-draft}
//   4. hand-back        — readout_post.py --ctx                 (best-effort; never ship-gated)
// FENCE/LEASE SEAM: the lease generation is threaded from reconcile() → runPhases(deps.generation)
//   → shipPhase(_, _, generation); every mutating boundary calls shipFenceOrPark(workItem, generation)
//   (renew-then-fence, fail-closed) BEFORE the mutation — the same generation build_phase.js fences on.
// IDEMPOTENCY SEAM: create / ready-flip / draft-flip / push-reconcile route through idempotent_write.py
//   (read-reality, apply-once). #118 generalizes that primitive to EVERY durable write (its FR-4).
// #118 may fold/relabel these leaves; #120 deliberately leaves them as clean, un-folded seams.
async function shipPhase(workItem, pr, generation) {
  const storeRoot = checkoutRoot()
  const target = await resolveBuildTarget(workItem)
  const worktree = target && target.worktree ? target.worktree : null
  if (!worktree) {
    return park(workItem, pr, 'could not resolve the build worktree for the back-half — park (no mutation against the repo root)')
  }
  const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const baseName = _srBase || ''
  if (!(await shipFenceOrPark(workItem, generation, storeRoot))) {
    return park(workItem, pr, 'lease lost before reconciling the PR head — park (UFR-4)')
  }
  let ready
  try {
    ready = await checkShipReadiness(workItem, worktree, baseName, generation, false, storeRoot)
  } catch (_e) {
    return park(workItem, pr, 'branch readiness could not be confirmed (unreadable) — park (UFR-2)')
  }
  if (!ready || !ready.ok) {
    const fresh = ready && ready.freshness
    if (fresh && fresh.decision === 'give_up_notify') {
      return park(workItem, pr, 'branch is behind its base after the catch-up limit — update it before merge')
    }
    if (fresh && fresh.decision === 'conflict') {
      return park(workItem, pr, 'bringing in the base conflicts — undone (branch unchanged); please resolve and re-run')
    }
    // fence first: on a lost lease ship_phase.py emits reconcile:{ok:false,reason:'unread'} TOO, so
    // checking reconcile first would mask the lease-loss diagnostic behind a generic reconcile park.
    if (ready && ready.fence && !ready.fence.ok) {
      return park(workItem, pr, 'lease lost before base catch-up — park (UFR-4)')
    }
    const reconcile = ready && ready.reconcile
    if (reconcile && !reconcile.ok) {
      return park(workItem, pr, `could not reconcile the PR head before judging readiness (${reconcile.reason || 'unreadable'})`)
    }
    return park(workItem, pr, `branch freshness could not be confirmed (${(fresh && fresh.decision) || 'unreadable'}) — park (UFR-2)`)
  }
  const integrated = !!ready.integrated
  let ciChecks = ready.checks
  const MAX_CI_PASSES = 6
  // Consecutive settle-leaf budget: each leaf waits ≤540s (the bash_timeout hook floors the
  // Bash tool at 600000ms, so ONE leaf can never outwait a long CI run), and real target
  // projects (weekly-eats, loupe) have CI well past 10 minutes. 4 rounds ≈ 36 min of total
  // patience (≥2x a 15-min run) — per consecutive streak, and only fully grantable while
  // MAX_CI_PASSES budget remains (fix rounds spend from the same pass budget). The counter
  // resets whenever checks actually settle or a fix is pushed (a new CI run deserves fresh
  // patience); MAX_CI_PASSES still bounds the loop.
  const MAX_SETTLE_ROUNDS = 4
  let settleRounds = 0
  for (let pass = 0; pass < MAX_CI_PASSES; pass += 1) {
    const parsed = parseCiChecks(ciChecks)
    if (parsed.error) {
      return park(workItem, pr, typeof parsed.error === 'string' ? parsed.error : 'CI status could not be read')
    }
    if (parsed.stale) {
      try {
        const recheck = await checkShipReadiness(workItem, worktree, baseName, generation, true, storeRoot)
        ciChecks = recheck && recheck.checks
      } catch (_e) {
        return park(workItem, pr, 'CI status could not be read')
      }
      continue
    }
    const ciRes = ciStatusTwin.classify(parsed.checks)
    if (ciRes.status === 'green') {
      return shipHandback(workItem, pr, { ready: true, ci: 'green', integrated, reason: 'merge-ready: CI green and branch up to date — awaiting owner merge' })
    }
    if (ciRes.status === 'none') {
      return shipHandback(workItem, pr, { ready: true, ci: 'none', integrated, reason: 'merge-ready: no required checks ran on the ready PR — confirm checks before merging' })
    }
    if (ciRes.status === 'pending') {
      // The live-run settle-poll deferred from #120 (0.10.0 qualification finding: pending
      // classified as red dispatched a CI fixer at checks that were merely running). CI
      // re-runs are near-deterministic on spec-driven runs because the DoD fill leg edits
      // the PR body and ci.yml's pull_request types include `edited` — pending is WAIT,
      // not FIX. One bounded courier leaf does the whole wait (deterministic, journaled);
      // its budget (540s) sits under the Bash tool ceiling the bash_timeout hook floors
      // to 600000ms, so the CLI's own honest budget-exhausted return is always reachable.
      settleRounds += 1
      let settled = null
      try {
        settled = await courier.runCourierJson(
          'wait for CI to settle',
          `python3 ${libPath('ci_settle_cli.py')} --work-item ${shq(workItem)}${worktree ? ` --worktree ${shq(worktree)}` : ''} --timeout-sec 540`,
          { require: ['settled'], retryRealFailure: false },
        )
      } catch (_e) {
        return park(workItem, pr, 'CI status could not be read while waiting for checks to settle')
      }
      if (!settled || settled.settled !== true) {
        if (settled && settled.checks && !Array.isArray(settled.checks) && settled.checks !== null) { ciChecks = settled.checks; continue }
        if (settleRounds < MAX_SETTLE_ROUNDS && settled && Array.isArray(settled.checks)) {
          ciChecks = settled.checks   // long CI run — another bounded round, budget above
          continue
        }
        const stillPending = (settled && Array.isArray(settled.checks))
          ? ciStatusTwin.classify(settled.checks).pending
          : (ciRes.pending || [])
        return park(workItem, pr, `CI checks still pending after the settle wait (${stillPending.join(', ')}) — confirm checks and re-run`)
      }
      settleRounds = 0
      ciChecks = settled.checks
      continue
    }
    let decided = null
    try {
      decided = await prepareCiFix(workItem, ciRes.failing)
    } catch (_e) {
      return park(workItem, pr, 'CI fix preparation could not be confirmed (unreadable) — park (UFR-2)')
    }
    if (!decided || decided.action === 'revert_and_gate') {
      if (!(await shipFenceOrPark(workItem, generation, storeRoot))) { return park(workItem, pr, 'lease lost before return-to-draft — park (UFR-4)') }
      const rd = await execJson(
        `python3 ${libPath('ship_phase.py')} --step revert-draft --work-item ${shq(workItem)}`, 'revert draft')
      const reverted = !!(rd && rd.ok)
      return shipHandback(workItem, pr, { ready: false, ci: 'red', integrated, reverted,
        reason: reverted
          ? 'checks could not be made to pass — returned to draft for you'
          : `checks could not be made to pass, and the PR could NOT be returned to draft (${(rd && rd.reason) || 'unknown'}) — please set it to draft before merging` })
    }
    if (decided.action === 'fix') {
      if (!decided.ok || decided.read_back === false) {
        return park(workItem, pr, 'could not record the CI-fix round (durable write failed) — park before the fix push (UFR-5)')
      }
      if (!(await shipFenceOrPark(workItem, generation, storeRoot))) { return park(workItem, pr, 'lease lost before CI fix push — park (UFR-4)') }
      await agent(
        `Fix the failing CI checks for this PR in the build worktree${worktree ? ' at ' + worktree : ''}: ${ciRes.failing.join(', ')}. ` +
        `Make ONLY the code changes needed to make the checks pass; do not write CI-log text into a commit.`,
        { label: 'fix-ci' })
      let pushed
      try {
        pushed = await pushCiFixRecheck(workItem, worktree)
      } catch (_e) {
        return park(workItem, pr, 'could not push the CI fix (transport failed) — park, no false ready')
      }
      if (!pushed || !pushed.pushed || pushed.read_back === false) {
        return park(workItem, pr, `could not push the CI fix (${(pushed && pushed.reason) || 'unknown'}) — park, no false ready`)
      }
      settleRounds = 0   // fresh CI run after the fix push — fresh settle patience
      ciChecks = pushed.checks
      continue
    }
    return park(workItem, pr, 'unexpected ci-decide action (' + (decided && decided.action) + ') — park (fail-closed)')
  }
  return park(workItem, pr, 'checks did not complete within the bound — confirm CI before merging')
}

async function park(workItem, pr, reason, mergeReady) {
  const rPost = await postReadout(workItem, pr,
    { reason, terminal: mergeReady ? 'completed' : 'parked', costBody: phaseCostPayload('ship') })
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered
    ? reason
    : `${reason} [warning: readout could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: mergeReady ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}

async function shipHandback(workItem, pr, info) {
  const prUrl = pr && pr.url ? pr.url : ''
  const ctx = {
    pr_url: prUrl,
    ci_status: info.ci === 'green' ? 'green — all required checks pass'
      : info.ci === 'none' ? 'no required checks ran on the ready PR — confirm before merging'
      : 'checks could not be made to pass — returned to draft',
    built_vs_acceptance: info.reason || '',
    smoke: ['Confirm the PR branch contains its base', 'Confirm CI on the ready head', 'Review the diff before merging'],
  }
  if (info.integrated) {
    ctx.integration_note = 'the final commit carries base integration done after the code review (the merged-in base was check-vetted, not re-reviewed)'
  }
  const rPost = await postReadout(workItem, pr,
    { ctx, terminal: info.ready ? 'completed' : 'parked', costBody: phaseCostPayload('ship') })
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered ? info.reason
    : `${info.reason} [warning: hand-back could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: info.ready ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}
module.exports.shipHandback = shipHandback

module.exports.shipPhase = shipPhase
module.exports.park = park

async function defaultPhaseLeaf(_phase, _workItem) {
  return { confidence: 'high', assumptions: [] }
}

module.exports.showrunner = showrunner
module.exports.resolveIntake = resolveIntake
module.exports.recordSkippedPhases = recordSkippedPhases
module.exports.cmdRunner = cmdRunner
module.exports.reconcile = reconcile
module.exports.checkoutRoot = checkoutRoot
module.exports.runPhases = runPhases
module.exports.PHASES = PHASES
module.exports.exec = exec
module.exports.persistPhase = persistPhase
module.exports.phaseCostPayload = phaseCostPayload
module.exports.readStartupState = readStartupState
module.exports.startupStateScript = startupStateScript
module.exports.mergeFrozenSnapshot = mergeFrozenSnapshot
module.exports.readDefinitionDraft = readDefinitionDraft
module.exports.cheapestModel = cheapestModel
module.exports.selfContained = selfContained
module.exports.authorModel = authorModel
