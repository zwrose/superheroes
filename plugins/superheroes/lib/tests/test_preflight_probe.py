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
    assert pp.cross_vendor_no_op_argv("cursor") == (
        "cursor-agent", "--model", "cursor-small", "-p", "--trust", "reply READY")


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
