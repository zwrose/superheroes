"""#2364: a PR body's Disclosed degradations says a review seat lacked its calibration only through one fixed marker,
and the marker is compared exactly against the latest review record; a degradation that mentions calibration outside a
valid marker is refused. One rule (calibration_disclosure), one caller (vet_slot handback --pr). No real gh: every call
is faked."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import calibration_disclosure as cd
import review_record as rr
import sanitized_view as sv
import vet_slot as vs

REPO = "owner/example"
PR = 42
VIEW = ("gh", "api", "repos/owner/example/pulls/42")
COMMENTS = "repos/owner/example/issues/42/comments?per_page=100&page="
USER = ("gh", "api", "user", "-q", ".login")
HANDBACK_MD = Path(__file__).resolve().parents[2] / "skills" / "workhorse" / "reference" / "handback.md"


def body(degradations, accepting="None\n"):
    """A handback-shaped body whose build record carries the degradations list (None = no degradations marker)."""
    listing = "" if degradations is None else (
        "<!-- superheroes:degradations -->\n### Disclosed degradations\n\n" + degradations + "\n")
    return ("Closes #1.\n\n## What's changing, and why\n\nA change.\n\n## What we're accepting\n\n" + accepting
            + "\n## How to see it\n\nN/A — nothing to see.\n\n## Advisor vet\n<!-- superheroes:advisor-vet -->\n"
            "old slot text\n\n<!-- superheroes:build-record -->\n<details><summary>Build record</summary>\n\n"
            + listing + "<!-- superheroes:followups none -->\n</details>\n")


def bullet(text, label="costly"):
    return body("- [%s] %s\n" % (label, text))


def mark(name, files):
    """The calibration marker for row ``name`` and the file list ``files`` (a string, written as given)."""
    return "`calibration-lacked[%s]: %s`" % (name, files)


def entry(label, file, state="read"):
    return {"label": label, "file": file, "sha256": None, "policyVersion": None, "read": state}


def cal(core="read", crew="read", claude="read"):
    return [entry("core", "core.md", core), entry("review-crew", "review-crew.md", crew),
            entry("CLAUDE.md", "CLAUDE.md", claude)]


def row(name, calibration=None, ran="engine-record"):
    out = {"name": name, "ran": ran}
    if ran == "engine-record" and calibration is not False:
        out["calibrationRead"] = cal() if calibration is None else calibration
    return out


def rec(reviewers, **extra):
    return {"ok": True, "url": "https://x/c/900", "reviewers": reviewers, **extra}


def comment(text, cid=1, login="advisor"):
    return {"id": cid, "html_url": "https://x/c/%d" % cid, "body": text, "created_at": "2026-10-31T10:00:00Z",
            "user": {"login": login}}


def record_comment(reviewers, findings=(), left=(), cid=900):
    stored = {"schema": rr.RECORD_SCHEMA, "findings": list(findings), "leftForOwner": list(left),
              "reviewers": reviewers}
    text = (rr.MARKER + "\n\n<details><summary>Record</summary>\n\n```json\n" + json.dumps(stored)
            + "\n```\n</details>\n")
    return comment(text, cid=cid, login="builder")


class Fake:
    def __init__(self, pr_body, comments):
        self.pr_body, self.comments, self.calls = pr_body, comments, []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        key = tuple(argv)
        if key == VIEW:
            payload = {"body": self.pr_body, "base": {"ref": "main", "repo": {"default_branch": "main"}},
                       "head": {"sha": "a" * 40}}
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        if key == USER:
            return SimpleNamespace(returncode=0, stdout="advisor\n", stderr="")
        if key[:2] == ("gh", "api") and key[2].startswith(COMMENTS):
            page = int(key[2].rsplit("=", 1)[1])
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.comments[(page - 1) * 100:page * 100]),
                                   stderr="")
        raise AssertionError("unexpected argv %r" % (argv,))


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def handback(pr_body, comments):
    return vs.run_verb("handback", PR, REPO, run=Fake(pr_body, comments))


def reasons(found):
    return [p["reason"] for p in found]


CODE1, SEC1, PRE1 = "code-reviewer (round 1)", "security-reviewer (round 1)", "premortem-reviewer (round 1)"
ALL_FILES = "core.md, review-crew.md, CLAUDE.md"
NOT_READ = cal("not-read", "not-read", "not-read")
READ_LINE = ": read its calibration: core.md, review-crew.md, CLAUDE.md"


# --- 1, 2: the incident, through handback --------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Calibration was stripped from the reviewers.",
    "Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.",
])
def test_dod_headline_unmarked_is_refused(text):
    pr_body = bullet(text)
    result = handback(pr_body, [record_comment([row(CODE1), row(SEC1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
    assert cd.MARKER_FORM in result["detail"] and cd.MARKER_EXAMPLE in result["detail"]
    assert reasons(cd.problems(rec([row(CODE1), row(SEC1)]), pr_body)) == [cd.REASON_UNMARKED]


def test_incident_wording_unmarked_is_refused():
    pr_body = bullet("The code, security and failure-mode reviewers judged without this project's threat model and"
                     " focus hints.")
    result = handback(pr_body, [record_comment([row(CODE1), row(SEC1), row(PRE1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
    assert reasons(cd.problems(rec([row(CODE1)]), pr_body)) == [cd.REASON_UNMARKED]


# --- 3, 4, 5: a marker against what the record grades -----------------------------------------------------------

def test_a_contradicted_marker_refuses():
    pr_body = bullet(mark(CODE1, "core.md"))
    found = cd.problems(rec([row(CODE1), row(SEC1)]), pr_body)
    assert reasons(found) == [cd.REASON]
    result = handback(pr_body, [record_comment([row(CODE1), row(SEC1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
    assert CODE1 + READ_LINE in result["detail"]
    assert SEC1 not in result["detail"]


@pytest.mark.parametrize("state", ["not-read", "unknown"])
def test_disclosure_naming_a_seat_not_graded_read_passes(state):
    reviewers = [row(CODE1, cal(crew=state)), row(SEC1)]
    assert handback(bullet(mark(CODE1, "review-crew.md")), [record_comment(reviewers)])["ok"] is True
    # the same marker for the seat that did read it is refused
    other = handback(bullet(mark(SEC1, "review-crew.md")), [record_comment(reviewers)])
    assert other["reason"] == "calibration-disclosure-contradicted" and SEC1 in other["detail"]


@pytest.mark.parametrize("state", ["not-read", "unknown", "unmeasured"])
def test_a_supported_marker_passes(state):
    reviewers = [row(CODE1, False if state == "unmeasured" else cal(state, state, state))]
    pr_body = bullet(mark(CODE1, "core.md"))
    assert handback(pr_body, [record_comment(reviewers)])["ok"] is True
    assert cd.problems(rec(reviewers), pr_body) == []


def test_a_seat_whose_order_named_no_calibration_may_be_named():
    reviewers = [row(CODE1, []), row(SEC1)]
    assert handback(bullet(mark(CODE1, "core.md")), [record_comment(reviewers)])["ok"] is True
    found = cd.problems(rec(reviewers), bullet(mark(SEC1, "core.md")))
    assert reasons(found) == [cd.REASON]


def test_a_marker_is_contradicted_by_any_named_file_read():
    reviewers = [row(CODE1, cal(core="read", crew="not-read"))]
    both = bullet(mark(CODE1, "core.md, review-crew.md"))
    assert reasons(cd.problems(rec(reviewers), both)) == [cd.REASON]
    assert handback(both, [record_comment(reviewers)])["reason"] == "calibration-disclosure-contradicted"
    only_crew = bullet(mark(CODE1, "review-crew.md"))
    assert cd.problems(rec(reviewers), only_crew) == []
    assert handback(only_crew, [record_comment(reviewers)])["ok"] is True


def test_a_marker_naming_an_absent_row_refuses():
    reviewers = [row(CODE1), row(SEC1)]
    for name in ("code-reviewer (round 9)", "code-reviewer (round 1) "):
        pr_body = bullet(mark(name, "core.md"))
        found = cd.problems(rec(reviewers), pr_body)
        assert reasons(found) == [cd.REASON_UNKNOWN_SEAT]
        result = handback(pr_body, [record_comment(reviewers)])
        assert result["ok"] is False and result["reason"] == "calibration-disclosure-unknown-seat"
        assert CODE1 in result["detail"] and SEC1 in result["detail"]
        assert "calibration-disclosure-contradicted" not in result["detail"]


def test_the_every_seat_group():
    pr_body = bullet(mark("*", "core.md"))
    both_unread = [row(CODE1, NOT_READ), row(SEC1, NOT_READ)]
    assert handback(pr_body, [record_comment(both_unread)])["ok"] is True
    one_read = [row(CODE1, NOT_READ), row(SEC1)]
    assert reasons(cd.problems(rec(one_read), pr_body)) == [cd.REASON]
    result = handback(pr_body, [record_comment(one_read)])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
    assert SEC1 in result["detail"] and CODE1 not in result["detail"]


def test_two_markers_in_one_bullet_are_each_checked():
    reviewers = [row(CODE1, cal(core="read", crew="not-read"))]
    pr_body = bullet(mark(CODE1, "review-crew.md") + " and " + mark(CODE1, "core.md"))
    assert reasons(cd.problems(rec(reviewers), pr_body)) == [cd.REASON]


def test_a_marker_wrapped_across_lines_is_read():
    pr_body = body("- [costly] `calibration-lacked[code-reviewer (round\n  1)]: core.md`\n")
    assert reasons(cd.problems(rec([row(CODE1)]), pr_body)) == [cd.REASON]
    assert cd.problems(rec([row(CODE1, NOT_READ)]), pr_body) == []


# --- 6: no calibration disclosure ------------------------------------------------------------------------

def test_no_calibration_disclosure_passes():
    reviewers = [row(CODE1)]
    assert handback(body(None), [record_comment(reviewers)])["ok"] is True
    unrelated = bullet("The integration test runner was unavailable, so the slow suite was skipped.")
    assert handback(unrelated, [record_comment(reviewers)])["ok"] is True
    assert cd.problems(rec(reviewers), unrelated) == []


# --- 7: fail closed on an unreadable record --------------------------------------------------------------

def test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_marker():
    failed = {"ok": False, "reason": "review-record-missing"}
    with pytest.raises(cd.Unreadable, match="review-record-missing"):
        cd.problems(failed, bullet("Calibration was stripped from the reviewers."))
    with pytest.raises(cd.Unreadable, match="review-record-missing"):
        cd.problems(failed, body(None))
    with pytest.raises(cd.Unreadable, match="did not succeed"):
        cd.problems(None, body(None))
    with pytest.raises(cd.Unreadable, match="the JSON does not parse"):
        cd.problems({"ok": False, "reason": "x", "detail": "the JSON does not parse"}, body(None))


def test_7b_a_missing_record_refuses_review_record_unreadable_naming_the_record():
    result = handback(bullet(mark(CODE1, "core.md")), [comment("chatter")])
    assert result["ok"] is False and result["reason"] == "review-record-unreadable"
    assert "the latest review record on PR 42" in result["detail"]


@pytest.mark.parametrize("reviewers", ["not a list", None, [CODE1], [row(CODE1), "not a dict"]])
def test_7c_a_malformed_reviewers_list_with_a_marker_refuses_review_record_unreadable(reviewers):
    pr_body = bullet(mark(CODE1, "core.md"))
    with pytest.raises(cd.Unreadable, match="reviewers list is missing or malformed"):
        cd.problems({"ok": True, "reviewers": reviewers}, pr_body)
    result = handback(pr_body, [record_comment(reviewers)])
    assert result["ok"] is False and result["reason"] == "review-record-unreadable"
    assert "reviewers list is missing or malformed" in result["detail"]


def test_7c_a_malformed_reviewers_list_with_no_marker_is_not_read():
    assert cd.problems({"ok": True, "reviewers": "not a list"}, body(None)) == []
    found = cd.problems({"ok": True, "reviewers": "not a list"}, bullet("Calibration was stripped from the reviewers."))
    assert reasons(found) == [cd.REASON_UNMARKED]


# --- the unmarked rule: a mention of calibration outside a valid marker -----------------------------------------

def test_an_unmarked_mention_refuses_whatever_the_record_says():
    pr_body = bullet("Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.")
    unread = [row(CODE1, NOT_READ), row(SEC1, NOT_READ)]
    result = handback(pr_body, [record_comment(unread)])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
    assert cd.MARKER_FORM in result["detail"]


def test_a_marker_does_not_cover_unmarked_prose_beside_it():
    pr_body = bullet(mark(CODE1, "core.md") + " and the security reviewer lacked review-crew.md.")
    reviewers = [row(CODE1, NOT_READ)]
    assert reasons(cd.problems(rec(reviewers), pr_body)) == [cd.REASON_UNMARKED]
    result = handback(pr_body, [record_comment(reviewers)])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"


def test_marker_prose_without_a_mention_passes():
    pr_body = bullet(mark(CODE1, "core.md, review-crew.md") + " — its engine dispatch held neither file.")
    reviewers = [row(CODE1, NOT_READ)]
    assert cd.problems(rec(reviewers), pr_body) == []
    assert handback(pr_body, [record_comment(reviewers)])["ok"] is True


@pytest.mark.parametrize("text", [
    mark(CODE1, "foo.md"),
    mark(CODE1, ""),
    mark(CODE1, "core.md, core.md"),
    mark(CODE1, "claude.md"),
    "`calibration-lacked[%s]:core.md`" % CODE1,
    mark(CODE1, "core.md,  review-crew.md"),
    mark("", "core.md"),
    "calibration-lacked[%s]: core.md" % CODE1,
], ids=["unknown-file", "empty-list", "duplicate-file", "lowercase-claude", "no-space-after-colon",
        "two-spaces-after-comma", "empty-brackets", "no-backticks"])
def test_a_malformed_marker_is_unmarked(text):
    pr_body = bullet(text)
    reviewers = [row(CODE1, NOT_READ)]
    assert reasons(cd.problems(rec(reviewers), pr_body)) == [cd.REASON_UNMARKED]
    result = handback(pr_body, [record_comment(reviewers)])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"


def test_the_doctrine_example_is_the_module_constant():
    doctrine = HANDBACK_MD.read_text(encoding="utf-8")
    assert cd.MARKER_EXAMPLE in doctrine and cd.MARKER_FORM in doctrine
    pr_body = bullet(cd.MARKER_EXAMPLE + " — its engine dispatch held neither file.")
    reviewers = [row("code-reviewer:s1 (round 1)", NOT_READ)]
    assert cd.problems(rec(reviewers), pr_body) == []
    assert handback(pr_body, [record_comment(reviewers)])["ok"] is True


def test_the_fix_sentence_spells_the_marker_from_the_constants():
    assert cd.MARKER_FORM in cd.FIX and cd.MARKER_EXAMPLE in cd.FIX
    assert cd.MARKER_FORM == "`calibration-lacked[<row name>]: <files>`"
    assert cd.MARKER_EXAMPLE == "`calibration-lacked[code-reviewer:s1 (round 1)]: core.md, review-crew.md`"


# --- the unmarked rule's wording: the claim test is unchanged -----------------------------------------------

def test_a_lack_in_another_clause_is_not_a_calibration_mention():
    record = rec([row(CODE1), row(SEC1)])
    text = "The code reviewer read core.md and review-crew.md, but the integration test runner was unavailable."
    assert cd.problems(record, bullet(text)) == []


@pytest.mark.parametrize("text", [
    "The code reviewer read core.md and the browser was missing.",
    "The code reviewer read core.md because the browser was unavailable.",
    "The integration-test runner was unavailable, so the code reviewer used core.md and review-crew.md for a static"
    " review.",
    "The integration-test runner was unavailable and the code reviewer read core.md instead.",
    "No tests ran and the code reviewer consulted core.md.",
    "The sanitized view did not remove core.md from the code reviewer.",
    "The code reviewer was not only missing core.md but also review-crew.md.",
])
def test_a_mixed_clause_is_refused_by_the_ruling(text):
    assert reasons(cd.problems(rec([row(CODE1)]), bullet(text))) == [cd.REASON_UNMARKED]
    result = handback(bullet(text), [record_comment([row(CODE1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"
    assert "in its own bullet or sentence" in result["detail"]


@pytest.mark.parametrize("pr_body", [
    body("- [harmless] The browser was missing.\n- [harmless] The code reviewer read core.md.\n"),
    body("- [harmless] The browser was unavailable.\n- [harmless] The code reviewer read core.md.\n"),
    body("- [harmless] The integration-test runner was unavailable.\n"
         "- [harmless] The code reviewer used core.md and review-crew.md for a static review.\n"),
    body("- [harmless] No tests ran.\n- [harmless] The code reviewer consulted core.md.\n"),
    body("- [harmless] The browser was missing. The code reviewer read its calibration in full.\n"),
    body("- [harmless] The browser was missing; the code reviewer read its calibration in full.\n"),
])
def test_the_split_rewording_passes(pr_body):
    assert handback(pr_body, [record_comment([row(CODE1)])])["ok"] is True
    assert cd.problems(rec([row(CODE1)]), pr_body) == []


@pytest.mark.parametrize("text", [
    "The code reviewer ran without core.md.",
    "core.md was stripped from the code reviewer's view.",
    "The code reviewer did not have review-crew.md.",
    "The sanitized view stripped core.md from the code reviewer.",
    "The sanitized view removed the project's review-crew.md from the code reviewer.",
    "The code reviewer had no calibration.",
    "The code reviewer had no access to CLAUDE.md.",
    "`core.md` and `review-crew.md` were withheld from the code reviewer.",
    "The code reviewer lacked the required core.md.",
    "Calibration for the code reviewer was stripped.",
    "core.md was still missing for the code reviewer.",
    "The code reviewer ran without project calibration.",
])
def test_a_lack_that_describes_the_calibration_is_a_mention(text):
    assert reasons(cd.problems(rec([row(CODE1)]), bullet(text))) == [cd.REASON_UNMARKED]


# --- the mention word is negation, after formatting is normalised ----------------------------------------------

@pytest.mark.parametrize("text", [
    "The code reviewer could not read core.md.",
    "The code reviewer couldn't read core.md.",
    "The code reviewer did not read core.md.",
    "The reviewers never read core.md or review-crew.md.",
    "core.md was not read by the code reviewer.",
    "core.md was not loaded for the code reviewer.",
    "The view did not include core.md or review-crew.md.",
    "core.md was not provided to the review seats.",
    "core.md was not supplied to the reviewers.",
    "core.md wasn't available to the reviewers.",
    "core.md isn't available inside the sanitized view.",
    "Calibration never reached the review seats.",
    "Calibration did not reach the reviewers.",
    "core.md was excluded from the code reviewer's view.",
    "core.md was hidden from every reviewer.",
    "The sanitized view dropped CLAUDE.md for every seat.",
    "CLAUDE.md was omitted from the reviewers' view.",
    "core.md was deleted from the reviewers' worktree.",
    "The reviewers were denied access to core.md.",
    "core.md was inaccessible to the reviewers.",
    "Calibration was gone from the sanitized view.",
    "The reviewers saw none of the project's calibration.",
    "The reviewers worked with zero calibration.",
    "The code reviewer didn’t have core.md.",
    "The code reviewer didn’t get its calibration.",
    "The review seats ran uncalibrated.",
    "The reviewers were not calibrated for this project.",
    "core.md was _stripped_ from the code reviewer.",
    "_core.md_ was stripped from the code reviewer.",
    "__Calibration__ was stripped from every seat.",
    "core.md was __missing__ for every seat.",
    "The reviewers lacked the project notes.",
    "The review seats ran without the project's conventions file.",
    "The code and security reviewers ran without the project's instructions file.",
    "The code reviewer read core.md but not review-crew.md.",
    "The reviewers lack core.md.",
    "The sanitized view will strip core.md from the reviewers.",
    "The view will withhold core.md from the reviewers.",
    "core.md was not available to the reviewers.",
    "core.md was left  out of the reviewers' view.",
])
def test_vet_825_sentences_refuse(text):
    assert reasons(cd.problems(rec([row(CODE1), row(SEC1)]), bullet(text))) == [cd.REASON_UNMARKED]
    result = handback(bullet(text), [record_comment([row(CODE1), row(SEC1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"


# --- 12: rows that never contradict --------------------------------------------------------------------

@pytest.mark.parametrize("only", [
    {"name": CODE1, "ran": "reported-by-session"},
    {"name": CODE1, "ran": "not-run"},
    {"name": CODE1, "ran": "engine-record"},  # no calibrationRead key
    {"name": CODE1, "ran": "engine-record", "calibrationRead": "not a list"},
    {"name": CODE1, "ran": "reported-by-session", "calibrationRead": cal()},  # session-reported, carries read grades
])
def test_a_row_with_no_measured_calibration_is_never_contradicted(only):
    for pr_body in (bullet(mark(CODE1, ALL_FILES)), bullet(mark("*", "core.md"))):
        assert cd.problems(rec([only]), pr_body) == []
        assert handback(pr_body, [record_comment([only])])["ok"] is True


# --- 13: the refusal detail ---------------------------------------------------------------------------------

def test_describe_carries_the_record_url_and_the_fix_sentence():
    found = cd.problems(rec([row(CODE1)]), bullet(mark(CODE1, "core.md")))
    text = cd.describe(found, "https://x/c/900")
    assert "https://x/c/900" in text and text.endswith(cd.FIX)
    assert "its marker for %s contradicts https://x/c/900: %s%s" % (CODE1, CODE1, READ_LINE) in text
    assert "the latest review record" in cd.describe(found, None)
    assert cd.REASON == "calibration-disclosure-contradicted"
    assert cd.REASON_UNKNOWN_SEAT == "calibration-disclosure-unknown-seat"
    assert cd.REASON_UNMARKED == "calibration-disclosure-unmarked"
    long_unmarked = [{"reason": cd.REASON_UNMARKED, "degradation": "x" * 500, "detail": "mentions calibration"}]
    assert "x" * 200 in cd.describe(long_unmarked, "u") and "x" * 201 not in cd.describe(long_unmarked, "u")


def test_describe_names_the_row_text_and_every_row_of_an_unknown_seat():
    found = cd.problems(rec([row(CODE1), row(SEC1)]), bullet(mark("nobody (round 3)", "core.md")))
    text = cd.describe(found, "https://x/c/900")
    assert ("its marker names nobody (round 3), which is not a row of https://x/c/900; its rows are: %s; %s"
            % (CODE1, SEC1)) in text
    assert text.endswith(cd.FIX)


# --- 14: the leftover check still runs first ------------------------------------------------------------

def test_the_leftover_check_still_refuses_first():
    left = {"id": "f-1", "title": "the retry loop never backs off", "outcome": "left-for-owner"}
    pr_body = bullet("Calibration was stripped from the reviewers.")
    result = handback(pr_body, [record_comment([row(CODE1)], findings=[left], left=["f-1"])])
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted"


def test_a_harmless_label_is_checked_too():
    pr_body = body("- [harmless] Calibration was stripped from the reviewers.\n")
    assert handback(pr_body, [record_comment([row(CODE1)])])["reason"] == "calibration-disclosure-unmarked"


# --- doctrine-prescribed disclosures are not calibration mentions (vet 826) ----------------------------------------

DOCTRINE = [
    ("costly", "The review owes the owner a direct look at the change, and this project declares no show-it surface."
               " The entry point is `none` (core.md has no `## Show-it surface`), so the owner reads the sample record"
               " under How to see it instead of opening a live page."),
    ("costly", "There is no live view for you to open: the project's calibration declares no show-it surface, so"
               ' "How to see it" shows rendered record lines, not a page.'),
    ("harmless", "The main merge at `05bed485` landed after session 6 closed. It brings only main's own reviewed content"
                 " (#2322), merged with no conflict, and CI and the calibrated verify ran on it."),
    ("harmless", "The pre-code brief check ran on codex's second allowlisted model, `gpt-6-astra`/high, not the"
                 " calibrated `gpt-6.1-sol`/xhigh, because the calibrated model was at capacity (a terminal forfeit,"
                 " twice)."),
]
CLAIM = " and the code reviewer lacked core.md"
# the insertion point is inside the clause that holds the exempt phrase, just before that clause's closing punctuation
ANCHORS = ["show-it surface.", "show-it surface, so", "ran on it.", "twice)."]


@pytest.mark.parametrize("label, text", DOCTRINE)
def test_doctrine_prescribed_disclosures_pass(label, text):
    record = rec([row(CODE1), row(SEC1)])
    assert cd.problems(record, bullet(text, label)) == []
    assert handback(bullet(text, label), [record_comment([row(CODE1), row(SEC1)])])["ok"] is True


@pytest.mark.parametrize("pair, anchor", list(zip(DOCTRINE, ANCHORS)))
def test_doctrine_disclosure_with_a_real_claim_still_refuses(pair, anchor):
    label, text = pair
    assert text.count(anchor) == 1
    claimed = text.replace(anchor, _insert(anchor))
    record = rec([row(CODE1), row(SEC1)])
    assert reasons(cd.problems(record, bullet(claimed, label))) == [cd.REASON_UNMARKED]
    result = handback(bullet(claimed, label), [record_comment([row(CODE1), row(SEC1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"


def _insert(anchor):
    """``anchor`` with the real claim spliced in before its closing punctuation: the period, or the comma of ", so"."""
    for end in (", so", "."):
        if anchor.endswith(end):
            return anchor[:-len(end)] + CLAIM + end
    raise AssertionError(anchor)


# --- the exemption never lets a real lack claim through (vet 827) -----------------------------------------------

@pytest.mark.parametrize("text", [
    "The code reviewer was not calibrated (gpt-6.1-sol ran bare).",
    "The reviewers were not calibrated 2 rounds in a row.",
    "The calibrated 3 files were stripped from the code reviewer.",
])
def test_an_exemption_never_lets_a_real_lack_claim_through(text):
    record = rec([row(CODE1), row(SEC1)])
    assert reasons(cd.problems(record, bullet(text))) == [cd.REASON_UNMARKED]
    result = handback(bullet(text), [record_comment([row(CODE1), row(SEC1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-unmarked"


@pytest.mark.parametrize("text", [
    "The entry point is `none` (a `core.md` with no `## Show-it surface`), so the owner reads the sample record.",
    "The calibrated-command test fixture uses this repo's real verify command, with the home directory and project id"
    " replaced, so a private path is not published in a public repo.",
])
def test_more_doctrine_wordings_pass(text):
    record = rec([row(CODE1), row(SEC1)])
    assert cd.problems(record, bullet(text)) == []
    assert handback(bullet(text), [record_comment([row(CODE1), row(SEC1)])])["ok"] is True


# --- 15: the sanitized view's notice ----------------------------------------------------------------------

def test_the_sanitized_view_notice_says_calibration_read_is_the_measurement():
    notice = sv.sanitized_view_notice({"stripped": ["CLAUDE.md"], "headSha": "a" * 40})
    assert "Stripped agent/IDE config names: CLAUDE.md (1 path(s) removed)" in notice
    assert "calibrationRead is the measurement" in notice
