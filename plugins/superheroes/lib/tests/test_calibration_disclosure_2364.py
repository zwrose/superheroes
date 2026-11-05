"""#2364: a PR body's Disclosed degradations never says a review seat lacked its calibration while the latest review
record grades that seat's calibrationRead read. One rule (calibration_disclosure), one caller (vet_slot handback --pr).
No real gh: every call is faked."""
import json
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

FIX = ("Read each seat's calibrationRead in the review record and disclose a calibration degradation only for a seat"
       " graded not-read or unknown, or whose order named no calibration, naming that seat; a disclosure that names no"
       " seat covers every seat. Put an unrelated lack (a browser, a tool, a runner) in its own bullet or sentence,"
       " apart from any mention of calibration.")


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


def seats(hits):
    return [[s["name"] for s in h["seats"]] for h in hits]


CODE1, SEC1, PRE1 = "code-reviewer (round 1)", "security-reviewer (round 1)", "premortem-reviewer (round 1)"


# --- 1, 2: the incident, through handback ------------------------------------------------------------

def test_dod_headline_stripped_calibration_the_record_grades_read_is_refused():
    pr_body = bullet("Calibration (CLAUDE.md, .claude) was stripped from the reviewers by the sanitized view.")
    result = handback(pr_body, [record_comment([row(CODE1), row(SEC1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
    assert CODE1 in result["detail"] and SEC1 in result["detail"]
    assert "read its calibration" in result["detail"]


def test_incident_wording_names_all_three_seats():
    pr_body = bullet("The code, security and failure-mode reviewers judged without this project's threat model and"
                     " focus hints.")
    result = handback(pr_body, [record_comment([row(CODE1), row(SEC1), row(PRE1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
    assert all(name in result["detail"] for name in (CODE1, SEC1, PRE1))


# --- 3, 4, 5: a seat the record does not grade read ----------------------------------------------------

@pytest.mark.parametrize("state", ["not-read", "unknown"])
def test_disclosure_naming_a_seat_not_graded_read_passes(state):
    reviewers = [row(CODE1, cal(crew=state)), row(SEC1)]
    assert handback(bullet("code-reviewer (round 1) lacked review-crew.md."), [record_comment(reviewers)])["ok"] is True
    # the same words about the seat that did read it are refused
    other = handback(bullet("security-reviewer (round 1) lacked review-crew.md."), [record_comment(reviewers)])
    assert other["reason"] == "calibration-disclosure-contradicted" and SEC1 in other["detail"]


def test_a_seat_whose_order_named_no_calibration_may_be_named():
    reviewers = [row(CODE1, []), row(SEC1)]
    assert handback(bullet("The code reviewer had no calibration."), [record_comment(reviewers)])["ok"] is True
    assert cd.contradicted(rec(reviewers), bullet("The security reviewer had no calibration."))


# --- 6: no calibration disclosure ------------------------------------------------------------------------

def test_no_calibration_disclosure_passes():
    reviewers = [row(CODE1)]
    assert handback(body(None), [record_comment(reviewers)])["ok"] is True
    unrelated = bullet("The integration test runner was unavailable, so the slow suite was skipped.")
    assert handback(unrelated, [record_comment(reviewers)])["ok"] is True
    assert cd.contradicted(rec(reviewers), unrelated) == []


# --- 7: fail closed on an unreadable record --------------------------------------------------------------

def test_7a_a_record_read_that_did_not_succeed_raises_even_with_no_claim():
    failed = {"ok": False, "reason": "review-record-missing"}
    with pytest.raises(cd.Unreadable, match="review-record-missing"):
        cd.contradicted(failed, bullet("Calibration was stripped from the reviewers."))
    with pytest.raises(cd.Unreadable, match="review-record-missing"):
        cd.contradicted(failed, body(None))
    with pytest.raises(cd.Unreadable, match="did not succeed"):
        cd.contradicted(None, body(None))
    with pytest.raises(cd.Unreadable, match="the JSON does not parse"):
        cd.contradicted({"ok": False, "reason": "x", "detail": "the JSON does not parse"}, body(None))


def test_7b_a_missing_record_refuses_review_record_unreadable_naming_the_record():
    result = handback(bullet("Calibration was stripped from the reviewers."), [comment("chatter")])
    assert result["ok"] is False and result["reason"] == "review-record-unreadable"
    assert "the latest review record on PR 42" in result["detail"]


@pytest.mark.parametrize("reviewers", ["not a list", None, [CODE1], [row(CODE1), "not a dict"]])
def test_7c_a_malformed_reviewers_list_with_a_claim_refuses_review_record_unreadable(reviewers):
    pr_body = bullet("Calibration was stripped from the reviewers.")
    with pytest.raises(cd.Unreadable, match="reviewers list is missing or malformed"):
        cd.contradicted({"ok": True, "reviewers": reviewers}, pr_body)
    result = handback(pr_body, [record_comment(reviewers)])
    assert result["ok"] is False and result["reason"] == "review-record-unreadable"
    assert "reviewers list is missing or malformed" in result["detail"]


def test_7c_a_malformed_reviewers_list_with_no_claim_is_not_read():
    assert cd.contradicted({"ok": True, "reviewers": "not a list"}, body(None)) == []


# --- 8 to 11: which seats and which files a claim reaches -------------------------------------------------

def test_f1_opposite_grades_on_one_seat_follow_the_files_the_claim_names():
    record = rec([row(CODE1, cal(core="read", crew="not-read"))])
    assert seats(cd.contradicted(record, bullet("The reviewers judged without the threat model."))) == [[CODE1]]
    assert cd.contradicted(record, bullet("The reviewers judged without the focus hints.")) == []


def test_f2_a_claim_naming_no_seat_covers_every_seat_and_names_the_contradicted_ones():
    record = rec([row("code-reviewer (round 1)"), row("security-reviewer (round 1)", cal(core="unknown"))])
    hits = cd.contradicted(record, bullet("Calibration was missing for the reviewers."))
    assert seats(hits) == [[CODE1]]
    assert hits[0]["seats"][0]["line"] == CODE1 + ": read its calibration: core.md, review-crew.md, CLAUDE.md"
    result = handback(bullet("Calibration was missing for the reviewers."), [record_comment(record["reviewers"])])
    assert result["reason"] == "calibration-disclosure-contradicted"
    assert CODE1 in result["detail"] and SEC1 not in result["detail"]


def test_f3_the_most_specific_seat_term_wins():
    record = rec([row("code-reviewer (round 1)", cal(crew="unknown")), row("code-reviewer (round 2)")])
    assert seats(cd.contradicted(record, bullet("code-reviewer (round 2) lacked review-crew.md"))) == [
        ["code-reviewer (round 2)"]]
    assert cd.contradicted(record, bullet("the code reviewer lacked review-crew.md")) == []


def test_f3_an_explicit_seat_that_did_not_run_never_widens_to_the_seats_of_its_lens():
    record = rec([row("code-reviewer (round 1)", ran="not-run"), row("code-reviewer (round 2)")])
    assert cd.contradicted(record, bullet("code-reviewer (round 1) lacked review-crew.md")) == []
    assert seats(cd.contradicted(record, bullet("the code reviewer lacked review-crew.md"))) == [
        ["code-reviewer (round 2)"]]


def test_f3_a_slice_seat_is_named_by_its_slice():
    record = rec([row("code-reviewer:api (round 1)", cal(crew="unknown")), row("code-reviewer:ui (round 1)")])
    assert cd.contradicted(record, bullet("code-reviewer:api lacked review-crew.md")) == []
    assert seats(cd.contradicted(record, bullet("code-reviewer:ui lacked review-crew.md"))) == [
        ["code-reviewer:ui (round 1)"]]


def test_a_seat_named_in_one_clause_is_not_checked_against_another_clauses_files():
    record = rec([row(CODE1, cal(core="read", crew="read", claude="read")),
                  row(SEC1, cal(core="read", crew="unknown", claude="read"))])
    text = "code-reviewer (round 1) lacked core.md; security-reviewer (round 1) lacked review-crew.md."
    assert seats(cd.contradicted(record, bullet(text))) == [[CODE1]]


def test_f4_a_lack_in_another_clause_is_not_a_calibration_claim():
    record = rec([row(CODE1), row(SEC1)])
    text = "The code reviewer read core.md and review-crew.md, but the integration test runner was unavailable."
    assert cd.contradicted(record, bullet(text)) == []


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
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]
    result = handback(bullet(text), [record_comment([row(CODE1)])])
    assert result["ok"] is False and result["reason"] == "calibration-disclosure-contradicted"
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
    assert cd.contradicted(rec([row(CODE1)]), pr_body) == []


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
def test_a_lack_that_describes_the_calibration_is_a_claim(text):
    assert seats(cd.contradicted(rec([row(CODE1)]), bullet(text))) == [[CODE1]]


# --- 12: rows that never contradict --------------------------------------------------------------------

@pytest.mark.parametrize("only", [
    {"name": CODE1, "ran": "reported-by-session"},
    {"name": CODE1, "ran": "not-run"},
    {"name": CODE1, "ran": "engine-record"},  # no calibrationRead key
    {"name": CODE1, "ran": "engine-record", "calibrationRead": "not a list"},
])
def test_a_row_with_no_measured_calibration_is_never_contradicted(only):
    pr_body = bullet("Calibration was stripped from the reviewers.")
    assert cd.contradicted(rec([only]), pr_body) == []
    assert handback(pr_body, [record_comment([only])])["ok"] is True


# --- 13: the refusal detail ---------------------------------------------------------------------------------

def test_describe_carries_the_record_url_and_the_fix_sentence():
    hits = cd.contradicted(rec([row(CODE1)]), bullet("Calibration was stripped from the reviewers."))
    text = cd.describe(hits, "https://x/c/900")
    assert "https://x/c/900" in text and text.endswith(FIX) and CODE1 in text
    assert "the latest review record" in cd.describe(hits, None)
    assert cd.REASON == "calibration-disclosure-contradicted"
    long_hit = [{"degradation": "x" * 500, "seats": [{"name": "a", "line": "a: read its calibration: core.md"}]}]
    assert "x" * 200 in cd.describe(long_hit, "u") and "x" * 201 not in cd.describe(long_hit, "u")


# --- 14: the leftover check still runs first ------------------------------------------------------------

def test_the_leftover_check_still_refuses_first():
    left = {"id": "f-1", "title": "the retry loop never backs off", "outcome": "left-for-owner"}
    pr_body = bullet("Calibration was stripped from the reviewers.")
    result = handback(pr_body, [record_comment([row(CODE1)], findings=[left], left=["f-1"])])
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted"


def test_a_harmless_label_is_checked_too():
    pr_body = body("- [harmless] Calibration was stripped from the reviewers.\n")
    assert handback(pr_body, [record_comment([row(CODE1)])])["reason"] == "calibration-disclosure-contradicted"


# --- 15: the sanitized view's notice ----------------------------------------------------------------------

def test_the_sanitized_view_notice_says_calibration_read_is_the_measurement():
    notice = sv.sanitized_view_notice({"stripped": ["CLAUDE.md"], "headSha": "a" * 40})
    assert "Stripped agent/IDE config names: CLAUDE.md (1 path(s) removed)" in notice
    assert "calibrationRead is the measurement" in notice
