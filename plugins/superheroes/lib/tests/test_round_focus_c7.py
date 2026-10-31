"""Every round from 2 on records one focus (the last fixes, or wider with the reason), and the review
record lists every wider round with its reason."""
import os
import sys

import pytest

import review_record as rr
import review_record_session as rs
import round_driver as RD

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_review_record as trr  # noqa: E402
import test_review_record_session as trs  # noqa: E402


def _mk_diff(sections):
    parts = []
    for path, body in sections:
        parts.extend(["diff --git a/%s b/%s" % (path, path), "index 1111111..2222222 100644",
                      "--- a/%s" % path, "+++ b/%s" % path, body])
    return "\n".join(parts) + "\n"


_REVIEWED = _mk_diff([("f.py", "@@ -1 +1 @@\n-a\n+b"), ("g.py", "@@ -1 +1 @@\n-a\n+b")])
_HEAD = _mk_diff([("f.py", "@@ -1 +1 @@\n-a\n+c"), ("g.py", "@@ -1 +1 @@\n-a\n+d"),
                  ("h.py", "@@ -1 +1 @@\n-a\n+n")])
_CONSEQUENCE = "a reviewer-found defect stays in the change"


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": _REVIEWED, "fixerVendor": "codex"}


def _fix(file, title):
    return {"file": file, "line": 1, "title": title, "severity": "Important", "consequence": _CONSEQUENCE}


def _round_two_state(fix_batch):
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["rounds"] = {"2": {}}
    state["decisions"] = []
    state["deltaBaseline"] = {"round": 2, "diff": _REVIEWED}
    state["reviewedDiff"] = _REVIEWED
    state["headDiff"] = _HEAD
    state["fixBatch"] = fix_batch
    return state


def _unknown_surface_state():
    state = _round_two_state([])
    state["_headDiffUnknown"] = True
    state["_headDiffSource"] = "unknown"
    RD._enter_delta_round(state, _cfg(), panel_diff_seam=lambda *_: (_HEAD, None), panel_head="a" * 40)
    return state


def _wider_account(**over):
    return trr.account(rounds={"count": 3, "cap": 5, "stoppedAtCap": False,
                               "wider": [{"round": 2, "why": "delta surface unknown"}]}, **over)


def test_t1_a_round_that_fixed_two_findings_audits_exactly_those_and_records_them():
    batch = [_fix("f.py", "bug f"), _fix("g.py", "bug g")]
    keys = [RD._finding_key_of(f) for f in batch]
    state = _round_two_state(batch)
    RD._enter_delta_round(state, _cfg())
    # axis: the delta round records the fixes it audits as its focus — see bite-proof record wo3_c7_round_focus
    assert [t["id"] for t in state["_auditTargets"]] == keys
    assert state["step"] == RD.P_AUDITS
    assert state["rounds"]["2"]["roundKind"] == "delta"
    assert state["rounds"]["2"]["focus"] == {"on": "fixes", "fixes": keys}


def test_edge1_a_delta_rounds_focus_fixes_equal_the_previous_fix_batch_keys():
    batch = [_fix("g.py", "bug g"), _fix("f.py", "bug f")]
    state = _round_two_state(batch)
    RD._enter_delta_round(state, _cfg())
    focus = state["rounds"]["2"]["focus"]
    assert focus["on"] == "fixes"
    assert focus["fixes"] == [RD._finding_key_of(batch[0]), RD._finding_key_of(batch[1])]
    assert len(focus["fixes"]) == 2


def test_edge2_an_unknown_surface_round_hands_back_and_records_no_wider_focus():
    # re-pinned: an unknown surface used to open a wider (full-panel) round; it hands the PR back now
    state = _unknown_surface_state()
    rec = state["rounds"].get("2", {})
    assert state["terminal"] == "handed-back"
    assert [d["kind"] for d in state["decisions"]] == ["fix-surface-unknown"]
    assert "focus" not in rec and rec.get("roundKind") != "full-panel-unknown-surface"


def test_edge2_a_converged_delta_settle_opens_no_confirmation_round():
    # re-pinned: the settle ends on the round's audit and scoped finder; no wider confirmation round
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"] = {"1": {}}
    state["decisions"] = []
    RD._settle_delta_converged(state, _cfg())
    assert state["round"] == 1 and "2" not in state["rounds"]
    assert not any(d["kind"] == "confirmation-rearm" for d in state["decisions"])
    assert "focus" not in state["rounds"]["1"]


def test_t2_a_wider_rounds_why_reaches_the_review_records_rounds_and_its_rendered_line(tmp_path):
    why = "delta surface unknown — full reviewer-deep panel"
    s = trs.Session(tmp_path, rounds={"1": {}, "2": {"focus": {"on": "fixes", "fixes": ["a.py::t@L3"]}},
                                      "3": {"focus": {"on": "wider", "why": why}}})
    s.seat("code-reviewer")
    session = s.save()
    account = rs.account_from_session(session, trs.extras(), trs.Fake().readers())
    assert account["rounds"]["wider"] == [{"round": 3, "why": why}]
    fake = trs.Fake()
    out = trs.send(tmp_path, session, fake)
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert rec["rounds"]["wider"] == [{"round": 3, "why": why}]
    assert "Round 3 looked wider than the last fixes: %s" % why in fake.marked()[0]["body"]


def test_the_session_account_lists_wider_rounds_in_round_order_and_only_wider_ones(tmp_path):
    s = trs.Session(tmp_path, rounds={"10": {"focus": {"on": "wider", "why": "late"}},
                                      "2": {"focus": {"on": "wider", "why": "early"}},
                                      "3": {"focus": {"on": "fixes", "fixes": []}}})
    s.seat("code-reviewer")
    rounds = rs.account_from_session(s.save(), trs.extras(), trs.Fake().readers())["rounds"]
    assert rounds["wider"] == [{"round": 2, "why": "early"}, {"round": 10, "why": "late"}]


def test_a_session_with_no_wider_round_leaves_the_wider_key_out(tmp_path):
    s = trs.Session(tmp_path, rounds={"1": {}, "2": {"focus": {"on": "fixes", "fixes": ["a.py::t@L3"]}}})
    s.seat("code-reviewer")
    rounds = rs.account_from_session(s.save(), trs.extras(), trs.Fake().readers())["rounds"]
    assert "wider" not in rounds


@pytest.mark.parametrize("wider", [
    pytest.param([{"round": "2", "why": "unknown"}], id="string-round"),
    pytest.param([{"round": True, "why": "unknown"}], id="bool-round"),
    pytest.param([{"round": 2, "why": "   "}], id="blank-why"),
    pytest.param([{"round": 2, "why": ""}], id="empty-why"),
    pytest.param([{"round": 2, "why": None}], id="null-why"),
    pytest.param([{"round": 2}], id="missing-why"),
    pytest.param(["round 2"], id="non-object-entry"),
    pytest.param("round 2: unknown", id="string-wider"),
    pytest.param(None, id="null-wider"),
    pytest.param({"round": 2, "why": "unknown"}, id="object-wider"),
])
def test_edge3_a_malformed_rounds_wider_is_refused(tmp_path, wider):
    # axis: the rounds.wider validation refuses a malformed entry or a non-list — see bite-proof record wo3_c7_round_focus
    acct = trr.account(rounds={"count": 2, "cap": 5, "stoppedAtCap": False, "wider": wider})
    fake = trr.Fake()
    out = rr.write(trr.put(tmp_path, acct), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "rounds")
    assert fake.writes == []


def test_edge3_a_well_formed_rounds_wider_is_accepted(tmp_path):
    fake = trr.Fake()
    out = rr.write(trr.put(tmp_path, _wider_account()), str(tmp_path), fake.readers())
    assert out["ok"], out


def test_edge4_a_record_with_no_wider_round_renders_exactly_as_before():
    plain = trr.build(trr.account())
    other = trr.build(trr.account(rounds={"count": 1, "cap": 3, "stoppedAtCap": False, "wider": []}))
    other["writtenAt"] = plain["writtenAt"]
    assert other == plain
    assert rr.render(other) == rr.render(plain)
    assert "looked wider" not in rr.render(plain)


def test_edge4_a_wider_round_adds_one_line_per_wider_round_and_nothing_else_moves():
    plain = trr.build(trr.account(rounds={"count": 3, "cap": 3, "stoppedAtCap": False}))
    wider = trr.build(trr.account(rounds={"count": 3, "cap": 3, "stoppedAtCap": False, "wider": [
        {"round": 2, "why": "delta surface unknown"}, {"round": 3, "why": "Critical surfaced by confirmation"}]}))
    wider["writtenAt"] = plain["writtenAt"]
    body = rr.render(wider)
    assert "Round 2 looked wider than the last fixes: delta surface unknown" in body
    assert "Round 3 looked wider than the last fixes: Critical surfaced by confirmation" in body
    assert body.count("looked wider than the last fixes") == 2
    assert [l for l in body.split("```json")[0].splitlines() if "looked wider" not in l] == \
        rr.render(plain).split("```json")[0].splitlines()
