import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LS = _load(os.path.join(_HERE, "..", "loop_synthesis.py"), "loop_synthesis")
CB = _load(os.path.join(_HERE, "..", "circuit_breaker.py"), "circuit_breaker")


def _f(file, title, severity):
    return {"file": file, "line": 1, "title": title, "severity": severity}


def test_missing_verdict_keeps_finding_at_original_severity():
    merged = [_f("a.py", "bug", "Important")]
    out = LS.consume(merged, [])  # no leaf verdicts at all
    assert len(out["findings"]) == 1 and out["findings"][0]["severity"] == "Important"
    assert out["drops"] == []


def test_malformed_leaf_output_keeps_everything():
    merged = [_f("a.py", "bug", "Important")]
    out = LS.consume(merged, "not-a-list")
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_clear_drop_with_reason_is_dropped():
    f = _f("a.py", "weak", "Minor")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "does not hold against the code"}
    out = LS.consume([f], [v])
    assert out["findings"] == []
    assert out["drops"][0]["reason"] == "does not hold against the code"
    assert out["drops"][0]["was_blocking_tagged"] is False


def test_drop_without_reason_is_kept_uncertain():
    f = _f("a.py", "weak", "Minor")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": ""}  # no reason -> keep
    out = LS.consume([f], [v])
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_dropped_blocker_is_flagged_distinctly_ufr10():
    f = _f("a.py", "real bug", "Critical")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "stale"}
    out = LS.consume([f], [v])
    assert out["drops"][0]["was_blocking_tagged"] is True


def test_severity_normalized_up_and_down():
    f1 = _f("a.py", "overstated", "Critical")
    f2 = _f("b.py", "understated", "Minor")
    v1 = {"id": CB.finding_identity(f1), "action": "keep", "severity": "Minor"}
    v2 = {"id": CB.finding_identity(f2), "action": "keep", "severity": "Important"}
    out = {x["file"]: x for x in LS.consume([f1, f2], [v1, v2])["findings"]}
    assert out["a.py"]["severity"] == "Minor"      # lowered
    assert out["b.py"]["severity"] == "Important"  # raised


def test_invalid_severity_keeps_original():
    f = _f("a.py", "bug", "Important")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Bogus"}
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Important"
