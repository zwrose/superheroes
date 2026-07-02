import importlib.util
import json
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load():
    spec = importlib.util.spec_from_file_location("fenced_json", os.path.join(LIB, "fenced_json.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FJ = load()


def test_stale_hash_leaves_existing_json_unchanged(tmp_path):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"newer","terminal":"clean"}\n', encoding="utf-8")
    result = FJ.write_record(str(path), {"terminal": "clean"}, expected_hash="wrong", run_id="older")
    assert result == {"ok": False, "reason": "stale"}
    assert json.loads(path.read_text(encoding="utf-8"))["runId"] == "newer"


def test_missing_run_id_does_not_write(tmp_path):
    path = tmp_path / "front-half-outcome.json"
    path.write_text('{"runId":"old","gate":"changes-requested"}\n', encoding="utf-8")
    before = FJ.content_hash(path.read_text(encoding="utf-8"))
    result = FJ.write_record(str(path), {"gate": "passed"}, expected_hash=before, run_id=None)
    assert result == {"ok": False, "reason": "missing-run-id"}
    assert json.loads(path.read_text(encoding="utf-8"))["gate"] == "changes-requested"


def test_missing_expected_hash_does_not_self_satisfy_cas(tmp_path):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"old","terminal":"halt"}\n', encoding="utf-8")
    result = FJ.write_record(str(path), {"terminal": "clean"}, expected_hash=None, run_id="run-new")
    assert result == {"ok": False, "reason": "missing-expected-hash"}
    assert json.loads(path.read_text(encoding="utf-8"))["terminal"] == "halt"


def test_unreadable_current_artifact_leaves_existing_json_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "telemetry-mirror.json"
    path.write_text('{"runId":"old","benchmarkValid":false}\n', encoding="utf-8")
    real_open = FJ.open
    def raising_open(name, *args, **kwargs):
        if os.fspath(name) == os.fspath(path) and "r" in (args[0] if args else kwargs.get("mode", "r")):
            raise OSError("permission denied")
        return real_open(name, *args, **kwargs)
    monkeypatch.setattr(FJ, "open", raising_open)
    result = FJ.write_record(str(path), {"benchmarkValid": True}, expected_hash="ignored", run_id="run-new")
    assert result == {"ok": False, "reason": "unreadable"}
    monkeypatch.setattr(FJ, "open", real_open)
    assert json.loads(path.read_text(encoding="utf-8"))["benchmarkValid"] is False


def test_failed_replace_leaves_existing_json_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"old","terminal":"halt"}\n', encoding="utf-8")
    before = FJ.content_hash(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(FJ.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")))
    result = FJ.write_record(str(path), {"terminal": "clean"}, expected_hash=before, run_id="run-new")
    assert result["ok"] is False
    assert result["reason"] == "replace-failed"
    assert json.loads(path.read_text(encoding="utf-8"))["terminal"] == "halt"


# --- --payload-path: the payload rides a staged FILE, never an inline courier arg ---
# (live 2026-07-02: the inline --payload-json of a large verdict was courier-mangled and
# terminal-record.json was never written).
import subprocess
import sys


def _cli(*args):
    return subprocess.run([sys.executable, os.path.join(LIB, "fenced_json.py"), *args],
                          capture_output=True, text=True)


def test_payload_path_writes_and_cleans_staging(tmp_path):
    path = tmp_path / "terminal-record.json"
    staged = tmp_path / "terminal-record.json.payload"
    payload = {"terminal": "clean", "findings": [{"evidence": "x" * 100000}]}
    staged.write_text(json.dumps(payload), encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--expected-hash", FJ.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["terminal"] == "clean" and written["runId"] == "run-1"
    assert len(written["findings"][0]["evidence"]) == 100000
    assert not staged.exists(), "the staged payload file is consumed (unlinked) on success"


def test_payload_path_missing_fails_closed(tmp_path):
    path = tmp_path / "terminal-record.json"
    r = _cli("write", "--path", str(path), "--payload-path", str(tmp_path / "absent.payload"),
             "--expected-hash", FJ.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert not path.exists()


# --- --payload-hash + --allow-overwrite: the 2-leaf fenced write (D3 fold) ---
# The runtime's stage-write is UNVERIFIED (one leaf); this helper verifies the staged text's
# sha256 itself before applying, folding the old hash read-back leaf into the write.


def test_payload_hash_mismatch_fails_closed_as_payload_corrupt(tmp_path):
    path = tmp_path / "terminal-record.json"
    staged = tmp_path / "terminal-record.json.payload"
    staged.write_text('{"terminal": "clean"}', encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--payload-hash", "0" * 64,
             "--expected-hash", FJ.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out == {"ok": False, "reason": "payload-corrupt"}
    assert not path.exists()
    assert staged.exists(), "a corrupt staged payload is kept for the runtime's retry"


def test_payload_hash_match_writes(tmp_path):
    path = tmp_path / "terminal-record.json"
    staged = tmp_path / "terminal-record.json.payload"
    text = '{"terminal": "clean"}'
    staged.write_text(text, encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--payload-hash", FJ.content_hash(text),
             "--expected-hash", FJ.content_hash(""), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    assert json.loads(path.read_text(encoding="utf-8"))["terminal"] == "clean"


def test_allow_overwrite_replaces_without_expected_hash(tmp_path):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"old","terminal":"halt"}\n', encoding="utf-8")
    staged = tmp_path / "terminal-record.json.payload"
    text = '{"terminal": "clean"}'
    staged.write_text(text, encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--payload-hash", FJ.content_hash(text), "--allow-overwrite", "--run-id", "run-2")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stderr
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["terminal"] == "clean" and written["runId"] == "run-2"


def test_payload_hash_tolerates_one_heredoc_newline(tmp_path):
    """The bundle's leaf-bash writeFile is a heredoc: it puts body+'\\n' on disk, one byte the
    sender's hash never covered. The staged check tolerates exactly that one newline; a second
    one (or any other alteration) still fails."""
    path = tmp_path / "terminal-record.json"
    staged = tmp_path / "terminal-record.json.payload"
    text = '{"terminal": "clean"}'
    staged.write_text(text + "\n", encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--payload-hash", FJ.content_hash(text), "--allow-overwrite", "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out["ok"] is True, r.stdout + r.stderr
    staged.write_text(text + "\n\n", encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--payload-hash", FJ.content_hash(text), "--allow-overwrite", "--run-id", "run-2")
    assert json.loads(r.stdout) == {"ok": False, "reason": "payload-corrupt"}


def test_allow_overwrite_requires_payload_hash(tmp_path):
    """Overwrite mode skips the CAS fence, so the payload self-check is its ONLY integrity
    guard — a courier that drops the --payload-hash pair must fail closed, not fail open."""
    path = tmp_path / "terminal-record.json"
    staged = tmp_path / "terminal-record.json.payload"
    staged.write_text('{"terminal": "clean"}', encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged),
             "--allow-overwrite", "--run-id", "run-1")
    assert json.loads(r.stdout) == {"ok": False, "reason": "payload-hash-required"}
    assert not path.exists()


def test_no_expected_hash_and_no_allow_overwrite_still_refused(tmp_path):
    # the CAS default is unchanged: omitting the fence is an error unless overwrite is explicit
    path = tmp_path / "terminal-record.json"
    staged = tmp_path / "terminal-record.json.payload"
    staged.write_text('{"terminal": "clean"}', encoding="utf-8")
    r = _cli("write", "--path", str(path), "--payload-path", str(staged), "--run-id", "run-1")
    out = json.loads(r.stdout)
    assert out == {"ok": False, "reason": "missing-expected-hash"}
    assert not path.exists()
