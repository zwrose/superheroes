// plugins/superheroes/lib/task_review.js
// In-process twin of task_review.py (#115 increment B) — byte-for-byte parity is CI-enforced
// (test_parity.py). The BESPOKE two-verdict per-task review decision (FR-5/FR-6/FR-7, UFR-5), NOT
// routed through reviewPanel. Reuses only the loop primitives: circuit_breaker.BLOCKING (the
// Critical/Important set), circuit_breaker.checkCircuitBreaker, and loop_state.decide.
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')

const REQUIRED_VERDICTS = ['spec_compliance', 'code_quality']
// exit_skipped maps to PARK, never complete: a deliberately-left-unresolved blocker must park (UFR-4).
// (The bespoke loop passes skippedBlocking=0 so loop_state never returns exit_skipped today; the
// fail-closed mapping guards against a future contract change rather than fail open.)
const _MAP = { review: 'review', exit_clean: 'complete', exit_skipped: 'park', halt: 'park' }

function _partition(findings) {
  const blocking = []; const minors = []; const cannotVerify = []
  for (const f of findings || []) {
    if (f && f.cannot_verify_from_diff) cannotVerify.push(f)
    // #276: the single, case-normalized, FAIL-CLOSED blocking predicate — only Minor/Nit demote;
    // every other severity (foreign scale, mis-cased, missing) is blocking. Shared with the circuit
    // breaker's own stuck-detection so the two can never disagree. Keep the leading `f &&` guard (as on
    // the cannot_verify line above) so a falsy element routes to minors rather than blocking — the
    // Python twin only ever receives dict findings, so this guard is JS-side defensiveness, not parity.
    if (f && circuitBreaker.isBlocking(f.severity)) blocking.push(f)
    else minors.push(f)
  }
  return { blocking, minors, cannotVerify }
}

function decide(verdicts, findings, rnd, maxRounds, history) {
  verdicts = verdicts || {}
  if (!REQUIRED_VERDICTS.every((k) => verdicts[k])) {
    return { action: 're_request', blocking: [], minors: [], cannot_verify: [],
      reason: 'both verdicts (spec-compliance + code-quality) are required (FR-5)' }
  }
  const { blocking, minors, cannotVerify } = _partition(findings)
  const rounds = (history || []).concat([{ round: rnd, findings: findings || [] }])
  const brk = circuitBreaker.checkCircuitBreaker(rounds, maxRounds)
  const [action, , loopReason] = loopState.decide(blocking.length, 0, rnd, maxRounds, !!brk.halt)
  let mapped = _MAP[action]
  let reason = loopReason
  if (brk.halt) {
    reason = brk.detail !== undefined ? brk.detail : reason
  }
  // FR-5/FR-6: the two verdicts GATE — they are not merely required-to-be-present. A non-'pass'
  // spec_compliance or code_quality can never complete, even with zero blocking findings, so a
  // reviewer that reports the task non-compliant sends it back for a fix round (#276). Vocabulary-
  // independent backstop: this holds even if a finding's severity drifts past _partition.
  const failing = REQUIRED_VERDICTS.filter((k) => verdicts[k] !== 'pass')
  if (mapped === 'complete' && failing.length) {
    mapped = 'review'
    reason = `verdict(s) ${failing.join(' + ')} are not 'pass' — the task is not compliant; a fix round is required before completion (FR-5/FR-6).`
  }
  // UFR-5: never complete while a cannot-verify item is unresolved — force a resolution round.
  if (mapped === 'complete' && cannotVerify.length) {
    mapped = 'review'
    reason = "unresolved 'cannot verify from diff' item(s) must be confirmed, sent back, or parked (UFR-5)"
  }
  return { action: mapped, blocking, minors, cannot_verify: cannotVerify, reason }
}

module.exports = { decide }
