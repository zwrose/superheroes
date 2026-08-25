"""PR mode for prior-comments resolution is read from session meta, not repo/ checkout (#1107)."""
import json
import os

import round_driver as RD
import round_records as RR


def _cfg(tmp_path):
    return {"repoRoot": str(tmp_path), "verifyCommand": "none"}


def _session_with_mode(tmp_path, mode=None, *, write_meta=True):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    if write_meta:
        meta = {}
        if mode is not None:
            meta["mode"] = mode
        with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    return session_dir


def test_prior_comments_pr_mode_without_repo_checkout_discloses(tmp_path):
    # axis: PR mode must disclose when prior-comments.json is absent — no repo/ required
    session_dir = _session_with_mode(tmp_path, "pr")
    assert not os.path.isdir(os.path.join(session_dir, "repo"))
    state = RD.new_state(_cfg(tmp_path))
    path = RD._resolve_prior_comments_path(session_dir, state)
    assert path.startswith("(")
    assert state["rounds"]["1"]["priorCommentsUnavailable"] is True


def test_prior_comments_branch_mode_absent_is_empty_no_disclosure(tmp_path):
    # axis: branch mode legitimately has no prior-comments file
    session_dir = _session_with_mode(tmp_path, "branch")
    state = RD.new_state(_cfg(tmp_path))
    assert RD._resolve_prior_comments_path(session_dir, state) == ""
    assert "priorCommentsUnavailable" not in state.get("rounds", {}).get("1", {})


def test_prior_comments_pr_mode_with_file_returns_real_path(tmp_path):
    # axis: present prior-comments.json is returned unchanged in PR mode
    session_dir = _session_with_mode(tmp_path, "pr")
    prior_path = os.path.join(session_dir, "prior-comments.json")
    with open(prior_path, "w", encoding="utf-8") as fh:
        fh.write("[]\n")
    state = RD.new_state(_cfg(tmp_path))
    assert RD._resolve_prior_comments_path(session_dir, state) == prior_path
    assert "priorCommentsUnavailable" not in state.get("rounds", {}).get("1", {})


def test_prior_comments_unknown_mode_fail_closed_discloses(tmp_path):
    # axis: unrecognized mode must disclose, not fall open to branch silence
    session_dir = _session_with_mode(tmp_path, "autofix")
    state = RD.new_state(_cfg(tmp_path))
    path = RD._resolve_prior_comments_path(session_dir, state)
    assert path.startswith("(")
    assert state["rounds"]["1"]["priorCommentsUnavailable"] is True


def test_prior_comments_absent_meta_fail_closed_discloses(tmp_path):
    # axis: missing meta.json is unknown mode — disclose, not branch silence
    session_dir = _session_with_mode(tmp_path, write_meta=False)
    state = RD.new_state(_cfg(tmp_path))
    path = RD._resolve_prior_comments_path(session_dir, state)
    assert path.startswith("(")
    assert state["rounds"]["1"]["priorCommentsUnavailable"] is True
