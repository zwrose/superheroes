"""Tests for pilot_attended.py — attended seeding plans and verify-at-seed."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_attended as pa  # noqa: E402
import pilot_identity as pi  # noqa: E402
import pilot_probe  # noqa: E402
import pilot_seed as ps  # noqa: E402

SLOT = "slot-a"
GENERATION = 1
SLOT_REF = "slot-a@1"
EXPECTED_ID = "pilot-owner@example.test"
OWNER_PERSONAL_ID = "owner-personal@example.test"
OTHER_PILOT_ID = "pilot-viewer@example.test"

ACCOUNTS = [
    {"account": "owner", "role": "resource-owner"},
    {"account": "viewer", "role": "viewer"},
]

THREE_ACCOUNTS = [
    {"account": "alpha", "role": "resource-owner"},
    {"account": "beta", "role": "viewer"},
    {"account": "gamma", "role": "viewer"},
]


def _expected_identities(**overrides):
    base = {
        "owner": EXPECTED_ID,
        "viewer": OTHER_PILOT_ID,
    }
    base.update(overrides)
    return base


def _plan(**kwargs):
    defaults = {
        "slot": SLOT,
        "generation": GENERATION,
        "accounts": ACCOUNTS,
        "attended_declaration": {"vehicle": "automation"},
        "capture_surfaces": ["cookies"],
        "expected_identities": _expected_identities(),
    }
    defaults.update(kwargs)
    return pa.attended_seeding_plan(**defaults)


def _verified_result(identity=EXPECTED_ID):
    return {
        "ok": True,
        "outcome": pa.OUTCOME_VERIFIED,
        "reason": None,
        "identity": identity,
    }


# --- seeding_vehicle ----------------------------------------------------------

def test_seeding_vehicle_defaults_to_automation():
    assert pa.seeding_vehicle({"vehicle": "automation"}, idp_rejects_automation=False) == "automation"


def test_seeding_vehicle_edge3_automation_with_idp_rejects_escalates_to_real_chrome():
    """Edge 3: automation + idp_rejects_automation=True → real-chrome."""
    assert pa.seeding_vehicle({"vehicle": "automation"}, idp_rejects_automation=True) == "real-chrome"


def test_seeding_vehicle_edge4_real_chrome_stays_real_chrome():
    """Edge 4: real-chrome + idp_rejects_automation=False → real-chrome."""
    assert pa.seeding_vehicle({"vehicle": "real-chrome"}, idp_rejects_automation=False) == "real-chrome"


def test_seeding_vehicle_edge1_not_dict_refused():
    """Edge 1: attended_declaration not a dict → attended-vehicle-invalid."""
    result = pa.seeding_vehicle("automation", idp_rejects_automation=False)
    assert result == {"ok": False, "reason": pa.REFUSAL_VEHICLE_INVALID}


def test_seeding_vehicle_edge1_missing_vehicle_refused():
    """Edge 1: missing vehicle → attended-vehicle-invalid."""
    result = pa.seeding_vehicle({}, idp_rejects_automation=False)
    assert result == {"ok": False, "reason": pa.REFUSAL_VEHICLE_INVALID}


def test_seeding_vehicle_edge1_unknown_vehicle_refused():
    """Edge 1: unknown vehicle → attended-vehicle-invalid."""
    result = pa.seeding_vehicle({"vehicle": "firefox"}, idp_rejects_automation=False)
    assert result == {"ok": False, "reason": pa.REFUSAL_VEHICLE_INVALID}


def test_seeding_vehicle_edge2_idp_rejects_not_bool_refused():
    """Edge 2: idp_rejects_automation not a real bool → attended-vehicle-invalid."""
    for bad in (1, "yes", None):
        result = pa.seeding_vehicle({"vehicle": "automation"}, idp_rejects_automation=bad)
        assert result == {"ok": False, "reason": pa.REFUSAL_VEHICLE_INVALID}


# --- attended_seeding_plan ----------------------------------------------------

def test_attended_seeding_plan_ok():
    result = _plan()
    assert result["ok"] is True
    assert result["slotRef"] == SLOT_REF
    assert result["vehicle"] == "automation"
    assert len(result["steps"]) == 2
    assert result["steps"][0]["account"] == "owner"
    assert result["steps"][0]["slotRef"] == SLOT_REF
    assert result["steps"][0]["vehicle"] == "automation"
    assert result["steps"][0]["contextOptions"] == {
        "indexedDB": False,
        "credentials": False,
    }
    assert result["steps"][0]["expectedIdentity"] == EXPECTED_ID
    assert SLOT_REF in result["steps"][0]["prompt"]
    assert "owner" in result["steps"][0]["prompt"]
    assert EXPECTED_ID in result["steps"][0]["prompt"]


def test_attended_seeding_plan_edge5_empty_account_set_refused():
    """Edge 5: empty account set → attended-account-set-empty."""
    result = _plan(accounts=[])
    assert result == {"ok": False, "reason": pa.REFUSAL_ACCOUNT_SET_EMPTY}


def test_attended_seeding_plan_edge6_missing_expected_identity_refused():
    """Edge 6: expected_identities missing an account → attended-account-set-mismatch."""
    result = _plan(expected_identities={"owner": EXPECTED_ID})
    assert result == {"ok": False, "reason": pa.REFUSAL_ACCOUNT_SET_MISMATCH}


def test_attended_seeding_plan_edge7_extra_expected_identity_refused():
    """Edge 7: expected_identities with extra key → attended-account-set-mismatch."""
    identities = _expected_identities()
    identities["extra"] = "extra@example.test"
    result = _plan(expected_identities=identities)
    assert result == {"ok": False, "reason": pa.REFUSAL_ACCOUNT_SET_MISMATCH}


def test_attended_seeding_plan_edge8_none_expected_identity_refused():
    """Edge 8: expected identity None → attended-expected-identity-missing."""
    result = _plan(expected_identities=_expected_identities(owner=None))
    assert result == {"ok": False, "reason": pa.REFUSAL_EXPECTED_IDENTITY_MISSING}


def test_attended_seeding_plan_edge9_empty_expected_identity_refused():
    """Edge 9: empty expected identity → attended-expected-identity-invalid."""
    result = _plan(expected_identities=_expected_identities(owner=""))
    assert result == {"ok": False, "reason": pa.REFUSAL_EXPECTED_IDENTITY_INVALID}


def test_attended_seeding_plan_edge9_non_string_expected_identity_refused():
    """Edge 9: non-string expected identity → attended-expected-identity-invalid."""
    result = _plan(expected_identities=_expected_identities(owner=123))
    assert result == {"ok": False, "reason": pa.REFUSAL_EXPECTED_IDENTITY_INVALID}


def test_attended_seeding_plan_edge10_session_storage_refused_verbatim():
    """Edge 10: sessionStorage → pilot_seed refusal verbatim."""
    result = _plan(capture_surfaces=["sessionStorage"])
    assert result == {"ok": False, "reason": ps.REFUSAL_SESSION_STORAGE}


def test_attended_seeding_plan_edge10_empty_capture_surfaces_refused_verbatim():
    """Edge 10: empty capture_surfaces → pilot_seed refusal verbatim."""
    result = _plan(capture_surfaces=[])
    assert result == {"ok": False, "reason": ps.REFUSAL_SURFACES_EMPTY}


def test_attended_seeding_plan_edge10_invalid_capture_surfaces_refused_verbatim():
    """Edge 10: invalid capture_surfaces → pilot_seed refusal verbatim."""
    result = _plan(capture_surfaces="cookies")
    assert result == {"ok": False, "reason": ps.REFUSAL_SURFACES_INVALID}


def test_attended_seeding_plan_edge11_invalid_slot_refused():
    """Edge 11: invalid slot → attended-slot-ref-invalid."""
    result = _plan(slot="")
    assert result == {"ok": False, "reason": pa.REFUSAL_SLOT_REF_INVALID}


def test_attended_seeding_plan_edge11_invalid_generation_refused():
    """Edge 11: invalid generation → attended-slot-ref-invalid."""
    result = _plan(generation=0)
    assert result == {"ok": False, "reason": pa.REFUSAL_SLOT_REF_INVALID}


def test_attended_seeding_plan_duplicate_account_refused_context_reused():
    result = _plan(accounts=[
        {"account": "owner", "role": "resource-owner"},
        {"account": "owner", "role": "viewer"},
    ])
    assert result == {"ok": False, "reason": pa.REFUSAL_CONTEXT_REUSED}


def test_attended_seeding_plan_invalid_account_entry_refused():
    result = _plan(accounts=[{"account": "", "role": "resource-owner"}])
    assert result == {"ok": False, "reason": pa.REFUSAL_ACCOUNT_INVALID}


def test_attended_seeding_plan_real_chrome_prompt_mentions_chrome():
    result = _plan(attended_declaration={"vehicle": "real-chrome"})
    assert result["vehicle"] == "real-chrome"
    assert "Chrome" in result["steps"][0]["prompt"]


def test_prompt_copy_no_jargon():
    text = pa.prompt_copy(SLOT_REF, "owner", EXPECTED_ID, "automation")
    for forbidden in ("slotRef", "verify-at-seed", "provenance"):
        assert forbidden not in text


# --- verify_at_seed -----------------------------------------------------------

def test_verify_at_seed_ok():
    result = pa.verify_at_seed(
        {"identity": EXPECTED_ID},
        expected_identity=EXPECTED_ID,
    )
    assert result == _verified_result()


def test_verify_at_seed_edge12_owner_personal_account_refused():
    """Edge 12: owner's own (different valid) identity → attended-identity-mismatch."""
    result = pa.verify_at_seed(
        {"identity": OWNER_PERSONAL_ID},
        expected_identity=EXPECTED_ID,
    )
    assert result == {
        "ok": False,
        "outcome": pa.OUTCOME_REFUSED,
        "reason": pa.REFUSAL_IDENTITY_MISMATCH,
        "identity": OWNER_PERSONAL_ID,
    }


def test_verify_at_seed_edge13_no_session_refused():
    """Edge 13: identity None with no-session → attended-identity-absent."""
    result = pa.verify_at_seed(
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result == {
        "ok": False,
        "outcome": pa.OUTCOME_REFUSED,
        "reason": pa.REFUSAL_IDENTITY_ABSENT,
        "identity": None,
    }


def test_verify_at_seed_edge14_not_dict_refused():
    """Edge 14: malformed answer (not dict) → attended-answer-invalid."""
    result = pa.verify_at_seed("bogus", expected_identity=EXPECTED_ID)
    assert result["reason"] == pa.REFUSAL_ANSWER_INVALID


def test_verify_at_seed_edge14_unknown_reason_refused():
    """Edge 14: unknown reason token → attended-answer-invalid."""
    result = pa.verify_at_seed({"reason": "bogus"}, expected_identity=EXPECTED_ID)
    assert result["reason"] == pa.REFUSAL_ANSWER_INVALID


def test_verify_at_seed_edge14_both_fields_refused():
    """Edge 14: both identity and reason set → attended-answer-invalid."""
    result = pa.verify_at_seed(
        {"identity": EXPECTED_ID, "reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result["reason"] == pa.REFUSAL_ANSWER_INVALID


def test_verify_at_seed_edge14_neither_field_refused():
    """Edge 14: neither field set → attended-answer-invalid."""
    result = pa.verify_at_seed({}, expected_identity=EXPECTED_ID)
    assert result["reason"] == pa.REFUSAL_ANSWER_INVALID


def test_verify_at_seed_edge15_empty_expected_identity_raises():
    """Edge 15: empty expected_identity → raises attended-expected-identity-invalid."""
    with pytest.raises(pa.PilotAttendedError) as exc:
        pa.verify_at_seed({"identity": EXPECTED_ID}, expected_identity="")
    assert exc.value.reason == pa.REFUSAL_EXPECTED_IDENTITY_INVALID


def test_verify_at_seed_edge15_non_string_expected_identity_raises():
    with pytest.raises(pa.PilotAttendedError) as exc:
        pa.verify_at_seed({"identity": EXPECTED_ID}, expected_identity=42)
    assert exc.value.reason == pa.REFUSAL_EXPECTED_IDENTITY_INVALID


# --- seed_outcome -------------------------------------------------------------

def test_seed_outcome_all_verified():
    steps = [
        {"account": "owner"},
        {"account": "viewer"},
    ]
    results = {
        "owner": _verified_result(EXPECTED_ID),
        "viewer": _verified_result(OTHER_PILOT_ID),
    }
    result = pa.seed_outcome(steps, results)
    assert result == {
        "ok": True,
        "outcome": pa.OUTCOME_VERIFIED,
        "reason": None,
        "accounts": ["owner", "viewer"],
    }


def test_seed_outcome_edge16_missing_result_refused():
    """Edge 16: missing result for planned account → attended-seed-incomplete."""
    steps = [{"account": "owner"}, {"account": "viewer"}]
    results = {"owner": _verified_result()}
    result = pa.seed_outcome(steps, results)
    assert result == {"ok": False, "reason": pa.REFUSAL_SEED_INCOMPLETE}


def test_seed_outcome_edge17_extra_result_refused():
    """Edge 17: extra result for unplanned account → attended-seed-incomplete."""
    steps = [{"account": "owner"}]
    results = {
        "owner": _verified_result(),
        "viewer": _verified_result(OTHER_PILOT_ID),
    }
    result = pa.seed_outcome(steps, results)
    assert result == {"ok": False, "reason": pa.REFUSAL_SEED_INCOMPLETE}


def test_seed_outcome_edge18_one_of_three_refused():
    """Edge 18: one of three accounts refused → whole slot refuses."""
    steps = [{"account": a} for a in ("alpha", "beta", "gamma")]
    results = {
        "alpha": _verified_result("alpha@example.test"),
        "beta": {
            "ok": False,
            "outcome": pa.OUTCOME_REFUSED,
            "reason": pa.REFUSAL_IDENTITY_MISMATCH,
            "identity": OWNER_PERSONAL_ID,
        },
        "gamma": _verified_result("gamma@example.test"),
    }
    result = pa.seed_outcome(steps, results)
    assert result == {
        "ok": False,
        "outcome": pa.OUTCOME_REFUSED,
        "reason": pa.REFUSAL_IDENTITY_MISMATCH,
        "account": "beta",
    }


# --- lapse_disposition --------------------------------------------------------

def test_lapse_disposition_edge19_first_no_session_reprobes():
    """Edge 19: first no-session → reprobe, not park."""
    result = pa.lapse_disposition(
        {"reason": pilot_probe.REASON_NO_SESSION},
        reprobe_count=0,
    )
    assert result["action"] == pi.ACTION_REPROBE
    assert result["outcome"] != pa.OUTCOME_PARKED


def test_lapse_disposition_edge20_confirmed_no_session_parks():
    """Edge 20: confirmed no-session → park, never remint."""
    result = pa.lapse_disposition(
        {"reason": pilot_probe.REASON_NO_SESSION},
        reprobe_count=1,
    )
    assert result == {
        "outcome": pa.OUTCOME_PARKED,
        "action": pi.ACTION_PARK,
        "reason": pilot_probe.REASON_NO_SESSION,
    }


def test_lapse_disposition_edge21_infrastructure_defers():
    """Edge 21: infrastructure token → defer, never park."""
    result = pa.lapse_disposition(
        {"reason": pilot_probe.REASON_TRANSPORT_ERROR},
        reprobe_count=0,
    )
    assert result["action"] == pi.ACTION_DEFER
    assert result["outcome"] != pa.OUTCOME_PARKED
