"""Ceiling decider for the acceptance harness (FR-8 / FR-9 / UFR-2).

Pure `decide(state)` over a plain dict: judges whether a live run has breached its
elapsed-time or spend ceiling and must be hard-killed, or may continue. Fail-CLOSED on
the readable ceiling — when spend is unreadable the run governs on elapsed alone and NEVER
kills on spend (an unreadable spend sample can never justify a kill, and can never mask an
elapsed breach).

The breach test is **invocation-scoped**: it compares the running invocation's fresh
`elapsed_sec` / `spend_sampled` PLUS the `budget_consumed` a prior attempt already burned
against the ceilings, so a retry (`attempt >= 2`, non-zero `budget_consumed`) trips on the
*remaining* budget rather than a fresh full ceiling. On attempt 1 (`budget_consumed` all
zero) this reduces to the raw comparison, so first-attempt behavior is unchanged.

`remaining` is the budget a retry inherits (`ceiling - budget_consumed`), with `spend`
`None` when the spend ceiling is unreadable this sample.

Mirrors `preflight.decide` (pure, no I/O; all clock/spend sampling lives in the mechanical
layer and is injected as `state`). Never raises.
"""

# Conservative built-in defaults applied when the owner configured no ceilings (FR-8):
# 30 minutes wall-clock, 5M measured output tokens.
DEFAULT_CEILINGS = {"elapsed_sec": 1800.0, "spend": 5_000_000.0}


def _positive_number(value, default):
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return default


def normalize_ceilings(ceilings=None):
    """Merge a partial owner ceiling dict with defaults. Never raises."""
    src = ceilings if isinstance(ceilings, dict) else {}
    return {
        "elapsed_sec": _positive_number(src.get("elapsed_sec"), DEFAULT_CEILINGS["elapsed_sec"]),
        "spend": _positive_number(src.get("spend"), DEFAULT_CEILINGS["spend"]),
    }


def decide(state):
    """Pure ceiling judgment over the injected `state` dict.

    Returns `{"action": "continue"|"kill", "ceiling": None|"elapsed"|"spend",
    "remaining": {"elapsed_sec": float, "spend": float|None}}`.

    Invocation-scoped totals fold in `budget_consumed` so a retry trips on the remaining
    budget. Spend only governs when `spend_readable`; otherwise the run continues on the
    elapsed ceiling alone and never kills on spend (fail-closed on the readable ceiling).
    """
    if not isinstance(state, dict):
        state = {}

    ceilings = normalize_ceilings(state.get("ceilings"))
    ceiling_elapsed = ceilings.get("elapsed_sec")
    ceiling_spend = ceilings.get("spend")

    consumed = state.get("budget_consumed") or {}
    consumed_elapsed = consumed.get("elapsed_sec") or 0.0
    consumed_spend = consumed.get("spend") or 0.0

    spend_readable = bool(state.get("spend_readable"))
    spend_sampled = state.get("spend_sampled")

    elapsed_sec = state.get("elapsed_sec") or 0.0

    # Remaining budget a retry inherits (invocation-scoped: ceiling - already-consumed).
    remaining = {
        "elapsed_sec": ceiling_elapsed - consumed_elapsed,
        "spend": (ceiling_spend - consumed_spend) if spend_readable else None,
    }

    # Invocation-scoped totals: this attempt's fresh usage plus any prior-attempt budget.
    total_elapsed = elapsed_sec + consumed_elapsed

    if total_elapsed >= ceiling_elapsed:
        return {"action": "kill", "ceiling": "elapsed", "remaining": remaining}

    # Spend only governs when readable; an unreadable sample never kills on spend.
    if spend_readable:
        total_spend = (spend_sampled or 0.0) + consumed_spend
        if total_spend >= ceiling_spend:
            return {"action": "kill", "ceiling": "spend", "remaining": remaining}

    return {"action": "continue", "ceiling": None, "remaining": remaining}
