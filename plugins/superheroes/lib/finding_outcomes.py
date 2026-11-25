"""The one home of the outcome rules for a review finding.

Every finding ends with exactly one outcome, spelled once in review_findings_schema.OUTCOMES.
This module is the only place that decides four things: whether a finding states a
consequence, how merged findings combine their consequence, whether a cited owner decision is
on record, and the outcome of a finding the review left unfixed.

A finding that is neither fixed nor shown wrong, and whose only consequence is code quality,
is craft, wherever in the project it sits. Any other consequence is real. An unfixed finding
with a real consequence is left for the owner, unless a decision on record names it, in which
case it is decided by a named ruling. A decision is on record only when it is an active Canon
entry, a recorded residual, a settled saved sheet answer for the pull request, or an owner ruling
whose pointer resolves: a readable comment in the pull request's own repository, at the exact
permalink, that is a standard chat-ruling record whose quoted block holds the owner's words (its
author is not checked, since every session posts as the owner). Two more recorded decisions use the
same pointer: a scope ruling (an out-of-scope ruling) and the advisor's bound (a prose-contract
definition of done). Each resolves through a chat-ruling record that holds its words, or through a vet
receipt on this pull request whose marker line names the finding's key (scope ruling) or states the
rounds (bound) with the words on the line above; the bound also needs the review's round count to be
at least the number it states. Severity never decides an outcome, except that a Critical is never
settled by a scope ruling or the advisor's bound.

The rules are pure: they read no file, run no git or subprocess and touch no network. Callers
pass text and dicts in. The one reader is decision_sources, which gathers the Canon and residual
text the rules are given. Anything missing or malformed fails closed, toward the owner.
"""
import re

import canon
import review_findings_schema
import session_contract  # no cycle: session_contract's imports never reach this module

OWNER_RULING = "owner-ruling"
SCOPE_RULING = "scope-ruling"
ADVISOR_BOUND = "advisor-bound"
# The kinds whose ref is a comment link and the words: each is read from the cited comment at write time.
LINKED_KINDS = (OWNER_RULING, SCOPE_RULING, ADVISOR_BOUND)
DECISION_KINDS = ("canon", "residual", "sheet-answer", OWNER_RULING, SCOPE_RULING, ADVISOR_BOUND)
# By value, not imported from vet_slot: a test asserts the two are equal.
VET_RECEIPT_MARKER = "<!-- superheroes:vet-receipt -->"
# Each is matched against one whole line, stripped; the scope key runs to the closing " -->" like the cap-choice marker's.
_SCOPE_MARKER = re.compile(r"<!-- superheroes:scope-ruling key=(.+) -->")
_BOUND_MARKER = re.compile(r"<!-- superheroes:advisor-bound rounds=([1-9][0-9]*) -->")
_ROUND_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_ROUNDS_STATED = re.compile(r"\b([1-9][0-9]*|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:review\s+)?rounds?\b", re.IGNORECASE)
_RECEIPT_WORDS_MIN = 12
# A pull request's comment is an issue comment on the same number; GitHub links it under /pull/, so both forms name it.
_COMMENT_PERMALINK = re.compile(r"https://github\.com/([^/\s#?]+)/([^/\s#?]+)/(?:issues|pull)/([0-9]+)#issuecomment-([0-9]+)")


RESTS_ON_RULING_FIELD = "restsOnRuling"
# fail-safe: any ruling/rulings/ruled word, an accepted/supplied/standing/conservative/owner's/advisor's rule, or a scope row.
# A bare "out of scope" and "not in changed material" are code-scope refutations the verifier order permits: neither matches
_RULING_PHRASE = re.compile(
    r"\b(?:rulings?|ruled|scope[\s-]+rows?"
    r"|(?:accepted|supplied|standing|conservative|owner(?:['’]s)?|advisor(?:['’]s)?)(?:\s+[\w'’-]+){0,2}\s+rules?)\b",
    re.IGNORECASE)
_QUOTED = re.compile(r'"([^"]*)"|“([^”]*)”|`([^`]*)`')
_QUOTE_MIN = 12


def _whole_key(key, text):
    """True when ``key`` is in ``text`` and is neither the start nor the end of a longer key (`…@L1` is not found inside
    `…@L12`, `a.py::…` is not found inside `src/a.py::…`, and `K` is not found inside a minted `K#<hash>`)."""
    # axis: a key counts only with a boundary on both sides, so a shorter path's ruling is never read inside a longer path or a hash-suffixed key — see bite-proof record wo1_scope_ruling_2478
    return re.search(r"(?<![A-Za-z0-9_@/.:-])" + re.escape(key) + r"(?![A-Za-z0-9_@/#]|[-.:][A-Za-z0-9_])", text) is not None


def _quoted_ruling_keys(text, ruling_reasons):
    """The keys of the rulings whose reason holds a quoted span (at least `_QUOTE_MIN` characters) of ``text``."""
    if not isinstance(ruling_reasons, dict):
        return set()
    reasons = {k: " ".join(v.split()) for k, v in ruling_reasons.items() if isinstance(k, str) and k.strip() and isinstance(v, str)}
    spans = {" ".join(s.split()) for m in _QUOTED.finditer(text) for s in m.groups() if s}
    return {k for k, v in reasons.items() for s in spans if len(s) >= _QUOTE_MIN and s in v}


def ruling_rest(text, ruling_keys=(), ruling_reasons=None):
    """None when ``text`` does not rest on a scope ruling, else {"findingKey": <key or None>}. A key (one of ``ruling_keys``,
    non-blank strings) appearing whole in the text names its ruling, and only when no quoted span points at a different ruling.
    A quoted span of the text (at least `_QUOTE_MIN` characters) that sits in a ruling's reason (``ruling_reasons``: key to
    reason) marks the text as resting on a ruling but never names one: it gives {"findingKey": None}, as do two whole keys and
    the ruling wording alone."""
    # axis: a verifier reason that names exactly one standing ruling's key whole rests on that ruling, unless a quoted span points at another — see bite-proof record wo1_scope_ruling_2478
    if not isinstance(text, str):
        return None
    keys = ruling_keys if isinstance(ruling_keys, (list, tuple, set, frozenset)) else ()
    named = {k for k in keys if isinstance(k, str) and k.strip() and _whole_key(k, text)}
    # axis: a quoted span that sits in a ruling's reason marks the text as resting on a ruling but never names one — see bite-proof record wo1_scope_ruling_2478 (E15)
    quoted = _quoted_ruling_keys(text, ruling_reasons)
    if len(named) == 1 and not quoted - named:
        return {"findingKey": next(iter(named))}
    # axis: a verifier reason that speaks of a standing/out-of-scope ruling rests on a ruling even with no key — see bite-proof record wo1_scope_ruling_2478
    if named or quoted or _RULING_PHRASE.search(text):
        return {"findingKey": None}
    return None


def rests_on_ruling(grade, reason=None):
    """True when ``grade`` is a wrong grade resting on a scope ruling: it carries a `restsOnRuling` dict, or (a row
    written before the mark) its reason, or ``reason``, speaks of a ruling. Never raises."""
    # axis: only a wrong grade can rest on a ruling, and a marked one always does — see bite-proof record wo1_scope_ruling_2478
    if not isinstance(grade, dict) or grade.get("verdict") != "wrong":
        return False
    if isinstance(grade.get(RESTS_ON_RULING_FIELD), dict):
        return True
    return ruling_rest(grade.get("reason")) is not None or ruling_rest(reason) is not None


def counted_verdict(grade):
    """The verdict a repeat's grade counts for: None for a wrong grade resting on a scope ruling (no code refutation),
    else the grade's own verdict (None for a non-dict). The one reader every repeat site uses."""
    # axis: a ruling-resting wrong grade counts as no verdict at every repeat reader — see bite-proof record wo1_scope_ruling_2478
    if rests_on_ruling(grade):
        return None
    return grade.get("verdict") if isinstance(grade, dict) else None


def has_stated_consequence(finding):
    """True only when finding is a dict whose consequence is a string with visible content."""
    if not isinstance(finding, dict):
        return False
    consequence = finding.get(review_findings_schema.CONSEQUENCE_KEY)
    return isinstance(consequence, str) and consequence.strip() != ""


def merged_consequence(members):
    """Combine the consequence of merged findings into (text or None, kind or None).

    The kind is code-quality only when every member says so, real when any member says real,
    and None otherwise; it never depends on member order. The text is the distinct stripped
    non-empty consequences in member order joined by a blank line, or None when there are none.
    """
    dicts = [m for m in members if isinstance(m, dict)] if isinstance(members, (list, tuple)) else []
    kinds = [m.get(review_findings_schema.CONSEQUENCE_KIND_KEY) for m in dicts]
    if review_findings_schema.REAL in kinds:
        kind = review_findings_schema.REAL
    elif kinds and all(k == review_findings_schema.CODE_QUALITY for k in kinds):
        kind = review_findings_schema.CODE_QUALITY
    else:
        kind = None
    texts = []
    for member in dicts:
        if has_stated_consequence(member):
            text = member[review_findings_schema.CONSEQUENCE_KEY].strip()
            if text not in texts:
                texts.append(text)
    return ("\n\n".join(texts) if texts else None), kind


def canon_decides(canon_text, entry_id):
    """True only when canon_text holds exactly one distinct complete entry with this id and no
    complete entry supersedes it; two different entries sharing an id resolve for no reader."""
    if not isinstance(canon_text, str) or not isinstance(entry_id, str) or entry_id == "":
        return False
    held = set()
    for line in canon_text.splitlines():
        if not canon._entry_shape_ok(line):
            continue
        if canon.ids_in(line) == {entry_id}:
            held.add(line)
        if (canon.entry_fields(line) or {}).get("supersedes") == entry_id:
            return False
    return len(held) == 1


def _squash(text):
    """text with every run of whitespace collapsed to one space and the ends stripped."""
    return " ".join(text.split())


def residual_decides(residual_text, ref):
    """True only when the whitespace-normalised ref occurs in the whitespace-normalised residual text."""
    if not isinstance(residual_text, str) or not isinstance(ref, str) or ref.strip() == "":
        return False
    return _squash(ref) in _squash(residual_text)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _answer_fits_sheet_schema(doc):
    """True only when doc fits the sheet schema's own answer definition (theme/sheet.schema.json $defs.answer),
    checked by sheet_prose's reader of that schema; any failure to read or check it is a misfit."""
    try:
        import json
        import sheet_prose
        with open(sheet_prose.SCHEMA, encoding="utf-8") as handle:
            defs = json.load(handle)["$defs"]
        return not sheet_prose._validate(defs["answer"], doc, "", defs)
    except Exception:
        return False


def sheet_answer_decides(answers, ref, pr):
    """True only when the cited card of this pull request holds a settled aligned or option answer. An aligned
    answer counts only while the published card (answers["cards"][card]["options"]) is known to offer no options."""
    if not isinstance(answers, dict) or not isinstance(ref, dict):
        return False
    if not (_is_int(pr) and _is_int(ref.get("pr")) and ref["pr"] == pr):
        return False
    card = ref.get("card")
    cards = answers.get("answers")
    if not isinstance(card, str) or not isinstance(cards, dict):
        return False
    doc = cards.get(card)
    if not isinstance(doc, dict):
        return False
    if not _answer_fits_sheet_schema(doc):
        return False
    answer = doc.get("answer")
    published = answers.get("cards")
    published = published.get(card) if isinstance(published, dict) else None
    offered = published.get("options") if isinstance(published, dict) else None
    if answer == "aligned":
        return offered == []
    option_id = doc.get("optionId")
    # an option answer counts only while the published card still offers that option
    return answer == "option" and isinstance(option_id, str) and option_id.strip() != "" and isinstance(offered, list) \
        and any((o.get("id") if isinstance(o, dict) else o) == option_id for o in offered)


def _sheet_ref_text(ref):
    if isinstance(ref, dict):
        return "pr %s card %s" % (ref.get("pr"), ref.get("card"))
    return str(ref)


def decided_by_well_formed(decided_by):
    """True only for {"kind": <DECISION_KINDS>, "ref": ...} with nothing else: ref is a non-blank
    string for canon and residual, {"pr": int, "card": non-blank string} for a sheet answer, and
    {"url": non-blank string, "words": non-blank string} for an owner ruling, a scope ruling and an advisor's bound."""
    if not isinstance(decided_by, dict) or set(decided_by) != {"kind", "ref"}:
        return False
    kind, ref = decided_by["kind"], decided_by["ref"]
    if kind not in DECISION_KINDS:
        return False
    if kind == "sheet-answer":
        return (isinstance(ref, dict) and set(ref) == {"pr", "card"} and _is_int(ref["pr"])
                and isinstance(ref["card"], str) and ref["card"].strip() != "")
    if kind in LINKED_KINDS:
        return isinstance(ref, dict) and set(ref) == {"url", "words"} and all(
            isinstance(ref[k], str) and ref[k].strip() != "" for k in ("url", "words"))
    return isinstance(ref, str) and ref.strip() != ""


def comment_permalink(url, repo):
    """The comment a ruling's link points at, as (owner, repo, issue number, comment id), or the reason it cannot be one.

    The link must be a comment permalink (leg L1), `/issues/<n>#issuecomment-<id>` or the `/pull/<n>#issuecomment-<id>`
    form a pull request's comment takes (a vet receipt's link, or a ruling recorded on a pull request), in the pull
    request's own repository, compared case-insensitively (leg L2). Returns (parts, None) or (None, why). Never raises."""
    # axis: the link must be a comment permalink — see bite-proof record wo_a_1958_owner_ruling
    # axis: a pull request comment's /pull/ link names the same comment and is accepted for every linked kind — see bite-proof record i2532_scope_bound (E-pull-link)
    found = _COMMENT_PERMALINK.fullmatch(url) if isinstance(url, str) else None
    if found is None:
        return None, WHY_NOT_A_PERMALINK
    owner, name, number, comment = found.groups()
    # axis: the link must be in the pull request's own repository — see bite-proof record wo_a_1958_owner_ruling
    if not (isinstance(repo, str) and repo.lower() == f"{owner}/{name}".lower()):
        return None, WHY_ANOTHER_REPOSITORY
    return (owner, name, number, int(comment)), None


def _linked_comment(ref, sources):
    """The comment a linked kind's ref points at, as ((url, words, issue number, body), None), or (None, why).

    The comment legs every linked kind shares: the ref names a link and words, the link is a comment permalink in the
    pull request's own repository, and the comment read (sources["ownerRulings"][url]) is that comment on that issue."""
    url, words = (ref.get("url"), ref.get("words")) if isinstance(ref, dict) else (None, None)
    if not (isinstance(url, str) and url.strip() and isinstance(words, str) and words.strip()):
        return None, WHY_NO_LINK_OR_WORDS
    parts, why = comment_permalink(url, sources.get("repo"))
    if parts is None:
        return None, why
    owner, name, number, comment_id = parts
    read = sources.get("ownerRulings")
    doc = read.get(url) if isinstance(read, dict) else None
    # axis: the comment read must be the one the link names, on the issue the link names — see bite-proof record wo_a_1958_owner_ruling
    # axis: the same holds for a scope ruling and an advisor's bound, whose comment is read the same way — see bite-proof record i2532_scope_bound (E-link)
    if not (isinstance(doc, dict) and _is_int(doc.get("id")) and doc["id"] == comment_id and isinstance(doc.get("issue_url"), str)
            and doc["issue_url"].lower().endswith(f"/repos/{owner}/{name}/issues/{number}".lower())):
        return None, WHY_COMMENT_UNREAD
    return (url, words, int(number), doc.get("body")), None


def _owner_ruling_on_record(ref, sources):
    """(True, text) when the ruling's pointer resolves through every leg, else (False, why); see on_record."""
    got, why = _linked_comment(ref, sources)
    if got is None:
        return False, why
    url, words, _, body = got
    quoted = canon.ruling_record_words(body)
    # axis: only a standard chat-ruling record is a ruling, since every session posts as the owner — see bite-proof record wo_a_1958_owner_ruling
    if quoted is None:
        return False, WHY_NOT_A_RULING_RECORD
    # axis: the quoted block of that record must hold the owner's words, and nothing else in the body counts — see bite-proof record wo_a_1958_owner_ruling
    if _squash(words) not in _squash(quoted):
        return False, WHY_WORDS_ABSENT
    return True, 'owner ruling "%s" (%s)' % (words, url)


def _stated_rounds(words):
    """The number of rounds ``words`` state (an int), or None: the first digits or number word before `round(s)`."""
    found = _ROUNDS_STATED.search(words)
    if found is None:
        return None
    return int(found.group(1)) if found.group(1).isdigit() else _ROUND_WORDS[found.group(1).lower()]


def _receipt_decision(kind, lines, words, key):
    """(True, rounds) when a decision line of the vet receipt records this decision, else (False, None).

    A line counts only when it is a marker line of the cited kind (a scope ruling's key equals ``key``, a non-blank
    string; a bound's marker states its rounds, returned) and the nearest non-blank line above it holds the squashed
    words, which must be at least `_RECEIPT_WORDS_MIN` visible characters. Text elsewhere in the receipt never counts."""
    held = _squash(words)
    # axis: words under the minimum count for no line, so a short boilerplate phrase the receipt happens to hold is never a decision — see bite-proof record i2532_scope_bound (E-receipt-line)
    if len(held) < _RECEIPT_WORDS_MIN:
        return False, None
    for at, line in enumerate(lines):
        text = line.strip()
        if kind == SCOPE_RULING:
            marked = _SCOPE_MARKER.fullmatch(text)
            # axis: a scope-ruling marker line names this finding's key, never another finding's — see bite-proof record i2532_scope_bound (E-receipt-line)
            if marked is None or not (isinstance(key, str) and key.strip() and marked.group(1) == key):
                continue
            rounds = None
        else:
            marked = _BOUND_MARKER.fullmatch(text)
            if marked is None:
                continue
            rounds = int(marked.group(1))
        above = next((l for l in reversed(lines[:at]) if l.strip()), "")
        # axis: the words sit on the nearest non-blank line above the marker line, so no marker adopts words from elsewhere in the receipt — see bite-proof record i2532_scope_bound (E-receipt-line)
        if held in _squash(above):
            return True, rounds
    return False, None


def _scope_or_bound_on_record(kind, ref, sources):
    """(True, text) when a scope ruling's or an advisor's bound's pointer resolves through every leg, else (False, why).

    The legs, in order: a Critical never settles this way; the shared comment legs; then the comment is either a
    standard chat-ruling record whose quoted block holds the words (a bound's words also state a number of rounds),
    or a vet receipt on this pull request holding a decision line of the kind (see _receipt_decision); any other body
    is refused. A bound also needs the review's round count to be at least the rounds it states."""
    # axis: a Critical finding is never settled by a scope ruling or the advisor's bound, checked before the comment is read — see bite-proof record i2532_scope_bound (E-critical)
    if sources.get("findingSeverity") == "Critical":
        return False, WHY_CRITICAL
    got, why = _linked_comment(ref, sources)
    if got is None:
        return False, why
    url, words, number, body = got
    quoted = canon.ruling_record_words(body)
    lines = body.splitlines() if isinstance(body, str) else []
    receipt = quoted is None and bool(lines) and lines[0].rstrip() == VET_RECEIPT_MARKER
    # axis: a body that is neither a chat-ruling record nor a vet receipt is no ruling or bound — see bite-proof record i2532_scope_bound (E-neither)
    if quoted is None and not receipt:
        return False, WHY_NEITHER_RECORD_NOR_RECEIPT
    stated = None
    if quoted is not None:
        # axis: the quoted block of the chat-ruling record must hold the words — see bite-proof record i2532_scope_bound (E-chat)
        if _squash(words) not in _squash(quoted):
            return False, WHY_WORDS_ABSENT
        if kind == ADVISOR_BOUND:
            stated = _stated_rounds(words)
            # axis: a bound's words must state a number of rounds — see bite-proof record i2532_scope_bound (E-chat-rounds)
            if stated is None:
                return False, WHY_BOUND_STATES_NO_ROUNDS
    else:
        pr = sources.get("reviewPr")
        # axis: a vet receipt counts only on the pull request under review — see bite-proof record i2532_scope_bound (E-receipt-pr)
        if not (_is_int(pr) and number == pr):
            return False, WHY_RECEIPT_ELSEWHERE
        found, stated = _receipt_decision(kind, lines, words, sources.get("findingKey"))
        if not found:
            if kind == SCOPE_RULING:
                return False, WHY_RECEIPT_NO_SCOPE_RULING
            return False, WHY_RECEIPT_NO_BOUND
    if kind == ADVISOR_BOUND:
        count = sources.get("reviewRounds")
        if not _is_int(count):
            return False, WHY_ROUNDS_UNKNOWN
        # axis: the review must have run at least the rounds the bound states — see bite-proof record i2532_scope_bound (E-bound-rounds)
        if count < stated:
            return False, WHY_FEWER_ROUNDS % (count, stated)
        return True, 'advisor\'s bound "%s" (%s)' % (words, url)
    return True, 'scope ruling "%s" (%s)' % (words, url)


# The texts on_record and its legs return when a decision is not on record. Each text has this one home: the
# returns name it, and UNRESOLVED_WHYS is built from it, so a reader that recognises a stale clause copies none.
WHY_NOT_A_PERMALINK = "the ruling's link is not a comment permalink"
WHY_ANOTHER_REPOSITORY = "the ruling's link is not in this repository"
WHY_NO_LINK_OR_WORDS = "the ruling names no link or words"
WHY_COMMENT_UNREAD = "the ruling's comment could not be read"
WHY_NOT_A_RULING_RECORD = "the ruling's comment is not a chat-ruling record"
WHY_WORDS_ABSENT = "the ruling's comment does not hold the owner's words"
WHY_CRITICAL = "a Critical finding is never settled by a scope ruling or the advisor's bound"
WHY_NEITHER_RECORD_NOR_RECEIPT = "the ruling's comment is neither a chat-ruling record nor a vet receipt"
WHY_BOUND_STATES_NO_ROUNDS = "the bound's words state no number of rounds"
WHY_RECEIPT_ELSEWHERE = "the vet receipt is not on this pull request"
WHY_RECEIPT_NO_SCOPE_RULING = "the vet receipt records no scope ruling for this finding with these words"
WHY_RECEIPT_NO_BOUND = "the vet receipt records no advisor's bound with these words"
WHY_ROUNDS_UNKNOWN = "the review's round count is unknown"
WHY_NO_DECISION = "no decision was cited"
WHY_KIND_UNKNOWN = "the cited decision kind is not recognised"
WHY_NO_REFERENCE = "the cited decision names no reference"
WHY_NO_CANON_TEXT = "no Canon text was available"
WHY_CANON_ENTRY_ABSENT = "the cited Canon entry is not on record"
WHY_NO_RESIDUAL_TEXT = "no residual text was available"
WHY_RESIDUAL_ABSENT = "the cited residual is not recorded"
WHY_NO_SHEET_ANSWERS = "no sheet answers were available"
WHY_SHEET_ANSWER_OPEN = "the sheet answer is not settled"
WHY_FEWER_ROUNDS = "the review ran %d rounds, fewer than the bound's %d"
# The plain failure texts; WHY_FEWER_ROUNDS is formatted with the counts and is listed apart.
UNRESOLVED_WHY_TEXTS = (
    WHY_NOT_A_PERMALINK, WHY_ANOTHER_REPOSITORY, WHY_NO_LINK_OR_WORDS, WHY_COMMENT_UNREAD, WHY_NOT_A_RULING_RECORD,
    WHY_WORDS_ABSENT, WHY_CRITICAL, WHY_NEITHER_RECORD_NOR_RECEIPT, WHY_BOUND_STATES_NO_ROUNDS, WHY_RECEIPT_ELSEWHERE,
    WHY_RECEIPT_NO_SCOPE_RULING, WHY_RECEIPT_NO_BOUND, WHY_ROUNDS_UNKNOWN, WHY_NO_DECISION, WHY_KIND_UNKNOWN,
    WHY_NO_REFERENCE, WHY_NO_CANON_TEXT, WHY_CANON_ENTRY_ABSENT, WHY_NO_RESIDUAL_TEXT, WHY_RESIDUAL_ABSENT,
    WHY_NO_SHEET_ANSWERS, WHY_SHEET_ANSWER_OPEN)
# The clause `settle` stamps on a leftover whose cited decision is not on record, with the failure text in %s.
UNRESOLVED_CLAUSE = "the cited decision is not on record: %s"
# Each failure text as a regular-expression source; the formatted one takes any integer where it writes %d.
UNRESOLVED_WHYS = tuple(re.escape(t) for t in UNRESOLVED_WHY_TEXTS) + (
    re.escape(WHY_FEWER_ROUNDS).replace("%d", r"-?\d+"),)


def on_record(decided_by, sources):
    """Decide whether a cited owner decision is on record: (True, what) or (False, why).

    decided_by is {"kind": canon | residual | sheet-answer | owner-ruling | scope-ruling | advisor-bound, "ref": ...};
    sources may hold canonText, residualText, residualSource, sheetAnswers, pr, and for the three linked kinds repo and
    ownerRulings ({link: the comment's JSON}), and for a scope ruling or an advisor's bound also reviewPr (the pull
    request number), reviewRounds (the review's round count), findingKey (the finding's stored key) and findingSeverity.
    An owner ruling is on record only when its link is an issue-comment permalink in
    the pull request's own repository, the comment read is that comment on that issue, its body is a standard
    chat-ruling record (canon.ruling_record_words), and that record's quoted block holds the words. A scope ruling or an
    advisor's bound needs the same comment legs and then either a chat-ruling record that holds the words (a bound's
    words also state a number of rounds), or a vet receipt on pull request reviewPr whose decision line (a scope-ruling
    marker line naming findingKey, or an advisor-bound marker line stating its rounds) has the words on the line
    above; a bound also needs reviewRounds to be at least the rounds it states, and a Critical finding is never settled
    by either. The comment's author_association is not read: every session posts as the owner, and on an
    organisation-owned repository the owner's own comment reads MEMBER. Never raises.
    """
    if not isinstance(decided_by, dict):
        return False, WHY_NO_DECISION
    if not isinstance(sources, dict):
        sources = {}
    kind = decided_by.get("kind")
    ref = decided_by.get("ref")
    if kind not in DECISION_KINDS:
        return False, WHY_KIND_UNKNOWN
    if ref is None or (isinstance(ref, str) and ref.strip() == ""):
        return False, WHY_NO_REFERENCE
    if kind == OWNER_RULING:
        return _owner_ruling_on_record(ref, sources)
    if kind in (SCOPE_RULING, ADVISOR_BOUND):
        return _scope_or_bound_on_record(kind, ref, sources)
    if kind == "canon":
        text = sources.get("canonText")
        if not isinstance(text, str):
            return False, WHY_NO_CANON_TEXT
        if not canon_decides(text, ref):
            return False, WHY_CANON_ENTRY_ABSENT
        return True, "canon %s" % ref
    if kind == "residual":
        text = sources.get("residualText")
        if not isinstance(text, str):
            return False, WHY_NO_RESIDUAL_TEXT
        if not residual_decides(text, ref):
            return False, WHY_RESIDUAL_ABSENT
        origin = sources.get("residualSource")
        suffix = " (read from %s)" % origin if isinstance(origin, str) and origin.strip() else ""
        return True, "residual %s%s" % (ref, suffix)
    answers = sources.get("sheetAnswers")
    if not isinstance(answers, dict) or "pr" not in sources:
        return False, WHY_NO_SHEET_ANSWERS
    if not sheet_answer_decides(answers, ref, sources.get("pr")):
        return False, WHY_SHEET_ANSWER_OPEN
    return True, "sheet-answer %s" % _sheet_ref_text(ref)


def settle(finding, *, ruling=None, sources=None, open_reason, open_at_end=False):
    """Settle a finding the review left unfixed: {"outcome", "reason", "decidedBy"}.

    Craft when the only consequence is code quality (it wins over any ruling); a named ruling
    when the latest rulings-log row cites a decision that is on record; otherwise left for the
    owner, with open_reason and, when a cited decision did not resolve, why; that leftover keeps the citation,
    so the record writer can promote it if the decision is on record by write time. Never reads severity.

    With ``open_at_end`` True, a leftover that cites no decision also carries `openAtLoopEnd: True`: it was left for
    the owner only because it was still open when its loop ended. Craft, a ruling and a leftover that cites a decision never do.
    """
    outcomes = review_findings_schema.OUTCOMES
    craft, left_for_owner, ruled = outcomes[2], outcomes[3], outcomes[4]
    finding = finding if isinstance(finding, dict) else {}
    if finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.CODE_QUALITY:
        stated = (finding[review_findings_schema.CONSEQUENCE_KEY].strip()
                  if has_stated_consequence(finding) else "no further consequence stated")
        return {"outcome": craft, "reason": "code quality only: " + stated, "decidedBy": None}
    decided_by = ruling.get("decidedBy") if isinstance(ruling, dict) else None
    why = ""
    if decided_by is not None:
        resolved, text = on_record(decided_by, sources)
        if resolved:
            return {"outcome": ruled, "reason": "decided by " + text, "decidedBy": decided_by}
        why = "; " + UNRESOLVED_CLAUSE % text
    result = {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": decided_by}
    if open_at_end and decided_by is None:
        result[session_contract.OPEN_AT_LOOP_END_FIELD] = True
    return result


def decision_sources(repo_root, base_ref, sheet_answers=None, pr=None):
    """The `sources` dict on_record reads: the Canon text, the ratified residuals and, when given, the sheet answers.

    A source that cannot be read is left out, so a decision that cites it is not on record. Canon is
    both copies (the working copy and the default branch's), so a supersession on the default branch
    retires an entry the working copy still holds. Residuals come from the review base when it pins
    them, else from the calibration store. Never raises."""
    sources = {}
    # With no repository named nothing is read: the ambient project's Canon is never taken for this one's.
    named = isinstance(repo_root, str) and repo_root.strip() != ""
    try:
        if not named:
            raise ValueError("no repository root")
        _, working, default_text = canon._locate(repo_root)
        sources["canonText"] = working + "\n" + default_text
    except Exception:  # noqa: BLE001 — fail closed: no Canon text means no Canon decision
        sources.pop("canonText", None)
    try:
        if not named:
            raise ValueError("no repository root")
        import round_orders
        text, provenance, failure = round_orders.resolve_order_residuals(repo_root, base_ref)
        if not failure and isinstance(text, str) and text.strip():
            sources["residualText"] = text
            based = isinstance(provenance, str) and "(base-pinned)" in provenance
            sources["residualSource"] = "base" if based else "calibration store"
    except Exception:  # noqa: BLE001 — fail closed: no residual text means no residual decision
        sources.pop("residualText", None)
        sources.pop("residualSource", None)
    if isinstance(sheet_answers, dict):
        sources["sheetAnswers"] = sheet_answers
        sources["pr"] = pr
    return sources
