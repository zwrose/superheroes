"""Tests for pilot slot identity, generation, and account-set types."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_slot  # noqa: E402
import store  # noqa: E402


def _raises(reason):
    return pytest.raises(pilot_slot.PilotSlotError, match=reason)


def test_slot_re_is_store_slot_re():
    assert pilot_slot.SLOT_RE is store.SLOT_RE


@pytest.mark.parametrize(
    "slot",
    [None, "", "a b", "-lead", "a@b", 3],
)
def test_validate_slot_id_refuses_invalid(slot):
    with _raises(pilot_slot.REFUSAL_SLOT_ID_INVALID):
        pilot_slot.validate_slot_id(slot)


def test_validate_slot_id_accepts_valid():
    assert pilot_slot.validate_slot_id("slot1") == "slot1"


@pytest.mark.parametrize(
    "generation",
    [0, -1, True, False, "1", 1.0, None],
)
def test_validate_generation_refuses_invalid(generation):
    with _raises(pilot_slot.REFUSAL_GENERATION_INVALID):
        pilot_slot.validate_generation(generation)


def test_validate_generation_accepts_valid():
    assert pilot_slot.validate_generation(1) == 1
    assert pilot_slot.validate_generation(42) == 42


def test_format_and_parse_round_trip():
    cases = [
        ("a", 1),
        ("slot", 9),
        ("Slot_1", 100),
        ("x9", 2),
    ]
    for slot, generation in cases:
        ref = pilot_slot.format_slot_ref(slot, generation)
        assert pilot_slot.parse_slot_ref(ref) == (slot, generation)


@pytest.mark.parametrize(
    "ref",
    [
        "noatsign",
        "a@b@c",
        "@3",
        "slot@",
        "slot@01",
        "slot@+3",
        "slot@3.0",
        "slot@ 3",
        None,
    ],
)
def test_parse_slot_ref_refuses_malformed(ref):
    with _raises(pilot_slot.REFUSAL_SLOT_REF_MALFORMED):
        pilot_slot.parse_slot_ref(ref)


def test_parse_slot_ref_refuses_invalid_slot_id():
    with _raises(pilot_slot.REFUSAL_SLOT_ID_INVALID):
        pilot_slot.parse_slot_ref("-lead@3")


@pytest.mark.parametrize(
    "ref",
    ["slot@0"],
)
def test_parse_slot_ref_refuses_invalid_generation(ref):
    with _raises(pilot_slot.REFUSAL_GENERATION_INVALID):
        pilot_slot.parse_slot_ref(ref)


def test_slot_account_set_builds_valid_dict():
    result = pilot_slot.slot_account_set(
        "slot1",
        2,
        [{"account": "owner", "role": "resource-owner"}],
    )
    assert result == {
        "slot": "slot1",
        "generation": 2,
        "ref": "slot1@2",
        "accounts": [{"account": "owner", "role": "resource-owner"}],
    }


def test_slot_account_set_copies_accounts():
    source = [{"account": "owner", "role": "resource-owner"}]
    result = pilot_slot.slot_account_set("slot1", 1, source)
    source[0]["role"] = "mutated"
    source.append({"account": "guest", "role": "share-recipient"})
    assert result["accounts"] == [{"account": "owner", "role": "resource-owner"}]


def test_account_keys_preserves_declaration_order():
    result = pilot_slot.slot_account_set(
        "slot1",
        1,
        [
            {"account": "owner", "role": "resource-owner"},
            {"account": "guest", "role": "share-recipient"},
        ],
    )
    assert pilot_slot.account_keys(result) == ["owner", "guest"]


def test_slot_account_set_refuses_empty_accounts():
    with _raises(pilot_slot.REFUSAL_ACCOUNT_SET_EMPTY):
        pilot_slot.slot_account_set("slot1", 1, [])


def test_slot_account_set_refuses_none_accounts():
    with _raises(pilot_slot.REFUSAL_ACCOUNT_SET_EMPTY):
        pilot_slot.slot_account_set("slot1", 1, None)


def test_slot_account_set_refuses_duplicate_account():
    accounts = [
        {"account": "owner", "role": "resource-owner"},
        {"account": "owner", "role": "share-recipient"},
    ]
    with _raises(pilot_slot.REFUSAL_ACCOUNT_DUPLICATE):
        pilot_slot.slot_account_set("slot1", 1, accounts)


def test_slot_account_set_refuses_missing_role():
    with _raises(pilot_slot.REFUSAL_ACCOUNT_ROLE_MISSING):
        pilot_slot.slot_account_set("slot1", 1, [{"account": "owner"}])


def test_slot_account_set_refuses_empty_role():
    with _raises(pilot_slot.REFUSAL_ACCOUNT_ROLE_MISSING):
        pilot_slot.slot_account_set(
            "slot1",
            1,
            [{"account": "owner", "role": ""}],
        )


def test_slot_account_set_refuses_non_mapping_entry():
    with _raises(pilot_slot.REFUSAL_ACCOUNT_ENTRY_INVALID):
        pilot_slot.slot_account_set("slot1", 1, ["not-a-mapping"])
