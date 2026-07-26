"""Tests for review_base_guard (#648)."""
import json
import os
import re
import shutil
import subprocess

import pytest

import review_base_guard as rbg
import store_core

REASON = rbg


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return str(root), sha


def _write_meta(session_dir, repo_root, sha, **overrides):
    os.makedirs(session_dir, exist_ok=True)
    meta = {
        "mode": "branch",
        "baseRef": sha,
        "baseBranch": "main",
        "baseFetch": "origin",
        "repoRoot": repo_root,
    }
    meta.update(overrides)
    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)


def _write_pr(session_dir, url):
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "pr.json"), "w", encoding="utf-8") as fh:
        json.dump({"url": url}, fh)


@pytest.fixture
def git_repo(tmp_path):
    return _init_repo(tmp_path)


# --- resolve_commit / pin -----------------------------------------------------

def test_resolve_commit_happy_path(git_repo):
    root, sha = git_repo
    assert rbg.resolve_commit(sha, root) == sha.lower()


def test_resolve_commit_empty_string(git_repo):
    root, _ = git_repo
    assert rbg.resolve_commit("", root) is None


def test_resolve_commit_literal_null(git_repo):
    root, _ = git_repo
    assert rbg.resolve_commit("null", root) is None


def test_resolve_commit_branch_name_rejected(git_repo):
    root, sha = git_repo
    # Prove main resolves via git — guard must still reject it.
    assert subprocess.run(
        ["git", "-C", root, "rev-parse", "--verify", "--quiet", "main^{commit}"],
        capture_output=True,
    ).returncode == 0
    assert rbg.resolve_commit("main", root) is None


def test_check_base_branch_name_reason_not_unresolved(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, baseRef="main")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_NOT_PINNED
    assert r["reason"] != REASON.REASON_UNRESOLVED


def test_check_base_abbreviated_sha_reason_not_unresolved(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, baseRef=sha[:7])
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_NOT_PINNED
    assert r["reason"] != REASON.REASON_UNRESOLVED


def test_check_base_literal_null_reason_not_unresolved(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, baseRef="null")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_NOT_PINNED
    assert r["reason"] != REASON.REASON_UNRESOLVED


def test_resolve_commit_abbreviated_sha(git_repo):
    root, sha = git_repo
    assert rbg.resolve_commit(sha[:7], root) is None


def test_resolve_commit_unknown_full_sha(git_repo):
    root, _ = git_repo
    bogus = "0" * 39 + "1"
    assert rbg.resolve_commit(bogus, root) is None


def test_resolve_commit_annotated_tag_object_id(git_repo):
    root, _ = git_repo
    subprocess.run(
        ["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t", "tag", "-a", "v1", "-m", "v1"],
        check=True,
        capture_output=True,
    )
    tag_oid = subprocess.run(
        ["git", "-C", root, "rev-parse", "v1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit_oid = subprocess.run(
        ["git", "-C", root, "rev-parse", "v1^{commit}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tag_oid == commit_oid:
        pytest.skip("annotated tag oid equals commit on this git")
    assert rbg.resolve_commit(tag_oid, root) is None


def test_resolve_commit_64_hex_shape_accepted(git_repo):
    root, _ = git_repo
    h64 = "a" * 64
    assert rbg.resolve_commit(h64, root) is None


def test_resolve_commit_uppercase_hex(git_repo):
    root, sha = git_repo
    assert rbg.resolve_commit(sha.upper(), root) == sha.lower()


def test_resolve_commit_non_string(git_repo):
    root, _ = git_repo
    assert rbg.resolve_commit(None, root) is None
    assert rbg.resolve_commit(5, root) is None
    assert rbg.resolve_commit({}, root) is None


def test_resolve_commit_run_seam(git_repo):
    root, sha = git_repo

    def none_run(_cwd, *_args):
        return None

    assert rbg.resolve_commit(sha, root, run=none_run) is None

    def wrong_run(_cwd, *_args):
        return "b" * 40

    assert rbg.resolve_commit(sha, root, run=wrong_run) is None


# --- meta.json ----------------------------------------------------------------

def test_meta_absent(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    os.remove(os.path.join(session, "meta.json"))
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_META_UNREADABLE


def test_meta_malformed_json(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    os.makedirs(session)
    with open(os.path.join(session, "meta.json"), "w") as fh:
        fh.write("{not json")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_META_UNREADABLE


def test_meta_json_list(git_repo, tmp_path):
    root, _ = git_repo
    session = str(tmp_path / "sess")
    os.makedirs(session)
    with open(os.path.join(session, "meta.json"), "w") as fh:
        json.dump([1, 2], fh)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_META_UNREADABLE


def test_meta_no_base_ref_key(git_repo, tmp_path):
    root, _ = git_repo
    session = str(tmp_path / "sess")
    os.makedirs(session)
    meta = {"mode": "branch", "baseBranch": "main", "baseFetch": "origin", "repoRoot": root}
    with open(os.path.join(session, "meta.json"), "w") as fh:
        json.dump(meta, fh)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_NOT_PINNED


def test_meta_base_ref_json_null(git_repo, tmp_path):
    root, _ = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, "a" * 40, baseRef=None)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_NOT_PINNED


# --- pin drift ----------------------------------------------------------------

def test_prior_pin_equal_mixed_case(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    r = rbg.check_base(session, root, prior_pin=sha.upper())
    assert r["ok"] is True


def test_prior_pin_different(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    other = "f" * 40
    r = rbg.check_base(session, root, prior_pin=other)
    assert r["reason"] == REASON.REASON_PIN_MOVED
    assert sha.lower() in r["detail"]
    assert other in r["detail"]


# --- fork / multi-remote ------------------------------------------------------

def test_pr_mode_matched_origin(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "git@github.com:acme/widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    _write_pr(session, "https://github.com/acme/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["ok"] is True
    assert r["baseRepoCheck"] == "matched"


def test_pr_mode_matched_origin_case_insensitive_path(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "git@github.com:Acme/Widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    _write_pr(session, "https://github.com/acme/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["ok"] is True
    assert r["baseRepoCheck"] == "matched"


def test_pr_mode_repo_mismatch(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "git@github.com:acme/widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    _write_pr(session, "https://github.com/otherorg/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_REPO_MISMATCH
    assert "otherorg" in r["detail"]
    assert "acme" in r["detail"]


def test_mode_unrecognized_empty(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_MODE_UNRECOGNIZED


def test_mode_unrecognized_absent(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    path = os.path.join(session, "meta.json")
    meta = json.load(open(path))
    del meta["mode"]
    with open(path, "w") as fh:
        json.dump(meta, fh)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_MODE_UNRECOGNIZED


@pytest.mark.parametrize("bad_mode", ["PR", "loop"])
def test_mode_unrecognized_values(git_repo, tmp_path, bad_mode):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode=bad_mode)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_MODE_UNRECOGNIZED


def test_prior_pin_non_string_int(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    r = rbg.check_base(session, root, prior_pin=5)
    assert r["reason"] == REASON.REASON_PIN_MOVED


def test_prior_pin_non_string_dict(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    r = rbg.check_base(session, root, prior_pin={"a": 1})
    assert r["reason"] == REASON.REASON_PIN_MOVED


def test_pr_mode_pr_json_absent(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "git@github.com:acme/widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_PR_REPO_UNRESOLVED


def test_pr_mode_bad_pr_url(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "git@github.com:acme/widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    _write_pr(session, "https://github.com/acme/widget")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_PR_REPO_UNRESOLVED


def test_pr_mode_no_origin(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    _write_pr(session, "https://github.com/acme/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_ORIGIN_UNRESOLVED


def test_branch_mode_ignores_pr_json(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="branch")
    _write_pr(session, "https://github.com/otherorg/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["ok"] is True
    assert r["baseRepoCheck"] == "not-applicable-branch-mode"


def test_pr_url_trailing_files_or_query(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "git@github.com:acme/widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    for url in (
        "https://github.com/acme/widget/pull/7/files",
        "https://github.com/acme/widget/pull/7?w=1",
    ):
        _write_pr(session, url)
        r = rbg.check_base(session, root)
        assert r["ok"] is True, url
        assert r["baseRepoCheck"] == "matched"


def test_pr_url_enterprise_host(git_repo, tmp_path):
    root, sha = git_repo
    subprocess.run(
        ["git", "-C", root, "remote", "add", "origin", "https://git.acme.corp/acme/widget.git"],
        check=True,
        capture_output=True,
    )
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, mode="pr")
    _write_pr(session, "https://git.acme.corp/acme/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["ok"] is True
    assert r["baseRepoCheck"] == "matched"


# --- round diff ---------------------------------------------------------------

def test_diff_none_path():
    r = rbg.check_round_diff(None)
    assert r["reason"] == REASON.REASON_DIFF_REQUIRED


def test_diff_missing_file(tmp_path):
    r = rbg.check_round_diff(str(tmp_path / "nope.txt"))
    assert r["reason"] == REASON.REASON_DIFF_UNREADABLE


def test_diff_directory_path(tmp_path):
    r = rbg.check_round_diff(str(tmp_path))
    assert r["reason"] == REASON.REASON_DIFF_UNREADABLE


def test_diff_invalid_utf8(tmp_path):
    p = tmp_path / "diff.txt"
    p.write_bytes(b"\xff\xfe\x00")
    r = rbg.check_round_diff(str(p))
    assert r["reason"] == REASON.REASON_DIFF_UNREADABLE


def test_diff_empty_file(tmp_path):
    p = tmp_path / "diff.txt"
    p.write_text("")
    r = rbg.check_round_diff(str(p))
    assert r["reason"] == REASON.REASON_DIFF_EMPTY


def test_diff_whitespace_only(tmp_path):
    p = tmp_path / "diff.txt"
    p.write_text("\n\n  \t\n")
    r = rbg.check_round_diff(str(p))
    assert r["reason"] == REASON.REASON_DIFF_EMPTY


def test_diff_one_hunk_ok(tmp_path):
    text = (
        "diff --git a/f.py b/f.py\n"
        "--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
    )
    p = tmp_path / "diff.txt"
    p.write_text(text)
    r = rbg.check_round_diff(str(p))
    assert r["ok"] is True
    assert r["text"] == text


def test_diff_malformed_non_git_output(tmp_path):
    p = tmp_path / "diff.txt"
    p.write_text("fatal: bad revision 'null'\n")
    r = rbg.check_round_diff(str(p))
    assert r["reason"] == REASON.REASON_DIFF_MALFORMED


def test_diff_rename_only_ok(tmp_path):
    text = (
        "diff --git a/x b/y\n"
        "similarity index 100%\n"
        "rename from x\n"
        "rename to y\n"
    )
    p = tmp_path / "diff.txt"
    p.write_text(text)
    r = rbg.check_round_diff(str(p))
    assert r["ok"] is True


def test_diff_binary_ok(tmp_path):
    text = "diff --git a/x b/x\nBinary files a/x and b/x differ\n"
    p = tmp_path / "diff.txt"
    p.write_text(text)
    r = rbg.check_round_diff(str(p))
    assert r["ok"] is True


# --- repo-root binding ----------------------------------------------------------

def test_repo_root_matches(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    r = rbg.check_base(session, root)
    assert r["ok"] is True


def test_repo_root_mismatch(git_repo, tmp_path):
    root, sha = git_repo
    other = tmp_path / "other"
    other.mkdir()
    session = str(tmp_path / "sess")
    _write_meta(session, str(other), sha)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH
    assert str(other) in r["detail"] or os.path.realpath(str(other)) in r["detail"]
    assert root in r["detail"] or os.path.realpath(root) in r["detail"]


def test_repo_root_absent(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    path = os.path.join(session, "meta.json")
    meta = json.load(open(path))
    del meta["repoRoot"]
    with open(path, "w") as fh:
        json.dump(meta, fh)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH


def test_repo_root_not_a_git_repo(tmp_path):
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    session = str(tmp_path / "sess")
    sha = "a" * 40
    _write_meta(session, str(nogit), sha)
    r = rbg.check_base(session, str(nogit))
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH


def test_repo_root_symlink_normalization(git_repo, tmp_path):
    root, sha = git_repo
    link = tmp_path / "link"
    try:
        link.symlink_to(root)
    except OSError:
        pytest.skip("symlink not supported")
    session = str(tmp_path / "sess")
    _write_meta(session, str(link), sha)
    r = rbg.check_base(session, root)
    assert r["ok"] is True


def test_repo_root_trailing_slash(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root + os.sep, sha)
    r = rbg.check_base(session, root)
    assert r["ok"] is True


def test_repo_root_empty_string(git_repo, tmp_path, monkeypatch):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, repoRoot="")
    monkeypatch.chdir(root)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH


def test_repo_root_relative_path(git_repo, tmp_path, monkeypatch):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, repoRoot=".")
    monkeypatch.chdir(root)
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH


def test_repo_root_empty_toplevel(git_repo, tmp_path, monkeypatch):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    monkeypatch.chdir(root)

    def empty_toplevel(_cwd, *args):
        if len(args) >= 2 and args[0] == "rev-parse" and args[1] == "--show-toplevel":
            return ""
        return store_core.run_git(_cwd, *args)

    r = rbg.check_base(session, root, run=empty_toplevel)
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH


# --- ordering -------------------------------------------------------------------

def test_ordering_meta_before_pr(git_repo, tmp_path):
    root, _ = git_repo
    session = str(tmp_path / "sess")
    os.makedirs(session)
    with open(os.path.join(session, "meta.json"), "w") as fh:
        fh.write("[]")
    _write_pr(session, "https://github.com/otherorg/widget/pull/7")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_META_UNREADABLE


def test_ordering_repo_root_before_unpinned(git_repo, tmp_path):
    root, sha = git_repo
    other = tmp_path / "other"
    other.mkdir()
    session = str(tmp_path / "sess")
    _write_meta(session, str(other), sha, baseRef="main")
    r = rbg.check_base(session, root)
    assert r["reason"] == REASON.REASON_REPO_ROOT_MISMATCH


# --- #648 — diff binding (stat level) -----------------------------------------

def _second_commit(repo_root, tmp_path, *, rename=False, binary=False, spaced_name=False):
    """Add a second commit on top of the init empty commit; return pin (first) sha."""
    pin = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if rename:
        path = os.path.join(repo_root, "old.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("v\n")
        subprocess.run(["git", "-C", repo_root, "add", "old.txt"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "add"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_root, "mv", "old.txt", "new.txt"], check=True, capture_output=True)
    elif spaced_name:
        path = os.path.join(repo_root, "x y.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("space\n")
        subprocess.run(["git", "-C", repo_root, "add", "x y.txt"], check=True, capture_output=True)
    elif binary:
        path = os.path.join(repo_root, "blob.bin")
        with open(path, "wb") as fh:
            fh.write(b"\x00\x01\xff")
        subprocess.run(["git", "-C", repo_root, "add", "blob.bin"], check=True, capture_output=True)
    else:
        path = os.path.join(repo_root, "f.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("line\n")
        subprocess.run(["git", "-C", repo_root, "add", "f.py"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "change"], check=True, capture_output=True)
    return pin


def _range_diff(repo_root, pin):
    return subprocess.run(
        ["git", "-C", repo_root, "diff", "%s...HEAD" % pin],
        check=True, capture_output=True, text=True,
    ).stdout


def _global_counts_from_stats(diff_text):
    stats, _, added, deleted = rbg._artifact_diff_stats(diff_text)
    return stats, added, deleted


def test_check_diff_binding_real_diff_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] and r["binding"] == "file-set+line-counts"


def test_check_diff_binding_wrong_pin_totals(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    wrong_pin = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    text = _range_diff(root, wrong_pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_MISMATCH
    assert "+" in r["detail"] and "-" in r["detail"]


def test_check_diff_binding_contamination_refuses(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)
    extra = (
        "\ndiff --git a/extra b/extra\nnew file mode 100644\n--- /dev/null\n+++ b/extra\n"
        "@@ -0,0 +1 @@\n+contam\n"
    )
    r = rbg.check_diff_binding(text + extra, pin, root)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_MISMATCH


def test_check_diff_binding_line_count_drift_refuses(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    lines = _range_diff(root, pin).splitlines()
    trimmed = "\n".join(ln for ln in lines if not (ln.startswith("+") and not ln.startswith("+++")))
    r = rbg.check_diff_binding(trimmed + "\n", pin, root)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_MISMATCH
    assert "artifact" in r["detail"] and "pin" in r["detail"]


def test_check_diff_binding_path_set_mismatch_totals_match(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)
    plus_before, minus_before = _global_counts_from_stats(text)[1:]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("diff --git "):
            lines[i] = "diff --git a/decoy.py b/decoy.py"
            break
    else:
        pytest.fail("expected at least one diff --git header")
    tampered = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    plus_after, minus_after = _global_counts_from_stats(tampered)[1:]
    assert plus_after == plus_before and minus_after == minus_before
    r = rbg.check_diff_binding(tampered, pin, root)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_MISMATCH
    assert "decoy.py" in r["detail"]


def test_check_diff_binding_binary_skips_numstat_dash(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path, binary=True)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"]


def test_check_diff_binding_rename_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path, rename=True)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] and r["binding"] == "file-set+line-counts"
    # Root-level rename only — git does not emit brace-compressed numstat for this shape.
    # Brace-compressed directory renames are covered by test_check_diff_binding_dir_rename_ok.


def _pin_and_dir_rename_with_modify(repo_root):
    old_dir = os.path.join(repo_root, "olddir")
    os.makedirs(old_dir)
    fpath = os.path.join(old_dir, "f.txt")
    with open(fpath, "w", encoding="utf-8") as fh:
        fh.write("v1\n")
    subprocess.run(["git", "-C", repo_root, "add", "olddir"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "base"], check=True, capture_output=True)
    pin = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    new_path = os.path.join(repo_root, "newdir", "f.txt")
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    subprocess.run(
        ["git", "-C", repo_root, "mv", fpath, new_path],
        check=True,
        capture_output=True,
    )
    with open(new_path, "w", encoding="utf-8") as fh:
        fh.write("v1\nv2\n")
    subprocess.run(["git", "-C", repo_root, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "mvdir"], check=True, capture_output=True)
    return pin


def test_check_diff_binding_dir_rename_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _pin_and_dir_rename_with_modify(root)
    numstat_plain = subprocess.run(
        ["git", "-C", root, "diff", "--numstat", "%s...HEAD" % pin],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "=>" in numstat_plain, "git must emit brace-compressed rename numstat: %r" % numstat_plain
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] and r["binding"] == "file-set+line-counts"


def _pin_and_rename_within_dir(repo_root):
    lib = os.path.join(repo_root, "lib")
    os.makedirs(lib)
    a_path = os.path.join(lib, "a.py")
    with open(a_path, "w", encoding="utf-8") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", repo_root, "add", "lib"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "base"], check=True, capture_output=True)
    pin = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    b_path = os.path.join(lib, "b.py")
    subprocess.run(["git", "-C", repo_root, "mv", a_path, b_path], check=True, capture_output=True)
    with open(b_path, "w", encoding="utf-8") as fh:
        fh.write("x\ny\n")
    subprocess.run(["git", "-C", repo_root, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "rename"], check=True, capture_output=True)
    return pin


def test_check_diff_binding_rename_within_dir_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _pin_and_rename_within_dir(root)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] and r["binding"] == "file-set+line-counts"


def test_parse_numstat_z_normal_and_rename():
    fixture = (
        "1\t0\tkeep.txt"
        + "\0"
        + "1\t1\t"
        + "\0"
        + "olddir/f.txt"
        + "\0"
        + "newdir/f.txt"
        + "\0"
    )
    stats, per_file_ok, added, deleted = rbg._parse_numstat(fixture)
    assert per_file_ok is True
    assert stats == {"keep.txt": (1, 0), "newdir/f.txt": (1, 1)}
    assert added == 2 and deleted == 1


def test_parse_numstat_surrogate_escaped_path():
    raw_name = b"\xff\xfe.txt"
    path = raw_name.decode("utf-8", errors="surrogateescape")
    fixture = (
        "1\t0\tnormal.txt"
        + "\0"
        + "2\t1\t"
        + path
        + "\0"
    )
    stats, per_file_ok, added, deleted = rbg._parse_numstat(fixture)
    assert per_file_ok is True
    assert stats["normal.txt"] == (1, 0)
    assert stats[path] == (2, 1)
    assert added == 3 and deleted == 1
    assert path in stats


def test_run_git_bytes_fails_closed_on_bad_revision(git_repo):
    root, _ = git_repo
    assert rbg._run_git_bytes(root, "diff", "--numstat", "-z", "0" * 40 + "...HEAD") is None


def test_check_diff_binding_numstat_raw_bytes_no_crash(git_repo, tmp_path, monkeypatch):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("diff --git "):
            lines[i] = 'diff --git "a/f.py" "b/f.py"'
            break
    text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    _, _, exp_added, exp_deleted = rbg._artifact_diff_stats(text)
    raw_path = b"\xff\xfe.txt"
    numstat_bytes = (
        ("%d\t%d\t" % (exp_added, exp_deleted)).encode("ascii") + raw_path + b"\x00"
    )

    real_bytes = rbg._run_git_bytes

    def fake_bytes(cwd, *args):
        if args and args[0] == "diff" and "--numstat" in args:
            return numstat_bytes
        return real_bytes(cwd, *args)

    monkeypatch.setattr(rbg, "_run_git_bytes", fake_bytes)

    def exploding_run(cwd, *args):
        if args and args[0] == "diff" and "--numstat" in args:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return store_core.run_git(cwd, *args)

    monkeypatch.setattr(store_core, "run_git", exploding_run)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] is True
    assert r["binding"] == "line-counts-only"


def test_check_diff_binding_default_path_calls_bytes_runner(git_repo, tmp_path, monkeypatch):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)
    calls = []
    real_bytes = rbg._run_git_bytes

    def track(cwd, *args):
        calls.append(args)
        return real_bytes(cwd, *args)

    monkeypatch.setattr(rbg, "_run_git_bytes", track)
    rbg.check_diff_binding(text, pin, root)
    assert any(a and a[0] == "diff" and "--numstat" in a for a in calls)


def test_check_diff_binding_non_utf8_path_real_repo(git_repo, tmp_path):
    root, _ = git_repo
    pin = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    bad_path = os.path.join(root.encode(), b"\xff\xfe.txt")
    try:
        with open(bad_path, "wb") as fh:
            fh.write(b"x\n")
    except (OSError, UnicodeEncodeError):
        pytest.skip(
            "filesystem rejected a non-UTF-8 byte sequence in the path (e.g. APFS EILSEQ)"
        )
    subprocess.run(["git", "-C", root, "add", "--", bad_path], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "commit", "-q", "-m", "badname"], check=True, capture_output=True)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] is True
    assert r["binding"] == "line-counts-only"


def test_check_diff_binding_explicit_run_returns_bytes(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)

    def stub_bytes(cwd, *args):
        if args and args[0] == "diff" and "--numstat" in args:
            return rbg._run_git_bytes(cwd, *args)
        return store_core.run_git(cwd, *args)

    r = rbg.check_diff_binding(text, pin, root, run=stub_bytes)
    assert r["ok"] is True


def test_check_diff_binding_unresolvable_numstat_row_line_counts_only(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = (
        "diff --git a/f.py b/f.py\n"
        "--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,6 @@\n"
        "-old\n"
        "+n1\n+n2\n+n3\n+n4\n+n5\n"
        "\\ No newline at end of file\n"
        "@@ -2,2 +0,0 @@\n"
        "-x\n"
        "-y\n"
    )
    _, act_added, act_deleted = _global_counts_from_stats(text)
    assert act_added == 5 and act_deleted == 3

    # Incomplete rename triple: counts must still land in the global expected total.
    numstat_z = "5\t3\t\0"

    def stub(cwd, *args):
        if args and args[0] == "diff" and "--numstat" in args:
            return numstat_z
        return store_core.run_git(cwd, *args)

    r = rbg.check_diff_binding(text, pin, root, run=stub)
    assert r["ok"] and r["binding"] == "line-counts-only"


def test_check_diff_binding_quoted_path_line_counts_only(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path, spaced_name=True)
    text = _range_diff(root, pin)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("diff --git "):
            # Force a quoted-path header git may emit; the simple regex cannot parse it.
            lines[i] = re.sub(
                r'^diff --git a/(.*) b/(.*)$',
                r'diff --git "a/\1" "b/\2"',
                line,
            )
            break
    text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] and r["binding"] == "line-counts-only"


def test_check_diff_binding_git_none_fail_closed(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    text = _range_diff(root, pin)

    def stub(cwd, *args):
        if args and args[0] == "diff" and "--numstat" in args:
            return None
        return store_core.run_git(cwd, *args)

    r = rbg.check_diff_binding(text, pin, root, run=stub)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_UNVERIFIABLE
    assert "recomputed" in r["detail"]


def _second_commit_plus_plus_lines(repo_root, tmp_path):
    """Second commit adds lines whose content starts with ++ / --- (false-refusal class)."""
    pin = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    path = os.path.join(repo_root, "f.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("keep\n+++ b/some/path\n--- a/other/path\n")
    subprocess.run(["git", "-C", repo_root, "add", "f.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "plus"], check=True, capture_output=True)
    return pin


def test_check_diff_binding_added_plus_plus_content_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit_plus_plus_lines(root, tmp_path)
    text = _range_diff(root, pin)
    numstat = subprocess.run(
        ["git", "-C", root, "diff", "--numstat", "%s...HEAD" % pin],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert numstat.split("\t")[0] == "3"
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"] and r["binding"] == "file-set+line-counts"


def _second_commit_deleted_dash_dash(repo_root):
    path = os.path.join(repo_root, "g.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("--leading\n")
    subprocess.run(["git", "-C", repo_root, "add", "g.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "add"], check=True, capture_output=True)
    pin = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("replaced\n")
    subprocess.run(["git", "-C", repo_root, "add", "g.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "del"], check=True, capture_output=True)
    return pin


def test_check_diff_binding_deleted_dash_dash_content_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit_deleted_dash_dash(root)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"]


def test_check_diff_binding_file_headers_not_counted(git_repo, tmp_path):
    root, _ = git_repo
    path = os.path.join(root, "one.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("old\n")
    subprocess.run(["git", "-C", root, "add", "one.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "commit", "-q", "-m", "add"], check=True, capture_output=True)
    pin = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    subprocess.run(["git", "-C", root, "add", "one.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "commit", "-q", "-m", "chg"], check=True, capture_output=True)
    text = _range_diff(root, pin)
    _, added, deleted = _global_counts_from_stats(text)
    assert added == 1 and deleted == 1


def test_check_diff_binding_no_newline_marker_not_deletion(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path)
    lines = _range_diff(root, pin).splitlines()
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if line.startswith("+") and not line.startswith("+++"):
            out.append("\\ No newline at end of file")
            break
    text = "\n".join(out) + "\n"
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"]


def _two_file_commit(repo_root):
    pin = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    a_path = os.path.join(repo_root, "A.txt")
    b_path = os.path.join(repo_root, "B.txt")
    with open(a_path, "w", encoding="utf-8") as fh:
        fh.write("a1\na2\n")
    with open(b_path, "w", encoding="utf-8") as fh:
        fh.write("b1\nb2\n")
    subprocess.run(["git", "-C", repo_root, "add", "A.txt", "B.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "base"], check=True, capture_output=True)
    with open(a_path, "w", encoding="utf-8") as fh:
        fh.write("a1\na2\nx\ny\n")
    with open(b_path, "w", encoding="utf-8") as fh:
        fh.write("")
    subprocess.run(["git", "-C", repo_root, "add", "A.txt", "B.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "twofile"], check=True, capture_output=True)
    return pin


def test_check_diff_binding_per_file_swap_refuses(git_repo, tmp_path):
    # Refusal here is decided by the global totals leg; per-file leg is covered by
    # test_check_diff_binding_per_file_distribution_isolates_leg.
    root, _ = git_repo
    pin = _two_file_commit(root)
    good = _range_diff(root, pin)

    def stub(cwd, *args):
        if args and args[0] == "diff" and "--numstat" in args:
            return "2\t0\tA.txt\00\t2\tB.txt\0"
        return store_core.run_git(cwd, *args)

    sections = []
    cur = []
    for line in good.splitlines():
        if line.startswith("diff --git ") and cur:
            sections.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        sections.append(cur)
    assert len(sections) == 2
    swapped = "\n".join(
        ["\n".join(sections[1]), "\n".join(sections[0])]
    ) + ("\n" if good.endswith("\n") else "")
    ga, gd = _global_counts_from_stats(good)[1:]
    sa, sd = _global_counts_from_stats(swapped)[1:]
    assert (ga, gd) == (sa, sd)
    r = rbg.check_diff_binding(swapped, pin, root, run=stub)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_MISMATCH


def test_check_diff_binding_per_file_distribution_isolates_leg(git_repo, tmp_path):
    root, _ = git_repo
    pin = _two_file_commit(root)
    good = _range_diff(root, pin)
    sections = []
    cur = []
    for line in good.splitlines():
        if line.startswith("diff --git ") and cur:
            sections.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        sections.append(cur)
    assert len(sections) == 2
    a_sec, b_sec = sections[0], sections[1]
    plus_idx = None
    for i, line in enumerate(a_sec):
        if line.startswith("+") and not line.startswith("+++"):
            plus_idx = i
            break
    assert plus_idx is not None, "expected at least one added line in A.txt hunk"
    moved_line = a_sec.pop(plus_idx)
    inserted = False
    for i, line in enumerate(b_sec):
        if line.startswith("@@"):
            b_sec.insert(i + 1, moved_line)
            inserted = True
            break
    if not inserted:
        b_sec.extend(["@@ -0,0 +1,1 @@", moved_line])
    mutated = "\n".join(["\n".join(a_sec), "\n".join(b_sec)]) + (
        "\n" if good.endswith("\n") else ""
    )
    pin_added, pin_deleted = _global_counts_from_stats(good)[1:]
    art_added, art_deleted = _global_counts_from_stats(mutated)[1:]
    assert (art_added, art_deleted) == (pin_added, pin_deleted), (
        "global leg must not be what fires: artifact +%d/-%d vs pin +%d/-%d"
        % (art_added, art_deleted, pin_added, pin_deleted)
    )
    r = rbg.check_diff_binding(mutated, pin, root)
    assert not r["ok"] and r["reason"] == REASON.REASON_DIFF_BASE_MISMATCH
    detail = r["detail"]
    assert "A.txt" in detail and "exp=" in detail and "act=" in detail
    assert "B.txt" in detail and detail.count("exp=") >= 2 and detail.count("act=") >= 2


def test_check_diff_binding_spaced_path_still_ok(git_repo, tmp_path):
    root, _ = git_repo
    pin = _second_commit(root, tmp_path, spaced_name=True)
    text = _range_diff(root, pin)
    r = rbg.check_diff_binding(text, pin, root)
    assert r["ok"]


# --- #648 — baseDegraded on check_base ----------------------------------------

def test_check_base_base_fetch_fetched_not_degraded(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, baseFetch="fetched")
    r = rbg.check_base(session, root)
    assert r["ok"] and r["baseDegraded"] is False


def test_check_base_base_fetch_failed_degraded(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha, baseFetch="fetch-failed (offline)")
    r = rbg.check_base(session, root)
    assert r["ok"] and r["baseDegraded"] is True


def test_check_base_base_fetch_absent_degraded(git_repo, tmp_path):
    root, sha = git_repo
    session = str(tmp_path / "sess")
    _write_meta(session, root, sha)
    meta = json.load(open(os.path.join(session, "meta.json"), encoding="utf-8"))
    meta.pop("baseFetch", None)
    with open(os.path.join(session, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    r = rbg.check_base(session, root)
    assert r["ok"] and r["baseDegraded"] is True


# --- #648 / #637 — shipped SKILL.md base-fetch refspec (zsh :r) ---------------

def _review_code_skill_md_path():
    lib_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(os.path.dirname(lib_dir), "skills", "review-code", "SKILL.md")


def test_skill_base_fetch_refspec_braced_against_zsh_modifier():
    skill_path = _review_code_skill_md_path()
    with open(skill_path, encoding="utf-8") as fh:
        lines = [ln for ln in fh if ln.startswith("BASE_FETCH=fetched;")]
    assert len(lines) == 1, f"expected exactly one BASE_FETCH=fetched line in {skill_path}, got {len(lines)}"
    line = lines[0]
    m_refspec = re.search(r'origin "(\+refs/heads/[^"]+)"', line)
    assert m_refspec, f"could not extract refspec from shipped line: {line!r}"
    refspec_tpl = m_refspec.group(1)
    bad = re.search(r"\$[A-Za-z_][A-Za-z0-9_]*:", refspec_tpl)
    assert bad is None, (
        f"unbraced $VAR: before colon — zsh treats : as history modifier (:r), "
        f"corrupting refspec and stale base pin (#637): {bad.group()!r} in refspec {refspec_tpl!r}"
    )
    zsh = shutil.which("zsh")
    if not zsh:
        pytest.skip("zsh not available")
    script = f'BASE_BRANCH=main; echo "{refspec_tpl}"'
    out = subprocess.run(
        [zsh, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "+refs/heads/main:refs/remotes/origin/main", (
        f"zsh expanded refspec incorrectly (zsh :r / #637 class): got {out!r}"
    )


def test_skill_mode_assigned_in_setup_fences():
    skill_path = _review_code_skill_md_path()
    with open(skill_path, encoding="utf-8") as fh:
        text = fh.read()
    assert "MODE=pr" in text, f"MODE=pr not found in shipped {skill_path}"
    assert "MODE=branch" in text, f"MODE=branch not found in shipped {skill_path}"
