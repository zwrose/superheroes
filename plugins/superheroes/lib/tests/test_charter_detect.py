"""Behavior tests for charter detection from session transcripts (lib/charter_detect.py)."""
import json
import os

import charter_detect as cd


def _write_transcript(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _user_charter(charter, *, is_sidechain=False, extra=None):
    content = (
        "<command-message>superheroes:%s</command-message>\n"
        "<command-name>/superheroes:%s</command-name>\n"
        "<command-args>Issue: #911</command-args>"
    ) % (charter, charter)
    rec = {
        "type": "user",
        "isSidechain": is_sidechain,
        "userType": "external",
        "message": {"role": "user", "content": content},
    }
    if extra:
        rec.update(extra)
    return rec


def test_detects_showrunner(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("showrunner")])
    assert cd.detect_charter(str(path)) == "showrunner"


def test_detects_workhorse(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse")])
    assert cd.detect_charter(str(path)) == "workhorse"


def test_detects_detective(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("detective")])
    assert cd.detect_charter(str(path)) == "detective"


def test_charter_names_matches_detection_regex():
    """CHARTER_NAMES is the single roster; reverting detective drops it here first."""
    assert "detective" in cd.CHARTER_NAMES
    assert len(cd.CHARTER_NAMES) == 3


def test_no_charter_transcript_returns_none(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {"type": "user", "isSidechain": False, "message": {"role": "user", "content": "hello"}},
        {"type": "assistant", "message": {"role": "assistant", "content": "hi"}},
    ])
    assert cd.detect_charter(str(path)) is None


def test_subagent_transcript_returns_none(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {
            "type": "user",
            "isSidechain": True,
            "message": {"role": "user", "content": "do the thing"},
        },
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {"role": "assistant", "content": "ok"},
        },
    ])
    assert cd.detect_charter(str(path)) is None


def test_tool_result_list_content_does_not_self_match(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {
            "type": "user",
            "isSidechain": False,
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "content": "<command-name>/superheroes:showrunner</command-name>",
                    }
                ],
            },
        },
    ])
    assert cd.detect_charter(str(path)) is None


def test_sidechain_charter_command_returns_none(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [_user_charter("workhorse", is_sidechain=True)])
    assert cd.detect_charter(str(path)) is None


def test_most_recent_invocation_wins(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        _user_charter("showrunner"),
        _user_charter("workhorse"),
    ])
    assert cd.detect_charter(str(path)) == "workhorse"


def test_robustness_none_path():
    assert cd.detect_charter(None) is None


def test_robustness_nonexistent_path(tmp_path):
    assert cd.detect_charter(str(tmp_path / "missing.jsonl")) is None


def test_robustness_directory_path(tmp_path):
    assert cd.detect_charter(str(tmp_path)) is None


def test_robustness_non_json_lines(tmp_path):
    path = tmp_path / "transcript.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json at all\n")
        fh.write("still not json\n")
    assert cd.detect_charter(str(path)) is None


def test_robustness_truncated_final_line_still_returns_earlier_match(tmp_path):
    path = tmp_path / "transcript.jsonl"
    with open(path, "wb") as fh:
        fh.write((json.dumps(_user_charter("showrunner")) + "\n").encode("utf-8"))
        fh.write(b'{"type":"user","truncated":')
    assert cd.detect_charter(str(path)) == "showrunner"


def test_bare_prose_mention_is_not_a_charter_invocation(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {
            "type": "user",
            "isSidechain": False,
            "message": {
                "role": "user",
                "content": "remind me how /superheroes:showrunner routes work",
            },
        },
    ])
    assert cd.detect_charter(str(path)) is None


def test_assistant_quoting_marker_returns_none(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": "Use <command-name>/superheroes:workhorse</command-name> to start.",
            },
        },
    ])
    assert cd.detect_charter(str(path)) is None


def test_unreadable_transcript_emits_breadcrumb(tmp_path, capsys):
    path = tmp_path / "transcript.jsonl"
    path.write_text('{"type":"user"}\n', encoding="utf-8")
    path.chmod(0o000)
    try:
        assert cd.detect_charter(str(path)) is None
        err = capsys.readouterr().err
        assert "superheroes charter_detect:" in err
        assert str(path) in err
    finally:
        path.chmod(0o644)


def test_unreadable_parent_directory_emits_breadcrumb(tmp_path, capsys):
    import os
    import stat

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        import pytest

        pytest.skip("root can bypass directory permission bits")
    secret = tmp_path / "secret"
    secret.mkdir()
    transcript = secret / "transcript.jsonl"
    _write_transcript(transcript, [_user_charter("showrunner")])
    secret.chmod(stat.S_IRUSR | stat.S_IWUSR)
    try:
        assert cd.detect_charter(str(transcript)) is None
        err = capsys.readouterr().err
        assert "superheroes charter_detect:" in err
        assert str(transcript) in err
    finally:
        secret.chmod(stat.S_IRWXU)


def test_foreign_plugin_prefix_does_not_detect(tmp_path):
    """Only /superheroes: prefix matches; foreign plugin commands are ignored."""
    path = tmp_path / "transcript.jsonl"
    foreign_content = (
        "<command-message>otherplugin:workhorse</command-message>\n"
        "<command-name>/otherplugin:workhorse</command-name>\n"
        "<command-args>Issue: #911</command-args>"
    )
    foreign_rec = {
        "type": "user",
        "isSidechain": False,
        "userType": "external",
        "message": {"role": "user", "content": foreign_content},
    }
    _write_transcript(path, [foreign_rec])
    assert cd.detect_charter(str(path)) is None

    superheroes_path = tmp_path / "superheroes.jsonl"
    _write_transcript(superheroes_path, [_user_charter("workhorse")])
    assert cd.detect_charter(str(superheroes_path)) == "workhorse"


def test_no_charter_transcript_emits_no_breadcrumb(tmp_path, capsys):
    path = tmp_path / "transcript.jsonl"
    _write_transcript(path, [
        {"type": "user", "isSidechain": False, "message": {"role": "user", "content": "hello"}},
    ])
    assert cd.detect_charter(str(path)) is None
    assert capsys.readouterr().err == ""
