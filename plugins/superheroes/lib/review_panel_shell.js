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
const roundPolicy = require('./review_round_policy.js')
const reviewMemory = require('./review_memory.js')
const { libPath } = require('./lib_root.js')   // #170: spine code root for lib composes

const SCHEMA_VERSION = 1
const BLOCKING = new Set(['Critical', 'Important'])
const _VERIFY_OK = new Set(['pass', 'skipped'])
const POLICY_SUBJECTS = new Set(['Test', 'Security', 'Code', 'Architecture', 'Failure-Mode'])

function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  return { schemaVersion: SCHEMA_VERSION, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}

function deferredSetPath(runDir) { return `${runDir}/deferred-set.json` }

async function loadDeferredSet(runDir) {
  // Deliberate degrade: a courier prose-flake on a missing/corrupt deferred-set reads as {}.
  // Worst case a deferred finding re-blocks or gets re-reviewed (waste, not corruption) — the
  // tally's skip-set is advisory; record_deferred.py is the authoritative write path.
  const set = await io().readJson(deferredSetPath(runDir), {})
  return (set && typeof set === 'object' && !Array.isArray(set)) ? set : {}
}

function resumeRound(records) {
  let best = 0
  for (const r of records) {
    const n = r && Number(r.round)
    if (Number.isFinite(n) && n > best) best = n
  }
  return best + 1
}

function assembleRounds(records, deferredSet) {
  const skip = new Set(Object.keys(deferredSet || {}))
  const out = []
  for (const rec of records) {
    if (!rec || typeof rec !== 'object') continue
    const findings = (rec.findings || []).filter((f) => !skip.has(circuitBreaker.findingIdentity(f)))
    out.push({
      round: Number(rec.round),
      findings,
      dimensions: rec.dimensions,
      coverageDecisions: rec.coverageDecisions,
    })
  }
  out.sort((a, b) => a.round - b.round)
  return out
}

function _breakerRoundDimensions(roundFindings) {
  const dims = {}
  for (const [name, result] of Object.entries(roundFindings || {})) {
    if (!result || typeof result !== 'object') continue
    dims[name] = { status: result.status || 'run' }
  }
  return dims
}

function buildPreviousDimensionState(records) {
  const previous = {}
  for (const rec of records || []) {
    for (const [name, dim] of Object.entries((rec && rec.dimensions) || {})) previous[name] = dim
  }
  return previous
}

function carryForwardDimension(records, name, sched) {
  for (let i = (records || []).length - 1; i >= 0; i -= 1) {
    const dim = records[i].dimensions && records[i].dimensions[name]
    if (dim) return Object.assign({}, dim, { status: 'skipped', carriedFromRound: sched.carriedFromRound })
  }
  return { status: 'skipped', findings: [], confidence: 'low', carriedFromRound: sched.carriedFromRound }
}

function buildFixContext(records, coverageDecisions) {
  const priorFindings = []
  const changedSubjects = []
  for (const rec of records || []) {
    priorFindings.push(...((rec && rec.findings) || []))
    if (Array.isArray(rec && rec.changedSubjects)) changedSubjects.push(...rec.changedSubjects)
  }
  return {
    priorFindings,
    classKeys: priorFindings.map((f) => f.classKey || reviewMemory.classKey(f)),
    generalizeRequired: reviewMemory.recurrentClasses(records, coverageDecisions),
    changedSubjects: Array.from(new Set(changedSubjects)),
    coverageDecisions: coverageDecisions || [],
  }
}

function reviewerContext(context, coverageDecisions, receiptContext) {
  return Object.assign({}, context || {}, { coverageDecisions: coverageDecisions || [], receiptContext })
}

function wouldOtherwiseCertify(roundFindings, reviewerSet) {
  for (const name of reviewerSet || []) {
    const result = roundFindings[name]
    if (!result || result.confidence !== 'high' || (result.findings || []).length > 0) return false
  }
  return true
}

function annotateChallengedCoverage(coverageDecisions, roundFindings, reviewerSet) {
  const known = new Set((coverageDecisions || []).map((d) => d && d.classKey).filter(Boolean))
  const out = (coverageDecisions || []).map((d) => Object.assign({}, d))
  const byClass = Object.fromEntries(out.filter((d) => d.classKey).map((d) => [d.classKey, d]))
  for (const name of reviewerSet || []) {
    const result = roundFindings[name]
    if (!result || result.status !== 'run') continue
    for (const f of result.findings || []) {
      if (!BLOCKING.has(f.severity)) continue
      const key = f.classKey || reviewMemory.classKey(f)
      if (!known.has(key)) continue
      const decision = byClass[key]
      if (decision) decision.challengedBy = name
    }
  }
  return out
}

// #174 confirmation-bar economics helpers.
// The NEW (non-carried) blocking severities a round surfaced.
function surfacedBlockingSeverities(record) {
  const findings = (record && Array.isArray(record.findings)) ? record.findings : []
  return findings.filter((f) => f && BLOCKING.has(f.severity)).map((f) => f.severity)
}
// A confirmation counts as a qualifying FULL panel only when every dimension ran FRESH at
// reviewer-deep with high confidence (the #167 invariant #174 preserves). A degraded attempt
// (low-confidence / carried / non-deep dim — possible on a resumed prior-run record) neither
// satisfies the panel obligation nor consumes the hard cap.
function confirmationQualifies(record) {
  const dims = (record && record.dimensions && typeof record.dimensions === 'object' && !Array.isArray(record.dimensions))
    ? record.dimensions : null
  if (!dims) return false
  const names = Object.keys(dims)
  if (!names.length) return false
  return names.every((n) => {
    const d = dims[n] || {}
    return d.status === 'run' && d.confidence === 'high' && d.tier === 'reviewer-deep'
  })
}
// Union of rework (changedSubjects) across a set of records. Any missing/non-array changed surface
// is unknown → null → treated as cross-cutting by the twin (fail toward one more panel).
function reworkAcross(records) {
  const out = []
  for (const r of records) {
    const cs = r && r.changedSubjects
    if (!Array.isArray(cs)) return null
    out.push(...cs)
  }
  return out
}
// Is a FURTHER full confirmation panel still owed? The follow-up decision is computed over
// EVERYTHING SINCE THE LAST QUALIFYING PANEL — the panel itself plus every later round — because
// findings surfaced and rework applied by post-confirmation scoped rounds land on THOSE rounds'
// records, not the panel's. Before any qualifying panel has run, the mandatory first panel is
// owed. A Critical still owed at the cap → park (certification withheld).
function panelWindow(records) {
  const all = records || []
  const qualifying = all.filter((r) => r && r.kind === 'confirmation' && confirmationQualifies(r))
  if (!qualifying.length) return { qualifying, since: [] }
  const lastRound = Number(qualifying[qualifying.length - 1].round) || 0
  const since = all.filter((r) => r && (Number(r.round) || 0) >= lastRound)
  return { qualifying, since }
}
function furtherConfirmationOwed(records) {
  const { qualifying, since } = panelWindow(records)
  if (!qualifying.length) return { owed: true, park: false, panels: 0 }
  const surfaced = since.flatMap(surfacedBlockingSeverities)
  const followup = roundPolicy.confirmationFollowup(
    surfaced, qualifying.length, roundPolicy.isCrossCutting(reworkAcross(since)))
  return { owed: followup.rearm, park: followup.park, panels: qualifying.length, reason: followup.reason }
}
// The honest certification summary (#174 req 4): how many QUALIFYING full panels ran and whether
// any blocking finding surfaced since the last one (resolved by scoped verify — not a pristine pass).
function certificationSummary(records) {
  const { qualifying, since } = panelWindow(records)
  return { fullPanels: qualifying.length,
    lastPanelSurfacedResolved: since.some((r) => surfacedBlockingSeverities(r).length > 0) }
}

function confirmationReady(records, round, justMarked) {
  if (justMarked) return false
  const marked = (records || []).filter((r) => r && r.confirmationPending)
  if (!marked.length) return false
  // #174: once a full confirmation has run, only RE-ENTER another when the economics demand it
  // (a Critical surfaced, or cross-cutting rework, under the cap). Otherwise the confirmation
  // obligation is satisfied and no further full panel runs — the terminal guard certifies.
  if (!furtherConfirmationOwed(records).owed) return false
  const markedRound = Math.max(...marked.map((r) => Number(r.round) || 0))
  const hasIntermediateAfterMarker = (records || []).some((r) => Number(r.round) > markedRound)
  if (!hasIntermediateAfterMarker) return true
  return round > markedRound + 1
}

// entry-bootstrap (#193) is the read seam for a resume: it ships DECISIONS + the bounded minimum,
// not record content. Each prior-run round comes back as a STUB — the policy/confirmation/
// certification scalars plus BLOCKING-finding skeletons only (the breaker, recurrence, round policy,
// and fix-context generalizeRequired never read non-blocking prior-round findings), so a two-round
// resume is one direct payload-tier answer instead of a receipt + N ~34k-token chunk leaves (the
// #118 courier-collapse bar). In-memory `records` are therefore a documented HYBRID: prior-run rounds
// are stubs, this-run rounds stay full (mergeRoundRecords keeps the richer live record). Once the
// bootstrap is big enough to be courier-fragile (pathological history), the helper writes it
// Python-side and returns only a receipt; the shell reads base64 chunks and verifies each chunk plus
// the reconstructed content hash before parsing (the #191 fallback transport).
const _SUMMARY_RECEIPT_BOUND = 4000
const _READ_CHUNK_CHARS = 4000

function _b64Bytes(b64) {
  const clean = String(b64 || '').replace(/[\r\n\t ]/g, '')
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  const out = []
  for (let i = 0; i < clean.length; i += 4) {
    const c0 = A.indexOf(clean[i]); const c1 = A.indexOf(clean[i + 1])
    const c2 = clean[i + 2] === '=' ? -1 : A.indexOf(clean[i + 2])
    const c3 = clean[i + 3] === '=' ? -1 : A.indexOf(clean[i + 3])
    if (c0 < 0 || c1 < 0 || (c2 < 0 && clean[i + 2] !== '=') || (c3 < 0 && clean[i + 3] !== '=')) throw new Error('bad base64')
    out.push((c0 << 2) | (c1 >> 4))
    if (c2 >= 0) out.push(((c1 & 15) << 4) | (c2 >> 2))
    if (c3 >= 0) out.push(((c2 & 3) << 6) | c3)
  }
  return out
}

function _utf8FromBytes(bytes) {
  let out = ''
  for (let i = 0; i < bytes.length;) {
    const b0 = bytes[i++]
    if (b0 < 0x80) { out += String.fromCharCode(b0); continue }
    if ((b0 & 0xe0) === 0xc0) {
      const b1 = bytes[i++] || 0
      out += String.fromCharCode(((b0 & 31) << 6) | (b1 & 63))
      continue
    }
    if ((b0 & 0xf0) === 0xe0) {
      const b1 = bytes[i++] || 0; const b2 = bytes[i++] || 0
      out += String.fromCharCode(((b0 & 15) << 12) | ((b1 & 63) << 6) | (b2 & 63))
      continue
    }
    const b1 = bytes[i++] || 0; const b2 = bytes[i++] || 0; const b3 = bytes[i++] || 0
    let cp = ((b0 & 7) << 18) | ((b1 & 63) << 12) | ((b2 & 63) << 6) | (b3 & 63)
    cp -= 0x10000
    out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 1023))
  }
  return out
}

function _decodeBase64Utf8(b64) {
  if (typeof Buffer !== 'undefined') return Buffer.from(String(b64 || ''), 'base64').toString('utf8')
  return _utf8FromBytes(_b64Bytes(b64))
}

function _jsonFromStdout(out) {
  try { return JSON.parse((out && out.stdout) || '') } catch (_) { return null }
}

// The chunk payload rides REVERSED (`rb64`, #191): plain base64-of-JSON is decode-bait — a
// live courier model recognizes it and answers with the DECODED content instead of the raw
// stdout, failing every hash check (run wf_fd9b5edc-e80: all chunk attempts transformed this
// way). Reversing makes the payload semantically opaque; reverse back before decoding.
// b64 is ASCII, so a naive character reverse is byte-safe.
function _unreverse(rb64) {
  return String(rb64 || '').split('').reverse().join('')
}

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
      if (parsed.chunkHash !== ioApi.contentHash(parsed.rb64 || '')) { parsed = null; continue }
      break
    }
    if (!parsed) return { ok: false, reason: corruptReason }
    try { text += _decodeBase64Utf8(_unreverse(parsed.rb64)) } catch (_) { return { ok: false, reason: corruptReason } }
    if (parsed.eof) break
    index = Number(parsed.nextIndex)
    if (!Number.isFinite(index)) return { ok: false, reason: corruptReason }
  }
  if (ioApi.contentHash(text) !== receipt.contentHash) return { ok: false, reason: corruptReason }
  return { ok: true, text }
}

async function _loadRoundRecordsOnce(runDir, reviewerSet, ioApi) {
  const out = await ioApi.runHelper('python3', [libPath('review_memory.py'), 'entry-bootstrap', '--path', ioApi.join(runDir, 'round-records.json'), '--dimensions', JSON.stringify(reviewerSet), '--extras-path', ioApi.join(runDir, 'last-extras.json'), '--sweep-stale-staging', '--out-path', ioApi.join(runDir, 'round-summary.json'), '--receipt-threshold', String(_SUMMARY_RECEIPT_BOUND)], { payload: true })
  let parsed = _jsonFromStdout(out)
  if (parsed && parsed.receipt === 'entry-bootstrap') {
    const read = await _readReceiptText(ioApi, parsed, 'entry-bootstrap', 'round-memory-helper-failed')
    if (!read.ok) return read
    try { parsed = JSON.parse(read.text) } catch (_) { parsed = null }
  }
  if (parsed && typeof parsed === 'object') return parsed.ok ? parsed : Object.assign({ ok: false }, parsed)
  return { ok: false, reason: 'round-memory-helper-failed' }
}

async function probeRoundRecords(runDir, ioApi) {
  const out = await ioApi.runHelper('python3', [libPath('review_memory.py'), 'probe', '--path', ioApi.join(runDir, 'round-records.json')])
  try {
    const parsed = JSON.parse((out && out.stdout) || '')
    if (parsed && typeof parsed === 'object') return parsed
  } catch (_) { /* fall through */ }
  return { ok: false, exists: true, state: 'unreadable', reason: 'round-memory-probe-failed' }
}

async function loadRoundRecords(runDir, reviewerSet, ioApi) {
  const first = await _loadRoundRecordsOnce(runDir, reviewerSet, ioApi)
  if (first.ok) return first
  const second = await _loadRoundRecordsOnce(runDir, reviewerSet, ioApi)
  if (second.ok) return second
  const probed = await probeRoundRecords(runDir, ioApi)
  if (probed && probed.ok && probed.exists === false) {
    return { ok: true, state: 'missing', records: [], contentHash: ioApi.contentHash(''), extras: null }
  }
  return {
    ok: false,
    state: 'unreadable',
    reason: 'round-memory-unreadable',
    records: [],
    contentHash: (probed && probed.contentHash) || first.contentHash || second.contentHash,
  }
}

// D3: the DURABLE round record is the bounded SKELETON (review_memory.skeletonRecord — a superset of
// the entry-bootstrap stub that seeds a resume: the durable form keeps non-blocking findings, the
// resume seed drops them), persisted in ONE verified CAS leaf for the typical
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

// mergeRoundRecords: the in-memory twin of persist_record's merge (dedupe the round, sort) —
// persist-skeleton never echoes the merged records back through the pipe, and the in-memory
// copy keeps the CURRENT session's full-bodied record (richer fix context than the durable
// skeleton; a resume gets the skeletons, same as before D3).
function mergeRoundRecords(records, record) {
  const merged = (records || []).filter((r) => r && r.round !== record.round)
  merged.push(record)
  merged.sort((a, b) => (Number(a.round) || 0) - (Number(b.round) || 0))
  return merged
}

// The post-fix update ships only the SMALL delta (confirmation marker, changed subjects,
// coverage decisions, fix summary) — never the round body — via review_memory.py update-round,
// self-verified in transport like persist-skeleton (--updates-hash; staged-file fallback past
// the safe inline size — the delta is usually small but coverageDecisions/fixes are unbounded).
// Deferred entries ride slimmed (identity/severity/reason + skeleton finding): their full
// bodies go to the round-bodies dump, not through this pipe or into round-records.json.
async function persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult, recordedCoverageDecisions, expectedHash, runId, lease, ioApi, legKind) {
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
  const records = (recordsForFix || []).map((r) => (r && r.round === round) ? Object.assign({}, r, updates) : r)
  return { ok: true, contentHash: parsed.contentHash, records }
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
  const out = await api.runHelper('python3', args, { payload: true })
  let parsed = _jsonFromStdout(out)
  if (parsed && parsed.receipt === 'review-setup-gather') {
    const read = await _readReceiptText(api, parsed, 'review-setup-gather', 'review-setup-gather-unreadable')
    if (!read.ok) return null
    try { parsed = JSON.parse(read.text) } catch (_) { parsed = null }
  }
  if (parsed && parsed.ok && parsed.memory && parsed.coverage) {
    if (!parsed.deferredSet || typeof parsed.deferredSet !== 'object') parsed.deferredSet = {}
    return parsed
  }
  return null
}

async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none',
                            forceCoverageDecisionExpectedHash, preloaded }) {
  runDir = runDir || runKey
  const runId = runKey || runDir
  const lease = legKind && legKind.lease
  const ioApi = io()
  // fold 2 (#141): the doc/code leg may hand us a PRELOADED setup gather — the run-dir mkdir,
  // entry-bootstrap (+extras), deferred-set seed, and entry coverage read folded into ONE upstream
  // leaf (gatherReviewSetup). When present we skip our own entry reads; when absent (the standalone
  // shell + its smokes) we fall back to reading each ourselves, unchanged. The coverage + deferred
  // set are consumed on the FIRST round only — later rounds re-read (both change after a fix).
  let memoryState = (preloaded && preloaded.memory) ? preloaded.memory
    : await loadRoundRecords(runDir, reviewerSet || [], ioApi)
  let entryCoverage = (preloaded && preloaded.coverage) ? preloaded.coverage : null
  let entryDeferredSet = preloaded ? preloaded.deferredSet : undefined
  let records = memoryState.ok ? memoryState.records : []
  let round = resumeRound(records)
  let lastExtras = memoryState.extras !== undefined ? memoryState.extras : null
  let justMarkedForConfirmation = false
  let fixRanThisRun = false
  const allUsage = {}

  if (!memoryState.ok) {
    return await finalizeVerdict(
      { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-unreadable', round },
      records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
  }

  if (!reviewerSet || reviewerSet.length === 0) {
    const v = await tallyRound({ runDir, round, roster: reviewerSet || [], maxRounds,
                                   roundFindings: {}, records, legKind, verifyResult: null,
                                   policy: { roundKind: 'baseline' }, coverageDecisions: [],
                                   runId, extras: lastExtras })
    return _usable(v) ? await finalizeVerdict(v, records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi) : _failClosed()
  }

  while (true) {
    const recoveringCorruptMemory = !memoryState.ok
    records = memoryState.ok ? memoryState.records : []
    const enterConfirmation = !recoveringCorruptMemory && confirmationReady(records, round, justMarkedForConfirmation)
    justMarkedForConfirmation = false

    const coverageTarget = await coverageDecisionTarget(runDir, context, legKind, ioApi)
    // fold 2 (#141): consume the gathered entry coverage on the first round; every later round
    // re-reads (a fix can record new coverage decisions mid-loop — lines below already re-read).
    let coverageState
    if (entryCoverage) { coverageState = entryCoverage; entryCoverage = null }
    else coverageState = await loadCoverageDecisions(coverageTarget, ioApi)
    if (!coverageState.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decisions-' + (coverageState.state || coverageState.reason || 'unreadable'), round },
        records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    const coverageDecisions = coverageState.decisions
    let coverageContentHash = coverageState.contentHash

    if (enterConfirmation && records.length) {
      const latest = records[records.length - 1]
      const ids = ((latest && latest.coverageDecisions) || []).map((d) => d.id).filter(Boolean)
      const visible = new Set(coverageDecisions.map((d) => d.id))
      if (ids.some((id) => !visible.has(id))) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decision-marker-missing', round },
          records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
    }

    const policy = roundPolicy.planRound({
      round,
      dimensions: reviewerSet,
      changedSubjects: recoveringCorruptMemory ? null : (lastExtras && lastExtras.changedSubjects),
      previous: buildPreviousDimensionState(records),
      confirmation: enterConfirmation,
    })
    const scheduled = policy.dimensions || {}
    const roundFindings = {}
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: coverageDecisions.map((d) => d.id).filter(Boolean) }
    await parallel(reviewerSet
      .filter((r) => (scheduled[r] || {}).action !== 'skip')
      .map((r) => () => dispatchReviewer(r, reviewerContext(context, coverageDecisions, receiptContext), rubric, runDir, round, roundFindings, Object.assign({}, scheduled[r], { roundKind: policy.roundKind, coverageDecisions, receiptContext, receiptArtifact: receiptContext.artifact }))))
    for (const [name, sched] of Object.entries(scheduled)) {
      if (sched.action === 'skip') roundFindings[name] = carryForwardDimension(records, name, sched)
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
      try { verifyResult = await verifyAgent(verifyCommand, runDir, round, ioApi) }
      catch (e) { verifyResult = 'fail' }
    }

    const tokenUsage = collectRoundUsage(roundFindings, round, synthesized)
    Object.assign(allUsage, tokenUsage)

    const roundCoverageDecisions = annotateChallengedCoverage(coverageDecisions, roundFindings, reviewerSet)
    const record = reviewMemory.recordFromDimensionResults(round, policy.roundKind, roundFindings, lastExtras && lastExtras.changedSubjects, roundCoverageDecisions, tokenUsage, enterConfirmation && policy.roundKind === 'confirmation')
    const persisted = await persistRoundRecord(runDir, reviewerSet, record, memoryState.contentHash, runId, lease, ioApi)
    if (!persisted.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    const recordsForFix = Array.isArray(persisted.records) ? persisted.records : mergeRoundRecords(records, record)
    records = recordsForFix
    memoryState = { ok: true, records: recordsForFix, contentHash: persisted.contentHash }

    if (recoveringCorruptMemory && wouldOtherwiseCertify(roundFindings, reviewerSet)) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-corrupt-recovery', round },
        records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }

    // fold 2 (#141): the round-1 tally reuses the gathered deferred-set (no fix has run between the
    // entry gather and this tally, so it is byte-identical to a fresh disk read). It is consumed
    // once — every later round re-reads (a fix may defer findings in between).
    const verdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
      roundFindings, records, legKind, synthesized, verifyResult, policy, coverageDecisions: roundCoverageDecisions,
      runId, extras: lastExtras, enterConfirmation, preloadedDeferredSet: entryDeferredSet })
    entryDeferredSet = undefined
    if (!_usable(verdict)) return _failClosed()

    if (verdict.terminal !== 'continue') {
      return await finalizeVerdict(verdict, records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }

    if (verdict.reason === 'awaiting final confirmation round') {
      round += 1
      continue
    }

    fixRanThisRun = true
    const fixContext = buildFixContext(recordsForFix, coverageDecisions)
    const fixResult = await runFixStep(fixStep, fixContext, verdict, runDir)
    if (!fixResult.ok) {
      const failVerdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
        roundFindings, records, legKind, synthesized, verifyResult, policy, coverageDecisions,
        runId, extras: fixResult.extras || lastExtras, fixStatus: 'failed', enterConfirmation })
      return await finalizeVerdict(
        _usable(failVerdict) ? failVerdict : _failClosed(),
        records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
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
          records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      const reloaded = await loadCoverageDecisions(target, ioApi)
      if (!reloaded.ok) {
        return await finalizeVerdict(
          { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'coverage-decisions-' + (reloaded.state || 'unreadable'), round },
          records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
      }
      recordedCoverageDecisions = reloaded.decisions
      expectedCovHash = reloaded.contentHash
      coverageContentHash = reloaded.contentHash
    }

    // body dump BEFORE the post-fix persist: both must happen, the dump is best-effort
    // anyway, and this ordering shrinks the crash window in which the audit bodies are
    // lost while the delta survives (or vice versa) at zero protocol cost.
    await dumpRoundBodiesBestEffort(runDir, round, verdict, fixResult.fixResult || {}, ioApi)
    const postFix = await persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult.fixResult || {}, recordedCoverageDecisions, persisted.contentHash, runId, lease, ioApi, legKind)
    if (!postFix.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    records = postFix.records || recordsForFix
    memoryState = { ok: true, records, contentHash: postFix.contentHash }
    justMarkedForConfirmation = true
    try { await ioApi.writeFile(`${runDir}/last-extras.json`, JSON.stringify(lastExtras)) } catch (_) {}
    round += 1
  }
}

async function finalizeVerdict(verdict, records, reviewerSet, round, legKind, fixRan, allUsage, runDir, runId, lease, ioApi) {
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
    const deepOpts = Object.assign({}, baseOpts, { tier: 'reviewer-deep', escalatedFrom: 'reviewer' })
    out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, deepOpts), deepOpts)
    if (_retryableReviewerIssue(out)) {
      out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, deepOpts, { retryFrom: 'reviewer-deep' })), deepOpts)
    }
  } else if (baseOpts.tier === 'reviewer-deep' && _retryableReviewerIssue(out)) {
    out = _shapeReviewerResult(await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, baseOpts, { tier: 'reviewer-deep', retryFrom: 'reviewer-deep' })), baseOpts)
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
          findings.push(finding)
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

async function verifyAgent(verifyCommand, runDir, round, ioApi) {
  // dumb pipe (run verify_gate.py, echo its JSON): courier:true so the bundle preamble pins it to
  // the cheapest model unconditionally (#118 — an unmarked label like 'run verify' inherits the
  // session model). The preamble strips the marker before the real agent().
  ioApi = ioApi || io()
  const outPath = ioApi.join(runDir, `verify-result-r${round}.json`)
  const command = `python3 ${libPath('verify_gate.py')} --command ${shq(verifyCommand || 'none')} --out ${shq(outPath)}`
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

async function tallyRound({ runDir, round, roster, maxRounds, roundFindings = {}, records = [],
                           legKind = {}, synthesized = null, verifyResult = null,
                           fixStatus = 'completed', extras = null, policy = {}, coverageDecisions = [],
                           runId, enterConfirmation = false, preloadedDeferredSet = undefined }) {
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
    // fold 2 (#141): the round-1 tally reuses the gathered deferred-set; every later round reads it
    // fresh (a fix may have deferred findings since the gather).
    const deferredSet = (preloadedDeferredSet && typeof preloadedDeferredSet === 'object')
      ? preloadedDeferredSet : await loadDeferredSet(runDir)
    const presentBlocking = panelTally.presentBlockingFromDimensionResults(roundFindings)
    const pdef = panelTally.presentDeferred(compiled, deferredSet)
    const skip = new Set(Object.keys(deferredSet))
    const prior = assembleRounds(records, deferredSet).filter((r) => r.round !== round)
    const priorRecords = (records || []).filter((r) => r && Number(r.round) !== round)
    const thisRound = {
      round,
      findings: compiled.filter((f) => !skip.has(circuitBreaker.findingIdentity(f))),
      dimensions: _breakerRoundDimensions(roundFindings),
      coverageDecisions: coverageDecisions || [],
      generalizeRequired: reviewMemory.recurrentClasses(priorRecords, coverageDecisions || []),
    }
    const brk = circuitBreaker.checkCircuitBreaker(prior.concat([thisRound]), maxRounds)
    const breakerHalt = !!brk.halt
    let { terminal, reason } = panelTally.decideTerminal(
      gate, presentBlocking, pdef, fixStatus, round, maxRounds, breakerHalt)
    if (terminal === 'halted' && breakerHalt && brk.detail) reason = brk.detail
    if ((terminal === 'clean' || terminal === 'clean-with-skips') &&
        verifyResult !== null && !_VERIFY_OK.has(verifyResult)) {
      terminal = 'halted'
      reason = verifyResult === 'timeout'
        ? 'verify command timed out — cannot certify clean'
        : 'verify command failed — cannot certify clean'
    }
    if (terminal === 'cannot-certify' && missing.length) {
      reason = 'coverage incomplete — missing review angle(s): ' + missing.join(', ')
    }
    const markedPending = (records || []).some((r) => r && r.confirmationPending)
    if ((terminal === 'clean' || terminal === 'clean-with-skips') && markedPending && !enterConfirmation) {
      // #174: a clean intermediate that owes a confirmation either forces one more full panel
      // (owed), parks when a Critical is still owed at the cap (park), or — when the confirmation
      // obligation is satisfied — certifies as-is (the ran confirmation + scoped verify suffice).
      const owe = furtherConfirmationOwed(records)
      if (owe.park) {
        terminal = 'halted'
        reason = owe.reason || 'Critical surfaced at the confirmation-panel cap — certification withheld'
      } else if (owe.owed) {
        terminal = 'continue'
        reason = 'awaiting final confirmation round'
      }
    }
    if ((terminal === 'clean' || terminal === 'clean-with-skips') && policy.roundKind === 'confirmation') {
      // confirmation round succeeded — clear marker on persisted record handled next round
    }
    const verdictOut = Object.assign({ schemaVersion: SCHEMA_VERSION, gate, confidence, findings: compiled,
      missing, drops, downgrades, terminal, reason, round }, safeExtras)
    // #174 requirement 4 (honest readout): on a certifying terminal, state exactly what was
    // established — how many QUALIFYING full panels ran and whether findings surfaced since the last
    // one were resolved by scoped verify (never implying a pristine fresh pass occurred).
    if (terminal === 'clean' || terminal === 'clean-with-skips') {
      verdictOut.certification = certificationSummary(records)
    }
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
  },
}
const SYNTH_SCHEMA = { type: 'object', required: ['findings', 'drops'],
  properties: { findings: { type: 'array' }, drops: { type: 'array' } } }
const VERIFY_SCHEMA = { type: 'object', required: ['result'],
  properties: { result: {}, code: {}, tail: {}, command: {}, returncode: {}, timedOut: {} } }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

module.exports = { reviewPanel, gatherReviewSetup, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }
