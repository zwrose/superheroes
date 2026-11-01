"""Tests for calibration_read: the runner's record of which calibration files a seat read (#2311).

Streams are built as JSONL in the test. Every file the tests read is written by the test, so the
expected hash is computed from bytes this file wrote.
"""
import hashlib
import json
import os
import sys
import time

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import calibration_read as CR  # noqa: E402
import calibration_resolve  # noqa: E402
import core_md  # noqa: E402
import engine_adapter  # noqa: E402
import engine_dispatch as ED  # noqa: E402
import model_registry as MR  # noqa: E402
import round_driver  # noqa: E402

CORE_TEXT = "# Core\n\nPolicy version: 2026-10-27.942777056682\n\nBody.\n"
LAYER_TEXT = "# Review crew layer\n\nNo version line here.\n"
CLAUDE_TEXT = "# Project\n\n- **Policy version:** `v7`\n"


class Calib:
    """Three calibration files on disk, an order that names them, and the stamp over it."""


@pytest.fixture
def calib(tmp_path, monkeypatch):
    c = Calib()
    c.root = str(tmp_path / "repo")
    os.makedirs(c.root)
    store = tmp_path / "store"
    store.mkdir()
    c.core = str(store / "core.md")
    c.layer = str(store / "review-crew.md")
    c.claude = os.path.join(c.root, "CLAUDE.md")
    c.bytes = {c.core: CORE_TEXT.encode(), c.layer: LAYER_TEXT.encode(),
               c.claude: CLAUDE_TEXT.encode()}
    for path, data in c.bytes.items():
        with open(path, "wb") as fh:
            fh.write(data)
    monkeypatch.setattr(CR, "resolved_paths", lambda repo_root: (c.core, c.layer, None))
    c.order = "Read %s then %s then %s before you review.\n" % (c.core, c.layer, c.claude)
    c.stamp = CR.stamp(c.root, c.order)
    return c


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _reads(result):
    return {entry["label"]: entry["read"] for entry in result}


def _lines(*events):
    return "\n".join(json.dumps(event) for event in events) + "\n"


# --- codex streams -------------------------------------------------------------


def _codex_cmd(item_id, command, **extra):
    item = {"id": item_id, "type": "command_execution", "command": command}
    item.update(extra)
    return {"type": "item.completed", "item": item}


def _codex_stream(*items):
    return _lines({"type": "thread.started", "thread_id": "t"}, {"type": "turn.started"},
                  *items, {"type": "turn.completed", "usage": {"input_tokens": 1}})


def test_codex_successful_read_of_each_file_records_read_with_hash_and_policy(calib):
    stdout = _codex_stream(
        _codex_cmd("a", "/bin/bash -lc 'cat %s'" % calib.core, exit_code=0),
        _codex_cmd("b", "/bin/bash -lc 'cat %s'" % calib.layer, exit_code=0),
        _codex_cmd("c", "/bin/bash -lc 'cat %s'" % calib.claude, exit_code=0),
    )
    result = CR.read_states("codex", stdout, calib.stamp)
    assert result == [
        {"label": "core", "file": "core.md", "sha256": _sha(calib.bytes[calib.core]),
         "policyVersion": "2026-10-27.942777056682", "read": "read"},
        {"label": "review-crew", "file": "review-crew.md",
         "sha256": _sha(calib.bytes[calib.layer]), "policyVersion": None, "read": "read"},
        {"label": "CLAUDE.md", "file": "CLAUDE.md", "sha256": _sha(calib.bytes[calib.claude]),
         "policyVersion": "v7", "read": "read"},
    ]
    dumped = json.dumps(result)
    for path in (calib.core, calib.layer, calib.claude, calib.root):
        assert path not in dumped


def test_codex_nonzero_exit_records_not_read_while_a_sibling_success_records_read(calib):
    stdout = _codex_stream(
        _codex_cmd("a", "cat %s" % calib.core, exit_code=1),
        _codex_cmd("b", "cat %s" % calib.layer, exit_code=0),
    )
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "not-read", "review-crew": "read", "CLAUDE.md": "not-read"}


def test_codex_calls_not_naming_the_files_record_not_read(calib):
    stdout = _codex_stream(
        _codex_cmd("a", "git status --short", exit_code=0),
        _codex_cmd("b", "cat /elsewhere/notes.txt", exit_code=0),
    )
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "not-read", "review-crew": "not-read", "CLAUDE.md": "not-read"}


@pytest.mark.parametrize("stdout", [
    "plain text, the engine printed no events\n",
    _lines({"hello": "world"}, {"type": "not-a-codex-event"}),
    "",
    None,
])
def test_codex_unrecognizable_stream_records_unknown_for_every_file(calib, stdout):
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "unknown", "review-crew": "unknown", "CLAUDE.md": "unknown"}


def test_unknown_engine_records_unknown(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0))
    assert set(_reads(CR.read_states("mystery", stdout, calib.stamp)).values()) == {"unknown"}


@pytest.mark.parametrize("command", [
    "test -f {core}", "ls -l {core}", "stat {core}", "/bin/bash -lc 'test -f {core}'",
    "cat {core}.backup", "cat {core}.md",
])
def test_codex_existence_checks_and_other_files_are_not_a_read(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] != "read"


def test_codex_existence_check_alone_records_not_read_and_unrecognized_program_records_unknown(calib):
    stdout = _codex_stream(_codex_cmd("a", "test -f %s" % calib.core, exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "not-read"
    stdout = _codex_stream(_codex_cmd("a", "mytool --load %s" % calib.core, exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_content_readers_in_pipelines_and_shell_wrappers_record_read(calib):
    stdout = _codex_stream(
        _codex_cmd("a", "/bin/bash -lc \"sed -n '1,40p' %s | head -n 5\"" % calib.core, exit_code=0),
        _codex_cmd("b", "cd /x && cat %s" % calib.layer, exit_code=0),
    )
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "read", "review-crew": "read", "CLAUDE.md": "not-read"}


def _truncated_stream():
    return _codex_stream(_codex_cmd("a", "git status --short", exit_code=0))


def test_truncated_capture_without_a_positive_read_records_unknown(calib):
    stdout = _truncated_stream()
    assert set(_reads(CR.read_states("codex", stdout, calib.stamp, truncated=True)).values()) == {"unknown"}
    assert set(_reads(CR.read_states("codex", stdout, calib.stamp)).values()) == {"not-read"}


def test_truncated_capture_keeps_a_positive_read(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp, truncated=True)) == {
        "core": "read", "review-crew": "unknown", "CLAUDE.md": "unknown"}


def test_capture_truncation_helper_prefers_the_stamped_count_then_the_head_marker():
    cap = ED.MAX_STDOUT_CAPTURE
    marker = ED._stdout_truncation_marker(cap + 5)
    assert ED._calibration_capture_truncated({"stdoutBytes": cap + 1, "stdoutBytesPreCap": True}, "") is True
    assert ED._calibration_capture_truncated({"stdoutBytes": 10, "stdoutBytesPreCap": True}, marker) is False
    assert ED._calibration_capture_truncated({}, marker + "{}") is True
    assert ED._calibration_capture_truncated({}, "{}") is False
    assert ED._calibration_capture_truncated({"stdoutCapRewriteFailed": True}, "{}") is True


def test_codex_basename_only_success_records_unknown(calib):
    stdout = _codex_stream(_codex_cmd("a", "cd /somewhere && cat core.md", exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "unknown", "review-crew": "not-read", "CLAUDE.md": "not-read"}


@pytest.mark.parametrize("command", [
    "git status --short\ncat {core}",
    "/bin/bash -lc \"git status --short\ncat {core}\"",
])
def test_codex_newline_is_a_command_boundary(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "read"


def test_codex_quoted_newline_does_not_split_a_command(calib):
    stdout = _codex_stream(_codex_cmd("a", "echo 'a\nb' {core}".format(core=calib.core), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] != "read"


@pytest.mark.parametrize("command", [
    "cd {root} && cat ./core.md", "cat ./core.md", "cat sub/core.md", "bash -c 'cat ./core.md'",
])
def test_codex_relative_path_to_the_basename_records_unknown(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(root=os.path.dirname(calib.core)), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_absolute_path_elsewhere_with_the_basename_is_not_a_read(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat /elsewhere/core.md", exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "not-read"


@pytest.mark.parametrize("command", [
    "rg --files-with-matches . {core}", "grep --files-without-match x {core}", "grep --count x {core}",
    "rg --quiet x {core}", "grep --files-with x {core}", "grep --cou . {core}", "grep -c x {core}",
    "grep -l x {core}", "rg --files {core}", "grep -A2 x {core}", "grep --colour x {core}",
    "echo '\n' cat {core}",
])
def test_codex_unlisted_grep_options_or_quoted_separators_are_never_a_read(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


@pytest.mark.parametrize("command", [
    "grep x {core}", "grep -n -i x {core}", "rg --line-number --ignore-case x {core}", "grep -inH -e x {core}",
])
def test_codex_listed_grep_options_are_a_read(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "read"


@pytest.mark.parametrize("command,grade", [
    ("cat <core>", "read"), ("head -n 50 <core>", "read"), ("tail -20 <core>", "read"),
    ("nl <core>", "read"), ("sed -n '1,200p' <core>", "read"), ("sed -n -e p <core>", "read"),
    ("awk '{print}' <core>", "read"), ("awk 'NR>=1 && NR<=40 {print $0}' <core>", "read"),
    ("grep foo <core>", "read"), ("grep -n -e foo <core>", "read"), ("rg -i foo <core>", "read"),
    ("grep -Fe foo <core>", "read"),
    ("grep -F -e <core> /tmp/other.txt", "unknown"), ("grep <core> /tmp/other.txt", "unknown"),
    ("grep --regexp=<core> /tmp/other.txt", "unknown"), ("grep -f <core> /tmp/other.txt", "unknown"),
    ("grep -- foo <core>", "unknown"), ("sed 's/a/b/' <core>", "unknown"),
    ("sed -n 's/a/b/p' <core>", "unknown"), ("sed -i -n p <core>", "unknown"),
    ("awk '{system(\"x\")}' <core>", "unknown"), ("awk -f prog <core>", "unknown"),
    ("cat -A <core>", "unknown"), ("head -c 10 <core>", "unknown"), ("xxd <core>", "unknown"),
    ("sort <core>", "unknown"), ("less -N <core>", "unknown"),
    ("test -f <core>", "not-read"), ("ls -l <core>", "not-read"),
])
def test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command(calib, command, grade):
    stdout = _codex_stream(_codex_cmd("a", command.replace("<core>", calib.core), exit_code=0))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade


def test_vocabulary_has_one_home():
    import calibration_vocab
    import review_record
    assert (CR.LABELS, CR.READ, CR.NOT_READ, CR.UNKNOWN) == (
        calibration_vocab.LABELS, calibration_vocab.READ, calibration_vocab.NOT_READ, calibration_vocab.UNKNOWN)
    assert review_record._CAL_LABELS is calibration_vocab.LABELS
    assert review_record._CAL_READ_STATES == calibration_vocab.READ_STATES


def test_codex_completed_call_without_exit_code_records_unknown(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_boolean_exit_code_is_not_a_success(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=False))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_started_but_never_completed_records_unknown(calib):
    started = {"type": "item.started", "item": {
        "id": "a", "type": "command_execution", "command": "cat %s" % calib.core}}
    assert _reads(CR.read_states("codex", _codex_stream(started), calib.stamp))["core"] == "unknown"


def test_codex_command_list_and_mcp_call_arguments(calib):
    stdout = _codex_stream(
        _codex_cmd("a", ["cat", calib.core], exit_code=0),
        {"type": "item.completed", "item": {
            "id": "b", "type": "mcp_tool_call", "arguments": {"path": calib.layer},
            "status": "completed", "error": None}},
        {"type": "item.completed", "item": {
            "id": "c", "type": "mcp_tool_call", "arguments": {"path": calib.claude},
            "status": "failed", "error": {"message": "denied"}}},
    )
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "read", "review-crew": "read", "CLAUDE.md": "not-read"}


def test_codex_realpath_of_a_symlinked_file_counts(calib, tmp_path):
    real = tmp_path / "real-core.md"
    real.write_bytes(calib.bytes[calib.core])
    link = tmp_path / "link-core.md"
    os.symlink(str(real), str(link))
    stamped = [dict(entry) for entry in calib.stamp]
    stamped[0]["path"] = str(link)
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % real, exit_code=0))
    assert _reads(CR.read_states("codex", stdout, stamped))["core"] == "read"


# --- claude streams ------------------------------------------------------------


def _claude_use(tool_id, name, tool_input):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]}}


def _claude_result(tool_id, **extra):
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}
    block.update(extra)
    return {"type": "user", "message": {"content": [block]}}


def test_claude_read_with_clean_tool_result_records_read(calib):
    stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}), _claude_result("t1"),
                    _claude_use("t2", "Bash", {"command": "cat %s" % calib.layer}),
                    _claude_result("t2", is_error=False))
    assert _reads(CR.read_states("claude", stdout, calib.stamp)) == {
        "core": "read", "review-crew": "read", "CLAUDE.md": "not-read"}


def test_claude_read_with_error_tool_result_records_not_read(calib):
    stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}),
                    _claude_result("t1", is_error=True))
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "not-read"


def test_claude_read_without_tool_result_records_unknown(calib):
    stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}))
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "unknown"


def test_claude_result_before_the_call_does_not_count(calib):
    stdout = _lines(_claude_result("t1"), _claude_use("t1", "Read", {"file_path": calib.core}))
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "unknown"


def test_claude_plain_text_records_unknown(calib):
    assert set(_reads(CR.read_states("claude", "just words\n", calib.stamp)).values()) == {"unknown"}


# --- cursor streams ------------------------------------------------------------


def _cursor_event(subtype, call_id, tool, args, result=None):
    body = {"args": args}
    if result is not None:
        body["result"] = result
    return {"type": "tool_call", "subtype": subtype, "call_id": call_id,
            "tool_call": {tool: body}}


def test_cursor_completed_read_with_success_result_records_read(calib):
    stdout = _lines(
        _cursor_event("started", "1", "readToolCall", {"path": calib.core}),
        _cursor_event("completed", "1", "readToolCall", {"path": calib.core},
                      {"success": {"content": "x"}}),
        _cursor_event("completed", "2", "shellToolCall", {"command": "cat %s" % calib.layer},
                      {"success": {"exitCode": 0}}),
        _cursor_event("completed", "3", "shellToolCall", {"command": "cat %s" % calib.claude},
                      {"success": {"exitCode": 2}}),
    )
    assert _reads(CR.read_states("cursor", stdout, calib.stamp)) == {
        "core": "read", "review-crew": "read", "CLAUDE.md": "not-read"}


def test_cursor_error_result_records_not_read(calib):
    stdout = _lines(_cursor_event("completed", "1", "readToolCall", {"path": calib.core},
                                  {"error": {"message": "no such file"}}))
    assert _reads(CR.read_states("cursor", stdout, calib.stamp))["core"] == "not-read"


def test_cursor_result_that_is_neither_success_nor_failure_records_unknown(calib):
    stdout = _lines(_cursor_event("completed", "1", "readToolCall", {"path": calib.core}, {}))
    assert _reads(CR.read_states("cursor", stdout, calib.stamp))["core"] == "unknown"


def test_cursor_plain_text_records_unknown(calib):
    assert set(_reads(CR.read_states("cursor", "plain\n", calib.stamp)).values()) == {"unknown"}


# --- stamp ---------------------------------------------------------------------


def test_stamp_keeps_only_files_the_order_names(calib):
    stamped = CR.stamp(calib.root, "Read %s only.\n" % calib.layer)
    assert [entry["label"] for entry in stamped] == ["review-crew"]
    assert CR.stamp(calib.root, "no paths in this order") == []
    assert CR.stamp(calib.root, "") == []
    assert CR.stamp(calib.root, None) == []
    assert [entry["label"] for entry in calib.stamp] == ["core", "review-crew", "CLAUDE.md"]


def test_stamp_hash_and_policy_are_taken_at_stamp_time(calib):
    with open(calib.core, "w", encoding="utf-8") as fh:
        fh.write("rewritten after the stamp\nPolicy version: changed\n")
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0))
    entry = CR.read_states("codex", stdout, calib.stamp)[0]
    assert entry["sha256"] == _sha(calib.bytes[calib.core])
    assert entry["policyVersion"] == "2026-10-27.942777056682"


def test_stamp_with_unreadable_file_records_null_hash_and_policy(calib, monkeypatch):
    ghost = os.path.join(os.path.dirname(calib.core), "ghost.md")
    monkeypatch.setattr(CR, "resolved_paths", lambda repo_root: (ghost, None, None))
    stamped = CR.stamp(calib.root, "Read %s\n" % ghost)
    assert stamped == [{"label": "core", "file": "ghost.md", "path": ghost,
                        "sha256": None, "policyVersion": None}]


def test_stamp_drops_core_and_layer_when_the_root_refuses(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    claude = str(root / "CLAUDE.md")
    with open(claude, "w", encoding="utf-8") as fh:
        fh.write(CLAUDE_TEXT)

    def refuse(cwd):
        raise calibration_resolve.UnresolvableRootError(cwd, cwd, "h", "d", "p")
    monkeypatch.setattr(calibration_resolve, "resolve", refuse)
    order = "Read /store/core.md and /store/review-crew.md and %s\n" % claude
    assert [entry["label"] for entry in CR.stamp(str(root), order)] == ["CLAUDE.md"]


@pytest.mark.parametrize("text,expected", [
    ("Policy version: 2026-10-27.942777056682\n", "2026-10-27.942777056682"),
    ("intro\n- policy VERSION: v3 extra words\n", "v3"),
    ("> **Policy version:** `v4`\n", "v4"),
    ("| `Policy version`: **v5**\n", "v5"),
    ("## Policy version:   v6\n", "v6"),
    ("Policy version:\nPolicy version: later\n", "later"),
    ("first\nPolicy version: one\nPolicy version: two\n", "one"),
    ("Mentions the Policy version: v9 mid-line\n", None),
    ("nothing here\n", None),
])
def test_policy_version_line_forms(tmp_path, monkeypatch, text, expected):
    path = str(tmp_path / "f.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    monkeypatch.setattr(CR, "resolved_paths", lambda root: (path, None, None))
    assert CR.stamp(str(tmp_path), path)[0]["policyVersion"] == expected


def test_public_functions_never_raise_on_garbage(calib):
    assert CR.read_states("codex", "x", "not-a-list") == []
    assert CR.read_states("codex", "x", [None, 3, {"path": 5}]) != None  # noqa: E711
    assert CR.stamp(None, 5) == []
    assert CR.stamp(object(), "x") == []


# --- round_driver delegation ---------------------------------------------------


def test_round_driver_delegate_returns_what_resolved_paths_returns(tmp_path, monkeypatch):
    core = tmp_path / "core.md"
    layer = tmp_path / "layer.md"
    core.write_text("c", encoding="utf-8")
    layer.write_text("l", encoding="utf-8")
    root = str(tmp_path)
    monkeypatch.setattr(calibration_resolve, "resolve", lambda cwd: {
        "dispatch_core": str(core), "dispatch_layer": str(layer)})
    assert round_driver._resolved_calibration_paths(root) == (str(core), str(layer), None)
    assert CR.resolved_paths(root) == (str(core), str(layer), None)
    monkeypatch.setattr(calibration_resolve, "resolve", lambda cwd: {
        "dispatch_core": str(tmp_path / "missing.md"), "dispatch_layer": None})
    assert round_driver._resolved_calibration_paths(root) == (None, None, None)

    def refuse(cwd):
        raise calibration_resolve.UnresolvableRootError(cwd, cwd, "h", "d", "p")
    monkeypatch.setattr(calibration_resolve, "resolve", refuse)
    expected = core_md.gate_refusal_line(core_md.gate_refusal(
        calibration_resolve.REASON_UNRESOLVABLE_ROOT, root))
    assert round_driver._resolved_calibration_paths(root) == (None, None, expected)
    assert CR.resolved_paths(root) == (None, None, expected)


# --- through the runner: run-opened stamp and the run's execution record -------


@pytest.fixture
def runner_env(tmp_path, monkeypatch):
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)


def _open_run(tmp_path, calib, run_name="run"):
    run_dir = str(tmp_path / run_name)
    seat = {"vendor": "codex", "model": MR.pin_only_models("codex")[0], "effort": "high",
            "role": "reviewer"}
    built = engine_adapter.build_argv_result(seat, "review", {"model": "sonnet", "cwd": calib.root})
    prompt_path = str(tmp_path / (run_name + "-prompt.txt"))
    with open(prompt_path, "w", encoding="utf-8") as fh:
        fh.write(calib.order)
    fed = "NOTICE preamble\n" + calib.order + "example block\n"
    ok, detail = ED._open_review_run(
        run_dir, engine="codex", argv=built["argv"], cwd=calib.root,
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=prompt_path, view_path=calib.root, view_meta={"headSha": "abc123fake"},
        fed_prompt=fed, order_id="calib-order", progress_path=os.path.join(run_dir, "p.jsonl"),
        repo_root=calib.root, echo_nonce="calib-nonce")
    assert ok, detail
    return run_dir


def _complete_attempt(run_dir, stdout):
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(stdout)
    with open(os.path.join(run_dir, "attempt-1.stderr"), "w", encoding="utf-8") as fh:
        fh.write("")
    ED._journal_append(run_dir, {"kind": "attempt-started", "attempt": 1, "childPid": 1,
                                 "at": time.time()})
    ED._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1, "exit": 0, "timedOut": False, "signal": None,
        "refusal": None, "at": time.time(), "wallSeconds": 1.0, "stdoutBytes": len(stdout)})


def _rewrite_opened(run_dir, mutate):
    records, _ = ED._journal_read(run_dir)
    for rec in records:
        if rec.get("kind") == "run-opened":
            mutate(rec)
    with open(ED._journal_path(run_dir), "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")


def test_open_review_run_stamps_the_files_the_order_named(runner_env, tmp_path, calib):
    run_dir = _open_run(tmp_path, calib)
    records, _ = ED._journal_read(run_dir)
    opened = [rec for rec in records if rec.get("kind") == "run-opened"][0]
    assert [(e["label"], e["sha256"], e["path"]) for e in opened["calibration"]] == [
        ("core", _sha(calib.bytes[calib.core]), calib.core),
        ("review-crew", _sha(calib.bytes[calib.layer]), calib.layer),
        ("CLAUDE.md", _sha(calib.bytes[calib.claude]), calib.claude)]


def test_open_review_run_records_none_and_still_opens_when_the_stamp_raises(
        runner_env, tmp_path, calib, monkeypatch):
    def boom(root, text):
        raise RuntimeError("stamp exploded")
    monkeypatch.setattr(CR, "stamp", boom)
    run_dir = _open_run(tmp_path, calib)
    records, _ = ED._journal_read(run_dir)
    opened = [rec for rec in records if rec.get("kind") == "run-opened"][0]
    assert opened["calibration"] is None
    _complete_attempt(run_dir, _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0)))
    record, error = ED.run_execution_record(run_dir)
    assert error is None
    assert "calibration" not in record["observation"]


def test_run_execution_record_observation_carries_read_for_a_file_a_codex_stream_read(
        runner_env, tmp_path, calib):
    run_dir = _open_run(tmp_path, calib)
    _complete_attempt(run_dir, _codex_stream(
        _codex_cmd("a", "/bin/bash -lc 'cat %s'" % calib.core, exit_code=0),
        _codex_cmd("b", "cat %s" % calib.layer, exit_code=1)))
    record, error = ED.run_execution_record(run_dir)
    assert error is None
    observed = record["observation"]["calibration"]
    assert _reads(observed) == {"core": "read", "review-crew": "not-read", "CLAUDE.md": "not-read"}
    assert observed[0]["sha256"] == _sha(calib.bytes[calib.core])
    assert observed[0]["policyVersion"] == "2026-10-27.942777056682"
    dumped = json.dumps(observed)
    for path in (calib.core, calib.layer, calib.claude, calib.root):
        assert path not in dumped


def test_run_execution_record_observation_has_empty_list_when_order_named_no_file(
        runner_env, tmp_path, calib):
    calib.order = "An order that names no calibration file.\n"
    run_dir = _open_run(tmp_path, calib)
    _complete_attempt(run_dir, _codex_stream(_codex_cmd("a", "ls", exit_code=0)))
    record, error = ED.run_execution_record(run_dir)
    assert error is None
    assert record["observation"]["calibration"] == []


def test_run_execution_record_observation_has_no_key_when_run_opened_lacks_the_stamp(
        runner_env, tmp_path, calib):
    run_dir = _open_run(tmp_path, calib)
    _rewrite_opened(run_dir, lambda rec: rec.pop("calibration"))
    _complete_attempt(run_dir, _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0)))
    record, error = ED.run_execution_record(run_dir)
    assert error is None
    assert "calibration" not in record["observation"]
