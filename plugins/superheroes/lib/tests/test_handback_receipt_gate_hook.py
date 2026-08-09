"""handback_receipt_gate.py — the PreToolUse(Bash) review-receipt gate hook (#624 §4).

Process contract: the hook classifies only Bash calls, emits a single atomic ``deny`` JSON for a
guarded handback in a marked worktree without a valid receipt (and for any inspection failure —
fail-closed), stays silent otherwise, and NEVER exits non-zero in normal operation.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest.mock as mock

import handback_gate as hg

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "handback_receipt_gate.py")

_DENY_INSPECT = "superheroes review-receipt gate: could not inspect this command (fail-closed)"
_READY = "gh pr ready"


def _run_hook(stdin_text):
    return subprocess.run(["python3", _HOOK], input=stdin_text,
                          capture_output=True, text=True, timeout=10)


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(path):
    path = str(path)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True,
                   capture_output=True, text=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "test")
    _git(path, "remote", "add", "origin", "git@github.com:org/repo.git")
    return path


def _commit_file(repo, name, content, msg="init"):
    p = os.path.join(repo, name)
    with open(p, "w") as f:
        f.write(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)


def _superheroes_dir(repo):
    import store_core as sc
    d = os.path.join(sc.get_worktree_gitdir(repo), hg._SIDECAR_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _write_build_lane(repo):
    d = _superheroes_dir(repo)
    obj = {
        "schema": hg.BUILD_LANE_SCHEMA,
        "lane": "full",
        "issue": "#624",
        "declaredAt": "2026-08-09T00:00:00Z",
        "repoRoot": os.path.realpath(repo),
    }
    with open(os.path.join(d, hg.BUILD_LANE_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _marked_repo(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo)
    return repo


def _run_gate_main(stdin_text, import_hook=None, modules_patch=None):
    patches = []
    if modules_patch is not None:
        patches.append(mock.patch.dict(sys.modules, modules_patch))
    if import_hook is not None:
        patches.append(mock.patch("builtins.__import__", import_hook))

    for p in patches:
        p.start()
    try:
        spec = importlib.util.spec_from_file_location("handback_receipt_gate_test", _HOOK)
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

def test_marked_worktree_ready_denies(tmp_path):
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _READY}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason != _DENY_INSPECT
    assert "review-receipt gate" in reason


def test_unmarked_worktree_ready_is_silent(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": repo,
                              "tool_input": {"command": _READY}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_ready_undo_in_marked_worktree_is_silent(tmp_path):
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": "gh pr ready --undo"}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_quoted_gh_pr_ready_is_silent(tmp_path):
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": 'echo "gh pr ready"'}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_ordinary_command_in_marked_worktree_is_silent(tmp_path):
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": "git status"}}))
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
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"cwd": cwd, "tool_input": {"command": _READY}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_edge_05_tool_name_not_bash(tmp_path):
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Edit", "cwd": cwd,
                              "tool_input": {"command": _READY}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_edge_06_tool_input_missing_or_not_dict(tmp_path):
    cwd = _marked_repo(tmp_path)
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
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": None}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_08_handback_gate_import_fails():
    real_import = __import__

    def fail_hg(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "handback_gate":
            raise ImportError("simulated import failure")
        return real_import(name, globals, locals, fromlist, level)

    rc, stdout = _run_gate_main(
        json.dumps({"tool_name": "Bash", "cwd": "/tmp", "tool_input": {"command": _READY}}),
        import_hook=fail_hg,
    )
    assert rc == 0
    out = json.loads(stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_09_validate_handback_raises(tmp_path):
    cwd = _marked_repo(tmp_path)
    payload = json.dumps({"tool_name": "Bash", "cwd": cwd,
                          "tool_input": {"command": _READY}})
    fake = mock.MagicMock()
    fake.validate_handback.side_effect = RuntimeError("simulated")
    rc, stdout = _run_gate_main(payload, modules_patch={"handback_gate": fake})
    assert rc == 0
    out = json.loads(stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == _DENY_INSPECT


def test_edge_10_validate_handback_allow_silent(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": repo,
                              "tool_input": {"command": _READY}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_edge_11_exit_code_always_zero(tmp_path):
    cwd = _marked_repo(tmp_path)
    cases = [
        "",
        "not json",
        json.dumps({"tool_name": "Bash", "cwd": cwd,
                    "tool_input": {"command": _READY}}),
        json.dumps({"tool_name": "Edit", "cwd": cwd,
                    "tool_input": {"command": _READY}}),
    ]
    for stdin_text in cases:
        r = _run_hook(stdin_text)
        assert r.returncode == 0, "hook must exit 0 on %r" % stdin_text


def test_stdout_is_at_most_one_json_object(tmp_path):
    cwd = _marked_repo(tmp_path)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": _READY}}))
    assert r.returncode == 0
    text = r.stdout
    if not text.strip():
        return
    decoder = json.JSONDecoder()
    _, end = decoder.raw_decode(text.lstrip())
    assert text.lstrip()[end:].strip() == ""
