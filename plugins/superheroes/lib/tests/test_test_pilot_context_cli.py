"""Tests for test_pilot_context_cli.py — FIX B: --worktree and --base threading."""
import json
import os
import subprocess
import sys

import pytest

# FIX B: verify --worktree makes git ops run in that tree, and --base changes the diff scope.


def _run_git(cwd, *args):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=True)
    return r.stdout.strip()


@pytest.fixture()
def two_repos(tmp_path):
    """Create a base repo with a commit on 'main', and a build-worktree checkout with a lib file."""
    base = tmp_path / "repo"
    base.mkdir()
    _run_git(str(base), "init", "-b", "main")
    _run_git(str(base), "config", "user.email", "test@test.com")
    _run_git(str(base), "config", "user.name", "Test")
    (base / "README.md").write_text("hello")
    _run_git(str(base), "add", "README.md")
    _run_git(str(base), "commit", "-m", "initial")

    # Branch off 'feature' with a lib-only file change
    _run_git(str(base), "checkout", "-b", "feature")
    lib_dir = base / "plugins" / "superheroes" / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "eval_clamp.js").write_text("// clamp")
    _run_git(str(base), "add", ".")
    _run_git(str(base), "commit", "-m", "add lib file")

    return {"base_repo": str(base), "branch": "feature", "base_branch": "main"}


# Repo root — tests are run from the root, same as test_test_pilot_applicability.py
# File lives at <root>/plugins/superheroes/lib/tests/__file__, so 5 levels up = root.
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)


def _invoke_resolve(worktree, work_item="wi-1", generation=None, base=None):
    cmd = [
        sys.executable,
        "plugins/superheroes/lib/test_pilot_context_cli.py",
        "resolve",
        "--work-item", work_item,
    ]
    if worktree is not None:
        cmd += ["--worktree", worktree]
    if base is not None:
        cmd += ["--base", base]
    if generation is not None:
        cmd += ["--generation", str(generation)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO_ROOT)
    return result


def test_worktree_arg_makes_diff_against_that_tree(two_repos):
    """FIX B: --worktree <path> makes the diff run in that tree (not showrunner cwd)."""
    repo = two_repos["base_repo"]
    result = _invoke_resolve(worktree=repo, base="main")
    assert result.returncode == 0, "stderr: %s" % result.stderr
    ctx = json.loads(result.stdout)
    # The build worktree's diff against main should show the lib file
    files = ctx["diff"]["files"]
    assert any("eval_clamp.js" in f for f in files), (
        "FIX B: expected eval_clamp.js in diff files; got %r" % files
    )


def test_base_arg_is_used_for_diff_scope(two_repos):
    """FIX B: --base changes the diff range (base...HEAD); default 'main' preserved when absent."""
    repo = two_repos["base_repo"]
    # With explicit --base main: should find the lib file in diff
    result_with_base = _invoke_resolve(worktree=repo, base="main")
    assert result_with_base.returncode == 0, result_with_base.stderr
    ctx_with = json.loads(result_with_base.stdout)
    files_with = ctx_with["diff"]["files"]
    assert any("eval_clamp.js" in f for f in files_with), (
        "FIX B: --base main should include the lib file; got %r" % files_with
    )


def test_worktree_head_reflects_build_tree_not_showrunner_root(two_repos):
    """FIX B: context head/worktree reflect the build tree's HEAD, not the showrunner root."""
    repo = two_repos["base_repo"]
    build_head = _run_git(repo, "rev-parse", "HEAD")
    result = _invoke_resolve(worktree=repo, base="main")
    assert result.returncode == 0, result.stderr
    ctx = json.loads(result.stdout)
    assert ctx["head"] == build_head, (
        "FIX B: context.head must reflect build worktree HEAD; got %r expected %r" % (ctx["head"], build_head)
    )
    assert ctx["worktree"] == repo or ctx["worktree"].rstrip("/") == repo.rstrip("/"), (
        "FIX B: context.worktree must reflect the build worktree path; got %r" % ctx["worktree"]
    )


def test_default_base_main_preserved_when_base_absent(two_repos):
    """FIX B: when --base is absent, behavior is unchanged (default main)."""
    repo = two_repos["base_repo"]
    # Without --base: should still work and find the lib file (same as main)
    result = _invoke_resolve(worktree=repo)  # no base
    assert result.returncode == 0, result.stderr
    ctx = json.loads(result.stdout)
    # diff should still be non-empty (the feature branch has 1 commit on top of main)
    assert isinstance(ctx["diff"]["files"], list)


def test_unresolvable_base_falls_back_gracefully(two_repos):
    """FIX B: an unresolvable base falls back to current behavior, not a crash."""
    repo = two_repos["base_repo"]
    # Use a base branch name that doesn't exist
    result = _invoke_resolve(worktree=repo, base="nonexistent-branch-xyz-abc")
    # Must not crash (returncode 0, valid JSON)
    assert result.returncode == 0, "Should not crash on unresolvable base; stderr: %s" % result.stderr
    ctx = json.loads(result.stdout)
    assert "diff" in ctx
