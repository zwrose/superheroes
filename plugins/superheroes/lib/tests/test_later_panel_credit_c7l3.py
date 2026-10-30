"""C7 L3 (WO-3): a finding a fixer reported fixed, that a later COMPLETE full panel did not raise
again, ends `fixed` — never a leftover — provided the fix report came after the finding's latest raise.

Drives the real round driver: the fold functions (`_stage_findings`, `_fold_apply_fixes`, `_fold_panel`) over
a staged state for each edge, and `run_loop` with scripted seams through to a terminal and
`review_record_session.account_from_session` for the vet's case (a converged loop whose fix a later
full panel confirmed, with no fix audit).

Measured: a `fixes` entry is the orchestrator's git-derived record and names no finding, so the credit
keys on the identity keys the fixer fold records beside it (`fixReportedKeys`), never on wording.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c7l3_wo3_driver.md
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

import review_record_session as rs  # noqa: E402
import session_contract as SC  # noqa: E402
import test_review_record_session as TRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

CONSEQUENCE = "users lose their saved work"
RECEIPT = {"kind": SC.FULL_PANEL_NOT_RERAISED, "panelRound": 2}


def _finding(title="Bug", line=1):
    return {"file": "f.py", "line": line, "title": title, "severity": "Important",
            "consequence": CONSEQUENCE, "consequenceKind": "real"}


def _key(title="Bug", line=1):
    return "f.py::%s@L%d" % (title.lower(), line)


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


def _round_one_state(*findings):
    """A state at the end of round 1: the findings staged, verified and live."""
    state = RD.new_state(TRD._cfg_cert())
    compiled, _ = RD.mechanical_compile([dict(f) for f in findings], TRD.DIFF)
    RD._stage_findings(state, compiled)
    RD._set_findings(state, state["_toVerify"])
    return state


def _fix(state, *, fixes=True, batch=None):
    """The round's apply-fixes report folds. No head diff comes back, so the next round is a full panel
    over the git-derived diff (no fix audit sits between the fix and the panel)."""
    state["_fixBatch"] = [dict(f) for f in (batch if batch is not None else state["findings"])]
    artifact = {"fixes": [{"file": "f.py", "summary": "guard restored"}] if fixes else []}
    RD._fold_apply_fixes(state, state["config"], artifact,
                   changed_subjects_seam=lambda *args: ["Code"],
                   panel_diff_seam=lambda config, head: (TRD.DIFF, None))


def _panel(state, raised=(), missing=()):
    """Fold a full panel at the state's round: every dimension runs but `missing`, and the code
    reviewer raises `raised`."""
    seats = {dim: {"findings": [], "confidence": "high"}
             for dim in RD._panel_dimensions(state["config"]) if dim not in missing}
    seats["code-reviewer"]["findings"] = [dict(f) for f in raised]
    RD._fold_panel(state, state["config"], {"seats": seats})


def _credited(state, key):
    row = _ledger(state)[key]
    return (row.get("disposition") == "fixed"
            and row.get("dispositionReceipt") == dict(RECEIPT, panelRound=state["round"]))


def test_a_fix_a_later_complete_panel_did_not_raise_again_is_fixed():
    state = _round_one_state(_finding())
    _fix(state)
    assert state["round"] == 2
    assert "disposition" not in _ledger(state)[_key()]
    _panel(state)
    row = _ledger(state)[_key()]
    assert row["disposition"] == "fixed"
    assert row["dispositionRound"] == 2
    assert row["dispositionReceipt"] == RECEIPT


def test_the_fixer_fold_records_the_keys_it_was_handed_beside_its_fix_report():
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state)
    assert sorted(state["rounds"]["1"]["fixReportedKeys"]) == sorted([_key(), _key("Other", 2)])
    assert state["rounds"]["1"]["fix"]["fixes"]


@pytest.mark.parametrize("seat_override", [{"confidence": "low"}, {"tier": "reviewer"}])
def test_a_complete_panel_that_does_not_qualify_gives_no_credit(seat_override):
    state = _round_one_state(_finding())
    _fix(state)
    seats = {dim: {"findings": [], "confidence": "high"} for dim in RD._panel_dimensions(state["config"])}
    seats["code-reviewer"].update(seat_override)
    RD._fold_panel(state, state["config"], {"seats": seats})
    assert state["fullPanelRan"] is True
    assert _ledger(state)[_key()].get("disposition") != "fixed"


def test_an_incomplete_panel_gives_no_credit():
    """axis: only a complete panel can confirm a fix by silence — an incomplete one may simply not have
    looked — see bite-proof record c7l3_wo3_driver"""
    state = _round_one_state(_finding())
    _fix(state)
    absent = next(d for d in RD._panel_dimensions(state["config"]) if d != "code-reviewer")
    _panel(state, missing=(absent,))
    assert state["fullPanelRan"] is False
    row = _ledger(state)[_key()]
    assert "disposition" not in row and "dispositionReceipt" not in row


def test_a_first_round_panel_gives_no_credit():
    state = _round_one_state(_finding())
    # a fix report that names the finding, held at round 1: nothing earlier than round 1 exists
    state["rounds"].setdefault("1", {})["fix"] = {"fixes": [{"file": "f.py"}]}
    state["rounds"]["1"]["fixReportedKeys"] = [_key()]
    _panel(state)
    assert state["round"] == 1
    assert "disposition" not in _ledger(state)[_key()]


def test_a_finding_the_panel_raises_again_gets_no_credit():
    state = _round_one_state(_finding())
    _fix(state)
    _panel(state, raised=[_finding()])
    row = _ledger(state)[_key()]
    assert "disposition" not in row and "dispositionReceipt" not in row
    assert row["raisedRound"] == 2


def test_a_fix_reported_before_the_latest_raise_gives_no_credit():
    """axis: a fix report made before the finding's latest raise says nothing about the raise after
    it — see bite-proof record c7l3_wo3_driver"""
    state = _round_one_state(_finding())
    _fix(state)                                   # fix reported in round 1
    _panel(state, raised=[_finding()])            # raised again in round 2
    state["round"] = 3                            # round 3's panel omits it; round 2 fixed nothing
    state["rounds"].setdefault("3", {})
    _panel(state)
    row = _ledger(state)[_key()]
    assert row["raisedRound"] == 2
    assert "disposition" not in row and "dispositionReceipt" not in row


def test_a_fix_reported_after_the_latest_raise_is_credited_by_the_next_complete_panel():
    state = _round_one_state(_finding())
    _fix(state)
    _panel(state, raised=[_finding()])            # raised again in round 2
    state["_fixBatch"] = [dict(f) for f in state["findings"]]
    _fix(state)                                   # fixed again in round 2 (after the re-raise)
    assert state["round"] == 3
    _panel(state)
    assert _ledger(state)[_key()]["disposition"] == "fixed"
    assert _ledger(state)[_key()]["dispositionReceipt"] == dict(RECEIPT, panelRound=3)


def test_a_fix_report_with_no_fixes_gives_no_credit():
    state = _round_one_state(_finding())
    _fix(state, fixes=False)
    _panel(state)
    assert "disposition" not in _ledger(state)[_key()]


def test_a_finding_the_fixer_was_not_handed_gets_no_credit():
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state, batch=[f for f in _round_one_state(_finding())["findings"]])
    _panel(state)
    ledger = _ledger(state)
    assert ledger[_key()]["disposition"] == "fixed"
    assert "disposition" not in ledger[_key("Other", 2)]


def test_a_finding_that_already_has_a_current_disposition_is_unchanged():
    state = _round_one_state(_finding())
    _fix(state)
    RD._record_disposition(state, _key(), "fixed", 2, dispositionReceipt={"headSha": "abc"})
    before = dict(_ledger(state)[_key()])
    _panel(state)
    assert _ledger(state)[_key()] == before
    assert before["dispositionReceipt"] == {"headSha": "abc"}


def test_a_finding_merged_into_another_is_skipped_and_its_representative_is_credited():
    state = _round_one_state(_finding(), _finding("Twin", 2))
    RD._record_merged_into(state, _key("Twin", 2), _key())
    _fix(state)
    _panel(state)
    ledger = _ledger(state)
    assert ledger[_key()]["disposition"] == "fixed"
    assert "disposition" not in ledger[_key("Twin", 2)]


def test_an_out_of_scope_ruling_is_not_overwritten():
    state = _round_one_state(_finding())
    RD._record_disposition(state, _key(), "out-of-scope", 1, outOfScopeReason="a later change")
    _fix(state)
    _panel(state)
    assert _ledger(state)[_key()]["disposition"] == "out-of-scope"


def test_a_credited_finding_is_not_settled_as_a_leftover():
    state = _round_one_state(_finding())
    _fix(state)
    _panel(state)
    RD._set_terminal(state, "converged")
    row = _ledger(state)[_key()]
    assert row["disposition"] == "fixed"
    assert "settledReason" not in row


_FIXER_FOLD_REFUSAL = "forced refusal at the fixer fold"


def _called_from_fixer_fold(depth):
    """True when the frame `depth` levels up from this helper is `_fold_apply_fixes`."""
    return sys._getframe(depth).f_code.co_name == "_fold_apply_fixes"


def _fixed_without_audit_seams():
    """A loop whose fixer reports a fix and returns no head diff and whose fixer-fold derivation
    refuses: the next round is a full panel, which does not raise the finding again."""
    def reviewer(dim, tier, rnd, ctx):
        return [_finding()] if rnd == 1 and dim == "code-reviewer" else []

    def fix_step(batch, rnd, payload):
        return {"fixes": [{"file": "f.py", "summary": "guard restored"}],
                "changedSubjects": ["Code"]}

    def panel_diff(config, head):
        if _called_from_fixer_fold(2):
            return None, _FIXER_FOLD_REFUSAL
        return TRD.HEAD, None

    seams = TRD._seams(reviewer=reviewer, fix_step=fix_step)
    seams["panel_diff"] = panel_diff
    return seams


def test_a_converged_loop_whose_fix_a_later_full_panel_confirmed_reports_it_fixed(tmp_path):
    result, state = TRD._run_loop_capturing_state(_fixed_without_audit_seams(), TRD._cfg_cert())
    assert state["terminal"] == "converged", state.get("certification")
    assert state["fullPanelRan"] is True
    assert not state.get("auditRounds")             # no fix audit ran
    row = _ledger(state)[_key()]
    assert row["disposition"] == "fixed" and row["dispositionReceipt"] == RECEIPT

    session = TRS.Session(tmp_path, **state).seat("code-reviewer")
    account = rs.account_from_session(session.save(), TRS.extras(), TRS.Fake().readers())
    outcomes = {f["findingKey"]: f["outcome"] for f in account["findings"]}
    assert outcomes == {_key(): "fixed"}


def test_a_reraised_member_of_a_merged_group_withholds_the_representatives_credit():
    state = _round_one_state(_finding(), _finding("Twin", 2))
    RD._record_merged_into(state, _key(), _key("Twin", 2))
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Twin"])
    _panel(state, raised=[_finding()])
    assert "disposition" not in _ledger(state)[_key("Twin", 2)]


def test_a_reraise_the_compile_drops_gets_no_credit():
    state = _round_one_state(_finding())
    _fix(state)
    no_consequence = {k: v for k, v in _finding().items() if k != "consequence"}
    _panel(state, raised=[no_consequence])
    assert not _credited(state, _key())


def test_the_receipt_kind_has_one_home_read_by_writer_and_record():
    assert RD.FULL_PANEL_NOT_RERAISED == SC.FULL_PANEL_NOT_RERAISED == RECEIPT["kind"]


def test_state_and_mirror_land_in_one_commit(tmp_path, monkeypatch):
    """A stop after the commit seals leaves neither file written; recovery replays both."""
    d = str(tmp_path)
    state = RD.new_state(TRD._cfg_cert())
    real_begin = RD.round_commit.begin
    monkeypatch.setattr(RD.round_commit, "begin",
                        lambda *a, **k: real_begin(*a, stop_at="sealed", **k))
    with pytest.raises(RD.round_commit.StopPoint):
        RD.save_state(d, state)
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))
    assert not os.path.exists(os.path.join(d, RD.MIRROR_FILE))
    RD.round_commit.recover(d)
    assert os.path.exists(os.path.join(d, RD.STATE_FILE))
    assert os.path.exists(os.path.join(d, RD.MIRROR_FILE))


def test_a_reraise_of_a_lineage_linked_original_withholds_the_reworded_keys_credit():
    state = _round_one_state(_finding(), _finding("Bug reworded", 1))
    state["findingLineage"] = {_key("Bug reworded"): _key()}
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Bug reworded"])
    _panel(state, raised=[_finding()])
    assert "disposition" not in _ledger(state)[_key("Bug reworded")]


def test_a_reworded_reraise_at_the_same_location_withholds_the_credit():
    """The panel's own staging links the reword to the guided original, so the original is not
    credited fixed by a panel that raised it again under new wording (credit runs after staging)."""
    state = _round_one_state(_finding())
    state["rulingsLog"] = [{"seq": RD._next_ruling_seq(state), "round": 1, "phase": RD.P_APPLY_FIXES,
                            "attempt": 0, "id": _key(), "findingKey": _key(),
                            "ruling": "guidance", "reason": "because", "by": "owner",
                            "file": "f.py", "line": 1, "guidance": "G1"}]
    _fix(state)
    _panel(state, raised=[_finding("Bug reworded")])
    assert state["findingLineage"] == {_key("Bug reworded"): _key()}
    assert "disposition" not in _ledger(state)[_key()]


def _reword_linked_to_a_decided_original():
    """A round-2 state whose original is guided and fixed, and the compile of a panel that raises
    only a reword of it at the same file and line."""
    state = _round_one_state(_finding())
    state["rulingsLog"] = [{"seq": RD._next_ruling_seq(state), "round": 1, "phase": RD.P_APPLY_FIXES,
                            "attempt": 0, "id": _key(), "findingKey": _key(),
                            "ruling": "guidance", "reason": "because", "by": "owner",
                            "file": "f.py", "line": 1, "guidance": "G1"}]
    _fix(state)
    compiled, _ = RD.mechanical_compile([_finding("Bug reworded")], TRD.DIFF)
    return state, compiled


def test_the_credit_step_leaves_lineage_and_decisions_as_they_were():
    """The credit step links rewordings on a scratch copy only; lineage and decisions are written by
    staging, never by the credit step."""
    state, compiled = _reword_linked_to_a_decided_original()
    lineage_before = copy.deepcopy(state.get("findingLineage"))
    rounds_before = copy.deepcopy(state.get("findingLineageRound"))
    decisions_before = copy.deepcopy(state["decisions"])
    RD._credit_fixes_not_reraised(state, compiled)
    assert state.get("findingLineage") == lineage_before
    assert state.get("findingLineageRound") == rounds_before
    assert state["decisions"] == decisions_before
    assert "disposition" not in _ledger(state)[_key()]      # the reword still raises the original's group


def test_staging_after_the_credit_step_records_one_ruling_carried_for_the_reword():
    """The reword's lineage link is written once, by staging."""
    state, compiled = _reword_linked_to_a_decided_original()
    RD._credit_fixes_not_reraised(state, compiled)
    RD._stage_findings(state, compiled)
    carried = [d for d in state["decisions"] if d["kind"] == "ruling-carried"]
    assert len(carried) == 1, carried
    assert state["findingLineage"] == {_key("Bug reworded"): _key()}


def _dropped_reword_case():
    """A guided original is fixed; the panel rewords it at its location with no consequence, so
    compilation drops the reword and only the raw report carries it."""
    state, _ = _reword_linked_to_a_decided_original()
    raw = {k: v for k, v in _finding("Bug reworded").items() if k != "consequence"}
    return state, [], [raw], _key()


def _merged_member_reraise_case():
    """Twin is merged into Bug; Twin holds a lineage link to its reword; the fixer fixed Bug; the
    panel raises that reword. The representative's group is raised."""
    state = _round_one_state(_finding(), _finding("Twin", 2))
    RD._record_merged_into(state, _key("Twin", 2), _key())
    state["findingLineage"] = {_key("Twin reworded", 2): _key("Twin", 2)}
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Bug"])
    compiled, _ = RD.mechanical_compile([_finding("Twin reworded", 2)], TRD.DIFF)
    return state, compiled, [], _key()


def _lineage_member_of_representative_case():
    """Twin is merged into Bug; Bug reworded is linked to Bug and fixed; the panel raises Twin, whose
    representative's lineage group holds the credited key."""
    state = _round_one_state(_finding(), _finding("Bug reworded", 1), _finding("Twin", 2))
    RD._record_merged_into(state, _key("Twin", 2), _key())
    state["findingLineage"] = {_key("Bug reworded"): _key()}
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Bug reworded"])
    compiled, _ = RD.mechanical_compile([_finding("Twin", 2)], TRD.DIFF)
    return state, compiled, [], _key("Bug reworded")


def _reworded_member_of_raised_representative_case():
    """Twin is merged into Bug; Twin reworded is linked to Twin and fixed; the panel raises Bug. The
    representative's merged member, and that member's lineage group, are raised with it."""
    state = _round_one_state(_finding(), _finding("Twin", 2), _finding("Twin reworded", 2))
    RD._record_merged_into(state, _key("Twin", 2), _key())
    state["findingLineage"] = {_key("Twin reworded", 2): _key("Twin", 2)}
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Twin reworded"])
    compiled, _ = RD.mechanical_compile([_finding()], TRD.DIFF)
    return state, compiled, [], _key("Twin reworded", 2)


@pytest.mark.parametrize("case", [_dropped_reword_case, _merged_member_reraise_case,
                                  _lineage_member_of_representative_case,
                                  _reworded_member_of_raised_representative_case])
def test_the_raised_closure_withholds_credit_from_every_key_the_panel_raised_again(case):
    """Raised keys grow, to a fixed point, by each key's merged-into representative, its merged members and lineage group;
    a ledger entry in that closure is never credited by silence."""
    state, compiled, raw, credited_key = case()
    RD._credit_fixes_not_reraised(state, compiled, raw)
    assert not _credited(state, credited_key)


def _reopened_after_fixed(marker_offset=0, extra_marks=()):
    """A round-3 state whose finding was fixed and audited (a `fixed` disposition newer than its
    raise), then reopened by an owner ruling in round 2: its marker sits `marker_offset` from that
    disposition's seq, or is absent when `marker_offset` is None, and `restagedInRound` records
    round 2 beside each marker. The retry's fixer step in round 2 reported the fix, so only a silent
    complete panel is missing."""
    state = _round_one_state(_finding())
    _fix(state)
    RD._record_disposition(state, _key(), "fixed", 1, dispositionReceipt={"headSha": "abc"})
    seq = state["dispositionSeqCounter"]
    marks = {} if marker_offset is None else {_key(): seq + marker_offset}
    marks.update({k: seq for k in extra_marks})
    state["restagedAfterDispositionSeq"] = marks
    state["restagedInRound"] = {k: state["round"] for k in marks}
    assert state["round"] == 2
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Bug"])
    assert state["round"] == 3
    return state


def test_a_fixed_disposition_a_ruling_reopened_is_credited_by_a_later_silent_panel_and_its_marker_goes():
    """axis: RESTAGE — an old `fixed` the reopening marker invalidates does not count as a current
    disposition, so the retry's fix is credited and the marker is superseded by the fresh `fixed`."""
    state = _reopened_after_fixed()
    assert RD._disposition_is_current(_ledger(state)[_key()])
    assert RD._restaged_after(state, _key(), _ledger(state)[_key()])
    _panel(state)
    assert _credited(state, _key())
    assert _key() not in state["restagedAfterDispositionSeq"]
    assert _key() not in state["restagedInRound"]


def test_credit_supersedes_the_markers_of_the_keys_ruling_closure_and_no_others():
    """axis: RESTAGE — a lineage member's reopening is superseded with the key's own; an unrelated
    key's marker stays."""
    state = _reopened_after_fixed(extra_marks=("f.py::reworded@L9", "f.py::unrelated@L8"))
    state["findingLineage"] = {"f.py::reworded@L9": _key()}
    _panel(state)
    assert _credited(state, _key())
    assert set(state["restagedAfterDispositionSeq"]) == {"f.py::unrelated@L8"}
    assert set(state["restagedInRound"]) == {"f.py::unrelated@L8"}


def test_a_reopened_finding_with_no_fix_report_keeps_its_marker_when_another_is_credited():
    """axis: RESTAGE — only a credited key's closure is superseded: a reopened `fixed` no fixer
    reported again stays reopened, so the settle path never counts its stale disposition current."""
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state, batch=[f for f in state["findings"] if f["title"] == "Other"])
    RD._record_disposition(state, _key(), "fixed", 1, dispositionReceipt={"headSha": "abc"})
    marks = {_key(): state["dispositionSeqCounter"]}
    state["restagedAfterDispositionSeq"] = dict(marks)
    _panel(state)
    assert _credited(state, _key("Other", 2))
    assert not _credited(state, _key())
    assert state["restagedAfterDispositionSeq"] == marks


def test_a_reopened_finding_whose_retry_reported_no_fix_is_not_credited_from_the_report_before_the_ruling():
    """axis: RESTAGE — vet 506: round 1 fixes A and B; a ruling reopens A; A's retry reports no fix;
    the round-3 silent panel must not credit A from round 1's report, which the ruling reopened, and
    A's reopening marker stays."""
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state)
    RD._record_disposition(state, _key(), "fixed", 1, dispositionReceipt={"headSha": "abc"})
    marks = {_key(): state["dispositionSeqCounter"]}
    state["restagedAfterDispositionSeq"] = dict(marks)
    _fix(state, fixes=False, batch=[f for f in state["findings"] if f["title"] == "Bug"])
    assert state["round"] == 3
    before = dict(_ledger(state)[_key()])
    _panel(state)
    assert _ledger(state)[_key()] == before
    assert state["restagedAfterDispositionSeq"] == marks


def test_a_reopened_finding_whose_marker_has_no_reopening_round_is_not_credited_and_keeps_its_marker():
    """axis: RESTAGE — a session from before the round was recorded fails closed: a marker with no
    `restagedInRound` entry is credited from no report, and stays."""
    state = _reopened_after_fixed()
    state["restagedInRound"] = {}
    marks = dict(state["restagedAfterDispositionSeq"])
    before = dict(_ledger(state)[_key()])
    _panel(state)
    assert _ledger(state)[_key()] == before
    assert state["restagedAfterDispositionSeq"] == marks


def test_a_reopened_finding_whose_retry_reported_no_fix_in_the_recorded_round_is_not_credited():
    """axis: RESTAGE — with the reopening round recorded, the report before it (round 1) is still
    not the retry's: a retry that reports no fix leaves the finding reopened, its marker and round."""
    state = _round_one_state(_finding(), _finding("Other", 2))
    _fix(state)
    RD._record_disposition(state, _key(), "fixed", 1, dispositionReceipt={"headSha": "abc"})
    marks = {_key(): state["dispositionSeqCounter"]}
    state["restagedAfterDispositionSeq"] = dict(marks)
    state["restagedInRound"] = {_key(): state["round"]}
    _fix(state, fixes=False, batch=[f for f in state["findings"] if f["title"] == "Bug"])
    before = dict(_ledger(state)[_key()])
    _panel(state)
    assert _ledger(state)[_key()] == before
    assert state["restagedAfterDispositionSeq"] == marks
    assert state["restagedInRound"] == {_key(): 2}


def test_a_retry_report_at_the_reopening_round_itself_counts():
    """axis: RESTAGE — the lower bound is inclusive: the fixer step of the round the reopening was
    recorded in carries the retry, so its report credits the finding."""
    state = _reopened_after_fixed()
    assert state["restagedInRound"][_key()] == 2 and 2 in RD._rounds_with_fix_report(state)
    _panel(state)
    assert _credited(state, _key())


@pytest.mark.parametrize("marker_offset", [None, -1])
def test_a_disposition_no_ruling_reopened_is_left_as_it_is_with_its_marker(marker_offset):
    """Control: no marker, or a marker older than the disposition, leaves the current `fixed` alone."""
    state = _reopened_after_fixed(marker_offset)
    before = dict(_ledger(state)[_key()])
    marks = dict(state["restagedAfterDispositionSeq"])
    assert RD._disposition_is_current(before)
    assert not RD._restaged_after(state, _key(), before)
    _panel(state)
    assert _ledger(state)[_key()] == before
    assert before["dispositionReceipt"] == {"headSha": "abc"}
    assert state["restagedAfterDispositionSeq"] == marks


def test_a_guided_fix_audited_then_restaged_and_retried_is_credited_by_a_silent_full_panel(monkeypatch):
    """axis: RESTAGE — the reviewer's scenario through run_loop: guidance arrives during the first fix,
    the fix is audited discharged, the finding is restaged, the retry reports fixes, and a complete
    silent full panel follows: the finding ends `fixed`, not left for the owner."""
    box = {}
    real_new_state = RD.new_state

    def capture(*args, **kwargs):
        box["state"] = real_new_state(*args, **kwargs)
        return box["state"]

    monkeypatch.setattr(RD, "new_state", capture)

    def reviewer(dim, tier, rnd, ctx):
        return [_finding()] if rnd == 1 and dim == "code-reviewer" else []

    def fix_step(batch, rnd, payload):
        if rnd == 1:  # guidance arrives while the first fix is out; that fix is audited
            state = box["state"]
            state["rulingsLog"] = [{"seq": RD._next_ruling_seq(state), "round": 1, "phase": RD.P_APPLY_FIXES,
                                    "attempt": 0, "id": _key(), "findingKey": _key(),
                                    "ruling": "guidance", "reason": "because", "by": "owner",
                                    "file": "f.py", "line": 1, "guidance": "G1"}]
            return {"fixes": [{"file": "f.py", "summary": "first try"}], "headDiff": TRD.HEAD,
                    "changedSubjects": ["Code"]}
        return {"fixes": [{"file": "f.py", "summary": "retry"}], "changedSubjects": ["Code"]}

    fixer_fold_calls = []

    def panel_diff(config, head):
        if _called_from_fixer_fold(2):
            fixer_fold_calls.append(head)
            if len(fixer_fold_calls) > 1:
                return None, _FIXER_FOLD_REFUSAL
        return TRD.HEAD, None

    seams = TRD._seams(reviewer=reviewer, fix_step=fix_step)
    seams["panel_diff"] = panel_diff
    _, state =TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert state is box["state"]
    row = _ledger(state)[_key()]
    assert state["terminal"] == "converged", (state.get("terminal"), state.get("certification"), row)
    assert row["disposition"] == "fixed" and row["dispositionReceipt"]["kind"] == SC.FULL_PANEL_NOT_RERAISED, row
    assert "settledReason" not in row
