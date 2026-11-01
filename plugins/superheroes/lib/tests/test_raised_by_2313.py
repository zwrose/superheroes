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
    f = _finding()
    assert RAISED not in _compile(f, sources={id(f): blank}, source=blank)


def test_c1_a_blank_sources_entry_falls_to_the_stage_source():
    f = _finding()
    assert _compile(f, sources={id(f): " "}, source=SC.OUTSIDE_SEAMS_CHECK)[RAISED] == SC.OUTSIDE_SEAMS_CHECK


@pytest.mark.parametrize("stage", [SC.OUTSIDE_FIX_AUDITOR, SC.OUTSIDE_SCOPED_FINDER, SC.OUTSIDE_SEAMS_CHECK])
def test_c1_a_stage_compile_carries_its_stage_name(stage):
    assert stage in ("fix auditor", "scoped finder", "seams check")
    assert _compile(_finding(), source=stage)[RAISED] == stage


def test_c1_a_panel_fold_stamps_each_staged_finding_with_its_seat(world):
    # axis: the panel fold passes the roster key through to compile
    from test_c4_sweep import _panel
    state = _panel(world, code_reviewer=[_sweep_parent(dimension="Failure-Mode", **{RAISED: "premortem-reviewer"})])
    (staged,) = state["_toVerify"]
    assert staged[RAISED] == "code-reviewer"
    (row,) = state[SC.DISPOSITION_LEDGER_KEY]
    assert row[RAISED] == "code-reviewer"


# ---- C2: a merge keeps the first raiser ------------------------------------------------------------------------


def test_c2_a_compile_dedupe_keeps_the_first_seats_raiser_even_when_the_later_one_wins_on_severity():
    # axis: the merged row's raiser is existing's, whichever side wins the base
    a, b = _finding(severity="Minor"), _finding(severity="Critical")
    compiled, drops = RD.mechanical_compile([a, b], DIFF, sources={id(a): "code-reviewer", id(b): "premortem-reviewer"})
    (row,) = compiled
    assert row["severity"] == "Critical" and row[RAISED] == "code-reviewer", row
    assert any(d["reason"] == RD.COMPILE_DROP_MERGED_SAME_PLACE for d in drops)


def test_c2_merge_same_finding_keeps_existings_raiser_when_incoming_wins():
    existing = dict(_compile(_finding(severity="Minor"), source="seams check"), **{RAISED: "code-reviewer"})
    incoming = dict(_compile(_finding(severity="Critical"), source="seams check"), **{RAISED: "premortem-reviewer"})
    merged = RD._merge_same_finding(existing, incoming)
    assert merged["severity"] == "Critical" and merged[RAISED] == "code-reviewer"


def test_c2_merge_same_finding_keeps_existings_raiser_when_existing_wins():
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
    held = dict(_compile(_finding(severity="Minor"), source="fix auditor"), **{RAISED: "code-reviewer"})
    fresh = dict(_compile(_finding(severity="Critical"), source="fix auditor"), **{RAISED: "premortem-reviewer"})
    [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
    assert row["severity"] == "Critical" and row[RAISED] == "code-reviewer"


def test_l2_a_carried_finding_without_a_raiser_stays_without_one():
    held = _compile(_finding(severity="Minor"))
    fresh = dict(_compile(_finding(severity="Critical")), **{RAISED: "premortem-reviewer"})
    [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
    assert row["severity"] == "Critical" and RAISED not in row


# ---- W1: a sweep hit -------------------------------------------------------------------------------------------


def test_w1_a_sweep_hit_finding_carries_the_searcher_seat_key():
    parent = _sweep_parent()
    hit = _hit(19)
    assert SC.sweep_hit_finding(hit, {"sweepId": "S-1"}, parent, raised_by="searcher:S-1:2")[RAISED] == "searcher:S-1:2"


@pytest.mark.parametrize("blank", [None, "", "  ", 3, ["searcher:S-1:1"]])
def test_w1_a_blank_or_non_string_raiser_stamps_nothing(blank):
    assert RAISED not in SC.sweep_hit_finding(_hit(19), {"sweepId": "S-1"}, _sweep_parent(), raised_by=blank)
    assert RAISED not in SC.sweep_hit_finding(_hit(19), {"sweepId": "S-1"}, _sweep_parent())


def test_w1_the_fold_stamps_each_inside_hit_with_the_seat_of_the_part_that_found_it(world):
    # axis: the sweep fold maps each hit to the seat key of its own part
    _to_sweep(world, _sweep_parent(severity="Critical"))
    state = _sweep(world, {"searcher:S-1:1": [], "searcher:S-1:2": [_hit(19, file="src/a.py")]})
    (hit,) = state["_toVerify"]
    assert hit["line"] == 19 and hit[RAISED] == "searcher:S-1:2"
    (row,) = [r for r in state[SC.DISPOSITION_LEDGER_KEY] if r["line"] == 19]
    assert row[RAISED] == "searcher:S-1:2"


# ---- R1: the record writer -------------------------------------------------------------------------------------


def test_r1_the_record_finding_carries_the_ledger_rows_raiser_not_its_lens(tmp_path):
    # axis: the writer copies raisedBy from the ledger row onto the record finding
    row = ledger_row("k-1", id="f-1", dimension="Failure-Mode", **{RAISED: "premortem-reviewer"})
    plain = ledger_row("k-2", id="f-2", line=4)
    _, by_id = _record_rows(tmp_path, row, plain)
    assert by_id["f-1"][RAISED] == "premortem-reviewer"
    assert RAISED not in by_id["f-2"]  # no known raiser: absent, never guessed from the dimension


def test_r1_a_blank_raiser_on_a_ledger_row_is_no_raiser(tmp_path):
    rows = [ledger_row("k-%d" % i, id="f-%d" % i, line=3 + i, **{RAISED: v}) for i, v in enumerate(["", "  ", None, 5])]
    _, by_id = _record_rows(tmp_path, *rows)
    assert all(RAISED not in f for f in by_id.values()), by_id


def test_r1_the_ledger_rows_raiser_wins_over_a_live_rows(tmp_path):
    held = ledger_row("k-1", id="f-1", **{RAISED: "code-reviewer"})
    live = {"findingKey": "k-1", "id": "f-1", "title": "t", "severity": "Important", "file": "a.py", "line": 3,
            "detail": "d", "dimension": "code-reviewer", RAISED: "premortem-reviewer"}
    session = Session(tmp_path / "acct", dispositionLedger=[held], findings=[live]).seat("code-reviewer").save()
    account = rs.account_from_session(session, extras(), Fake().readers())
    (f,) = account["findings"]
    assert f[RAISED] == "code-reviewer"


def test_r1_a_live_row_with_no_ledger_row_supplies_its_raiser(tmp_path):
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
    account = {"findings": [_earlier()]}
    rs._fill(account, [_earlier(**{RAISED: "code-reviewer"})])
    assert account["findings"][0][RAISED] == "code-reviewer"


@pytest.mark.parametrize("held", ["", "  ", None, 4])
def test_r2_fill_treats_a_blank_earlier_raiser_as_none(held):
    account = {"findings": [_earlier(**{RAISED: "premortem-reviewer"})]}
    rs._fill(account, [_earlier(**{RAISED: held})])
    assert RAISED not in account["findings"][0]


def test_r2_a_finding_this_session_did_not_raise_is_carried_with_its_raiser_and_without_one_when_it_had_none():
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
    assert _unfolded(tmp_path, "code-reviewer", round_phases.P_PANEL)[RAISED] == "code-reviewer"


def test_a1_an_unfolded_stage_report_is_raised_by_its_stage_name(tmp_path):
    assert _unfolded(tmp_path, "seams-check", round_phases.P_SEAMS)[RAISED] == SC.OUTSIDE_SEAMS_CHECK


def test_a1_an_unfolded_sweep_hit_is_raised_by_its_searcher_seat(tmp_path):
    account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE)}))
    (f,) = account["findings"]
    assert f[RAISED] == SEAT_1 and f["reviewer"] == SEAT_1
