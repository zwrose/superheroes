import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BL = _load("build_lane")
RD = _load("round_driver")
SC = _load("store_core")


def _init_repo(tmp_path, branch="main"):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", branch], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    return str(repo)


def _cli(*args):
    proc = subprocess.run(
        [sys.executable, "-B", os.path.join(_LIB, "build_lane.py"), *args],
        text=True, capture_output=True,
    )
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    body = json.loads(lines[-1]) if lines else {}
    return proc.returncode, body


def test_declare_refuses_a_non_full_lane(tmp_path):
    repo = _init_repo(tmp_path)
    rc, body = _cli("declare", "--repo-root", repo, "--lane", "light", "--issue", "624")
    assert rc != 0
    assert body == {"ok": False, "reason": "lane must be full"}


def test_declare_refuses_a_missing_issue(tmp_path):
    repo = _init_repo(tmp_path)
    rc, body = _cli("declare", "--repo-root", repo, "--lane", "full", "--issue", "  ")
    assert rc != 0
    assert body["ok"] is False
    assert "issue" in body["reason"]


def test_declare_refuses_non_numeric_issue(tmp_path):
    repo = _init_repo(tmp_path)
    rc, body = _cli("declare", "--repo-root", repo, "--lane", "full", "--issue", "#624")
    assert rc != 0
    assert body == {"ok": False, "reason": "issue must be numeric"}


def test_marker_carries_the_branch(tmp_path):
    repo = _init_repo(tmp_path, branch="feature/wo9")
    rc, body = _cli("declare", "--repo-root", repo, "--lane", "full", "--issue", "624")
    assert rc == 0 and body["ok"]
    with open(body["path"], encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk["branch"] == "feature/wo9"
    assert body["marker"]["branch"] == "feature/wo9"


def test_atomic_write_uses_temp_and_replace(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    calls = {"mkstemp": False, "replace": False}
    orig_mkstemp = BL.tempfile.mkstemp
    orig_replace = os.replace

    def track_mkstemp(*a, **k):
        calls["mkstemp"] = True
        return orig_mkstemp(*a, **k)

    def track_replace(src, dst):
        calls["replace"] = True
        return orig_replace(src, dst)

    monkeypatch.setattr(BL.tempfile, "mkstemp", track_mkstemp)
    monkeypatch.setattr(os, "replace", track_replace)
    result = BL.declare(repo, "full", "624")
    assert result["ok"]
    assert calls["mkstemp"] and calls["replace"]


def test_declare_success_emits_marker(tmp_path):
    repo = _init_repo(tmp_path)
    result = BL.declare(repo, "full", "930")
    assert result["ok"]
    assert os.path.isfile(result["path"])
    with open(result["path"], encoding="utf-8") as fh:
        marker = json.load(fh)
    assert marker["schema"] == BL.BUILD_LANE_SCHEMA
    assert marker["lane"] == "full"
    assert marker["issue"] == "930"
    assert marker["repoRoot"] == os.path.realpath(repo)


def test_redeclare_identical_values_is_idempotent(tmp_path):
    repo = _init_repo(tmp_path)
    first = BL.declare(repo, "full", "624")
    with open(first["path"], encoding="utf-8") as fh:
        before = fh.read()
    second = BL.declare(repo, "full", "624")
    assert second["ok"]
    with open(second["path"], encoding="utf-8") as fh:
        after = fh.read()
    assert json.loads(before)["issue"] == json.loads(after)["issue"]
    assert json.loads(before)["branch"] == json.loads(after)["branch"]


def test_redeclare_different_issue_overwrites(tmp_path):
    repo = _init_repo(tmp_path)
    BL.declare(repo, "full", "624")
    second = BL.declare(repo, "full", "930")
    assert second["ok"]
    with open(second["path"], encoding="utf-8") as fh:
        marker = json.load(fh)
    assert marker["issue"] == "930"


def test_declare_refuses_non_repository(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    result = BL.declare(str(plain), "full", "624")
    assert result["ok"] is False
    assert result["reason"] == "not a repository"


def test_declare_refuses_detached_head(tmp_path):
    repo = _init_repo(tmp_path)
    sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(["git", "-C", repo, "checkout", "--detach", sha])
    result = BL.declare(repo, "full", "624")
    assert result["ok"] is False
    assert "detached" in result["reason"].lower()


def test_clear_when_no_marker_exists(tmp_path):
    repo = _init_repo(tmp_path)
    result = BL.clear(repo)
    assert result == {"ok": True, "removed": False}


def test_clear_removes_marker(tmp_path):
    repo = _init_repo(tmp_path)
    declared = BL.declare(repo, "full", "624")
    assert declared["ok"]
    cleared = BL.clear(repo)
    assert cleared == {"ok": True, "removed": True}
    assert not os.path.isfile(declared["path"])


def test_declare_refuses_unwritable_marker(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    path = BL._marker_path(repo)

    def boom(path, payload):
        raise OSError("permission denied")

    monkeypatch.setattr(BL, "_atomic_write_json", boom)
    result = BL.declare(repo, "full", "624")
    assert result["ok"] is False
    assert "unwritable" in result["reason"]
    assert not os.path.isfile(path)


def test_bootstrap_marker_carries_branch(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    repo = os.path.join(d, "_gitrepo")
    os.makedirs(repo, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "review-branch"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    toplevel = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], text=True).strip()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"repoRoot": toplevel}, fh)
    RD._bootstrap_review_session_marker(d)
    gitdir = SC.get_worktree_gitdir(repo)
    marker_path = os.path.join(gitdir, RD.SIDECAR_DIRNAME, RD._REVIEW_SESSION_MARKER)
    assert os.path.isfile(marker_path)
    with open(marker_path, encoding="utf-8") as fh:
        marker = json.load(fh)
    assert marker["branch"] == "review-branch"


def test_bootstrap_marker_failure_is_journaled(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    repo = os.path.join(d, "_gitrepo")
    os.makedirs(repo, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(["git", "-C", repo, "checkout", "--detach", sha])
    toplevel = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], text=True).strip()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"repoRoot": toplevel}, fh)
    RD._bootstrap_review_session_marker(d)
    journal = RD.read_journal(d)
    assert any(e.get("cmd") == "bootstrap-review-session-marker"
               and e.get("outcome") == "failed"
               and "detached" in e.get("reason", "").lower() for e in journal)
