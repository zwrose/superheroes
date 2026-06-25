import importlib.util, json, os
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    path = os.path.join(_HERE, "..", name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MF = _load("merge_findings")


def _f(file, line, title, sev):
    return {"file": file, "line": line, "title": title, "severity": sev, "evidence": "e"}


def test_merge_dedupes_by_identity_keeps_higher_severity(tmp_path):
    rd = tmp_path / "round-1"
    rd.mkdir()
    (rd / "findings-a.json").write_text(json.dumps([_f("x.py", 1, "bug", "Important")]))
    (rd / "findings-b.json").write_text(json.dumps([_f("x.py", 1, "bug", "Critical")]))
    merged = MF.merge(str(tmp_path), 1, ["a", "b"])
    assert len(merged) == 1 and merged[0]["severity"] == "Critical"
    on_disk = json.loads((rd / "merged.json").read_text())
    assert on_disk == merged


def test_merge_failsafe_on_missing_or_malformed(tmp_path):
    rd = tmp_path / "round-1"
    rd.mkdir()
    (rd / "findings-a.json").write_text("{ not json")
    (rd / "findings-b.json").write_text(json.dumps([_f("y.py", 2, "z", "Minor")]))
    merged = MF.merge(str(tmp_path), 1, ["a", "b", "missing"])
    assert len(merged) == 1 and merged[0]["title"] == "z"
