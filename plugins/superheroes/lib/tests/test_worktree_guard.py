"""Unit tests for lib/worktree_guard.py — PreToolUse worktree discard guard (#682).

Uses real git repositories in tmp_path; does not mock subprocess or git.
"""
import os
import subprocess

import pytest

import owner_authority
import worktree_guard as wg


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", cwd, *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path):
    path = str(path)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True,
                   capture_output=True, text=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    return path


def _commit_file(repo, name, content, msg="init"):
    p = os.path.join(repo, name)
    with open(p, "w") as f:
        f.write(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)
    return p


def _calibrated(monkeypatch):
    monkeypatch.setattr(owner_authority, "calibration_state", lambda cwd: "calibrated")


# --- 1. Red-then-green: the checkout-revert wipe (#682) -----------------------

def test_issue_682_checkout_revert_wipe_denies_on_dirty_tree(tmp_path, monkeypatch):
    """The recorded wipe: uncommitted delivery at a path must not be destroyed."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "committed\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("PRIOR_UNCOMMITTED_DELIVERY")
    _calibrated(monkeypatch)
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"
    assert "checkout-revert wipe" in reason


def test_issue_682_checkout_revert_wipe_allows_on_clean_tree(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "committed\n")
    _calibrated(monkeypatch)
    assert wg.classify("git checkout -- f.txt", repo) == ("allow", "")


# --- 2. destructive_discard_action: matches -----------------------------------

@pytest.mark.parametrize("command,action", [
    ("git checkout -- f.txt", "checkout-path"),
    ("git checkout HEAD f.txt", "checkout-path"),
    ("git checkout --pathspec-from-file=paths.txt", "checkout-path"),
    ("git checkout -f main", "checkout-force"),
    ("git checkout --force file", "checkout-force"),
    ("git switch -f main", "switch-force"),
    ("git switch --discard-changes", "switch-force"),
    ("git restore f.txt", "restore"),
    ("git restore -SW f.txt", "restore"),
    ("git restore --staged --worktree f.txt", "restore"),
    ("git restore -- --staged", "restore"),
    ("git reset --hard", "reset-hard"),
    ("git clean -fd", "clean"),
    ("git clean", "clean"),
    ("git clean -i", "clean"),
    ("git checkout-index -f", "checkout-index-force"),
    ("git rm -f tracked.txt", "rm-force"),
    ("git worktree remove -f ../wt", "worktree-remove-force"),
])
def test_destructive_discard_action_recognises_each_shape(command, action):
    assert wg.destructive_discard_action(command) == action


@pytest.mark.parametrize("command", [
    "git checkout main",
    "git checkout -b feat",
    "git checkout -B feat",
    "git switch main",
    "git switch -c feat",
    "git stash",
    "git stash -u",
    "git reset",
    "git reset --soft",
    "git reset --mixed HEAD~1",
    "git clean -n",
    "git clean -nd",
    "git clean -n -f",
    "git rm --cached f",
    "git restore -S f",
    "git restore --staged f",
    "git worktree remove wt",
    'echo "git reset --hard"',
    "grep -r 'git checkout --' docs/",
    "git commit -m 'document the git checkout -- file hazard'",
])
def test_destructive_discard_action_none_for_safe(command):
    assert wg.destructive_discard_action(command) is None


def test_destructive_discard_action_none_for_non_string():
    assert wg.destructive_discard_action(None) is None
    assert wg.destructive_discard_action(42) is None


# --- 3. Refusal messages verbatim ----------------------------------------------

def test_refusal_message_verbatim():
    expected = (
        "superheroes worktree guard: this `git checkout-path` would discard 3 "
        "uncommitted change(s) in this worktree, and git keeps no copy of them. "
        "This is the checkout-revert wipe (issue #682): the command that reverts a "
        "probe edit also erases a prior order's uncommitted delivery at the same "
        "path. Recover the intent instead — commit the work first, `git stash -u` "
        "it (add `-a` to include ignored files; in a conflicted tree `git add` the "
        "unmerged paths first), or revert a probe edit with an inverse Edit rather "
        "than a git discard."
    )
    assert wg.refusal_message("checkout-path", 3) == expected


def test_indeterminate_message_verbatim():
    expected = (
        "superheroes worktree guard: could not determine whether this "
        "`git restore` would destroy uncommitted work — it may target another "
        "worktree, or the repository could not be inspected — so it is refused "
        "(fail-closed). Commit or `git stash -u` your work first, or revert a probe "
        "edit with an inverse Edit rather than a git discard."
    )
    assert wg.indeterminate_message("restore") == expected


# --- 4. classify: no filesystem access for non-matching command ---------------

def test_classify_non_matching_skips_filesystem(monkeypatch):
    def _boom(cwd):
        raise AssertionError("filesystem probe must not run for non-matching command")

    monkeypatch.setattr(owner_authority, "calibration_state", _boom)
    assert wg.classify("echo hello", "/this/path/does/not/exist") == ("allow", "")


# --- 5. Fail-closed edges 1–25 ------------------------------------------------

def test_edge_01_command_none_or_non_string_allows():
    assert wg.classify(None, "/any") == ("allow", "")
    assert wg.classify(123, "/any") == ("allow", "")


def test_edge_02_cwd_none_or_invalid_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    decision, reason = wg.classify("git checkout -- f.txt", None)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("checkout-path")
    decision, reason = wg.classify("git checkout -- f.txt", 42)
    assert decision == "deny"
    decision, reason = wg.classify("git checkout -- f.txt", "/nonexistent/path/xyz")
    assert decision == "deny"


def test_edge_03_not_a_repo_allows(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    bare = str(tmp_path / "not-a-repo")
    os.makedirs(bare)
    assert wg.classify("git checkout -- f.txt", bare) == ("allow", "")


def test_edge_04_git_status_nonzero_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    os.chmod(os.path.join(repo, ".git"), 0)
    try:
        decision, reason = wg.classify("git checkout -- f.txt", repo)
        assert decision == "deny"
        assert reason == wg.indeterminate_message("checkout-path")
    finally:
        os.chmod(os.path.join(repo, ".git"), 0o755)


def test_edge_05_git_binary_absent_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    monkeypatch.setattr(wg.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(
        FileNotFoundError("git")))
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"


def test_edge_06_git_status_timeout_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")

    def _timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(wg.subprocess, "run", _timeout)
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"


def test_edge_07_dangling_git_symlink_denies_not_absent(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    os.symlink(os.path.join(repo, "missing-target"), os.path.join(repo, ".git"))
    decision, reason = wg.classify("git restore f.txt", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("restore")


def test_edge_08_git_file_linked_worktree_treated_as_present(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    main = _init_repo(tmp_path / "main")
    _commit_file(main, "f.txt", "x\n")
    linked = str(tmp_path / "linked")
    _git(main, "worktree", "add", "-b", "linked-branch", linked)
    with open(os.path.join(linked, "f.txt"), "w") as f:
        f.write("dirty")
    decision, reason = wg.classify("git checkout -- f.txt", linked)
    assert decision == "deny"


def test_edge_09_clean_tree_allows(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "clean\n")
    assert wg.classify("git checkout -- f.txt", repo) == ("allow", "")


def test_edge_10_untracked_only_tracked_actions_allow(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    with open(os.path.join(repo, "untracked.txt"), "w") as f:
        f.write("new")
    assert wg.classify("git restore tracked.txt", repo) == ("allow", "")
    assert wg.classify("git checkout -- tracked.txt", repo) == ("allow", "")


def test_edge_11_untracked_only_force_actions_deny(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    with open(os.path.join(repo, "untracked.txt"), "w") as f:
        f.write("new")
    decision, _ = wg.classify("git checkout -f main", repo)
    assert decision == "deny"
    decision, _ = wg.classify("git switch -f main", repo)
    assert decision == "deny"
    decision, _ = wg.classify("git reset --hard", repo)
    assert decision == "deny"


def test_edge_12_untracked_only_clean_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    with open(os.path.join(repo, "untracked.txt"), "w") as f:
        f.write("new")
    decision, _ = wg.classify("git clean -fd", repo)
    assert decision == "deny"


def test_edge_13_clean_dry_run_empty_allows(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "clean\n")
    assert wg.classify("git clean -fdx", repo) == ("allow", "")


def test_edge_14_calibration_state_raises_denies(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")

    def _boom(cwd):
        raise RuntimeError("probe failed")

    monkeypatch.setattr(owner_authority, "calibration_state", _boom)
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"


def test_edge_15_uncalibrated_allows(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    monkeypatch.setattr(owner_authority, "calibration_state", lambda cwd: "uncalibrated")
    assert wg.classify("git checkout -- f.txt", repo) == ("allow", "")


def test_edge_16_git_dash_c_elsewhere_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    decision, reason = wg.classify("git -C ../elsewhere checkout -- f", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("checkout-path")


def test_edge_17_cd_elsewhere_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    decision, reason = wg.classify("cd ../elsewhere && git reset --hard", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("reset-hard")


def test_edge_18_git_work_tree_env_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    decision, reason = wg.classify("GIT_WORK_TREE=../t git restore f", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("restore")


def test_edge_19_restore_staged_only_allows(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    assert wg.classify("git restore -S f", repo) == ("allow", "")
    assert wg.classify("git restore --staged f", repo) == ("allow", "")


def test_edge_20_restore_staged_and_worktree_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    decision, _ = wg.classify("git restore -SW f", repo)
    assert decision == "deny"
    decision, _ = wg.classify("git restore --staged --worktree f", repo)
    assert decision == "deny"


def test_edge_21_restore_dash_dash_staged_pathspec_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    decision, _ = wg.classify("git restore -- --staged", repo)
    assert decision == "deny"


def test_edge_22_checkout_head_file_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "file", "x\n")
    with open(os.path.join(repo, "file"), "w") as f:
        f.write("dirty")
    decision, _ = wg.classify("git checkout HEAD file", repo)
    assert decision == "deny"


def test_edge_23_checkout_main_branch_allows(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    assert wg.classify("git checkout main", repo) == ("allow", "")


def test_edge_24_quoted_inner_git_allows(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    cmd = "git commit -m 'git checkout -- f'"
    assert wg.classify(cmd, repo) == ("allow", "")


def test_edge_25_compound_commit_then_checkout_denies(tmp_path, monkeypatch):
    """Probe runs before commit; tree still dirty when checkout segment is classified."""
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    decision, _ = wg.classify("git commit -m x && git checkout -- f", repo)
    assert decision == "deny"


# --- target_is_resolvable unit checks ------------------------------------------

def test_target_is_resolvable_false_for_dash_c():
    assert wg.target_is_resolvable("git -C /other checkout -- f") is False


def test_target_is_resolvable_false_for_git_dir():
    assert wg.target_is_resolvable("git --git-dir=/other/.git checkout -- f") is False


def test_target_is_resolvable_false_for_cd():
    assert wg.target_is_resolvable("cd /other && git reset --hard") is False


def test_target_is_resolvable_true_for_plain_git():
    assert wg.target_is_resolvable("git checkout -- f") is True


# --- at_risk direct probes -----------------------------------------------------

def test_at_risk_indeterminate_for_bad_cwd():
    assert wg.at_risk(None, "restore", "git restore f") == ("indeterminate", 0)
    assert wg.at_risk("", "restore", "git restore f") == ("indeterminate", 0)
    assert wg.at_risk("/no/such/dir", "restore", "git restore f") == ("indeterminate", 0)


def test_at_risk_worktree_remove_force_always_indeterminate(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    assert wg.at_risk(repo, "worktree-remove-force", "git worktree remove -f wt") == (
        "indeterminate", 0,
    )


# --- clean probe: --exclude fail-open regression (#682) -----------------------

def test_at_risk_clean_exclude_fail_open_regression(tmp_path):
    """--exclude=foo is not -X; before the fix this wrongly returned ('clean', 0)."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "committed\n")
    with open(os.path.join(repo, "newwork.txt"), "w") as f:
        f.write("new")
    assert wg.at_risk(repo, "clean", "git clean -fd --exclude=foo") == ("at-risk", 1)


def test_at_risk_clean_fdx_with_untracked(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "committed\n")
    with open(os.path.join(repo, "newwork.txt"), "w") as f:
        f.write("new")
    assert wg.at_risk(repo, "clean", "git clean -fdx") == ("at-risk", 1)


def test_at_risk_clean_fdX_with_ignored_only(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, ".gitignore", "*.tmp\n", msg="ignore")
    with open(os.path.join(repo, "file.tmp"), "w") as f:
        f.write("ignored untracked")
    assert wg.at_risk(repo, "clean", "git clean -fdX") == ("at-risk", 1)


def test_at_risk_clean_fdx_nothing_to_remove(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "clean\n")
    assert wg.at_risk(repo, "clean", "git clean -fdx") == ("clean", 0)


def test_at_risk_clean_exclude_does_not_add_X_probe(tmp_path):
    """--exclude must not make the probe carry -X (assert via behavior, not argv)."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, ".gitignore", "*.tmp\n", msg="ignore")
    with open(os.path.join(repo, "file.tmp"), "w") as f:
        f.write("ignored untracked")
    # Only ignored untracked present; real git clean -fd --exclude=foo removes nothing.
    # If the probe wrongly added -X, dry-run would list file.tmp → at-risk.
    assert wg.at_risk(repo, "clean", "git clean -fd --exclude=foo") == ("clean", 0)
