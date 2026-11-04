"""The one home of the leftover-acceptance rule (#2280, #2332): every finding the latest review record leaves for the
owner (its ``leftForOwner`` list) is named in the PR body's ``## What we're accepting`` section by its record id,
together with its title, in one acceptance. A paraphrase that drops the id, or an id with no title, does not name it.
An id that shares its normal form with no other leftover id of the record is compared under one normalisation (NFKC,
case-folded, every Unicode dash read as ``-``) as a whole token after the punctuation around it is stripped, so ``F-1``
and ``f-1`` name one id but ``f-1`` is never inside ``f-1-b``. Two or more ids of one record that share a normal form
are each compared on their exact bytes: nothing is stripped, the acceptance is not split on whitespace, and an
occurrence of one inside an occurrence of a longer id of the same group does not count, so one acceptance never names
two of them. The punctuation around an id is classified after NFKC, so a full-width wrapper (``（Ｆ－１）``,
``Ｆ－１：``) is stripped like its ASCII form, and a zero-width character (U+200B, U+200C, U+200D, U+2060, U+FEFF) touching
an id reads as outside it. One acceptance counts for at most one leftover: the leftovers and the acceptances are paired
one to one by a maximum matching (``_assign``, deterministic: leftovers in record order, each one's acceptances that carry
``fixed-above`` tried first, then the others, each in body order), and a leftover with no acceptance of its own is
missing. The title is compared by its words, ignoring case, quotes, punctuation and Markdown underscore emphasis
(quotes and apostrophes are dropped, so ``don't`` and ``don’t`` agree; backticks, a hyphen written as a space and
underscores that wrap a word, as in ``_slow retry_``, are read as spaces; an underscore inside a word is kept). An
acceptance that
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
_QUOTES = {ord(c): None for c in "\"'“”„‟‘’‚‛«»"}


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


_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")


def _tokens(text):
    """The whitespace-separated pieces of ``text``, each without the punctuation that wraps or ends it; empty ones dropped.
    A zero-width character (U+200B, U+200C, U+200D, U+2060, U+FEFF) separates tokens like a space, so one touching an id
    reads as outside it."""
    # axis: a zero-width character is a token separator, never part of an id
    pieces = (piece.lstrip(_LEAD).rstrip(_TRAIL) for piece in _ZERO_WIDTH.sub(" ", text).split())
    return [piece for piece in pieces if piece]


def _title_key(text):
    """A title or an acceptance reduced to its words: NFKC, case-folded, dashes as ``-``, quotes and apostrophes dropped
    (straight and typographic alike, so ``don't``, ``don’t`` and ``dont`` agree), Markdown underscore emphasis dropped (a
    run of underscores that touches a non-word character or an end of the text, so ``_slow retry_`` reads as
    ``slow retry``; ``foo_bar`` keeps its underscore), every other run of non-word characters one space."""
    folded = _DASHES.sub("-", unicodedata.normalize("NFKC", text).casefold()).translate(_QUOTES)
    # axis: an underscore run at a word edge is emphasis and reads as a space; one between two word characters is kept
    folded = re.sub(r"(?<!\w)_+|_+(?!\w)", " ", folded)
    return re.sub(r"[^\w]+", " ", folded).strip()


def _id_named(item, ident):
    """Whether the id's tokens appear as a consecutive run of the item's tokens, both under ``normalise_id``. The text is
    normalised (NFKC, case-folded, dashes) before its punctuation is stripped, so a full-width wrapper is stripped like
    its ASCII form."""
    # axis: NFKC comes before the punctuation around an id is classified, so （Ｆ－１） and Ｆ－１： read as (f-1) and f-1:
    want, have = _tokens(normalise_id(ident)), _tokens(normalise_id(item))
    # axis: an id with no token left after stripping its punctuation is matched as a whole token by the old character rule
    if not want:
        return re.search("(?<![%s])%s(?![%s])" % (_ID_CHAR, re.escape(ident), _ID_CHAR), item) is not None
    n = len(want)
    # axis: whole-token equality, never a substring, so f-1 is not inside f-1-b and F/1 is not inside F.1.2
    return any(have[i:i + n] == want for i in range(len(have) - n + 1))


def _spans(item, ident):
    """The (start, end) of every occurrence of ``ident``'s exact bytes in ``item`` bounded as a whole id."""
    pattern = "(?<![%s])%s(?![%s])" % (_ID_CHAR, re.escape(ident), _ID_CHAR)
    return [found.span() for found in re.finditer(pattern, item)]


def _exact_named(item, ident, group):
    """Whether ``item`` carries ``ident`` on its exact bytes: nothing stripped, no whitespace split, no normalisation.
    An occurrence that lies inside an occurrence of a longer id of ``group`` (the ids sharing ``ident``'s normal form)
    is the longer id's, not this one's, and does not count."""
    longer = [span for other in group if len(other) > len(ident) for span in _spans(item, other)]
    # axis: the id is named only by an occurrence no longer colliding id of the group accounts for
    return any(not any(lo <= start and end <= hi for lo, hi in longer) for start, end in _spans(item, ident))


def _names(item, ident, title, group=None):
    """Whether one acceptance names the id and carries the title (its words, case and punctuation aside). An id with a
    ``group`` (the ids of the record sharing its normal form, itself included) is named on its exact bytes
    (``_exact_named``); any other id as a whole token run under the normalisation (``_id_named``). A title that reduces
    to no words is carried only byte for byte."""
    # axis: a colliding id never goes the normalised path, so one acceptance cannot name two ids of one group
    if not (_exact_named(item, ident, group) if group else _id_named(item, ident)):
        return False
    if title is None:
        return True
    key = _title_key(title)
    # axis: a title of punctuation only has no words to compare, so it is carried byte for byte
    if not key:
        return title in item
    return " " + key + " " in " " + _title_key(item) + " "


def _collisions(leftovers):
    """{id: the frozenset of ids sharing its normal form} for each id that shares it with a different leftover id; those
    ids are matched on their exact bytes. An id sharing its form with none is absent."""
    forms = {}
    for ident, _title in leftovers:
        # axis: the normal form is taken after NFKC, as _id_named reads an id
        forms.setdefault(tuple(_tokens(normalise_id(ident))), set()).add(ident)
    return {ident: frozenset(ids) for ids in forms.values() if len(ids) > 1 for ident in ids}


def _accepting_items(body):
    return pr_sheet.accepting_listed(_visible(body if isinstance(body, str) else ""))


FIXED_ABOVE_RE = re.compile(
    r"(?<![A-Za-z0-9_-])fixed-above\s+#([1-9][0-9]*)\s+`?([0-9a-f]{7,40})`?(?![0-9A-Za-z])")


def _assign(leftovers, items, colliding):
    """{leftover index: item index}: each acceptance is given to at most one leftover and each leftover takes at most one
    acceptance, by a maximum bipartite matching over the pairs ``_names`` holds true (Kuhn's augmenting paths; leftovers
    taken in record order). Each leftover tries the acceptances naming it that carry ``fixed-above #<PR> <commit>`` first
    (in body order), then the others (in body order), and an acceptance no leftover holds yet before one that is held, so
    the same input always gives the same assignment and the disposition line goes to the first leftover (in record order)
    that names it. A leftover absent from the result has no acceptance of its own."""
    carries = [FIXED_ABOVE_RE.search(item) is not None for item in items]
    naming = [[j for j, item in enumerate(items) if _names(item, ident, title, colliding.get(ident))]
              for ident, title in leftovers]
    # axis: the acceptances carrying the disposition are tried first (a stable sort keeps body order within each kind), so the
    # first acceptance carrying it decides for a leftover that several name
    naming = [sorted(names, key=lambda j: not carries[j]) for names in naming]
    holder = {}  # item index -> the leftover index that holds it

    def place(i, seen):
        for j in naming[i]:
            if j not in holder and j not in seen:
                holder[j] = i
                return True
        for j in naming[i]:
            if j in seen:
                continue
            seen.add(j)
            # axis: a held acceptance moves to another leftover only when that one has an acceptance of its own to take
            if place(holder[j], seen):
                holder[j] = i
                return True
        return False

    for i in range(len(leftovers)):
        place(i, set())
    return dict(sorted((i, j) for j, i in holder.items()))


def missing(record, body):
    """The leftovers ``body``'s What we're accepting does not name, as [{"id", "title"}] in record order ([] when every
    one is named, or the record leaves none). ``record`` is ``review_record.read``'s result; Unreadable when it cannot be
    read. Only text that renders counts (``_visible``). A leftover whose finding carries no title is checked by its id
    alone. One acceptance counts for at most one leftover (``_assign``): a leftover with no acceptance of its own is
    missing, however many acceptances name it or however many leftovers one acceptance names."""
    items = _accepting_items(body)
    leftovers = _leftovers(record)
    given = _assign(leftovers, items, _collisions(leftovers))
    # axis: two ids of one record that share a normal form are each matched on their exact bytes, and one acceptance is
    # given to one leftover, so neither satisfies the other
    return [{"id": ident, "title": title} for n, (ident, title) in enumerate(leftovers) if n not in given]


def fixed_above(record, body):
    """The leftovers an acceptance resolves as fixed by a higher layer (#2332), as [{"id", "title", "layer", "commit"}] in
    record order. A leftover is resolved by the acceptance it is assigned (``_assign``, the one-to-one rule ``missing``
    reads) when that acceptance carries ``fixed-above #<PR> <7-40 hex commit>``; a leftover with no acceptance of its own,
    or one whose acceptance carries no such form, is not listed. Only the full form counts: the word alone or a malformed
    form is plain text. Unreadable exactly where ``missing`` raises it. Whether the named PR is a higher member of this PR's
    stack is the caller's to check."""
    return [{k: v for k, v in claim.items() if k != "acceptance"} for claim in assigned_fixed_above(record, body)]


def assigned_fixed_above(record, body):
    """``fixed_above``'s claims, each with ``acceptance``: the visible text of the acceptance the whole-body assignment
    gave its leftover, so a caller that maps a claim back to its acceptance reads the one assignment and never matches an
    acceptance alone again."""
    items = _accepting_items(body)
    leftovers = _leftovers(record)
    given = _assign(leftovers, items, _collisions(leftovers))
    claims = []
    for n, (ident, title) in enumerate(leftovers):
        found = FIXED_ABOVE_RE.search(items[given[n]]) if n in given else None
        # axis: only the acceptance a leftover is assigned can resolve it, so one line is never a claim for two leftovers
        if found:
            claims.append({"id": ident, "title": title, "layer": int(found.group(1)), "commit": found.group(2),
                           "acceptance": items[given[n]]})
    return claims


def describe(gaps):
    """The refusal detail naming each missing leftover with its title."""
    named = ["%s (%s)" % (g["id"], g["title"]) if g["title"] else g["id"] for g in gaps]
    return ("What we're accepting does not name these findings left for the owner, each by its record id and its title"
            " in one line, matched as lib/leftover_accepting.py states: " + "; ".join(named))
