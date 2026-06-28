// plugins/superheroes/lib/worker_recovery.js
// In-process twin of worker_recovery.py (#115 increment B) — byte-for-byte parity is CI-enforced
// (test_parity.py). Bounded build-worker recovery (UFR-3): (attempt, signal, maxAttempts) ->
// {action, reason} where action ∈ retry_with_context | escalate | park. A "plan is wrong" signal
// parks immediately; otherwise retry (early attempts), escalate on the attempt before the cap, then
// park at the cap.
const PLAN_WRONG = 'plan_wrong'
const DEFAULT_MAX_ATTEMPTS = 3

function decide(attempt, signal, maxAttempts = DEFAULT_MAX_ATTEMPTS) {
  if (signal === PLAN_WRONG) {
    return { action: 'park',
      reason: 'worker signalled the plan/task is wrong or too large — park (UFR-3)' }
  }
  if (attempt >= maxAttempts) {
    return { action: 'park',
      reason: `worker still blocked at the fixed maximum (${maxAttempts}) — park (UFR-3)` }
  }
  if (attempt === maxAttempts - 1) {
    return { action: 'escalate',
      reason: 'retry budget nearly spent — escalate to a more capable worker (UFR-3)' }
  }
  return { action: 'retry_with_context',
    reason: `worker needs more context — retry (attempt ${attempt} of ${maxAttempts})` }
}

module.exports = { decide, DEFAULT_MAX_ATTEMPTS, PLAN_WRONG }
