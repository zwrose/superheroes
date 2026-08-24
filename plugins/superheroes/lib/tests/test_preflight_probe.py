"""Fake-based units for preflight_probe.py (#472, WO-3). No real gh/codex/network — every probe
call in this file passes an injected `run`, or (for the CLI test) monkeypatches the module-level
probe functions so `main()` never shells out."""
import json
import os
import re
import subprocess
from types import SimpleNamespace

import pytest

import core_md
import mode_registry as mr
import store_core as sc

import preflight_probe as pp


def _assert_read_error_payload_shape(read_error, *, reason_prefix):
    """Payload readErrors carry the reason token and never leak absolute paths."""
    assert read_error is not None
    assert read_error.startswith(reason_prefix)
    if ": " not in read_error:
        return
    detail = read_error.split(": ", 1)[1]
    for token in re.findall(r"\S+", detail):
        cleaned = token.rstrip(".,;)")
        assert not os.path.isabs(cleaned), (
            "absolute path leaked in readError payload: %r in %r" % (cleaned, read_error))


def test_redact_read_error_payload_line_strips_git_stderr_and_relativizes_paths(tmp_path):
    repo = str(tmp_path)
    abs_core = os.path.join(repo, ".claude", "superheroes", "core.md")
    raw = "repo-root-unavailable: git could not be run at %s: fatal: not a git repo" % repo
    redacted = pp._redact_read_error_payload_line(raw, cwd=repo)
    assert redacted.startswith("repo-root-unavailable: git could not be run at ")
    assert "fatal:" not in redacted
    _assert_read_error_payload_shape(redacted, reason_prefix="repo-root-unavailable: ")

    raw_core = "core-md-unreadable: dangling symlink at %s" % abs_core
    redacted_core = pp._redact_read_error_payload_line(raw_core, cwd=repo)
    assert redacted_core == "core-md-unreadable: dangling symlink at .claude/superheroes/core.md"


def test_config_read_payload_redacts_read_error(tmp_path):
    repo = str(tmp_path)
    abs_core = os.path.join(repo, ".claude", "superheroes", "core.md")
    snap = {
        "status": core_md.CONFIG_UNREADABLE,
        "reason": core_md.GATE_REASON_UNREADABLE,
        "readError": "core-md-unreadable: dangling symlink at %s" % abs_core,
    }
    payload = pp.config_read_payload(snap, cwd=repo)
    _assert_read_error_payload_shape(payload["readError"], reason_prefix="core-md-unreadable: ")
    assert ".claude/superheroes/core.md" in payload["readError"]


def _fake_run(returncode, stdout="", stderr=""):
    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return _run


def _raising_run(exc):
    def _run(argv, **kwargs):
        raise exc
    return _run


def _assert_probe_argv_matches_builder_minus_stream_json(builder, probe):
    """Probe argv equals builder read-role argv with --output-format stream-json removed."""
    # axis: exact positional equality — every builder token accounted for, stream-json at tail
    expected_tail = ["--output-format", "stream-json"]
    assert list(builder) == list(probe) + expected_tail, (
        "probe argv must equal builder minus %r: builder=%r probe=%r"
        % (expected_tail, list(builder), list(probe)))
    assert builder[-2:] == expected_tail, (
        "stream-json tokens must remain at builder tail, got %r" % list(builder[-2:]))


def _scratch_repo_cwd_checks(kwargs, *, forbidden_realpaths=()):
    """Property checks for disposable scratch repo cwd (Rider 29)."""
    cwd = kwargs.get("cwd")
    assert cwd is not None
    process_cwd = os.getcwd()
    cwd_real = os.path.realpath(cwd)
    assert cwd_real != os.path.realpath(process_cwd)
    for path in forbidden_realpaths:
        assert cwd_real != os.path.realpath(path)
    assert os.path.isdir(cwd)
    assert os.path.isdir(os.path.join(cwd, ".git"))
    entries = [e for e in os.listdir(cwd) if e != ".git"]
    assert entries == []


def _make_scratch_cwd_recording_run(forbidden_realpaths=(), raise_exc=None):
    """Fake run that records cwd and asserts scratch-repo properties at call time."""
    captured = {}

    def _run(argv, **kwargs):
        captured["cwd"] = kwargs.get("cwd")
        captured["kwargs"] = kwargs
        _scratch_repo_cwd_checks(kwargs, forbidden_realpaths=forbidden_realpaths)
        if raise_exc is not None:
            raise raise_exc
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return _run, captured


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


def test_probe_command_closes_stdin_to_prevent_inherited_pipe_hang():
    captured = {}

    def _run(argv, **kwargs):
        captured.update(kwargs)
        if "input" not in kwargs:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=120)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = pp.probe_command("t", ["t"], run=_run)
    assert result["ok"] is True
    assert captured["input"] == ""


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
        "codex", "exec", "--sandbox", "read-only", "-")


def test_cross_vendor_no_op_argv_cursor():
    # The cursor probe threads the project's configured cursor model (engine_adapter's SSOT),
    # never a hard-coded id — `cursor-small` was observed unavailable in a live run.
    import engine_adapter
    probe = pp.cross_vendor_no_op_argv("cursor")
    assert probe == (
        "cursor-agent", "--model", engine_adapter._CURSOR_MODEL, "-p", "--trust",
        "--mode", "plan")
    builder = engine_adapter.build_argv("cursor", "review", None, {})
    assert builder[builder.index("--mode") + 1] == "plan"
    # Every read-role token the builder emits is carried by the probe, except the
    # stream-json output format the probe deliberately omits (it parses no stdout).
    _assert_probe_argv_matches_builder_minus_stream_json(builder, probe)


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


# axis: exact equality of preamble-then-ask, not a suffix match
def test_probe_prompt_asks_for_a_single_word_and_nothing_else():
    # The probe must stay a no-op: an ask that invites WORK turns every compose
    # into a real dispatch under probe_command's 120s timeout.
    # Exact equality is deliberate (Rider 31): suffix/substring match would pass
    # prompts that invite work after the READY ask.
    import engine_dispatch

    assert pp.probe_prompt() == (
        engine_dispatch.ANTIHIJACK_PREAMBLE
        + "Reply with the single word READY and nothing else.\n")


def test_cross_vendor_cli_probe_feeds_preamble_on_stdin_codex():
    import engine_dispatch

    captured = {}

    def _run(argv, **kwargs):
        captured["input"] = kwargs.get("input", "")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    pp.cross_vendor_cli_probe("codex", run=_run)
    assert captured["input"].startswith(engine_dispatch.ANTIHIJACK_PREAMBLE)
    assert "READY" in captured["input"]


def test_cross_vendor_cli_probe_feeds_preamble_on_stdin_cursor():
    import engine_dispatch

    captured = {}

    def _run(argv, **kwargs):
        captured["input"] = kwargs.get("input", "")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    pp.cross_vendor_cli_probe("cursor", run=_run)
    assert captured["input"].startswith(engine_dispatch.ANTIHIJACK_PREAMBLE)
    assert "READY" in captured["input"]


def test_cross_vendor_cli_probe_unknown_engine_no_stdin_prompt():
    captured = {}

    def _run(argv, **kwargs):
        captured["input"] = kwargs.get("input", "")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    pp.cross_vendor_cli_probe("mystery", run=_run)
    assert captured["input"] == ""


# --- Rider 29: engine-CLI probes pin cwd to disposable scratch repo -------------------------

# axis: the cwd handed to the engine is a disposable git repo that is not the caller's tree, and it is removed afterwards
def test_cross_vendor_cli_probe_codex_uses_disposable_scratch_repo_cwd(tmp_path):
    repo_root = str(tmp_path)
    run, captured = _make_scratch_cwd_recording_run(forbidden_realpaths=(repo_root,))
    scratch_cwd = None
    result = pp.cross_vendor_cli_probe("codex", run=run)
    scratch_cwd = captured["cwd"]
    assert result["ok"] is True
    assert not os.path.exists(scratch_cwd)


def test_cross_vendor_cli_probe_cursor_uses_disposable_scratch_repo_cwd(tmp_path):
    repo_root = str(tmp_path)
    run, captured = _make_scratch_cwd_recording_run(forbidden_realpaths=(repo_root,))
    scratch_cwd = None
    result = pp.cross_vendor_cli_probe("cursor", run=run)
    scratch_cwd = captured["cwd"]
    assert result["ok"] is True
    assert not os.path.exists(scratch_cwd)


def test_cross_vendor_cli_probe_scratch_repo_removed_when_run_raises(tmp_path):
    repo_root = str(tmp_path)
    run, captured = _make_scratch_cwd_recording_run(
        forbidden_realpaths=(repo_root,), raise_exc=OSError("boom"))
    scratch_cwd = None
    result = pp.cross_vendor_cli_probe("codex", run=run)
    scratch_cwd = captured["cwd"]
    assert result["ok"] is False
    assert "boom" in result["detail"]
    assert not os.path.exists(scratch_cwd)


def test_composition_liveness_codex_uses_disposable_scratch_repo_cwd(tmp_path):
    repo_root = str(tmp_path)
    run, captured = _make_scratch_cwd_recording_run(forbidden_realpaths=(repo_root,))
    scratch_cwd = None
    needed = {"codex": [("gpt-5.6-terra", "high")]}
    result = pp.composition_liveness(needed, run=run)
    scratch_cwd = captured["cwd"]
    assert result["codex"]["live"] is True
    assert not os.path.exists(scratch_cwd)


def test_composition_liveness_cursor_uses_disposable_scratch_repo_cwd(tmp_path):
    repo_root = str(tmp_path)
    run, captured = _make_scratch_cwd_recording_run(forbidden_realpaths=(repo_root,))
    scratch_cwd = None
    needed = {"cursor": [("composer-2.5", None)]}
    result = pp.composition_liveness(needed, run=run)
    scratch_cwd = captured["cwd"]
    assert result["cursor"]["live"] is True
    assert not os.path.exists(scratch_cwd)


def test_composition_liveness_scratch_repo_removed_when_run_raises(tmp_path):
    repo_root = str(tmp_path)
    run, captured = _make_scratch_cwd_recording_run(
        forbidden_realpaths=(repo_root,), raise_exc=OSError("boom"))
    scratch_cwd = None
    needed = {"codex": [("gpt-5.6-terra", "high")]}
    result = pp.composition_liveness(needed, run=run)
    scratch_cwd = captured["cwd"]
    assert result["codex"]["live"] is False
    assert not os.path.exists(scratch_cwd)


def test_engine_probe_mkdtemp_failure_fail_loud(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("no temp space")

    monkeypatch.setattr(pp.tempfile, "mkdtemp", _boom)
    result = pp.cross_vendor_cli_probe("codex", run=fake0)
    assert result["ok"] is False
    assert "no temp space" in result["detail"]


def test_engine_probe_git_init_failure_fail_loud(monkeypatch):
    init_stderr = "fatal: scratch repo init rejected by test"

    def _fail_init(argv, **kwargs):
        if len(argv) >= 4 and argv[0] == "git" and argv[1] == "-C" and argv[3] == "init":
            return SimpleNamespace(returncode=1, stdout="", stderr=init_stderr)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pp.subprocess, "run", _fail_init)
    result = pp.cross_vendor_cli_probe("codex", run=fake0)
    assert result["ok"] is False
    assert result["detail"] == init_stderr


def test_gh_auth_probe_does_not_use_scratch_repo():
    captured = {}

    def _run(argv, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = pp.gh_auth_probe(run=_run)
    assert result["ok"] is True
    assert "cwd" not in captured


# --- Rider 30: probe argv drift guard (order + multiplicity) ------------------------------

# axis: token order and multiplicity, not set membership
def test_probe_argv_drift_guard_duplicate_builder_token_fails():
    builder = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--mode", "plan", "--output-format", "stream-json", "--trust",
    ]
    probe = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--mode", "plan",
    ]
    with pytest.raises(AssertionError):
        _assert_probe_argv_matches_builder_minus_stream_json(builder, probe)


# axis: omitted builder tokens fail — not a subsequence match
def test_probe_argv_drift_guard_builder_only_token_inserted_fails():
    builder = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--extra", "--mode", "plan", "--output-format", "stream-json",
    ]
    probe = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--mode", "plan",
    ]
    with pytest.raises(AssertionError):
        _assert_probe_argv_matches_builder_minus_stream_json(builder, probe)


def test_probe_argv_drift_guard_transposed_builder_tokens_fails():
    builder = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--mode", "plan",
        "--trust", "--output-format", "stream-json",
    ]
    probe = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--mode", "plan",
    ]
    with pytest.raises(AssertionError):
        _assert_probe_argv_matches_builder_minus_stream_json(builder, probe)


def test_probe_argv_drift_guard_probe_token_missing_from_builder_fails():
    builder = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--mode", "plan", "--output-format", "stream-json",
    ]
    probe = [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust",
        "--mode", "plan", "--bogus",
    ]
    with pytest.raises(AssertionError):
        _assert_probe_argv_matches_builder_minus_stream_json(builder, probe)


def test_probe_argv_drift_guard_real_values_pass():
    import engine_adapter

    probe = pp.cross_vendor_no_op_argv("cursor")
    builder = engine_adapter.build_argv("cursor", "review", None, {})
    _assert_probe_argv_matches_builder_minus_stream_json(builder, probe)


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


# --- dispatch_calibration via engine_preferences_for_gate (#699 riders 7+8) -----------------

def test_dispatch_calibration_config_ok_matches_accessor_rows(tmp_path):
    import engine_pref
    import model_tier_overrides as mto

    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    tiers = mto.effective_tiers(mto.resolve_profile_path(repo, store))
    cfg = core_md.engine_preferences_for_gate(cwd=repo, root=store)
    assert cfg.status == core_md.CONFIG_OK
    expected = engine_pref.dispatch_calibration_rows(cfg.prefs, tiers)
    rows = pp.dispatch_calibration(cwd=repo, root=store)
    assert rows == expected


def test_dispatch_calibration_absent_returns_defaults_without_read_error(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "absent")
    rows = pp.dispatch_calibration(cwd=repo, root=store)
    assert len(rows) == 4
    assert all("readError" not in r for r in rows)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "codex"


def test_dispatch_calibration_dangling_symlink_returns_marker_row(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "dangling")
    rows = pp.dispatch_calibration(cwd=repo, root=store)
    assert len(rows) == 1
    assert rows[0]["role"] == "*"
    assert rows[0]["engine"] is None
    assert rows[0]["model"] is None
    assert rows[0]["readError"].startswith("core-md-unreadable: ")
    _assert_read_error_payload_shape(rows[0]["readError"], reason_prefix="core-md-unreadable: ")


def test_dispatch_calibration_corrupt_returns_marker_row(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    cal = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(cal, exist_ok=True)
    open(os.path.join(cal, "core.md"), "w", encoding="utf-8").write("not parseable core\n")
    rows = pp.dispatch_calibration(cwd=repo, root=store)
    assert len(rows) == 1
    assert rows[0]["role"] == "*"
    assert rows[0]["engine"] is None
    assert rows[0]["model"] is None
    assert rows[0]["readError"].startswith("core-md-unreadable: ")
    _assert_read_error_payload_shape(rows[0]["readError"], reason_prefix="core-md-unreadable: ")


def _git_unavailable(monkeypatch, detail="FileNotFoundError: no git"):
    real = sc.run_git_result

    def fake(cwd, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(None, sc.GIT_UNAVAILABLE, detail)
        return real(cwd, *args)

    monkeypatch.setattr(sc, "run_git_result", fake)


def test_dispatch_calibration_root_unavailable_returns_marker_not_defaults(tmp_path, monkeypatch):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _git_unavailable(monkeypatch)
    rows = pp.dispatch_calibration(cwd=repo, root=store)
    assert len(rows) == 1
    assert rows[0]["role"] == "*"
    assert rows[0]["engine"] is None
    assert rows[0]["model"] is None
    assert rows[0]["readError"].startswith("repo-root-unavailable: ")
    _assert_read_error_payload_shape(
        rows[0]["readError"], reason_prefix="repo-root-unavailable: ")
    assert "readError" in rows[0]


def test_dispatch_calibration_cli_carries_marker_on_unreadable(tmp_path, monkeypatch, capsys):
    # Coverage/anti-stub test: passes at the base commit too — pins behavior the dispatch_selftest
    # stub was masking, not a regression test for the one-snapshot readout work.
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    repo, store = _selftest_repo_with_core_shape(tmp_path, "dangling")
    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    cal = payload["dispatchCalibration"]
    assert len(cal) == 1
    assert cal[0]["role"] == "*"
    assert cal[0]["readError"].startswith("core-md-unreadable: ")
    _assert_read_error_payload_shape(cal[0]["readError"], reason_prefix="core-md-unreadable: ")
    assert payload["aggregate"]["go"] is False
    vocab = [p for p in payload["probes"] if p["tool"] == "dispatch-vocab"]
    assert len(vocab) == 1
    assert vocab[0]["ok"] is False


def test_dispatch_calibration_invalid_utf8_tiers_returns_evaluation_failed_marker(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    profile = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    with open(profile, "wb") as fh:
        fh.write(b"<!-- review-crew: v1 -->\n## Model tiers\n\xff: opus\n")
    rows = pp.dispatch_calibration(cwd=repo, root=store)
    assert len(rows) == 1
    assert rows[0]["role"] == "*"
    assert rows[0]["engine"] is None
    assert rows[0]["model"] is None
    assert rows[0]["readError"].startswith("model-tiers-unreadable:")
    _assert_read_error_payload_shape(
        rows[0]["readError"],
        reason_prefix="model-tiers-unreadable:")


def test_dispatch_calibration_tiers_unreadable_returns_marker_row(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can read mode 0o000 files")
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    profile = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    with open(profile, "w", encoding="utf-8") as fh:
        fh.write("## Model tiers\nimplementer: opus\n")
    os.chmod(profile, 0o000)
    try:
        rows = pp.dispatch_calibration(cwd=repo, root=store)
        assert len(rows) == 1
        assert rows[0]["role"] == "*"
        assert rows[0]["engine"] is None
        assert rows[0]["model"] is None
        assert rows[0]["readError"].startswith("model-tiers-unreadable:")
    finally:
        os.chmod(profile, 0o644)


def test_dispatch_calibration_tiers_unreadable_never_raises(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can read mode 0o000 files")
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    profile = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    with open(profile, "w", encoding="utf-8") as fh:
        fh.write("## Model tiers\n")
    os.chmod(profile, 0o000)
    try:
        rows = pp.dispatch_calibration(cwd=repo, root=store)
        assert isinstance(rows, list)
        assert len(rows) == 1
    finally:
        os.chmod(profile, 0o644)


def test_dispatch_selftest_config_tiers_unreadable(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can read mode 0o000 files")
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    profile = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    with open(profile, "w", encoding="utf-8") as fh:
        fh.write("## Model tiers\n")
    os.chmod(profile, 0o000)
    try:
        cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
        assert cfg["tiers"] == {}
        assert "read_error" in cfg
        assert cfg["read_error"].startswith("model-tiers-unreadable:")
    finally:
        os.chmod(profile, 0o644)


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
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )

    rc = pp.main(["preflight_probe.py", "run", "--engine", "codex"])

    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert set(payload.keys()) == {
        "probes", "dispatchCalibration", "aggregate", "browserNote", "crossVendorEngines",
        "configRead"}
    assert payload["aggregate"]["go"] is True
    assert len(payload["probes"]) == 3
    tools = {p["tool"] for p in payload["probes"]}
    assert tools == {"gh auth", "dispatch-vocab", "cross-vendor-cli:codex"}
    assert payload["crossVendorEngines"] == ["codex"]


def test_cli_run_without_engine_derives_configured_engines(tmp_path, monkeypatch, capsys):
    # Fix C: when --engine is omitted, the CLI derives every configured non-Claude engine from
    # the project's RAW enginePreferences and probes each — not a hard-coded codex.
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )
    monkeypatch.setattr(
        pp.core_md, "engine_preferences_for_gate",
        lambda **kw: core_md.CoreGateConfig(
            {"implementation": "cursor", "briefCheck": "claude"},
            core_md.CONFIG_OK, None))

    rc = pp.main(["preflight_probe.py", "run", "--cwd", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["crossVendorEngines"] == ["cursor"]
    tools = {p["tool"] for p in payload["probes"]}
    assert tools == {"gh auth", "dispatch-vocab", "cross-vendor-cli:cursor"}


def test_cli_run_without_engine_all_claude_probes_none(monkeypatch, capsys):
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )
    monkeypatch.setattr(
        pp.core_md, "engine_preferences_for_gate",
        lambda **kw: core_md.CoreGateConfig(
            {"briefCheck": "claude"},
            core_md.CONFIG_OK, None))

    rc = pp.main(["preflight_probe.py", "run"])

    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["crossVendorEngines"] == []
    assert len(payload["probes"]) == 2   # gh auth + dispatch-vocab — no cross-vendor when all-Claude


def test_dispatch_selftest_config_fails_closed_on_corrupt_core(tmp_path):
    import importlib.util

    cm_path = os.path.join(os.path.dirname(__file__), "..", "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md_gate", cm_path)
    cm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cm)
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    cm.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                    "patterns": ""}, "confirmed", root=store, now="2026-06-30")
    core_path = cm.core_path(repo, store)
    with open(core_path, "w", encoding="utf-8") as fh:
        fh.write("corrupt core\n")
    import dispatch_selftest

    cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
    assert "read_error" in cfg
    pr = dispatch_selftest.probe_result(config=cfg)
    assert pr["ok"] is False
    assert "configuration read failed" in pr["detail"]
    agg = pp.aggregate([{"tool": "dispatch-vocab", "ok": pr["ok"], "detail": pr["detail"]}])
    assert agg["go"] is False


def test_dispatch_selftest_config_clean_when_no_core(tmp_path):
    import model_tier_overrides

    cfg = pp._dispatch_selftest_config(cwd=str(tmp_path))
    # Absent core.md no longer skips the tier read (#752 rider 7).
    assert cfg["prefs"] == {}
    assert "read_error" not in cfg
    assert cfg["tiers"] == model_tier_overrides.effective_tiers(None)
    assert cfg["tiers"] != {}
    import dispatch_selftest

    pr = dispatch_selftest.probe_result(config=cfg)
    assert pr["ok"] is True


def _selftest_repo_with_core_shape(tmp_path, shape):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    cal = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(cal, exist_ok=True)
    core_p = os.path.join(cal, "core.md")
    text = core_md.render_core(
        {
            "verifyCommand": "npm test",
            "stackTags": [],
            "enginePreferences": {"reviewer": "cursor"},
            "threatModel": "t",
            "patterns": "",
        },
        "confirmed",
        "2026-01-01",
        "2026-01-01",
    )
    if shape == "directory":
        os.mkdir(core_p)
    elif shape == "dangling":
        os.symlink("/nonexistent/preflight-dangle", core_p)
    elif shape == "absent":
        pass
    elif shape == "ok":
        open(core_p, "w", encoding="utf-8").write(text)
    return repo, store


def test_dispatch_selftest_config_unreadable_shapes(tmp_path):
    for shape in ("directory", "dangling"):
        repo, store = _selftest_repo_with_core_shape(tmp_path / shape, shape)
        cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
        assert "read_error" in cfg
        assert "core-md-unreadable" in cfg["read_error"]


def test_dispatch_selftest_config_unreadable_read_error_byte_identity(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    cal = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(cal, exist_ok=True)
    core_p = os.path.join(cal, "core.md")
    open(core_p, "w", encoding="utf-8").write("not parseable core\n")
    cfg_cls = core_md._classify_core_md_at_path(core_p)
    expected = "core-md-unreadable: " + cfg_cls.detail
    cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
    assert cfg["read_error"] == expected


def test_dispatch_selftest_config_root_unavailable_returns_read_error(tmp_path, monkeypatch):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _git_unavailable(monkeypatch)
    cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
    assert "read_error" in cfg
    assert cfg["read_error"].startswith("repo-root-unavailable: ")


def test_dispatch_selftest_config_unresolvable_root_returns_read_error(
    tmp_path, isolated_default_store_root
):
    import calibration_resolve as cr
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    default_store = isolated_default_store_root
    empty = tmp_path / "empty_store"
    empty.mkdir()
    empty_s = str(empty)
    store = __import__("mode_registry").ensure_project_store(str(repo), root=default_store)
    cfg_dir = os.path.join(store, "config")
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, "review-crew.md"), "w") as fh:
        fh.write("## Focus hints\n- code: x\n")
    cfg = pp._dispatch_selftest_config(cwd=str(repo), root=empty_s)
    assert "read_error" in cfg
    assert cr.REASON_UNRESOLVABLE_ROOT in cfg["read_error"]


def test_dispatch_selftest_config_ok_returns_prefs(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
    assert "read_error" not in cfg
    assert cfg["prefs"] == {"reviewer": "cursor"}
    assert isinstance(cfg["tiers"], dict)


def test_dispatch_vocab_probe_blocks_aggregate_on_failure(monkeypatch):
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": False, "detail": "broken"},
    )
    probes = [pp.gh_auth_probe(run=fake0), dispatch_selftest.probe_result()]
    agg = pp.aggregate(probes)
    assert agg["go"] is False
    assert "dispatch-vocab" in agg["blocking"]


def test_preflight_run_includes_dispatch_vocab_probe(monkeypatch, capsys):
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )

    rc = pp.main(["preflight_probe.py", "run", "--engine", "codex"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    vocab = [p for p in payload["probes"] if p["tool"] == "dispatch-vocab"]
    assert len(vocab) == 1
    assert vocab[0]["ok"] is True
    assert payload["aggregate"]["go"] is True


# --- composition preflight (#510 WO-3) -------------------------------------------------------

def test_model_no_op_argv_cursor_grok_dispatch_token():
    import engine_adapter
    argv = pp.model_no_op_argv("cursor", "cursor-grok-4.6", "xhigh")
    expected = tuple(engine_adapter.build_argv(
        "cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6"}))
    assert argv == expected
    assert argv == (
        "cursor-agent", "--model", "cursor-grok-4.6-xhigh", "-p", "--trust",
        "--mode", "plan", "--output-format", "stream-json")


def test_model_no_op_argv_cursor_bogus_model_returns_none():
    assert pp.model_no_op_argv("cursor", "bogus-model", "high") is None


def test_model_no_op_argv_codex_effort_none_resolves_from_matrix():
    argv = pp.model_no_op_argv("codex", "gpt-5.6-sol")
    assert argv is not None
    assert "model_reasoning_effort=xhigh" in argv


def test_model_no_op_argv_codex_terra_effort_none_resolves_second_tier():
    argv = pp.model_no_op_argv("codex", "gpt-5.6-terra")
    assert argv is not None
    assert "model_reasoning_effort=high" in argv


def test_model_no_op_argv_codex_matches_builder():
    import engine_adapter
    argv = pp.model_no_op_argv("codex", "gpt-5.6-sol", "xhigh")
    expected = tuple(engine_adapter.build_argv(
        "codex", "review", "xhigh", {"engine_model": "gpt-5.6-sol"}))
    assert argv == expected
    assert argv[-1] == "-"


def test_model_no_op_argv_codex_bogus_model_returns_none():
    assert pp.model_no_op_argv("codex", "gpt-9-bogus") is None


def test_needed_configs_for_review_tiers_omits_claude():
    configs = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex", "cursor"])
    assert "claude" not in configs
    assert configs["codex"] == [("gpt-5.6-sol", "xhigh"), ("gpt-5.6-terra", "high")]
    assert configs["cursor"] == [("cursor-grok-4.6", "xhigh")]


def test_composition_liveness_cursor_both_models_ok_is_live():
    calls = []

    def _run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed = {"cursor": [("composer-2.5", None), ("cursor-grok-4.6", "xhigh")]}
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

    needed = {"cursor": [("composer-2.5", None), ("cursor-grok-4.6", "xhigh")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["cursor"]["live"] is False
    assert result["cursor"]["models"]["composer-2.5"]["ok"] is True
    assert result["cursor"]["models"]["cursor-grok-4.6"]["ok"] is False


def test_composition_liveness_live_and_models_derived_from_cells():
    # axis: vestigial copies — live flag and models map stay consistent with cells
    all_ok_needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    all_ok = pp.composition_liveness(all_ok_needed, run=fake0)
    for vendor, info in all_ok.items():
        if vendor == "claude":
            continue
        assert info["live"] == all(c["ok"] for c in info["cells"])
        assert set(info["models"]) == {c["model"] for c in info["cells"]}
        for model, entry in info["models"].items():
            rel = [c for c in info["cells"] if c["model"] == model]
            assert rel
            assert entry["ok"] == all(c["ok"] for c in rel)

    def _partial_run(argv, **kwargs):
        model = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if model == "gpt-5.6-sol":
            return SimpleNamespace(returncode=1, stdout="", stderr="fail")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    partial_needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    partial = pp.composition_liveness(partial_needed, run=_partial_run)
    info = partial["codex"]
    assert info["live"] is False
    assert info["live"] == all(c["ok"] for c in info["cells"])
    assert set(info["models"]) == {c["model"] for c in info["cells"]}
    for model, entry in info["models"].items():
        rel = [c for c in info["cells"] if c["model"] == model]
        assert rel
        assert entry["ok"] == all(c["ok"] for c in rel)

    collision_needed = {"codex": [("gpt-5.6-sol", "xhigh"), ("gpt-5.6-sol", "high")]}
    collision = pp.composition_liveness(collision_needed, run=_collision_run)
    info = collision["codex"]
    assert set(info["models"]) == {c["model"] for c in info["cells"]}
    for model, entry in info["models"].items():
        rel = [c for c in info["cells"] if c["model"] == model]
        assert rel
        assert entry["ok"] == all(c["ok"] for c in rel)

    empty = pp.composition_liveness({"codex": []}, run=fake0)
    assert empty["codex"]["live"] is False


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
    assert result["claude"] == {"live": True, "models": {}, "cells": []}


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


def test_composition_liveness_hardened_dispatch_codex():
    import engine_dispatch

    captured = {}

    def _run(argv, **kwargs):
        inp = kwargs.get("input", "")
        captured["input"] = inp
        if not inp.startswith(engine_dispatch.ANTIHIJACK_PREAMBLE):
            return SimpleNamespace(returncode=1, stdout="", stderr="no preamble")
        if argv[-1] != "-":
            return SimpleNamespace(returncode=1, stdout="", stderr="not stdin form")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed = {"codex": [("gpt-5.6-sol", "xhigh")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["codex"]["live"] is True
    assert "READY" in captured["input"]


def test_composition_liveness_hardened_dispatch_cursor():
    import engine_dispatch

    captured = {}

    def _run(argv, **kwargs):
        inp = kwargs.get("input", "")
        captured["input"] = inp
        if not inp.startswith(engine_dispatch.ANTIHIJACK_PREAMBLE):
            return SimpleNamespace(returncode=1, stdout="", stderr="no preamble")
        if any("READY" in str(a).upper() for a in argv):
            return SimpleNamespace(returncode=1, stdout="", stderr="positional prompt")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed = {"cursor": [("cursor-grok-4.6", "xhigh")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["cursor"]["live"] is True
    assert "READY" in captured["input"]


def _collision_run(argv, **kwargs):
    effort = next((a for a in argv if a.startswith("model_reasoning_effort=")), "")
    if effort == "model_reasoning_effort=high":
        return SimpleNamespace(returncode=1, stdout="", stderr="high failed")
    return SimpleNamespace(returncode=0, stdout="READY", stderr="")


def test_composition_liveness_same_model_collision_fail_closed_high_first():
    needed = {"codex": [("gpt-5.6-sol", "high"), ("gpt-5.6-sol", "xhigh")]}
    result = pp.composition_liveness(needed, run=_collision_run)
    assert result["codex"]["live"] is False
    assert result["codex"]["models"]["gpt-5.6-sol"]["ok"] is False


def test_composition_liveness_same_model_collision_fail_closed_xhigh_first():
    needed = {"codex": [("gpt-5.6-sol", "xhigh"), ("gpt-5.6-sol", "high")]}
    result = pp.composition_liveness(needed, run=_collision_run)
    assert result["codex"]["live"] is False
    assert result["codex"]["models"]["gpt-5.6-sol"]["ok"] is False


def test_composition_liveness_same_model_both_configs_ok_is_live():
    needed = {"codex": [("gpt-5.6-sol", "high"), ("gpt-5.6-sol", "xhigh")]}
    result = pp.composition_liveness(needed, run=fake0)
    assert result["codex"]["live"] is True
    assert result["codex"]["models"]["gpt-5.6-sol"]["ok"] is True


def test_probe_argv_builders_contain_no_positional_prompt():
    import engine_adapter

    builders = [
        ("cross_vendor", pp.cross_vendor_no_op_argv("codex")),
        ("cross_vendor", pp.cross_vendor_no_op_argv("cursor")),
        ("model_no_op", pp.model_no_op_argv("codex", "gpt-5.6-sol", "xhigh")),
        ("model_no_op", pp.model_no_op_argv("cursor", "cursor-grok-4.6", "xhigh")),
        ("model_no_op", pp.model_no_op_argv("codex", "gpt-5.6-terra", "high")),
        ("model_no_op", pp.model_no_op_argv("cursor", "composer-2.5", None)),
    ]
    for label, argv in builders:
        assert argv is not None, "%s returned None" % label
        for element in argv:
            assert "READY" not in str(element).upper(), (
                "%s argv element %r contains READY" % (label, element))
            assert len(str(element).split()) == 1, (
                "%s argv element %r is multi-word" % (label, element))


def test_live_vendors_for_composition_claude_always_in_live_list():
    live, _live_cells, liveness, _notes, _prov = pp.live_vendors_for_composition(["codex", "cursor"], run=fake1)
    assert "claude" in live
    assert liveness["claude"]["live"] is True


def test_live_vendors_for_composition_all_ok_includes_external():
    live, _live_cells, _, _, _ = pp.live_vendors_for_composition(["codex", "cursor"], run=fake0)
    assert live == ["claude", "codex", "cursor"]


def test_live_vendors_for_composition_external_failure_excludes_vendor():
    live, _live_cells, _, _, _ = pp.live_vendors_for_composition(["codex", "cursor"], run=fake1)
    assert live == ["claude"]


def test_live_vendors_for_composition_returns_five_tuple():
    result = pp.live_vendors_for_composition(["codex"], run=fake0)
    assert len(result) == 5


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
            "cells": [
                {"model": m, "effort": e, "ok": True, "detail": ""}
                for m, e in needed["codex"]
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0
    assert liveness_cache.write(liveness, needed, path=cache_path, now=now)

    def _boom(argv, **kwargs):
        raise AssertionError("run must not be called on cache hit")

    live, _live_cells, _liv, notes, _prov = pp.live_vendors_for_composition(
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
    live, _live_cells, _liv, _notes, _prov = pp.live_vendors_for_composition(
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

    live, _live_cells, _liv, notes, provenance = pp.live_vendors_for_composition(
        ["codex", "cursor"],
        run=_boom,
        probe_mode="cache-only",
        cache_path="/nonexistent/path.json",
        now=1000.0,
    )
    assert live == ["claude"]
    assert provenance == "unprobed"
    assert any(n.get("constraint") == "preflight-cache-only" for n in notes)


def test_live_vendors_for_composition_cache_only_miss_never_stamps_probed():
    # bite-axis: cache-only with no usable cache must not claim probed provenance
    _live, _live_cells, _liv, _notes, provenance = pp.live_vendors_for_composition(
        ["codex"],
        probe_mode="cache-only",
        cache_path="/nonexistent/path.json",
        now=1000.0,
    )
    assert provenance != "probed"
    assert provenance == "unprobed"


def test_live_vendors_for_composition_provenance_per_branch(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    liveness = {
        "codex": {
            "live": True,
            "models": {m: {"ok": True, "detail": ""} for m, _ in needed["codex"]},
            "cells": [
                {"model": m, "effort": e, "ok": True, "detail": ""}
                for m, e in needed["codex"]
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0
    liveness_cache.write(liveness, needed, path=cache_path, now=now)

    def _boom(argv, **kwargs):
        raise AssertionError("run must not be called")

    _live, _cells, _liv, _notes, cache_hit_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_boom,
        cache_path=cache_path,
        now=now + 1,
    )
    assert cache_hit_prov == "probed"

    _live, _cells, _liv, _notes, cache_only_miss_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_boom,
        probe_mode="cache-only",
        cache_path="/nonexistent/path.json",
        now=now,
    )
    assert cache_only_miss_prov == "unprobed"

    _live, _cells, _liv, _notes, fresh_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=str(tmp_path / "fresh-cache.json"),
        now=now,
    )
    assert fresh_prov == "probed"


def test_live_vendors_for_composition_cache_only_hit_reuses(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    liveness = {
        "codex": {
            "live": True,
            "models": {m: {"ok": True, "detail": ""} for m, _ in needed["codex"]},
            "cells": [
                {"model": m, "effort": e, "ok": True, "detail": ""}
                for m, e in needed["codex"]
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 2000.0
    liveness_cache.write(liveness, needed, path=cache_path, now=now)

    def _boom(argv, **kwargs):
        raise AssertionError("run must not be called on cache-only hit")

    live, _live_cells, _liv, notes, _prov = pp.live_vendors_for_composition(
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
    live, _live_cells, _liv, notes, _prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=cache_path,
        now=1000.0,
    )
    assert "codex" in live
    assert any(n.get("constraint") == "preflight-cache-write-failed" for n in notes)


def test_live_vendors_for_composition_fresh_path_emits_cell_dead_notes():
    def _run(argv, **kwargs):
        model = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if model == "gpt-5.6-terra":
            return SimpleNamespace(
                returncode=1, stdout="", stderr="Command timed out after 120 seconds")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    live, live_cells, _liv, notes, _prov = pp.live_vendors_for_composition(["codex"], run=_run)
    assert "codex" not in live
    assert any(c[1] == "gpt-5.6-sol" for c in live_cells)
    cell_notes = [n for n in notes if n.get("constraint") == "liveness-cell"]
    assert any(n["model"] == "gpt-5.6-terra" for n in cell_notes)
    assert any("timed out" in n["reason"] for n in cell_notes)


def test_live_vendors_for_composition_cache_path_emits_cell_dead_notes(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    liveness = {
        "codex": {
            "live": False,
            "models": {
                m: {"ok": (m != "gpt-5.6-terra"), "detail": (
                    "Command timed out after 120 seconds" if m == "gpt-5.6-terra" else "")}
                for m, _ in needed["codex"]
            },
            "cells": [
                {
                    "model": m,
                    "effort": e,
                    "ok": (m != "gpt-5.6-terra"),
                    "detail": (
                        "Command timed out after 120 seconds" if m == "gpt-5.6-terra" else ""),
                }
                for m, e in needed["codex"]
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0
    liveness_cache.write(liveness, needed, path=cache_path, now=now)

    live, live_cells, _liv, notes, _prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=cache_path,
        now=now + 1,
    )
    assert "codex" not in live
    assert any(c[1] == "gpt-5.6-sol" for c in live_cells)
    cell_notes = [n for n in notes if n.get("constraint") == "liveness-cell"]
    assert any(n["model"] == "gpt-5.6-terra" for n in cell_notes)
    assert any("timed out" in n["reason"] for n in cell_notes)


def test_cli_compose_liveness_writes_receipt(tmp_path, monkeypatch, capsys):
    import liveness_cache

    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None: {
        "codex": {"live": True, "models": {}, "cells": []},
        "claude": {"live": True, "models": {}, "cells": []},
    })
    monkeypatch.setattr(pp.core_md, "read", lambda *a, **k: {"enginePreferences": {}})

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", str(tmp_path)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "live" in payload
    assert "cachePath" in payload
    assert payload["cachePath"] == str(cache_file)
    assert cache_file.is_file()


# --- readout_config (#752 riders 7 + 27a) --------------------------------------------------


def test_readout_config_ok(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    snap = pp.readout_config(cwd=repo, root=store)
    assert snap["status"] == core_md.CONFIG_OK
    assert snap["reason"] is None
    assert snap["readError"] is None
    assert snap["prefs"] == {"reviewer": "cursor"}


def test_readout_config_absent(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "absent")
    snap = pp.readout_config(cwd=repo, root=store)
    assert snap["status"] == core_md.CONFIG_ABSENT
    assert snap["reason"] is None
    assert snap["readError"] is None
    assert snap["prefs"] == {}


def test_readout_config_status_tokens_match_constants(tmp_path):
    """Emitted status values must stay aligned with core_md constants."""
    repo_ok, store_ok = _selftest_repo_with_core_shape(tmp_path, "ok")
    snap_ok = pp.readout_config(cwd=repo_ok, root=store_ok)
    assert snap_ok["status"] == core_md.CONFIG_OK
    repo_absent, store_absent = _selftest_repo_with_core_shape(tmp_path / "absent", "absent")
    snap_absent = pp.readout_config(cwd=repo_absent, root=store_absent)
    assert snap_absent["status"] == core_md.CONFIG_ABSENT


def test_readout_config_dangling_symlink(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "dangling")
    snap = pp.readout_config(cwd=repo, root=store)
    assert snap["status"] == "unreadable"
    assert snap["readError"].startswith("core-md-unreadable: ")
    assert snap["prefs"] == {}


def test_readout_config_git_unavailable(tmp_path, monkeypatch):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _git_unavailable(monkeypatch)
    snap = pp.readout_config(cwd=repo, root=store)
    assert snap["readError"].startswith("repo-root-unavailable: ")
    assert snap["reason"] == core_md.GATE_REASON_ROOT_UNAVAILABLE
    assert snap["prefs"] == {}


def test_readout_config_gate_config_refusal_raises_fail_closed(tmp_path, monkeypatch):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")

    def fake_gate(**kw):
        return core_md.CoreGateConfig({}, "future-unknown-status", "detail")

    monkeypatch.setattr(pp.core_md, "engine_preferences_for_gate", fake_gate)
    snap = pp.readout_config(cwd=repo, root=store)
    assert snap["readError"].startswith("dispatch-gate-evaluation-failed: ")
    assert snap["reason"] == core_md.GATE_REASON_EVALUATION_FAILED
    assert snap["prefs"] == {}


def test_run_one_snapshot_self_consistent(tmp_path, monkeypatch, capsys):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    calls = []
    ok_cfg = core_md.CoreGateConfig({}, core_md.CONFIG_OK, None)

    def counting_gate(**kw):
        calls.append(1)
        return ok_cfg

    monkeypatch.setattr(pp.core_md, "engine_preferences_for_gate", counting_gate)
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(calls) == 1


def test_run_unreadable_config_self_consistent(tmp_path, monkeypatch, capsys):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "dangling")
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["configRead"]["reason"] is not None
    assert payload["configRead"]["readError"] is not None
    _assert_read_error_payload_shape(
        payload["configRead"]["readError"], reason_prefix="core-md-unreadable: ")
    assert payload["aggregate"]["go"] is not True


def test_run_readable_project_config_read_ok(tmp_path, monkeypatch, capsys):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["configRead"] == {
        "status": core_md.CONFIG_OK, "reason": None, "readError": None}
    assert set(payload.keys()) == {
        "probes", "dispatchCalibration", "aggregate", "browserNote", "crossVendorEngines",
        "configRead"}
    assert isinstance(payload["probes"], list)
    assert isinstance(payload["dispatchCalibration"], list)
    assert isinstance(payload["aggregate"], dict)
    assert isinstance(payload["browserNote"], str)
    assert isinstance(payload["crossVendorEngines"], list)


def test_compose_liveness_unreadable_core_config_read_and_note(tmp_path, monkeypatch, capsys):
    import liveness_cache

    repo, store = _selftest_repo_with_core_shape(tmp_path, "dangling")
    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None: {
        "codex": {"live": True, "models": {}, "cells": []},
        "claude": {"live": True, "models": {}, "cells": []},
    })

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["configRead"]["readError"] is not None
    _assert_read_error_payload_shape(
        payload["configRead"]["readError"], reason_prefix="core-md-unreadable: ")
    assert payload["configRead"]["reason"] == core_md.GATE_REASON_UNREADABLE
    unread_notes = [n for n in payload["notes"] if n.get("constraint") == core_md.GATE_REASON_UNREADABLE]
    assert len(unread_notes) == 1
    assert unread_notes[0]["reason"] == payload["configRead"]["readError"]


def test_compose_liveness_readable_core_no_unreadable_note(tmp_path, monkeypatch, capsys):
    import liveness_cache

    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None: {
        "codex": {"live": True, "models": {}, "cells": []},
        "claude": {"live": True, "models": {}, "cells": []},
    })

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["configRead"]["readError"] is None
    assert payload["configRead"]["reason"] is None
    unread_notes = [n for n in payload["notes"] if n.get("constraint") == core_md.GATE_REASON_UNREADABLE]
    assert unread_notes == []


def test_compose_liveness_configured_engines_come_from_the_snapshot(tmp_path, monkeypatch, capsys):
    import liveness_cache

    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))

    distinctive_snapshot = {
        "prefs": {"reviewer": "cursor", "implementer": "cursor",
                  "briefCheck": "cursor", "pilot": "cursor"},
        "status": core_md.CONFIG_OK, "reason": None, "readError": None,
    }
    monkeypatch.setattr(pp, "readout_config", lambda cwd=None, root=None: distinctive_snapshot)

    poison_msg = "compose-liveness must use the snapshot, not an independent core.md read"

    def poison(*a, **kw):
        raise AssertionError(poison_msg)

    monkeypatch.setattr(pp.core_md, "read", poison)
    monkeypatch.setattr(pp.core_md, "engine_preferences_for_gate", poison)

    captured = {}

    def capture_live_vendors(configured_vendors, *args, **kwargs):
        captured["configured_vendors"] = configured_vendors
        return (["claude"], [], {}, [], "probed")

    monkeypatch.setattr(pp, "live_vendors_for_composition", capture_live_vendors)

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert captured["configured_vendors"] == ["cursor"]
    assert payload["crossVendorEngines"] == ["cursor"]


def test_both_cli_config_read_payloads_use_the_shared_projection(tmp_path, monkeypatch, capsys):
    import dispatch_selftest
    import liveness_cache

    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None: {
        "codex": {"live": True, "models": {}, "cells": []},
        "claude": {"live": True, "models": {}, "cells": []},
    })

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", repo])
    assert rc == 0
    compose_payload = json.loads(capsys.readouterr().out)
    assert set(compose_payload["configRead"].keys()) == set(pp.CONFIG_READ_FIELDS)
    assert "prefs" not in compose_payload["configRead"]

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    run_payload = json.loads(capsys.readouterr().out)
    assert set(run_payload["configRead"].keys()) == set(pp.CONFIG_READ_FIELDS)
    assert "prefs" not in run_payload["configRead"]


def _seed_invalid_utf8_tiers(repo):
    profile = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    with open(profile, "wb") as fh:
        fh.write(b"<!-- review-crew: v1 -->\n## Model tiers\n\xff: opus\n")


def test_readout_config_keys_are_core_only(tmp_path):
    for shape in ("ok", "absent", "dangling"):
        repo, store = _selftest_repo_with_core_shape(tmp_path / shape, shape)
        snap = pp.readout_config(cwd=repo, root=store)
        assert set(snap.keys()) == {"prefs", "status", "reason", "readError"}


def test_readout_config_does_not_read_tiers(tmp_path, monkeypatch):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    calls = []
    real = pp.model_tier_overrides.effective_tiers

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(pp.model_tier_overrides, "effective_tiers", counting)
    snap = pp.readout_config(cwd=repo, root=store)
    assert len(calls) == 0
    assert snap["status"] == core_md.CONFIG_OK


def test_readout_config_ok_with_corrupt_tiers_profile_is_unaffected(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    _seed_invalid_utf8_tiers(repo)
    snap = pp.readout_config(cwd=repo, root=store)
    assert snap["status"] == core_md.CONFIG_OK
    assert snap["readError"] is None
    assert snap["prefs"] == {"reviewer": "cursor"}
    assert set(snap.keys()) == {"prefs", "status", "reason", "readError"}


def test_absent_core_with_corrupt_tiers_blocks_go(tmp_path, monkeypatch, capsys):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "absent")
    _seed_invalid_utf8_tiers(repo)
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["aggregate"]["go"] is False
    vocab = [p for p in payload["probes"] if p["tool"] == "dispatch-vocab"]
    assert len(vocab) == 1
    assert vocab[0]["ok"] is False
    cal = payload["dispatchCalibration"]
    assert len(cal) == 1
    assert cal[0]["role"] == "*"
    assert cal[0]["readError"].startswith("model-tiers-unreadable: UTF-8 decode failed at ")
    _assert_read_error_payload_shape(
        cal[0]["readError"], reason_prefix="model-tiers-unreadable: ")


def test_dispatch_selftest_config_absent_core_reads_real_tiers(tmp_path):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "absent")
    profile = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    with open(profile, "w", encoding="utf-8") as fh:
        fh.write("<!-- review-crew: v1 -->\n## Model tiers\nreviewer-deep: opus\n")

    cfg = pp._dispatch_selftest_config(cwd=repo, root=store)
    assert cfg["prefs"] == {}
    assert cfg["tiers"]["reviewer-deep"] == "opus"
    assert cfg["tiers"] != {}


def test_dispatch_calibration_snapshot_read_error_beats_explicit_prefs():
    rows = pp.dispatch_calibration(
        prefs={"reviewer": "cursor"},
        tiers={},
        snapshot={
            "prefs": {},
            "status": "unreadable",
            "reason": core_md.GATE_REASON_UNREADABLE,
            "readError": "core-md-unreadable: dangling",
        })
    assert len(rows) == 1
    assert rows[0]["role"] == "*"
    assert rows[0]["readError"] == "core-md-unreadable: dangling"


def test_config_read_payload_keys_are_core_only(tmp_path, monkeypatch, capsys):
    import liveness_cache

    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})
    import dispatch_selftest

    monkeypatch.setattr(
        dispatch_selftest,
        "probe_result",
        lambda config=None: {"tool": "dispatch-vocab", "ok": True, "detail": "ok (1 checks)"},
    )
    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None: {
        "codex": {"live": True, "models": {}, "cells": []},
        "claude": {"live": True, "models": {}, "cells": []},
    })

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["configRead"].keys()) == {"status", "reason", "readError"}

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", repo])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["configRead"].keys()) == {"status", "reason", "readError"}


def test_run_reads_tiers_once_per_consumer(tmp_path, monkeypatch, capsys):
    repo, store = _selftest_repo_with_core_shape(tmp_path, "ok")
    calls = []
    real = pp.model_tier_overrides.effective_tiers_for_gate

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(pp.model_tier_overrides, "effective_tiers_for_gate", counting)
    monkeypatch.setattr(pp, "gh_auth_probe", lambda run=None: {
        "tool": "gh auth", "ok": True, "exit": 0, "detail": ""})
    monkeypatch.setattr(pp, "cross_vendor_cli_probe", lambda engine, run=None, argv=None: {
        "tool": "cross-vendor-cli:" + engine, "ok": True, "exit": 0, "detail": ""})

    rc = pp.main(["preflight_probe.py", "run", "--cwd", repo])
    assert rc == 0
    capsys.readouterr()
    assert len(calls) == 2
