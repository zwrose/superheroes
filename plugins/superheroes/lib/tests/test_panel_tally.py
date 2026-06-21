"""Tests for the deterministic review-panel tally (`panel_tally`).

These pin the per-round gate/confidence, the 4-terminal continuation + precedence, the
present-∩-deferred accounting with the severity ceiling, the fail-safe across every read
(never a silent `clean`), and the durable record — all deterministically, no agents.
"""
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PT = _load(os.path.join(_HERE, "..", "panel_tally.py"), "panel_tally")


def _f(file, line, title, severity, dimension="Code", evidence="repro"):
    return {"file": file, "line": line, "title": title, "severity": severity,
            "dimension": dimension, "evidence": evidence}


def test_layout_helpers_compose_run_key_dir():
    assert PT.findings_path("/run", 2, "security").endswith("/run/round-2/findings-security.json")
    assert PT.deferred_set_path("/run").endswith("/run/deferred-set.json")
    assert PT.verdict_path("/run", 3).endswith("/run/round-3/verdict.json")


def test_compile_dedupes_by_location_keeps_higher_severity_unions_dimensions():
    findings = [
        _f("a.py", 10, "Off-by-one", "Minor", "Code"),
        _f("a.py", 10, "Off-by-one", "Important", "Security"),
    ]
    out = PT.compile_findings(findings)
    assert len(out) == 1
    assert out[0]["severity"] == "Important"
    assert "Code" in out[0]["dimension"] and "Security" in out[0]["dimension"]


def test_compile_drops_uncited_and_out_of_context():
    findings = [
        _f("a.py", None, "No line", "Important"),     # citation check
        _f(None, 5, "No file", "Important"),          # citation check
        _f("z.py", 5, "Outside", "Important"),        # out of context
        _f("a.py", 5, "Real", "Important"),
    ]
    out = PT.compile_findings(findings, context_files=["a.py"])
    assert [x["title"] for x in out] == ["Real"]


def test_compile_classifies_tradeoff_as_judgment_else_mechanical():
    j = _f("a.py", 1, "Trade-off call", "Important")
    j["tradeoff"] = True
    m = _f("b.py", 2, "One fix", "Important")
    out = {x["title"]: x for x in PT.compile_findings([j, m])}
    assert out["Trade-off call"]["classification"] == "judgment"
    assert out["One fix"]["classification"] == "mechanical"


def test_round_gate_clean_when_all_complete_no_blockers():
    gate, conf, missing = PT.round_gate([_f("a.py", 1, "nit", "Nit")], ["code", "security"], ["code", "security"])
    assert gate == "clean" and conf == "high" and missing == []


def test_round_gate_blocking_when_blocker_present():
    gate, conf, missing = PT.round_gate([_f("a.py", 1, "bug", "Important")], ["code"], ["code"])
    assert gate == "blocking"


def test_round_gate_cannot_certify_when_a_reviewer_did_not_complete():
    gate, conf, missing = PT.round_gate([], ["code", "security"], ["code"])
    assert gate == "cannot-certify" and conf == "low"


def test_round_gate_names_the_missing_review_angles():
    gate, conf, missing = PT.round_gate([], ["code", "security", "architecture"], ["code"])
    assert missing == ["security", "architecture"]


def test_confidence_low_when_a_finding_lacks_verification_evidence():
    bad = _f("a.py", 1, "bug", "Minor")
    bad["evidence"] = ""
    gate, conf, missing = PT.round_gate([bad], ["code"], ["code"])
    assert conf == "low"


def test_present_deferred_counts_same_identity_same_severity():
    f = _f("a.py", 1, "bug", "Important")
    deferred = {PT._identity(f): "Important"}
    assert PT.present_deferred([f], deferred) == 1


def test_present_deferred_excludes_severity_escalation():
    # deferred at Important; re-flagged at Critical → NOT deferred (severity ceiling)
    f = _f("a.py", 1, "bug", "Critical")
    deferred = {PT._identity(f): "Important"}
    assert PT.present_deferred([f], deferred) == 0


def test_present_deferred_ignores_identities_not_present_this_round():
    f = _f("a.py", 1, "bug", "Important")
    deferred = {"other.py::stale": "Important"}
    assert PT.present_deferred([f], deferred) == 0


def test_present_deferred_excludes_different_issue_at_same_location():
    # deferral is keyed by file::normalized_title, so a DIFFERENT issue at the same file is a
    # new, non-deferred blocker (FR-10) — not silently inheriting the earlier deferral.
    deferred = {PT._identity(_f("a.py", 1, "bug one", "Important")): "Important"}
    other = _f("a.py", 1, "a different bug", "Important")
    assert PT.present_deferred([other], deferred) == 0
