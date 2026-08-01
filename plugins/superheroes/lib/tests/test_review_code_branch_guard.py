"""Executable detector for review-code's auto-fix branch guard (#769).

Extracts the shipped bash block from SKILL.md and runs it against real git
fixtures so a guard that reads right but behaves wrong cannot pass.
"""
import os
import re
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_SKILL_MD = os.path.join(PLUGIN, "skills", "review-code", "SKILL.md")
AUTO_FIX_LOOP_MD = os.path.join(
    PLUGIN, "skills", "review-code", "reference", "auto-fix-loop.md"
)

_GIT_ENV_STRIP = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_TEMPLATE_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
        "GIT_COMMON_DIR",
        "GIT_CEILING_DIRECTORIES",
    }
)

_GIT_ISOLATION_FLAGS = ("-c", "init.templateDir=", "-c", "core.hooksPath=/dev/null")

LEGACY_GUARD = """\
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ]; then
  echo "Auto-fix needs PR branch '$PR_BRANCH' checked out (currently on '$CURRENT_BRANCH')."
  echo "Check out the branch, or re-run with --post (read-only GitHub) or --review-only (read-only terminal)."
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


def _sanitized_git_env(tmp_path=None):
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_STRIP}
    env.update(_git_env())
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    if tmp_path is not None:
        global_config = tmp_path / "gitconfig.global"
        global_config.write_text("", encoding="utf-8")
        env["GIT_CONFIG_GLOBAL"] = str(global_config)
    else:
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    return env


def _git(cwd, *args, env=None, tmp_path=None):
    base = _sanitized_git_env(tmp_path)
    if env:
        base.update(env)
    subprocess.run(
        ["git", *_GIT_ISOLATION_FLAGS, "-C", cwd, *args],
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


def run_guard(block, repo_dir, pr_branch, head_sha, base_env=None, tmp_path=None):
    """Run a guard bash block in repo_dir with PR_BRANCH and HEAD_SHA set."""
    env = _sanitized_git_env(tmp_path)
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
    git_env = _sanitized_git_env(tmp_path)

    subprocess.run(
        ["git", *_GIT_ISOLATION_FLAGS, "init", "-b", pr_branch, "--bare", str(bare)],
        check=True,
        capture_output=True,
        text=True,
        env=git_env,
    )
    subprocess.run(
        ["git", *_GIT_ISOLATION_FLAGS, "init", "-b", pr_branch, str(work)],
        check=True,
        capture_output=True,
        text=True,
        env=git_env,
    )

    readme = work / "README"
    readme.write_text("initial\n", encoding="utf-8")
    work_dir = str(work)
    _git(work_dir, "add", "README", tmp_path=tmp_path)
    _git(work_dir, "commit", "-m", "initial", tmp_path=tmp_path)
    head_sha = subprocess.run(
        ["git", *_GIT_ISOLATION_FLAGS, "-C", work_dir, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=git_env,
    ).stdout.strip()

    _git(work_dir, "remote", "add", "origin", str(bare), tmp_path=tmp_path)
    _git(work_dir, "push", "-u", "origin", pr_branch, tmp_path=tmp_path)
    _git(work_dir, "fetch", "origin", tmp_path=tmp_path)

    return {
        "work_dir": work_dir,
        "pr_branch": pr_branch,
        "head_sha": head_sha,
        "bare": str(bare),
        "tmp_path": tmp_path,
    }


def _combined_output(stdout, stderr):
    return stdout + stderr


def _setup_on_pr_branch(world):
    _git(world["work_dir"], "checkout", world["pr_branch"], tmp_path=world["tmp_path"])


def _setup_adopted(world, branch_name="adopted-x"):
    _git(
        world["work_dir"],
        "checkout",
        "-B",
        branch_name,
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "branch",
        "--set-upstream-to",
        f"origin/{world['pr_branch']}",
        branch_name,
        tmp_path=world["tmp_path"],
    )


def _setup_adopted_extra_commit(world):
    _setup_adopted(world)
    extra = os.path.join(world["work_dir"], "extra.txt")
    with open(extra, "w", encoding="utf-8") as fh:
        fh.write("extra\n")
    _git(world["work_dir"], "add", "extra.txt", tmp_path=world["tmp_path"])
    _git(world["work_dir"], "commit", "-m", "extra commit", tmp_path=world["tmp_path"])


def _setup_spoofed_upstream(world):
    """Local branch whose @{upstream} renders as origin/<pr_branch> but tracks '.'."""
    branch_name = "spoofed-upstream"
    _git(
        world["work_dir"],
        "checkout",
        "-B",
        branch_name,
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{branch_name}.remote",
        ".",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{branch_name}.merge",
        f"refs/remotes/origin/{world['pr_branch']}",
        tmp_path=world["tmp_path"],
    )


def _setup_wrong_upstream(world):
    other = "other-branch"
    _git(
        world["work_dir"],
        "branch",
        other,
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )
    _git(world["work_dir"], "push", "origin", other, tmp_path=world["tmp_path"])
    _git(world["work_dir"], "fetch", "origin", tmp_path=world["tmp_path"])
    local = "local-wrong-upstream"
    _git(
        world["work_dir"],
        "checkout",
        "-B",
        local,
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "branch",
        "--set-upstream-to",
        f"origin/{other}",
        local,
        tmp_path=world["tmp_path"],
    )


def _setup_no_upstream(world):
    local = "no-upstream"
    _git(
        world["work_dir"],
        "checkout",
        "-B",
        local,
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )


def _setup_detached(world):
    _git(
        world["work_dir"],
        "checkout",
        "--detach",
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )


def _setup_detached_with_head_branch_config(world):
    """Detached at head_sha with branch.HEAD.remote/merge set (Finding 1 regression)."""
    _setup_detached(world)
    _git(
        world["work_dir"],
        "config",
        "branch.HEAD.remote",
        "origin",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        "branch.HEAD.merge",
        f"refs/heads/{world['pr_branch']}",
        tmp_path=world["tmp_path"],
    )


def _setup_detached_with_empty_branch_config(world):
    """Detached at head_sha with branch..remote/merge set (empty subsection)."""
    _setup_detached(world)
    _git(
        world["work_dir"],
        "config",
        "branch..remote",
        "origin",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        "branch..merge",
        f"refs/heads/{world['pr_branch']}",
        tmp_path=world["tmp_path"],
    )


def _setup_branch_null(world):
    """Create a local branch literally named 'null' at head_sha."""
    _git(
        world["work_dir"],
        "checkout",
        "-B",
        "null",
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )


def _setup_head_symbolic_to_tag(world, tag_name="v-pr-head"):
    """HEAD symbolic to a tag with adopted-looking branch.<tag>.* config."""
    full_ref = f"refs/tags/{tag_name}"
    _git(world["work_dir"], "tag", tag_name, world["head_sha"], tmp_path=world["tmp_path"])
    _git(
        world["work_dir"],
        "symbolic-ref",
        "HEAD",
        full_ref,
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{tag_name}.remote",
        "origin",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{tag_name}.merge",
        f"refs/heads/{world['pr_branch']}",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{full_ref}.remote",
        "origin",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{full_ref}.merge",
        f"refs/heads/{world['pr_branch']}",
        tmp_path=world["tmp_path"],
    )


def _setup_head_symbolic_to_remote_tracking(world):
    """HEAD symbolic to origin/<pr_branch> with adopted-looking config."""
    pr_branch = world["pr_branch"]
    remote_branch = f"origin/{pr_branch}"
    full_ref = f"refs/remotes/origin/{pr_branch}"
    _git(
        world["work_dir"],
        "symbolic-ref",
        "HEAD",
        full_ref,
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{remote_branch}.remote",
        "origin",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{remote_branch}.merge",
        f"refs/heads/{pr_branch}",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{full_ref}.remote",
        "origin",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{full_ref}.merge",
        f"refs/heads/{pr_branch}",
        tmp_path=world["tmp_path"],
    )


def _setup_adopted_fork_remote(world, branch_name="adopted-fork"):
    """Adopted-looking branch tracking remote 'fork' instead of 'origin'."""
    _git(
        world["work_dir"],
        "checkout",
        "-B",
        branch_name,
        world["head_sha"],
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "remote",
        "add",
        "fork",
        world["bare"],
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{branch_name}.remote",
        "fork",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        f"branch.{branch_name}.merge",
        f"refs/heads/{world['pr_branch']}",
        tmp_path=world["tmp_path"],
    )


def _setup_pr_branch_name_only_moved_head(world):
    """On PR branch by name, no tracking config, HEAD one commit ahead."""
    pr_branch = world["pr_branch"]
    _git(world["work_dir"], "checkout", pr_branch, tmp_path=world["tmp_path"])
    _git(
        world["work_dir"],
        "config",
        "--unset",
        f"branch.{pr_branch}.remote",
        tmp_path=world["tmp_path"],
    )
    _git(
        world["work_dir"],
        "config",
        "--unset",
        f"branch.{pr_branch}.merge",
        tmp_path=world["tmp_path"],
    )
    extra = os.path.join(world["work_dir"], "name-leg.txt")
    with open(extra, "w", encoding="utf-8") as fh:
        fh.write("name-leg\n")
    _git(world["work_dir"], "add", "name-leg.txt", tmp_path=world["tmp_path"])
    _git(world["work_dir"], "commit", "-m", "name-leg extra", tmp_path=world["tmp_path"])


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
    assert "CURRENT_BRANCH=$(git symbolic-ref --quiet HEAD)" in block
    assert 'case "$CURRENT_BRANCH" in refs/heads/?*)' in block
    assert 'TRACK_REMOTE=$(git config --get "branch.$CURRENT_BRANCH.remote")' in block


_MANDATORY_ACCEPTANCE_PATTERNS = (
    ("name_match", "PR_BRANCH", '"$CURRENT_BRANCH" != "$PR_BRANCH"'),
    ("track_remote", "origin", '[ "$TRACK_REMOTE" = origin ]'),
    ("track_merge", "refs/heads", 'refs/heads/$PR_BRANCH'),
    ("head_at_pr", "HEAD_SHA", '[ "$LOCAL_HEAD" = "$HEAD_SHA" ]'),
)


def _acceptance_leg_tokens_from_guard_home(block):
    """Derive pinned acceptance-leg anchors from the shipped guard bash block."""
    derived = [
        (leg_name, token)
        for leg_name, token, pattern in _MANDATORY_ACCEPTANCE_PATTERNS
        if pattern in block
    ]
    if not derived:
        raise ValueError("guard home: zero acceptance-leg tokens derived")
    missing = [
        (leg_name, pattern)
        for leg_name, _token, pattern in _MANDATORY_ACCEPTANCE_PATTERNS
        if pattern not in block
    ]
    if missing:
        raise ValueError(
            "guard home: missing mandatory acceptance-leg pattern(s) — %r" % missing
        )
    return [(leg_name, token) for leg_name, token, _ in _MANDATORY_ACCEPTANCE_PATTERNS]


def _auto_fix_loop_row_text(doc):
    match = re.search(
        r"^\| Auto-fixing a PR you don't have checked out\s+\|(.+?)\|\s*$",
        doc,
        re.MULTILINE,
    )
    assert match is not None, (
        "auto-fix-loop.md: Common-Mistakes row "
        "'Auto-fixing a PR you don't have checked out' not found"
    )
    return match.group(1)


def _row_carries_acceptance_token(row_text, leg_name, token):
    if token == "origin":
        return "origin" in row_text
    if token == "refs/heads":
        return "refs/heads" in row_text
    if token == "HEAD_SHA":
        return "headRefOid" in row_text and "`HEAD`" in row_text
    if token == "PR_BRANCH":
        return "current branch" in row_text.lower() or "PR's branch" in row_text
    raise AssertionError("unknown acceptance token %r for leg %r" % (token, leg_name))


def test_auto_fix_loop_row_describes_both_acceptance_legs():
    """§11: auto-fix-loop.md row restates each acceptance leg from the shipped guard."""
    home_block = extract_branch_guard()
    home_tokens = _acceptance_leg_tokens_from_guard_home(home_block)
    with open(AUTO_FIX_LOOP_MD, encoding="utf-8") as fh:
        doc = fh.read()
    row_text = _auto_fix_loop_row_text(doc)
    missing = [
        (leg, token)
        for leg, token in home_tokens
        if not _row_carries_acceptance_token(row_text, leg, token)
    ]
    assert not missing, (
        "auto-fix-loop.md row missing acceptance leg(s) from shipped guard — %r"
        % missing
    )


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
        tmp_path=git_world["tmp_path"],
    )
    assert code == 0, _combined_output(out, err)


def test_state_2_adopted_accept(git_world, shipped_guard):
    _setup_adopted(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 0, _combined_output(out, err)


def test_state_2b_pr_branch_name_only_moved_head_accept(git_world, shipped_guard):
    """Name-match leg: on PR branch by name even without tracking config or PR HEAD."""
    _setup_pr_branch_name_only_moved_head(git_world)
    current_head = subprocess.run(
        [
            "git",
            *_GIT_ISOLATION_FLAGS,
            "-C",
            git_world["work_dir"],
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_sanitized_git_env(git_world["tmp_path"]),
    ).stdout.strip()
    assert current_head != git_world["head_sha"]
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 0, _combined_output(out, err)


def test_state_3_adopted_extra_commit_refuse(git_world, shipped_guard):
    _setup_adopted_extra_commit(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text
    current_head = subprocess.run(
        [
            "git",
            *_GIT_ISOLATION_FLAGS,
            "-C",
            git_world["work_dir"],
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_sanitized_git_env(git_world["tmp_path"]),
    ).stdout.strip()
    assert f"(found '{current_head}')" in text
    assert current_head != git_world["head_sha"]


def test_state_4_wrong_upstream_refuse(git_world, shipped_guard):
    _setup_wrong_upstream(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "found 'refs/heads/other-branch'" in text


def test_state_4b_spoofed_upstream_symbolic_refuse(git_world, shipped_guard):
    """Issue #769: rendered @{upstream} is spoofable — guard must refuse the real path.

    A branch with remote '.' and merge refs/remotes/origin/<pr_branch> makes
    git rev-parse --symbolic-full-name '@{upstream}' print refs/remotes/origin/<pr_branch>
    while tracking a local ref — so the guard reads branch.<name>.remote /
    branch.<name>.merge instead.
    """
    _setup_spoofed_upstream(git_world)
    pr_branch = git_world["pr_branch"]
    upstream = subprocess.run(
        [
            "git",
            *_GIT_ISOLATION_FLAGS,
            "-C",
            git_world["work_dir"],
            "rev-parse",
            "--symbolic-full-name",
            "@{upstream}",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_sanitized_git_env(git_world["tmp_path"]),
    ).stdout.strip()
    assert upstream == f"refs/remotes/origin/{pr_branch}"

    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        pr_branch,
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text


def test_state_4c_spoofed_upstream_tracked_remote_isolation_refuse(git_world, shipped_guard):
    """Isolates the TRACK_REMOTE leg: remote '.' with merge corrected to refs/heads/<pr>."""
    _setup_spoofed_upstream(git_world)
    pr_branch = git_world["pr_branch"]
    branch_name = "spoofed-upstream"
    _git(
        git_world["work_dir"],
        "config",
        f"branch.{branch_name}.merge",
        f"refs/heads/{pr_branch}",
        tmp_path=git_world["tmp_path"],
    )

    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        pr_branch,
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "found '.'" in text


def test_state_5_no_upstream_refuse(git_world, shipped_guard):
    _setup_no_upstream(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "found 'none'" in text


def test_state_6_detached_head_refuse(git_world, shipped_guard):
    _setup_detached(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text
    assert "currently on '<detached HEAD>'" in text


def test_state_6b_detached_head_with_branch_head_config_refuse(git_world, shipped_guard):
    """Detached at PR head with branch.HEAD.* set must still refuse (Finding 1)."""
    _setup_detached_with_head_branch_config(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text


def test_state_6c_detached_head_with_empty_subsection_config_refuse(git_world, shipped_guard):
    """Detached at PR head with branch..* set must still refuse (empty subsection)."""
    _setup_detached_with_empty_branch_config(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text


def test_state_6d_head_symbolic_to_tag_with_adopted_config_refuse(git_world, shipped_guard):
    """HEAD symbolic to a tag with adopted-looking branch.<tag>.* must refuse."""
    _setup_head_symbolic_to_tag(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text
    assert "currently on '<detached HEAD>'" in text


def test_state_6e_head_symbolic_to_remote_tracking_with_adopted_config_refuse(
    git_world, shipped_guard
):
    """HEAD symbolic to origin/<pr> with adopted-looking config must refuse."""
    _setup_head_symbolic_to_remote_tracking(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "An ADOPTED build also qualifies" in text
    assert "currently on '<detached HEAD>'" in text


def test_state_4d_adopted_fork_remote_refuse(git_world, shipped_guard):
    """Adopted-looking branch whose tracking remote is 'fork' must refuse."""
    _setup_adopted_fork_remote(git_world)
    code, out, err = run_guard(
        shipped_guard,
        git_world["work_dir"],
        git_world["pr_branch"],
        git_world["head_sha"],
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "found 'fork'" in text


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
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "no head branch" in text or "An ADOPTED build also qualifies" in text


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
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
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
        tmp_path=git_world["tmp_path"],
    )
    assert code == 1
    text = _combined_output(out, err)
    assert "PR branch" in text
    assert "adopted-x" in text
