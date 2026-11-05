"""The one home of the calibration-disclosure rule (#2364): a PR body's ``### Disclosed degradations`` list never says a
review seat lacked its calibration (``core.md``, ``review-crew.md`` or ``CLAUDE.md`` stripped from, missing for, or
withheld from it) when the latest review record grades that seat's calibration ``read``. The record's
``calibrationRead`` is the measurement; the sanitized view's strip list is not.

The claim test is simple on purpose: a clause that names a calibration file or calibration and holds any negation or
removal word is a claim, whatever the word is about, after Markdown emphasis and typographic apostrophes are normalised. A truthful clause that mixes an unrelated lack with a calibration
mention is refused, and the refusal tells the builder to put the unrelated lack in its own bullet or sentence.

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
       " graded not-read or unknown, or whose order named no calibration, naming that seat; a disclosure that does not"
       " name a seat in full covers every seat. Put an unrelated lack (a browser, a tool, a runner) in its own bullet or"
       " sentence, apart from any mention of calibration.")
_LENS_WORD_HINT = ('A lens word such as "test" or "code" does not name a seat; name the seat in full (for example'
                   ' "test-role (round 1)") to point a claim at one seat.')

_CORE, _CREW, _CLAUDE = "core", "review-crew", "CLAUDE.md"
_CLAUSES = re.compile(r"[.;](?=\s|$)|\b(?:but|while|whereas|although)\b", re.I)
_NOUNS = (
    (re.compile(r"\bcore\.md\b|\bcore calibration\b|\bthreat[- ]models?\b|\bcanonical patterns\b", re.I), (_CORE,)),
    (re.compile(r"\breview[- ]crew(?:\.md)?\b|\bfocus hints?\b|\breview notes\b", re.I), (_CREW,)),
    (re.compile(r"\bclaude\.md\b", re.I), (_CLAUDE,)),
)
_GENERIC = re.compile(
    r"\b(?:un)?calibrat(?:e|es|ed|ing|ion|ions)\b|\bproject notes\b|\bconventions file\b|\binstructions file\b", re.I)
# A clause that names a calibration file or calibration and holds any negation or removal word is a claim, whatever the
# word is about. Nothing else about the clause is judged. The trade is deliberate: a truthful clause that mixes an
# unrelated lack with a calibration mention is refused, and an unrelated lack belongs in its own bullet or sentence.
_LACK = re.compile(
    r"\b(?:not|never|no|none|nothing|zero|cannot|without|lack(?:s|ed|ing)?|missing|strip(?:s|ped|ping)?(?: of)?|"
    r"remov(?:e|es|ed|ing|al)|withh(?:e|o)ld(?:s|ing)?|withheld|(?:left|leaves|leaving|leave) out|"
    r"exclud(?:e|es|ed|ing)|omit(?:s|ted|ting)?|omission|drop(?:s|ped|ping)?|delet(?:e|es|ed|ing)|"
    r"hid(?:e|es|den|ing)?|den(?:y|ies|ied|ying|ial)|inaccessible|unavailable|absent|gone|unread|"
    r"uncalibrat(?:e|es|ed|ing|ion|ions))\b|(?<=[a-z])n't\b", re.I)
# Calibration mentions that are never a claim: the project's show-it surface declaration (the doctrine's own required
# disclosure) and "calibrated" as a modifier before verify, model or command, or in "the calibrated <model identifier>"
# (a token that starts with a letter and holds a digit).
_EXEMPT = re.compile(
    r"\b(?:core\.md|(?:the\s+)?(?:project'?s\s+)?calibration)\s+(?:has|declares|with)\s+no\s+(?:#+\s*)?show-it surface\b"
    r"|\bshow-it surface\b|\bcalibrated[\s-]+(?:verify|model|command)s?\b|\bthe\s+calibrated\s+[a-z]\S*\d\S*", re.I)
_ALIASES = {"premortem": ("failure-mode", "failure mode")}
# Markdown emphasis characters become spaces and typographic apostrophes and the no-break space become their plain
# forms, so formatting cannot hide a word from the patterns above.
_FORMATTING = str.maketrans({"_": " ", "*": " ", "~": " ", "`": " ", "‘": "'", "’": "'", " ": " "})


class Unreadable(Exception):
    """The latest review record could not be read, so the rule cannot be checked."""


def _normalise(text):
    """``text`` with Markdown emphasis characters (underscore, asterisk, tilde, backtick) as spaces, curly apostrophes as
    ``'`` and the no-break space as a space, then every run of whitespace (newlines included) as one space. The one
    normal form of the degradation text and of every seat term."""
    # axis: formatting (emphasis characters, curly apostrophes, the no-break space) never hides a claim word or a calibration noun from the patterns, and whitespace runs are collapsed so the body and the seat terms share one normal form — see bite-proof record i2364_calibration_disclosure
    return re.sub(r"\s+", " ", text.translate(_FORMATTING))


def _claims(text):
    """Each clause of one degradation's text that claims a seat lacked calibration, with the labels that clause names:
    [(clause, labels)], [] for none. The labels stay with their own clause, so one clause's files never scope
    another's seats."""
    out = []
    for clause in _CLAUSES.split(text):
        # axis: a doctrine-prescribed show-it disclosure or a stock "calibrated verify/model/command" phrase is masked before the claim test, and a real calibration claim beside it still counts — see bite-proof record i2364_calibration_disclosure
        masked = _EXEMPT.sub(" ", clause)
        specific = [label for noun, named in _NOUNS if noun.search(masked) for label in named]
        # axis: a clause that names calibration and holds any negation or removal word is a claim, with no judgment of which subject the word belongs to — see bite-proof record i2364_calibration_disclosure
        if (specific or _GENERIC.search(masked)) and _LACK.search(masked):
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
                # axis: seat terms are normalised by the same function as the degradation text, so formatting never breaks a full-name match — see bite-proof record i2364_calibration_disclosure
                key = _normalise(term).strip().lower()
                if key:
                    levels[level].setdefault(key, []).append(row)
    return levels


# The first four levels of ``_terms`` (full row name, name without round, seat key, lens name) name a seat. The fifth
# (short lens words such as "test" and "code", and their aliases) never narrows a claim.
_NARROWING_LEVELS = 4


def _edge(term):
    """The pattern that finds ``term`` as a whole token (no word character or hyphen beside it)."""
    return re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(term), re.I)


def _mentions(rows, text, levels):
    """The row groups ``text`` names by the first ``levels`` levels of ``_terms``, most specific term first; each matched
    span is blanked before the next term, so an explicit target never widens through its own alias."""
    found = []
    for level in _terms(rows)[:levels]:
        for term in sorted(level, key=len, reverse=True):
            pattern = _edge(term)
            if pattern.search(text):
                found.append(level[term])
                # axis: a matched span is blanked so a less specific term cannot match inside it and widen the target — see bite-proof record i2364_calibration_disclosure
                text = pattern.sub(lambda m: " " * len(m.group(0)), text)
    return found


def _hit_rows(rows, clause, labels):
    """The ran rows one claim clause contradicts. Its seats are the ones the clause names in full; a clause that names
    none (a lens word such as "test" alone names none) covers every seat that ran."""
    ran = [r for r in rows if r.get("ran") != "not-run"]
    # axis: each claim clause is checked with its own seats and its own files, never with another claim clause's — see bite-proof record i2364_calibration_disclosure
    # axis: a claim clause narrows only to a seat named in full; a lens word alone never narrows it — see bite-proof record i2364_calibration_disclosure
    mentions = _mentions(rows, clause, _NARROWING_LEVELS)
    if not mentions:
        # axis: a claim that names no seat covers every seat, so any contradicted ran row is a hit — see bite-proof record i2364_calibration_disclosure
        return [r for r in ran if _contradicted_row(r, labels)]
    hit = []
    for group in mentions:
        targets = [r for r in group if r.get("ran") != "not-run"]
        if targets and all(_contradicted_row(r, labels) for r in targets):
            hit.extend(targets)
    return hit


def _lens_word_only(rows, normal, claims):
    """Whether the bullet holds a short lens word (a level-4 term) while none of its claim clauses names a seat in full."""
    short = _terms(rows)[_NARROWING_LEVELS:]
    if not any(_edge(term).search(normal) for level in short for term in level):
        return False
    return not any(_mentions(rows, clause, _NARROWING_LEVELS) for clause, _labels in claims)


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
        normal = _normalise(text)
        claims = _claims(normal)
        if claims:
            claimed.append((text, normal, claims))
    if not claimed:
        return []
    rows = record.get("reviewers")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise Unreadable("the record's reviewers list is missing or malformed")
    out = []
    for text, normal, claims in claimed:
        hit = {id(r) for clause, labels in claims for r in _hit_rows(rows, clause, labels)}
        seats, seen = [], set()
        for row in rows:
            if id(row) in hit and str(row.get("name")) not in seen:
                seen.add(str(row.get("name")))
                seats.append({"name": row.get("name"),
                              "line": "%s: %s" % (row.get("name"), review_record._calibration_words(row))})
        if seats:
            found = {"degradation": text, "seats": seats}
            if _lens_word_only(rows, normal, claims):
                found["lensWordOnly"] = True
            out.append(found)
    return out


def describe(hits, record_url):
    """The refusal detail naming each contradicted disclosure with the record's line for each seat it names."""
    where = record_url if isinstance(record_url, str) and record_url else "the latest review record"
    text = ""
    for h in hits:
        part = "Disclosed degradation %r contradicts %s: %s" % (h["degradation"][:200], where,
                                                                "; ".join(s["line"] for s in h["seats"]))
        if h.get("lensWordOnly"):
            part += ". " + _LENS_WORD_HINT
        text += (("" if not text else " " if text.endswith(".") else "; ") + part)
    return text + ("" if text.endswith(".") else ".") + " " + FIX
