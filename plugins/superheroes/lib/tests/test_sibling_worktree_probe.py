import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "sibling_worktree_probe",
        os.path.join(_HERE, "..", "sibling_worktree_probe.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SWP = _load()


def _init_repo(path):
    subprocess.run(["git", "-C", path, "init", "-q"], check=True)
    readme = os.path.join(path, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    subprocess.run(["git", "-C", path, "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", path, "-c", "user.email=t@t.local", "-c", "user.name=t",
         "commit", "-qm", "init"],
        check=True,
    )
    return path


def _linked_worktrees(tmp_path, count=2):
    main = str(tmp_path / "main")
    os.makedirs(main, exist_ok=True)
    _init_repo(main)
    worktrees = []
    for i in range(count):
        wt = str(tmp_path / ("wt%d" % i))
        subprocess.run(["git", "-C", main, "worktree", "add", "-q", wt], check=True)
        worktrees.append(wt)
    return main, worktrees


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": list(argv), "kwargs": dict(kwargs)})
        if not self.responses:
            raise RuntimeError("unexpected git call")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _proc(rc=0, stdout="", stderr=""):
    class P:
        returncode = rc
    p = P()
    p.stdout = stdout
    p.stderr = stderr
    return p


def test_snapshot_excludes_assigned_by_real_path(tmp_path):
    main, wts = _linked_worktrees(tmp_path, count=2)
    assigned = os.path.realpath(wts[0])
    snap = SWP.snapshot(main, assigned)
    assert snap["status"] == "ok"
    paths = set(snap["worktrees"])
    assert assigned not in paths
    assert os.path.realpath(wts[1]) in paths


def test_snapshot_excludes_symlink_assigned_path(tmp_path):
    main, wts = _linked_worktrees(tmp_path, count=2)
    link = str(tmp_path / "assigned-link")
    os.symlink(wts[0], link)
    snap = SWP.snapshot(main, link)
    assert snap["status"] == "ok"
    assert os.path.realpath(wts[0]) not in snap["worktrees"]


def test_compare_head_delta():
    before = {
        "status": "ok",
        "truncated": False,
        "worktrees": {
            "/wt": {"path": "/wt", "headSha": "a", "porcelainSha256": "p", "reflogCount": 1},
        },
    }
    after = {
        "status": "ok",
        "truncated": False,
        "worktrees": {
            "/wt": {"path": "/wt", "headSha": "b", "porcelainSha256": "p", "reflogCount": 1},
        },
    }
    result = SWP.compare(before, after)
    assert result["status"] == "observed"
    assert any(d["kind"] == "head-changed" for d in result["deltas"])


def test_compare_porcelain_delta():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": {"headSha": "a", "porcelainSha256": "p1", "reflogCount": 1}},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": {"headSha": "a", "porcelainSha256": "p2", "reflogCount": 1}},
    }
    result = SWP.compare(before, after)
    assert any(d["kind"] == "porcelain-changed" for d in result["deltas"])


def test_compare_reflog_delta():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": {"headSha": "a", "porcelainSha256": "p", "reflogCount": 1}},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": {"headSha": "a", "porcelainSha256": "p", "reflogCount": 2}},
    }
    result = SWP.compare(before, after)
    assert any(d["kind"] == "reflog-changed" for d in result["deltas"])


def test_compare_null_reflog_to_number_is_not_delta():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": {"headSha": "a", "porcelainSha256": "p", "reflogCount": None}},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": {"headSha": "a", "porcelainSha256": "p", "reflogCount": 3}},
    }
    result = SWP.compare(before, after)
    assert result["deltas"] == []


def test_compare_appeared_and_disappeared():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/gone": {"headSha": "a", "porcelainSha256": "p", "reflogCount": 1}},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/new": {"headSha": "b", "porcelainSha256": "q", "reflogCount": 1}},
    }
    result = SWP.compare(before, after)
    kinds = {d["kind"] for d in result["deltas"]}
    assert "appeared" in kinds
    assert "disappeared" in kinds


def test_snapshot_deadline_exhaustion_returns_indeterminate():
    def slow_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    snap = SWP.snapshot("/repo", "/assigned", deadline=0.001, run=slow_run)
    assert snap["status"] == "indeterminate"


def test_snapshot_truncation_reported(tmp_path, monkeypatch):
    main, _wts = _linked_worktrees(tmp_path, count=3)
    snap = SWP.snapshot(main, _wts[0], max_worktrees=1)
    assert snap["status"] == "ok"
    assert snap["truncated"] is True
    assert len(snap["worktrees"]) == 1


def test_git_optional_locks_on_every_call():
    calls = []

    def recording_run(argv, **kwargs):
        calls.append(kwargs.get("env", {}))
        if "worktree" in argv and "list" in argv:
            return _proc(stdout="worktree /other\nHEAD abc\nbranch refs/heads/x\n")
        if "rev-parse" in argv:
            return _proc(stdout="abc\n")
        if "status" in argv:
            return _proc(stdout="")
        if "rev-list" in argv:
            return _proc(stdout="1\n")
        return _proc(rc=1)

    snap = SWP.snapshot("/repo", "/assigned", run=recording_run)
    assert snap["status"] == "ok"
    assert calls
    assert all(c.get("GIT_OPTIONAL_LOCKS") == "0" for c in calls)


def test_snapshot_never_raises_on_runner_throw():
    def throwing_run(argv, **kwargs):
        raise OSError("boom")

    snap = SWP.snapshot("/repo", "/assigned", run=throwing_run)
    assert snap["status"] == "indeterminate"


def test_compare_never_raises():
    assert SWP.compare(None, {}).get("status") == "indeterminate"


def test_snapshot_disappeared_path_not_error(tmp_path):
    main, wts = _linked_worktrees(tmp_path, count=2)
    sibling = wts[1]
    missing_path = str(tmp_path / "vanished-wt")
    fake2 = FakeRunner([
        _proc(stdout=(
            "worktree %s\nHEAD abc\nbranch refs/heads/main\n\n"
            "worktree %s\nHEAD def\nprunable gone\n"
        ) % (os.path.realpath(wts[0]), missing_path)),
    ])
    snap2 = SWP.snapshot(main, wts[0], run=fake2)
    assert snap2["status"] == "ok"
    entry2 = snap2["worktrees"][os.path.realpath(missing_path)]
    assert entry2["disappeared"] is True


def test_compare_reports_truncation():
    before = {"status": "ok", "truncated": True, "worktrees": {}}
    after = {"status": "ok", "truncated": False, "worktrees": {}}
    assert SWP.compare(before, after)["truncated"] is True


def test_worktree_list_failure_indeterminate():
    snap = SWP.snapshot("/repo", "/assigned", run=FakeRunner([_proc(rc=1)]))
    assert snap["status"] == "indeterminate"
    assert snap["reason"] == "worktree-list-failed"
