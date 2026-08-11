"""Tests for pilot_conformance_declarations.py — declaration conformance rows (C10)."""
import copy
import json
import os
import stat
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_conformance as pc  # noqa: E402
import pilot_conformance_declarations as pcd  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_policy  # noqa: E402
import pilot_provision as pp  # noqa: E402

from test_pilot_conformance import (  # noqa: E402
    EXERCISED_AT,
    _MINIMAL_PILOT_JSON,
    _write_calibration_layer,
)
from test_pilot_provision import (  # noqa: E402
    SAMPLE_POLICY,
    _mint_block,
    _valid_minted_pilot_block,
    _valid_pilot_block,
)

NOW = EXERCISED_AT
EMPTY_REGISTRY = {"schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION, "records": []}


def _registry_record(kind, declaration):
    return {
        "kind": kind,
        "declarationDigest": pilot_contract.declaration_digest(declaration),
        "exercisedAt": "2026-08-02T04:00:00Z",
        "receipt": {"result": "pass", "evidence": "exercised"},
    }


def _two_slot_policy():
    policy = copy.deepcopy(SAMPLE_POLICY)
    policy["slots"]["slot-b"] = {
        "origin": "http://127.0.0.1:5174",
        "permittedRedirects": ["http://127.0.0.1:5174"],
        "expectedIdentities": {"owner": "pilot-owner-b@example.test"},
        "mintableAccounts": ["pilot-owner-b"],
        "accountClasses": {"owner": "dev"},
    }
    return policy


def _row_for(rows, kind, slot_ref):
    matches = [
        row for row in rows
        if row["kind"] == kind and row["slotRef"] == slot_ref
    ]
    assert len(matches) == 1
    return matches[0]


# --- multi-slot attested vs absent -------------------------------------------

def test_multi_slot_kind_attested_for_one_slot_absent_for_another():
    policy = _two_slot_policy()
    block = _valid_minted_pilot_block()
    slot_a_ref = "slot-a@1"
    slot_b_ref = "slot-b@1"
    info_a = pp.declaration_for("app-lifecycle", block, policy, slot_a_ref)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [_registry_record("app-lifecycle", info_a["declaration"])],
    }
    rows = pcd.declaration_rows(block, policy, registry, now=NOW)
    row_a = _row_for(rows, "app-lifecycle", slot_a_ref)
    row_b = _row_for(rows, "app-lifecycle", slot_b_ref)
    assert row_a["status"] == pcd.STATUS_ATTESTED
    assert row_b["status"] == pcd.STATUS_ABSENT
    assert row_a["slotRef"] != row_b["slotRef"]


# --- every status and reason token -------------------------------------------

def test_status_attested_has_no_reason():
    policy = SAMPLE_POLICY
    block = _valid_minted_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("identity-probe", block, policy, slot_ref)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [_registry_record("identity-probe", info["declaration"])],
    }
    row = _row_for(
        pcd.declaration_rows(block, policy, registry, now=NOW),
        "identity-probe",
        slot_ref,
    )
    assert row["status"] == pcd.STATUS_ATTESTED
    assert row["reason"] is None
    assert row["declarationDigest"] == pilot_contract.declaration_digest(info["declaration"])


def test_status_not_applicable_has_no_reason_or_digest():
    policy = copy.deepcopy(SAMPLE_POLICY)
    del policy["slots"]["slot-a"]["mintableAccounts"]
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    row = _row_for(
        pcd.declaration_rows(block, policy, EMPTY_REGISTRY, now=NOW),
        "mint-gate-off",
        slot_ref,
    )
    assert row["status"] == pcd.STATUS_NOT_APPLICABLE
    assert row["reason"] is None
    assert row["declarationDigest"] is None


def test_status_absent_unexercised_reason_token():
    policy = SAMPLE_POLICY
    block = _valid_minted_pilot_block()
    slot_ref = "slot-a@1"
    row = _row_for(
        pcd.declaration_rows(block, policy, EMPTY_REGISTRY, now=NOW),
        "identity-probe",
        slot_ref,
    )
    assert row["status"] == pcd.STATUS_ABSENT
    assert row["reason"] == pcd.REASON_DECLARATION_UNEXERCISED


def test_status_absent_declaration_for_refusal_token():
    policy = copy.deepcopy(SAMPLE_POLICY)
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    row = _row_for(
        pcd.declaration_rows(block, policy, EMPTY_REGISTRY, now=NOW),
        "mint-gate-off",
        slot_ref,
    )
    assert row["status"] == pcd.STATUS_ABSENT
    assert row["reason"] == pp.REFUSAL_MINT_DECLARATION_MISSING


# --- digest binding -----------------------------------------------------------

def test_digest_mismatch_reports_absent_not_attested():
    policy = SAMPLE_POLICY
    block = _valid_minted_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("identity-probe", block, policy, slot_ref)
    wrong_declaration = copy.deepcopy(info["declaration"])
    wrong_declaration["path"] = "/api/other"
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [_registry_record("identity-probe", wrong_declaration)],
    }
    row = _row_for(
        pcd.declaration_rows(block, policy, registry, now=NOW),
        "identity-probe",
        slot_ref,
    )
    assert row["status"] == pcd.STATUS_ABSENT
    assert row["reason"] == pcd.REASON_DECLARATION_UNEXERCISED


# --- row isolation ------------------------------------------------------------

def test_exception_mid_enumeration_leaves_remaining_rows(monkeypatch):
    policy = _two_slot_policy()
    block = _valid_minted_pilot_block()
    original = pp.declaration_for
    calls = {"count": 0}

    def flaky(kind, pilot_block, policy_doc, slot_ref):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return original(kind, pilot_block, policy_doc, slot_ref)

    monkeypatch.setattr(pp, "declaration_for", flaky)
    rows = pcd.declaration_rows(block, policy, EMPTY_REGISTRY, now=NOW)
    assert len(rows) > 1
    assert any(row["reason"] == pcd.REASON_ROW_RAISED for row in rows)
    assert any(row["status"] == pcd.STATUS_ABSENT for row in rows[1:])


# --- ok envelope --------------------------------------------------------------

def test_ok_false_for_empty_row_list(monkeypatch):
    monkeypatch.setattr(pcd, "declaration_rows", lambda *args, **kwargs: [])
    envelope = pcd.declarations_block({}, {}, EMPTY_REGISTRY, now=NOW)
    assert envelope["rows"] == []
    assert envelope["ok"] is False


def test_ok_false_when_any_row_absent():
    policy = SAMPLE_POLICY
    block = _valid_minted_pilot_block()
    envelope = pcd.declarations_block(block, policy, EMPTY_REGISTRY, now=NOW)
    assert envelope["absent"] > 0
    assert envelope["ok"] is False


def test_ok_true_when_all_rows_attested_or_not_applicable():
    policy = SAMPLE_POLICY
    block = _valid_minted_pilot_block()
    slot_ref = "slot-a@1"
    records = []
    for kind in pilot_contract.DECLARATION_KINDS:
        info = pp.declaration_for(kind, block, policy, slot_ref)
        if info["applicable"]:
            records.append(_registry_record(kind, info["declaration"]))
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": records,
    }
    envelope = pcd.declarations_block(block, policy, registry, now=NOW)
    assert envelope["ok"] is True
    assert envelope["absent"] == 0


# --- policy material non-leak -------------------------------------------------

def test_rows_do_not_leak_policy_material():
    policy = copy.deepcopy(SAMPLE_POLICY)
    secret = "super-secret-identity-token-xyzzy"
    policy["slots"]["slot-a"]["expectedIdentities"]["owner"] = secret
    policy["datastore"]["expectedIdentity"] = secret
    block = _valid_minted_pilot_block()
    rows = pcd.declaration_rows(block, policy, EMPTY_REGISTRY, now=NOW)
    serialized = json.dumps(rows)
    assert secret not in serialized
    material = pilot_policy.policy_material(policy)
    for values in material.values():
        for needle in values:
            assert needle not in serialized


# --- resolve_inputs registry fail-closed ---------------------------------------

def _resolved_declarations_inputs(tmp_path, **kwargs):
    reach_root = tmp_path / "reach"
    reach_root.mkdir()
    cwd = reach_root
    _write_calibration_layer(cwd, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    policy = copy.deepcopy(SAMPLE_POLICY)
    policy["declaration"] = "example-project-pilot-policy"
    with open(
        policy_root / "example-project-pilot-policy.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(policy, handle)
    defaults = {
        "policy_root": str(policy_root),
        "reach_roots": [str(reach_root)],
        "now": NOW,
    }
    defaults.update(kwargs)
    return pc.resolve_inputs(str(cwd), **defaults)


def test_resolve_inputs_no_registry_path(tmp_path):
    inputs, resolution = _resolved_declarations_inputs(tmp_path)
    assert "declarations" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["declarations"]["reason"] == pc.REASON_INPUT_NO_REGISTRY_PATH


def test_resolve_inputs_registry_missing_path(tmp_path):
    missing = str(tmp_path / "missing-registry.json")
    inputs, resolution = _resolved_declarations_inputs(tmp_path, registry_path=missing)
    assert "declarations" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["declarations"]["reason"] == pc.REASON_INPUT_REGISTRY_MISSING


def test_resolve_inputs_registry_unreadable(tmp_path):
    unreadable = tmp_path / "registry.json"
    unreadable.write_text("{}", encoding="utf-8")
    os.chmod(unreadable, 0o000)
    try:
        inputs, resolution = _resolved_declarations_inputs(
            tmp_path, registry_path=str(unreadable),
        )
    finally:
        os.chmod(unreadable, stat.S_IWUSR | stat.S_IRUSR)
    assert "declarations" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["declarations"]["reason"] == pc.REASON_INPUT_REGISTRY_UNREADABLE


def test_resolve_inputs_registry_invalid_json(tmp_path):
    bad_json = tmp_path / "registry.json"
    bad_json.write_text("{not json", encoding="utf-8")
    inputs, resolution = _resolved_declarations_inputs(
        tmp_path, registry_path=str(bad_json),
    )
    assert "declarations" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["declarations"]["reason"] == pc.REASON_INPUT_REGISTRY_INVALID_JSON


def test_resolve_inputs_registry_invalid_shape(tmp_path):
    bad_shape = tmp_path / "registry.json"
    bad_shape.write_text('{"schemaVersion": 1}', encoding="utf-8")
    inputs, resolution = _resolved_declarations_inputs(
        tmp_path, registry_path=str(bad_shape),
    )
    assert "declarations" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["declarations"]["reason"] == pc.REASON_INPUT_REGISTRY_INVALID_SHAPE


# --- main() e2e ---------------------------------------------------------------

def _repo_root():
    return os.path.realpath(os.path.join(_HERE, "..", "..", "..", ".."))


def test_main_includes_declarations_without_allow_live_effects(tmp_path, capsys):
    reach_root = tmp_path / "reach"
    reach_root.mkdir()
    _write_calibration_layer(reach_root, include_mint=True)
    policy_root = tmp_path / "policy"
    policy_root.mkdir()
    policy = copy.deepcopy(SAMPLE_POLICY)
    policy["declaration"] = "example-project-pilot-policy"
    with open(
        policy_root / "example-project-pilot-policy.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(policy, handle)
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(EMPTY_REGISTRY), encoding="utf-8")

    exit_code = pc.main([
        "pilot_conformance.py",
        "run",
        "--cwd",
        str(reach_root),
        "--policy-root",
        str(policy_root),
        "--reach-root",
        str(reach_root),
        "--registry-path",
        str(registry_path),
        "--now",
        NOW,
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "declarations" in payload
    assert payload["declarations"] is not None
    assert payload["declarations"]["schemaVersion"] == pcd.SCHEMA
    assert exit_code == 1
