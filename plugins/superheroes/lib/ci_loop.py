"""Deterministic bound for the step 8 CI-fix loop — the band's loop-skipping defense
(cf. loop_state.py / circuit_breaker.py) applied to CI. Pure + fail-CLOSED: on a
bad/ambiguous input it HALTS (revert-to-draft + GATE), never loops free.
"""

DEFAULT_MAX_ROUNDS = 5


def decide(failing_signatures, history, rnd, max_rounds=DEFAULT_MAX_ROUNDS):
    """('fix' | 'revert_and_gate', reason).

    failing_signatures: list/tuple of the current red checks' stable ids (empty
        => green; the caller should not call decide when green).
    history: list of prior rounds' failing_signatures (most recent last).
    rnd: 1-based current round number.
    Halts (revert_and_gate) when: no actionable failures (caller error), the round
    cap is reached, or the exact same red set recurs (no net progress).
    """
    if not isinstance(failing_signatures, (list, tuple)) or not failing_signatures:
        return ("revert_and_gate", "no actionable failing checks (fail-closed)")
    cur = tuple(sorted(failing_signatures))
    if rnd >= max_rounds:
        return ("revert_and_gate", "CI-fix round cap (%d) reached" % max_rounds)
    for prev in history or []:
        if tuple(sorted(prev)) == cur:
            return ("revert_and_gate", "recurring CI failure set — no net progress")
    return ("fix", "attempt round %d" % rnd)
