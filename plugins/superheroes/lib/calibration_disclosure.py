"""The one home of the calibration-disclosure rule (#2364): a PR body's ``### Disclosed degradations`` list never says a
review seat lacked its calibration (``core.md``, ``review-crew.md`` or ``CLAUDE.md`` stripped from, missing for, or
withheld from it) when the latest review record grades that seat's calibration ``read``. The record's
``calibrationRead`` is the measurement; the sanitized view's strip list is not.

One caller, no second copy of the rule: ``vet_slot.py handback --pr``. ``contradicted`` takes the latest record exactly
as ``review_record.py read --pr <n>`` returns it and the PR body; it returns the disclosures the record contradicts, and
raises ``Unreadable`` for a record it cannot read, which the caller reports as unreadable, never as a pass. A row with no
measured calibration (session-reported, not run, no ``calibrationRead``) is never contradicted: the check never refuses
on a fact the record does not hold."""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import pr_sheet  # noqa: E402
import review_record  # noqa: E402
import round_phases  # noqa: E402

REASON = "calibration-disclosure-contradicted"

FIX = ("Read each seat's calibrationRead in the review record and disclose a calibration degradation only for a seat"
       " graded not-read or unknown, or whose order named no calibration, naming that seat; a disclosure that names no"
       " seat covers every seat.")

_CORE, _CREW, _CLAUDE = "core", "review-crew", "CLAUDE.md"
_CLAUSES = re.compile(r"[.;](?=\s|$)|\b(?:but|while|whereas|although)\b", re.I)
_NOUNS = (
    (re.compile(r"\bcore\.md\b|\bcore calibration\b|\bthreat[- ]models?\b|\bcanonical patterns\b", re.I), (_CORE,)),
    (re.compile(r"\breview[- ]crew(?:\.md)?\b|\bfocus hints?\b|\breview notes\b", re.I), (_CREW,)),
    (re.compile(r"\bclaude\.md\b", re.I), (_CLAUDE,)),
)
_GENERIC = re.compile(r"\bcalibrations?\b", re.I)
# A lack term counts only when it describes a calibration noun: one that comes before the noun ("without core.md",
# "lacked review-crew.md") or one that follows it ("calibration was stripped"), with a short gap between them that
# crosses no comma, colon or semicolon and holds no verb of reading ("unavailable, so the reviewer used core.md").
_PRE_LACK = re.compile(
    r"\b(?:without|lack(?:s|ed|ing)?|missing|withh(?:e|o)ld(?:s|ing)?|stripped of|no|"
    r"(?:did not|didn't|never) (?:have|get|got|see|saw|receive|received|had)|not (?:given|handed|passed))\b", re.I)
_POST_LACK = re.compile(
    r"\b(?:strip(?:s|ped|ping)?|missing|withh(?:e|o)ld(?:s|ing)?|unavailable|not available|absent|removed|"
    r"(?:left|leaves|leaving) out|not (?:given|handed|passed))\b", re.I)
_GAP_WORDS = 8
_GAP_BREAK = re.compile(r"[,;:]|\b(?:read|reads|used|uses|opened|opens|loaded|saw|had|got|received)\b", re.I)
_ALIASES = {"premortem": ("failure-mode", "failure mode")}


class Unreadable(Exception):
    """The latest review record could not be read, so the rule cannot be checked."""


def _joins(gap):
    """Whether a lack term and a calibration noun ``gap`` apart describe one another: a parenthesis is dropped, and
    what is left is at most a few words with no clause break and no verb of reading."""
    gap = re.sub(r"\([^()]*\)", " ", gap)
    return len(gap.split()) <= _GAP_WORDS and not _GAP_BREAK.search(gap) and "(" not in gap and ")" not in gap


def _lacked(clause, noun):
    """Whether some lack term in ``clause`` describes a match of ``noun``."""
    for m in noun.finditer(clause):
        # axis: a lack term counts only when it describes the calibration noun, never when it merely shares the clause — see bite-proof record i2364_calibration_disclosure
        if any(_joins(clause[lack.end():m.start()]) for lack in _PRE_LACK.finditer(clause, 0, m.start())) \
                or any(_joins(clause[m.end():lack.start()]) for lack in _POST_LACK.finditer(clause, m.end())):
            return True
    return False


def _claims(text):
    """Each clause of one degradation's text that claims a seat lacked calibration, with the labels that clause names:
    [(clause, labels)], [] for none. The labels stay with their own clause, so one clause's files never scope
    another's seats."""
    out = []
    for clause in _CLAUSES.split(text):
        specific = [label for noun, named in _NOUNS if _lacked(clause, noun) for label in named]
        if specific or _lacked(clause, _GENERIC):
            out.append((clause, list(dict.fromkeys(specific)) or [_CORE, _CREW, _CLAUDE]))
    return out


def _contradicted_row(row, labels):
    """Whether the record measured this row reading every one of ``labels`` it holds an entry for."""
    # axis: only an engine-record row whose calibrationRead is a non-empty list with every entry for the claimed labels read is contradicted; unmeasured, session-reported, not-run, none-named, not-read and unknown rows never are — see bite-proof record i2364_calibration_disclosure
    if row.get("ran") != "engine-record":
        return False
    files = review_record._valid_calibration(row.get("calibrationRead"))
    held = [e for e in files or [] if e["label"] in labels]
    return bool(held) and all(e["read"] == "read" for e in held)


def _terms(rows):
    """The seat terms for each level, most specific first: a list per level of (term, rows named by it)."""
    levels = [{}, {}, {}, {}, {}]
    for row in rows:
        name = row.get("name")
        if not isinstance(name, str):
            continue
        base = review_record._seat_round(name)[0]
        stem = next((k for k in review_record._STEM_ROLE if base.startswith(k)), None)
        seat = base[len(stem):] if stem else base
        lens = round_phases.seat_lens(seat)
        word = review_record._PANEL_LENS.get(lens)
        named = [(0, name), (1, base)]
        if not stem:
            named += [(2, seat), (3, lens)] + ([(4, word)] + [(4, a) for a in _ALIASES.get(word, ())] if word else [])
        for level, term in named:
            if isinstance(term, str) and term:
                levels[level].setdefault(term.lower(), []).append(row)
    return levels


def _mentions(rows, text):
    """The row groups ``text`` names, most specific term first; each matched span is blanked before the next term, so
    an explicit target never widens through its own alias."""
    found = []
    for level in _terms(rows):
        for term in sorted(level, key=len, reverse=True):
            pattern = re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(term), re.I)
            if pattern.search(text):
                found.append(level[term])
                # axis: a matched span is blanked so a less specific term cannot match inside it and widen the target — see bite-proof record i2364_calibration_disclosure
                text = pattern.sub(lambda m: " " * len(m.group(0)), text)
    return found


def _hit_rows(rows, clause, rest, labels):
    """The ran rows one claim clause contradicts. Its seats are the ones the clause names; a clause that names none
    takes the seats the bullet's other, non-claim clauses (``rest``) name, and failing that it covers every seat."""
    ran = [r for r in rows if r.get("ran") != "not-run"]
    # axis: each claim clause is checked with its own seats and its own files, never with another claim clause's — see bite-proof record i2364_calibration_disclosure
    mentions = _mentions(rows, clause) or _mentions(rows, rest)
    if not mentions:
        # axis: a claim that names no seat covers every seat, so any contradicted ran row is a hit — see bite-proof record i2364_calibration_disclosure
        return [r for r in ran if _contradicted_row(r, labels)]
    hit = []
    for group in mentions:
        targets = [r for r in group if r.get("ran") != "not-run"]
        if targets and all(_contradicted_row(r, labels) for r in targets):
            hit.extend(targets)
    return hit


def contradicted(record, body):
    """The calibration disclosures in ``body``'s degradations the latest record contradicts, as [{"degradation", "seats":
    [{"name", "line"}]}] in body order ([] when none). ``record`` is ``review_record.read``'s result; Unreadable when it
    cannot be read, even when the body discloses nothing about calibration."""
    # axis: a read that did not succeed (missing, unreadable, gh failed) is unreadable, never a pass — see bite-proof record i2364_calibration_disclosure
    if not isinstance(record, dict) or record.get("ok") is not True:
        detail = record.get("detail") or record.get("reason") if isinstance(record, dict) else None
        raise Unreadable(detail or "the review record read did not succeed")
    claimed = []
    for _label, text in pr_sheet.degradations_listed(body):
        claims = _claims(text)
        if claims:
            claimed.append((text, claims))
    if not claimed:
        return []
    rows = record.get("reviewers")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise Unreadable("the record's reviewers list is missing or malformed")
    out = []
    for text, claims in claimed:
        claim_clauses = {clause for clause, _labels in claims}
        rest = " ".join(c for c in _CLAUSES.split(text) if c not in claim_clauses)
        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, clause, rest, labels)}
        seats, seen = [], set()
        for row in rows:
            if id(row) in hit and str(row.get("name")) not in seen:
                seen.add(str(row.get("name")))
                seats.append({"name": row.get("name"),
                              "line": "%s: %s" % (row.get("name"), review_record._calibration_words(row))})
        if seats:
            out.append({"degradation": text, "seats": seats})
    return out


def describe(hits, record_url):
    """The refusal detail naming each contradicted disclosure with the record's line for each seat it names."""
    where = record_url if isinstance(record_url, str) and record_url else "the latest review record"
    parts = ["Disclosed degradation %r contradicts %s: %s" % (h["degradation"][:200], where,
                                                             "; ".join(s["line"] for s in h["seats"])) for h in hits]
    return "; ".join(parts) + ". " + FIX
