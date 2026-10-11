import base64
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys

import pytest

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK_PATH = os.path.join(_PLUGIN, "hooks", "session_start.py")
_LIB = os.path.join(_PLUGIN, "lib")


def _load_hook(module_name="session_start_under_test"):
    spec = importlib.util.spec_from_file_location(module_name, _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _isolated_reviewer_home(tmp_path, monkeypatch):
    """No hook test may read or write the real reviewer sign-in or see ambient cloud variables."""
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("CODEX_HOME", "CLAUDE_CODE_REMOTE", "SUPERHEROES_REVIEWER_PASS"):
        monkeypatch.delenv(name, raising=False)


def test_every_hook_test_starts_with_the_reviewer_home_isolated(tmp_path):
    assert os.environ["HOME"] == str(tmp_path / "isolated-home")
    assert not any(n in os.environ for n in ("CODEX_HOME", "CLAUDE_CODE_REMOTE",
                                             "SUPERHEROES_REVIEWER_PASS"))


def _stdin(monkeypatch, payload):
    if payload is None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    elif isinstance(payload, str):
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    else:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def _stdout_lines(capsys):
    return [ln for ln in capsys.readouterr().out.splitlines() if ln]


def _context_from_stdout(capsys):
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    return out["hookSpecificOutput"]["additionalContext"]


def _run_startup(monkeypatch, capsys, payload, env_file=None):
    mod = _load_hook("session_start_host_model_%s" % id(payload))
    if env_file is None:
        monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    base = {"source": "startup", "cwd": "/tmp"}
    base.update(payload)
    _stdin(monkeypatch, base)
    rc = mod.main()
    return rc


def _accepted_sources():
    mod = _load_hook("_sources_probe")
    return sorted(mod._SOURCES)


def test_startup_envelope_shape(monkeypatch, capsys):
    # Axis: valid startup payload emits exactly one SessionStart JSON line with non-empty context.
    mod = _load_hook("session_start_envelope")
    _stdin(monkeypatch, {"source": "startup", "cwd": "/tmp"})
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"].strip()


@pytest.mark.parametrize("source", _accepted_sources())
def test_each_accepted_source_produces_output(monkeypatch, capsys, source):
    # Axis: all four documented sources must reach bootstrap, not just startup.
    mod = _load_hook(f"session_start_source_{source}")
    _stdin(monkeypatch, {"source": source, "cwd": "/tmp"})
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"].strip()


def test_unrecognised_source_is_silent(monkeypatch, capsys):
    # Axis: unknown source must not emit stdout — only the recognised gate may bootstrap.
    mod = _load_hook("session_start_unknown_source")
    _stdin(monkeypatch, {"source": "other", "cwd": "/tmp"})
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_missing_source_key_is_silent(monkeypatch, capsys):
    # Axis: payload without source must exit quietly with no bootstrap output.
    mod = _load_hook("session_start_no_source")
    _stdin(monkeypatch, {"cwd": "/tmp"})
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_malformed_stdin_is_silent(monkeypatch, capsys):
    # Axis: invalid JSON on stdin must return 0 without stdout or exception.
    mod = _load_hook("session_start_bad_json")
    _stdin(monkeypatch, "not-json{")
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_empty_stdin_is_silent(monkeypatch, capsys):
    # Axis: empty stdin follows the `or "{}"` path and must not bootstrap.
    mod = _load_hook("session_start_empty_stdin")
    _stdin(monkeypatch, None)
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


@pytest.mark.parametrize("payload", [[], 123])
def test_non_dict_json_payload_is_silent(monkeypatch, capsys, payload):
    # Axis: only dict payloads may proceed — arrays and strings are ignored.
    mod = _load_hook(f"session_start_nondict_{type(payload).__name__}")
    _stdin(monkeypatch, payload)
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_bootstrap_failure_still_emits_breadcrumb(monkeypatch, capsys):
    # Axis: assemble raising must still return 0 and surface the failure breadcrumb in context.
    mod = _load_hook("session_start_bootstrap_fail")
    import session_context

    def boom(*_a, **_k):
        raise RuntimeError("assemble blew up")

    monkeypatch.setattr(session_context, "assemble", boom)
    _stdin(monkeypatch, {"source": "startup", "cwd": "/tmp"})
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "Session bootstrap failed to assemble" in ctx


def test_sweep_stale_exception_is_swallowed(monkeypatch, capsys):
    # Axis: cache sweep failure must not affect exit code or stdout envelope.
    mod = _load_hook("session_start_sweep_fail")
    import cache_markers

    monkeypatch.setattr(
        cache_markers,
        "sweep_stale",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("sweep failed")),
    )
    _stdin(monkeypatch, {"source": "startup", "cwd": "/tmp"})
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_host_flag_reaches_bootstrap(monkeypatch, capsys):
    # Axis: --host argv value must be forwarded into session_context.assemble.
    mod = _load_hook("session_start_host_flag")
    import session_context

    seen = []

    def capture(_cwd, _transcript, _root, host, source=None):
        seen.append(host)
        return "## stub context"

    monkeypatch.setattr(session_context, "assemble", capture)
    monkeypatch.setattr(sys, "argv", ["session_start.py", "--host", "codex"])
    _stdin(monkeypatch, {"source": "startup", "cwd": "/tmp"})
    assert mod.main() == 0
    assert seen == ["codex"]


def _write_charter_transcript(path, charter):
    content = (
        "<command-message>superheroes:%s</command-message>\n"
        "<command-name>/superheroes:%s</command-name>\n"
        "<command-args>Issue: #911</command-args>"
    ) % (charter, charter)
    rec = {
        "type": "user",
        "isSidechain": False,
        "userType": "external",
        "message": {"role": "user", "content": content},
    }
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def test_compact_charter_transcript_injects_recovery_in_hook_output(tmp_path, monkeypatch, capsys):
    # Axis: compact SessionStart with a charter transcript forwards source and emits recovery text.
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    mod = _load_hook("session_start_compact_charter")
    transcript = tmp_path / "transcript.jsonl"
    _write_charter_transcript(transcript, "workhorse")
    skill_path = os.path.join(_PLUGIN, "skills", "workhorse", "SKILL.md")
    _stdin(monkeypatch, {
        "source": "compact",
        "cwd": str(tmp_path),
        "transcript_path": str(transcript),
    })
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "### Charter recovery" in ctx
    assert skill_path in ctx
    assert "file on disk is the authority" in ctx


def test_host_model_string_writes_env_and_context(tmp_path, monkeypatch, capsys):
    # Axis: string model is quoted into CLAUDE_ENV_FILE and named in bootstrap context.
    env_file = tmp_path / "session_env.sh"
    env_file.write_text("", encoding="utf-8")
    model = "claude-opus-5"
    assert _run_startup(monkeypatch, capsys, {"model": model}, env_file=env_file) == 0
    assert env_file.read_text(encoding="utf-8") == (
        "export SUPERHEROES_HOST_MODEL=%s\n" % shlex.quote(model)
    )
    ctx = _context_from_stdout(capsys)
    assert "### Host model" in ctx
    assert "Host model (read from the session-start hook payload): %s" % model in ctx


def test_host_model_absent_writes_empty_env_and_unknown_context(tmp_path, monkeypatch, capsys):
    # Axis: missing model key clears SUPERHEROES_HOST_MODEL and discloses unknown in context.
    env_file = tmp_path / "session_env.sh"
    env_file.write_text("", encoding="utf-8")
    assert _run_startup(monkeypatch, capsys, {}, env_file=env_file) == 0
    assert env_file.read_text(encoding="utf-8") == "export SUPERHEROES_HOST_MODEL=''\n"
    ctx = _context_from_stdout(capsys)
    assert "### Host model" in ctx
    assert "Host model: unknown" in ctx
    assert "seat composition falls back to the claude host's family" in ctx


def test_host_model_stale_reset_clears_via_env_file(tmp_path, monkeypatch, capsys):
    # Axis: model-less start appends empty export so sourcing the file clears a stale value.
    env_file = tmp_path / "session_env.sh"
    env_file.write_text("export SUPERHEROES_HOST_MODEL=claude-opus-5\n", encoding="utf-8")
    assert _run_startup(monkeypatch, capsys, {}, env_file=env_file) == 0
    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines[-1] == "export SUPERHEROES_HOST_MODEL=''"
    proc = subprocess.run(
        ["/bin/sh", "-c", ". %s; printf %%s \"$SUPERHEROES_HOST_MODEL\"" % shlex.quote(str(env_file))],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    _context_from_stdout(capsys)


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-5; rm -rf /",
        {"id": 123},
        {"display_name": "Opus"},
        "",
        " " * 5,
    ],
)
def test_host_model_malformed_or_injection_writes_empty(tmp_path, monkeypatch, capsys, model):
    # Axis: values outside the allowed shape are rejected and written as empty.
    env_file = tmp_path / "session_env.sh"
    env_file.write_text("", encoding="utf-8")
    assert _run_startup(monkeypatch, capsys, {"model": model}, env_file=env_file) == 0
    assert env_file.read_text(encoding="utf-8") == "export SUPERHEROES_HOST_MODEL=''\n"
    ctx = _context_from_stdout(capsys)
    assert "Host model: unknown" in ctx


def test_host_model_dict_id_writes_env_and_context(tmp_path, monkeypatch, capsys):
    # Axis: dict payload with string id uses the id after shape check.
    env_file = tmp_path / "session_env.sh"
    env_file.write_text("", encoding="utf-8")
    model_id = "claude-opus-5[1m]"
    payload_model = {"id": model_id, "display_name": "Opus"}
    assert _run_startup(monkeypatch, capsys, {"model": payload_model}, env_file=env_file) == 0
    assert env_file.read_text(encoding="utf-8") == (
        "export SUPERHEROES_HOST_MODEL=%s\n" % shlex.quote(model_id)
    )
    ctx = _context_from_stdout(capsys)
    assert "Host model (read from the session-start hook payload): %s" % model_id in ctx


def test_host_model_skipped_when_claude_env_file_unset(tmp_path, monkeypatch, capsys):
    # Axis: without CLAUDE_ENV_FILE the hook must not create or touch an env file.
    env_file = tmp_path / "never_created.sh"
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    assert _run_startup(monkeypatch, capsys, {"model": "claude-opus-5"}) == 0
    assert not env_file.exists()
    _context_from_stdout(capsys)


def _pass_fixture(refresh=""):
    """A fixture reviewer pass built at run time: (base64 pass, access token, id token)."""
    def b64u(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def jwt(tag):
        claims = json.dumps({"exp": 4_000_000_000, "sub": tag}).encode()
        return ".".join([b64u(b"head-" + tag.encode()), b64u(claims), b64u(b"sig-" + tag.encode())])

    access, ident = jwt("access"), jwt("ident")
    obj = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
           "tokens": {"id_token": ident, "access_token": access, "refresh_token": refresh,
                      "account_id": "acct-fixture"},
           "last_refresh": "2026-10-10T12:00:00Z"}
    return base64.b64encode(json.dumps(obj).encode()).decode("ascii"), access, ident


def _cloud_session(monkeypatch, tmp_path, cloud=True, pass_value=None):
    """Point HOME at tmp_path and set the cloud variables; returns the default sign-in path."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for name in ("CODEX_HOME", "CLAUDE_CODE_REMOTE", "SUPERHEROES_REVIEWER_PASS"):
        monkeypatch.delenv(name, raising=False)
    if cloud:
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    if pass_value is not None:
        monkeypatch.setenv("SUPERHEROES_REVIEWER_PASS", pass_value)
    return home / ".codex" / "auth.json"


def _raw_and_context(capsys):
    raw = capsys.readouterr().out
    lines = [ln for ln in raw.splitlines() if ln]
    assert len(lines) == 1
    return raw, json.loads(lines[0])["hookSpecificOutput"]["additionalContext"]


def test_reviewer_pass_section_absent_outside_a_cloud_session(tmp_path, monkeypatch, capsys):
    # Axis: outside a cloud session the hook neither writes a sign-in nor adds the section.
    pass_value, _, _ = _pass_fixture()
    dest = _cloud_session(monkeypatch, tmp_path, cloud=False, pass_value=pass_value)
    assert _run_startup(monkeypatch, capsys, {}) == 0
    assert "### Reviewer pass" not in _context_from_stdout(capsys)
    assert not dest.exists()


def test_reviewer_pass_placed_in_a_cloud_session(tmp_path, monkeypatch, capsys):
    # Axis: a cloud session with a pass writes the sign-in file and says so without printing the pass.
    pass_value, access, ident = _pass_fixture()
    dest = _cloud_session(monkeypatch, tmp_path, pass_value=pass_value)
    assert _run_startup(monkeypatch, capsys, {}) == 0
    raw, ctx = _raw_and_context(capsys)
    assert "### Reviewer pass\nThe reviewer pass is in place; it lapses 2096-10-02." in ctx
    assert json.loads(dest.read_text())["tokens"]["access_token"] == access
    for secret in (pass_value, access, ident):
        assert secret not in raw


def test_reviewer_pass_section_says_so_when_the_variable_could_not_be_removed(
        tmp_path, monkeypatch, capsys):
    # Axis: placed but no env file to record the removal, so the section says the pass is still visible.
    pass_value, _, _ = _pass_fixture()
    _cloud_session(monkeypatch, tmp_path, pass_value=pass_value)
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    assert _run_startup(monkeypatch, capsys, {}) == 0
    ctx = _context_from_stdout(capsys)
    assert "The reviewer pass is in place; it lapses 2096-10-02." in ctx
    assert "still visible to processes in this session" in ctx


def test_reviewer_pass_section_says_none_is_set(tmp_path, monkeypatch, capsys):
    # Axis: a cloud session with no pass tells the agent review seats cannot run.
    dest = _cloud_session(monkeypatch, tmp_path)
    assert _run_startup(monkeypatch, capsys, {}) == 0
    ctx = _context_from_stdout(capsys)
    assert "### Reviewer pass\nNo reviewer pass is set in this cloud environment" in ctx
    assert not dest.exists()


def test_reviewer_pass_section_names_the_refusal_reason_only(tmp_path, monkeypatch, capsys):
    # Axis: a pass that can renew is refused, and the section names the reason token only.
    renewal = "renewal-fixture-key"
    pass_value, _, _ = _pass_fixture(refresh=renewal)
    dest = _cloud_session(monkeypatch, tmp_path, pass_value=pass_value)
    assert _run_startup(monkeypatch, capsys, {}) == 0
    raw, ctx = _raw_and_context(capsys)
    assert "The reviewer pass could not be placed (pass-can-renew)" in ctx
    assert renewal not in raw and pass_value not in raw
    assert not dest.exists()


def test_reviewer_pass_call_raising_never_fails_the_hook(tmp_path, monkeypatch, capsys):
    # Axis: an exception from place is swallowed and named by type only, in a cloud session.
    _cloud_session(monkeypatch, tmp_path)
    import cloud_pass

    def boom(*_a, **_k):
        raise RuntimeError("secret message")

    monkeypatch.setattr(cloud_pass, "place", boom)
    env_file = tmp_path / "env-file"
    assert _run_startup(monkeypatch, capsys, {}, env_file=env_file) == 0
    assert "unset SUPERHEROES_REVIEWER_PASS" in env_file.read_text().splitlines()
    raw, ctx = _raw_and_context(capsys)
    assert "The reviewer pass could not be placed (RuntimeError)" in ctx
    assert "secret message" not in raw


def test_reviewer_pass_leaves_later_shells_as_a_marker_only(tmp_path, monkeypatch, capsys):
    # Axis: after placement the env file unsets the pass variable and exports only its SHA-256.
    import hashlib
    pass_value, _, _ = _pass_fixture()
    dest = _cloud_session(monkeypatch, tmp_path, pass_value=pass_value)
    env_file = tmp_path / "env-file"
    assert _run_startup(monkeypatch, capsys, {}, env_file=env_file) == 0
    lines = env_file.read_text().splitlines()
    marker = hashlib.sha256(dest.read_bytes()).hexdigest()
    assert "unset SUPERHEROES_REVIEWER_PASS" in lines
    assert "export SUPERHEROES_REVIEWER_PASS_SHA256=%s" % marker in lines
    assert pass_value not in env_file.read_text()


def test_reviewer_pass_env_file_untouched_when_nothing_was_placed(tmp_path, monkeypatch, capsys):
    # Axis: a refused placement still unsets the pass in later shells but exports no marker.
    pass_value, _, _ = _pass_fixture(refresh="renewal-fixture-key")
    _cloud_session(monkeypatch, tmp_path, pass_value=pass_value)
    env_file = tmp_path / "env-file"
    assert _run_startup(monkeypatch, capsys, {}, env_file=env_file) == 0
    lines = env_file.read_text().splitlines()
    assert "unset SUPERHEROES_REVIEWER_PASS" in lines
    assert not any("PASS_SHA256" in line for line in lines)
