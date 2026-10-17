#!/usr/bin/env python3
"""PreToolUse(Bash) iPhone-check approver — the plugin approves its own `lib/iphone_check.py` (#1893).

Reads the PreToolUse payload from stdin. When the Bash command is, as a whole, one plain call of
THIS plugin's `lib/iphone_check.py` with one of its eight verbs (and, for `drive`, one of the
pilot's AXe steps), and the worktree guard's classifier does not deny it, it emits
`permissionDecision: "allow"`. For every other input it stays silent.

Contract (fail-closed — "closed" here means no decision, never allow):

- `permissionDecision: "allow"` is printed if and only if the matcher in `decide` accepts the
  command. Every other input — any other command, any parse doubt, any internal error — writes
  NOTHING. This hook never prints `deny` and never prints `ask`; the worktree guard owns refusal.
- stdout is written EXACTLY ONCE, atomically, at the very end — never partial output.
- The whole body is wrapped in try/except. ANY internal failure (empty or unparseable stdin, a
  classifier raise) → silence. The process always exits 0.

Stdlib-only.
"""
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

_REFUSED_CHARS = frozenset("#$`\\\n\r\0")
_OPERATOR_CHARS = frozenset("();<>|&")
_VERBS = frozenset(("preflight", "boot", "open", "drive", "shot", "read", "judge", "render"))
_DRIVE_STEPS = frozenset(("tap", "type", "button", "swipe", "describe-ui"))

_ALLOW = json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "superheroes: this plugin's own iPhone check command (lib/iphone_check.py)"}})


def plugin_roots(environ):
    """This plugin's root (two levels above this file), plus an absolute CLAUDE_PLUGIN_ROOT."""
    raw = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    env_root = environ.get("CLAUDE_PLUGIN_ROOT")
    if isinstance(env_root, str) and os.path.isabs(env_root):
        raw.append(env_root)
    roots = []
    for r in raw:
        for form in (os.path.normpath(r), os.path.realpath(r)):
            if form not in roots:
                roots.append(form)
    return roots


def _is_operator(token):
    return bool(token) and all(ch in _OPERATOR_CHARS for ch in token)


def decide(payload, plugin_roots):
    """True to allow, False otherwise. Never raises: any error is no decision."""
    try:
        return _decide(payload, plugin_roots)
    except Exception:
        return False


def _decide(payload, roots):
    # 1. a Bash call with a string command
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return False
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return False
    command = tool_input["command"]

    # 2. characters the tokenizer would hide from us (default shlex drops everything after `#`)
    if any(ch in _REFUSED_CHARS for ch in command):
        return False

    # 3. tokenize; an unclosed quote is a ValueError (caught by decide → False)
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)

    # 4. no operator token, except the judge's trailing `< file`
    redirect = False
    if len(tokens) >= 2 and tokens[-2] == "<" and not _is_operator(tokens[-1]):
        redirect = True
        tokens = tokens[:-2]
    if any(_is_operator(t) for t in tokens):
        return False

    # 5. bare `python3`, at most one `-B`
    if not tokens or tokens[0] != "python3":
        return False
    i = 1
    if i < len(tokens) and tokens[i] == "-B":
        i += 1

    # 6. the script is this plugin's own lib/iphone_check.py, by absolute path
    if i >= len(tokens):
        return False
    script = tokens[i]
    i += 1
    if not os.path.isabs(script) or ".." in script.split("/"):
        return False
    approved = {os.path.normpath(os.path.join(r, "lib", "iphone_check.py")) for r in roots}
    if os.path.normpath(script) not in approved:
        return False

    # 7. one of the eight verbs
    if i >= len(tokens) or tokens[i] not in _VERBS:
        return False
    verb = tokens[i]
    rest = tokens[i + 1:]

    # 8. only `judge` reads its step from stdin
    if redirect and verb != "judge":
        return False

    # 9. `drive` passes one AXe step after `--`
    if verb == "drive":
        if "--" not in rest:
            return False
        after = rest[rest.index("--") + 1:]
        if not after or after[0] not in _DRIVE_STEPS:
            return False

    # 10. the worktree guard's classifier has the last word
    import worktree_guard
    decision, _ = worktree_guard.classify(command, payload.get("cwd"))
    return decision != "deny"


def main():
    out = None  # the single string to write, computed fully before any output (atomic single write)
    try:
        payload = json.loads(sys.stdin.read())
        if decide(payload, plugin_roots(os.environ)):
            out = _ALLOW
    except Exception:
        out = None

    if out is not None:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
