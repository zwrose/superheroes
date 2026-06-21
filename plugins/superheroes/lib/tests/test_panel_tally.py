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
