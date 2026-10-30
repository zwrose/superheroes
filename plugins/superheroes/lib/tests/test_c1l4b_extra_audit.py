"""C1-L4b: a review session handed back at its round cap can be reopened once, by the advisor's order, for
one extra audit round.

The round audits only the cap round's fixes. It dispatches no panel, scoped finder, gap sweep, fixer or verify
run, it is labelled in the record, and it is never counted in the cap. A PR gets at most one, across all its
sessions. No session begins round `cap + 1` except through the `extra-audit` verb.

Drives the real round driver through the CLI functions (`cmd_next`, `cmd_submit`, `cmd_extra_audit`) on a session
directory built the way production builds one, and the review record writer through its injected readers.

Bite-proof records: c1l4b_wo_a, c1l4b_wo_g
"""
import glob
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import test_outcome_settle_c7 as TOC  # noqa: E402
import test_review_record as TRR  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # the driver module these sessions run on is test_round_driver's own load of it

CAP = 2
PR = 2239
WHY = "the advisor wants the cap round's fixes audited once"
VENDORS = ["claude", "codex"]
SUPERSEDED = "round-receipt.superseded-1.json"


# --- a session driven through the CLI functions ----------------------------------------------------

def _finding(title, severity="Important", file="newsurf.py"):
    return {"title": title, "severity": severity, "consequence": TRD._CONSEQUENCE, "file": file, "line": 1}


def _audit_artifact(payload, extra_round, extra, fail_titles):
    results = []
    for t in payload.get("targets", []):
        failing = extra == "not-discharged" if extra_round else t.get("title") in fail_titles
        row = {"id": t["id"], "auditorVendor": t.get("auditorVendor")}
        if failing:
            row.update(ruling="not-discharged", reason="still broken")
        elif extra_round and extra == "new-issue":
            row.update(ruling="discharged-but-new-issue", reason="fix resolves it", evidence="tests pass",
                       newIssues=[_finding("raised-by-the-audit")])
        else:
            row.update(ruling="discharged", reason="fix resolves it", evidence="tests pass")
        results.append(row)
    return {"results": results,
            "collectionManifest": {t["id"]: t.get("auditorVendor") for t in payload.get("targets", [])}}


def _respond(cap=CAP, scoped=None, fail_titles=(), extra="discharged", findings=True):
    """Scripted answers: the panel raises one blocker, the scoped finder raises a new one in `scoped`'s rounds
    (by default the cap round), every audit discharges except `fail_titles`, and the extra round (any round past
    the cap) answers `extra`: discharged, not-discharged or new-issue."""
    scoped = {cap: [_finding("open-important")]} if scoped is None else scoped
    base = TRD._responder(round1_findings=list(TRD._A_FINDING) if findings else None, vendors=VENDORS)
    fixes = {"n": 0}

    def respond(phase, payload, rnd):
        if phase == RD.P_SCOPED:
            return {"findings": [dict(f) for f in scoped.get(rnd, [])]}
        if phase == RD.P_APPLY_FIXES:
            fixes["n"] += 1
            return {"fixes": [], "headDiff": TRD._headf_ns(fixes["n"]), "changedSubjects": ["Code"]}
        if phase == RD.P_AUDITS:
            return _audit_artifact(payload, rnd > cap, extra, fail_titles)
        return base(phase, payload, rnd)

    return respond


def _start(tmp_path, cap=CAP):
    """A fresh session directory inside its own real checkout, seeded as review setup seeds one."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout = str(tmp_path / "checkout")
    TRD.enter_checkout(checkout)
    TRD._seed_repo_root_if_missing(d, checkout)
    return d, TRD._cfg(maxRounds=cap)


def _drive(d, respond, cfg=None, max_steps=200):
    """next/submit until `next` emits the terminal; return that `next` answer and every action emitted."""
    emitted = []
    for step in range(max_steps):
        n = RD.cmd_next(d, cfg if step == 0 else None)
        assert n["ok"], n
        emitted.append(n["action"])
        if n["action"] == RD.P_TERMINAL:
            return n, emitted
        art = TRD._claim_reviewer(d, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("the session did not reach a terminal in %d steps" % max_steps)


def _capped(tmp_path, cap=CAP, **script):
    """A finalized session handed back at its cap with the cap round's fix never audited."""
    d, cfg = _start(tmp_path, cap)
    terminal, _emitted = _drive(d, _respond(cap=cap, **script), cfg)
    assert terminal["payload"]["verdict"] == "handed-back", terminal
    state = _state(d)
    assert state["decisions"][-1]["kind"] == "round-cap" and state["round"] == cap, state["decisions"][-3:]
    assert state["_receiptFinalized"] is True
    return d


def _state(d):
    ok, state = RD.load_state(d)
    assert ok and state is not None
    return state


def _pin_head(monkeypatch, d):
    """The checkout's head is the session's certified head (no commit needed): `_checkout_head` is the seam."""
    state = _state(d)
    head = RD._session_certified_head(d, state)
    if not head:
        meta_path = os.path.join(d, "meta.json")
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        head = meta[RD.FIX_FOLD_HEAD_KEY] = "d" * 40
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    monkeypatch.setattr(RD, "_checkout_head", lambda session_dir, st: head)
    return head


def _order(tmp_path, body=None, name="order.json"):
    path = str(tmp_path / name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"why": WHY} if body is None else body, fh)
    return path


def _readers(comments=(), **over):
    base = {"list_comments": lambda pr, repo: list(comments), "repo_name": lambda root: "o/r",
            "create_comment": lambda pr, repo, body: {"id": 10 ** 6, "url": "http://c/reserved"}}
    base.update(over)
    return base


def _files(d):
    """sha256 of every file in the session directory but the journal and the lock."""
    skip = (RD.JOURNAL_FILE, RD.round_records.LOCK_FILE)
    out = {}
    for root, _dirs, names in os.walk(d):
        for name in names:
            rel = os.path.relpath(os.path.join(root, name), d)
            if rel not in skip:
                with open(os.path.join(root, name), "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _read(d, name):
    with open(os.path.join(d, name), "rb") as fh:
        return fh.read()


def _refused(d, order, token, **kw):
    """The order is refused with `token`, journals exactly one refusal row, and changes nothing else."""
    before, rows = _files(d), len(RD.read_journal(d))
    kw.setdefault("readers", _readers())
    out = RD.cmd_extra_audit(d, order, "advisor", PR, **kw)
    assert out["ok"] is False and out["reason"] == token, out
    assert _files(d) == before
    journal = RD.read_journal(d)
    assert len(journal) == rows + 1, journal[rows:]
    assert (journal[-1]["cmd"], journal[-1]["outcome"], journal[-1]["reason"]) == ("extra-audit", "refused", token)
    return out


def _ordered(tmp_path, monkeypatch, **script):
    """A capped session, its extra audit round ordered. Returns (session dir, the cap round's fix batch keys)."""
    d = _capped(tmp_path, **script)
    _pin_head(monkeypatch, d)
    batch = RD._fix_batch_keys(_state(d))
    assert batch, "the cap round applied no fix batch"
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())
    assert out == {"ok": True, "round": CAP + 1, "supersededReceipt": SUPERSEDED}, out
    return d, batch


def _finish(d, respond):
    """next/submit from an ordered session to its terminal; the actions emitted on the way."""
    return _drive(d, respond)


def _rows(state, title):
    """The disposition-ledger rows titled `title`."""
    return [e for e in state.get(RD.session_contract.DISPOSITION_LEDGER_KEY) or [] if e.get("title") == title]


def _account(tmp_path, state):
    session = TRRS.Session(tmp_path / "rec", **state).seat("code-reviewer").save()
    return RS.account_from_session(session, TRRS.extras())


# --- T1: an ordered extra round audits the cap round's fixes and converges ---------------------------

def test_t1_an_ordered_extra_round_dispatches_only_the_audits_and_a_discharge_converges(tmp_path, monkeypatch):
    # axis: the extra round's actions are the audits and the terminal, over exactly the cap round's fix batch;
    # the record counts the cap rounds and labels the extra one — see bite-proof record c1l4b_wo_a
    d, batch = _ordered(tmp_path, monkeypatch)
    state = _state(d)
    assert state["round"] == CAP + 1 and not state.get("terminal") and state["step"] == RD.P_AUDITS
    assert state["extraAudit"]["round"] == CAP + 1 and state["extraAudit"]["why"] == WHY
    assert [dec["kind"] for dec in state["decisions"]][-1] == "extra-audit-ordered"
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_AUDITS and n["round"] == CAP + 1, n
    assert [t["id"] for t in n["payload"]["targets"]] == batch
    assert "verify" not in n["payload"]
    terminal, emitted = _finish(d, _respond())
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    assert terminal["payload"]["verdict"] == "converged"
    final = _state(d)
    assert final["terminal"] == "converged" and final["decisions"][-1]["kind"] == "converged"
    assert sorted(final["rounds"]) == ["1", "2", "3"] and final["round"] == CAP + 1
    rows = _rows(final, "open-important")
    assert len(rows) == 1 and rows[0]["disposition"] == "fixed", rows
    assert "settledReason" not in rows[0]
    account = _account(tmp_path, final)
    assert account["rounds"]["count"] == CAP
    assert account["rounds"]["extraAudit"] == {"why": WHY}
    assert account["rounds"]["stoppedAtCap"] is False
    RR._validate(account)


# --- T2: a non-discharging extra audit hands the PR back open ----------------------------------------

def test_t2_a_non_discharging_extra_audit_hands_back_open_with_no_further_round(tmp_path, monkeypatch):
    # axis: the extra round runs no scoped finder, fixer or recovery after its audits, whatever they find
    # — see bite-proof record c1l4b_wo_a
    d, batch = _ordered(tmp_path, monkeypatch, extra="not-discharged")
    terminal, emitted = _finish(d, _respond(extra="not-discharged"))
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    assert terminal["payload"]["verdict"] == "handed-back"
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert final["round"] == CAP + 1 and sorted(final["rounds"]) == ["1", "2", "3"]
    rows = _rows(final, "open-important")
    assert len(rows) == 1 and rows[0]["disposition"] == "left-for-owner" and rows[0]["settledReason"], rows
    account = _account(tmp_path, final)
    assert account["rounds"]["stoppedAtCap"] is True and account["rounds"]["count"] == CAP
    assert account["rounds"]["extraAudit"] == {"why": WHY}
    outcomes = [f["outcome"] for f in account["findings"] if f["title"] == "open-important"]
    assert outcomes == ["left-for-owner"], account["findings"]
    again = RD.cmd_next(d)
    assert again["ok"] and again["action"] == RD.P_TERMINAL
    assert _state(d)["round"] == CAP + 1


def test_t2b_a_new_issue_raised_by_the_extra_audit_is_settled_and_never_searched(tmp_path, monkeypatch):
    # axis: an audit's new issue ends with an outcome at the extra round's terminal and opens no scoped round
    d, batch = _ordered(tmp_path, monkeypatch)
    terminal, emitted = _finish(d, _respond(extra="new-issue"))
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert [r["disposition"] for r in _rows(final, "open-important")] == ["fixed"]
    raised = _rows(final, "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["disposition"] == "left-for-owner", raised
    assert "_newIssues" not in final


# --- T2c: guidance no fixer ever received keeps the extra round from converging ------------------------

_RULED_KEY = "f.py::bug@L1"  # the panel's round-1 finding: fixed and audited long before the extra round


def _guided_extra_round(tmp_path, monkeypatch, ruled):
    """An ordered extra round whose audits all discharge; with `ruled`, a guidance ruling on a session
    finding the extra round's audit targets do not carry is recorded after the order and before the audits."""
    d, batch = _ordered(tmp_path, monkeypatch)
    assert _RULED_KEY not in batch, batch
    if ruled:
        path = TOC._write_rulings(tmp_path / "rulings.json", [
            {"id": _RULED_KEY, "ruling": "guidance", "reason": "the owner wants it handled this way",
             "guidance": "keep the public signature as it is"}])
        out = RD.cmd_rule(d, path, "owner")
        assert out.get("ok"), out
        assert [r["ruling"] for r in _state(d)["rulingsLog"]] == ["guidance"]
    terminal, emitted = _finish(d, _respond())
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    return terminal, _state(d)


def test_t2c_a_guidance_ruling_no_fixer_received_hands_the_extra_round_back_open(tmp_path, monkeypatch):
    # axis: a guidance ruling no fixer ever received keeps the extra round from converging — see bite-proof record c1l4b_wo_g
    terminal, final = _guided_extra_round(tmp_path, monkeypatch, ruled=True)
    assert terminal["payload"]["verdict"] == "handed-back"
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    detail = final["decisions"][-1]["detail"]
    assert "guidance recorded but never sent to a fixer" in detail and "(guidance)" in detail, detail
    assert final["certification"]["shape"] is None and "(guidance)" in final["certification"]["reason"]


def test_t2c_the_same_extra_round_without_the_ruling_converges(tmp_path, monkeypatch):
    # axis: A/B for the test above — with no ruling recorded the same discharged audits converge
    terminal, final = _guided_extra_round(tmp_path, monkeypatch, ruled=False)
    assert terminal["payload"]["verdict"] == "converged"
    assert final["terminal"] == "converged" and final["decisions"][-1]["kind"] == "converged"
    assert not final.get("rulingsLog")


# --- T3: a second order in the same session ----------------------------------------------------------

def test_t3_a_second_order_in_the_same_session_is_refused_and_changes_nothing(tmp_path, monkeypatch):
    # axis: a session that already ran its extra round refuses a second order — see bite-proof record c1l4b_wo_a
    d, _batch = _ordered(tmp_path, monkeypatch, extra="not-discharged")
    _finish(d, _respond(extra="not-discharged"))
    assert _state(d)["decisions"][-1]["kind"] == "extra-audit-open"
    _refused(d, _order(tmp_path), "extra-audit-already-run")


# --- T4: a second session on the same PR -------------------------------------------------------------

def _posted(tmp_path, session_id, extra):
    fake = TRR.Fake()
    rounds = {"count": 3, "cap": 4, "stoppedAtCap": False}
    if extra:
        rounds["extraAudit"] = {"why": WHY}
    out = RR.write(TRR.put(tmp_path / "rec", TRR.account(sessionId=session_id, rounds=rounds)),
                   str(tmp_path), fake.readers())
    assert out["ok"], out
    return fake.comments


@pytest.mark.parametrize("case", ["record-shows-it", "unparseable-record", "comment-list-failed"])
def test_t4_a_second_session_on_the_same_pr_is_refused_by_the_prs_history(tmp_path, monkeypatch, case):
    # axis: an earlier record that shows the round refuses; history that cannot be read refuses and never reads
    # as "not run" — see bite-proof record c1l4b_wo_a
    (tmp_path / "rec").mkdir()
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    order = _order(tmp_path)
    if case == "record-shows-it":
        out = _refused(d, order, "extra-audit-already-run-on-pr",
                       readers=_readers(_posted(tmp_path, "s-other", extra=True)))
        assert out["sessionId"] == "s-other" and out["url"]
    elif case == "unparseable-record":
        broken = {"id": 99, "author": "bot", "body": RR.MARKER + "\nnot a record", "url": "http://c/99"}
        _refused(d, order, "extra-audit-pr-history-unreadable",
                 readers=_readers(_posted(tmp_path, "s-other", extra=False) + [broken]))
    else:
        _refused(d, order, "extra-audit-pr-history-unreadable",
                 readers=_readers(list_comments=lambda pr, repo: None))
    # a readable history with no such record lets the same order through
    out = RD.cmd_extra_audit(d, order, "advisor", PR,
                             readers=_readers(_posted(tmp_path, "s-other", extra=False)))
    assert out["ok"] is True, out


def _reservation(session_id, cid=500):
    return {"id": cid, "author": "bot", "url": "http://c/%d" % cid,
            "body": "%s\nsessionId: %s\nwhy: %s\n" % (RR.EXTRA_AUDIT_RESERVED_MARKER, session_id, WHY)}


def test_t4b_a_second_session_sees_the_first_sessions_reservation_though_no_record_shows_the_round(
        tmp_path, monkeypatch):
    # axis: the allowance is claimed on the PR at order time, before any record shows the round
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    out = _refused(d, _order(tmp_path), "extra-audit-already-run-on-pr",
                   readers=_readers([_reservation("s-other")]))
    assert out["sessionId"] == "s-other" and out["url"] == "http://c/500"


def test_t4c_the_order_posts_one_reservation_and_a_rerun_after_a_crash_by_the_same_session_is_accepted(
        tmp_path, monkeypatch):
    # axis: the reservation is posted before the state commit; the same session's own reservation never counts
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    sid = RD._meta_session_id(d)
    posted = []

    def create(pr, repo, body):
        posted.append((pr, repo, body))
        return {"id": 700, "url": "http://c/700"}

    def failing_begin(session_dir, kind, **kw):
        raise RD.round_commit.CommitRefused("commit-apply-failed", "injected")

    real_begin = RD.round_commit.begin
    monkeypatch.setattr(RD.round_commit, "begin", failing_begin)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers(create_comment=create))
    assert out["ok"] is False and len(posted) == 1
    lines = posted[0][2].split("\n")
    assert lines[0] == RR.EXTRA_AUDIT_RESERVED_MARKER and lines[1] == "sessionId: %s" % sid and WHY in posted[0][2]
    assert "extraAudit" not in _state(d)
    monkeypatch.setattr(RD.round_commit, "begin", real_begin)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR,
                             readers=_readers([_reservation(sid, 700)], create_comment=create))
    assert out["ok"] is True, out


def test_t4g_two_sessions_that_both_read_an_empty_history_elect_the_lower_comment_id(tmp_path, monkeypatch):
    # axis: the first reservation posted wins; the loser refuses after posting and leaves its reservation in place
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    sid = RD._meta_session_id(d)
    store = []

    def create_for(cid):
        def create(pr, repo, body):
            store.append({"id": cid, "author": "bot", "url": "http://c/%d" % cid, "body": body})
            return {"id": cid, "url": "http://c/%d" % cid}
        return create

    # the other session posted first (lower id) between this session's empty read and its own post
    store.append(_reservation("s-other", 600))
    reads = []

    def listing(pr, repo):
        reads.append(1)
        return [] if len(reads) == 1 else list(store)

    out = _refused(d, _order(tmp_path), "extra-audit-already-run-on-pr",
                   readers=_readers(list_comments=listing, create_comment=create_for(700)))
    assert out["sessionId"] == "s-other" and len(reads) == 2
    assert any(c["id"] == 700 for c in store)  # the loser's reservation stays
    # the winner: its own lower-id reservation, with the other session's higher-id one present, is accepted
    store[:] = [_reservation(sid, 600)]
    reads.clear()

    def listing_winner(pr, repo):
        reads.append(1)
        return [] if len(reads) == 1 else list(store) + [_reservation("s-other", 700)]

    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR,
                             readers=_readers(list_comments=listing_winner, create_comment=create_for(650)))
    assert out["ok"] is True, out


def test_t4h_a_winners_rerun_ignores_a_later_higher_id_loser_reservation(tmp_path, monkeypatch):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    sid = RD._meta_session_id(d)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR,
                             readers=_readers([_reservation(sid, 700), _reservation("s-other", 800)],
                                              create_comment=lambda pr, repo, body: {"id": 900, "url": "u"}))
    assert out["ok"] is True, out


def test_t4i_a_failed_reread_after_the_reservation_refuses_with_nothing_written_locally(tmp_path, monkeypatch):
    # axis: the election read fails closed
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    reads = []

    def listing(pr, repo):
        reads.append(1)
        return [] if len(reads) == 1 else None

    _refused(d, _order(tmp_path), "extra-audit-pr-history-unreadable",
             readers=_readers(list_comments=listing))
    assert len(reads) == 2 and "extraAudit" not in _state(d)


def test_t4d_a_reservation_that_cannot_be_posted_refuses_with_nothing_written(tmp_path, monkeypatch):
    # axis: no reservation, no reopening
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    order = _order(tmp_path)
    _refused(d, order, "extra-audit-reservation-failed",
             readers=_readers(create_comment=lambda pr, repo, body: None))

    def boom(pr, repo, body):
        raise RuntimeError("post exploded")

    _refused(d, order, "extra-audit-reservation-failed", readers=_readers(create_comment=boom))
    assert "extraAudit" not in _state(d)


def test_t4e_a_reservation_naming_no_session_fails_closed(tmp_path, monkeypatch):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    bad = {"id": 501, "author": "bot", "url": "http://c/501", "body": RR.EXTRA_AUDIT_RESERVED_MARKER + "\nnothing"}
    _refused(d, _order(tmp_path), "extra-audit-pr-history-unreadable", readers=_readers([bad]))


def test_t4f_a_repository_that_cannot_be_resolved_refuses_and_never_reads_the_ambient_directory(
        tmp_path, monkeypatch):
    # axis: a failed repository lookup refuses before any PR read
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    order = _order(tmp_path)
    calls = []

    def listing(pr, repo):
        calls.append(repo)
        return []

    for name in (lambda root: None, lambda root: 1 / 0):
        _refused(d, order, "extra-audit-pr-history-unreadable",
                 readers=_readers(list_comments=listing, repo_name=name))
    assert calls == []


def test_history_reads_fail_closed_for_each_cause_and_report_the_round_when_shown(tmp_path):
    # axis: extra_audit_history has one failure reason for a failed list, an unparseable record and an unexpected error
    (tmp_path / "rec").mkdir()
    shown = _posted(tmp_path, "s-other", extra=True)
    out = RR.extra_audit_history(PR, "o/r", _readers(shown))
    assert out["ok"] and out["ran"] is True and out["sessionId"] == "s-other" and out["url"]
    clear = _posted(tmp_path, "s-other", extra=False)
    none_ran = {"ok": True, "ran": False, "sessionId": None, "url": None, "ownId": None, "lowestCompetingId": None}
    assert RR.extra_audit_history(PR, "o/r", _readers(clear)) == none_ran
    assert RR.extra_audit_history(PR, "o/r", _readers([])) == none_ran

    def boom(pr, repo):
        raise RuntimeError("the list exploded")

    broken = {"id": 99, "author": "bot", "body": RR.MARKER + "\nnot a record", "url": "http://c/99"}
    causes = (("o/r", _readers(list_comments=lambda pr, repo: None), "review-record-gh-failed"),
              ("o/r", _readers(clear + [broken]), "review-record-unreadable"),
              ("o/r", _readers(list_comments=boom), "RuntimeError"),
              (None, _readers(repo_name=lambda root: None), "review-record-gh-failed"))
    for repo, readers, fragment in causes:
        out = RR.extra_audit_history(PR, repo, readers)
        assert out["ok"] is False and out["reason"] == "review-record-history-unreadable", out
        assert fragment in out["detail"], out
    # a repo left out is resolved by the repo-name reader
    assert RR.extra_audit_history(PR, None, _readers(clear))["ok"] is True


# --- T5: the receipt of the first terminal is kept; the new terminal writes its own ------------------

def test_t5_the_first_receipt_is_kept_byte_for_byte_and_the_new_terminal_writes_its_own(tmp_path, monkeypatch):
    # axis: the superseded copy holds the original bytes; the new receipt is valid and names the new terminal
    d = _capped(tmp_path)
    original = _read(d, RD.RECEIPT_FILE)
    assert json.loads(original)["verdict"] == "handed-back"
    _pin_head(monkeypatch, d)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())
    assert out["ok"] and out["supersededReceipt"] == SUPERSEDED
    assert _read(d, SUPERSEDED) == original
    assert _read(d, RD.RECEIPT_FILE) == original  # the reopen leaves the live receipt alone
    assert _state(d)["extraAudit"]["supersededReceiptSha256"] == hashlib.sha256(original).hexdigest()
    _finish(d, _respond())
    fresh = _read(d, RD.RECEIPT_FILE)
    assert fresh != original and _read(d, SUPERSEDED) == original
    receipt = json.loads(fresh)
    assert receipt["verdict"] == "converged" and RD.validate_receipt(receipt)[0]
    assert any(dec["kind"] == "extra-audit-ordered" for dec in receipt["decisions"])
    replay = RD.cmd_next(d)
    assert replay["ok"] and replay["action"] == RD.P_TERMINAL, replay
    assert _read(d, RD.RECEIPT_FILE) == fresh


# --- T6: crash windows -------------------------------------------------------------------------------

def test_t6a_a_failure_between_the_receipt_copy_and_the_state_commit_loses_nothing(tmp_path, monkeypatch):
    # axis: the copy is idempotent and the state commit is the one reopening write — a re-run finishes the order
    d = _capped(tmp_path)
    original = _read(d, RD.RECEIPT_FILE)
    state_before = _read(d, RD.STATE_FILE)
    _pin_head(monkeypatch, d)
    real_begin = RD.round_commit.begin

    def failing_begin(session_dir, kind, **kw):
        if kind == "extra-audit-order":
            raise RD.round_commit.CommitRefused("commit-apply-failed", "injected")
        return real_begin(session_dir, kind, **kw)

    monkeypatch.setattr(RD.round_commit, "begin", failing_begin)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())
    assert out["ok"] is False and out["reason"] == "commit-apply-failed", out
    assert _read(d, RD.STATE_FILE) == state_before
    state = _state(d)
    assert state["terminal"] == "handed-back" and "extraAudit" not in state
    assert _read(d, SUPERSEDED) == original and _read(d, RD.RECEIPT_FILE) == original
    replay = RD.cmd_next(d)
    assert replay["ok"] and replay["action"] == RD.P_TERMINAL, replay
    monkeypatch.setattr(RD.round_commit, "begin", real_begin)
    done = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())
    assert done["ok"] is True, done
    copies = glob.glob(os.path.join(d, "round-receipt.superseded-*.json"))
    assert [os.path.basename(p) for p in copies] == [SUPERSEDED] and _read(d, SUPERSEDED) == original


def test_t6b_after_the_order_a_fresh_next_emits_the_audits_and_the_session_completes(tmp_path, monkeypatch):
    # axis: the order is the whole reopen — nothing else is owed before the audits are dispatched
    d, batch = _ordered(tmp_path, monkeypatch)
    first = RD.cmd_next(d)
    second = RD.cmd_next(d)
    assert first["action"] == RD.P_AUDITS and second["expectedStateHash"] == first["expectedStateHash"]
    assert [t["id"] for t in second["payload"]["targets"]] == batch
    terminal, _emitted = _finish(d, _respond())
    assert terminal["payload"]["verdict"] == "converged"
    assert RD._verify_terminal_receipt(d) is None


# --- T7: the checkout must still be at the session's certified head ----------------------------------

def test_t7_a_moved_checkout_refuses_before_any_write_and_the_restored_head_is_accepted(tmp_path, monkeypatch):
    # axis: a checkout off the certified head refuses before any write — see bite-proof record c1l4b_wo_a
    # The real git boundary: `_checkout_head` is NOT patched; the session's own temporary checkout moves.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    d = _capped(tmp_path)
    checkout = str(tmp_path / "checkout")
    ident = ("-c", "user.name=superheroes-test", "-c", "user.email=superheroes-test@example.invalid",
             "-c", "commit.gpgsign=false")

    def git(*args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", LC_ALL="C")
        return subprocess.run(["git", *ident, "-C", checkout, *args], capture_output=True, text=True,
                              check=True, env=env).stdout.strip()

    certified = git("rev-parse", "HEAD")
    meta_path = os.path.join(d, "meta.json")
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    meta[RD.FIX_FOLD_HEAD_KEY] = certified
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    git("commit", "-q", "--allow-empty", "-m", "the checkout moves")
    moved = git("rev-parse", "HEAD")
    assert moved != certified
    out = _refused(d, _order(tmp_path), "extra-audit-head-moved")
    assert (out["certifiedHead"], out["checkoutHead"]) == (certified, moved)
    git("reset", "-q", "--hard", certified)
    assert RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())["ok"] is True


def test_t7_a_checkout_head_git_cannot_name_refuses_head_unresolvable(tmp_path, monkeypatch):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    monkeypatch.setattr(RD, "_checkout_head", lambda session_dir, st: None)
    _refused(d, _order(tmp_path), "extra-audit-head-unresolvable")


def test_reservation_comment_scrubs_a_credential_quoted_in_the_reason():
    secret = "sk-" + "a" * 48
    sent = []

    def create(pr, repo, body):
        sent.append(body)
        return {"id": 1, "url": "http://c/r"}

    out = RR.reserve_extra_audit(PR, "o/r", "sess-1", "reason quoting " + secret, readers=_readers(create_comment=create))
    assert out["ok"] is True and len(sent) == 1
    assert secret not in sent[0]
    assert "sessionId: sess-1" in sent[0]


# --- T8: the remaining refusals ----------------------------------------------------------------------

def test_t8_state_that_does_not_load_refuses_state_unreadable(tmp_path):
    empty = str(tmp_path / "empty")
    os.makedirs(empty)
    _refused(empty, _order(tmp_path), "extra-audit-state-unreadable")
    torn = str(tmp_path / "torn")
    os.makedirs(torn)
    with open(os.path.join(torn, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    _refused(torn, _order(tmp_path), "extra-audit-state-unreadable")


@pytest.mark.parametrize("make", ["missing", "not-json", "list", "extra-key", "blank-why", "non-string-why"])
def test_t8_an_order_file_that_is_not_one_non_blank_why_is_refused(tmp_path, monkeypatch, make):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    if make == "missing":
        order = str(tmp_path / "absent.json")
    elif make == "not-json":
        order = str(tmp_path / "bad.json")
        with open(order, "w", encoding="utf-8") as fh:
            fh.write("{why")
    else:
        body = {"list": ["why"], "extra-key": {"why": WHY, "by": "me"}, "blank-why": {"why": "  \n"},
                "non-string-why": {"why": 3}}[make]
        order = _order(tmp_path, body)
    _refused(d, order, "extra-audit-order-invalid")


def test_t8_a_session_not_handed_back_at_the_cap_is_refused(tmp_path, monkeypatch):
    # a session still running
    running = str(tmp_path / "running")
    os.makedirs(running)
    assert RD.cmd_next(running, TRD._cfg(maxRounds=CAP))["ok"]
    assert not _state(running).get("terminal")
    _refused(running, _order(tmp_path), "extra-audit-not-at-cap")
    # a converged one
    sub = tmp_path / "converged"
    sub.mkdir()
    d, cfg = _start(sub)
    terminal, _emitted = _drive(d, _respond(findings=False), cfg)
    assert terminal["payload"]["verdict"] == "converged"
    _refused(d, _order(tmp_path), "extra-audit-not-at-cap")
    # a hand-back for an owner's choice
    sub = tmp_path / "owner"
    sub.mkdir()
    d = _capped(sub)
    state = _state(d)
    state["decisions"][-1]["kind"] = "owner-choice-open"
    RD.save_state(d, state)
    _refused(d, _order(tmp_path), "extra-audit-not-at-cap")


def test_t8_a_cap_hand_back_with_no_unaudited_fix_has_nothing_to_audit(tmp_path, monkeypatch):
    # a stall found in the cap round hands back `round-cap` with no fix of that round to audit
    sub = tmp_path / "stall"
    sub.mkdir()
    d = _capped(sub, cap=4, scoped={2: [_finding("late")]}, fail_titles=("late",))
    state = _state(d)
    assert "fix" not in state["rounds"]["4"], state["rounds"]["4"].keys()
    _pin_head(monkeypatch, d)
    _refused(d, _order(tmp_path), "extra-audit-nothing-to-audit")
    # the same refusal when the cap round's `fix` entry is not there
    sub = tmp_path / "nofix"
    sub.mkdir()
    d = _capped(sub)
    _pin_head(monkeypatch, d)
    state = _state(d)
    state["rounds"][str(CAP)].pop("fix")
    RD.save_state(d, state)
    _refused(d, _order(tmp_path), "extra-audit-nothing-to-audit")


@pytest.mark.parametrize("edit", [b"{not json", b"{}"], ids=["unreadable", "not-a-receipt"])
def test_t8_a_finalized_receipt_edited_on_disk_refuses_receipt_faulted(tmp_path, monkeypatch, edit):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    with open(os.path.join(d, RD.RECEIPT_FILE), "wb") as fh:
        fh.write(edit)
    _refused(d, _order(tmp_path), "extra-audit-receipt-faulted")
    assert not os.path.exists(os.path.join(d, SUPERSEDED))


def test_t8_a_superseded_copy_that_differs_from_the_receipt_refuses_receipt_faulted(tmp_path, monkeypatch):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    with open(os.path.join(d, SUPERSEDED), "wb") as fh:
        fh.write(b"another receipt")
    _refused(d, _order(tmp_path), "extra-audit-receipt-faulted")


# --- T9: the loaded-state guard ----------------------------------------------------------------------

@pytest.mark.parametrize("extra,rnd", [(None, CAP + 1),
                                       ({"why": "x", "round": CAP + 2}, CAP + 1),
                                       ({"why": "x", "round": CAP + 2}, CAP + 2)],
                         ids=["no-order", "order-for-another-round", "two-past-the-cap"])
def test_t9_a_loaded_state_above_its_cap_without_its_order_still_hands_back(tmp_path, extra, rnd):
    # axis: a state above its cap without the matching order still hands back `round-cap` — see bite-proof record c1l4b_wo_a
    d = str(tmp_path)
    assert RD.cmd_next(d, TRD._cfg(maxRounds=CAP))["ok"]
    state = _state(d)
    assert not state.get("terminal")
    state["round"] = rnd
    # a later round has no panel to wait at (a saved one is retired on load), so the state waits at verify
    state["step"] = RD.P_VERIFY
    state["pending"] = None
    if extra is not None:
        state["extraAudit"] = extra
    RD.save_state(d, state)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_TERMINAL, out
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"


def test_t9_a_state_ordered_its_extra_round_is_not_handed_back_on_load(tmp_path, monkeypatch):
    d, _batch = _ordered(tmp_path, monkeypatch)
    out = RD.cmd_next(d)
    assert out["ok"] and out["action"] == RD.P_AUDITS, out
    assert not _state(d).get("terminal")


# --- the extra round composes no panel ---------------------------------------------------------------

def test_t11_a_surface_the_extra_round_cannot_derive_hands_back_instead_of_scheduling_a_panel(tmp_path, monkeypatch):
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    state = _state(d)
    state["_headDiffUnknown"] = True  # the cap round's post-fix head diff could not be resolved
    RD.save_state(d, state)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())
    assert out["ok"] is True, out
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert final["round"] == CAP + 1 and final["step"] == RD.P_TERMINAL
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_TERMINAL, n
    assert _state(d)["decisions"][-1]["kind"] == "extra-audit-open"


def test_t12_a_lane_that_would_need_a_panel_hands_back_instead_of_halting_for_a_recompose(tmp_path, monkeypatch):
    import lane_call
    d = _capped(tmp_path)
    _pin_head(monkeypatch, d)
    monkeypatch.setattr(lane_call, "call", lambda root, paths, proposed=None: {"floor": "full"})
    state = _state(d)
    state["config"]["seatMap"] = {"laneBasis": {"floor": None}}
    RD.save_state(d, state)
    out = RD.cmd_extra_audit(d, _order(tmp_path), "advisor", PR, readers=_readers())
    assert out["ok"] is True, out
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert not any(dec["kind"] == RD.LANE_EXPANDED_RECOMPOSE for dec in final["decisions"])


# --- T10: the record writer's backstop ---------------------------------------------------------------

def _extra_account(session_id):
    return TRR.account(sessionId=session_id,
                       rounds={"count": 3, "cap": 4, "stoppedAtCap": False, "extraAudit": {"why": WHY}})


def test_t10_the_writer_refuses_a_second_sessions_record_that_shows_the_extra_round(tmp_path):
    # axis: another session's earlier record that shows the round refuses this one's — see bite-proof record c1l4b_wo_a
    fake = TRR.Fake()
    first = RR.write(TRR.put(tmp_path, _extra_account("s-A")), str(tmp_path), fake.readers())
    assert first["ok"], first
    posted = len(fake.comments)
    out = RR.write(TRR.put(tmp_path, _extra_account("s-B"), "second.json"), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-record-extra-audit-repeated", out
    assert len(fake.comments) == posted


def test_t10_the_same_session_may_rewrite_its_own_record(tmp_path):
    fake = TRR.Fake()
    assert RR.write(TRR.put(tmp_path, _extra_account("s-A")), str(tmp_path), fake.readers())["ok"]
    again = RR.write(TRR.put(tmp_path, _extra_account("s-A"), "again.json"), str(tmp_path), fake.readers())
    assert again["ok"] is True, again


def test_t10_an_unreadable_earlier_record_never_blocks_a_write(tmp_path):
    fake = TRR.Fake()
    fake.comments.append({"id": 50, "author": "bot", "body": RR.MARKER + "\nnot a record", "url": "http://c/50"})
    out = RR.write(TRR.put(tmp_path, _extra_account("s-B")), str(tmp_path), fake.readers())
    assert out["ok"] is True, out
