// review_panel_shell.js — the reusable review-panel + loop-to-clean orchestration shell (#86, #115).
//
// CONTROL FLOW ONLY. Every judgement (compile, gate, confidence, the four loop terminals, the
// fix-failure -> halted decision, the circuit breaker) lives in the parity-locked pure-decider
// twins (panel_tally / loop_synthesis / circuit_breaker / loop_state); this shell detects events and
// forwards them IN MEMORY. The shell makes exactly one branch: `if (terminal !== 'continue')`.
const { io } = require('./io_seam.js')
const panelTally = require('./panel_tally.js')
const loopSynthesis = require('./loop_synthesis.js')
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
const verifyGateTwin = require('./verify_gate.js')
const reviewMemory = require('./review_memory.js')
const { libPath } = require('./lib_root.js')   // #170: spine code root for lib composes

const SCHEMA_VERSION = 1
// #396: THREE strictly-ordered duration bounds, so a genuine verify timeout is CLASSIFIED and its
// result file WRITTEN before any outer bound hard-kills the process:
//   gate --timeout (VERIFY_TIMEOUT_SECONDS = 570s)
//     < the courier's Bash-tool floor (600s — injected by hooks/bash_timeout.py, and asked for in the
//       leaf prompt below)
//     < the perl-alarm ceiling (VERIFY_ALARM_SECONDS = 630s).
// verify_gate.py's own subprocess.run(timeout=570) raises TimeoutExpired FIRST and atomically writes a
// distinct `result: "timeout"` (UFR-4) before the 600s Bash kill or the 630s alarm can fire. The alarm
// is the OUTERMOST backstop — it only bites a courier that honors a HIGHER Bash timeout, or a host with
// no bash_timeout hook. The gate is deliberately NOT a mirror of verify_gate.DEFAULT_TIMEOUT (600): it
// is chosen strictly below the Bash floor for this ordering, so the two are independent by design (no
// drift-mirror to keep in sync). `perl` is an assumed host tool here (the repo's own timeout-wrapper
// convention; it ships on macOS + mainstream Linux) — an absent perl fails CLOSED (no result file →
// 'fail'), the safe direction.
const VERIFY_TIMEOUT_SECONDS = 570
const VERIFY_ALARM_SECONDS = 630
// #276: the blocking partition routes through circuit_breaker.isBlocking (case-normalized, fail-closed)
// — the single shared predicate, so this shell never disagrees with the panel gate / breaker on blocks.
const POLICY_SUBJECTS = new Set(['Test', 'Security', 'Code', 'Architecture', 'Failure-Mode'])

// ── #211 decider leaves (couriers): the shell asks the Python deciders "what now?" and receives
// small meaningful JSON — never findings. Each reads the durable round-records.json from disk; the
// scalars the durable skeleton can't hold (gate/present-blocking/uncertified reason) ride DOWN as
// args. A mangled/unparseable answer returns null → the caller fails closed (the decider's
// documented direction). Cheap tier (`courier: true`); the answers carry no oversized payload.
function _jsonAnswer(out) {
  try { const p = JSON.parse((out && out.stdout) || ''); return (p && typeof p === 'object') ? p : null }
  catch (_) { return null }
}

async function planRoundDecider({ runDir, round, roster, changedSubjects, justMarked, coverageTarget, docMode, ioApi }) {
  const args = [libPath('review_loop_plan.py'), 'plan-round',
    '--path', ioApi.join(runDir, 'round-records.json'),
    '--round', String(round),
    '--dimensions', JSON.stringify(roster || [])]
  if (coverageTarget) args.push('--coverage-path', coverageTarget.path, '--coverage-mode', coverageTarget.mode)
  if (changedSubjects !== null && changedSubjects !== undefined) args.push('--changed-subjects', JSON.stringify(changedSubjects))
  if (justMarked) args.push('--just-marked')
  if (docMode) args.push('--doc-mode')
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const ans = _jsonAnswer(await ioApi.runHelper('python3', args, { label: 'plan review round', courier: true }))
    if (ans && ans.ok) return ans
  }
  return null
}

async function tallyRoundDecider({ runDir, round, roster, maxRounds, gate, confidence, missing,
  presentBlocking, uncertifiedReason, fixStatus, verifyResult, enterConfirmation, coverageTarget,
  worklistOutPath, docMode, ioApi }) {
  const args = [libPath('review_loop_plan.py'), 'tally-round',
    '--path', ioApi.join(runDir, 'round-records.json'),
    '--round', String(round),
    '--roster', JSON.stringify(roster || []),
    '--max-rounds', String(maxRounds),
    '--gate', gate,
    '--confidence', confidence,
    '--missing', JSON.stringify(missing || []),
    '--present-blocking', String(presentBlocking || 0),
    '--deferred-path', deferredSetPath(runDir),
    '--fix-status', fixStatus || 'completed']
  if (coverageTarget) args.push('--coverage-path', coverageTarget.path, '--coverage-mode', coverageTarget.mode)
  if (worklistOutPath) args.push('--worklist-out-path', worklistOutPath)
  if (verifyResult !== null && verifyResult !== undefined) args.push('--verify-result', String(verifyResult))
  if (enterConfirmation) args.push('--enter-confirmation')
  if (uncertifiedReason) args.push('--uncertified-reason', uncertifiedReason)
  if (docMode) args.push('--doc-mode')
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const ans = _jsonAnswer(await ioApi.runHelper('python3', args, { label: 'tally review round', courier: true }))
    if (ans && typeof ans.terminal === 'string') return ans
  }
  return null
}

function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  return { schemaVersion: SCHEMA_VERSION, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}

function deferredSetPath(runDir) { return `${runDir}/deferred-set.json` }
// (#211: the JS loadDeferredSet is gone — the tally decider reads deferred-set.json Python-side via
// --deferred-path, fail-soft to {}. This retired the review loop's last prose-vulnerable JS read.)

function reviewerContext(context, coverageDecisions, receiptContext) {
  return Object.assign({}, context || {}, { coverageDecisions: coverageDecisions || [], receiptContext })
}

function annotateChallengedCoverage(coverageDecisions, roundFindings, reviewerSet) {
  const known = new Set((coverageDecisions || []).map((d) => d && d.classKey).filter(Boolean))
  const out = (coverageDecisions || []).map((d) => Object.assign({}, d))
  const byClass = Object.fromEntries(out.filter((d) => d.classKey).map((d) => [d.classKey, d]))
  for (const name of reviewerSet || []) {
    const result = roundFindings[name]
    if (!result || result.status !== 'run') continue
    for (const f of result.findings || []) {
      if (!circuitBreaker.isBlocking(f.severity)) continue
      const key = f.classKey || reviewMemory.classKey(f)
      if (!known.has(key)) continue
      const decision = byClass[key]
      if (decision) decision.challengedBy = name
    }
  }
  return out
}

// #211: the entry read (gatherReviewSetup) rides DECISIONS, so its answer is normally a small direct
// blob. The receipt+chunk transport survives as the EMERGENCY FALLBACK only — an answer that
// unexpectedly outgrows the receipt bound (e.g. a coverage-decision list that has grown large): the
// helper writes the blob to disk Python-side and answers a small receipt, and the shell reassembles it
// via read-chunk. Each chunk ships as RAW TEXT (a readable JSON fragment), not base64 — run-5 evidence
// showed the API safety layer REFUSES an opaque base64-shaped blob as a model answer, and an earlier
// run showed a courier decoding a b64 payload (decode-bait). The reader verifies each chunk's
// chunkHash (over the text exactly as shipped) plus the reconstructed content hash before parsing, so
// any retype still fails closed.
const _SUMMARY_RECEIPT_BOUND = 4000
const _READ_CHUNK_CHARS = 4000

function _jsonFromStdout(out) {
  try { return JSON.parse((out && out.stdout) || '') } catch (_) { return null }
}

// #211: each chunk ships as RAW TEXT (`text`, the on-disk slice verbatim), not a reversed-base64
// blob. run-5 evidence showed the API safety layer refuses an opaque base64-shaped answer, and an
// earlier run showed a courier decoding a b64 payload (decode-bait) — a readable JSON fragment has
// nothing to unwrap and pattern-matches as benign. The chunkHash covers the text exactly as shipped,
// so a courier that retypes or "fixes" the slice breaks the hash and the read fails closed, and the
// reconstructed-content-hash check at the end still guards the full reassembly.
async function _readReceiptText(ioApi, receipt, expectedReceipt, corruptReason) {
  if (!receipt || receipt.receipt !== expectedReceipt || !receipt.path || !receipt.contentHash) return { ok: false, reason: corruptReason }
  const chunkSize = receipt.chunkSize || _READ_CHUNK_CHARS
  let index = 0
  let text = ''
  for (let guard = 0; guard < 10000; guard += 1) {
    let parsed = null
    for (let attempt = 0; attempt < 3; attempt += 1) {
      // payload marker: chunk answers are ~2KB relay payloads — they ride the copy-faithful
      // payload tier, not the cheapest courier tier (#191 gap: the read leg missed the pin).
      const out = await ioApi.runHelper('python3', [libPath('review_memory.py'), 'read-chunk', '--path', receipt.path, '--index', String(index), '--chunk-size', String(chunkSize)], { payload: true })
      parsed = _jsonFromStdout(out)
      if (!parsed || !parsed.ok || parsed.index !== index) { parsed = null; continue }
      if (parsed.contentHash !== receipt.contentHash) { parsed = null; continue }
      if (typeof parsed.text !== 'string' || parsed.chunkHash !== ioApi.contentHash(parsed.text)) { parsed = null; continue }
      break
    }
    if (!parsed) return { ok: false, reason: corruptReason }
    text += parsed.text
    if (parsed.eof) break
    index = Number(parsed.nextIndex)
    if (!Number.isFinite(index)) return { ok: false, reason: corruptReason }
  }
  if (ioApi.contentHash(text) !== receipt.contentHash) return { ok: false, reason: corruptReason }
  return { ok: true, text }
}

// D3: the DURABLE round record is the bounded SKELETON (review_memory.skeletonRecord — evidence
// bodies and receipts stripped, finding identity/class/severity kept), persisted in ONE verified
// CAS leaf for the typical
// round: the skeleton rides the courier args inline, self-verified by --record-hash =
// sha256(record-json) — a courier that mangles the JSON cannot also recompute its hash, so
// corruption fails closed as record-corrupt (one retry, then cannot-certify upstream) instead
// of persisting silently altered content. A many-finding round whose skeleton outgrows a safe
// inline arg falls back to a staged file (+1 unverified stage leaf; the same hash check covers
// it). Python re-applies summarize_record on arrival, so evidence bodies can never land in
// round-records.json even if the JS twin drifts. Full bodies of the audit targets
// (dropped/deferred findings) ride the separate BEST-EFFORT round-bodies dump; the final
// round's bodies live in terminal-record.json.
const _INLINE_RECORD_BOUND = 6000

// _selfVerifiedHelper: run a review_memory.py write verb whose payload self-verifies in
// transport (--…-hash = sha256 of the exact text). Retries ONCE on a transport-corrupt
// payload or an unparseable answer; a real refusal (stale/unreadable/round-missing) is
// final. The helper side answers ok-idempotently when a prior attempt already persisted
// this exact write and only its ANSWER was lost — so the retry-after-mangled-answer path
// converges instead of dying 'stale'.
async function _selfVerifiedHelper(ioApi, args, stagedPath, stagedText, corruptReason) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    let out
    if (stagedPath) {
      try {
        out = await ioApi.stageAndRunHelper(stagedPath, stagedText, 'python3', args)
      } catch (_) {
        // a missing parent dir is the common first-attempt failure (fresh run dir); create it
        // and let the retry re-stage.
        const dir = String(stagedPath).slice(0, String(stagedPath).lastIndexOf('/'))
        if (dir) { try { await ioApi.mkdirp(dir) } catch (_e) { /* the retry fails closed */ } }
        continue
      }
    } else {
      out = await ioApi.runHelper('python3', args)
    }
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    if (parsed && parsed.reason && parsed.reason !== corruptReason) return { ok: false, reason: parsed.reason }
  }
  return { ok: false, reason: 'helper-failed' }
}

async function persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi) {
  const recordJson = JSON.stringify(reviewMemory.skeletonRecord(record))
  const inline = recordJson.length <= _INLINE_RECORD_BOUND
  const stagedPath = inline ? null : ioApi.join(runDir, `round-skeleton-r${record.round}.json`)
  const args = [libPath('review_memory.py'), 'persist-skeleton',
    '--path', ioApi.join(runDir, 'round-records.json')]
  args.push(...(inline ? ['--record-json', recordJson] : ['--record-path', stagedPath]))
  args.push('--record-hash', ioApi.contentHash(recordJson),
    '--round', String(record.round), '--dimensions', JSON.stringify(reviewerSet || []),
    '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId)
  if (lease) args.push('--lease', lease)
  return _selfVerifiedHelper(ioApi, args, stagedPath, recordJson, 'record-corrupt')
}

// D3 best-effort forensics: the FULL bodies of this round's dropped + deferred findings — the
// audit targets (UFR-10 dropped-blocker evidence, receipt trust audits). A fixed finding's
// evidence is its fix commit, so fixed bodies don't ride. ONE fire-and-forget leaf under the
// spec's FR-4 best-effort carve-out: nothing advances on this write, so a failed (or
// courier-mangled) dump degrades the audit trail, never the run.
async function dumpRoundBodiesBestEffort(runDir, round, verdict, fixReport, ioApi) {
  const drops = (verdict && Array.isArray(verdict.drops)) ? verdict.drops : []
  const deferred = (fixReport && Array.isArray(fixReport.deferred)) ? fixReport.deferred : []
  if (!drops.length && !deferred.length) return
  try {
    await ioApi.writeFile(ioApi.join(runDir, `round-bodies-r${round}.json`),
      JSON.stringify({ schemaVersion: 1, round, drops, deferred }))
  } catch (_) { /* best-effort by contract */ }
}

// (#211: mergeRoundRecords is gone — the shell no longer keeps an in-memory records copy; the
// durable skeleton on disk is the single source of truth the deciders read.)

// The post-fix update ships only the SMALL delta (confirmation marker, changed subjects,
// coverage decisions, fix summary) — never the round body — via review_memory.py update-round,
// self-verified in transport like persist-skeleton (--updates-hash; staged-file fallback past
// the safe inline size — the delta is usually small but coverageDecisions/fixes are unbounded).
// Deferred entries ride slimmed (identity/severity/reason + skeleton finding): their full
// bodies go to the round-bodies dump, not through this pipe or into round-records.json.
async function persistPostFixRecord(runDir, reviewerSet, round, fixResult, recordedCoverageDecisions, expectedHash, runId, lease, ioApi, legKind) {
  const updates = {
    changedSubjects: fixResult.changedSubjects || [],
    coverageDecisions: reviewMemory.skeletonCoverageDecisions(recordedCoverageDecisions || []),
    fix: {
      fixes: fixResult.fixes || fixResult.fixed || [],
      deferred: reviewMemory.skeletonDeferred(fixResult.deferred || []),
      changedSubjectDetails: fixResult.changedSubjectDetails || [],
    },
  }
  if (legKind && legKind.panel) updates.confirmationPending = true
  const updatesJson = JSON.stringify(updates)
  const inline = updatesJson.length <= _INLINE_RECORD_BOUND
  const stagedPath = inline ? null : ioApi.join(runDir, `round-updates-r${round}.json`)
  const args = [libPath('review_memory.py'), 'update-round',
    '--path', ioApi.join(runDir, 'round-records.json'), '--round', String(round)]
  args.push(...(inline ? ['--updates-json', updatesJson] : ['--updates-path', stagedPath]))
  args.push('--updates-hash', ioApi.contentHash(updatesJson),
    '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId)
  if (lease) args.push('--lease', lease)
  const parsed = await _selfVerifiedHelper(ioApi, args, stagedPath, updatesJson, 'updates-corrupt')
  if (!parsed.ok) return { ok: false, reason: parsed.reason || 'helper-failed' }
  // #211: only the CAS hash rides back — the shell keeps no in-memory record copy (the durable
  // skeleton on disk is the source of truth the deciders read next round).
  return { ok: true, contentHash: parsed.contentHash }
}

async function coverageDecisionTarget(runDir, context, legKind, ioApi) {
  if (context && context.docPath) return { mode: 'doc', path: context.docPath }
  const path = (context && context.coverageDecisionPath) || (legKind && legKind.coverageDecisionPath) || ioApi.join(runDir, 'review-coverage-decisions.json')
  return { mode: 'code', path }
}

// The coverage read is computed entirely PYTHON-SIDE (coverage_decisions.py load): decisions
// parsed and the fence hash taken over the exact on-disk bytes. A raw courier readText here
// poisoned the loop live (2026-07-02, 4 runs): the sandbox io leaf answers PROSE for a
// missing/odd file, and contentHash(prose) turned every later fenced write into a permanent
// 'stale' park — courier text must never enter an integrity decision. A mangled helper
// ANSWER fails JSON.parse and parks fail-closed (never silently-empty decisions).
async function loadCoverageDecisions(target, ioApi) {
  const out = await ioApi.runHelper('python3', [libPath('coverage_decisions.py'), 'load',
    '--path', target.path, '--mode', target.mode === 'doc' ? 'doc' : 'code'])
  const stdout = String((out && out.stdout) || '')
  try {
    const parsed = JSON.parse(stdout)
    if (parsed && typeof parsed === 'object') return parsed
  } catch (_) { /* fall through to fail-closed */ }
  const firstBrace = stdout.indexOf('{')
  const lastBrace = stdout.lastIndexOf('}')
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    try {
      const parsed = JSON.parse(stdout.slice(firstBrace, lastBrace + 1))
      if (parsed && typeof parsed === 'object') return parsed
    } catch (_) { /* fall through to fail-closed */ }
  }
  return { ok: false, state: 'unreadable', reason: 'coverage-load-helper-failed' }
}

function collectRoundUsage(roundFindings, round, synthesized) {
  const usage = {}
  for (const [name, result] of Object.entries(roundFindings || {})) {
    const real = _realUsage(result && result.usage)
    if (real) usage[`${name}:r${round}`] = real
  }
  const synthUsage = _realUsage(synthesized && synthesized.usage)
  if (synthUsage) usage[`synthesis:r${round}`] = synthUsage
  return usage
}

function _realUsage(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const out = {}
  let positive = false
  for (const [key, v] of Object.entries(value)) {
    if (typeof v !== 'number' || !Number.isFinite(v)) continue
    if (v > 0) positive = true
    out[key] = v
  }
  return positive ? out : null
}

function _stripZeroUsage(out) {
  if (!out || typeof out !== 'object' || Array.isArray(out)) return out
  const usage = _realUsage(out.usage)
  if (usage) return Object.assign({}, out, { usage })
  if (!Object.prototype.hasOwnProperty.call(out, 'usage')) return out
  const cleaned = Object.assign({}, out)
  delete cleaned.usage
  return cleaned
}

function _expectedReceiptIds(opts) {
  opts = opts || {}
  if (Array.isArray(opts.receiptCoverageDecisionIds)) return opts.receiptCoverageDecisionIds.filter(Boolean)
  return (opts.coverageDecisions || []).map((d) => d && d.id).filter(Boolean)
}

function _reviewerReceiptIssue(result, opts) {
  if (!result || result.confidence !== 'high' || result.externalReview) return null
  const receipt = result.verificationReceipt
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) return 'missing'
  if (opts && opts.receiptArtifact && receipt.artifact !== opts.receiptArtifact) return 'stale'
  if (!Array.isArray(receipt.coverageDecisionIds)) return 'stale'
  const gotIds = new Set(receipt.coverageDecisionIds || [])
  for (const id of _expectedReceiptIds(opts)) if (!gotIds.has(id)) return 'stale'
  const neededSteps = new Set(['citation', 'reachability', 'missing-check', 'tooling'])
  for (const step of Array.isArray(receipt.chain) ? receipt.chain : []) {
    if (step && typeof step === 'object' && step.evidence) neededSteps.delete(step.step)
  }
  return neededSteps.size ? 'stale' : null
}

function _withReceiptFreshness(shaped, opts) {
  if (!shaped || !Array.isArray(shaped.findings) || shaped.confidence !== 'high' || shaped.externalReview) return shaped
  const issue = _reviewerReceiptIssue(shaped, opts || {})
  if (!issue) return shaped
  const out = Object.assign({}, shaped, { confidence: 'low' })
  if (issue === 'missing') out.receiptMissing = true
  else {
    out.receiptStale = true
    out.findings = []
  }
  return out
}

function _retryableReviewerIssue(out) {
  return !_validReviewerResult(out) || !!(out && (out.receiptMissing || out.receiptStale))
}

// #212: a retry that exists to cure a SPECIFIC defect must say which one, so reviewerAgent can add a
// corrective instruction (a blind re-dispatch of the identical prompt just re-flips the same coin).
// Covers every retryable cause, not only receipts: `malformed` catches a schema-failing/off-task
// answer (live precedent: a reviewer glitched onto an unrelated MCP connector and returned nonsense).
function _retryReason(out) {
  // FR-1/FR-2: a denied verification probe (permissionDenied) is degraded to receiptMissing by
  // ensureReviewerShape, but its retry must NOT be told to "supply a receipt" — it must be told the
  // denied probe is FINAL and to verify another way / return low. Surface it ahead of receipt-missing.
  if (out && out.permissionDenied) return 'permission-denied'
  if (out && out.receiptMissing) return 'receipt-missing'
  if (out && out.receiptStale) return 'receipt-stale'
  if (!_validReviewerResult(out)) return 'malformed'
  return null
}

function expectedUsageLeaves(reviewerSet, round, legKind, fixRan) {
  const leaves = (reviewerSet || []).map((name) => `${name}:r${round}`)
  if (legKind && legKind.panel) leaves.push(`synthesis:r${round}`)
  if (legKind && legKind.code) leaves.push(`verify:r${round}`)
  if (fixRan) leaves.push(`fix:r${round}`)
  return leaves
}

// The telemetry round scalars (roundCount, dimensionCounts) come from round-records.json ON
// DISK (review_telemetry.py write-from-records composes Python-side); only small scalars ride
// the invocation, and the helper answers with the same small summary it wrote (D3: telemetry
// never embeds rounds) so finalizeVerdict never re-reads the file back through the pipe.
// No expected-hash: the telemetry file is a single-writer run artifact written once at the
// terminal — the old pre-read + CAS pair cost a leaf and protected nothing the lease doesn't.
async function writeTelemetry(runDir, expectedLeaves, usage, terminal, runId, lease, ioApi) {
  const args = [libPath('review_telemetry.py'), 'write-from-records',
    '--path', ioApi.join(runDir, 'review-telemetry.json'),
    '--records-path', ioApi.join(runDir, 'round-records.json'),
    '--expected-leaves-json', JSON.stringify(expectedLeaves || []),
    '--usage-json', JSON.stringify(usage || {}),
    '--run-id', runId]
  if (terminal) args.push('--terminal', String(terminal))
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, benchmarkValid: false, reason: 'telemetry-write-failed' }
  } catch (_) {
    return { ok: false, benchmarkValid: false, reason: 'telemetry-write-failed' }
  }
}

async function recordCoverageDecision(targetPath, decision, expectedHash, mode, runId, lease, ioApi) {
  const cmd = mode === 'code' ? 'record-code' : 'record-doc'
  const args = [libPath('coverage_decisions.py'), cmd, '--path', targetPath, '--decision-json', JSON.stringify(decision), '--expected-hash', expectedHash, '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'coverage-decision-write-failed' }
  } catch (_) {
    return { ok: false, reason: 'coverage-decision-write-failed' }
  }
}

// gatherReviewSetup: fold 2 (#141) — run the review loop's decision-free entry stretch (run-dir
// mkdir + deferred-set seed read + entry-bootstrap + coverage load) as ONE review_setup_gather.py leaf,
// all Python-side. Returns the combined blob { ok, memory, deferredSet, coverage } for the caller to
// hand reviewPanel as `preloaded` (and, on the doc leg, to seed runtimeDeferred). Returns null on a
// gather transport failure — the caller then falls back to a plain mkdir + reviewPanel's own reads
// (correct, just unfolded). reviewerSet MUST equal the set the caller passes reviewPanel, so the
// gathered memory/coverage are byte-parity with reviewPanel's own entry reads.
async function gatherReviewSetup({ runDir, reviewerSet, context, legKind, ioApi }) {
  const api = ioApi || io()
  const target = await coverageDecisionTarget(runDir, context, legKind || {}, api)
  const args = [libPath('review_setup_gather.py'), 'gather',
    '--run-dir', runDir,
    '--records-path', api.join(runDir, 'round-records.json'),
    '--dimensions', JSON.stringify(reviewerSet || []),
    '--extras-path', api.join(runDir, 'last-extras.json'),
    '--deferred-path', api.join(runDir, 'deferred-set.json'),
    '--coverage-path', target.path,
    '--coverage-mode', target.mode === 'doc' ? 'doc' : 'code',
    '--out-path', api.join(runDir, 'review-setup-gather.json'),
    '--receipt-threshold', String(_SUMMARY_RECEIPT_BOUND)]
  if (legKind && legKind.docMode) args.push('--doc-mode')
  const out = await api.runHelper('python3', args, { payload: true })
  let parsed = _jsonFromStdout(out)
  if (parsed && parsed.receipt === 'review-setup-gather') {
    const read = await _readReceiptText(api, parsed, 'review-setup-gather', 'review-setup-gather-unreadable')
    if (!read.ok) return null
    try { parsed = JSON.parse(read.text) } catch (_) { parsed = null }
  }
  if (parsed && parsed.ok && parsed.resume && parsed.coverage) {
    if (!parsed.deferredSet || typeof parsed.deferredSet !== 'object') parsed.deferredSet = {}
    return parsed
  }
  return null
}

async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none', verifyCwd = null,
                            forceCoverageDecisionExpectedHash, preloaded }) {
  runDir = runDir || runKey
  const runId = runKey || runDir
  const lease = legKind && legKind.lease
  const ioApi = io()
  // #211: the entry read rides DECISIONS, not records. The doc/code leg hands us a PRELOADED gather
  // (resume decision + round-1 plan + coverage + deferred, folded into ONE leaf); standalone (the
  // smokes) we self-gather. The shell holds NO findings — only decisions + the CAS hash. One retry,
  // then a mangled/unreadable entry parks cannot-certify (never a fresh round on an unverifiable seed).
  let setup = (preloaded && preloaded.resume) ? preloaded
    : await gatherReviewSetup({ runDir, reviewerSet: reviewerSet || [], context, legKind, ioApi })
  if (!setup || !setup.resume) {
    setup = await gatherReviewSetup({ runDir, reviewerSet: reviewerSet || [], context, legKind, ioApi })
  }
  const resume = setup && setup.resume
  let round = (resume && resume.round) || 1
  const allUsage = {}
  let fixRanThisRun = false
  if (!resume || !resume.ok) {
    // a stable machine-readable park reason (round-memory-<state>), never a raw loader exception —
    // a mangled gather (resume null) is 'round-memory-unreadable', a corrupt file 'round-memory-corrupt'.
    const reason = (resume && resume.state) ? 'round-memory-' + resume.state
      : 'round-memory-unreadable'
    return await finalizeVerdict(
      { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason, round },
      reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
  }
  let memoryContentHash = resume.contentHash
  let lastExtras = resume.extras !== undefined ? resume.extras : null
  let entryPlan = setup.plan || null
  let entryCoverage = setup.coverage || null
  let justMarkedForConfirmation = false

  if (!reviewerSet || reviewerSet.length === 0) {
    const v = await tallyRound({ runDir, round, roster: reviewerSet || [], maxRounds,
                                   roundFindings: {}, legKind, verifyResult: null,
                                   policy: { roundKind: 'baseline' }, coverageDecisions: [],
                                   coverageTarget: null, runId, extras: lastExtras, docMode: legKind && legKind.docMode, ioApi })
    return _usable(v) ? await finalizeVerdict(v, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi) : _failClosed()
  }

  while (true) {
    const coverageTarget = await coverageDecisionTarget(runDir, context, legKind, ioApi)
    // The PLAN decision (schedule + carried + enterConfirmation) and the per-round coverage read.
    // Round 1: both came from the entry gather (consume once). Later rounds: the plan-round decider
    // with the coverage read FOLDED in (one round-entry leaf, #118). A mangled plan answer parks.
    let plan, coverageState
    if (entryPlan) {
      plan = entryPlan; entryPlan = null
      coverageState = entryCoverage; entryCoverage = null
    } else {
      plan = await planRoundDecider({ runDir, round, roster: reviewerSet,
        changedSubjects: (lastExtras && lastExtras.changedSubjects),
        justMarked: justMarkedForConfirmation, coverageTarget, docMode: legKind && legKind.docMode, ioApi })
      if (!plan) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-plan-unreadable', round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      coverageState = plan.coverage || null
    }
    justMarkedForConfirmation = false
    if (!coverageState || !coverageState.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decisions-' + ((coverageState && (coverageState.state || coverageState.reason)) || 'unreadable'), round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    const coverageDecisions = coverageState.decisions
    let coverageContentHash = coverageState.contentHash
    const enterConfirmation = !!plan.enterConfirmation
    const roundKind = plan.roundKind

    // #174 confirmation coverage-marker check: every coverage id the latest record marked (the plan
    // decider surfaces them from disk) must still be visible in the live coverage — a decision lost
    // between marking and confirmation parks rather than certifies over a missing principle.
    if (enterConfirmation && Array.isArray(plan.latestCoverageDecisionIds) && plan.latestCoverageDecisionIds.length) {
      const visible = new Set(coverageDecisions.map((d) => d.id))
      if (plan.latestCoverageDecisionIds.some((id) => !visible.has(id))) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decision-marker-missing', round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
    }

    const scheduled = plan.dimensions || {}
    // #394: a leg whose reviewerAgent ALWAYS dispatches at a single fixed tier declares that tier
    // (legKind.dispatchTier). The whole-branch final-review leg (legKind.panel:false, build_phase's
    // tier-blind reviewerAgent) is the case: it unconditionally dispatches deep. But the round policy
    // tiers a post-baseline round with prior findings as CHEAP ('reviewer'), which — via
    // _shapeReviewerResult stamping a findings-bearing cheap answer 'low' — arms dispatchReviewer's
    // cheap->deep escalation into a BYTE-IDENTICAL re-dispatch of the already-deep review (the first,
    // completed answer discarded). Pinning the scheduled run-tier to the leg's honest dispatch tier
    // makes the confidence stamp truthful and the escalation branch never arm. The per-task panel legs
    // (legKind.panel:true) declare no dispatchTier, so their real cheap->deep escalation is untouched.
    if (legKind && legKind.dispatchTier) {
      for (const name of Object.keys(scheduled)) {
        const sched = scheduled[name]
        if (sched && sched.action === 'run' && sched.tier !== legKind.dispatchTier) {
          scheduled[name] = Object.assign({}, sched, { tier: legKind.dispatchTier })
        }
      }
    }
    const roundFindings = {}
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: coverageDecisions.map((d) => d.id).filter(Boolean) }
    await parallel(reviewerSet
      .filter((r) => (scheduled[r] || {}).action !== 'skip')
      .map((r) => () => dispatchReviewer(r, reviewerContext(context, coverageDecisions, receiptContext), rubric, runDir, round, roundFindings, Object.assign({}, scheduled[r], { roundKind, coverageDecisions, receiptContext, receiptArtifact: receiptContext.artifact }))))
    for (const [name, sched] of Object.entries(scheduled)) {
      // the carried (skipped-dimension) state comes from the plan decider (structurally clean —
      // findings empty by construction); a defensive fallback covers a missing carried entry.
      if (sched.action === 'skip') roundFindings[name] = (plan.carried && plan.carried[name]) ||
        { status: 'skipped', findings: [], confidence: 'low', carriedFromRound: sched && sched.carriedFromRound }
    }

    let synthesized = null
    if (legKind.panel) {
      try {
        synthesized = await synthesizeRound(roundFindings, context, rubric, runDir, round)
      } catch (e) {
        try { log(`review-panel r${round}: synthesis threw (${e && e.message ? e.message : e}) — falling back to raw compile`) } catch (_) {}
        synthesized = null
      }
      if (!synthesized) {
        try { log(`review-panel r${round}: synthesis produced no result — falling back to raw compile (no findings dropped)`) } catch (_) {}
      }
      graftSynthesizedFindings(roundFindings, synthesized)
    }

    let verifyResult = null
    if (legKind.code) {
      try { verifyResult = await verifyAgent(verifyCommand, runDir, round, ioApi, verifyCwd) }
      catch (e) { verifyResult = 'fail' }
      // #279 bounded corrective re-run: when verify is the SOLE blocker — a 'fail' with zero blocking
      // findings this round — the fix loop has nothing to resolve and so can never earn a re-verify,
      // and one transient infra flake (a module-resolution error in an untouched file, node_modules
      // still settling after an in-branch install, a shared vite-cache collision) becomes a terminal
      // halt on a branch that found nothing to fix. Re-run verify exactly once (serialized, same round
      // file). Two consecutive fails reproduce today's fail-closed halt exactly — no loop, cap 1
      // (precedent: #212 corrective retry / fix-before-park). A round with blocking findings takes the
      // fix leg (which re-verifies next round), so the re-run is scoped to the no-work case only.
      if (verifyResult === 'fail' && panelTally.presentBlockingFromDimensionResults(roundFindings) === 0) {
        try { log(`review-panel r${round}: verify failed with zero blocking findings — one bounded corrective re-run (#279)`) } catch (_) {}
        try { verifyResult = await verifyAgent(verifyCommand, runDir, round, ioApi, verifyCwd) }
        catch (e) { verifyResult = 'fail' }
        // Surface the flake vs the real regression: a fail→pass flip means the verify gate is flaky
        // (worth investigating the infra cause); a fail→fail confirms a genuine failure (halts below).
        try { log(`review-panel r${round}: corrective re-run verify → ${verifyResult}`) } catch (_) {}
      }
    }

    const tokenUsage = collectRoundUsage(roundFindings, round, synthesized)
    Object.assign(allUsage, tokenUsage)

    const roundCoverageDecisions = annotateChallengedCoverage(coverageDecisions, roundFindings, reviewerSet)
    const record = reviewMemory.recordFromDimensionResults(round, roundKind, roundFindings, lastExtras && lastExtras.changedSubjects, roundCoverageDecisions, tokenUsage, enterConfirmation && roundKind === 'confirmation')
    // persist the SKELETON down (the verified CAS write, unchanged) — then discard it: the tally
    // decider reads the just-persisted disk state, so the shell keeps no record copy in memory.
    const persisted = await persistRoundRecord(runDir, reviewerSet, record, memoryContentHash, runId, lease, ioApi)
    if (!persisted.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    memoryContentHash = persisted.contentHash

    // the tally reads the just-persisted rounds from disk (breaker + terminal + confirmation
    // economics + certification) and, on a continue, writes the fixer worklist to the SAME leaf and
    // rides only its pointer back. gate / present-blocking / uncertified-reason ride DOWN (below).
    const verdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
      roundFindings, legKind, synthesized, verifyResult, policy: { roundKind }, coverageDecisions: roundCoverageDecisions,
      coverageTarget, runId, extras: lastExtras, enterConfirmation, docMode: legKind && legKind.docMode, ioApi })
    if (!_usable(verdict)) return _failClosed()

    if (verdict.terminal !== 'continue') {
      return await finalizeVerdict(verdict, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }

    if (verdict.reason === 'awaiting final confirmation round') {
      round += 1
      continue
    }

    fixRanThisRun = true
    // #211 pointers-down: the fixer receives the worklist PATH (the tally leaf wrote it), never
    // inlined findings. A continue with no worklist pointer means the fold write failed — park.
    const worklistPath = verdict.worklistPath
    if (!worklistPath) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'fix-context-' + (verdict.worklistReason || 'write-failed'), round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    const fixResult = await runFixStep(fixStep, { worklistPath, round }, verdict, runDir)
    if (!fixResult.ok) {
      const failVerdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
        roundFindings, legKind, synthesized, verifyResult, policy: { roundKind }, coverageDecisions: roundCoverageDecisions,
        coverageTarget, runId, extras: fixResult.extras || lastExtras, fixStatus: 'failed', enterConfirmation, docMode: legKind && legKind.docMode, ioApi })
      return await finalizeVerdict(
        _usable(failVerdict) ? failVerdict : _failClosed(),
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }

    lastExtras = fixResult.extras || { changedSubjects: (fixResult.fixResult && fixResult.fixResult.changedSubjects) || [], needsConfirmation: true }
    let recordedCoverageDecisions = coverageDecisions
    let expectedCovHash = forceCoverageDecisionExpectedHash || coverageContentHash
    for (const decision of ((fixResult.fixResult && fixResult.fixResult.coverageDecisions) || [])) {
      const target = await coverageDecisionTarget(runDir, context, legKind, ioApi)
      const res = await recordCoverageDecision(target.path, decision, expectedCovHash, target.mode, runId, lease, ioApi)
      if (!res.ok) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decision-write-failed', round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      const reloaded = await loadCoverageDecisions(target, ioApi)
      if (!reloaded.ok) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decisions-' + (reloaded.state || 'unreadable'), round },
          reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      recordedCoverageDecisions = reloaded.decisions
      expectedCovHash = reloaded.contentHash
      coverageContentHash = reloaded.contentHash
    }

    // body dump BEFORE the post-fix persist: both must happen, the dump is best-effort
    // anyway, and this ordering shrinks the crash window in which the audit bodies are
    // lost while the delta survives (or vice versa) at zero protocol cost.
    await dumpRoundBodiesBestEffort(runDir, round, verdict, fixResult.fixResult || {}, ioApi)
    const postFix = await persistPostFixRecord(runDir, reviewerSet, round, fixResult.fixResult || {}, recordedCoverageDecisions, memoryContentHash, runId, lease, ioApi, legKind)
    if (!postFix.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    memoryContentHash = postFix.contentHash
    justMarkedForConfirmation = true
    try { await ioApi.writeFile(`${runDir}/last-extras.json`, JSON.stringify(lastExtras)) } catch (_) {}
    round += 1
  }
}

async function finalizeVerdict(verdict, reviewerSet, round, legKind, fixRan, allUsage, runDir, runId, lease, ioApi) {
  const expectedLeaves = []
  for (let r = 1; r <= round; r += 1) expectedLeaves.push(...expectedUsageLeaves(reviewerSet, r, legKind, fixRan && r === round))
  const telemWrite = await writeTelemetry(runDir, expectedLeaves, allUsage, verdict.terminal, runId, lease, ioApi)
  // Attach the SMALL summary the helper answered with (the round history stays in
  // round-records.json only) — re-reading the telemetry file back through the pipe would
  // re-create the mega-payload hop, and a verdict embedding every round would ride the
  // terminal-record write the same way.
  let telemetry = { benchmarkValid: false, reason: 'telemetry-write-failed' }
  if (telemWrite.ok) {
    telemetry = Object.assign({}, telemWrite)
    delete telemetry.ok
  }
  return Object.assign({}, verdict, { telemetry })
}

function _validReviewerResult(out) {
  return !!out && Array.isArray(out.findings) && (out.confidence === 'high' || out.confidence === 'low')
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

function _shapeReviewerResult(out, opts) {
  if (Array.isArray(out)) {
    const conf = ((opts || {}).tier === 'reviewer' && out.length > 0) ? 'low' : 'high'
    return { findings: normalizeReviewerFindings(out), confidence: conf, legacyArray: true }
  }
  const shaped = _stripZeroUsage(out)
  if (!shaped || !Array.isArray(shaped.findings)) return shaped
  return _withReceiptFreshness(Object.assign({}, shaped, { findings: normalizeReviewerFindings(shaped.findings) }), opts || {})
}

async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings, opts) {
  const baseOpts = opts || {}
  let out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, baseOpts), baseOpts)
  let escalated = false
  if (baseOpts.tier === 'reviewer' && (_retryableReviewerIssue(out) || out.confidence !== 'high')) {
    escalated = true
    // #212: the escalation to reviewer-deep IS a re-dispatch — carry the corrective retryReason when
    // the shallow answer had a curable defect (null when it was just an honest low, nothing to correct).
    const deepOpts = Object.assign({}, baseOpts, { tier: 'reviewer-deep', escalatedFrom: 'reviewer', retryReason: _retryReason(out) })
    out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, deepOpts), deepOpts)
    if (_retryableReviewerIssue(out)) {
      out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, deepOpts, { retryFrom: 'reviewer-deep', retryReason: _retryReason(out) })), deepOpts)
    }
  } else if (baseOpts.tier === 'reviewer-deep' && _retryableReviewerIssue(out)) {
    out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, baseOpts, { tier: 'reviewer-deep', retryFrom: 'reviewer-deep', retryReason: _retryReason(out) })), baseOpts)
  }
  if (!_validReviewerResult(out)) {
    roundFindings[reviewer] = { status: 'missing', dimension: reviewer, findings: [], confidence: 'low', malformed: true, legacyArray: !!(out && out.legacyArray), escalated }
    return
  }
  roundFindings[reviewer] = Object.assign({ status: 'run', dimension: reviewer, escalated, tier: baseOpts.tier, malformed: false }, out)
}

async function synthesizeRound(roundFindings, context, rubric, runDir, round) {
  const compiled = panelTally.compileDimensionResults(roundFindings)
  const leaf = await synthesisLeaf(compiled, context, rubric, runDir, round)
  const consumed = loopSynthesis.consume(compiled, leaf && Array.isArray(leaf.verdicts) ? leaf.verdicts : [])
  return Object.assign(consumed, { usage: leaf && leaf.usage })
}

function graftSynthesizedFindings(roundFindings, synthesized) {
  if (!synthesized || typeof synthesized !== 'object' || !Array.isArray(synthesized.findings)) return
  const keptById = Object.create(null)
  for (const kept of synthesized.findings) {
    if (!kept || typeof kept !== 'object' || Array.isArray(kept)) continue
    keptById[circuitBreaker.findingIdentity(kept)] = kept
  }
  for (const [name, result] of Object.entries(roundFindings || {})) {
    if (!result || typeof result !== 'object' || !Array.isArray(result.findings)) continue
    const findings = []
    for (const finding of result.findings) {
      if (!finding || typeof finding !== 'object' || Array.isArray(finding)) continue
      const kept = keptById[circuitBreaker.findingIdentity(finding)]
      if (!kept) {
        if (finding.file === null || finding.file === undefined || finding.line === null || finding.line === undefined) {
          // synthesis could not verify this no-location finding (no keep verdict) but we keep it so
          // it still counts for the gate. Flag it `synthesisUnverified` so the tally decider can
          // reproduce the OLD `compiled` view: the CURRENT round's breaker findings + present-deferred
          // EXCLUDE it (synthesis dropped it), while recurrence/generalize over prior rounds still
          // see it (#211 parity — this preserves the #174 generalize-grace, which relied on exactly
          // this current=compiled / prior=record asymmetry).
          findings.push(Object.assign({}, finding, { synthesisUnverified: true }))
        }
        continue
      }
      const enriched = Object.assign({}, finding)
      if ((enriched.title === undefined || enriched.title === null || enriched.title === '') &&
          kept.title !== undefined && kept.title !== null && kept.title !== '') {
        enriched.title = kept.title
      }
      if (kept.severity !== undefined && kept.severity !== null && kept.severity !== '') enriched.severity = kept.severity
      if (!enriched.classKey && kept.classKey) enriched.classKey = kept.classKey
      findings.push(enriched)
    }
    roundFindings[name] = Object.assign({}, result, { findings })
  }
}

async function verifyAgent(verifyCommand, runDir, round, ioApi, cwd) {
  // dumb pipe (run verify_gate.py, echo its JSON): courier:true so the bundle preamble pins it to
  // the cheapest model unconditionally (#118 — an unmarked label like 'run verify' inherits the
  // session model). The preamble strips the marker before the real agent().
  ioApi = ioApi || io()
  const outPath = ioApi.join(runDir, `verify-result-r${round}.json`)
  // #396: when a build worktree is threaded (the whole-branch final-review gate roots verify in the
  // tree under review), pass verify_gate.py an explicit --cwd instead of letting the courier leaf run
  // in the hosting session's inherited cwd, and enforce the duration ceiling MECHANICALLY: pass
  // --timeout and self-bound the whole command with a perl alarm so the budget never depends on the
  // courier honoring the Bash `timeout` param. The gate --timeout / Bash floor / perl alarm are three
  // strictly-ordered bounds (see VERIFY_TIMEOUT_SECONDS) so verify_gate.py classifies its own
  // TimeoutExpired and writes its result file before any outer bound kills the process. No cwd threaded
  // (the review-code leg roots verify by cd-wrapping the courier PROMPT via showrunner.js
  // withTargetCommandPrompts — a SEPARATE rooting mechanism, kept in sync by hand) → the composed
  // command is byte-identical to before.
  const gateArgs = `--command ${shq(verifyCommand || 'none')}` +
    (cwd ? ` --cwd ${shq(cwd)} --timeout ${VERIFY_TIMEOUT_SECONDS}` : '') +
    ` --out ${shq(outPath)}`
  const bareCommand = `python3 ${libPath('verify_gate.py')} ${gateArgs}`
  const command = cwd
    ? `perl -e 'alarm shift; exec @ARGV' ${VERIFY_ALARM_SECONDS} ${bareCommand}`
    : bareCommand
  const prompt =
    `Run exactly this command with Bash and return ONLY its final stdout JSON, unchanged.\n` +
    `This command can run for several minutes. Invoke Bash with an explicit timeout parameter of 600000 ms ` +
    `(the Bash tool accepts a timeout parameter up to 600000 ms). Do NOT background it. ` +
    `Do NOT answer until the command prints its final JSON. Your structured output fields must be the JSON object's own fields ` +
    `(result/code/tail); do not nest the JSON as a string.\n\n` +
    command
  const runCourier = () => agent(prompt, { label: 'run verify', schema: VERIFY_SCHEMA, courier: true })
  // A THROWN verify courier must be treated EXACTLY like an unusable answer — never collapsed to 'fail'
  // before the file read-back runs. Live (harness-run 26, wf_1ed21465-6f3): the haiku courier ran
  // verify_gate.py correctly (round-stamped file written, result PASS) but never called its
  // StructuredOutput tool (emitted the tag as literal text), so agent() THREW; the call-site catch
  // then collapsed a clean round to 'fail' with the pass evidence sitting on disk. Swallowing the throw
  // to null here keeps the round-stamped file authoritative in BOTH directions: it is still REQUIRED to
  // grant pass (anti-fabrication, unchanged) AND is now consulted before we ever conclude fail. The
  // call-site catch remains only as a last-resort backstop.
  const tryCourier = async () => { try { return await runCourier() } catch (_) { return null } }
  const out = await tryCourier()
  const commandSkipped = !verifyCommand || String(verifyCommand).trim().toLowerCase() === 'none'
  if (commandSkipped) return verifyResultFromPayload(verifyCommand, out, { allowPass: false }) || 'fail'
  const readBack = await ioApi.readJson(outPath, null)
  const fromFile = verifyResultFromPayload(verifyCommand, readBack, { allowPass: true })
  if (fromFile) return fromFile
  const fromDirect = verifyResultFromPayload(verifyCommand, out, { allowPass: false })
  if (fromDirect) return fromDirect
  const retryOut = await tryCourier()
  const retryReadBack = await ioApi.readJson(outPath, null)
  const fromRetryFile = verifyResultFromPayload(verifyCommand, retryReadBack, { allowPass: true })
  if (fromRetryFile) return fromRetryFile
  // Both couriers AND both read-backs yielded nothing usable -> the anti-fabrication fail-closed default.
  return verifyResultFromPayload(verifyCommand, retryOut, { allowPass: false }) || 'fail'
}

function own(obj, key) {
  return !!obj && Object.prototype.hasOwnProperty.call(obj, key)
}

function _integerString(value) {
  const s = String(value).trim()
  return /^-?\d+$/.test(s) ? s : null
}

function verifyResultFromPayload(verifyCommand, payload, opts) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null
  opts = opts || {}
  if (typeof payload.result === 'string') {
    try {
      const nested = JSON.parse(payload.result)
      if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
        return verifyResultFromPayload(verifyCommand, nested, opts)
      }
    } catch (_) { /* fall through to normal result handling */ }
  }
  const command = verifyCommand || (own(payload, 'command') ? payload.command : 'none')
  const commandSkipped = !command || String(command).trim().toLowerCase() === 'none'
  if (payload.result === 'pass') return opts.allowPass ? 'pass' : null
  if (payload.result === 'skipped') return commandSkipped ? 'skipped' : null
  if (payload.result === 'fail' || payload.result === 'timeout') return payload.result
  if (commandSkipped) return 'skipped'
  const timedOut = payload.timedOut === true || String(payload.timedOut).toLowerCase() === 'true'
  if (timedOut) return 'timeout'
  const rc = own(payload, 'returncode') ? payload.returncode : (own(payload, 'code') ? payload.code : undefined)
  const rcStr = _integerString(rc)
  if (!rcStr) return null
  const classified = verifyGateTwin.classify({ command, returncode: rcStr, timedOut: false })
  return classified === 'pass' && !opts.allowPass ? null : classified
}

// The LIVE tally: compute the answer-time facts from the round's own reviewer answers, ride the
// scalars the durable skeleton can't hold DOWN to the tally-round decider (which owns the terminal
// from disk + writes the fix worklist on a continue), and assemble the verdict — this round's
// findings/drops/downgrades for the readout, the decider's decisions for control flow.
async function tallyRound({ runDir, round, roster, maxRounds, roundFindings = {},
                           legKind = {}, synthesized = null, verifyResult = null,
                           fixStatus = 'completed', extras = null, policy = {}, coverageDecisions = [],
                           coverageTarget = null, runId, enterConfirmation = false, docMode = false, ioApi }) {
  const api = ioApi || io()
  const safeExtras = {}
  if (extras && typeof extras === 'object') {
    for (const k of ['fixes', 'deferred', 'parentOrigin']) if (k in extras) safeExtras[k] = extras[k]
  }
  try {
    if (!roster || roster.length === 0) {
      return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
        findings: [], missing: [], drops: [], downgrades: [], terminal: 'cannot-certify', round,
        reason: 'empty reviewer set — nothing to certify' }, safeExtras)
    }
    // answer-time facts from the LIVE reviewer answers (the durable skeleton strips the receipts
    // these need): gate/confidence/missing, present-blocking, and the #212 named uncertified reason.
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: (coverageDecisions || []).map((d) => d.id).filter(Boolean) }
    const gateOut = panelTally.roundGateFromDimensionResults(
      roundFindings, roster, policy.roundKind === 'confirmation', receiptContext)
    const gate = gateOut.gate
    const confidence = gateOut.confidence
    const missing = gateOut.incomplete
    let compiled, drops, downgrades
    if (synthesized && typeof synthesized === 'object') {
      compiled = synthesized.findings || []
      drops = synthesized.drops || []
      // #186: blocking→non-blocking severity downgrades ride alongside drops for the readout's
      // owner-scrutiny section (visibility only; the severity change itself already applied).
      downgrades = synthesized.downgrades || []
    } else {
      compiled = panelTally.compileDimensionResults(roundFindings)
      drops = []
      downgrades = []
    }
    const presentBlocking = panelTally.presentBlockingFromDimensionResults(roundFindings)
    // #212 named reason only matters on a cannot-certify GATE — compute it from the live per-seat
    // results and ride it DOWN (the decider can't recompute it: the skeleton strips the receipts).
    const uncertifiedReason = (gate === 'cannot-certify') ? panelTally.uncertifiedReason(roundFindings, roster) : null

    // the decider owns the terminal (breaker + decideTerminal + #174 economics + certification) from
    // disk; on a continue it writes the fixer worklist to the SAME leaf and rides only its pointer.
    const decided = await tallyRoundDecider({ runDir, round, roster, maxRounds, gate, confidence, missing,
      presentBlocking, uncertifiedReason, fixStatus, verifyResult, enterConfirmation, coverageTarget,
      worklistOutPath: api.join(runDir, `fix-context-r${round}.json`), docMode, ioApi: api })
    // a mangled/unparseable decider answer fails closed — never a silent clean (the #211 adversarial
    // invariant): the shell's _failClosed sentinel halts + flags recordMissing.
    if (!decided || typeof decided.terminal !== 'string') return _failClosed()

    const verdictOut = Object.assign({ schemaVersion: SCHEMA_VERSION, gate, confidence, findings: compiled,
      missing, drops, downgrades, terminal: decided.terminal, reason: decided.reason, round }, safeExtras)
    // #212 uncertified flag (from the decider — set on a cannot-certify gate, even routing to fix).
    if (decided.uncertified) verdictOut.uncertified = true
    // #174 req 4 honest certification summary rides on a certifying terminal (from the decider).
    if (decided.certification) verdictOut.certification = decided.certification
    // #211 fix-context pointer (written by the folded decider on a continue) — never inlined findings.
    if (own(decided, 'worklistPath')) verdictOut.worklistPath = decided.worklistPath
    if (own(decided, 'worklistReason')) verdictOut.worklistReason = decided.worklistReason
    // #381 structured cap-halt discriminator (from the decider) — the whole-branch final-review gate
    // routes on this (round-cap → hand off to review-code; every other halt kind parks), never on prose.
    if (own(decided, 'haltKind')) verdictOut.haltKind = decided.haltKind
    return verdictOut
  } catch (exc) {
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
      findings: [], missing: [], drops: [], downgrades: [], terminal: 'halted', round,
      reason: 'tally failed: ' + (exc && exc.message ? exc.message : exc) }, safeExtras)
  }
}

async function runFixStep(fixStep, fixContext, verdict, runDir) {
  try {
    const fixResult = await fixStep(fixContext, verdict, runDir)
    if (!fixResult) return { ok: false, extras: null, fixResult: null }
    const schedulingExtras = fixSchedulingExtras(fixResult)
    await recordDeferred(fixResult, verdict, runDir)
    const detailExtras = plainExtras(fixResult.extras)
    const extras = Object.assign({}, detailExtras || {}, schedulingExtras || {})
    return { ok: true, extras: Object.keys(extras).length ? extras : null, fixResult }
  } catch (e) {
    try { log(`review-panel: fix step failed, treating as fix failure -> halted: ${e && e.message ? e.message : e}`) } catch (_) {}
    return { ok: false, extras: null, fixResult: null }
  }
}

function plainExtras(value) {
  return (value && typeof value === 'object' && !Array.isArray(value)) ? value : null
}

function fixSchedulingExtras(fixResult) {
  if (!fixResult || typeof fixResult !== 'object' || Array.isArray(fixResult)) return null
  const out = {}
  if (Array.isArray(fixResult.changedSubjects)) {
    out.changedSubjects = fixResult.changedSubjects.filter((s) => POLICY_SUBJECTS.has(s))
    out.needsConfirmation = true
  }
  if (Array.isArray(fixResult.changedSubjectDetails)) out.changedSubjectDetails = fixResult.changedSubjectDetails
  else if (Array.isArray(fixResult.changedSubjects)) out.changedSubjectDetails = fixResult.changedSubjects
  const extras = plainExtras(fixResult.extras)
  if (extras && Object.prototype.hasOwnProperty.call(extras, 'needsConfirmation')) {
    out.needsConfirmation = extras.needsConfirmation
  }
  return Object.keys(out).length ? out : null
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['terminal'],
  properties: {
    schemaVersion: { type: 'number' },
    gate: { enum: ['clean', 'blocking', 'cannot-certify'] },
    confidence: { enum: ['high', 'low'] },
    findings: { type: 'array' },
    drops: { type: 'array' },
    downgrades: { type: 'array' },
    terminal: { enum: ['continue', 'clean', 'clean-with-skips', 'cannot-certify', 'halted'] },
    reason: { type: 'string' },
    recordMissing: { type: 'boolean' },
    uncertified: { type: 'boolean' },
  },
}
const SYNTH_SCHEMA = { type: 'object', required: ['findings', 'drops'],
  properties: { findings: { type: 'array' }, drops: { type: 'array' } } }
const VERIFY_SCHEMA = { type: 'object', required: ['result'],
  properties: { result: {}, code: {}, tail: {}, command: {}, returncode: {}, timedOut: {} } }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// verifyAgent exported for #381: build_phase's whole-branch final review re-runs the verify gate ONCE
// after its one-pass fix batch lands (the fix changed the tree, so the round's pre-fix verify result is
// stale) — reusing this leaf keeps the verify contract (round-stamped file authoritative, anti-
// fabrication fail-closed) single-sourced instead of duplicating it at the call site.
// tallyRoundDecider and planRoundDecider exported for #397 doc-panel smoke tests.
module.exports = { reviewPanel, gatherReviewSetup, verifyAgent, tallyRoundDecider, planRoundDecider, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }
