"""Certification receipt today-fields must match round_driver.build_receipt (#1271 C12 L2-G)."""
import json
import os
import shutil

import pytest
import round_certification as RC
import round_driver as RD

from round_certification_fixtures import (
    PARITY_FIXTURES,
    STATE_FILE,
    parity_multi_round_fix,
    write_session,
)

CERTIFICATION_EXTRA_KEYS = frozenset(
    ("terminalState", "terminalCause", "seats", "disclosures", "provenanceLabels")
)

# The writer's receipt is a superset of the driver's except certificationShape when any
# seat is hand-landed — the writer labels audited-chain, never full-panel-confirmed (#1271).
PARITY_FIELD_EXCEPTIONS = frozenset({"certificationShape"})


def _load_state(session_dir):
    with open(os.path.join(session_dir, STATE_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def _assert_receipt_parity(session_dir):
    assert len(PARITY_FIELD_EXCEPTIONS) == 1
    state = _load_state(session_dir)
    driver_receipt = RD.build_receipt(state, session_dir)
    cert_receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    assert cert_receipt is not None
    assert set(cert_receipt.keys()) >= set(driver_receipt.keys())
    for key in driver_receipt:
        if key in PARITY_FIELD_EXCEPTIONS:
            continue
        assert cert_receipt[key] == driver_receipt[key], "mismatch on key %r" % key
    hand_landed = any(
        s.get("provenance") == RC.PROVENANCE_HAND_LANDED for s in cert_receipt.get("seats") or []
    )
    if hand_landed:
        assert cert_receipt["certificationShape"] == "audited-chain"
    else:
        assert cert_receipt["certificationShape"] == driver_receipt["certificationShape"]
    extra = set(cert_receipt.keys()) - set(driver_receipt.keys())
    assert extra == CERTIFICATION_EXTRA_KEYS, "unexpected extra keys: %s" % sorted(extra)
    ok, reason = RD.validate_receipt(cert_receipt)
    assert ok, reason


def parity_hand_landed_shape(tmp_path):
    """Hand-landed seat forces audited-chain certificationShape on the writer receipt."""
    return write_session(
        tmp_path,
        name="hand-landed",
        state={
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            },
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                }
            },
        },
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": "abc123",
                "provenance": RC.PROVENANCE_HAND_LANDED,
            }
        ],
    )


PARITY_FIXTURES_WITH_HAND_LANDED = PARITY_FIXTURES + (
    ("hand-landed-shape", parity_hand_landed_shape),
)

ROUND_TRIP_FIXTURES = (
    ("converged-single-round", PARITY_FIXTURES[0][1]),
    ("multi-round-fix", parity_multi_round_fix),
    ("hand-landed-shape", parity_hand_landed_shape),
)


@pytest.mark.parametrize(
    "label,builder",
    PARITY_FIXTURES_WITH_HAND_LANDED,
    ids=[label for label, _ in PARITY_FIXTURES_WITH_HAND_LANDED],
)
def test_certification_receipt_matches_driver_today_fields(tmp_path, label, builder):
    session_dir = builder(tmp_path)
    _assert_receipt_parity(session_dir)


@pytest.mark.parametrize(
    "label,builder",
    ROUND_TRIP_FIXTURES,
    ids=[label for label, _ in ROUND_TRIP_FIXTURES],
)
def test_materialized_state_round_trip_matches_driver_receipt(tmp_path, label, builder):
    session_dir = builder(tmp_path)
    state = _load_state(session_dir)
    materialized = RD._materialize_run_loop_session(state, 0, source_session_dir=session_dir)
    try:
        cert_receipt, refusal = RC.certify(materialized)
        assert refusal is None, refusal
        driver_receipt = RD.build_receipt(state, session_dir)
        assert set(cert_receipt.keys()) >= set(driver_receipt.keys())
        for key in driver_receipt:
            if key in PARITY_FIELD_EXCEPTIONS:
                continue
            assert cert_receipt[key] == driver_receipt[key], "mismatch on key %r" % key
        hand_landed = any(
            s.get("provenance") == RC.PROVENANCE_HAND_LANDED
            for s in cert_receipt.get("seats") or []
        )
        if hand_landed:
            assert cert_receipt["certificationShape"] == "audited-chain"
        else:
            assert cert_receipt["certificationShape"] == driver_receipt["certificationShape"]
    finally:
        shutil.rmtree(materialized, ignore_errors=True)
