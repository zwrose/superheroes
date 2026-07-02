import json
import os
import subprocess
import sys

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, LIB)
import control_plane


def _run(tmp_path, args):
    env = {**os.environ, "SUPERHEROES_STORE_ROOT": str(tmp_path / "store")}
    cmd = [sys.executable, os.path.join(LIB, "build_state_cli.py"), *args]
    return subprocess.run(cmd, cwd=str(tmp_path), env=env, text=True, capture_output=True, timeout=30)


def _state(tmp_path):
    issue_dir = os.path.join(
        str(tmp_path / "store"),
        "checkouts",
        control_plane.checkout_key(str(tmp_path)),
        "issues",
        "wi",
    )
    path = os.path.join(issue_dir, "build-state.json")
    return json.loads(open(path, encoding="utf-8").read())


def test_record_built_is_read_back_and_idempotent(tmp_path):
    first = _run(tmp_path, ["record-built", "--work-item", "wi", "--task", "1"])
    assert first.returncode == 0, first.stderr
    out1 = json.loads(first.stdout)
    assert out1["ok"] is True
    assert out1["read_back"] is True
    assert out1["task"] == "1"

    second = _run(tmp_path, ["record-built", "--work-item", "wi", "--task", "1"])
    out2 = json.loads(second.stdout)
    assert out2["ok"] is True
    assert out2["already"] is True
    assert out2["read_back"] is True
    st = _state(tmp_path)
    assert list((st.get("built") or {}).keys()) == ["1"]


def test_record_reviewed_is_read_back_and_idempotent(tmp_path):
    first = _run(tmp_path, ["record-reviewed", "--work-item", "wi", "--task", "2"])
    assert first.returncode == 0, first.stderr
    out1 = json.loads(first.stdout)
    assert out1["ok"] is True
    assert out1["read_back"] is True
    assert out1["task"] == "2"

    second = _run(tmp_path, ["record-reviewed", "--work-item", "wi", "--task", "2"])
    out2 = json.loads(second.stdout)
    assert out2["ok"] is True
    assert out2["already"] is True
    st = _state(tmp_path)
    assert list((st.get("reviewed") or {}).keys()) == ["2"]
