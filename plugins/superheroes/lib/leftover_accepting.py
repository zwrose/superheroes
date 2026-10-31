"""The one home of the leftover-acceptance rule (#2280): every finding the latest review record leaves for the owner
(its ``leftForOwner`` list) is named in the PR body's ``## What we're accepting`` section by its record id, byte for
byte, together with its title, in one acceptance. A paraphrase that drops the id, or an id with no title, does not name
it.

Two callers, no second copy of the rule: ``vet_slot.py handback --pr`` (the builder's check before the ready mark) and
``vet_slot.py write`` (the advisor's slot write, for a READY verdict only). ``missing`` takes the latest record exactly as
``review_record.py read --pr <n>`` returns it and the PR body; it returns the leftovers the section does not name, and
raises ``Unreadable`` for a record it cannot read, which a caller reports as unreadable, never as a pass."""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import pr_sheet  # noqa: E402
import review_record  # noqa: E402

_ID_CHAR = "A-Za-z0-9_-"


class Unreadable(Exception):
    """The latest review record could not be read, so the rule cannot be checked."""


def _leftovers(record):
    """(id, title or None) for each leftForOwner entry, in the record's order; Unreadable for anything malformed."""
    # axis: a read that did not succeed (missing, unreadable, gh failed) is unreadable, never a pass
    if not isinstance(record, dict) or record.get("ok") is not True:
        detail = record.get("detail") or record.get("reason") if isinstance(record, dict) else None
        raise Unreadable(detail or "the review record read did not succeed")
    left, findings = record.get("leftForOwner"), record.get("findings")
    # axis: a leftForOwner or findings field that is not a list (or holds a non-dict finding) is unreadable
    if not isinstance(left, list) or not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        raise Unreadable("the record's leftForOwner or findings list is missing or malformed")
    out = []
    for name in left:
        held = [f for f in findings if f.get("outcome") == review_record._LEFT_FOR_OWNER
                and review_record._name(f) == name]
        # axis: a leftForOwner entry that is not a non-empty string, or names no left-for-owner finding, is unreadable
        if not (isinstance(name, str) and name.strip() and held):
            raise Unreadable("leftForOwner entry %r names no finding left for the owner" % (name,))
        title = held[0].get("title")
        out.append((name, title if isinstance(title, str) and title.strip() else None))
    return out


def _names(item, ident, title):
    """Whether one acceptance names the id as a whole token and carries the title, both byte for byte."""
    token = re.search("(?<![%s])%s(?![%s])" % (_ID_CHAR, re.escape(ident), _ID_CHAR), item)
    return token is not None and (title is None or title in item)


def missing(record, body):
    """The leftovers ``body``'s What we're accepting does not name, as [{"id", "title"}] in record order ([] when every
    one is named, or the record leaves none). ``record`` is ``review_record.read``'s result; Unreadable when it cannot be
    read. A leftover whose finding carries no title is checked by its id alone."""
    items = pr_sheet.accepting_listed(body if isinstance(body, str) else "")
    return [{"id": ident, "title": title} for ident, title in _leftovers(record)
            if not any(_names(item, ident, title) for item in items)]


def describe(gaps):
    """The refusal detail naming each missing leftover with its title."""
    named = ["%s (%s)" % (g["id"], g["title"]) if g["title"] else g["id"] for g in gaps]
    return ("What we're accepting does not name these findings left for the owner, each by its record id byte for byte"
            " with its title in one line: " + "; ".join(named))
