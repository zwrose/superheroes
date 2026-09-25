"""#1272 layer 3B: write-run phase gate and non-blocking survivor disclosures."""
import importlib.util
import inspect
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from round_certification_fixtures import DEFAULT_PANEL_PAYLOAD_SHA, write_session

import round_certification as RC
import session_contract as SC

HEAD = "a" * 40


def _hand_landed_evidence_binding(**overrides):
    evidence = {
        "source": "runner",
        "runnerNonce": "hand-landed-nonce",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    evidence.update(overrides)
    return evidence


def _write_stamp_evidence(**overrides):
    return _hand_landed_evidence_binding(
        resultKind=SC.WRITE_RESULT_KIND,
        resultDigest=SC.payload_sha256({"testFailed": False, "testPassed": True}),
        **overrides,
    )


def _hand_landed_envelope(evidence, payload, *, order_sha="f" * 64):
    return {
        "orderSha256": order_sha,
        "payload": payload,
        "executionEvidence": evidence,
    }


def _journal_binding(evidence):
    return {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}


def _hand_landed_journal_row(phase, seat, payload_sha, evidence, *, attempt=0):
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": 1,
        "attempt": attempt,
        "seat": seat,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": payload_sha,
        "executionEvidence": {
            field: evidence[field]
            for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        },
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": 0,
            "attempt": attempt,
        },
    }


def _write_stamp_session(tmp_path, phase, seat="code-reviewer"):
    evidence = _write_stamp_evidence(runKind=SC.run_kind_for_phase(phase))
    payload = {"fixes": [{"file": "a.py", "description": "fixed"}]}
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        journal_lines=[_hand_landed_journal_row(phase, seat, payload_sha, evidence)],
        envelopes=[
            {
                "seat": seat,
                "phase": phase,
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence,
                "payload": payload,
            }
        ],
    )
    return session_dir


def _certifiable_session(tmp_path, state):
    return write_session(
        tmp_path,
        state=state,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )


def _ctx_for_state(state, tmp_path):
    ctx, err = RC._load_context(_certifiable_session(tmp_path, state))
    assert err is None
    return ctx


# --- B1: write-run stamp phase gate ------------------------------------------------


def test_l3_b1_write_stamp_out_of_phase_refused(tmp_path):
    for phase in (RC.PANEL_PHASE, RC.AUDITS_PHASE):
        ctx, _ = RC._load_context(_write_stamp_session(tmp_path / phase, phase))
        refusal = RC.check_unrun_review(ctx)
        assert refusal is not None
        assert refusal["class"] == "unrun-review"
        assert refusal["bindingFailure"] == "execution-evidence-write-stamp-out-of-phase"


def test_l3_b1_write_stamp_admitted_on_fixer_phase(tmp_path):
    ctx, _ = RC._load_context(_write_stamp_session(tmp_path, RC.FIXER_PHASE))
    assert RC.check_unrun_review(ctx) is None


def test_l3_b1_edge_phase_absent_refuses():
    evidence = _write_stamp_evidence()
    envelope = _hand_landed_envelope(evidence, {"fixes": []})
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=_journal_binding(evidence),
        recorded_nonces={"hand-landed-nonce"}, phase=None,
    )
    assert ok is False
    assert failure == "execution-evidence-write-stamp-out-of-phase"


def test_l3_b1_edge_phase_not_string_refuses():
    evidence = _write_stamp_evidence()
    envelope = _hand_landed_envelope(evidence, {"fixes": []})
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=_journal_binding(evidence),
        recorded_nonces={"hand-landed-nonce"}, phase=1,
    )
    assert ok is False
    assert failure == "execution-evidence-write-stamp-out-of-phase"


def test_l3_b1_edge_unknown_phase_refuses():
    evidence = _write_stamp_evidence()
    envelope = _hand_landed_envelope(evidence, {"fixes": []})
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=_journal_binding(evidence),
        recorded_nonces={"hand-landed-nonce"}, phase="dispatch-unknown",
    )
    assert ok is False
    assert failure == "execution-evidence-write-stamp-out-of-phase"


def test_l3_b1_edge_fixer_phase_valid_stamp_admitted():
    evidence = _write_stamp_evidence()
    envelope = _hand_landed_envelope(evidence, {"fixes": []})
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=_journal_binding(evidence),
        recorded_nonces={"hand-landed-nonce"}, phase=RC.FIXER_PHASE,
    )
    assert ok is True
    assert failure == RC.EXECUTION_ONLY_BINDING


def test_l3_b1_edge_payload_bound_kind_unchanged_on_panel_phase():
    fixes = [{"file": "a.py", "description": "fixed"}]
    evidence = _hand_landed_evidence_binding(
        resultKind="fixes",
        resultDigest=SC.payload_sha256(fixes),
    )
    envelope = _hand_landed_envelope(evidence, {"fixes": fixes})
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=_journal_binding(evidence),
        recorded_nonces={"hand-landed-nonce"}, phase=RC.PANEL_PHASE,
    )
    assert ok is True
    assert failure is None


def test_l3_b1_edge_binding_incomplete_wins_over_phase():
    evidence = _hand_landed_evidence_binding(resultKind="")
    envelope = _hand_landed_envelope(evidence, {"fixes": []})
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=_journal_binding(evidence),
        recorded_nonces={"hand-landed-nonce"}, phase=RC.PANEL_PHASE,
    )
    assert ok is False
    assert failure == "execution-evidence-binding-incomplete"


def test_l3_b1_phase_rule_single_definition():
    spec = importlib.util.spec_from_file_location(
        "session_contract_census", os.path.join(_LIB, "session_contract.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    source = inspect.getsource(mod)
    assert source.count("def execution_only_admissible_for_phase") == 1


# --- B2/B3: non-blocking disposition path -------------------------------------------


def test_l3_b2_nonblocking_survivor_disclosed_not_refused(tmp_path):
    state = {
        "findings": [
            {
                "id": "M1",
                "file": "a.py",
                "line": 1,
                "title": "style nit",
                "severity": "Minor",
            }
        ],
    }
    session_dir = _certifiable_session(tmp_path, state)
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt is not None
    assert receipt["disclosures"]["survivingNonBlocking"] == [
        {
            "id": "M1",
            "findingKey": "a.py::style nit@L1",
            "file": "a.py",
            "line": 1,
            "title": "style nit",
            "severity": "Minor",
        },
    ]
    assert not any(f.get("id") == "M1" for f in receipt["findings"])


def test_l3_b4_pre_v5_session_refuses_undispositioned_minor(tmp_path):
    state = {
        "schemaVersion": 4,
        "findings": [
            {
                "id": "M1",
                "file": "a.py",
                "line": 1,
                "title": "style nit",
                "severity": "Minor",
            }
        ],
    }
    ctx = _ctx_for_state(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"


def test_l3_b5_pre_v5_receipt_carries_no_surviving_nonblocking(tmp_path):
    state_v4 = {
        "schemaVersion": 4,
        "findings": [
            {
                "id": "M1",
                "file": "a.py",
                "line": 1,
                "title": "style nit",
                "severity": "Minor",
                "disposition": "refuted",
                "refutedReason": "intentional",
            }
        ],
    }
    ctx_v4 = _ctx_for_state(state_v4, tmp_path / "v4")
    disclosures_v4 = RC._receipt_disclosures(ctx_v4, ctx_v4["state"])
    assert "survivingNonBlocking" not in disclosures_v4

    state_v5 = {
        "schemaVersion": 5,
        "findings": [
            {
                "id": "M1",
                "file": "a.py",
                "line": 1,
                "title": "style nit",
                "severity": "Minor",
            }
        ],
    }
    ctx_v5 = _ctx_for_state(state_v5, tmp_path / "v5")
    disclosures_v5 = RC._receipt_disclosures(ctx_v5, ctx_v5["state"])
    assert "survivingNonBlocking" in disclosures_v5


def test_l3_b3_critical_may_not_take_the_nonblocking_path(tmp_path):
    ctx = _ctx_for_state(
        {"findings": [{"id": "C1", "severity": "Critical", "title": "blocker"}]},
        tmp_path,
    )
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["detail"] == "Critical finding may not take the non-blocking path"


def test_l3_b2_edge_severity_absent_refuses(tmp_path):
    ctx = _ctx_for_state({"findings": [{"id": "X1", "title": "no sev"}]}, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert "not in the closed severity contract" in refusal["detail"]


def test_l3_b2_edge_severity_outside_contract_refuses(tmp_path):
    ctx = _ctx_for_state(
        {"findings": [{"id": "X1", "severity": "Urgent", "title": "foreign"}]},
        tmp_path,
    )
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert "not in the closed severity contract" in refusal["detail"]


@pytest.mark.parametrize("severity", ["minor", " Nit ", " minor "])
def test_l3_b2_edge_severity_case_or_whitespace_variant_refuses(tmp_path, severity):
    ctx = _ctx_for_state(
        {"findings": [{"id": "X1", "severity": severity, "title": "malformed"}]},
        tmp_path,
    )
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert "not in the closed severity contract" in refusal["detail"]


def test_l3_b2_edge_important_without_disposition_refuses(tmp_path):
    ctx = _ctx_for_state(
        {"findings": [{"id": "I1", "severity": "Important", "title": "must fix"}]},
        tmp_path,
    )
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["detail"] == "finding has no disposition recorded"


def test_l3_b2_edge_minor_with_disposition_not_disclosed(tmp_path):
    ctx = _ctx_for_state(
        {
            "findings": [
                {
                    "id": "M1",
                    "severity": "Minor",
                    "title": "handled",
                    "disposition": "refuted",
                    "refutedReason": "intentional",
                }
            ],
        },
        tmp_path,
    )
    assert RC.check_disposition_without_receipt(ctx) is None
    assert ctx.get("nonblocking_disclosures") in (None, [])


def test_l3_b2_edge_merged_into_resolves_before_disclosure(tmp_path):
    rep = {
        "id": "R1",
        "file": "m.py",
        "line": 1,
        "title": "root",
        "severity": "Minor",
        "disposition": "refuted",
        "refutedReason": "ok",
    }
    member = {
        "id": "M1",
        "file": "m.py",
        "line": 2,
        "title": "member",
        "severity": "Minor",
        SC.MERGED_INTO_FIELD: SC.finding_identity_key(rep),
    }
    ctx = _ctx_for_state({"findings": [rep, member]}, tmp_path)
    assert RC.check_disposition_without_receipt(ctx) is None
    assert ctx.get("nonblocking_disclosures") in (None, [])


def test_l3_b2_edge_merged_nonblocking_members_omitted_from_receipt(tmp_path):
    rep = {
        "id": "R1",
        "file": "m.py",
        "line": 1,
        "title": "root",
        "severity": "Minor",
    }
    member = {
        "id": "M2",
        "file": "m.py",
        "line": 2,
        "title": "member",
        "severity": "Minor",
        SC.MERGED_INTO_FIELD: SC.finding_identity_key(rep),
    }
    session_dir = _certifiable_session(tmp_path, {"findings": [rep, member]})
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt is not None
    receipt_ids = {f.get("id") for f in receipt["findings"]}
    assert "R1" not in receipt_ids
    assert "M2" not in receipt_ids
    disclosed_ids = {row.get("id") for row in receipt["disclosures"]["survivingNonBlocking"]}
    assert disclosed_ids == {"R1", "M2"}
