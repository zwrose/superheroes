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
import bisect
import os
import re
import sys
import unicodedata

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import md_fence  # noqa: E402
import md_hidden  # noqa: E402
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
# a `<` GitHub's HTML tokenizer leaves data state on (#2389 V849-1): `<` + `!`, `?`, `/` not followed by `>`, or an ASCII
# letter. These are exactly the entries out of `_DATA` in `md_hidden._tokenize`; the text after one may be hidden markup.
_TAG_ENTRY = re.compile(r"<(?:[!?]|/(?!>)|[A-Za-z])")
# the token that starts a fixed-above claim, counted on its own (case-insensitive) so a claim a cut removed is seen even when it wraps across lines
_FIXED_ABOVE_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])fixed-above(?![A-Za-z0-9_])", re.IGNORECASE)
# the two words of a fixed-above claim, matched apart, so a line that holds a claim split by a comment is still seen
_FIXED_WORD = re.compile(r"fixed", re.IGNORECASE)
_ABOVE_WORD = re.compile(r"above", re.IGNORECASE)
# an ATX heading line (CommonMark: up to three spaces, one to six #, then a space, a tab or the line's end)
_ATX_LINE = re.compile(r" {0,3}#{1,6}(?:[ \t\r\n]|\Z)")


def _code_span_end(line, i):
    """Where the inline code span opening with the backtick run at ``i`` ends, or None when no run of exactly the
    same length closes it on this line (CommonMark: the run is then literal backticks). A span that runs onto a later
    line is not followed, so a comment inside it is cut: the check fails toward a refusal, never a pass."""
    run = _TICKS.match(line, i).group(0)
    for close in _TICKS.finditer(line, i + len(run)):
        if len(close.group(0)) == len(run):
            return close.end()
    return None


def _terminator(line):
    """The one Markdown line terminator ending ``line`` (``\\r\\n``, ``\\n`` or ``\\r``), or ``""`` for a last line with none."""
    return "\r\n" if line.endswith("\r\n") else line[-1] if line.endswith(("\n", "\r")) else ""


def _visible(body):
    """The body reduced to text the leftover check may count (``_visible_claim`` returns it with the claim flag)."""
    return _visible_claim(body)[0]


def _visible_claim(body):
    """``(text, claim_removed)``: the body reduced to text the leftover check may count, and whether that removed a
    ``fixed-above`` claim. Every change below only removes text, so a miss fails toward a ``leftover-not-accepted``
    refusal and never toward a pass.

    * Every HTML comment (one that spans lines included) is cut out. A whole-line ``superheroes:`` marker is kept, so the
      section reader still finds the build-record boundary.
    * A line whose start ``md_hidden.scan`` does not read VISIBLE (hidden or unsure) keeps only its line terminator, a
      marker line excepted (#2389).
    * V849-1, one entry condition (#2389 V847-1, BR684-2, BR684-3, vet 849): on a line that is kept, the rest of the line
      is cut, with no comment state carried to later lines, at the first ``<`` that GitHub's HTML tokenizer leaves data
      state on (``_TAG_ENTRY``, the entries out of ``_DATA`` in ``md_hidden._tokenize``): a ``<`` followed by ``!``,
      ``?``, ``/`` and anything but ``>``, or an ASCII letter. A ``<`` followed by anything else (``a < b``, ``<3``, an
      empty end tag ``</>``) is text. It applies wherever the ``<`` sits. Plain: ``<!--`` keeps opening the multi-line
      comment state (its branch comes first); any other entry ``<`` cuts the rest of the line and sets no comment state
      itself. Escaped: a backslash before an entry ``<`` keeps the text before the backslash and cuts from the backslash
      (inside an HTML block GitHub honours no escape). Code span: a span whose content holds an entry ``<`` is kept only
      up to that ``<``; the tail read for comment state starts after the span. Fenced: a line ``md_fence`` calls fenced
      is not trusted (a raw HTML block such as ``<pre>`` makes a tilde line text, not a fence), so one holding an entry
      ``<`` anywhere is blanked whole when it is a fence content line, never shortened, so the shortened text cannot
      read as a fence delimiter when the section reader re-reads it, and shortened at that ``<`` when it is a fence
      delimiter line, so it stays the opener or closer it was. A fenced line with no entry ``<`` is kept whole.
    * A comment the cut tail opens and does not close (an unclosed ``<!--`` in the tail of any cut kind: plain, escaped,
      code span) still opens the comment state for later lines. An open comment state ends at a blank line or an ATX
      heading that ``md_hidden`` reads VISIBLE (an inline comment cannot cross either; a raw HTML comment that does is
      md_hidden's).
    * A removed claim voids the body (B): ``claim_removed`` is true when the text holds fewer ``fixed-above`` tokens than
      the source (case-insensitive) or fewer whole ``FIXED_ABOVE_RE`` matches (over the whole text, so a claim wrapped
      across lines counts). ``_accepting_items`` then returns no acceptance, whichever path removed the claim, so every
      leftover reads missing. A body whose hidden text merely mentions ``fixed-above`` is voided too, which fails toward
      a refusal.
    * BR684-E-1, a cut heading voids the body: it is void when any line ``md_hidden`` reads VISIBLE that is an ATX
      heading in its source changes in the output at all.
    * Rule 3, a body is voided when a cut changes a visible line's block role, cuts a visible heading, or touches a
      ``fixed-above`` claim (wrapped ones included) or manufactures one. (a) Removal: a ``FIXED_ABOVE_RE`` match in the
      whole source body (run over the joined source, so a claim wrapped across lines is one match) that touches a line the
      cuts changed voids the body, unless it lies on one line and that line's sorted whole claims are identical before
      and after the cut (so an inline comment on a claim line keeps the claim). (b) Manufacture: a line the cuts changed
      that could join a claim from fragments, and whose sorted whole claims differ before and after the cut, voids the
      body (the per-line guard kept from the earlier leg, so a claim joined from fragments cannot balance one a cut
      removed). A placeholder that is no claim matches neither.
    * The block-role guard: the body is void when a cut changed the block role (fence kind, or ATX heading or not) of a
      line ``md_hidden`` reads VISIBLE, because the section reader re-parses the cut text.
    * Kept as they were: a whole-line ``superheroes:`` marker is kept; a line ``md_hidden`` blanks stays blanked;
      ``md_hidden`` failing on a str blanks every non-marker line; the output keeps the input's line count (the last
      line without a terminator excepted); ``_visible`` never raises on a str; every change only removes text, or voids.
    * Lines are Markdown lines (``md_fence.split_lines``: ``\\r\\n``, ``\\r``, ``\\n``), so U+2028, U+2029, U+0085, VT, FF,
      FS, GS and RS are ordinary characters inside one.

    Not modelled: the cut over-reaches where GitHub would show the tail (inline markup, autolinks, ``a <b`` in prose),
    which is accepted because it fails toward a refusal."""
    lines = md_fence.split_lines(body)
    # axis: lines break only on Markdown endings (never U+2028 and the other str.splitlines breaks), and the fence scan
    # reads each line with exactly one terminator removed — see bite-proof record i2389_scanner_line_boundaries.md
    fence_scan = md_fence.scan([line[:len(line) - len(_terminator(line))] for line in lines])
    fenced, fence_kinds = fence_scan.inert, fence_scan.kinds
    rendering = md_hidden.scan(body)
    offset, shown = 0, []
    for line in lines:
        try:
            shown.append(rendering.state_at(offset) == md_hidden.VISIBLE)
        except ValueError:
            shown.append(False)  # a line start md_hidden does not report reads as not visible: the cut fails closed
        offset += len(line)
    out, inside = [], False
    for n, line in enumerate(lines):
        term = _terminator(line)
        # axis: an open comment state ends at a blank line or an ATX heading that md_hidden reads VISIBLE: an inline comment cannot
        # cross either (a paragraph ends there), and a raw HTML comment that does is md_hidden's, which then reads the line hidden;
        # so an over-read comment never swallows the heading that bounds the acceptance section — see bite-proof record i2389_leftover_visible_within_line.md
        if inside and shown[n] and (not line.strip() or _ATX_LINE.match(line)):
            inside = False
        if not inside and _MARKER_LINE.match(line):
            out.append(line)
            continue
        # axis: a fenced line (by md_fence's rules) is shown text; a comment open across it stays open
        if fenced[n] and not inside:
            # axis: a fenced line md_hidden does not read VISIBLE keeps only its terminator — see bite-proof record i2389_scanner_line_boundaries.md
            if not shown[n]:
                out.append(term)
                continue
            # axis: a fenced line holding an entry `<` anywhere is treated as holding an opener, as a raw HTML block makes a tilde line text, not a fence — see bite-proof record i2389_leftover_visible_within_line.md
            # axis: a fence content line holding an entry `<` is blanked whole, never shortened, so it cannot become a fence delimiter when the section reader re-reads it; a delimiter line is shortened at that `<`, so it stays the opener or closer it was — see bite-proof record i2389_leftover_visible_within_line.md
            opener = _TAG_ENTRY.search(line)
            if opener is None:
                out.append(line)
            elif fence_kinds[n] == md_fence.KIND_CONTENT:
                out.append(term)
            else:
                out.append(line[:opener.start()] + term)
            continue
        kept, i, cut = [], 0, None
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
                # axis: a backslash before an entry `<` keeps the text before the backslash, then cuts the rest of the line from the backslash (inside an HTML block GitHub honours no escape) — see bite-proof record i2389_leftover_visible_within_line.md
                if _TAG_ENTRY.match(line, i + 1) is not None:
                    cut = i + 2  # the tail read for comment state starts after the entry `<`: it sets no comment state itself
                    break
                kept.append(line[i:i + 2])
                i += 2
            elif line[i] == "`":
                # axis: a code span closes only on a backtick run of exactly its own length
                end = _code_span_end(line, i)
                run = len(_TICKS.match(line, i).group(0))
                # axis: a code span whose content holds an entry `<` keeps the span only up to that `<`, then cuts the rest of the line, so text inside the span after it (which GitHub hides inside an HTML block, honouring no code span) never counts — see bite-proof record i2389_leftover_visible_within_line.md
                quoted = _TAG_ENTRY.search(line, i + run, end - run) if end is not None else None
                if quoted is not None:
                    kept.append(line[i:quoted.start()])
                    cut = end  # the tail read for comment state starts after the span: a quoted opener opens nothing
                    break
                kept.append(line[i:end if end is not None else i + run])
                i = end if end is not None else i + run
            elif line.startswith("<!--", i):
                inside, i = True, i + 4
            # axis: any other unescaped, unquoted entry `<` (a tag, an end tag, a PI, a declaration, a bogus opener) cuts the rest of the line: GitHub's tokenizer leaves data state there and hides what follows — see bite-proof record i2389_leftover_visible_within_line.md
            elif _TAG_ENTRY.match(line, i):
                cut = i
                break
            else:
                kept.append(line[i])
                i += 1
        if cut is not None:
            tail = line[cut:]
            # axis: a comment the cut tail opens and does not close still opens the comment state for later lines (fails closed: an over-read only cuts more) — see bite-proof record i2389_leftover_visible_within_line.md
            opened = tail.rfind("<!--")
            if opened >= 0 and tail.find("-->", opened + 4) < 0:
                inside = True
        text = "".join(kept)
        # axis: a line md_hidden does not read VISIBLE keeps only its terminator (the loop above still ran, so `inside` carries on)
        # — see bite-proof record i2389_scanner_line_boundaries.md
        if not shown[n]:
            text = term
        # the line keeps its own terminator (\r\n, \n or lone \r) even when a comment cut it, so the line count never changes
        out.append(text if not term or text.endswith(term) else text + term)
    text = "".join(out)
    # axis: a ``fixed-above`` claim the cuts removed (fewer tokens, or fewer whole claims over the whole text, so a wrapped one counts)
    # voids the body, whichever path removed it; the caller then accepts nothing — see bite-proof record i2389_leftover_visible_within_line.md
    void = (len(_FIXED_ABOVE_TOKEN.findall(text)) < len(_FIXED_ABOVE_TOKEN.findall(body))
            or len(FIXED_ABOVE_RE.findall(text)) < len(FIXED_ABOVE_RE.findall(body)))
    # axis: (b) manufacture: a line the cuts changed that holds both the word "fixed" and the word "above" in its source and whose
    # whole claims differ before and after the cut (one removed, or one joined from fragments) voids the body, so a joined claim
    # elsewhere cannot balance the counts of one the cuts removed — see bite-proof record i2389_leftover_visible_within_line.md
    void = void or any(out[n] != lines[n] and _FIXED_WORD.search(lines[n]) and _ABOVE_WORD.search(lines[n])
                       and sorted(FIXED_ABOVE_RE.findall(out[n])) != sorted(FIXED_ABOVE_RE.findall(lines[n]))
                       for n in range(len(lines)))
    # axis: (a) removal: a ``fixed-above`` claim in the source body (matched over the whole joined source, so one wrapped across
    # lines is one match) that touches a line the cuts changed voids the body, unless it lies on one line and that line's sorted
    # whole claims are the same before and after the cut; a placeholder that is no claim (``fixed-above #<layer PR> <commit>``)
    # matches nothing here, so cutting it voids nothing — see bite-proof record i2389_leftover_visible_within_line.md
    if not void:
        starts = [0]
        for line in lines:
            starts.append(starts[-1] + len(line))
        for claim in FIXED_ABOVE_RE.finditer("".join(lines)):
            first = bisect.bisect_right(starts, claim.start()) - 1
            last = bisect.bisect_right(starts, claim.end() - 1) - 1
            if any(out[n] != lines[n] for n in range(first, last + 1)) and not (
                    first == last
                    and sorted(FIXED_ABOVE_RE.findall(out[first])) == sorted(FIXED_ABOVE_RE.findall(lines[first]))):
                void = True
                break
    # axis: so does a cut that changes a heading md_hidden reads VISIBLE and that is an ATX heading in its source, in any way, because
    # the section reader finds the acceptance section by its heading — see bite-proof record i2389_leftover_visible_within_line.md
    void = void or any(shown[n] and _ATX_LINE.match(lines[n]) and out[n] != lines[n] for n in range(len(lines)))
    # axis: and so does a cut that changes the block role of any line md_hidden reads VISIBLE (its fence kind, or whether it is an
    # ATX heading), because the section reader re-parses the cut text and a manufactured or lost fence or heading moves what it
    # reads as the acceptance section — see bite-proof record i2389_leftover_visible_within_line.md
    if not void:
        out_bare = [item[:len(item) - len(_terminator(item))] for item in out]
        out_kinds = md_fence.scan(out_bare).kinds
        void = any(shown[n] and (out_kinds[n] != fence_kinds[n]
                                 or bool(_ATX_LINE.match(out[n])) != bool(_ATX_LINE.match(lines[n])))
                   for n in range(len(lines)))
    return text, void


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
    text, claim_removed = _visible_claim(body if isinstance(body, str) else "")
    # axis: a body whose visible text lost a fixed-above claim accepts nothing, so a claim needing stack verification is never dropped while its acceptance counts — see bite-proof record i2389_leftover_visible_within_line.md
    if claim_removed:
        return []
    return pr_sheet.accepting_listed(text)


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
