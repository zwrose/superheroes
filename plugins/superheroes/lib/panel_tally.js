// plugins/superheroes/lib/panel_tally.js
const { findingIdentity, isBlocking } = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
// BLOCKING is the drift-guarded canonical blocking vocabulary (exported; SSOT §11). The blocking
// PARTITION decision routes through circuit_breaker.isBlocking (#276) — case-normalized + fail-closed
// — so the panel gate never disagrees with _partition / the breaker on what blocks.
const BLOCKING = new Set(['Critical', 'Important'])
const SEV_RANK = { Critical: 0, Important: 1, Minor: 2, Nit: 3 }
const _ACTION_TO_TERMINAL = { review: 'continue', exit_clean: 'clean', exit_skipped: 'clean-with-skips', halt: 'halted' }

function _mergeDims(a, b) {
  const parts = []
  for (const src of [a.dimension, b.dimension]) {
    if (!src) continue
    for (let p of String(src).split('+')) { p = p.trim(); if (p && !parts.includes(p)) parts.push(p) }
  }
  return parts.join(' + ')
}
function compileFindings(findings, contextFiles) {
  const byId = Object.create(null)   // null-proto: `fid in byId` tests own keys only (Python dict parity)
  for (const f of findings) {
    if (f.file === null || f.file === undefined || f.line === null || f.line === undefined) continue
    if (contextFiles != null && !contextFiles.includes(f.file)) continue
    const fid = findingIdentity(f)
    if (fid in byId) {
      const ex = byId[fid]
      const dims = _mergeDims(ex, f)
      const merged = ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) <
                      (SEV_RANK[ex.severity] != null ? SEV_RANK[ex.severity] : 99)) ? Object.assign({}, f) : Object.assign({}, ex)
      merged.dimension = dims
      if (!merged.docSection) {
        const preserved = ex.docSection || f.docSection
        if (preserved) merged.docSection = preserved
      }
      byId[fid] = merged
    } else byId[fid] = Object.assign({}, f)
  }
  const out = Object.values(byId)
  for (const f of out) f.classification = f.tradeoff ? 'judgment' : 'mechanical'
  return out
}
function roundGate(compiled, expectedRoster, completedRoster) {
  const incomplete = expectedRoster.filter((r) => !completedRoster.includes(r))
  const hasBlocker = compiled.some((f) => isBlocking(f.severity))
  let gate
  if (incomplete.length) gate = 'cannot-certify'
  else if (hasBlocker) gate = 'blocking'
  else gate = 'clean'
  const allVerifiable = compiled.every((f) => !!f.evidence)
  const confidence = (!incomplete.length && allVerifiable) ? 'high' : 'low'
  return { gate, confidence, incomplete }
}
function presentDeferred(compiled, deferredSet) {
  let n = 0
  for (const f of compiled) {
    if (!isBlocking(f.severity)) continue
    const deferredSev = deferredSet[findingIdentity(f)]
    if (deferredSev === undefined || deferredSev === null) continue
    if ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) >= (SEV_RANK[deferredSev] != null ? SEV_RANK[deferredSev] : 99)) n += 1
  }
  return n
}
function decideTerminal(gate, presentBlocking, presentDeferredCount, fixStatus, rnd, maxRounds, breakerHalt) {
  // FR-9 precedence (#212 fix-before-park): a cannot-certify round with NO fixable blocking finding
  // parks immediately (coverage is the sole gap). A cannot-certify round that STILL holds unresolved
  // blockers is NOT parked — its findings are real regardless of the uncertified seat, so it routes
  // to the fix leg like a `blocking` round (falls through). Gate-based, so it covers every entrance
  // to cannot-certify uniformly (receipt-missing/stale, a missing/malformed seat, a coverage-gap
  // round holding blockers). Certification stays withheld: the next round's gate re-dooms the seat.
  const blockingFixed = Math.max(0, presentBlocking - presentDeferredCount)
  if (gate === 'cannot-certify' && blockingFixed === 0) {
    return { terminal: 'cannot-certify', reason: 'coverage not certified — a review seat did not certify after its retry' }
  }
  if (fixStatus === 'failed') return { terminal: 'halted', reason: 'the fix step did not complete (failed or timed out)' }
  const [action, , reason] = loopState.decide(blockingFixed, presentDeferredCount, rnd, maxRounds, !!breakerHalt)
  return { terminal: _ACTION_TO_TERMINAL[action], reason }
}
// The defect-class phrasing that names WHY a seat could not certify (#212). Each class is a DISTINCT
// string so a park diagnoses the failure instead of anonymizing it.
const _SEAT_PHRASE = {
  'receipt-missing': (n) => `${n} returned no verification receipt after retry (receipt-missing — uncertifiable)`,
  'receipt-stale': (n) => `${n} returned a stale verification receipt after retry (receipt-stale — uncertifiable)`,
  malformed: (n) => `${n} did not return a usable result after retry (malformed — uncertifiable)`,
  'genuinely-incomplete': (n) => `${n} reported low confidence after retry (genuinely-incomplete — uncertifiable)`,
  'coverage-gap': (n) => `${n} did not complete after its retry (coverage-gap — uncertifiable)`,
}
function _seatDefectClass(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return 'coverage-gap'
  if (result.externalReview) return null
  if (result.confidence === 'high') return null
  if (result.receiptMissing) return 'receipt-missing'
  if (result.receiptStale) return 'receipt-stale'
  if ((result.status !== 'run' && result.status !== 'skipped') || result.malformed) return 'malformed'
  if (result.status === 'skipped') return 'coverage-gap'
  return 'genuinely-incomplete'
}
function uncertifiedReason(results, expectedRoster) {
  // The honest cannot-certify reason: name every seat that blocks certification AND why (#212).
  // Returns a `;`-joined phrase, or null when every seat certified (caller keeps the terminal reason).
  results = results || {}
  const parts = []
  for (const name of expectedRoster || []) {
    const cls = _seatDefectClass(results[name])
    if (cls) parts.push(_SEAT_PHRASE[cls](name))
  }
  return parts.length ? parts.join('; ') : null
}
function _currentBlockingFindings(results) {
  const out = []
  for (const [, result] of Object.entries(results || {})) {
    if (!result || result.status !== 'run') continue
    for (const f of Array.isArray(result.findings) ? result.findings : []) {
      if (!f || f.carried) continue
      if (isBlocking(f.severity)) out.push(f)
    }
  }
  return out
}
function presentBlockingFromDimensionResults(results) {
  return _currentBlockingFindings(results).length
}
function blockingFindingsFromDimensionResults(results) {
  return _currentBlockingFindings(results).map((f) => Object.assign({}, f))
}
function compileDimensionResults(results) {
  const findings = []
  for (const [name, result] of Object.entries(results || {})) {
    if (!result || typeof result !== 'object' || Array.isArray(result)) continue
    for (const f of Array.isArray(result.findings) ? result.findings : []) {
      if (!f || typeof f !== 'object' || Array.isArray(f)) continue
      const item = Object.assign({}, f)
      if (!Object.prototype.hasOwnProperty.call(item, 'dimension')) item.dimension = result.dimension || name
      if (result.status === 'skipped') {
        item.carried = true
        item.sourceRound = result.carriedFromRound
      }
      findings.push(item)
    }
  }
  return compileFindings(findings)
}
function _validFinalReceipt(result, receiptContext) {
  const receipt = result && result.verificationReceipt
  if (!receipt || !receipt.artifact || !Array.isArray(receipt.coverageDecisionIds)) return false
  receiptContext = receiptContext || {}
  if (receiptContext.artifact && receipt.artifact !== receiptContext.artifact) return false
  const needed = new Set(receiptContext.coverageDecisionIds || [])
  const gotIds = new Set(receipt.coverageDecisionIds || [])
  for (const id of needed) if (!gotIds.has(id)) return false
  const chain = Array.isArray(receipt.chain) ? receipt.chain : []
  const got = new Set()
  for (const step of chain) {
    if (!step || typeof step !== 'object' || !step.evidence) return false
    got.add(step.step)
  }
  return ['citation', 'reachability', 'missing-check', 'tooling'].every((x) => got.has(x))
}
function roundGateFromDimensionResults(results, expectedRoster, finalConfirmation, receiptContext) {
  const completed = Object.entries(results || {})
    .filter(([, result]) => result.status === 'run' || result.status === 'skipped')
    .map(([name]) => name)
  const compiled = compileDimensionResults(results)
  const base = roundGate(compiled, expectedRoster, completed)
  for (const name of expectedRoster) {
    const result = (results || {})[name] || {}
    if (result.confidence !== 'high') return { gate: 'cannot-certify', confidence: 'low', incomplete: base.incomplete }
  }
  if (finalConfirmation) {
    for (const name of expectedRoster) {
      const result = (results || {})[name] || {}
      // externalReview (#38/receipt-fabrication fix): an external-engine reviewer has no native
      // chain-of-verification receipt to offer, but it IS a real independent review — accept it as
      // an alternate, honestly-labeled confirmation path instead of demanding a receipt shape it
      // structurally can't produce.
      if (result.externalReview) continue
      if (!_validFinalReceipt(result, receiptContext)) {
        return { gate: 'cannot-certify', confidence: 'low', incomplete: base.incomplete }
      }
    }
  }
  if (base.gate === 'clean' && _currentBlockingFindings(results).length > 0) {
    return { gate: 'blocking', confidence: base.confidence, incomplete: base.incomplete }
  }
  return base
}
module.exports = { compileFindings, roundGate, presentDeferred, decideTerminal, uncertifiedReason, compileDimensionResults, roundGateFromDimensionResults, presentBlockingFromDimensionResults, blockingFindingsFromDimensionResults, BLOCKING, SEV_RANK, _ACTION_TO_TERMINAL }
