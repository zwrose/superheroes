// plugins/superheroes/lib/panel_tally.js
const { findingIdentity } = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
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
      byId[fid] = merged
    } else byId[fid] = Object.assign({}, f)
  }
  const out = Object.values(byId)
  for (const f of out) f.classification = f.tradeoff ? 'judgment' : 'mechanical'
  return out
}
function roundGate(compiled, expectedRoster, completedRoster) {
  const incomplete = expectedRoster.filter((r) => !completedRoster.includes(r))
  const hasBlocker = compiled.some((f) => BLOCKING.has(f.severity))
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
    if (!BLOCKING.has(f.severity)) continue
    const deferredSev = deferredSet[findingIdentity(f)]
    if (deferredSev === undefined || deferredSev === null) continue
    if ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) >= (SEV_RANK[deferredSev] != null ? SEV_RANK[deferredSev] : 99)) n += 1
  }
  return n
}
function decideTerminal(gate, presentBlocking, presentDeferredCount, fixStatus, rnd, maxRounds, breakerHalt) {
  if (gate === 'cannot-certify') return { terminal: 'cannot-certify', reason: 'a reviewer did not complete after its retry — coverage not certified' }
  if (fixStatus === 'failed') return { terminal: 'halted', reason: 'the fix step did not complete (failed or timed out)' }
  const blockingFixed = Math.max(0, presentBlocking - presentDeferredCount)
  const [action, , reason] = loopState.decide(blockingFixed, presentDeferredCount, rnd, maxRounds, !!breakerHalt)
  return { terminal: _ACTION_TO_TERMINAL[action], reason }
}
function _currentBlockingFindings(results) {
  const out = []
  for (const [, result] of Object.entries(results || {})) {
    if (!result || result.status !== 'run') continue
    for (const f of Array.isArray(result.findings) ? result.findings : []) {
      if (!f || f.carried) continue
      if (BLOCKING.has(f.severity)) out.push(f)
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
module.exports = { compileFindings, roundGate, presentDeferred, decideTerminal, compileDimensionResults, roundGateFromDimensionResults, presentBlockingFromDimensionResults, blockingFindingsFromDimensionResults, BLOCKING, SEV_RANK, _ACTION_TO_TERMINAL }
