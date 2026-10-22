"""#2046 WO-2: the refusals a Claude Code subagent transcript shows are read by a closed marker list.

Fixtures are synthetic transcripts in the real JSONL shape (an assistant `tool_use` row, then a user
`tool_result` row), written into `tmp_path`. Part one pins each marker row and the reader's shape
tolerance; part two pins the three faults; part three pins `unreported` and the never-raises edge.
"""
import json

import pytest

import observed_refusals as OR


def _use(call_id, name="Bash", tool_input=None):
    if tool_input is None:
        tool_input = {"command": "echo " + call_id}
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": call_id, "name": name, "input": tool_input}]}}


def _result(call_id, content, is_error=True):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": call_id, "is_error": is_error, "content": content}]}}


def _write(tmp_path, rows, name="transcript.jsonl"):
    path = tmp_path / name
    path.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows))
    return str(path)


def _one(tmp_path, text, tool_input=None, name="Bash"):
    return OR.read_transcript(_write(tmp_path, [_use("toolu_1", name, tool_input), _result("toolu_1", text)]))


_MARKER_CASES = [
    ("Permission to use Bash with command rm -rf x has been denied.", "permission"),
    ("Permission for this action was denied by the Claude Code auto mode classifier. Reason: x", "permission"),
    ("Permission for this command was denied by a built-in Claude Code safety check.", "permission"),
    ("<tool_use_error>Blocked: this path is outside the sandbox</tool_use_error>", "permission"),
    ("The user doesn't want to proceed with this tool use. The tool use was rejected.", "permission"),
    ("This command requires approval", "permission"),
    ("This Bash command contains multiple operations. The following part requires approval: git push", "permission"),
]


@pytest.mark.parametrize("text,refused_by", _MARKER_CASES)
def test_each_non_hook_marker_is_recognized(tmp_path, text, refused_by):
    observed, fault = _one(tmp_path, text)
    assert fault is None
    assert observed == [{"tool": "Bash", "command": "echo toolu_1", "refusedBy": refused_by}]


def test_hook_marker_is_recognized_as_hook(tmp_path):
    for text in (
        "PreToolUse:Bash hook error: [guard.sh]: no pushing",
        "PreToolUse:Edit hook blocking error from command: guard.sh",
    ):
        observed, fault = _one(tmp_path, text)
        assert fault is None
        assert observed == [{"tool": "Bash", "command": "echo toolu_1", "refusedBy": "hook"}]


def test_marker_list_is_closed_and_uses_the_three_refused_by_values():
    assert isinstance(OR.MARKERS, tuple)
    assert {row[2] for row in OR.MARKERS} <= {"permission", "hook", "sandbox"}
    assert all(row[0] for row in OR.MARKERS)


@pytest.mark.parametrize("text", [
    "Permission to use Bash",
    "PreToolUse:Bash did something else",
    "This Bash command contains multiple operations and runs fine",
    "Command was denied by someone",
    "Exit code 1\nboom",
    "File has not been read yet. Read it first before writing to it.",
    "String to replace not found in file.",
])
def test_non_refusals_and_partial_markers_are_not_counted(tmp_path, text):
    assert _one(tmp_path, text) == ([], None)


def test_is_error_false_is_not_counted(tmp_path):
    path = _write(tmp_path, [_use("toolu_1"), _result("toolu_1", "This command requires approval", is_error=False)])
    assert OR.read_transcript(path) == ([], None)


def test_string_and_list_content(tmp_path):
    as_list = [{"type": "text", "text": "Permission to use Bash with command x"},
               {"type": "text", "text": " has been denied."}]
    observed, fault = _one(tmp_path, as_list)
    assert fault is None and [o["refusedBy"] for o in observed] == ["permission"]
    assert _one(tmp_path, [{"type": "image"}, 5, None]) == ([], None)
    assert _one(tmp_path, None) == ([], None)


def test_leading_whitespace_and_error_prefix_are_stripped(tmp_path):
    for text in ("Error: This command requires approval", "  \nError: This command requires approval",
                 "\t This command requires approval"):
        observed, _ = _one(tmp_path, text)
        assert [o["refusedBy"] for o in observed] == ["permission"]


def test_command_falls_back_through_file_path_path_and_json(tmp_path):
    text = "Permission to use Edit has been denied"
    assert _one(tmp_path, text, {"file_path": "/a/b", "path": "/c"}, "Edit")[0][0]["command"] == "/a/b"
    assert _one(tmp_path, text, {"path": "/c"}, "Glob")[0][0]["command"] == "/c"
    assert _one(tmp_path, text, {"command": 5, "file_path": "/a"}, "Bash")[0][0]["command"] == "/a"
    assert _one(tmp_path, text, {"b": 1, "a": [2]}, "Task")[0][0]["command"] == '{"a": [2], "b": 1}'
    assert _one(tmp_path, text, "weird", "Task")[0][0]["command"] == '"weird"'


def test_orphan_tool_use_id_still_counts(tmp_path):
    path = _write(tmp_path, [_result("toolu_nope", "This command requires approval")])
    assert OR.read_transcript(path) == (
        [{"tool": None, "command": "<unknown tool call>", "refusedBy": "permission"}], None)


def test_order_is_transcript_order_and_results_match_by_id(tmp_path):
    rows = [_use("a", tool_input={"command": "first"}), _use("b", tool_input={"command": "second"}),
            _result("b", "This command requires approval"), _result("a", "Exit code 2"),
            _use("c", tool_input={"command": "third"}),
            _result("c", "PreToolUse:Bash hook error: [x]: no")]
    observed, fault = OR.read_transcript(_write(tmp_path, rows))
    assert fault is None
    assert [(o["command"], o["refusedBy"]) for o in observed] == [("second", "permission"), ("third", "hook")]


def test_malformed_lines_and_non_object_rows_are_skipped(tmp_path):
    rows = ["{not json", "[1, 2]", "", _use("toolu_1"), "null", _result("toolu_1", "This command requires approval"),
            {"type": "user", "message": "text"}, {"type": "assistant", "message": {"content": "x"}}]
    observed, fault = OR.read_transcript(_write(tmp_path, rows))
    assert fault is None and len(observed) == 1


def test_fault_missing(tmp_path):
    assert OR.read_transcript(str(tmp_path / "nope.jsonl")) == ([], "transcript-missing")
    assert OR.read_transcript(None) == ([], "transcript-missing")


def test_fault_unreadable(tmp_path):
    assert OR.read_transcript(str(tmp_path)) == ([], "transcript-unreadable")
    bad = tmp_path / "bad.jsonl"
    bad.write_bytes(b"\xff\xfe\x00{")
    assert OR.read_transcript(str(bad)) == ([], "transcript-unreadable")


def test_fault_unparseable(tmp_path):
    assert OR.read_transcript(_write(tmp_path, ["not json", "[1]", "42"])) == ([], "transcript-unparseable")


def test_empty_file_is_not_a_fault(tmp_path):
    assert OR.read_transcript(_write(tmp_path, [])) == ([], None)


def test_unreported_is_multiset(tmp_path):
    observed = [{"tool": "Bash", "command": "git push", "refusedBy": "permission"}] * 2
    one = [{"command": "git push", "refusedBy": "permission", "next": "stopped"}]
    assert OR.unreported(observed, one) == observed[:1]
    assert OR.unreported(observed, one * 2) == []
    assert OR.unreported(observed, []) == observed


def test_unreported_matches_whitespace_stripped():
    observed = [{"tool": "Bash", "command": "  git push\n", "refusedBy": "permission"}]
    assert OR.unreported(observed, [{"command": "git push "}]) == []
    assert OR.unreported(observed, [{"command": "git pull"}]) == observed


@pytest.mark.parametrize("refusals", [None, "git push", 5, {"command": "git push"}, [None, 3, "x", {"command": 4}]])
def test_unreported_treats_non_list_or_bad_entries_as_nothing_reported(refusals):
    observed = [{"tool": "Bash", "command": "git push", "refusedBy": "permission"}]
    assert OR.unreported(observed, refusals) == observed


@pytest.mark.parametrize("garbage", [None, 5, 1.5, [], {}, object(), b"x"])
def test_public_functions_never_raise_on_garbage(garbage, tmp_path):
    observed, fault = OR.read_transcript(garbage)
    assert observed == [] and fault in ("transcript-missing", "transcript-unreadable")
    assert OR.unreported(garbage, garbage) == []
    kept = [{"command": []}] if not isinstance(garbage, dict) else [garbage, {"command": []}]
    assert OR.unreported([garbage, {"command": []}], garbage) == kept
    assert OR.read_transcript(tmp_path) == ([], "transcript-unreadable")
