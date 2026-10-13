"""Behavior tests for lib/compaction_directive.py — the one home of compaction directives (#1814)."""
import json
import os
import subprocess
import sys
import threading
import time

import pytest

import charter_detect
import compaction_directive as cd

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_LIB, "compaction_directive.py")

SID = "sess-abc_123"


def _env(tmp_path):
    return {"HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}


def _touch(path, mtime=None, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _charter_record(command):
    return {
        "type": "user",
        "isSidechain": False,
        "message": {"role": "user", "content": (
            "<command-message>superheroes:%s</command-message>\n"
            "<command-name>/superheroes:%s</command-name>" % (command, command))},
    }


def _write_transcript(path, records):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _run(tmp_path, *args):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
           "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}
    r = subprocess.run([sys.executable, "-B", _SCRIPT] + list(args), env=env,
                       capture_output=True, text=True, timeout=20, cwd=str(tmp_path))
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r


# ---------------------------------------------------------------- roster
def test_modes_equal_directive_keys():
    assert set(cd.MODES) == set(cd.DIRECTIVES)
    assert len(cd.MODES) == len(set(cd.MODES)) == 5


def test_modes_cover_every_charter_name_plus_generic():
    assert set(cd.MODES) == set(charter_detect.CHARTER_NAMES) | {"generic"}


@pytest.mark.parametrize("mode", cd.MODES)
def test_every_mode_drops_raw_artifacts(mode):
    assert "DROP" in cd.DIRECTIVES[mode]
    assert "Verbatim tool output, file diffs, probe transcripts, and command stdout" in cd.DIRECTIVES[mode]


_REQUIRED = {
    "showrunner": ["Resume-point pointer", "Live build lanes", "Vet ordinal",
                   "Open owner decisions", "standing owner ruling"],
    "workhorse": ["Issue number being built", "The open PR and its build record",
                  "the PR body's build-record section", "durable record",
                  "Current work order and its scope fence", "Build worktree path and branch name",
                  "earned versus still owed", "open blocker or park"],
    "detective": ["the incident issue is the durable record", "Hypotheses already ruled out",
                  "what ruled each one out", "Demonstration state", "disposable copy",
                  "Named diagnosis budget and how much of it is spent",
                  "examined surface is never edited"],
    "discovery": ["work item slug", "path of the spec draft", "Requirements agreed with the owner",
                  "unhappy paths", "Open questions still owed to the owner",
                  "where the owner's approval stands"],
    "generic": ["notes on the important things to preserve, especially your role and responsibilities",
                "The task in progress and its state", "Decisions made, and by whom",
                "What is waiting on the owner", "short recap of \"where we are and what you need from me\""],
}


@pytest.mark.parametrize("mode", cd.MODES)
def test_each_mode_carries_its_required_items(mode):
    text = cd.DIRECTIVES[mode]
    for phrase in _REQUIRED[mode]:
        assert phrase.lower() in text.lower(), (mode, phrase)


def test_directives_are_plain_text_not_json():
    for text in cd.DIRECTIVES.values():
        assert not text.lstrip().startswith(("{", "["))


# ---------------------------------------------------------------- detect_mode
def test_detect_mode_returns_detected_charter(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_transcript(path, [_charter_record("workhorse")])
    assert cd.detect_mode(str(path)) == "workhorse"


def test_detect_mode_generic_when_no_charter(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_transcript(path, [{"type": "user", "message": {"role": "user", "content": "hi"}}])
    assert cd.detect_mode(str(path)) == "generic"


@pytest.mark.parametrize("bad", [None, "", "/nonexistent/t.jsonl", 42])
def test_detect_mode_generic_when_transcript_missing_or_garbage(bad):
    assert cd.detect_mode(bad) == "generic"


# ---------------------------------------------------------------- paths
def test_checkpoint_paths_live_under_config_dir(tmp_path):
    env = _env(tmp_path)
    base = os.path.join(str(tmp_path / "cfg"), "superheroes", "checkpoints")
    assert cd.checkpoint_dir(env) == base
    assert cd.checkpoint_path(SID, env) == os.path.join(base, SID + ".md")
    assert cd.delivered_marker_path(SID, env) == os.path.join(base, SID + ".delivered")


@pytest.mark.parametrize("bad", ["../x", "", "a" * 129, "a/b", "a b", "x\n", "..", ".hidden", None, 7])
def test_invalid_session_id_gets_no_path(tmp_path, bad):
    env = _env(tmp_path)
    assert cd.checkpoint_path(bad, env) is None
    assert cd.delivered_marker_path(bad, env) is None


def test_session_id_at_the_length_limit_is_valid(tmp_path):
    env = _env(tmp_path)
    assert cd.checkpoint_path("a" * 128, env) is not None
    assert cd.checkpoint_path("a" * 129, env) is None


def test_unresolvable_config_dir_yields_none(tmp_path):
    env = {"CLAUDE_CONFIG_DIR": "relative/dir", "HOME": str(tmp_path)}
    assert cd.checkpoint_dir(env) is None
    assert cd.checkpoint_path(SID, env) is None
    assert cd.delivered_marker_path(SID, env) is None
    assert cd.find_transcript(SID, env) is None


def test_find_transcript_returns_existing_match(tmp_path):
    env = _env(tmp_path)
    assert cd.find_transcript(SID, env) is None
    hit = tmp_path / "cfg" / "projects" / "-proj-a" / (SID + ".jsonl")
    _touch(str(hit))
    assert cd.find_transcript(SID, env) == str(hit)
    assert cd.find_transcript("other", env) is None
    assert cd.find_transcript("../x", env) is None


# ------------------------------------- a relative CLAUDE_CONFIG_DIR resolves against the session cwd
def _rel_env(tmp_path):
    return {"HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": "cfg"}


def _session_and_elsewhere(tmp_path, monkeypatch):
    """A session cwd that is NOT the process cwd; returns (session cwd, its checkpoint dir)."""
    session = tmp_path / "session"
    elsewhere = tmp_path / "elsewhere"
    session.mkdir()
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return str(session), os.path.join(str(session), "cfg", "superheroes", "checkpoints")


def test_relative_override_resolves_against_session_cwd(tmp_path, monkeypatch):
    session, base = _session_and_elsewhere(tmp_path, monkeypatch)
    env = _rel_env(tmp_path)
    assert cd.checkpoint_dir(env, cwd=session) == base
    assert cd.checkpoint_path(SID, env, cwd=session) == os.path.join(base, SID + ".md")
    assert cd.delivered_marker_path(SID, env, cwd=session) == os.path.join(base, SID + ".delivered")


def test_relative_override_notes_and_marker_land_under_session_cwd(tmp_path, monkeypatch):
    session, base = _session_and_elsewhere(tmp_path, monkeypatch)
    env = _rel_env(tmp_path)
    notes = cd.save_notes(SID, "keep this", env, cwd=session)
    marker = cd.mark_delivered(SID, env, cwd=session)
    assert notes == os.path.join(base, SID + ".md") and os.path.isfile(notes)
    assert marker == os.path.join(base, SID + ".delivered") and os.path.isfile(marker)
    assert cd.read_notes(SID, env, cwd=session)[0] == "keep this"
    assert cd.read_notes(SID, env)[0] == ""            # no cwd: today's behaviour, unresolvable
    assert cd.delivered_recently(SID, env, cwd=session) is True
    assert cd.delivered_recently(SID, env) is False
    assert cd.consume_delivered(SID, env, cwd=session) is True
    assert not os.path.exists(marker)
    assert not os.path.exists(os.path.join(os.getcwd(), "cfg"))


def test_relative_override_find_transcript_uses_session_cwd(tmp_path, monkeypatch):
    session, _ = _session_and_elsewhere(tmp_path, monkeypatch)
    env = _rel_env(tmp_path)
    hit = os.path.join(session, "cfg", "projects", "-proj-a", SID + ".jsonl")
    _touch(hit)
    assert cd.find_transcript(SID, env, cwd=session) == hit
    assert cd.find_transcript(SID, env) is None


def test_absolute_override_ignores_session_cwd(tmp_path, monkeypatch):
    session, _ = _session_and_elsewhere(tmp_path, monkeypatch)
    env = _env(tmp_path)
    base = os.path.join(str(tmp_path / "cfg"), "superheroes", "checkpoints")
    assert cd.checkpoint_dir(env, cwd=session) == base == cd.checkpoint_dir(env)
    assert cd.checkpoint_path(SID, env, cwd=session) == cd.checkpoint_path(SID, env)


@pytest.mark.parametrize("cwd", [None, "", "session", "./session", 7])
def test_relative_override_with_unusable_cwd_yields_none(tmp_path, cwd):
    env = _rel_env(tmp_path)
    assert cd.checkpoint_dir(env, cwd=cwd) is None
    assert cd.checkpoint_path(SID, env, cwd=cwd) is None
    assert cd.delivered_marker_path(SID, env, cwd=cwd) is None
    assert cd.find_transcript(SID, env, cwd=cwd) is None
    assert cd.save_notes(SID, "x", env, cwd=cwd) is None
    assert cd.mark_delivered(SID, env, cwd=cwd) is None


# ---------------------------------------------------------------- read_notes
def test_read_notes_absent_is_empty(tmp_path):
    assert cd.read_notes(SID, _env(tmp_path)) == ("", None)
    assert cd.read_notes("../x", _env(tmp_path)) == ("", None)


def test_read_notes_returns_text_and_mtime(tmp_path):
    env = _env(tmp_path)
    _touch(cd.checkpoint_path(SID, env), mtime=1_700_000_000, text="- decided X\n")
    text, mtime = cd.read_notes(SID, env)
    assert text == "- decided X\n"
    assert mtime == 1_700_000_000


def test_read_notes_truncates_with_trailing_pointer_line(tmp_path):
    env = _env(tmp_path)
    path = cd.checkpoint_path(SID, env)
    _touch(path, text="Q" * 25000)
    text, _ = cd.read_notes(SID, env)
    last = text.splitlines()[-1]
    assert last == "…(checkpoint notes truncated at 20000 characters — full file at %s)" % path
    assert text.count("Q") == 20000


def test_read_notes_under_limit_is_untruncated(tmp_path):
    env = _env(tmp_path)
    _touch(cd.checkpoint_path(SID, env), text="n" * 20000)
    text, _ = cd.read_notes(SID, env)
    assert "truncated" not in text


def test_read_notes_unreadable_is_empty(tmp_path):
    env = _env(tmp_path)
    path = cd.checkpoint_path(SID, env)
    os.makedirs(path)          # a directory where the file should be: open() fails
    assert cd.read_notes(SID, env) == ("", None)


# ---------------------------------------------------------------- compose
def test_compose_bare_directive_has_no_extra_sections():
    out = cd.compose("workhorse")
    assert out.startswith(cd.DIRECTIVES["workhorse"].rstrip("\n"))
    assert "Checkpoint notes for this session" not in out
    assert "The owner's own compaction instructions" not in out


def test_compose_unknown_mode_is_generic():
    assert cd.compose("nonsense").startswith(cd.DIRECTIVES["generic"].rstrip("\n"))


def test_compose_notes_section_has_iso_mtime_and_path():
    out = cd.compose("detective", notes="- ruled out H1", notes_path="/c/s.md",
                     notes_mtime=1_700_000_000)
    assert ("Checkpoint notes for this session (written 2023-11-14T22:13:20Z, file /c/s.md) "
            "— preserve their substance:\n- ruled out H1") in out
    assert out.index(cd.DIRECTIVES["detective"].rstrip("\n")) < out.index("Checkpoint notes")


def test_compose_owner_section_follows_notes():
    out = cd.compose("generic", notes="n", notes_path="/p", notes_mtime=0,
                     user_instructions="focus on the API")
    header = "The owner's own compaction instructions (take precedence where they conflict):"
    assert header + "\nfocus on the API" in out
    assert out.index("Checkpoint notes") < out.index(header)


@pytest.mark.parametrize("empty", [None, "", "   \n"])
def test_compose_empty_user_instructions_adds_no_owner_section(empty):
    assert "owner's own compaction instructions" not in cd.compose("generic", user_instructions=empty)


def test_compose_empty_notes_adds_no_notes_section():
    assert "Checkpoint notes for this session" not in cd.compose("generic", notes="")


def test_compose_is_pure():
    assert cd.compose("showrunner", "n", "/p", 5, "u") == cd.compose("showrunner", "n", "/p", 5, "u")


# ---------------------------------------------------------------- delivered_recently
def test_delivered_recently_true_for_fresh_marker(tmp_path):
    env = _env(tmp_path)
    _touch(cd.delivered_marker_path(SID, env), mtime=1000)
    assert cd.delivered_recently(SID, env, now=1060) is True


def test_consume_delivered_is_one_shot(tmp_path):
    env = _env(tmp_path)
    marker = cd.delivered_marker_path(SID, env)
    _touch(marker, mtime=1000)
    assert cd.consume_delivered(SID, env, now=1060) is True
    assert not os.path.exists(marker)
    assert cd.consume_delivered(SID, env, now=1061) is False


def test_delivered_recently_false_without_marker(tmp_path):
    assert cd.delivered_recently(SID, _env(tmp_path), now=1000) is False


def test_delivered_recently_false_for_stale_marker(tmp_path):
    env = _env(tmp_path)
    _touch(cd.delivered_marker_path(SID, env), mtime=1000)
    assert cd.delivered_recently(SID, env, now=1121) is False
    assert cd.delivered_recently(SID, env, now=1120) is True
    assert cd.delivered_recently(SID, env, window_seconds=10, now=1060) is False


def test_delivered_recently_false_for_another_sessions_marker(tmp_path):
    env = _env(tmp_path)
    _touch(cd.delivered_marker_path("other-session", env), mtime=1000)
    assert cd.delivered_recently(SID, env, now=1001) is False


@pytest.mark.parametrize("bad", ["../x", "", None])
def test_delivered_recently_false_for_invalid_session_id(tmp_path, bad):
    env = _env(tmp_path)
    _touch(os.path.join(str(tmp_path / "cfg"), "superheroes", "checkpoints", ".delivered"), mtime=1000)
    assert cd.delivered_recently(bad, env, now=1001) is False


def test_delivered_recently_defaults_to_wall_clock(tmp_path):
    env = _env(tmp_path)
    _touch(cd.delivered_marker_path(SID, env))
    assert cd.delivered_recently(SID, env) is True


def test_delivered_recently_false_when_config_dir_unresolved(tmp_path):
    assert cd.delivered_recently(SID, {"CLAUDE_CONFIG_DIR": "rel", "HOME": str(tmp_path)}) is False


# ---------------------------------------------------------------- CLI
def test_cli_path_verb(tmp_path):
    code, out, _ = _run(tmp_path, "path", "--session-id", SID)
    base = os.path.join(str(tmp_path / "cfg"), "superheroes", "checkpoints")
    assert code == 0
    assert out == {"ok": True, "path": os.path.join(base, SID + ".md"),
                   "markerPath": os.path.join(base, SID + ".delivered")}


@pytest.mark.parametrize("verb", ["path", "instructions"])
@pytest.mark.parametrize("bad", ["../x", "a" * 129, ""])
def test_cli_refuses_invalid_session_id(tmp_path, verb, bad):
    code, out, _ = _run(tmp_path, verb, "--session-id", bad)
    assert code == 1
    assert out == {"ok": False, "reason": "session-id-invalid"}


@pytest.mark.parametrize("verb", ["path", "instructions"])
def test_cli_refuses_when_config_dir_unresolved(tmp_path, verb):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": "relative/home"}   # no override, HOME not absolute
    r = subprocess.run([sys.executable, "-B", _SCRIPT, verb, "--session-id", SID], env=env,
                       capture_output=True, text=True, timeout=20, cwd=str(tmp_path))
    assert r.returncode == 1
    assert json.loads(r.stdout) == {"ok": False, "reason": "config-dir-unresolved"}


def test_cli_mode_verb(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_transcript(path, [_charter_record("architect-discovery")])
    code, out, _ = _run(tmp_path, "mode", "--transcript", str(path))
    assert (code, out) == (0, {"ok": True, "mode": "discovery"})
    code, out, _ = _run(tmp_path, "mode", "--transcript", str(tmp_path / "missing.jsonl"))
    assert (code, out) == (0, {"ok": True, "mode": "generic"})


def test_cli_instructions_with_transcript_and_notes(tmp_path):
    env = _env(tmp_path)
    notes_path = cd.checkpoint_path(SID, env)
    _touch(notes_path, mtime=1_700_000_000, text="- PR 12 is the record\n")
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, [_charter_record("workhorse")])
    code, out, _ = _run(tmp_path, "instructions", "--session-id", SID, "--transcript", str(transcript),
                        "--user-instructions", "keep the API names")
    assert code == 0
    assert out["ok"] is True and out["mode"] == "workhorse"
    assert out["notesPath"] == notes_path and out["notesFound"] is True
    assert out["markerPath"] == cd.delivered_marker_path(SID, env)
    assert out["instructions"] == cd.compose("workhorse", "- PR 12 is the record\n", notes_path,
                                             1_700_000_000, "keep the API names")


def test_cli_instructions_without_notes_or_transcript_is_generic(tmp_path):
    code, out, _ = _run(tmp_path, "instructions", "--session-id", SID)
    assert code == 0
    assert out["mode"] == "generic" and out["notesFound"] is False
    assert out["instructions"] == cd.compose("generic")
    assert "owner's own compaction instructions" not in out["instructions"]


def test_cli_instructions_falls_back_to_find_transcript(tmp_path):
    _write_transcript(tmp_path / "cfg" / "projects" / "-p" / (SID + ".jsonl"),
                      [_charter_record("detective")])
    code, out, _ = _run(tmp_path, "instructions", "--session-id", SID)
    assert code == 0 and out["mode"] == "detective"


def test_cli_instructions_empty_user_instructions_adds_no_owner_section(tmp_path):
    code, out, _ = _run(tmp_path, "instructions", "--session-id", SID, "--user-instructions", "")
    assert code == 0
    assert "owner's own compaction instructions" not in out["instructions"]


def test_cli_user_instructions_starting_with_dash_is_one_value(tmp_path):
    code, out, _ = _run(tmp_path, "instructions", "--session-id", SID,
                        "--user-instructions", "--keep everything -v")
    assert code == 0
    assert "--keep everything -v" in out["instructions"]


def test_cli_usage_error_exits_nonzero_without_json(tmp_path):
    code, out, r = _run(tmp_path, "path")
    assert code == 2 and out is None and r.stderr


# ------------------------------------------- the mod's CLI + file handoff, for real (#1814)
_PLUGIN_ROOT = os.path.dirname(_LIB)
_MOD_SOURCE = os.path.join(_PLUGIN_ROOT, "hooks", "mod", "argv.ts")
_FALLBACK_HOOK = os.path.join(_PLUGIN_ROOT, "hooks", "compaction_context.py")


def _run_stdin(tmp_path, stdin, *args):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
           "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}
    r = subprocess.run([sys.executable, "-B", _SCRIPT] + list(args), env=env, input=stdin,
                       capture_output=True, text=True, timeout=20, cwd=str(tmp_path))
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None)


def test_mod_script_path_template_resolves_to_this_script():
    # the mod (hooks/mod/argv.ts) builds `${pluginRoot}/lib/compaction_directive.py`; the mod tests stub the
    # process, so this is the check that the suffix lands on the real file under the plugin root
    with open(_MOD_SOURCE, encoding="utf-8") as fh:
        source = fh.read()
    assert "`${pluginRoot}/lib/compaction_directive.py`" in source
    assert os.path.samefile(os.path.join(_PLUGIN_ROOT, "lib", "compaction_directive.py"), _SCRIPT)


def test_mod_roundtrip_saved_notes_reach_compaction_then_fallback_defers(tmp_path):
    env = _env(tmp_path)
    notes = "## Checkpoint notes\nMode: workhorse\n- PR 12 is the record\n"
    # turn.complete: the mod hands the block body to `save` on stdin
    code, out = _run_stdin(tmp_path, notes, "save", "--session-id", SID)
    assert code == 0 and out == {"ok": True, "path": cd.checkpoint_path(SID, env)}
    with open(out["path"], encoding="utf-8") as fh:
        assert fh.read() == notes
    # session.compact: the mod asks for the instructions with the owner's text
    code, out, _ = _run(tmp_path, "instructions", "--session-id", SID,
                        "--user-instructions", "keep the API names")
    assert code == 0 and out["notesFound"] is True
    assert "PR 12 is the record" in out["instructions"]
    assert "keep the API names" in out["instructions"]
    # ... and publishes the delivered marker through the `mark` verb, as the mod does
    code, marked, _ = _run(tmp_path, "mark", "--session-id", SID)
    assert code == 0 and marked["path"] == out["markerPath"]
    # PreCompact fallback hook, same session: it consumes the marker and prints nothing
    hook_env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
                "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}
    first = subprocess.run([sys.executable, "-B", _FALLBACK_HOOK], env=hook_env,
                           input=json.dumps({"session_id": SID}), capture_output=True,
                           text=True, timeout=20, cwd=str(tmp_path))
    assert first.returncode == 0 and first.stdout == ""
    assert not os.path.exists(out["markerPath"])
    # the marker is single-use: a second compaction falls back to the hook's own text
    second = subprocess.run([sys.executable, "-B", _FALLBACK_HOOK], env=hook_env,
                            input=json.dumps({"session_id": SID}), capture_output=True,
                            text=True, timeout=20, cwd=str(tmp_path))
    assert second.returncode == 0 and "PR 12 is the record" in second.stdout


def test_cli_save_refuses_empty_notes_and_keeps_the_last_good_ones(tmp_path):
    env = _env(tmp_path)
    assert _run_stdin(tmp_path, "good notes\n", "save", "--session-id", SID)[0] == 0
    code, out = _run_stdin(tmp_path, "  \n", "save", "--session-id", SID)
    assert (code, out) == (1, {"ok": False, "reason": "empty-notes"})
    with open(cd.checkpoint_path(SID, env), encoding="utf-8") as fh:
        assert fh.read() == "good notes\n"


def test_cli_save_refuses_invalid_session_id(tmp_path):
    code, out = _run_stdin(tmp_path, "notes", "save", "--session-id", "../x")
    assert (code, out) == (1, {"ok": False, "reason": "session-id-invalid"})


def test_save_notes_failure_leaves_the_previous_notes_and_no_temp_file(tmp_path, monkeypatch):
    env = _env(tmp_path)
    cd.save_notes(SID, "old notes\n", env)

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(cd.os, "replace", boom)
    with pytest.raises(OSError):
        cd.save_notes(SID, "new notes\n", env)
    directory = os.path.dirname(cd.checkpoint_path(SID, env))
    assert sorted(os.listdir(directory)) == [".lock", SID + ".md"]
    with open(cd.checkpoint_path(SID, env), encoding="utf-8") as fh:
        assert fh.read() == "old notes\n"


def test_cli_mark_publishes_a_complete_marker_atomically(tmp_path):
    env = _env(tmp_path)
    code, out, _ = _run(tmp_path, "mark", "--session-id", SID)
    assert code == 0 and out == {"ok": True, "path": cd.delivered_marker_path(SID, env)}
    with open(out["path"], encoding="utf-8") as fh:
        assert fh.read().isdigit()
    assert cd.delivered_recently(SID, env) is True
    assert not [n for n in os.listdir(os.path.dirname(out["path"])) if n.endswith(".tmp")]


def test_cli_mark_failed_write_leaves_no_marker(tmp_path, monkeypatch):
    env = _env(tmp_path)

    def boom(_fd, _mode, *a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cd.os, "fdopen", boom)
    with pytest.raises(OSError):
        cd.mark_delivered(SID, env)
    marker = cd.delivered_marker_path(SID, env)
    assert not os.path.exists(marker)
    assert not [n for n in os.listdir(os.path.dirname(marker)) if n.endswith(".tmp")]


def test_cli_mark_refuses_an_invalid_session_id(tmp_path):
    code, out, _ = _run(tmp_path, "mark", "--session-id", "../x")
    assert code == 1 and out == {"ok": False, "reason": "session-id-invalid"}


# ------------------------------------- the CLI resolves a relative override against its process cwd
def _run_in(cwd, env_extra, *args, stdin=None):
    env = {"PATH": os.environ.get("PATH", "")}
    env.update(env_extra)
    r = subprocess.run([sys.executable, "-B", _SCRIPT] + list(args), env=env, input=stdin,
                       capture_output=True, text=True, timeout=20, cwd=str(cwd))
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r


def test_cli_relative_override_resolves_under_process_cwd(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    env = _rel_env(tmp_path)
    base = os.path.join(str(session), "cfg", "superheroes", "checkpoints")
    code, out, _ = _run_in(session, env, "path", "--session-id", SID)
    assert code == 0
    assert out == {"ok": True, "path": os.path.join(base, SID + ".md"),
                   "markerPath": os.path.join(base, SID + ".delivered")}
    code, saved, _ = _run_in(session, env, "save", "--session-id", SID, stdin="cli notes")
    assert code == 0 and saved == {"ok": True, "path": os.path.join(base, SID + ".md")}
    code, marked, _ = _run_in(session, env, "mark", "--session-id", SID)
    assert code == 0 and marked == {"ok": True, "path": os.path.join(base, SID + ".delivered")}
    code, out, _ = _run_in(session, env, "instructions", "--session-id", SID)
    assert code == 0 and out["notesFound"] is True
    assert out["notesPath"] == os.path.join(base, SID + ".md")
    assert out["markerPath"] == os.path.join(base, SID + ".delivered")
    assert not os.path.exists(str(tmp_path / "cfg"))


def test_cli_absolute_override_unaffected_by_process_cwd(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    base = os.path.join(str(tmp_path / "cfg"), "superheroes", "checkpoints")
    code, out, _ = _run_in(session, {"HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")},
                           "path", "--session-id", SID)
    assert code == 0 and out["path"] == os.path.join(base, SID + ".md")


# ---------------------------------------------------------------- unmark_attempt
def _stamped(tmp_path, now_seconds, sid=SID):
    env = _env(tmp_path)
    path = cd.mark_delivered(sid, env, now=now_seconds)
    return env, path


def test_unmark_in_window_removes_the_marker_including_both_ends(tmp_path):
    env, path = _stamped(tmp_path, 1000)
    assert cd.unmark_attempt(SID, 999000, 1001000, env) is True
    assert not os.path.exists(path)
    for since, until in ((1000000, 1000000), (1000000, 2000000), (0, 1000000)):
        cd.mark_delivered(SID, env, now=1000)
        assert cd.unmark_attempt(SID, since, until, env) is True
        assert not os.path.exists(path)


@pytest.mark.parametrize("since,until", [(1000001, 2000000), (0, 999999), (2000000, 3000000)])
def test_unmark_out_of_window_keeps_the_marker(tmp_path, since, until):
    env, path = _stamped(tmp_path, 1000)
    assert cd.unmark_attempt(SID, since, until, env) is False
    assert os.path.exists(path)


def test_unmark_missing_marker_is_false(tmp_path):
    assert cd.unmark_attempt(SID, 0, 10 ** 15, _env(tmp_path)) is False


@pytest.mark.parametrize("content", ["", "not a number", "12.5", "\x00\x01"])
def test_unmark_garbage_content_keeps_the_marker(tmp_path, content):
    env = _env(tmp_path)
    path = cd.delivered_marker_path(SID, env)
    _touch(path, text=content)
    assert cd.unmark_attempt(SID, 0, 10 ** 15, env) is False
    assert os.path.exists(path)


def test_unmark_leaves_another_sessions_marker(tmp_path):
    env, other = _stamped(tmp_path, 1000, sid="other-session")
    assert cd.unmark_attempt(SID, 0, 10 ** 15, env) is False
    assert os.path.exists(other)


@pytest.mark.parametrize("bad", ["../x", "", None])
def test_unmark_invalid_session_id_is_false(tmp_path, bad):
    assert cd.unmark_attempt(bad, 0, 10 ** 15, _env(tmp_path)) is False


def test_unmark_unresolved_config_dir_is_false(tmp_path):
    assert cd.unmark_attempt(SID, 0, 10 ** 15, {"CLAUDE_CONFIG_DIR": "rel", "HOME": str(tmp_path)}) is False


def test_cli_unmark_verb_removes_in_window_and_answers_ok_otherwise(tmp_path):
    env = _env(tmp_path)
    path = cd.mark_delivered(SID, env, now=1000)
    code, out, _ = _run(tmp_path, "unmark", "--session-id", SID, "--since", "0", "--until", "999999")
    assert (code, out) == (0, {"ok": True, "removed": False})
    assert os.path.exists(path)
    code, out, _ = _run(tmp_path, "unmark", "--session-id", SID, "--since", "999999", "--until", "1000001")
    assert (code, out) == (0, {"ok": True, "removed": True})
    assert not os.path.exists(path)
    code, out, _ = _run(tmp_path, "unmark", "--session-id", SID, "--since", "0", "--until", "1000001")
    assert (code, out) == (0, {"ok": True, "removed": False})


def test_cli_unmark_refusals(tmp_path):
    code, out, _ = _run(tmp_path, "unmark", "--session-id", "../x", "--since", "0", "--until", "1")
    assert (code, out) == (1, {"ok": False, "reason": "session-id-invalid"})
    code, out, _ = _run(tmp_path, "unmark", "--session-id", SID, "--since", "soon", "--until", "1")
    assert (code, out) == (1, {"ok": False, "reason": "window-invalid"})
    env = {"PATH": os.environ.get("PATH", ""), "HOME": "relative/home"}
    r = subprocess.run([sys.executable, "-B", _SCRIPT, "unmark", "--session-id", SID, "--since", "0",
                        "--until", "1"], env=env, capture_output=True, text=True, timeout=20, cwd=str(tmp_path))
    assert r.returncode == 1
    assert json.loads(r.stdout) == {"ok": False, "reason": "config-dir-unresolved"}


# ---------------------------------------------------------------- reap
NOW = 2000000000
DAY = 86400
OLD_NOTES = NOW - cd.NOTES_MAX_AGE_DAYS * DAY - 1
FRESH_NOTES = NOW - cd.NOTES_MAX_AGE_DAYS * DAY + 1


def _ckpt(tmp_path, name):
    return os.path.join(cd.checkpoint_dir(_env(tmp_path)), name)


def test_reap_removes_old_notes_and_keeps_newer_ones(tmp_path):
    _touch(_ckpt(tmp_path, "old-one.md"), mtime=OLD_NOTES)
    _touch(_ckpt(tmp_path, "new-one.md"), mtime=FRESH_NOTES)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 1
    assert not os.path.exists(_ckpt(tmp_path, "old-one.md"))
    assert os.path.exists(_ckpt(tmp_path, "new-one.md"))


def test_reap_removes_markers_past_the_delivery_window_and_keeps_newer_ones(tmp_path):
    _touch(_ckpt(tmp_path, "old-one.delivered"), mtime=NOW - 121)
    _touch(_ckpt(tmp_path, "new-one.delivered"), mtime=NOW - 119)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 1
    assert not os.path.exists(_ckpt(tmp_path, "old-one.delivered"))
    assert os.path.exists(_ckpt(tmp_path, "new-one.delivered"))


def test_reap_never_touches_the_current_session(tmp_path):
    _touch(_ckpt(tmp_path, SID + ".md"), mtime=OLD_NOTES)
    _touch(_ckpt(tmp_path, SID + ".delivered"), mtime=OLD_NOTES)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0
    assert os.path.exists(_ckpt(tmp_path, SID + ".md"))
    assert os.path.exists(_ckpt(tmp_path, SID + ".delivered"))


def test_reap_ignores_names_that_are_not_a_session_id_with_a_known_suffix(tmp_path):
    names = ["has space.md", ".md", "a.b.md", "a" * 129 + ".md", "x.txt", "x.md.bak", ".checkpoint.abc.tmp",
             "x.delivered.old"]
    for name in names:
        _touch(_ckpt(tmp_path, name), mtime=OLD_NOTES)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0
    assert all(os.path.exists(_ckpt(tmp_path, name)) for name in names)


def test_reap_never_follows_or_removes_a_symlink(tmp_path):
    target = tmp_path / "elsewhere" / "target.md"
    _touch(str(target), mtime=OLD_NOTES)
    os.makedirs(os.path.dirname(_ckpt(tmp_path, "x")), exist_ok=True)
    os.symlink(str(target), _ckpt(tmp_path, "linked.md"))
    os.symlink(str(tmp_path / "missing"), _ckpt(tmp_path, "dangling.delivered"))
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0
    assert os.path.islink(_ckpt(tmp_path, "linked.md"))
    assert os.path.islink(_ckpt(tmp_path, "dangling.delivered"))
    assert target.exists()


def test_reap_does_not_recurse_or_remove_directories(tmp_path):
    _touch(_ckpt(tmp_path, os.path.join("nested", "inner.md")), mtime=OLD_NOTES)
    os.makedirs(_ckpt(tmp_path, "dir.md"))
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0
    assert os.path.exists(_ckpt(tmp_path, os.path.join("nested", "inner.md")))
    assert os.path.isdir(_ckpt(tmp_path, "dir.md"))


def test_reap_counts_every_file_it_removes(tmp_path):
    for sid in ("a1", "b2", "c3"):
        _touch(_ckpt(tmp_path, sid + ".md"), mtime=OLD_NOTES)
    _touch(_ckpt(tmp_path, "d4.delivered"), mtime=NOW - 500)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 4


def test_reap_defaults_to_the_wall_clock(tmp_path):
    _touch(_ckpt(tmp_path, "old-one.md"), mtime=time.time() - (cd.NOTES_MAX_AGE_DAYS + 1) * DAY)
    _touch(_ckpt(tmp_path, "new-one.md"))
    assert cd.reap(SID, _env(tmp_path)) == 1


def test_reap_is_a_no_op_without_a_resolvable_dir_directory_or_session_id(tmp_path):
    assert cd.reap(SID, {"CLAUDE_CONFIG_DIR": "rel", "HOME": str(tmp_path)}, now=NOW) == 0
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0     # no checkpoint directory yet
    _touch(_ckpt(tmp_path, "old-one.md"), mtime=OLD_NOTES)
    for bad in ("../x", "", None):
        assert cd.reap(bad, _env(tmp_path), now=NOW) == 0
    assert os.path.exists(_ckpt(tmp_path, "old-one.md"))


def test_reap_resolves_a_relative_config_dir_against_cwd(tmp_path):
    env = {"CLAUDE_CONFIG_DIR": "relcfg", "HOME": str(tmp_path)}
    old = tmp_path / "relcfg" / "superheroes" / "checkpoints" / "old-one.md"
    _touch(str(old), mtime=OLD_NOTES)
    assert cd.reap(SID, env, cwd=str(tmp_path), now=NOW) == 1
    assert not old.exists()


def test_reap_never_raises(tmp_path, monkeypatch):
    _touch(_ckpt(tmp_path, "old-one.md"), mtime=OLD_NOTES)

    def boom(*_a, **_k):
        raise OSError("scandir failed")

    monkeypatch.setattr(os, "scandir", boom)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0


def _ckpt_listing(tmp_path):
    return sorted(os.listdir(os.path.dirname(_ckpt(tmp_path, "x"))))


def test_reap_removes_a_stale_file_and_leaves_only_the_lock_file(tmp_path):
    _touch(_ckpt(tmp_path, "old-one.md"), mtime=OLD_NOTES)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 1
    assert _ckpt_listing(tmp_path) == [".lock"]
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0      # the lock file is never a candidate
    assert _ckpt_listing(tmp_path) == [".lock"]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_a_production_save_waits_for_a_held_lock_before_publishing(tmp_path):
    path = _ckpt(tmp_path, "busy-one.md")
    _touch(path, mtime=OLD_NOTES, text="old")
    saved = []
    with cd._checkpoint_lock(os.path.dirname(path)) as held:    # a reaper mid-sweep
        assert held
        writer = threading.Thread(target=lambda: saved.append(cd.save_notes("busy-one", "fresh save", _env(tmp_path))))
        writer.start()
        writer.join(0.3)
        assert writer.is_alive() and _read(path) == "old"        # the real writer is held at publication
    writer.join(10)
    assert saved == [path] and _read(path) == "fresh save"


def test_a_production_marker_write_waits_for_a_held_lock_before_publishing(tmp_path):
    marker = cd.delivered_marker_path("busy-one", _env(tmp_path))
    _touch(marker, text="old")
    with cd._checkpoint_lock(os.path.dirname(marker)) as held:
        assert held
        writer = threading.Thread(target=lambda: cd.mark_delivered("busy-one", _env(tmp_path), now=5))
        writer.start()
        writer.join(0.3)
        assert writer.is_alive() and _read(marker) == "old"
    writer.join(10)
    assert _read(marker) == "5000"


def test_a_reap_holding_the_lock_removes_the_stale_file_before_the_save_lands(tmp_path, monkeypatch):
    path = _ckpt(tmp_path, "busy-one.md")
    _touch(path, mtime=OLD_NOTES, text="old")
    in_sweep, release = threading.Event(), threading.Event()
    real_scandir = os.scandir

    def paused_scandir(target):
        in_sweep.set()                  # the reaper holds the lock and the stale file still exists
        assert release.wait(10)
        return real_scandir(target)

    monkeypatch.setattr(os, "scandir", paused_scandir)
    result, saved = [], []
    reaper = threading.Thread(target=lambda: result.append(cd.reap(SID, _env(tmp_path), now=NOW)))
    reaper.start()
    assert in_sweep.wait(10)
    writer = threading.Thread(target=lambda: saved.append(cd.save_notes("busy-one", "fresh save", _env(tmp_path))))
    writer.start()
    writer.join(0.3)
    assert writer.is_alive() and _read(path) == "old"          # the save cannot land mid-sweep
    release.set()
    reaper.join(10)
    writer.join(10)
    assert result == [1] and saved == [path]
    assert _read(path) == "fresh save"                         # swept first, then the fresh save published


def test_concurrent_reaps_remove_each_stale_file_once_and_never_a_fresh_one(tmp_path):
    for i in range(20):
        _touch(_ckpt(tmp_path, "old%d.md" % i), mtime=OLD_NOTES)
    _touch(_ckpt(tmp_path, "new-one.md"), mtime=FRESH_NOTES)
    counts = []
    threads = [threading.Thread(target=lambda: counts.append(cd.reap(SID, _env(tmp_path), now=NOW)))
               for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert sorted(counts) == [0, 0, 0, 20]
    assert _ckpt_listing(tmp_path) == [".lock", "new-one.md"]


def test_reap_deletes_nothing_where_fcntl_is_unavailable(tmp_path, monkeypatch):
    _touch(_ckpt(tmp_path, "old-one.md"), mtime=OLD_NOTES)
    monkeypatch.setattr(cd, "fcntl", None)
    assert cd.reap(SID, _env(tmp_path), now=NOW) == 0
    assert _ckpt_listing(tmp_path) == ["old-one.md"]


def test_writers_still_save_without_the_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "fcntl", None)
    path = cd.save_notes(SID, "notes", _env(tmp_path))
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == "notes"
