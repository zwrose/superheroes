# plugins/superheroes/lib/task_review.py
"""Per-task review decision (FR-5/FR-6/FR-7, UFR-5) — the BESPOKE two-verdict review, NOT routed
through reviewPanel. Reuses only the loop primitives: circuit_breaker.BLOCKING (the
Critical/Important set), circuit_breaker.check_circuit_breaker, and loop_state.decide."""
import circuit_breaker
import loop_state

REQUIRED_VERDICTS = ("spec_compliance", "code_quality")
# The ONLY severities that demote a finding to a non-blocking Minor: the rubric's non-blocking tiers
# (Minor/Nit — SSOT §11, guarded by test_ssot_drift). Matched case-insensitively, and — crucially —
# every OTHER value FAILS CLOSED to blocking (#276): a foreign scale (`blocker`/`high`/`medium`), an
# unknown tier, a mis-cased `critical`, or a missing severity must never silently demote a blocker to
# a Minor. Unknown severity means blocking, not non-blocking.
_NON_BLOCKING = frozenset({"minor", "nit"})
# exit_skipped maps to PARK, never complete: a deliberately-left-unresolved blocker must park (UFR-4).
# (The bespoke loop passes skipped_blocking=0 so loop_state never returns exit_skipped today; the
# fail-closed mapping guards against a future contract change rather than fail open.)
_MAP = {"review": "review", "exit_clean": "complete", "exit_skipped": "park", "halt": "park"}


def _is_blocking(severity):
    return str("" if severity is None else severity).strip().lower() not in _NON_BLOCKING


def _partition(findings):
    blocking, minors, cannot_verify = [], [], []
    for f in findings or []:
        if f.get("cannot_verify_from_diff"):
            cannot_verify.append(f)
        if _is_blocking(f.get("severity")):
            blocking.append(f)
        else:
            minors.append(f)
    return blocking, minors, cannot_verify


def decide(verdicts, findings, rnd, max_rounds, history):
    verdicts = verdicts or {}
    if not all(verdicts.get(k) for k in REQUIRED_VERDICTS):
        return {"action": "re_request", "blocking": [], "minors": [], "cannot_verify": [],
                "reason": "both verdicts (spec-compliance + code-quality) are required (FR-5)"}
    blocking, minors, cannot_verify = _partition(findings)
    rounds = list(history or []) + [{"round": rnd, "findings": findings or []}]
    brk = circuit_breaker.check_circuit_breaker(rounds, max_rounds)
    action, _mandatory, reason = loop_state.decide(
        blocking_fixed=len(blocking), skipped_blocking=0, rnd=rnd,
        max_rounds=max_rounds, breaker_halt=bool(brk.get("halt")))
    mapped = _MAP[action]
    if brk.get("halt"):
        reason = brk.get("detail", reason)
    # FR-5/FR-6: the two verdicts GATE — they are not merely required-to-be-present. A non-'pass'
    # spec_compliance or code_quality can never complete, even with zero blocking findings, so a
    # reviewer that reports the task non-compliant sends it back for a fix round (#276). Vocabulary-
    # independent backstop: this holds even if a finding's severity drifts past _partition.
    failing = [k for k in REQUIRED_VERDICTS if verdicts.get(k) != "pass"]
    if mapped == "complete" and failing:
        mapped = "review"
        reason = ("verdict(s) %s are not 'pass' — the task is not compliant; a fix round is required "
                  "before completion (FR-5/FR-6)." % " + ".join(failing))
    # UFR-5: never complete while a cannot-verify item is unresolved — force a resolution round.
    if mapped == "complete" and cannot_verify:
        mapped = "review"
        reason = ("unresolved 'cannot verify from diff' item(s) must be confirmed, sent back, "
                  "or parked (UFR-5)")
    return {"action": mapped, "blocking": blocking, "minors": minors,
            "cannot_verify": cannot_verify, "reason": reason}
