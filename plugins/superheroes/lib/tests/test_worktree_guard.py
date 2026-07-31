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
    ("git clean -f -e -n", "clean"),
    ("git clean -f --exclude -n", "clean"),
    ("git -P checkout -- tracked.txt", "checkout-path"),
    ("git --noglob-pathspecs reset --hard", "reset-hard"),
])
def test_destructive_discard_action_recognises_each_shape(command, action):
    assert wg.destructive_discard_action(command) == action


@pytest.mark.parametrize("command", [
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


def test_single_operand_branch_switch_not_destructive_with_cwd(tmp_path):
    """An ordinary branch switch is not a discard — proven against a real repo, not no-cwd."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _git(repo, "branch", "other")
    assert wg.destructive_discard_actions("git checkout other", repo) == []


def test_no_cwd_single_operand_checkout_fails_closed(monkeypatch):
    """#682 round 3: the module must not contradict its own fail-closed contract."""
    _calibrated(monkeypatch)
    for command in ("git checkout .", "git checkout -- f.txt", "git reset --hard"):
        decision, _ = wg.classify(command, None)
        assert decision == "deny", command


def test_compound_clean_probe_is_scoped_to_its_own_segment(tmp_path, monkeypatch):
    """#682 round 3: a safe later segment's flags must not weaken the probe for an earlier one."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, ".gitignore", "*.log\n", msg="ignore")
    with open(os.path.join(repo, "precious.txt"), "w") as f:
        f.write("UNCOMMITTED WORK")
    _calibrated(monkeypatch)
    assert wg.classify("git clean -fd", repo)[0] == "deny"
    assert wg.classify("git clean -fd && git clean -nX", repo)[0] == "deny"


def test_segment_accounting_mixed_command():
    """segment_accounting classifies each segment independently."""
    records = wg.segment_accounting("env git reset --hard && git clean -n")
    kinds = {record["segment"]: record["kind"] for record in records}
    assert kinds["env git reset --hard"] == "unaccounted"
    assert kinds["git clean -n"] == "safe"


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
    calls = []

    def _missing(*a, **k):
        calls.append(1)
        raise FileNotFoundError("git")

    monkeypatch.setattr(wg.subprocess, "run", _missing)
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("checkout-path")
    assert len(calls) >= 1


def test_edge_06_git_status_timeout_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    calls = []

    def _timeout(*a, **k):
        calls.append(1)
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(wg.subprocess, "run", _timeout)
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("checkout-path")
    assert len(calls) >= 1


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


def test_at_risk_worktree_remove_force_clean_target_allows(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-b", "wt-branch", wt)
    assert wg.at_risk(repo, "worktree-remove-force", f"git worktree remove -f {wt}") == (
        "clean", 0,
    )


def test_at_risk_worktree_remove_force_dirty_target_at_risk(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-b", "wt-branch", wt)
    with open(os.path.join(wt, "f.txt"), "w") as f:
        f.write("dirty")
    assert wg.at_risk(repo, "worktree-remove-force", f"git worktree remove -f {wt}") == (
        "at-risk", 1,
    )


def test_at_risk_worktree_remove_force_unresolvable_path_indeterminate(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    assert wg.at_risk(repo, "worktree-remove-force", "git worktree remove -f") == (
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


# --- unparsed message --------------------------------------------------------

def test_unparsed_message_verbatim():
    expected = (
        "superheroes worktree guard: could not confidently parse this command's git "
        "invocation — it may include a destructive discard subcommand — so it is refused "
        "(fail-closed) rather than risk wiping uncommitted work. Commit or `git stash -u` "
        "your work first, or revert a probe edit with an inverse Edit rather than a git "
        "discard."
    )
    assert wg.unparsed_message() == expected


# --- unexpected probe state --------------------------------------------------

def test_classify_unexpected_at_risk_state_denies(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("dirty")
    monkeypatch.setattr(wg, "at_risk", lambda *a, **k: ("bogus-state", 0))
    decision, reason = wg.classify("git checkout -- f.txt", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("checkout-path")


# --- submodule probe ---------------------------------------------------------

def test_at_risk_dirty_submodule_denies(tmp_path, monkeypatch):
    """Both status probe families pass --ignore-submodules=none."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    calls = []

    def _fake_run(cwd, *args):
        calls.append(args)
        if "status" in args:
            if "--ignore-submodules=none" not in args:
                raise AssertionError("status probe must pass --ignore-submodules=none")
            class _Result:
                returncode = 0
                stdout = " M sub\n"
            return _Result()
        raise AssertionError("unexpected git invocation")

    monkeypatch.setattr(wg, "_run_git", _fake_run)
    assert wg.at_risk(repo, "restore", "git restore f.txt") == ("at-risk", 1)
    assert calls


# --- CENSUS: classify chokepoint corpus --------------------------------------
# New parser changes are measured against this table, not by adding matcher unit tests.

def _dirty_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    with open(os.path.join(repo, "tracked.txt"), "w") as f:
        f.write("dirty")
    with open(os.path.join(repo, "untracked.txt"), "w") as f:
        f.write("new")
    _calibrated(monkeypatch)
    return repo


def _clean_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    _calibrated(monkeypatch)
    return repo


def _ignored_only_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, ".gitignore", "*.tmp\n", msg="ignore")
    _commit_file(repo, "tracked.txt", "x\n")
    with open(os.path.join(repo, "build.tmp"), "w") as f:
        f.write("ignored")
    _calibrated(monkeypatch)
    return repo


CENSUS_DENY_DIRTY = [
    # §2 every segment, not first match
    ("git restore tracked.txt && git checkout -f main", "dirty"),
    ("git rm -f tracked.txt && git clean -fd", "dirty"),
    ("git restore tracked.txt && git clean -fd", "dirty"),
    # §3 segment splitting
    ("(cd sub && git reset --hard)", "dirty"),
    ("sleep 1 & git reset --hard", "dirty"),
    ("git checkout \\\n -- README.md", "dirty"),
    # §4 git global options
    ("git -P checkout -- tracked.txt", "dirty"),
    ("git --no-replace-objects checkout -- tracked.txt", "dirty"),
    ("git --noglob-pathspecs reset --hard", "dirty"),
    # §5 option values not read as flags
    ("git clean -f -e -n", "dirty"),
    ("git clean -f --exclude -n", "dirty"),
    # §6 single-operand checkout
    ("git checkout .", "dirty"),
    ("git checkout README.md", "dirty"),
    # §1 unparsed / reserved-word shapes
    ("! git reset --hard", "dirty"),
    ("then git reset --hard", "dirty"),
    ("/usr/bin/git reset --hard", "dirty"),
    ("then git clean -fd", "dirty"),
    # one per destructive action name
    ("git checkout -- f.txt", "dirty"),
    ("git checkout -f main", "dirty"),
    ("git switch -f main", "dirty"),
    ("git restore tracked.txt", "dirty"),
    ("git reset --hard", "dirty"),
    ("git clean -fd", "dirty"),
    ("git checkout-index -f", "dirty"),
    ("git rm -f tracked.txt", "dirty"),
    ("git worktree remove -f ../wt", "dirty"),
    ("git clean -fen", "dirty"),
    ("git clean -fe n", "dirty"),
    ("env git reset --hard && git clean -n", "dirty"),
    ("command git checkout -- tracked.txt && git reset --soft HEAD", "dirty"),
    ("git reset --hard && env git clean -fd", "dirty"),
    ("env git -c advice.detachedHead=false reset --hard", "dirty"),
    ("env git --git-dir=.git reset --hard", "dirty"),
]

CENSUS_ALLOW = [
    ("git status", "dirty"),
    ("git commit -m 'document the git checkout -- hazard'", "dirty"),
    ("git restore --staged f", "dirty"),
    ("git restore -S f", "dirty"),
    ("git clean -n -d", "dirty"),
    ("git clean -nfe pattern", "dirty"),
    ("git clean -ne '*.pyc'", "dirty"),
    ("git stash -u", "dirty"),
    ("git checkout main", "dirty"),
    ("git checkout -b new", "dirty"),
    ("git checkout -bfeature", "dirty"),
    ("gitk --all", "dirty"),
    ("git-foo status", "dirty"),
    ("mygit reset --hard", "dirty"),
    # clean tree destructive forms
    ("git checkout -- f.txt", "clean"),
    ("git checkout -- tracked.txt", "clean"),
    ("git checkout -f main", "clean"),
    ("git switch -f main", "clean"),
    ("git restore tracked.txt", "clean"),
    ("git reset --hard", "clean"),
    ("git clean -fd", "clean"),
    ("git checkout-index -f", "clean"),
    ("git rm -f tracked.txt", "clean"),
    # uncalibrated destructive forms
    ("git checkout -- f.txt", "uncalibrated"),
    ("git reset --hard", "uncalibrated"),
    ("git clean -fd", "uncalibrated"),
]


@pytest.mark.parametrize("command,tree_state", CENSUS_DENY_DIRTY)
def test_census_deny_on_dirty_tree(command, tree_state, tmp_path, monkeypatch):
    assert tree_state == "dirty"
    repo = _dirty_repo(tmp_path, monkeypatch)
    if "README.md" in command:
        _commit_file(repo, "README.md", "committed\n")
        with open(os.path.join(repo, "README.md"), "w") as f:
            f.write("dirty readme")
    decision, _ = wg.classify(command, repo)
    assert decision == "deny"


@pytest.mark.parametrize("command,tree_state", CENSUS_ALLOW)
def test_census_allow_cases(command, tree_state, tmp_path, monkeypatch):
    if tree_state == "dirty":
        repo = _dirty_repo(tmp_path, monkeypatch)
    elif tree_state == "clean":
        repo = _clean_repo(tmp_path, monkeypatch)
    else:
        repo = _init_repo(tmp_path / "repo")
        _commit_file(repo, "tracked.txt", "x\n")
        with open(os.path.join(repo, "tracked.txt"), "w") as f:
            f.write("dirty")
        monkeypatch.setattr(owner_authority, "calibration_state",
                            lambda cwd: "uncalibrated")
    decision, reason = wg.classify(command, repo)
    assert decision == "allow", (command, tree_state, reason)


def test_census_ignored_only_checkout_force_denies(tmp_path, monkeypatch):
    """§7: checkout-force includes ignored entries in the risk probe."""
    repo = _ignored_only_repo(tmp_path, monkeypatch)
    decision, _ = wg.classify("git checkout -f main", repo)
    assert decision == "deny"


def test_census_ignored_only_reset_hard_allows(tmp_path, monkeypatch):
    """§7: reset-hard does not include ignored entries."""
    repo = _ignored_only_repo(tmp_path, monkeypatch)
    assert wg.classify("git reset --hard", repo) == ("allow", "")


def test_census_unparsed_deny_message(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _dirty_repo(tmp_path, monkeypatch)
    decision, reason = wg.classify("env git reset --hard", repo)
    assert decision == "deny"
    assert reason == wg.unparsed_message()


def test_census_deny_treeish_checkout_overwrites_untracked(tmp_path, monkeypatch):
    """Tree-ish path checkout replaces UNTRACKED work at the same path.

    draft.txt is committed only on `other`; on `main` it is untracked, so the tracked-only probe
    cannot see it and only the tree-ish arm can. Without the tree-ish fix this test allows.
    """
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "seed.txt", "seed\n")
    _git(repo, "checkout", "-q", "-b", "other")
    _commit_file(repo, "draft.txt", "version from the other branch\n", msg="other draft")
    _git(repo, "checkout", "-q", "main")
    with open(os.path.join(repo, "draft.txt"), "w") as f:
        f.write("PRECIOUS UNCOMMITTED UNTRACKED WORK")
    _calibrated(monkeypatch)
    decision, _ = wg.classify("git checkout other -- draft.txt", repo)
    assert decision == "deny"


def test_census_deny_assume_unchanged_invisible_to_probe(tmp_path, monkeypatch):
    """assume-unchanged edits are invisible to status; presence of the bit is indeterminate."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    _git(repo, "update-index", "--assume-unchanged", "tracked.txt")
    with open(os.path.join(repo, "tracked.txt"), "w") as f:
        f.write("edited after assume-unchanged")
    _calibrated(monkeypatch)
    decision, reason = wg.classify("git checkout -- tracked.txt", repo)
    assert decision == "deny"
    assert reason == wg.indeterminate_message("checkout-path")


def test_at_risk_worktree_remove_force_ignored_only_target_is_clean(tmp_path):
    """#682 round 3: a worktree that has merely run pytest must stay force-removable."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, ".gitignore", "__pycache__/\n", msg="ignore")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-b", "wt-branch", wt)
    os.makedirs(os.path.join(wt, "__pycache__"), exist_ok=True)
    with open(os.path.join(wt, "__pycache__", "x.pyc"), "w") as f:
        f.write("bytecode")
    assert wg.at_risk(repo, "worktree-remove-force", f"git worktree remove -f {wt}") == ("clean", 0)


def test_at_risk_worktree_remove_force_untracked_only_target_at_risk(tmp_path):
    """The ignored-file arm must not become a tracked-only probe: untracked work still denies."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-b", "wt-branch", wt)
    with open(os.path.join(wt, "draft.txt"), "w") as f:
        f.write("UNTRACKED WORK IN THE WORKTREE")
    assert wg.at_risk(repo, "worktree-remove-force", f"git worktree remove -f {wt}") == (
        "at-risk", 1,
    )


def test_destructive_discard_actions_all_segments(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "tracked.txt", "x\n")
    actions = wg.destructive_discard_actions(
        "git restore tracked.txt && git clean -fd", repo,
    )
    assert "restore" in actions
    assert "clean" in actions
