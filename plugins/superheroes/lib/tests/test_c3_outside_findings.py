"""C3-A: a finding cited on a line the PR did not touch goes to the review record's "Outside this PR" list.

The invariant: every finding a compile sees whose cited (file, line) is not a line the PR touched lands once on the
state's top-level `outsideThisPR`, attributed to the seat or stage that raised it; it is never a compiled finding, never
a `compileDrops` row (so never under `refused`), never open work. The PR-body citation and a break-it
`scope_exempt` finding stay in scope. The lines the PR touched are the added lines plus the head line just before
and just after each run of deleted lines; a context line is not touched.

T1 a panel finding on an untouched file · T2 a context line of a changed file · T3 added and deletion-adjacent lines stay
in · T4 no cap: five outside findings, all kept · T5 a sweep entry is never merged into or counted · T6 dedupe ·
T7 attribution from the driver's own seat map and each stage name · T8 the extra audit's partition · T9 an abandoned
session does not list an outside finding open. Edges E1-E5 follow, then the parser's own cases (P1-P4).

Bite-proof record: c3_wo_a_outside
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import diff_scope  # noqa: E402
import pr_body_stage  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
from test_review_record_session import Fake, Session, extras, put_envelope, put_extras  # noqa: E402

CONSEQUENCE = "a defect stays in the change"

# src/a.py: head lines 1-7 are context except 3-4 (see the hunk below); the second hunk adds head line 19.
#   hunk 1  " l1" " l2" "-d3" "-d4" " l5" " l6" " l7"  -> head l1=1 l2=2 l5=3 l6=4 l7=5; touched {2, 3}
#   hunk 2  " c18" "+add19" " c20" " c21"              -> head 18..21; touched {19}
DIFF = (
    "diff --git a/src/a.py b/src/a.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/src/a.py\n"
    "+++ b/src/a.py\n"
    "@@ -1,7 +1,5 @@\n"
    " l1\n l2\n-d3\n-d4\n l5\n l6\n l7\n"
    "@@ -20,3 +18,4 @@\n"
    " c18\n+add19\n c20\n c21\n")
TOUCHED_ADDED = 19
TOUCHED_BEFORE_RUN = 2
TOUCHED_AFTER_RUN = 3
CONTEXT_FAR, CONTEXT_AFTER_RUN, CONTEXT_AFTER_ADDED = 1, 4, 20


def _finding(title, file="src/a.py", line=1, severity="Important", **extra):
    out = {"title": title, "file": file, "line": line, "severity": severity, "consequence": CONSEQUENCE,
           "body": "the body", "confidence": "High"}
    out.update(extra)
    return out


@pytest.fixture
def world(tmp_path):
    w = BL.World(tmp_path)
    w.state["reviewedDiff"] = DIFF
    return w


def _panel(world, **by_seat):
    """Fold one panel round whose seats return the given findings (`code_reviewer=[...]` -> seat `code-reviewer`)."""
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    for name, found in by_seat.items():
        seats[name.replace("_", "-")] = {"findings": list(found)}
    RD._fold(world.state, world.state["config"], RD.P_PANEL, {"seats": seats}, session_dir=str(world.session))
    return world.state


def _hits(state):
    """`[(source name, [(id, file, line, title)])]` for each entry on the state's outside list."""
    return [(e["source"]["name"], [(h["id"], h["file"], h["line"], h["title"]) for h in e["hits"]])
            for e in state.get("outsideThisPR") or []]


def _compile_drops(state):
    return [d for rec in state["rounds"].values() for d in rec.get("compileDrops") or []]


def _drop(title="t", file="a.py", line=3, source="code-reviewer"):
    return {"file": file, "line": line, "title": title, "reason": RD.COMPILE_DROP_OUTSIDE, "source": source}


def _account(tmp_path, state):
    """The account `review_record_session` builds from a session holding the driven state's rounds and outside list."""
    session = Session(tmp_path / "acct", rounds=state["rounds"], **(
        {"outsideThisPR": state["outsideThisPR"]} if "outsideThisPR" in state else {})).seat("code-reviewer").save()
    return session, rs.account_from_session(session, extras(), Fake().readers())


# ---- T1 ------------------------------------------------------------------------------------------------------


def test_t1_an_important_finding_on_a_file_the_diff_does_not_touch_is_outside_the_pr(world, tmp_path):
    # axis: the routing helper keeps an outside row out of compileDrops and out of the account's findings and refused — see bite-proof record c3_wo_a_outside
    state = _panel(world, code_reviewer=[_finding("Unrelated defect", file="src/other.py", line=4)])
    assert state["outsideThisPR"] == [{
        "source": {"kind": "reviewer", "name": "code-reviewer", "sweepId": None},
        "hits": [{"id": "O-1", "file": "src/other.py", "line": 4, "title": "Unrelated defect"}]}]
    assert state["_toVerify"] == []  # never staged, so never verified, fixed or blocking
    assert not state.get("findings") and not state.get("dispositionLedger")
    assert _compile_drops(state) == []
    assert state["rounds"]["1"]["compileDrops"] == []
    assert not any(f.get("severity") == "Important" for f in state.get("findings") or [])
    session, account = _account(tmp_path, state)
    assert account["outsideThisPR"] == state["outsideThisPR"]
    assert account["findings"] == [] and account["refused"] == []
    fake = Fake()
    assert rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers())["ok"]
    body = fake.marked()[-1]["body"]
    assert "Outside this PR (1)" in body and "For the advisor to sort at the vet." in body
    assert "O-1 src/other.py:4 · Unrelated defect (from code-reviewer)" in body
    shown = body.split("<details>")[0]  # the readable summary, before the raw record block
    assert "left for the owner" not in shown and shown.count("Unrelated defect") == 1  # no owner card, no finding row
    assert rr.read(7, readers=fake.readers())["outsideThisPR"] == state["outsideThisPR"]


# ---- T2 ------------------------------------------------------------------------------------------------------


def test_t2_a_finding_on_a_context_line_of_a_changed_file_is_outside(world, tmp_path):
    # axis: a context line is not a line the PR touched — see bite-proof record c3_wo_a_outside
    state = _panel(world, code_reviewer=[
        _finding("On a context line", line=CONTEXT_FAR),
        _finding("Context after the run", line=CONTEXT_AFTER_RUN),
        _finding("Context after an added line", line=CONTEXT_AFTER_ADDED)])
    assert _hits(state) == [("code-reviewer", [
        ("O-1", "src/a.py", CONTEXT_FAR, "On a context line"),
        ("O-2", "src/a.py", CONTEXT_AFTER_RUN, "Context after the run"),
        ("O-3", "src/a.py", CONTEXT_AFTER_ADDED, "Context after an added line")])]
    assert state["_toVerify"] == [] and _compile_drops(state) == []
    _session, account = _account(tmp_path, state)
    assert account["findings"] == [] and account["refused"] == []


# ---- T3 ------------------------------------------------------------------------------------------------------


def test_t3_added_and_deletion_adjacent_lines_stay_in_the_review(world):
    # axis: the line just before and just after a deletion run, and an added line, are touched — see bite-proof record c3_wo_a_outside
    state = _panel(world, code_reviewer=[
        _finding("On an added line", line=TOUCHED_ADDED),
        _finding("Just before the deletion", line=TOUCHED_BEFORE_RUN),
        _finding("Just after the deletion", line=TOUCHED_AFTER_RUN)])
    assert sorted(f["title"] for f in state["_toVerify"]) == [
        "Just after the deletion", "Just before the deletion", "On an added line"]
    assert "outsideThisPR" not in state and _compile_drops(state) == []


# ---- T4 ------------------------------------------------------------------------------------------------------


def test_t4_five_outside_findings_from_one_seat_are_all_kept_under_one_entry(world):
    # axis: no cap in code — every outside finding raised is kept — see bite-proof record c3_wo_a_outside
    found = [_finding("Outside %d" % n, file="src/other.py", line=n) for n in range(1, 6)]
    state = _panel(world, code_reviewer=found)
    assert _hits(state) == [("code-reviewer", [("O-%d" % n, "src/other.py", n, "Outside %d" % n) for n in range(1, 6)])]
    assert _compile_drops(state) == []


# ---- T5 ------------------------------------------------------------------------------------------------------

SWEEP = {"source": {"kind": "sweep", "name": "test-role", "sweepId": "sw-1"},
         "hits": [{"id": "O-%d" % n, "file": "s.py", "line": n, "title": "swept %d" % n} for n in range(1, 5)]}


def test_t5_a_sweep_entry_is_never_merged_into_or_counted_against_a_reviewer(world):
    # axis: a sweep entry is never a target and never counted to a reviewer, though it shares the seat's name — see bite-proof record c3_wo_a_outside
    world.state["outsideThisPR"] = [dict(SWEEP, hits=[dict(h) for h in SWEEP["hits"]])]
    state = _panel(world, test_role=[_finding("Outside A", file="src/other.py", line=1),
                                     _finding("Outside B", file="src/other.py", line=2)])
    first, second = state["outsideThisPR"]
    assert first == SWEEP  # unchanged, still its 4 hits together
    assert second == {"source": {"kind": "reviewer", "name": "test-role", "sweepId": None}, "hits": [
        {"id": "O-5", "file": "src/other.py", "line": 1, "title": "Outside A"},
        {"id": "O-6", "file": "src/other.py", "line": 2, "title": "Outside B"}]}
    assert len(state["outsideThisPR"]) == 2


# ---- T6 ------------------------------------------------------------------------------------------------------


def test_t6_folding_the_same_outside_drops_twice_leaves_one_hit_each(world):
    # axis: a hit already on that reviewer's entry adds nothing, so a re-fold never doubles it — see bite-proof record c3_wo_a_outside
    state = world.state
    drops = [_drop("one", line=1), _drop("two", line=2)]
    assert RD._record_outside(state, [dict(d) for d in drops]) == []
    assert RD._record_outside(state, [dict(d) for d in drops]) == []
    assert _hits(state) == [("code-reviewer", [("O-1", "a.py", 1, "one"), ("O-2", "a.py", 2, "two")])]
    # a second source with the same file, line and title is its own hit
    RD._record_outside(state, [_drop("one", line=1, source="seams check")])
    assert [(n, [h[0] for h in hits]) for n, hits in _hits(state)] == [("code-reviewer", ["O-1", "O-2"]), ("seams check", ["O-3"])]
    # and a re-fold of the same seams-check artifact through the driver adds nothing
    artifact = {"findings": [_finding("Swept", file="src/other.py", line=9)]}
    RD._fold_seams(state, state["config"], artifact)
    RD._fold_seams(state, state["config"], artifact)
    assert [h for n, hits in _hits(state) if n == "seams check" for h in hits if h[3] == "Swept"] == [
        ("O-4", "src/other.py", 9, "Swept")]


# ---- T7 ------------------------------------------------------------------------------------------------------


def test_t7_a_panel_finding_is_attributed_to_the_seat_that_returned_it_not_to_its_own_dimension(world):
    # axis: the source is the driver's own seat map, never a field the finding carries — see bite-proof record c3_wo_a_outside
    state = _panel(world, code_reviewer=[
        _finding("Labelled as another lens", file="src/other.py", line=1, dimension="security-reviewer")])
    assert _hits(state) == [("code-reviewer", [("O-1", "src/other.py", 1, "Labelled as another lens")])]


def test_t7_a_break_it_intercepted_copy_is_attributed_to_the_test_role(world):
    state = _panel(world, test_role=[BL._break_it_finding(file="src/other.py", line=1, dimension="Code")])
    assert [(n, [(h[1], h[2]) for h in hits]) for n, hits in _hits(state)] == [(break_it.ROLE, [("src/other.py", 1)])]


def test_t7_the_seams_check_scoped_finder_and_fix_auditor_carry_their_stage_names(world):
    outside = lambda title: _finding(title, file="src/other.py", line=1)  # noqa: E731
    # unit level: a named source, a per-finding map, a default
    a, b, c = outside("a"), outside("b"), outside("c")
    _compiled, drops = RD.mechanical_compile([a, b, c], DIFF, sources={id(a): "fix auditor"}, source="scoped finder")
    assert [d["source"] for d in drops] == ["fix auditor", "scoped finder", "scoped finder"]
    _compiled, drops = RD.mechanical_compile([outside("d")], DIFF)
    assert [d["source"] for d in drops] == ["reviewer"]
    state = world.state
    RD._fold_seams(state, state["config"], {"findings": [outside("From the seams check")]})
    state["_newIssues"] = [outside("From an audit during the scoped step")]
    RD._fold_scoped(state, state["config"], {"findings": [outside("From the scoped finder")]})
    state["_newIssues"] = [outside("Pending at the terminal")]
    RD._seed_pending_new_issues(state)
    state["_auditFirst"] = True
    state["_newIssues"] = [outside("From an audit before round one")]
    RD._after_audits(state, state["config"])
    assert [(n, [h[3] for h in hits]) for n, hits in _hits(state)] == [
        ("seams check", ["From the seams check"]),
        ("scoped finder", ["From the scoped finder"]),  # the scoped fold compiles the scoped finder's own findings first
        ("fix auditor", ["From an audit during the scoped step", "Pending at the terminal",
                         "From an audit before round one"])]
    assert _compile_drops(state) == []


# ---- T8 ------------------------------------------------------------------------------------------------------


@pytest.fixture
def extra_round(world, monkeypatch):
    """The extra audit round with every target discharged; the chokepoint and the hand-back are spied."""
    state = world.state
    state["extraAudit"] = {"round": state["round"]}
    state["_auditOutcome"] = {"notDischarged": []}
    calls = []
    monkeypatch.setattr(RD, "_terminal_converged", lambda s, c, full_panel: calls.append("converged"))
    return state, calls


def test_t8_an_extra_audit_new_issue_outside_the_pr_does_not_hand_the_pr_back(extra_round):
    # axis: a new issue cited outside the PR goes to the outside list and never holds the extra round open — see bite-proof record c3_wo_a_outside
    state, calls = extra_round
    state["_newIssues"] = [_finding("Raised by the audit", file="src/other.py", line=3)]
    RD._settle_extra_audit(state, state["config"])
    assert calls == ["converged"]
    assert state.get("terminal") != "handed-back"
    assert not [d for d in state["decisions"] if d["kind"] == "extra-audit-open"]
    assert _hits(state) == [("fix auditor", [("O-1", "src/other.py", 3, "Raised by the audit")])]
    assert not state.get("_newIssues")


def test_t8_an_extra_audit_new_issue_inside_the_pr_still_hands_the_pr_back(extra_round):
    state, calls = extra_round
    state["_newIssues"] = [_finding("Raised on an added line", line=TOUCHED_ADDED),
                           _finding("Raised outside", file="src/other.py", line=3)]
    RD._settle_extra_audit(state, state["config"])
    assert calls == []
    assert state["terminal"] == "handed-back"
    (decision,) = [d for d in state["decisions"] if d["kind"] == "extra-audit-open"]
    assert "Raised on an added line" in decision["detail"] and "Raised outside" not in decision["detail"]
    assert _hits(state) == [("fix auditor", [("O-1", "src/other.py", 3, "Raised outside")])]
    # the hand-back's terminal settle seeded the in-PR issue to the ledger; the outside one never reached it
    assert [r["title"] for r in state["dispositionLedger"]] == ["Raised on an added line"]


# ---- T9 ------------------------------------------------------------------------------------------------------

UNFOLDED = {"title": "Unfolded defect", "severity": "Important", "file": "u.py", "line": 8, "consequence": CONSEQUENCE}


def _abandoned(tmp_path, **state):
    s = Session(tmp_path, **{"terminal": None, **state}).seat("code-reviewer")
    session = s.save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": "m", "payload": {"findings": [UNFOLDED]}})
    return session


def test_t9_an_abandoned_session_does_not_list_a_finding_on_the_outside_list_as_open(tmp_path):
    # axis: a stored finding that is a hit on the outside list is not listed open a second time — see bite-proof record c3_wo_a_outside
    control = rs.account_from_session(_abandoned(tmp_path / "control"), extras(), Fake().readers(), abandoned="stopped")
    assert [f["title"] for f in control["findings"]] == ["Unfolded defect"]  # without the list the finding is open
    hit = {"id": "O-1", "file": "u.py", "line": "8", "title": "Unfolded defect"}  # a string line is read as its int
    for kind in ({"kind": "reviewer", "name": "code-reviewer", "sweepId": None},
                 {"kind": "sweep", "name": "code-reviewer", "sweepId": "sw-1"}):
        session = _abandoned(tmp_path / kind["kind"], outsideThisPR=[{"source": kind, "hits": [dict(hit, line=8)]}])
        account = rs.account_from_session(session, extras(), Fake().readers(), abandoned="stopped")
        assert account["findings"] == [] and account["refused"] == []
        assert account["outsideThisPR"][0]["hits"][0]["title"] == "Unfolded defect"
    # the control keeps the stored report's own source name and changes only the line, so only the line can keep it open
    other_line = _abandoned(tmp_path / "other", outsideThisPR=[{"source": {"kind": "reviewer", "name": "code-reviewer", "sweepId": None},
                                                                "hits": [dict(hit, line=9)]}])
    kept = rs.account_from_session(other_line, extras(), Fake().readers(), abandoned="stopped")
    assert [f["title"] for f in kept["findings"]] == ["Unfolded defect"]  # a hit at another line covers nothing


def _abandoned_in_rounds(tmp_path, reported_rounds, **state):
    """An abandoned session whose code-reviewer stored the one unfolded finding in each of `reported_rounds`."""
    s = Session(tmp_path, **{"terminal": None, "round": max(reported_rounds), "rounds": {str(n): {} for n in reported_rounds},
                             **state})
    for rnd in reported_rounds:
        s.seat("code-reviewer", rnd=rnd)
    session = s.save()
    for rnd in reported_rounds:
        put_envelope(session, "code-reviewer", {"vendor": "codex", "model": "m", "payload": {"findings": [UNFOLDED]}},
                     rnd=rnd)
    return session


def _round_one_hit(world):
    """The state after the driver sent the unfolded finding outside in round 1: the list and its round provenance."""
    state = world.state
    state["round"] = 1
    assert RD._record_outside(state, [_drop(UNFOLDED["title"], file=UNFOLDED["file"], line=UNFOLDED["line"])]) == []
    assert state["_outsideRounds"] == [
        {"title": UNFOLDED["title"], "file": UNFOLDED["file"], "line": UNFOLDED["line"], "round": 1}]
    return state


def test_t9_a_later_round_report_of_the_same_hit_is_listed_open_when_the_driver_kept_the_round(world, tmp_path):
    # axis: the driver's `_outsideRounds` provenance scopes the exclusion to the round that sent the hit outside, so a later round's report of the same title, file and line stays open — see bite-proof record c3_wo_a_outside
    state = _round_one_hit(world)
    carried = {"outsideThisPR": state["outsideThisPR"], "_outsideRounds": state["_outsideRounds"]}
    both = rs.account_from_session(_abandoned_in_rounds(tmp_path / "both", [1, 2], **carried), extras(), Fake().readers(),
                                   abandoned="stopped")
    assert [(f["title"], f["outcome"]) for f in both["findings"]] == [("Unfolded defect", None)]  # the round-2 report
    only_first = rs.account_from_session(_abandoned_in_rounds(tmp_path / "first", [1], **carried), extras(),
                                         Fake().readers(), abandoned="stopped")
    assert only_first["findings"] == [] and only_first["refused"] == []  # the round-1 report is the listed hit
    # control: the same session without the provenance rows reads as the legacy shape, which excludes every round
    legacy = rs.account_from_session(
        _abandoned_in_rounds(tmp_path / "legacy", [1, 2], outsideThisPR=state["outsideThisPR"]), extras(), Fake().readers(),
        abandoned="stopped")
    assert legacy["findings"] == []


def test_t9_an_unfolded_report_on_an_untouched_line_is_outside_not_open_work(tmp_path):
    # axis: a report the loop never folded that cites a line its round's diff did not touch is an outside finding, listed on the account's outside list and never as open work, so abandoning before the fold does not change how it is treated — see bite-proof record c3_wo_a_outside
    account = rs.account_from_session(_abandoned(tmp_path / "out", reviewedDiff=DIFF), extras(), Fake().readers(),
                                      abandoned="stopped")
    assert account["findings"] == [] and account["refused"] == []
    assert account["outsideThisPR"] == [{"source": {"kind": "reviewer", "name": "code-reviewer", "sweepId": None},
                                         "hits": [{"id": "O-1", "file": "u.py", "line": 8, "title": "Unfolded defect"}]}]
    # the same report on a line the diff touched stays open, and with no diff nothing is outside
    adds_line_8 = "diff --git a/u.py b/u.py\n--- a/u.py\n+++ b/u.py\n@@ -7,0 +8,1 @@\n+added\n"
    assert diff_scope.parse_touched_lines(adds_line_8) == {"u.py": {8}}
    touched = rs.account_from_session(_abandoned(tmp_path / "in", reviewedDiff=adds_line_8), extras(), Fake().readers(),
                                      abandoned="stopped")
    assert [f["title"] for f in touched["findings"]] == ["Unfolded defect"] and "outsideThisPR" not in touched
    # a hit already on the list keeps its place: the recovered one is numbered after it, under its own source
    listed = {"source": {"kind": "reviewer", "name": "x", "sweepId": None},
              "hits": [{"id": "O-1", "file": "z.py", "line": 1, "title": "Other"}]}
    both = rs.account_from_session(_abandoned(tmp_path / "both", reviewedDiff=DIFF, outsideThisPR=[listed]), extras(),
                                   Fake().readers(), abandoned="stopped")
    assert [(e["source"]["name"], [h["id"] for h in e["hits"]]) for e in both["outsideThisPR"]] == [
        ("x", ["O-1"]), ("code-reviewer", ["O-2"])]
    assert listed["hits"] == [{"id": "O-1", "file": "z.py", "line": 1, "title": "Other"}]  # the state's list is not edited


def test_t9_an_audit_candidate_matching_a_settled_ledger_row_on_an_untouched_line_is_outside_and_reopens_nothing(tmp_path):
    # axis: the scope check runs before a listed identity is handled, so a report that matches a settled ledger row but cites a line its round's diff did not touch is recovered as outside and never reopens that row — see bite-proof record c3_wo_a_outside
    candidate = dict(UNFOLDED)
    key = rs.sc.finding_identity_key(rs._normalized(candidate))
    adds_line_3 = "diff --git a/o.py b/o.py\n--- a/o.py\n+++ b/o.py\n@@ -2,0 +3,1 @@\n+added\n"  # touches only o.py
    adds_line_8 = "diff --git a/u.py b/u.py\n--- a/u.py\n+++ b/u.py\n@@ -7,0 +8,1 @@\n+added\n"
    for diff, outside_expected in ((adds_line_3, True), (adds_line_8, False)):
        row = {"findingKey": key, "title": candidate["title"], "outcome": "fixed", "reason": "r", "decidedBy": "auditor"}
        recovered = []
        out = rs._unfolded(str(tmp_path), [], {}, [row], settled_rounds={key: 2}, settled_kinds={key: "fixed"},
                           pending=[dict(candidate)], pending_round=2, reviewed_diff=diff, recovered=recovered)
        assert out == []
        if outside_expected:  # the earlier settlement stands and the report is recovered outside under its source
            assert row["outcome"] == "fixed" and recovered == [("fix auditor", candidate["title"], "u.py", 8)]
        else:  # control: a report the round's diff does touch still reopens the settled row
            assert row["outcome"] is None and row["reason"] == rs.UNFOLDED_OPEN and recovered == []


def _test_role_account(tmp_path, proposal, seat="test-role"):
    session = Session(tmp_path, terminal=None, reviewedDiff=DIFF).seat(seat).save()
    put_envelope(session, seat, {"vendor": "codex", "model": "m", "payload": {"findings": [proposal]}})
    return rs.account_from_session(session, extras(), Fake().readers(), abandoned="stopped")


@pytest.mark.parametrize("seat", ["test-role:s1", "test-role:w2u1"])
def test_t9_a_sliced_test_seats_unfolded_break_it_proposal_stays_open_like_the_whole_change_seats(tmp_path, seat):
    # axis: a sliced test seat (`test-role:<id>`) is the test role for the break-it scope exemption, by its lens, so its valid proposal stays open and is never recovered outside — see bite-proof record c2_wo8_merge_scoped_fixes
    valid = BL._break_it_finding(file=BL.TEST_PATH, line=1)
    account = _test_role_account(tmp_path / "valid", valid, seat)
    assert [f["title"] for f in account["findings"]] == [valid["title"]] and "outsideThisPR" not in account
    # control: the seat's lens only buys the exemption, so a proposal the intercept would not exempt is still outside
    off_line = _test_role_account(tmp_path / "off", dict(valid, line=8), seat)
    assert off_line["findings"] == []
    assert [(e["source"]["name"], [h["title"] for h in e["hits"]]) for e in off_line["outsideThisPR"]] == [
        (seat, [valid["title"]])]


def test_t9_an_unfolded_break_it_proposal_stays_open_only_when_the_intercept_would_exempt_it(tmp_path):
    # axis: the test role's own break-it proposal is scope-exempt at compile only when its block parses, names the cited file and cites line 1 (break_it.intercept's rule), so only such a proposal is never classified outside here — see bite-proof record c3_wo_a_outside
    valid = BL._break_it_finding(file=BL.TEST_PATH, line=1)
    account = _test_role_account(tmp_path / "valid", valid)
    assert [f["title"] for f in account["findings"]] == [valid["title"]] and "outsideThisPR" not in account
    line_text = _test_role_account(tmp_path / "text", dict(valid, line="1"))  # a citation that coerces to line 1 is exempt
    assert [f["title"] for f in line_text["findings"]] == [valid["title"]]
    # not exempt at compile, so outside here too: another line, a block for another path, a malformed or missing block
    for name, proposal in (("line", dict(valid, line=8)),
                           ("path", dict(valid, file="u.py")),
                           ("malformed", dict(valid, suggestion="break-it-test v1\nnot a block")),
                           ("none", dict(valid, suggestion=None))):
        account = _test_role_account(tmp_path / name, proposal)
        assert account["findings"] == [], name
        assert [h["title"] for e in account["outsideThisPR"] for h in e["hits"]] == [valid["title"]], name
        assert account["outsideThisPR"][0]["source"]["name"] == "test-role", name


def test_t9_a_hit_held_by_one_source_does_not_hide_the_same_place_reported_by_another(tmp_path):
    # axis: the exclusion holds only for a hit under the report's own source name (seat, or stage name), so a hit held by one source never hides the same place reported by another — see bite-proof record c3_wo_a_outside
    hit = {"id": "O-1", "file": "u.py", "line": 8, "title": "Unfolded defect"}

    def held_by(name):
        return [{"source": {"kind": "reviewer", "name": name, "sweepId": None}, "hits": [dict(hit)]}]

    # held under another source: the code-reviewer's report is recovered under its own entry, after the existing hit
    other = rs.account_from_session(_abandoned(tmp_path / "other", reviewedDiff=DIFF, outsideThisPR=held_by("seams check")),
                                    extras(), Fake().readers(), abandoned="stopped")
    assert other["findings"] == []
    assert [(e["source"]["name"], [h["id"] for h in e["hits"]]) for e in other["outsideThisPR"]] == [
        ("seams check", ["O-1"]), ("code-reviewer", ["O-2"])]
    # held under its own source: nothing is added
    own = rs.account_from_session(_abandoned(tmp_path / "own", reviewedDiff=DIFF, outsideThisPR=held_by("code-reviewer")),
                                  extras(), Fake().readers(), abandoned="stopped")
    assert [(e["source"]["name"], [h["id"] for h in e["hits"]]) for e in own["outsideThisPR"]] == [
        ("code-reviewer", ["O-1"])]
    # a stage's report is named by the stage: a seams-check report is not hidden by the panel seat's hit, and is by its own
    for held, expected in (("code-reviewer", [("code-reviewer", ["O-1"]), ("seams check", ["O-2"])]),
                           ("seams check", [("seams check", ["O-1"])])):
        s = Session(tmp_path / ("stage-" + held.replace(" ", "-")), terminal=None, reviewedDiff=DIFF, outsideThisPR=held_by(held))
        s.seat("code-reviewer", phase="dispatch-seams-check")
        session = s.save()
        put_envelope(session, "code-reviewer", {"vendor": "codex", "model": "m", "payload": {"findings": [UNFOLDED]}},
                     phase="dispatch-seams-check")
        account = rs.account_from_session(session, extras(), Fake().readers(), abandoned="stopped")
        assert account["findings"] == []
        assert [(e["source"]["name"], [h["id"] for h in e["hits"]]) for e in account["outsideThisPR"]] == expected


# ---- T10 -----------------------------------------------------------------------------------------------------


def test_t10_an_abandoned_session_does_not_list_a_blank_file_finding_the_compile_already_refused(world, tmp_path):
    # axis: a blank-file uncited drop keeps the finding's line, so the session record's drop key matches the stored report and the finding is not listed open again — see bite-proof record c3_wo_a_outside
    blank = _finding("Blank file defect", file=" ", line=1)
    state = _panel(world, code_reviewer=[blank])
    rows = [d for d in _compile_drops(state) if d.get("title") == "Blank file defect"]
    assert len(rows) == 1 and rows[0]["line"] == 1 and rows[0]["file"] == " "
    assert rows[0]["reason"] == "uncited — no file:line" and "outsideThisPR" not in state
    session = Session(tmp_path / "stored", terminal=None, rounds=state["rounds"]).seat("code-reviewer").save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": "m", "payload": {"findings": [blank]}})
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned="stopped")
    assert account["findings"] == []  # not listed open: it is already refused
    assert [r["title"] for r in account["refused"]] == ["Blank file defect"]
    # control: a drop row without the line (the shape before this rule) does not match the stored report
    stripped = {k: dict(v) for k, v in state["rounds"].items()}
    for rec in stripped.values():
        for d in rec.get("compileDrops") or []:
            d.pop("line", None)
    control = Session(tmp_path / "control", terminal=None, rounds=stripped).seat("code-reviewer").save()
    put_envelope(control, "code-reviewer", {"vendor": "codex", "model": "m", "payload": {"findings": [blank]}})
    again = rs.account_from_session(control, extras(), Fake().readers(), abandoned="stopped")
    assert [f["title"] for f in again["findings"]] == ["Blank file defect"]


# ---- fail-closed edges ----------------------------------------------------------------------------------------


def test_e1_no_diff_means_nothing_is_outside():
    found = [_finding("Anywhere", file="src/other.py", line=1)]
    compiled, drops = RD.mechanical_compile(list(found), None)
    assert [f["title"] for f in compiled] == ["Anywhere"] and drops == []
    state = {"reviewedDiff": None, "extraAudit": {"round": 1}, "round": 1, "_newIssues": list(found)}
    assert RD._route_outside_new_issues(state, list(found)) == found
    assert "outsideThisPR" not in state and state["_newIssues"] == found


def test_e2_an_unreadable_line_or_file_is_never_routed_outside():
    cases = [_finding("Text line", line="not-a-number"), _finding("No line", line=None),
             _finding("List file", file=["a.py"]), _finding("Bool line", line=True)]
    _compiled, drops = RD.mechanical_compile(cases, DIFF)
    assert [d["reason"] for d in drops] == [RD.COMPILE_DROP_LINE_NOT_INTEGER, "uncited — no file:line",
                                            "uncited — no file:line", RD.COMPILE_DROP_LINE_NOT_INTEGER]
    state = {"reviewedDiff": DIFF, "_newIssues": list(cases)}
    assert RD._route_outside_new_issues(state, list(cases)) == cases
    assert "outsideThisPR" not in state
    assert RD._record_outside(state, list(drops)) == drops


def test_e2_the_pr_body_citation_and_a_scope_exempt_finding_stay_in_scope():
    body = _finding("PR body", file=pr_body_stage.CITATION, line=1)
    exempt = _finding("Exempt", file="src/other.py", line=1)
    compiled, drops = RD.mechanical_compile([body, exempt], DIFF, scope_exempt={id(exempt)})
    assert sorted(f["title"] for f in compiled) == ["Exempt", "PR body"] and drops == []
    state = {"reviewedDiff": DIFF, "_newIssues": [body]}
    assert RD._route_outside_new_issues(state, [body]) == [body]


def test_e3_a_blank_or_missing_title_still_makes_a_valid_hit():
    state = {}
    rest = RD._record_outside(state, [_drop(title=None, line=1), _drop(title="  ", line=2), _drop(title=7, line=3)])
    assert rest == []
    assert [h["title"] for h in state["outsideThisPR"][0]["hits"]] == ["untitled finding"] * 3
    assert rr._outside_fault(state["outsideThisPR"][0]) is None


def test_e4_an_outside_list_that_is_not_a_list_is_replaced_not_crashed_on():
    for bad in ("x", {"hits": []}, 7, None):
        state = {"outsideThisPR": bad}
        assert RD._record_outside(state, [_drop()]) == []
        assert _hits(state) == [("code-reviewer", [("O-1", "a.py", 3, "t")])]


def test_e5_the_other_drops_come_back_unchanged_and_no_hit_means_no_key():
    state = {}
    others = [{"file": "a.py", "line": 1, "title": "t", "reason": RD.COMPILE_DROP_NO_CONSEQUENCE}, "odd"]
    assert RD._record_outside(state, list(others)) == others
    assert RD._record_outside(state, None) == [] and RD._record_outside(state, []) == []
    assert "outsideThisPR" not in state


# ---- the parser: P1-P4 ---------------------------------------------------------------------------------------


def test_p1_touched_lines_of_the_fixture_diff():
    assert diff_scope.parse_touched_lines(DIFF) == {"src/a.py": {2, 3, 19}}
    assert diff_scope.parse_diff_lines(DIFF)["src/a.py"] >= {1, 2, 3, 4, 5, 18, 19, 20, 21}  # unchanged: anchors include context


def test_p2_a_deletion_at_a_hunk_start_has_no_line_before_and_one_that_ends_the_file_marks_the_counter():
    start = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -5,3 +5,1 @@\n-gone1\n-gone2\n keep\n")
    assert diff_scope.parse_touched_lines(start) == {"x.py": {5}}
    end = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,1 @@\n keep\n-gone1\n-gone2\n")
    assert diff_scope.parse_touched_lines(end) == {"x.py": {1, 2}}  # line 2 may not exist in the file; harmless


def test_p3_crlf_diffs_and_no_newline_markers_and_several_files():
    # x.py: " keep"(1) " keep2"(2) "-old" -> the line before the run is 2; the marker ends nothing, so "+new" (3) and
    # "+new2" (4) are still added lines; if the marker ended the hunk, 3 would still be marked (the line after the run) but 4 would not
    text = ("diff --git a/x.py b/x.py\r\n--- a/x.py\r\n+++ b/x.py\r\n@@ -1,3 +1,4 @@\r\n keep\r\n keep2\r\n-old\r\n"
            "\\ No newline at end of file\r\n+new\r\n+new2\r\n"
            "diff --git a/y.py b/y.py\r\n--- a/y.py\r\n+++ b/y.py\r\n@@ -1,2 +1,3 @@\r\n a\r\n+b\r\n c\r\n")
    assert diff_scope.parse_touched_lines(text) == {"x.py": {2, 3, 4}, "y.py": {2}}


def test_p4_a_deleted_file_and_a_no_prefix_diff_have_no_anchorable_line():
    gone = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a\n-b\n"
    assert diff_scope.parse_touched_lines(gone) == {}
    no_prefix = "--- x.py\n+++ x.py\n@@ -1,1 +1,2 @@\n a\n+b\n"
    assert diff_scope.parse_touched_lines(no_prefix) == {}
