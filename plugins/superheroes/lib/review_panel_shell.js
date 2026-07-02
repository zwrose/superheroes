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

const SCHEMA_VERSION = 1
const BLOCKING = new Set(['Critical', 'Important'])
const _VERIFY_OK = new Set(['pass', 'skipped'])

function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  return { schemaVersion: SCHEMA_VERSION, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}

function deferredSetPath(runDir) { return `${runDir}/deferred-set.json` }

async function loadDeferredSet(runDir) {
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
    out.push({ round: Number(rec.round), findings })
  }
  out.sort((a, b) => a.round - b.round)
  return out
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

function confirmationReady(records, round, justMarked) {
  if (justMarked) return false
  const marked = (records || []).filter((r) => r && r.confirmationPending)
  if (!marked.length) return false
  const markedRound = Math.max(...marked.map((r) => Number(r.round) || 0))
  const hasIntermediateAfterMarker = (records || []).some((r) => Number(r.round) > markedRound)
  if (!hasIntermediateAfterMarker) return true
  return round > markedRound + 1
}

// load-summary is the read twin of persist-skeleton: the resume seed comes back as BOUNDED
// per-round summaries (finding skeletons + per-dimension status — everything the breaker,
// recurrence, policy, and fix-context need in memory), never full findings bodies —
// echoing a multi-round evidence-laden file through the courier stdout is the same
// mega-payload defect as the write side (live 2026-07-02), in reverse. --extras-path folds
// the loop's second entry read (last-extras.json) into the same leaf; it comes back as
// `extras` (null when missing/corrupt — the old readJson-default parity).
async function loadRoundRecords(runDir, reviewerSet, ioApi) {
  const out = await ioApi.runHelper('python3', ['plugins/superheroes/lib/review_memory.py', 'load-summary', '--path', ioApi.join(runDir, 'round-records.json'), '--dimensions', JSON.stringify(reviewerSet), '--extras-path', ioApi.join(runDir, 'last-extras.json')])
  try {
    const parsed = JSON.parse(out.stdout || '{}')
    return parsed.ok ? parsed : Object.assign({ ok: false }, parsed)
  } catch (_) {
    return { ok: false, reason: 'round-memory-helper-failed' }
  }
}

// D3: the DURABLE round record is the bounded SKELETON (review_memory.skeletonRecord — exactly
// what load-summary seeds a resume with), persisted in ONE verified CAS leaf for the typical
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
async function persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi) {
  const recordJson = JSON.stringify(reviewMemory.skeletonRecord(record))
  const inline = recordJson.length <= _INLINE_RECORD_BOUND
  const stagedPath = ioApi.join(runDir, `round-skeleton-r${record.round}.json`)
  const args = ['plugins/superheroes/lib/review_memory.py', 'persist-skeleton',
    '--path', ioApi.join(runDir, 'round-records.json')]
  args.push(...(inline ? ['--record-json', recordJson] : ['--record-path', stagedPath]))
  args.push('--record-hash', ioApi.contentHash(recordJson),
    '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId)
  if (lease) args.push('--lease', lease)
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (!inline) {
      try { await ioApi.writeFile(stagedPath, recordJson) } catch (_) { continue }
    }
    const out = await ioApi.runHelper('python3', args)
    let parsed = null
    try { parsed = JSON.parse((out && out.stdout) || '') } catch (_) { parsed = null }
    if (parsed && parsed.ok) return parsed
    // a real refusal (stale/unreadable) is final; only a transport-corrupt record (or an
    // unparseable answer) earns the one retry.
    if (parsed && parsed.reason && parsed.reason !== 'record-corrupt') return { ok: false, reason: parsed.reason }
  }
  return { ok: false, reason: 'helper-failed' }
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
// coverage decisions, fix summary) — never the round body — via review_memory.py update-round.
// Deferred entries ride slimmed (identity/severity/reason + skeleton finding): their full
// bodies go to the round-bodies dump, not through this pipe or into round-records.json.
async function persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult, recordedCoverageDecisions, expectedHash, runId, lease, ioApi, legKind) {
  const updates = {
    changedSubjects: fixResult.changedSubjects || [],
    coverageDecisions: recordedCoverageDecisions || [],
    fix: { fixes: fixResult.fixes || fixResult.fixed || [], deferred: reviewMemory.skeletonDeferred(fixResult.deferred || []) },
  }
  if (legKind && legKind.panel) updates.confirmationPending = true
  const args = ['plugins/superheroes/lib/review_memory.py', 'update-round',
    '--path', ioApi.join(runDir, 'round-records.json'), '--round', String(round),
    '--updates-json', JSON.stringify(updates),
    '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  let parsed = null
  try { parsed = out.ok ? JSON.parse(out.stdout) : null } catch (_) { parsed = null }
  if (!parsed || !parsed.ok) return { ok: false, reason: (parsed && parsed.reason) || 'helper-failed' }
  const records = (recordsForFix || []).map((r) => (r && r.round === round) ? Object.assign({}, r, updates) : r)
  return { ok: true, contentHash: parsed.contentHash, records }
}

async function coverageDecisionTarget(runDir, context, legKind, ioApi) {
  if (context && context.docPath) return { mode: 'doc', path: context.docPath }
  const path = (context && context.coverageDecisionPath) || (legKind && legKind.coverageDecisionPath) || ioApi.join(runDir, 'review-coverage-decisions.json')
  return { mode: 'code', path }
}

function parseDocCoverageDecisions(text) {
  const out = []
  const lines = String(text || '').split(/\n/)
  let inSection = false
  for (const line of lines) {
    if (/^##\s+/.test(line)) inSection = line.trim() === '## Review coverage decisions'
    if (!inSection) continue
    const jsonMatch = line.match(/review-coverage-decision-json:(\{.*\})`?$/)
    if (jsonMatch) {
      try { out.push(JSON.parse(jsonMatch[1])); continue } catch (_) {}
    }
    const m = line.match(/^- \*\*([^*]+)\*\* .*class `([^`]+)`\): (.*)$/)
    if (m) out.push({ id: m[1], classKey: m[2], text: m[3] })
  }
  return out
}

async function loadCoverageDecisions(target, ioApi) {
  const path = target.path
  let text = ''
  try { text = await ioApi.readText(path) } catch (err) {
    if (err && err.code === 'ENOENT') return { ok: true, decisions: [], contentHash: ioApi.contentHash('') }
    return { ok: false, state: 'unreadable', reason: err && err.message }
  }
  if (target.mode === 'doc') return { ok: true, decisions: parseDocCoverageDecisions(text), contentHash: ioApi.contentHash(text) }
  try {
    const decisions = JSON.parse(text || '[]')
    if (!Array.isArray(decisions)) return { ok: false, state: 'corrupt' }
    return { ok: true, decisions, contentHash: ioApi.contentHash(text) }
  } catch (_) {
    return { ok: false, state: 'corrupt' }
  }
}

function collectRoundUsage(roundFindings, round, synthesized) {
  const usage = {}
  for (const [name, result] of Object.entries(roundFindings || {})) {
    if (result && result.usage) usage[`${name}:r${round}`] = result.usage
  }
  if (synthesized && synthesized.usage) usage[`synthesis:r${round}`] = synthesized.usage
  return usage
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
  const args = ['plugins/superheroes/lib/review_telemetry.py', 'write-from-records',
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
  const args = ['plugins/superheroes/lib/coverage_decisions.py', cmd, '--path', targetPath, '--decision-json', JSON.stringify(decision), '--expected-hash', expectedHash, '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'coverage-decision-write-failed' }
  } catch (_) {
    return { ok: false, reason: 'coverage-decision-write-failed' }
  }
}

async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none',
                            forceCoverageDecisionExpectedHash }) {
  runDir = runDir || runKey
  const runId = runKey || runDir
  const lease = legKind && legKind.lease
  const ioApi = io()
  let memoryState = await loadRoundRecords(runDir, reviewerSet || [], ioApi)
  let records = memoryState.ok ? memoryState.records : []
  let round = resumeRound(records)
  let lastExtras = memoryState.extras !== undefined ? memoryState.extras : null
  let justMarkedForConfirmation = false
  let fixRanThisRun = false
  const allUsage = {}

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
    const coverageState = await loadCoverageDecisions(coverageTarget, ioApi)
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
    }

    let verifyResult = null
    if (legKind.code) {
      try { verifyResult = await verifyAgent(verifyCommand, runDir, round) }
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

    const verdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
      roundFindings, records, legKind, synthesized, verifyResult, policy, coverageDecisions: roundCoverageDecisions,
      runId, extras: lastExtras, enterConfirmation })
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

    const postFix = await persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult.fixResult || {}, recordedCoverageDecisions, persisted.contentHash, runId, lease, ioApi, legKind)
    if (!postFix.ok) {
      return await finalizeVerdict(
        { schemaVersion: SCHEMA_VERSION, terminal: 'cannot-certify', reason: 'round-memory-write-failed', round },
        records, reviewerSet, round, legKind, fixRanThisRun, allUsage, runDir, runId, lease, ioApi)
    }
    records = postFix.records || recordsForFix
    memoryState = { ok: true, records, contentHash: postFix.contentHash }
    await dumpRoundBodiesBestEffort(runDir, round, verdict, fixResult.fixResult || {}, ioApi)
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

async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings, opts) {
  const baseOpts = opts || {}
  let out = await reviewerAgent(reviewer, context, rubric, runDir, round, baseOpts)
  if (Array.isArray(out)) {
    const conf = (baseOpts.tier === 'reviewer' && out.length > 0) ? 'low' : 'high'
    out = { findings: out, confidence: conf, legacyArray: true }
  }
  let escalated = false
  if (baseOpts.tier === 'reviewer' && (!_validReviewerResult(out) || out.confidence !== 'high')) {
    escalated = true
    out = await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, baseOpts, { tier: 'reviewer-deep', escalatedFrom: 'reviewer' }))
    if (Array.isArray(out)) out = { findings: out, confidence: 'high', legacyArray: true }
  }
  if (!_validReviewerResult(out) || out.confidence !== 'high') {
    roundFindings[reviewer] = { status: 'missing', dimension: reviewer, findings: _validReviewerResult(out) ? out.findings : [], confidence: _validReviewerResult(out) ? out.confidence : 'low', malformed: !_validReviewerResult(out), legacyArray: !!(out && out.legacyArray), escalated }
    return
  }
  roundFindings[reviewer] = Object.assign({ status: 'run', dimension: reviewer, escalated, tier: baseOpts.tier }, out)
}

async function synthesizeRound(roundFindings, context, rubric, runDir, round) {
  const compiled = panelTally.compileDimensionResults(roundFindings)
  const leaf = await synthesisLeaf(compiled, context, rubric, runDir, round)
  const consumed = loopSynthesis.consume(compiled, leaf && Array.isArray(leaf.verdicts) ? leaf.verdicts : [])
  return Object.assign(consumed, { usage: leaf && leaf.usage })
}

async function verifyAgent(verifyCommand, runDir, round) {
  // dumb pipe (run verify_gate.py, echo its JSON): courier:true so the bundle preamble pins it to
  // the cheapest model unconditionally (#118 — an unmarked label like 'run verify' inherits the
  // session model). The preamble strips the marker before the real agent().
  const out = await agent(
    `Run exactly this and return ONLY its stdout JSON, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/verify_gate.py --command ${shq(verifyCommand || 'none')} --emit-run`,
    { label: 'run verify', schema: VERIFY_SCHEMA, courier: true })
  if (!out) return 'fail'
  return verifyGateTwin.classify({ command: verifyCommand || 'none', returncode: out.returncode, timedOut: out.timedOut })
}

async function tallyRound({ runDir, round, roster, maxRounds, roundFindings = {}, records = [],
                           legKind = {}, synthesized = null, verifyResult = null,
                           fixStatus = 'completed', extras = null, policy = {}, coverageDecisions = [],
                           runId, enterConfirmation = false }) {
  const safeExtras = {}
  if (extras && typeof extras === 'object') {
    for (const k of ['fixes', 'deferred', 'parentOrigin']) if (k in extras) safeExtras[k] = extras[k]
  }
  try {
    if (!roster || roster.length === 0) {
      return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
        findings: [], missing: [], drops: [], terminal: 'cannot-certify', round,
        reason: 'empty reviewer set — nothing to certify' }, safeExtras)
    }
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: (coverageDecisions || []).map((d) => d.id).filter(Boolean) }
    const gateOut = panelTally.roundGateFromDimensionResults(
      roundFindings, roster, policy.roundKind === 'confirmation', receiptContext)
    const gate = gateOut.gate
    const confidence = gateOut.confidence
    const missing = gateOut.incomplete
    let compiled, drops
    if (synthesized && typeof synthesized === 'object') {
      compiled = synthesized.findings || []
      drops = synthesized.drops || []
    } else {
      compiled = panelTally.compileDimensionResults(roundFindings)
      drops = []
    }
    const deferredSet = await loadDeferredSet(runDir)
    const presentBlocking = panelTally.presentBlockingFromDimensionResults(roundFindings)
    const pdef = panelTally.presentDeferred(compiled, deferredSet)
    const skip = new Set(Object.keys(deferredSet))
    const prior = assembleRounds(records, deferredSet).filter((r) => r.round !== round)
    const priorRecords = (records || []).filter((r) => r && Number(r.round) !== round)
    const thisRound = {
      round,
      findings: compiled.filter((f) => !skip.has(circuitBreaker.findingIdentity(f))),
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
      terminal = 'continue'
      reason = 'awaiting final confirmation round'
    }
    if ((terminal === 'clean' || terminal === 'clean-with-skips') && policy.roundKind === 'confirmation') {
      // confirmation round succeeded — clear marker on persisted record handled next round
    }
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate, confidence, findings: compiled,
      missing, drops, terminal, reason, round }, safeExtras)
  } catch (exc) {
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
      findings: [], missing: [], drops: [], terminal: 'halted', round,
      reason: 'tally failed: ' + (exc && exc.message ? exc.message : exc) }, safeExtras)
  }
}

async function runFixStep(fixStep, fixContext, verdict, runDir) {
  try {
    const fixResult = await fixStep(fixContext, verdict, runDir)
    if (!fixResult) return { ok: false, extras: null, fixResult: null }
    await recordDeferred(fixResult, verdict, runDir)
    return { ok: true, extras: fixResult.extras || null, fixResult }
  } catch (e) {
    try { log(`review-panel: fix step failed, treating as fix failure -> halted: ${e && e.message ? e.message : e}`) } catch (_) {}
    return { ok: false, extras: null, fixResult: null }
  }
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
    terminal: { enum: ['continue', 'clean', 'clean-with-skips', 'cannot-certify', 'halted'] },
    reason: { type: 'string' },
    recordMissing: { type: 'boolean' },
  },
}
const SYNTH_SCHEMA = { type: 'object', required: ['findings', 'drops'],
  properties: { findings: { type: 'array' }, drops: { type: 'array' } } }
const VERIFY_SCHEMA = { type: 'object', required: ['command'],
  properties: { command: {}, returncode: {}, timedOut: {} } }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

module.exports = { reviewPanel, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }
