"""The one home of the outcome rules for a review finding.

Every finding ends with exactly one outcome, spelled once in review_findings_schema.OUTCOMES.
This module is the only place that decides four things: whether a finding states a
consequence, how merged findings combine their consequence, whether a cited owner decision is
on record, and the outcome of a finding the review left unfixed.

A finding that is neither fixed nor shown wrong, and whose only consequence is code quality,
is craft, wherever in the project it sits. Any other consequence is real. An unfixed finding
with a real consequence is left for the owner, unless a decision on record names it, in which
case it is decided by a named ruling. A decision is on record only when it is an active Canon
entry, a recorded residual, or a settled saved sheet answer for the pull request. Severity
never decides an outcome.

The module is pure: it reads no file, runs no git or subprocess and touches no network.
Callers pass text and dicts in. Anything missing or malformed fails closed, toward the owner.
"""
import canon
import review_findings_schema

_DECISION_KINDS = ("canon", "residual", "sheet-answer")
_SUPERSEDES_PREFIX = "supersedes: "


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


def _supersedes_target(line):
    """The id a complete entry line names in its supersedes field, or None."""
    for field in line.split(canon.SEP)[4:-2]:
        if field.startswith(_SUPERSEDES_PREFIX):
            return field[len(_SUPERSEDES_PREFIX):].strip()
    return None


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
        if _supersedes_target(line) == entry_id:
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


def sheet_answer_decides(answers, ref, pr):
    """True only when the cited card of this pull request holds a settled accept or option answer."""
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
    answer = doc.get("answer")
    if answer == "accept":
        return True
    option_id = doc.get("optionId")
    return answer == "option" and isinstance(option_id, str) and option_id.strip() != ""


def _sheet_ref_text(ref):
    if isinstance(ref, dict):
        return "pr %s card %s" % (ref.get("pr"), ref.get("card"))
    return str(ref)


def on_record(decided_by, sources):
    """Decide whether a cited owner decision is on record: (True, what) or (False, why).

    decided_by is {"kind": canon | residual | sheet-answer, "ref": ...}; sources may hold
    canonText, residualText, residualSource, sheetAnswers and pr. Never raises.
    """
    if not isinstance(decided_by, dict):
        return False, "no decision was cited"
    if not isinstance(sources, dict):
        sources = {}
    kind = decided_by.get("kind")
    ref = decided_by.get("ref")
    if kind not in _DECISION_KINDS:
        return False, "the cited decision kind is not recognised"
    if ref is None or (isinstance(ref, str) and ref.strip() == ""):
        return False, "the cited decision names no reference"
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
    owner, with open_reason and, when a cited decision did not resolve, why. Never reads severity.
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
    return {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": None}
