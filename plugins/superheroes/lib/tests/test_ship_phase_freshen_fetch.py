# plugins/superheroes/lib/tests/test_ship_phase_freshen_fetch.py
"""B3 (#315): ship-freshen must NOT report "already up to date" when `git fetch origin` failed.

The detector this fix ships: a REAL `git fetch` against a broken remote (origin URL points at a
nonexistent path — no monkeypatched runner) leaves the local base ref stale, so the merge is a
no-op. The pre-fix code reported "already up to date" — a network failure masquerading as
freshness (PHILOSOPHY promise 5). The fixed leaf reports the fetch failure AND journals a
`notify` breadcrumb the owner can read back.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLI = str(HERE.parent / "ship_phase.py")
LIB = str(HERE.parent)
sys.path.insert(0, LIB)
import control_plane  # noqa: E402
import journal  # noqa: E402

_GE = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(clone, *args):
    subprocess.run(["git", "-C", str(clone), *args], env=dict(os.environ, **_GE), check=True,
                   capture_output=True)


def _repo_with_broken_origin(tmp_path):
    """A clone on a feature branch AT origin/main's tip (so a merge of main is a no-op), whose
    origin URL is then repointed at a nonexistent path so any `git fetch origin` fails for real."""
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    _git(clone, "commit", "--allow-empty", "-m", "base")
    _git(clone, "push", "origin", "HEAD:main", "-u", "-q")
    _git(clone, "checkout", "-q", "-b", "feature")   # feature is AT main's tip -> contains main
    # Break the remote: fetch will now fail (nonexistent path) but local 'main' still resolves.
    _git(clone, "remote", "set-url", "origin", str(tmp_path / "does-not-exist.git"))
    # sanity: a real fetch fails
    rc = subprocess.run(["git", "-C", str(clone), "fetch", "--quiet", "origin"],
                        capture_output=True).returncode
    assert rc != 0, "precondition: fetch against the broken origin must fail"
    return clone


def _run_freshen(clone):
    env = os.environ.copy()
    env["PYTHONPATH"] = LIB
    proc = subprocess.run(
        [sys.executable, CLI, "--step", "freshen", "--work-item", "wi", "--worktree", str(clone)],
        cwd=str(clone), env=env, capture_output=True, text=True)
    return json.loads(proc.stdout)


def test_freshen_fetch_failure_is_not_reported_as_up_to_date(tmp_path):
    clone = _repo_with_broken_origin(tmp_path)
    out = _run_freshen(clone)
    assert "already up to date" not in (out.get("reason") or "").lower(), (
        "a failed fetch must not masquerade as freshness, got %r" % out)
    assert "fetch failed" in (out.get("reason") or "").lower(), (
        "the reason must disclose the fetch failure, got %r" % out)


def test_freshen_fetch_failure_journals_a_breadcrumb(tmp_path):
    clone = _repo_with_broken_origin(tmp_path)
    _run_freshen(clone)
    events = journal.read_events(control_plane.paths(str(clone), "wi")["events"])
    notes = [e for e in events if isinstance(e, dict) and e.get("type") == "notify"]
    assert any("fetch" in (e.get("detail") or "").lower() for e in notes), (
        "a notify breadcrumb disclosing the fetch failure must be journaled, got %r" % events)
