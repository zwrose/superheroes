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
import model_registry as MR
import seat_bundle
import store_core as sc

import preflight_probe as pp

# Fakes that answer every argv the same way must also answer `codex --version` at (or above)
# the registry's floor, so the codex-CLI-floor gate never refuses a probe this file's fakes
# never intended to fail. Read from the registry, never a literal (common.md migration rule).
_CODEX_FLOOR_VERSION = MR.codex_min_cli()[0]
_CODEX_VERSION_STDOUT = "codex-cli %s\n" % _CODEX_FLOOR_VERSION


def _answer_codex_version_at_floor(argv):
    """A canned at-floor success reply when `argv` is the codex-CLI-floor gate's own
    `codex --version` probe; None otherwise (caller falls through to its own handling). A
    custom fake `run` that discriminates by `-m`/effort flags must not also be asked to answer
    this bare `("codex", "--version")` call — it isn't shaped like a dispatch argv."""
    if list(argv) == ["codex", "--version"]:
        return SimpleNamespace(returncode=0, stdout=_CODEX_VERSION_STDOUT, stderr="")
    return None


def _run_that_forbids_dispatch(msg="run must not be called"):
    """A fake run that answers ONLY the codex-CLI-floor gate's own `codex --version` probe (a
    cache hit still runs that gate before consulting the cache); any other call — a real
    per-cell/no-op dispatch — means the cache was bypassed and is a test failure."""
    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        raise AssertionError(msg)
    return _run


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
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
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
    """Fake run that records cwd and asserts scratch-repo properties at call time.

    The codex-CLI-floor gate's `codex --version` probe runs through the plain (non-scratch-repo)
    `probe_command`, so it carries no `cwd` — answered here at the registry floor without the
    scratch-repo assertions, and without touching `captured["cwd"]`, so a caller's later read of
    `captured["cwd"]` still names the real scratch-repo cwd from the no-op probe."""
    captured = {}

    def _run(argv, **kwargs):
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout=_CODEX_VERSION_STDOUT, stderr="")
        captured["cwd"] = kwargs.get("cwd")
        captured["kwargs"] = kwargs
        _scratch_repo_cwd_checks(kwargs, forbidden_realpaths=forbidden_realpaths)
        if raise_exc is not None:
            raise raise_exc
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return _run, captured


fake0 = _fake_run(0, stdout=_CODEX_VERSION_STDOUT)
fake1 = _fake_run(1, stdout=_CODEX_VERSION_STDOUT)

# Registry-derived codex fixtures for the tests below (never a re-spelled model literal).
_CODEX_REVIEWER_DEEP_CELL = MR.matrix_config("reviewer-deep", "codex")   # (model, effort)
_CODEX_REVIEWER_CELL = MR.matrix_config("reviewer", "codex")             # (model, effort)
_CODEX_LADDER = MR.ladder("codex")
_CODEX_LADDER_DEFAULT_CELL = _CODEX_LADDER[0]
_CODEX_LADDER_ALT_CELL = next(c for c in _CODEX_LADDER if c[0] != _CODEX_LADDER_DEFAULT_CELL[0])
_CODEX_PIN_ONLY_MODEL = MR.pin_only_models("codex")[0]


# --- probe_command -----------------------------------------------------------------------

def test_probe_command_ok_on_exit_zero():
    # A plain empty-stdout fake, deliberately not the shared codex-version-answering fake0/fake1
    # (this test asserts the exact detail string, so it must not pick up their canned version
    # text — those fakes exist to satisfy the codex-CLI-floor gate, not this generic probe).
    result = pp.probe_command("t", ["t"], run=_fake_run(0))
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


# --- codex_cli_floor_probe (#1435 WO-2b) ----------------------------------------------------


def _decrement_version(version_str):
    """The floor version with its rightmost non-zero component decremented by one — a version
    that compares strictly below `version_str` as int tuples."""
    parts = [int(p) for p in version_str.split(".")]
    i = len(parts) - 1
    while i >= 0:
        if parts[i] > 0:
            parts[i] -= 1
            break
        i -= 1
    return ".".join(str(p) for p in parts)


def _increment_version(version_str):
    parts = [int(p) for p in version_str.split(".")]
    parts[-1] += 1
    return ".".join(str(p) for p in parts)


# bite-axis: codex_cli_floor_probe refuses a codex CLI below the registry floor, naming the floor, the required model, and the CLI's own version in the detail
def test_codex_cli_floor_probe_below_floor_refused():
    below = _decrement_version(_CODEX_FLOOR_VERSION)
    floor_model = MR.codex_min_cli()[1]

    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % below, stderr="")

    result = pp.codex_cli_floor_probe(run=_run)
    assert result is not None
    assert result["ok"] is False
    assert result["tool"] == "cross-vendor-cli:codex"
    assert result["detail"].startswith("codex-cli-too-old:")
    assert _CODEX_FLOOR_VERSION in result["detail"]
    assert floor_model in result["detail"]
    assert below in result["detail"]


# bite-axis: codex_cli_floor_probe compares versions NUMERICALLY, never as a bare string — a
# CLI that is numerically below the floor but lexically greater (e.g. "0.99.0" vs "0.157.0",
# where "9" > "1" at the first differing character) must still be refused. This is the same
# trap `test_i4_codex_min_cli_compares_numerically_not_as_a_string` already guards on
# `codex_min_cli()`; the dispatch gate itself (`found_key >= floor_key`) needs the same proof.
def test_codex_cli_floor_probe_numerically_below_but_lexically_above_refused():
    floor_major, floor_minor, _floor_patch = (int(p) for p in _CODEX_FLOOR_VERSION.split("."))
    trap_minor = 99
    assert trap_minor < floor_minor, "expected the registry floor's minor to exceed 99"
    assert str(trap_minor) > str(floor_minor), (
        "expected '%d' to sort lexically ABOVE '%d' (first-char trap)" % (trap_minor, floor_minor)
    )
    trap_version = "%d.%d.0" % (floor_major, trap_minor)

    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % trap_version, stderr="")

    result = pp.codex_cli_floor_probe(run=_run)
    assert result is not None
    assert result["ok"] is False
    assert result["detail"].startswith("codex-cli-too-old:")


def test_codex_cli_floor_probe_at_floor_passes():
    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=0, stdout=_CODEX_VERSION_STDOUT, stderr="")

    assert pp.codex_cli_floor_probe(run=_run) is None


def test_codex_cli_floor_probe_above_floor_passes():
    above = _increment_version(_CODEX_FLOOR_VERSION)

    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % above, stderr="")

    assert pp.codex_cli_floor_probe(run=_run) is None


# bite-axis: codex_cli_floor_probe fails closed and refuses when the CLI's version output cannot be parsed
def test_codex_cli_floor_probe_unparseable_output_refused():
    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=0, stdout="not a version\n", stderr="")

    result = pp.codex_cli_floor_probe(run=_run)
    assert result is not None
    assert result["ok"] is False
    assert result["detail"].startswith("codex-cli-version-unknown:")


def test_codex_cli_floor_probe_runner_raises_refused():
    def _run(argv, **kwargs):
        raise OSError("no codex binary")

    result = pp.codex_cli_floor_probe(run=_run)
    assert result is not None
    assert result["ok"] is False
    assert result["detail"].startswith("codex-cli-version-unknown:")


def test_codex_cli_floor_probe_no_declared_floor_skips_probe(monkeypatch):
    calls = []

    def _run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=_CODEX_VERSION_STDOUT, stderr="")

    monkeypatch.setattr(pp.model_registry, "codex_min_cli", lambda: None)
    assert pp.codex_cli_floor_probe(run=_run) is None
    assert calls == []


# bite-axis: cross_vendor_cli_probe("codex") refuses on a below-floor CLI without ever running the exec no-op
def test_cross_vendor_cli_probe_codex_below_floor_refuses_without_exec():
    below = _decrement_version(_CODEX_FLOOR_VERSION)
    calls = []

    def _run(argv, **kwargs):
        calls.append(list(argv))
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % below, stderr="")
        raise AssertionError("the exec no-op must not run when the floor gate refuses")

    result = pp.cross_vendor_cli_probe("codex", run=_run)
    assert result["ok"] is False
    assert result["detail"].startswith("codex-cli-too-old:")
    assert calls == [["codex", "--version"]]


def test_cross_vendor_cli_probe_cursor_unaffected_by_codex_floor_gate():
    below = _decrement_version(_CODEX_FLOOR_VERSION)

    def _run(argv, **kwargs):
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % below, stderr="")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    result = pp.cross_vendor_cli_probe("cursor", run=_run)
    assert result["ok"] is True


# bite-axis: composition_liveness refuses every codex cell on a below-floor CLI without ever probing a single cell
def test_composition_liveness_codex_below_floor_all_cells_refused_without_per_cell_probe():
    below = _decrement_version(_CODEX_FLOOR_VERSION)
    calls = []

    def _run(argv, **kwargs):
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % below, stderr="")
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed = {"codex": [_CODEX_LADDER_DEFAULT_CELL, _CODEX_LADDER_ALT_CELL]}
    result = pp.composition_liveness(needed, run=_run)
    info = result["codex"]
    assert info["live"] is False
    for model, _effort in needed["codex"]:
        assert info["models"][model]["ok"] is False
        assert info["models"][model]["detail"].startswith("codex-cli-too-old:")
    for cell in info["cells"]:
        assert cell["ok"] is False
        assert cell["detail"].startswith("codex-cli-too-old:")
    assert calls == []


# bite-axis: live_vendors_for_composition bypasses its own liveness cache the moment the codex CLI drops below floor, refusing without a stale-cached-ready read
def test_live_vendors_for_composition_cache_bypassed_when_codex_cli_drops_below_floor(
    tmp_path, monkeypatch,
):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    model, effort = _CODEX_LADDER_DEFAULT_CELL
    needed_override = {"codex": [(model, effort)]}
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0

    def _at_floor_run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    live, _cells, _liv, _notes, _src, first_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_at_floor_run,
        needed_override=needed_override,
        cache_path=cache_path,
        now=now,
    )
    assert "codex" in live
    assert first_prov["servedFromCache"] is False
    with open(cache_path, encoding="utf-8") as fh:
        receipt_before = fh.read()

    below = _decrement_version(_CODEX_FLOOR_VERSION)

    def _below_floor_run(argv, **kwargs):
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % below, stderr="")
        raise AssertionError("no per-cell probe may run once the codex CLI is below floor")

    live2, _cells2, _liv2, notes2, _src2, second_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_below_floor_run,
        needed_override=needed_override,
        cache_path=cache_path,
        now=now + 1,
    )
    assert "codex" not in live2
    assert second_prov["servedFromCache"] is False
    assert any("codex-cli-too-old" in n.get("reason", "") for n in notes2)
    with open(cache_path, encoding="utf-8") as fh:
        receipt_after = fh.read()
    assert receipt_after == receipt_before


# bite-axis: live_vendors_for_composition samples the codex-CLI-floor boundary EXACTLY ONCE per
# composition and threads that single observation into composition_liveness — a disagreeing
# second `codex --version` reply (a transient flake in either direction between the two probe
# sites) must never be consulted, so a below-floor CLI can never be reported live and an
# above-floor CLI can never have its liveness recomputed from a stale second sample.
def test_live_vendors_for_composition_probes_codex_floor_exactly_once_below_then_would_pass():
    model, effort = _CODEX_LADDER_DEFAULT_CELL
    needed_override = {"codex": [(model, effort)]}
    below = _decrement_version(_CODEX_FLOOR_VERSION)
    version_calls = []

    def _run(argv, **kwargs):
        if list(argv) == ["codex", "--version"]:
            version_calls.append(list(argv))
            if len(version_calls) > 1:
                raise AssertionError(
                    "codex --version must be sampled exactly once per composition"
                )
            return SimpleNamespace(returncode=0, stdout="codex-cli %s\n" % below, stderr="")
        raise AssertionError("no per-cell probe may run once the codex CLI is below floor")

    live, _cells, liveness, _notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run,
        needed_override=needed_override,
    )
    assert "codex" not in live
    assert liveness["codex"]["live"] is False
    assert version_calls == [["codex", "--version"]]


def test_live_vendors_for_composition_single_probe_backs_the_cache_write(tmp_path):
    import liveness_cache

    model, effort = _CODEX_LADDER_DEFAULT_CELL
    needed_override = {"codex": [(model, effort)]}
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0
    version_calls = []

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            version_calls.append(list(argv))
            if len(version_calls) > 1:
                raise AssertionError(
                    "codex --version must be sampled exactly once per composition"
                )
            return at_floor
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    live, _cells, _liv, _notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run,
        needed_override=needed_override,
        cache_path=cache_path,
        now=now,
    )
    assert "codex" in live
    rec = liveness_cache.read(cache_path, now=now)
    assert rec is not None
    assert rec["liveness"]["codex"]["live"] is True
    assert version_calls == [["codex", "--version"]]


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
        "-f", "--sandbox", "enabled")
    seat = seat_bundle.validate_effort_only(
        seat_bundle.parse(json.dumps(
            {"vendor": "cursor", "model": "composer-2.5", "effort": None})),
    )
    assert seat.get("ok"), seat.get("detail", seat.get("reason"))
    builder = engine_adapter.build_argv(seat, "review", {})
    assert "-f" in builder
    assert builder[builder.index("--sandbox") + 1] == "enabled"
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
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
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
    needed = {"codex": [_CODEX_LADDER_DEFAULT_CELL]}
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
    needed = {"codex": [_CODEX_LADDER_DEFAULT_CELL]}
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
    seat = seat_bundle.validate_effort_only(
        seat_bundle.parse(json.dumps(
            {"vendor": "cursor", "model": "composer-2.5", "effort": None})),
    )
    assert seat.get("ok"), seat.get("detail", seat.get("reason"))
    builder = engine_adapter.build_argv(seat, "review", {})
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
    seat = seat_bundle.validate_effort_only(
        seat_bundle.parse(json.dumps(
            {"vendor": "cursor", "model": "cursor-grok-4.6", "effort": "xhigh"})),
    )
    assert seat.get("ok"), seat.get("detail", seat.get("reason"))
    expected = tuple(engine_adapter.build_argv(seat, "review", {}))
    assert argv == expected
    assert argv == (
        "cursor-agent", "--model", "cursor-grok-4.6-xhigh", "-p", "--trust",
        "-f", "--sandbox", "enabled", "--output-format", "stream-json")


def test_model_no_op_argv_cursor_bogus_model_returns_none():
    assert pp.model_no_op_argv("cursor", "bogus-model", "high") is None


def test_model_no_op_argv_codex_effort_none_resolves_from_matrix():
    model, effort = _CODEX_REVIEWER_DEEP_CELL
    argv = pp.model_no_op_argv("codex", model)
    assert argv is not None
    assert ("model_reasoning_effort=%s" % effort) in argv


def test_model_no_op_argv_codex_effort_none_resolves_second_tier(monkeypatch):
    """When the probed model does not match the first `_PROBE_TIERS` entry's matrix cell,
    effort resolution falls through to the second tier's cell."""
    real_matrix_config = MR.matrix_config
    reviewer_model, reviewer_effort = _CODEX_REVIEWER_CELL

    def _fake_matrix_config(role, vendor):
        if vendor == "codex" and role == "reviewer-deep":
            return ("gpt-nope-tier-probe", "xhigh")
        return real_matrix_config(role, vendor)

    monkeypatch.setattr(pp.model_registry, "matrix_config", _fake_matrix_config)
    argv = pp.model_no_op_argv("codex", reviewer_model)
    assert argv is not None
    assert ("model_reasoning_effort=%s" % reviewer_effort) in argv


def test_model_no_op_argv_codex_matches_builder():
    import engine_adapter
    argv = pp.model_no_op_argv("codex", "gpt-5.6-sol", "xhigh")
    seat = seat_bundle.validate_effort_only(
        seat_bundle.parse(json.dumps(
            {"vendor": "codex", "model": "gpt-5.6-sol", "effort": "xhigh"})),
    )
    assert seat.get("ok"), seat.get("detail", seat.get("reason"))
    expected = tuple(engine_adapter.build_argv(seat, "review", {}))
    assert argv == expected
    assert argv[-1] == "-"


def test_model_no_op_argv_codex_bogus_model_returns_none():
    assert pp.model_no_op_argv("codex", "gpt-9-bogus") is None


def test_needed_configs_for_review_tiers_omits_claude():
    configs = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex", "cursor"])
    assert "claude" not in configs
    assert configs["codex"] == [_CODEX_REVIEWER_DEEP_CELL, _CODEX_REVIEWER_CELL]
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
    model_a, effort_a = _CODEX_LADDER_DEFAULT_CELL
    model_b, effort_b = _CODEX_LADDER_ALT_CELL

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        model = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if model == model_a:
            return SimpleNamespace(returncode=1, stdout="", stderr="fail")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    needed = {"codex": [(model_a, effort_a), (model_b, effort_b)]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["codex"]["live"] is False
    assert result["codex"]["models"][model_a]["ok"] is False
    assert result["codex"]["models"][model_b]["ok"] is True


def test_composition_liveness_claude_always_live():
    result = pp.composition_liveness({"claude": []}, run=fake1)
    assert result["claude"] == {"live": True, "models": {}, "cells": []}


def test_composition_liveness_probe_exception_not_live():
    model, effort = _CODEX_LADDER_DEFAULT_CELL
    needed = {"codex": [(model, effort)]}
    result = pp.composition_liveness(needed, run=_raising_run(OSError("boom")))
    assert result["codex"]["live"] is False
    assert result["codex"]["models"][model]["ok"] is False
    assert "boom" in result["codex"]["models"][model]["detail"]


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
    model, effort = _CODEX_LADDER_DEFAULT_CELL

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    needed = {"codex": [(model, effort), ("gpt-9-bogus", "xhigh")]}
    result = pp.composition_liveness(needed, run=_run)
    assert result["codex"]["live"] is False
    assert result["codex"]["models"][model]["ok"] is True
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
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        inp = kwargs.get("input", "")
        captured["input"] = inp
        if not inp.startswith(engine_dispatch.ANTIHIJACK_PREAMBLE):
            return SimpleNamespace(returncode=1, stdout="", stderr="no preamble")
        if argv[-1] != "-":
            return SimpleNamespace(returncode=1, stdout="", stderr="not stdin form")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    model, effort = _CODEX_LADDER_DEFAULT_CELL
    needed = {"codex": [(model, effort)]}
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
        ("model_no_op", pp.model_no_op_argv(
            "codex", _CODEX_LADDER_ALT_CELL[0], _CODEX_LADDER_ALT_CELL[1])),
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
    live, _live_cells, liveness, _notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex", "cursor"], run=fake1)
    assert "claude" in live
    assert liveness["claude"]["live"] is True


def test_live_vendors_for_composition_all_ok_includes_external():
    live, _live_cells, _, _, _, _ = pp.live_vendors_for_composition(["codex", "cursor"], run=fake0)
    assert live == ["claude", "codex", "cursor"]


def test_live_vendors_for_composition_external_failure_excludes_vendor():
    live, _live_cells, _, _, _, _ = pp.live_vendors_for_composition(["codex", "cursor"], run=fake1)
    assert live == ["claude"]


def test_live_vendors_for_composition_returns_six_tuple():
    result = pp.live_vendors_for_composition(["codex"], run=fake0)
    assert len(result) == 6


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

    live, _live_cells, _liv, notes, _src, cache_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run_that_forbids_dispatch("run must not be called on cache hit"),
        cache_path=cache_path,
        now=now + 1,
    )
    assert "codex" in live
    assert any(n.get("constraint") == "preflight-cache" for n in notes)
    assert cache_prov["servedFromCache"] is True
    assert "served from cache" in next(
        n["reason"] for n in notes if n.get("constraint") == "preflight-cache"
    )


def test_live_vendors_for_composition_stamps_configured_ttl_and_refuses_after_env_change(
    tmp_path, monkeypatch,
):
    import liveness_cache

    monkeypatch.setenv(liveness_cache._ENV_TTL, "600")
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 10_000.0

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    live, _, _, _, _, _ = pp.live_vendors_for_composition(
        ["codex"],
        run=_run,
        cache_path=cache_path,
        now=now,
    )
    assert "codex" in live
    with open(cache_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    assert raw["ttl"] == 600

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    assert liveness_cache.read(cache_path, now=now + 700) is None

    monkeypatch.setenv(liveness_cache._ENV_TTL, "100000")
    assert liveness_cache.read(cache_path, now=now + 700) is None


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
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    now = 1000.0
    live, _live_cells, _liv, _notes, _src, cache_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run,
        cache_path=cache_path,
        now=now,
    )
    assert calls
    assert "codex" in live
    rec = liveness_cache.read(cache_path, now=now)
    assert rec is not None
    assert cache_prov["servedFromCache"] is False


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

    _live, _cells, _liv, _notes, cache_hit_src, cache_hit_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run_that_forbids_dispatch(),
        cache_path=cache_path,
        now=now + 1,
    )
    assert cache_hit_src == liveness_cache.LIVE_CELLS_SOURCE_PROBED
    assert cache_hit_prov["servedFromCache"] is True
    assert cache_hit_prov["probedAt"] == now
    assert cache_hit_prov["remainingTtl"] == 3599

    _live, _cells, _liv, _notes, fresh_src, fresh_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=str(tmp_path / "fresh-cache.json"),
        now=now,
    )
    assert fresh_src == liveness_cache.LIVE_CELLS_SOURCE_PROBED
    assert fresh_prov == {
        "servedFromCache": False,
        "probedAt": None,
        "remainingTtl": None,
    }


def test_live_vendors_for_composition_probe_then_reprobe_uses_cache(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex"])
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0

    calls = []

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        calls.append(now)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    _live, _cells, _liv, _notes, _src, first_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run,
        cache_path=cache_path,
        now=now,
    )
    assert first_prov["servedFromCache"] is False
    assert calls

    _live, _cells, _liv, _notes, _src, second_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run_that_forbids_dispatch("run must not be called on cache hit"),
        cache_path=cache_path,
        now=now + 700,
    )
    assert second_prov["servedFromCache"] is True
    assert second_prov["probedAt"] == now
    assert second_prov["remainingTtl"] == 2900


def test_live_vendors_for_composition_provenance_values_in_vocabulary_home(tmp_path, monkeypatch):
    """Every provenance value the producer returns is a member of the vocabulary home."""
    import liveness_cache as lc

    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    vocab = lc.LIVE_CELLS_SOURCES
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
    lc.write(liveness, needed, path=cache_path, now=now)

    provenance_values = []
    _live, _cells, _liv, _notes, cache_hit_src, cache_hit_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=_run_that_forbids_dispatch(),
        cache_path=cache_path,
        now=now + 1,
    )
    provenance_values.append(cache_hit_src)

    _live, _cells, _liv, _notes, fresh_src, fresh_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=str(tmp_path / "fresh-cache.json"),
        now=now,
    )
    provenance_values.append(fresh_src)

    for prov in provenance_values:
        assert prov in vocab
    assert cache_hit_prov["servedFromCache"] is True
    assert fresh_prov["servedFromCache"] is False


def test_live_vendors_for_composition_cache_write_failure_disclosed(tmp_path):
    import liveness_cache

    blocker = tmp_path / "not-a-dir"
    blocker.write_text("blocks mkdir")
    cache_path = str(blocker / "composition-liveness.json")
    live, _live_cells, _liv, notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=cache_path,
        now=1000.0,
    )
    assert "codex" in live
    assert any(n.get("constraint") == "preflight-cache-write-failed" for n in notes)


def test_live_vendors_for_composition_fresh_path_emits_cell_dead_notes():
    model_ok, effort_ok = _CODEX_LADDER_DEFAULT_CELL
    model_dead, effort_dead = _CODEX_LADDER_ALT_CELL

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        model = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if model == model_dead:
            return SimpleNamespace(
                returncode=1, stdout="", stderr="Command timed out after 120 seconds")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed_override = {"codex": [(model_ok, effort_ok), (model_dead, effort_dead)]}
    live, live_cells, _liv, notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"], run=_run, needed_override=needed_override)
    assert "codex" not in live
    assert any(c[1] == model_ok for c in live_cells)
    cell_notes = [n for n in notes if n.get("constraint") == "liveness-cell"]
    assert any(n["model"] == model_dead for n in cell_notes)
    assert any("timed out" in n["reason"] for n in cell_notes)


def test_live_vendors_for_composition_cache_path_emits_cell_dead_notes(tmp_path, monkeypatch):
    import liveness_cache

    monkeypatch.delenv(liveness_cache._ENV_TTL, raising=False)
    model_ok, effort_ok = _CODEX_LADDER_DEFAULT_CELL
    model_dead, effort_dead = _CODEX_LADDER_ALT_CELL
    needed = {"codex": [[model_ok, effort_ok], [model_dead, effort_dead]]}
    liveness = {
        "codex": {
            "live": False,
            "models": {
                model_ok: {"ok": True, "detail": ""},
                model_dead: {"ok": False, "detail": "Command timed out after 120 seconds"},
            },
            "cells": [
                {"model": model_ok, "effort": effort_ok, "ok": True, "detail": ""},
                {"model": model_dead, "effort": effort_dead, "ok": False,
                 "detail": "Command timed out after 120 seconds"},
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    cache_path = str(tmp_path / "composition-liveness.json")
    now = 1000.0
    liveness_cache.write(liveness, needed, path=cache_path, now=now)

    live, live_cells, _liv, notes, _src, cache_prov = pp.live_vendors_for_composition(
        ["codex"],
        run=fake0,
        cache_path=cache_path,
        now=now + 1,
        needed_override={"codex": [(model_ok, effort_ok), (model_dead, effort_dead)]},
    )
    assert "codex" not in live
    assert any(c[1] == model_ok for c in live_cells)
    cell_notes = [n for n in notes if n.get("constraint") == "liveness-cell"]
    assert any(n["model"] == model_dead for n in cell_notes)
    assert any("timed out" in n["reason"] for n in cell_notes)
    assert any("served from cache" in n["reason"] for n in cell_notes)
    assert any("seconds of effective TTL remaining" in n["reason"] for n in cell_notes)
    assert cache_prov["servedFromCache"] is True
    assert cache_prov["remainingTtl"] == 3599


def test_live_vendors_for_composition_cache_served_note_constraint_matches_fresh_probe():
    model_ok, effort_ok = _CODEX_LADDER_DEFAULT_CELL
    model_dead, effort_dead = _CODEX_LADDER_ALT_CELL

    def _run(argv, **kwargs):
        at_floor = _answer_codex_version_at_floor(argv)
        if at_floor is not None:
            return at_floor
        model = argv[argv.index("-m") + 1] if "-m" in argv else ""
        if model == model_dead:
            return SimpleNamespace(
                returncode=1, stdout="", stderr="Command timed out after 120 seconds")
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    needed_override = {"codex": [(model_ok, effort_ok), (model_dead, effort_dead)]}
    _live, _cells, _liv, fresh_notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"], run=_run, needed_override=needed_override)
    fresh_cell_notes = [n for n in fresh_notes if n.get("constraint") == "liveness-cell"]
    assert fresh_cell_notes

    import liveness_cache

    needed = {"codex": [[model_ok, effort_ok], [model_dead, effort_dead]]}
    liveness = {
        "codex": {
            "live": False,
            "models": {
                model_ok: {"ok": True, "detail": ""},
                model_dead: {"ok": False, "detail": "Command timed out after 120 seconds"},
            },
            "cells": [
                {"model": model_ok, "effort": effort_ok, "ok": True, "detail": ""},
                {"model": model_dead, "effort": effort_dead, "ok": False,
                 "detail": "Command timed out after 120 seconds"},
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    cache_path = "/tmp/unused-for-this-test.json"
    now = 1000.0
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        cache_path = td + "/receipt.json"
        assert liveness_cache.write(liveness, needed, path=cache_path, now=now)
        _live, _cells, _liv, cached_notes, _src, _prov = pp.live_vendors_for_composition(
            ["codex"],
            run=fake0,
            cache_path=cache_path,
            now=now + 1,
            needed_override=needed_override,
        )
    cached_cell_notes = [n for n in cached_notes if n.get("constraint") == "liveness-cell"]
    assert len(cached_cell_notes) == len(fresh_cell_notes)
    for cached, fresh in zip(cached_cell_notes, fresh_cell_notes):
        assert cached["constraint"] == fresh["constraint"]
        assert cached["constraint"] == "liveness-cell"
        assert cached["reason"].startswith(fresh["reason"])
        assert "served from cache" in cached["reason"]
        assert "seconds of effective TTL remaining" in cached["reason"]


def test_cli_compose_liveness_writes_receipt(tmp_path, monkeypatch, capsys):
    import liveness_cache

    cache_file = tmp_path / "state" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None, **_kw: {
        "codex": {"live": True, "models": {}, "cells": []},
        "claude": {"live": True, "models": {}, "cells": []},
    })
    monkeypatch.setattr(pp.core_md, "read", lambda *a, **k: {"enginePreferences": {}})

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", str(tmp_path)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "live" in payload
    assert "cachePath" in payload
    assert "cacheProvenance" in payload
    assert payload["cacheProvenance"]["servedFromCache"] is False
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
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None, **_kw: {
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
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None, **_kw: {
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
        return (["claude"], [], {}, [], "probed", {
            "servedFromCache": False,
            "probedAt": None,
            "remainingTtl": None,
        })

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
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None, **_kw: {
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
    monkeypatch.setattr(pp, "composition_liveness", lambda needed, run=None, **_kw: {
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
