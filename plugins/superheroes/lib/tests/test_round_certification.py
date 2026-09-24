import base64
import hashlib
import json
import os
import sys

import model_registry
import pytest
import record_paths
import round_records

import round_certification as RC
import session_contract
from round_certification_fixtures import (
    DEFAULT_FINDINGS_RESULT_SHA,
    DEFAULT_PANEL_PAYLOAD_SHA,
    HEAD_SHA,
    MUST_REFUSE_FIXTURES,
    write_session,
    write_certifiable_session,
    _binding_fields,
    _dispatch_journal_with_binding,
    _FIX_PRESENT_BYTES,
    _hand_landed_binding_journal_row,
    _head_content_read_row,
    _write_head_content_blobs,
)

HEAD = HEAD_SHA

QUALIFICATION_HELPER_CENSUS = (
    "_execution_binding_matches_journal",
    "_observation_qualifies",
    "_hand_landed_evidence_qualifies",
    "_fix_still_present_at_head",
)


_FIX_PRESENT_DIGEST = hashlib.sha256(_FIX_PRESENT_BYTES).hexdigest()


def _fix_content_disposition_receipt(**overrides):
    receipt = {
        "headSha": HEAD,
        "verifyResult": "pass",
        "fixContentDigest": _FIX_PRESENT_DIGEST,
    }
    receipt.update(overrides)
    return receipt


def _envelope_execution_evidence_from_journal(journal_evidence):
    observation = {
        "read": journal_evidence.get("read", "engaged"),
        "source": journal_evidence.get("source", "runner"),
        "telemetry": journal_evidence.get("telemetry", "tool-calls"),
        "stdoutBytes": journal_evidence.get("stdoutBytes", 10),
        "wallSeconds": journal_evidence.get("wallSeconds", 1.0),
        "tokens": None,
        "toolCalls": journal_evidence.get("toolCalls", 1),
    }
    out = {
        key: journal_evidence[key]
        for key in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        if key in journal_evidence
    }
    out["observation"] = observation
    if isinstance(journal_evidence.get("engineModel"), str) and journal_evidence["engineModel"]:
        out["engineModel"] = journal_evidence["engineModel"]
    return out


# axis: legacy journal row with no transport field is the writer's input surface, not driver-produced.
def test_receipt_seat_model_none_when_transport_absent(tmp_path):
    seat = "test-reviewer"
    binding = _binding_fields("dispatch-model-nonce", result_digest=DEFAULT_FINDINGS_RESULT_SHA)
    journal_evidence = {
        **binding,
        "read": "engaged",
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
        "toolCalls": 1,
        "engineModel": "gpt-5.6-sol",
    }
    journal_row = _dispatch_journal_with_binding(
        seat=seat,
        nonce="dispatch-model-nonce",
    )
    journal_row["executionEvidence"] = journal_evidence
    ctx, _ = RC._load_context(
        write_certifiable_session(
            tmp_path,
            journal_lines=[journal_row],
            envelopes=[
                {
                    "seat": seat,
                    "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                    "executionEvidence": _envelope_execution_evidence_from_journal(
                        journal_evidence
                    ),
                }
            ],
        )
    )
    row = RC._collect_seats(ctx)[0]
    assert row["model"] is None


def _forbidden_driver_module_names():
    # Built from pieces so this test's own source does not trip the constant census.
    return ("round_" + "driver", "test_round_" + "driver_integration")


def _driver_import_census(path):
    import ast

    forbidden = _forbidden_driver_module_names()
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=path)
    saw_import = False
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            saw_import = True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden or any(part in forbidden for part in alias.name.split(".")):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module in forbidden
                or any(part in forbidden for part in node.module.split("."))
            ):
                violations.append(node.module)
            for alias in node.names:
                if alias.name in forbidden:
                    violations.append(alias.name)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("import_module", "__import__"):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value in forbidden:
                            violations.append(arg.value)
            elif isinstance(func, ast.Attribute) and func.attr in (
                "import_module", "spec_from_file_location",
            ):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value in forbidden:
                            violations.append(arg.value)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(name in node.value for name in forbidden):
                violations.append(node.value)
    return saw_import, violations


def test_driver_import_census_rejects_qualified_from_import(tmp_path):
    probe = tmp_path / "probe_import.py"
    driver_name = "round_" + "driver"
    probe.write_text(
        "from plugins.superheroes.lib import %s\n" % driver_name,
        encoding="utf-8",
    )
    saw_import, violations = _driver_import_census(str(probe))
    assert saw_import
    assert violations, "qualified from-import must be flagged"


# axis: writer-side tests and fixtures never import or name the round driver at any depth.
def _writer_module_import_snippet():
    import ast

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "test_round_certification.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=path)
    stdlib = frozenset(sys.builtin_module_names) | frozenset((
        "ast", "base64", "hashlib", "json", "os", "re", "subprocess", "tempfile",
    ))
    chunks = []
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".")[0] for alias in node.names]
        else:
            roots = [node.module.split(".")[0]] if node.module else []
        if any(root == "pytest" for root in roots):
            continue
        if roots and all(root in stdlib for root in roots):
            continue
        segment = ast.get_source_segment(source, node)
        if segment:
            chunks.append(segment.strip())
    return "\n".join(chunks)


def test_writer_tests_run_with_no_driver():
    here = os.path.dirname(os.path.abspath(__file__))
    targets = (
        os.path.join(here, "test_round_certification.py"),
        os.path.join(here, "round_certification_fixtures.py"),
    )
    for path in targets:
        saw_import, violations = _driver_import_census(path)
        assert saw_import, "census must parse imports in %s" % path
        assert not violations, "forbidden driver reference in %s: %s" % (path, violations)
    lib_dir = os.path.dirname(here)
    tests_dir = here
    snippet = """
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
%s
_forbidden = ("round_" + "driver", "test_round_" + "driver_integration")
for _name in list(sys.modules):
    if _name.split(".")[-1] in _forbidden:
        raise AssertionError("forbidden driver module loaded: " + _name)
""" % (lib_dir, tests_dir, _writer_module_import_snippet())
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_certify_clean_session_returns_receipt(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt is not None
    assert receipt["terminalState"] == "certified"
    assert receipt["terminalCause"] is None
    assert receipt["verdict"] == "converged"
    assert receipt["seats"][0]["provenance"] == "dispatch-observed"


def test_absent_session_dir_refuses(tmp_path):
    missing = str(tmp_path / "missing")
    receipt, refusal = RC.certify(missing)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"


def test_unreadable_loop_state_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    path = os.path.join(session_dir, RC.STATE_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.STATE_FILE


def test_missing_loop_state_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    os.remove(os.path.join(session_dir, RC.STATE_FILE))
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["artifact"] == RC.STATE_FILE


def test_absent_journal_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    os.remove(os.path.join(session_dir, RC.JOURNAL_FILE))
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FILE


def test_unreadable_journal_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    os.remove(path)
    os.mkdir(path)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FILE


def test_journal_corrupt_line_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"cmd":"ok"}\n')
        fh.write("not-json\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FILE
    assert "line 2" in refusal["detail"]


def test_journal_blank_lines_only_does_not_certify_claimed_seats(tmp_path):
    session_dir = write_session(tmp_path, envelopes=[])
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal is not None


def test_unknown_verdict_refuses(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={"terminal": "mystery-verdict"},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert "mystery-verdict" in refusal["detail"]


def test_unmapped_provenance_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "orchestrator-fulfilled",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "executionEvidence": {"read": "engaged", "source": "runner"},
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"


def test_seat_opened_never_closed_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "advance",
                "outcome": "opened",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "roster": [{"seat": "code-reviewer", "occurrence": 0}],
            }
        ],
        envelopes=[],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == RC.JOURNAL_FILE


# --- check_unrun_review -------------------------------------------------------

def test_check_unrun_review_dispatch_observed_clean_passes(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


def test_check_unrun_review_dispatch_observed_missing_telemetry_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == "code-reviewer"


def test_check_unrun_review_stale_head_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _dispatch_journal_with_binding(head_sha="b" * 40),
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"


def test_check_evidence_head_bound_absent_cited_head_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _dispatch_journal_with_binding(head_sha=None),
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_evidence_head_bound(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == "code-reviewer"
    assert (
        refusal["bindingFailure"]
        == RC.BINDING_FAILURE_EXECUTION_EVIDENCE_HEAD_UNBOUND
    )


def test_check_evidence_head_bound_unresolvable_certified_head_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        meta={"headSha": None},
        state={
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
            },
        },
        journal_lines=[_dispatch_journal_with_binding()],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_evidence_head_bound(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == RC.META_FILE
    assert (
        refusal["bindingFailure"]
        == RC.BINDING_FAILURE_CERTIFIED_HEAD_UNRESOLVABLE
    )


def test_check_unrun_review_hand_landed_clean_passes(tmp_path):
    evidence = {
        **_binding_fields("hand-nonce", result_digest=DEFAULT_FINDINGS_RESULT_SHA),
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    session_dir = write_session(
        tmp_path,
        journal_lines=[_hand_landed_binding_journal_row("code-reviewer", DEFAULT_PANEL_PAYLOAD_SHA, evidence)],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "provenance": "hand-landed",
                "executionEvidence": evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


# --- check_same_family_seat ---------------------------------------------------

def test_check_same_family_seat_clean_passes(tmp_path):
    session_dir = write_session(tmp_path)
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_same_family_seat(ctx) is None


def test_check_same_family_seat_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "claude", "model": "sonnet-5"}},
                        "degradations": [
                            {
                                "constraint": "same-family",
                                "seat": "code-reviewer",
                            }
                        ],
                    },
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


def test_maker_author_family_matches_registry_for_each_vendor(tmp_path):
    session_dir = write_session(tmp_path)
    for vendor in model_registry.VENDORS:
        ctx, _ = RC._load_context(session_dir)
        ctx["state"]["config"]["fixerVendor"] = vendor
        assert RC.maker_author_family(ctx["state"]) == model_registry.family_for(
            "code-fixer", vendor
        )


@pytest.mark.parametrize("with_seats_entry", [False, True])
def test_same_family_declared_degradation_refuses(tmp_path, with_seats_entry):
    seat_map = {
        "degradations": [
            {
                "constraint": "same-family",
                "seat": "code-reviewer",
            }
        ],
    }
    if with_seats_entry:
        seat_map["seats"] = {"code-reviewer": {"vendor": "claude", "model": "sonnet-5"}}
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": seat_map,
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


@pytest.mark.parametrize(
    "vendor",
    [pytest.param(None, id="missing"), pytest.param("", id="empty"), pytest.param(42, id="not-string")],
)
def test_same_family_declared_degradation_refuses_malformed_vendor(tmp_path, vendor):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": vendor, "model": "sonnet-5"}},
                        "degradations": [
                            {
                                "constraint": "same-family",
                                "seat": "code-reviewer",
                            }
                        ],
                    },
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


def test_same_family_unresolvable_without_degradations_refuses(tmp_path):
    unknown_vendor = "not-a-registered-vendor"
    session_dir = write_session(
        tmp_path,
        state={
            "config": {"fixerVendor": unknown_vendor},
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {
                            "code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"},
                        },
                    },
                }
            ],
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert unknown_vendor in refusal["detail"]


def test_same_family_unresolvable_maker_family_refuses(tmp_path):
    unknown_vendor = "not-a-registered-vendor"
    session_dir = write_session(
        tmp_path,
        state={
            "config": {"fixerVendor": unknown_vendor},
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "degradations": [
                            {
                                "constraint": "same-family",
                                "seat": "code-reviewer",
                            }
                        ],
                    },
                }
            ],
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == "seatMapReceipts/1"
    assert unknown_vendor in refusal["detail"]


def test_same_family_additive_undeclared_matching_family_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {
                            "code-reviewer": {"vendor": "claude", "model": "sonnet-5"},
                        },
                    },
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


# --- check_unfetched_findings -------------------------------------------------

def test_check_unfetched_findings_clean_passes(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unfetched_findings(ctx) is None


def test_check_unfetched_findings_missing_envelope_refuses(tmp_path):
    session_dir = write_session(tmp_path, envelopes=[])
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"


def test_check_unfetched_findings_journal_mismatch_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "wrong-hash",
                "executionEvidence": {"read": "engaged", "source": "runner"},
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["bindingFailure"] == "journal-envelope-mismatch"


# --- check_disposition_without_receipt ------------------------------------------

def test_check_disposition_without_receipt_clean_passes(tmp_path):
    session_dir = write_certifiable_session(tmp_path)
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_disposition_without_receipt(ctx) is None


def test_check_disposition_without_receipt_base_guard_not_checked_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"config": {"fixerVendor": "claude", "baseGuard": "not-checked", "headSha": HEAD}},
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "base-guard-not-checked"


def test_check_disposition_without_receipt_fixed_missing_receipt_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F1",
                    "severity": "Important",
                    "disposition": "fixed",
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "F1"


@pytest.mark.parametrize(
    "verify_result",
    [None, "fail", "timeout", "unknown"],
)
def test_check_disposition_without_receipt_fixed_non_pass_verify_refuses(
    tmp_path, verify_result
):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F1",
                    "file": "a.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(
                        verifyResult=verify_result,
                    ),
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "verify-not-pass"
    assert refusal["artifact"] == "F1"


def test_check_disposition_without_receipt_critical_out_of_scope_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "C1",
                    "severity": "Critical",
                    "disposition": "out-of-scope",
                    "outOfScopeReason": "accepted risk",
                    "followUp": {
                        "revisitTrigger": "milestone M",
                        "classClosure": "none",
                    },
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "C1"


def test_check_disposition_without_receipt_missing_revisit_trigger_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "I1",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "outOfScopeReason": "deferred",
                    "followUp": {"classClosure": "tracked in issue-99"},
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["bindingFailure"] == "missing-revisit-trigger"


def test_check_disposition_without_receipt_missing_class_closure_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "I1",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "outOfScopeReason": "deferred",
                    "followUp": {"revisitTrigger": "2026-12-01"},
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["bindingFailure"] == "missing-class-closure"


def test_check_disposition_without_receipt_refuted_missing_reason_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {"id": "R1", "severity": "Minor", "disposition": "refuted"},
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"


def test_check_disposition_without_receipt_unknown_disposition_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "U1",
                    "severity": "Important",
                    "disposition": "maybe",
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "U1"
    assert refusal["detail"] == "unknown disposition 'maybe'"


def test_check_disposition_without_receipt_missing_disposition_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "N1",
                    "severity": "Important",
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "N1"
    assert refusal["detail"] == "finding has no disposition recorded"


# --- totality tables ----------------------------------------------------------

def test_verdict_totality_covers_certified_verdicts():
    for verdict in RC.CERTIFIED_VERDICTS:
        assert RC.map_verdict_to_terminal_state(verdict) is not None


def test_verdict_totality_unknown_refuses():
    assert RC.map_verdict_to_terminal_state("not-a-verdict") is None


def test_terminal_cause_known_converged_is_none():
    assert RC.map_terminal_cause("converged", "converged") is None


def test_terminal_cause_unknown_combination_refuses():
    assert RC.map_terminal_cause("converged", "verify-fail") is None
    assert RC.map_terminal_cause("halted", "converged") is None


def test_resolve_terminal_certified_rejects_unlisted_decision_key(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "terminal": "converged",
            "decisions": [{"round": 1, "kind": "verify-fail", "detail": "verify failed"}],
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert "verify-fail" in refusal["detail"]


def test_certified_receipt_projects_disposition_and_proof(tmp_path):
    """Refuted disposition proof is the recorded reason, not a fix-content dict."""
    fix_content_receipt = {"headSha": HEAD, "verifyResult": "pass"}
    expected_reason = "Intentional behavior confirmed during review."
    refuted_finding = {
        "id": "F1",
        "file": "a.py",
        "line": 1,
        "title": "issue",
        "severity": "Minor",
        "disposition": "refuted",
        "refutedReason": expected_reason,
        "dispositionReceipt": fix_content_receipt,
    }
    session_dir = write_certifiable_session(
        tmp_path,
        state={"findings": [refuted_finding]},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    finding = receipt["findings"][0]
    assert finding["disposition"] == "refuted"
    assert finding["dispositionReceipt"] == expected_reason
    assert finding["dispositionReceipt"] != fix_content_receipt
    assert not isinstance(finding["dispositionReceipt"], dict)


def test_journal_evidence_scoped_by_round_refuses_cross_round_substitution(tmp_path):
    import round_records as RR

    round1_payload = {"findings": [], "round": 1}
    round2_payload = {"findings": [], "round": 2}
    round1_sha = RR.payload_sha256(round1_payload)
    round2_sha = RR.payload_sha256(round2_payload)
    session_dir = write_session(
        tmp_path,
        state={
            "round": 2,
            "terminal": "converged",
            "decisions": [{"round": 2, "kind": "converged", "detail": "certified"}],
            "findings": [
                {
                    "id": "F1",
                    "file": "a.py",
                    "severity": "Minor",
                    "disposition": "refuted",
                    "dispositionReceipt": {"headSha": HEAD, "verifyResult": "pass"},
                }
            ],
        },
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": RC.PANEL_PHASE,
                "round": 2,
                "attempt": 0,
                "seat": "code-reviewer",
                "occurrence": 0,
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": round2_sha,
                "executionEvidence": _dispatch_journal_with_binding(
                    payload_sha=round2_sha, nonce="round2-nonce"
                )["executionEvidence"],
                "recordIdentity": {
                    "phase": RC.PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            },
            _dispatch_journal_with_binding(payload_sha=round1_sha, nonce="round1-nonce"),
        ],
        envelopes=[
            {
                "round": 2,
                "seat": "code-reviewer",
                "payload": round1_payload,
                "payloadSha256": round1_sha,
            },
        ],
    )
    _write_head_content_blobs(
        session_dir,
        {"schema": "head-content-blobs/2", "headSha": HEAD, "files": {}, "reads": []},
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert "journal payload hash disagrees" in refusal["detail"]


def test_important_out_of_scope_disclosure_is_case_insensitive(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "I1",
                    "severity": "important",
                    "disposition": "out-of-scope",
                    "outOfScopeReason": "follow-on work",
                    "followUp": {
                        "revisitTrigger": "next release",
                        "classClosure": "deferred to platform team",
                    },
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt["disclosures"]["importantOutOfScope"] == [
        {
            "id": "I1",
            "title": None,
            "severity": "important",
            "reason": "follow-on work",
        }
    ]


def test_fixed_disposition_missing_fix_commit_row_uses_missing_token(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-missing",
                    "file": "src/absent.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(),
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_head_content_blobs(
        session_dir,
        {"schema": "head-content-blobs/2", "headSha": HEAD, "files": {}, "reads": []},
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-missing"


def test_bite_same_family_unresolvable_refuses(tmp_path):
    unknown_vendor = "not-a-registered-vendor"
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "config": {"fixerVendor": unknown_vendor},
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {
                            "code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"},
                        },
                    },
                }
            ],
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal is not None
    assert refusal["class"] == "unfetched-findings"


def test_seat_provenance_totality_maps_receipt_values():
    assert RC.map_seat_provenance("dispatch-observed") == "dispatch-observed"
    assert RC.map_seat_provenance("hand-landed") == "hand-landed"


def test_seat_provenance_orchestrator_fulfilled_refuses():
    assert RC.map_seat_provenance("orchestrator-fulfilled") is None


def test_certification_shape_matrix():
    state = {"certification": {"shape": "custom-shape"}}
    seats_dispatch = [{"provenance": "dispatch-observed"}]
    assert RC._certification_shape(state, seats_dispatch) == "custom-shape"

    state_full = {"certification": {"shape": "full-panel-confirmed"}}
    seats_hand = [{"provenance": "hand-landed"}]
    assert RC._certification_shape(state_full, seats_hand) == "audited-chain"

    state_none = {"certification": {"shape": None}}
    assert RC._certification_shape(state_none, seats_hand) == "audited-chain"

    state_other = {"certification": {"shape": "custom-shape"}}
    assert RC._certification_shape(state_other, seats_hand) == "custom-shape"


def test_hand_landed_forces_audited_chain_shape(tmp_path):
    evidence = {
        **_binding_fields("hand-shape-nonce"),
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    session_dir = write_session(
        tmp_path,
        state={
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
            },
            "findings": [],
        },
        journal_lines=[_hand_landed_binding_journal_row("code-reviewer", DEFAULT_PANEL_PAYLOAD_SHA, evidence)],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "provenance": "hand-landed",
                "executionEvidence": evidence,
            }
        ],
    )
    _write_head_content_blobs(
        session_dir,
        {"schema": "head-content-blobs/2", "headSha": HEAD, "files": {}, "reads": []},
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt["certificationShape"] == "audited-chain"


# --- bite-proof targets (neutralization lives in test, detector unedited) -----

def test_bite_unrun_review_dispatch_telemetry_removed_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_bite_same_family_seat_degradation_refuses(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "claude"}},
                        "degradations": [{"constraint": "same-family", "seat": "code-reviewer"}],
                    },
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "same-family-seat"


def test_bite_unfetched_findings_open_seat_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _dispatch_journal_with_binding(seat="code-reviewer"),
            {
                "cmd": "next",
                "outcome": "opened",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "security-reviewer",
            },
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == "security-reviewer"


def test_bite_disposition_without_receipt_base_guard_refuses(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={"config": {"fixerVendor": "claude", "baseGuard": "not-checked", "headSha": HEAD}},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "disposition-without-receipt"


# --- producer meta cannot bypass escape-class checks (#1271 WO-L2-I) ------------

def _meta_bypass_session(tmp_path, *, state=None, journal_lines=None, envelopes=None, meta=None):
    return write_session(
        tmp_path,
        name="meta-bypass",
        state=state,
        journal_lines=journal_lines,
        envelopes=envelopes,
        meta=dict(meta or {}, producer="run-loop"),
    )


def test_meta_producer_cannot_bypass_unrun_review(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_meta_producer_cannot_bypass_same_family_seat(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        name="meta-bypass",
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "claude"}},
                        "degradations": [{"constraint": "same-family", "seat": "code-reviewer"}],
                    },
                }
            ]
        },
        meta={"producer": "run-loop"},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "same-family-seat"


def test_meta_producer_cannot_bypass_unfetched_findings(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "next",
                "outcome": "opened",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "security-reviewer",
            }
        ],
        envelopes=[],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_meta_producer_cannot_bypass_disposition_without_receipt(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        name="meta-bypass",
        state={"config": {"fixerVendor": "claude", "baseGuard": "not-checked", "headSha": HEAD}},
        meta={"producer": "run-loop"},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "disposition-without-receipt"


def test_meta_producer_arbitrary_key_cannot_bypass_unrun_review(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        meta={"producer": "run-loop", "mode": "pr", "bypassToken": "anything"},
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_fixed_disposition_fix_still_present_at_head_certifies(tmp_path):
    content = b"fix still present\n"
    row, digest = _head_content_read_row("src/guard.py", content)
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-present",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(
                        fixContentDigest=digest,
                    ),
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="panel-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    _write_head_content_blobs(
        session_dir,
        {
            "schema": "head-content-blobs/2",
            "headSha": HEAD,
            "files": {"src/guard.py": base64.b64encode(content).decode("ascii")},
            "reads": [row],
        },
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_disposition_without_receipt(ctx) is None


def test_fixed_disposition_missing_head_content_blobs_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-missing-blobs",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": {"headSha": HEAD, "verifyResult": "pass"},
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="panel-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-missing"


def test_fixed_disposition_fix_content_unreadable_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-unreadable",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(),
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="panel-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    path = os.path.join(session_dir, RC.HEAD_CONTENT_BLOBS_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-unreadable"


def test_fixed_disposition_legacy_head_content_blob_refuses_schema_unsupported(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-legacy",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(),
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="panel-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    _write_head_content_blobs(
        session_dir,
        {
            "headSha": HEAD,
            "files": {"src/guard.py": "fix present\n"},
            "fixCommits": [
                {"headSha": HEAD, "path": "src/guard.py", "present": True},
            ],
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-schema-unsupported"


def test_fixed_disposition_missing_fix_content_digest_refuses(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-no-digest",
                    "file": "a.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": {"headSha": HEAD, "verifyResult": "pass"},
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-reverted"


def test_fixed_disposition_fix_content_digest_mismatch_refuses(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-digest-mismatch",
                    "file": "a.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(
                        fixContentDigest="0" * 64,
                    ),
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-reverted"


def test_fixed_disposition_malformed_base64_in_blob_refuses(tmp_path):
    row, digest = _head_content_read_row("src/guard.py", b"claimed bytes\n")
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-bad-b64",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(
                        fixContentDigest=digest,
                    ),
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="panel-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    _write_head_content_blobs(
        session_dir,
        {
            "schema": "head-content-blobs/2",
            "headSha": HEAD,
            "files": {"src/guard.py": "!!!not-base64!!!"},
            "reads": [row],
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "fix-content-unreadable"


def test_bite_fix_content_bytes_digest_mismatch_refuses(tmp_path):
    """Fabricated blob: reads row digest does not match files[path] bytes (WO-A3 step 8)."""
    claimed_digest = hashlib.sha256(b"claimed content\n").hexdigest()
    planted_bytes = b"different planted bytes\n"
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-fabricated",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": _fix_content_disposition_receipt(
                        fixContentDigest=claimed_digest,
                    ),
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="panel-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    _write_head_content_blobs(
        session_dir,
        {
            "schema": "head-content-blobs/2",
            "headSha": HEAD,
            "files": {
                "src/guard.py": base64.b64encode(planted_bytes).decode("ascii"),
            },
            "reads": [
                {
                    "headSha": HEAD,
                    "path": "src/guard.py",
                    "contentDigest": claimed_digest,
                    "bytes": len(planted_bytes),
                    "readAt": "2026-01-01T00:00:00Z",
                    "source": "git-show",
                    "readError": None,
                }
            ],
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "fix-content-reverted"


def test_hand_landed_journal_recorded_runner_nonce_certifies(tmp_path):
    evidence = {
        "source": "runner",
        "runnerNonce": "journal-nonce",
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
    payload = {"findings": []}
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_sha, evidence)
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


def test_hand_landed_unrecorded_runner_nonce_refuses(tmp_path):
    evidence = {
        "source": "runner",
        "runnerNonce": "minted-nonce",
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
    journal_evidence = dict(evidence)
    journal_evidence["runnerNonce"] = "journal-nonce"
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_sha, journal_evidence)
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-dispatch-unrecorded"


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


def _hand_landed_envelope(evidence, payload, *, order_sha="f" * 64):
    return {
        "orderSha256": order_sha,
        "payload": payload,
        "executionEvidence": evidence,
    }


def test_hand_landed_write_run_kind_qualifies_without_payload_key():
    evidence = _hand_landed_evidence_binding(
        resultKind=session_contract.WRITE_RESULT_KIND,
        resultDigest=session_contract.payload_sha256(
            {"testFailed": False, "testPassed": True}),
    )
    payload = {"fixes": [{"file": "a.py", "description": "fixed"}]}
    envelope = _hand_landed_envelope(evidence, payload)
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is True
    assert failure == RC.EXECUTION_ONLY_BINDING


def test_hand_landed_review_kind_absent_from_payload_refuses():
    evidence = _hand_landed_evidence_binding(resultKind="findings")
    payload = {"fixes": []}
    envelope = _hand_landed_envelope(evidence, payload)
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is False
    assert failure == "execution-evidence-result-mismatch"


def test_hand_landed_fixer_kind_qualifies_with_matching_digest():
    fixes = [{"file": "a.py", "description": "fixed"}]
    evidence = _hand_landed_evidence_binding(
        resultKind="fixes",
        resultDigest=session_contract.payload_sha256(fixes),
    )
    payload = {"fixes": fixes}
    envelope = _hand_landed_envelope(evidence, payload)
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, failure = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is True
    assert failure is None


def test_hand_landed_journal_digest_mismatch_refuses(tmp_path):
    evidence = {
        "source": "runner",
        "runnerNonce": "journal-nonce",
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
    journal_evidence = dict(evidence)
    journal_evidence["recordDigest"] = "f" * 64
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_sha, journal_evidence)
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-binding-mismatch"


def _hand_landed_findings_envelope(*, observation_overrides=None, evidence_overrides=None):
    findings = [{"id": "f1", "severity": "Minor", "title": "t"}]
    observation = {
        "read": "engaged",
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
    }
    if observation_overrides:
        observation.update(observation_overrides)
    evidence = _hand_landed_evidence_binding(
        resultDigest=session_contract.payload_sha256(findings),
        observation=observation,
    )
    if evidence_overrides:
        evidence.update(evidence_overrides)
    payload = {"findings": findings}
    envelope = _hand_landed_envelope(evidence, payload)
    journal_binding = {
        field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
    }
    return envelope, journal_binding


def test_hand_landed_read_unknown_refuses_not_engaged():
    envelope, _journal_binding = _hand_landed_findings_envelope(
        observation_overrides={"read": "unknown"},
    )
    ok, failure = RC._hand_landed_read_qualifies(envelope["executionEvidence"])
    assert ok is False
    assert failure == "execution-evidence-not-engaged"


def test_hand_landed_read_outside_enum_refuses_invalid():
    envelope, _journal_binding = _hand_landed_findings_envelope(
        observation_overrides={"read": "disengaged"},
    )
    ok, failure = RC._hand_landed_read_qualifies(envelope["executionEvidence"])
    assert ok is False
    assert failure == "execution-evidence-read-invalid"


def test_hand_landed_unknown_observation_field_refuses():
    envelope, _journal_binding = _hand_landed_findings_envelope(
        observation_overrides={"read": "engaged", "bogusField": True},
    )
    ok, failure = RC._hand_landed_read_qualifies(envelope["executionEvidence"])
    assert ok is False
    assert failure == "execution-evidence-unknown-field"


def test_hand_landed_read_engaged_qualifies():
    envelope, _journal_binding = _hand_landed_findings_envelope()
    ok, failure = RC._hand_landed_read_qualifies(envelope["executionEvidence"])
    assert ok is True
    assert failure is None


def test_check_hand_landed_read_engaged_unknown_read_refuses(tmp_path):
    evidence = _hand_landed_evidence_binding(
        observation={
            "read": "unknown",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    )
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_sha, evidence)
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_hand_landed_read_engaged(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-not-engaged"


def _minimal_orders_manifest(*, session_id="test-session-001", rnd=1, phase=RC.PANEL_PHASE, attempt=0):
    return {
        "schema": "orders-manifest/1",
        "session": session_id,
        "round": rnd,
        "phase": phase,
        "attempt": attempt,
        "orders": "not-emitted",
        "seats": {
            "security-reviewer": {
                "storeKey": "security-reviewer",
                "seat": "security-reviewer",
                "occurrence": 0,
                "vendor": "claude",
                "model": "sonnet",
                "engine": "claude",
                "resultContract": "seat-result/2",
                "orderSha256": "a" * 64,
                "orderPath": "/dev/null",
                "envelopeStubPath": "/dev/null",
            },
        },
    }


def _write_orders_manifest(session_dir, manifest):
    path = RC._orders_manifest_path(
        session_dir, manifest["round"], manifest["phase"], manifest["attempt"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = session_contract.canonical(manifest)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return session_contract.sha256_text(text)


def _orders_emitted_journal_row(manifest_sha, *, phase=RC.PANEL_PHASE, rnd=1, attempt=0, cmd="advance"):
    return {
        "cmd": cmd,
        "outcome": "orders-emitted",
        "phase": phase,
        "round": rnd,
        "attempt": attempt,
        "manifestSha256": manifest_sha,
    }


def test_roster_from_orders_emitted_derives_roster(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row(manifest_sha)
    roster = RC._roster_from_orders_emitted(session_dir, event)
    assert roster == [("security-reviewer", 0)]


def test_journal_open_seats_orders_emitted_reports_open_seat(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(
        tmp_path,
        journal_lines=[_orders_emitted_journal_row(manifest_sha)],
    )
    _write_orders_manifest(session_dir, manifest)
    journal, _ = RC._read_jsonl(os.path.join(session_dir, RC.JOURNAL_FILE), RC.JOURNAL_FILE)
    unclosed, refusal = RC._journal_open_seats(journal, session_dir)
    assert refusal is None
    assert len(unclosed) == 1
    key, _event = unclosed[0]
    assert key == (RC.PANEL_PHASE, 1, 0, "security-reviewer", 0)


def test_roster_from_orders_emitted_manifest_sha_mismatch_returns_none(tmp_path):
    manifest = _minimal_orders_manifest()
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row("b" * 64)
    roster = RC._roster_from_orders_emitted(session_dir, event)
    assert roster is None
    unclosed, refusal = RC._journal_open_seats([event], session_dir)
    assert unclosed is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    assert "sha256" in refusal["detail"]


def test_check_unfetched_findings_orders_emitted_manifest_sha_mismatch_refuses(tmp_path):
    manifest = _minimal_orders_manifest()
    session_dir = write_session(
        tmp_path,
        journal_lines=[_orders_emitted_journal_row("b" * 64)],
    )
    _write_orders_manifest(session_dir, manifest)
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    assert "sha256" in refusal["detail"]


def test_check_unfetched_findings_orders_emitted_missing_manifest_sha_refuses(tmp_path):
    manifest = _minimal_orders_manifest()
    session_dir = write_session(
        tmp_path,
        journal_lines=[{
            "cmd": "advance",
            "outcome": "orders-emitted",
            "phase": RC.PANEL_PHASE,
            "round": 1,
            "attempt": 0,
        }],
    )
    _write_orders_manifest(session_dir, manifest)
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    assert refusal["detail"] == (
        "orders-emitted event lacks manifestSha256 integrity field")


def test_check_unfetched_findings_orders_emitted_unreadable_manifest_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[_orders_emitted_journal_row("a" * 64)],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    assert refusal["detail"] == "orders manifest unreadable or malformed"


def test_check_unfetched_findings_orders_emitted_seats_not_dict_refuses(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest["seats"] = []
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(
        tmp_path,
        journal_lines=[_orders_emitted_journal_row(manifest_sha)],
    )
    _write_orders_manifest(session_dir, manifest)
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    assert refusal["detail"] == "orders manifest seats field is not an object"


def test_orders_emitted_roster_refuses_non_object_seat_entry(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest["seats"] = {"bad-entry": "not-an-object"}
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row(manifest_sha)
    manifest_path = RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
    assert roster is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == manifest_path
    assert refusal["detail"] == (
        "orders manifest seat entry 'bad-entry' is not an object")


def test_orders_emitted_roster_refuses_unusable_seat_field(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest["seats"] = {
        "bad-seat": {
            "storeKey": "bad-seat",
            "seat": "",
            "occurrence": 0,
            "vendor": "claude",
            "model": "sonnet",
            "engine": "claude",
            "resultContract": "seat-result/2",
            "orderSha256": "a" * 64,
            "orderPath": "/dev/null",
            "envelopeStubPath": "/dev/null",
        },
    }
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row(manifest_sha)
    manifest_path = RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
    assert roster is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == manifest_path
    assert refusal["detail"] == (
        "orders manifest seat entry 'bad-seat' has unusable seat field")


def test_orders_emitted_roster_refuses_unusable_occurrence(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest["seats"]["security-reviewer"]["occurrence"] = -1
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row(manifest_sha)
    manifest_path = RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
    assert roster is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == manifest_path
    assert refusal["detail"] == (
        "orders manifest seat entry 'security-reviewer' has unusable occurrence")


def test_check_unfetched_findings_orders_emitted_unusable_seat_entry_refuses(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest["seats"] = {"bad-entry": []}
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(
        tmp_path,
        journal_lines=[_orders_emitted_journal_row(manifest_sha)],
    )
    _write_orders_manifest(session_dir, manifest)
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC._orders_manifest_path(
        session_dir, 1, RC.PANEL_PHASE, 0)
    assert refusal["detail"] == (
        "orders manifest seat entry 'bad-entry' is not an object")


def test_roster_from_orders_emitted_authenticated_empty_seats_yields_empty_roster(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest["seats"] = {}
    manifest_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    session_dir = write_session(
        tmp_path,
        journal_lines=[_orders_emitted_journal_row(manifest_sha)],
    )
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row(manifest_sha)
    roster = RC._roster_from_orders_emitted(session_dir, event)
    assert roster == []
    unclosed, refusal = RC._journal_open_seats(
        [_orders_emitted_journal_row(manifest_sha)], session_dir)
    assert refusal is None
    assert unclosed == []
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unfetched_findings(ctx) is None


# --- WO-L2-M: evidence qualifies by proof, never by default -------------------

def test_dispatch_observed_missing_runner_nonce_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"findings": []},
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": RC.PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "executionEvidence": {
                    "read": "engaged",
                    "source": "runner",
                    "telemetry": "tool-calls",
                    "stdoutBytes": 10,
                    "wallSeconds": 1.0,
                },
                "recordIdentity": {
                    "phase": RC.PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-binding-incomplete"


def test_dispatch_observed_matching_runner_nonce_certifies(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        state={"findings": []},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


def test_dispatch_observed_unrecorded_journal_binding_refuses(tmp_path):
    envelope_evidence = {
        **_binding_fields("orphan-nonce"),
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        state={"findings": []},
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": RC.PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "payloadSha256": payload_sha,
                "recordIdentity": {
                    "phase": RC.PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": envelope_evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-dispatch-unrecorded"


def test_slot_scoped_nonce_same_slot_certifies(tmp_path):
    nonce = "slot-nonce"
    evidence = {
        **_binding_fields(nonce),
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    session_dir = write_session(
        tmp_path,
        state={"findings": []},
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_sha, evidence)
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence,
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


def _plain_hand_landed_journal_row(seat, payload_sha):
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": RC.PANEL_PHASE,
        "round": 1,
        "attempt": 0,
        "seat": seat,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": payload_sha,
        "recordIdentity": {
            "phase": RC.PANEL_PHASE,
            "seat": seat,
            "occurrence": 0,
            "attempt": 0,
        },
    }


def test_slot_scoped_nonce_different_slot_refuses(tmp_path):
    borrowed_nonce = "shared-nonce"
    evidence_a = {
        **_binding_fields(borrowed_nonce),
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    evidence_b = dict(evidence_a)
    payload_a = "sha-a"
    payload_b = "sha-b"
    session_dir = write_session(
        tmp_path,
        state={"findings": []},
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_a, evidence_a),
            _plain_hand_landed_journal_row("security-reviewer", payload_b),
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_a,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence_a,
            },
            {
                "seat": "security-reviewer",
                "payloadSha256": payload_b,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence_b,
            },
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-dispatch-unrecorded"


@pytest.mark.parametrize("helper_name", QUALIFICATION_HELPER_CENSUS)
def test_qualification_helpers_refuse_empty_or_absent_evidence(tmp_path, helper_name):
    if helper_name == "_execution_binding_matches_journal":
        ok, failure = RC._execution_binding_matches_journal(None, None, set())
        assert not ok
        assert failure
        ok, failure = RC._execution_binding_matches_journal({}, None, set())
        assert not ok
        assert failure
    elif helper_name == "_observation_qualifies":
        ok, failure = RC._observation_qualifies(None, HEAD, None)
        assert not ok
        assert failure
        ok, failure = RC._observation_qualifies({}, HEAD, None)
        assert not ok
        assert failure
    elif helper_name == "_hand_landed_evidence_qualifies":
        ok, failure = RC._hand_landed_evidence_qualifies({}, HEAD)
        assert not ok
        assert failure
        ok, failure = RC._hand_landed_evidence_qualifies({"executionEvidence": None}, HEAD)
        assert not ok
        assert failure
    elif helper_name == "_fix_still_present_at_head":
        session_dir = write_session(tmp_path, state={"findings": []})
        ctx, _ = RC._load_context(session_dir)
        finding = {
            "id": "F-empty",
            "file": "src/missing.py",
            "disposition": "fixed",
        }
        receipt = {"headSha": HEAD}
        refusal = RC._fix_still_present_at_head(ctx, finding, receipt)
        assert refusal is not None
        assert refusal["bindingFailure"] == "fix-content-missing"
    else:
        pytest.fail("uncovered qualification helper in census: %s" % helper_name)


def test_bite_fix_content_missing_blobs_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F-bite",
                    "file": "src/guard.py",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": {"headSha": HEAD, "verifyResult": "pass"},
                }
            ]
        },
        journal_lines=[_dispatch_journal_with_binding(payload_sha="panel-sha", nonce="bite-nonce")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "fix-content-missing"


def test_bite_dispatch_observed_binding_always_runs_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"findings": []},
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": RC.PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
                "executionEvidence": {
                    "read": "engaged",
                    "source": "runner",
                    "telemetry": "tool-calls",
                    "stdoutBytes": 10,
                    "wallSeconds": 1.0,
                },
                "recordIdentity": {
                    "phase": RC.PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_bite_slot_scoped_nonce_refuses_cross_slot(tmp_path):
    import round_records as RR

    borrowed_nonce = "cross-slot-nonce"
    evidence_a = {
        **_binding_fields(borrowed_nonce),
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    evidence_b = dict(evidence_a)
    payload_a = RR.payload_sha256({"findings": [], "seat": "code-reviewer"})
    payload_b = RR.payload_sha256({"findings": [], "seat": "security-reviewer"})
    session_dir = write_session(
        tmp_path,
        state={"findings": []},
        journal_lines=[
            _hand_landed_binding_journal_row("code-reviewer", payload_a, evidence_a),
            _plain_hand_landed_journal_row("security-reviewer", payload_b),
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payload": {"findings": [], "seat": "code-reviewer"},
                "payloadSha256": payload_a,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence_a,
            },
            {
                "seat": "security-reviewer",
                "payload": {"findings": [], "seat": "security-reviewer"},
                "payloadSha256": payload_b,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "executionEvidence": evidence_b,
            },
        ],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-dispatch-unrecorded"


@pytest.mark.parametrize(
    "label,builder,expect",
    MUST_REFUSE_FIXTURES,
    ids=[label for label, _, _ in MUST_REFUSE_FIXTURES],
)
def test_must_refuse_fixtures_keep_refusal_reason(tmp_path, label, builder, expect):
    session_dir = builder(tmp_path)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None, label
    assert refusal is not None, label
    if "class_" in expect:
        assert refusal["class"] == expect["class_"], label
    if "class_in" in expect:
        assert refusal["class"] in expect["class_in"], label
    if expect.get("artifact_required"):
        assert refusal.get("artifact"), label
    if "artifact" in expect:
        assert refusal["artifact"] == expect["artifact"], label
    if "binding_failure" in expect:
        assert refusal.get("bindingFailure") == expect["binding_failure"], label


# --- WO-R1-A fixes -------------------------------------------------------------

def test_journal_fault_marker_refuses_certification(tmp_path):
    session_dir = write_certifiable_session(tmp_path)
    fault_path = os.path.join(session_dir, RC.JOURNAL_FAULT_FILE)
    with open(fault_path, "w", encoding="utf-8") as fh:
        fh.write('{"cmd":"submit","phase":"run-verify","fault":"disk full"}\n')
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FAULT_FILE


def test_journal_fault_marker_malformed_still_refuses(tmp_path):
    session_dir = write_certifiable_session(tmp_path)
    fault_path = os.path.join(session_dir, RC.JOURNAL_FAULT_FILE)
    with open(fault_path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FAULT_FILE


def test_repeated_seat_attempt_observation_is_slot_scoped(tmp_path):
    import round_records as RR

    payload_a = RR.payload_sha256({"findings": [], "attempt": 0})
    payload_b = RR.payload_sha256({"findings": [], "attempt": 1})
    nonce_a = "nonce-a0"
    nonce_b = "nonce-a1"
    session_dir = write_certifiable_session(
        tmp_path,
        journal_lines=[
            _dispatch_journal_with_binding(payload_sha=payload_a, nonce=nonce_a, attempt=0),
            _dispatch_journal_with_binding(payload_sha=payload_b, nonce=nonce_b, attempt=1),
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "attempt": 0,
                "payload": {"findings": [], "attempt": 0},
                "payloadSha256": payload_a,
            },
            {
                "seat": "code-reviewer",
                "attempt": 1,
                "payload": {"findings": [], "attempt": 1},
                "payloadSha256": payload_b,
            },
        ],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["terminalState"] == "certified"


def test_check_unfetched_findings_missing_payload_sha_refuses(tmp_path):
    import round_records as RR

    payload = {"findings": []}
    good_sha = RR.payload_sha256(payload)
    session_dir = write_session(
        tmp_path,
        journal_lines=[_dispatch_journal_with_binding(payload_sha=good_sha)],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": good_sha}],
    )
    path = record_paths.store_path(
        session_dir, 1, RC.PANEL_PHASE, record_paths.storage_key("code-reviewer", 0), 0
    )
    with open(path, encoding="utf-8") as fh:
        env = json.load(fh)
    del env["payloadSha256"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(env, fh, sort_keys=True)
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal is not None
    assert refusal["class"] == "unfetched-findings"
    assert "payloadSha256" in refusal["detail"]


def test_check_unfetched_findings_recomputes_payload_hash_from_content(tmp_path):
    import round_records as RR

    payload = {"findings": []}
    good_sha = RR.payload_sha256(payload)
    stale_sha = "0" * 64
    session_dir = write_session(
        tmp_path,
        journal_lines=[_dispatch_journal_with_binding(payload_sha=stale_sha)],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": stale_sha}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "journal-envelope-mismatch"
    assert good_sha != stale_sha


def test_check_unfetched_findings_seat_missing_schema_exempt_from_payload_hash(tmp_path):
    import round_records as RR

    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": RC.PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "executionEvidence": {
                    "read": "engaged",
                    "source": "runner",
                    "telemetry": "tool-calls",
                    "stdoutBytes": 10,
                    "wallSeconds": 1.0,
                    **_binding_fields("missing-nonce"),
                },
                "recordIdentity": {
                    "phase": RC.PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[],
    )
    path = record_paths.store_path(
        session_dir, 1, RC.PANEL_PHASE, record_paths.storage_key("code-reviewer", 0), 0
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    missing_env = {
        "schema": RR.SEAT_MISSING_SCHEMA,
        "session": "test-session-001",
        "round": 1,
        "phase": RC.PANEL_PHASE,
        "seat": "code-reviewer",
        "attempt": 0,
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "reason": "forfeit",
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(missing_env, fh, sort_keys=True)
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal is None


def test_empty_seat_set_refuses_certification(tmp_path):
    session_dir = write_session(tmp_path, journal_lines=[], envelopes=[])
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == RC.JOURNAL_FILE


def test_seat_map_cannot_bypass_empty_seat_set_refusal(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"}},
                    },
                }
            ]
        },
        journal_lines=[],
        envelopes=[],
    )
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == RC.JOURNAL_FILE
