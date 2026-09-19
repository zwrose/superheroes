"""#1272 WO-3: one home for evidence-digest subject, list-type classifier, audit provenance."""
import importlib
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import audits  # noqa: E402
import engine_adapter  # noqa: E402
import payload_contracts  # noqa: E402
import round_adapters  # noqa: E402
import round_phases  # noqa: E402
import round_records  # noqa: E402
import session_contract  # noqa: E402

RD = importlib.import_module("round_driver")

_PHASE_FOR_KIND = {
    "findings": round_phases.P_PANEL,
    "verdicts": round_phases.P_VERIFIERS,
    "grouping": round_phases.P_SYNTHESIS,
    "ruling": round_phases.P_AUDITS,
}

_PAYLOAD_FIXTURES = {
    "findings": {
        "well-formed": {"findings": [{"dimension": "d", "taxonomy": "t", "title": "x"}]},
        "missing-key": {},
        "wrong-type": {"findings": "x"},
        "mismatched-kind": {"verdicts": [{"id": "v1", "verdict": "pass"}]},
    },
    "verdicts": {
        "well-formed": {"verdicts": [{"id": "v1", "verdict": "pass"}]},
        "missing-key": {},
        "wrong-type": {"verdicts": "x"},
        "mismatched-kind": {"findings": [{"dimension": "d", "taxonomy": "t", "title": "x"}]},
    },
    "grouping": {
        "well-formed": {"grouping": [{"member_ids": ["a"]}]},
        "missing-key": {},
        "wrong-type": {"grouping": "x"},
        "mismatched-kind": {"findings": []},
    },
    "ruling": {
        "well-formed": {"id": "a1", "ruling": "discharged", "reason": "ok", "evidence": "e"},
        "missing-key": {},
        "wrong-type": {"id": "a1", "ruling": 123, "reason": "ok"},
        "empty-ruling": {"id": "a1", "ruling": "", "reason": "ok"},
        "mismatched-kind": {"findings": []},
    },
}

_DRIFT_CASES = [
    (kind, label, payload)
    for kind in engine_adapter.REVIEW_RESULT_KINDS
    for label, payload in _PAYLOAD_FIXTURES[kind].items()
]


def test_record_result_kinds_subset_of_review_result_kinds():
    assert set(session_contract.RECORD_RESULT_KINDS) <= set(engine_adapter.REVIEW_RESULT_KINDS)


def test_review_list_result_kinds_partition_review_result_kinds():
    assert (set(session_contract.REVIEW_LIST_RESULT_KINDS)
            | set(session_contract.RECORD_RESULT_KINDS)
            | {"grouping"} == set(engine_adapter.REVIEW_RESULT_KINDS))


_NON_REVIEW_KIND_CASES = [
    ("result", {"result": "pass", "command": "none", "exit": 0}, (True, "pass")),
    ("result", {"command": "none"}, (False, None)),
    ("fixes", {"fixes": [{"file": "a"}]}, (True, [{"file": "a"}])),
]


@pytest.mark.parametrize("kind,payload,expected", _NON_REVIEW_KIND_CASES)
def test_evidence_digest_subject_non_review_kinds(kind, payload, expected):
    assert session_contract.evidence_digest_subject(payload, kind) == expected


@pytest.mark.parametrize("kind,label,payload", _DRIFT_CASES)
def test_evidence_digest_subject_matches_review_payload_carried(kind, label, payload):
    phase = _PHASE_FOR_KIND[kind]
    shaped = RD._runner_shaped_result(phase, kind, payload)
    assert session_contract.evidence_digest_subject(payload, kind) == (
        engine_adapter.review_payload_carried(shaped, kind))


def test_is_list_type_classifies_contract_tokens():
    assert payload_contracts.is_list_type(payload_contracts.LIST_TYPE_TOKEN) is True
    assert payload_contracts.is_list_type(payload_contracts.NULLABLE_LIST_TYPE_TOKEN) is True
    for token in ("list", "object", None):
        assert payload_contracts.is_list_type(token) is False


def test_apply_audit_results_stamps_unauthenticated_cause_no_auditor():
    target = {"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important"}
    out = audits.apply_audit_results(
        [target],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={})
    entry = next(a for a in out["audits"] if a["id"] == "v0")
    assert entry["unauthenticatedCause"] == audits.UNAUTHENTICATED_NO_AUDITOR_RECORDED


def test_apply_audit_results_stamps_unauthenticated_cause_missing_manifest_entry():
    out = audits.apply_audit_results(
        [{"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important"}],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={})
    entry = next(a for a in out["audits"] if a["id"] == "v0")
    assert entry["unauthenticatedCause"] == audits.UNAUTHENTICATED_MANIFEST_ENTRY_MISSING


def test_apply_audit_results_stamps_unauthenticated_cause_vendor_mismatch():
    out = audits.apply_audit_results(
        [{"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important"}],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={"v0": "claude"})
    entry = next(a for a in out["audits"] if a["id"] == "v0")
    assert entry["unauthenticatedCause"] == audits.UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH


def test_adapter_provenance_source_values_are_round_records_constants():
    """Bites on: round_driver provenance tokens stay aliased to round_records definitions."""
    rd_source = open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8").read()
    assert "AUDIT_PROVENANCE_RUNNER_RECORD = round_records.AUDIT_PROVENANCE_RUNNER_RECORD" in rd_source
    assert "AUDIT_PROVENANCE_HAND_LANDED = round_records.AUDIT_PROVENANCE_HAND_LANDED" in rd_source
    disclosures = {}
    indexed = {
        ("runner-seat", 0): {
            "kind": round_adapters._KIND_RESULT,
            "envelope": {
                "schema": round_records.SEAT_RESULT_SCHEMA_V2,
                "provenance": round_records.PROVENANCE_DISPATCH_OBSERVED,
                "executionEvidence": {"source": "codex"},
            },
        },
        ("hand-seat", 0): {
            "kind": round_adapters._KIND_RESULT,
            "envelope": {
                "schema": round_records.SEAT_RESULT_SCHEMA_V2,
                "provenance": round_records.PROVENANCE_HAND_LANDED,
                "executionEvidence": {"source": "cursor"},
            },
        },
    }
    round_adapters._trusted_vendors(["runner-seat", "hand-seat"], indexed, None, disclosures)
    prov = disclosures["provenanceSource"]
    assert prov["runner-seat"] == round_records.AUDIT_PROVENANCE_RUNNER_RECORD
    assert prov["hand-seat"] == round_records.AUDIT_PROVENANCE_HAND_LANDED


def test_fold_audits_missing_manifest_detail_from_cause_not_prose(monkeypatch):
    """Bites on: _fold_audits manifest-missing detail comes from cause branch, not reason prose."""

    def _fake_apply_audit_results(*_args, **_kwargs):
        return {
            "audits": [{
                "id": "t1",
                "ruling": "not-discharged",
                "reason": "anything",
                "unauthenticatedCause": audits.UNAUTHENTICATED_MANIFEST_ENTRY_MISSING,
            }],
            "unauthenticated": ["t1"],
            "notDischarged": ["t1"],
            "discharged": [],
            "newIssues": [],
            "unaudited": [],
            "ambiguous": [],
            "malformed": [],
            "unmatched": [],
            "echoMismatch": [],
        }

    monkeypatch.setattr(RD.audits, "apply_audit_results", _fake_apply_audit_results)
    state = {"round": 1, "rounds": {}, "auditRounds": [], "decisions": [],
             "_auditTargets": [{"id": "t1", "auditorVendor": "codex",
                                "independence": "cross-vendor"}]}
    RD._fold_audits(state, {}, {
        "results": [{"id": "t1", "ruling": "discharged", "reason": "anything",
                     "auditorVendor": "codex"}],
        "collectionManifest": {},
    })
    fail = [d for d in state["decisions"] if d["kind"] == "audit-provenance-fail"]
    assert len(fail) == 1
    assert "expected a collectionManifest entry keyed 't1'" in fail[0]["detail"]
    assert "anything" not in fail[0]["detail"]
