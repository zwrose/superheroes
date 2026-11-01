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
P_SEAMS = "dispatch-seams-check"
P_SECOND_TEST = "dispatch-second-test"
P_SWEEP = "dispatch-sweep"
P_VERIFY = "run-verify"
P_APPLY_FIXES = "apply-fixes"
P_TERMINAL = "terminal"

# Default cap on findings one apply-fixes step carries.
FIX_BATCH_CAP_DEFAULT = 4

# The round cap: a review session never begins a round after it, and no session this driver mints
# carries a larger one. The only home of the number.
ROUND_CAP = 4

ALL_PHASES = (
    P_PANEL, P_VERIFIERS, P_SYNTHESIS, P_AUDITS, P_SCOPED, P_SEAMS, P_VERIFY, P_APPLY_FIXES,
    P_TERMINAL, P_SECOND_TEST, P_SWEEP,
)

# The repository-sweep search is cut into at most this many size-balanced parts of the tracked files;
# one searcher seat reads each part.
SWEEP_PARTS = 4

# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only (doc
# provenance) — deliberately absent here; test_dispatch_tables pins the per-leg subset.
DIMENSIONS = list(round_panel_contract.DEFAULT_PANEL_DIMENSIONS)

# Per-finding verification verdicts — lives here so the payload-contract layer can cite it
# without importing `verification`; `verification.VERDICTS` re-exports this tuple.
VERDICTS = ("CONFIRMED", "PLAUSIBLE", "REFUTED")


def panel_dimensions(config):
    """Configured panel dimensions, or the default DIMENSIONS list."""
    return round_panel_contract.panel_dimensions_from_config(config)


def seat_lens(key):
    """The lens of a panel seat key: the key itself, or the part before the first ':' of a slice seat key whose lens is a dimension."""
    if isinstance(key, str) and ":" in key:
        lens = key.split(":", 1)[0]
        if lens in DIMENSIONS:
            return lens
    return key


# The lenses a sliced round 1 seats once per slice; every other lens stays one seat over the whole change.
SLICED_LENSES = ("code-reviewer", "test-role", "security-reviewer")


def panel_roster(state, config):
    """The panel's seat keys: the configured dimensions, except that a sliced round 1 seats the whole-change lenses once
    and each slice's own code, test and (when the slice carries one) security seat."""
    dims = list(panel_dimensions(config))
    plan = state.get("slicePlan") if isinstance(state, dict) else None
    rnd = state.get("round") if isinstance(state, dict) else None
    # axis: only a round-1 plan that says it was sliced and lists slices changes the roster; anything else keeps the configured dimensions
    if not (isinstance(plan, dict) and plan.get("sliced") is True) or (isinstance(rnd, int) and rnd > 1):
        return dims
    # axis: while a later unread wave is open the panel seats only that wave's seats, never the first wave's again
    wave = state.get("_sliceWave")
    wave_roster = state.get("_sliceWaveRoster")
    if (isinstance(wave, int) and not isinstance(wave, bool) and wave > 1 and isinstance(wave_roster, list)
            and wave_roster and all(isinstance(k, str) and k for k in wave_roster)):
        return list(wave_roster)
    slices = plan.get("slices")
    # axis: a slice cut for a later unread wave carries a `wave` mark and is seated only by that wave's roster, never by the first wave's
    slices = [s for s in slices if isinstance(s, dict) and isinstance(s.get("id"), str) and s["id"]
              and "wave" not in s] if isinstance(slices, list) else []
    if not slices:
        return dims
    roster = [d for d in dims if d not in SLICED_LENSES]
    for sl in slices:
        if "code-reviewer" in dims:
            roster.append("code-reviewer:" + sl["id"])
        if "test-role" in dims:
            roster.append("test-role:" + sl["id"])
        # axis: a slice seats the security lens only when its plan row says it touches a risk area (a row with no `security` key reads as not touching)
        if "security-reviewer" in dims and sl.get("security") is True:
            roster.append("security-reviewer:" + sl["id"])
    return roster


# The lens whose later-wave seat reads the whole change rather than a slice.
WAVE_WHOLE_LENS = "premortem-reviewer"


def is_slice_seat(key):
    """True for a seat key `<lens>:<slice id>` of a slice seat; the premortem's whole-change wave seat is not one."""
    return seat_lens(key) != key and seat_lens(key) != WAVE_WHOLE_LENS


def wave_roster(dims, new_slices, with_whole):
    """The seats of one later unread wave: each new slice's own code, test and (when its `security` is true) security seat, then,
    when ``with_whole``, the one whole-change premortem seat of that wave (`premortem-reviewer:<wave id>`, the wave id being the
    first part of the slices' ids before `u`)."""
    roster = []
    wave_id = ""
    for sl in new_slices:
        wave_id = wave_id or sl["id"].partition("u")[0]
        if "code-reviewer" in dims:
            roster.append("code-reviewer:" + sl["id"])
        if "test-role" in dims:
            roster.append("test-role:" + sl["id"])
        if "security-reviewer" in dims and sl.get("security") is True:
            roster.append("security-reviewer:" + sl["id"])
    if with_whole and wave_id and WAVE_WHOLE_LENS in dims:
        roster.append("%s:%s" % (WAVE_WHOLE_LENS, wave_id))
    return roster


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
