"""Behavior tests for the PreCompact compaction_context hook (#911)."""
import importlib.util
import io
import json
import os
import subprocess
import sys

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK_PATH = os.path.join(_PLUGIN, "hooks", "compaction_context.py")


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


def test_showrunner_emits_top_level_additional_context(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_showrunner")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("showrunner")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert "additionalContext" in out
    assert "hookSpecificOutput" not in out
    assert "SHOWRUNNER" in out["additionalContext"]
    ctx = out["additionalContext"]
    assert "Resume-point pointer" in ctx
    assert "Live build lanes" in ctx
    assert "Vet ordinal" in ctx
    assert "Open owner decisions" in ctx
    assert "hard line" in ctx
    assert "Verbatim tool output, file diffs" in ctx


def test_workhorse_emits_top_level_additional_context(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_workhorse")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert "additionalContext" in out
    assert "hookSpecificOutput" not in out
    assert "WORKHORSE" in out["additionalContext"]
    assert "SHOWRUNNER" not in out["additionalContext"]
    ctx = out["additionalContext"]
    assert "Issue number being built" in ctx
    assert "Current work order" in ctx
    assert "Build worktree path and branch name" in ctx
    assert "receipts have been earned" in ctx
    assert "open blocker" in ctx
    assert "Verbatim tool output, file diffs" in ctx


def test_detective_emits_top_level_additional_context(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_detective")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("detective")])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    lines = _stdout_lines(capsys)
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert "additionalContext" in out
    assert "hookSpecificOutput" not in out
    assert "DETECTIVE" in out["additionalContext"]
    assert "SHOWRUNNER" not in out["additionalContext"]
    assert "WORKHORSE" not in out["additionalContext"]
    ctx = out["additionalContext"]
    assert "Incident under diagnosis" in ctx
    assert "Hypotheses already ruled out" in ctx
    assert "Demonstration state" in ctx
    assert "disposable copy" in ctx
    assert "diagnosis budget" in ctx
    assert "examined surface is never edited" in ctx
    assert "Verbatim tool output, file diffs" in ctx


def test_compaction_skeletons_cover_all_charter_names():
    """Skeleton dict keys must match CHARTER_NAMES — fails if detective entry is removed."""
    import charter_detect

    mod = _load_hook("cc_skeleton_roster")
    assert set(mod._COMPACTION_SKELETONS) == set(charter_detect.CHARTER_NAMES)


def test_no_charter_transcript_is_silent(monkeypatch, capsys, tmp_path):
    mod = _load_hook("cc_no_charter")
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {"type": "user", "isSidechain": False, "message": {"role": "user", "content": "hello"}},
    ])
    _stdin(monkeypatch, _precompact_payload(str(path)))
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_missing_transcript_path_is_silent(monkeypatch, capsys):
    mod = _load_hook("cc_missing_path")
    _stdin(monkeypatch, _precompact_payload(None))
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_none_transcript_path_is_silent(monkeypatch, capsys):
    mod = _load_hook("cc_none_path")
    payload = _precompact_payload("/unused")
    payload["transcript_path"] = None
    _stdin(monkeypatch, payload)
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_malformed_stdin_is_silent(monkeypatch, capsys):
    mod = _load_hook("cc_bad_json")
    _stdin(monkeypatch, "not-json{")
    assert mod.main() == 0
    assert _stdout_lines(capsys) == []


def test_subagent_transcript_is_silent(monkeypatch, capsys, tmp_path):
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
    assert _stdout_lines(capsys) == []


def test_subprocess_exit_code_always_zero(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("showrunner")])
    payload = _precompact_payload(str(path))
    r = subprocess.run(
        ["python3", _HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r.returncode == 0

    r2 = subprocess.run(
        ["python3", _HOOK_PATH],
        input="not-json",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r2.returncode == 0
