import ast
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_ROOT = os.path.join(_HERE, "..")

_FORBIDDEN_LITERALS = frozenset({
    "--bg",
    "claude-mode-background-write",
    "background-launched",
    "attempt-suspended",
    "attempt-bg-stop",
    "bgStop",
    "backgroundStopUnconfirmed",
    "transcript",
    "background-launch-unacknowledged",
    "background-launch-failed",
    "background-session-unlisted",
    "background-transcript-ambiguous",
    "background-agents-unreadable",
    "background-session-ended-without-result",
    "background-stop-unconfirmed",
    "transcriptResult",
    "transcriptToolCalls",
    "claude-mode-unsupported",
})

_REMOVED_SYMBOLS = frozenset({
    "background_outcome",
    "MODE_BACKGROUND",
    "RESULT_DELIVERY_TRANSCRIPT",
    "_NON_PRINT_CLAUDE_MODE_ENGINES",
    "claude_mode_supported",
    "claude_launch_id",
    "claude_cli_argv",
    "_claude_cli",
    "_claude_agents_rows",
    "_parse_claude_agents_rows",
    "_run_engine_files_background",
    "_run_claude_background_launch",
    "_stop_live_background_sessions",
    "_background_stop",
    "_background_stop_unconfirmed",
    "_is_background_claude_mode",
    "_claude_mode_background_write_refusal",
    "MODE_REFUSAL_CLAUDE_MODE_BACKGROUND_WRITE",
    "claude_transcript_result",
    "claude_transcript_turn_ended",
    "_attempt_bg_resumable",
    "_attempt_bg_budget_exhausted",
    "_record_bg_stop_on_slot",
    "_read_transcript_rows",
})


# The relay is a separate, ruled use of a background session; its argv builder is the one place
# the flag may be spelled. The retired surface is background *dispatch*.
_RELAY_ARGV_FILE = "engine_adapter.py"
_RELAY_ARGV_FUNCTION = "claude_relay_argv"


def _admitted_relay_flag(name, tree):
    """The `--bg` literals admitted: those inside `claude_relay_argv` in `engine_adapter.py`."""
    if name != _RELAY_ARGV_FILE:
        return set()
    return {
        id(inner)
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and fn.name == _RELAY_ARGV_FUNCTION
        for inner in ast.walk(fn)
        if isinstance(inner, ast.Constant) and inner.value == "--bg"
    }


def retired_background_problems(lib_root):
    problems = []
    scanned = set()
    lib_root = os.path.abspath(lib_root)
    for name in sorted(os.listdir(lib_root)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(lib_root, name)
        if not os.path.isfile(path):
            continue
        scanned.add(name)
        rel = os.path.relpath(path, lib_root)
        try:
            source = open(path, encoding="utf-8").read()
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            problems.append("%s:unparseable" % rel)
            continue
        admitted = _admitted_relay_flag(name, tree)
        for node in ast.walk(tree):
            if id(node) in admitted:
                continue
            if isinstance(node, ast.Constant) and node.value in _FORBIDDEN_LITERALS:
                problems.append("%s:%d:%s" % (rel, node.lineno, node.value))
            elif isinstance(node, ast.Name) and node.id in _REMOVED_SYMBOLS:
                problems.append("%s:%d:%s" % (rel, node.lineno, node.id))
            elif isinstance(node, ast.Attribute) and node.attr in _REMOVED_SYMBOLS:
                problems.append("%s:%d:%s" % (rel, node.lineno, node.attr))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in _REMOVED_SYMBOLS:
                    problems.append("%s:%d:%s" % (rel, node.lineno, node.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _REMOVED_SYMBOLS or (
                        alias.asname and alias.asname in _REMOVED_SYMBOLS
                    ):
                        problems.append("%s:%d:%s" % (rel, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in _REMOVED_SYMBOLS or (
                        alias.asname and alias.asname in _REMOVED_SYMBOLS
                    ):
                        problems.append("%s:%d:%s" % (rel, node.lineno, alias.name))
    return sorted(problems), scanned


def test_shipped_lib_has_no_retired_background_surface(tmp_path):
    # axis: shipped lib modules carry no retired background literals or symbols
    problems, scanned = retired_background_problems(_LIB_ROOT)
    assert problems == []
    assert scanned
    for required in (
        "engine_dispatch.py",
        "engine_adapter.py",
        "engine_result_channel.py",
        "claude_modes.py",
    ):
        assert required in scanned
    assert not os.path.isfile(os.path.join(_LIB_ROOT, "background_outcome.py"))


def test_census_bites_on_planted_background_surface(tmp_path):
    # axis: census reports planted literals, imports, and symbol names
    planted = tmp_path / "planted.py"
    planted.write_text(
        'import background_outcome\n'
        'argv = ["claude", "--bg"]\n'
        'detail = "background-stop-unconfirmed"\n'
        'def _background_stop():\n'
        '    pass\n',
        encoding="utf-8",
    )
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n", encoding="utf-8")
    problems, _scanned = retired_background_problems(str(tmp_path))
    whats = [p.split(":", 2)[-1] for p in problems if p.startswith("planted.py:")]
    assert sorted(whats) == [
        "--bg",
        "_background_stop",
        "background-stop-unconfirmed",
        "background_outcome",
    ]
    assert not any(p.startswith("clean.py:") for p in problems)


def test_census_admits_the_flag_only_in_the_relay_argv_builder(tmp_path):
    # axis: `--bg` is admitted in claude_relay_argv of engine_adapter.py and nowhere else
    (tmp_path / "engine_adapter.py").write_text(
        'def claude_cloud_argv():\n'
        '    return ["claude", "--bg"]\n'
        '\n'
        'def claude_relay_argv(name, prompt):\n'
        '    return ["claude", "--bg", "-n", name, prompt]\n',
        encoding="utf-8",
    )
    (tmp_path / "elsewhere.py").write_text(
        'def claude_relay_argv(name, prompt):\n'
        '    return ["claude", "--bg", "-n", name, prompt]\n',
        encoding="utf-8",
    )
    problems, _scanned = retired_background_problems(str(tmp_path))
    assert problems == ["elsewhere.py:2:--bg", "engine_adapter.py:2:--bg"]
