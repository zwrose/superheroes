"""The review-seat allowance (#2071): the closed codex tool set, the read-only MCP file server and
the positive stream judge. See seat_allowance.py and seat_read_tool.py."""
import json
import os
import re
import subprocess
import sys

import pytest

import engine_adapter as EA
import model_registry as MR
import seat_allowance as SA

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOL = os.path.join(_LIB, "seat_read_tool.py")
_ALLOWANCE_SRC = os.path.join(_LIB, "seat_allowance.py")

_CODEX_MODEL, _CODEX_EFFORT = MR.matrix_config("reviewer", "codex")


def _codex_seat():
    return {"vendor": "codex", "model": _CODEX_MODEL, "effort": _CODEX_EFFORT}


def _subsequence_count(argv, tokens):
    n = len(tokens)
    return sum(1 for i in range(len(argv) - n + 1) if argv[i:i + n] == tokens)


# --------------------------------------------------------------- codex_review_args


def test_codex_review_args_exact_shape_with_cwd():
    args = SA.codex_review_args("/work/wt")
    assert args[:5] == ["--ignore-user-config", "--disable", "shell_tool",
                        "--disable", "unified_exec"]
    assert args[5] == "-c"
    assert args[6] == "mcp_servers.superheroes_read.command=" + json.dumps(sys.executable)
    assert args[7] == "-c"
    assert args[8] == "mcp_servers.superheroes_read.args=" + json.dumps(
        ["-I", "-B", _TOOL, "--root", "/work/wt"], separators=(",", ":"))
    assert args[9:] == ["-c", 'mcp_servers.superheroes_read.default_tools_approval_mode="approve"']
    assert os.path.isabs(_TOOL) and os.path.isfile(_TOOL)


@pytest.mark.parametrize("cwd", [None, "", 7])
def test_codex_review_args_without_usable_cwd_has_no_root_pair(cwd):
    args = SA.codex_review_args(cwd)
    assert "--root" not in "".join(args)
    assert args[8] == "mcp_servers.superheroes_read.args=" + json.dumps(
        ["-I", "-B", _TOOL], separators=(",", ":"))


def test_codex_review_args_quotes_paths_as_valid_toml_strings():
    cwd = '/tmp/a dir/with "quotes" and \\ back'
    args = SA.codex_review_args(cwd)
    value = args[8].split("=", 1)[1]
    assert json.loads(value) == ["-I", "-B", _TOOL, "--root", cwd]
    assert value.startswith("[") and value.endswith("]")


# --------------------------------------------------------------- census


@pytest.mark.parametrize("cwd", [None, "/work/wt"])
def test_every_codex_review_argv_carries_the_closed_set_once_in_order(cwd):
    opts = {"cwd": cwd} if cwd else {}
    result = EA.build_argv_result(_codex_seat(), "review", opts)
    assert result["reason"] is None
    argv = result["argv"]
    closed = SA.codex_review_args(cwd)
    assert _subsequence_count(argv, closed) == 1
    assert argv.count("--ignore-user-config") == 1
    start = argv.index("--ignore-user-config")
    assert argv[start:start + len(closed)] == closed
    effort_at = argv.index("model_reasoning_effort=%s" % _CODEX_EFFORT)
    assert effort_at < start
    assert argv[-1] == "-"
    if cwd:
        assert argv[-3:] == ["-C", cwd, "-"]
        assert start + len(closed) == len(argv) - 3
    else:
        assert start + len(closed) == len(argv) - 1


@pytest.mark.parametrize("cwd", [None, "/work/wt"])
def test_codex_build_argv_carries_none_of_the_closed_set(cwd):
    opts = {"cwd": cwd} if cwd else {}
    argv = EA.build_argv_result(_codex_seat(), "build", opts)["argv"]
    assert "--ignore-user-config" not in argv
    assert "--disable" not in argv
    assert not any("mcp_servers" in token for token in argv)
    assert _subsequence_count(argv, SA.codex_review_args(cwd)) == 0


def test_claude_review_argv_loads_no_mcp_server():
    argv = EA.build_argv_result(
        {"vendor": "claude", "model": "sonnet-5.5", "effort": "high"}, "review", {})["argv"]
    assert argv.index("--strict-mcp-config") == argv.index("--restricted") + 1


# --------------------------------------------------------------- module shape


def test_allowance_sentences_are_exact():
    assert SA.REVIEW_ALLOWANCE == (
        "You may read, list and search files with your read tools, and you run no program: a "
        "test, check or command run you need is the driver's, which runs the project's declared "
        "verify command.")
    assert SA.FIXER_ALLOWANCE == (
        "You run only the commands this order names (its scoped tests, validators, break-it "
        "commands and the commit) and your edit tools, and none of the project's own scripts "
        "beyond them; the full verify command stays the driver's.")
    assert SA.READ_SERVER_NAME == "superheroes_read"


def test_allowance_module_names_no_program():
    with open(_ALLOWANCE_SRC, encoding="utf-8") as handle:
        text = handle.read()
    for word in ("security", "bash", "curl", "rm", "sh", "zsh", "git", "node", "npm"):
        assert not re.search(r"\b%s\b" % re.escape(word), text), word


# --------------------------------------------------------------- seat_read_tool protocol


class _Server:
    def __init__(self, root, *extra):
        self.proc = subprocess.Popen(
            [sys.executable, "-I", "-B", _TOOL, "--root", str(root), *extra],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
        self._next = 0

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def recv(self):
        line = self.proc.stdout.readline()
        assert line, "server closed stdout; stderr=%r" % self.proc.stderr.read()
        return json.loads(line)

    def request(self, method, params=None):
        self._next += 1
        msg = {"jsonrpc": "2.0", "id": self._next, "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)
        reply = self.recv()
        assert reply["id"] == self._next
        return reply

    def call(self, name, arguments):
        reply = self.request("tools/call", {"name": name, "arguments": arguments})
        return reply["result"]

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.proc.stdout.close()
        self.proc.stderr.close()


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    srv = _Server(root)
    yield srv, root
    srv.close()


def _text(result):
    return result["content"][0]["text"]


def test_initialize_echoes_protocol_and_lists_tools(server):
    srv, _root = server
    reply = srv.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
    assert reply["result"]["protocolVersion"] == "2024-11-05"
    assert reply["result"]["capabilities"] == {"tools": {}}
    assert "serverInfo" in reply["result"]
    srv.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools = srv.request("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["read_file", "list_dir", "search"]
    for tool in tools:
        assert tool["annotations"] == {"readOnlyHint": True}
        assert tool["inputSchema"]["type"] == "object"


def test_initialize_defaults_protocol_version(server):
    srv, _root = server
    assert srv.request("initialize", {})["result"]["protocolVersion"] == "2025-06-18"


def test_ping_and_notification_gets_no_reply(server):
    srv, _root = server
    srv.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    srv.send({"jsonrpc": "2.0", "method": "notifications/anything", "params": {}})
    reply = srv.request("ping")
    assert reply["result"] == {}


def test_unknown_method_is_32601(server):
    srv, _root = server
    reply = srv.request("resources/list")
    assert reply["error"]["code"] == -32601
    assert "result" not in reply


def test_read_file_window_and_continuation_note(server):
    srv, root = server
    (root / "f.txt").write_text("".join("line %d\n" % i for i in range(1, 11)))
    result = srv.call("read_file", {"path": "f.txt", "offset": 3, "limit": 4})
    assert "isError" not in result
    lines = _text(result).split("\n")
    assert lines[:4] == ["     3\tline 3", "     4\tline 4", "     5\tline 5", "     6\tline 6"]
    assert "offset=7" in lines[4]
    whole = _text(srv.call("read_file", {"path": "f.txt"}))
    assert whole.split("\n")[-1] == "    10\tline 10"
    assert "more lines remain" not in whole


def test_read_file_limit_is_capped_at_2000(server):
    srv, root = server
    (root / "big.txt").write_text("".join("%d\n" % i for i in range(1, 2501)))
    text = _text(srv.call("read_file", {"path": "big.txt", "limit": 99999}))
    assert text.split("\n")[1999] == "  2000\t2000"
    assert "offset=2001" in text


def test_read_file_absolute_path_outside_root_is_readable(server, tmp_path):
    srv, _root = server
    outside = tmp_path / "outside.txt"
    outside.write_text("outside-nonce\n")
    result = srv.call("read_file", {"path": str(outside)})
    assert "isError" not in result
    assert "outside-nonce" in _text(result)


def test_read_file_failures_are_is_error(server):
    srv, root = server
    (root / "sub").mkdir()
    for args in ({"path": "missing.txt"}, {"path": "sub"}, {"path": ""}, {},
                 {"path": "x", "offset": "one"}):
        result = srv.call("read_file", args)
        assert result["isError"] is True, args
        assert _text(result)


def test_list_dir_sorted_with_directory_suffix(server):
    srv, root = server
    (root / "b.txt").write_text("")
    (root / "a_dir").mkdir()
    (root / "c.txt").write_text("")
    assert _text(srv.call("list_dir", {})).split("\n") == ["a_dir/", "b.txt", "c.txt"]
    assert _text(srv.call("list_dir", {"path": "a_dir"})) == "[no entries]"
    assert srv.call("list_dir", {"path": "nope"})["isError"] is True


def test_search_hit_skips_git_binary_and_oversize(server):
    srv, root = server
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\nneedle here\n")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("needle in git\n")
    (root / "bin.dat").write_bytes(b"\xff\xfe needle \x00")
    (root / "huge.txt").write_text("needle\n" + "x" * (2 * 1024 * 1024 + 1))
    result = srv.call("search", {"pattern": "nee+dle"})
    assert "isError" not in result
    lines = _text(result).split("\n")
    assert lines == ["%s:2: needle here" % (root / "src" / "a.py")]
    single = _text(srv.call("search", {"pattern": "x = 1", "path": "src/a.py"}))
    assert single.endswith("a.py:1: x = 1")


def test_search_caps_results_and_truncates_text(server):
    srv, root = server
    (root / "m.txt").write_text("hit " + "y" * 500 + "\n" + "hit\n" * 10)
    lines = _text(srv.call("search", {"pattern": "hit", "max_results": 3})).split("\n")
    assert len(lines) == 4 and "cap 3" in lines[3]
    first = lines[0].split(": ", 1)[1]
    assert len(first) == 300


def test_search_bad_regex_and_missing_path_are_is_error(server):
    srv, _root = server
    bad = srv.call("search", {"pattern": "("})
    assert bad["isError"] is True and "regular expression" in _text(bad)
    assert srv.call("search", {"pattern": "a", "path": "nope"})["isError"] is True
    assert srv.call("search", {"pattern": 5})["isError"] is True
    assert _text(srv.call("search", {"pattern": "zzz-nothing"})) == "[no matches]"


def test_unknown_tool_and_bad_arguments_are_is_error(server):
    srv, _root = server
    assert srv.call("run_command", {"command": "true"})["isError"] is True
    reply = srv.request("tools/call", {"name": "read_file", "arguments": ["x"]})
    assert reply["result"]["isError"] is True
    reply = srv.request("tools/call", "nonsense")
    assert reply["result"]["isError"] is True


def test_garbage_line_gets_parse_error_and_server_survives(server):
    srv, _root = server
    srv.proc.stdin.write("not json\n")
    srv.proc.stdin.flush()
    assert srv.recv()["error"]["code"] == -32700
    assert srv.request("ping")["result"] == {}


def test_relative_paths_resolve_against_root_not_cwd(tmp_path):
    root = tmp_path / "rooted"
    root.mkdir()
    (root / "here.txt").write_text("rooted\n")
    srv = _Server(root)
    try:
        assert "rooted" in _text(srv.call("read_file", {"path": "here.txt"}))
    finally:
        srv.close()


def test_default_root_is_the_working_directory(tmp_path):
    (tmp_path / "cwd.txt").write_text("from-cwd\n")
    proc = subprocess.Popen(
        [sys.executable, "-I", "-B", _TOOL], cwd=str(tmp_path),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                     "params": {"name": "read_file",
                                                "arguments": {"path": "cwd.txt"}}}) + "\n")
        proc.stdin.flush()
        reply = json.loads(proc.stdout.readline())
        assert "from-cwd" in _text(reply["result"])
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)
        proc.stdout.close()


def test_read_tool_source_starts_no_program_and_writes_no_file():
    with open(_TOOL, encoding="utf-8") as handle:
        text = handle.read()
    for needle in ("subprocess", "os.system", "os.exec", "os.spawn", "pty"):
        assert needle not in text, needle
    assert not re.search(r"open\([^)]*[\"'][wax+]", text)


# --------------------------------------------------------------- outside_allowance


def _item(kind, event="item.completed", **fields):
    return {"type": event, "item": dict({"id": "item_1", "type": kind}, **fields)}


@pytest.mark.parametrize("obj", [
    _item("agent_message", text="hi"),
    _item("reasoning", event="item.started"),
    _item("todo_list"),
    _item("error", message="boom"),
    _item("web_search", query="q"),
    _item("mcp_tool_call", server="superheroes_read", tool="read_file"),
    _item("mcp_tool_call", event="item.started", server="superheroes_read", tool="search"),
])
def test_outside_allowance_inside(obj):
    assert SA.outside_allowance(obj) is None


@pytest.mark.parametrize("obj", [
    {"type": "thread.started", "thread_id": "t"},
    {"type": "turn.completed", "usage": {}},
    {"type": "item.updated", "item": {"type": "command_execution", "command": "x"}},
    {"type": "item.completed"},
    {"type": "item.completed", "item": "command_execution"},
    {"item": {"type": "command_execution"}},
    [], "text", 5, None,
])
def test_outside_allowance_not_a_judged_event(obj):
    assert SA.outside_allowance(obj) is None


def test_outside_allowance_command_execution_is_outside():
    found = SA.outside_allowance(_item("command_execution", command="a" * 500))
    assert found.startswith("command_execution: aaa")
    assert len(found) <= 200
    started = SA.outside_allowance(_item("command_execution", event="item.started",
                                         command="./run_me.sh"))
    assert started == "command_execution: ./run_me.sh"


def test_outside_allowance_other_item_kinds_are_outside():
    assert SA.outside_allowance(_item("file_change", changes=[])) == "file_change"
    assert SA.outside_allowance(_item("never_seen_before")) == "never_seen_before"
    assert SA.outside_allowance(_item("mcp_tool_call", server="node_repl", tool="js")) \
        == "mcp_tool_call: node_repl.js"
    assert SA.outside_allowance(_item("mcp_tool_call")) == "mcp_tool_call: None.None"
    assert len(SA.outside_allowance(_item("x" * 900))) <= 200


# --------------------------------------------------------------- scan_stream


def _write_lines(path, objs, extra=()):
    with open(path, "wb") as handle:
        for obj in objs:
            handle.write((json.dumps(obj) + "\n").encode())
        for raw in extra:
            handle.write(raw)


def test_scan_stream_truth_table(tmp_path):
    path = tmp_path / "stream.jsonl"
    _write_lines(path, [
        {"type": "thread.started", "thread_id": "t"},
        _item("agent_message", text="ok"),
        _item("mcp_tool_call", server="superheroes_read", tool="read_file"),
        _item("command_execution", event="item.started", command="./run_me.sh"),
        _item("command_execution", command="./run_me.sh"),
        _item("file_change"),
        _item("mcp_tool_call", server="node_repl", tool="js"),
        _item("never_seen_before"),
        ["not", "an", "event"],
    ], extra=[b"garbage line\n", b"\xff\xfe\n", b"\n", b'{"type": "item.completed"'])
    violations, ok = SA.scan_stream(str(path))
    assert ok is True
    assert violations == [
        "command_execution: ./run_me.sh",
        "file_change",
        "mcp_tool_call: node_repl.js",
        "never_seen_before",
    ]


def test_scan_stream_clean_stream(tmp_path):
    path = tmp_path / "clean.jsonl"
    _write_lines(path, [_item("agent_message", text="ok"), {"type": "turn.completed"}])
    assert SA.scan_stream(str(path)) == ([], True)


def test_scan_stream_caps_the_violation_list(tmp_path):
    path = tmp_path / "many.jsonl"
    _write_lines(path, [_item("command_execution", command="c%d" % i) for i in range(50)])
    violations, ok = SA.scan_stream(str(path))
    assert ok is True and len(violations) == 20
    assert len(SA.scan_stream(str(path), limit=3)[0]) == 3


def test_scan_stream_unreadable_file_is_not_ok(tmp_path):
    assert SA.scan_stream(str(tmp_path / "absent.jsonl")) == ([], False)
    assert SA.scan_stream(str(tmp_path)) == ([], False)
    assert SA.scan_stream(None) == ([], False)


def test_scan_stream_reports_a_violation_before_9_mib_of_allowed_lines(tmp_path):
    path = tmp_path / "padded.jsonl"
    padding = (json.dumps(_item("agent_message", text="p" * 900)) + "\n").encode()
    with open(path, "wb") as handle:
        handle.write((json.dumps(_item("command_execution", command="./run_me.sh")) + "\n")
                     .encode())
        written = 0
        while written < 9 * 1024 * 1024:
            handle.write(padding)
            written += len(padding)
    assert os.path.getsize(path) > 9 * 1024 * 1024
    violations, ok = SA.scan_stream(str(path))
    assert ok is True
    assert violations == ["command_execution: ./run_me.sh"]


def test_scan_stream_reports_a_violation_after_9_mib_of_allowed_lines(tmp_path):
    path = tmp_path / "padded_first.jsonl"
    padding = (json.dumps(_item("agent_message", text="p" * 900)) + "\n").encode()
    with open(path, "wb") as handle:
        written = 0
        while written < 9 * 1024 * 1024:
            handle.write(padding)
            written += len(padding)
        handle.write((json.dumps(_item("file_change")) + "\n").encode())
    assert SA.scan_stream(str(path)) == (["file_change"], True)
