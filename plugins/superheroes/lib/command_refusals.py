#!/usr/bin/env python3
"""The one home of the refused-command stop rule and of the refusal-entry shape (#2011).

Every order the plugin writes for a fixer or an implementer carries `ORDER_TEXT`; no order
surface keeps a hand copy of the sentence. `refusals_fault` is the one check of a result's
`refusals` list. Leaf module: stdlib only, imports nothing from `lib/`.
"""

STOP_RULE = (
    "A refused or denied command is a stop. Report it in your result's refusals list and do not "
    "retry it in another form: not another path to the program, another tool, another wrapper, "
    "or another command with the same effect."
)

REFUSAL_MEANING = (
    "A refused or denied command is one a permission denial, a hook refusal, or a sandbox refusal "
    "stopped; a command that ran and failed is not a refusal, and the failure rules cover it."
)

REFUSED_BY = ("permission", "hook", "sandbox")
ENTRY_REQUIRED = ("command", "refusedBy", "next")
ENTRY_OPTIONAL = ("hook",)

ENTRY_SHAPE = (
    "Each refusals entry carries command (the command exactly as you wrote it), refusedBy "
    "(permission, hook or sandbox), hook (the hook's name when the refusal gave one, else null), "
    "and next (what you did next). An empty list means you met none."
)

ORDER_TEXT = STOP_RULE + " " + REFUSAL_MEANING + " " + ENTRY_SHAPE


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
        return None
    except Exception as exc:  # noqa: BLE001 — a validator must never raise
        return "refusals-check-error:%s" % type(exc).__name__
