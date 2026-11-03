"""The one home of the leftover-acceptance rule (#2280, #2332): every finding the latest review record leaves for the
owner (its ``leftForOwner`` list) is named in the PR body's ``## What we're accepting`` section by its record id,
together with its title, in one acceptance. A paraphrase that drops the id, or an id with no title, does not name it.
The id is compared under one normalisation (NFKC, case-folded, every Unicode dash read as ``-``) as a whole token after
the punctuation around it is stripped, so ``F-1`` and ``f-1`` name one id but ``f-1`` is never inside ``f-1-b``; two ids
of one record that share a normal form are each matched byte for byte, so neither satisfies the other. The title is
compared by its words, case and punctuation aside (quotes, backticks, a hyphen written as a space). An acceptance that
carries ``fixed-above #<PR> <7-40 hex commit>`` resolves the leftovers it names as fixed by that higher layer
(``fixed_above``); whether the named PR is a higher member of this PR's stack is the caller's check, not this module's.

Two callers, no second copy of the rule: ``vet_slot.py handback --pr`` (the builder's check before the ready mark) and
``vet_slot.py write`` (the advisor's slot write, for a READY verdict only). ``missing`` takes the latest record exactly as
``review_record.py read --pr <n>`` returns it and the PR body; it returns the leftovers the section does not name, and
raises ``Unreadable`` for a record it cannot read, which a caller reports as unreadable, never as a pass."""
import os
import re
import sys
import unicodedata

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import md_fence  # noqa: E402
import pr_sheet  # noqa: E402
import review_record  # noqa: E402

_ID_CHAR = "A-Za-z0-9_-"
_DASHES = re.compile("[‐‑‒–—―−﹘﹣－]")
_LEAD = "\"'`([{<*_~“‘«"
_TRAIL = "\"'`)]}>.,;:!?*_~”’»"
_QUOTES = {ord(c): None for c in "“”„‟‘’‚‛«»"}


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
                and review_record._name(f) == name and not review_record.repeat_held_elsewhere(f, findings)]
        # axis: a leftForOwner entry that is not a non-empty string, or names no left-for-owner finding, is unreadable
        if not (isinstance(name, str) and name.strip() and held):
            raise Unreadable("leftForOwner entry %r names no finding left for the owner" % (name,))
        # axis: two findings sharing one id are each checked with their own title, never only the first
        for f in held:
            title = f.get("title")
            pair = (name, title if isinstance(title, str) and title.strip() else None)
            if pair not in out:
                out.append(pair)
    return out


_MARKER_LINE = re.compile(r"^<!-- superheroes:[^>]*-->\s*$")
_TICKS = re.compile(r"`+")


def _code_span_end(line, i):
    """Where the inline code span opening with the backtick run at ``i`` ends, or None when no run of exactly the
    same length closes it on this line (CommonMark: the run is then literal backticks). A span that runs onto a later
    line is not followed, so a comment inside it is cut: the check fails toward a refusal, never a pass."""
    run = _TICKS.match(line, i).group(0)
    for close in _TICKS.finditer(line, i + len(run)):
        if len(close.group(0)) == len(run):
            return close.end()
    return None


def _visible(body):
    """The body as it renders, for matching: every HTML comment (one that spans lines included) is cut out, while a
    comment delimiter inside a fenced block (``md_fence``'s CommonMark rules), an inline code span, or after a
    backslash escape is shown text and stays. A whole-line ``superheroes:`` marker is kept, so the section reader still
    finds the build-record boundary."""
    lines = body.splitlines(keepends=True)
    fenced = md_fence.scan([line.rstrip("\n") for line in lines]).inert
    out, inside = [], False
    for n, line in enumerate(lines):
        # axis: a fenced line (by md_fence's rules) is shown text; a comment open across it stays open
        if (fenced[n] and not inside) or (not inside and _MARKER_LINE.match(line)):
            out.append(line)
            continue
        kept, i = [], 0
        while i < len(line):
            if inside:
                # axis: text inside a comment, up to its closer on any later line, never counts
                end = line.find("-->", i)
                if end < 0:
                    i = len(line)
                    break
                inside, i = False, end + 3
            elif line[i] == "\\" and i + 1 < len(line):
                # axis: an escaped character (a backtick or a `<`) is literal text, never a delimiter
                kept.append(line[i:i + 2])
                i += 2
            elif line[i] == "`":
                # axis: a code span closes only on a backtick run of exactly its own length
                end = _code_span_end(line, i)
                run = len(_TICKS.match(line, i).group(0))
                kept.append(line[i:end if end is not None else i + run])
                i = end if end is not None else i + run
            elif line.startswith("<!--", i):
                inside, i = True, i + 4
            else:
                kept.append(line[i])
                i += 1
        text = "".join(kept)
        out.append(text + "\n" if line.endswith("\n") and not text.endswith("\n") else text)
    return "".join(out)


def normalise_id(text):
    """The one normal form two spellings of a record id are compared in: NFKC, case-folded, every Unicode dash as ``-``."""
    return _DASHES.sub("-", unicodedata.normalize("NFKC", text).casefold())


def _tokens(text):
    """The whitespace-separated pieces of ``text``, each without the punctuation that wraps or ends it; empty ones dropped."""
    pieces = (piece.lstrip(_LEAD).rstrip(_TRAIL) for piece in text.split())
    return [piece for piece in pieces if piece]


def _title_key(text):
    """A title or an acceptance reduced to its words: NFKC, case-folded, dashes as ``-``, typographic quotes dropped, every
    other run of non-word characters one space."""
    folded = _DASHES.sub("-", unicodedata.normalize("NFKC", text).casefold())
    return re.sub(r"[^\w]+", " ", folded.translate(_QUOTES)).strip()


def _id_named(item, ident, exact):
    """Whether the id's tokens appear as a consecutive run of the item's tokens (normalised, or byte for byte when
    ``exact``)."""
    want, have = _tokens(ident), _tokens(item)
    # axis: an id with no token left after stripping its punctuation is matched as a whole token by the old character rule
    if not want:
        return re.search("(?<![%s])%s(?![%s])" % (_ID_CHAR, re.escape(ident), _ID_CHAR), item) is not None
    if not exact:
        want, have = [normalise_id(t) for t in want], [normalise_id(t) for t in have]
    n = len(want)
    # axis: whole-token equality, never a substring, so f-1 is not inside f-1-b and F/1 is not inside F.1.2
    return any(have[i:i + n] == want for i in range(len(have) - n + 1))


def _names(item, ident, title, exact=False):
    """Whether one acceptance names the id as a whole token run (``_id_named``) and carries the title (its words, case
    and punctuation aside). A title that reduces to no words is carried only byte for byte."""
    if not _id_named(item, ident, exact):
        return False
    if title is None:
        return True
    key = _title_key(title)
    # axis: a title of punctuation only has no words to compare, so it is carried byte for byte
    if not key:
        return title in item
    return " " + key + " " in " " + _title_key(item) + " "


def _collisions(leftovers):
    """The ids that share a normal form with a different leftover id: those are matched byte for byte."""
    forms = {}
    for ident, _title in leftovers:
        forms.setdefault(tuple(normalise_id(t) for t in _tokens(ident)), set()).add(ident)
    return {ident for ids in forms.values() if len(ids) > 1 for ident in ids}


def _accepting_items(body):
    return pr_sheet.accepting_listed(_visible(body if isinstance(body, str) else ""))


def missing(record, body):
    """The leftovers ``body``'s What we're accepting does not name, as [{"id", "title"}] in record order ([] when every
    one is named, or the record leaves none). ``record`` is ``review_record.read``'s result; Unreadable when it cannot be
    read. Only text that renders counts (``_visible``). A leftover whose finding carries no title is checked by its id
    alone."""
    items = _accepting_items(body)
    leftovers = _leftovers(record)
    colliding = _collisions(leftovers)
    # axis: two ids of one record that share a normal form are each matched byte for byte, so neither satisfies the other
    return [{"id": ident, "title": title} for ident, title in leftovers
            if not any(_names(item, ident, title, exact=ident in colliding) for item in items)]


FIXED_ABOVE_RE = re.compile(
    r"(?<![A-Za-z0-9_-])fixed-above\s+#([1-9][0-9]*)\s+`?([0-9a-f]{7,40})`?(?![0-9A-Za-z])")


def fixed_above(record, body):
    """The leftovers an acceptance resolves as fixed by a higher layer (#2332), as [{"id", "title", "layer", "commit"}] in
    record order. A leftover is resolved by the first acceptance that names it (as ``missing`` reads it) and carries
    ``fixed-above #<PR> <7-40 hex commit>``; one named by no such acceptance is not listed. Only the full form counts: the
    word alone or a malformed form is plain text. Unreadable exactly where ``missing`` raises it. Whether the named PR is a
    higher member of this PR's stack is the caller's to check."""
    items = _accepting_items(body)
    leftovers = _leftovers(record)
    colliding = _collisions(leftovers)
    claims = []
    for ident, title in leftovers:
        for item in items:
            found = FIXED_ABOVE_RE.search(item)
            # axis: the first acceptance that names the leftover and carries the disposition decides it
            if found and _names(item, ident, title, exact=ident in colliding):
                claims.append({"id": ident, "title": title, "layer": int(found.group(1)), "commit": found.group(2)})
                break
    return claims


def describe(gaps):
    """The refusal detail naming each missing leftover with its title."""
    named = ["%s (%s)" % (g["id"], g["title"]) if g["title"] else g["id"] for g in gaps]
    return ("What we're accepting does not name these findings left for the owner, each by its record id byte for byte"
            " with its title in one line: " + "; ".join(named))
