"""C4 layer 2: a repository sweep in the review record, and its recovery from an abandoned session.

The invariant: when a session is abandoned after searcher results were stored and before their sweep folded, every hit
those results carry is recovered exactly as the fold would have routed it: an outside hit under that sweep's own
`kind: "sweep"` entry on the account's "Outside this PR" list (once), an inside hit as an open finding that is never
fixed and never dropped, and a dropped or covered hit not at all. Searchers never appear as reviewers on the record, in
any session.

R1 outside and inside hits · R2 the same place from two parts · R3 covered, malformed and PR-body hits · R4 a folded sweep
· R5 no searcher is a reviewer · R6 a completed session with a sweep reads reviewed · R7 the ungraded reason · R8 the
PR-body citation is never outside · R9 no readable scope · E2-E10 the fail-closed edges.

Bite-proof record: c4_wo2b_recovery
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

import pr_body_stage  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import session_contract as sc  # noqa: E402
from test_review_record_session import (  # noqa: E402
    CODEX, EARLIER, GOOD_RUN, HEAD, Fake, Session, extras, ledger_row, put_envelope, put_extras,
)

CONSEQUENCE = "a defect stays in the change"
REASON = "owner stopped the loop"
SWEEP_PHASE = "dispatch-sweep"
SEAT_1, SEAT_2 = "searcher:S-1:1", "searcher:S-1:2"
REVIEWER = "code-reviewer (round 1)"  # the one reviewer row every session here holds
UNFOLDED_REASON = "found by a repository sweep that never reached the verifier before the loop was closed"
UNGRADED_REASON = "a repository-sweep hit the verifier did not grade"
# the PR touches u.py line 8 only
DIFF = "diff --git a/u.py b/u.py\n--- a/u.py\n+++ b/u.py\n@@ -7,0 +8,1 @@\n+added\n"
PARENT = {"title": "Retry without a cap", "file": "p.py", "line": 5, "severity": "Important", "consequence": CONSEQUENCE,
          "kindOfMistake": {"kind": "unchecked retry", "places": [{"file": "c.py", "line": 9}]}}
PENDING = {"sweepId": "S-1", "findingKey": sc.finding_identity_key(PARENT), "title": PARENT["title"], "file": "p.py",
           "line": 5, "searchDescription": {"kind": "unchecked retry", "looksLike": "a retry with no cap", "examples": []}}
INSIDE = {"file": "u.py", "line": 8, "what": "inside copy"}
OUTSIDE = {"file": "o.py", "line": 3, "what": "outside copy"}
REVIEWER_ENTRY = {"source": {"kind": "reviewer", "name": "code-reviewer", "sweepId": None},
                  "hits": [{"id": "O-1", "file": "z.py", "line": 1, "title": "Z"}]}


def _hit_key(hit, parent=None):
    """The identity key the fold would mint for an inside hit."""
    return sc.finding_identity_key(sc.sweep_hit_finding(hit, PENDING, parent or {**PARENT, **PENDING}))


def _stored(root, results, abandoned=True, rounds=None, seats=(), **state):
    """A session dir whose searchers stored `results` (seat key -> payload) and whose sweep S-1 is still pending."""
    base = {"terminal": None, "round": 1, "reviewedDiff": DIFF, "_sweepPending": [dict(PENDING)],
            "_sweepCarry": [dict(PARENT)], "rounds": rounds or {"1": {}}}
    if not abandoned:
        base = {"terminal": "converged", "round": 1, "rounds": rounds or {"1": {}}}
    s = Session(root, **{**base, **state}).seat("code-reviewer")
    for seat in results:
        s.seat(seat, phase=SWEEP_PHASE)
    session = s.save()
    for seat, payload in results.items():
        put_envelope(session, seat, {"vendor": "claude", "model": "haiku", "payload": payload}, phase=SWEEP_PHASE)
    return session


def _account(session, abandoned=REASON):
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned=abandoned)
    rr._validate(account)  # the review record's own validator
    return account


def _sweep_entries(account):
    return [e for e in account.get("outsideThisPR") or [] if e["source"]["kind"] == "sweep"]


def _hits(*hits):
    return {"hits": list(hits)}


# ---- R1 ------------------------------------------------------------------------------------------------------


def test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open(tmp_path):
    # axis: a stored searcher result is read from the search slots, which `_slots` never holds — see bite-proof record c4_wo2b_recovery
    # axis: a recovered sweep hit lands under its sweep's own entry, never a reviewer's — see bite-proof record c4_wo2b_recovery
    session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, outsideThisPR=[REVIEWER_ENTRY])
    account = _account(session)
    assert account["outsideThisPR"][0] == REVIEWER_ENTRY
    assert _sweep_entries(account) == [{"source": {"kind": "sweep", "name": "searchers", "sweepId": "S-1"},
                                        "hits": [{"id": "O-2", "file": "o.py", "line": 3, "title": "outside copy"}]}]
    (finding,) = account["findings"]
    assert (finding["title"], finding["file"], finding["line"], finding["severity"]) == ("inside copy", "u.py", 8, "Important")
    assert finding["outcome"] is None and finding["reason"] == UNFOLDED_REASON and finding["reviewer"] == SEAT_1
    assert finding["findingKey"] == _hit_key(INSIDE) and finding["consequence"] == CONSEQUENCE
    assert not any(r["outcome"] == "fixed" for r in account["findings"])


def test_r1_the_written_record_reads_not_reviewed_and_renders_the_sweep_entry(tmp_path):
    session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)})
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers(), abandoned=REASON)
    assert out["ok"] and out["status"] == "not-reviewed", out
    record = rr.read(7, readers=fake.readers())
    assert [e["source"] for e in record["outsideThisPR"]] == [{"kind": "sweep", "name": "searchers", "sweepId": "S-1"}]
    assert "from sweep S-1 by searchers" in fake.marked()[-1]["body"]
    assert [(f["title"], f["outcome"], f["reason"]) for f in record["findings"]] == [("inside copy", None, UNFOLDED_REASON)]


# ---- R2 ------------------------------------------------------------------------------------------------------


def test_r2_the_same_hit_stored_by_two_parts_is_recovered_once_and_the_first_what_wins(tmp_path):
    # axis: the same place found twice is one hit, the first kept — see bite-proof record c4_wo2b_recovery
    session = _stored(tmp_path, {SEAT_2: _hits(dict(OUTSIDE, what="second"), dict(INSIDE, what="second")),
                                 SEAT_1: _hits(dict(OUTSIDE, what="first"), dict(INSIDE, what="first"))})
    account = _account(session)
    assert [h["title"] for e in _sweep_entries(account) for h in e["hits"]] == ["first"]  # part order, not storage order
    assert [f["title"] for f in account["findings"]] == ["first"]


# ---- R3 ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("hit", [
    pytest.param({"file": "p.py", "line": 5, "what": "the parent's own place"}, id="parent-place"),
    pytest.param({"file": "c.py", "line": 9, "what": "a place of the kind"}, id="kind-place"),
])
def test_r3_a_covered_hit_recovers_nothing(tmp_path, hit):
    # axis: a hit at the parent's own place or one of its places is covered, neither inside nor outside — see bite-proof record c4_wo2b_recovery
    account = _account(_stored(tmp_path, {SEAT_1: _hits(hit)}))
    assert account["findings"] == [] and _sweep_entries(account) == []


@pytest.mark.parametrize("hit", [
    pytest.param({"file": "", "line": 3, "what": "x"}, id="blank-file"),
    pytest.param({"line": 3, "what": "x"}, id="no-file"),
    pytest.param({"file": "o.py", "line": "3", "what": "x"}, id="string-line"),
    pytest.param({"file": "o.py", "line": True, "what": "x"}, id="bool-line"),
    pytest.param({"file": "o.py", "what": "x"}, id="no-line"),
    pytest.param("not an object", id="not-an-object"),
])
def test_r3_a_malformed_hit_recovers_nothing(tmp_path, hit):
    account = _account(_stored(tmp_path, {SEAT_1: _hits(hit)}))
    assert account["findings"] == [] and _sweep_entries(account) == []


def test_r3_a_pr_body_citation_hit_recovers_nothing(tmp_path):
    # axis: a hit citing the PR body is dropped and counted, never classified — see bite-proof record c4_wo2b_recovery
    account = _account(_stored(tmp_path, {SEAT_1: _hits({"file": pr_body_stage.CITATION, "line": 8, "what": "body"})}))
    assert account["findings"] == [] and _sweep_entries(account) == []


# ---- R4 ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("held", [
    pytest.param({"_sweepPending": []}, id="folded-and-cleared"),
    pytest.param({"_sweepPending": [dict(PENDING, sweepId="S-2")]}, id="another-sweep"),
    pytest.param({"_sweepPending": None}, id="not-a-list"),
])
def test_r4_a_sweep_no_longer_pending_recovers_nothing_a_second_time(tmp_path, held):
    # axis: a sweep no longer pending was folded and its hits are in the state, so it recovers nothing — see bite-proof record c4_wo2b_recovery
    state = dict(held, outsideThisPR=[REVIEWER_ENTRY])
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, **state))
    assert account["findings"] == [] and _sweep_entries(account) == []


def test_r4_a_state_with_no_pending_key_recovers_nothing(tmp_path):
    session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)})
    path = os.path.join(session, "loop-state.json")
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    del state["_sweepPending"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    account = _account(session)
    assert account["findings"] == [] and _sweep_entries(account) == []


def test_r4_a_sweep_already_folded_with_its_hits_in_the_state_adds_nothing_twice(tmp_path):
    # the fold put the outside hit on the list and the inside hit in the live findings; a sweep still marked pending
    # (the verifier pass had not finished) must not list either a second time
    folded_entry = {"source": {"kind": "sweep", "name": "searchers", "sweepId": "S-1"},
                    "hits": [{"id": "O-2", "file": "o.py", "line": 3, "title": "outside copy"}]}
    live = {"findingKey": _hit_key(INSIDE), "id": "f-9", "title": "inside copy", "severity": "Important", "file": "u.py",
            "line": 8, "detail": "d", "dimension": "code-reviewer"}
    session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, outsideThisPR=[REVIEWER_ENTRY, folded_entry],
                      findings=[live])
    account = _account(session)
    assert [h["id"] for e in account["outsideThisPR"] for h in e["hits"]] == ["O-1", "O-2"]
    assert [f["id"] for f in account["findings"]] == ["f-9"]


# ---- R5 ------------------------------------------------------------------------------------------------------


def _names(reviewers):
    return [v.get("name") for v in reviewers]


def test_r5_no_searcher_is_a_reviewer_in_an_abandoned_session(tmp_path):
    # axis: `_slots` keeps review slots only, so a searcher is never a reviewer row — see bite-proof record c4_wo2b_recovery
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE), SEAT_2: _hits(OUTSIDE)}))
    assert not [n for n in _names(account["reviewers"]) if "searcher" in str(n)]
    assert _names(account["reviewers"]) == [REVIEWER]


def test_r5_no_searcher_is_a_reviewer_in_a_completed_session(tmp_path):
    session = _stored(tmp_path, {SEAT_1: _hits(INSIDE), SEAT_2: _hits(OUTSIDE)}, abandoned=False)
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    record = rr.read(7, readers=fake.readers())
    assert [v["name"] for v in record["reviewers"]] == [REVIEWER]
    assert "searcher" not in json.dumps(record["reviewers"])
    assert [(phase, seat) for (phase, _r, seat, _o) in rs._search_slots(rs._journal(session))] == [
        (SWEEP_PHASE, SEAT_1), (SWEEP_PHASE, SEAT_2)]
    assert not [k for k in rs._slots(rs._journal(session)) if k[0] == SWEEP_PHASE]


# ---- R6 ------------------------------------------------------------------------------------------------------


def test_r6_a_completed_session_with_a_sweep_and_a_passing_review_reads_reviewed(tmp_path):
    sweep_row = {"sweepId": "S-1", "findingKey": "k", "title": "t", "file": "a.py", "line": 3, "parts": 1, "missing": [],
                 "inside": 0, "outside": 0, "covered": 0, "dropped": 0, "ungraded": 0}
    s = Session(tmp_path, dispositionLedger=[ledger_row()],
                rounds={"1": {"fix": {"fixes": [{"title": "t", "file": "a.py"}]}, "sweeps": [sweep_row]}},
                seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}])
    s.seat("code-reviewer", head=HEAD, nonce="n1").seat(SEAT_1, phase=SWEEP_PHASE, head=HEAD)
    session = s.save()
    put_envelope(session, SEAT_1, {"vendor": "claude", "model": "haiku", "payload": _hits(OUTSIDE)}, phase=SWEEP_PHASE)
    runs = {"/run/n1": (dict(GOOD_RUN, runnerNonce="n1", viewHeadSha=HEAD), None)}
    fake = Fake(runs=runs)
    out = rs.write_from_session(session, put_extras(tmp_path, extras(ci="green", runDirs=["/run/n1"])), str(tmp_path),
                                fake.readers())
    assert out["ok"] and out["status"] == "reviewed", out
    assert [v["name"] for v in rr.read(7, readers=fake.readers())["reviewers"]] == [REVIEWER]


# ---- R7 ------------------------------------------------------------------------------------------------------


def _ungraded_session(tmp_path, keys):
    hit = {"title": "ungraded site", "severity": "Important", "file": "u.py", "line": 8, "consequence": CONSEQUENCE}
    key = sc.finding_identity_key(hit)
    row = ledger_row(key=key, title="ungraded site", file="u.py", line=8)
    row.pop("disposition")
    row.pop("dispositionRound")
    row.pop("dispositionSeq")
    sweep = {"sweepId": "S-1", "findingKey": "k", "title": "t", "file": "a.py", "line": 3, "parts": 1, "missing": [],
             "inside": 1, "outside": 0, "covered": 0, "dropped": 0, "ungraded": 1}
    if keys is not None:
        sweep["ungradedKeys"] = [key] if keys else []
    return Session(tmp_path, dispositionLedger=[row], rounds={"1": {"sweeps": [sweep]}}).seat("code-reviewer").save(), key


def test_r7_an_ungraded_sweep_hit_reads_open_with_the_reason_it_was_withheld(tmp_path):
    # axis: a sweep hit the verifier did not grade reads open with that reason, not the generic one — see bite-proof record c4_wo2b_recovery
    session, key = _ungraded_session(tmp_path, keys=True)
    account = rs.account_from_session(session, extras(), Fake().readers())
    (finding,) = account["findings"]
    assert finding["findingKey"] == key and finding["outcome"] is None and finding["reason"] == UNGRADED_REASON
    fake = Fake()
    assert rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers())["ok"]
    assert [(f["outcome"], f["reason"]) for f in rr.read(7, readers=fake.readers())["findings"]] == [(None, UNGRADED_REASON)]


def test_r7_a_driven_session_keeps_the_withheld_hits_key_and_the_record_reads_its_reason(tmp_path):
    # axis: the withheld hit's identity key is kept on its sweep row so the record can give the reason it stayed open — see bite-proof record c4_wo2b_recovery
    import test_c4_sweep as c4  # noqa: E402
    run = c4.Driven(tmp_path / "run", [c4._finding()], hits={("S-1", 1): [c4._hit(19, what="ungraded site")]},
                    silent=("ungraded site",))
    run.drive()
    state = run.state()
    (row,) = state["rounds"]["1"]["sweeps"]
    (ledger,) = [e for e in state[sc.DISPOSITION_LEDGER_KEY] if e.get("title") == "ungraded site"]
    assert row["ungraded"] == 1 and row["ungradedKeys"] == [sc.finding_identity_key(ledger)]
    # the ledger as it stood before the end-of-loop settle gave each open row its own disposition
    ledger = [{k: v for k, v in e.items() if not k.startswith("disposition")} for e in state[sc.DISPOSITION_LEDGER_KEY]]
    session = Session(tmp_path / "acct", dispositionLedger=ledger, rounds=state["rounds"]).seat("code-reviewer").save()
    finding = [f for f in rs.account_from_session(session, extras(), Fake().readers())["findings"]
               if f["title"] == "ungraded site"]
    assert [(f["outcome"], f["reason"]) for f in finding] == [(None, UNGRADED_REASON)]


@pytest.mark.parametrize("keys", [pytest.param(None, id="no-ungradedKeys"), pytest.param(False, id="empty-ungradedKeys")])
def test_r7_a_sweep_row_with_no_ungraded_keys_leaves_the_generic_reason(tmp_path, keys):
    session, _key = _ungraded_session(tmp_path, keys=keys)
    (finding,) = rs.account_from_session(session, extras(), Fake().readers())["findings"]
    assert finding["outcome"] is None and finding["reason"] == rs.STILL_OPEN


# ---- R8 ------------------------------------------------------------------------------------------------------


def test_r8_the_pr_body_citation_is_never_outside_the_round():
    # axis: the PR-body citation is in scope whatever the diff touches, so it is never recovered as outside — see bite-proof record c4_wo2b_recovery
    scope = {"u.py": {8}}
    assert rs._outside_the_round({"file": pr_body_stage.CITATION, "line": 3}, scope) is None
    assert rs._outside_the_round({"file": "x.py", "line": 3}, scope) == 3  # control: another file on that line is outside
    assert rs._outside_the_round({"file": "u.py", "line": 8}, scope) is None  # and a touched line is not


def test_r8_a_stored_reviewer_report_citing_the_pr_body_is_open_work_never_recovered_as_outside(tmp_path):
    report = {"title": "PR body is wrong", "severity": "Important", "file": pr_body_stage.CITATION, "line": 4,
              "consequence": CONSEQUENCE}
    s = Session(tmp_path, terminal=None, reviewedDiff=DIFF).seat("code-reviewer")
    session = s.save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": [report]}})
    account = _account(session)
    assert [(f["title"], f["outcome"]) for f in account["findings"]] == [("PR body is wrong", None)]
    assert account.get("outsideThisPR") in (None, [])


# ---- R9 ------------------------------------------------------------------------------------------------------


def test_r9_a_result_with_no_readable_scope_is_recovered_as_outside_only(tmp_path):
    # axis: with no readable scope no hit is known to be on a touched line, so every hit is recovered outside and none as open work — see bite-proof record c4_wo2b_recovery
    session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, reviewedDiff=None)
    account = _account(session)
    assert account["findings"] == []
    assert [(h["file"], h["line"]) for e in _sweep_entries(account) for h in e["hits"]] == [("u.py", 8), ("o.py", 3)]


# ---- fail-closed edges ---------------------------------------------------------------------------------------


def test_e1_no_stored_searcher_result_recovers_nothing(tmp_path):
    account = _account(_stored(tmp_path, {}))
    assert account["findings"] == [] and "outsideThisPR" not in account


@pytest.mark.parametrize("payload", [
    pytest.param({"hits": "nope"}, id="hits-not-a-list"),
    pytest.param({"hits": None}, id="hits-null"),
    pytest.param({}, id="no-hits"),
    pytest.param(["not", "a", "dict"], id="payload-not-an-object"),
])
def test_e2_a_stored_result_that_is_not_a_hit_list_recovers_nothing(tmp_path, payload):
    account = _account(_stored(tmp_path, {SEAT_1: payload, SEAT_2: _hits(OUTSIDE)}))
    assert [h["title"] for e in _sweep_entries(account) for h in e["hits"]] == ["outside copy"]  # the sound part still counts
    assert account["findings"] == []


@pytest.mark.parametrize("seat", ["searcher:S-1", "searcher::1", "searcher:S-1:x", "searcher:S-1:-1", "searcher:S-1:"])
def test_e3_a_seat_key_that_does_not_parse_recovers_nothing(tmp_path, seat):
    assert rs._sweep_of_seat(seat) is None
    account = _account(_stored(tmp_path, {seat: _hits(INSIDE, OUTSIDE)}))
    assert account["findings"] == [] and _sweep_entries(account) == []
    assert rs._sweep_of_seat(SEAT_2) == ("S-1", 2)


def test_e6_a_parent_missing_from_pending_and_carry_still_recovers_both_kinds_without_a_crash(tmp_path):
    bare = {"sweepId": "S-1"}
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, _sweepPending=[bare], _sweepCarry=[]))
    assert [h["title"] for e in _sweep_entries(account) for h in e["hits"]] == ["outside copy"]
    (finding,) = account["findings"]
    assert finding["title"] == "inside copy" and finding["outcome"] is None and finding["severity"] is None
    assert finding["reason"] == UNFOLDED_REASON


@pytest.mark.parametrize("carry", [None, "x", [None, 5]])
def test_e6_a_carry_that_is_not_a_list_of_findings_is_ignored(tmp_path, carry):
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, _sweepCarry=carry))
    assert [h["title"] for e in _sweep_entries(account) for h in e["hits"]] == ["outside copy"]
    assert [f["title"] for f in account["findings"]] == ["inside copy"]


@pytest.mark.parametrize("held", [None, "x", {"a": 1}])
def test_e8_an_outside_list_that_is_absent_or_not_a_list_still_takes_the_sweep_hit(tmp_path, held):
    account = _account(_stored(tmp_path, {SEAT_1: _hits(OUTSIDE)}, outsideThisPR=held))
    assert [(e["source"]["kind"], [h["id"] for h in e["hits"]]) for e in account["outsideThisPR"]] == [("sweep", ["O-1"])]


def test_e9_an_inside_hit_already_listed_is_not_listed_twice(tmp_path):
    live = {"findingKey": _hit_key(INSIDE), "id": "f-9", "title": "inside copy", "severity": "Important", "file": "u.py",
            "line": 8, "detail": "d", "dimension": "code-reviewer"}
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE)}, findings=[live]))
    assert [f["id"] for f in account["findings"]] == ["f-9"]


def test_e10_a_sweep_row_with_a_malformed_ungraded_keys_reads_as_empty(tmp_path):
    session, _key = _ungraded_session(tmp_path, keys=None)
    path = os.path.join(session, "loop-state.json")
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    state["rounds"]["1"]["sweeps"][0]["ungradedKeys"] = "not a list"
    state["rounds"]["1"]["sweeps"].append("not a row")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    (finding,) = rs.account_from_session(session, extras(), Fake().readers())["findings"]
    assert finding["reason"] == rs.STILL_OPEN
