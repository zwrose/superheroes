import json
import os
import subprocess
import sys

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, LIB)
import control_plane


def _run(tmp_path, payload, extra=None):
    env = {**os.environ, "SUPERHEROES_STORE_ROOT": str(tmp_path / "store")}
    cmd = [
        sys.executable,
        os.path.join(LIB, "phase_progress_entry.py"),
        "save",
        "--work-item", "wi",
        "--step", "2",
        "--phase", "build",
        "--payload", json.dumps(payload),
    ] + list(extra or [])
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


def test_phase_progress_journal_only_leaves_checkpoint_untouched(tmp_path):
    # #118 park tail: --journal-only appends the journal record durably but must NOT
    # write the checkpoint cursor (a parked phase did not complete; advancing lastGoodStep
    # would make a resume skip it).
    result = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["journal_confirmed"] is True
    assert "checkpoint_confirmed" not in out
    paths = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))
    lines = open(paths["events"], encoding="utf-8").read().splitlines()
    assert len([line for line in lines if '"phase_record"' in line]) == 1
    assert not os.path.exists(paths["checkpoint"])


def test_phase_progress_journal_only_is_idempotent(tmp_path):
    first = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    assert json.loads(first.stdout)["ok"] is True
    second = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    out2 = json.loads(second.stdout)
    assert out2["ok"] is True
    assert out2["already"] is True
    events = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))["events"]
    lines = open(events, encoding="utf-8").read().splitlines()
    assert len([line for line in lines if '"phase_record"' in line]) == 1


def test_phase_progress_journal_only_then_full_save_advances_cursor(tmp_path):
    # a park journaled with --journal-only followed by a later successful full save (the resume
    # re-ran the phase and proceeded) must land the cursor and keep the journal deduped per payload.
    park = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    assert json.loads(park.stdout)["ok"] is True
    done = _run(tmp_path, {"phase": "build", "gate": "passed"})
    out = json.loads(done.stdout)
    assert out["ok"] is True
    assert out["checkpoint_confirmed"] is True
    assert out["step"] == 2


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
