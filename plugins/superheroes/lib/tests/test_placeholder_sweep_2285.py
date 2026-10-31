"""#2285: the claude write channel leaves no sandbox placeholder in the worktree.

Invariant: after a claude write run folds, the worktree holds no path that is new since the
before-run snapshot, empty and read-only; a path the snapshot holds is never removed, a new path
with content (or a write bit) is left and reported, and without a complete snapshot nothing goes."""
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


# axis: new empty read-only files and dirs go, at any depth, and only those.
def test_placeholders_created_during_run_are_removed(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    os.makedirs(os.path.join(wt, "pkg"))
    baseline = _snapshot(wt)
    assert baseline["status"] == "ok"
    _placeholder_file(wt, ".bashrc")
    _placeholder_file(wt, "pkg/.mcp.json")
    _placeholder_dir(wt, ".vscode")
    out = _sweep(wt, baseline)
    assert sorted(out["removed"]) == [".bashrc", ".vscode", "pkg/.mcp.json"]
    assert out["left"] == [] and out["leftCount"] == 0
    assert out["incomplete"] is False and out["error"] is None
    for rel in (".bashrc", ".vscode", "pkg/.mcp.json"):
        assert not os.path.lexists(os.path.join(wt, rel))


# axis: a new writable dir that held only placeholders is left (it is not read-only), and a new
# read-only dir that still holds something is left.
def test_new_dirs_that_are_not_placeholders_are_left(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    _placeholder_file(wt, ".claude/settings.json")
    full_dir = os.path.join(wt, "out")
    os.makedirs(full_dir)
    with open(os.path.join(full_dir, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("x")
    os.chmod(full_dir, 0o555)
    try:
        out = _sweep(wt, baseline)
    finally:
        os.chmod(full_dir, 0o755)
    assert out["removed"] == [".claude/settings.json"]
    assert out["left"] == [".claude", "out", "out/a.txt"]
    assert os.path.isdir(os.path.join(wt, ".claude"))
    assert os.path.isfile(os.path.join(full_dir, "a.txt"))


# axis: a path the snapshot holds is never removed, empty and read-only or not.
def test_pre_existing_empty_file_survives(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    kept = _placeholder_file(wt, ".gitconfig")
    kept_dir = _placeholder_dir(wt, ".idea")
    baseline = _snapshot(wt)
    out = _sweep(wt, baseline)
    assert out["removed"] == [] and out["left"] == []
    assert os.path.isfile(kept) and os.path.isdir(kept_dir)


# axis: a new file with content, or a new empty file with a write bit, is left and reported.
def test_new_non_empty_file_survives(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    baseline = _snapshot(wt)
    full = os.path.join(wt, "report.txt")
    with open(full, "w", encoding="utf-8") as fh:
        fh.write("x")
    os.chmod(full, 0o444)
    open(os.path.join(wt, "empty-writable.txt"), "w").close()
    out = _sweep(wt, baseline)
    assert out["removed"] == []
    assert out["left"] == ["empty-writable.txt", "report.txt"] and out["leftCount"] == 2
    assert os.path.isfile(full)


# axis: no complete snapshot means nothing is removed.
def test_no_snapshot_removes_nothing(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    placeholder = _placeholder_file(wt, ".bashrc")
    for baseline in (None, {"status": "incomplete", "reason": "budget-exhausted"}):
        out = _sweep(wt, baseline)
        assert out["removed"] == [] and out["incomplete"] is True
        assert out["error"].startswith("baseline-")
    assert os.path.isfile(placeholder)


# axis: a snapshot that runs out of budget is not ok, so the fold removes nothing.
def test_snapshot_budget_exhausted_is_incomplete(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    ticks = iter(range(0, 1000, 100))
    out = ED._placeholder_snapshot(wt, budget_seconds=1, clock=lambda: next(ticks))
    assert out == {"status": "incomplete", "reason": "budget-exhausted"}


# axis: `.git`, symlinks and a subtree the snapshot did not walk are never swept.
def test_sweep_spares_git_symlinks_and_unwalked_subtrees(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    os.makedirs(os.path.join(wt, "vendor"))
    external = tmp_path / "external"
    external.mkdir()
    baseline = _snapshot(wt)
    baseline["paths"] = [p for p in baseline["paths"] if not p.startswith("vendor")]
    baseline["pruned"].append("vendor")
    in_vendor = _placeholder_file(wt, "vendor/.bashrc")
    target = _placeholder_file(external, ".bashrc")
    os.symlink(str(external), os.path.join(wt, "linked"))
    os.symlink(target, os.path.join(wt, "linked-file"))
    out = _sweep(wt, baseline)
    assert out["removed"] == []
    assert os.path.isfile(in_vendor) and os.path.isfile(target)
    assert sorted(out["left"]) == ["linked", "linked-file"]


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
        assert sorted(sweep["removed"]) == [".bashrc", ".vscode"]
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
