"""Tests for pilot_identity.py — identity-probe exercise and lapse episode."""
import inspect
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_contract  # noqa: E402
import pilot_identity as pi  # noqa: E402
import pilot_probe  # noqa: E402
import pilot_slot  # noqa: E402

EXPECTED_ID = "owner@example.test"
OTHER_ID = "other@example.test"
SLOT_REF = "slot-a@1"
POLICY_DIGEST = "abcd1234ef567890"

HOSTILE_VALUES = [
    None,
    [],
    {},
    set(),
    0,
    True,
    "",
    b"x",
    object(),
    [[]],
    {"k": set()},
]


def _slot_accounts(accounts=None):
    if accounts is None:
        accounts = [
            {"account": "owner", "role": "resource-owner"},
            {"account": "viewer", "role": "viewer"},
        ]
    return pilot_slot.slot_account_set("slot-a", 1, accounts)


def _passing_pair_answers():
    return {
        "owner": {
            "seeded": {"identity": EXPECTED_ID},
            "unseeded": {"reason": pilot_probe.REASON_NO_SESSION},
        },
        "viewer": {
            "seeded": {"identity": "viewer@example.test"},
            "unseeded": {"reason": pilot_probe.REASON_NO_SESSION},
        },
    }


def _expected_identities():
    return {
        "owner": EXPECTED_ID,
        "viewer": "viewer@example.test",
    }


# --- probe_answer -------------------------------------------------------------

def test_probe_answer_identity():
    result = pi.probe_answer(identity=EXPECTED_ID)
    assert result == {"identity": EXPECTED_ID, "reason": None}


def test_probe_answer_reason():
    result = pi.probe_answer(reason=pilot_probe.REASON_NO_SESSION)
    assert result == {"identity": None, "reason": pilot_probe.REASON_NO_SESSION}


def test_probe_answer_both_fields_refused():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.probe_answer(identity=EXPECTED_ID, reason=pilot_probe.REASON_NO_SESSION)
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ANSWER_INVALID


def test_probe_answer_neither_field_refused():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.probe_answer()
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ANSWER_INVALID


def test_probe_answer_empty_identity_refused():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.probe_answer(identity="")
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ANSWER_INVALID


def test_probe_answer_unknown_reason_refused():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.probe_answer(reason="bogus-token")
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ANSWER_REASON_UNKNOWN


# --- evaluate_pair success ----------------------------------------------------

def test_evaluate_pair_ok():
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result == {"ok": True, "reason": None, "detail": None}


# --- edge 1: identical before other refusals ----------------------------------

def test_evaluate_pair_identical_before_seeded_refused():
    """Edge 1: identical-answer check runs before seeded-refused."""
    result = pi.evaluate_pair(
        {"reason": pilot_probe.REASON_NO_SESSION},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_ANSWERS_IDENTICAL


def test_evaluate_pair_identical_before_seeded_mismatch():
    """Edge 1: identical correct identity before mismatch path."""
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID},
        {"identity": EXPECTED_ID},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_ANSWERS_IDENTICAL


# --- edge 2: both no-session => identical -------------------------------------

def test_evaluate_pair_both_no_session_identical():
    """Edge 2: both no-session => identical, not unseeded-not-no-session."""
    result = pi.evaluate_pair(
        {"reason": pilot_probe.REASON_NO_SESSION},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_ANSWERS_IDENTICAL
    assert result["reason"] != pi.REFUSAL_IDENTITY_PROBE_UNSEEDED_NOT_NO_SESSION


# --- edge 3: same correct identity => identical --------------------------------

def test_evaluate_pair_same_correct_identity_identical():
    """Edge 3: same correct identity => identical, not ok."""
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID},
        {"identity": EXPECTED_ID},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_ANSWERS_IDENTICAL


# --- edge 4: unseeded identity refuses ----------------------------------------

def test_evaluate_pair_unseeded_identity_refused():
    """Edge 4: unseeded returning identity refuses."""
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID},
        {"identity": OTHER_ID},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_UNSEEDED_NOT_NO_SESSION


# --- edge 5: unseeded infrastructure refuses ----------------------------------

def test_evaluate_pair_unseeded_infrastructure_refused():
    """Edge 5: unseeded infrastructure token refuses."""
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID},
        {"reason": pilot_probe.REASON_TRANSPORT_ERROR},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_UNSEEDED_NOT_NO_SESSION


def test_evaluate_pair_seeded_refused():
    result = pi.evaluate_pair(
        {"reason": pilot_probe.REASON_WRONG_IDENTITY},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_SEEDED_REFUSED
    assert result["detail"] == pilot_probe.REASON_WRONG_IDENTITY


def test_evaluate_pair_seeded_mismatch():
    result = pi.evaluate_pair(
        {"identity": OTHER_ID},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_SEEDED_IDENTITY_MISMATCH


def test_evaluate_pair_expected_missing():
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity="",
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_EXPECTED_MISSING


def test_evaluate_pair_invalid_answer():
    result = pi.evaluate_pair(
        {"identity": EXPECTED_ID, "reason": pilot_probe.REASON_NO_SESSION},
        {"reason": pilot_probe.REASON_NO_SESSION},
        expected_identity=EXPECTED_ID,
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_ANSWER_INVALID


# --- run_pair_exercise --------------------------------------------------------

def test_run_pair_exercise_ok():
    result = pi.run_pair_exercise(
        expected_identity=EXPECTED_ID,
        seeded_probe=lambda: {"identity": EXPECTED_ID},
        unseeded_probe=lambda: {"reason": pilot_probe.REASON_NO_SESSION},
    )
    assert result["ok"] is True


# --- edge 6: same callable refuses --------------------------------------------

def test_run_pair_exercise_same_callable_refused():
    """Edge 6: same callable for both legs => legs-not-distinct."""
    probe = lambda: {"identity": EXPECTED_ID}
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.run_pair_exercise(
            expected_identity=EXPECTED_ID,
            seeded_probe=probe,
            unseeded_probe=probe,
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_PROBE_LEGS_NOT_DISTINCT


# --- edge 7: each probe called exactly once -----------------------------------

def test_run_pair_exercise_each_probe_once():
    """Edge 7: each probe called exactly once."""
    seeded_count = 0
    unseeded_count = 0

    def seeded():
        nonlocal seeded_count
        seeded_count += 1
        return {"identity": EXPECTED_ID}

    def unseeded():
        nonlocal unseeded_count
        unseeded_count += 1
        return {"reason": pilot_probe.REASON_NO_SESSION}

    pi.run_pair_exercise(
        expected_identity=EXPECTED_ID,
        seeded_probe=seeded,
        unseeded_probe=unseeded,
    )
    assert seeded_count == 1
    assert unseeded_count == 1


# --- edge 8: raising probe ----------------------------------------------------

def test_run_pair_exercise_raising_probe():
    """Edge 8: raising probe => leg-failed, exception does not escape."""
    def bad():
        raise RuntimeError("transport down")

    result = pi.run_pair_exercise(
        expected_identity=EXPECTED_ID,
        seeded_probe=bad,
        unseeded_probe=lambda: {"reason": pilot_probe.REASON_NO_SESSION},
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_LEG_FAILED
    assert result["detail"] == "seeded"


def test_run_pair_exercise_not_callable():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.run_pair_exercise(
            expected_identity=EXPECTED_ID,
            seeded_probe=None,
            unseeded_probe=lambda: {"reason": pilot_probe.REASON_NO_SESSION},
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_PROBE_NOT_CALLABLE


# --- evaluate_slot ------------------------------------------------------------

def test_evaluate_slot_ok():
    slot_accounts = _slot_accounts()
    result = pi.evaluate_slot(
        slot_accounts,
        _expected_identities(),
        _passing_pair_answers(),
    )
    assert result["ok"] is True
    assert all(account_result["ok"] for account_result in result["accounts"].values())


# --- edge 9: one failing account ----------------------------------------------

def test_evaluate_slot_one_failing_account():
    """Edge 9: one failing account => overall ok False."""
    slot_accounts = _slot_accounts()
    answers = _passing_pair_answers()
    answers["viewer"]["unseeded"] = {"identity": OTHER_ID}
    result = pi.evaluate_slot(slot_accounts, _expected_identities(), answers)
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_UNSEEDED_NOT_NO_SESSION


# --- edge 10: key-set mismatch both directions --------------------------------

def test_evaluate_slot_missing_account_in_answers():
    """Edge 10: account missing from answers."""
    slot_accounts = _slot_accounts()
    answers = _passing_pair_answers()
    del answers["viewer"]
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_slot(slot_accounts, _expected_identities(), answers)
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH
    assert "missing from answers" in exc.value.detail


def test_evaluate_slot_extra_account_in_answers():
    """Edge 10: extra account in answers."""
    slot_accounts = _slot_accounts()
    answers = _passing_pair_answers()
    answers["extra"] = {
        "seeded": {"identity": "x@example.test"},
        "unseeded": {"reason": pilot_probe.REASON_NO_SESSION},
    }
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_slot(slot_accounts, _expected_identities(), answers)
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH
    assert "extra in answers" in exc.value.detail


def test_evaluate_slot_empty_accounts():
    accounts = [{"account": "owner", "role": "resource-owner"}]
    slot_accounts = pilot_slot.slot_account_set("slot-a", 1, accounts)
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_slot(
            {"slot": "slot-a", "generation": 1, "ref": "slot-a@1", "accounts": []},
            {"owner": EXPECTED_ID},
            {"owner": {"seeded": {"identity": EXPECTED_ID}, "unseeded": {"reason": pilot_probe.REASON_NO_SESSION}}},
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_ACCOUNT_SET_EMPTY


def test_evaluate_slot_missing_leg():
    slot_accounts = _slot_accounts([{"account": "owner", "role": "resource-owner"}])
    result = pi.evaluate_slot(
        slot_accounts,
        {"owner": EXPECTED_ID},
        {"owner": {"seeded": {"identity": EXPECTED_ID}}},
    )
    assert result["ok"] is False
    assert result["reason"] == pi.REFUSAL_IDENTITY_ANSWER_INVALID


# --- evaluate_wrong_account_leg -----------------------------------------------

def test_wrong_account_leg_wrong_identity_token():
    result = pi.evaluate_wrong_account_leg(
        {"reason": pilot_probe.REASON_WRONG_IDENTITY},
        expected_identity=EXPECTED_ID,
        other_identity=OTHER_ID,
    )
    assert result["ok"] is True


def test_wrong_account_leg_other_identity():
    result = pi.evaluate_wrong_account_leg(
        {"identity": OTHER_ID},
        expected_identity=EXPECTED_ID,
        other_identity=OTHER_ID,
    )
    assert result["ok"] is True


# --- edge 11: vacuous -----------------------------------------------------------

def test_wrong_account_leg_vacuous():
    """Edge 11: other_identity == expected_identity => vacuous."""
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_wrong_account_leg(
            {"identity": EXPECTED_ID},
            expected_identity=EXPECTED_ID,
            other_identity=EXPECTED_ID,
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_WRONG_ACCOUNT_VACUOUS


def test_wrong_account_leg_not_discriminated():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_wrong_account_leg(
            {"identity": EXPECTED_ID},
            expected_identity=EXPECTED_ID,
            other_identity=OTHER_ID,
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_WRONG_ACCOUNT_NOT_DISCRIMINATED


def test_wrong_account_leg_unexpected_identity():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_wrong_account_leg(
            {"identity": "third@example.test"},
            expected_identity=EXPECTED_ID,
            other_identity=OTHER_ID,
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_WRONG_ACCOUNT_UNEXPECTED_IDENTITY


# --- edge 12: infrastructure => inconclusive ----------------------------------

@pytest.mark.parametrize(
    "token",
    sorted(pilot_probe.INFRASTRUCTURE_REASONS),
)
def test_wrong_account_leg_infrastructure_inconclusive(token):
    """Edge 12: each infrastructure token => inconclusive."""
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.evaluate_wrong_account_leg(
            {"reason": token},
            expected_identity=EXPECTED_ID,
            other_identity=OTHER_ID,
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_WRONG_ACCOUNT_INCONCLUSIVE


# --- lapse_step ---------------------------------------------------------------

def test_lapse_step_continue_on_identity():
    result = pi.lapse_step(
        {"identity": EXPECTED_ID},
        sign_in_path="captured",
        reprobe_count=0,
    )
    assert result["action"] == pi.ACTION_CONTINUE


def test_lapse_step_reprobe_on_no_session():
    result = pi.lapse_step(
        {"reason": pilot_probe.REASON_NO_SESSION},
        sign_in_path="captured",
        reprobe_count=0,
    )
    assert result["action"] == pi.ACTION_REPROBE
    assert result["class"] == "lapse"


def test_lapse_step_park_captured_confirmed():
    result = pi.lapse_step(
        {"reason": pilot_probe.REASON_NO_SESSION},
        sign_in_path="captured",
        reprobe_count=1,
    )
    assert result["action"] == pi.ACTION_PARK


def test_lapse_step_remint_minted_confirmed():
    result = pi.lapse_step(
        {"reason": pilot_probe.REASON_NO_SESSION},
        sign_in_path="minted",
        reprobe_count=1,
    )
    assert result["action"] == pi.ACTION_REMINT


# --- edge 13: infrastructure => defer -----------------------------------------

@pytest.mark.parametrize(
    "token",
    sorted(pilot_probe.INFRASTRUCTURE_REASONS),
)
def test_lapse_step_infrastructure_defer(token):
    """Edge 13: each infrastructure token => ACTION_DEFER."""
    result = pi.lapse_step(
        {"reason": token},
        sign_in_path="captured",
        reprobe_count=0,
    )
    assert result["action"] == pi.ACTION_DEFER
    assert result["class"] == "infrastructure"


# --- edge 14: identity-class => refuse ----------------------------------------

@pytest.mark.parametrize(
    "token",
    sorted(pilot_probe.IDENTITY_REASONS),
)
def test_lapse_step_identity_refuse(token):
    """Edge 14: each identity-class token => ACTION_REFUSE."""
    result = pi.lapse_step(
        {"reason": token},
        sign_in_path="captured",
        reprobe_count=0,
    )
    assert result["action"] == pi.ACTION_REFUSE
    assert result["class"] == "identity"


# --- edge 15: reprobe_count 2 refuses -----------------------------------------

def test_lapse_step_reprobe_budget_two_refused():
    """Edge 15: reprobe_count == 2 => refuses."""
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.lapse_step(
            {"reason": pilot_probe.REASON_NO_SESSION},
            sign_in_path="captured",
            reprobe_count=2,
        )
    assert exc.value.reason == pi.REFUSAL_LAPSE_REPROBE_BUDGET_INVALID


def test_lapse_step_sign_in_path_invalid():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.lapse_step(
            {"reason": pilot_probe.REASON_NO_SESSION},
            sign_in_path="bogus",
            reprobe_count=0,
        )
    assert exc.value.reason == pi.REFUSAL_LAPSE_SIGN_IN_PATH_INVALID


# --- lapse_episode ------------------------------------------------------------

def test_lapse_episode_continue_on_identity():
    result = pi.lapse_episode(
        lambda: {"identity": EXPECTED_ID},
        sign_in_path="captured",
    )
    assert result["action"] == pi.ACTION_CONTINUE
    assert result["probeCalls"] == 1


def test_lapse_episode_park_captured():
    calls = []
    def probe():
        calls.append(1)
        return {"reason": pilot_probe.REASON_NO_SESSION}

    result = pi.lapse_episode(probe, sign_in_path="captured")
    assert result["action"] == pi.ACTION_PARK
    assert result["probeCalls"] == 2
    assert len(calls) == 2


# --- edge 16: at most two probe calls -----------------------------------------

def test_lapse_episode_at_most_two_calls():
    """Edge 16: forever no-session => exactly 2 calls, terminal park."""
    calls = 0

    def probe():
        nonlocal calls
        calls += 1
        return {"reason": pilot_probe.REASON_NO_SESSION}

    result = pi.lapse_episode(probe, sign_in_path="captured")
    assert calls == 2
    assert result["probeCalls"] == 2
    assert result["action"] == pi.ACTION_PARK


# --- edge 17: remint falsy => park --------------------------------------------

def test_lapse_episode_remint_falsy_park():
    """Edge 17: remint returning falsy => PARK, reminted False."""
    result = pi.lapse_episode(
        lambda: {"reason": pilot_probe.REASON_NO_SESSION},
        sign_in_path="minted",
        remint=lambda: False,
    )
    assert result["action"] == pi.ACTION_PARK
    assert result["reminted"] is False
    assert result["reason"] == pi.REFUSAL_LAPSE_REMINT_FAILED


# --- edge 18: remint raises => park ---------------------------------------------

def test_lapse_episode_remint_raises_park():
    """Edge 18: remint raising => PARK, exception does not escape."""
    def remint():
        raise RuntimeError("mint failed")

    result = pi.lapse_episode(
        lambda: {"reason": pilot_probe.REASON_NO_SESSION},
        sign_in_path="minted",
        remint=remint,
    )
    assert result["action"] == pi.ACTION_PARK
    assert result["reminted"] is False


# --- edge 19: remint None refuses ---------------------------------------------

def test_lapse_episode_remint_none_refused():
    """Edge 19: remint=None on minted path => remint-unavailable."""
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.lapse_episode(
            lambda: {"reason": pilot_probe.REASON_NO_SESSION},
            sign_in_path="minted",
            remint=None,
        )
    assert exc.value.reason == pi.REFUSAL_LAPSE_REMINT_UNAVAILABLE


def test_lapse_episode_remint_success():
    result = pi.lapse_episode(
        lambda: {"reason": pilot_probe.REASON_NO_SESSION},
        sign_in_path="minted",
        remint=lambda: True,
    )
    assert result["action"] == pi.ACTION_CONTINUE
    assert result["reminted"] is True


def test_lapse_episode_probe_not_callable():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.lapse_episode(None, sign_in_path="captured")
    assert exc.value.reason == pi.REFUSAL_LAPSE_PROBE_NOT_CALLABLE


def test_lapse_episode_probe_raises_defer():
    result = pi.lapse_episode(
        lambda: (_ for _ in ()).throw(RuntimeError("fail")),
        sign_in_path="captured",
    )
    assert result["action"] == pi.ACTION_DEFER
    assert result["reason"] == pi.REFUSAL_IDENTITY_PROBE_LEG_FAILED


def test_lapse_episode_first_probe_raises_probe_calls_one():
    result = pi.lapse_episode(
        lambda: (_ for _ in ()).throw(RuntimeError("fail")),
        sign_in_path="captured",
    )
    assert result["probeCalls"] == 1


def test_lapse_episode_second_probe_raises_probe_calls_two():
    calls = 0

    def probe():
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"reason": pilot_probe.REASON_NO_SESSION}
        raise RuntimeError("fail")

    result = pi.lapse_episode(probe, sign_in_path="captured")
    assert result["probeCalls"] == 2
    assert result["action"] == pi.ACTION_DEFER


# --- identity_probe_declaration -----------------------------------------------

def test_identity_probe_declaration_shape():
    declaration = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID, "viewer": "viewer@example.test"},
    )
    assert declaration["slot"] == "slot-a"
    assert declaration["generation"] == 1
    assert declaration["policyDigest"] == POLICY_DIGEST
    assert declaration["accountKeys"] == ["owner", "viewer"]
    assert "expectedIdentityDigest" in declaration


# --- edge 20: no identity strings in declaration --------------------------------

def test_identity_probe_declaration_no_identity_strings():
    """Edge 20: declaration contains no expected-identity string values."""
    declaration = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID},
    )
    blob = json.dumps(declaration)
    assert EXPECTED_ID not in blob


# --- edge 21: identity change changes digest ------------------------------------

def test_identity_probe_declaration_digest_binds_identity():
    """Edge 21: changing expected identity changes declaration digest."""
    decl_a = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID},
    )
    decl_b = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": OTHER_ID},
    )
    assert pilot_contract.declaration_digest(decl_a) != pilot_contract.declaration_digest(decl_b)


def test_identity_probe_declaration_bad_slot():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.identity_probe_declaration(
            slot_ref="bad",
            policy_digest=POLICY_DIGEST,
            expected_identities={"owner": EXPECTED_ID},
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_DECLARATION_SLOT_INVALID


def test_identity_probe_declaration_bad_policy_digest():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.identity_probe_declaration(
            slot_ref=SLOT_REF,
            policy_digest="",
            expected_identities={"owner": EXPECTED_ID},
        )
    assert exc.value.reason == pi.REFUSAL_IDENTITY_DECLARATION_INVALID


# --- identity_probe_receipt ---------------------------------------------------

def test_identity_probe_receipt_pass():
    declaration = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID},
    )
    slot_result = pi.evaluate_slot(
        pilot_slot.slot_account_set("slot-a", 1, [{"account": "owner", "role": "resource-owner"}]),
        {"owner": EXPECTED_ID},
        {
            "owner": {
                "seeded": {"identity": EXPECTED_ID},
                "unseeded": {"reason": pilot_probe.REASON_NO_SESSION},
            },
        },
    )
    record = pi.identity_probe_receipt(
        declaration,
        slot_result,
        exercised_at="2026-08-02T12:00:00Z",
    )
    assert record["kind"] == "identity-probe"
    assert record["receipt"]["result"] == "pass"
    assert record["receipt"]["evidence"]
    assert EXPECTED_ID not in record["receipt"]["evidence"]


def test_identity_probe_receipt_fail_evidence_no_identity():
    declaration = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID},
    )
    slot_result = {"ok": False, "reason": pi.REFUSAL_IDENTITY_PROBE_SEEDED_REFUSED, "accounts": {}}
    record = pi.identity_probe_receipt(
        declaration,
        slot_result,
        exercised_at="2026-08-02T12:00:00Z",
    )
    assert record["receipt"]["result"] == "fail"
    assert EXPECTED_ID not in record["receipt"]["evidence"]


# --- edge 22: fail receipt not exercised --------------------------------------

def test_fail_receipt_not_exercised():
    """Edge 22: fail receipt does not satisfy is_exercised."""
    declaration = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID},
    )
    slot_result = {"ok": False, "reason": pi.REFUSAL_IDENTITY_PROBE_SEEDED_REFUSED, "accounts": {}}
    record = pi.identity_probe_receipt(
        declaration,
        slot_result,
        exercised_at="2026-08-02T12:00:00Z",
    )
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [record],
    }
    assert pilot_contract.is_exercised(registry, "identity-probe", declaration) is False


def test_identity_probe_receipt_bad_exercised_at():
    with pytest.raises(pi.PilotIdentityError) as exc:
        pi.identity_probe_receipt({}, {"ok": True, "accounts": {}}, exercised_at="")
    assert exc.value.reason == pi.REFUSAL_IDENTITY_RECEIPT_ARGUMENT_INVALID


def test_require_identity_probe_exercised_propagates():
    declaration = pi.identity_probe_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        expected_identities={"owner": EXPECTED_ID},
    )
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pi.require_identity_probe_exercised({}, declaration)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


# --- malformed input ------------------------------------------------------------

def _public_callables():
    names = []
    for name in dir(pi):
        if name.startswith("_"):
            continue
        obj = getattr(pi, name)
        if inspect.isclass(obj):
            continue
        if callable(obj):
            names.append(name)
    return names


@pytest.mark.parametrize("name", _public_callables())
def test_public_entry_points_no_builtin_on_hostile(name):
    """No public entry point leaks builtin exceptions on malformed input."""
    fn = getattr(pi, name)
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())

  # Build minimal hostile kwargs per function.
    for hostile in HOSTILE_VALUES:
        kwargs = {}
        if name == "probe_answer":
            if hostile is None:
                continue
            kwargs = {"identity": hostile}
        elif name == "evaluate_pair":
            kwargs = {"seeded": hostile, "unseeded": hostile, "expected_identity": hostile}
        elif name == "run_pair_exercise":
            kwargs = {
                "expected_identity": hostile,
                "seeded_probe": hostile,
                "unseeded_probe": hostile,
            }
        elif name == "evaluate_slot":
            kwargs = {"slot_accounts": hostile, "expected_identities": hostile, "answers": hostile}
        elif name == "evaluate_wrong_account_leg":
            kwargs = {
                "answer": hostile,
                "expected_identity": hostile,
                "other_identity": hostile,
            }
        elif name == "lapse_step":
            kwargs = {"answer": hostile, "sign_in_path": hostile, "reprobe_count": hostile}
        elif name == "lapse_episode":
            kwargs = {"probe": hostile, "sign_in_path": hostile}
        elif name == "identity_probe_declaration":
            kwargs = {
                "slot_ref": hostile,
                "policy_digest": hostile,
                "expected_identities": hostile,
            }
        elif name == "identity_probe_receipt":
            kwargs = {"declaration": hostile, "result": hostile, "exercised_at": hostile}
        elif name == "require_identity_probe_exercised":
            kwargs = {"registry": hostile, "declaration": hostile}
        else:
            continue

        try:
            fn(**kwargs)
        except Exception as exc:
            if type(exc) in (pi.PilotIdentityError, pilot_contract.PilotContractError):
                continue
            if type(exc) in (TypeError, ValueError, KeyError, AttributeError):
                pytest.fail(
                    "%s leaked %s on hostile %r" % (name, type(exc).__name__, hostile)
                )
            continue
