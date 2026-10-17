"""iphone_allow.py — the PreToolUse(Bash) hook that approves the plugin's own iPhone check (#1893).

The hook prints `permissionDecision: "allow"` iff the whole command is one plain call of this
plugin's own `lib/iphone_check.py` with one of its verbs (and, for `drive`, one of the pilot's AXe
steps) and the worktree guard's classifier does not deny it. Every other input — any other
command, any parse doubt, any internal error — prints nothing and exits 0.

Two channels: `decide` / `plugin_roots` in-process (the truth table), and the real hook as a
subprocess (the stdout and exit-code contract).
"""
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

import worktree_guard

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "iphone_allow.py")
ROOT_SCRIPT = os.path.join(_PLUGIN, "lib", "iphone_check.py")

_UUID = "00000000-0000-0000-0000-000000000000"
_OTHER_ROOT_SCRIPT = "/tmp/other/plugin/lib/iphone_check.py"
_ALLOWED = f"python3 -B {ROOT_SCRIPT} preflight"

_spec = importlib.util.spec_from_file_location("iphone_allow_test", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_ALLOW_OUT = {"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "superheroes: this plugin's own iPhone check command (lib/iphone_check.py)"}}


def _payload(command, **extra):
    return {"tool_name": "Bash", "tool_input": {"command": command}, **extra}


def _decide(payload, environ=None):
    return hook.decide(payload, hook.plugin_roots({} if environ is None else environ))


def _run_hook(stdin_text):
    return subprocess.run(["python3", _HOOK], input=stdin_text,
                          capture_output=True, text=True, timeout=10)


_ALLOWED_ROWS = [
    # axis: preflight from the plugin's own root is approved
    f"python3 -B {ROOT_SCRIPT} preflight --issue-names-check",
    # axis: boot is approved
    f"python3 -B {ROOT_SCRIPT} boot --phone {_UUID}",
    # axis: open is approved, and a quoted URL keeps its `&` and `?` out of the operator check
    f"python3 -B {ROOT_SCRIPT} open --phone {_UUID} --url 'http://127.0.0.1:3000/a?b=c&d=e' --run-dir /tmp/r",
    # axis: drive tap is approved
    f"python3 -B {ROOT_SCRIPT} drive --phone {_UUID} -- tap --label Continue",
    # axis: drive type is approved
    f"python3 -B {ROOT_SCRIPT} drive --phone {_UUID} -- type 'hello'",
    # axis: drive button is approved
    f"python3 -B {ROOT_SCRIPT} drive --phone {_UUID} -- button home",
    # axis: drive swipe is approved
    f"python3 -B {ROOT_SCRIPT} drive --phone {_UUID} -- swipe --start-x 300 --start-y 400 --end-x 50 --end-y 400",
    # axis: drive describe-ui is approved
    f"python3 -B {ROOT_SCRIPT} drive --phone {_UUID} -- describe-ui",
    # axis: shot is approved
    f"python3 -B {ROOT_SCRIPT} shot --phone {_UUID} --out /tmp/a.png --run-dir /tmp/r --token t",
    # axis: read is approved
    f"python3 -B {ROOT_SCRIPT} read --run-dir /tmp/r --token t --where browser",
    # axis: judge with its stdin redirect is approved
    f"python3 -B {ROOT_SCRIPT} judge < /tmp/step.json",
    # axis: render is approved
    f"python3 -B {ROOT_SCRIPT} render --in /tmp/check.json",
    # axis: the `-B` flag is optional
    f"python3 {ROOT_SCRIPT} preflight",
    # axis: a quoted script path is the same path
    f'python3 -B "{ROOT_SCRIPT}" preflight',
]

_NO_DECISION_ROWS = [
    # axis: another plugin root's iphone_check.py is not this plugin's
    f"python3 -B {_OTHER_ROOT_SCRIPT} preflight",
    # axis: a relative script path is refused
    "python3 -B lib/iphone_check.py preflight",
    # axis: a `..` component is refused even when it normalizes to the approved path
    f"python3 -B {os.path.join(_PLUGIN, 'lib', '..', 'lib', 'iphone_check.py')} preflight",
    # axis: the plugin's own other scripts are not approved
    f"python3 -B {os.path.join(_PLUGIN, 'lib', 'launcher.py')} preflight",
    # axis: `;` joins a second command
    f"{_ALLOWED} ; rm -rf /tmp/x",
    # axis: `&&` joins a second command
    f"{_ALLOWED} && echo x",
    # axis: `||` joins a second command
    f"{_ALLOWED} || echo x",
    # axis: a pipe is a second command
    f"{_ALLOWED} | cat",
    # axis: a trailing `&` backgrounds and may join a command
    f"{_ALLOWED} &",
    # axis: an output redirect is refused
    f"{_ALLOWED} > /tmp/out",
    # axis: an append redirect is refused
    f"{_ALLOWED} >> /tmp/out",
    # axis: an fd redirect is refused
    f"{_ALLOWED} 2>&1",
    # axis: the judge stdin redirect on a non-judge verb is refused
    f"python3 -B {ROOT_SCRIPT} preflight < /tmp/x",
    # axis: a `#` hides the rest from default shlex while Bash runs it (brief-check F1)
    f"python3 -B {ROOT_SCRIPT} preflight#x; printf ESCAPE",
    # axis: `$(...)` substitution inside an argument is refused
    f"python3 -B {ROOT_SCRIPT} boot --phone $(id)",
    # axis: backtick substitution inside an argument is refused
    f"python3 -B {ROOT_SCRIPT} boot --phone `id`",
    # axis: a variable reference is refused
    f"python3 -B {ROOT_SCRIPT} boot --phone $UDID",
    # axis: a backslash is refused
    f"python3 -B {ROOT_SCRIPT} boot --phone a\\ b",
    # axis: a newline joins two commands
    f"{_ALLOWED}\nrm -rf /tmp/x",
    # axis: a carriage return is refused
    f"{_ALLOWED}\rrm -rf /tmp/x",
    # axis: a NUL is refused
    f"{_ALLOWED}\0",
    # axis: an unknown verb is refused
    f"python3 -B {ROOT_SCRIPT} nuke",
    # axis: no verb is refused
    f"python3 -B {ROOT_SCRIPT}",
    # axis: drive without `--` is refused
    f"python3 -B {ROOT_SCRIPT} drive --phone X tap",
    # axis: drive with `--` and nothing after it is refused
    f"python3 -B {ROOT_SCRIPT} drive --phone X --",
    # axis: an unknown drive step is refused
    f"python3 -B {ROOT_SCRIPT} drive --phone X -- erase",
    # axis: drive screenshot is excluded (the pilot uses the shot verb)
    f"python3 -B {ROOT_SCRIPT} drive --phone X -- screenshot",
    # axis: drive list-simulators is excluded (the handed IDs are the pilot's only phones)
    f"python3 -B {ROOT_SCRIPT} drive --phone X -- list-simulators",
    # axis: only bare `python3` is the interpreter — `python`
    f"python -B {ROOT_SCRIPT} preflight",
    # axis: only bare `python3` is the interpreter — an absolute path
    f"/usr/bin/python3 -B {ROOT_SCRIPT} preflight",
    # axis: only bare `python3` is the interpreter — `env`
    f"env python3 -B {ROOT_SCRIPT} preflight",
    # axis: only bare `python3` is the interpreter — an assignment prefix
    f"FOO=1 python3 -B {ROOT_SCRIPT} preflight",
    # axis: `-c` is not an accepted interpreter flag
    "python3 -c 'print(1)'",
    # axis: an extra interpreter flag is refused
    f"python3 -B -X x {ROOT_SCRIPT} preflight",
    # axis: `-B` twice is refused
    f"python3 -B -B {ROOT_SCRIPT} preflight",
    # axis: an unclosed quote is a parse doubt
    f"python3 -B {ROOT_SCRIPT} open --url 'http://x",
    # axis: an empty command is refused
    "",
    # axis: a whitespace-only command is refused
    "   ",
]


@pytest.mark.parametrize("command", _ALLOWED_ROWS)
def test_own_iphone_check_is_allowed(command):
    assert _decide(_payload(command)) is True


@pytest.mark.parametrize("command", _NO_DECISION_ROWS)
def test_everything_else_gets_no_decision(command):
    assert _decide(_payload(command)) is False


def test_other_root_gets_no_decision():
    # axis: rule 6, the root comparison — another root's lib/iphone_check.py is not this plugin's
    assert _decide(_payload(f"python3 -B {_OTHER_ROOT_SCRIPT} preflight")) is False


@pytest.mark.parametrize("payload", [
    # axis: payload not a dict
    [1, 2, 3],
    "python3",
    None,
    # axis: tool_name missing
    {"tool_input": {"command": _ALLOWED}},
    # axis: tool_name not Bash
    {"tool_name": "Edit", "tool_input": {"command": _ALLOWED}},
    {"tool_name": "bash", "tool_input": {"command": _ALLOWED}},
    # axis: tool_input missing or not a dict
    {"tool_name": "Bash"},
    {"tool_name": "Bash", "tool_input": "bad"},
    # axis: command missing or not a string
    {"tool_name": "Bash", "tool_input": {}},
    {"tool_name": "Bash", "tool_input": {"command": None}},
    {"tool_name": "Bash", "tool_input": {"command": ["python3"]}},
    {"tool_name": "Bash", "tool_input": {"command": 7}},
])
def test_malformed_payload_gets_no_decision(payload):
    assert _decide(payload) is False


# --- the worktree guard's deny still wins -------------------------------------

def test_classifier_deny_wins(monkeypatch):
    # axis: rule 10 — an otherwise-allowed command is refused when the worktree guard says deny
    command = f"python3 -B {ROOT_SCRIPT} preflight"
    assert _decide(_payload(command)) is True, "precondition: the command is allowed before the patch"
    monkeypatch.setattr(worktree_guard, "classify", lambda command, cwd: ("deny", "x"))
    assert _decide(_payload(command)) is False


def test_classifier_raise_gets_no_decision(monkeypatch):
    # axis: rule 10 — a classifier that raises is no decision, never allow
    def boom(command, cwd):
        raise RuntimeError("simulated")

    monkeypatch.setattr(worktree_guard, "classify", boom)
    assert _decide(_payload(f"python3 -B {ROOT_SCRIPT} preflight")) is False


def test_classifier_raise_through_main_prints_nothing_and_exits_zero(monkeypatch, capsys):
    # axis: the process contract — an internal error is silence and exit 0, not a traceback
    def boom(command, cwd):
        raise RuntimeError("simulated")

    monkeypatch.setattr(worktree_guard, "classify", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload(f"python3 -B {ROOT_SCRIPT} preflight"))))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_classifier_receives_command_and_cwd(monkeypatch):
    # axis: rule 10 consults the guard's own classifier with the payload's command and cwd
    seen = []
    monkeypatch.setattr(worktree_guard, "classify", lambda command, cwd: seen.append((command, cwd)) or ("allow", ""))
    command = f"python3 -B {ROOT_SCRIPT} preflight"
    assert _decide(_payload(command, cwd="/some/cwd")) is True
    assert seen == [(command, "/some/cwd")]


# --- the plugin root from the environment -------------------------------------

def test_plugin_root_from_environment_is_allowed(tmp_path):
    # axis: an absolute CLAUDE_PLUGIN_ROOT adds its lib/iphone_check.py to the approved scripts
    d = str(tmp_path)
    command = f"python3 -B {os.path.join(d, 'lib', 'iphone_check.py')} preflight"
    assert _decide(_payload(command), {"CLAUDE_PLUGIN_ROOT": d}) is True
    # axis: the same path without the environment root is another root's script
    assert _decide(_payload(command), {}) is False
    # axis: the file-derived root still counts when the environment root is set
    assert _decide(_payload(f"python3 -B {ROOT_SCRIPT} preflight"), {"CLAUDE_PLUGIN_ROOT": d}) is True


def test_relative_plugin_root_in_environment_is_ignored():
    # axis: a relative CLAUDE_PLUGIN_ROOT adds nothing — only the file-derived root counts
    env = {"CLAUDE_PLUGIN_ROOT": "some/relative/root"}
    assert hook.plugin_roots(env) == hook.plugin_roots({})
    command = f"python3 -B {os.path.join(os.getcwd(), 'some/relative/root', 'lib', 'iphone_check.py')} preflight"
    assert _decide(_payload(command), env) is False


def test_plugin_roots_carry_normpath_and_realpath(tmp_path):
    # axis: both the normpath and the realpath of each root are approved (a symlinked install)
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    roots = hook.plugin_roots({"CLAUDE_PLUGIN_ROOT": str(link)})
    assert os.path.normpath(str(link)) in roots
    assert os.path.realpath(str(link)) in roots
    assert os.path.dirname(os.path.dirname(os.path.abspath(_HOOK))) in roots


# --- the real hook as a process ------------------------------------------------

def test_process_allow_row_prints_one_allow_line():
    r = _run_hook(json.dumps(_payload(f"python3 -B {ROOT_SCRIPT} preflight")))
    assert r.returncode == 0
    assert r.stdout.count("\n") == 1
    assert json.loads(r.stdout) == _ALLOW_OUT


def test_process_judge_redirect_row_is_allowed():
    r = _run_hook(json.dumps(_payload(f"python3 -B {ROOT_SCRIPT} judge < /tmp/step.json")))
    assert r.returncode == 0
    assert json.loads(r.stdout) == _ALLOW_OUT


def test_process_no_decision_row_prints_nothing():
    r = _run_hook(json.dumps(_payload(f"python3 -B {ROOT_SCRIPT} preflight ; rm -rf /tmp/x")))
    assert r.returncode == 0
    assert r.stdout == ""


def test_process_other_root_row_prints_nothing():
    r = _run_hook(json.dumps(_payload(f"python3 -B {_OTHER_ROOT_SCRIPT} preflight")))
    assert r.returncode == 0
    assert r.stdout == ""


@pytest.mark.parametrize("stdin_text", [
    # axis: empty stdin is a payload we could not receive — silence, exit 0
    "",
    # axis: non-JSON stdin — silence, exit 0
    "not json {",
    # axis: a JSON payload that is not an object — silence, exit 0
    "[1,2,3]",
    # axis: a non-Bash tool — silence, exit 0
    json.dumps({"tool_name": "Edit", "tool_input": {"command": _ALLOWED}}),
])
def test_process_bad_stdin_prints_nothing_and_exits_zero(stdin_text):
    r = _run_hook(stdin_text)
    assert r.returncode == 0
    assert r.stdout == ""


def test_hook_never_prints_deny_or_ask():
    # axis: the hook only ever allows or stays silent — refusal belongs to the worktree guard
    for command in (f"python3 -B {ROOT_SCRIPT} nuke", "rm -rf /", f"python3 -B {_OTHER_ROOT_SCRIPT} preflight"):
        r = _run_hook(json.dumps(_payload(command)))
        assert r.returncode == 0
        assert "deny" not in r.stdout and "ask" not in r.stdout
