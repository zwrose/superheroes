#!/usr/bin/env python3
"""Schedule-only round policy for the shared review loop.

This helper never decides loop terminals and never computes recurrence. It only decides
round kind, reviewer run/skip choices, tiers, and cheap-result escalation policy.
"""

DEEP = "reviewer-deep"
CHEAP = "reviewer"
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
