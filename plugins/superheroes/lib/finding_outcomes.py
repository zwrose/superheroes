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
whose pointer resolves: a readable owner-authored comment in the pull request's own repository, at
the exact permalink, that is a standard chat-ruling record whose quoted block holds the owner's
words. Severity never decides an outcome.

The rules are pure: they read no file, run no git or subprocess and touch no network. Callers
pass text and dicts in. The one reader is decision_sources, which gathers the Canon and residual
text the rules are given. Anything missing or malformed fails closed, toward the owner.
"""
import re

import canon
import review_findings_schema

OWNER_RULING = "owner-ruling"
DECISION_KINDS = ("canon", "residual", "sheet-answer", OWNER_RULING)
_COMMENT_PERMALINK = re.compile(r"https://github\.com/([^/\s#?]+)/([^/\s#?]+)/issues/([0-9]+)#issuecomment-([0-9]+)")


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
    {"url": non-blank string, "words": non-blank string} for an owner ruling."""
    if not isinstance(decided_by, dict) or set(decided_by) != {"kind", "ref"}:
        return False
    kind, ref = decided_by["kind"], decided_by["ref"]
    if kind not in DECISION_KINDS:
        return False
    if kind == "sheet-answer":
        return (isinstance(ref, dict) and set(ref) == {"pr", "card"} and _is_int(ref["pr"])
                and isinstance(ref["card"], str) and ref["card"].strip() != "")
    if kind == OWNER_RULING:
        return isinstance(ref, dict) and set(ref) == {"url", "words"} and all(
            isinstance(ref[k], str) and ref[k].strip() != "" for k in ("url", "words"))
    return isinstance(ref, str) and ref.strip() != ""


def comment_permalink(url, repo):
    """The comment a ruling's link points at, as (owner, repo, issue number, comment id), or the reason it cannot be one.

    The link must be an issue-comment permalink (leg L1) in the pull request's own repository, compared
    case-insensitively (leg L2). Returns (parts, None) or (None, why). Never raises."""
    # axis: the link must be a comment permalink — see bite-proof record wo_a_1958_owner_ruling
    found = _COMMENT_PERMALINK.fullmatch(url) if isinstance(url, str) else None
    if found is None:
        return None, "the ruling's link is not a comment permalink"
    owner, name, number, comment = found.groups()
    # axis: the link must be in the pull request's own repository — see bite-proof record wo_a_1958_owner_ruling
    if not (isinstance(repo, str) and repo.lower() == f"{owner}/{name}".lower()):
        return None, "the ruling's link is not in this repository"
    return (owner, name, number, int(comment)), None


def _owner_ruling_on_record(ref, sources):
    """(True, text) when the ruling's pointer resolves through every leg, else (False, why); see on_record."""
    url, words = (ref.get("url"), ref.get("words")) if isinstance(ref, dict) else (None, None)
    if not (isinstance(url, str) and url.strip() and isinstance(words, str) and words.strip()):
        return False, "the ruling names no link or words"
    parts, why = comment_permalink(url, sources.get("repo"))
    if parts is None:
        return False, why
    owner, name, number, comment_id = parts
    read = sources.get("ownerRulings")
    doc = read.get(url) if isinstance(read, dict) else None
    # axis: the comment read must be the one the link names, on the issue the link names — see bite-proof record wo_a_1958_owner_ruling
    if not (isinstance(doc, dict) and _is_int(doc.get("id")) and doc["id"] == comment_id and isinstance(doc.get("issue_url"), str)
            and doc["issue_url"].lower().endswith(f"/repos/{owner}/{name}/issues/{number}".lower())):
        return False, "the ruling's comment could not be read"
    body = doc.get("body")
    quoted = canon.ruling_record_words(body)
    # axis: only a standard chat-ruling record is a ruling, since every session posts as the owner — see bite-proof record wo_a_1958_owner_ruling
    if quoted is None:
        return False, "the ruling's comment is not a chat-ruling record"
    # axis: the quoted block of that record must hold the owner's words, and nothing else in the body counts — see bite-proof record wo_a_1958_owner_ruling
    if _squash(words) not in _squash(quoted):
        return False, "the ruling's comment does not hold the owner's words"
    return True, 'owner ruling "%s" (%s)' % (words, url)


def on_record(decided_by, sources):
    """Decide whether a cited owner decision is on record: (True, what) or (False, why).

    decided_by is {"kind": canon | residual | sheet-answer | owner-ruling, "ref": ...}; sources may hold
    canonText, residualText, residualSource, sheetAnswers, pr, and for an owner ruling repo and ownerRulings
    ({link: the comment's JSON}). An owner ruling is on record only when its link is an issue-comment permalink in
    the pull request's own repository, the comment read is that comment on that issue, its body is a standard
    chat-ruling record (canon.ruling_record_words), and that record's quoted block holds the words. The comment's
    author_association is not read: every session posts as the owner, and on an organisation-owned repository the
    owner's own comment reads MEMBER. Never raises.
    """
    if not isinstance(decided_by, dict):
        return False, "no decision was cited"
    if not isinstance(sources, dict):
        sources = {}
    kind = decided_by.get("kind")
    ref = decided_by.get("ref")
    if kind not in DECISION_KINDS:
        return False, "the cited decision kind is not recognised"
    if ref is None or (isinstance(ref, str) and ref.strip() == ""):
        return False, "the cited decision names no reference"
    if kind == OWNER_RULING:
        return _owner_ruling_on_record(ref, sources)
    if kind == "canon":
        text = sources.get("canonText")
        if not isinstance(text, str):
            return False, "no Canon text was available"
        if not canon_decides(text, ref):
            return False, "the cited Canon entry is not on record"
        return True, "canon %s" % ref
    if kind == "residual":
        text = sources.get("residualText")
        if not isinstance(text, str):
            return False, "no residual text was available"
        if not residual_decides(text, ref):
            return False, "the cited residual is not recorded"
        origin = sources.get("residualSource")
        suffix = " (read from %s)" % origin if isinstance(origin, str) and origin.strip() else ""
        return True, "residual %s%s" % (ref, suffix)
    answers = sources.get("sheetAnswers")
    if not isinstance(answers, dict) or "pr" not in sources:
        return False, "no sheet answers were available"
    if not sheet_answer_decides(answers, ref, sources.get("pr")):
        return False, "the sheet answer is not settled"
    return True, "sheet-answer %s" % _sheet_ref_text(ref)


def settle(finding, *, ruling=None, sources=None, open_reason):
    """Settle a finding the review left unfixed: {"outcome", "reason", "decidedBy"}.

    Craft when the only consequence is code quality (it wins over any ruling); a named ruling
    when the latest rulings-log row cites a decision that is on record; otherwise left for the
    owner, with open_reason and, when a cited decision did not resolve, why; that leftover keeps the citation,
    so the record writer can promote it if the decision is on record by write time. Never reads severity.
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
        why = "; the cited decision is not on record: " + text
    return {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": decided_by}


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
