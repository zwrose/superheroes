"""C1-L11d (issue #2273): an empty returning round's record carries the earlier review.

A returning PR whose only change since the last reviewed commit is a catch-up merge (or proven copies) converges in
round 1 with no reviewer run (C1-L11b). Its record write used to refuse, because nothing ran. Now the record reads
reviewed with no reviewer run in its session only when all of these hold:

C1  the session is exactly the empty returning round (one converged returning round, nothing audited, verified,
    carried or found);
C2  the PR's latest earlier record is a finished, not abandoned review whose final commit is the session's
    `lastReviewed`, whose findings all have an outcome, and which has a reviewer row that ran and covers that commit;
C3  the record writer itself re-derives from git that nothing changed since that commit (the returning-review decider
    answers `changed` with no changed file); it never takes the account's word.

`review_record.carry_refusal` is the one check of C2 and C3. A failing leg refuses the session writer
(`review-session-unsupported`, nothing posted) and demotes every carried row to `not-run` in the record writer.

Edges, each with its test:

E1  no earlier record posted: refuse (test_c1l11b_carried_findings.py::test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record);
E2  an earlier finding with no outcome: refuse, and the record writer demotes;
E3  the earlier record's final commit is not `lastReviewed`: refuse;
E4  the earlier record is not-reviewed or abandoned: refuse;
E5  the session ran anything: today's behaviour exactly;
E6  writer only: a hand-built carried account over a real source change: every row not-run;
E7  writer only: an earlier record not-reviewed, abandoned or unsettled: every row not-run;
E8  `carriedFrom` and `carriedReview` must name each other: review-account-invalid;
E9  a decider that raises (or answers with a non-dict) is a refusal, never a pass;
E10 a change holding one countable line is not an empty round: the scoped finder runs.

Bite-proof record: c1l11d_wo_a_carried_review
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import session_contract as SC  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

RD = TRD.RD
ROW = {"name": "code-reviewer", "vendor": "codex", "model": TRRS.CODEX, "planned": True, "ran": True, "runDir": None}
MAKERS = [{"family": "anthropic", "source": "builder"}]
OPEN = {"id": "code-001", "title": "t", "severity": "Minor", "file": "a.py", "line": 3, "body": "b", "consequence": "c",
        "outcome": None, "reason": None, "reviewer": "code-reviewer"}
WHY = "the change since the last reviewed commit held nothing countable, so no reviewer ran in this round"


def _catch_up(repo):
    """main moves and is merged into the PR: the change since the last reviewed commit has nothing to read."""
    repo.moved = repo.main_commit("docs/other.md", "other\n")
    repo.merge_main()


def _empty_session(tmp_path, monkeypatch):
    s = TS.Session(tmp_path, monkeypatch, change=_catch_up, base_after=lambda repo: repo.moved)
    s.cfg["headSha"] = s.head  # the session reviews the PR's head: the account's final commit
    answer = s.next()
    assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
    assert s.state()["rounds"]["1"]["scopedFinder"] == "skipped-empty-surface"
    return s


def _changed_session(tmp_path, monkeypatch):
    """A returning PR whose change since the last reviewed commit holds 40 countable lines: no empty round."""
    return TS.Session(tmp_path, monkeypatch, first=TS._first_leg(), change=TS._append("src/app.py", TR.numbered("fix", 40)))


def _acct(s, **over):
    base = {"schema": RR.ACCOUNT_SCHEMA, "pr": 7, "sessionId": "earlier-session", "lane": "full", "laneReason": "big",
            "finalCommit": s.reviewed, "ci": "green", "findings": [], "rawFindingsFiles": [], "makers": MAKERS,
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"],
            "reviewers": [dict(ROW, commit=s.reviewed)], "repoRoot": s.repo.root}
    return {**base, **over}


def _post_earlier(fake, s, edit=None, at=None, **over):
    """Post the PR's earlier review on `fake`: a record built the way the writer builds one, on the last reviewed
    commit (or on `at`). `edit` may change the record before it is posted (a status the writer would not make)."""
    at = at or s.reviewed
    rec = RR.build_record(_acct(s, **{"finalCommit": at, "reviewers": [dict(ROW, commit=at)], **over}), TRRS.Fake(head=at).readers())
    assert rec["status"] == "reviewed" or over.get("findings"), rec
    if edit is not None:
        edit(rec)
    fake.comments.append({"id": len(fake.comments) + 1, "author": "bot", "body": RR.render(rec), "url": "http://c/earlier"})
    return rec


def _open_finding(rec):
    """The earlier record as a hand edit could leave it: reads reviewed, and one finding has no outcome."""
    rec.update(status="reviewed", parked=False, whatIsMissing=[])


def _send(tmp_path, s, fake, **over):
    extras = TRRS.extras(ci="green", makers=MAKERS, **over)
    return RS.write_from_session(s.dir, TRRS.put_extras(tmp_path, extras), s.repo.root, fake.readers())


def _latest(fake):
    return RR.read(7, readers=fake.readers())


def _carried_account(s, **over):
    """A hand-built account for the record writer: every reviewer row carried from the last reviewed commit."""
    row = dict(ROW, commit=s.reviewed, step=None, carriedFrom=s.reviewed)
    return _acct(s, **{"sessionId": "session-2", "finalCommit": s.head, "baseRef": s.cfg["baseRef"], "reviewers": [row],
                       "carriedReview": {"lastReviewed": s.reviewed, "why": WHY}, **over})


def _write(tmp_path, s, fake, account):
    path = tmp_path / "account.json"
    path.write_text(json.dumps(account))
    return RR.write(str(path), s.repo.root, fake.readers())


def _row_states(rec):
    return [(v["ran"], "carried" in v) for v in rec["reviewers"]]


# --- DoD row 1: a catch-up merge only, the record is marked carried and reads reviewed with no reviewer run ----------------

def test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run(tmp_path, monkeypatch):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    out = _send(tmp_path, s, fake)
    assert out["ok"] is True and out["status"] == "reviewed", out
    rec = _latest(fake)
    assert rec["status"] == "reviewed" and rec["finalCommit"]["sha"] == s.head
    assert rec["reviewers"] and all(v["carried"] == {"commit": s.reviewed} and v["commit"] == s.reviewed
                                    and v["ran"] == "reported-by-session" and v["coversFinalCommit"] is True
                                    and v["cost"] == {"tokens": None, "minutes": None} and "observation" not in v
                                    for v in rec["reviewers"]), rec["reviewers"]
    # the record says plainly that no reviewer ran in this round, and why
    assert rec["checked"][1] == ("Reviewers that ran: none in this round — carried from the earlier review of %s: code-reviewer"
                                 % s.reviewed[:7]), rec["checked"]
    assert RS.CARRIED_WHY % s.reviewed[:7] in rec["checked"], rec["checked"]
    body = fake.marked()[-1]["body"]
    assert "- code-reviewer: carried from %s" % s.reviewed[:7] in body and "ran (reported by the session)" not in body
    assert "none in this round" in body.splitlines()[1]
    compact = RR._summary(rec, 1)
    assert "Reviewers that ran: none in this round; 1 reviewer carried from the earlier review" in compact, compact
    # no reviewer was dispatched in the session: it converged on its first `next`, with no seat result journaled
    assert not [r for r in RS._journal(s.dir) if r.get("outcome") == "recorded"]


# --- E2 (DoD row 2): one earlier finding with no outcome ----------------------------------------------------------------------

def test_e2_an_unsettled_earlier_finding_refuses_review_session_unsupported(tmp_path, monkeypatch):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s, edit=_open_finding, findings=[OPEN])
    before = list(fake.comments)
    out = _send(tmp_path, s, fake)
    assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED and out["detail"] == "an earlier finding is still open", out
    assert fake.writes == [] and fake.comments == before


# --- E3: the earlier record's final commit is not the session's lastReviewed -------------------------------------------------

@pytest.mark.parametrize("at", ["head", "c" * 40], ids=["the-head-itself", "an-unknown-commit"])
def test_e3_an_earlier_record_on_another_final_commit_refuses(tmp_path, monkeypatch, at):
    # the head itself is the case only this leg refuses: the decider reads an empty surface from it, and says `changed`
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s, at=s.head if at == "head" else None,
                  edit=None if at == "head" else lambda rec: rec.update(finalCommit={"sha": at, "source": "GitHub PR"}))
    out = _send(tmp_path, s, fake)
    assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
    assert out["detail"] == "the earlier record's final commit is not the last reviewed commit", out
    assert fake.writes == []


# --- E4: the earlier review did not finish, or was abandoned --------------------------------------------------------------------

@pytest.mark.parametrize("edit", [lambda rec: rec.update(status="not-reviewed"),
                                  lambda rec: rec.update(abandoned={"reason": "the loop was closed before it ended"})],
                         ids=["not-reviewed", "abandoned"])
def test_e4_an_earlier_review_that_is_not_finished_or_was_abandoned_refuses(tmp_path, monkeypatch, edit):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s, edit=edit)
    out = _send(tmp_path, s, fake)
    assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
    assert out["detail"].startswith("the earlier review does not stand for this head (earlier-review-incomplete:"), out
    assert fake.writes == []


# --- E5: a session that ran anything is today's behaviour exactly ----------------------------------------------------------------

@pytest.mark.parametrize("edit", [
    lambda st: st["rounds"].update({"2": {}}),
    lambda st: st["rounds"]["1"].update(carried=[{"findingKey": "rr1:x"}]),
    lambda st: st["rounds"]["1"].update(verifyPasses=[{"held": 0}]),
    lambda st: st["config"].update(returningCarried=[{"findingKey": "rr1:x"}]),
    lambda st: st.update(findings=[{"id": "F-1", "title": "t", "severity": "Important", "file": "a.py", "line": 1}]),
    lambda st: st.update(dispositionLedger=[TRRS.ledger_row()]),
], ids=["a-second-round", "a-carried-finding", "a-verifier-pass", "carried-in-config", "a-finding", "a-ledger-row"])
def test_e5_a_session_that_ran_anything_still_refuses_as_it_did(tmp_path, monkeypatch, edit):
    s = _empty_session(tmp_path, monkeypatch)
    path = os.path.join(s.dir, SC.STATE_FILE)
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    edit(state)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    before = list(fake.comments)
    out = _send(tmp_path, s, fake)
    assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
    assert fake.writes == [] and fake.comments == before


# --- E6 (brief-check F1): the writer re-derives the empty surface; the account's word is never taken ------------------------

def test_e6_a_carried_account_over_a_real_source_change_demotes_every_row(tmp_path, monkeypatch):
    s = _changed_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    out = _write(tmp_path, s, fake, _carried_account(s))
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    rec = _latest(fake)
    assert rec["reviewers"] and _row_states(rec) == [("not-run", False)] * len(rec["reviewers"]), rec["reviewers"]
    assert all(v["runNote"] == "the change since the last reviewed commit holds changed files" for v in rec["reviewers"])
    assert {"fact": "code-reviewer ran", "session": True, "code": "not-run"} in rec["sessionDisagreements"]
    assert rec["checked"][1] == "Reviewers that ran: none", rec["checked"]


def test_e6_positive_control_the_same_account_over_a_catch_up_merge_is_carried(tmp_path, monkeypatch):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    out = _write(tmp_path, s, fake, _carried_account(s))
    assert out["ok"] is True and out["status"] == "reviewed", out
    assert _row_states(_latest(fake)) == [("reported-by-session", True)]


# --- E7 (brief-check F2): the writer repeats the earlier record's eligibility checks ------------------------------------------

@pytest.mark.parametrize("edit,over,why", [
    (lambda rec: rec.update(status="not-reviewed"), {}, "the earlier review does not stand for this head (earlier-review-incomplete:"),
    (lambda rec: rec.update(abandoned={"reason": "closed early"}), {}, "the earlier review does not stand for this head (earlier-review-incomplete:"),
    (_open_finding, {"findings": [OPEN]}, "an earlier finding is still open"),
], ids=["not-reviewed", "abandoned", "unsettled"])
def test_e7_a_carried_account_over_an_earlier_record_that_does_not_qualify_demotes_every_row(tmp_path, monkeypatch, edit, over, why):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s, edit=edit, **over)
    out = _write(tmp_path, s, fake, _carried_account(s, **over))
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    rec = _latest(fake)
    assert _row_states(rec) == [("not-run", False)], rec["reviewers"]
    assert rec["reviewers"][0]["runNote"].startswith(why), rec["reviewers"]


def test_e7_a_carried_row_the_earlier_record_has_no_covering_row_for_is_not_run(tmp_path, monkeypatch):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    stranger = dict(_carried_account(s)["reviewers"][0], name="test-role")
    out = _write(tmp_path, s, fake, _carried_account(s, reviewers=[stranger, _carried_account(s)["reviewers"][0]]))
    rows = {v["name"]: v for v in _latest(fake)["reviewers"]}
    assert out["ok"] is True, out
    assert rows["test-role"]["ran"] == "not-run" and "carried" not in rows["test-role"]
    assert rows["test-role"]["runNote"] == "no matching covering reviewer in the earlier record"
    assert rows["code-reviewer"]["carried"] == {"commit": s.reviewed}


def test_e7_with_no_earlier_record_posted_every_carried_row_is_not_run(tmp_path, monkeypatch):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    out = _write(tmp_path, s, fake, _carried_account(s))
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    assert _row_states(_latest(fake)) == [("not-run", False)]


# --- E8: carriedFrom and carriedReview must name each other ---------------------------------------------------------------------

def _without(key):
    return lambda a: {k: v for k, v in a.items() if k != key}


@pytest.mark.parametrize("edit", [
    _without("carriedReview"),
    lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="d" * 40)),
    lambda a: dict(a, reviewers=[{k: v for k, v in a["reviewers"][0].items() if k != "carriedFrom"}]),
    lambda a: dict(a, reviewers=[dict(a["reviewers"][0], carriedFrom="abc123")]),
    lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="abc123")),
    lambda a: dict(a, carriedReview=dict(a["carriedReview"], why="  ")),
    lambda a: dict(a, carriedReview={"lastReviewed": a["carriedReview"]["lastReviewed"]}),
    lambda a: dict(a, carriedReview="carried"),
], ids=["no-carriedReview", "mismatched-sha", "no-row-carries-it", "short-carriedFrom", "short-lastReviewed", "blank-why",
        "no-why", "not-a-dict"])
def test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid(tmp_path, monkeypatch, edit):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    before = list(fake.comments)
    out = _write(tmp_path, s, fake, edit(_carried_account(s)))
    assert out["ok"] is False and out["reason"] == "review-account-invalid", out
    assert fake.writes == [] and fake.comments == before


# --- E9: a decider that raises, or answers with anything but a dict, is never a pass ----------------------------------------------

def _raises(*args, **kwargs):
    raise RuntimeError("git went away")


@pytest.mark.parametrize("decide,note", [(_raises, "(RuntimeError)"), (lambda *a, **k: None, "could not be read")],
                         ids=["raises", "not-a-dict"])
def test_e9_the_record_writer_demotes_every_row_when_the_decider_fails(tmp_path, monkeypatch, decide, note):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    readers = dict(fake.readers(), returning_decide=decide)
    path = tmp_path / "account.json"
    path.write_text(json.dumps(_carried_account(s)))
    out = RR.write(str(path), s.repo.root, readers)
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    rec = _latest(fake)
    assert _row_states(rec) == [("not-run", False)] and note in rec["reviewers"][0]["runNote"], rec["reviewers"]


@pytest.mark.parametrize("decide", [_raises, lambda *a, **k: None], ids=["raises", "not-a-dict"])
def test_e9_the_session_writer_refuses_when_the_decider_fails(tmp_path, monkeypatch, decide):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    _post_earlier(fake, s)
    before = list(fake.comments)
    extras = TRRS.put_extras(tmp_path, TRRS.extras(ci="green", makers=MAKERS))
    out = RS.write_from_session(s.dir, extras, s.repo.root, dict(fake.readers(), returning_decide=decide))
    assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
    assert fake.writes == [] and fake.comments == before


# --- E10 (DoD row 3): a change holding one countable line is not an empty round ---------------------------------------------------

def test_e10_a_change_with_one_countable_line_runs_the_scoped_finder_as_before(tmp_path, monkeypatch):
    s = TS.Session(tmp_path, monkeypatch, first=TS._first_leg(), change=TS._append("src/app.py", TR.numbered("fix", 1)))
    answer = s.next()
    state = s.state()
    assert (answer["action"], answer["phase"], answer["round"]) == (RD.P_SCOPED, RD.P_SCOPED, 1), answer
    assert state["rounds"]["1"]["roundKind"] == RD.RETURNING_KIND
    assert state["rounds"]["1"].get("scopedFinder") != "skipped-empty-surface", state["rounds"]["1"]
    assert RS._empty_returning_round(state) is None


# --- the one check, called directly ------------------------------------------------------------------------------------------------

def test_carry_refusal_names_the_first_failing_leg_and_passes_when_every_leg_holds(tmp_path, monkeypatch):
    s = _empty_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    prior = _post_earlier(fake, s)
    ask = lambda p, sha=s.reviewed, decide=None: RR.carry_refusal(p, sha, s.repo.root, s.cfg["baseRef"], s.head, [], decide)  # noqa: E731
    assert ask(prior) is None
    assert ask(None) == "the earlier record's final commit is not the last reviewed commit"
    assert ask(prior, sha="abc123") == "the earlier record's final commit is not the last reviewed commit"
    assert ask(dict(prior, findings=[OPEN])) == "an earlier finding is still open"
    assert ask(dict(prior, findings={"a": 1})) == "an earlier finding is still open"
    assert ask(dict(prior, findings=[dict(OPEN, outcome="fixed"), "x"])) == "an earlier finding is still open"
    assert ask(dict(prior, reviewers=[dict(prior["reviewers"][0], coversFinalCommit=False)])).startswith(
        "the earlier review does not stand for this head")
    # a decider that finds a changed file is not an empty surface, even when it reads `changed`
    changed = lambda *a, **k: {"read": "changed", "changedFiles": ["src/app.py"], "why": []}  # noqa: E731
    assert ask(prior, decide=changed) == "the change since the last reviewed commit holds changed files"
    # the decider says the covering reviewer exists, but the record's own rows do not show a run
    allowed = lambda *a, **k: {"read": "changed", "changedFiles": [], "why": []}  # noqa: E731
    no_run = dict(prior, reviewers=[dict(prior["reviewers"][0], ran="not-run")])
    assert ask(no_run, decide=allowed) == "no reviewer of the earlier record ran and covers its final commit"
