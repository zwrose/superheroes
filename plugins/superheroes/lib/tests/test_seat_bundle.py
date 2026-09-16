import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, "..", filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SB = _load("seat_bundle", "seat_bundle.py")
MR = _load("model_registry", "model_registry.py")
ED = _load("engine_dispatch", "engine_dispatch.py")
DG = _load("dispatch_guard", "dispatch_guard.py")
EA = _load("engine_adapter", "engine_adapter.py")


def _seat_json(vendor, model, effort):
    return json.dumps({"vendor": vendor, "model": model, "effort": effort})


_REVIEW_ROLE = "reviewer"
_WRITE_ROLE = "implementer"


@pytest.mark.parametrize(
    "cli_module,subcmd,extra",
    [
        (ED, ["dispatch-review"], ["--prompt-path", "p", "--repo-root", "/tmp"]),
        (ED, ["dispatch-write"], ["--prompt-path", "p", "--cwd", "/tmp", "--run-dir", "/tmp/r"]),
        (DG, ["check"], []),
    ],
)
def test_seat_json_and_token_accepted(cli_module, subcmd, extra, tmp_path, monkeypatch):
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

    argv_base = subcmd + [
        "--role", _REVIEW_ROLE if "review" in subcmd[0] else _WRITE_ROLE,
    ]
    if "dispatch-review" in subcmd[0]:
        argv_base += ["--prompt-path", str(prompt), "--repo-root", str(repo), "--run-dir", str(run_dir)]
    elif "dispatch-write" in subcmd[0]:
        argv_base += [
            "--prompt-path", str(prompt), "--cwd", str(wt), "--run-dir", str(run_dir),
        ]
    json_seat = _seat_json("codex", "gpt-5.6-sol", "high")
    token_seat = "cursor:composer-2.5"
    seat_cases = (
        (json_seat, "codex", "gpt-5.6-sol", "high"),
        (token_seat, "cursor", "composer-2.5", None),
    )
    for seat, exp_vendor, exp_model, exp_effort in seat_cases:
        argv = argv_base + ["--seat", seat]
        if cli_module is DG:
            argv = ["check", "--role", _REVIEW_ROLE, "--seat", seat]
        dropped = SB.scan_dropped_flags(argv)
        assert dropped == []
        captured = {}
        if cli_module is ED:
            if "dispatch-review" in subcmd[0]:
                def _fake_review_impl(seat_bundle, *, role, **kwargs):
                    captured["seat"] = seat_bundle
                    captured["role"] = role
                    return {"ok": True, "terminal": True}

                monkeypatch.setattr(cli_module, "_dispatch_review_impl", _fake_review_impl)
            else:
                def _fake_write_impl(seat_bundle, *, role, **kwargs):
                    captured["seat"] = seat_bundle
                    captured["role"] = role
                    return {"ok": True, "terminal": True}

                monkeypatch.setattr(cli_module, "_dispatch_write_impl", _fake_write_impl)
            rc = cli_module.main(argv)
            assert rc == 0
            assert captured["seat"]["vendor"] == exp_vendor
            assert captured["seat"]["model"] == exp_model
            assert captured["seat"]["effort"] == exp_effort
        if cli_module is DG:
            def _fake_validate(role, vendor, model, effort):
                captured.update(
                    role=role, vendor=vendor, model=model, effort=effort,
                )
                return {
                    "ok": True,
                    "role": role,
                    "vendor": vendor,
                    "model_id": model,
                    "effort": effort,
                    "dispatch_token": None,
                    "effort_source": None,
                    "resolved_model": model,
                    "allowlist": [],
                    "allowlist_pairs": [],
                    "reason": None,
                }

            monkeypatch.setattr(cli_module, "validate", _fake_validate)
            rc = cli_module.main(argv)
            assert rc == 0
            assert captured["vendor"] == exp_vendor
            assert captured["model"] == exp_model
            assert captured["effort"] == exp_effort
        parser = cli_module.build_parser()
        if cli_module is ED:
            sub = subcmd[0]
            actions = parser._subparsers._actions[-1].choices[sub]._actions  # noqa: SLF001
        else:
            actions = parser._subparsers._actions[-1].choices["check"]._actions  # noqa: SLF001
        assert any(a.dest == "seat" for a in actions)
        assert any(a.dest == "role" for a in actions)


_DROPPED = ("--engine", "--model", "--effort", "--engine-model", "--vendor")
_CLI_CASES = [
    (ED, "dispatch-review", ["--prompt-path", "p", "--repo-root", "/tmp", "--run-dir", "/tmp/r"]),
    (ED, "dispatch-write", ["--prompt-path", "p", "--cwd", "/tmp", "--run-dir", "/tmp/r"]),
    (DG, "check", []),
]


@pytest.mark.parametrize("flag", _DROPPED)
@pytest.mark.parametrize("spelling", ["value", "equals"])
@pytest.mark.parametrize("cli_module,subcmd,tail", _CLI_CASES)
def test_dropped_flags_refuse_and_name_seat(cli_module, subcmd, tail, flag, spelling):
    seat = _seat_json("codex", "gpt-5.6-sol", "high")
    base = [subcmd, "--role", _REVIEW_ROLE, "--seat", seat] + tail
    if spelling == "value":
        argv = base[:1] + [flag, "codex"] + base[1:]
    else:
        argv = base[:1] + [flag + "=codex"] + base[1:]
    if cli_module is DG:
        argv = ["check", "--role", _REVIEW_ROLE, "--seat", seat, flag, "codex"]
        if spelling == "equals":
            argv = ["check", "--role", _REVIEW_ROLE, "--seat", seat, flag + "=codex"]
    rc = cli_module.main(argv)
    assert rc == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"engine": "codex"},
        {"model": "sonnet"},
        {"effort": "high"},
        {"engine_model": "gpt-5.6-sol"},
        {"engine": "codex", "model": "sonnet", "effort": "high"},
    ],
)
def test_dispatch_review_legacy_library_refusal(kwargs):
    res = ED.dispatch_review("codex", prompt_path="p", **kwargs)
    assert res["ok"] is False
    assert res["reason"] == "legacy-seat-args"
    assert "--seat" in res["detail"]


@pytest.mark.parametrize("kwargs", [{"engine": "cursor"}, {"model": "x", "effort": "high"}])
def test_dispatch_write_legacy_library_refusal(kwargs):
    res = ED.dispatch_write(prompt_path="p", cwd="/tmp", **kwargs)
    assert res["ok"] is False
    assert res["reason"] == "legacy-seat-args"


def test_dispatch_review_unknown_keyword_refused():
    res = ED.dispatch_review(
        seat=_seat_json("codex", "gpt-5.6-sol", "high"),
        role=_REVIEW_ROLE,
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
        seat=_seat_json("codex", "gpt-5.6-sol", "high"),
        role=_WRITE_ROLE,
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
        seat=_seat_json("codex", "gpt-5.6-sol", "high"),
        role=_REVIEW_ROLE,
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
        seat=_seat_json("codex", "gpt-5.6-sol", "high"),
        role=_WRITE_ROLE,
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
        "--role", _REVIEW_ROLE,
        "--prompt-path", "p",
        "--repo-root", "/tmp",
        "--run-dir", "/tmp/r",
    ]
    assert SB.scan_dropped_flags(argv) == ["--vendor"]
    rc = ED.main(argv)
    assert rc == 1


def test_composer_null_effort_accepted():
    bundle = SB.parse(_seat_json("cursor", "composer-2.5", None))
    assert bundle["ok"] is True
    validated = SB.validate(bundle, "implementer")
    assert validated["ok"] is True
    assert validated["effort"] is None
    assert validated["effortSource"] == "declared-none"


def test_composer_high_effort_refused_names_empty_set():
    bundle = SB.parse(_seat_json("cursor", "composer-2.5", "high"))
    validated = SB.validate(bundle, "implementer")
    assert validated["ok"] is False
    assert validated["reason"] == "invalid-model-effort"
    assert "(none)" in validated["detail"]


def test_grok_xhigh_accepted():
    bundle = SB.parse(_seat_json("cursor", "cursor-grok-4.6", "xhigh"))
    validated = SB.validate(bundle, "reviewer-deep")
    assert validated["ok"] is True
    assert validated["effort"] == "xhigh"


def test_codex_effort_accepted():
    bundle = SB.parse(_seat_json("codex", "gpt-5.6-sol", "high"))
    validated = SB.validate(bundle, "reviewer")
    assert validated["ok"] is True


def test_cross_vendor_effort_hint():
    bundle = SB.parse(_seat_json("cursor", "cursor-grok-4.6", "high"))
    validated = SB.validate(bundle, "implementer")
    assert validated["ok"] is False
    assert "codex" in validated["detail"]


def test_effort_key_absent_refused():
    raw = json.dumps({"vendor": "cursor", "model": "composer-2.5"})
    bundle = SB.parse(raw)
    assert bundle["ok"] is False
    assert bundle["reason"] == "effort-key-absent"


def test_unparseable_seat_refused():
    bundle = SB.parse("not-json-or-token")
    assert bundle["ok"] is False
    assert bundle["reason"] == "seat-unparseable"


def test_unknown_role_refused():
    bundle = SB.parse(_seat_json("cursor", "composer-2.5", None))
    validated = SB.validate(bundle, "not-a-role")
    assert validated["ok"] is False
    assert validated["reason"] == "unknown-role"
    assert "implementer" in validated["detail"] or "reviewer" in validated["detail"]


def test_dropped_flag_with_valid_seat_still_refuses():
    argv = [
        "dispatch-review",
        "--engine", "codex",
        "--seat", _seat_json("codex", "gpt-5.6-sol", "high"),
        "--role", _REVIEW_ROLE,
        "--prompt-path", "p",
        "--repo-root", "/tmp",
        "--run-dir", "/tmp/r",
    ]
    assert SB.scan_dropped_flags(argv)
    rc = ED.main(argv)
    assert rc == 1
