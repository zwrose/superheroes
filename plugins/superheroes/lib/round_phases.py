#!/usr/bin/env python3
"""Shared phase-name constants and cycle-free helpers for the round driver and its record/adapter
layers (#723).

Single home for the `P_*` action strings so `round_driver`, `round_adapters`, and
`round_records` agree without import cycles. Stdlib-only."""
# Phases (the `action` a `next` emits; each is fulfilled by exactly one orchestrator dispatch).
P_PANEL = "dispatch-panel"
P_VERIFIERS = "dispatch-verifiers"
P_SYNTHESIS = "dispatch-synthesis"
P_AUDITS = "dispatch-audits"
P_SCOPED = "dispatch-scoped-finder"
P_GAPSWEEP = "dispatch-gap-sweep"
P_VERIFY = "run-verify"
P_FIXER = "dispatch-fixer"
P_JUDGMENT = "present-judgment"
P_STALL = "present-stall-menu"
P_TERMINAL = "terminal"

ALL_PHASES = (
    P_PANEL, P_VERIFIERS, P_SYNTHESIS, P_AUDITS, P_SCOPED, P_GAPSWEEP, P_VERIFY, P_FIXER,
    P_JUDGMENT, P_STALL, P_TERMINAL,
)

# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only (doc
# provenance) — deliberately absent here; test_dispatch_tables pins the per-leg subset.
DIMENSIONS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
              "test-reviewer", "premortem-reviewer"]

# The four stall-menu choices (never "judge the dispute yourself"). accept-the-risk is offerable
# ONLY for a CONFIRMED-with-receipt finding; the menu payload gates it per-run.
ACCEPT_RISK_CHOICE = "accept-the-disclosed-risk"
STALL_CHOICES = ("ship-smaller", "spend-more", ACCEPT_RISK_CHOICE, "hold")

# The three per-finding judgment dispositions the judgment gate offers (never "judge the dispute
# yourself"): fix the finding as the reviewer suggested, fix it with owner free-text guidance, or
# skip it with a citable reason (a skipped blocker rides the exit disclosure — the skipped-blocking
# channel). The judgment gate is an INTERVENTION that folds back into the fix leg, NOT a terminal
# (#507 R2a) — the stall menu is the ONLY terminal, reachable solely from the audit-stall path.
JUDGMENT_DISPOSITIONS = ("fix-as-suggested", "fix-with-guidance", "skip")


def panel_dimensions(config):
    """Configured panel dimensions, or the default DIMENSIONS list."""
    dims = config.get("dimensions") if isinstance(config, dict) else None
    if isinstance(dims, (list, tuple)):
        strings = [d for d in dims if isinstance(d, str)]
        return strings if strings else list(DIMENSIONS)
    return list(DIMENSIONS)


# Verify submit-shape guard — lives here so `round_adapters` never imports `round_driver`.
_VERIFY_RESULTS = ("pass", "fail", "timeout", "skipped", "none", "unverified")

_VERIFY_RUNNER_ENVELOPE_HINTS = {
    "passed": "`passed` is the raw runner envelope's key — the driver consumes {\"result\": "
              "\"pass\"} (or \"fail\"), never a boolean",
    "exitCode": "`exitCode` is the raw runner envelope's key — translate it to a `result` token",
    "status": "`status` is not the driver's key — the driver consumes `result`",
}


def verify_result_fault(artifact):
    """None when a verify artifact carries a RECOGNIZED `result` token; otherwise a reason string."""
    if not isinstance(artifact, dict):
        return ("verify artifact is %s, not a result object; expected {\"result\": \"<one of: %s>\"}"
                "; resubmit the same phase/attempt/state-hash with a corrected artifact" % (
                    type(artifact).__name__, ", ".join(sorted(_VERIFY_RESULTS))))
    if not isinstance(artifact, dict):
        artifact = {}
    result = artifact.get("result")
    if isinstance(result, str) and result in _VERIFY_RESULTS:
        return None
    parts = [
        "verify artifact carries no usable `result` (got %r)" % (result,),
        "expected {\"result\": \"<one of: %s>\"}" % ", ".join(sorted(_VERIFY_RESULTS)),
        "resubmit the same phase/attempt/state-hash with a corrected artifact",
    ]
    hints = [_VERIFY_RUNNER_ENVELOPE_HINTS[k] for k in sorted(_VERIFY_RUNNER_ENVELOPE_HINTS)
             if k in artifact]
    if hints:
        parts.append("; ".join(hints))
    return "; ".join(parts)
