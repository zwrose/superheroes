"""PR mode for prior-comments resolution is read from session meta, not repo/ checkout (#1107)."""
import json
import os

import pytest

import round_commit
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


def _canonical_prior_path(session_dir):
    return RD._prior_comments_canonical_path(session_dir)


def _cli_next_prior_comments(tmp_path, session_dir, prior_path, *, mode="pr"):
    from test_round_driver import _guard_argv

    argv = ["next", "--session-dir", session_dir, "--prior-comments", prior_path]
    argv += _guard_argv(session_dir, mode=mode)
    rc = RD.main(argv)
    assert rc == 0
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    return state


def _assert_prior_comments_biconditional(session_dir, state):
    # axis: config["priorComments"] is non-None iff canonical prior-comments.json exists with equal contents
    canonical = _canonical_prior_path(session_dir)
    prior = state["config"].get("priorComments")
    file_exists = os.path.isfile(canonical)
    if prior is None:
        assert not file_exists
        return
    assert file_exists
    with open(canonical, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk == prior


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param(
            {
                "mode": "branch",
                "source": [{"id": "c1", "justification": "fixed"}],
                "cli_from": "external",
            },
            id="valid_list_elsewhere",
        ),
        pytest.param(
            {
                "mode": "branch",
                "source": None,
                "cli_from": "missing",
            },
            id="unreadable_path",
        ),
        pytest.param(
            {
                "mode": "branch",
                "source": {"not": "a-list"},
                "cli_from": "external",
            },
            id="non_list_json",
        ),
        pytest.param(
            {
                "mode": "branch",
                "source": [{"keep": "me"}],
                "cli_from": "canonical",
            },
            id="canonical_path_supplied",
        ),
        pytest.param(
            {
                "mode": "branch",
                "source": [{"new": True}],
                "cli_from": "external",
                "preexisting_canonical": [{"old": True}],
            },
            id="preexisting_canonical_replaced",
        ),
        pytest.param(
            {
                "mode": "branch",
                "source": [{"branch": True}],
                "cli_from": "external",
            },
            id="branch_mode_materialized",
        ),
        pytest.param(
            {
                "mode": "branch",
                "source": [{"write": "blocked"}],
                "cli_from": "external",
                "fail_materialize": True,
            },
            id="materialization_write_failure",
        ),
    ],
)
def test_prior_comments_config_canonical_biconditional(tmp_path, scenario, monkeypatch):
    session_dir = _session_with_mode(tmp_path, scenario["mode"])
    canonical = _canonical_prior_path(session_dir)
    source = scenario["source"]

    if scenario.get("preexisting_canonical") is not None:
        with open(canonical, "w", encoding="utf-8") as fh:
            json.dump(scenario["preexisting_canonical"], fh)

    if scenario["cli_from"] == "missing":
        cli_path = str(tmp_path / "does-not-exist.json")
    elif scenario["cli_from"] == "canonical":
        with open(canonical, "w", encoding="utf-8") as fh:
            json.dump(source, fh)
        cli_path = canonical
    else:
        cli_path = str(tmp_path / "prior-source.json")
        with open(cli_path, "w", encoding="utf-8") as fh:
            json.dump(source, fh)

    if scenario.get("fail_materialize"):
        def _boom(path, obj):
            raise OSError("bite-proof simulated write failure")

        monkeypatch.setattr(round_commit, "atomic_write_json", _boom)

    state = _cli_next_prior_comments(tmp_path, session_dir, cli_path, mode=scenario["mode"])
    _assert_prior_comments_biconditional(session_dir, state)

    if scenario.get("fail_materialize") or scenario["cli_from"] == "missing" or not isinstance(
            source, list):
        assert state["config"].get("priorComments") is None
        assert not os.path.isfile(canonical)
    else:
        assert state["config"]["priorComments"] == source
        resolved = RD._resolve_prior_comments_path(session_dir, state)
        assert resolved == canonical
        assert "priorCommentsUnavailable" not in state.get("rounds", {}).get("1", {})


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


def test_prior_comments_unavailable_marker_and_disclosure_inseparable(tmp_path):
    # axis: PR-mode unavailable marker must always record priorCommentsUnavailable — never decouple
    session_dir = _session_with_mode(tmp_path, "pr")
    state = RD.new_state(_cfg(tmp_path))
    path = RD._resolve_prior_comments_path(session_dir, state)
    assert path == RD._prior_comments_unavailable_marker()
    assert state["rounds"]["1"]["priorCommentsUnavailable"] is True

    broken = {"rounds": {}, "config": _cfg(tmp_path)}
    with pytest.raises(KeyError):
        RD._resolve_prior_comments_path(session_dir, broken)
