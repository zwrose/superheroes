"""Behavior tests for the PreCompact compaction_context hook (#911, #1814): the plain-text fallback."""
import importlib.util
import io
import json
import os
import subprocess
import sys
import time

import pytest

import charter_detect
import compaction_directive

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK_PATH = os.path.join(_PLUGIN, "hooks", "compaction_context.py")


@pytest.fixture(autouse=True)
def _isolated_config_dir(monkeypatch, tmp_path):
    """Checkpoint notes and delivery markers resolve under CLAUDE_CONFIG_DIR — never the real one."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path))


def _marker(session_id, age_seconds=0):
    path = compaction_directive.delivered_marker_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8"):
        pass
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _expected(mode):
    return compaction_directive.DIRECTIVES[mode].rstrip("\n") + "\n"


def _plain_stdout(capsys):
    out = capsys.readouterr().out
    assert not out.lstrip().startswith("{"), "PreCompact stdout must be plain text, not JSON"
    return out


def _load_hook(module_name="compaction_context_under_test"):
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


def _user_charter(charter, *, is_sidechain=False):
    content = (
        "<command-message>superheroes:%s</command-message>\n"
        "<command-name>/superheroes:%s</command-name>\n"
        "<command-args>Issue: #911</command-args>"
    ) % (charter, charter)
    return {
        "type": "user",
        "isSidechain": is_sidechain,
        "userType": "external",
        "message": {"role": "user", "content": content},
    }


def _write_transcript(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _precompact_payload(transcript_path, **extra):
    payload = {
        "session_id": "sess-test",
        "transcript_path": transcript_path,
        "cwd": "/tmp/project",
        "hook_event_name": "PreCompact",
        "trigger": "auto",
        "custom_instructions": "",
    }
    payload.update(extra)
    return payload


def test_showrunner_prints_plain_text_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_showrunner")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("showrunner")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    out = _plain_stdout(capsys)
    assert out == _expected("showrunner")
    assert "additionalContext" not in out
    assert "SHOWRUNNER" in out
    assert "Resume-point pointer" in out
    assert "Live build lanes" in out
    assert "Vet ordinal" in out
    assert "Open owner decisions" in out
    assert "hard line" in out
    assert "Verbatim tool output, file diffs" in out


def test_workhorse_prints_plain_text_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_workhorse")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    out = _plain_stdout(capsys)
    assert "WORKHORSE" in out
    assert "SHOWRUNNER" not in out
    assert "Issue number being built" in out
    assert "build-record section" in out
    assert "Current work order" in out
    assert "Build worktree path and branch name" in out
    assert "receipts have been earned" in out
    assert "open blocker" in out
    assert "Verbatim tool output, file diffs" in out


def test_detective_prints_plain_text_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_detective")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("detective")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    out = _plain_stdout(capsys)
    assert "DETECTIVE" in out
    assert "SHOWRUNNER" not in out
    assert "WORKHORSE" not in out
    assert "Incident under diagnosis" in out
    assert "Hypotheses already ruled out" in out
    assert "Demonstration state" in out
    assert "disposable copy" in out
    assert "diagnosis budget" in out
    assert "examined surface is never edited" in out
    assert "Verbatim tool output, file diffs" in out


def test_discovery_prints_plain_text_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_discovery")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("architect-discovery")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("discovery")


def test_modes_directives_cover_all_charter_names_and_generic():
    """MODES/DIRECTIVES keys must be the charter roster plus generic — fails if a charter is dropped."""
    assert set(compaction_directive.MODES) == set(compaction_directive.DIRECTIVES)
    assert set(compaction_directive.DIRECTIVES) == set(charter_detect.CHARTER_NAMES) | {"generic"}


def test_hook_holds_no_directive_text():
    """The invariant: directive text lives only in lib/compaction_directive.py."""
    mod = _load_hook("cc_no_text")
    assert not hasattr(mod, "_COMPACTION_SKELETONS")
    with open(_HOOK_PATH, encoding="utf-8") as fh:
        assert "PRESERVE" not in fh.read()


def test_fresh_marker_for_same_session_is_silent(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_marker_fresh")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    marker = _marker("sess-test", age_seconds=5)
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []
    # One-shot: the hook consumed the marker, so a retry within the window prints.
    assert not os.path.exists(marker)
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("workhorse")


def test_marker_for_a_different_session_still_prints(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_marker_other")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _marker("some-other-session", age_seconds=5)
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("workhorse")


def test_stale_marker_still_prints(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_marker_stale")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _marker("sess-test", age_seconds=600)
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("workhorse")


def test_missing_session_id_never_suppresses(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_no_session")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _marker("sess-test", age_seconds=1)
    payload = _precompact_payload(str(path))
    del payload["session_id"]
    _stdin(monkeypatch, payload)
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("workhorse")


def test_invalid_session_id_never_suppresses(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_bad_session")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _stdin(monkeypatch, _precompact_payload(str(path), session_id="../sess-test"))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("workhorse")


def test_checkpoint_notes_are_appended_for_this_session(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_notes")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("detective")])
    notes_path = compaction_directive.checkpoint_path("sess-test")
    os.makedirs(os.path.dirname(notes_path), exist_ok=True)
    with open(notes_path, "w", encoding="utf-8") as fh:
        fh.write("- H2 ruled out by the A/B on the copy\n")
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    out = _plain_stdout(capsys)
    assert out.startswith(_expected("detective").rstrip("\n"))
    assert "Checkpoint notes for this session (written " in out
    assert "file %s)" % notes_path in out
    assert "- H2 ruled out by the A/B on the copy" in out


def test_unreadable_notes_still_print_the_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_notes_unreadable")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("detective")])
    os.makedirs(compaction_directive.checkpoint_path("sess-test"))   # a directory, not a file
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("detective")


def test_custom_instructions_are_not_repeated(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_custom")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _stdin(monkeypatch, _precompact_payload(str(path), custom_instructions="OWNER-TEXT-XYZ"))
    assert mod.main() == 0
    out = _plain_stdout(capsys)
    assert "OWNER-TEXT-XYZ" not in out
    assert "owner's own compaction instructions" not in out


def test_no_charter_transcript_prints_generic_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_no_charter")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {"type": "user", "isSidechain": False, "message": {"role": "user", "content": "hello"}},
    ])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("generic")


def test_missing_transcript_path_prints_generic_directive(monkeypatch, capsys):
    mod = _load_hook("cc_missing_path")
    payload = _precompact_payload("/unused")
    del payload["transcript_path"]
    _stdin(monkeypatch, payload)
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("generic")


def test_none_transcript_path_prints_generic_directive(monkeypatch, capsys):
    mod = _load_hook("cc_none_path")
    payload = _precompact_payload("/unused")
    payload["transcript_path"] = None
    _stdin(monkeypatch, payload)
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("generic")


@pytest.mark.parametrize("garbage", ["not-json{", "[1, 2]", "null", '"str"'])
def test_garbage_stdin_is_silent_and_fail_open(monkeypatch, capsys, garbage):
    mod = _load_hook("cc_bad_json")
    _stdin(monkeypatch, garbage)
    assert mod.main() == 0
    assert capsys.readouterr().out == ""


def test_unresolvable_config_dir_still_prints_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_no_cfg")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/dir")
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("workhorse")


def test_subagent_transcript_prints_generic_directive(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_subagent")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {
            "type": "user",
            "isSidechain": True,
            "message": {"role": "user", "content": "do the thing"},
        },
    ])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _plain_stdout(capsys) == _expected("generic")


def test_subprocess_exit_code_always_zero(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("showrunner")])
    payload = _precompact_payload(str(path))
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(tmp_path / "cfg"), HOME=str(tmp_path))
    r = subprocess.run(
        ["python3", _HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert r.returncode == 0
    assert r.stdout == _expected("showrunner")

    r2 = subprocess.run(
        ["python3", _HOOK_PATH],
        input="not-json",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert r2.returncode == 0
