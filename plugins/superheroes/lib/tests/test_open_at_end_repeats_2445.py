"""A finding left for the owner only because it was open when its loop ended counts as open for repeat matching (#2445).

The settle marks it `openAtLoopEnd: true` (ledger row and review-record finding); `repeat_marks.decision_outcome` reads a
marked earlier finding as open (rule 4), on both repeat routes, for an earlier record and an earlier round of the
session. A deliberate deferral (out of scope, a cited or pending ruling) is never marked and keeps rule 3.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo1_open_at_end_2445.md
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as rr  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_outcome_settle_c7 import CANON_ID, OTHER_ID, SOURCES, _finding, _row, _staged_state  # noqa: E402
from test_review_record import Fake, account, build, finding, put  # noqa: E402
from test_review_record_repeats_c1l8 import lfo, mark, session_account  # noqa: E402
from test_review_record_session import KEY, ledger_row  # noqa: E402

RD = TRD.RD
SC, RM, FO = RD.session_contract, RD.repeat_marks, RD.finding_outcomes
MARK = SC.OPEN_AT_LOOP_END_FIELD
ROUTES = ["judge", "exact"]
OPEN_REASON = "still open when the review loop ended (halted)"
CITED = {"kind": "canon", "ref": CANON_ID}
KEPT = {"outcome": "left-for-owner", "reason": "repeat of x; keeps its earlier outcome (left-for-owner)"}
LFO = {"outcome": "left-for-owner", "reason": OPEN_REASON}
REAL = _finding("Real", 1, "Important", "real")
REAL_KEY = "f.py::real@L1"


def _raw(title, line=4):
    return {"file": "f.py", "line": line, "title": title, "severity": "Important", "consequence": "lost work"}


def _record_finding(raw, outcome="left-for-owner", **extra):
    row = dict(raw, findingKey=RM.opaque_key(raw), outcome=outcome, reason=OPEN_REASON, decidedBy=None)
    row.update(extra)
    return row


def _record_pool(*findings):
    entries, why = RM.read_earlier_findings({"ok": True, "findings": list(findings), "finalCommit": {"sha": "a" * 40}})
    assert why is None
    return RM.build_pool(RD.new_state(TRD._cfg()), 2, entries)


def _decision(pool, raw, route):
    """`decide`'s answer for a confirmed repeat of pool entry e1, found by the judge's name or by exact identity."""
    staged = [dict(raw if route == "exact" else dict(raw, title=raw["title"] + ", reworded"), id="v1")]
    refs = RM.judge_refs([{"group_id": "g", "member_ids": ["v1"], "repeatOf": "e1"}]) if route == "judge" else {}
    entry, source = RM.mark_repeats(staged, pool, refs)["v1"]
    assert source == route
    return RM.decide(RM.decision_outcome(entry), "confirmed", True)


def _session_pool(state):
    return RM.build_pool(state, 2, [])


def _halted(raw=REAL, **dispositions):
    """A session state holding ``raw`` open (given any ledger ``dispositions`` first), ready for its loop to end."""
    state = _staged_state([raw])
    for disposition, fields in dispositions.items():
        RD._record_disposition(state, REAL_KEY, disposition, 1, **fields)
    return state


# ---- a: settle -------------------------------------------------------------------------------------

def test_a_settle_marks_only_a_bare_open_leftover_asked_to_mark_it():
    real, quality = _finding("Bug", 1, "Important", "real"), _finding("Tidy", 1, "Important", "code-quality")
    assert FO.settle(real, open_reason="open", open_at_end=True) == {
        "outcome": "left-for-owner", "reason": "open", "decidedBy": None, MARK: True}
    for plain in (FO.settle(real, open_reason="open"), FO.settle(real, open_reason="open", open_at_end=False)):
        assert plain["outcome"] == "left-for-owner" and MARK not in plain
    unresolved = FO.settle(real, ruling={"decidedBy": {"kind": "canon", "ref": OTHER_ID}}, sources=SOURCES,
                           open_reason="open", open_at_end=True)
    assert unresolved["outcome"] == "left-for-owner" and unresolved["decidedBy"] and MARK not in unresolved
    ruled = FO.settle(real, ruling={"decidedBy": CITED}, sources=SOURCES, open_reason="open", open_at_end=True)
    assert ruled["outcome"] == "ruling" and MARK not in ruled
    craft = FO.settle(quality, open_reason="open", open_at_end=True)
    assert craft["outcome"] == "craft" and MARK not in craft


# ---- b, c: a record's finding, judge-named and exact -------------------------------------------------

@pytest.mark.parametrize("route", ROUTES)
def test_b_c_a_repeat_of_a_record_finding_left_open_at_loop_end_is_new_without_changing_the_pooled_outcome(route):
    raw = _raw("record bug")
    marked, bare = _record_finding(raw, **{MARK: True}), _record_finding(raw)
    pool = _record_pool(marked)
    assert (pool[0]["outcome"], pool[0][MARK]) == ("left-for-owner", True)
    assert RM.order_list(pool)[0] == {"ref": "e1", "id": None, "file": "f.py", "line": 4, "title": "record bug",
                                      "outcome": "left-for-owner"}
    assert _decision(pool, raw, route) == (False, None)
    assert RM.decide(RM.decision_outcome(RM.record_entry(marked)), "confirmed", True) == (False, None)
    assert _decision(_record_pool(bare), raw, route) == (True, None)  # the same entry without the marker is kept
    assert RM.decide(RM.decision_outcome(RM.record_entry(bare)), "confirmed", True) == (True, None)


# ---- d: healthy siblings and fail-closed readers -----------------------------------------------------

@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("extra", [{"reason": "out of scope: later; " + OPEN_REASON}, {"decidedBy": CITED}],
                         ids=["out-of-scope", "cited-ruling"])
def test_d_a_deliberate_deferral_in_a_record_is_still_kept(extra, route):
    raw = _raw("deferred")
    assert _decision(_record_pool(_record_finding(raw, **extra)), raw, route) == (True, None)


@pytest.mark.parametrize("over", [
    {MARK: "true"}, {MARK: 1}, {MARK: "yes"}, {MARK: None}, {MARK: False},
    {MARK: True, "decidedBy": CITED}, {MARK: True, "outcome": "craft"}, {MARK: True, "outcome": "fixed"},
    {MARK: True, "outcome": None}], ids=str)
def test_d_record_entry_ignores_a_marker_that_is_not_exactly_true_or_sits_beside_a_decision_or_another_outcome(over):
    entry = RM.record_entry(_record_finding(_raw("x"), **over))
    assert MARK not in entry and RM.decision_outcome(entry) == entry["outcome"]


def test_d_the_one_reader_is_an_identity_check_on_true():
    rows = ({MARK: True}, {MARK: "true"}, {MARK: 1}, {MARK: None}, {}, None, "x")
    assert [SC.open_at_loop_end(r) for r in rows] == [True, False, False, False, False, False, False]
    assert MARK in SC.DISPOSITION_FAMILY_FIELDS
    assert RM.decision_outcome({"outcome": "left-for-owner", MARK: "true"}) == "left-for-owner"
    assert RM.decision_outcome({"outcome": "left-for-owner", MARK: True}) is None


# ---- e: the session's own ledger ----------------------------------------------------------------------

@pytest.mark.parametrize("route", ROUTES)
def test_e_a_row_settled_open_when_the_loop_ended_carries_the_marker_and_its_repeat_is_new(route):
    state = _halted()
    RD._set_terminal(state, "halted")
    row = _row(state, "Real")
    assert row["disposition"] == "left-for-owner" and row[MARK] is True and "decidedBy" not in row
    (entry,) = _session_pool(state)
    assert (entry["outcome"], entry[MARK], RM.decision_outcome(entry)) == ("left-for-owner", True, None)
    assert _decision(_session_pool(state), REAL, route) == (False, None)


@pytest.mark.parametrize("route", ROUTES)
def test_e_an_out_of_scope_row_settled_the_same_way_carries_no_marker_and_is_kept(route):
    state = _halted(**{"out-of-scope": {"outOfScopeReason": "later"}})
    RD._set_terminal(state, "halted")
    row = _row(state, "Real")
    assert row["settledReason"].startswith("out of scope: later; ") and MARK not in row
    assert MARK not in _session_pool(state)[0]
    assert _decision(_session_pool(state), REAL, route) == (True, None)


@pytest.mark.parametrize("cited", [None, {"kind": "canon", "ref": OTHER_ID}], ids=["uncited", "cited"])
def test_e_an_out_of_scope_row_a_newer_bound_decision_overrode_is_marked_unless_that_decision_cites_one(
        monkeypatch, cited):
    state = _halted(**{"out-of-scope": {"outOfScopeReason": "later"}})
    bound = {"findingKey": REAL_KEY, "ruling": "guidance", "seq": 1, "reason": "try again", "decidedBy": cited}
    monkeypatch.setattr(RD, "_row_decision", lambda *args: bound)
    monkeypatch.setattr(RD, "_decision_sources", lambda s: copy.deepcopy(SOURCES))
    state["sentUnderDecision"] = {REAL_KEY: 1}  # the guidance reached a fixer, so no ruling is pending
    RD._set_terminal(state, "halted")
    row = _row(state, "Real")
    assert row["disposition"] == "left-for-owner" and not row["settledReason"].startswith("out of scope: ")
    assert (MARK in row) == (cited is None)
    assert row.get("decidedBy") == cited or cited is None


def test_e_a_pending_undispatched_owner_ruling_is_never_marked(monkeypatch):
    state = _halted()
    bound = {"findingKey": REAL_KEY, "ruling": "guidance", "seq": 1, "reason": "try again", "decidedBy": None}
    monkeypatch.setattr(RD, "_row_decision", lambda *args: bound)
    RD._set_terminal(state, "halted")
    row = _row(state, "Real")
    assert "never sent to a fixer" in row["settledReason"] and MARK not in row


@pytest.mark.parametrize("out_of_scope", [False, True], ids=["open", "out-of-scope"])
def test_e_the_ungraded_sweep_reason_swap_never_adds_or_removes_the_marker(out_of_scope):
    state = _halted(**({"out-of-scope": {"outOfScopeReason": "later"}} if out_of_scope else {}))
    state["rounds"].setdefault("1", {})["sweeps"] = [{"ungradedKeys": [REAL_KEY]}]
    RD._set_terminal(state, "halted")
    row = _row(state, "Real")
    assert row["settledReason"] == RD.SWEEP_UNGRADED_REASON and (MARK in row) == (not out_of_scope)


def test_e_a_merged_member_reads_its_representatives_marker():
    state = _staged_state([_finding("Rep", 1, "Important", "real"), _finding("Member", 2, "Important", "real")])
    RD._record_merged_into(state, "f.py::member@L2", "f.py::rep@L1")
    RD._set_terminal(state, "halted")
    pool = _session_pool(state)
    assert {e["title"]: e.get(MARK) for e in pool} == {"Rep": True, "Member": True}
    assert [RM.decide(RM.decision_outcome(e), "confirmed", True) for e in pool] == [(False, None)] * 2


def test_e_a_newer_disposition_replaces_the_settle_and_the_marker_with_it():
    state = _halted()
    RD._set_terminal(state, "halted")
    assert _row(state, "Real")[MARK] is True
    RD._record_disposition(state, REAL_KEY, "fixed", 1, dispositionReceipt="r")
    assert MARK not in _row(state, "Real")


def test_e_session_entry_reads_the_marker_only_from_a_bare_left_for_owner_row_that_is_not_a_kept_repeat():
    def entry(**over):
        row = ledger_row(disposition="left-for-owner", settledReason=OPEN_REASON, **over)
        return RM.session_entry(row, 3, ({KEY: row}, {}, {}))
    assert entry(**{MARK: True})[MARK] is True
    for over in ({}, {MARK: "true"}, {MARK: 1}, {MARK: True, "decidedBy": CITED}, {MARK: True, "repeatKept": KEPT}):
        read = entry(**over)
        assert read["outcome"] == "left-for-owner" and MARK not in read and RM.decision_outcome(read) == "left-for-owner"


# ---- f: the record writer ------------------------------------------------------------------------------

@pytest.mark.parametrize("over,marked", [
    ({MARK: True}, True), ({}, False), ({MARK: "true"}, False), ({MARK: True, "decidedBy": CITED}, False),
    ({MARK: True, "repeatKept": KEPT}, False),
    ({MARK: True, "disposition": "out-of-scope", "outOfScopeReason": "later"}, False)],
    ids=["marked", "unmarked", "not-true", "cited", "kept-repeat", "out-of-scope"])
def test_f_the_account_carries_the_marker_only_for_a_bare_open_at_loop_end_settle(tmp_path, over, marked):
    row = ledger_row(**{"disposition": "left-for-owner", "settledReason": OPEN_REASON, **over})
    (found,) = session_account(tmp_path, [row])["findings"]
    assert found["outcome"] == "left-for-owner" and (found.get(MARK) is True) == marked and (MARK in found) == marked


@pytest.mark.parametrize("over", [
    {MARK: "yes"}, {MARK: 1}, {MARK: None}, {MARK: True, "outcome": "fixed", "reason": "fixed in 1a2b3c4"},
    {MARK: True, "decidedBy": CITED}], ids=str)
def test_f_the_validator_refuses_a_marker_that_is_not_true_or_sits_on_another_outcome_or_beside_a_decision(
        tmp_path, over):
    fake = Fake()
    acct = account(findings=[finding("code-001", **{**LFO, **over})])
    out = rr.write(put(tmp_path, acct), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "findings[0].openAtLoopEnd")
    assert fake.writes == []


def test_f_the_validator_accepts_a_true_marker_on_a_left_for_owner_finding():
    rec = build(account(findings=[finding("code-001", **LFO, **{MARK: True})]))
    assert [f.get(MARK) for f in rec["findings"]] == [True]


def test_f_the_normalisation_pass_drops_the_marker_a_carried_recheck_or_an_owner_ruling_made_stale():
    marked = finding("code-001", **LFO, **{MARK: True})
    marked = dict(marked, findingKey=rr._key(marked))
    other = finding("code-002", title="other", **LFO)
    assert rr._drop_stale_open_marker([marked, other])[0] is marked  # a bare left-for-owner finding keeps it
    cited = rr._apply_owner_rulings([marked], [marked], [{"key": "code-001", "url": "u", "words": "w"}])
    assert MARK in cited[0] and cited[0]["decidedBy"], "premise: the ruling pass leaves the marker beside a citation"
    assert MARK not in rr._drop_stale_open_marker(cited)[0]
    head = "a" * 40
    check = {"key": "code-001", "settled": "fixed", "commit": "b" * 40, "checkedHead": head, "evidence": "the guard holds"}
    moved, _ = rr._recheck_carried([marked], [check], head, lambda commit, at: True, {"findings": [marked]})
    assert moved[0]["outcome"] == "fixed" and MARK in moved[0], "premise: the carried re-check leaves the marker on a fixed one"
    dropped = rr._drop_stale_open_marker(moved)[0]
    assert MARK not in dropped and dropped["outcome"] == "fixed"


def test_f_a_record_built_from_a_marked_finding_an_owner_ruling_cites_is_written_without_the_marker():
    marked = finding("code-001", **LFO, **{MARK: True})
    plain = build(account(findings=[marked]))["findings"][0]
    assert plain[MARK] is True and plain["outcome"] == "left-for-owner"
    ruled = build(account(findings=[marked], ownerRulings=[{"key": "code-001", "url": "u", "words": "go"}]))["findings"][0]
    assert ruled["outcome"] == "left-for-owner" and ruled["decidedBy"]["kind"] == "owner-ruling" and MARK not in ruled


# ---- g: _seed_ledger_entry -----------------------------------------------------------------------------

def test_g_re_raising_a_row_settled_open_at_loop_end_keeps_its_real_consequence():
    real = {"file": "f.py", "line": 1, "title": "Bug", "severity": "Minor", "consequence": "lost work",
            "consequenceKind": "real"}

    def reraised(strip_marker):
        state = RD.new_state({"repoRoot": "/nonexistent-review-project"})
        RD._stage_findings(state, [real])
        RD._set_findings(state, state["_toVerify"])
        RD._set_terminal(state, "halted")
        row = state[SC.DISPOSITION_LEDGER_KEY][0]
        assert row["disposition"] == "left-for-owner" and row[MARK] is True
        if strip_marker:
            del row[MARK]
        RD._set_terminal(state, None)
        state["round"] = 2
        RD._stage_findings(state, [dict(real, severity="Important", consequence="harder to read",
                                        consequenceKind="code-quality")])
        return state[SC.DISPOSITION_LEDGER_KEY][0]

    kept = reraised(strip_marker=False)
    assert kept["consequenceKind"] == "real" and "lost work" in kept["consequence"]
    assert reraised(strip_marker=True)["consequenceKind"] == "code-quality"  # control: the marker is what holds it


# ---- h: item-417 grouping --------------------------------------------------------------------------------

def test_h_two_repeats_of_a_marked_left_for_owner_original_hold_one_owner_card():
    record = [lfo("e", "e-key", **{MARK: True}), lfo("r1", "r1-key", repeatOf=mark("e-key")),
              lfo("r2", "r2-key", repeatOf=mark("e-key"))]
    assert [rr.repeat_held_elsewhere(f, record) for f in record] == [False, True, True]


# ---- i: the driver's own repeat path (`_fold_synthesis` -> `_repeat_plan` -> `decision_outcome`) ----------

import test_repeat_marks_c1l8 as C8  # noqa: E402


def _driver_state(*record_findings):
    entries, why = RM.read_earlier_findings(C8._record_payload(list(record_findings)))
    assert why is None
    return C8._state(earlierFindings=entries)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("marked", [True, False], ids=["marked", "unmarked"])
def test_i_the_driver_routes_a_repeat_of_a_marked_record_finding_as_new_and_keeps_an_unmarked_one(marked, route):
    raw = C8._raw("record bug", line=4)
    stored = _record_finding(raw, **({MARK: True} if marked else {}))
    state = _driver_state(stored)
    new = raw if route == "exact" else C8._raw("record bug, reworded", line=4)
    C8._verify(state, [new], {new["title"]: "CONFIRMED"})
    C8._synth(state, [C8._group(C8._ids(state)[new["title"]], ref="e1")] if route == "judge" else None)
    row = C8._row(state, new)
    assert row["repeatOf"]["findingKey"] == stored["findingKey"]
    if marked:  # rule 4: a new finding, still linked to the original, going to the fix
        assert "repeatKept" not in row and C8._titles(state) == [new["title"]] and C8._batch(state) == [new["title"]]
    else:  # rule 3: kept with the earlier outcome, no fix
        assert row["repeatKept"]["outcome"] == "left-for-owner" and C8._titles(state) == [] and C8._batch(state) == []


def test_i_an_exact_code_quality_repeat_of_a_marked_record_finding_keeps_its_real_consequence_to_the_settle():
    raw = C8._raw("record bug", line=4, consequence="lost work", consequenceKind="real")
    state = _driver_state(_record_finding(raw, **{MARK: True}))
    tidy = dict(raw, severity="Minor", consequence="harder to read", consequenceKind="code-quality")
    C8._verify(state, [tidy], {tidy["title"]: "CONFIRMED"})
    C8._synth(state, None)
    row = C8._row(state, tidy)
    assert "repeatKept" not in row and row["consequenceKind"] == "real" and "lost work" in row["consequence"]
    RD._set_terminal(state, "halted")
    settled = C8._row(state, tidy)
    assert settled["disposition"] == "left-for-owner" and settled[MARK] is True  # never craft


def test_i_a_judge_named_code_quality_repeat_keeps_its_own_consequence():
    # the judge route leaves the original as its own record finding (it is carried), so nothing is merged
    raw = C8._raw("record bug", line=4, consequence="lost work", consequenceKind="real")
    state = _driver_state(_record_finding(raw, **{MARK: True}))
    tidy = C8._raw("record bug, reworded", line=4, severity="Minor", consequence="harder to read",
                   consequenceKind="code-quality")
    C8._verify(state, [tidy], {tidy["title"]: "CONFIRMED"})
    C8._synth(state, [C8._group(C8._ids(state)[tidy["title"]], ref="e1")])
    assert C8._row(state, tidy)["consequenceKind"] == "code-quality"


def test_i_a_reopened_consequence_survives_a_synthesis_merge_into_another_code_quality_finding():
    raw = C8._raw("record bug", line=4, consequence="lost work", consequenceKind="real")
    state = _driver_state(_record_finding(raw, **{MARK: True}))
    tidy = dict(raw, severity="Minor", consequence="harder to read", consequenceKind="code-quality")
    other = C8._raw("tidy neighbour", line=9, severity="Minor", consequence="harder to read",
                    consequenceKind="code-quality")
    C8._verify(state, [tidy, other], {tidy["title"]: "CONFIRMED", other["title"]: "CONFIRMED"})
    ids = C8._ids(state)
    C8._synth(state, [C8._group(ids[tidy["title"]], ids[other["title"]])])
    reps = [r for r in state[SC.DISPOSITION_LEDGER_KEY] if not r.get(SC.MERGED_INTO_FIELD)]
    assert len(reps) == 1 and reps[0]["consequenceKind"] == "real", reps
    RD._set_terminal(state, "halted")
    rep = next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if not r.get(SC.MERGED_INTO_FIELD))
    assert rep["disposition"] == "left-for-owner", rep  # the merged representative is never settled as craft
