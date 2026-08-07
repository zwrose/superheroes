import importlib.util
import io
import json
import os
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


def _stdin(monkeypatch, payload):
    if payload is None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    elif isinstance(payload, str):
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    else:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def _stdout_lines(capsys):
    return [ln for ln in capsys.readouterr().out.splitlines() if ln]


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
