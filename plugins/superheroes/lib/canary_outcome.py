"""Single home for canary probe outcome vocabulary (#1247).

A new outcome member is a fall-open vector: consumers that compare against the old members
silently mis-handle the new one. No module outside this file may name a canary outcome token as
a literal.

Wire contract
-------------

A canary probe result is a mapping with:

**Required** keys:

- ``engine`` (str, non-empty) — adapter refuses a probe without it; the driver routes probes to
  vendors by it.
- ``outcome`` — a member of ``ALL_OUTCOMES``.
- ``engaged`` (bool).
- ``detectedPlant`` (bool).
- ``evidence`` (mapping).
- ``detail`` (str).

**Optional** keys:

- ``model`` (str).
- ``sanitizedView`` (mapping).
"""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from dispatch_outcome import (
    REASON_FORFEIT_ENGAGED_ARTIFACT,
    REASON_FORFEITED,
    REASON_UNRUNNABLE,
    REASON_VACUOUS,
)

OUTCOME_OK = "ok"  # the ONLY pass member
OUTCOME_NOT_ENGAGED = "not-engaged"  # dispatch succeeded; investigation not proven
OUTCOME_PLANT_UNDETECTED = "plant-undetected"  # dispatch succeeded; engaged; plant not named

_DISPATCH_FAILURE_OUTCOMES = frozenset({
    REASON_FORFEITED,
    REASON_VACUOUS,
    REASON_FORFEIT_ENGAGED_ARTIFACT,
    REASON_UNRUNNABLE,
})

PASS_OUTCOMES = frozenset({OUTCOME_OK})
ALL_OUTCOMES = frozenset({
    OUTCOME_OK,
    OUTCOME_NOT_ENGAGED,
    OUTCOME_PLANT_UNDETECTED,
    REASON_FORFEITED,
    REASON_VACUOUS,
    REASON_FORFEIT_ENGAGED_ARTIFACT,
    REASON_UNRUNNABLE,
})
NON_PASS_OUTCOMES = ALL_OUTCOMES - PASS_OUTCOMES

# Repo-relative paths of every module that imports this vocabulary. A module that imports
# ``canary_outcome`` and is not listed here is a census failure, not a warning.
CONSUMERS = frozenset({
    "plugins/superheroes/lib/seat_canary.py",
    "plugins/superheroes/lib/round_driver.py",
    "plugins/superheroes/eval/review_loop_runner.py",
})


def classify(*, dispatch_reason_outcome, engaged, detected_plant):
    """Ordered, total precedence for the producer's outcome decision."""
    if dispatch_reason_outcome in _DISPATCH_FAILURE_OUTCOMES:
        return dispatch_reason_outcome
    if engaged is not True:
        return OUTCOME_NOT_ENGAGED
    # axis: an undetected plant is never ok
    if detected_plant is not True:
        return OUTCOME_PLANT_UNDETECTED
    return OUTCOME_OK


def is_pass(outcome):
    """True only for declared pass members; unknown or missing is not a pass."""
    return outcome in PASS_OUTCOMES


def _probe_fields(probe):
    engaged = probe.get("engaged") if isinstance(probe, dict) else None
    detected_plant = probe.get("detectedPlant") if isinstance(probe, dict) else None
    return engaged, detected_plant


def normalize(probe):
    """Fail-closed ingestion guard; never raises."""
    if not isinstance(probe, dict):
        return OUTCOME_NOT_ENGAGED, "canary-probe-not-a-mapping"

    outcome = probe.get("outcome")
    engaged, detected_plant = _probe_fields(probe)

    if outcome is None:
        derived = classify(
            dispatch_reason_outcome=None, engaged=engaged, detected_plant=detected_plant)
        return derived, "canary-outcome-absent"

    if outcome not in ALL_OUTCOMES:
        derived = classify(
            dispatch_reason_outcome=None, engaged=engaged, detected_plant=detected_plant)
        return derived, "canary-outcome-unknown:%r" % (outcome,)

    if outcome == OUTCOME_OK and (engaged is not True or detected_plant is not True):
        # axis: a caller cannot assert a pass its fields refuse
        derived = classify(
            dispatch_reason_outcome=None, engaged=engaged, detected_plant=detected_plant)
        return derived, "canary-outcome-contradicts-fields"

    return outcome, None
