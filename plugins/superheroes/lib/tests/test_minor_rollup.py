# plugins/superheroes/lib/tests/test_minor_rollup.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import minor_rollup as mr


def test_read_missing_is_empty(tmp_path):
    assert mr.read(str(tmp_path / "nope.json")) == []


def test_append_then_read_roundtrip(tmp_path):
    p = str(tmp_path / "minor.json")
    mr.append(p, [{"file": "a.py", "title": "nit one", "severity": "Minor"}])
    assert len(mr.read(p)) == 1


def test_append_is_idempotent_by_identity(tmp_path):
    p = str(tmp_path / "minor.json")
    f = {"file": "a.py", "title": "nit one", "severity": "Minor"}
    mr.append(p, [f])
    merged = mr.append(p, [f])           # same identity again
    assert len(merged) == 1
