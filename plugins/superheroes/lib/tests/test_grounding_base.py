# plugins/superheroes/lib/tests/test_grounding_base.py
"""`definition_doc.py grounding-base`: a detached worktree at the freshly fetched default-branch tip."""
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import definition_doc  # noqa: E402

_DEFINITION_DOC = os.path.join(_LIB, "definition_doc.py")
_ID = ["-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "init.defaultBranch=main"]


def _git(cwd, *args):
    proc = subprocess.run(["git", *_ID, "-C", str(cwd), *args], capture_output=True, text=True)
    assert proc.returncode == 0, "git %s failed: %s" % (" ".join(args), proc.stderr)
    return proc.stdout.strip()


def _commit_file(repo, name):
    (repo / name).write_text(name + "\n")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", "add " + name)


@pytest.fixture
def stale(tmp_path):
    """A bare origin, a seed clone, and a session clone on branch `stale` cut before main moved.
    The session's local origin/main is not yet fetched past the old tip."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", *_ID, "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", *_ID, "clone", "-q", str(origin), str(seed)], check=True,
                   capture_output=True)
    _commit_file(seed, "a.txt")
    _git(seed, "push", "-q", "origin", "main")
    session = tmp_path / "session"
    subprocess.run(["git", *_ID, "clone", "-q", str(origin), str(session)], check=True,
                   capture_output=True)
    _git(session, "checkout", "-q", "-b", "stale")
    _commit_file(session, "branch-only.txt")
    old_tip = _git(session, "rev-parse", "origin/main")
    _commit_file(seed, "new-on-main.txt")
    _git(seed, "push", "-q", "origin", "main")
    return {"origin": origin, "seed": seed, "session": session, "old_tip": old_tip,
            "new_tip": _git(origin, "rev-parse", "main"), "dest": tmp_path / "view",
            "tmp": tmp_path}


def _worktrees(repo):
    return _git(repo, "worktree", "list", "--porcelain")


def _refusal(stale_fx, dest=None, root=None):
    with pytest.raises(definition_doc.GroundingBaseError) as info:
        definition_doc.grounding_base(root=str(root or stale_fx["session"]),
                                      dest=str(dest or stale_fx["dest"]))
    return info.value


def test_stale_branch_materializes_the_fetched_default_tip(stale):
    # Bites on: skipping the fetch (a stale local origin/main would be materialized) or grounding on the session branch
    session, dest = stale["session"], stale["dest"]
    assert stale["old_tip"] != stale["new_tip"]
    head_before = _git(session, "rev-parse", "HEAD")
    res = definition_doc.grounding_base(root=str(session), dest=str(dest))
    try:
        assert res["ok"] is True
        assert res["ref"] == "origin/main"
        assert res["sha"] == stale["new_tip"]
        assert res["path"] == os.path.realpath(str(dest))
        assert (dest / "new-on-main.txt").is_file()
        assert (dest / "a.txt").is_file()
        assert not (dest / "branch-only.txt").exists()
        assert _git(dest, "rev-parse", "HEAD") == stale["new_tip"]
        assert _git(session, "rev-parse", "HEAD") == head_before
        assert _git(session, "rev-parse", "--abbrev-ref", "HEAD") == "stale"
    finally:
        _git(session, "worktree", "remove", str(dest))
    assert not dest.exists()


def test_fetch_failure_refuses_and_creates_nothing(stale):
    # Bites on: ignoring the fetch's non-zero exit (an unreachable origin must refuse, not ground on a stale ref)
    session, dest = stale["session"], stale["dest"]
    _git(session, "remote", "set-url", "origin", str(stale["tmp"] / "nonexistent"))
    before = _worktrees(session)
    err = _refusal(stale)
    assert err.reason == "grounding-base-fetch-failed"
    assert not dest.exists()
    assert _worktrees(session) == before


def test_no_origin_refuses(stale):
    # Bites on: a missing origin treated as success instead of grounding-base-no-origin
    session, dest = stale["session"], stale["dest"]
    _git(session, "remote", "remove", "origin")
    before = _worktrees(session)
    err = _refusal(stale)
    assert err.reason == "grounding-base-no-origin"
    assert not dest.exists()
    assert _worktrees(session) == before


def test_unresolvable_origin_head_refuses(stale):
    # Bites on: guessing a default branch when origin/HEAD does not resolve
    session, dest = stale["session"], stale["dest"]
    _git(session, "remote", "set-head", "origin", "-d")
    before = _worktrees(session)
    err = _refusal(stale)
    assert err.reason == "grounding-base-default-unknown"
    assert "set-head" in str(err)
    assert not dest.exists()
    assert _worktrees(session) == before


def test_existing_dest_refuses(stale):
    # Bites on: materializing over an existing dest instead of grounding-base-dest-exists
    session, dest = stale["session"], stale["dest"]
    dest.mkdir()
    (dest / "keep.txt").write_text("keep\n")
    before = _worktrees(session)
    err = _refusal(stale)
    assert err.reason == "grounding-base-dest-exists"
    assert (dest / "keep.txt").read_text() == "keep\n"
    assert _worktrees(session) == before
    assert _git(session, "rev-parse", "origin/main") == stale["old_tip"]


def test_dest_inside_repo_refuses_before_fetching(stale):
    # Bites on: removing the dest-inside-repo check (or running it after the fetch, which would move origin/main)
    session = stale["session"]
    inside = session / "nested" / "view"
    before = _worktrees(session)
    err = _refusal(stale, dest=inside)
    assert err.reason == "grounding-base-dest-inside-repo"
    assert not inside.exists()
    assert _worktrees(session) == before
    assert _git(session, "rev-parse", "origin/main") == stale["old_tip"]


def test_dest_at_repo_top_refuses_as_existing(stale):
    # Bites on: the repo top itself accepted as a dest
    err = _refusal(stale, dest=stale["session"])
    assert err.reason in ("grounding-base-dest-exists", "grounding-base-dest-inside-repo")


def test_not_a_repo_refuses(tmp_path):
    # Bites on: an unresolvable repository root (a broken `.git` entry) not refused with grounding-base-not-a-repo
    broken = tmp_path / "broken"
    (broken / ".git").mkdir(parents=True)
    with pytest.raises(definition_doc.GroundingBaseError) as info:
        definition_doc.grounding_base(root=str(broken), dest=str(tmp_path / "view"))
    assert info.value.reason == "grounding-base-not-a-repo"
    assert not (tmp_path / "view").exists()


def test_greenfield_directory_has_no_origin(tmp_path):
    # Bites on: a directory with no git at all grounding on something instead of refusing (store_core.repo_root treats it as its own root, so the refusal is no-origin)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(definition_doc.GroundingBaseError) as info:
        definition_doc.grounding_base(root=str(plain), dest=str(tmp_path / "view"))
    assert info.value.reason == "grounding-base-no-origin"
    assert not (tmp_path / "view").exists()


def test_worktree_add_failure_refuses_and_registers_nothing(stale):
    # Bites on: a failed `git worktree add` reported as success
    session = stale["session"]
    blocker = stale["tmp"] / "blocker"
    blocker.write_text("a file, so nothing can be created beneath it\n")
    before = _worktrees(session)
    err = _refusal(stale, dest=blocker / "view")
    assert err.reason == "grounding-base-worktree-failed"
    assert _worktrees(session) == before


def _cli(*args):
    return subprocess.run([sys.executable, "-B", _DEFINITION_DOC, "grounding-base", *args],
                          capture_output=True, text=True, timeout=120)


def test_cli_success_prints_exactly_the_contract_keys(stale):
    # Bites on: the CLI success shape drifting from {ok, ref, sha, path} or exiting non-zero
    session, dest = stale["session"], stale["dest"]
    proc = _cli("--root", str(session), "--dest", str(dest))
    try:
        assert proc.returncode == 0, proc.stderr
        got = json.loads(proc.stdout)
        assert list(got) == ["ok", "ref", "sha", "path"]
        assert got["ok"] is True and got["sha"] == stale["new_tip"]
        assert got["path"] == os.path.realpath(str(dest))
    finally:
        _git(session, "worktree", "remove", str(dest))


def test_cli_refusal_prints_exactly_the_contract_keys_on_stdout(stale):
    # Bites on: the CLI refusal shape drifting from {ok, reason, detail}, going to stderr, or exiting 0
    session, dest = stale["session"], stale["dest"]
    dest.mkdir()
    before = _worktrees(session)
    proc = _cli("--root", str(session), "--dest", str(dest))
    assert proc.returncode == 1
    got = json.loads(proc.stdout)
    assert list(got) == ["ok", "reason", "detail"]
    assert got["ok"] is False and got["reason"] == "grounding-base-dest-exists"
    assert _worktrees(session) == before
