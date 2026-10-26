#!/usr/bin/env python3
"""The one home of the refused-command stop rule, the refusal-entry shape (#2011), and the
file-write rule (#2067, #2126).

Every order the plugin writes for a fixer or an implementer carries `ORDER_TEXT` and
`FILE_WRITE_RULE`; no order surface keeps a hand copy of either. `refusals_fault` is the one
check of a result's `refusals` list. Leaf module: stdlib only, imports nothing from `lib/`.
"""

STOP_RULE = (
    "A refused or denied command is a stop. Report it in your result's refusals list and do not "
    "retry it in another form: not another path to the program, another tool, another wrapper, "
    "or another command with the same effect. The one exception: when the refusing guard's or "
    "hook's own refusal message names a route (an exact command or tool to use instead), you may "
    "take exactly that route, once, and record it as that entry's route; every other form, and "
    "every auto-mode classifier denial, stays a stop."
)

REFUSAL_MEANING = (
    "A refused or denied command is one that a permission denial, a hook refusal, a sandbox refusal, "
    "or the harness's own safety checks (a shell-command checker or an auto-mode classifier) "
    "stopped, or one held for an approval that nobody answers; record those last two kinds with "
    "refusedBy permission. A command that ran and failed is not a refusal, and the failure rules "
    "cover it."
)

REFUSED_BY = ("permission", "hook", "sandbox")
# The refusers whose own message may name a route (#2167): a hook, or the sandbox ("split into
# plain commands"). A permission entry never carries one: an auto-mode classifier denial stays a stop.
ROUTE_REFUSED_BY = ("hook", "sandbox")
ENTRY_REQUIRED = ("command", "refusedBy", "next")
ENTRY_OPTIONAL = ("hook", "route")

ENTRY_SHAPE = (
    "Each refusals entry carries command (the command exactly as you wrote it), refusedBy "
    "(permission, hook or sandbox), hook (the hook's name when the refusal gave one, else null), "
    "route (the route a hook's or the sandbox's own refusal message named and you took, else "
    "null), and next "
    "(what you did next). An empty list means you met none."
)

ORDER_TEXT = STOP_RULE + " " + REFUSAL_MEANING + " " + ENTRY_SHAPE

FILE_WRITE_RULE = (
    "Create and edit files only with the host's file-write and file-edit tools (Write and Edit on "
    "Claude Code); never through a shell command that writes a file — a heredoc, `cat >` or `>` "
    "redirection, `tee`, `sed -i`, or an interpreter script (`python -`, `node -e`)."
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
                if by not in ROUTE_REFUSED_BY:
                    return where + ".route needs refusedBy hook or sandbox"
        return None
    except Exception as exc:  # noqa: BLE001 — a validator must never raise
        return "refusals-check-error:%s" % type(exc).__name__
