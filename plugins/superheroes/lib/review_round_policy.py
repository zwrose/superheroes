#!/usr/bin/env python3
"""Schedule-only round policy for the shared review loop.

This helper never decides loop terminals and never computes recurrence. It only decides
round kind, reviewer run/skip choices, tiers, and cheap-result escalation policy.
"""

import circuit_breaker

DEEP = "reviewer-deep"
CHEAP = "reviewer"
# #174 confirmation-bar economics: at most this many FULL confirmation panels per loop, and the
# rework-breadth (distinct policy subjects the fix touched) at or above which a confirmation's
# rework counts as "cross-cutting" and re-arms one more full confirmation.
MAX_CONFIRMATIONS = 2
CROSS_CUTTING_SUBJECTS = 3
SUBJECT_FALLBACK = {
    "test": "Test",
    "security": "Security",
    "code": "Code",
    "architecture": "Architecture",
    "failure": "Failure-Mode",
    "premortem": "Failure-Mode",
}
POLICY_SUBJECTS = set(SUBJECT_FALLBACK.values())


def _dim(prev, name):
    if not isinstance(prev, dict):
        return {}
    info = prev.get(name, {})
    return info if isinstance(info, dict) else {}


def _changed_subjects(value):
    if not isinstance(value, list):
        return None
    out = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
            continue
        if isinstance(item, dict):
            for key in ("subject", "dimension", "policySubject"):
                subject = _policy_subject(item.get(key))
                if subject:
                    out.append(subject)
            # Section-only doc-reviser notes intentionally map to "known empty"; deep confirmation bounds skips.
            continue
        return None
    return sorted(set(out))


def _policy_subject(value):
    if not isinstance(value, str) or not value:
        return None
    if value in POLICY_SUBJECTS:
        return value
    return SUBJECT_FALLBACK.get(str(value or "").split("-")[0].lower())


def _safe_round(value):
    if value is None or value == "":
        return 1, False
    try:
        n = int(value)
        if isinstance(value, float) or (isinstance(value, str) and "." in str(value).strip()):
            return 1, True
        return n, False
    except (TypeError, ValueError):
        return 1, True


def _subjects(name, info):
    if isinstance(info.get("subjects"), list):
        return [s for s in info.get("subjects") if isinstance(s, str)]
    subjects = []
    for finding in info.get("findings") or []:
        if isinstance(finding, dict) and isinstance(finding.get("dimension"), str):
            subjects.append(finding["dimension"])
    prefix = str(name or "").split("-")[0].lower()
    fallback = SUBJECT_FALLBACK.get(prefix)
    if fallback:
        subjects.append(fallback)
    return sorted(set(subjects))


def _has_findings(info):
    findings = info.get("findings")
    current = info.get("currentFindings")
    carried = info.get("carriedFindings")
    for value in (findings, current, carried):
        if isinstance(value, list) and len(value) > 0:
            return True
    if isinstance(info.get("hasFindings"), bool):
        return info["hasFindings"]
    if isinstance(findings, list):
        return len(findings) > 0
    return None


def _subject_touched(name, info, changed_subjects):
    if changed_subjects is None:
        return None
    subjects = _subjects(name, info)
    return bool(set(subjects) & set(changed_subjects))


def plan_round(state):
    state = state or {}
    dimensions = list(state.get("dimensions") or []) if isinstance(state.get("dimensions") or [], list) else []
    previous = state.get("previous") if isinstance(state.get("previous"), dict) else {}
    changed_subjects = _changed_subjects(state.get("changedSubjects"))
    confirmation = bool(state.get("confirmation"))
    round_no, malformed_round = _safe_round(state.get("round"))

    if malformed_round:
        return {
            "roundKind": "intermediate",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "malformed round state"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    if confirmation:
        return {
            "roundKind": "confirmation",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "confirmation full-panel"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    if round_no <= 1:
        return {
            "roundKind": "baseline",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "baseline full-panel"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    if changed_subjects is None:
        return {
            "roundKind": "intermediate",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "unknown changed subjects"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    out = {}
    for name in dimensions:
        info = _dim(previous, name)
        touched = _subject_touched(name, info, changed_subjects)
        has_findings = _has_findings(info)
        if has_findings is True or touched:
            out[name] = {"action": "run", "tier": CHEAP, "reason": "previous finding or changed subject"}
        elif info.get("confidence") == "high" and has_findings is False:
            out[name] = {
                "action": "skip",
                "tier": DEEP,
                "reason": "high-confidence clean and untouched",
                "carriedFromRound": info.get("round"),
            }
        else:
            out[name] = {"action": "run", "tier": DEEP, "reason": "not skip eligible"}
    return {"roundKind": "intermediate", "dimensions": out, "escalationPolicy": "cheap-first"}


def is_cross_cutting(changed_subjects, threshold=CROSS_CUTTING_SUBJECTS):
    """#174: the rework of a confirmation's fix is 'cross-cutting' when it touched at least
    `threshold` distinct policy subjects (default ≥3 of the 5). Reuses the shared changed-subjects
    normalizer, so a malformed / unknown surface returns None → treated as cross-cutting (fail
    toward one more confirmation, never toward a premature certify)."""
    subjects = _changed_subjects(changed_subjects)
    if subjects is None:
        return True
    return len(set(subjects)) >= threshold


def confirmation_followup(surfaced_severities, confirmations_run, cross_cutting,
                          max_confirmations=MAX_CONFIRMATIONS):
    """#174 confirmation-bar economics — the follow-up decision after a FULL confirmation panel
    surfaced blocking findings (which the fix loop still resolves + verifies, requirement 1).

    Requirements 2 & 3:
      - Only a Critical surfaced by the confirmation, OR cross-cutting rework, triggers one more
        full confirmation panel.
      - Hard cap: at most `max_confirmations` full confirmation panels per loop.
      - A Critical still owed at the cap parks (certification withheld, fail-safe direction
        unchanged); a non-Critical at the cap is resolved by a scoped verify, then certified.

    Returns {rearm, park, atCap, reason} — all deterministic; the caller schedules another full
    confirmation iff `rearm`, and withholds certification (parks) iff `park`."""
    sevs = [s for s in (surfaced_severities or []) if isinstance(s, str)]
    # #291: case-normalized Critical match — a surfaced mis-cased `critical` must still park at the cap
    # (was `"Critical" in sevs`, case-sensitive, so a lowercase Critical resolved by scoped verify).
    has_critical = any(circuit_breaker.is_critical(s) for s in sevs)
    trigger = has_critical or bool(cross_cutting)
    at_cap = confirmations_run >= max_confirmations
    if not trigger:
        return {"rearm": False, "park": False, "atCap": at_cap,
                "reason": "non-Critical findings, rework not cross-cutting — resolve by scoped "
                          "verify; no further confirmation panel"}
    if at_cap:
        if has_critical:
            return {"rearm": False, "park": True, "atCap": True,
                    "reason": "Critical surfaced at the confirmation-panel cap — park; "
                              "certification withheld"}
        return {"rearm": False, "park": False, "atCap": True,
                "reason": "confirmation-panel cap reached — resolve remaining by scoped verify; "
                          "no further panel"}
    return {"rearm": True, "park": False, "atCap": False,
            "reason": ("Critical surfaced by confirmation" if has_critical else "cross-cutting "
                       "rework") + " — one more full confirmation panel required"}
