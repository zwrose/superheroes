"""#2280: a PR is never marked ready, and its vet slot never written READY, while a finding the latest review record
leaves for the owner is not named, by record id and title, under What we're accepting. One rule (leftover_accepting),
two callers (vet_slot handback --pr and vet_slot write). No real gh: every call is faked."""
import json
from types import SimpleNamespace

import pytest

import leftover_accepting as la
import review_record as rr
import vet_slot as vs

REPO = "owner/example"
PR = 42
VIEW = ("gh", "api", "repos/owner/example/pulls/42")
COMMENTS = "repos/owner/example/issues/42/comments?per_page=100&page="
USER = ("gh", "api", "user", "-q", ".login")

F1 = {"id": "f-1", "title": "the retry loop never backs off", "outcome": "left-for-owner"}
F2 = {"id": "f-2", "title": "a stale cache entry survives restart", "outcome": "left-for-owner"}
FIXED = {"id": "f-3", "title": "typo in the help text", "outcome": "fixed"}

ACCEPT_BOTH = ("- f-1 the retry loop never backs off: merging accepts slower recovery.\n"
               "- f-2 a stale cache entry survives restart: merging accepts one stale read.\n")
ACCEPT_ONLY_F1 = "- f-1 the retry loop never backs off: merging accepts slower recovery.\n"
# the paraphrase that held three C1 layers: the title is right, the record id is absent
ACCEPT_PARAPHRASED = ("- f-1 the retry loop never backs off: merging accepts slower recovery.\n"
                      "- a stale cache entry survives restart: merging accepts one stale read.\n")


def body(accepting):
    return ("Closes #1.\n\n## What's changing, and why\n\nA change.\n\n## What we're accepting\n\n" + accepting
            + "\n## How to see it\n\nN/A — nothing to see.\n\n## Advisor vet\n<!-- superheroes:advisor-vet -->\n"
            "old slot text\n\n<!-- superheroes:build-record -->\n<details><summary>Build record</summary>\n\n"
            "<!-- superheroes:followups none -->\n</details>\n")


def record_comment(findings, left=None, cid=900):
    rec = {"schema": rr.RECORD_SCHEMA, "findings": findings,
           "leftForOwner": [f["id"] for f in findings if f["outcome"] == "left-for-owner"] if left is None else left}
    text = (rr.MARKER + "\n\n<details><summary>Record</summary>\n\n```json\n" + json.dumps(rec)
            + "\n```\n</details>\n")
    return comment(text, cid=cid, login="builder")


def comment(text, cid=1, login="advisor"):
    return {"id": cid, "html_url": "https://x/c/%d" % cid, "body": text, "created_at": "2026-10-31T10:00:00Z",
            "user": {"login": login}}


RECEIPT = comment("<!-- superheroes:vet-receipt -->\n**Vet 1: READY.**\n<!-- superheroes:dispositions none -->\n")


class Fake:
    def __init__(self, pr_body, comments):
        self.pr_body, self.comments, self.edited, self.calls = pr_body, comments, [], []

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
        if argv[:3] == ["gh", "pr", "edit"]:
            with open(argv[7], encoding="utf-8") as handle:
                self.edited.append(handle.read())
            self.pr_body = self.edited[-1]
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError("unexpected argv %r" % (argv,))


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def handback(pr_body, comments):
    return vs.run_verb("handback", PR, REPO, run=Fake(pr_body, comments))


def write(pr_body, comments, tmp_path, verdict="READY"):
    slot = tmp_path / "slot.md"
    slot.write_text("**Verdict: %s** · %s\n\nOwner half.\n" % (verdict, "a" * 40), encoding="utf-8")
    fake = Fake(pr_body, comments)
    return vs.run_verb("write", PR, REPO, slot_file=str(slot), run=fake), fake


# --- the one rule ----------------------------------------------------------------------------------

def read_ok(*findings, left=None):
    return rr.read(PR, REPO, readers={"list_comments": lambda _p, _r: [
        {"id": 900, "author": "b", "body": record_comment(list(findings), left)["body"], "url": "u"}]})


def test_all_ids_present_passes():
    assert la.missing(read_ok(F1, F2, FIXED), body(ACCEPT_BOTH)) == []


def test_one_id_missing_is_named_with_its_title():
    assert la.missing(read_ok(F1, F2), body(ACCEPT_ONLY_F1)) == [{"id": "f-2", "title": F2["title"]}]


def test_paraphrase_with_the_title_but_no_id_is_missing():
    assert la.missing(read_ok(F1, F2), body(ACCEPT_PARAPHRASED)) == [{"id": "f-2", "title": F2["title"]}]


def test_id_without_its_title_is_missing():
    assert la.missing(read_ok(F1), body("- f-1 a slow retry: merging accepts it.\n")) == [
        {"id": "f-1", "title": F1["title"]}]


def test_id_and_title_in_different_lines_is_missing():
    split = "- f-1 is accepted.\n- the retry loop never backs off, as said.\n"
    assert [g["id"] for g in la.missing(read_ok(F1), body(split))] == ["f-1"]


def test_id_inside_a_longer_id_does_not_name_it():
    longer = "- f-10 the retry loop never backs off: merging accepts it.\n"
    assert [g["id"] for g in la.missing(read_ok(F1), body(longer))] == ["f-1"]


def test_id_outside_what_were_accepting_does_not_name_it():
    elsewhere = body("None\n").replace("A change.", "A change. f-1 the retry loop never backs off.")
    assert [g["id"] for g in la.missing(read_ok(F1), elsewhere)] == ["f-1"]


def test_record_with_no_leftovers_passes():
    assert la.missing(read_ok(FIXED), body("None\n")) == []


def test_leftover_without_a_title_is_checked_by_id_alone():
    untitled = {"id": "f-4", "outcome": "left-for-owner"}
    assert la.missing(read_ok(untitled), body("- f-4 accepted as is.\n")) == []
    assert [g["id"] for g in la.missing(read_ok(untitled), body("None\n"))] == ["f-4"]


@pytest.mark.parametrize("record", [
    {"ok": False, "reason": "review-record-missing", "detail": "no review record on PR 42"},
    {"ok": False, "reason": "review-record-unreadable", "detail": "the JSON does not parse"},
    None,
    {"ok": True, "findings": []},  # no leftForOwner list at all
    {"ok": True, "leftForOwner": "f-1", "findings": []},
    {"ok": True, "leftForOwner": ["f-1"], "findings": [F2]},  # names no finding left for the owner
    {"ok": True, "leftForOwner": [""], "findings": []},
    {"ok": True, "leftForOwner": [], "findings": ["not a dict"]},
])
def test_unreadable_record_raises_never_passes(record):
    with pytest.raises(la.Unreadable):
        la.missing(record, body(ACCEPT_BOTH))


# --- caller 1: the builder's handback before the ready mark ----------------------------------------

def test_handback_passes_when_every_leftover_is_named():
    assert handback(body(ACCEPT_BOTH), [record_comment([F1, F2])])["ok"] is True


@pytest.mark.parametrize("accepting", [ACCEPT_ONLY_F1, ACCEPT_PARAPHRASED])
def test_handback_refuses_a_missing_or_paraphrased_id_naming_it(accepting):
    result = handback(body(accepting), [record_comment([F1, F2])])
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted"
    assert "f-2 (%s)" % F2["title"] in result["detail"] and "f-1" not in result["detail"]


def test_handback_reads_the_latest_record():
    stale = record_comment([F1, F2], cid=900)
    latest = record_comment([dict(F2, outcome="fixed"), F1], cid=901)
    assert handback(body(ACCEPT_ONLY_F1), [stale, latest])["ok"] is True


def test_handback_refuses_an_unreadable_record():
    broken = comment(rr.MARKER + "\n\n<details>\n\n```json\n{not json\n```\n</details>\n", cid=900)
    result = handback(body(ACCEPT_BOTH), [broken])
    assert result["ok"] is False and result["reason"] == "review-record-unreadable"


def test_handback_refuses_a_missing_record():
    result = handback(body(ACCEPT_BOTH), [comment("chatter")])
    assert result["ok"] is False and result["reason"] == "review-record-unreadable"


def test_handback_passes_a_record_with_no_leftovers():
    assert handback(body("None\n"), [record_comment([FIXED])])["ok"] is True


def test_break_it_handback_without_the_check_passes_a_missing_id(monkeypatch):
    """Removing the check from the handback caller turns the refusal test red."""
    monkeypatch.setattr(vs, "check_leftovers", lambda *a: None)
    assert handback(body(ACCEPT_ONLY_F1), [record_comment([F1, F2])])["ok"] is True


# --- caller 2: the advisor's READY slot write ------------------------------------------------------

def test_write_ready_passes_when_every_leftover_is_named(tmp_path):
    result, fake = write(body(ACCEPT_BOTH), [RECEIPT, record_comment([F1, F2])], tmp_path)
    assert result["ok"] is True and len(fake.edited) == 1


@pytest.mark.parametrize("accepting", [ACCEPT_ONLY_F1, ACCEPT_PARAPHRASED])
def test_write_ready_refuses_a_missing_id_naming_it_and_edits_nothing(accepting, tmp_path):
    result, fake = write(body(accepting), [RECEIPT, record_comment([F1, F2])], tmp_path)
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted"
    assert "f-2 (%s)" % F2["title"] in result["detail"]
    assert fake.edited == []


def test_write_ready_refuses_an_unreadable_record(tmp_path):
    result, fake = write(body(ACCEPT_BOTH), [RECEIPT], tmp_path)
    assert result["reason"] == "review-record-unreadable" and fake.edited == []


def test_write_ready_passes_a_record_with_no_leftovers(tmp_path):
    result, _fake = write(body("None\n"), [RECEIPT, record_comment([FIXED])], tmp_path)
    assert result["ok"] is True


@pytest.mark.parametrize("verdict", ["NOT-READY", "PARKED"])
def test_write_of_a_hold_is_not_checked(verdict, tmp_path):
    """Only READY is held: the advisor can always write the NOT-READY slot that sends the PR back."""
    result, _fake = write(body(ACCEPT_ONLY_F1), [RECEIPT, record_comment([F1, F2])], tmp_path, verdict=verdict)
    assert result["ok"] is True


def test_break_it_write_without_the_check_writes_ready_over_a_missing_id(monkeypatch, tmp_path):
    """Removing the check from the write caller turns the refusal test red."""
    monkeypatch.setattr(vs, "check_leftovers", lambda *a: None)
    result, fake = write(body(ACCEPT_ONLY_F1), [RECEIPT, record_comment([F1, F2])], tmp_path)
    assert result["ok"] is True and len(fake.edited) == 1


def test_both_callers_reach_the_one_rule(monkeypatch, tmp_path):
    """One function, two callers: both go through leftover_accepting.missing, and vet_slot holds no copy."""
    seen = []
    real = la.missing
    monkeypatch.setattr(la, "missing", lambda rec, b: seen.append(b) or real(rec, b))
    handback(body(ACCEPT_BOTH), [record_comment([F1, F2])])
    write(body(ACCEPT_BOTH), [RECEIPT, record_comment([F1, F2])], tmp_path)
    assert len(seen) == 2


# --- review round 1 (codex light-lane seat) fixes ---------------------------------------------------

def test_id_and_title_only_inside_an_html_comment_are_not_named():
    """code-001: GitHub renders `None` alone; the id and title in the comment never reach the owner."""
    hidden = body("- None <!-- f-1 the retry loop never backs off -->\n")
    assert [g["id"] for g in la.missing(read_ok(F1), hidden)] == ["f-1"]
    assert handback(hidden, [record_comment([F1])])["reason"] == "leftover-not-accepted"


def test_visible_text_beside_a_comment_still_names_it():
    shown = body("- f-1 the retry loop never backs off <!-- builder note -->: merging accepts it.\n")
    assert la.missing(read_ok(F1), shown) == []


def test_two_findings_sharing_an_id_are_each_checked_with_their_own_title(tmp_path):
    """code-002: the second finding's title is required too, not only the first's."""
    twin = dict(F2, id="f-1")
    assert la.missing(read_ok(F1, twin), body(ACCEPT_ONLY_F1)) == [{"id": "f-1", "title": F2["title"]}]
    both = body(ACCEPT_ONLY_F1 + "- f-1 a stale cache entry survives restart: merging accepts it.\n")
    assert la.missing(read_ok(F1, twin), both) == []
    result, fake = write(body(ACCEPT_ONLY_F1), [RECEIPT, record_comment([F1, twin], left=["f-1", "f-1"])], tmp_path)
    assert result["reason"] == "leftover-not-accepted" and fake.edited == []


def test_ready_detection_reads_the_canonical_verdict_form(monkeypatch):
    """code-003: READY is read from rubric/vet-verdict-form.json through stack_check, its one home."""
    assert vs.reads_ready("**Verdict: READY** · " + "a" * 40) is True
    assert vs.reads_ready("\n\n**Verdict: READY** · x\n") is True
    assert vs.reads_ready("**Verdict: NOT-READY** · x") is False
    assert vs.reads_ready("**Verdict: PARKED** · x") is False
    form = (" · ", [("**Vet: GO**", "READY"), ("**Vet: HOLD**", "NOT-READY"), ("**Vet: PARK**", "PARKED")])
    monkeypatch.setattr(vs.stack_check, "_load_vet_verdict_form", lambda: (form, None))
    assert vs.reads_ready("**Vet: GO** · x") is True
    assert vs.reads_ready("**Verdict: READY** · x") is False


def test_an_unreadable_verdict_form_runs_the_check(monkeypatch):
    monkeypatch.setattr(vs.stack_check, "_load_vet_verdict_form", lambda: (None, "missing"))
    assert vs.reads_ready("**Verdict: NOT-READY** · x") is True


# --- review round 2 fixes ---------------------------------------------------------------------------

def test_a_comment_spanning_lines_hides_the_id_and_title(tmp_path):
    """code-004: the opener sits on the line before; GitHub renders only `None`."""
    hidden = body("<!--\nf-1 the retry loop never backs off --> None\n")
    assert [g["id"] for g in la.missing(read_ok(F1), hidden)] == ["f-1"]
    assert handback(hidden, [record_comment([F1])])["reason"] == "leftover-not-accepted"
    result, fake = write(hidden, [RECEIPT, record_comment([F1])], tmp_path)
    assert result["reason"] == "leftover-not-accepted" and fake.edited == []


def test_a_comment_opener_inside_a_code_span_is_shown_text(tmp_path):
    """code-005: a title that quotes the comment opener in a code span can still be named."""
    literal = dict(F1, title="Handle `<!--` literally")
    shown = body("- f-1 Handle `<!--` literally: merging accepts it.\n")
    assert la.missing(read_ok(literal), shown) == []
    assert handback(shown, [record_comment([literal])])["ok"] is True
    result, _fake = write(shown, [RECEIPT, record_comment([literal])], tmp_path)
    assert result["ok"] is True


def test_visible_keeps_fenced_text_and_marker_lines_and_drops_an_unclosed_comment():
    assert la._visible("```\n<!-- shown -->\n```\n") == "```\n<!-- shown -->\n```\n"
    assert la._visible("<!-- superheroes:build-record -->\nx\n") == "<!-- superheroes:build-record -->\nx\n"
    assert la._visible("a <!-- b\nc\nd --> e\nf <!-- g") == "a \n\n e\nf "


# --- review round 3 fixes ---------------------------------------------------------------------------

@pytest.mark.parametrize("accepting", [
    "- None `<!-- f-1 the retry loop never backs off -->``\n",  # code-006: a longer run does not close the span
    "- None \\`<!-- f-1 the retry loop never backs off -->`\n",  # code-006: an escaped backtick opens no span
    "```None```\n- None <!-- f-1 the retry loop never backs off -->\n",  # code-007: an inline run opens no fence
])
def test_a_comment_outside_any_real_code_span_or_fence_stays_hidden(accepting, tmp_path):
    hidden = body(accepting)
    assert [g["id"] for g in la.missing(read_ok(F1), hidden)] == ["f-1"]
    assert handback(hidden, [record_comment([F1])])["reason"] == "leftover-not-accepted"
    result, fake = write(hidden, [RECEIPT, record_comment([F1])], tmp_path)
    assert result["reason"] == "leftover-not-accepted" and fake.edited == []


def test_an_escaped_comment_opener_is_shown_text():
    assert la._visible("a \\<!-- b --> c\n") == "a \\<!-- b --> c\n"


def test_a_double_backtick_span_holding_a_single_backtick_is_one_span():
    assert la._visible("x ``a ` <!-- b --> c`` y\n") == "x ``a ` <!-- b --> c`` y\n"


def test_ready_write_checks_the_body_it_will_publish(tmp_path):
    """code-008: an id named only in the old slot text, which the write replaces, does not count."""
    shaped = ("Closes #1.\n\n## What we're accepting\n\nNone\n\n<!-- superheroes:advisor-vet -->\n"
              "- f-1 the retry loop never backs off: merging accepts it.\n\n<!-- superheroes:build-record -->\n"
              "<details><summary>Build record</summary>\n\n<!-- superheroes:followups none -->\n</details>\n")
    result, fake = write(shaped, [RECEIPT, record_comment([F1])], tmp_path)
    assert result["reason"] == "leftover-not-accepted" and fake.edited == []
