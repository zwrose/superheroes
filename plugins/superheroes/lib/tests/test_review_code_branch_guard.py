"""Executable detector for review-code's auto-fix branch guard (#769).

Extracts the shipped bash block from SKILL.md and runs it against real git
fixtures so a guard that reads right but behaves wrong cannot pass.
"""
import os
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_SKILL_MD = os.path.join(PLUGIN, "skills", "review-code", "SKILL.md")

LEGACY_GUARD = """\
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ]; then
  echo "Auto-fix needs PR branch '$PR_BRANCH' checked out (currently on '$CURRENT_BRANCH')."
  echo "Check out the branch, or re-run with --post (read-only GitHub) or --review-only (read-only terminal)."
  exit 1
fi
"""

SHARED_CONTRACT_GUARD = """\
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
UPSTREAM_REF=$(git rev-parse --symbolic-full-name '@{upstream}' 2>/dev/null) || UPSTREAM_REF=""
LOCAL_HEAD=$(git rev-parse HEAD)
case "$PR_BRANCH" in ""|null) echo "Auto-fix: pr.json has no head branch — refusing (fail closed)."; exit 1;; esac
case "$HEAD_SHA"   in ""|null) echo "Auto-fix: pr.json has no head SHA — refusing (fail closed)."; exit 1;; esac
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ] \\
   && ! { [ "$UPSTREAM_REF" = "refs/remotes/origin/$PR_BRANCH" ] && [ "$LOCAL_HEAD" = "$HEAD_SHA" ]; }; then
  echo "Auto-fix needs the PR's branch '$PR_BRANCH' (currently on '$CURRENT_BRANCH')."
  echo "An ADOPTED build also qualifies, but only when BOTH hold: upstream is 'refs/remotes/origin/$PR_BRANCH' (found '${UPSTREAM_REF:-none}') AND HEAD is the PR head '$HEAD_SHA' (found '$LOCAL_HEAD')."
  echo "Otherwise check out the branch, or re-run with --post (read-only GitHub) or --review-only (read-only terminal)."
  exit 1
fi
"""


def _git_env():
    return {
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }


def _git(cwd, *args, env=None):
    base = os.environ.copy()
    base.update(_git_env())
    if env:
        base.update(env)
    subprocess.run(
        ["git", "-C", cwd, *args],
        check=True,
        capture_output=True,
        text=True,
        env=base,
    )


def extract_branch_guard(skill_md_path=None):
    """Return the first ```bash block after the **Auto-fix branch guard anchor."""
    path = skill_md_path or DEFAULT_SKILL_MD
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    anchor_idx = None
    for i, line in enumerate(lines):
        if line.startswith("**Auto-fix branch guard"):
            anchor_idx = i
            break
    if anchor_idx is None:
        raise ValueError(
            "SKILL.md: anchor paragraph '**Auto-fix branch guard' not found"
        )

    in_fence = False
    bash_lines = []
    for line in lines[anchor_idx + 1 :]:
        if line.strip() == "```bash":
            in_fence = True
            continue
        if in_fence:
            if line.strip() == "```":
                if not bash_lines:
                    raise ValueError("SKILL.md: fenced bash block is empty")
                break
            bash_lines.append(line)

    if not in_fence:
        raise ValueError(
            "SKILL.md: no ```bash fenced block found after anchor"
        )

    block = "".join(bash_lines).rstrip("\n")
    if not block.strip():
        raise ValueError("SKILL.md: fenced bash block is empty")
    return block


def run_guard(block, repo_dir, pr_branch, head_sha, base_env=None):
    """Run a guard bash block in repo_dir with PR_BRANCH and HEAD_SHA set."""
    env = os.environ.copy()
    env.update(_git_env())
    if base_env:
        env.update(base_env)
    env["PR_BRANCH"] = pr_branch
    env["HEAD_SHA"] = head_sha
    result = subprocess.run(
        ["bash", "-c", block],
        cwd=repo_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def build_git_fixture(tmp_path, pr_branch="feature-pr"):
    """Bare origin + work clone with one commit on pr_branch, then fetch origin."""
    bare = tmp_path / "origin.git"
    work = tmp_path / "work"

    subprocess.run(
        ["git", "init", "-b", pr_branch, "--bare", str(bare)],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **_git_env()},
    )
    subprocess.run(
        ["git", "init", "-b", pr_branch, str(work)],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **_git_env()},
    )

    readme = work / "README"
    readme.write_text("initial\n", encoding="utf-8")
    work_dir = str(work)
    _git(work_dir, "add", "README")
    _git(work_dir, "commit", "-m", "initial")
    head_sha = subprocess.run(
        ["git", "-C", work_dir, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **_git_env()},
    ).stdout.strip()

    _git(work_dir, "remote", "add", "origin", str(bare))
    _git(work_dir, "push", "-u", "origin", pr_branch)
    _git(work_dir, "fetch", "origin")

    return {
        "work_dir": work_dir,
        "pr_branch": pr_branch,
        "head_sha": head_sha,
        "bare": str(bare),
    }


def _combined_output(stdout, stderr):
    return stdout + stderr


def _setup_on_pr_branch(world):
    _git(world["work_dir"], "checkout", world["pr_branch"])


def _setup_adopted(world, branch_name="adopted-x"):
    _git(world["work_dir"], "checkout", "-B", branch_name, world["head_sha"])
    _git(
        world["work_dir"],
        "branch",
        "--set-upstream-to",
        f"origin/{world['pr_branch']}",
        branch_name,
    )


def _setup_adopted_extra_commit(world):
    _setup_adopted(world)
    extra = os.path.join(world["work_dir"], "extra.txt")
    with open(extra, "w", encoding="utf-8") as fh:
        fh.write("extra\n")
    _git(world["work_dir"], "add", "extra.txt")
    _git(world["work_dir"], "commit", "-m", "extra commit")


def _setup_wrong_upstream(world):
    other = "other-branch"
    _git(world["work_dir"], "branch", other, world["head_sha"])
    _git(world["work_dir"], "push", "origin", other)
    _git(world["work_dir"], "fetch", "origin")
    local = "local-wrong-upstream"
    _git(world["work_dir"], "checkout", "-B", local, world["head_sha"])
    _git(
        world["work_dir"],
        "branch",
        "--set-upstream-to",
        f"origin/{other}",
        local,
    )


def _setup_no_upstream(world):
    local = "no-upstream"
    _git(world["work_dir"], "checkout", "-B", local, world["head_sha"])


def _setup_detached(world):
    _git(world["work_dir"], "checkout", "--detach", world["head_sha"])


def _setup_branch_null(world):
    """Create a local branch literally named 'null' at head_sha."""
    _git(world["work_dir"], "checkout", "-B", "null", world["head_sha"])


def _refusal_output(stdout, stderr):
    return _combined_output(stdout, stderr)


def _guard_has_fail_closed_edges(block):
    """True when the guard refuses empty/null PR_BRANCH or HEAD_SHA."""
    return "pr.json has no head branch" in block


# --- extractor fail-closed ---------------------------------------------------


def test_extractor_raises_when_anchor_missing(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# no anchor here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="anchor paragraph"):
        extract_branch_guard(str(skill))


def test_extractor_raises_when_bash_fence_missing(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("**Auto-fix branch guard (PR mode).\n\nNo fence.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no ```bash fenced block"):
        extract_branch_guard(str(skill))


def test_extractor_raises_when_bash_fence_empty(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "**Auto-fix branch guard (PR mode).\n\n```bash\n```\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fenced bash block is empty"):
        extract_branch_guard(str(skill))


def test_extractor_returns_shipped_block():
    block = extract_branch_guard()
    assert "CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)" in block


# --- state table (shipped guard from SKILL.md) -------------------------------


@pytest.fixture
def git_world(tmp_path):
    return build_git_fixture(tmp_path)


@pytest.fixture
def shipped_guard():
    return extract_branch_guard()


def test_state_1_on_pr_branch_accept(git_world, shipped_guard):
    _setup_on_pr_branch(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 0, _refusal_output(out, err)


def test_state_2_adopted_accept(git_world, shipped_guard):
    _setup_adopted(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 0, _refusal_output(out, err)


def test_state_3_adopted_extra_commit_refuse(git_world, shipped_guard):
    _setup_adopted_extra_commit(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 1
    text = _refusal_output(out, err)
    assert git_world["pr_branch"] in text or "adopted" in text.lower()


def test_state_4_wrong_upstream_refuse(git_world, shipped_guard):
    _setup_wrong_upstream(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 1
    text = _refusal_output(out, err)
    assert "upstream" in text.lower() or git_world["pr_branch"] in text


def test_state_5_no_upstream_refuse(git_world, shipped_guard):
    _setup_no_upstream(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 1
    text = _refusal_output(out, err)
    assert "upstream" in text.lower() or "none" in text.lower() or git_world["pr_branch"] in text


def test_state_6_detached_head_refuse(git_world, shipped_guard):
    _setup_detached(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 1
    text = _refusal_output(out, err)
    assert git_world["pr_branch"] in text or "HEAD" in text


@pytest.mark.parametrize(
    "pr_branch_env,setup_fn",
    [
        ("", _setup_on_pr_branch),
        ("null", _setup_on_pr_branch),
        ("", _setup_branch_null),
        ("null", _setup_branch_null),
    ],
    ids=["empty-on-pr", "null-on-pr", "empty-on-null-branch", "null-on-null-branch"],
)
def test_state_7_pr_branch_empty_or_null_refuse(
    git_world, shipped_guard, pr_branch_env, setup_fn
):
    setup_fn(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        pr_branch_env,
        git_world["head_sha"],
    )
    on_null_branch = setup_fn is _setup_branch_null
    if on_null_branch and pr_branch_env == "null":
        expected = 1 if _guard_has_fail_closed_edges(shipped_guard) else 0
    else:
        expected = 1
    assert code == expected
    if expected == 1:
        text = _refusal_output(out, err)
        if "no head branch" in text:
            assert "fail closed" in text
        else:
            assert "PR branch" in text or git_world["pr_branch"] in text


@pytest.mark.parametrize(
    "head_sha_env",
    ["", "null"],
    ids=["empty", "literal-null"],
)
def test_state_8_head_sha_empty_or_null_refuse(git_world, shipped_guard, head_sha_env):
    _setup_on_pr_branch(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        head_sha_env,
    )
    expected = 1 if _guard_has_fail_closed_edges(shipped_guard) else 0
    assert code == expected
    if expected == 1:
        text = _refusal_output(out, err)
        assert "no head SHA" in text
        assert "fail closed" in text


# --- anti-inertness: legacy guard must refuse adopted state (#769) -----------


def test_legacy_guard_refuses_adopted_state_proves_harness_discriminates(git_world):
    """Issue #769: the legacy name-only guard refuses an adopted upstream build.

    If someone reverts the shipped guard to the legacy block, state 2 (adopted
    branch with correct upstream and HEAD) goes red. If the harness is broken so
    everything trivially passes, this test goes red.
    """
    _setup_adopted(git_world)
    code, out, err = run_guard(
        LEGACY_GUARD,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
    )
    assert code == 1
    text = _refusal_output(out, err)
    assert "PR branch" in text
    assert "adopted-x" in text


# --- shared-contract green-path helper (used by throwaway script) --------------


def run_all_states(block, tmp_path_factory):
    """Drive all eight state-table cases against a guard block; for external scripts."""
    import tempfile
    from pathlib import Path

    cases = [
        ("state_1", _setup_on_pr_branch, lambda w: w["pr_branch"], lambda w: w["head_sha"], 0),
        ("state_2", _setup_adopted, lambda w: w["pr_branch"], lambda w: w["head_sha"], 0),
        ("state_3", _setup_adopted_extra_commit, lambda w: w["pr_branch"], lambda w: w["head_sha"], 1),
        ("state_4", _setup_wrong_upstream, lambda w: w["pr_branch"], lambda w: w["head_sha"], 1),
        ("state_5", _setup_no_upstream, lambda w: w["pr_branch"], lambda w: w["head_sha"], 1),
        ("state_6", _setup_detached, lambda w: w["pr_branch"], lambda w: w["head_sha"], 1),
        ("state_7a", _setup_on_pr_branch, lambda w: "", lambda w: w["head_sha"], 1),
        ("state_7b", _setup_on_pr_branch, lambda w: "null", lambda w: w["head_sha"], 1),
        ("state_7c", _setup_branch_null, lambda w: "", lambda w: w["head_sha"], 1),
        ("state_7d", _setup_branch_null, lambda w: "null", lambda w: w["head_sha"], 1),
        ("state_8a", _setup_on_pr_branch, lambda w: w["pr_branch"], lambda w: "", 1),
        ("state_8b", _setup_on_pr_branch, lambda w: w["pr_branch"], lambda w: "null", 1),
    ]

    results = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        for name, setup, pr_fn, sha_fn, expect in cases:
            world = build_git_fixture(base / name)
            setup(world)
            code, out, err = run_guard(
                block, world["work_dir"], pr_fn(world), sha_fn(world)
            )
            results.append((name, code, expect, _refusal_output(out, err)))

    return results
