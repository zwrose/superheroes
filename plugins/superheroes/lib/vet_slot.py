#!/usr/bin/env python3
"""Write or check the advisor-vet slot of a PR body against its vet receipt.

Consumers: the showrunner vet's owner-half write (``write``), the merged or
closed-PR follow-ups sweep (``check``), and the workhorse's ready-PR step
(``handback``: the same body read ``write`` and ``check`` run first, over a body file or
an open PR, with no receipt, so a builder fixes a bad marker while its lane is live; over an open PR
it also refuses ``stack-not-caught-up`` or ``stack-lower-unreadable`` for a stacked PR whose head
does not hold its lower branch's current head). The writer compares two machine-readable
marker lists and reads no other prose: the build record's
``<!-- superheroes:followups FU1 FU2 -->`` marker (or ``none``) and the latest vet
receipt's ``<!-- superheroes:dispositions FU1 FU2 -->`` marker (or ``none``).
``write`` changes the PR body only in the span strictly between the advisor-vet
marker line and the build-record marker line, and only when the two lists name the
same ids. The followups marker is the builder's own declaration; the writer trusts
it and does not re-derive it from the prose; the vet reads both. Any failed read or
check is a refusal with one of twenty reasons (``bad-argument``, ``read-failed``,
``body-emptied`` (``write`` only, before any marker check: the body is empty or whitespace, or no live
``What's changing, and why`` heading sits above the advisor-vet marker (live: GitHub renders it, decided by
``md_hidden.scan``), so the builder's owner half is lost and the body is restored from the PR's edit history rather
than re-stamped; when the parse could not decide the render the detail says so and the advisor moves the text by hand),
``markers-invalid``, ``slot-span-foreign-content`` (another ``superheroes:`` marker line
inside the slot span, which the write would delete),
``slot-span-builder-text`` (``write`` only, builder body: the slot span holds text other than the builder's reminder
and the advisor's own earlier verdict - a builder section, prose above the verdict line, or any other HTML
comment - which the write would delete), ``receipt-missing``, ``followup-undispositioned``,
``disposition-unknown``, ``none-over-list``, ``write-failed`` (also: the marker or the slot's first line would render
hidden, or ``md_hidden`` cannot be sure it renders),
``write-unconfirmed``, ``owner-command-in-body`` (``handback`` only: a fenced shell block that
names a database tool or a Keychain read), ``leftover-not-accepted`` and ``review-record-unreadable`` (``handback``
over an open PR, and ``write`` of a READY verdict: a finding the latest review record leaves for the owner is not
named, by record id and title, under What we're accepting, or that record cannot be read; the rule's one home is
``leftover_accepting.py``), ``fixed-above-not-in-stack`` and ``fixed-above-unverified`` (both callers of the leftover
rule: an acceptance carries ``fixed-above #<PR> <commit>`` and the named PR is not a higher member of this PR's own
stack, or the stack cannot be read so the disposition is not accepted), ``calibration-disclosure-contradicted``, ``calibration-disclosure-unknown-seat`` and
``calibration-disclosure-unmarked`` (``handback`` over an open PR: a calibration marker in a degradation bullet that the
latest review record contradicts, or that names a row the record lacks, or a degradation bullet that mentions
calibration outside the marker; the rule's one home is ``calibration_disclosure.py``)) and a detail naming what was wrong; no edit is made, except
for ``write-unconfirmed``: the edit call was launched (and may have failed) but the
readback failed or differed from the pushed body. One JSON line on stdout; exit 0
on ok, 1 on refusal.

A PR no builder made (a dependency bump, a bot's PR) has no build record. ``write`` and ``check`` read such a body as
having no follow-ups and need no build-record or followups marker: ``write`` puts the slot under the advisor-vet marker
to the end of the body, or appends a ``## Advisor vet`` heading, the marker and the slot when the marker is absent. The
body takes this path only if ``no_build_record`` finds it non-blank and showing no builder sign anywhere (a superheroes
marker other than advisor-vet, the ``Build record`` wrapper, or a builder section heading); every other body takes
the build-record path described before this paragraph, unchanged. ``handback`` is unchanged: it is the builder's
verb, and a builder body keeps needing its build record."""
import argparse
import bisect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import calibration_disclosure  # noqa: E402
import gh_pages  # noqa: E402
import leftover_accepting  # noqa: E402
import md_fence  # noqa: E402
import md_hidden  # noqa: E402
import pr_body_regions  # noqa: E402
import review_record  # noqa: E402
import stack_check  # noqa: E402

GH_TIMEOUT = 120
RECEIPT_MARKER = "<!-- superheroes:vet-receipt -->"
PENDING_MARKER = "<!-- superheroes:pending-proposals -->"
REASON_STACK_NOT_CAUGHT_UP = "stack-not-caught-up"
REASON_STACK_LOWER_UNREADABLE = "stack-lower-unreadable"
REASON_BODY_EMPTIED = "body-emptied"
FOLLOWUPS_MARKER_NAME = "followups"
DISPOSITIONS_MARKER_NAME = "dispositions"
VERBS = ("write", "check", "handback")
SHELL_LANGUAGES = frozenset({"bash", "sh", "zsh", "shell", "console", "shell-session", "sh-session",
                             "shellsession", "terminal", "shell-script", "ksh", "fish", "text", "txt",
                             "plaintext", ""})
DATABASE_TOOLS = ("mongosh", "mongo", "mongodump", "mongorestore", "psql", "pg_dump", "pg_restore",
                  "mysql", "mysqldump", "redis-cli", "sqlite3")
OWNER_COMMAND_ADVICE = ("a command the owner is asked to run that names a database tool or reads a"
                        " Keychain item lives in a committed file on the PR branch: move the block"
                        " into that file and have the body tell the owner to run the file"
                        " (bash <path>) rather than paste its lines")

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_HEAD_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_KEYCHAIN_RE = re.compile(
    r"""(?<![\w-])['"]?security['"]?\s+['"]?find-(?:generic|internet)-password['"]?(?![\w-])""")
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)")
_DATABASE_TOOL_RE = re.compile(
    r"(?<![A-Za-z0-9_.@-])(?:%s)(?![A-Za-z0-9_./:@-])"
    % "|".join(re.escape(tool) for tool in sorted(DATABASE_TOOLS, key=len, reverse=True)))
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_LIST_MARKER_RE = re.compile(r"^(?:[-*+]|[0-9]{1,9}[.)])[ \t]+")
_ATX_HEADING_RE = re.compile(r"^ {0,3}#{1,6} (.*)$")
# the slot-span guard's own heading pattern: a space or a tab after the hashes, or a bare hash run (_ATX_HEADING_RE stays as is)
_SLOT_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
_REMINDER_OPENER = "<!-- advisor: BEFORE writing this slot"
# no_build_record's own patterns: wider than the module's on purpose (over-matching reads as builder-shaped)
_SUPERHEROES_OPEN_RE = re.compile(r"<!--\s*superheroes:")
_BUILD_RECORD_WRAPPER_RE = re.compile(r"<summary[^>]*>\s*build\s+record", re.IGNORECASE)
_ANY_HEADING_RE = re.compile(r"^[ \t>*+\-0-9.)]*#{1,6}[ \t]+(.*)$")
_ACCEPTING_KEY = "what were accepting"
_BUILDER_HEADING_KEYS = ("whats changing", _ACCEPTING_KEY, "how to see it", "build record", "build brief",
                         "dispatch provenance", "disclosed degradations", "followups for the advisor",
                         "definition of done", "dod disposition", "size tripwire", "biteproof records")


class _Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(2)  # no usage text: stdout carries exactly one JSON line


def _refusal(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail}


def _bare(whole):
    """``whole`` (one item of ``md_fence.split_lines``) without its one terminator: ``\\r\\n``, ``\\n`` or ``\\r``."""
    if whole.endswith("\r\n"):
        return whole[:-2]
    if whole.endswith(("\n", "\r")):
        return whole[:-1]
    return whole


def _bare_lines(text):
    """The Markdown lines of ``text`` (``md_fence.split_lines``), each without its terminator."""
    return [_bare(whole) for whole in md_fence.split_lines(text)]


def _line_state(rendering, offset):
    """The ``md_hidden`` state of the Markdown line HOLDING ``offset``: the last ``rendering.lines`` entry at or before it.

    The one chokepoint for a visibility read at an offset that may sit inside a line (``_find_live_standalone_markers``
    returns ``offset + leading``, and a Markdown line can begin with U+2028 or other Unicode whitespace). ``state_at``
    is never called here: it raises for an offset that is not a line start. No line at or before ``offset`` (a negative
    offset, an empty body) reads ``UNSURE``, which every caller treats as not visible."""
    # axis: a visibility read at an offset inside a Markdown line reads the line holding it, never raising on a non-line-start — see bite-proof record i2389_vet_slot_md_hidden.md
    starts = [at for at, _state in rendering.lines]
    index = bisect.bisect_right(starts, offset) - 1
    if index < 0:
        return md_hidden.UNSURE
    return rendering.lines[index][1]


def _live_lines(text):
    """Yield ``(offset, line)`` for every line outside a code fence, lines read as Markdown reads them
    (``md_fence.split_lines``: ``\\r\\n``, a lone ``\\r`` or ``\\n``; U+2028 and the other ``str.splitlines`` breaks
    are ordinary characters).

    HTML comments are not modelled: a marker line always counts, whether or not it sits inside
    what looks like an HTML comment."""
    raw = md_fence.split_lines(text)
    bare = [_bare(line) for line in raw]
    inert = md_fence.scan_contexts(bare).inert
    offset = 0
    for line, dead, whole in zip(bare, inert, raw):
        if not dead:
            yield offset, line
        offset += len(whole)


def read_marker_list(text, name, after=0):
    """Return the ids of the one live ``<!-- superheroes:<name> ... -->`` line, or None for ``none``.

    A marker line starts at column zero, outside any code fence; it must not start above offset
    ``after``."""
    prefix = "<!-- superheroes:%s" % name
    found = []
    for offset, line in _live_lines(text):
        rest = line[len(prefix):]
        if line.startswith(prefix) and (rest[:1] == " " or rest[:3] == "-->"):
            found.append((offset, line))
    # axis: a followups or dispositions marker present other than exactly once refuses markers-invalid
    if len(found) != 1:
        raise _Refusal("markers-invalid", "%s marker appears %d times" % (name, len(found)))
    start, line = found[0]
    # axis: a followups marker above the build-record marker refuses markers-invalid
    if start < after:
        raise _Refusal("markers-invalid", "%s marker is not below the build-record marker" % name)
    match = re.match(r"^<!-- superheroes:%s (none|FU[1-9][0-9]*(?: FU[1-9][0-9]*)*) -->$"
                     % re.escape(name), line.rstrip())
    # axis: a marker line off the exact shape refuses markers-invalid
    if not match:
        raise _Refusal("markers-invalid", "%s marker is malformed: %s" % (name, line))
    if match.group(1) == "none":
        return None
    ids = match.group(1).split()
    for i, fu_id in enumerate(ids):
        # axis: an id listed twice in one marker refuses markers-invalid
        if fu_id in ids[:i]:
            raise _Refusal("markers-invalid", "%s marker repeats %s" % (name, fu_id))
    return ids


def _find_live_standalone_markers(body, marker):
    """Fence-aware, zero-indent standalone ``marker`` lines."""
    found = []
    for offset, line in _live_lines(body):
        if md_fence.indent_width(line) == 0 and line.strip() == marker:
            leading = len(line) - len(line.lstrip())
            found.append(offset + leading)
    return found


def _live_heading_offsets(body):
    """``(offset, text)`` of the live ATX headings of ``body``: the document-level headings ``md_hidden.scan`` reads as
    ``VISIBLE`` (``text`` as ``md_hidden`` gives it, comment and tag runs removed).

    Live means GitHub renders it. A heading ``md_hidden`` reads ``HIDDEN`` or ``UNSURE`` is never live, and a setext
    heading is never in ``Rendering.headings``, so it never counts."""
    # axis: only a heading md_hidden reads VISIBLE is live; hidden and unsure headings are skipped — see bite-proof record i2389_vet_slot_md_hidden.md
    for offset, text, state in md_hidden.scan(body).headings:
        if state == md_hidden.VISIBLE:
            yield offset, text


def _heading_key(text):
    """A heading's text lower-cased, U+2019 as ``'``, reduced to letters, digits and single spaces."""
    kept = "".join(ch for ch in text.lower().replace("’", "'") if ch.isalnum() or ch == " ")
    return " ".join(kept.split())


def check_not_emptied(body):
    """Refuse ``body-emptied`` when ``body`` is empty or whitespace, or has lost the owner half: no live
    ``What's changing, and why`` heading sits above the advisor-vet marker (anywhere, when that marker is absent).

    Live means GitHub renders it, decided by ``md_hidden.scan`` (``_live_heading_offsets``): a heading read ``hidden`` or
    ``unsure`` is not held, and neither is an image heading (its text holds ``![``). When no heading is held and the
    parse holds an unsure point above the marker, the detail says the render could not be decided and that the advisor
    moves the text by hand, never the edit-history remedy.

    The single chokepoint of the ``write`` path, called before any marker check. A non-string body is left to
    ``analyze_body``, which refuses it ``read-failed``."""
    if not isinstance(body, str):
        return
    remedy = "; restore the builder's body from the PR's edit history before writing the slot"
    # axis: an empty or whitespace body refuses body-emptied, not read-failed — see bite-proof record i2323_vet_slot_emptied.md
    if not body.strip():
        raise _Refusal("body-emptied", "PR body is empty" + remedy)
    markers = _find_live_standalone_markers(body, pr_body_regions.REGION_MARKERS["advisor-vet"])
    limit = min(markers) if markers else len(body) + 1
    # axis: a heading inside an HTML comment span does not count — see bite-proof record i2323_vet_slot_emptied.md
    # axis: a heading not above the advisor-vet marker does not count — see bite-proof record i2323_vet_slot_emptied.md
    # axis: only a heading md_hidden reads VISIBLE is the owner half (G1), and an image heading (its text holds "![") never is (G2) — see bite-proof record i2389_vet_slot_md_hidden.md
    held = [at for at, text in _live_heading_offsets(body)
            if at < limit and "![" not in text and _heading_key(text).startswith("whats changing")]
    # axis: a body with no live owner-half heading above the marker refuses body-emptied, before any marker check — see bite-proof record i2323_vet_slot_emptied.md
    if not held:
        unsure = [(at, why) for at, why in md_hidden.scan(body).unsure if at < limit]
        # axis: an undecided render above the marker (G3) says so and sends the advisor to move the text by hand, with no edit-history remedy — see bite-proof record i2389_vet_slot_md_hidden.md
        if unsure:
            raise _Refusal("body-emptied", 'PR body has no "What\'s changing, and why" heading%s that GitHub is sure to'
                           " render: the render could not be decided (%s); the advisor moves the text by hand"
                           % (" above the advisor-vet marker" if markers else "", unsure[0][1]))
        raise _Refusal("body-emptied", 'PR body has no "What\'s changing, and why" heading%s%s'
                       % (" above the advisor-vet marker" if markers else "", remedy))


def _span_owned_problem(span):
    """Why the slot ``span`` is not the advisor's own, as ``(line_number, line, sign, why)``, or None when it is.

    The advisor's own span, after the builder's reminder comments and the blank lines are removed, is nothing, or a
    run of lines that (a) opens with a verdict token of the canonical form, (b) holds no HTML comment opener or
    closer, and (c) holds no live ATX heading (outside a code fence; a space or a tab after the hashes, or none)."""
    # axis: the span is read as Markdown lines (md_fence.split_lines), so text after a U+2028 or other splitlines-only break stays inside its line — see bite-proof record i2389_vet_slot_md_hidden.md
    kept = list(enumerate(_bare_lines(span), 1))
    while True:  # reminders go first, one at a time, so a fence mark inside one cannot hide a later heading
        inert = md_fence.scan_contexts([text for _n, text in kept]).inert
        opening = next((i for i, (_n, text) in enumerate(kept)
                        if not inert[i] and " ".join(text.split()).startswith(_REMINDER_OPENER)), None)
        if opening is None:
            break
        number, first = kept[opening]
        closing = None
        for j in range(opening, len(kept)):
            text = kept[j][1]
            at = text.find("-->", len(text) - len(text.lstrip()) + len("<!--") if j == opening else 0)
            if at >= 0:
                closing = (j, text, at)
                break
        # axis: a reminder with no closing --> before the build-record marker is not the advisor's — see bite-proof record i2352_vet_slot_builder_text.md
        if closing is None:
            return number, first, "(b) no comment", "a reminder comment is never closed"
        j, text, at = closing
        # axis: text after a reminder's closing --> on the same line is span content, not the advisor's — see bite-proof record i2352_vet_slot_builder_text.md
        if text[at + 3:].strip():
            return kept[j][0], text, "(b) no comment", "text follows the reminder's closing -->"
        del kept[opening:j + 1]
    inert = md_fence.scan_contexts([text for _n, text in kept]).inert
    rest = [(number, text, dead) for (number, text), dead in zip(kept, inert) if text.strip()]
    if not rest:
        return None
    form, error = stack_check._load_vet_verdict_form()
    # axis: an unreadable verdict form refuses a non-empty span, failing closed — see bite-proof record i2352_vet_slot_builder_text.md
    if form is None:
        return rest[0][0], rest[0][1], "(a) verdict first", "the verdict form cannot be read (%s)" % error
    tokens = [token for token, _verdict in form[1]]
    for index, (number, text, dead) in enumerate(rest):
        # axis: the first remaining line must open with a verdict token — see bite-proof record i2352_vet_slot_builder_text.md
        if index == 0 and not any(text.startswith(token) for token in tokens):
            return number, text, "(a) verdict first", "the span does not open with a verdict line"
        # axis: no remaining line may hold an HTML comment opener or closer — see bite-proof record i2352_vet_slot_builder_text.md
        if "<!--" in text or "-->" in text:
            return number, text, "(b) no comment", "an HTML comment other than the builder's reminder"
        # axis: no remaining line outside a code fence may be an ATX heading, tab-separated or bare too — see bite-proof record i2352_vet_slot_builder_text.md
        if not dead and _SLOT_HEADING_RE.match(text):
            return number, text, "(c) no heading", "a heading (a builder section)"
    return None


def check_span_owned(body, advisor_at, build_at):
    """Refuse ``slot-span-builder-text`` when the slot span of ``body`` holds anything but the advisor's own content.

    The span is the one ``evaluate`` replaces: from the line after the advisor-vet marker line to the build-record
    marker line. Called on the ``write`` path of a builder body only, after ``analyze_body``, and again over the
    composed body (emitter ⊆ recogniser)."""
    # axis: the checked span is exactly the span the write replaces: it starts after the marker's own str.splitlines() line (the shared helper) and ends at the build-record marker, so builder text after a lone CR or U+2028 on the marker line is checked, never deleted unread — see bite-proof record i2352_vet_slot_builder_text.md
    start = _after_marker_line(body, advisor_at)
    if start < 0:  # the marker is the last line: there is no span (the write refuses this body itself)
        return
    problem = _span_owned_problem(body[start:build_at])
    if problem is None:
        return
    number, text, sign, why = problem
    raise _Refusal("slot-span-builder-text",
                   "the slot span holds text that is not the advisor's own: line %d of the span, %r, fails sign %s: %s;"
                   " write replaces only the builder's reminder and the advisor's own verdict; move that text above"
                   " the ## Advisor vet heading or below the build-record marker, or ask the builder to, then write"
                   " again" % (number, text[:60], sign, why))


def no_build_record(body):
    """Whether ``body`` is a PR no builder made: non-blank, and showing no builder sign anywhere.

    The one place the decision is made (``evaluate`` and ``_run_verb``, for ``write`` and ``check``; never
    ``handback``). The scan is of the raw text, code fences and HTML comments included (not ``_live_lines``): doubt
    reads as builder-shaped, so the allowance only ever turns a refusal into a write for a body with no builder sign.
    A builder sign is any of: a ``<!-- superheroes:`` other than a line that is exactly the advisor-vet marker; the
    ``<summary>Build record`` wrapper; an ATX heading (in a quote or list too) whose key starts with a builder
    section's. A ``What we're accepting`` heading below the live advisor-vet marker is the advisor's slot and does not
    count; with no live marker it counts."""
    # axis: a blank or non-string body is never no-build-record, so write refuses it body-emptied — see bite-proof record i2342_vet_slot_no_build_record.md
    if not isinstance(body, str) or not body.strip():
        return False
    # axis: the Build record wrapper is a builder sign, split across lines or not — see bite-proof record i2342_vet_slot_no_build_record.md
    if _BUILD_RECORD_WRAPPER_RE.search(body):
        return False
    marker = pr_body_regions.REGION_MARKERS["advisor-vet"]
    markers = _find_live_standalone_markers(body, marker)
    marker_at = min(markers) if markers else None
    offset = 0
    for whole in body.splitlines(keepends=True):
        line = whole.rstrip("\r\n")
        # axis: a superheroes marker other than the advisor-vet line is a builder sign, fenced or commented too — see bite-proof record i2342_vet_slot_no_build_record.md
        if _SUPERHEROES_OPEN_RE.search(line) and line.strip() != marker:
            return False
        # axis: headings below the advisor-vet marker are scanned too — see bite-proof record i2342_vet_slot_no_build_record.md
        heading = _ANY_HEADING_RE.match(line)
        if heading:
            # axis: a tab inside a heading separates its words here, so a tab-separated builder heading is still a builder sign — see bite-proof record i2352_vet_slot_builder_text.md
            key = _heading_key(" ".join(heading.group(1).split()))
            # axis: a builder-section heading is a builder sign, in a quote, list, fence or comment too — see bite-proof record i2342_vet_slot_no_build_record.md
            if key.startswith(_BUILDER_HEADING_KEYS):
                # axis: What we're accepting below the live advisor-vet marker is the advisor's slot, not a builder sign — see bite-proof record i2342_vet_slot_no_build_record.md
                exempt = key.startswith(_ACCEPTING_KEY) and marker_at is not None and offset > marker_at
                if not exempt:
                    return False
        offset += len(whole)
    return True


def analyze_no_build_record(body):
    """The no-build-record twin of ``analyze_body``: return the advisor-vet marker's offset, or None when absent.

    A body with the marker twice refuses ``markers-invalid``. The blank-body arm is defensive only: ``write`` and
    ``check`` never route a blank body here (``no_build_record`` is False for it)."""
    if not isinstance(body, str) or not body.strip():
        raise _Refusal("read-failed", "PR body is empty" if isinstance(body, str) else
                       "PR body is not a string")
    found = _find_live_standalone_markers(body, pr_body_regions.REGION_MARKERS["advisor-vet"])
    if len(found) > 1:
        raise _Refusal("markers-invalid", "advisor-vet marker appears %d times" % len(found))
    return found[0] if found else None


def _after_marker_line(body, advisor_at):
    """The offset just past the advisor-vet marker's own ``str.splitlines()`` line, the line the readers split.

    -1 when that line has no terminator (the marker is the last line); ``write-failed`` when no line holds the offset."""
    # axis: the slot starts after the marker's own str.splitlines() line, the line the readers split, so a marker line ended by a lone CR, U+2028 or any other splitlines separator cannot keep an old verdict line first in the region — see bite-proof record i2342_vet_slot_no_build_record.md
    line_start = 0
    for whole in body.splitlines(keepends=True):
        if line_start <= advisor_at < line_start + len(whole):
            return line_start + len(whole) if whole.splitlines()[0] != whole else -1
        line_start += len(whole)
    raise _Refusal("write-failed", "the advisor-vet marker offset is not on any line of the body")


def _check_verdict_reads_first(new_body, slot_text):
    """Refuse ``write-failed`` unless the first non-empty line of the composed body's advisor-vet region, read as
    ``stack_check.read_vet_verdict`` reads it, is the slot text's first non-empty line."""
    region, region_refusal = pr_body_regions.read_region(new_body, "advisor-vet")
    first_written = stack_check._first_nonempty_line(slot_text)
    first_read = stack_check._first_nonempty_line(region) if region is not None else None
    # axis: the region the merge train reads must open with the slot's own first line, else the write refuses write-failed and pushes nothing — see bite-proof record i2342_vet_slot_no_build_record.md
    if region_refusal is not None or region is None or first_read != first_written:
        raise _Refusal("write-failed", "the advisor-vet region's first line as the merge train reads it is %r, not the"
                       " new verdict line %r%s" % (first_read, first_written,
                                                   "; region read refused: %s" % region_refusal
                                                   if region_refusal is not None else ""))


def _compose_no_build_record(body, advisor_at, slot_text):
    """The new body of a no-build-record ``write``; a ``write-failed`` refusal when it would not hold.

    Marker present: the slot runs from the line after the marker to the end of the body. Marker absent: a
    ``## Advisor vet`` heading, the marker and the slot are appended."""
    marker = pr_body_regions.REGION_MARKERS["advisor-vet"]
    slot = slot_text.strip("\n")
    heading_at = None
    if advisor_at is None:
        prefix = body.rstrip("\r\n")
        new_body = prefix + "\n\n## Advisor vet\n" + marker + "\n\n" + slot + "\n"
        heading_at = len(prefix) + 2
        marker_at = heading_at + len("## Advisor vet\n")
        slot_at = marker_at + len(marker) + len("\n\n")
    else:
        line_end = _after_marker_line(body, advisor_at)
        if line_end >= 0:
            prefix = body[:line_end]
            new_body = prefix + "\n" + slot + "\n"
            slot_at = len(prefix) + len("\n")
        else:  # the marker is the last line, with no terminator after it
            prefix = body
            new_body = body + "\n\n" + slot + "\n"
            slot_at = len(body) + len("\n\n")
        marker_at = advisor_at
    # the offset at which the slot text begins is known from the composition above, never searched for
    if new_body[slot_at:slot_at + len(slot)] != slot:
        raise _Refusal("write-failed", "span invariant violated")
    if not new_body.startswith(prefix):
        raise _Refusal("write-failed", "span invariant violated")
    # axis: a slot text that carries a builder heading or the Build record wrapper makes the composed body builder-shaped, refused write-failed — see bite-proof record i2342_vet_slot_no_build_record.md
    if not no_build_record(new_body):
        raise _Refusal("write-failed", "the slot text carries a builder heading or build-record wrapper; the composed"
                       " body would read as a builder body")
    problem = _unrendered_slot(new_body, marker_at, heading_at, slot_at)
    # axis: a composed body whose marker line, verdict line or appended heading GitHub hides (or md_hidden is unsure of) refuses write-failed (G4) — see bite-proof record i2389_vet_slot_md_hidden.md
    if problem:
        raise _Refusal("write-failed", problem)
    if _find_live_standalone_markers(new_body, marker) != [marker_at]:
        raise _Refusal("write-failed", "composed body moved or shadowed slot markers")
    _check_verdict_reads_first(new_body, slot_text)
    return new_body


def _visibility_problem(rendering, marker_at, slot_at, heading_at=None):
    """Why the composed slot would not render, or None. The one visibility check of both write paths, on one
    ``md_hidden.scan`` (``rendering``): the line holding the advisor-vet marker (``marker_at``), the line holding the
    slot's first character (``slot_at``, the verdict line) and, when given, the appended ``## Advisor vet`` heading
    (``heading_at``) must each read ``VISIBLE``. ``hidden`` and ``unsure`` are both a problem; the sentence says which."""
    def why(state):
        return "the render could not be decided" if state == md_hidden.UNSURE else "GitHub hides it"

    # axis: the marker line must read VISIBLE (hidden or unsure refuses), decided by md_hidden — see bite-proof record i2389_vet_slot_md_hidden.md
    state = _line_state(rendering, marker_at)
    if state != md_hidden.VISIBLE:
        return "the advisor-vet marker line reads %s (%s), so the slot would not render" % (state, why(state))
    # axis: the verdict line (the slot's first line) must read VISIBLE (hidden or unsure refuses), decided by md_hidden — see bite-proof record i2389_vet_slot_md_hidden.md
    state = _line_state(rendering, slot_at)
    if state != md_hidden.VISIBLE:
        return "the slot's verdict line reads %s (%s), so the slot would not render" % (state, why(state))
    # axis: the appended Advisor vet heading must be a heading md_hidden reads VISIBLE — see bite-proof record i2389_vet_slot_md_hidden.md
    if heading_at is not None:
        state = {at: st for at, _text, st in rendering.headings}.get(heading_at)
        if state != md_hidden.VISIBLE:
            return ("the appended Advisor vet heading reads %s (%s), so the slot would not render"
                    % (state or "not a heading", why(state) if state else "GitHub does not render it as a heading"))
    return None


def _unrendered_slot(new_body, marker_at, heading_at, slot_at):
    """Why the composed slot of the bot path would not render, or None: one ``md_hidden.scan`` of ``new_body``, read by
    ``_visibility_problem``. ``slot_at`` is the offset in ``new_body`` at which the slot text begins."""
    return _visibility_problem(md_hidden.scan(new_body), marker_at, slot_at, heading_at)


def analyze_body(body):
    """Check the body read and its markers; return (advisor_offset, build_offset, followups)."""
    # axis: an empty or non-string body read refuses read-failed
    if not isinstance(body, str) or not body.strip():
        raise _Refusal("read-failed", "PR body is empty" if isinstance(body, str) else
                       "PR body is not a string")
    offsets = {}
    for name in ("advisor-vet", "build-record"):
        found = _find_live_standalone_markers(body, pr_body_regions.REGION_MARKERS[name])
        # axis: a slot marker present other than exactly once refuses markers-invalid
        if len(found) != 1:
            raise _Refusal("markers-invalid", "%s marker appears %d times" % (name, len(found)))
        offsets[name] = found[0]
    # axis: an advisor-vet marker not above the build-record marker refuses markers-invalid
    if offsets["advisor-vet"] >= offsets["build-record"]:
        raise _Refusal("markers-invalid", "advisor-vet marker is not above the build-record marker")
    followups = read_marker_list(body, FOLLOWUPS_MARKER_NAME, after=offsets["build-record"])
    # axis: the guard's span starts at the same offset the write's slot does, after the advisor-vet marker's own str.splitlines() line (the shared helper), never after the next "\n", so a foreign marker after a lone CR, U+2028 or form feed marker line refuses instead of being deleted — see bite-proof record i2342_vet_slot_no_build_record.md
    span_start = _after_marker_line(body, offsets["advisor-vet"])
    # Unreachable through this entry point: the -1 return and the helper's write-failed raise cannot happen here, because _find_live_standalone_markers returns a line start and the build-record marker sits on a later line, so the marker line always has a terminator — see bite-proof record i2342_vet_slot_no_build_record.md (H5a)
    if span_start < 0:
        raise _Refusal("markers-invalid", "the advisor-vet marker line has no terminator")
    for offset, line in _live_lines(body):
        stripped = line.strip()
        # axis: any other superheroes marker line inside the slot span refuses slot-span-foreign-content
        if span_start <= offset < offsets["build-record"] and stripped.startswith("<!-- superheroes:"):
            name = re.match(r"<!-- (superheroes:[^\s>]*)", stripped).group(1)
            raise _Refusal("slot-span-foreign-content",
                           "the slot span holds the %s marker; nothing goes between the advisor-vet"
                           " and build-record markers, so move it below the build-record marker" % name)
    return offsets["advisor-vet"], offsets["build-record"], followups


def _strip_containers(line):
    """Return ``(text, quote_depth)``: ``line`` without leading blockquote and list-item markers."""
    text = line.lstrip()
    depth = 0
    while True:
        # axis: blockquote and list markers are stripped in any order and interleaving
        if text.startswith(">"):
            depth += 1
            text = text[1:]
            # axis: one space after a blockquote marker belongs to the marker
            if text.startswith(" "):
                text = text[1:]
        else:
            stripped = _LIST_MARKER_RE.sub("", text, count=1)
            if stripped == text:
                return text, depth
            text = stripped
        text = text.lstrip()


def _strip_quotes(line, depth):
    """Drop up to ``depth`` leading blockquote markers from a fence content line."""
    for _ in range(depth):
        text = line.lstrip()
        # axis: a content line with fewer markers than the opener keeps what it has
        if not text.startswith(">"):
            break
        line = text[2:] if text[1:2] == " " else text[1:]
    return line


def _owner_shell_blocks(body):
    """Yield ``(opener_line, language, content_lines)`` for each fenced shell block.

    Lenient on purpose (``md_fence.scan`` is CommonMark-strict): a fence nested in a list or a
    blockquote at any indent still counts, and an unterminated fence runs to the end of the body.
    A line inside an HTML comment opens no fence."""
    fence = None
    in_comment = False
    # axis: the body is read as Markdown lines (md_fence.split_lines), so a fence opener after a U+2028 or other splitlines-only break opens no fence — see bite-proof record i2389_vet_slot_md_hidden.md
    for number, line in enumerate(_bare_lines(body), 1):
        text, depth = _strip_containers(line)
        # axis: a line with fewer blockquote markers than the opener ends a quoted fence, then is re-read
        if fence is not None and depth < fence["depth"]:
            if fence["language"] in SHELL_LANGUAGES:
                yield fence["line"], fence["language"], fence["lines"]
            fence = None
        if fence is not None:
            run = text.rstrip(" \t")
            # axis: only a same-character run at least as long as the opener's closes the fence
            if run and not run.strip(fence["char"]) and len(run) >= fence["size"]:
                if fence["language"] in SHELL_LANGUAGES:
                    yield fence["line"], fence["language"], fence["lines"]
                fence = None
            else:
                fence["lines"].append(_strip_quotes(line, fence["depth"]))
            continue
        # axis: a line inside an HTML comment opens no fence; the line holding --> ends the comment
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        opener = _FENCE_OPEN_RE.match(text)
        # axis: a backtick run with a backtick in its info string is inline code, not a fence
        if opener and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
            words = opener.group(2).split()
            language = words[0].lower().lstrip("{").lstrip(".").rstrip("}") if words else ""
            fence = {"line": number, "language": language, "char": opener.group(1)[0],
                     "size": len(opener.group(1)), "depth": depth, "lines": []}
            continue
        # axis: an HTML comment opener inside an inline-code span is prose, not a comment
        prose = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        at = prose.rfind("<!--")
        # axis: a <!-- with no --> after it on its line enters a comment; one closed on its line does not
        if at >= 0 and "-->" not in prose[at + 4:]:
            in_comment = True
    # axis: an unterminated shell fence runs to the end of the body and is still a block
    if fence is not None and fence["language"] in SHELL_LANGUAGES:
        yield fence["line"], fence["language"], fence["lines"]


def _code_part(line):
    """``line`` up to the first unquoted ``#`` that starts a shell comment."""
    quote = None
    i = 0
    while i < len(line):
        char = line[i]
        # axis: a backslash outside single quotes escapes the next character
        if char == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        # axis: an unquoted # at line start or after whitespace begins a comment
        elif char == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
        i += 1
    return line


def _calls_owner_tool(line):
    """The database tool (or ``security find-...-password``) ``line`` names, else None.

    A mention is enough: no command position, wrapper, quote or heredoc is judged. A shell comment is
    skipped unless it holds a ``$(`` or a backtick, which a pasted comment can run as a substitution."""
    code = _code_part(line)
    comment = line[len(code):]
    # axis: a comment holding a substitution opener is matched too; any other comment text is not
    text = line if "$(" in comment or "`" in comment else code
    for pattern in (_KEYCHAIN_RE, _DATABASE_TOOL_RE):
        found = pattern.search(text)
        if found:
            return " ".join(found.group(0).replace('"', "").replace("'", "").split())
    return None


def owner_command_blocks(body):
    """One ``{"line", "language", "tool"}`` per fenced shell block that names an owner-run tool."""
    found = []
    for number, language, lines in _owner_shell_blocks(body):
        joined = []
        carry = None
        for content in lines:
            # axis: a line ending in a backslash continues onto the next line, joined with a space
            # axis: a backslash ending a shell comment is not a continuation
            code = _code_part(content).rstrip()
            if code.endswith("\\"):
                carry = (carry + " " if carry else "") + code[:-1]
                continue
            joined.append((carry + " " if carry else "") + content)
            carry = None
        # axis: a trailing continuation with no next line is still matched
        if carry is not None:
            joined.append(carry)
        for content in joined:
            tool = _calls_owner_tool(content)
            if tool:
                found.append({"line": number, "language": language, "tool": tool})
                break
    return found


def check_handback(body):
    """The builder's handback read: ``analyze_body`` itself, so it agrees with ``write`` and ``check``;
    it also refuses a fenced shell block that names a database tool or a Keychain read."""
    try:
        ids = analyze_body(body)[2]
    except _Refusal as exc:
        detail = exc.detail
        # axis: a hyphenated follow-ups line where the followups marker belongs is named in the detail
        if detail.startswith("%s marker appears 0 times" % FOLLOWUPS_MARKER_NAME) and any(
                line.startswith("<!-- superheroes:follow-ups") for _o, line in _live_lines(body)):
            detail += ("; a hyphenated <!-- superheroes:follow-ups ... --> line is not it: write"
                       " <!-- superheroes:followups FU1 FU2 --> or <!-- superheroes:followups none -->")
        return _refusal(exc.reason, detail)
    blocks = owner_command_blocks(body)
    # axis: a fenced shell block that names a database tool or a Keychain read refuses owner-command-in-body
    if blocks:
        named = ["the fenced %s block opening at line %d names %s"
                 % (b["language"] or "no-language", b["line"], b["tool"]) for b in blocks]
        return _refusal("owner-command-in-body", "; ".join(named) + "; " + OWNER_COMMAND_ADVICE)
    return {"ok": True, "verb": "handback", "followups": ids or []}


def _handback_file(body_file):
    try:
        with open(body_file, encoding="utf-8") as handle:
            body = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        return _refusal("read-failed", "body file unreadable: %s" % exc)
    return check_handback(body)


def _claim_name(claim):
    return "%s (%s)" % (claim["id"], claim["title"]) if claim["title"] else claim["id"]


def _check_fixed_above(pr, repo, claims, run, membership_reader):
    """Refuse unless every claim's named PR is a member of this PR's own stack at a higher position (#2332). A stack that
    cannot be read refuses too: the disposition is then not accepted."""
    try:
        if membership_reader is not None:
            read = membership_reader(pr, repo)
        else:
            read = stack_check.read_membership(pr=pr, repo=repo, run=run or subprocess.run)
    except Exception as exc:  # a reader that raises is a read that failed
        # axis: a membership reader that raises refuses fixed-above-unverified, never passes
        raise _Refusal("fixed-above-unverified", "%s: the stack membership of PR %d could not be read (%s: %s); the"
                       " disposition is not accepted" % ("; ".join(_claim_name(c) for c in claims), pr,
                                                         type(exc).__name__, exc))
    reason = read.get("reason") if isinstance(read, dict) else None
    # axis: a read that succeeded in saying this PR is in no stack (not-linked) cannot have a higher layer: refuses
    # fixed-above-not-in-stack
    if isinstance(read, dict) and read.get("ok") is not True and reason == stack_check.REASON_NOT_LINKED:
        raise _Refusal("fixed-above-not-in-stack", "; ".join(
            "%s names #%d, but PR #%d is in no stack" % (_claim_name(c), c["layer"], pr) for c in claims))
    # axis: a read that is not an object (membership unknown) or did not succeed refuses fixed-above-unverified, never passes
    if not isinstance(read, dict) or read.get("ok") is not True:
        cause = ("%s: %s" % (reason, read.get("detail"))) if isinstance(read, dict) else "the read was not an object"
        raise _Refusal("fixed-above-unverified", "%s: the stack membership of PR %d could not be read (%s); the"
                       " disposition is not accepted" % ("; ".join(_claim_name(c) for c in claims), pr, cause))
    members = read.get("members")
    members = [m for m in members if isinstance(m, dict)] if isinstance(members, list) else []
    position = {m.get("number"): m.get("position") for m in members}
    mine = position.get(pr)
    # axis: a read that does not list this PR at an integer position is malformed: refuses fixed-above-unverified
    if not isinstance(mine, int) or isinstance(mine, bool):
        raise _Refusal("fixed-above-unverified", "%s: the stack membership read does not list PR %d at a position; the"
                       " disposition is not accepted" % ("; ".join(_claim_name(c) for c in claims), pr))
    failing = []
    for claim in claims:
        layer = position.get(claim["layer"])
        # axis: a named layer that is not a member of this PR's stack, or sits at or below it, is not a higher layer
        if not (isinstance(layer, int) and not isinstance(layer, bool) and layer > mine):
            why = ("is not a member of PR %d's stack" % pr if claim["layer"] not in position
                   else "is at or below PR %d in the stack" % pr)
            failing.append("%s names #%d, which %s" % (_claim_name(claim), claim["layer"], why))
    if failing:
        raise _Refusal("fixed-above-not-in-stack", "; ".join(failing))


def _latest_record(pr, repo, comments):
    rows = [{"id": c.get("id"), "author": c["user"]["login"], "body": c["body"], "url": c.get("html_url")}
            for c in comments]
    return review_record.read(pr, repo, readers={"list_comments": lambda _pr, _repo: rows})


def check_calibration_disclosures(pr, repo, body, comments):
    """Refuse while a calibration marker in a degradation bullet is contradicted by the latest review record among
    ``comments`` or names a row the record lacks, or while a degradation bullet mentions calibration outside the marker
    (``calibration_disclosure``, the rule's one home), or while that record cannot be read."""
    record = _latest_record(pr, repo, comments)
    try:
        found = calibration_disclosure.problems(record, body)
    except calibration_disclosure.Unreadable as exc:
        raise _Refusal("review-record-unreadable", "the latest review record on PR %d: %s" % (pr, exc))
    if found:
        raise _Refusal(found[0]["reason"], calibration_disclosure.describe(found, record.get("url")))


def check_leftovers(pr, repo, body, comments, run=None, membership_reader=None):
    """Refuse while the latest review record among ``comments`` leaves a finding for the owner that the body's What we're
    accepting does not name (``leftover_accepting``, the rule's one home), or while that record cannot be read. An
    acceptance that carries ``fixed-above #<PR> <commit>`` also refuses unless that PR is a higher member of this PR's own
    stack, or when the stack cannot be read (#2332); with no such acceptance the stack is never read."""
    record = _latest_record(pr, repo, comments)
    try:
        gaps = leftover_accepting.missing(record, body)
    except leftover_accepting.Unreadable as exc:
        # axis: a review record that is missing or cannot be read refuses review-record-unreadable, never passes
        raise _Refusal("review-record-unreadable", "the latest review record on PR %d: %s" % (pr, exc))
    # axis: a leftover What we're accepting does not name by id and title refuses leftover-not-accepted
    if gaps:
        raise _Refusal("leftover-not-accepted", leftover_accepting.describe(gaps))
    try:
        claims = leftover_accepting.fixed_above(record, body)
    except leftover_accepting.Unreadable as exc:
        raise _Refusal("review-record-unreadable", "the latest review record on PR %d: %s" % (pr, exc))
    # axis: with no fixed-above acceptance the stack is never read
    if claims:
        _check_fixed_above(pr, repo, claims, run, membership_reader)


def reads_ready(slot_text):
    """Whether the slot's verdict line (its first non-empty line) opens with a READY token of the canonical verdict
    form (``rubric/vet-verdict-form.json``, read through ``stack_check``). A form that cannot be read reads READY, so
    the leftover check runs rather than being skipped."""
    form, _error = stack_check._load_vet_verdict_form()
    # axis: an unreadable verdict form fails toward running the leftover check
    if form is None:
        return True
    first = next((line for line in slot_text.splitlines() if line.strip()), "")
    return any(first.startswith(token) for token, verdict in form[1] if verdict == stack_check.VERDICT_READY)


def check_slot_text(slot_text):
    if not isinstance(slot_text, str) or not slot_text.strip():
        raise _Refusal("write-failed", "slot text is empty")
    for line in slot_text.splitlines():
        if line.strip().startswith("<!-- superheroes:"):
            raise _Refusal("write-failed", "slot text carries a marker: %s" % line.strip())
    # axis: slot text carrying an HTML comment opener or closer anywhere refuses write-failed
    if "<!--" in slot_text or "-->" in slot_text:
        raise _Refusal("write-failed", "slot text carries an HTML comment opener or closer")


def _select_receipt(comments, advisor_login):
    best = None
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != advisor_login:
            continue
        first = comment["body"].lstrip("﻿ \t\r\n").splitlines()
        if first and first[0].rstrip() == RECEIPT_MARKER:
            if best is None or comment["created_at"] >= best["created_at"]:
                best = comment
    return best


def evaluate(verb, body, comments, slot_text=None, advisor_login=None):
    """The chokepoint: every check, then the result (with ``newBody`` for write)."""
    try:
        # axis: a body with no builder sign takes the no-build-record path on write and check — see bite-proof record i2342_vet_slot_no_build_record.md
        bare = no_build_record(body)
        if bare:
            advisor_at, ids = analyze_no_build_record(body), None
        else:
            # axis: the evaluate chokepoint refuses an emptied body on write before analyze_body — see bite-proof record i2323_vet_slot_emptied.md
            if verb == "write":
                check_not_emptied(body)
            advisor_at, build_at, ids = analyze_body(body)
            # axis: the evaluate chokepoint refuses builder text in the slot span on write, after analyze_body — see bite-proof record i2352_vet_slot_builder_text.md
            if verb == "write":
                check_span_owned(body, advisor_at, build_at)
        if verb == "write":
            check_slot_text(slot_text)
        if not isinstance(advisor_login, str) or not advisor_login.strip():
            raise _Refusal("read-failed", "advisor login is missing")
        receipt = _select_receipt(comments, advisor_login.strip())
        if receipt is None:
            if verb == "check" and ids is None:
                return {"ok": True, "verb": "check", "followups": [], "receipt": None,
                        "receiptPresent": False}
            raise _Refusal("receipt-missing", "no comment opens with the vet-receipt marker")
        disposed = read_marker_list(receipt["body"], DISPOSITIONS_MARKER_NAME)
        # axis: a none dispositions marker over a followups list refuses none-over-list
        if ids is not None and disposed is None:
            raise _Refusal("none-over-list", "receipt dispositions read none over %s" % " ".join(ids))
        missing = [i for i in (ids or []) if i not in (disposed or [])]
        # axis: a follow-up id with no disposition refuses followup-undispositioned
        if missing:
            raise _Refusal("followup-undispositioned", "%s: no disposition" % ", ".join(missing))
        unknown = [i for i in (disposed or []) if i not in (ids or [])]
        # axis: a disposition id the build record lacks refuses disposition-unknown
        if unknown:
            raise _Refusal("disposition-unknown", "%s: not in the followups marker" % ", ".join(unknown))
    except _Refusal as exc:
        return _refusal(exc.reason, exc.detail)
    result = {"ok": True, "verb": verb, "followups": ids or [],
              "receipt": receipt.get("html_url") or receipt.get("id")}
    if verb == "check":
        result["receiptPresent"] = True
        return result
    if bare:
        try:
            result["newBody"] = _compose_no_build_record(body, advisor_at, slot_text)
        except _Refusal as exc:
            return _refusal(exc.reason, exc.detail)
        return result
    try:
        # axis: the builder path starts the slot after the marker's own str.splitlines() line (the shared helper), never after the next "\n", so a lone CR or U+2028 marker line cannot keep an old verdict line first — see bite-proof record i2342_vet_slot_no_build_record.md
        a = _after_marker_line(body, advisor_at)
    except _Refusal as exc:
        return _refusal(exc.reason, exc.detail)
    if a < 0:  # a builder body's marker line is ended by the build-record marker that follows it
        return _refusal("write-failed", "the advisor-vet marker line has no terminator")
    # axis: the write's span ends at the build-record marker's own line start (build_at itself), never after the previous "\n", so old slot text on a line ended by a lone CR or U+2028 before the marker is replaced, not kept — see bite-proof record i2342_vet_slot_no_build_record.md
    b = build_at
    new_body = body[:a] + "\n" + slot_text.strip("\n") + "\n\n" + body[b:]
    tail = len(body) - b
    if new_body[:a] != body[:a] or new_body[len(new_body) - tail:] != body[b:]:
        return _refusal("write-failed", "span invariant violated")
    try:
        new_advisor_at, new_build_at, new_ids = analyze_body(new_body)
    except _Refusal as exc:
        return _refusal("write-failed", "composed body broke markers: %s" % exc.detail)
    if new_ids != ids or new_advisor_at != advisor_at or new_body[new_build_at:] != body[build_at:]:
        return _refusal("write-failed", "composed body moved or shadowed slot markers")
    # the composed body is body[:a] + "\n" + slot + ...: the slot text begins at a + 1, known from the composition
    # axis: the builder path refuses write-failed unless the marker line and the slot's first line both read VISIBLE on md_hidden.scan (G5, BRIEF-1) — see bite-proof record i2389_vet_slot_md_hidden.md
    problem = _visibility_problem(md_hidden.scan(new_body), new_advisor_at, a + 1)
    if problem:
        return _refusal("write-failed", problem)
    try:
        # axis: the builder path refuses write-failed unless the composed region's first line, as the merge train reads it, is the slot's — see bite-proof record i2342_vet_slot_no_build_record.md
        _check_verdict_reads_first(new_body, slot_text)
    except _Refusal as exc:
        return _refusal(exc.reason, exc.detail)
    try:
        # axis: the composed slot must itself read as the advisor's own, so a later write is never refused — see bite-proof record i2352_vet_slot_builder_text.md
        check_span_owned(new_body, new_advisor_at, new_build_at)
    except _Refusal as exc:
        return _refusal("write-failed", "the composed slot would not read as the advisor's own on the next write: %s"
                        % exc.detail)
    result["newBody"] = new_body
    return result


def _gh(run, argv, what, reason="read-failed"):
    """Run one gh call; a failure is ``reason`` with ``what`` leading the detail."""
    try:
        proc = run(argv, capture_output=True, text=True, timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise _Refusal(reason, "%s: gh call timed out" % what)
    except OSError as exc:
        raise _Refusal(reason, "%s: %s" % (what, exc))
    if proc.returncode != 0:
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise _Refusal(reason, "%s: exit %d %s" % (what, proc.returncode, out))
    return proc.stdout or ""


def _gh_json(run, argv, what):
    try:
        return json.loads(_gh(run, argv, what))
    except ValueError as exc:
        raise _Refusal("read-failed", "%s: bad JSON: %s" % (what, exc))


def _read_pr(run, pr, repo):
    """The one REST read of the PR: the payload, a dict."""
    payload = _gh_json(run, ["gh", "api", "repos/%s/pulls/%d" % (repo, pr)], "PR body")
    if not isinstance(payload, dict):
        raise _Refusal("read-failed", "PR body: body is not a string")
    return payload


def _body_of(payload):
    if "body" not in payload:
        raise _Refusal("read-failed", "PR body: body is not a string")
    body = payload["body"]
    # axis: a REST null body is an empty body, not a malformed one
    if body is None:
        return ""
    if not isinstance(body, str):
        raise _Refusal("read-failed", "PR body: body is not a string")
    return body


def _read_body(run, pr, repo):
    return _body_of(_read_pr(run, pr, repo))


def check_caught_up(run, repo, payload):
    """Refuse a ready marking of a stacked PR whose published head does not hold its lower branch's
    current head. None when the PR is caught up or is not stacked (its base is the default branch,
    and no further gh call is made). ``payload`` is the PR's REST payload."""
    def unreadable(detail):
        return _Refusal(REASON_STACK_LOWER_UNREADABLE, detail)

    base = payload.get("base") if isinstance(payload, dict) else None
    head = payload.get("head") if isinstance(payload, dict) else None
    base_repo = base.get("repo") if isinstance(base, dict) else None
    # axis: a PR payload lacking base, base.repo or head as objects refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
    if not (isinstance(base, dict) and isinstance(base_repo, dict) and isinstance(head, dict)):
        raise unreadable("the PR payload lacks base, base.repo or head as objects; its lower layer"
                         " cannot be read")
    base_ref = base.get("ref")
    default_branch = base_repo.get("default_branch")
    # axis: a base ref or default branch that is not a non-empty string refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
    if not (isinstance(base_ref, str) and base_ref.strip()
            and isinstance(default_branch, str) and default_branch.strip()):
        raise unreadable("the PR payload's base.ref or base.repo.default_branch is not a non-empty"
                         " string")
    head_sha = head.get("sha")
    # axis: a head sha that is not 40 hex characters refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
    if not (isinstance(head_sha, str) and _HEAD_SHA_RE.match(head_sha)):
        raise unreadable("the PR payload's head.sha is not 40 hex characters: %r" % (head_sha,))
    # axis: a PR on the default branch is not stacked: no refusal and no compare read — see bite-proof record c1l11e_wo_a_catch_up
    if base_ref == default_branch:
        return None
    what = "compare %s...%s" % (base_ref, head_sha[:12])
    argv = ["gh", "api", "repos/%s/compare/%s...%s" % (repo, urllib.parse.quote(base_ref, safe="/"),
                                                       head_sha)]
    # axis: a compare read that fails, times out, raises OSError or prints bad JSON refuses stack-lower-unreadable, original detail kept — see bite-proof record c1l11e_wo_a_catch_up
    try:
        compare = _gh_json(run, argv, what)
    except _Refusal as exc:
        raise unreadable(exc.detail)
    # axis: a compare read that is not an object refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
    if not isinstance(compare, dict):
        raise unreadable("%s: the compare read is not an object" % what)
    behind = compare.get("behind_by")
    # axis: a behind_by that is missing, not an int, a bool or negative refuses stack-lower-unreadable — see bite-proof record c1l11e_wo_a_catch_up
    if not isinstance(behind, int) or isinstance(behind, bool) or behind < 0:
        raise unreadable("%s: behind_by is not a count: %r" % (what, behind))
    # axis: a head behind its lower branch refuses stack-not-caught-up — see bite-proof record c1l11e_wo_a_catch_up
    if behind > 0:
        raise _Refusal(
            REASON_STACK_NOT_CAUGHT_UP,
            "the PR head %s is %d commit(s) behind its lower branch %s; catch the layer up: merge %s"
            " into the layer with a local --no-ff merge and push it, run the calibrated verify on"
            " the merged head, review the catch-up with a returning review-code session"
            " (rubric/native-stacks.md, How a stack stays current), then run handback again"
            % (head_sha[:12], behind, base_ref, base_ref))
    return None


def _read_comments(run, pr, repo):
    def fetch(endpoint):
        try:
            return _gh(run, ["gh", "api", endpoint], "comments")
        except _Refusal:
            return None
    comments = gh_pages.read(fetch, "repos/%s/issues/%d/comments" % (repo, pr))
    if comments is None:
        raise _Refusal("read-failed", "comments: a page could not be read")
    for c in comments:
        if not isinstance(c, dict):
            raise _Refusal("read-failed", "comments: a comment lacks body, created_at, or user.login")
        user = c.get("user")
        if not (isinstance(c, dict) and isinstance(c.get("body"), str)
                and isinstance(c.get("created_at"), str)
                and isinstance(user, dict) and isinstance(user.get("login"), str)):
            raise _Refusal("read-failed", "comments: a comment lacks body, created_at, or user.login")
    return comments


def _read_advisor_login(run):
    login = _gh(run, ["gh", "api", "user", "-q", ".login"], "advisor login").strip()
    if not login:
        raise _Refusal("read-failed", "advisor login: empty")
    return login


def _normalize(text):
    return text.replace("\r\n", "\n").rstrip()


def run_verb(verb, pr, repo, slot_file=None, run=None, body_file=None):
    if body_file is not None:
        if verb != "handback" or pr is not None or repo is not None or slot_file is not None:
            return _refusal("bad-argument", "--body-file goes with handback alone")
        return _handback_file(body_file)
    if not isinstance(pr, int) or isinstance(pr, bool) or pr < 1:
        return _refusal("bad-argument", "pr must be a positive integer")
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _refusal("bad-argument", "repo must be owner/name")
    if verb not in VERBS or (verb == "write") != (slot_file is not None):
        return _refusal("bad-argument", "write needs --slot-file; check and handback take none")
    try:
        return _run_verb(verb, pr, repo, slot_file, run or subprocess.run)
    except _Refusal as exc:
        return _refusal(exc.reason, exc.detail)


def _run_verb(verb, pr, repo, slot_file, run):
    if not shutil.which("gh"):
        raise _Refusal("read-failed", "gh not on PATH")
    payload = _read_pr(run, pr, repo)
    if verb == "handback":
        check_caught_up(run, repo, payload)
        body = _body_of(payload)
        result = check_handback(body)
        if result["ok"]:
            comments = _read_comments(run, pr, repo)
            check_leftovers(pr, repo, body, comments, run)
            # axis: a disclosed calibration degradation the record grades read refuses calibration-disclosure-contradicted — see bite-proof record i2364_calibration_disclosure
            check_calibration_disclosures(pr, repo, body, comments)
        return result
    body = _body_of(payload)
    # axis: a body with no builder sign takes the no-build-record path on write and check — see bite-proof record i2342_vet_slot_no_build_record.md
    if no_build_record(body):
        analyze_no_build_record(body)
    else:
        if verb == "write":
            check_not_emptied(body)
        advisor_at, build_at, _ids = analyze_body(body)
        # axis: the _run_verb chokepoint refuses builder text in the slot span before the slot file is read or any further gh call — see bite-proof record i2352_vet_slot_builder_text.md
        if verb == "write":
            check_span_owned(body, advisor_at, build_at)
    slot_text = None
    if verb == "write":
        try:
            with open(slot_file, encoding="utf-8") as handle:
                slot_text = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise _Refusal("write-failed", "slot file unreadable: %s" % exc)
        check_slot_text(slot_text)
    advisor_login = _read_advisor_login(run)
    comments = _read_comments(run, pr, repo)
    result = evaluate(verb, body, comments, slot_text, advisor_login=advisor_login)
    if not result["ok"] or verb == "check":
        return result
    if reads_ready(slot_text):
        # axis: the READY check reads the body the write will publish, never the old slot text it replaces
        check_leftovers(pr, repo, result["newBody"], comments, run)
    new_body = result.pop("newBody")
    if _read_body(run, pr, repo) != body:
        raise _Refusal("write-failed", "PR body changed between the read and the push")
    path = None
    pushed = "slot write already pushed"
    try:
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md",
                                             prefix="vet-slot-", delete=False) as handle:
                path = handle.name
                handle.write(new_body)
        except OSError as exc:
            raise _Refusal("write-failed", "edit: %s" % exc)
        try:  # once launched, a failed edit call is an unconfirmed write: read back
            _gh(run, ["gh", "pr", "edit", str(pr), "-R", repo, "--body-file", path], "edit",
                reason="write-unconfirmed")
        except _Refusal as exc:
            pushed = "slot edit call failed (%s)" % exc.detail
    finally:
        if path is not None and os.path.exists(path):
            os.unlink(path)
    try:
        readback = _read_body(run, pr, repo)
    except _Refusal as exc:
        raise _Refusal("write-unconfirmed", "%s; readback: %s" % (pushed, exc.detail))
    if _normalize(readback) != _normalize(new_body):
        raise _Refusal("write-unconfirmed", "%s; readback differs from the pushed body" % pushed)
    return result


def main(argv=None, run=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        parser = _Parser(prog="vet_slot", add_help=False)
        verbs = parser.add_subparsers(dest="verb")
        for name in VERBS:
            sub = verbs.add_parser(name, add_help=False)
            required = name != "handback"  # handback takes --pr/--repo or --body-file
            sub.add_argument("--pr", type=int, required=required)
            sub.add_argument("--repo", required=required)
            if name == "write":
                sub.add_argument("--slot-file", required=True)
            if name == "handback":
                sub.add_argument("--body-file")
        args = parser.parse_args(argv)
        if args.verb not in VERBS:
            raise SystemExit(2)
    except SystemExit:
        result = _refusal("bad-argument", "invalid command-line arguments")
    else:
        result = run_verb(args.verb, args.pr, args.repo, getattr(args, "slot_file", None), run=run,
                          body_file=getattr(args, "body_file", None))
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
