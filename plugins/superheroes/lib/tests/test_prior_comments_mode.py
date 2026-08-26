"""PR mode for prior-comments resolution is read from session meta, not repo/ checkout (#1107)."""
import json
import os
import subprocess

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
    if mode == "pr":
        repo = os.path.join(session_dir, "_gitrepo")
        subprocess.check_call(
            ["git", "remote", "add", "origin", "git@github.com:acme/widget.git"],
            cwd=repo,
        )
        with open(os.path.join(session_dir, "pr.json"), "w", encoding="utf-8") as fh:
            json.dump({"url": "https://github.com/acme/widget/pull/7"}, fh)
    rc = RD.main(argv)
    assert rc == 0
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    return state


def _assert_prior_comments_biconditional(session_dir, state):
    # axis: for comments supplied via next --prior-comments, config["priorComments"] is non-None
    # iff canonical prior-comments.json exists with equal contents (directly-written canonical
    # files are the pre-existing path tracked in #958)
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
                "mode": "pr",
                "source": [{"id": "c1", "justification": "fixed"}],
                "cli_from": "external",
            },
            id="pr_valid_list_elsewhere",
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
                "mode": "pr",
                "source": None,
                "cli_from": "missing",
            },
            id="pr_unreadable_path",
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
                "mode": "pr",
                "source": [{"new": True}],
                "cli_from": "external",
                "preexisting_canonical": [{"old": True}],
            },
            id="pr_preexisting_canonical_replaced",
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
        pytest.param(
            {
                "mode": "pr",
                "source": [{"write": "blocked"}],
                "cli_from": "external",
                "fail_materialize": True,
            },
            id="pr_materialization_write_failure",
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

    mode = scenario["mode"]
    is_failure = (
        scenario.get("fail_materialize")
        or scenario["cli_from"] == "missing"
        or not isinstance(source, list)
    )
    if is_failure:
        assert state["config"].get("priorComments") is None
        assert not os.path.isfile(canonical)
        if mode == "pr":
            resolved = RD._resolve_prior_comments_path(session_dir, state)
            assert resolved == RD._prior_comments_unavailable_marker()
            assert state.get("rounds", {}).get("1", {}).get("priorCommentsUnavailable") is True
    else:
        assert state["config"]["priorComments"] == source
        resolved = RD._resolve_prior_comments_path(session_dir, state)
        assert resolved == canonical
        assert "priorCommentsUnavailable" not in state.get("rounds", {}).get("1", {})
        if mode == "pr":
            assert resolved != RD._prior_comments_unavailable_marker()


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


def _run_next_prior_comments_cli(capsys, session_dir, prior_path):
    from test_round_driver import _guard_argv

    argv = ["next", "--session-dir", session_dir, "--prior-comments", prior_path]
    argv += _guard_argv(session_dir, fresh=False)
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out.splitlines()[-1]) if out else None
    return rc, parsed


def test_prior_comments_on_non_fresh_state_refused_preserves_canonical(tmp_path, capsys):
    # axis: non-fresh --prior-comments must refuse before clobbering the canonical file
    session_dir = _session_with_mode(tmp_path, "branch")
    prior_a = str(tmp_path / "prior-a.json")
    prior_b = str(tmp_path / "prior-b.json")
    with open(prior_a, "w", encoding="utf-8") as fh:
        json.dump([{"id": "a", "justification": "from A"}], fh)
    with open(prior_b, "w", encoding="utf-8") as fh:
        json.dump([{"id": "b", "justification": "from B"}], fh)

    _cli_next_prior_comments(tmp_path, session_dir, prior_a, mode="branch")
    canonical = _canonical_prior_path(session_dir)
    with open(canonical, "rb") as fh:
        before_bytes = fh.read()

    rc, out = _run_next_prior_comments_cli(capsys, session_dir, prior_b)
    assert rc == 1
    assert out == {"ok": False, "reason": "prior-comments-not-fresh-state", "value": prior_b}

    with open(canonical, "rb") as fh:
        assert fh.read() == before_bytes
    ok, state = RD.load_state(session_dir)
    assert ok and state["config"]["priorComments"] == [{"id": "a", "justification": "from A"}]


def test_prior_comments_on_non_fresh_state_refused_when_canonical_absent(tmp_path, capsys):
    # axis: refusal must not create a canonical file that was absent
    from test_round_driver import _guard_argv, _run_main

    session_dir = _session_with_mode(tmp_path, "branch")
    rc0, _ = _run_main(["next", "--session-dir", session_dir] + _guard_argv(session_dir), capsys)
    assert rc0 == 0
    canonical = _canonical_prior_path(session_dir)
    assert not os.path.isfile(canonical)

    prior_path = str(tmp_path / "prior-new.json")
    with open(prior_path, "w", encoding="utf-8") as fh:
        json.dump([{"id": "new"}], fh)

    rc, out = _run_next_prior_comments_cli(capsys, session_dir, prior_path)
    assert rc == 1
    assert out == {"ok": False, "reason": "prior-comments-not-fresh-state", "value": prior_path}
    assert not os.path.isfile(canonical)


def test_prior_comments_on_unreadable_state_refused(tmp_path, capsys):
    # axis: load_state refusal (v1 state) is not fresh — same loud refusal, no materialization
    from test_round_driver import _guard_argv

    session_dir = str(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {}}, fh)
    prior_path = str(tmp_path / "prior.json")
    with open(prior_path, "w", encoding="utf-8") as fh:
        json.dump([], fh)
    canonical = _canonical_prior_path(session_dir)

    argv = ["next", "--session-dir", session_dir, "--prior-comments", prior_path]
    argv += _guard_argv(session_dir)
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out.splitlines()[-1])
    assert rc == 1
    assert parsed == {"ok": False, "reason": "prior-comments-not-fresh-state", "value": prior_path}
    assert not os.path.isfile(canonical)


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


def test_prior_comments_deeply_nested_json_fail_closed(tmp_path):
    # axis: deeply nested valid JSON must not crash next — priorComments stays unset
    session_dir = _session_with_mode(tmp_path, "branch")
    canonical = _canonical_prior_path(session_dir)
    depth = 2000
    prior_path = str(tmp_path / "deep.json")
    with open(prior_path, "w", encoding="utf-8") as fh:
        fh.write("[" * depth + "]" * depth)

    state = _cli_next_prior_comments(tmp_path, session_dir, prior_path, mode="branch")
    assert state["config"].get("priorComments") is None
    assert not os.path.isfile(canonical)


def test_prior_comments_post_replace_write_failure_reconciles(tmp_path, monkeypatch):
    # axis: when write raises after the file landed, reconciliation returns True iff on-disk matches
    session_dir = _session_with_mode(tmp_path, "branch")
    canonical = _canonical_prior_path(session_dir)
    source = [{"id": "c1", "justification": "fixed"}]
    prior_path = str(tmp_path / "prior-source.json")
    with open(prior_path, "w", encoding="utf-8") as fh:
        json.dump(source, fh)

    real_atomic = round_commit.atomic_write_json

    def _raise_after_landing(path, obj):
        real_atomic(path, obj)
        raise OSError("simulated post-replace fsync failure")

    monkeypatch.setattr(round_commit, "atomic_write_json", _raise_after_landing)

    state = _cli_next_prior_comments(tmp_path, session_dir, prior_path, mode="branch")
    _assert_prior_comments_biconditional(session_dir, state)
    assert state["config"]["priorComments"] == source
    assert os.path.isfile(canonical)


def test_prior_comments_no_stranded_file_on_post_fresh_refusal(tmp_path, monkeypatch):
    # axis: a refusal after the fresh branch begins must not leave a canonical file with no state
    def _refuse_placeholders(*_a, **_k):
        raise ValueError("order-render-refused:probe-seat:probe-reason")

    monkeypatch.setattr(RD, "_order_placeholders", _refuse_placeholders)
    session_dir = _session_with_mode(tmp_path, "branch")
    canonical = _canonical_prior_path(session_dir)
    prior_path = str(tmp_path / "prior.json")
    with open(prior_path, "w", encoding="utf-8") as fh:
        json.dump([{"id": "x"}], fh)

    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude"], "diff": "diff --git a/f b/f\n",
                                    "fixerVendor": "claude", "repoRoot": str(tmp_path),
                                    "priorComments": [{"id": "x"}]})
    assert out["ok"] is False
    assert out["reason"] == "order-render-refused"
    assert not os.path.isfile(canonical)
    ok, state = RD.load_state(session_dir)
    assert ok and state is None
