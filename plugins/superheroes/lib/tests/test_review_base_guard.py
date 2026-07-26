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
