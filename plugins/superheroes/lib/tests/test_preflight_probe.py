"""Fake-based units for preflight_probe.py (#472, WO-3). No real gh/codex/network — every probe
call in this file passes an injected `run`, or (for the CLI test) monkeypatches the module-level
probe functions so `main()` never shells out."""
import json
import os
import subprocess
from types import SimpleNamespace

import core_md
import mode_registry as mr
import store_core as sc

import preflight_probe as pp


def _fake_run(returncode, stdout="", stderr=""):
    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return _run


def _raising_run(exc):
    def _run(argv, **kwargs):
        raise exc
    return _run


fake0 = _fake_run(0)
fake1 = _fake_run(1)


# --- probe_command -----------------------------------------------------------------------

def test_probe_command_ok_on_exit_zero():
    result = pp.probe_command("t", ["t"], run=fake0)
    assert result == {"tool": "t", "ok": True, "exit": 0, "detail": ""}


def test_probe_command_not_ok_on_exit_nonzero():
    result = pp.probe_command("t", ["t"], run=fake1)
    assert result["ok"] is False
    assert result["exit"] == 1


def test_probe_command_fail_loud_on_exception():
    result = pp.probe_command("t", ["t"], run=_raising_run(OSError("boom")))
    assert result["ok"] is False
    assert result["exit"] is None
    assert "boom" in result["detail"]


def test_probe_command_never_raises_on_timeout_expired():
    import subprocess
    exc = subprocess.TimeoutExpired(cmd="t", timeout=120)
    result = pp.probe_command("t", ["t"], run=_raising_run(exc))
    assert result["ok"] is False
    assert result["exit"] is None


# --- gh_auth_probe -------------------------------------------------------------------------

def test_gh_auth_probe_ok_true():
    result = pp.gh_auth_probe(run=fake0)
    assert result["ok"] is True
    assert result["tool"] == "gh auth"


def test_gh_auth_probe_ok_false():
    result = pp.gh_auth_probe(run=fake1)
    assert result["ok"] is False
    assert result["tool"] == "gh auth"


# --- cross_vendor_cli_probe / cross_vendor_no_op_argv --------------------------------------

def test_cross_vendor_cli_probe_ok_and_tool_label():
    result = pp.cross_vendor_cli_probe("codex", run=fake0)
    assert result["ok"] is True
    assert result["tool"] == "cross-vendor-cli:codex"


def test_cross_vendor_no_op_argv_codex():
    assert pp.cross_vendor_no_op_argv("codex") == (
        "codex", "exec", "--sandbox", "read-only", "reply with the single word READY")


def test_cross_vendor_no_op_argv_cursor():
    # The cursor probe threads the project's configured cursor model (engine_adapter's SSOT),
    # never a hard-coded id — `cursor-small` was observed unavailable in a live run.
    import engine_adapter
    assert pp.cross_vendor_no_op_argv("cursor") == (
        "cursor-agent", "--model", engine_adapter._CURSOR_MODEL, "-p", "--trust", "reply READY")


def test_cross_vendor_no_op_argv_unknown_engine():
    assert pp.cross_vendor_no_op_argv("mystery") == ("mystery", "--version")


def test_cross_vendor_cli_probe_none_engine_does_not_raise():
    # Fix E: a bad `engine` arg (None, a non-str) must not TypeError building the label/argv
    # before the guarded probe_command runs.
    result = pp.cross_vendor_cli_probe(None, run=fake0)
    assert "ok" in result
    assert result["ok"] is True
    assert result["tool"] == "cross-vendor-cli:None"


def test_cross_vendor_cli_probe_argv_override():
    captured = {}

    def _run(argv, **kwargs):
        captured["argv"] = argv
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    pp.cross_vendor_cli_probe("codex", run=_run, argv=("codex", "--version"))
    assert captured["argv"] == ["codex", "--version"]


# --- browser_probe_result ------------------------------------------------------------------

def test_browser_probe_result_ok():
    assert pp.browser_probe_result(True) == {"tool": "browser", "ok": True, "detail": ""}


def test_browser_probe_result_not_ok_with_detail():
    assert pp.browser_probe_result(False, "no approval") == {
        "tool": "browser", "ok": False, "detail": "no approval"}


# --- aggregate ------------------------------------------------------------------------------

def test_aggregate_all_ok_go_true():
    results = [{"tool": "a", "ok": True}, {"tool": "b", "ok": True}]
    agg = pp.aggregate(results)
    assert agg["go"] is True
    assert agg["blocking"] == []
    assert set(agg["checked"]) == {"a", "b"}
    assert agg["na"] == []


def test_aggregate_required_applicable_failure_blocks():
    results = [{"tool": "a", "ok": True}, {"tool": "b", "ok": False}]
    agg = pp.aggregate(results)
    assert agg["go"] is False
    assert "b" in agg["blocking"]


def test_aggregate_not_applicable_failure_never_blocks():
    results = [{"tool": "a", "ok": False, "applicable": False}]
    agg = pp.aggregate(results)
    assert agg["go"] is True
    assert "a" in agg["na"]
    assert agg["blocking"] == []


def test_aggregate_not_required_failure_does_not_block():
    results = [{"tool": "a", "ok": False, "required": False}]
    agg = pp.aggregate(results)
    assert agg["go"] is True
    assert agg["blocking"] == []


def test_aggregate_empty_results_go_false():
    # Fix B: zero probes at all is never a vacuous "go" — you cannot go on zero checks.
    agg = pp.aggregate([])
    assert agg["go"] is False
    assert agg["blocking"] == ["<no-probes>"]
    agg_none = pp.aggregate(None)
    assert agg_none["go"] is False
    assert agg_none["blocking"] == ["<no-probes>"]


def test_aggregate_non_dict_record_blocks():
    # Fix B: a malformed (non-dict) record is a BLOCKING failure, never silently dropped.
    results = ["not-a-dict", {"tool": "a", "ok": True}]
    agg = pp.aggregate(results)
    assert agg["go"] is False
    assert agg["blocking"] == ["<malformed:0>"]
    assert agg["checked"] == ["a"]


def test_aggregate_dict_missing_ok_blocks():
    # Fix B: a dict missing `ok` is a BLOCKING failure, never silently skipped.
    results = [{"tool": "a"}, {"tool": "b", "ok": True}]
    agg = pp.aggregate(results)
    assert agg["go"] is False
    assert agg["blocking"] == ["<malformed:0>"]
    assert agg["checked"] == ["b"]


def test_aggregate_dict_missing_tool_blocks():
    # Same fail-loud treatment for a dict missing `tool`.
    results = [{"ok": True}]
    agg = pp.aggregate(results)
    assert agg["go"] is False
    assert agg["blocking"] == ["<malformed:0>"]


# --- dispatch_calibration --------------------------------------------------------------------

_TIERS = {"implementer": "sonnet", "pilot": "sonnet", "reviewer": "sonnet",
          "reviewer-deep": "opus"}


def test_dispatch_calibration_default_engines_and_models():
    rows = pp.dispatch_calibration(prefs={}, tiers=_TIERS)
    by_role = {r["role"]: r for r in rows}
    assert by_role["implementer"]["model"] == "sonnet"
    assert by_role["pilot"]["model"] == "sonnet"
    assert by_role["brief-check"]["engine"] == "codex"   # resolve_engine default on empty prefs
    assert "reviewer=sonnet reviewer-deep=opus" in by_role["review-code"]["model"]


def test_dispatch_calibration_brief_check_claude_fallback_model():
    rows = pp.dispatch_calibration(prefs={"briefCheck": "claude"}, tiers=_TIERS)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "claude"
    assert by_role["brief-check"]["model"] == "opus"


def test_dispatch_calibration_never_raises_on_garbage_tiers():
    # Distinguishes coerced-rows from the except-fallthrough (which would return []): garbage
    # tiers coerce to {}, so implementer's model is None via .get() — not an empty list. This
    # kills the mutant where the isinstance-dict tiers coercion is removed.
    rows = pp.dispatch_calibration(prefs={}, tiers="not-a-dict")
    by_role = {r["role"]: r for r in rows}
    assert set(by_role) == {"implementer", "brief-check", "review-code", "pilot"}
    assert by_role["implementer"]["model"] is None


def test_dispatch_calibration_prefs_none_reads_raw_and_defaults_brief_check_to_codex(tmp_path):
    # Regression for the Important fix: the prefs=None PRODUCTION path must read the RAW
    # enginePreferences (via core_md.read), not engine_pref.load_engine_prefs's normalized output
    # (which fills an absent briefCheck -> "claude" and would suppress the codex default). Mirrors
    # the seeding in test_configure_view.py::_seed_core_and_layer.
    repo = str(tmp_path)
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    root = str(tmp_path / "store")
    mr.write_registry(repo, mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": ""},
                                        "confirmed", "2026-07-19", "2026-07-19"))

    rows = pp.dispatch_calibration(cwd=repo, root=root)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "codex"


# --- configured_cross_vendor_engines -------------------------------------------------------

def test_configured_cross_vendor_engines_default_is_codex_only():
    # brief-check fails open to codex by default (the ratified cross-vendor pre-code check), so
    # an all-default project ({}) is NOT all-Claude — it derives ["codex"].
    assert pp.configured_cross_vendor_engines({}) == ["codex"]


def test_configured_cross_vendor_engines_all_claude_when_brief_check_explicit():
    # All-Claude only when brief-check is EXPLICITLY claude and no other role is external.
    assert pp.configured_cross_vendor_engines({"briefCheck": "claude"}) == []


def test_configured_cross_vendor_engines_cursor_implementer_only():
    assert pp.configured_cross_vendor_engines(
        {"implementation": "cursor", "briefCheck": "claude"}) == ["cursor"]


def test_configured_cross_vendor_engines_mixed_codex_and_cursor():
    # brief-check still defaults to codex alongside an explicit cursor implementer.
    assert pp.configured_cross_vendor_engines({"implementation": "cursor"}) == ["codex", "cursor"]


def test_configured_cross_vendor_engines_tolerant_of_non_dict():
    assert pp.configured_cross_vendor_engines("not-a-dict") == ["codex"]
    assert pp.configured_cross_vendor_engines(None) == ["codex"]


# --- CLI --------------------------------------------------------------------------------------

def test_cli_run_prints_json_with_expected_keys(monkeypatch, capsys):
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})

    rc = pp.main(["preflight_probe.py", "run", "--engine", "codex"])

    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert set(payload.keys()) == {
        "probes", "dispatchCalibration", "aggregate", "browserNote", "crossVendorEngines"}
    assert payload["aggregate"]["go"] is True
    assert len(payload["probes"]) == 2
    assert payload["crossVendorEngines"] == ["codex"]


def test_cli_run_without_engine_derives_configured_engines(tmp_path, monkeypatch, capsys):
    # Fix C: when --engine is omitted, the CLI derives every configured non-Claude engine from
    # the project's RAW enginePreferences and probes each — not a hard-coded codex.
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp.core_md, "read", lambda *a, **k: {
        "enginePreferences": {"implementation": "cursor", "briefCheck": "claude"}})

    rc = pp.main(["preflight_probe.py", "run", "--cwd", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["crossVendorEngines"] == ["cursor"]
    tools = {p["tool"] for p in payload["probes"]}
    assert tools == {"gh auth", "cross-vendor-cli:cursor"}


def test_cli_run_without_engine_all_claude_probes_none(monkeypatch, capsys):
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp.core_md, "read", lambda *a, **k: {
        "enginePreferences": {"briefCheck": "claude"}})

    rc = pp.main(["preflight_probe.py", "run"])

    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["crossVendorEngines"] == []
    assert len(payload["probes"]) == 1   # gh auth only — no cross-vendor probe when all-Claude


# --- composition preflight (#510 WO-3) -------------------------------------------------------

def test_model_no_op_argv_cursor_grok_dispatch_token():
    argv = pp.model_no_op_argv("cursor", "cursor-grok-4.5", "high")
    assert argv == (
        "cursor-agent", "--model", "cursor-grok-4.5-high", "-p", "--trust", "reply READY")


def test_model_no_op_argv_cursor_bogus_model_returns_none():
    assert pp.model_no_op_argv("cursor", "bogus-model", "high") is None


def test_model_no_op_argv_codex_includes_model_flag():
    assert pp.model_no_op_argv("codex", "gpt-5.6-sol") == (
        "codex", "exec", "--sandbox", "read-only", "-m", "gpt-5.6-sol",
        "reply with the single word READY")


def test_model_no_op_argv_codex_bogus_model_returns_none():
    assert pp.model_no_op_argv("codex", "gpt-9-bogus") is None


def test_needed_configs_for_review_tiers_omits_claude():
    configs = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex", "cursor"])
    assert "claude" not in configs
    assert configs["codex"] == [("gpt-5.6-sol", "xhigh"), ("gpt-5.6-terra", "high")]
    assert configs["cursor"] == [("cursor-grok-4.5", "high")]


def test_composition_liveness_cursor_both_models_ok_is_live():
    calls = []

    def _run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed = {"cursor": [("composer-2.5", None), ("cursor-grok-4.5", "high")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["cursor"]["live"] is True
    assert all(m["ok"] for m in result["cursor"]["models"].values())
    assert len(calls) == 2


def test_composition_liveness_cursor_grok_fails_not_live():
    def _run(argv, **kwargs):
        model_flag = argv[argv.index("--model") + 1] if "--model" in argv else ""
        if "grok" in model_flag:
            return SimpleNamespace(returncode=1, stdout="", stderr="grok unavailable")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed = {"cursor": [("composer-2.5", None), ("cursor-grok-4.5", "high")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["cursor"]["live"] is False
    assert result["cursor"]["models"]["composer-2.5"]["ok"] is True
    assert result["cursor"]["models"]["cursor-grok-4.5"]["ok"] is False


def test_composition_liveness_codex_both_ok_is_live():
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    result = pp.composition_liveness(needed, run=fake0)
    assert result["codex"]["live"] is True


def test_composition_liveness_codex_one_fails_not_live():
    def _run(argv, **kwargs):
        model = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if model == "gpt-5.6-sol":
            return SimpleNamespace(returncode=1, stdout="", stderr="fail")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    result = pp.composition_liveness(needed, run=_run)
    assert result["codex"]["live"] is False
    assert result["codex"]["models"]["gpt-5.6-sol"]["ok"] is False
    assert result["codex"]["models"]["gpt-5.6-terra"]["ok"] is True


def test_composition_liveness_claude_always_live():
    result = pp.composition_liveness({"claude": []}, run=fake1)
    assert result["claude"] == {"live": True, "models": {}}


def test_composition_liveness_probe_exception_not_live():
    needed = {"codex": [("gpt-5.6-terra", "high")]}
    result = pp.composition_liveness(needed, run=_raising_run(OSError("boom")))
    assert result["codex"]["live"] is False
    assert result["codex"]["models"]["gpt-5.6-terra"]["ok"] is False
    assert "boom" in result["codex"]["models"]["gpt-5.6-terra"]["detail"]


def test_composition_liveness_unknown_cursor_model_not_live_without_run():
    calls = []

    def _run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    needed = {"cursor": [("bogus-model", "high")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["cursor"]["live"] is False
    assert result["cursor"]["models"]["bogus-model"]["ok"] is False
    assert result["cursor"]["models"]["bogus-model"]["detail"] == "unknown/unroutable model"
    assert calls == []


def test_composition_liveness_unknown_codex_model_not_live_without_run():
    calls = []

    def _run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    needed = {"codex": [("gpt-5.6-terra", "high"), ("gpt-9-bogus", "xhigh")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["codex"]["live"] is False
    assert result["codex"]["models"]["gpt-5.6-terra"]["ok"] is True
    assert result["codex"]["models"]["gpt-9-bogus"]["ok"] is False
    assert result["codex"]["models"]["gpt-9-bogus"]["detail"] == "unknown/unroutable model"
    assert len(calls) == 1


def test_composition_liveness_empty_config_list_not_live():
    result = pp.composition_liveness({"codex": []}, run=fake0)
    assert result["codex"]["live"] is False


def test_composition_liveness_non_dict_returns_empty():
    assert pp.composition_liveness(None) == {}
    assert pp.composition_liveness("not-a-dict") == {}


def test_live_vendors_for_composition_claude_always_in_live_list():
    live, liveness, _notes = pp.live_vendors_for_composition(["codex", "cursor"], run=fake1)
    assert "claude" in live
    assert liveness["claude"]["live"] is True


def test_live_vendors_for_composition_all_ok_includes_external():
    live, _, _ = pp.live_vendors_for_composition(["codex", "cursor"], run=fake0)
    assert live == ["claude", "codex", "cursor"]


def test_live_vendors_for_composition_external_failure_excludes_vendor():
    live, _, _ = pp.live_vendors_for_composition(["codex", "cursor"], run=fake1)
    assert live == ["claude"]


def test_live_vendors_for_composition_returns_three_tuple():
    result = pp.live_vendors_for_composition(["codex"], run=fake0)
    assert len(result) == 3


def test_live_vendors_for_composition_cache_hit_skips_probe(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    liveness = {
        "codex": {
            "live": True,
            "models": {
                m: {"ok": True, "detail": ""}
                for m, _ in needed["codex"]
            },
        },
        "claude": {"live": True, "models": {}},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0
    assert liveness_cache.write(liveness, needed, path=cache_path, now=now)

    def _boom(argv, **kwargs):
        raise AssertionError("run must not be called on cache hit")

    live, _liv, notes = pp.live_vendors_for_composition(
        ["codex"],
        run=_boom,
        cache_path=cache_path,
        now=now + 1,
    )
    assert "codex" in live
    assert any(n.get("constraint") == "preflight-cache" for n in notes)


def test_live_vendors_for_composition_cache_miss_stale_probes_and_writes(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    cache_path = str(tmp_path / "composition-liveness.json")
    old_liveness = {
        "codex": {
            "live": True,
            "models": {
                m: {"ok": True, "detail": ""}
                for m, _ in needed["codex"]
            },
        },
        "claude": {"live": True, "models": {}},
    }
    needed_for_write = {v: [[m, e] for m, e in entries] for v, entries in needed.items()}
    liveness_cache.write(old_liveness, needed_for_write, path=cache_path, now=100.0)

    calls = []

    def _run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    now = 1000.0
    live, _liv, _notes = pp.live_vendors_for_composition(
        ["codex"],
        run=_run,
        cache_path=cache_path,
        now=now,
    )
    assert calls
    assert "codex" in live
    rec = liveness_cache.read(cache_path, now=now)
    assert rec is not None


def test_live_vendors_for_composition_cache_only_miss_no_probe():
    def _boom(argv, **kwargs):
        raise AssertionError("run must not be called in cache-only miss")

    live, _liv, notes = pp.live_vendors_for_composition(
        ["codex", "cursor"],
        run=_boom,
        probe_mode="cache-only",
        cache_path="/nonexistent/path.json",
        now=1000.0,
    )
    assert live == ["claude"]
    assert any(n.get("constraint") == "preflight-cache-only" for n in notes)


def test_live_vendors_for_composition_cache_only_hit_reuses(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    liveness = {
        "codex": {
            "live": True,
            "models": {m: {"ok": True, "detail": ""} for m, _ in needed["codex"]},
        },
        "claude": {"live": True, "models": {}},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 2000.0
    liveness_cache.write(liveness, needed, path=cache_path, now=now)

    def _boom(argv, **kwargs):
        raise AssertionError("run must not be called on cache-only hit")

    live, _liv, notes = pp.live_vendors_for_composition(
        ["codex"],
        run=_boom,
        probe_mode="cache-only",
        cache_path=cache_path,
        now=now + 5,
    )
    assert "codex" in live
    assert any(n.get("constraint") == "preflight-cache" for n in notes)


def test_live_vendors_for_composition_cache_write_failure_disclosed(tmp_path):
    import liveness_cache

    blocker = tmp_path / "not-a-dir"
    blocker.write_text("blocks mkdir")
    cache_path = str(blocker / "composition-liveness.json")
    live, _liv, notes = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=cache_path,
        now=1000.0,
    )
    assert "codex" in live
    assert any(n.get("constraint") == "preflight-cache-write-failed" for n in notes)


def test_cli_compose_liveness_writes_receipt(tmp_path, monkeypatch, capsys):
    import liveness_cache

    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None: {
        "codex": {"live": True, "models": {}},
        "claude": {"live": True, "models": {}},
    })
    monkeypatch.setattr(pp.core_md, "read", lambda *a, **k: {"enginePreferences": {}})

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", str(tmp_path)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "live" in payload
    assert "cachePath" in payload
    assert payload["cachePath"] == str(cache_file)
    assert cache_file.is_file()
