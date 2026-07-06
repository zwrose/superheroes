"""Pure CI-status classifier for the ship phase (green / red / pending / none).
Fail-CLOSED for certification: only an unambiguous pass set is green — a check that is
failing/errored/unknown is red, and a check that is still RUNNING is "pending", its own
status (0.10.0 qualification finding: pending folded into red made the ship loop dispatch
a CI fixer against checks that were merely in flight; the fixer had nothing to fix and the
run parked. Pending means WAIT, red means FIX — neither ever certifies green).
"""

_PASS = {"pass", "success", "skipping", "skipped", "neutral"}
_PENDING = {"pending", "queued", "in_progress", "expected", "waiting", "requested"}
# Canonical cross-boundary export (CONVENTIONS §11): acceptance_deps._rollup_pending
# consumes this — never fork a second pending-state list.
PENDING_STATES = frozenset(x.upper() for x in _PENDING)


def _bucket(item):
    if not isinstance(item, dict):
        return "unknown"
    return str(item.get("bucket") or item.get("state") or item.get("conclusion") or "unknown").lower()


def classify(checks):
    """({"status": "green"|"red"|"pending"|"none", "failing": [name...], "pending": [name...]}).

    none    = no checks gate the PR (empty/None input).
    green   = at least one gating check and every one is a pass.
    pending = nothing hard-failed but at least one check is still running.
    red     = any check hard-failed (or is an unknown non-pass state — fail closed);
              `failing` names ONLY those, never the still-running ones, so a CI-fix
              leg is aimed at real failures and a settle-wait at the rest.
    """
    if not isinstance(checks, (list, tuple)) or not checks:
        return {"status": "none", "failing": [], "pending": []}
    failing = []
    pending = []
    saw_gating = False
    for item in checks:
        b = _bucket(item)
        name = item.get("name") if isinstance(item, dict) else None
        if b in ("skipping", "skipped", "neutral"):
            continue
        saw_gating = True
        if b in _PASS:
            continue
        if b in _PENDING:
            pending.append(name or "unknown")
        else:
            failing.append(name or "unknown")
    if failing:
        return {"status": "red", "failing": failing, "pending": pending}
    if pending:
        return {"status": "pending", "failing": [], "pending": pending}
    if not saw_gating:
        return {"status": "none", "failing": [], "pending": []}
    return {"status": "green", "failing": [], "pending": []}
