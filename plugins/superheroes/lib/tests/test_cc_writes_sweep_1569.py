"""#1569: the claude write channel leaves no `.claude/.cc-writes` residue in the worktree.

Invariant: every claude write run that folds has swept its worktree of empty `.claude/.cc-writes`
dirs (and their then-empty `.claude` parent), dir_fd-relative, never following symlinks, entering
`.git` or crossing devices, within a wall budget; no other run is swept."""
import itertools
import json
import os
import subprocess
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


# axis: a skipped root (a nested registered worktree) is never entered, so its staging dir survives.
def test_sweep_prunes_skip_roots(tmp_path):
    _plant(tmp_path, ".claude/worktrees/sib/.claude/.cc-writes")
    _plant(tmp_path, "plain/.claude/.cc-writes")
    root = os.path.realpath(str(tmp_path))
    sib = os.path.join(root, ".claude", "worktrees", "sib")
    out = ED._sweep_cc_writes(root, skip_roots={sib})
    assert out["removed"] == ["plain/.claude/.cc-writes", "plain/.claude"]
    assert (tmp_path / ".claude" / "worktrees" / "sib" / ".claude" / ".cc-writes").is_dir()


# axis: an unenumerable worktree list means no sweep at all, reported incomplete.
def test_fold_sweep_skips_when_worktrees_unenumerable(tmp_path):
    staging = _plant(tmp_path, ".claude/.cc-writes")
    got = ED._fold_cc_writes_sweep({"opened": {
        "runKind": ED.RUN_KIND_WRITE, "engine": "claude", "cwd": str(tmp_path)}})
    assert got == {"removed": [], "incomplete": True, "error": "worktree-enumeration-failed"}
    assert os.path.isdir(staging)


# axis: an exhausted budget stops the walk before it touches anything (S1).
def test_sweep_budget_exhausted_is_incomplete(tmp_path):
    _plant(tmp_path, ".claude/.cc-writes")
    ticks = itertools.count()
    out = ED._sweep_cc_writes(
        os.path.realpath(str(tmp_path)), budget_seconds=0, clock=lambda: next(ticks))
    assert out == {"removed": [], "incomplete": True, "error": None}
    assert (tmp_path / ".claude" / ".cc-writes").is_dir()


# axis: the budget is checked while a directory's children are statted and before any removal,
# so a wide directory cannot run past the deadline or remove after it.
def test_sweep_budget_expiring_mid_directory_removes_nothing(tmp_path):
    _plant(tmp_path, ".claude/.cc-writes")
    _plant(tmp_path, "wide/a")
    _plant(tmp_path, "wide/b")
    root = os.path.realpath(str(tmp_path))
    now = [0.0]
    real = os.stat

    def stat(p, *a, **k):
        now[0] += 6.0
        return real(p, *a, **k)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ED.os, "stat", stat)
        out = ED._sweep_cc_writes(root, budget_seconds=10.0, clock=lambda: now[0])
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


# axis: a claude write run never sweeps a nested registered worktree's staging dir.
def test_claude_write_fold_spares_nested_worktree(tmp_path, monkeypatch):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, _main = _linked_worktree(tmp_path)
    sib = os.path.join(wt, ".claude", "worktrees", "sib")
    os.makedirs(os.path.dirname(sib))
    subprocess.run(["git", "-C", wt, "worktree", "add", "-q", sib], check=True)
    sib_staging = _plant(sib, ".claude/.cc-writes")
    _plant(wt, "sub/.claude/.cc-writes")
    run_dir = str(tmp_path / "run")
    fake = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    assert res["ok"] is True, res
    assert os.path.isdir(sib_staging)
    assert not os.path.exists(os.path.join(wt, "sub", ".claude"))
    assert res["ccWritesSweep"]["incomplete"] is False


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
