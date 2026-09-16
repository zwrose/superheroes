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
def test_four_key_seat_json_accepted(cli_module, subcmd, role, tmp_path, monkeypatch):
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

    captured = {}

    def _sentinel(*_a, **_k):
        return {"ok": False, "reason": "chokepoint-sentinel", "detail": "sentinel"}

    patch_target = SB if cli_module is DG else cli_module.seat_bundle
    monkeypatch.setattr(patch_target, "resolve_entry", _sentinel)
    rc = cli_module.main(argv)
    if cli_module is DG:
        assert rc == 1
    else:
        assert rc == 0

    parser = cli_module.build_parser()
    if cli_module is ED:
        actions = parser._subparsers._actions[-1].choices[subcmd]._actions  # noqa: SLF001
    else:
        actions = parser._subparsers._actions[-1].choices["check"]._actions  # noqa: SLF001
    assert any(a.dest == "seat" for a in actions)
    assert not any(a.dest == "role" for a in actions)


_DROPPED = ("--engine", "--model", "--effort", "--engine-model", "--vendor", "--role")
_CLI_CASES = [
    (ED, "dispatch-review", ["--prompt-path", "p", "--repo-root", "/tmp", "--run-dir", "/tmp/r"]),
    (ED, "dispatch-write", ["--prompt-path", "p", "--cwd", "/tmp", "--run-dir", "/tmp/r"]),
    (DG, "check", []),
]


@pytest.mark.parametrize("flag", _DROPPED)
@pytest.mark.parametrize("spelling", ["value", "equals"])
@pytest.mark.parametrize("cli_module,subcmd,tail", _CLI_CASES)
def test_dropped_flags_refuse_and_name_seat(cli_module, subcmd, tail, flag, spelling):
    seat = _seat_json("codex", "gpt-5.6-sol", "high", _REVIEW_ROLE)
    base = [subcmd, "--seat", seat] + tail
    if spelling == "value":
        argv = base[:1] + [flag, "codex"] + base[1:]
    else:
        argv = base[:1] + [flag + "=codex"] + base[1:]
    if cli_module is DG:
        argv = ["check", "--seat", seat, flag, "codex"]
        if spelling == "equals":
            argv = ["check", "--seat", seat, flag + "=codex"]
    rc = cli_module.main(argv)
    assert rc == 1
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
    assert res["reason"] == "legacy-seat-args"
    assert "--seat" in res["detail"]


@pytest.mark.parametrize("kwargs", [{"engine": "cursor"}, {"model": "x", "effort": "high"}, {"role": "implementer"}])
def test_dispatch_write_legacy_library_refusal(kwargs):
    res = ED.dispatch_write(prompt_path="p", cwd="/tmp", **kwargs)
    assert res["ok"] is False
    assert res["reason"] == "legacy-seat-args"


def test_dispatch_write_legacy_library_refusal_full_terminal_envelope():
    res = ED.dispatch_write(prompt_path="p", cwd="/tmp", engine="cursor")
    assert res["ok"] is False
    assert res["reason"] == "legacy-seat-args"
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
    assert res["reason"] == "unknown-dispatch-kwargs"
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
    assert res["reason"] == "unknown-dispatch-kwargs"
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
    assert res["reason"] == "unrunnable"
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
    assert res["reason"] == "unrunnable"
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
    assert resolved["effortSource"] == "declared-none"


def test_composer_high_effort_refused_names_empty_set():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "composer-2.5", "high", _WRITE_ROLE),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "invalid-model-effort"
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
    assert resolved["reason"] == "effort-key-absent"
    assert "effort" in resolved["detail"]


def test_role_key_absent_refused():
    raw = json.dumps({"vendor": "cursor", "model": "composer-2.5", "effort": None})
    resolved = SB.resolve_entry(raw, verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["reason"] == "role-key-absent"
    assert "role" in resolved["detail"]


def test_role_null_refused():
    raw = json.dumps({"vendor": "cursor", "model": "composer-2.5", "effort": None, "role": None})
    resolved = SB.resolve_entry(raw, verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["reason"] == "role-null"
    assert "role" in resolved["detail"]


def test_unknown_role_refused():
    resolved = SB.resolve_entry(
        _seat_json("cursor", "composer-2.5", None, "not-a-role"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "unknown-role"
    assert "implementer" in resolved["detail"] or "reviewer" in resolved["detail"]


def test_bare_token_seat_refused():
    resolved = SB.resolve_entry("cursor:composer-2.5", verb="guard-check")
    assert resolved["ok"] is False
    assert resolved["reason"] == "seat-token-dropped"
    assert "role" in resolved["detail"]


def test_brief_check_mode_reviewer_seat_refused():
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "xhigh", _REVIEW_ROLE),
        verb="dispatch-review",
        mode="brief-check",
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "mode-role-mismatch"
    assert "brief-check" in resolved["detail"]


def test_semantic_allowlist_verdict_empty_pairs_refused(monkeypatch):
    def _fake_validate(role, vendor, model, effort):
        return {"ok": True, "reason": None, "allowlist": [], "allowlist_pairs": []}

    monkeypatch.setattr(SB.dispatch_allowlist, "validate", _fake_validate)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "allowlist-malformed"
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
    assert resolved["reason"] == "allowlist-malformed"


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
    assert resolved["reason"] == "allowlist-malformed"


def test_allowlist_guard_raise_refused(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("guard exploded")

    monkeypatch.setattr(SB.dispatch_allowlist, "validate", _boom)
    resolved = SB.resolve_entry(
        _seat_json("codex", "gpt-5.6-sol", "high"),
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "allowlist-raised"


def test_dict_seat_without_ok_promotion_refused():
    resolved = SB.resolve_entry(
        {"vendor": "codex", "model": "gpt-5.6-sol", "effort": "high"},
        verb="guard-check",
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "role-key-absent"


def test_chokepoint_invariant_all_paths_use_resolve_entry(monkeypatch, tmp_path):
    sentinel = {"ok": False, "reason": "chokepoint-sentinel", "detail": "sentinel"}

    def _sentinel(*_a, **_k):
        return sentinel

    monkeypatch.setattr(SB, "resolve_entry", _sentinel)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seat = _seat_json("codex", "gpt-5.6-sol", "high")

    review_argv = [
        "dispatch-review", "--seat", seat,
        "--prompt-path", str(prompt), "--repo-root", str(repo), "--run-dir", str(run_dir),
    ]
    assert ED.main(review_argv) == 0

    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /fake\n", encoding="utf-8")
    write_argv = [
        "dispatch-write",
        "--seat", _seat_json("codex", "gpt-5.6-sol", "high", _WRITE_ROLE),
        "--prompt-path", str(prompt), "--cwd", str(wt), "--run-dir", str(run_dir),
    ]
    assert ED.main(write_argv) == 0

    assert DG.main(["check", "--seat", seat]) == 1

    opened = {
        "resolvedInputs": {
            "engine": "codex",
            "model": "gpt-5.6-sol",
            "effort": "high",
            "role": _REVIEW_ROLE,
        },
        "runKind": ED.RUN_KIND_REVIEW,
        "mode": "review",
    }
    verdict = ED._spawn_allowlist_verdict(opened)
    assert verdict["ok"] is False
    assert "sentinel" in verdict["reason"]


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
    assert resolved["effortSource"] == "seat-default"


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
    assert resolved["reason"] == "model-ambiguous"
    assert "gpt-5.6-terra" in resolved["detail"]
    assert "gpt-5.6-sol" in resolved["detail"]


@pytest.mark.parametrize("verb", ["guard-check", "dispatch-write"])
def test_edge5_off_allowlist_model_null_effort_refused_at_allowlist(verb):
    resolved = SB.resolve_entry(
        _seat_json("cursor", "gpt-5.3-codex-high", None, _WRITE_ROLE),
        verb=verb,
    )
    assert resolved["ok"] is False
    assert resolved["reason"] == "allowlist-refused"
    assert "composer-2.5" in resolved["detail"] or "allowlist" in resolved["detail"]


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
    assert resolved["reason"] == "mode-role-mismatch"


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
