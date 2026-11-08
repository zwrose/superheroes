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

What counts as text (#2389, the segment-first model): the section and its items are read once, from the body with the
lines ``md_hidden`` does not read VISIBLE blanked (``_blanked_lines``), by the one reader ``pr_sheet.accepting_item_spans_of``.
Only then is each item read (``_item_cut``), so a cut can never move structure or join words GitHub separates. An item where
a within-line cut fires (an entry ``<``, an unclosed ``<!--``) counts as nothing, never the words before the cut (#2389 vet
856); a hidden or dropped line only ends the item at that line. Claims are compared per item (``_cut_items``): an item whose
whole ``fixed-above #<PR> <commit>`` claims differ from its own source span's counts as nothing, never summed across items,
and a bare mention of the word is never compared. Spans and the claim compare: see ``_cut_items``. Known over-refusal (not
modelled beyond V852-4): an item holding a ``<`` that can start markup anywhere, or continued by a tag line such as
``</div>``, counts as nothing.

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


def _blanked_lines(body):
    """``(lines, shown)``: one entry per ``md_fence.split_lines(body)`` line (a blanked line reduced to its terminator, an
    unterminated blanked last line kept as ``""``), and the flags (``shown[n]`` is true when line ``n`` is read VISIBLE); see
    ``_cut_items``. A whole-line ``superheroes:`` marker line is kept whatever ``md_hidden`` reads, so the section reader
    still finds the build-record boundary. ``md_hidden`` failing on a str reads every line unsure: every other line blanks."""
    # axis: lines break only on Markdown endings (never U+2028 and the other str.splitlines breaks) — see bite-proof record i2389_scanner_line_boundaries.md
    lines = md_fence.split_lines(body)
    rendering = md_hidden.scan(body)
    offset, shown, out = 0, [], []
    for line in lines:
        try:
            shown.append(rendering.state_at(offset) == md_hidden.VISIBLE)
        except ValueError:
            shown.append(False)  # a line start md_hidden does not report reads as not visible: the cut fails closed
        offset += len(line)
        # axis: a line md_hidden does not read VISIBLE keeps only its terminator, a marker line excepted — see bite-proof record i2389_scanner_line_boundaries.md
        out.append(line if shown[-1] or _MARKER_LINE.match(line) else _terminator(line))
    return out, shown


def _blanked(body):
    """``(text, shown)``: ``_blanked_lines``'s lines joined, and its flags; positions are read from ``_blanked_lines``."""
    lines, shown = _blanked_lines(body)
    return "".join(lines), shown


def _visible(body):
    """The body with the lines ``md_hidden`` does not read VISIBLE blanked (``_blanked``'s text); no within-line cut."""
    return _blanked(body)[0]


def _scan_line(line, start):
    """``(kept, cut)``: the text of one ``text`` line of an item from ``start`` on, and whether a cut fired on it. A cut makes
    the whole item count as nothing (``_item_cut`` reads ``kept`` only when ``cut`` is false), because the words before an
    entry ``<`` may be joined by GitHub to hidden or shown text after it (#2389 vet 856). Within-line rules: an escaped entry
    ``<`` cuts; any other escaped character is kept; a code span is kept, unless its content holds an entry ``<`` (cut); a
    ``<!-- ... -->`` closed on the line is dropped and the scan goes on (not a cut); an unclosed ``<!--`` cuts; any other
    entry ``<`` (``_TAG_ENTRY``) cuts."""
    kept, i = [], start
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            # axis: an escaped character (a backtick or a `<`) is literal text, never a delimiter
            # axis: a backslash before an entry `<` keeps the text before the backslash and cuts from it (inside an HTML block GitHub honours no escape) — see bite-proof record i2389_leftover_visible_within_line.md
            if _TAG_ENTRY.match(line, i + 1) is not None:
                return "".join(kept), True
            kept.append(line[i:i + 2])
            i += 2
        elif line[i] == "`":
            # axis: a code span closes only on a backtick run of exactly its own length
            end = _code_span_end(line, i)
            run = len(_TICKS.match(line, i).group(0))
            # axis: a code span whose content holds an entry `<` keeps the span only up to that `<`, then cuts, so text inside the span after it (which GitHub hides inside an HTML block, honouring no code span) never counts — see bite-proof record i2389_leftover_visible_within_line.md
            quoted = _TAG_ENTRY.search(line, i + run, end - run) if end is not None else None
            if quoted is not None:
                kept.append(line[i:quoted.start()])
                return "".join(kept), True
            kept.append(line[i:end if end is not None else i + run])
            i = end if end is not None else i + run
        elif line.startswith("<!--", i):
            close = line.find("-->", i + 4)
            # axis: a comment closed on its line is dropped; an unclosed one cuts to the item's end, since GitHub hides what follows it
            if close < 0:
                return "".join(kept), True
            i = close + 3
        # axis: any other unescaped, unquoted entry `<` (a tag, an end tag, a PI, a declaration, a bogus opener) cuts: GitHub's tokenizer leaves data state there and hides what follows — see bite-proof record i2389_leftover_visible_within_line.md
        elif _TAG_ENTRY.match(line, i):
            return "".join(kept), True
        else:
            kept.append(line[i])
            i += 1
    return "".join(kept), False


def _item_cut(lines, span, shown):
    """The text of one item, or ``""`` when the item counts as nothing. ``lines`` are the lines (terminators kept) of
    ``_blanked_lines``, ``span`` one entry of ``pr_sheet.accepting_item_spans_of`` of it, ``shown`` the per-line flags of
    ``_blanked_lines``. The span is walked in order:

    * A line ``md_hidden`` does not read VISIBLE, or a ``dropped`` line, is a stop point: the item ends at that line and keeps
      the text of the lines before it. It is not a cut. A ``blank`` line is skipped, as the reader skips it.
    * A ``text`` line is scanned by ``_scan_line``. A closed inline ``<!-- ... -->`` comment is dropped and is not a cut.
    * A ``fenced`` line is kept literally (GitHub shows a fence's content as it is; no comment is dropped on it).

    A cut anywhere in the walked lines makes the whole item count as nothing (``""``), never the words before the cut:
    an entry ``<`` on a ``text`` line (plain, escaped or inside a code span), an unclosed ``<!--``, or an entry ``<`` on a
    ``fenced`` line. The words before such a ``<`` may be joined by GitHub to what follows (``f-1<span>-other</span>`` shows
    ``f-1-other``; a title word cut short reads whole) (#2389 vet 856). Otherwise the result is the kept parts, stripped and
    joined with one space, as ``pr_sheet.accepting_listed`` joins an item. It only removes text."""
    parts = []
    for k, (n, kind) in enumerate(span):
        # axis: a line md_hidden does not read VISIBLE, or one the reader drops (a whole-line comment, a line inside one), stops the item — see bite-proof record i2389_leftover_visible_within_line.md
        if n >= len(lines) or n >= len(shown) or not shown[n] or kind == "dropped":
            break
        if kind == "blank":
            continue
        line = lines[n][:len(lines[n]) - len(_terminator(lines[n]))]
        start = pr_sheet.item_text_start(line) if k == 0 else 0
        if kind == "fenced":
            # axis: a fenced line is literal text, no comment is dropped on it; an entry `<` on it makes the whole item count as nothing — see bite-proof record i2389_leftover_visible_within_line.md
            if _TAG_ENTRY.search(line, start):
                return ""
            parts.append(line[start:].strip())
        else:
            kept, cut = _scan_line(line, start)
            # axis: a cut anywhere in the item (entry `<` plain, escaped or code-spanned, unclosed `<!--`) makes the whole item count as nothing, never the words before the cut (#2389 vet 856, G22) — see bite-proof record i2389_leftover_visible_within_line.md
            if cut:
                return ""
            parts.append(kept.strip())
    return " ".join(part for part in parts if part)


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
    """The acceptances the body lists under What we're accepting, each reduced to the text GitHub shows (#2389): ``[]`` for a
    body that is not a str or has no acceptance. Read once, reduced per item:

    1. The body is blanked (``_blanked_lines``): a line ``md_hidden`` does not read VISIBLE keeps only its terminator.
    2. The section and its items are read once, from the blanked lines, by ``pr_sheet.accepting_item_spans_of``.
    3. Each item is read by ``_item_cut``: a hidden or dropped line is a stop point that ends the item at that line (the
       item keeps the lines before it); a fenced line is literal; a closed inline comment is dropped; and a cut anywhere in
       the item (an entry ``<`` on a text line, plain, escaped or code-spanned, an unclosed ``<!--``, an entry ``<`` on a
       fenced line) makes the whole item count as nothing, never the words before the cut (#2389 vet 856).
    4. Claims are compared per item (``_cut_items``): the sorted ``FIXED_ABOVE_RE`` claims of an item's text differing from
       those of its claim source (the source's own items, read before blanking, hidden and dropped lines included) make that item count as
       nothing (a claim removed, joined or changed). Claims are never summed across items, so equal claims in two items
       cannot cancel. Only whole claims are compared: a bare mention of ``fixed-above`` that is not a claim never matters. A
       claim wrapped across lines is one whole match in the source span (an item's lines are joined before the regex runs).
       The body-wide void is retired: one item that counts as nothing leaves the other items counting.
    5. The empty items, and the None, N/A, NA and Nothing items, are no acceptance (``pr_sheet.acceptance_texts``).

    Not modelled: Markdown link and image titles, and image alt text, count as text, though GitHub shows them only as
    attributes (V852-4, disclosed). Known over-refusal: an item holding a ``<`` that can start markup anywhere in it (an
    inline tag, an autolink, a ``<`` + letter, ``!``, ``?`` or ``/``, plain, escaped or code-spanned), or continued by a tag
    line such as ``</div>``, counts as nothing, though GitHub would show its words.

    Steps 1, 2 and 4's rule (the claim source) and its over-refusal: see ``_cut_items``.

    Every change only removes text, or makes an item count as nothing. Never raises on a str."""
    return pr_sheet.acceptance_texts(_cut_items(body)[0])


def _cut_items(body):
    """``(items, void)``: the text of every item of the section (``_accepting_items`` steps 1 to 4, before the None and N/A
    filter; ``""`` for an item that counts as nothing), and ``void``, always ``False`` (the body-wide void is retired).
    ``([], False)`` for anything that is not a str.

    One line list (#2389 vet 859): ``_blanked_lines`` has one entry per source line, and the spans
    (``pr_sheet.accepting_item_spans_of`` over the entries minus their terminators), the cuts (``_item_cut``) and the sources
    (``md_fence.split_lines(body)``) all index it, so span index ``n`` is source line ``n``. It is never joined and split
    again (a blanked last line would vanish; a lone ``\\r`` before a blanked ``\\n`` line would join into ``\\r\\n``).

    The claim compare (#2389 vet 860; it retires vet 859's join): the section's items are also read from the source lines
    (``src_spans``, the same reader over the lines before blanking). Each item of the blanked reading has a claim source: its
    own lines, plus every line of each source item that shares a line with it, joined in line order with one space. The item
    counts as nothing unless the sorted ``FIXED_ABOVE_RE`` claims of its cut text equal those of its claim source. So a
    blanked line never moves a claim out of the item that names the finding: the claims are compared against the source's
    own items, not the blanked reading's. The claim source only grows an item's comparison, so it never makes an item count
    that counted as nothing.

    Known over-refusal: an item counts as nothing when a line of the acceptance as written (before hidden lines are blanked)
    holds a claim that the item's shown text lacks. That covers a hidden or unsure first, middle or last line (a hidden last
    line holding a claim counts as nothing, as when it ends in a newline; a hidden first line holding a claim, which GitHub
    hides), and a paragraph GitHub shows apart after a column-0 comment line. The two over-refusals of vet 859 are cases of it."""
    if not isinstance(body, str):
        return [], False
    blanked, shown = _blanked_lines(body)
    source_lines = md_fence.split_lines(body)
    # axis: one line list (#2389 vet 859, G24): the spans, the cuts and the sources all index the entries of `blanked`, one per source line, so every span index names the same line in both; the lines are never joined and split again — see bite-proof record i2389_leftover_visible_within_line.md
    spans = pr_sheet.accepting_item_spans_of([line[:len(line) - len(_terminator(line))] for line in blanked])
    cuts = [_item_cut(blanked, span, shown) for span in spans]
    src_spans = pr_sheet.accepting_item_spans_of([line[:len(line) - len(_terminator(line))] for line in source_lines])
    owner = {n: i for i, sp in enumerate(src_spans) for n, _kind in sp}
    sources = []
    for span in spans:
        # axis: an item's claims are compared against the source's own items (#2389 vet 860, G25): the claim source is the item's own lines plus every line of each source item that shares a line with it, so a blanked line never moves a claim out of the item that names the finding — see bite-proof record i2389_leftover_visible_within_line.md
        taken = {n for n, _kind in span}
        for i in {owner[n] for n in taken if n in owner}:
            taken |= {n for n, _kind in src_spans[i]}
        sources.append(" ".join(source_lines[n].strip() for n in sorted(taken) if n < len(source_lines)))
    # axis: claims are compared per item, never summed across items (#2389 vet 856, G23): an item whose cut text holds other whole claims than its claim source (one removed, joined from fragments, or changed) counts as nothing, so equal claims in two items cannot cancel — see bite-proof record i2389_leftover_visible_within_line.md
    return [cut if sorted(FIXED_ABOVE_RE.findall(cut)) == sorted(FIXED_ABOVE_RE.findall(source)) else ""
            for cut, source in zip(cuts, sources)], False


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
    read. Only text that renders counts (``_accepting_items``: read once from the blanked body, cut per item). A leftover
    whose finding carries no title is checked by its id alone. One acceptance counts for at most one leftover
    (``_assign``): a leftover with no acceptance of its own is missing, however many acceptances name it or however many
    leftovers one acceptance names."""
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
    """``fixed_above``'s claims, each with ``acceptance``: the cut text of the acceptance the whole-body assignment
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
