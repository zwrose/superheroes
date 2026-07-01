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

async function loadRoundRecords(runDir, reviewerSet, ioApi) {
  const out = await ioApi.runHelper('python3', ['plugins/superheroes/lib/review_memory.py', 'load', '--path', ioApi.join(runDir, 'round-records.json'), '--dimensions', JSON.stringify(reviewerSet)])
  try {
    const parsed = JSON.parse(out.stdout || '{}')
    return parsed.ok ? parsed : Object.assign({ ok: false }, parsed)
  } catch (_) {
    return { ok: false, reason: 'round-memory-helper-failed' }
  }
}

async function persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi) {
  const args = ['plugins/superheroes/lib/review_memory.py', 'persist', '--path', ioApi.join(runDir, 'round-records.json'), '--dimensions', JSON.stringify(reviewerSet), '--record-json', JSON.stringify(record), '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  try {
    return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'helper-failed' }
  } catch (_) {
    return { ok: false, reason: 'helper-failed' }
  }
}

async function persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult, recordedCoverageDecisions, expectedHash, runId, lease, ioApi) {
  const record = Object.assign({}, (recordsForFix || []).find((r) => r && r.round === round) || {})
  record.confirmationPending = true
  record.changedSubjects = fixResult.changedSubjects || []
  record.coverageDecisions = recordedCoverageDecisions || []
  record.fix = { fixes: fixResult.fixes || fixResult.fixed || [], deferred: fixResult.deferred || [] }
  return persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi)
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

function telemetryPayload(records, expectedLeaves, usage, benchmark, terminal) {
  const missing = expectedLeaves.filter((leaf) => !usage[leaf])
  const total = expectedLeaves.reduce((sum, leaf) => sum + Number((usage[leaf] && usage[leaf].total) || 0), 0)
  const dimensionCounts = {}
  for (const rec of records || []) {
    for (const [name, dim] of Object.entries((rec && rec.dimensions) || {})) {
      const counts = dimensionCounts[name] || { run: 0, skipped: 0, cheap: 0, deep: 0, escalated: 0 }
      if (dim.status === 'skipped') counts.skipped += 1
      if (dim.status === 'run') counts.run += 1
      if (dim.tier === 'reviewer') counts.cheap += 1
      if (dim.tier === 'reviewer-deep') counts.deep += 1
      if (dim.escalated) counts.escalated += 1
      dimensionCounts[name] = counts
    }
  }
  return {
    schemaVersion: 1,
    terminal,
    roundCount: (records || []).length,
    rounds: records || [],
    tokenUsage: { complete: missing.length === 0, expectedLeaves, present: expectedLeaves.filter((leaf) => usage[leaf]), missing, total },
    dimensionCounts,
    benchmarkValid: !benchmark || missing.length === 0,
  }
}

async function writeTelemetry(runDir, payload, expectedHash, runId, lease, ioApi) {
  const args = ['plugins/superheroes/lib/review_telemetry.py', 'write', '--path', ioApi.join(runDir, 'review-telemetry.json'), '--payload-json', JSON.stringify(payload), '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId]
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
  let lastExtras = await ioApi.readJson(`${runDir}/last-extras.json`, null)
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
    const recordsForFix = Array.isArray(persisted.records) ? persisted.records : records.concat([record])
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

    const postFix = await persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult.fixResult || {}, recordedCoverageDecisions, persisted.contentHash, runId, lease, ioApi)
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
  const payload = telemetryPayload(records, expectedLeaves, allUsage, false, verdict.terminal)
  const telemPath = ioApi.join(runDir, 'review-telemetry.json')
  let telemHash = ioApi.contentHash('')
  try { telemHash = ioApi.contentHash(await ioApi.readText(telemPath)) } catch (_) {}
  const telemWrite = await writeTelemetry(runDir, payload, telemHash, runId, lease, ioApi)
  let telemetry = { benchmarkValid: false, reason: 'telemetry-write-failed' }
  if (telemWrite.ok) {
    try { telemetry = JSON.parse(await ioApi.readText(telemPath)) } catch (_) {}
  }
  return Object.assign({}, verdict, { telemetry })
}

function _validReviewerResult(out) {
  return !!out && Array.isArray(out.findings) && (out.confidence === 'high' || out.confidence === 'low')
}

async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings, opts) {
  const baseOpts = opts || {}
  let out = await reviewerAgent(reviewer, context, rubric, runDir, round, baseOpts)
  if (Array.isArray(out)) out = { findings: out, confidence: out.length === 0 ? 'high' : 'low', legacyArray: true }
  let escalated = false
  if (baseOpts.tier === 'reviewer' && (!_validReviewerResult(out) || out.confidence !== 'high')) {
    escalated = true
    out = await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, baseOpts, { tier: 'reviewer-deep', escalatedFrom: 'reviewer' }))
    if (Array.isArray(out)) out = { findings: out, confidence: out.length === 0 ? 'high' : 'low', legacyArray: true }
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
  const out = await agent(
    `Run exactly this and return ONLY its stdout JSON, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/verify_gate.py --command ${shq(verifyCommand || 'none')} --emit-run`,
    { label: `verify:r${round}`, schema: VERIFY_SCHEMA })
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
    const thisRound = {
      round,
      findings: compiled.filter((f) => !skip.has(circuitBreaker.findingIdentity(f))),
      coverageDecisions: coverageDecisions || [],
      generalizeRequired: reviewMemory.recurrentClasses(records, coverageDecisions || []),
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
    if (terminal === 'clean' && markedPending && !enterConfirmation) {
      terminal = 'continue'
      reason = 'awaiting final confirmation round'
    }
    if (terminal === 'clean' && policy.roundKind === 'confirmation') {
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
