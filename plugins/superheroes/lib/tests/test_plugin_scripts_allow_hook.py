"""plugin_scripts_allow.py — the PreToolUse(Bash) hook that approves the plugin's own helper scripts (#2140).

The hook prints `permissionDecision: "allow"` iff the whole command is one plain call
`python3 [-B] <plugin root>/lib/<name>.py [args…]` with `<name>` one of eight of this plugin's own
scripts (for `round_driver.py`: one of the driver's approved verbs, no flag that hands it a command line, and a session
folder whose saved state still matches the driver's own mirror stamp) and the worktree guard's
classifier does not deny it. Every other input — any other command, any parse
doubt, any internal error — prints nothing and exits 0.

Two channels: `decide` / `plugin_roots` in-process (the truth table), and the real hook as a
subprocess (the stdout and exit-code contract).
"""
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

import mode_registry
import round_driver
import session_contract
import worktree_guard

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "plugin_scripts_allow.py")
LIB = os.path.join(_PLUGIN, "lib")
DRIVER = os.path.join(LIB, "round_driver.py")
GUARD = os.path.join(LIB, "dispatch_guard.py")

_OTHER_ROOT_LIB = "/tmp/other/plugin/lib"
# the fresh-session case the hook allows is a real session folder with no state file yet. It is made at
# run time (the `fresh` fixture) and put in place of this placeholder inside each test, so no collected
# parameter value or id depends on a per-process path (pytest-xdist workers must collect identical ids)
_SESSION = "{SESSION}"
_ALLOWED = f"python3 -B {DRIVER} next --session-dir {_SESSION}"
_SEAT = '{"vendor":"codex","model":null,"effort":null,"role":"mechanical"}'

_spec = importlib.util.spec_from_file_location("plugin_scripts_allow_test", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_EIGHT_SCRIPTS = [
    "round_driver.py", "break_it.py", "review_store.py", "mode_reconcile.py",
    "calibration_resolve.py", "size_count.py", "order_lint.py", "dispatch_guard.py",
]


def _driver_subcommands():
    # the driver's own argparse parser is the source of truth for which verbs exist
    import argparse
    parser = round_driver.build_parser()
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert actions, "round_driver.build_parser() has no subparsers action — the census is inert"
    return set(actions[0].choices)


def _allow_out(name):
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "superheroes: this plugin's own review-loop or build helper "
                                    f"script (lib/{name})"}}


def _payload(command, **extra):
    return {"tool_name": "Bash", "tool_input": {"command": command}, **extra}


def _decide(payload, environ=None):
    return hook.decide(payload, hook.plugin_roots({} if environ is None else environ))


def _run_hook(stdin_text):
    return subprocess.run(["python3", _HOOK], input=stdin_text,
                          capture_output=True, text=True, timeout=10)


def _short(command):
    return command.replace(_PLUGIN, "<root>").replace("\n", "\\n").replace("\r", "\\r").replace("\0", "\\0")


@pytest.fixture
def fresh(tmp_path):
    # a real session folder with no state file yet, made per test
    d = tmp_path / "fresh-session"
    d.mkdir()
    return str(d)


def _fill(text, fresh):
    return text.replace(_SESSION, fresh)


def _fill_deep(value, fresh):
    if isinstance(value, str):
        return _fill(value, fresh)
    if isinstance(value, dict):
        return {k: _fill_deep(v, fresh) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill_deep(v, fresh) for v in value]
    return value


def test_the_lists_are_pinned():
    # axis: the approved-script list and the command-flag list are exactly the ruled ones (the driver verb
    # list is checked against the driver's own parser, not a copy)
    assert hook.APPROVED_SCRIPTS == frozenset(_EIGHT_SCRIPTS)
    assert tuple(hook.COMMAND_FLAGS) == ("verify-command", "break-it-interpreter", "records-path")


@pytest.mark.parametrize("name", _EIGHT_SCRIPTS)
def test_each_listed_script_at_the_plugin_root_is_allowed(name, fresh):
    # axis: each of the eight listed scripts at the plugin's own root is approved, `-B` and all
    args = f"next --session-dir {fresh}" if name == "round_driver.py" else "check --x 1"
    command = f"python3 -B {os.path.join(LIB, name)} {args}"
    got = _decide(_payload(command))
    assert got is True, _short(command)


def test_every_approved_driver_verb_is_a_parser_subcommand():
    # axis: a verb the driver retired cannot stay auto-approved — every approved verb is a subcommand
    # of the driver's own argparse parser
    known = _driver_subcommands()
    assert known and "next" in known, sorted(known)
    assert hook.ROUND_DRIVER_VERBS, "the hook approves no driver verb"
    unknown = sorted(hook.ROUND_DRIVER_VERBS - known)
    assert not unknown, "approved but not a round_driver subcommand: %s" % unknown


@pytest.mark.parametrize("verb", sorted(hook.ROUND_DRIVER_VERBS))
def test_each_driver_verb_is_allowed(verb, fresh):
    # axis: each approved round_driver verb is approved
    command = f"python3 -B {DRIVER} {verb} --session-dir {fresh}"
    got = _decide(_payload(command))
    assert got is True, _short(command)


_ALLOWED_ROWS = [
    # axis: the `-B` flag is optional
    f"python3 {DRIVER} next --session-dir {_SESSION}",
    # axis: a quoted script path is the same path
    f'python3 -B "{DRIVER}" next --session-dir {_SESSION}',
    # axis: a single-quoted JSON argument keeps its `{`, `}` and `*` out of the expansion scan
    f"python3 -B {GUARD} check --seat '{_SEAT}'",
    # axis: a single-quoted argument holding `{`, `}` and `*` is allowed
    f"python3 -B {GUARD} check --seat '{{a}}*'",
    # axis: a double-quoted argument holding `?`, `[`, `]` and `~` is allowed
    f'python3 -B {GUARD} check --seat "a?[b]~c"',
    # axis: quote state is tracked — an apostrophe inside double quotes does not open a single quote
    f"python3 -B {GUARD} check --seat \"it's\"",
    # axis: quote state is tracked — a double quote inside single quotes does not open a double quote
    f"python3 -B {GUARD} check --seat 'say \"hi\"'",
    # axis: a driver flag that is not a command flag is allowed (`--vendors` is not an abbreviation of either)
    f"python3 -B {DRIVER} next --session-dir {_SESSION} --leg code --vendors '[\"claude\",\"codex\"]' --max-rounds 3",
    # axis: `--flag=value` is allowed for a flag that is not a command flag
    f"python3 -B {DRIVER} next --session-dir={_SESSION} --seat-map '{{\"a\":1}}'",
    # axis: a driver verb with a later `-`-prefixed value that is not a long option is allowed
    f"python3 -B {DRIVER} attest --session-dir {_SESSION} --failure 3 --note -x",
]


@pytest.mark.parametrize("command", _ALLOWED_ROWS, ids=_short)
def test_allowed_rows(command, fresh):
    command = _fill(command, fresh)
    got = _decide(_payload(command))
    assert got is True, _short(command)


_NO_DECISION_ROWS = [
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
    # axis: an output redirect is refused (no redirect exception here)
    f"{_ALLOWED} > /tmp/out",
    # axis: an append redirect is refused
    f"{_ALLOWED} >> /tmp/out",
    # axis: an input redirect is refused (no redirect exception here)
    f"{_ALLOWED} < /tmp/in",
    # axis: an fd redirect is refused
    f"{_ALLOWED} 2>&1",
    # axis: a subshell paren is an operator token
    f"( {_ALLOWED} )",
    # axis: `$(...)` substitution is refused
    f"python3 -B {DRIVER} next --session-dir $(id)",
    # axis: backtick substitution is refused
    f"python3 -B {DRIVER} next --session-dir `id`",
    # axis: a variable reference is refused
    f"python3 -B {DRIVER} next --session-dir $SESSION",
    # axis: the skills' own `ROOT_DIR=…; python3 -B "$ROOT_DIR/lib/…"` form is refused
    f'ROOT_DIR="{_PLUGIN}"; python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir /tmp/s',
    # axis: a `#` hides the rest from default shlex while Bash runs it
    f"python3 -B {DRIVER} next#x; printf ESCAPE",
    # axis: a backslash is refused
    f"python3 -B {DRIVER} next --session-dir a\\ b",
    # axis: a newline joins two commands
    f"{_ALLOWED}\nrm -rf /tmp/x",
    # axis: a carriage return is refused
    f"{_ALLOWED}\rrm -rf /tmp/x",
    # axis: a NUL is refused
    f"{_ALLOWED}\0",
    # axis: an unquoted `*` is a glob
    f"python3 -B {DRIVER} next --session-dir /tmp/*",
    # axis: an unquoted `~/x` is a tilde expansion
    "python3 -B " + DRIVER + " next --session-dir ~/x",
    # axis: an unquoted `?` is a glob
    f"python3 -B {DRIVER} next --session-dir /tmp/s?",
    # axis: an unquoted `[` `]` pair is a glob
    f"python3 -B {DRIVER} next --session-dir /tmp/[ab]",
    # axis: an unquoted brace is a brace expansion
    f"python3 -B {DRIVER} next --session-dir /tmp/{{a,b}}",
    # axis: an unbalanced single quote is a parse doubt
    f"python3 -B {GUARD} check --seat 'x",
    # axis: an unbalanced double quote is a parse doubt
    f'python3 -B {GUARD} check --seat "x',
    # axis: a quote closed by the other kind stays open
    f"python3 -B {GUARD} check --seat 'x\"",
    # axis: a listed name under another plugin root is not this plugin's
    f"python3 -B {_OTHER_ROOT_LIB}/round_driver.py next --session-dir /tmp/s",
    # axis: a listed name under another plugin root's lib is not this plugin's (a non-driver script)
    f"python3 -B {_OTHER_ROOT_LIB}/dispatch_guard.py check",
    # axis: a `..` component is refused even when it normalizes to the approved path
    f"python3 -B {os.path.join(LIB, '..', 'lib', 'round_driver.py')} next --session-dir /tmp/s",
    # axis: a `..` component is refused when it climbs out of the plugin root to another `lib`
    f"python3 -B {os.path.join(_PLUGIN, '..', 'x', 'lib', 'round_driver.py')} next --session-dir /tmp/s",
    # axis: a relative script path is refused
    "python3 -B lib/round_driver.py next --session-dir /tmp/s",
    # axis: a script in a nested directory of lib is not the lib script
    f"python3 -B {os.path.join(LIB, 'tests', 'round_driver.py')} next --session-dir /tmp/s",
    # axis: an unlisted plugin script gets no decision — engine_dispatch.py
    f"python3 -B {os.path.join(LIB, 'engine_dispatch.py')} check",
    # axis: an unlisted plugin script gets no decision — seat_map.py
    f"python3 -B {os.path.join(LIB, 'seat_map.py')} check",
    # axis: an unlisted plugin script gets no decision — build_lane.py
    f"python3 -B {os.path.join(LIB, 'build_lane.py')} check",
    # axis: an unlisted plugin script gets no decision — cloud_builder.py
    f"python3 -B {os.path.join(LIB, 'cloud_builder.py')} check",
    # axis: an unlisted plugin script gets no decision — review_record.py
    f"python3 -B {os.path.join(LIB, 'review_record.py')} check",
    # axis: a script that replaces a caller-named path gets no decision
    f"python3 -B {os.path.join(LIB, 'review_result.py')} write --path /tmp/x --action halt --round 1",
    # axis: the program must be bare `python3` — `python`
    f"python -B {DRIVER} next --session-dir /tmp/s",
    # axis: the program must be bare `python3` — `bash`
    f"bash {DRIVER} next --session-dir /tmp/s",
    # axis: the program must be bare `python3` — `node`
    f"node {DRIVER} next --session-dir /tmp/s",
    # axis: the program must be bare `python3` — an absolute path
    f"/usr/bin/python3 -B {DRIVER} next --session-dir /tmp/s",
    # axis: the program must be bare `python3` — `env`
    f"env python3 -B {DRIVER} next --session-dir /tmp/s",
    # axis: the program must be bare `python3` — an assignment prefix
    f"FOO=1 python3 -B {DRIVER} next --session-dir /tmp/s",
    # axis: `python3 -c` runs text, not a script
    "python3 -c 'print(1)'",
    # axis: `python3 -m` runs a module, not a script
    "python3 -m pytest",
    # axis: an extra interpreter flag is refused
    f"python3 -B -X x {DRIVER} next --session-dir /tmp/s",
    # axis: `-B` twice is refused
    f"python3 -B -B {DRIVER} next --session-dir /tmp/s",
    # axis: a command with only `python3` is refused
    "python3",
    # axis: a command with only `python3 -B` is refused
    "python3 -B",
    # axis: an empty command is refused
    "",
    # axis: a whitespace-only command is refused
    "   ",
    # axis: the driver's `run-verify` verb runs the session's verify command
    f"python3 -B {DRIVER} run-verify --session-dir /tmp/s",
    # axis: the driver's `rule` verb records an owner ruling
    f"python3 -B {DRIVER} rule --session-dir /tmp/s --ruling-file /tmp/r --by x",
    # axis: `--help` is not a verb
    f"python3 -B {DRIVER} --help",
    # axis: no verb is refused (E8)
    f"python3 -B {DRIVER}",
    # axis: an option before the verb is refused
    f"python3 -B {DRIVER} --session-dir /tmp/s next",
    # axis: an unknown verb is refused
    f"python3 -B {DRIVER} nuke --session-dir /tmp/s",
    # axis: `--verify-command` in full is refused (the driver stores it and runs it later)
    f"{_ALLOWED} --verify-command none",
    # axis: `--verify-command=value` is refused
    f"{_ALLOWED} --verify-command=none",
    # axis: a quoted flag token is the same flag
    f"{_ALLOWED} '--verify-command' none",
    # axis: argparse prefix abbreviation — `--verify-c`
    f"{_ALLOWED} --verify-c x",
    # axis: argparse prefix abbreviation — `--verify`
    f"{_ALLOWED} --verify x",
    # axis: argparse prefix abbreviation — `--v`
    f"{_ALLOWED} --v x",
    # axis: `--break-it-interpreter` in full is refused
    f"{_ALLOWED} --break-it-interpreter python3",
    # axis: `--break-it-interpreter=value` abbreviated is refused
    f"{_ALLOWED} --break-it-i=x",
    # axis: argparse prefix abbreviation — `--br`
    f"{_ALLOWED} --br x",
    # axis: `--records-path` names a file the driver later replaces — refused in full, `=value` and abbreviated
    f"{_ALLOWED} --records-path /tmp/notes.txt",
    f"{_ALLOWED} --records-path=/tmp/notes.txt",
    f"{_ALLOWED} --rec /tmp/notes.txt",
    f"python3 -B {DRIVER} submit --session-dir /tmp/s --records-path /tmp/notes.txt",
    # axis: a command flag is refused on any approved verb, not only `next`
    f"python3 -B {DRIVER} submit --session-dir /tmp/s --verify-command x",
    # axis: brief-check F1 — a brace expansion spells the flag twice (`--verify-command=id` x2)
    f"{_ALLOWED} --{{verify-command,verify-command}}=id",
    # axis: a bare `--` ends option parsing and is refused
    f"{_ALLOWED} --",
]


@pytest.mark.parametrize("command", _NO_DECISION_ROWS, ids=_short)
def test_everything_else_gets_no_decision(command, fresh):
    command = _fill(command, fresh)
    got = _decide(_payload(command))
    assert got is False, _short(command)


# The hook's own set, plus the seven characters it must refuse: parametrizing over the hook's set alone
# would drop a character's row the moment it left the set, so removing it could never turn a row red.
_REFUSED_UNDER_TEST = sorted(hook._REFUSED_CHARS | set("#$`\\\n\r\0"))


@pytest.mark.parametrize("char", _REFUSED_UNDER_TEST, ids=lambda c: f"U+{ord(c):04X}")
def test_each_refused_character_alone_gets_no_decision(char):
    # axis: each refused character is refused on its own — carried inside a single-quoted word of an
    # otherwise-approvable call, so no expansion, operator, path or verb check can reject it instead
    def command(c):
        return f"python3 -B {GUARD} check --seat 'a{c}b'"

    plain = _decide(_payload(command("")))
    assert plain is True, "isolation guard: the command without the character is approvable"
    got = _decide(_payload(command(char)))
    assert got is False, _short(command(char))


@pytest.mark.parametrize("char", sorted(set("{}*?[]~")))
def test_each_expansion_character_is_refused_unquoted_and_allowed_quoted(char):
    # axis: each of `{ } * ? [ ] ~` is refused outside quotes and passes inside single and double quotes
    def command(word):
        return f"python3 -B {GUARD} check --seat {word}"

    single = _decide(_payload(command(f"'a{char}b'")))
    assert single is True, "isolation guard: single-quoted is approvable"
    double = _decide(_payload(command(f'"a{char}b"')))
    assert double is True, "isolation guard: double-quoted is approvable"
    got = _decide(_payload(command(f"a{char}b")))
    assert got is False, _short(command(f"a{char}b"))


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
def test_malformed_payload_gets_no_decision(payload, fresh):
    payload = _fill_deep(payload, fresh)
    got = _decide(payload)
    assert got is False, repr(payload)


# --- F2: `run-verify` is refused by its verb, whatever the session's state holds -

def test_run_verify_gets_no_decision_whatever_the_session_state_holds(tmp_path):
    # axis: F2 — `run-verify` is refused by its verb alone, with a fresh folder and with a driver-stamped
    # state that names a verify command; a hand-written state without the driver's stamp is refused for
    # every verb, `next` included
    d = str(tmp_path)
    run_verify = f"python3 -B {DRIVER} run-verify --session-dir {d}"
    nxt = f"python3 -B {DRIVER} next --session-dir {d}"
    assert _decide(_payload(run_verify)) is False
    assert _decide(_payload(nxt)) is True
    state = json.dumps({"config": {"verifyCommand": "touch /tmp/escaped"}}).encode("utf-8")
    s = _driver_session(tmp_path, state)
    run_verify = f"python3 -B {DRIVER} run-verify --session-dir {s}"
    nxt = f"python3 -B {DRIVER} next --session-dir {s}"
    assert _decide(_payload(run_verify)) is False
    assert _decide(_payload(nxt)) is True
    (s / session_contract.STATE_FILE).write_bytes(state + b" ")
    assert _decide(_payload(nxt)) is False


def test_extra_audit_gets_no_decision(tmp_path):
    # axis: the driver's `extra-audit` verb reopens a finished session and reads the PR's comments, so
    # like `rule` it is not on the verb list and is left to the normal permission check
    d = str(tmp_path)
    order = str(tmp_path / "order.md")
    extra_audit = f"python3 -B {DRIVER} extra-audit --session-dir {d} --order-file {order} --by advisor --pr 1"
    nxt = f"python3 -B {DRIVER} next --session-dir {d}"
    assert _decide(_payload(extra_audit)) is False
    assert _decide(_payload(nxt)) is True


# --- the session's saved state must be the driver's own ------------------------

_STATE = b'{"config":{"verifyCommand":"none"},"round":1}'


def _driver_session(tmp_path, state_bytes):
    """A session folder holding `state_bytes` as loop-state.json and a mirror stamped as
    `round_driver._mirror_bytes` stamps it (same `stateSha256` of the exact bytes)."""
    d = tmp_path / "session"
    d.mkdir()
    (d / session_contract.STATE_FILE).write_bytes(state_bytes)
    mirror = {"schema": round_driver.MIRROR_SCHEMA, "sessionId": None,
              "stateSha256": hashlib.sha256(state_bytes).hexdigest(),
              "state": state_bytes.decode("utf-8")}
    (d / round_driver.MIRROR_FILE).write_text(json.dumps(mirror, sort_keys=True, separators=(",", ":")))
    return d


def _submit(*args):
    return f"python3 -B {DRIVER} submit " + " ".join(str(a) for a in args)


def test_a_matching_session_is_allowed(tmp_path):
    # axis: a session whose state matches the driver's mirror stamp is allowed (isolation guard for the rows below)
    d = _driver_session(tmp_path, _STATE)
    assert _decide(_payload(_submit("--session-dir", d))) is True


def test_a_state_edited_after_the_mirror_was_written_gets_no_decision(tmp_path):
    # axis: a driver call whose session state does not match the driver's own mirror stamp gets no decision (E1)
    d = _driver_session(tmp_path, _STATE)
    command = _submit("--session-dir", d)
    assert _decide(_payload(command)) is True, "isolation guard: the matching session is allowed"
    (d / session_contract.STATE_FILE).write_bytes(_STATE.replace(b'"none"', b'"touch /tmp/escaped"'))
    assert _decide(_payload(command)) is False


def test_a_state_with_no_mirror_gets_no_decision(tmp_path):
    # axis: a state file with no mirror beside it gets no decision (E2)
    d = _driver_session(tmp_path, _STATE)
    (d / round_driver.MIRROR_FILE).unlink()
    assert _decide(_payload(_submit("--session-dir", d))) is False


@pytest.mark.parametrize("mirror_text", ["not json {", "[1,2]", "{}", '{"stateSha256":7}', ""])
def test_a_mirror_that_is_not_a_stamp_gets_no_decision(tmp_path, mirror_text):
    # axis: a mirror that is not JSON, not an object, or without a string `stateSha256` gets no decision (E3)
    d = _driver_session(tmp_path, _STATE)
    (d / round_driver.MIRROR_FILE).write_text(mirror_text)
    assert _decide(_payload(_submit("--session-dir", d))) is False


def test_session_dir_given_twice_gets_no_decision(tmp_path, fresh):
    # axis: `--session-dir` named twice gets no decision, in either spelling (E4)
    d = _driver_session(tmp_path, _STATE)
    assert _decide(_payload(_submit("--session-dir", d, "--session-dir", fresh))) is False
    assert _decide(_payload(_submit(f"--session-dir={d}", f"--session-dir={fresh}"))) is False
    assert _decide(_payload(_submit("--session-dir", d, f"--session-dir={fresh}"))) is False


def test_session_dir_missing_gets_no_decision():
    # axis: a driver call with no `--session-dir` gets no decision, and so does one with no value (E5)
    assert _decide(_payload(_submit())) is False
    assert _decide(_payload(_submit("--leg", "code"))) is False
    assert _decide(_payload(_submit("--session-dir"))) is False


@pytest.mark.parametrize("abbrev", ["--s", "--se", "--session", "--session-d"])
def test_an_abbreviated_session_dir_gets_no_decision(abbrev, fresh):
    # axis: an argparse abbreviation of `--session-dir` gets no decision, alone or beside the full option (E6)
    assert _decide(_payload(_submit(abbrev, "/x"))) is False
    assert _decide(_payload(_submit("--session-dir", fresh, abbrev, "/x"))) is False
    assert _decide(_payload(_submit("--session-dir", fresh, f"{abbrev}=/x"))) is False


def test_a_relative_session_dir_with_no_cwd_gets_no_decision(tmp_path):
    # axis: a relative `--session-dir` with no absolute payload `cwd` gets no decision (E7)
    _driver_session(tmp_path, _STATE)
    command = _submit("--session-dir", "session")
    assert _decide(_payload(command)) is False
    assert _decide(_payload(command, cwd="relative/cwd")) is False
    assert _decide(_payload(command, cwd=7)) is False
    assert _decide(_payload(command, cwd=str(tmp_path))) is True, "isolation guard: allowed with an absolute cwd"


def test_a_relative_session_dir_is_resolved_against_the_payload_cwd(tmp_path):
    # axis: a relative `--session-dir` joins the payload's absolute `cwd`, and the state there is checked (h)
    d = _driver_session(tmp_path, _STATE)
    command = _submit("--session-dir", "session")
    assert _decide(_payload(command, cwd=str(tmp_path))) is True
    (d / session_contract.STATE_FILE).write_bytes(_STATE + b" ")
    assert _decide(_payload(command, cwd=str(tmp_path))) is False


def test_session_dir_equals_form_is_allowed_for_a_matching_session(tmp_path):
    # axis: `--session-dir=<dir>` is read the same as `--session-dir <dir>` (i)
    d = _driver_session(tmp_path, _STATE)
    assert _decide(_payload(_submit(f"--session-dir={d}"))) is True
    (d / session_contract.STATE_FILE).write_bytes(_STATE + b" ")
    assert _decide(_payload(_submit(f"--session-dir={d}"))) is False


def test_a_fresh_session_with_no_state_file_is_allowed(tmp_path):
    # axis: a session folder holding no loop-state.json (nothing saved yet) is still allowed (E9)
    assert _decide(_payload(_submit("--session-dir", tmp_path))) is True
    assert _decide(_payload(_submit("--session-dir", tmp_path / "not-yet-made"))) is True


def test_an_unreadable_state_or_mirror_gets_no_decision(tmp_path):
    # axis: a state path that cannot be read as a file (here a directory) gets no decision (E8)
    d = _driver_session(tmp_path, _STATE)
    (d / session_contract.STATE_FILE).unlink()
    (d / session_contract.STATE_FILE).mkdir()
    assert _decide(_payload(_submit("--session-dir", d))) is False


def test_an_exception_in_the_session_check_gets_no_decision(fresh):
    # axis: an exception inside the session-state check is no decision, never allow (E8)
    assert hook._session_state_is_drivers(["--session-dir", fresh], None) is True, "isolation guard"
    assert hook._session_state_is_drivers([None], None) is False
    assert hook._session_state_is_drivers(["--session-dir", None], None) is False


def test_a_state_the_real_driver_wrote_is_allowed(tmp_path):
    # axis: the stamp the driver itself writes (`_write_state_bytes`) is the stamp the hook accepts
    d = tmp_path / "session"
    d.mkdir()
    round_driver._write_state_bytes(str(d), _STATE)
    assert (d / session_contract.STATE_FILE).read_bytes() == _STATE
    assert _decide(_payload(_submit("--session-dir", d))) is True
    (d / session_contract.STATE_FILE).write_bytes(_STATE + b" ")
    assert _decide(_payload(_submit("--session-dir", d))) is False


# --- the worktree guard's deny still wins --------------------------------------

def test_classifier_deny_wins_on_a_real_destructive_git_mention(monkeypatch, fresh):
    # axis: step 8 — a destructive git mention in an approved call's arguments is `unaccounted` to the
    # real classifier on a calibrated project, which denies it; the hook then gives no decision
    command = f"python3 -B {DRIVER} next --session-dir {fresh} git reset --hard"
    monkeypatch.setattr(mode_registry, "calibration_state", lambda cwd: "uncalibrated")
    assert _decide(_payload(command)) is True, "isolation guard: allowed when the guard allows (uncalibrated)"
    monkeypatch.setattr(mode_registry, "calibration_state", lambda cwd: "calibrated")
    assert worktree_guard.classify(command, "/tmp")[0] == "deny", "precondition: the real classifier denies it"
    assert _decide(_payload(command, cwd="/tmp")) is False


def test_classifier_deny_wins(monkeypatch, fresh):
    # axis: step 8 — an otherwise-allowed command is refused when the worktree guard says deny
    allowed = _fill(_ALLOWED, fresh)
    assert _decide(_payload(allowed)) is True, "precondition: the command is allowed before the patch"
    monkeypatch.setattr(worktree_guard, "classify", lambda command, cwd: ("deny", "x"))
    assert _decide(_payload(allowed)) is False


def test_classifier_raise_gets_no_decision(monkeypatch, fresh):
    # axis: step 8 — a classifier that raises is no decision, never allow (E5)
    def boom(command, cwd):
        raise RuntimeError("simulated")

    monkeypatch.setattr(worktree_guard, "classify", boom)
    assert _decide(_payload(_fill(_ALLOWED, fresh))) is False


def test_classifier_raise_through_main_prints_nothing_and_exits_zero(monkeypatch, capsys, fresh):
    # axis: the process contract — an internal error is silence and exit 0, not a traceback (E5, E9)
    def boom(command, cwd):
        raise RuntimeError("simulated")

    monkeypatch.setattr(worktree_guard, "classify", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload(_fill(_ALLOWED, fresh)))))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_classifier_receives_command_and_cwd(monkeypatch, fresh):
    # axis: step 8 consults the guard's own classifier with the payload's command and cwd
    allowed = _fill(_ALLOWED, fresh)
    seen = []
    monkeypatch.setattr(worktree_guard, "classify", lambda command, cwd: seen.append((command, cwd)) or ("allow", ""))
    assert _decide(_payload(allowed, cwd="/some/cwd")) is True
    assert seen == [(allowed, "/some/cwd")]


# --- the plugin root from the environment -------------------------------------

def test_plugin_root_from_environment_is_allowed(tmp_path, fresh):
    # axis: an absolute CLAUDE_PLUGIN_ROOT adds its lib/<name>.py to the approved scripts
    d = str(tmp_path)
    command = f"python3 -B {os.path.join(d, 'lib', 'round_driver.py')} next --session-dir {fresh}"
    assert _decide(_payload(command), {"CLAUDE_PLUGIN_ROOT": d}) is True
    # axis: the same path without the environment root is another root's script
    assert _decide(_payload(command), {}) is False
    # axis: the file-derived root still counts when the environment root is set
    assert _decide(_payload(_fill(_ALLOWED, fresh)), {"CLAUDE_PLUGIN_ROOT": d}) is True
    # axis: an unlisted name under the environment root is still refused
    other = f"python3 -B {os.path.join(d, 'lib', 'engine_dispatch.py')} check"
    assert _decide(_payload(other), {"CLAUDE_PLUGIN_ROOT": d}) is False


def test_relative_plugin_root_in_environment_is_ignored():
    # axis: a relative CLAUDE_PLUGIN_ROOT adds nothing — only the file-derived root counts (E6)
    env = {"CLAUDE_PLUGIN_ROOT": "some/relative/root"}
    assert hook.plugin_roots(env) == hook.plugin_roots({})
    command = f"python3 -B {os.path.join(os.getcwd(), 'some/relative/root', 'lib', 'round_driver.py')} next --session-dir /tmp/s"
    assert _decide(_payload(command), env) is False


# --- the real hook as a process ------------------------------------------------

@pytest.mark.parametrize("name,args", [
    ("round_driver.py", f"next --session-dir {_SESSION}"),
    ("dispatch_guard.py", "check --x 1"),
])
def test_process_allow_row_prints_one_allow_line(name, args, fresh):
    # axis: the contract — an allowed command prints exactly one allow line naming the real script, and exits 0
    r = _run_hook(json.dumps(_payload(_fill(f"python3 -B {os.path.join(LIB, name)} {args}", fresh))))
    assert r.returncode == 0
    assert r.stdout.count("\n") == 1
    assert json.loads(r.stdout) == _allow_out(name)


@pytest.mark.parametrize("command", [
    # axis: a compound command prints nothing
    f"{_ALLOWED} ; rm -rf /tmp/x",
    # axis: another root's script prints nothing
    f"python3 -B {_OTHER_ROOT_LIB}/round_driver.py next --session-dir /tmp/s",
    # axis: an unlisted script prints nothing
    f"python3 -B {os.path.join(LIB, 'engine_dispatch.py')} check",
    # axis: `run-verify` prints nothing
    f"python3 -B {DRIVER} run-verify --session-dir /tmp/s",
    # axis: a command flag prints nothing
    f"{_ALLOWED} --verify-command none",
])
def test_process_no_decision_row_prints_nothing(command, fresh):
    r = _run_hook(json.dumps(_payload(_fill(command, fresh))))
    assert r.returncode == 0
    assert r.stdout == ""


@pytest.mark.parametrize("stdin_text", [
    # axis: empty stdin is a payload we could not receive — silence, exit 0 (E1)
    "",
    # axis: non-JSON stdin — silence, exit 0 (E1)
    "not json {",
    # axis: a JSON payload that is not an object — silence, exit 0 (E2)
    "[1,2,3]",
    # axis: a non-Bash tool — silence, exit 0 (E2)
    json.dumps({"tool_name": "Edit", "tool_input": {"command": _ALLOWED}}),
    # axis: a missing command — silence, exit 0 (E3)
    json.dumps({"tool_name": "Bash", "tool_input": {}}),
    # axis: a non-string command — silence, exit 0 (E3)
    json.dumps({"tool_name": "Bash", "tool_input": {"command": 7}}),
])
def test_process_bad_stdin_prints_nothing_and_exits_zero(stdin_text, fresh):
    r = _run_hook(_fill(stdin_text, fresh))
    assert r.returncode == 0
    assert r.stdout == ""


def test_hook_never_prints_deny_or_ask():
    # axis: the hook only ever allows or stays silent — refusal belongs to the worktree guard
    for command in (f"python3 -B {DRIVER} nuke", "rm -rf /", f"python3 -B {_OTHER_ROOT_LIB}/round_driver.py next"):
        r = _run_hook(json.dumps(_payload(command)))
        assert r.returncode == 0
        assert "deny" not in r.stdout and "ask" not in r.stdout
