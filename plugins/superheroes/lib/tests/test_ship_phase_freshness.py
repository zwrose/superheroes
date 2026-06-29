# plugins/superheroes/lib/tests/test_ship_phase_freshness.py
"""Tests for ship_phase.py --step freshness with the configurable --base arg.

The freshness step checks whether origin/<base> is an ancestor of HEAD.
  - When --base is absent: uses hardcoded 'main' (default behavior, unchanged).
  - When --base <branch> is present: uses origin/<branch> instead.
  - Fail-closed: a bad/unresolvable base yields 'gate' (rc 2 from git), not 'up_to_date'.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLI = str(HERE.parent / "ship_phase.py")
LIB = str(HERE.parent)


def _run_freshness(tmp_path, repo_path, extra_args=None, env_extra=None):
    """Run ship_phase.py --step freshness from repo_path, return (returncode, parsed_json)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = LIB
    if env_extra:
        env.update(env_extra)
    cmd = [sys.executable, CLI, "--step", "freshness", "--work-item", "wi"]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, cwd=str(repo_path), env=env, capture_output=True, text=True)
    result = None
    try:
        result = json.loads(proc.stdout)
    except Exception:
        pass
    return proc.returncode, result


def _make_repo_with_origin_branch(tmp_path):
    """Create a local repo with a 'remote' (bare clone) that has a feature branch."""
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    ge = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
          "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    env = dict(os.environ, **ge)
    subprocess.run(["git", "-C", str(clone), "commit", "--allow-empty", "-m", "base"], env=env, check=True)
    subprocess.run(["git", "-C", str(clone), "push", "origin", "HEAD:main", "-u", "-q"], env=env, check=True)
    # Create a feature branch on origin that is AT the same commit (branch is up to date).
    subprocess.run(["git", "-C", str(clone), "push", "origin", "HEAD:live-showrunner-102", "-q"], env=env, check=True)
    # Fetch so the local clone knows about origin/live-showrunner-102.
    subprocess.run(["git", "-C", str(clone), "fetch", "origin", "-q"], env=env, check=True)
    return clone


def test_freshness_default_base_uses_main(tmp_path):
    """Absent --base uses 'main' (default); HEAD contains origin/main -> up_to_date."""
    repo = _make_repo_with_origin_branch(tmp_path)
    rc, result = _run_freshness(tmp_path, repo)
    assert result is not None, "ship_phase must produce JSON"
    assert result["decision"] == "up_to_date", f"default base=main, branch up to date -> up_to_date, got {result}"


def test_freshness_explicit_base_uses_configured_branch(tmp_path):
    """--base live-showrunner-102 -> checks origin/live-showrunner-102; HEAD contains it -> up_to_date."""
    repo = _make_repo_with_origin_branch(tmp_path)
    rc, result = _run_freshness(tmp_path, repo, extra_args=["--base", "live-showrunner-102"])
    assert result is not None, "ship_phase must produce JSON"
    assert result["decision"] == "up_to_date", (
        f"explicit base=live-showrunner-102, HEAD contains it -> up_to_date, got {result}")


def test_freshness_default_behavior_unchanged_no_base_arg(tmp_path):
    """Byte-identical default: no --base arg -> same result as the current code path."""
    repo = _make_repo_with_origin_branch(tmp_path)
    rc_default, result_default = _run_freshness(tmp_path, repo)
    rc_explicit, result_explicit = _run_freshness(tmp_path, repo, extra_args=["--base", "main"])
    # Both should give the same decision.
    assert result_default["decision"] == result_explicit["decision"], (
        "default (no --base) must equal --base main")


# ---------------------------------------------------------------------------
# C-I1: freshness must resolve --base the SAME way build_state_cli's gather does
# (local -> origin/<base>), so a base that exists only LOCALLY (not pushed to
# origin) is honored — not gated as if behind. And an unresolvable base fails
# CLOSED with a specific reason, not an opaque ancestor-read error.
# ---------------------------------------------------------------------------

def _commit(clone, msg):
    ge = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
          "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    env = dict(os.environ, **ge)
    subprocess.run(["git", "-C", str(clone), "commit", "--allow-empty", "-m", msg],
                   env=env, check=True)


def test_freshness_honors_local_only_base(tmp_path):
    """A base branch that exists LOCALLY but is NOT pushed to origin -> resolved via the local
    fallback. HEAD contains that local base -> up_to_date (not falsely gated). This is the bug:
    origin/<base>-only resolution gated a genuinely-up-to-date branch."""
    # Bare origin with only 'main'; clone is up to date with main.
    repo = _make_repo_with_origin_branch(tmp_path)
    # Create a base branch that lives ONLY locally (never pushed), AT the current HEAD.
    subprocess.run(["git", "-C", str(repo), "branch", "local-only-base", "HEAD"], check=True)
    # Sanity: origin/local-only-base does NOT exist (so origin-only resolution would fail/gate).
    rp = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet",
                         "origin/local-only-base"], capture_output=True)
    assert rp.returncode != 0, "precondition: origin/local-only-base must not exist"
    rc, result = _run_freshness(tmp_path, repo, extra_args=["--base", "local-only-base"])
    assert result is not None, "ship_phase must produce JSON"
    assert result["decision"] == "up_to_date", (
        f"local-only base at HEAD -> up_to_date (not gated), got {result}")


def test_freshness_unresolvable_base_gates_with_specific_reason(tmp_path):
    """An unresolvable --base (neither local nor origin) fails CLOSED -> decision 'gate' with a
    SPECIFIC reason naming the base, not an opaque ancestor-read error."""
    repo = _make_repo_with_origin_branch(tmp_path)
    rc, result = _run_freshness(tmp_path, repo, extra_args=["--base", "no-such-base-anywhere"])
    assert result is not None, "ship_phase must produce JSON"
    assert result["decision"] == "gate", f"unresolvable base must gate, got {result}"
    assert "reason" in result, "gate must carry a specific reason"
    assert "no-such-base-anywhere" in result["reason"], "reason must name the specific base"
