#!/usr/bin/env python3
"""Shared phase-name constants and cycle-free helpers for the round driver and its record/adapter
layers (#723).

Single home for the `P_*` action strings so `round_driver`, `round_adapters`, and
`round_records` agree without import cycles. Stdlib-only."""
import round_panel_contract

# Phases (the `action` a `next` emits; each is fulfilled by exactly one orchestrator dispatch).
P_PANEL = "dispatch-panel"
P_VERIFIERS = "dispatch-verifiers"
P_SYNTHESIS = "dispatch-synthesis"
P_AUDITS = "dispatch-audits"
P_SCOPED = round_panel_contract.P_SCOPED_FINDER_PHASE
P_GAPSWEEP = "dispatch-gap-sweep"
P_VERIFY = "run-verify"
P_FIXER = "dispatch-fixer"
P_TERMINAL = "terminal"

# Default cap on findings per dispatch-fixer order (#1272 round economy).
FIX_BATCH_CAP_DEFAULT = 4

ALL_PHASES = (
    P_PANEL, P_VERIFIERS, P_SYNTHESIS, P_AUDITS, P_SCOPED, P_GAPSWEEP, P_VERIFY, P_FIXER,
    P_TERMINAL,
)

# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only (doc
# provenance) — deliberately absent here; test_dispatch_tables pins the per-leg subset.
DIMENSIONS = list(round_panel_contract.DEFAULT_PANEL_DIMENSIONS)

# Owner-gate vocabulary the retired gates used. The round driver reads none of it: no phase presents
# anything to the owner. Kept ONLY because `review_gate_policy` (the gate-policy calibration library,
# retired by a follow-up) derives its rule vocabulary from these names at import.
ONE_MORE_ROUND_CHOICE = "one-more-round"
ACCEPT_RISK_CHOICE = "accept-the-disclosed-risk"
HOLD_CHOICE = "hold"
STALL_CHOICES = (ONE_MORE_ROUND_CHOICE, ACCEPT_RISK_CHOICE, HOLD_CHOICE)
RETIRED_STALL_CHOICES = ("ship-smaller", "spend-more")
RETIRED_STALL_CHOICE_PREFIX = "stall-choice-retired:"
JUDGMENT_DISPOSITIONS = ("fix-as-suggested", "fix-with-guidance", "skip")

# Per-finding verification verdicts — lives here so the payload-contract layer can cite it
# without importing `verification`; `verification.VERDICTS` re-exports this tuple.
VERDICTS = ("CONFIRMED", "PLAUSIBLE", "REFUTED")


def panel_dimensions(config):
    """Configured panel dimensions, or the default DIMENSIONS list."""
    return round_panel_contract.panel_dimensions_from_config(config)


# Verify submit-shape guard — lives here so `round_adapters` never imports `round_driver`.
_VERIFY_RESULTS = ("pass", "fail", "timeout", "skipped", "none", "unverified")

_VERIFY_RUNNER_ENVELOPE_HINTS = {
    "passed": "`passed` is the raw runner envelope's key — the driver consumes {\"result\": "
              "\"pass\"} (or \"fail\"), never a boolean",
    "exitCode": "`exitCode` is the raw runner envelope's key — translate it to a `result` token",
    "status": "`status` is not the driver's key — the driver consumes `result`",
}


_VERIFY_VIA = ("local", "ci-exact-head")
_HEX = frozenset("0123456789abcdefABCDEF")


def _ci_verify_shape_fault(artifact):
    """None unless `via`/`ci`/`reason` are malformed; a `ci-exact-head` claim carries a passing result,
    a CI run identity and the reason the local verify command could not run. No evidence rides a local verify."""
    via = artifact.get("via")
    if "via" not in artifact:
        extra = [k for k in ("ci", "reason") if k in artifact]
        return ("ci-verify-shape: `%s` present without `via: \"ci-exact-head\"` — no evidence rides a "
                "local verify" % "`/`".join(extra)) if extra else None
    # axis: the ci-exact-head shape is refused before any fetch — see bite-proof record wo_b_2072_ci_verify
    if not isinstance(via, str) or via not in _VERIFY_VIA:
        return "ci-verify-shape: `via` is %r, not one of: %s" % (via, ", ".join(_VERIFY_VIA))
    if via == "local":
        extra = [k for k in ("ci", "reason") if k in artifact]
        return ("ci-verify-shape: `%s` present on a local verify — no evidence rides a local verify"
                % "`/`".join(extra)) if extra else None
    if artifact.get("result") != "pass":
        return "ci-verify-shape: a ci-exact-head verify stands in only for a pass (got result %r)" % (
            artifact.get("result"),)
    ci = artifact.get("ci")
    if not isinstance(ci, dict):
        return "ci-verify-shape: `ci` is %s, not an object" % type(ci).__name__
    for field in ("workflow", "conclusion"):
        value = ci.get(field)
        if not (isinstance(value, str) and value.strip()):
            return "ci-verify-shape: `ci.%s` is %r, not a non-empty string" % (field, value)
    run_id = ci.get("runId")
    if isinstance(run_id, bool) or not (
            (isinstance(run_id, int) and run_id > 0)
            or (isinstance(run_id, str) and run_id.isascii() and run_id.isdigit() and int(run_id) > 0)):
        return "ci-verify-shape: `ci.runId` is %r, not a positive integer or digit string" % (run_id,)
    head = ci.get("headSha")
    if not (isinstance(head, str) and len(head) in (40, 64) and all(c in _HEX for c in head)):
        return "ci-verify-shape: `ci.headSha` is %r, not a 40- or 64-hex commit sha" % (head,)
    reason = artifact.get("reason")
    if not (isinstance(reason, str) and reason.strip()):
        return "ci-verify-shape: `reason` is %r, not a non-empty string naming why the local verify cannot run" % (
            reason,)
    return None


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
        return _ci_verify_shape_fault(artifact)
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
