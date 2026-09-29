"""#1467 item 2: a worktree-dirtied-by-attempt forfeit names the paths the attempt dirtied."""
import importlib.util
import os
import subprocess
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E2E = _load_module("dirtied_paths_e2e_helpers", "test_engine_dispatch_e2e.py")
ED = E2E.ED

_GIT_ENV = E2E._GIT_ENV


@pytest.fixture(autouse=True)
def _pin_temp_and_journal(tmp_path, monkeypatch):
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _git(cwd, *args):
    merged = dict(os.environ)
    merged.update(_GIT_ENV)
    return subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, check=True, env=merged,
    )


def _repo(tmp_path):
    path = str(tmp_path / "repo")
    E2E._init_repo(path)
    return os.path.realpath(path)


def _write(repo, rel, text):
    full = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


# --- T1: real path -------------------------------------------------------------


def test_t1_real_path_forfeit_names_planted_probe_mutation(tmp_path, monkeypatch):
    wt, _main = E2E._linked_worktree(tmp_path)
    run_dir = E2E._run_dir(tmp_path, "run-dirtied")
    prompt_path = E2E._prompt(tmp_path)
    E2E._install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        out_file=os.path.join(wt, "probe-mutation.txt"), sleep_s=20,
    )
    res = _poll_short(wt, run_dir, prompt_path)
    assert res["terminal"] is True
    assert res["detail"] == "worktree-dirtied-by-attempt"
    assert res["dirtiedPaths"]["status"] == "ok"
    assert "probe-mutation.txt" in res["dirtiedPaths"]["paths"]


def _poll_short(wt, run_dir, prompt_path):
    deadline = time.monotonic() + 120
    last = None
    while time.monotonic() < deadline:
        last = ED.dispatch_write(
            seat=E2E._cursor_seat(), prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
            order_id="dirtied-1", timeout=3, retry_timeout=3,
        )
        if last.get("terminal") or last.get("reason") != "running":
            return last
        time.sleep(0.2)
    pytest.fail("no terminal; last=%s" % (last,))


# --- T2 ------------------------------------------------------------------------


def test_t2_modified_tracked_and_added_untracked_are_listed(tmp_path):
    repo = _repo(tmp_path)
    baseline = ED._worktree_baseline(repo)
    _write(repo, "README.md", "changed\n")
    _write(repo, "new.txt", "new\n")
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got == {
        "status": "ok", "paths": ["README.md", "new.txt"],
        "headMoved": False, "truncated": False,
    }


# --- T3 ------------------------------------------------------------------------


def test_t3_committed_path_listed_when_head_moved_and_status_clean(tmp_path):
    repo = _repo(tmp_path)
    baseline = ED._worktree_baseline(repo)
    _write(repo, "committed.txt", "x\n")
    _git(repo, "add", "committed.txt")
    _git(repo, "commit", "-qm", "attempt commit")
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got["status"] == "ok"
    assert got["headMoved"] is True
    assert got["paths"] == ["committed.txt"]


# --- T4 ------------------------------------------------------------------------


def _valid(repo):
    return ED._worktree_baseline(repo)


@pytest.mark.parametrize("label,mutate,token", [
    ("not-a-dict", lambda b: "nope", "baseline-not-a-dict"),
    ("none", lambda b: None, "baseline-not-a-dict"),
    ("head-unreadable", lambda b: dict(b, headSha="zzz"), "baseline-head-unreadable"),
    ("legacy-no-version", lambda b: {k: v for k, v in b.items() if k != "entriesVersion"},
     "baseline-entries-version-missing"),
    ("version-mismatch", lambda b: dict(b, entriesVersion=ED.BASELINE_ENTRIES_VERSION + 99),
     "baseline-entries-version-unknown"),
    ("overflow", lambda b: dict(b, entriesOverflow=True), "baseline-entries-overflow"),
    ("entries-not-list", lambda b: dict(b, entries="x"), "baseline-entries-malformed"),
    ("entries-bad-record", lambda b: dict(b, entries=[[1]]), "baseline-entries-malformed"),
], ids=[
    "not-a-dict", "none", "head-unreadable", "legacy-no-version", "version-mismatch",
    "overflow", "entries-not-list", "entries-bad-record",
])
def test_t4_invalid_baseline_is_indeterminate(tmp_path, label, mutate, token):
    repo = _repo(tmp_path)
    baseline = mutate(_valid(repo))
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got == {"status": "indeterminate", "reason": token}


def test_t4_unreachable_baseline_head_with_head_moved_is_indeterminate(tmp_path):
    repo = _repo(tmp_path)
    baseline = dict(_valid(repo), headSha="1" * 40)
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got == {"status": "indeterminate", "reason": "git-diff-failed"}


# --- T5 ------------------------------------------------------------------------


def test_t5_rename_lists_both_endpoints(tmp_path):
    repo = _repo(tmp_path)
    baseline = ED._worktree_baseline(repo)
    _git(repo, "mv", "README.md", "RENAMED.md")
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got["status"] == "ok"
    assert got["paths"] == ["README.md", "RENAMED.md"]


def test_t5_more_than_200_paths_is_capped_and_truncated(tmp_path):
    repo = _repo(tmp_path)
    baseline = ED._worktree_baseline(repo)
    for i in range(205):
        _write(repo, "many/f%03d.txt" % i, "x\n")
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got["status"] == "ok"
    assert got["truncated"] is True
    assert len(got["paths"]) == 200
    assert got["paths"] == sorted(got["paths"])
    assert got["paths"][0] == "many/f000.txt"


# --- T6: documented limit ------------------------------------------------------


def test_t6_edit_of_already_dirty_file_with_unchanged_status_is_not_listed(tmp_path):
    repo = _repo(tmp_path)
    _write(repo, "README.md", "dirty at open\n")
    baseline = ED._worktree_baseline(repo)
    _write(repo, "README.md", "edited again by the attempt\n")
    got = ED._worktree_dirtied_paths(baseline, repo)
    assert got == {"status": "ok", "paths": [], "headMoved": False, "truncated": False}
