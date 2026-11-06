"""The one home of the calibration-disclosure rule (#2364): a PR body's ``### Disclosed degradations`` list says a review
seat lacked calibration (``core.md``, ``review-crew.md`` or ``CLAUDE.md``) only through one fixed marker, and the handback
check reads that marker exactly against the latest review record.

The marker is one Markdown code span inside a degradation bullet, ``MARKER_FORM``: ``calibration-lacked[<row name>]:
<files>``, for example ``MARKER_EXAMPLE``. ``<row name>`` is the review record's row ``name`` byte for byte, or ``*`` for
every row whose ``ran`` is not ``not-run``. ``<files>`` is one or more of ``core.md``, ``review-crew.md`` and
``CLAUDE.md`` (exact case), separated by a comma and one space, with no duplicate. The parse is ``_MARKER``, applied to
the raw bullet text; a span that does not parse to a valid marker is left in the text.

The invariant: every valid marker in a degradation bullet is compared exactly against the latest review record, and a
degradation bullet that mentions calibration outside a valid marker never passes, whatever the record says.
- A marker contradicts the record when a target row is an engine-record row whose ``calibrationRead`` grades at least
  one of the marker's named files ``read`` (one named file read is enough). Refused ``REASON``.
- A marker whose row name matches no row of the record exactly is refused ``REASON_UNKNOWN_SEAT``; the match is never
  widened.
- The text left after the valid markers are removed is read as before: a clause that names a calibration file or
  calibration together with a negation or removal word, after the doctrine exemptions (the show-it surface declaration,
  "calibrated" before verify, model or command, and "the calibrated <model identifier>") are masked, is a calibration
  mention outside the marker, refused ``REASON_UNMARKED``. A clause that names calibration with no lack word is not one.
- Every other case passes: not-read, unknown, an unmeasured row (no or malformed ``calibrationRead``), a row whose order
  named none (``[]``), ``reported-by-session``, ``not-run``, and ``*`` with no target. The check never refuses on a fact
  the record does not hold.

One caller, no second copy of the rule: ``vet_slot.py handback --pr``. ``problems`` takes the latest record exactly as
``review_record.py read --pr <n>`` returns it and the PR body; it returns the problems found, and raises ``Unreadable``
for a record it cannot read, which the caller reports as unreadable, never as a pass."""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import calibration_vocab  # noqa: E402
import pr_sheet  # noqa: E402
import review_record  # noqa: E402

REASON = "calibration-disclosure-contradicted"
REASON_UNKNOWN_SEAT = "calibration-disclosure-unknown-seat"
REASON_UNMARKED = "calibration-disclosure-unmarked"

MARKER_FORM = "`calibration-lacked[<row name>]: <files>`"
MARKER_EXAMPLE = "`calibration-lacked[code-reviewer:s1 (round 1)]: core.md, review-crew.md`"
_MARKER = re.compile(r"`calibration-lacked\[([^\]`]+)\]: ([^`]+)`")
_FILE_LABELS = {"core.md": calibration_vocab.LABEL_CORE, "review-crew.md": calibration_vocab.LABEL_REVIEW_CREW,
                "CLAUDE.md": calibration_vocab.LABEL_CLAUDE_MD}
_EVERY_SEAT = "*"

FIX = ("Disclose a review seat that lacked calibration only with the marker " + MARKER_FORM + ", for example "
       + MARKER_EXAMPLE + ": the row name exactly as the review record names it (or * for every seat that ran), and the"
       " files it lacked from core.md, review-crew.md and CLAUDE.md, each separated by a comma and a space. Name only a"
       " seat the record grades not-read or unknown for those files, or does not measure. Put an unrelated lack (a"
       " browser, a tool, a runner) in its own bullet or sentence, apart from any mention of calibration.")

_CLAUSES = re.compile(r"[.;](?=\s|$)|\b(?:but|while|whereas|although)\b", re.I)
_NOUNS = (
    re.compile(r"\bcore\.md\b|\bcore calibration\b|\bthreat[- ]models?\b|\bcanonical patterns\b", re.I),
    re.compile(r"\breview[- ]crew(?:\.md)?\b|\bfocus hints?\b|\breview notes\b", re.I),
    re.compile(r"\bclaude\.md\b", re.I),
)
_GENERIC = re.compile(
    r"\b(?:un)?calibrat(?:e|es|ed|ing|ion|ions)\b|\bproject notes\b|\bconventions file\b|\binstructions file\b", re.I)
# A clause that names a calibration file or calibration and holds any negation or removal word is a mention of a
# calibration lack, whatever the word is about. Nothing else about the clause is judged. The trade is deliberate: a
# truthful clause that mixes an unrelated lack with a calibration mention is refused, and an unrelated lack belongs in
# its own bullet or sentence.
_LACK = re.compile(
    r"\b(?:not|never|no|none|nothing|zero|cannot|without|lack(?:s|ed|ing)?|missing|strip(?:s|ped|ping)?(?: of)?|"
    r"remov(?:e|es|ed|ing|al)|withh(?:e|o)ld(?:s|ing)?|withheld|(?:left|leaves|leaving|leave) out|"
    r"exclud(?:e|es|ed|ing)|omit(?:s|ted|ting)?|omission|drop(?:s|ped|ping)?|delet(?:e|es|ed|ing)|"
    r"hid(?:e|es|den|ing)?|den(?:y|ies|ied|ying|ial)|inaccessible|unavailable|absent|gone|unread|"
    r"uncalibrat(?:e|es|ed|ing|ion|ions))\b|(?<=[a-z])n't\b", re.I)
# Calibration mentions that are never a lack: the project's show-it surface declaration (the doctrine's own required
# disclosure) and "calibrated" as a modifier before verify, model or command, or in "the calibrated <model identifier>"
# (a token that starts with a letter and holds a digit).
_EXEMPT = re.compile(
    r"\b(?:core\.md|(?:the\s+)?(?:project'?s\s+)?calibration)\s+(?:has|declares|with)\s+no\s+(?:#+\s*)?show-it surface\b"
    r"|\bshow-it surface\b|\bcalibrated[\s-]+(?:verify|model|command)s?\b|\bthe\s+calibrated\s+[a-z]\S*\d\S*", re.I)
# Markdown emphasis characters become spaces and typographic apostrophes and the no-break space become their plain
# forms, so formatting cannot hide a word from the patterns above.
_FORMATTING = str.maketrans({"_": " ", "*": " ", "~": " ", "`": " ", "‘": "'", "’": "'", "\xa0": " "})
# The placeholder ``problems`` leaves in a detail for the record's address; ``describe`` fills it.
_WHERE = "<where>"


class Unreadable(Exception):
    """The latest review record could not be read, so the rule cannot be checked."""


def _normalise(text):
    """``text`` with Markdown emphasis characters (underscore, asterisk, tilde, backtick) as spaces, curly apostrophes as
    ``'`` and the no-break space as a space, then every run of whitespace (newlines included) as one space. The one
    normal form of the degradation text."""
    # axis: formatting (emphasis characters, curly apostrophes, the no-break space) never hides a lack word or a calibration noun from the patterns, and whitespace runs are collapsed into one normal form — see bite-proof record i2364_calibration_disclosure
    return re.sub(r"\s+", " ", text.translate(_FORMATTING))


def _valid_markers(text):
    """The valid markers in the raw ``text``, in text order: [(match, row text, labels)]. A span with a name outside the
    three files, a duplicate name or an empty list is not a valid marker and is left to the unmarked test."""
    out = []
    for match in _MARKER.finditer(text):
        files = match.group(2).split(", ")
        labels = [_FILE_LABELS.get(name) for name in files]
        # axis: a marker is valid only when its files are a non-empty list of the three exact names with no duplicate; any other span is left in the text and refused as unmarked — see bite-proof record i2364_calibration_disclosure
        if None not in labels and len(set(files)) == len(files):
            out.append((match, match.group(1), labels))
    return out


def _unmarked_text(text, markers):
    """The raw ``text`` with each valid marker span (from ``_valid_markers``) replaced by one space."""
    parts, end = [], 0
    for match, _row, _labels in markers:
        parts += [text[end:match.start()], " "]
        end = match.end()
    return "".join(parts) + text[end:]


def _mentions_calibration(normal):
    """Whether any clause of the normalised ``normal`` text names a calibration file or calibration together with a
    negation or removal word, after the doctrine exemptions are masked."""
    for clause in _CLAUSES.split(normal):
        # axis: a doctrine-prescribed show-it disclosure or a stock "calibrated verify/model/command" phrase is masked before the mention test, and a real calibration lack beside it still counts — see bite-proof record i2364_calibration_disclosure
        masked = _EXEMPT.sub(" ", clause)
        # axis: a clause that names calibration and holds any negation or removal word is a mention of a lack, with no judgment of which subject the word belongs to — see bite-proof record i2364_calibration_disclosure
        if (any(noun.search(masked) for noun in _NOUNS) or _GENERIC.search(masked)) and _LACK.search(masked):
            return True
    return False


def _contradicts(row, labels):
    """Whether the record measured this row reading at least one of the marker's ``labels``."""
    # axis: only an engine-record row counts; unmeasured, session-reported, not-run and none-named rows never contradict a marker — see bite-proof record i2364_calibration_disclosure
    if row.get("ran") != "engine-record":
        return False
    files = review_record._valid_calibration(row.get("calibrationRead")) or []
    # axis: one named file graded read contradicts the marker, so a partly false marker cannot pass — see bite-proof record i2364_calibration_disclosure
    return any(entry["label"] in labels and entry["read"] == calibration_vocab.READ for entry in files)


def problems(record, body):
    """The problems in ``body``'s degradations against the latest review record, as [{"reason", "degradation", "detail"}]
    in body order ([] when none). ``record`` is ``review_record.read``'s result; Unreadable when it cannot be read, even
    when the body holds no marker and no mention. Within one bullet the markers' problems come first in text order, then
    at most one unmarked problem."""
    # axis: a read that did not succeed (missing, unreadable, gh failed) is unreadable, never a pass — see bite-proof record i2364_calibration_disclosure
    if not isinstance(record, dict) or record.get("ok") is not True:
        detail = record.get("detail") or record.get("reason") if isinstance(record, dict) else None
        raise Unreadable(detail or "the review record read did not succeed")
    bullets = [(text, _valid_markers(text)) for _label, text in pr_sheet.degradations_listed(body)]
    rows = []
    if any(markers for _text, markers in bullets):
        rows = record.get("reviewers")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise Unreadable("the record's reviewers list is missing or malformed")
    out = []
    for text, markers in bullets:
        for _match, row_text, labels in markers:
            if row_text == _EVERY_SEAT:
                targets = [r for r in rows if r.get("ran") != "not-run"]
            else:
                targets = [r for r in rows if r.get("name") == row_text]
                # axis: a marker whose row name matches no row exactly is refused unknown-seat, never widened to a near match — see bite-proof record i2364_calibration_disclosure
                if not targets:
                    names = "; ".join(str(r.get("name")) for r in rows)
                    out.append({"reason": REASON_UNKNOWN_SEAT, "degradation": text,
                                "detail": "its marker names %s, which is not a row of %s; its rows are: %s"
                                          % (row_text, _WHERE, names)})
                    continue
            lines = ["%s: %s" % (r.get("name"), review_record._calibration_words(r))
                     for r in targets if _contradicts(r, labels)]
            if lines:
                out.append({"reason": REASON, "degradation": text,
                            "detail": "its marker for %s contradicts %s: %s" % (row_text, _WHERE, "; ".join(lines))})
        # axis: only the valid marker spans are masked before the unmarked test, so prose beside a marker is still read — see bite-proof record i2364_calibration_disclosure
        left = _unmarked_text(text, markers)
        # axis: a bullet that mentions calibration outside a valid marker is refused unmarked, whatever the record says — see bite-proof record i2364_calibration_disclosure
        if _mentions_calibration(_normalise(left)):
            out.append({"reason": REASON_UNMARKED, "degradation": text,
                        "detail": "mentions calibration outside the marker"})
    return out


def describe(found, record_url):
    """The refusal detail naming each problem in ``found`` (``problems``' result), then the fix sentence."""
    where = record_url if isinstance(record_url, str) and record_url else "the latest review record"
    parts = []
    for p in found:
        sep = " " if p["reason"] == REASON_UNMARKED else ": "
        sentence = "Disclosed degradation %r%s%s" % (p["degradation"][:200], sep, p["detail"].replace(_WHERE, where))
        parts.append(sentence if sentence.endswith(".") else sentence + ".")
    return " ".join(parts) + " " + FIX
