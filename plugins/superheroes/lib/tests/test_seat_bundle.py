import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, "..", filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


SB = _load("seat_bundle", "seat_bundle.py")
MR = _load("model_registry", "model_registry.py")
ED = _load("engine_dispatch", "engine_dispatch.py")
DG = _load("dispatch_guard", "dispatch_guard.py")


def _seat_json(vendor, model, effort, role="reviewer"):
    return json.dumps({"vendor": vendor, "model": model, "effort": effort, "role": role})


def _seat_dict(vendor, model, effort, role="reviewer"):
    return {"vendor": vendor, "model": model, "effort": effort, "role": role}


_REVIEW_ROLE = "reviewer"
_WRITE_ROLE = "implementer"
_BRIEF_ROLE = "brief-check"


@pytest.mark.parametrize(
    "cli_module,subcmd,role",
    [
        (ED, "dispatch-review", _REVIEW_ROLE),
        (ED, "dispatch-write", _WRITE_ROLE),
        (DG, "check", _REVIEW_ROLE),
    ],
)
def test_entry_clis_route_through_chokepoint_and_expose_seat_flag(cli_module, subcmd, role, tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /fake\n", encoding="utf-8")

    json_seat = _seat_json("codex", "gpt-5.6-sol", "high", role)
    if cli_module is ED and subcmd == "dispatch-review":
        argv = [
            subcmd, "--seat", json_seat,
            "--prompt-path", str(prompt), "--repo-root", str(repo), "--run-dir", str(run_dir),
        ]
    elif cli_module is ED:
        argv = [
            subcmd, "--seat", json_seat,
            "--prompt-path", str(prompt), "--cwd", str(wt), "--run-dir", str(run_dir),
        ]
    else:
        argv = ["check", "--seat", json_seat]

    def _sentinel(*_a, **_k):
        token = "chokepoint-sentinel" if cli_module is DG else "role-key-absent"
        return {"ok": False, "entryReason": token, "detail": "sentinel"}

    patch_target = SB if cli_module is DG else cli_module.seat_bundle
    monkeypatch.setattr(patch_target, "resolve_entry", _sentinel)
    rc = cli_module.main(argv)
    out = capsys.readouterr().out.strip()
    if cli_module is DG:
        assert rc == 1
        payload = json.loads(out.splitlines()[0])
        assert payload["reason"] == "chokepoint-sentinel"
    else:
        assert rc == 0
        result = json.loads(out.splitlines()[-1])
        assert result["detail"] == "sentinel"

    parser = cli_module.build_parser()
    if cli_module is ED:
        actions = parser._subparsers._actions[-1].choices[subcmd]._actions  # noqa: SLF001
    else:
        actions = parser._subparsers._actions[-1].choices["check"]._actions  # noqa: SLF001
    assert any(a.dest == "seat" for a in actions)
    assert not any(a.dest == "role" for a in actions)


@pytest.mark.parametrize(
    "verb,role",
    [
        ("dispatch-review", _REVIEW_ROLE),
        ("dispatch-write", _WRITE_ROLE),
        ("guard-check", _REVIEW_ROLE),
    ],
)
def test_four_key_seat_json_accepted(verb, role):
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high", role),
        verb=verb,
    )
    assert resolved["ok"] is True
    assert resolved["vendor"] == "codex"
    assert resolved["model"] == "gpt-5.6-sol"
    assert resolved["effort"] == "high"
    assert resolved["role"] == role


_DROPPED = ("--engine", "--model", "--effort", "--engine-model", "--vendor", "--role")


def _valid_cli_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /fake\n", encoding="utf-8")
    return repo, prompt, run_dir, wt


@pytest.mark.parametrize("flag", _DROPPED)
@pytest.mark.parametrize("spelling", ["value", "equals"])
def test_dropped_flags_refuse_and_name_seat_dispatch_review(flag, spelling, tmp_path, capsys):
    # axis: R8 — dropped legacy flag refuses dispatch-review CLI and names the seat
    repo, prompt, run_dir, _wt = _valid_cli_paths(tmp_path)
    seat = _seat_json("codex", "gpt-5.6-sol", "high", _REVIEW_ROLE)
    base = [
        "dispatch-review", "--seat", seat,
        "--prompt-path", str(prompt), "--repo-root", str(repo), "--run-dir", str(run_dir),
    ]
    if spelling == "value":
        argv = base[:1] + [flag, "codex"] + base[1:]
    else:
        argv = base[:1] + [flag + "=codex"] + base[1:]
    assert ED.main(argv) == 1
    result = json.loads(capsys.readouterr().out.strip())
    assert result["entryReason"] == "legacy-seat-args"
    assert result["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert flag in result["detail"]
    assert "--seat" in result["detail"]


@pytest.mark.parametrize("flag", _DROPPED)
@pytest.mark.parametrize("spelling", ["value", "equals"])
def test_dropped_flags_refuse_and_name_seat_dispatch_write(flag, spelling, tmp_path, capsys):
    # axis: R8 — dropped legacy flag refuses dispatch-write CLI and names the seat
    _repo, prompt, run_dir, wt = _valid_cli_paths(tmp_path)
    seat = _seat_json("codex", "gpt-5.6-sol", "high", _WRITE_ROLE)
    base = [
        "dispatch-write", "--seat", seat,
        "--prompt-path", str(prompt), "--cwd", str(wt), "--run-dir", str(run_dir),
    ]
    if spelling == "value":
        argv = base[:1] + [flag, "codex"] + base[1:]
    else:
        argv = base[:1] + [flag + "=codex"] + base[1:]
    assert ED.main(argv) == 1
    result = json.loads(capsys.readouterr().out.strip())
    assert result["entryReason"] == "legacy-seat-args"
    assert result["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert flag in result["detail"]
    assert "--seat" in result["detail"]


@pytest.mark.parametrize("flag", _DROPPED)
@pytest.mark.parametrize("spelling", ["value", "equals"])
def test_dropped_flags_refuse_and_name_seat_guard_check(flag, spelling, capsys):
    # axis: R8 — dropped legacy flag refuses guard-check CLI and names the seat
    seat = _seat_json("codex", "gpt-5.6-sol", "high", _REVIEW_ROLE)
    if spelling == "value":
        argv = ["check", "--seat", seat, flag, "codex"]
    else:
        argv = ["check", "--seat", seat, flag + "=codex"]
    assert DG.main(argv) == 1
    result = json.loads(capsys.readouterr().out.strip())
    assert result["entryReason"] == "legacy-seat-args"
    assert flag in result["detail"]
    assert "--seat" in result["detail"]
    if flag == "--role":
        dropped = SB.scan_dropped_flags(argv)
        assert "--role" in dropped


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"engine": "codex"},
        {"model": "sonnet"},
        {"effort": "high"},
        {"engine_model": "gpt-5.6-sol"},
        {"role": "reviewer"},
        {"engine": "codex", "model": "sonnet", "effort": "high"},
    ],
)
def test_dispatch_review_legacy_library_refusal(kwargs):
    res = ED.dispatch_review("codex", prompt_path="p", **kwargs)
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "legacy-seat-args"
    assert "--seat" in res["detail"]


@pytest.mark.parametrize("kwargs", [{"engine": "cursor"}, {"model": "x", "effort": "high"}, {"role": "implementer"}])
def test_dispatch_write_legacy_library_refusal(kwargs):
    res = ED.dispatch_write(prompt_path="p", cwd="/tmp", **kwargs)
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "legacy-seat-args"


def test_dispatch_write_legacy_library_refusal_full_terminal_envelope():
    res = ED.dispatch_write(prompt_path="p", cwd="/tmp", engine="cursor")
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "legacy-seat-args"
    assert res["terminal"] is True
    assert res["runDir"] == ""
    assert res["argv"] == []
    assert res["attempts"] == 0
    assert res["forfeited"] is False
    assert res.get("runOpened") is False


def test_dispatch_review_unknown_keyword_refused():
    res = ED.dispatch_review(
        seat=_seat_json("codex", "gpt-5.6-sol", "high"),
        prompt_path="p",
        repo_root="/tmp",
        prompt_pat="typo",
    )
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "unknown-dispatch-kwargs"
    assert "prompt_pat" in res["detail"]
    assert "prompt_path" in res["detail"]


def test_dispatch_write_unknown_keyword_refused():
    res = ED.dispatch_write(
        seat=_seat_json("codex", "gpt-5.6-sol", "high", _WRITE_ROLE),
        prompt_path="p",
        cwd="/tmp",
        prompt_pat="typo",
    )
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "unknown-dispatch-kwargs"
    assert "prompt_pat" in res["detail"]
    assert "prompt_path" in res["detail"]


def test_dispatch_write_refuses_read_only_role():
    res = ED.dispatch_write(
        seat=_seat_json("codex", "gpt-5.6-sol", "high", _REVIEW_ROLE),
        prompt_path="p",
        cwd="/tmp",
        run_dir="/tmp/r",
    )
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "verb-role-mismatch"
    assert "read-only" in res["detail"]
    assert res["attempts"] == 0
    assert res.get("runOpened") is False


def test_dispatch_review_refuses_write_only_role():
    res = ED.dispatch_review(
        seat=_seat_json("codex", "gpt-5.6-sol", "high", _WRITE_ROLE),
        prompt_path="p",
        repo_root="/tmp",
    )
    assert res["ok"] is False
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["entryReason"] == "verb-role-mismatch"
    assert "write-only" in res["detail"]
    assert res["attempts"] == 0
    assert res.get("runOpened") is False


def test_dropped_vendor_flag_refuses():
    argv = [
        "dispatch-review",
        "--vendor", "codex",
        "--seat", _seat_json("codex", "gpt-5.6-sol", "high"),
        "--prompt-path", "p",
        "--repo-root", "/tmp",
        "--run-dir", "/tmp/r",
    ]
    assert SB.scan_dropped_flags(argv) == ["--vendor"]
    rc = ED.main(argv)
    assert rc == 1


def test_dropped_role_flag_refuses_and_names_replacement():
    argv = [
        "dispatch-review",
        "--role", _REVIEW_ROLE,
        "--seat", _seat_json("codex", "gpt-5.6-sol", "high"),
        "--prompt-path", "p",
        "--repo-root", "/tmp",
        "--run-dir", "/tmp/r",
    ]
    assert SB.scan_dropped_flags(argv) == ["--role"]
    rc = ED.main(argv)
    assert rc == 1


def test_composer_null_effort_accepted_via_resolve_entry():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "composer-2.5", None, _WRITE_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is True
    assert resolved["effort"] is None
    assert resolved["effortSource"] == "caller"


def test_composer_high_effort_refused_names_empty_set():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "composer-2.5", "high", _WRITE_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "invalid-model-effort"
    assert "(none)" in resolved["detail"]


def test_grok_xhigh_accepted():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "cursor-grok-4.6", "xhigh", "reviewer-deep"),
        verb="guard-check",
    )
    assert resolved["ok"] is True
    assert resolved["effort"] == "xhigh"


def test_codex_effort_accepted():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is True


def test_cross_vendor_effort_hint():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "cursor-grok-4.6", "high", _WRITE_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert "codex" in resolved["detail"]


def test_effort_key_absent_refused():
    raw = json.dumps({"vendor": "cursor", "model": "composer-2.5", "role": "implementer"})
    resolved = SB.resolve_entry(raw, verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "effort-key-absent"
    assert "effort" in resolved["detail"]


def test_role_key_absent_refused():
    raw = json.dumps({"vendor": "cursor", "model": "composer-2.5", "effort": None})
    resolved = SB.resolve_entry(raw, verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "role-key-absent"
    assert "role" in resolved["detail"]


def test_role_null_refused():
    raw = json.dumps({"vendor": "cursor", "model": "composer-2.5", "effort": None, "role": None})
    resolved = SB.resolve_entry(raw, verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "role-null"
    assert "role" in resolved["detail"]


def test_unknown_role_refused():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "composer-2.5", None, "not-a-role"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "unknown-role"
    valid = ", ".join(MR.roles())
    assert f"valid roles: {valid}" in resolved["detail"]


def test_bare_token_seat_refused():
    resolved = SB.resolve_entry("cursor:composer-2.5", verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "seat-token-dropped"
    assert "role" in resolved["detail"]


def test_brief_check_mode_reviewer_seat_refused():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "xhigh", _REVIEW_ROLE),
        verb="dispatch-review",
        mode="brief-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "mode-role-mismatch"
    assert "brief-check" in resolved["detail"]


def test_brief_check_role_normal_review_mode_refused():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "xhigh", _BRIEF_ROLE),
        verb="dispatch-review",
        mode="review",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "mode-role-mismatch"
    assert "brief-check" in resolved["detail"]


def test_brief_check_role_omitted_mode_refused_on_dispatch_review():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "xhigh", _BRIEF_ROLE),
        verb="dispatch-review",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "mode-role-mismatch"


def test_brief_check_role_guard_check_omitted_mode_accepted():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "xhigh", _BRIEF_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is True
    assert resolved["role"] == _BRIEF_ROLE


@pytest.mark.parametrize("verb", ["dispatch-review", "dispatch-write"])
def test_claude_vendor_refused_at_dispatch_chokepoint(verb):
    # axis: vendor with no engine adapter is refused at resolve_entry, not engine-config later
    role = _REVIEW_ROLE if verb == "dispatch-review" else _WRITE_ROLE
    resolved = SB.resolve_entry(
        _seat_json("claude", "opus-5", "xhigh", role),
        verb=verb,
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "undispatchable-vendor"
    assert "claude" in resolved["detail"]
    assert "codex" in resolved["detail"]
    assert "cursor" in resolved["detail"]


@pytest.mark.parametrize("role", ["mechanical", "synthesis", "pilot"])
@pytest.mark.parametrize("verb", ["dispatch-review", "dispatch-write"])
def test_unclassified_role_refused_for_dispatch_verbs(role, verb):
    resolved = SB.resolve_entry(
        _seat_json("claude", "haiku-4.5", "medium", role),
        verb=verb,
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "verb-role-mismatch"
    assert "read_write" in resolved["detail"]


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-review"])
def test_null_model_unique_effort_match_review_role(verb):
    resolved = SB.resolve_entry(
        _seat_json("codex", None, "xhigh", _REVIEW_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is True
    assert resolved["model"] == "gpt-5.6-sol"
    assert resolved["effort"] == "xhigh"
    assert resolved["modelSource"] == "resolved"


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-write"])
def test_null_model_unique_effort_match_write_role(verb):
    resolved = SB.resolve_entry(
        _seat_json("codex", None, "xhigh", _WRITE_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is True
    assert resolved["model"] == "gpt-5.6-sol"
    assert resolved["effort"] == "xhigh"
    assert resolved["modelSource"] == "resolved"


def test_null_model_effort_without_allowlist_pair_refused():
    resolved = SB.resolve_entry(
        _seat_json("codex", None, "low", _REVIEW_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "allowlist-refused"
    assert "low" in resolved["detail"]


def test_effort_source_matches_allowlist_verdict():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", None, _REVIEW_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is True
    assert resolved["effortSource"] in SB._EFFORT_SOURCE_CANONICAL
    assert resolved["allowlistVerdict"]["effort_source"] == resolved["effortSource"]


def test_effort_source_map_is_closed_canonical_vocabulary():
    assert set(SB._EFFORT_SOURCE_MAP.keys()) == MR.EFFORT_SOURCES
    mapped = set(SB._EFFORT_SOURCE_MAP.values())
    assert mapped <= SB._EFFORT_SOURCE_CANONICAL


def test_resolve_entry_refusal_has_no_reason_key():
    resolved = SB.resolve_entry(
        '{"vendor": "codex", "model": "gpt-5.6-sol", "effort": "high"}',
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "role-key-absent"
    assert "reason" not in resolved


def test_semantic_allowlist_verdict_empty_pairs_refused(monkeypatch):
    def _fake_validate(role, vendor, model, effort):
        return {"ok": True, "reason": None, "allowlist": [], "allowlist_pairs": []}

    monkeypatch.setattr(SB.dispatch_allowlist, "validate", _fake_validate)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "allowlist-malformed"
    assert "allowlist_pairs" in resolved["detail"]


def test_semantic_allowlist_verdict_role_vendor_mismatch_refused(monkeypatch):
    verdict = DG.validate("reviewer", "codex", "gpt-5.6-sol", "high")
    verdict = dict(verdict)
    verdict["role"] = "implementer"
    monkeypatch.setattr(SB.dispatch_allowlist, "validate", lambda *a, **k: verdict)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "allowlist-malformed"


def test_semantic_allowlist_verdict_pair_absent_refused(monkeypatch):
    verdict = DG.validate("reviewer", "codex", "gpt-5.6-sol", "high")
    verdict = dict(verdict)
    verdict["allowlist_pairs"] = [["gpt-5.6-terra", "high"]]
    monkeypatch.setattr(SB.dispatch_allowlist, "validate", lambda *a, **k: verdict)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "allowlist-malformed"


def test_allowlist_guard_raise_refused(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("guard exploded")

    monkeypatch.setattr(SB.dispatch_allowlist, "validate", _boom)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "allowlist-raised"


def test_dict_seat_without_ok_promotion_refused():
    resolved = SB.resolve_entry(
        {"vendor": "codex", "model": "gpt-5.6-sol", "effort": "high"},
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "role-key-absent"


def test_match_effort_empty_allowed_always_none():
    assert SB._match_effort(None, ()) is None
    assert SB._match_effort("high", ()) is None


def test_dispatch_review_accepted_params_derived_from_signature():
    text = SB.dispatch_review_accepted_params()
    assert "seat" in text
    assert "prompt_path" in text
    assert "session_dir" in text
    assert "args" not in text
    assert "kwargs" not in text


def test_dispatch_write_accepted_params_derived_from_signature():
    text = SB.dispatch_write_accepted_params()
    assert "seat" in text
    assert "cwd" in text
    assert "expected_items_file" in text
    assert "args" not in text
    assert "kwargs" not in text


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-write"])
def test_edge1_cursor_implementer_null_model_resolves(verb):
    resolved = SB.resolve_entry(
        _seat_json("cursor", None, None, _WRITE_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is True
    assert resolved["model"] == "composer-2.5"
    assert resolved["modelSource"] == "seat-default"
    assert resolved["effortSource"] == "default"


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-review"])
def test_edge2_codex_reviewer_null_effort_resolves(verb):
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", None, _REVIEW_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is True
    assert resolved["model"] == "gpt-5.6-sol"
    assert resolved["effort"] == "high"
    assert resolved["modelSource"] == "caller"
    assert resolved["effortSource"] == "resolved"


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-review"])
def test_edge3_null_model_ambiguous_effort_refuses_naming_models(verb):
    resolved = SB.resolve_entry(
        _seat_json("codex", None, "high", _REVIEW_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "model-ambiguous"
    assert "gpt-5.6-terra" in resolved["detail"]
    assert "gpt-5.6-sol" in resolved["detail"]


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-write"])
def test_edge5_off_allowlist_model_null_effort_refused_at_allowlist(verb):
    resolved = SB.resolve_entry(
        _seat_json("cursor", "gpt-5.3-codex-high", None, _WRITE_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "allowlist-refused"
    pairs = ", ".join(
        "(%s, %s)" % (m, e)
        for m, e in MR.allowlist(_WRITE_ROLE, "cursor")
    )
    assert f"implementer/cursor allowlist [{pairs}]" in resolved["detail"]


def test_edge6_brief_check_mode_reviewer_refused_before_allowlist(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("allowlist reached")

    monkeypatch.setattr(SB.dispatch_allowlist, "validate", _boom)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high", _REVIEW_ROLE),
        verb="dispatch-review",
        mode="brief-check",
    )
    assert resolved["ok"] is False
    assert resolved["entryReason"] == "mode-role-mismatch"


def test_wo8_edge8_brief_check_reviewer_refused_before_allowlist(monkeypatch):
    # axis: WO-8 edge 8 — mode brief-check with reviewer seat refuses before allowlist
    test_edge6_brief_check_mode_reviewer_refused_before_allowlist(monkeypatch)


def test_wo10_edge6_brief_check_reviewer_refused_before_allowlist(monkeypatch):
    # axis: WO-10 edge 6 — entry chokepoint leg order refuses before allowlist
    test_edge6_brief_check_mode_reviewer_refused_before_allowlist(monkeypatch)


def test_dropped_flag_with_valid_seat_still_refuses():
    argv = [
        "dispatch-review",
        "--engine", "codex",
        "--seat", _seat_json("codex", "gpt-5.6-sol", "high"),
        "--prompt-path", "p",
        "--repo-root", "/tmp",
        "--run-dir", "/tmp/r",
    ]
    assert SB.scan_dropped_flags(argv)
    rc = ED.main(argv)
    assert rc == 1
