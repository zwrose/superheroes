"""Part 2 of C6-WO-B: in a cloud session `dispatch_review` makes the clone's history complete, and
fetches origin/main, right before it builds the sanitized view. Real git, no network."""
import json
import os
import subprocess

import pytest

import engine_dispatch
from test_engine_dispatch import FakeRunner, _codex_seat, _valid_prompt

SHALLOW = "sanitized-view-diff-base-shallow"
UNRESOLVED = "sanitized-view-diff-base-unresolved"
_GIT_IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid",
                 "-c", "commit.gpgsign=false"]


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    proc = subprocess.run(["git", *_GIT_IDENTITY, *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def make_shallow_clone(tmp_path):
    """A depth-1 clone of a bare origin holding three commits, with refs/remotes/origin/main
    deleted. Returns (clone path, [first, second, third commit of origin])."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    shas = []
    for index in range(3):
        (work / "a.txt").write_text("version %d\n" % index)
        _git(work, "add", "a.txt")
        _git(work, "commit", "-q", "-m", "commit %d" % index)
        shas.append(_git(work, "rev-parse", "HEAD"))
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--depth", "1", "file://" + str(origin), str(clone))
    _git(clone, "update-ref", "-d", "refs/remotes/origin/main")
    return str(clone), shas


def clean_review_runner():
    """A fake engine whose one reply is a valid review with no findings."""
    reply = json.dumps({"findings": [], "investigated": ["a.txt"]})
    return FakeRunner([(reply, False, 0, "")])


def review(tmp_path, clone, diff_base, runner, **extra):
    return engine_dispatch.dispatch_review(
        seat=_codex_seat(), prompt_path=_valid_prompt(tmp_path), repo_root=clone,
        run_engine=runner, diff_base=diff_base, **extra)


def is_shallow(clone):
    return _git(clone, "rev-parse", "--is-shallow-repository") == "true"


def test_cloud_review_of_a_shallow_clone_gets_history_and_runs(tmp_path, monkeypatch):
    # Axis: DoD row. A shallow clone with no origin/main gets full history and origin/main before
    # the review is dispatched, and the review then runs instead of refusing.
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    clone, shas = make_shallow_clone(tmp_path)
    assert is_shallow(clone)
    runner = clean_review_runner()
    res = review(tmp_path, clone, shas[0], runner)
    assert res.get("detail") != SHALLOW, res
    assert res["ok"] is True, res
    assert len(runner.calls) == 1
    assert not is_shallow(clone)
    assert _git(clone, "rev-parse", "--verify", "refs/remotes/origin/main") == shas[2]
    assert res["cloudHistory"] == {"ok": True, "reason": None,
                                   "fetched": ["unshallow", "origin/main"]}


def test_review_of_a_shallow_clone_outside_a_cloud_session_still_refuses(tmp_path, monkeypatch):
    # Axis: without CLAUDE_CODE_REMOTE nothing is fetched. A diff base the shallow clone holds (its
    # own tip) gets today's shallow refusal; the origin's first commit, which the clone lacks, gets
    # today's unresolved refusal. Neither runs the engine, and neither carries a cloudHistory key.
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    clone, shas = make_shallow_clone(tmp_path)
    for base, detail in ((shas[2], SHALLOW), (shas[0], UNRESOLVED)):
        runner = clean_review_runner()
        res = review(tmp_path, clone, base, runner)
        assert res["ok"] is False
        assert res["detail"] == detail
        assert res["attempts"] == 0
        assert runner.calls == []
        assert is_shallow(clone)
        assert "cloudHistory" not in res


def test_cloud_history_that_is_not_ok_still_refuses_with_the_unchanged_detail(
        tmp_path, monkeypatch):
    # Axis: a failed history answer never blocks and never opens the gate: build_view still
    # refuses with exactly its own detail, and the answer rides along as cloudHistory.
    import cloud_builder
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    answer = {"ok": False, "reason": "unshallow-failed", "fetched": []}
    monkeypatch.setattr(cloud_builder, "ensure_history", lambda repo_root, **kw: answer)
    clone, shas = make_shallow_clone(tmp_path)
    runner = clean_review_runner()
    res = review(tmp_path, clone, shas[2], runner)
    assert res["ok"] is False and res["detail"] == SHALLOW and res["attempts"] == 0
    assert runner.calls == []
    assert res["cloudHistory"] == answer


def test_cloud_history_that_raises_is_recorded_and_review_goes_on_to_build_view(
        tmp_path, monkeypatch):
    # Axis: G1. ensure_history raising is caught, recorded as raised, and build_view still runs.
    import cloud_builder
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")

    def boom(repo_root, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(cloud_builder, "ensure_history", boom)
    clone, shas = make_shallow_clone(tmp_path)
    res = review(tmp_path, clone, shas[2], clean_review_runner())
    assert res["cloudHistory"] == {"ok": False, "reason": "raised"}
    assert res["detail"] == SHALLOW


def test_ensure_history_is_given_the_validated_repo_root_before_build_view(
        tmp_path, monkeypatch):
    # Axis: ordering and argument. ensure_history gets the repo root build_view gets, and runs first.
    import cloud_builder
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    order = []
    monkeypatch.setattr(cloud_builder, "ensure_history",
                        lambda repo_root, **kw: order.append(("history", repo_root))
                        or {"ok": True, "reason": None, "fetched": []})

    def build_view(repo_root, **kw):
        order.append(("view", repo_root))
        raise engine_dispatch.sanitized_view.SanitizedViewError("stop-here")

    clone, shas = make_shallow_clone(tmp_path)
    res = engine_dispatch.dispatch_review(
        seat=_codex_seat(), prompt_path=_valid_prompt(tmp_path), repo_root=clone,
        run_engine=clean_review_runner(), build_view=build_view, diff_base=shas[0])
    assert [name for name, _ in order] == ["history", "view"]
    assert order[0][1] == order[1][1]
    assert res["detail"] == "stop-here"
