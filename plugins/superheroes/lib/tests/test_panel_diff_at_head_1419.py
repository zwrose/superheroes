#!/usr/bin/env python3
"""#1419 — unknown-surface full panel reviews git-derived head diff, never a stale reviewed diff."""
import importlib.util
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

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


def _unknown_surface_state(config):
    state = RD.new_state(config)
    state["round"] = 2
    state["rounds"] = {"2": {}}
    state["_headDiffUnknown"] = True
    state["_headDiffSource"] = "unknown"
    state["decisions"] = []
    RD._enter_delta_round(state, config)
    return state


_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]


def test_b1_panel_diff_at_head_after_fixer_without_head_diff(tmp_path):
    repo, base_sha, diff_commit1 = _init_two_commit_repo(tmp_path)
    d = str(tmp_path / "session")
    cfg = _cfg(verifyCommand="pytest -q", diff=diff_commit1, repoRoot=repo, baseRef=base_sha)
    diff_round1 = diff_commit1

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER and rnd == 1:
            _commit_file(repo, "f.py", "fixed head\n", "fixer commit")
            return {"fixes": [{"file": "f.py"}], "changedSubjects": ["Code"]}
        return _responder(round1_findings=_A_FINDING)(phase, payload, rnd)

    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      respond(n["phase"], n["payload"], n["round"]))
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_VERIFY
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"], {"result": "pass"})
    assert s2["ok"], s2
    n3 = RD.cmd_next(d)
    assert n3["phase"] == RD.P_PANEL
    ok, state = RD.load_state(d)
    assert ok
    panel_round = state["round"]
    assert state["rounds"][str(panel_round)]["panelDiffSource"] == "git-derived"
    diff_commit2 = _git_diff(repo, base_sha)
    assert diff_commit2 != diff_round1
    rdir = round_records.round_dir(d, panel_round)
    materialized = open(os.path.join(rdir, "diff.txt"), encoding="utf-8").read()
    assert materialized == diff_commit2
    assert materialized != diff_round1


@pytest.mark.parametrize(
    "edge_id,config_over,monkey",
    [
        ("repoRoot missing", {"repoRoot": None, "baseRef": "abc"}, None),
        ("baseRef missing", {"baseRef": None}, "repo"),
        ("baseRef not a commit", {"baseRef": "not-a-commit"}, "repo"),
        ("empty diff", {}, "empty"),
    ],
)
def test_b2_parks_when_panel_diff_underivable(tmp_path, edge_id, config_over, monkey):
    repo, base_sha, _diff = _init_two_commit_repo(tmp_path)
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)
    cfg.update(config_over)
    if monkey == "repo":
        pass
    elif monkey == "empty":
        cfg["baseRef"] = _rev_parse(repo)
    state = _unknown_surface_state(cfg)
    assert state["terminal"] == "cannot-certify"
    assert state["certification"]["reason"].startswith(RD.PANEL_DIFF_UNDERIVABLE_CAUSE)
    assert state["step"] != RD.P_PANEL


def test_b2_git_unavailable_parks(tmp_path, monkeypatch):
    repo, base_sha, _diff = _init_two_commit_repo(tmp_path)
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)
    real_run = subprocess.run

    def _raise_file_not_found(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(RD.subprocess, "run", _raise_file_not_found)
    state = _unknown_surface_state(cfg)
    assert state["certification"]["reason"].startswith(
        "%s: git unavailable" % RD.PANEL_DIFF_UNDERIVABLE_CAUSE)
    assert state["step"] != RD.P_PANEL


def test_b2_git_diff_nonzero_parks(tmp_path, monkeypatch):
    repo, base_sha, _diff = _init_two_commit_repo(tmp_path)
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)
    real_run = subprocess.run

    def _wrapped(*args, **kwargs):
        cmd = args[0] if args else []
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "diff":
            class _Proc:
                returncode = 128
                stdout = b""
                stderr = b"fatal: bad"
            return _Proc()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(RD.subprocess, "run", _wrapped)
    state = _unknown_surface_state(cfg)
    assert "git diff exit" in state["certification"]["reason"]
    assert state["step"] != RD.P_PANEL


def test_b2_git_timeout_parks(tmp_path, monkeypatch):
    repo, base_sha, _diff = _init_two_commit_repo(tmp_path)
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=120)

    monkeypatch.setattr(RD.subprocess, "run", _timeout)
    state = _unknown_surface_state(cfg)
    assert state["certification"]["reason"].startswith(RD.PANEL_DIFF_UNDERIVABLE_CAUSE)
    assert state["step"] != RD.P_PANEL


def test_b2_git_diff_non_utf8_parks(tmp_path, monkeypatch):
    repo, base_sha, _diff = _init_two_commit_repo(tmp_path)
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)
    real_run = subprocess.run

    def _wrapped(*args, **kwargs):
        cmd = args[0] if args else []
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "diff":
            class _Proc:
                returncode = 0
                stdout = b"diff --git a/f.py b/f.py\n+\xff\n"
                stderr = b""
            return _Proc()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(RD.subprocess, "run", _wrapped)
    state = _unknown_surface_state(cfg)
    assert state["terminal"] == "cannot-certify"
    assert state["certification"]["reason"].startswith(RD.PANEL_DIFF_UNDERIVABLE_CAUSE)
    assert "diff not UTF-8" in state["certification"]["reason"]
    assert state["step"] != RD.P_PANEL


def test_b3_derived_diff_matches_git_cli_byte_exact(tmp_path):
    trailing = "line one\nline two   \n"
    repo, base_sha, _ = _init_two_commit_repo(
        tmp_path, first_body="base\n", second_body=trailing, path="ws.py")
    cfg = _cfg(repoRoot=repo, baseRef=base_sha)
    state = _unknown_surface_state(cfg)
    assert state.get("terminal") != "cannot-certify"
    expected = _git_diff(repo, base_sha)
    assert state["reviewedDiff"] == expected
    assert state["headDiff"] == expected
