#!/usr/bin/env python3
"""The one home of the refused-command stop rule, the refusal-entry shape (#2011), the
file-write rule (#2067, #2126), the delete rule (#2314), the stop-and-delete rule (#2412), and the
session-wide refusal rule and its sanctioned retry exceptions (#2431), and the plain-command rule
(#2458).

Every order the plugin writes for a fixer or an implementer carries `ORDER_TEXT`,
`FILE_WRITE_RULE`, `DELETE_RULE`, `STOP_AND_DELETE_RULE` (#2412) and `PLAIN_COMMAND_RULE` (#2458);
no order surface keeps a hand copy of any, except that `agents/implementer.md` keeps a
census-tested copy of the stop rule (`STOP_RULE`, `REFUSAL_MEANING`, `ENTRY_SHAPE`).
`refusals_fault` is the one check of a result's `refusals` list. Leaf module: stdlib only, imports
nothing from `lib/`.
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

PLAIN_COMMAND_RULE = (
    "Write every shell command in plain form, so that no command waits on an approval nobody is "
    "there to give: a chained, looping or variable-dependent command cannot be pre-approved, and "
    "it is held for the owner's approval even in auto mode. Run one plain command per call. A "
    "single command on its own, such as a read-only `git`, `gh api` or `cat`, stays fine as one "
    "plain call. Put multi-step work (a loop, several file operations, anything that needs a "
    "shell variable) in a script file in your own scratch directory, written with the file-write "
    "tool, and run it with one plain interpreter call such as `bash <path>` or `python3 <path>`. "
    "Never chain commands with `;`, `&&` or `||`, and never pipe into a loop. Make directories "
    "and copy or move files with the file tools or inside such a script, never as chained shell "
    "commands. Two rules still bind beside this one and are not loosened by it: a delete never "
    "moves into the script, it stays its own plain call as the delete rule says; and where the "
    "file-write rule binds you, a file that rule sends to the file tools is never written by the "
    "script. A seat with no file-write tool runs only single plain commands and leaves any "
    "multi-step script to the seat that dispatched it. This rule prevents a refusal about a "
    "command's form; when one happens anyway, the stop rule governs it."
)

# The sanctioned retry exceptions: the only acts a seat may take after another seat's refusal, or
# re-take after its own. Each entry names the act class, the seats that may re-run it, the
# conditions it runs under, and the disclosure it owes. A new entry needs the owner's word with the
# field sightings behind it; adding one is this entry plus its test, and every order picks it up.
SANCTIONED_RETRIES = (
    {
        "act": "a bite-proof red or green run",
        "who": ("the build's orchestrator", "a vet"),
        "conditions": (
            "after a refusal by a permission check or the auto-mode classifier (refusedBy "
            "permission), never by a hook or the sandbox",
            "in a throwaway copy of the tree",
            "with the mutation in place for the red run and reverted before the green run",
            "never committed or pushed",
        ),
        "disclosure": "the PR body (for a vet, the vet receipt) names the refusal and the re-run",
    },
)

SESSION_RULE_HEAD = (
    "A refusal binds the whole build session, not only the seat that met it. No seat, the "
    "orchestrator and a vet included, takes a refused act in any form, and handing a refused act "
    "to another seat (an implementer, a check-runner, a pilot) is taking it in another form. The "
    "stop rule's two exceptions belong to the seat that met the refusal, taken once by that seat; "
    "no other seat inherits them. The only other exceptions are the sanctioned retries listed in "
    "SANCTIONED_RETRIES in lib/command_refusals.py, each taken only by the seats it names, only on "
    "its conditions, and only with its disclosure:"
)

SESSION_RULE_TAIL = (
    "A refused act that no entry covers stays a stop for the whole session: record it, and a claim "
    "it would have proved goes back UNVERIFIED. A new entry needs the owner's word, with the field "
    "sightings behind it."
)


def session_rule(entries):
    """The session-wide refusal rule, rendered from ``entries`` (the shape of ``SANCTIONED_RETRIES``)."""
    items = [
        "(%d) %s: %s may re-run it, only %s; %s." % (
            n, e["act"], " or ".join(e["who"]), ", ".join(e["conditions"]), e["disclosure"])
        for n, e in enumerate(entries, 1)
    ]
    return " ".join([SESSION_RULE_HEAD] + (items or ["none."]) + [SESSION_RULE_TAIL])


SESSION_RULE = session_rule(SANCTIONED_RETRIES)

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

def compose_order_text(entries):
    """The whole refused-command order text, with the session rule rendered from ``entries``."""
    return " ".join([STOP_RULE, session_rule(entries), REFUSAL_MEANING, ENTRY_SHAPE])


ORDER_TEXT = compose_order_text(SANCTIONED_RETRIES)

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
