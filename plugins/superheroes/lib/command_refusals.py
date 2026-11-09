#!/usr/bin/env python3
"""The one home of the refused-command stop rule, the refusal-entry shape (#2011), the
file-write rule (#2067, #2126), the delete rule (#2314), and the stop-and-delete rule (#2412).

Every order the plugin writes for a fixer or an implementer carries `ORDER_TEXT`,
`FILE_WRITE_RULE`, `DELETE_RULE` and `STOP_AND_DELETE_RULE` (#2412); no order surface keeps a hand copy of any. `refusals_fault` is the one
check of a result's `refusals` list. Leaf module: stdlib only, imports nothing from `lib/`.
"""

STOP_RULE = (
    "A refused or denied command is a stop. Report it in your result's refusals list and do not "
    "retry it in another form: not another path to the program, another tool, another wrapper, "
    "or another command with the same effect. There are two exceptions. First: when the refusing "
    "guard's or hook's own refusal message names a route (an exact command or tool to use "
    "instead), you may take exactly that route, once, and record it as that entry's route. "
    "Second: when a refusal is only about the command's form (a compound command, a variable or "
    "program inside `bash -c`, a heredoc or pipe the guard will not parse) and not about what the "
    "command does, you may re-issue the same command once in plain form (each command its own "
    "plain call, with no compound, wrapper, heredoc or pipe) and record that plain form as that "
    "entry's route. A second refusal, and any refusal about what the command does (a delete, a "
    "push, a network call, a permission), stays a stop; so does every other form. A refused "
    "command that carries a delete is never only about its form."
)

REFUSAL_MEANING = (
    "A refused or denied command is one that a permission denial, a hook refusal, a sandbox refusal, "
    "or the harness's own safety checks (a shell-command checker or an auto-mode classifier) "
    "stopped, or one held for an approval that nobody answers; record those last two kinds with "
    "refusedBy permission. A command that ran and failed is not a refusal, and the failure rules "
    "cover it."
)

REFUSED_BY = ("permission", "hook", "sandbox")
ENTRY_REQUIRED = ("command", "refusedBy", "next")
ENTRY_OPTIONAL = ("hook", "route")

ENTRY_SHAPE = (
    "Each refusals entry carries command (the command exactly as you wrote it), refusedBy "
    "(permission, hook or sandbox), hook (the hook's name when the refusal gave one, else null), "
    "route (the route a refusal message named and you took, or the plain form you re-issued "
    "after a form-only refusal, else null), and next "
    "(what you did next). An empty list means you met none."
)

ORDER_TEXT = STOP_RULE + " " + REFUSAL_MEANING + " " + ENTRY_SHAPE

FILE_WRITE_RULE = (
    "Create and edit files only with the host's file-write and file-edit tools (Write and Edit on "
    "Claude Code); never through a shell command that writes a file — a heredoc, `cat >` or `>` "
    "redirection, `tee`, `sed -i`, or an interpreter script (`python -`, `node -e`)."
)

DELETE_RULE = (
    "Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||` or `;`, "
    "not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain call, "
    "one path per call."
)

STOP_AND_DELETE_RULE = (
    "Stop only a process you started yourself, and only by its PID, never by name or pattern "
    "(`pkill`, `killall`, or `kill` over a `pgrep` or `ps` match): other sessions share this "
    "machine. Delete only a path you created in this session or one your task names for deletion, "
    "never by a name pattern or a glob over a directory you did not create."
)


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def refusals_fault(value):
    """Return ``None`` when ``value`` is a valid refusals list, else a short reason. Never raises."""
    try:
        if not isinstance(value, list):
            return "refusals not a list"
        allowed = ENTRY_REQUIRED + ENTRY_OPTIONAL
        for i, entry in enumerate(value):
            where = "refusals[%d]" % i
            if not isinstance(entry, dict):
                return where + " not an object"
            for key in entry:
                if key not in allowed:
                    return "%s unknown key: %s" % (where, key)
            for key in ENTRY_REQUIRED:
                if key not in entry:
                    return "%s.%s missing" % (where, key)
            for key in ("command", "next"):
                if _blank(entry[key]):
                    return "%s.%s blank" % (where, key)
            by = entry["refusedBy"]
            if not isinstance(by, str) or by not in REFUSED_BY:
                return where + ".refusedBy"
            if "hook" in entry and entry["hook"] is not None and _blank(entry["hook"]):
                return where + ".hook"
            if "route" in entry and entry["route"] is not None:
                if _blank(entry["route"]):
                    return where + ".route"
        return None
    except Exception as exc:  # noqa: BLE001 — a validator must never raise
        return "refusals-check-error:%s" % type(exc).__name__
