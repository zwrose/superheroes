import importlib.util
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = load("definition_doc")


def test_stale_gate_write_refuses_to_touch_doc(tmp_path):
    doc = tmp_path / "tasks.md"
    doc.write_text("---\ngates: {review: changes-requested}\n---\nbody\n", encoding="utf-8")
    result = DD.set_gate(str(doc), "passed", expected_hash="wrong", run_id="run-new")
    assert result == {"ok": False, "reason": "stale"}
    assert "changes-requested" in doc.read_text(encoding="utf-8")


def test_failed_gate_replace_leaves_old_doc(tmp_path, monkeypatch):
    doc = tmp_path / "plan.md"
    doc.write_text("---\ngates: {review: changes-requested}\n---\nbody\n", encoding="utf-8")
    before = DD.content_hash(doc.read_text(encoding="utf-8"))
    monkeypatch.setattr(DD.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")))
    result = DD.set_gate(str(doc), "passed", expected_hash=before, run_id="run-new")
    assert result["ok"] is False
    assert result["reason"] == "replace-failed"
    assert "changes-requested" in doc.read_text(encoding="utf-8")


def test_doc_changed_after_review_snapshot_does_not_pass(tmp_path):
    doc = tmp_path / "tasks.md"
    doc.write_text("---\ngates: {review: changes-requested}\n---\nreviewed\n", encoding="utf-8")
    reviewed_hash = DD.content_hash(doc.read_text(encoding="utf-8"))
    doc.write_text("---\ngates: {review: changes-requested}\n---\nchanged after review\n", encoding="utf-8")
    result = DD.set_gate(str(doc), "passed", expected_hash=reviewed_hash, run_id="run-reviewed")
    assert result == {"ok": False, "reason": "stale"}
    assert "passed" not in doc.read_text(encoding="utf-8")
