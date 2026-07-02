import json
import os
import subprocess
import sys

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, LIB)
import control_plane


def _run(tmp_path, payload):
    env = {**os.environ, "SUPERHEROES_STORE_ROOT": str(tmp_path / "store")}
    cmd = [
        sys.executable,
        os.path.join(LIB, "phase_progress_entry.py"),
        "save",
        "--work-item", "wi",
        "--step", "2",
        "--phase", "build",
        "--payload", json.dumps(payload),
    ]
    return subprocess.run(cmd, cwd=str(tmp_path), env=env, text=True, capture_output=True, timeout=30)


def test_phase_progress_idempotent_and_read_back_confirmed(tmp_path):
    first = _run(tmp_path, {"phase": "build", "confidence": "high"})
    assert first.returncode == 0, first.stderr
    out1 = json.loads(first.stdout)
    assert out1["ok"] is True
    assert out1["journal_confirmed"] is True
    assert out1["checkpoint_confirmed"] is True
    second = _run(tmp_path, {"phase": "build", "confidence": "high"})
    out2 = json.loads(second.stdout)
    assert out2["ok"] is True
    assert out2["already"] is True
    events = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))["events"]
    lines = open(events, encoding="utf-8").read().splitlines()
    assert len([line for line in lines if '"phase_record"' in line]) == 1


def test_phase_progress_malformed_payload_fails_closed(tmp_path):
    env = {**os.environ, "SUPERHEROES_STORE_ROOT": str(tmp_path / "store")}
    cmd = [
        sys.executable,
        os.path.join(LIB, "phase_progress_entry.py"),
        "save",
        "--work-item", "wi",
        "--step", "2",
        "--phase", "build",
        "--payload", "{",
    ]
    result = subprocess.run(cmd, cwd=str(tmp_path), env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert "malformed" in out["error"]
