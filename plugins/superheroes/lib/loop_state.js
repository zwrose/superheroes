// plugins/superheroes/lib/loop_state.js
function decide(blockingFixed, skippedBlocking, rnd, maxRounds, breakerHalt) {
  if (breakerHalt) {
    return ['halt', true, 'circuit breaker halted (stuck / recurrence) — stop and report the still-open findings and the commit range; do not loop further.']
  }
  if (blockingFixed > 0) {
    if (rnd >= maxRounds) {
      return ['halt', true, `round cap (${maxRounds}) reached with blocking fixes still landing — REPORT the open findings; do NOT declare success.`]
    }
    return ['review', true, `MANDATORY: ${blockingFixed} blocking (Critical/Important) finding(s) were addressed this round — re-review from scratch to verify they resolved and introduced nothing new. You may NOT exit, declare success, or offer the next round as 'optional'. The loop exists to verify fixes; your confidence that 'it is clean' is exactly what this gate overrides.`]
  }
  if (skippedBlocking > 0) {
    return ['exit_skipped', false, `no blocking finding addressed; ${skippedBlocking} blocking finding(s) were deliberately skipped — exit CLEAN-EXCEPT-FOR-SKIPPED: list the skipped blocker(s); do not report a plain success.`]
  }
  return ['exit_clean', false, 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.']
}
module.exports = { decide }
