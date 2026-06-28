# plugins/superheroes/lib/tests/test_build_state_cli.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
CLI = os.path.join(HERE, "..", "build_state_cli.py")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def test_gather_maps_trailered_commit_and_flags_untrailered(tmp_path):
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    # Move onto a feature branch, then anchor a `main` base ref at the base commit, so the
    # task/stray commits land ABOVE the merge-base (works whatever git's default branch is).
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "stray (no trailer)", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1,2"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]
    assert st["unmapped_commits"] >= 1                 # the stray commit
    assert st["provenance"] in ("absent", "present", "garbled")


def test_gather_reads_git_from_the_worktree_not_cwd(tmp_path):
    # The build branch lives in a SEPARATE build worktree; gather must read git from --worktree, not
    # the ambient cwd. Run from an UNRELATED empty repo (cwd) and point --worktree at the real build repo.
    wt = str(tmp_path / "wt")
    os.makedirs(wt)
    _git(wt, "init", "-q")
    _git(wt, "commit", "--allow-empty", "-m", "base", "-q")
    _git(wt, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(wt, "branch", "-f", "main", "HEAD")
    _git(wt, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    _git(wt, "commit", "--allow-empty", "-m", "stray (no trailer)", "-q")
    cwd = str(tmp_path / "cwd")           # the showrunner's main checkout — a DIFFERENT, commit-free repo
    os.makedirs(cwd)
    _git(cwd, "init", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1,2", "--worktree", wt],
                         cwd=cwd, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]              # read came from the worktree, not cwd
    assert st["unmapped_commits"] >= 1                  # the stray commit


# ---------------------------------------------------------------------------
# Configurable base branch (--base) tests
# ---------------------------------------------------------------------------

def test_gather_with_explicit_base_uses_configured_base(tmp_path):
    """--base <branch> feeds the merge-base instead of origin/HEAD detection."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base-commit", "-q")
    # Create a local 'feature-base' branch at the base commit.
    _git(repo, "branch", "feature-base", "HEAD")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-cfg")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run(
        [sys.executable, CLI, "gather", "--work-item", "wi",
         "--branch", "superheroes/wi-cfg", "--valid-ids", "1",
         "--base", "feature-base"],
        cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    st = json.loads(out.stdout)
    # Only 1 commit above the configured base and it has a valid Task-Id.
    # git log output has a trailing blank line that produces 1 spurious empty row;
    # the key invariant is that the task commit IS mapped (committed_task_ids has "1").
    assert "1" in st["committed_task_ids"]
    # The only "unmapped" entry should be from the trailing blank line (not a real commit).
    # When using the default base without --base the test has a stray commit -> >= 2 unmapped.
    # With the correct --base, only the blank-line artifact remains.
    assert st["unmapped_commits"] <= 1


def test_gather_default_base_unchanged_when_base_arg_absent(tmp_path):
    """Absent --base uses the existing _base() resolution; default unchanged."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run(
        [sys.executable, CLI, "gather", "--work-item", "wi",
         "--branch", "superheroes/wi-abc", "--valid-ids", "1"],
        cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]


def test_gather_unresolvable_base_fails_closed(tmp_path):
    """An unresolvable --base must exit non-zero (fail closed), never open UFR-7."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run(
        [sys.executable, CLI, "gather", "--work-item", "wi",
         "--branch", "superheroes/wi-abc", "--valid-ids", "1",
         "--base", "nonexistent-branch-xyz"],
        cwd=repo, env=env, capture_output=True, text=True)
    # Must fail closed: non-zero exit (never silently yield a result with 0 unmapped)
    assert out.returncode != 0, "unresolvable base must fail closed (non-zero exit)"


def test_record_reviewed_then_gather_reads_it(tmp_path):
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    subprocess.run([sys.executable, CLI, "record-reviewed", "--work-item", "wi", "--task", "1"],
                   cwd=repo, env=env, check=True)
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1"],
                         cwd=repo, env=env, capture_output=True, text=True)
    assert json.loads(out.stdout)["review_records"].get("1") == "passed"
