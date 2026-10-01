"""#1569: the claude write channel runs every sandbox-confined Bash command and leaves no residue.

Invariants: (A) the settings allow Bash if and only if the journaled sandbox froze
`managedPolicyPresent` as the boolean False; (B) that bool is computed once at open, and an
unreadable managed-policy location counts as present; (C) every claude write run that folds has
swept its worktree of empty `.claude/.cc-writes` dirs, and no other run is swept."""
import itertools
import json
import os
import sys

import pytest

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    EA,
    FakeRunner,
    _ClaudeStdoutWriteFakeRunner,
    _build_ok_stdout,
    _claude_write_runner,
    _dispatch_write,
    _ensure_claude_config_dir,
    _implementer_claude_seat,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
)
from test_claude_write_sandbox_1554 import (
    _SANDBOX,
    _assert_sandboxed_shape,
    _claude_seat,
    _settings_of,
)


def _with_policy(value):
    return dict(_SANDBOX, managedPolicyPresent=value)


# --- Invariant A: the settings allow ---------------------------------------------------------


# axis: a False frozen flag emits exactly the Bash allow beside the unchanged deny list.
def test_settings_allow_bash_when_managed_policy_absent():
    obj = json.loads(EA.claude_write_sandbox_settings(_with_policy(False)))
    assert obj["permissions"] == {"allow": ["Bash"], "deny": ["WebFetch", "WebSearch"]}


# axis: an absent, True, or non-bool flag fails closed to no allow.
@pytest.mark.parametrize("sandbox", [
    pytest.param(dict(_SANDBOX), id="absent"),
    pytest.param(_with_policy(True), id="true"),
    pytest.param(_with_policy(None), id="none"),
    pytest.param(_with_policy(0), id="zero"),
    pytest.param(_with_policy("false"), id="string-false"),
])
def test_settings_no_allow_unless_literal_false(sandbox):
    obj = json.loads(EA.claude_write_sandbox_settings(sandbox))
    assert "allow" not in obj["permissions"]
    assert obj["permissions"] == {"deny": ["WebFetch", "WebSearch"]}


# axis: the allow changes nothing about confinement: the sandbox block is identical.
def test_settings_sandbox_block_unchanged_by_allow():
    absent = json.loads(EA.claude_write_sandbox_settings(dict(_SANDBOX)))
    allowed = json.loads(EA.claude_write_sandbox_settings(_with_policy(False)))
    assert allowed["sandbox"] == absent["sandbox"]
    assert allowed["env"] == absent["env"]
    raw = EA.claude_write_sandbox_settings(_with_policy(False))
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))


# axis: the built argv stays the sandboxed shape and carries the allow.
def test_argv_stays_sandboxed_and_carries_allow():
    res = EA.build_argv_result(
        _claude_seat(), "build", {"claudeWriteSandbox": _with_policy(False)})
    assert res["reason"] is None
    _assert_sandboxed_shape(res["argv"])
    assert _settings_of(res["argv"])["permissions"]["allow"] == ["Bash"]


# --- Invariant B: managed-policy presence ----------------------------------------------------


def _patch_locations(monkeypatch, *pairs):
    monkeypatch.setattr(ED, "_managed_policy_locations", lambda: tuple(pairs))


# axis: absent files and dirs are absent.
def test_presence_all_absent(tmp_path, monkeypatch):
    _patch_locations(monkeypatch, (str(tmp_path / "a.json"), "file"), (str(tmp_path / "a.d"), "dir"))
    assert ED._managed_policy_present() is False


# axis: a present file location is present.
def test_presence_file_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.json"
    path.write_text("{}", encoding="utf-8")
    _patch_locations(monkeypatch, (str(path), "file"))
    assert ED._managed_policy_present() is True


# axis: a dangling symlink at a file location is present (E3).
def test_presence_dangling_symlink_is_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.json"
    os.symlink(str(tmp_path / "nowhere"), str(path))
    _patch_locations(monkeypatch, (str(path), "file"))
    assert ED._managed_policy_present() is True


# axis: a directory at a file location is present (E3).
def test_presence_dir_at_file_location_is_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.json"
    path.mkdir()
    _patch_locations(monkeypatch, (str(path), "file"))
    assert ED._managed_policy_present() is True


# axis: a not-a-directory parent is absent (E1).
def test_presence_not_a_directory_parent_is_absent(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    _patch_locations(monkeypatch, (str(blocker / "managed-settings.json"), "file"))
    assert ED._managed_policy_present() is False


# axis: a dir location is absent when missing or empty, present with an entry (E1, E5).
def test_presence_dir_location_states(tmp_path, monkeypatch):
    d = tmp_path / "managed-settings.d"
    _patch_locations(monkeypatch, (str(d), "dir"))
    assert ED._managed_policy_present() is False
    d.mkdir()
    assert ED._managed_policy_present() is False
    (d / "10-policy.json").write_text("{}", encoding="utf-8")
    assert ED._managed_policy_present() is True


# axis: a regular file at a dir location is present (E4).
def test_presence_file_at_dir_location_is_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.d"
    path.write_text("x", encoding="utf-8")
    _patch_locations(monkeypatch, (str(path), "dir"))
    assert ED._managed_policy_present() is True


# axis: an lstat error other than not-found counts as present (E2).
def test_presence_lstat_permission_error_is_present(tmp_path, monkeypatch):
    path = str(tmp_path / "managed-settings.json")
    _patch_locations(monkeypatch, (path, "file"))
    real = os.lstat

    def lstat(p, *a, **k):
        if p == path:
            raise PermissionError(13, "denied")
        return real(p, *a, **k)

    monkeypatch.setattr(ED.os, "lstat", lstat)
    assert ED._managed_policy_present() is True


# axis: a listdir error on an existing dir location counts as present (E5).
def test_presence_listdir_permission_error_is_present(tmp_path, monkeypatch):
    d = tmp_path / "managed-settings.d"
    d.mkdir()
    _patch_locations(monkeypatch, (str(d), "dir"))
    real = os.listdir

    def listdir(p="."):
        if p == str(d):
            raise PermissionError(13, "denied")
        return real(p)

    monkeypatch.setattr(ED.os, "listdir", listdir)
    assert ED._managed_policy_present() is True


# axis: the unpatched locations are the literal platform tuple.
def test_managed_policy_locations_literals():
    if sys.platform == "darwin":
        assert ED._managed_policy_locations() == (
            ("/Library/Application Support/ClaudeCode/managed-settings.json", "file"),
            ("/Library/Application Support/ClaudeCode/managed-settings.d", "dir"),
            ("/Library/Managed Preferences/com.anthropic.claudecode.plist", "file"),
        )
    else:
        assert ED._managed_policy_locations() == (
            ("/etc/claude-code/managed-settings.json", "file"),
            ("/etc/claude-code/managed-settings.d", "dir"),
        )


# axis: the resolver freezes the helper's value into the journaled sandbox dict.
@pytest.mark.parametrize("present", [True, False])
def test_resolver_threads_managed_policy_present(tmp_path, monkeypatch, present):
    monkeypatch.setattr(ED, "_managed_policy_present", lambda: present)
    wt, _main = _linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    assert sandbox["managedPolicyPresent"] is present


# --- Invariant C: the sweep ------------------------------------------------------------------


def _plant(root, rel):
    path = os.path.join(str(root), *rel.split("/"))
    os.makedirs(path)
    return path


# axis: empty staging dirs and their then-empty `.claude` parents go, at every depth.
def test_sweep_removes_empty_staging_and_parents(tmp_path):
    _plant(tmp_path, ".claude/.cc-writes")
    _plant(tmp_path, "a/b/.claude/.cc-writes")
    out = ED._sweep_cc_writes(os.path.realpath(str(tmp_path)))
    assert out["incomplete"] is False and out["error"] is None
    assert sorted(out["removed"]) == sorted([
        ".claude/.cc-writes", ".claude", "a/b/.claude/.cc-writes", "a/b/.claude"])
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "a" / "b" / ".claude").exists()
    assert (tmp_path / "a" / "b").is_dir()


# axis: a `.claude` that holds anything else keeps itself and that content.
def test_sweep_keeps_claude_with_other_content(tmp_path):
    _plant(tmp_path, ".claude/.cc-writes")
    (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    out = ED._sweep_cc_writes(os.path.realpath(str(tmp_path)))
    assert out["removed"] == [".claude/.cc-writes"]
    assert (tmp_path / ".claude" / "settings.json").is_file()
    assert not (tmp_path / ".claude" / ".cc-writes").exists()


# axis: a non-empty staging dir is never removed.
def test_sweep_keeps_non_empty_staging(tmp_path):
    staging = _plant(tmp_path, ".claude/.cc-writes")
    with open(os.path.join(staging, "pending"), "w", encoding="utf-8") as fh:
        fh.write("x")
    out = ED._sweep_cc_writes(os.path.realpath(str(tmp_path)))
    assert out["removed"] == []
    assert os.path.isfile(os.path.join(staging, "pending"))


# axis: a symlinked `.claude` is never followed (S3).
def test_sweep_does_not_follow_symlinked_claude(tmp_path):
    external = tmp_path / "external"
    (external / ".cc-writes").mkdir(parents=True)
    root = tmp_path / "root"
    root.mkdir()
    os.symlink(str(external), str(root / ".claude"))
    out = ED._sweep_cc_writes(os.path.realpath(str(root)))
    assert out["removed"] == []
    assert (external / ".cc-writes").is_dir()
    assert os.path.islink(str(root / ".claude"))


# axis: a symlinked `.cc-writes` and its target both survive (S4).
def test_sweep_does_not_remove_symlinked_staging(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    root = tmp_path / "root"
    (root / ".claude").mkdir(parents=True)
    os.symlink(str(external), str(root / ".claude" / ".cc-writes"))
    out = ED._sweep_cc_writes(os.path.realpath(str(root)))
    assert out["removed"] == []
    assert os.path.islink(str(root / ".claude" / ".cc-writes"))
    assert external.is_dir()


# axis: `.git` is pruned from the walk (S2).
def test_sweep_prunes_git(tmp_path):
    _plant(tmp_path, ".git/.claude/.cc-writes")
    out = ED._sweep_cc_writes(os.path.realpath(str(tmp_path)))
    assert out["removed"] == []
    assert (tmp_path / ".git" / ".claude" / ".cc-writes").is_dir()


# axis: an exhausted budget stops the walk before it touches anything (S1).
def test_sweep_budget_exhausted_is_incomplete(tmp_path):
    _plant(tmp_path, ".claude/.cc-writes")
    ticks = itertools.count()
    out = ED._sweep_cc_writes(
        os.path.realpath(str(tmp_path)), budget_seconds=0, clock=lambda: next(ticks))
    assert out == {"removed": [], "incomplete": True, "error": None}
    assert (tmp_path / ".claude" / ".cc-writes").is_dir()


# axis: a subdirectory on another device is never entered (S2).
def test_sweep_does_not_cross_devices(tmp_path, monkeypatch):
    _plant(tmp_path, "mount/.claude/.cc-writes")
    _plant(tmp_path, "plain/.claude/.cc-writes")
    mount_ino = os.stat(str(tmp_path / "mount")).st_ino
    real = os.stat

    def stat(p, *a, **k):
        res = real(p, *a, **k)
        if res.st_ino == mount_ino:
            fields = list(res)
            fields[2] = res.st_dev + 1
            return os.stat_result(fields)
        return res

    monkeypatch.setattr(ED.os, "stat", stat)
    out = ED._sweep_cc_writes(os.path.realpath(str(tmp_path)))
    assert out["removed"] == ["plain/.claude/.cc-writes", "plain/.claude"]
    assert (tmp_path / "mount" / ".claude" / ".cc-writes").is_dir()


# axis: the sweep never raises; an unexpected error is reported incomplete with what was removed.
def test_sweep_never_raises(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(ED.os, "fwalk", boom)
    assert ED._sweep_cc_writes(str(tmp_path)) == {
        "removed": [], "incomplete": True, "error": "RuntimeError"}


# axis: the fold sweep is claude-write only; missing run context is incomplete, not a raise.
def test_fold_sweep_scope_and_missing_cwd(tmp_path):
    assert ED._fold_cc_writes_sweep({"opened": {"runKind": ED.RUN_KIND_WRITE, "engine": "codex"}}) is None
    assert ED._fold_cc_writes_sweep({"opened": {"runKind": ED.RUN_KIND_REVIEW, "engine": "claude"}}) is None
    for cwd in (None, 7):
        got = ED._fold_cc_writes_sweep(
            {"opened": {"runKind": ED.RUN_KIND_WRITE, "engine": "claude", "cwd": cwd}})
        assert got == {"removed": [], "incomplete": True, "error": "run-context-incomplete"}


# --- Invariant C: wiring through the production fold -----------------------------------------


def _folded_result(run_dir):
    records, _ = ED._journal_read(run_dir)
    return next(r for r in records if r.get("kind") == "run-folded")["result"]


# axis: a claude write run sweeps its worktree before the terminal record is journaled.
def test_claude_write_fold_sweeps_worktree(tmp_path, monkeypatch):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, _main = _linked_worktree(tmp_path)
    _plant(wt, ".claude/.cc-writes")
    _plant(wt, "sub/.claude/.cc-writes")
    run_dir = str(tmp_path / "run")
    fake = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    assert res["ok"] is True, res
    assert not os.path.exists(os.path.join(wt, ".claude"))
    assert not os.path.exists(os.path.join(wt, "sub", ".claude"))
    expected = {"removed": [".claude/.cc-writes", ".claude", "sub/.claude/.cc-writes", "sub/.claude"],
                "incomplete": False, "error": None}
    for sweep in (res["ccWritesSweep"], _folded_result(run_dir)["ccWritesSweep"]):
        assert sorted(sweep["removed"]) == sorted(expected["removed"])
        assert sweep["incomplete"] is False and sweep["error"] is None


# axis: a codex write run is never swept and carries no sweep key.
def test_codex_write_fold_does_not_sweep(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    staging = _plant(wt, ".claude/.cc-writes")
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir)
    assert res["ok"] is True, res
    assert os.path.isdir(staging)
    assert "ccWritesSweep" not in res
    assert "ccWritesSweep" not in _folded_result(run_dir)
