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

# Each text holds at least one non-trivial line (24+ characters, 12+ letters, not a heading). CORE_TEXT gained
# the "## Verify" heading so a heading-only output can be told from the file; LAYER_TEXT was widened because its
# only prose line was 21 characters, which is trivial.
CORE_TEXT = "# Core\n\nPolicy version: 2026-10-27.942777056682\n\n## Verify\n\nBody.\n"
LAYER_TEXT = "# Review crew layer\n\nNo version line here, only the layer's own guidance.\n"
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
        _codex_cmd("a", "/bin/bash -lc 'cat %s'" % calib.core, exit_code=0, aggregated_output=CORE_TEXT),
        _codex_cmd("b", "/bin/bash -lc 'cat %s'" % calib.layer, exit_code=0, aggregated_output=LAYER_TEXT),
        _codex_cmd("c", "/bin/bash -lc 'cat %s'" % calib.claude, exit_code=0, aggregated_output=CLAUDE_TEXT),
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
        _codex_cmd("a", "cat %s" % calib.core, exit_code=1, aggregated_output=CORE_TEXT),
        _codex_cmd("b", "cat %s" % calib.layer, exit_code=0, aggregated_output=LAYER_TEXT),
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
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] != "read"


def test_codex_existence_check_alone_records_not_read_and_unrecognized_program_records_unknown(calib):
    stdout = _codex_stream(_codex_cmd("a", "test -f %s" % calib.core, exit_code=0, aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "not-read"
    stdout = _codex_stream(_codex_cmd("a", "mytool --load %s" % calib.core, exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_pipeline_in_a_shell_wrapper_is_unknown_and_a_cd_joined_reader_records_read(calib):
    stdout = _codex_stream(
        _codex_cmd("a", "/bin/bash -lc \"sed -n '1,40p' %s | head -n 5\"" % calib.core, exit_code=0,
                   aggregated_output=CORE_TEXT),
        _codex_cmd("b", "cd /x; cat %s" % calib.layer, exit_code=0, aggregated_output=LAYER_TEXT),
    )
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "unknown", "review-crew": "read", "CLAUDE.md": "not-read"}


@pytest.mark.parametrize("command", [
    "true || cat {core}", "if true; then cat {core}; fi",
    "(cat {core})", "for f in a; do\ncat {core}\ndone", "true && /bin/sh -c 'cat {core}'",
])
def test_codex_content_reader_that_may_not_have_run_is_unknown(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def _grep_stream(path, **extra):
    use = {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "id": "g", "name": "Grep",
        "input": dict({"pattern": ".", "path": path}, **extra)}]}}
    result = {"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "g", "is_error": False, "content": CORE_TEXT}]}}
    return "\n".join(json.dumps(o) for o in (use, result))


def test_claude_grep_content_on_the_exact_path_is_a_read(calib):
    stdout = _grep_stream(calib.core, output_mode="content")
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "read"


@pytest.mark.parametrize("extra", [
    {}, {"output_mode": "files_with_matches"}, {"output_mode": "count"},
    {"output_mode": "content", "head_limit": 5},
])
def test_claude_grep_without_printed_content_is_unknown(calib, extra):
    stdout = _grep_stream(calib.core, **extra)
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "unknown"


def _mcp_result(text):
    return {"content": [{"type": "text", "text": text}]}


def test_mcp_metadata_tool_naming_the_path_is_unknown_and_read_file_is_read(calib):
    def mcp(tool):
        return _codex_stream({"type": "item.completed", "item": {
            "id": "b", "type": "mcp_tool_call", "tool": tool, "arguments": {"path": calib.core},
            "status": "completed", "error": None, "result": _mcp_result(CORE_TEXT)}})
    assert _reads(CR.read_states("codex", mcp("get_file_info"), calib.stamp))["core"] == "unknown"
    assert _reads(CR.read_states("codex", mcp("read_file"), calib.stamp))["core"] == "read"


def test_mcp_read_tool_credits_only_its_path_arguments(calib):
    def mcp(tool, arguments):
        return _codex_stream({"type": "item.completed", "item": {
            "id": "b", "type": "mcp_tool_call", "tool": tool, "arguments": arguments,
            "status": "completed", "error": None, "result": _mcp_result(CORE_TEXT)}})
    assert _reads(CR.read_states("codex", mcp("read_file", {"path": calib.core}), calib.stamp))["core"] == "read"
    other = {"path": "/tmp/notes.txt", "note": calib.core}
    assert _reads(CR.read_states("codex", mcp("read_file", other), calib.stamp))["core"] == "unknown"
    many = {"paths": [calib.core]}
    assert _reads(CR.read_states("codex", mcp("read_multiple_files", many), calib.stamp))["core"] == "read"


def test_mcp_read_file_needs_a_result_that_shows_the_file(calib):
    def grade(**extra):
        item = {"id": "b", "type": "mcp_tool_call", "tool": "read_file", "arguments": {"path": calib.core},
                "status": "completed", "error": None}
        item.update(extra)
        stdout = _codex_stream({"type": "item.completed", "item": item})
        return _reads(CR.read_states("codex", stdout, calib.stamp))["core"]
    assert grade(result=_mcp_result(CORE_TEXT)) == "read"
    assert grade() == "unknown"
    assert grade(result=None) == "unknown"
    assert grade(result=_mcp_result("")) == "unknown"
    assert grade(result=_mcp_result("some other file's text, with no line of the stamped one")) == "unknown"


def test_unsupported_mcp_tool_naming_the_basename_relatively_is_unknown(calib):
    stdout = _codex_stream({"type": "item.completed", "item": {
        "id": "b", "type": "mcp_tool_call", "tool": "load_file", "arguments": {"path": "./core.md"},
        "status": "completed", "error": None, "result": _mcp_result(CORE_TEXT)}})
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_unsupported_mcp_tool_naming_an_absolute_path_elsewhere_is_not_read(calib):
    other = "/elsewhere/" + calib.core.rsplit("/", 1)[-1]
    stdout = _codex_stream({"type": "item.completed", "item": {
        "id": "b", "type": "mcp_tool_call", "tool": "load_file", "arguments": {"path": other},
        "status": "completed", "error": None, "result": _mcp_result(CORE_TEXT)}})
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "not-read"


def _truncated_stream():
    return _codex_stream(_codex_cmd("a", "git status --short", exit_code=0))


def test_truncated_capture_without_a_positive_read_records_unknown(calib):
    stdout = _truncated_stream()
    assert set(_reads(CR.read_states("codex", stdout, calib.stamp, truncated=True)).values()) == {"unknown"}
    assert set(_reads(CR.read_states("codex", stdout, calib.stamp)).values()) == {"not-read"}


def test_truncated_capture_keeps_a_positive_read(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0, aggregated_output=CORE_TEXT))
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
    stdout = _codex_stream(_codex_cmd("a", "cd /somewhere && cat core.md", exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
        "core": "unknown", "review-crew": "not-read", "CLAUDE.md": "not-read"}


@pytest.mark.parametrize("command", [
    "git status --short\ncat {core}",
    "/bin/bash -lc \"git status --short\ncat {core}\"",
])
def test_codex_newline_is_a_command_boundary_so_two_commands_are_unknown(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_quoted_newline_does_not_split_a_command(calib):
    stdout = _codex_stream(_codex_cmd("a", "echo 'a\nb' {core}".format(core=calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] != "read"


@pytest.mark.parametrize("command", [
    "cd {root} && cat ./core.md", "cat ./core.md", "cat sub/core.md", "bash -c 'cat ./core.md'",
])
def test_codex_relative_path_to_the_basename_records_unknown(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(root=os.path.dirname(calib.core)), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_absolute_path_elsewhere_with_the_basename_is_not_a_read(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat /elsewhere/core.md", exit_code=0, aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "not-read"


@pytest.mark.parametrize("command", [
    "rg --files-with-matches . {core}", "grep --files-without-match x {core}", "grep --count x {core}",
    "rg --quiet x {core}", "grep --files-with x {core}", "grep --cou . {core}", "grep -c x {core}",
    "grep -l x {core}", "rg --files {core}", "grep -A2 x {core}", "grep --colour x {core}",
    "echo '\n' cat {core}",
])
def test_codex_unlisted_grep_options_or_quoted_separators_are_never_a_read(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


@pytest.mark.parametrize("command", [
    "grep x {core}", "grep -n -i x {core}", "rg --line-number --ignore-case x {core}", "grep -inH -e x {core}",
])
def test_codex_listed_grep_options_are_a_read(calib, command):
    stdout = _codex_stream(_codex_cmd("a", command.format(core=calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "read"


@pytest.mark.parametrize("command,grade", [
    ("cat <core>", "read"), ("head -n 50 <core>", "read"), ("tail -20 <core>", "read"),
    ("nl <core>", "read"), ("sed -n '1,200p' <core>", "read"), ("sed -n -e p <core>", "read"),
    ("awk '{print}' <core>", "read"), ("awk '{print $0}' <core>", "read"),
    ("awk 'NR>=1 && NR<=40 {print $0}' <core>", "unknown"),
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
    stdout = _codex_stream(_codex_cmd("a", command.replace("<core>", calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade


@pytest.mark.parametrize("command,grade", [
    ("cat <core>", "read"), ("cd /tmp && cat <core>", "read"), ("cd /tmp; head -n 5 <core>", "read"),
    ("bash -lc 'cat <core>'", "read"), ("sh -c 'sed -n 1,5p <core>'", "read"), ("tail -n +1 <core>", "read"),
    ("awk '{print}' <core>", "read"),
    # the output is not shown to the reviewer, or the command may not have run
    ("cat <core> > /dev/null", "unknown"), ("cat <core> | wc -l", "unknown"), ("cat <core> | tee x", "unknown"),
    ("head -n 0 <core>", "unknown"), ("head -0 <core>", "unknown"), ("tail -n 0 <core>", "unknown"),
    ("awk 'NR==0 {print}' <core>", "unknown"), ("cat <<EOF\n<core>\nEOF", "unknown"),
    ("bash -n -c 'cat <core>'", "unknown"), ("exit 0; cat <core>", "unknown"),
    ("kill -9 $$; cat <core>", "unknown"), ("set -e; false; cat <core>", "unknown"),
    # more than one command, a second wrapper, a prefix word, or a count of zero
    ("sed -n 1,5p <core> | head -n 5", "unknown"), ("cat <core> && echo done", "unknown"),
    ("cd /a && cd /b && cat <core>", "unknown"), ("env X=1 cat <core>", "unknown"),
    ("sudo cat <core>", "unknown"), ("bash -c 'bash -c \"cat <core>\"'", "unknown"),
    ("bash -c 'cat <core>' extra", "unknown"), ("bash -n 'cat <core>'", "unknown"),
    ("sed -n 0,5p <core>", "unknown"),
    ("tail -n +0 <core>", "unknown"), ("awk 'NR<=5 {print}' <core>", "unknown"),
    ("cat <core> a#b > /dev/null", "unknown"), ("X=/bin/cat <core>", "unknown"),
    ("test -f <core>", "not-read"), ("ls -l <core>", "not-read"),
])
def test_codex_read_is_credited_only_for_one_structurally_single_command(calib, command, grade):
    stdout = _codex_stream(_codex_cmd("a", command.replace("<core>", calib.core), exit_code=0,
                                      aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade


_CORE_LINE = "Policy version: 2026-10-27.942777056682"
_RG_HELP = (
    "ripgrep 14.1.0\n"
    "\n"
    "USAGE:\n"
    "    rg [OPTIONS] PATTERN [PATH ...]\n"
    "    rg [OPTIONS] -e PATTERN ... [PATH ...]\n"
    "    rg [OPTIONS] -f PATTERNFILE ... [PATH ...]\n"
    "    rg [OPTIONS] --files [PATH ...]\n"
    "\n"
    "ARGS:\n"
    "    <PATTERN>    A regular expression used for searching.\n"
    "    <PATH>...    A file or directory to search.\n"
    "\n"
    "OPTIONS:\n"
    "    -h, --help       Prints help information. Use --help for more details.\n"
    "    -V, --version    Prints version information.\n")
_OTHER_FILE_OUTPUT = "".join(
    "line %d of an unrelated notes file, nothing from the stamped file\n" % n for n in range(1, 51))
_NO_OUTPUT_KEY = None  # the completion event carries no aggregated_output at all


@pytest.mark.parametrize("command,output,grade", [
    # vet 782: command texts that pass the structural rule yet show the reviewer none of the file
    pytest.param("rg -h <core>", _RG_HELP, "unknown", id="rg-h-is-help"),
    pytest.param("rg -nh <core>", _RG_HELP, "unknown", id="rg-nh-is-help"),
    # `rg -h <core>` is refused by the structural rule alone (rg takes <core> as the PATTERN, so no file operand is
    # left); the same shapes with a pattern before <core> pass the structural rule and only the output check stops them
    pytest.param("rg -h Policy <core>", _RG_HELP, "unknown", id="rg-h-with-pattern-is-help"),
    pytest.param("rg -nh Policy <core>", _RG_HELP, "unknown", id="rg-nh-with-pattern-is-help"),
    pytest.param("rg -E utf8 <core>", "notes.txt:see <core>\n", "unknown", id="rg-E-is-the-encoding-option"),
    pytest.param("sed -n '1,50p' /tmp/other.txt <core>", _OTHER_FILE_OUTPUT, "unknown", id="two-files-one-stream"),
    pytest.param("tail -n +99999 <core>", "", "unknown", id="tail-start-past-the-end"),
    pytest.param("sed -n '99999p' <core>", "", "unknown", id="sed-line-past-the-end"),
    pytest.param("cat /dev/null # <core>", "", "unknown", id="shell-comment"),
    # a plain read whose output does not show the file
    pytest.param("cat <core>", "", "unknown", id="cat-empty-output"),
    pytest.param("cat <core>", "## Verify\n\n", "unknown", id="cat-heading-and-blank-only"),
    pytest.param("cat <core>", _NO_OUTPUT_KEY, "unknown", id="cat-no-aggregated-output-key"),
    pytest.param("grep -H Policy <core>", "other.md:" + _CORE_LINE + "\n", "unknown", id="grep-H-prefix-names-another-file"),
    # reads whose output shows the file
    pytest.param("cat <core>", CORE_TEXT, "read", id="cat-full-text"),
    pytest.param("/bin/bash -lc \"sed -n '1,300p' <core>\"", CORE_TEXT, "read", id="wrapped-sed-full-text"),
    pytest.param("grep -n Policy <core>", "3:" + _CORE_LINE + "\n", "read", id="grep-n-line-number-prefix"),
    pytest.param("grep -nH Policy <core>", "<core>:3:" + _CORE_LINE + "\n", "read", id="grep-nH-path-and-number-prefix"),
    pytest.param("grep -H Policy <core>", "core.md:" + _CORE_LINE + "\n", "read", id="grep-H-basename-prefix"),
    pytest.param("sed -n '1,5p' <core>", "".join(line + "\n" for line in CORE_TEXT.splitlines()[:5]), "read",
                 id="sed-first-five-lines"),
    pytest.param("nl <core>", "     3\t" + _CORE_LINE + "\n", "read", id="nl-number-and-tab-prefix"),
])
def test_codex_read_needs_the_calls_own_output_to_show_the_file(calib, command, output, grade):
    extra = {} if output is _NO_OUTPUT_KEY else {"aggregated_output": output.replace("<core>", calib.core)}
    stdout = _codex_stream(_codex_cmd("a", command.replace("<core>", calib.core), exit_code=0, **extra))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade


def test_a_stamp_entry_without_line_digests_grades_unknown_for_an_otherwise_good_read(calib):
    old = [{k: v for k, v in entry.items() if k != "lineDigests"} for entry in calib.stamp]
    assert all("lineDigests" not in entry for entry in old)
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0, aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, old))["core"] == "unknown"
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "read"


def test_observation_entry_carries_no_line_digests_and_no_path(calib):
    assert "lineDigests" in calib.stamp[0] and "path" in calib.stamp[0]
    observed = CR._observation_entry(calib.stamp[0], "read")
    assert "lineDigests" not in observed and "path" not in observed
    assert observed == {"label": "core", "file": "core.md", "sha256": _sha(calib.bytes[calib.core]),
                        "policyVersion": "2026-10-27.942777056682", "read": "read"}


def test_non_trivial_line_boundaries():
    assert (CR.MIN_LINE_CHARS, CR.MIN_LINE_LETTERS) == (24, 12)
    assert CR._is_nontrivial("abcdefghijkl" + "0" * 12)          # 24 characters, 12 letters
    assert not CR._is_nontrivial("abcdefghijkl" + "0" * 11)      # 23 characters
    assert not CR._is_nontrivial("abcdefghijk" + "0" * 13)       # 24 characters, 11 letters
    assert not CR._is_nontrivial("#" + "abcdefghijkl" + "0" * 12)  # a heading
    for trivial in ("## Verify", "None", "---", ""):
        assert not CR._is_nontrivial(trivial)


def test_stamp_line_digests_are_sorted_unique_capped_and_never_hold_line_text(calib):
    entries = {entry["label"]: entry for entry in calib.stamp}
    assert entries["core"]["lineDigests"] == [_sha(_CORE_LINE.encode())]
    assert entries["review-crew"]["lineDigests"] == [
        _sha(b"No version line here, only the layer's own guidance.")]
    lines = ["distinct non-trivial line number %04d" % n for n in range(450)]
    with open(calib.core, "w", encoding="utf-8") as fh:
        fh.write("# Heading\n\n" + "\n".join(lines) + "\n")
    digests = {e["label"]: e for e in CR.stamp(calib.root, calib.order)}["core"]["lineDigests"]
    assert digests == sorted(digests) and len(digests) == 400
    assert _sha(lines[399].encode()) in digests and _sha(lines[400].encode()) not in digests
    with open(calib.core, "w", encoding="utf-8") as fh:
        fh.write("   " + lines[0] + "   \n" + lines[0] + "\n" + lines[1] + "\n")
    digests = {e["label"]: e for e in CR.stamp(calib.root, calib.order)}["core"]["lineDigests"]
    assert digests == sorted([_sha(lines[0].encode()), _sha(lines[1].encode())])
    dumped = json.dumps(calib.stamp)
    for text in (_CORE_LINE, "layer's own guidance", "Policy version:** `v7"):
        assert text not in dumped


def test_run_opened_stamp_holds_line_digests_but_no_line_text(runner_env, tmp_path, calib):
    run_dir = _open_run(tmp_path, calib)
    with open(ED._journal_path(run_dir), encoding="utf-8") as fh:
        journal = fh.read()
    records, _ = ED._journal_read(run_dir)
    opened = [rec for rec in records if rec.get("kind") == "run-opened"][0]
    assert opened["calibration"][0]["lineDigests"] == [_sha(_CORE_LINE.encode())]
    for text in (_CORE_LINE, "layer's own guidance"):
        assert text not in journal


def test_vocabulary_has_one_home():
    import calibration_vocab
    import review_record
    assert (CR.LABELS, CR.READ, CR.NOT_READ, CR.UNKNOWN) == (
        calibration_vocab.LABELS, calibration_vocab.READ, calibration_vocab.NOT_READ, calibration_vocab.UNKNOWN)
    assert review_record._CAL_LABELS is calibration_vocab.LABELS
    assert review_record._CAL_READ_STATES == calibration_vocab.READ_STATES


def test_codex_completed_call_without_exit_code_records_unknown(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_boolean_exit_code_is_not_a_success(calib):
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=False, aggregated_output=CORE_TEXT))
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"


def test_codex_started_but_never_completed_records_unknown(calib):
    started = {"type": "item.started", "item": {
        "id": "a", "type": "command_execution", "command": "cat %s" % calib.core}}
    assert _reads(CR.read_states("codex", _codex_stream(started), calib.stamp))["core"] == "unknown"


def test_codex_command_list_and_mcp_call_arguments(calib):
    stdout = _codex_stream(
        _codex_cmd("a", ["cat", calib.core], exit_code=0, aggregated_output=CORE_TEXT),
        {"type": "item.completed", "item": {
            "id": "b", "type": "mcp_tool_call", "tool": "read_file", "arguments": {"path": calib.layer},
            "status": "completed", "error": None, "result": _mcp_result(LAYER_TEXT)}},
        {"type": "item.completed", "item": {
            "id": "c", "type": "mcp_tool_call", "tool": "read_file", "arguments": {"path": calib.claude},
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
    stdout = _codex_stream(_codex_cmd("a", "cat %s" % real, exit_code=0, aggregated_output=CORE_TEXT))
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
    stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}),
                    _claude_result("t1", content=CORE_TEXT),
                    _claude_use("t2", "Bash", {"command": "cat %s" % calib.layer}),
                    _claude_result("t2", is_error=False, content=LAYER_TEXT))
    assert _reads(CR.read_states("claude", stdout, calib.stamp)) == {
        "core": "read", "review-crew": "read", "CLAUDE.md": "not-read"}


def test_claude_read_with_error_tool_result_records_not_read(calib):
    stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}),
                    _claude_result("t1", is_error=True, content=CORE_TEXT))
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "not-read"


def test_claude_read_without_tool_result_records_unknown(calib):
    stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}))
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "unknown"


def test_claude_result_before_the_call_does_not_count(calib):
    stdout = _lines(_claude_result("t1", content=CORE_TEXT),
                    _claude_use("t1", "Read", {"file_path": calib.core}))
    assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "unknown"


def _numbered(text):
    """``text`` as the Claude Read tool prints it: a right-aligned line number, a tab, the line."""
    return "\n".join("%6d\t%s" % (n, line) for n, line in enumerate(text.splitlines(), 1))


def _numbered_arrow(text):
    """``text`` as the Claude Code Read tool prints it: a right-aligned line number, U+2192, the line."""
    return "\n".join("%6d→%s" % (n, line) for n, line in enumerate(text.splitlines(), 1))


def test_claude_read_with_numbered_content_reads_and_with_empty_content_is_unknown(calib):
    def grade(content):
        stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}), _claude_result("t1", content=content))
        return _reads(CR.read_states("claude", stdout, calib.stamp))["core"]
    assert _numbered(CORE_TEXT).startswith("     1\t# Core")
    assert _numbered_arrow(CORE_TEXT).startswith("     1→# Core")
    assert grade(_numbered(CORE_TEXT)) == "read"
    assert grade([{"type": "text", "text": _numbered(CORE_TEXT)}]) == "read"
    assert grade(_numbered_arrow(CORE_TEXT)) == "read"
    assert grade([{"type": "text", "text": _numbered_arrow(CORE_TEXT)}]) == "read"
    assert grade("") == "unknown"
    assert grade([]) == "unknown"
    assert grade(None) == "unknown"
    assert grade(_numbered("# Other\n\nA line that belongs to some other file entirely.\n")) == "unknown"


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
                      {"success": {"content": CORE_TEXT}}),
        _cursor_event("completed", "2", "shellToolCall", {"command": "cat %s" % calib.layer},
                      {"success": {"exitCode": 0, "stdout": LAYER_TEXT}}),
        _cursor_event("completed", "3", "shellToolCall", {"command": "cat %s" % calib.claude},
                      {"success": {"exitCode": 2, "stdout": CLAUDE_TEXT}}),
    )
    assert _reads(CR.read_states("cursor", stdout, calib.stamp)) == {
        "core": "read", "review-crew": "read", "CLAUDE.md": "not-read"}


def test_cursor_success_without_the_files_text_records_unknown(calib):
    stdout = _lines(
        _cursor_event("completed", "1", "readToolCall", {"path": calib.core}, {"success": {"content": "x"}}),
        _cursor_event("completed", "2", "shellToolCall", {"command": "cat %s" % calib.layer},
                      {"success": {"exitCode": 0}}),
    )
    assert _reads(CR.read_states("cursor", stdout, calib.stamp)) == {
        "core": "unknown", "review-crew": "unknown", "CLAUDE.md": "not-read"}


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


def test_stamp_names_a_file_under_the_real_root_when_the_root_is_given_through_a_symlink(calib, tmp_path, monkeypatch):
    link = str(tmp_path / "root-link")
    os.symlink(calib.root, link)
    # the order names CLAUDE.md by its real path; the root arrives through the symlink
    stamped = CR.stamp(link, "Read %s only.\n" % calib.claude)
    assert [(e["label"], e["path"], e["sha256"]) for e in stamped] == [
        ("CLAUDE.md", calib.claude, _sha(calib.bytes[calib.claude]))]
    # the order names it through the symlink the root was given as
    via_link = os.path.join(link, "CLAUDE.md")
    stamped = CR.stamp(link, "Read %s only.\n" % via_link)
    assert [(e["label"], e["path"]) for e in stamped] == [("CLAUDE.md", via_link)]
    # a core file resolved through a symlink is named by its real path
    core_link = str(tmp_path / "core-link.md")
    os.symlink(calib.core, core_link)
    monkeypatch.setattr(CR, "resolved_paths", lambda repo_root: (core_link, None, None))
    stamped = CR.stamp(calib.root, "Read %s only.\n" % calib.core)
    assert [(e["label"], e["path"]) for e in stamped] == [("core", calib.core)]
    assert CR.stamp(link, "Read nothing named.\n") == []


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
                        "sha256": None, "policyVersion": None, "lineDigests": []}]


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
        _codex_cmd("a", "/bin/bash -lc 'cat %s'" % calib.core, exit_code=0, aggregated_output=CORE_TEXT),
        _codex_cmd("b", "cat %s" % calib.layer, exit_code=1, aggregated_output=LAYER_TEXT)))
    record, error = ED.run_execution_record(run_dir)
    assert error is None
    observed = record["observation"]["calibration"]
    assert _reads(observed) == {"core": "read", "review-crew": "not-read", "CLAUDE.md": "not-read"}
    assert observed[0]["sha256"] == _sha(calib.bytes[calib.core])
    assert observed[0]["policyVersion"] == "2026-10-27.942777056682"
    dumped = json.dumps(observed)
    for path in (calib.core, calib.layer, calib.claude, calib.root):
        assert path not in dumped
    assert "lineDigests" not in dumped


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
