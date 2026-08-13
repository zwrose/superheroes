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


def _wt(path, *, head="a", porcelain="p", reflog=1, readable=True, **extra):
    entry = {
        "path": path,
        "readable": readable,
        "headSha": head,
        "headMeasured": readable,
        "porcelainSha256": porcelain,
        "porcelainMeasured": readable,
        "reflogCount": reflog,
        "reflogMeasured": readable and reflog is not None,
    }
    entry.update(extra)
    return entry


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


# axis: each of the three change signals (head sha, porcelain sha256, reflog count) is compared independently
def test_compare_head_delta():
    before = {
        "status": "ok",
        "truncated": False,
        "worktrees": {"/wt": _wt("/wt", head="a")},
    }
    after = {
        "status": "ok",
        "truncated": False,
        "worktrees": {"/wt": _wt("/wt", head="b")},
    }
    result = SWP.compare(before, after)
    assert result["status"] == "observed"
    assert any(d["kind"] == "head-changed" for d in result["deltas"])
    assert "coverage" in result


def test_compare_porcelain_delta():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": _wt("/wt", porcelain="p1")},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": _wt("/wt", porcelain="p2")},
    }
    result = SWP.compare(before, after)
    assert any(d["kind"] == "porcelain-changed" for d in result["deltas"])


def test_compare_reflog_delta():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": _wt("/wt", reflog=1)},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": _wt("/wt", reflog=2)},
    }
    result = SWP.compare(before, after)
    assert any(d["kind"] == "reflog-changed" for d in result["deltas"])


def test_compare_null_reflog_to_number_is_not_delta():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {
            "/wt": _wt("/wt", reflog=None, reflogMeasured=False),
        },
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/wt": _wt("/wt", reflog=3)},
    }
    result = SWP.compare(before, after)
    assert result["deltas"] == []
    assert result["coverage"]["signals"]["reflogCount"]["measuredBefore"] == 0
    assert result["coverage"]["signals"]["reflogCount"]["measuredAfter"] == 1


def test_compare_appeared_and_disappeared():
    before = {
        "status": "ok", "truncated": False,
        "worktrees": {"/gone": _wt("/gone")},
    }
    after = {
        "status": "ok", "truncated": False,
        "worktrees": {"/new": _wt("/new", head="b", porcelain="q")},
    }
    result = SWP.compare(before, after)
    kinds = {d["kind"] for d in result["deltas"]}
    assert "appeared" in kinds
    assert "disappeared" in kinds


def test_snapshot_deadline_exhaustion_on_worktree_list_returns_indeterminate():
    def slow_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    snap = SWP.snapshot("/repo", "/assigned", deadline=0.001, run=slow_run)
    assert snap["status"] == "indeterminate"
    assert snap["reason"] == "deadline-exhausted"
    assert snap.get("worktrees") in (None, {})


def test_snapshot_truncation_reported(tmp_path, monkeypatch):
    main, _wts = _linked_worktrees(tmp_path, count=3)
    snap = SWP.snapshot(main, _wts[0], max_worktrees=1)
    assert snap["status"] == "ok"
    assert snap["truncated"] is True
    assert len(snap["worktrees"]) == 1


def test_git_optional_locks_on_every_call(tmp_path):
    calls = []
    assigned = str(tmp_path / "assigned")
    sibling = str(tmp_path / "other")
    os.makedirs(assigned)
    os.makedirs(sibling)

    def recording_run(argv, **kwargs):
        calls.append(kwargs.get("env", {}))
        if "worktree" in argv and "list" in argv:
            return _proc(stdout=(
                "worktree %s\nHEAD abc\nbranch refs/heads/main\n\n"
                "worktree %s\nHEAD def\nbranch refs/heads/x\n"
            ) % (assigned, sibling))
        if "rev-parse" in argv:
            return _proc(stdout="abc\n")
        if "status" in argv:
            return _proc(stdout="")
        if "rev-list" in argv:
            return _proc(stdout="1\n")
        return _proc(rc=1)

    snap = SWP.snapshot(str(tmp_path / "repo"), assigned, run=recording_run)
    assert snap["status"] == "ok"
    assert len(calls) == 4
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


def test_snapshot_one_unreadable_sibling_does_not_abort_snapshot(tmp_path):
    assigned = str(tmp_path / "assigned")
    good_path = str(tmp_path / "good")
    bad_path = str(tmp_path / "bad")
    for path in (assigned, good_path, bad_path):
        os.makedirs(path)

    def recording_run(argv, **kwargs):
        if "worktree" in argv and "list" in argv:
            return _proc(stdout=(
                "worktree %s\nHEAD aaa\nbranch refs/heads/main\n\n"
                "worktree %s\nHEAD bbb\nbranch refs/heads/good\n\n"
                "worktree %s\nHEAD ccc\nbranch refs/heads/bad\n"
            ) % (assigned, good_path, bad_path))
        cwd = argv[argv.index("-C") + 1] if "-C" in argv else ""
        if "rev-parse" in argv and os.path.realpath(cwd) == os.path.realpath(bad_path):
            return _proc(rc=1, stderr="fatal: ambiguous argument 'HEAD'\n")
        if "rev-parse" in argv:
            return _proc(stdout="deadbeef\n")
        if "status" in argv:
            return _proc(stdout="")
        if "rev-list" in argv:
            return _proc(stdout="2\n")
        return _proc(rc=1)

    snap = SWP.snapshot(str(tmp_path / "repo"), assigned, run=recording_run)
    assert snap["status"] == "ok"
    assert os.path.realpath(good_path) in snap["worktrees"]
    bad_entry = snap["worktrees"][os.path.realpath(bad_path)]
    assert bad_entry["readable"] is False
    assert bad_entry["reason"]


def test_compare_unreadable_sibling_reports_kind():
    good = os.path.realpath("/good")
    bad = os.path.realpath("/bad")
    before = {
        "status": "ok",
        "truncated": False,
        "worktrees": {
            good: _wt(good),
            bad: SWP._unreadable_entry(bad, "head-failed"),
        },
    }
    after = dict(before)
    result = SWP.compare(before, after)
    assert any(d["kind"] == "unreadable" for d in result["deltas"])


def test_capture_sibling_baseline_never_passes_none_deadline(monkeypatch):
    """_capture_sibling_baseline must always bound snapshot, including when preflight_timeout is None."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "engine_dispatch",
        os.path.join(_HERE, "..", "engine_dispatch.py"),
    )
    ed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ed)
    captured = []

    def recording_snapshot(repo_root, assigned_cwd, *, deadline=None, run=None, max_worktrees=None):
        captured.append(deadline)
        return {"status": "ok", "truncated": False, "worktrees": {}}

    monkeypatch.setattr(ed.sibling_worktree_probe, "snapshot", recording_snapshot)
    for preflight_timeout in (None, 0, 1, 120, 1000):
        captured.clear()
        ed._capture_sibling_baseline("/repo", "/assigned", preflight_timeout=preflight_timeout)
        assert len(captured) == 1
        assert captured[0] is not None
