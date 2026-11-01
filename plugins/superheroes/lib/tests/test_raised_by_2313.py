"""#2313: every finding the review loop raises carries `raisedBy`, the name of the run that first raised it.

The invariant: the driver stamps it (the roster seat key for a panel finding, the stage name for a non-panel compile, the
searcher seat key for a sweep hit); a value a seat sends itself never survives; once set it never changes, not on a
re-raise, a merge or a carry into a later session; the record writer copies it onto the record finding; a finding whose
first raiser is not known carries no `raisedBy` at all (never a guess from its lens).

C1 compile stamps · C2 merge · L1 ledger re-raise · L2 carried merge · W1 sweep · R1 record writer · R2 later session ·
V1 the account validator · H1 content identity · A1 abandoned-session recovery.

Bite-proof record: i2313_raised_by
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases  # noqa: E402
import session_contract as SC  # noqa: E402
import verification  # noqa: E402
from test_audit_spawned_riders_2115 import P_KEY, _audit_issue, _child, _scoped_state  # noqa: E402
from test_c1l11b_carried_findings import _finding as _carried_record, _session  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_c4_kind_of_mistake import DIFF, _record_rows  # noqa: E402
from test_c4_sweep import _both, _finding as _sweep_parent, _hit, _sweep, _to_sweep, world  # noqa: E402,F401
from test_c4_sweep_recovery import INSIDE, SEAT_1, _account, _hits, _stored  # noqa: E402
from test_review_record import account as acct, finding as record_finding, put  # noqa: E402
from test_review_record import Fake as RecordFake  # noqa: E402
from test_review_record_abandoned_2137 import REASON  # noqa: E402
from test_review_record_session import Fake, Session, extras, ledger_row, put_envelope, CODEX  # noqa: E402

RAISED = SC.RAISED_BY_FIELD
CONSEQUENCE = "a defect stays in the change"


def _finding(title="Retry without a cap", line=2, severity="Important", **extra):
    out = {"title": title, "file": "src/a.py", "line": line, "severity": severity, "consequence": CONSEQUENCE,
           "body": "the body", "confidence": "High"}
    out.update(extra)
    return out


def _compile(finding, **kw):
    compiled, _drops = RD.mechanical_compile([finding], DIFF, **kw)
    assert len(compiled) == 1, compiled
    return compiled[0]


# ---- C1: what compile stamps ------------------------------------------------------------------------------------


def test_c1_a_panel_finding_is_stamped_with_its_roster_seat_not_its_lens():
    # axis: the raiser is the roster seat key, never the finding's dimension
    f = _finding(dimension="Failure-Mode")
    out = _compile(f, sources={id(f): "code-reviewer"})
    assert out[RAISED] == "code-reviewer" and out["dimension"] != "code-reviewer"
    assert "premortem" not in out[RAISED]


def test_c1_a_sliced_seat_key_is_kept_whole():
    # axis: a sliced seat key is stamped whole, never cut back to its base seat
    f = _finding()
    assert _compile(f, sources={id(f): "code-reviewer:s1"})[RAISED] == "code-reviewer:s1"


def test_c1_a_raiser_the_seat_sent_never_survives_compile():
    # axis: a seat-sent raisedBy is replaced by the roster key
    f = _finding(**{RAISED: "premortem-reviewer"})
    assert _compile(f, sources={id(f): "code-reviewer"})[RAISED] == "code-reviewer"
    g = _finding(**{RAISED: "premortem-reviewer"})
    assert _compile(g, source=SC.OUTSIDE_FIX_AUDITOR)[RAISED] == SC.OUTSIDE_FIX_AUDITOR


@pytest.mark.parametrize("sent", ["premortem-reviewer", "", "  ", None, 7])
def test_c1_with_neither_sources_nor_source_the_field_is_absent(sent):
    # axis: no known raiser is no raisedBy — never the seat's own value, never the outside default
    out = _compile(_finding(**{RAISED: sent}))
    assert RAISED not in out


@pytest.mark.parametrize("blank", ["", "   ", None, 3])
def test_c1_a_blank_source_is_no_raiser(blank):
    # axis: a blank or non-string source stamps no raiser
    f = _finding()
    assert RAISED not in _compile(f, sources={id(f): blank}, source=blank)


def test_c1_a_blank_sources_entry_falls_to_the_stage_source():
    # axis: a blank per-finding source falls through to the stage name rather than stamping nothing
    f = _finding()
    assert _compile(f, sources={id(f): " "}, source=SC.OUTSIDE_SEAMS_CHECK)[RAISED] == SC.OUTSIDE_SEAMS_CHECK


@pytest.mark.parametrize("stage", [SC.OUTSIDE_FIX_AUDITOR, SC.OUTSIDE_SCOPED_FINDER, SC.OUTSIDE_SEAMS_CHECK])
def test_c1_a_stage_compile_carries_its_stage_name(stage):
    # axis: a non-panel compile stamps its own stage name
    assert stage in ("fix auditor", "scoped finder", "seams check")
    assert _compile(_finding(), source=stage)[RAISED] == stage


def test_c1_a_panel_fold_stamps_each_staged_finding_with_its_seat(world):
    # axis: the panel fold gives each staged finding and ledger row its own seat's key, not the first finding's seat or a seat-sent value
    from test_c4_sweep import _panel
    # a fold that gave every finding the first finding's seat would pass a test staging one seat's findings only
    state = _panel(world,
                   code_reviewer=[_sweep_parent(title="Retry without a cap", line=2, dimension="Failure-Mode", **{RAISED: "premortem-reviewer"})],
                   premortem_reviewer=[_sweep_parent(title="Loop without a bound", line=19, **{RAISED: "code-reviewer"})])
    staged = {f["title"]: f for f in state["_toVerify"]}
    assert set(staged) == {"Retry without a cap", "Loop without a bound"}, staged
    assert staged["Retry without a cap"][RAISED] == "code-reviewer"
    assert staged["Loop without a bound"][RAISED] == "premortem-reviewer"
    rows = {r["title"]: r for r in state[SC.DISPOSITION_LEDGER_KEY]}
    assert set(rows) == set(staged), rows
    assert rows["Retry without a cap"][RAISED] == "code-reviewer"
    assert rows["Loop without a bound"][RAISED] == "premortem-reviewer"


# ---- C2: a merge keeps the first raiser ------------------------------------------------------------------------


def test_c2_a_compile_dedupe_keeps_the_first_seats_raiser_even_when_the_later_one_wins_on_severity():
    # axis: the merged row's raiser is existing's, whichever side wins the base
    a, b = _finding(severity="Minor"), _finding(severity="Critical")
    compiled, drops = RD.mechanical_compile([a, b], DIFF, sources={id(a): "code-reviewer", id(b): "premortem-reviewer"})
    (row,) = compiled
    assert row["severity"] == "Critical" and row[RAISED] == "code-reviewer", row
    assert any(d["reason"] == RD.COMPILE_DROP_MERGED_SAME_PLACE for d in drops)


def test_c2_merge_same_finding_keeps_existings_raiser_when_incoming_wins():
    # axis: the merged raiser is existing's when the incoming side wins the base on severity
    existing = dict(_compile(_finding(severity="Minor"), source="seams check"), **{RAISED: "code-reviewer"})
    incoming = dict(_compile(_finding(severity="Critical"), source="seams check"), **{RAISED: "premortem-reviewer"})
    merged = RD._merge_same_finding(existing, incoming)
    assert merged["severity"] == "Critical" and merged[RAISED] == "code-reviewer"


def test_c2_merge_same_finding_keeps_existings_raiser_when_existing_wins():
    # axis: the merged raiser is existing's when existing wins the base on severity
    existing = dict(_compile(_finding(severity="Critical"), source="seams check"), **{RAISED: "code-reviewer"})
    incoming = dict(_compile(_finding(severity="Minor"), source="seams check"), **{RAISED: "premortem-reviewer"})
    assert RD._merge_same_finding(existing, incoming)[RAISED] == "code-reviewer"


@pytest.mark.parametrize("severity", ["Minor", "Critical"])
def test_c2_merge_same_finding_leaves_the_raiser_absent_when_existing_has_none(severity):
    # axis: a row with no known first raiser never gains one from the incoming side
    existing = _compile(_finding(severity="Important"))
    incoming = dict(_compile(_finding(severity=severity)), **{RAISED: "premortem-reviewer"})
    assert RAISED not in existing
    assert RAISED not in RD._merge_same_finding(existing, incoming)


# ---- L1: the ledger row ----------------------------------------------------------------------------------------


def _state():
    return RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})


def _seed(ledger, seen, finding, round_no):
    key = RD._finding_identity_key(finding)
    return RD._seed_ledger_entry(_state(), ledger, seen, finding, key, round_no)


def test_l1_a_re_raise_by_another_seat_keeps_the_first_raiser():
    # axis: the first raiser survives the ledger row being replaced on a re-raise
    ledger, seen = [], {}
    first = _seed(ledger, seen, _finding(**{RAISED: "code-reviewer"}), 1)
    assert first[RAISED] == "code-reviewer"  # no existing row: the finding's own value stands
    seen[RD._finding_identity_key(first)] = 0
    ledger.append(first)
    second = _seed(ledger, seen, _finding(**{RAISED: "premortem-reviewer"}), 2)
    assert second[RAISED] == "code-reviewer"


def test_l1_an_existing_row_without_a_raiser_stays_without_one():
    # axis: a row with no known raiser never gains one from a re-raise
    ledger, seen = [], {}
    first = _seed(ledger, seen, _finding(), 1)
    assert RAISED not in first
    seen[RD._finding_identity_key(first)] = 0
    ledger.append(first)
    second = _seed(ledger, seen, _finding(**{RAISED: "premortem-reviewer"}), 2)
    assert RAISED not in second


# ---- L2: the carried merge -------------------------------------------------------------------------------------


def test_l2_a_fresh_report_merged_into_a_carried_finding_keeps_the_carried_raiser():
    # axis: the carried merge keeps the carried finding's raiser even when the fresh report wins on severity
    held = dict(_compile(_finding(severity="Minor"), source="fix auditor"), **{RAISED: "code-reviewer"})
    fresh = dict(_compile(_finding(severity="Critical"), source="fix auditor"), **{RAISED: "premortem-reviewer"})
    [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
    assert row["severity"] == "Critical" and row[RAISED] == "code-reviewer"


def test_l2_a_carried_finding_without_a_raiser_stays_without_one():
    # axis: a carried finding with no known raiser never gains one from the fresh report
    held = _compile(_finding(severity="Minor"))
    fresh = dict(_compile(_finding(severity="Critical")), **{RAISED: "premortem-reviewer"})
    [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
    assert row["severity"] == "Critical" and RAISED not in row


def _scoped_fold(scoped=(), issues=()):
    """Fold the scoped scan over a built state; the staged findings by title."""
    state = _scoped_state()
    state["_newIssues"] = [dict(i) for i in issues]
    RD._fold_scoped(state, state["config"], {"findings": [dict(f) for f in scoped]})
    return {f["title"]: f for f in state["_toVerify"]}


def test_c3_a_scoped_candidate_at_an_audit_issues_anchor_keeps_the_auditor_as_raiser():
    # axis: the fix audits run first, so the auditor stays the raiser where the compile kept the scoped dict at the anchor
    staged = _scoped_fold(scoped=[_child(), _child(title="Other drift", line=1)], issues=[_audit_issue(P_KEY)])  # the round diff touches lines 1 and 2 of f.py
    assert staged["Stale comment"][RAISED] == SC.OUTSIDE_FIX_AUDITOR
    assert "Other drift" in staged, sorted(staged)
    assert staged["Other drift"][RAISED] == SC.OUTSIDE_SCOPED_FINDER  # a scoped-only anchor keeps the scoped finder


def test_c3_a_scoped_candidate_that_forges_a_raiser_never_gets_the_auditor_stamp():
    # axis: only an anchor an audit new issue raised takes the auditor stamp; a seat-sent raisedBy never survives
    staged = _scoped_fold(scoped=[dict(_child(), **{RAISED: SC.OUTSIDE_FIX_AUDITOR})], issues=[])
    assert staged["Stale comment"][RAISED] == SC.OUTSIDE_SCOPED_FINDER


# ---- M1: a synthesis merge keeps the earliest member's raiser --------------------------------------------------


def _member(severity, raised_by=None, raised_round=None):
    out = {"title": "Retry without a cap", "file": "src/a.py", "line": 2, "severity": severity, "consequence": CONSEQUENCE}
    if raised_by is not None:
        out[RAISED] = raised_by
    if raised_round is not None:
        out[SC.RAISED_ROUND_FIELD] = raised_round
    return out


def test_m1_a_merge_takes_the_raiser_of_the_member_raised_earliest_not_the_severity_representative():
    # axis: the merged raiser is the earliest member's (smallest raisedRound; none means this round), not the representative's
    carried = _member("Minor", "code-reviewer", raised_round=1)
    fresh = _member("Important", "scoped finder")
    for members in ([carried, fresh], [fresh, carried]):
        merged = verification._merge_group(members)
        assert merged["severity"] == "Important" and merged[RAISED] == "code-reviewer", merged


def test_m1_the_earliest_of_two_carried_members_wins():
    # axis: among members that carry a raisedRound the strictly smaller one is earlier, in either member order
    later = _member("Important", "premortem-reviewer", raised_round=3)
    earlier = _member("Minor", "code-reviewer", raised_round=2)
    for members in ([later, earlier], [earlier, later]):
        assert verification._merge_group(members)[RAISED] == "code-reviewer", members


def test_m1_members_that_tie_on_the_round_keep_the_kept_findings_raiser_in_either_order():
    # axis: with equal raisedRound the raiser follows the kept (highest-severity) member, never the order the seat listed them in
    for members in ([_member("Minor", "code-reviewer", raised_round=1), _member("Important", "premortem-reviewer", raised_round=1)],
                    [_member("Important", "premortem-reviewer", raised_round=1), _member("Minor", "code-reviewer", raised_round=1)]):
        merged = verification._merge_group(members)
        assert merged["severity"] == "Important" and merged[RAISED] == "premortem-reviewer", merged


def test_m1_equal_severity_members_tied_on_the_round_keep_the_last_listed_members_raiser():
    # axis: equal severity keeps the last-listed member, and the merged raiser follows it
    first_round = SC.FIRST_RAISED_ROUND_FIELD
    code = dict(_member("Important", "code-reviewer"), **{first_round: 1})
    premortem = dict(_member("Important", "premortem-reviewer"), **{first_round: 1})
    assert verification._merge_group([code, premortem])[RAISED] == "premortem-reviewer"
    assert verification._merge_group([premortem, code])[RAISED] == "code-reviewer"


def test_m1_a_strictly_earlier_member_beats_a_later_representative_in_either_order():
    # axis: a member raised in round 1 beats a higher-severity representative raised in round 2, whatever the member order
    early = _member("Minor", "code-reviewer", raised_round=1)
    late = _member("Important", "scoped finder", raised_round=2)
    for members in ([early, late], [late, early]):
        merged = verification._merge_group(members)
        assert merged["severity"] == "Important" and merged[RAISED] == "code-reviewer", merged


def test_m1_members_raised_in_one_round_keep_the_representatives_raiser():
    # axis: with no raisedRound on any member the representative's raiser stands
    low = _member("Minor", "code-reviewer")
    high = _member("Important", "premortem-reviewer")
    assert verification._merge_group([low, high])[RAISED] == "premortem-reviewer"
    assert verification._merge_group([high, low])[RAISED] == "premortem-reviewer"


def test_m1_an_earliest_member_with_no_raiser_leaves_the_merge_without_one():
    # axis: a merge never invents a raiser — the earliest member has none, so the merged finding has none
    earliest = _member("Minor", None, raised_round=1)
    fresh = _member("Important", "scoped finder")
    merged = verification._merge_group([earliest, fresh])
    assert merged["severity"] == "Important" and RAISED not in merged, merged


def test_m2_a_merge_carries_the_chosen_members_first_raise_round_with_its_raiser_across_two_merges():
    # axis: the chosen earliest member's round travels with its raiser, so a second merge never swaps in a later seat
    first = verification._merge_group([_member("Minor", "code-reviewer", raised_round=1),
                                       _member("Important", "scoped finder", raised_round=3)])
    assert first[RAISED] == "code-reviewer" and first[SC.FIRST_RAISED_ROUND_FIELD] == 1, first
    round_two = _member("Important", "premortem-reviewer", raised_round=2)
    for members in ([first, round_two], [round_two, first]):
        merged = verification._merge_group(members)
        assert merged[RAISED] == "code-reviewer" and merged[SC.FIRST_RAISED_ROUND_FIELD] == 1, merged


def test_m2_synthesis_syncs_the_first_raise_round_onto_the_ledger_row_with_the_raiser():
    # axis: the representative's ledger row takes the chosen member's firstRaisedRound together with its raiser
    rep = {"title": "t", "file": "f.py", "line": 1, RAISED: "code-reviewer", SC.FIRST_RAISED_ROUND_FIELD: 1}
    row = {"title": "t", "file": "f.py", "line": 1, RAISED: "scoped finder", SC.FIRST_RAISED_ROUND_FIELD: 3}
    state = {SC.DISPOSITION_LEDGER_KEY: [row]}
    RD._sync_merged_consequences(state, [rep])
    assert row[RAISED] == "code-reviewer" and row[SC.FIRST_RAISED_ROUND_FIELD] == 1, row


def _synced_ledger_row(ledger_raiser, rep_raiser):
    rep = {"title": "t", "file": "f.py", "line": 1}
    if rep_raiser is not None:
        rep[RAISED] = rep_raiser
    row = dict(rep)
    if ledger_raiser is not None:
        row[RAISED] = ledger_raiser
    state = {SC.DISPOSITION_LEDGER_KEY: [row]}
    RD._sync_merged_consequences(state, [rep])
    return state[SC.DISPOSITION_LEDGER_KEY][0]


def test_s1_synthesis_carries_the_chosen_earliest_raiser_onto_the_ledger_row():
    # axis: the representative's ledger row takes the raiser synthesis chose, not the representative's original one
    assert _synced_ledger_row("security-reviewer", "code-reviewer")[RAISED] == "code-reviewer"


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_s1_two_findings_staged_in_one_round_merge_to_the_kept_findings_raiser_in_either_grouping_order(order):
    # axis: through the synthesis fold the kept finding's live row and ledger row both carry its own raiser, not the first-listed member's
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    minor = _finding(title="Minor one", line=1, severity="Minor", **{RAISED: "code-reviewer"})
    important = _finding(title="Important one", line=2, severity="Important", **{RAISED: "premortem-reviewer"})
    RD._stage_findings(state, [minor, important])
    staged = verification.stage_ids(state["_toVerify"])
    assert {f[SC.RAISED_ROUND_FIELD] for f in staged} == {state["round"]}  # both staged rows carry the one current round
    state["_verified"] = staged
    ids = [staged[i]["id"] for i in order]
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g", "member_ids": ids}]})
    (live,) = state["findings"]
    ledger = state[SC.DISPOSITION_LEDGER_KEY]
    row = ledger[RD._ledger_index_by_key(ledger)[RD._finding_identity_key(live)]]
    assert live["severity"] == "Important" and live[RAISED] == "premortem-reviewer" and row[RAISED] == "premortem-reviewer", (live, row)


@pytest.mark.parametrize("reverse", [False, True])
def test_s2_a_finding_first_raised_in_round_one_keeps_its_raiser_when_restaged_beside_a_fresh_round_two_finding(reverse):
    # axis: staging rewrites raisedRound to the current round, so the merged raiser follows the driver-owned firstRaisedRound
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    RD._stage_findings(state, [_finding(title="Minor one", line=1, severity="Minor", **{RAISED: "code-reviewer"})])
    first_round = state["round"]
    state["round"] = first_round + 1
    RD._stage_findings(state, [
        _finding(title="Minor one", line=1, severity="Minor", **{RAISED: "scoped finder"}),
        _finding(title="Important one", line=2, severity="Important", **{RAISED: "scoped finder"}),
    ])
    staged = verification.stage_ids(state["_toVerify"])
    by_title = {f["title"]: f for f in staged}
    assert by_title["Minor one"][SC.RAISED_ROUND_FIELD] == by_title["Important one"][SC.RAISED_ROUND_FIELD] == state["round"]
    assert by_title["Minor one"][SC.FIRST_RAISED_ROUND_FIELD] == first_round
    assert by_title["Important one"][SC.FIRST_RAISED_ROUND_FIELD] == state["round"]
    state["_verified"] = staged
    titles = ["Minor one", "Important one"]
    ids = [by_title[t]["id"] for t in (reversed(titles) if reverse else titles)]
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g", "member_ids": ids}]})
    (live,) = state["findings"]
    ledger = state[SC.DISPOSITION_LEDGER_KEY]
    row = ledger[RD._ledger_index_by_key(ledger)[RD._finding_identity_key(live)]]
    assert live["severity"] == "Important" and live[RAISED] == "code-reviewer" and row[RAISED] == "code-reviewer", (live, row)


def test_s2_a_first_raised_round_the_seat_sends_never_survives_compile():
    # axis: firstRaisedRound is driver-owned — a value a seat sends is stripped at compile, like raisedBy
    out = _compile(_finding(**{SC.FIRST_RAISED_ROUND_FIELD: 0}), source=SC.OUTSIDE_SEAMS_CHECK)
    assert SC.FIRST_RAISED_ROUND_FIELD not in out
    assert SC.FIRST_RAISED_ROUND_FIELD in SC.TRANSIENT_FINDING_FIELDS


def _returning_state(tmp_path, monkeypatch, **record_over):
    """A returning session driven through `_seed_carried`: one Minor finding `code-reviewer` raised in an earlier
    session, sent back to the verifier (line 3: the later commit touches only the hunk around line 27, so no audit
    targets it). Returns (state, its row key)."""
    carried = _carried_record(3, title="the carried value is wrong", severity="Minor", **dict({RAISED: "code-reviewer"}, **record_over))
    s = _session(tmp_path, monkeypatch, [carried])
    s.next()
    state = s.state()
    key = carried[SC.FINDING_KEY_FIELD]
    assert [RD._finding_identity_key(f) for f in state["_carriedToVerify"]] == [key], state.get("_carriedToVerify")
    return state, key


def _ledger_row(state, key):
    ledger = state[SC.DISPOSITION_LEDGER_KEY]
    return ledger[RD._ledger_index_by_key(ledger)[key]]


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_s3_a_finding_carried_from_an_earlier_session_keeps_its_raiser_beside_a_fresh_more_severe_finding_in_either_grouping_order(
        tmp_path, monkeypatch, order):
    # axis: a carried finding ranks before every finding first raised in the returning session, so its raiser survives a merge with a fresher, more severe one
    state, key = _returning_state(tmp_path, monkeypatch)
    fresh = _finding(title="Important one", line=2, severity="Important", **{RAISED: "premortem-reviewer"})
    RD._stage_findings(state, RD._with_carried(state, [fresh]))  # the staging the carried finding meets later in the same session
    staged = verification.stage_ids(state["_toVerify"])
    by_title = {f["title"]: f for f in staged}
    state["_verified"] = staged
    ids = [staged[i]["id"] for i in order]
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g", "member_ids": ids}]})
    (live,) = state["findings"]
    row = _ledger_row(state, RD._finding_identity_key(live))
    assert live["severity"] == "Important", live
    assert live[RAISED] == "code-reviewer" and row[RAISED] == "code-reviewer", (live, row)
    assert live[SC.FIRST_RAISED_ROUND_FIELD] == row[SC.FIRST_RAISED_ROUND_FIELD] == SC.CARRIED_FIRST_RAISED_ROUND, (live, row)
    # the stamp `_seed_carried` wrote survived the later staging (the existing-row path), and the fresh finding ranks after it
    assert by_title["the carried value is wrong"][SC.FIRST_RAISED_ROUND_FIELD] == SC.CARRIED_FIRST_RAISED_ROUND
    assert by_title["Important one"][SC.FIRST_RAISED_ROUND_FIELD] == state["round"] == 1
    assert _ledger_row(state, key)[SC.FIRST_RAISED_ROUND_FIELD] == SC.CARRIED_FIRST_RAISED_ROUND


def test_s3_a_carried_finding_that_arrives_with_its_own_first_raise_round_is_seeded_at_the_carried_constant(tmp_path, monkeypatch):
    # axis: `_seed_carried` stamps the carried constant whatever firstRaisedRound the carried finding brought
    state, key = _returning_state(tmp_path, monkeypatch, **{SC.FIRST_RAISED_ROUND_FIELD: 3})
    assert _ledger_row(state, key)[SC.FIRST_RAISED_ROUND_FIELD] == SC.CARRIED_FIRST_RAISED_ROUND != 3


def test_s1_synthesis_carries_an_absent_raiser_onto_the_ledger_row():
    # axis: a chosen earliest member with no raiser clears the ledger row's raiser
    assert RAISED not in _synced_ledger_row("security-reviewer", None)


# ---- W1: a sweep hit -------------------------------------------------------------------------------------------


def test_w1_a_sweep_hit_finding_carries_the_searcher_seat_key():
    # axis: the hit finding carries the searcher seat key it was given
    parent = _sweep_parent()
    hit = _hit(19)
    assert SC.sweep_hit_finding(hit, {"sweepId": "S-1"}, parent, raised_by="searcher:S-1:2")[RAISED] == "searcher:S-1:2"


@pytest.mark.parametrize("blank", [None, "", "  ", 3, ["searcher:S-1:1"]])
def test_w1_a_blank_or_non_string_raiser_stamps_nothing(blank):
    # axis: a blank, non-string or absent searcher key stamps no raiser
    assert RAISED not in SC.sweep_hit_finding(_hit(19), {"sweepId": "S-1"}, _sweep_parent(), raised_by=blank)
    assert RAISED not in SC.sweep_hit_finding(_hit(19), {"sweepId": "S-1"}, _sweep_parent())


def test_w1_the_fold_stamps_each_inside_hit_with_the_seat_of_the_part_that_found_it(world):
    # axis: the sweep fold maps each hit to the seat key of its own part
    # a fold that stamped every hit with the loop's last seat key would pass a test whose hits all come from the last part
    _to_sweep(world, _sweep_parent(severity="Critical"))
    state = _sweep(world, {"searcher:S-1:1": [_hit(3, file="src/a.py")], "searcher:S-1:2": [_hit(19, file="src/a.py", what="loops without a bound")]})
    by_line = {h["line"]: h for h in state["_toVerify"]}
    assert set(by_line) == {3, 19}, by_line
    assert by_line[3][RAISED] == "searcher:S-1:1" and by_line[19][RAISED] == "searcher:S-1:2"
    rows = {r["line"]: r for r in state[SC.DISPOSITION_LEDGER_KEY] if r["line"] in (3, 19) and r.get(RAISED, "").startswith("searcher:")}
    assert rows[3][RAISED] == "searcher:S-1:1" and rows[19][RAISED] == "searcher:S-1:2"


# ---- R1: the record writer -------------------------------------------------------------------------------------


def test_r1_the_record_finding_carries_the_ledger_rows_raiser_not_its_lens(tmp_path):
    # axis: the writer copies raisedBy from the ledger row onto the record finding
    row = ledger_row("k-1", id="f-1", dimension="Failure-Mode", **{RAISED: "code-reviewer"})  # the raiser is not the lens's seat
    plain = ledger_row("k-2", id="f-2", line=4)
    _, by_id = _record_rows(tmp_path, row, plain)
    assert by_id["f-1"][RAISED] == "code-reviewer"
    assert RAISED not in by_id["f-2"]  # no known raiser: absent, never guessed from the dimension


def test_r1_a_blank_raiser_on_a_ledger_row_is_no_raiser(tmp_path):
    # axis: a blank or non-string ledger raiser is stripped, and the finding still reaches the record as no raiser
    rows = [ledger_row("k-%d" % i, id="f-%d" % i, line=3 + i, **{RAISED: v}) for i, v in enumerate(["", "  ", None, 5])]
    _, by_id = _record_rows(tmp_path, *rows)
    assert set(by_id) == {r["id"] for r in rows} and len(by_id) == len(rows), by_id
    assert all(RAISED not in f for f in by_id.values()), by_id


def test_r1_the_ledger_rows_raiser_wins_over_a_live_rows(tmp_path):
    # axis: the ledger row's raiser is kept over a live row's, and it is neither seat the dimension names
    held = ledger_row("k-1", id="f-1", **{RAISED: "premortem-reviewer"})  # the ledger row's dimension is code-reviewer
    live = {"findingKey": "k-1", "id": "f-1", "title": "t", "severity": "Important", "file": "a.py", "line": 3,
            "detail": "d", "dimension": "code-reviewer", RAISED: "security-reviewer"}
    session = Session(tmp_path / "acct", dispositionLedger=[held], findings=[live]).seat("code-reviewer").save()
    account = rs.account_from_session(session, extras(), Fake().readers())
    (f,) = account["findings"]
    assert f[RAISED] == "premortem-reviewer"


def test_r1_a_live_row_with_no_ledger_row_supplies_its_raiser(tmp_path):
    # axis: a live row with no ledger row supplies the raiser itself
    live = {"findingKey": "k-9", "id": "f-9", "title": "t", "severity": "Important", "file": "a.py", "line": 3,
            "detail": "d", "dimension": "code-reviewer", RAISED: "code-reviewer:s1"}
    session = Session(tmp_path / "acct", findings=[live]).seat("code-reviewer").save()
    account = rs.account_from_session(session, extras(), Fake().readers())
    (f,) = account["findings"]
    assert f[RAISED] == "code-reviewer:s1"


# ---- R2: a later session ---------------------------------------------------------------------------------------


def _earlier(**extra):
    return {"findingKey": "k-1", "id": "f-1", "title": "t", "file": "a.py", "line": 3, **extra}


def test_r2_fill_gives_a_finding_the_earlier_records_first_raiser():
    # axis: the earlier record's first raiser wins over a later session's
    account = {"findings": [_earlier(**{RAISED: "premortem-reviewer"}), dict(_earlier(), findingKey="k-2", id="f-2",
                                                                             **{RAISED: "code-reviewer"})]}
    earlier = [_earlier(**{RAISED: "code-reviewer"}), dict(_earlier(), findingKey="k-2", id="f-2")]
    rs._fill(account, earlier)
    assert account["findings"][0][RAISED] == "code-reviewer"
    # axis: an earlier record finding without a raiser leaves the later one without it
    assert RAISED not in account["findings"][1]


def test_r2_fill_names_the_raiser_on_a_later_finding_that_lacks_one():
    # axis: a later finding with no raiser takes the earlier record's
    account = {"findings": [_earlier()]}
    rs._fill(account, [_earlier(**{RAISED: "code-reviewer"})])
    assert account["findings"][0][RAISED] == "code-reviewer"


@pytest.mark.parametrize("held", ["", "  ", None, 4])
def test_r2_fill_treats_a_blank_earlier_raiser_as_none(held):
    # axis: a blank or non-string earlier raiser is none, so it clears nothing and names nothing
    account = {"findings": [_earlier(**{RAISED: "premortem-reviewer"})]}
    rs._fill(account, [_earlier(**{RAISED: held})])
    assert RAISED not in account["findings"][0]


def test_r2_a_finding_this_session_did_not_raise_is_carried_with_its_raiser_and_without_one_when_it_had_none():
    # axis: a carried earlier finding keeps its raiser, and has none when it had none
    account = {"findings": []}
    earlier = [_earlier(reason="fixed in abc", **{RAISED: "code-reviewer"}),
               dict(_earlier(reason="fixed in abc"), findingKey="k-2", id="f-2")]
    one, two = rs._carried(account, earlier)
    assert one[RAISED] == "code-reviewer" and RAISED not in two


# ---- V1: the account validator ---------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", "\t\n", None, 5, True, ["code-reviewer"], {"a": 1}])
def test_v1_an_empty_whitespace_or_non_string_raiser_is_refused(tmp_path, bad):
    # axis: raisedBy is a non-blank string or absent
    out = rr.write(put(tmp_path, acct(findings=[record_finding(**{RAISED: bad})])), str(tmp_path), RecordFake().readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "findings[0].raisedBy"), out


def test_v1_an_absent_or_non_blank_raiser_is_accepted(tmp_path):
    # axis: the validator accepts an absent or non-blank raiser and the record posts it unchanged
    fake = RecordFake()
    for kwargs in ({}, {RAISED: "code-reviewer"}, {RAISED: "searcher:S-1:2"}, {RAISED: "fix auditor"}):
        out = rr.write(put(tmp_path, acct(findings=[record_finding(**kwargs)])), str(tmp_path), fake.readers())
        assert out["ok"], (kwargs, out)
    posted = rr.read(7, readers=fake.readers())["findings"][0]
    assert posted[RAISED] == "fix auditor"


# ---- H1: content identity --------------------------------------------------------------------------------------


def test_h1_two_findings_that_differ_only_in_raiser_share_a_content_hash():
    # axis: the loop-stamped raiser is outside the content hash, so identity does not depend on the seat
    a, b = _finding(**{RAISED: "code-reviewer"}), _finding(**{RAISED: "premortem-reviewer"})
    assert RAISED in SC.TRANSIENT_FINDING_FIELDS
    assert SC.content_hash_suffix(a) == SC.content_hash_suffix(b) == SC.content_hash_suffix(_finding())
    assert SC.content_hash_suffix(_finding(title="another")) != SC.content_hash_suffix(a)


# ---- A1: abandoned-session recovery ----------------------------------------------------------------------------


def _unfolded(tmp_path, seat, phase):
    s = Session(tmp_path, terminal=None).seat(seat, phase=phase)
    session = s.save()
    put_envelope(session, seat, {"vendor": "codex", "model": CODEX, "payload": {"findings": [
        {"title": "Unfolded defect", "severity": "Important", "consequence": CONSEQUENCE, "file": "a.py", "line": 3}]}},
        phase=phase)
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned=REASON)
    (f,) = account["findings"]
    rr._validate(account)
    return f


def test_a1_an_unfolded_panel_report_is_raised_by_its_seat(tmp_path):
    # axis: recovery stamps an unfolded panel report with its seat key
    assert _unfolded(tmp_path, "code-reviewer", round_phases.P_PANEL)[RAISED] == "code-reviewer"


def test_a1_an_unfolded_stage_report_is_raised_by_its_stage_name(tmp_path):
    # axis: recovery stamps an unfolded non-panel report with its stage name
    assert _unfolded(tmp_path, "seams-check", round_phases.P_SEAMS)[RAISED] == SC.OUTSIDE_SEAMS_CHECK


def test_a1_an_unfolded_sweep_hit_is_raised_by_its_searcher_seat(tmp_path):
    # axis: recovery stamps an unfolded sweep hit with its searcher seat key
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE)}))
    (f,) = account["findings"]
    assert f[RAISED] == SEAT_1 and f["reviewer"] == SEAT_1
