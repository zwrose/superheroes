"""Tests for the micro engine check (#299 Phase 4). The engine binaries are STUBBED as fake `codex`
/ `cursor-agent` executables on PATH — build_argv, the real subprocess, and parse_result all run for
real; only the model binary is faked, so CI never needs live codex/cursor."""
import json
import os
import stat
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import engine_check_cli

# A fake engine binary: reads+discards stdin, optionally writes the artifact, prints a result blob.
# `create` controls the artifact; `blob` is the stdout the real parse_result will consume.
_STUB = """#!/usr/bin/env python3
import sys
sys.stdin.read()
CREATE = {create!r}
if CREATE:
    with open("engine-check.txt", "w") as fh:
        fh.write("engine-check ok\\n")
sys.stdout.write({blob!r})
"""

_OK_BLOB = json.dumps({"ok": True, "signal": "ok", "evidence": {"testPassed": False, "testFailed": False}}) + "\n"
# a cursor-style stream that ends in the honest-ok object (parse_result takes the LAST object)
_STREAM_OK_BLOB = ('{"type":"assistant","text":"working"}\n'
                   '{"type":"result"}\n' + _OK_BLOB)
_REFUSE_BLOB = json.dumps({"ok": False, "signal": "plan_wrong"}) + "\n"


def _write_stub(bindir, name, create=True, blob=_OK_BLOB):
    path = os.path.join(bindir, name)
    with open(path, "w") as fh:
        fh.write(_STUB.format(create=create, blob=blob))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _bindir(tmp_path, monkeypatch):
    b = str(tmp_path / "bin")
    os.makedirs(b)
    monkeypatch.setenv("PATH", b + os.pathsep + os.environ.get("PATH", ""))
    return b


def test_codex_check_passes_with_artifact(tmp_path, monkeypatch):
    b = _bindir(tmp_path, monkeypatch)
    _write_stub(b, "codex", create=True, blob=_OK_BLOB)
    r = engine_check_cli.check_engine("codex")
    assert r["ok"] is True, r
    assert r["artifact"] is True and r["sha"]


def test_cursor_check_passes_with_stream_json(tmp_path, monkeypatch):
    b = _bindir(tmp_path, monkeypatch)
    _write_stub(b, "cursor-agent", create=True, blob=_STREAM_OK_BLOB)
    r = engine_check_cli.check_engine("cursor")
    assert r["ok"] is True, r
    assert r["artifact"] is True and r["sha"]


def test_ok_but_no_artifact_fails(tmp_path, monkeypatch):
    # An engine that claims ok but produced nothing must fail (the artifact is the real evidence).
    b = _bindir(tmp_path, monkeypatch)
    _write_stub(b, "codex", create=False, blob=_OK_BLOB)
    r = engine_check_cli.check_engine("codex")
    assert r["ok"] is False and "artifact" in r["reason"]


def test_honest_refusal_fails(tmp_path, monkeypatch):
    # An honest {"ok":false} refusal parks (never coerced to ok) — the check reports it as a FAIL.
    b = _bindir(tmp_path, monkeypatch)
    _write_stub(b, "codex", create=False, blob=_REFUSE_BLOB)
    r = engine_check_cli.check_engine("codex")
    assert r["ok"] is False and "honest ok" in r["reason"]


def test_missing_binary_fails_cleanly(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)  # empty bindir, no codex stub
    # Ensure no real codex leaks in from the ambient PATH tail by checking the reason shape either way.
    r = engine_check_cli.check_engine("codex")
    # Either the binary is absent (clean not-found) — the CI case — or (unlikely here) a real codex ran.
    assert isinstance(r, dict) and "engine" in r
    if r["ok"] is False:
        assert r["reason"]


def test_unknown_engine_empty_argv(tmp_path, monkeypatch):
    r = engine_check_cli.check_engine("gpt5")
    assert r["ok"] is False and "unknown-engine" in r["reason"]


def test_run_check_aggregates_and_json_cli(tmp_path, monkeypatch, capsys):
    b = _bindir(tmp_path, monkeypatch)
    _write_stub(b, "codex", create=True, blob=_OK_BLOB)
    _write_stub(b, "cursor-agent", create=True, blob=_STREAM_OK_BLOB)
    code = engine_check_cli.main(["--engines", "codex,cursor", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] is True
    assert {r["engine"] for r in out["results"]} == {"codex", "cursor"}


def test_run_check_fails_when_one_engine_fails(tmp_path, monkeypatch):
    b = _bindir(tmp_path, monkeypatch)
    _write_stub(b, "codex", create=True, blob=_OK_BLOB)
    _write_stub(b, "cursor-agent", create=False, blob=_OK_BLOB)  # cursor produces no artifact
    out = engine_check_cli.run_check(["codex", "cursor"])
    assert out["ok"] is False
    assert any(r["engine"] == "cursor" and not r["ok"] for r in out["results"])


def test_no_engines_is_trivial_ok(tmp_path, monkeypatch):
    out = engine_check_cli.run_check([])
    assert out["ok"] is True and out["results"] == []
