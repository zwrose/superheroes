"""Merge-in-progress tests for lib/worktree_guard.py (#2054, field case weekly-eats#3186).

During ``git merge main`` the merge stages main's changes and leaves one file conflicted.
``git checkout --theirs <conflicted file>`` was refused because the whole-tree probe counted
the merge's own staged changes as the builder's uncommitted work. The merge branch of
``at_risk`` judges a merge-side checkout/restore on the paths it names only.

Uses real git repositories in tmp_path; does not mock git.
"""
import os
import re
import stat
import subprocess

import pytest

import mode_registry
import worktree_guard as wg


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-C", cwd, *args],
        check=check,
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


def _write(repo, name, content):
    p = os.path.join(repo, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)
    return p


def _commit_file(repo, name, content, msg="init"):
    p = _write(repo, name, content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)
    return p


def _calibrated(monkeypatch):
    monkeypatch.setattr(mode_registry, "calibration_state", lambda cwd: "calibrated")


MAIN_CHANGED = ("a.txt", "b.txt", "c.txt", "d.txt")


def _merge_repo(tmp_path, monkeypatch, conflict_style=None, linked=False):
    """A repo mid-``git merge main``: f.txt conflicts, main also changed several other files.

    Returns the directory to run commands in (the repo, or its linked worktree).
    """
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    if conflict_style:
        _git(repo, "config", "merge.conflictStyle", conflict_style)
    _commit_file(repo, "f.txt", "base\n")
    for name in MAIN_CHANGED:
        _write(repo, name, "base " + name + "\n")
    _write(repo, "sub/x.txt", "base x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit_file(repo, "f.txt", "feature\n", "feature edits f")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "f.txt", "main\n")
    for name in MAIN_CHANGED:
        _write(repo, name, "main " + name + "\n")
    _write(repo, "g.txt", "new on main\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "main edits")
    if linked:
        work = str(tmp_path / "linked")
        _git(repo, "worktree", "add", "-q", work, "feature")
    else:
        work = repo
        _git(repo, "checkout", "-q", "feature")
    merged = _git(work, "merge", "--no-edit", "main", check=False)
    assert merged.returncode == 1, merged.stdout + merged.stderr
    staged = _git(work, "status", "--porcelain", "--untracked-files=no").stdout.splitlines()
    # The fixture must create the #3186 condition: merge-staged changes on unnamed paths.
    assert len([ln for ln in staged if not ln.startswith("UU")]) >= len(MAIN_CHANGED)
    assert any(ln.startswith("UU") and ln.endswith("f.txt") for ln in staged)
    return work


def _merge_head_file(work):
    out = _git(work, "rev-parse", "--git-path", "MERGE_HEAD").stdout.strip()
    return out if os.path.isabs(out) else os.path.join(work, out)


def _normalize(data):
    return re.sub(rb"^(<{7,}|>{7,}|\|{7,})(?: .*)?$", rb"\1", data, flags=re.MULTILINE)


def _refusal(action, count):
    return ("deny", wg.refusal_message(action, count))


def _indeterminate(action):
    return ("deny", wg.indeterminate_message(action))


# --- premise: merge-tree reproduces the conflict file the merge wrote ---------

@pytest.mark.parametrize("style", [None, "zdiff3"])
def test_merge_tree_reproduces_conflicted_file_after_label_normalization(
    tmp_path, monkeypatch, style,
):
    work = _merge_repo(tmp_path, monkeypatch, conflict_style=style)
    result = _git(work, "merge-tree", "--write-tree", "HEAD", "MERGE_HEAD", check=False)
    assert result.returncode == 1
    tree = result.stdout.splitlines()[0]
    assert re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", tree)
    blob = subprocess.run(
        ["git", "-C", work, "cat-file", "blob", f"{tree}:f.txt"],
        check=True, capture_output=True,
    ).stdout
    with open(os.path.join(work, "f.txt"), "rb") as f:
        worktree = f.read()
    assert b"<<<<<<<" in worktree
    assert _normalize(blob) == _normalize(worktree)


# --- the #3186 shape ----------------------------------------------------------

@pytest.mark.parametrize("style", [None, "zdiff3"])
@pytest.mark.parametrize("command", [
    "git checkout --theirs f.txt",
    "git checkout --ours f.txt",
    "git checkout --theirs -- f.txt",
    "git restore --theirs f.txt",
])
def test_3186_merge_side_checkout_of_untouched_conflicted_file_allows(
    tmp_path, monkeypatch, command, style,
):
    work = _merge_repo(tmp_path, monkeypatch, conflict_style=style)
    assert wg.classify(command, work) == ("allow", "")


def test_merge_staged_path_without_builder_edit_allows(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    assert wg.classify("git checkout --theirs a.txt", work) == ("allow", "")


def test_conflicted_file_in_a_subdirectory_cwd_allows_then_denies_after_edit(
    tmp_path, monkeypatch,
):
    work = _merge_repo(tmp_path, monkeypatch)
    sub = os.path.join(work, "sub")
    assert wg.classify("git checkout --theirs ../f.txt", sub) == ("allow", "")
    _write(work, "f.txt", "resolved by the builder\n")
    assert wg.classify("git checkout --theirs ../f.txt", sub) == _refusal("checkout-path", 1)


def test_linked_worktree_merge_allows_3186_shape(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch, linked=True)
    assert os.sep.join(["worktrees", ""]) in _merge_head_file(work)
    assert wg.classify("git checkout --theirs f.txt", work) == ("allow", "")
    _write(work, "f.txt", "resolved by the builder\n")
    assert wg.classify("git checkout --theirs f.txt", work) == _refusal("checkout-path", 1)


# --- edge 4 / edge 5: the builder's own work still refuses --------------------

def test_edge4_partial_resolution_of_conflicted_file_denies(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    with open(os.path.join(work, "f.txt"), "a") as f:
        f.write("builder's partial resolution\n")
    assert wg.classify("git checkout --theirs f.txt", work) == _refusal("checkout-path", 1)
    assert wg.classify("git restore --theirs f.txt", work) == _refusal("restore", 1)


def test_edge5_unstaged_edit_on_merge_staged_path_denies(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    with open(os.path.join(work, "a.txt"), "a") as f:
        f.write("builder's unstaged edit\n")
    assert wg.classify("git checkout --theirs a.txt", work) == _refusal("checkout-path", 1)


def test_executable_bit_edit_on_conflicted_file_denies_with_filemode_off(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    _git(work, "config", "core.filemode", "false")
    target = os.path.join(work, "f.txt")
    os.chmod(target, os.stat(target).st_mode | stat.S_IXUSR)
    assert wg.classify("git checkout --theirs f.txt", work) == _refusal("checkout-path", 1)
    assert wg.classify("git restore --theirs f.txt", work) == _refusal("restore", 1)


@pytest.mark.parametrize("filemode", ["false", "true"])
def test_edge1_2_executable_bit_edit_on_stage_zero_path_denies_whatever_filemode_says(
    tmp_path, monkeypatch, filemode,
):
    work = _merge_repo(tmp_path, monkeypatch)
    _git(work, "config", "core.filemode", filemode)
    target = os.path.join(work, "a.txt")
    os.chmod(target, os.stat(target).st_mode | stat.S_IXUSR)
    assert _git(work, "ls-files", "--stage", "a.txt").stdout.startswith("100644 ")
    assert wg.classify("git checkout --theirs a.txt", work) == _refusal("checkout-path", 1)
    assert wg.classify("git restore --theirs a.txt", work) == _refusal("restore", 1)


@pytest.mark.parametrize("filemode", ["false", "true"])
def test_edge3_stage_zero_path_with_content_and_mode_unchanged_allows(
    tmp_path, monkeypatch, filemode,
):
    work = _merge_repo(tmp_path, monkeypatch)
    _git(work, "config", "core.filemode", filemode)
    assert wg.classify("git checkout --theirs a.txt", work) == ("allow", "")
    assert wg.classify("git restore --theirs a.txt", work) == ("allow", "")


@pytest.mark.parametrize("kind", ["symlink", "gitlink"])
def test_edge4_stage_zero_symlink_or_gitlink_entry_is_indeterminate(tmp_path, monkeypatch, kind):
    work = _merge_repo(tmp_path, monkeypatch)
    if kind == "symlink":
        target = os.path.join(work, "a.txt")
        os.remove(target)
        os.symlink("b.txt", target)
        _git(work, "add", "a.txt")
        name, mode = "a.txt", "120000"
    else:
        nested = _init_repo(os.path.join(work, "sm"))
        _commit_file(nested, "n.txt", "nested\n")
        _git(work, "add", "sm")
        name, mode = "sm", "160000"
    assert _git(work, "ls-files", "--stage", name).stdout.startswith(mode + " ")
    assert _git(work, "diff", "--quiet", "--ignore-submodules=none", "--", name).returncode == 0
    assert wg.classify(f"git checkout --theirs {name}", work) == _indeterminate("checkout-path")
    assert wg.classify(f"git restore --theirs {name}", work) == _indeterminate("restore")


def test_unclosed_opening_marker_like_line_is_ordinary_content(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    target = os.path.join(repo, "f.txt")
    tail = "".join("unchanged context %d\n" % i for i in range(12)) + "<<<<<<< original-example\n"

    def commit_version(first_line, message):
        _write(repo, "f.txt", first_line + "\n" + tail)
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", message)

    commit_version("base", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    commit_version("feature", "feature")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "other.txt", "main change\n")
    commit_version("main", "main")
    _git(repo, "checkout", "-q", "feature")
    assert _git(repo, "merge", "--no-edit", "main", check=False).returncode == 1

    command = "git checkout --theirs f.txt"
    assert wg.classify(command, repo) == ("allow", "")
    with open(target, "rb") as f:
        original = f.read()
    with open(target, "wb") as f:
        f.write(original.replace(b"<<<<<<< original-example", b"<<<<<<< OWNER-ONLY-DRAFT"))
    assert wg.classify(command, repo) == _refusal("checkout-path", 1)


def test_unlabeled_closing_marker_like_content_inside_a_conflict_does_not_hide_the_markers(
    tmp_path, monkeypatch,
):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    target = os.path.join(repo, "f.txt")

    def commit_version(first_line, message):
        _write(repo, "f.txt", first_line + "\n>>>>>>>literal\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", message)

    commit_version("base", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    commit_version("feature", "feature")
    _git(repo, "checkout", "-q", "main")
    commit_version("main", "main")
    _git(repo, "checkout", "-q", "feature")
    assert _git(repo, "merge", "--no-edit", "main", check=False).returncode == 1

    command = "git checkout --theirs f.txt"
    assert wg.classify(command, repo) == ("allow", "")
    with open(target, "rb") as f:
        original = f.read()
    with open(target, "wb") as f:
        f.write(original.replace(b">>>>>>>literal", b">>>>>>>OWNER-ONLY-DRAFT"))
    assert wg.classify(command, repo) == _refusal("checkout-path", 1)


@pytest.mark.parametrize("style", [None, "diff3", "zdiff3"])
def test_base_marker_like_line_in_the_theirs_half_is_ordinary_content(
    tmp_path, monkeypatch, style,
):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    if style:
        _git(repo, "config", "merge.conflictStyle", style)
    target = os.path.join(repo, "f.txt")

    def commit_version(content, message):
        _write(repo, "f.txt", content)
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", message)

    commit_version("base\n", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    commit_version("feature\n", "feature")
    _git(repo, "checkout", "-q", "main")
    commit_version("main\n||||||| original-example\n", "main")
    _git(repo, "checkout", "-q", "feature")
    assert _git(repo, "merge", "--no-edit", "main", check=False).returncode == 1

    command = "git checkout --theirs f.txt"
    assert wg.classify(command, repo) == ("allow", "")
    with open(target, "rb") as f:
        original = f.read()
    with open(target, "wb") as f:
        f.write(original.replace(b"||||||| original-example", b"||||||| OWNER-ONLY-DRAFT"))
    assert wg.classify(command, repo) == _refusal("checkout-path", 1)


def test_unrecognised_conflict_style_is_indeterminate(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch, conflict_style="zdiff3")
    _git(work, "config", "merge.conflictStyle", "bogus")
    assert wg.classify("git checkout --theirs f.txt", work) == _indeterminate("checkout-path")


def test_unreadable_conflict_style_is_indeterminate(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    real_run_git = wg._run_git

    def failing_config_read(cwd, *args):
        if args[:1] == ("config",):
            return subprocess.CompletedProcess(args, 128, "", "fatal: bad config")
        return real_run_git(cwd, *args)

    monkeypatch.setattr(wg, "_run_git", failing_config_read)
    assert wg.classify("git checkout --theirs f.txt", work) == _indeterminate("checkout-path")


def test_edge6_merge_staged_changes_on_unnamed_paths_do_not_count(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    with open(os.path.join(work, "a.txt"), "a") as f:
        f.write("builder's unstaged edit on an unnamed path\n")
    # The edit is on a.txt; the command names only f.txt, so only f.txt is judged.
    assert wg.classify("git checkout --theirs f.txt", work) == ("allow", "")


# --- restore --source ---------------------------------------------------------

def test_restore_source_of_unedited_conflicted_file_allows(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    assert wg.classify("git restore --source=main f.txt", work) == ("allow", "")


def test_restore_source_of_edited_conflicted_file_denies(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    with open(os.path.join(work, "f.txt"), "a") as f:
        f.write("builder's partial resolution\n")
    assert wg.classify("git restore --source=main f.txt", work) == _refusal("restore", 1)


@pytest.mark.parametrize("operand", ["sub", "sub/", "'*.txt'", "nosuch.txt"])
def test_edge7_restore_source_non_exact_operand_falls_to_whole_tree_probe(
    tmp_path, monkeypatch, operand,
):
    work = _merge_repo(tmp_path, monkeypatch)
    _write(work, "sub/untracked.txt", "builder's untracked file\n")
    decision, reason = wg.classify(f"git restore --source=main {operand}", work)
    assert decision == "deny"
    # The whole-tree probe's refusal, not the merge branch's fail-closed one.
    assert "would discard" in reason
    assert "could not determine" not in reason


# --- edges 1-3: fail closed ---------------------------------------------------

def test_edge1_merge_head_not_a_commit_denies(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    with open(_merge_head_file(work), "w") as f:
        f.write("this is not a commit\n")
    assert wg.classify("git checkout --theirs f.txt", work) == _indeterminate("checkout-path")


def test_edge1_merge_head_with_two_commit_lines_denies(tmp_path, monkeypatch):
    work = _merge_repo(tmp_path, monkeypatch)
    head = _git(work, "rev-parse", "HEAD").stdout.strip()
    merge_head = _git(work, "rev-parse", "MERGE_HEAD").stdout.strip()
    with open(_merge_head_file(work), "w") as f:
        f.write(merge_head + "\n" + head + "\n")
    assert wg.classify("git checkout --theirs f.txt", work) == _indeterminate("checkout-path")


def _fail_merge_tree(monkeypatch, how):
    real = wg._run_git

    def wrapped(cwd, *args):
        if "merge-tree" in args:
            if how == "timeout":
                raise subprocess.TimeoutExpired(["git", *args], 5)
            if how == "missing":
                raise FileNotFoundError("git")
            if how == "garbage":
                return subprocess.CompletedProcess(args, 0, "not-an-object-id\n", "")
            return subprocess.CompletedProcess(args, 128, "", "fatal: boom")
        return real(cwd, *args)

    monkeypatch.setattr(wg, "_run_git", wrapped)


@pytest.mark.parametrize("how", ["fails", "timeout", "missing", "garbage"])
def test_edge2_merge_tree_unavailable_denies(tmp_path, monkeypatch, how):
    work = _merge_repo(tmp_path, monkeypatch)
    _fail_merge_tree(monkeypatch, how)
    assert wg.classify("git checkout --theirs f.txt", work) == _indeterminate("checkout-path")


def test_edge2_merge_tree_failure_does_not_matter_for_a_stage_zero_target(
    tmp_path, monkeypatch,
):
    work = _merge_repo(tmp_path, monkeypatch)
    _fail_merge_tree(monkeypatch, "fails")
    # a.txt holds nothing the merge needs recomputed: only the unmerged path needs merge-tree.
    assert wg.classify("git checkout --theirs a.txt", work) == ("allow", "")


@pytest.mark.parametrize("command,action", [
    ("git checkout --theirs nosuch.txt", "checkout-path"),
    ("git checkout --ours -- nosuch.txt", "checkout-path"),
    ("git restore --theirs nosuch.txt", "restore"),
])
def test_edge3_operand_matching_nothing_refuses_as_indeterminate(
    tmp_path, monkeypatch, command, action,
):
    work = _merge_repo(tmp_path, monkeypatch)
    assert wg.classify(command, work) == _indeterminate(action)


# --- edges 8-9: forms outside the merge branch keep today's probe -------------

@pytest.mark.parametrize("command", [
    "git checkout --theirs main -- f.txt",
    "git -c core.quotepath=off checkout --theirs f.txt",
    "FOO=1 git checkout --theirs f.txt",
    "git restore --staged --worktree --theirs f.txt",
    "git restore --patch --theirs f.txt",
])
def test_edge8_forms_outside_the_merge_branch_keep_the_whole_tree_probe(
    tmp_path, monkeypatch, command,
):
    work = _merge_repo(tmp_path, monkeypatch)
    decision, reason = wg.classify(command, work)
    assert decision == "deny"
    assert "would discard" in reason


def test_edge9_no_merge_in_progress_keeps_the_whole_tree_probe(tmp_path, monkeypatch):
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "base\n")
    _commit_file(repo, "other.txt", "base\n")
    _write(repo, "other.txt", "builder's unrelated edit\n")
    assert wg.classify("git checkout --theirs f.txt", repo) == _refusal("checkout-path", 1)
