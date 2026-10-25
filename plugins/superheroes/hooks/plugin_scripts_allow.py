#!/usr/bin/env python3
"""PreToolUse(Bash) approver — the plugin approves its own review-loop and build helper scripts (#2140).

Reads the PreToolUse payload from stdin. When the Bash command is, as a whole, one plain call
`python3 [-B] <plugin root>/lib/<name>.py [args…]` with `<name>` on `APPROVED_SCRIPTS` (nine of THIS
plugin's own scripts), and the worktree guard's classifier does not deny it, it emits
`permissionDecision: "allow"`. For every other input it stays silent.

This is a best-effort pattern check over the command text, not a parse of what Bash will run: every
doubt (an unbalanced quote, an expansion character, an operator, a path that is not exactly one of
the approved scripts, an internal error) fails toward no decision, never toward allow. The list is
`APPROVED_SCRIPTS`. What it leaves to the normal permission path: every other plugin script, any
other program, any compound or variable form (`;`, `&&`, `|`, a redirect, `$ROOT_DIR`, `$(…)`, a
backtick), the `round_driver.py` verbs `run-verify` and `rule`, and a `round_driver.py` call that
carries `--verify-command`, `--break-it-interpreter` or `--records-path` (or an argparse
abbreviation of any), because the first two hand a command line to a later run and the third names
a file the driver later replaces with the records export. A listed script may write only its own
fixed file names under a session or store directory its caller names; a script that writes to a path
its caller names verbatim stays off the list. For the round driver, the session's saved state must
also match the stamp the driver wrote beside it, so a hand-edited `loop-state.json` gets no decision.

Contract (fail-closed — "closed" here means no decision, never allow):

- `permissionDecision: "allow"` is printed if and only if `decide` accepts the command. This hook
  never prints `deny` and never prints `ask`; the worktree guard owns refusal.
- stdout is written EXACTLY ONCE, atomically, at the very end — never partial output.
- The whole body is wrapped in try/except. ANY internal failure (empty or unparseable stdin, a
  classifier raise) → silence. The process always exits 0.

Stdlib-only.
"""
import hashlib
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iphone_allow import _REFUSED_CHARS, _is_operator, plugin_roots  # noqa: E402
from session_contract import MIRROR_FILE, STATE_FILE  # noqa: E402

APPROVED_SCRIPTS = frozenset((
    "round_driver.py", "break_it.py", "review_store.py", "grounding_stage.py",
    "mode_reconcile.py", "calibration_resolve.py", "size_count.py", "order_lint.py",
    "dispatch_guard.py",
))
ROUND_DRIVER_VERBS = frozenset((
    "next", "submit", "record-result", "record-missing", "advance", "correct-fixer-refusals",
    "attest", "checkpoint",
))
COMMAND_FLAGS = ("verify-command", "break-it-interpreter", "records-path")

_EXPANSION_CHARS = frozenset("{}*?[]~")


def _allow_json(name):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "superheroes: this plugin's own review-loop or build helper "
                                    "script (lib/%s)" % name}})


def _approved_name(payload, plugin_roots):
    """The approved script's name, or None. Never raises: any error is no decision."""
    try:
        return _match(payload, plugin_roots)
    except Exception:
        return None


def decide(payload, plugin_roots):
    """True to allow, False otherwise. Never raises: any error is no decision."""
    return _approved_name(payload, plugin_roots) is not None


def _unquoted_expansion(command):
    """True when the command has an expansion character outside quotes, or an unbalanced quote."""
    quote = None
    for ch in command:
        if quote is None:
            if ch in _EXPANSION_CHARS:
                return True
            if ch in "'\"":
                quote = ch
        elif ch == quote:
            quote = None
    return quote is not None


def _session_state_is_drivers(rest, cwd):
    """True when `rest` (the tokens after the verb) names its session folder exactly once, as the
    literal `--session-dir`, and that folder holds either no state file or a state file whose sha256
    equals the `stateSha256` of the mirror beside it. Never raises: any error is False."""
    try:
        values = []
        for i, t in enumerate(rest):
            if not t.startswith("--"):
                continue
            stem = t[2:].split("=", 1)[0]
            if stem and stem != "session-dir" and "session-dir".startswith(stem):
                return False
            if t == "--session-dir":
                if i + 1 >= len(rest):
                    return False
                values.append(rest[i + 1])
            elif t.startswith("--session-dir="):
                values.append(t[len("--session-dir="):])
        if len(values) != 1 or not values[0]:
            return False
        session_dir = values[0]
        if not os.path.isabs(session_dir):
            if not isinstance(cwd, str) or not os.path.isabs(cwd):
                return False
            session_dir = os.path.join(cwd, session_dir)
        state_path = os.path.join(session_dir, STATE_FILE)
        if not os.path.lexists(state_path):
            return True
        with open(state_path, "rb") as f:
            state_bytes = f.read()
        with open(os.path.join(session_dir, MIRROR_FILE), "rb") as f:
            mirror = json.loads(f.read().decode("utf-8"))
        if not isinstance(mirror, dict) or not isinstance(mirror.get("stateSha256"), str):
            return False
        return mirror["stateSha256"] == hashlib.sha256(state_bytes).hexdigest()
    except Exception:
        return False


def _match(payload, roots):
    # 1. a Bash call with a string command
    # axis: only a Bash tool call with a string command can be approved
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return None
    command = tool_input["command"]

    # 2. characters the tokenizer would hide from us (default shlex drops everything after `#`)
    # axis: `# $ backtick \ newline CR NUL` anywhere refuses — each hides or adds a command from the token view
    if any(ch in _REFUSED_CHARS for ch in command):
        return None

    # 3. quote-aware expansion scan: Bash expands these outside quotes, the token view does not show it
    # axis: `{ } * ? [ ] ~` outside quotes (glob, brace, tilde) and an unbalanced quote refuse; inside quotes they pass
    if _unquoted_expansion(command):
        return None

    # 4. tokenize; an unclosed quote is a ValueError (caught by _approved_name → None)
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)

    # axis: any operator token (`;` `&&` `||` `|` `&` `<` `>` …) refuses — no redirect exception here
    if any(_is_operator(t) for t in tokens):
        return None

    # 5. bare `python3`, at most one `-B`
    # axis: the program is bare `python3` with at most one `-B`; any other program or interpreter flag refuses
    if not tokens or tokens[0] != "python3":
        return None
    i = 1
    if i < len(tokens) and tokens[i] == "-B":
        i += 1

    # 6. the script is one of this plugin's own approved lib scripts, by absolute path
    if i >= len(tokens):
        return None
    script = tokens[i]
    rest = tokens[i + 1:]
    # axis: the script path is absolute, has no `..` segment, and normalizes to a plugin root's lib/<name>
    if not os.path.isabs(script) or ".." in script.split("/"):
        return None
    normalized = os.path.normpath(script)
    name = None
    for root in roots:
        if os.path.dirname(normalized) == os.path.normpath(os.path.join(root, "lib")):
            name = os.path.basename(normalized)
            break
    # axis: the name is on APPROVED_SCRIPTS — an unlisted plugin script gets no decision
    if name not in APPROVED_SCRIPTS:
        return None

    # 7. the round driver: one of the eight verbs, and no flag that hands it a command line or a caller-named export path
    if name == "round_driver.py":
        # axis: the first token after the driver is an allowed verb (`run-verify`, `rule`, `--help`, an option, nothing refuse)
        if not rest or rest[0] not in ROUND_DRIVER_VERBS:
            return None
        for t in rest[1:]:
            # axis: `--` ends option parsing and is refused
            if t == "--":
                return None
            # axis: `--verify-command` / `--break-it-interpreter` / `--records-path`, in full or as an argparse prefix abbreviation, refuse
            if t.startswith("--"):
                stem = t[2:].split("=", 1)[0]
                if stem and any(flag.startswith(stem) for flag in COMMAND_FLAGS):
                    return None
        # axis: a driver call whose session state does not match the driver's own mirror stamp gets no decision
        if not _session_state_is_drivers(rest[1:], payload.get("cwd")):
            return None

    # 8. the worktree guard's classifier has the last word
    # axis: an otherwise-approved command is refused when the worktree guard says deny
    import worktree_guard
    decision, _ = worktree_guard.classify(command, payload.get("cwd"))
    if decision == "deny":
        return None
    return name


def main():
    out = None  # the single string to write, computed fully before any output (atomic single write)
    try:
        payload = json.loads(sys.stdin.read())
        name = _approved_name(payload, plugin_roots(os.environ))
        if name is not None:
            out = _allow_json(name)
    except Exception:
        out = None

    if out is not None:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
