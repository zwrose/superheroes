"""#1978: a mid-build merge of the base branch adds nothing to the size fold.

Invariant: a write run opened with `--size-base-ref` folds its count from the merge base of HEAD
and that ref whenever the merge base is newer than `--size-base`, so main's own lines merged into
the branch mid-build are not the build's; the build's own lines, before and after the merge, still
count, and a ref that does not resolve refuses at open and reads indeterminate at fold."""
import os
import subprocess

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    FakeRunner,
    _dispatch_write,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
)
from test_size_tripwire_fold_1582 import _head, _implementing_runner, _opened_record

_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", cwd, "-c", "user.email=t@t.local", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True, env=_GIT_ENV,
    )


def _commit_file(repo, rel, lines, message):
    with open(os.path.join(repo, rel), "w", encoding="utf-8") as fh:
        fh.write("y = 2\n" * lines)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", message)


def _merged_build(tmp_path, main_lines=300, own_before=10):
    """A build worktree that branched at `start`, committed its own lines, then merged a main
    carrying `main_lines` non-test lines. Returns (worktree, start sha, main branch name)."""
    wt, main = _linked_worktree(tmp_path)
    start = _head(wt)
    main_branch = _git(main, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _commit_file(wt, "own.py", own_before, "build: own lines")
    _commit_file(main, "mainline.py", main_lines, "main: moved on")
    _git(wt, "merge", "--no-ff", "-qm", "merge main", main_branch)
    return wt, start, main_branch


# axis: main's lines merged mid-build are not the build's; the count runs from the merge base.
def test_mid_build_merge_adds_nothing(tmp_path):
    wt, start, main_branch = _merged_build(tmp_path)
    main_tip = _git(wt, "rev-parse", main_branch).stdout.strip()
    res = _dispatch_write(
        tmp_path, _implementing_runner({"added.py": 20}), cwd=wt, run_dir=str(tmp_path / "run"),
        size_base=start, size_line=140, size_base_ref=main_branch,
    )
    assert res["ok"] is True, res
    tripwire = res["sizeTripwire"]
    assert tripwire["status"] == "ok", tripwire
    assert tripwire["tripwireCount"] == 30
    assert tripwire["crossed"] is False
    assert tripwire["base"] == start
    assert tripwire["baseRef"] == main_branch
    assert tripwire["countedFrom"] == main_tip
    assert _opened_record(str(tmp_path / "run"))["sizeTripwireInputs"] == {
        "base": start, "line": 140, "baseRef": main_branch}


# axis: the build's own lines past the line still cross after a merge.
def test_own_lines_still_cross(tmp_path):
    wt, start, main_branch = _merged_build(tmp_path, own_before=100)
    res = _dispatch_write(
        tmp_path, _implementing_runner({"added.py": 41}), cwd=wt, run_dir=str(tmp_path / "run"),
        size_base=start, size_line=140, size_base_ref=main_branch,
    )
    assert res["sizeTripwire"]["tripwireCount"] == 141
    assert res["sizeTripwire"]["crossed"] is True


# axis: a ref older than the build's base never counts lines from before that base.
def test_stale_ref_counts_from_the_build_base(tmp_path):
    wt, main = _linked_worktree(tmp_path)
    old = _head(wt)
    _commit_file(main, "before.py", 300, "main: before the build started")
    _git(main, "branch", "stale", old)
    _git(wt, "merge", "-q", _git(main, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip())
    start = _head(wt)
    res = _dispatch_write(
        tmp_path, _implementing_runner({"added.py": 20}), cwd=wt, run_dir=str(tmp_path / "run"),
        size_base=start, size_line=140, size_base_ref="stale",
    )
    assert res["sizeTripwire"]["countedFrom"] == start
    assert res["sizeTripwire"]["tripwireCount"] == 20


# axis: a ref that does not resolve refuses before anything opens; a ref without the size inputs
# is incomplete.
def test_unresolvable_ref_refuses(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    sha = _head(wt)
    cases = [
        ({"size_base": sha, "size_line": 140, "size_base_ref": "no-such-branch"},
         "size-base-unresolvable"),
        ({"size_base": sha, "size_line": 140, "size_base_ref": "--all"},
         "size-base-unresolvable"),
        ({"size_base_ref": "HEAD"}, "size-inputs-incomplete"),
    ]
    for index, (kwargs, token) in enumerate(cases):
        run_dir = str(tmp_path / ("run-%d" % index))
        fake = FakeRunner([])
        res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, **kwargs)
        assert res["ok"] is False and res["detail"] == token, (kwargs, res)
        assert fake.calls == []
        records, _ = ED._journal_read(run_dir)
        assert not any(r.get("kind") == "run-opened" for r in records), (kwargs, records)


# axis: a ref gone by fold time is no count, never a count from the wrong base.
def test_ref_gone_at_fold_is_indeterminate(tmp_path, monkeypatch):
    wt, start, main_branch = _merged_build(tmp_path)
    resolve = ED._resolve_commit
    calls = []

    def gone_after_open(cwd, rev, timeout=None):
        calls.append(rev)
        return resolve(cwd, rev, timeout=timeout) if len(calls) == 1 else None

    monkeypatch.setattr(ED, "_resolve_commit", gone_after_open)
    res = _dispatch_write(
        tmp_path, _implementing_runner({"added.py": 20}), cwd=wt, run_dir=str(tmp_path / "run"),
        size_base=start, size_line=140, size_base_ref=main_branch,
    )
    assert res["ok"] is True, res
    assert res["sizeTripwire"] == {
        "status": "indeterminate", "base": start, "line": 140, "baseRef": main_branch,
        "reason": "size-base-unresolvable"}


# axis: the CLI carries the ref through to the dispatch.
def test_cli_carries_the_ref(tmp_path):
    args = ED.build_parser().parse_args([
        "dispatch-write", "--seat", "codex:implementer", "--prompt-path", "p.txt",
        "--cwd", str(tmp_path), "--run-dir", str(tmp_path / "run"),
        "--size-base", "a" * 40, "--size-line", "140", "--size-base-ref", "origin/main",
    ])
    assert args.size_base_ref == "origin/main"


# axis: a continuation with a different ref, or none, refuses against the journaled inputs.
def test_continuation_ref_mismatch(tmp_path):
    wt, start, main_branch = _merged_build(tmp_path)
    active = str(tmp_path / "active")
    _dispatch_write(
        tmp_path, FakeRunner([]), cwd=wt, run_dir=active, max_wait=0,
        size_base=start, size_line=140, size_base_ref=main_branch,
    )
    for ref in ("HEAD", None):
        res = _dispatch_write(
            tmp_path, FakeRunner([]), cwd=wt, run_dir=active, max_wait=0,
            size_base=start, size_line=140, size_base_ref=ref,
        )
        assert res["detail"] == "size-inputs-mismatch", (ref, res)


# axis: the merge-base calls share the fold's one budget; a spent budget is a timeout, not a count.
def test_spent_budget_is_a_timeout(tmp_path):
    wt, start, main_branch = _merged_build(tmp_path)
    assert ED._size_count_from(wt, start, main_branch, deadline=0) == (None, "git-timeout")
    assert ED._size_count_from(wt, start, None, deadline=0) == (start, None)
