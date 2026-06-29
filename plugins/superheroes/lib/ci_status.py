"""Pure CI-status classifier for the ship phase (green / red / none). Fail-CLOSED:
a check that is not unambiguously a pass (fail/cancel/error/pending/unknown) is
treated as not-green, so the run never certifies green it cannot substantiate.
"""

_PASS = {"pass", "success", "skipping", "skipped", "neutral"}
_BAD = {"fail", "failure", "cancel", "cancelled", "error", "timed_out", "action_required",
        "pending", "queued", "in_progress", "expected", "stale", "startup_failure"}


def _bucket(item):
    if not isinstance(item, dict):
        return "unknown"
    return str(item.get("bucket") or item.get("state") or item.get("conclusion") or "unknown").lower()


def classify(checks):
    """({"status": "green"|"red"|"none", "failing": [name...]}).

    none  = no checks gate the PR (empty/None input).
    green = at least one check and every non-skipped check is a pass.
    red   = any check is not a pass (failing, errored, or still pending).
    """
    if not isinstance(checks, (list, tuple)) or not checks:
        return {"status": "none", "failing": []}
    failing = []
    saw_gating = False
    for item in checks:
        b = _bucket(item)
        name = item.get("name") if isinstance(item, dict) else None
        if b in ("skipping", "skipped", "neutral"):
            continue
        saw_gating = True
        if b not in _PASS:
            failing.append(name or "unknown")
    if failing:
        return {"status": "red", "failing": failing}
    if not saw_gating:
        return {"status": "none", "failing": []}
    return {"status": "green", "failing": []}
