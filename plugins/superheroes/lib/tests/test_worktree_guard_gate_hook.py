"""worktree_guard_gate.py — the PreToolUse(Bash) worktree guard hook (#682).

Process contract: the hook classifies only Bash calls, emits a single atomic `deny` JSON for a
destructive discard on a calibrated dirty repo (and for any inspection failure — fail-closed),
stays silent otherwise, and NEVER exits non-zero in normal operation.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest.mock as mock

import mode_registry

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "worktree_guard_gate.py")

_DENY_INSPECT = "superheroes worktree guard: could not inspect this command (fail-closed)"
_DESTRUCTIVE = "git checkout -- f.txt"


def _run_hook(stdin_text):
    return subprocess.run(["python3", _HOOK], input=stdin_text,
                          capture_output=True, text=True, timeout=10)


def _calibrate(cwd):
    """Write a valid registry for cwd under the env-pinned (conftest) store root."""
    rec = mode_registry.write_registry(cwd, mode_registry.IN_REPO, None)
    assert rec is not None, "precondition: registry write landed for %s" % cwd
    return cwd


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _dirty_git_repo(tmp_path):
    """Real git repo with one tracked file holding uncommitted content."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo), "init")
    _git(str(repo), "config", "user.email", "t@example.com")
    _git(str(repo), "config", "user.name", "test")
    f = repo / "f.txt"
    f.write_text("committed\n")
    _git(str(repo), "add", "f.txt")
    _git(str(repo), "commit", "-m", "init")
    f.write_text("PRIOR_UNCOMMITTED_DELIVERY\n")
    return str(repo)


def _clean_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo), "init")
    _git(str(repo), "config", "user.email", "t@example.com")
    _git(str(repo), "config", "user.name", "test")
    f = repo / "f.txt"
    f.write_text("committed\n")
    _git(str(repo), "add", "f.txt")
    _git(str(repo), "commit", "-m", "init")
    return str(repo)


def _run_gate_main(stdin_text, import_hook=None, modules_patch=None):
    patches = []
    if modules_patch is not None:
        patches.append(mock.patch.dict(sys.modules, modules_patch))
    if import_hook is not None:
        patches.append(mock.patch("builtins.__import__", import_hook))

    for p in patches:
        p.start()
    try:
        spec = importlib.util.spec_from_file_location("worktree_guard_gate_test", _HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        try:
            sys.stdin = io.StringIO(stdin_text)
            buf = io.StringIO()
            sys.stdout = buf
            rc = mod.main()
            return rc, buf.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
    finally:
        for p in reversed(patches):
            p.stop()


# --- end-to-end behaviour ----------------------------------------------------

def test_destructive_on_dirty_calibrated_denies(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason != _DENY_INSPECT
    assert "worktree guard" in reason


def test_destructive_on_clean_calibrated_is_silent(tmp_path):
    cwd = _calibrate(_clean_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_destructive_on_uncalibrated_is_silent(tmp_path):
    cwd = _dirty_git_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_ordinary_command_on_dirty_calibrated_is_silent(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": "git commit -m x"}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


# --- fail-closed edges (one test each) ---------------------------------------

def test_edge_01_stdin_empty():
    r = _run_hook("")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_02_stdin_unparseable():
    r = _run_hook("not json {")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_03_stdin_non_object():
    r = _run_hook("[1,2,3]")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_04_tool_name_missing(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    r = _run_hook(json.dumps({"cwd": cwd, "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_edge_05_tool_name_not_bash(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Edit", "cwd": cwd,
                              "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_edge_06_tool_input_missing_or_not_dict(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    for payload in (
        json.dumps({"tool_name": "Bash", "cwd": cwd}),
        json.dumps({"tool_name": "Bash", "cwd": cwd, "tool_input": "bad"}),
    ):
        r = _run_hook(payload)
        assert r.returncode == 0
        out = json.loads(r.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_07_command_not_string(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": None}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_08_worktree_guard_import_fails():
    real_import = __import__

    def fail_wg(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "worktree_guard":
            raise ImportError("simulated import failure")
        return real_import(name, globals, locals, fromlist, level)

    rc, stdout = _run_gate_main(
        json.dumps({"tool_name": "Bash", "cwd": "/tmp", "tool_input": {"command": _DESTRUCTIVE}}),
        import_hook=fail_wg,
    )
    assert rc == 0
    out = json.loads(stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_09_classify_raises(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    payload = json.dumps({"tool_name": "Bash", "cwd": cwd,
                          "tool_input": {"command": _DESTRUCTIVE}})
    fake = mock.MagicMock()
    fake.classify.side_effect = RuntimeError("simulated")
    rc, stdout = _run_gate_main(payload, modules_patch={"worktree_guard": fake})
    assert rc == 0
    out = json.loads(stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_10_classify_allow_silent(tmp_path):
    cwd = _calibrate(_clean_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_edge_11_exit_code_always_zero(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    cases = [
        "",
        "not json",
        json.dumps({"tool_name": "Bash", "cwd": cwd,
                    "tool_input": {"command": _DESTRUCTIVE}}),
        json.dumps({"tool_name": "Edit", "cwd": cwd,
                    "tool_input": {"command": _DESTRUCTIVE}}),
    ]
    for stdin_text in cases:
        r = _run_hook(stdin_text)
        assert r.returncode == 0, "hook must exit 0 on %r" % stdin_text


def test_stdout_is_at_most_one_json_object(tmp_path):
    cwd = _calibrate(_dirty_git_repo(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _DESTRUCTIVE}}))
    assert r.returncode == 0
    text = r.stdout
    if not text.strip():
        return
    decoder = json.JSONDecoder()
    _, end = decoder.raw_decode(text.lstrip())
    assert text.lstrip()[end:].strip() == ""
