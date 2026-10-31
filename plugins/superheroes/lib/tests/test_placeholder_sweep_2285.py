"""#2285: the claude write channel leaves no sandbox placeholder in the worktree.

Invariant: after a claude write run folds, no `SANDBOX_PLACEHOLDERS` path that the before-run
snapshot showed absent is left empty and read-only in the worktree; a path the snapshot showed
present is never removed, every other new path (an unlisted placeholder-shaped one included) is
left and reported, and without a complete snapshot nothing goes."""
import json
import os

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    FakeRunner,
    _ClaudeStdoutWriteFakeRunner,
    _build_ok_stdout,
    _claude_write_runner,
    _dispatch_write,
    _ensure_claude_config_dir,
    _implementer_claude_seat,
    _init_repo,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
)


def _placeholder_file(root, rel):
    path = os.path.join(str(root), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()
    os.chmod(path, 0o444)
    return path


def _placeholder_dir(root, rel):
    path = os.path.join(str(root), *rel.split("/"))
    os.makedirs(path)
    os.chmod(path, 0o555)
    return path


def _sweep(root, baseline):
    return ED._sweep_placeholders(os.path.realpath(str(root)), baseline)


def _snapshot(root):
    return ED._placeholder_snapshot(os.path.realpath(str(root)))


# axis: listed placeholders new since the snapshot go, files and dirs, `.claude` children before it.
def test_listed_placeholders_created_during_run_are_removed(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    assert baseline["status"] == "ok" and baseline["present"] == []
    _placeholder_file(wt, ".bashrc")
    _placeholder_dir(wt, ".vscode")
    _placeholder_file(wt, ".claude/settings.json")
    os.chmod(os.path.join(wt, ".claude"), 0o555)
    out = _sweep(wt, baseline)
    assert out["removed"] == [".bashrc", ".vscode", ".claude/settings.json", ".claude"], out
    assert out["left"] == [] and out["unlisted"] == []
    assert out["incomplete"] is False and out["error"] is None
    for rel in (".bashrc", ".vscode", ".claude"):
        assert not os.path.lexists(os.path.join(wt, rel))


# axis: a listed path the snapshot saw is never removed, empty and read-only or not.
def test_pre_existing_placeholder_survives(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    kept = _placeholder_file(wt, ".gitconfig")
    kept_dir = _placeholder_dir(wt, ".idea")
    baseline = _snapshot(wt)
    assert baseline["present"] == [".gitconfig", ".idea"]
    out = _sweep(wt, baseline)
    assert out["removed"] == [] and out["left"] == []
    assert os.path.isfile(kept) and os.path.isdir(kept_dir)


# axis: a new empty read-only path off the list, or a listed name below the root, is left and named.
def test_unlisted_placeholder_is_left_and_reported(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    deep = _placeholder_file(wt, "pkg/.mcp.json")
    other = _placeholder_file(wt, ".newrc")
    empty_dir = _placeholder_dir(wt, ".newdir")
    out = _sweep(wt, baseline)
    assert out["removed"] == []
    assert out["unlisted"] == [".newdir", ".newrc", "pkg/.mcp.json"]
    assert out["left"] == [".newdir", ".newrc", "pkg", "pkg/.mcp.json"]
    assert os.path.isfile(deep) and os.path.isfile(other) and os.path.isdir(empty_dir)


# axis: a new file with content, or a new empty file with a write bit, survives, listed or not.
def test_new_non_empty_file_survives(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    full = os.path.join(wt, ".mcp.json")
    with open(full, "w", encoding="utf-8") as fh:
        fh.write("{}")
    os.chmod(full, 0o444)
    open(os.path.join(wt, ".bashrc"), "w").close()
    out = _sweep(wt, baseline)
    assert out["removed"] == []
    assert out["left"] == [".bashrc", ".mcp.json"] and out["unlisted"] == []
    assert os.path.isfile(full) and os.path.isfile(os.path.join(wt, ".bashrc"))


# axis: no complete snapshot means nothing is removed.
def test_no_snapshot_removes_nothing(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    placeholder = _placeholder_file(wt, ".bashrc")
    for baseline in (None, {"status": "incomplete", "reason": "budget-exhausted"},
                     {"status": "ok", "paths": []}):
        out = _sweep(wt, baseline)
        assert out["removed"] == [] and out["incomplete"] is True
        assert out["error"].startswith("baseline-")
    assert os.path.isfile(placeholder)


# axis: a snapshot that runs out of budget is not ok.
def test_snapshot_budget_exhausted_is_incomplete(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    ticks = iter(range(0, 1000, 100))
    out = ED._placeholder_snapshot(wt, budget_seconds=1, clock=lambda: next(ticks))
    assert out == {"status": "incomplete", "reason": "budget-exhausted"}


# axis: a directory the snapshot cannot open makes it incomplete, never a silent gap.
def test_snapshot_unreadable_subtree_is_incomplete(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    os.makedirs(os.path.join(wt, "locked"))
    real_open = ED.os.open

    def guarded_open(path, flags, mode=0o777, *, dir_fd=None):
        if path == "locked":
            raise PermissionError(13, "Permission denied", path)
        return real_open(path, flags, mode, dir_fd=dir_fd)
    monkeypatch.setattr(ED.os, "open", guarded_open)
    baseline = _snapshot(wt)
    monkeypatch.undo()
    assert baseline == {"status": "incomplete", "reason": "PermissionError"}


# axis: a listed parent that is a symlink is never followed, at snapshot or at sweep.
def test_symlinked_claude_dir_is_not_followed(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    external = tmp_path / "external"
    victim = _placeholder_file(external, "settings.json")
    os.symlink(str(external), os.path.join(wt, ".claude"))
    out = _sweep(wt, baseline)
    assert out["removed"] == [] and os.path.isfile(victim)
    again = _snapshot(wt)
    assert again["present"] == [".claude"]
    assert _sweep(wt, again)["removed"] == [] and os.path.isfile(victim)


# axis: a worktree root replaced by a symlink after the snapshot is never swept.
def test_root_replaced_by_symlink_is_not_swept(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    other = _init_repo(str(tmp_path / "other"))
    victim = _placeholder_file(other, ".bashrc")
    os.rename(wt, str(tmp_path / "moved"))
    os.symlink(str(other), wt)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / ED.PLACEHOLDER_BASELINE_NAME).write_text(json.dumps(baseline), encoding="utf-8")
    out = ED._fold_placeholder_sweep(str(run_dir), {"opened": {
        "runKind": ED.RUN_KIND_WRITE, "engine": "claude", "cwd": wt}})
    assert out["removed"] == [] and out["error"] == "root-changed"
    assert os.path.isfile(victim)


# axis: a new read-only listed dir that stays keeps its own mode after the sweep.
def test_new_read_only_dir_that_stays_keeps_its_mode(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    parent = os.path.join(wt, ".claude")
    _placeholder_file(wt, ".claude/settings.json")
    with open(os.path.join(parent, "notes.txt"), "w", encoding="utf-8") as fh:
        fh.write("x")
    os.chmod(parent, 0o555)
    try:
        out = _sweep(wt, baseline)
        mode = os.stat(parent).st_mode & 0o777
    finally:
        os.chmod(parent, 0o755)
    assert out["removed"] == [".claude/settings.json"]
    assert out["left"] == [".claude", ".claude/notes.txt"] and out["unlisted"] == []
    assert mode == 0o555


# --- wiring through the production open and fold ---------------------------------------------


def _folded_result(run_dir):
    records, _ = ED._journal_read(run_dir)
    return next(r for r in records if r.get("kind") == "run-folded")["result"]


def _placeholder_planting_runner(wt):
    inner = _claude_write_runner()

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        _placeholder_file(wt, ".bashrc")
        _placeholder_dir(wt, ".vscode")
        with open(os.path.join(wt, "deliverable.txt"), "w", encoding="utf-8") as fh:
            fh.write("work\n")
        return inner(argv, prompt_bytes, timeout, progress_cb, cwd)
    return runner


# axis: the open snapshots before the engine runs and the fold reports what it removed.
def test_claude_write_fold_removes_run_placeholders(tmp_path, monkeypatch):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, _main = _linked_worktree(tmp_path)
    kept = _placeholder_file(wt, ".gitconfig")
    run_dir = str(tmp_path / "run")
    fake = _ClaudeStdoutWriteFakeRunner([_placeholder_planting_runner(wt)])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    assert res["ok"] is True, res
    for sweep in (res["placeholderSweep"], _folded_result(run_dir)["placeholderSweep"]):
        assert sweep["removed"] == [".bashrc", ".vscode"]
        assert sweep["left"] == ["deliverable.txt"]
        assert sweep["incomplete"] is False and sweep["error"] is None
    assert os.path.isfile(kept)
    assert os.path.isfile(os.path.join(wt, "deliverable.txt"))
    assert not os.path.lexists(os.path.join(wt, ".bashrc"))


# axis: a codex write run is never swept and carries no sweep key.
def test_codex_write_fold_does_not_sweep_placeholders(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        _placeholder_file(wt, ".bashrc")
        return _build_ok_stdout()
    fake = FakeRunner([runner])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir)
    assert res["ok"] is True, res
    assert os.path.isfile(os.path.join(wt, ".bashrc"))
    assert "placeholderSweep" not in res
    assert "placeholderSweep" not in _folded_result(run_dir)
