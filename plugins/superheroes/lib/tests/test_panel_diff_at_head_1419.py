#!/usr/bin/env python3
"""#1419 — the post-fix head diff is git-derived at the fix-fold head, never a stale reviewed diff; a fix
surface git cannot derive hands the PR back (the unknown-surface panel it once fed is gone)."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from session_checkout import seed_session_meta  # noqa: E402

import review_diff_bytes as rdb  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records  # noqa: E402

from test_round_driver import (  # noqa: E402
    _cfg, _drive_to_phase, _responder,
)

_GIT_ID = (
    "-c", "user.email=t@t.local",
    "-c", "user.name=t",
)


def _git(repo, *args):
    return subprocess.run(
        ["git", *_GIT_ID, "-C", repo, *args],
        check=True, capture_output=True, text=True)


def _rev_parse(repo):
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _git_diff(repo, base):
    return subprocess.run(
        ["git", "diff", "%s...HEAD" % base],
        cwd=repo, capture_output=True, text=False, check=True).stdout.decode("utf-8")


def _git_diff_at(repo, base, head):
    return subprocess.run(
        ["git", "diff", "%s...%s" % (base, head)],
        cwd=repo, capture_output=True, text=False, check=True).stdout.decode("utf-8")


def _init_two_commit_repo(tmp_path, first_body="old\n", second_body="new\n", path="f.py"):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo), "init", "-q", "-b", "main")
    p = repo / path
    p.write_text(first_body, encoding="utf-8")
    _git(str(repo), "add", path)
    _git(str(repo), "commit", "-qm", "base")
    base_sha = _rev_parse(str(repo))
    p.write_text(second_body, encoding="utf-8")
    _git(str(repo), "add", path)
    _git(str(repo), "commit", "-qm", "head")
    return str(repo), base_sha, _git_diff(str(repo), base_sha)


def _commit_file(repo, path, body, message="fix"):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(body)
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", message)


_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
               "consequence": "a reviewer-found defect stays in the change"}]


def test_b1_fixer_without_head_diff_derives_git_and_audits(tmp_path):
    repo, base_sha, diff_commit1 = _init_two_commit_repo(tmp_path)
    d = str(tmp_path / "session")
    seed_session_meta(d, repo)
    cfg = _cfg(verifyCommand="pytest -q", diff=diff_commit1, repoRoot=repo, baseRef=base_sha)
    diff_round1 = diff_commit1

    def respond(phase, payload, rnd):
        if phase == RD.P_APPLY_FIXES and rnd == 1:
            _commit_file(repo, "f.py", "fixed head\n", "fixer commit")
            return {"fixes": [{"file": "f.py"}], "changedSubjects": ["Code"]}
        return _responder(round1_findings=_A_FINDING)(phase, payload, rnd)

    n = _drive_to_phase(d, cfg, respond, RD.P_APPLY_FIXES)
    fix_round = n["round"]
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      respond(n["phase"], n["payload"], n["round"]))
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_AUDITS
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"][str(fix_round)]["headDiffSource"] == "git"
    diff_commit2 = _git_diff(repo, base_sha)
    assert diff_commit2 != diff_round1
    assert state["headDiff"] == diff_commit2
    assert state["reviewedDiff"] == diff_commit2
    assert state["reviewedDiff"] != diff_round1


def test_b1_a_fix_whose_post_fix_diff_git_cannot_derive_hands_the_pr_back(tmp_path, monkeypatch):
    """Re-pinned from the unknown-surface panel tests (b1-b4): the post-fix diff the fold derives from
    git refuses once, so the surface is unknown; the next round hands the PR back with its findings
    open and no panel is scheduled. The tests of the removed panel-diff refresh and its park
    (the `panel-diff-underivable` cause, the verify-then-panel gate) are deleted with them."""
    repo, base_sha, diff_round1 = _init_two_commit_repo(tmp_path)
    real_derive = RD._derive_panel_diff_at_head
    calls = []

    def refuse_first(config, head_sha):
        calls.append(head_sha)
        if len(calls) == 1:
            return None, "git unavailable: forced for the unknown-surface path"
        return real_derive(config, head_sha)

    monkeypatch.setattr(RD, "_derive_panel_diff_at_head", refuse_first)
    d = str(tmp_path / "session")
    seed_session_meta(d, repo)
    cfg = _cfg(verifyCommand="pytest -q", diff=diff_round1, repoRoot=repo, baseRef=base_sha)

    def respond(phase, payload, rnd):
        if phase == RD.P_APPLY_FIXES and rnd == 1:
            _commit_file(repo, "f.py", "fixed head\n", "fixer commit")
            return {"fixes": [{"file": "f.py"}], "changedSubjects": ["Code"]}
        return _responder(round1_findings=_A_FINDING)(phase, payload, rnd)

    n = _drive_to_phase(d, cfg, respond, RD.P_APPLY_FIXES)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      respond(n["phase"], n["payload"], n["round"]))
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_TERMINAL
    ok, state = RD.load_state(d)
    assert ok
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"
    assert state["step"] != RD.P_PANEL
    assert not any(dec["kind"] == "unknown-surface" for dec in state["decisions"])


def test_b4_producer_refuses_live_head(tmp_path):
    repo, base_sha, _ = _init_two_commit_repo(tmp_path)
    head_sha = _rev_parse(repo)
    with pytest.raises(ValueError, match="explicit commit"):
        rdb.run_git_diff_three_dot(repo, base_sha, "HEAD", timeout=10)
    with pytest.raises(ValueError, match="explicit commit"):
        rdb.run_git_diff_three_dot(repo, base_sha, " head ", timeout=10)
    with pytest.raises(ValueError, match="explicit commit"):
        rdb.run_git_diff_three_dot(repo, base_sha, None, timeout=10)
    proc = rdb.run_git_diff_three_dot(repo, base_sha, head_sha, timeout=10)
    assert proc.returncode == 0


_NON_FULL_OID_CASES = [
    "HEAD",
    "@",
    "HEAD~0",
    "ORIG_HEAD",
    "main",
    "abc1234",
    "a" * 39,
    "a" * 41,
    "a" * 40 + " ",
    "",
    None,
    123,
]


@pytest.mark.parametrize("which", ["base_sha", "head_sha"])
@pytest.mark.parametrize("bad_ref", _NON_FULL_OID_CASES, ids=lambda v: repr(v))
def test_v1_explicit_commit_guard_rejects_non_full_oid(tmp_path, which, bad_ref, monkeypatch):
    repo, base_sha, _ = _init_two_commit_repo(tmp_path)
    head_sha = _rev_parse(repo)
    calls = []

    def _record_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(rdb.subprocess, "run", _record_run)
    kwargs = {"repo_root": repo, "timeout": 10}
    kwargs["base_sha"] = bad_ref if which == "base_sha" else base_sha
    kwargs["head_sha"] = bad_ref if which == "head_sha" else head_sha
    with pytest.raises(ValueError, match="explicit commit"):
        rdb.run_git_diff_three_dot(**kwargs)
    assert calls == []


def test_v1_explicit_commit_guard_accepts_full_oid_lengths(tmp_path, monkeypatch):
    repo, base_sha, _ = _init_two_commit_repo(tmp_path)
    head_sha = _rev_parse(repo)
    sha256_placeholder = "b" * 64
    calls = []

    def _fake_run(*args, **kwargs):
        calls.append(1)
        class _Proc:
            returncode = 0
            stdout = b""
            stderr = b""
        return _Proc()

    monkeypatch.setattr(rdb.subprocess, "run", _fake_run)
    rdb.run_git_diff_three_dot(repo, base_sha, head_sha, timeout=10)
    rdb.run_git_diff_three_dot(repo, base_sha, sha256_placeholder, timeout=10)
    assert len(calls) == 2


def test_v1_derive_panel_diff_resolves_short_base_ref(tmp_path):
    repo, base_sha, _ = _init_two_commit_repo(tmp_path)
    head_sha = _rev_parse(repo)
    short_base = base_sha[:7]
    cfg = _cfg(repoRoot=repo, baseRef=short_base, **{RD.FIX_FOLD_HEAD_KEY: head_sha})
    diff_text, err = RD._derive_panel_diff_at_head(cfg, head_sha)
    assert err is None
    assert diff_text == _git_diff_at(repo, base_sha, head_sha)


def test_v2_derive_panel_diff_maps_head_value_error(tmp_path):
    repo, base_sha, _ = _init_two_commit_repo(tmp_path)
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)
    diff_text, detail = RD._derive_panel_diff_at_head(cfg, "HEAD")
    assert diff_text is None
    assert detail is not None
    assert "explicit commit" in detail
