"""Tests for session_mode.resolve — review-session mode SSOT (#1151)."""
import json
import os
import subprocess

import pytest

import session_mode as sm


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


def _write_check_base_meta(session_dir, repo_root, sha, **overrides):
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


def _write_session_meta(session_dir, payload):
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def _assert_resolved(result, mode, evidence):
    assert result == {
        "mode": mode,
        "evidence": evidence,
        "resolved": True,
        "disclosure": None,
    }


def _assert_unresolved(result, disclosure_substr=None):
    assert result["mode"] == sm.MODE_PR
    assert result["evidence"] == sm.EVIDENCE_UNRESOLVED
    assert result["resolved"] is False
    assert isinstance(result["disclosure"], str)
    assert result["disclosure"]
    if disclosure_substr is not None:
        assert disclosure_substr in result["disclosure"]


def test_resolve_meta_mode_pr():
    _assert_resolved(sm.resolve({"mode": "pr"}, {}), "pr", sm.EVIDENCE_SESSION_META)


def test_resolve_meta_mode_branch():
    _assert_resolved(
        sm.resolve({"mode": "branch"}, {}), "branch", sm.EVIDENCE_SESSION_META,
    )


def test_resolve_config_mode_when_meta_empty():
    _assert_resolved(
        sm.resolve({}, {"mode": "branch"}), "branch", sm.EVIDENCE_DRIVER_CONFIG,
    )


def test_resolve_unresolved_when_both_empty():
    _assert_unresolved(sm.resolve({}, {}), "not set")


def test_resolve_invalid_meta_does_not_fall_through_to_config():
    _assert_unresolved(
        sm.resolve({"mode": "bogus"}, {"mode": "branch"}),
        "session metadata",
    )


@pytest.mark.parametrize("meta", [{"mode": ""}, {"mode": None}])
def test_resolve_present_but_invalid_empty_meta(meta):
    _assert_unresolved(sm.resolve(meta, {"mode": "branch"}), "session metadata")


@pytest.mark.parametrize("meta", [{"mode": 123}, {"mode": ["pr"]}])
def test_resolve_non_string_meta_mode(meta):
    _assert_unresolved(sm.resolve(meta, {}))


def test_resolve_none_inputs():
    _assert_unresolved(sm.resolve(None, None))


def test_resolve_non_dict_inputs():
    _assert_unresolved(sm.resolve("notadict", 42))


def test_resolve_wrong_case_meta_mode():
    _assert_unresolved(sm.resolve({"mode": "PR"}, {"mode": "branch"}))


_MALFORMED_INPUTS = [
    (None, None),
    ("notadict", 42),
    ({"mode": 123}, {}),
    ({"mode": ["pr"]}, {}),
    ({"mode": ""}, {}),
    ({"mode": None}, {}),
    ({"mode": "bogus"}, {}),
    ({"mode": "PR"}, {}),
    ({}, {}),
]


@pytest.mark.parametrize("meta,config", _MALFORMED_INPUTS)
def test_resolve_never_raises(meta, config):
    sm.resolve(meta, config)


def test_resolve_purity_equal_but_not_identical():
    first = sm.resolve({"mode": "pr"}, {})
    second = sm.resolve({"mode": "pr"}, {})
    assert first == second
    assert first is not second


def test_resolve_purity_mutation_does_not_affect_next_call():
    result = sm.resolve({}, {})
    result["mode"] = "branch"
    result["resolved"] = True
    next_result = sm.resolve({}, {})
    _assert_unresolved(next_result, "not set")


def test_evidence_line_resolved_from_meta():
    result = sm.resolve({"mode": "pr"}, {})
    assert sm.evidence_line(result) == "Review session mode pr (from session metadata)."


def test_evidence_line_resolved_from_config():
    result = sm.resolve({}, {"mode": "branch"})
    assert (
        sm.evidence_line(result)
        == "Review session mode branch (from driver configuration)."
    )


def test_evidence_line_unresolved_returns_disclosure():
    result = sm.resolve({}, {})
    assert sm.evidence_line(result) == result["disclosure"]


@pytest.fixture
def git_repo(tmp_path):
    return _init_repo(tmp_path)


@pytest.mark.parametrize(
    "meta_payload,expected_mode_repr",
    [
        ({}, None),
        ({"mode": None}, None),
        ({"mode": "bogus"}, "bogus"),
        ({"mode": 5}, 5),
    ],
)
def test_check_base_mode_derivation_refuses_invalid(
    git_repo, tmp_path, meta_payload, expected_mode_repr,
):
    """T4: check_base still refuses invalid session modes with unchanged reason/detail."""
    import review_base_guard as rbg

    root, sha = git_repo
    session = str(tmp_path / "sess-invalid")
    payload = {
        "baseRef": sha,
        "baseBranch": "main",
        "baseFetch": "origin",
        "repoRoot": root,
    }
    payload.update(meta_payload)
    _write_session_meta(session, payload)
    result = rbg.check_base(session, root)
    assert result["ok"] is False
    assert result["reason"] == rbg.REASON_MODE_UNRECOGNIZED
    assert result["detail"] == (
        "meta.mode must be 'pr' or 'branch', got %s" % repr(expected_mode_repr)
    )


@pytest.mark.parametrize("mode", ["pr", "branch"])
def test_check_base_mode_derivation_accepts_valid(git_repo, tmp_path, mode):
    """T4: check_base still proceeds past mode resolution for pr and branch."""
    import review_base_guard as rbg

    root, sha = git_repo
    session = str(tmp_path / ("sess-" + mode))
    _write_check_base_meta(session, root, sha, mode=mode)
    if mode == "pr":
        subprocess.run(
            ["git", "-C", root, "remote", "add", "origin", "git@github.com:acme/widget.git"],
            check=True,
            capture_output=True,
        )
        with open(os.path.join(session, "pr.json"), "w", encoding="utf-8") as fh:
            json.dump({"url": "https://github.com/acme/widget/pull/1"}, fh)
    result = rbg.check_base(session, root)
    assert result.get("reason") != rbg.REASON_MODE_UNRECOGNIZED


@pytest.mark.parametrize(
    "meta_payload",
    [
        {},
        {"mode": None},
        {"mode": "bogus"},
        {"mode": 5},
    ],
)
def test_read_meta_mode_derivation_refuses_invalid(tmp_path, meta_payload):
    """T4: _read_meta still refuses invalid session modes with unchanged reason."""
    import grounding_stage as gs

    session = str(tmp_path / "sess-invalid")
    _write_session_meta(session, meta_payload)
    result = gs._read_meta(session)
    assert result["ok"] is False
    assert result["reason"] == "meta-mode-unknown"


@pytest.mark.parametrize("mode", ["pr", "branch"])
def test_read_meta_mode_derivation_accepts_valid(tmp_path, mode):
    """T4: _read_meta still proceeds for pr and branch."""
    import grounding_stage as gs

    session = str(tmp_path / ("sess-" + mode))
    _write_session_meta(session, {"mode": mode})
    result = gs._read_meta(session)
    assert result == {"ok": True, "mode": mode}
