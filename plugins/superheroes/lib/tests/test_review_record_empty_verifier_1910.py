"""#1910 defect 4: a hand-accepted verifier phase with nothing staged to verify is not a planned reviewer."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_phases  # noqa: E402

from test_review_record_session import CODEX, HEAD, Fake, extras, send  # noqa: E402
from test_review_record_session_c7l3 import _hand_session, _names  # noqa: E402

VERIFIER = "verifiers reviewer (round 1)"
ZERO = {"CONFIRMED": 0, "PLAUSIBLE": 0, "REFUTED": 0, "ambiguous": 0, "downgrades": 0, "drops": 0, "unverified": 0}
SEAT = {"vendor": "codex", "model": CODEX}


def _verifier_session(tmp_path, verify_passes="absent", prov=()):
    """A finished hand-submit session: one panel seat ran in round 1 and the round's verifier phase was accepted by hand."""
    session = _hand_session(tmp_path, {1: {"code-reviewer": "run"}},
                            seatMapReceipts=[{"round": "1", "map": {"seats": {"code-reviewer": SEAT}, "makerFamilies": ["xai"]}}])
    path = os.path.join(session, "loop-state.json")
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    if verify_passes != "absent":
        state["rounds"]["1"]["verifyPasses"] = verify_passes
    state["rounds"]["1"]["verifierProvenance"] = list(prov)
    state["_ordersAnchors"] = {"1:%s:0" % round_phases.P_VERIFIERS: {"headSha": HEAD}}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    with open(os.path.join(session, "driver-journal.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"cmd": "submit", "outcome": "accepted", "phase": round_phases.P_VERIFIERS, "round": 1, "attempt": 0}) + "\n")
    return session


def test_t1_an_empty_verifier_phase_adds_no_reviewer_and_does_not_park_the_record(tmp_path):
    session = _verifier_session(tmp_path, [dict(ZERO)])
    names = _names(rs.account_from_session(session, extras(), Fake().readers()))
    # bites on: an all-zero verifier phase listed as a planned reviewer that did not run
    assert VERIFIER not in names and "code-reviewer (round 1)" in names
    fake = Fake()
    out = send(tmp_path, session, fake, ci="green")
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert [v["name"] for v in rec["reviewers"]] == ["code-reviewer (round 1)"]
    # the fixture's panel seat is unbound to the final commit, so the status can read not-reviewed for that reason: assert the verifier's part only
    assert rec["missingReviews"] == [] and not any("verifiers" in line or "did not run" in line for line in out["whatIsMissing"])
    assert out["parked"] is False, out


def test_t2_a_verifier_phase_with_unanswered_findings_and_no_folded_verdicts_still_parks(tmp_path):
    session = _verifier_session(tmp_path, [dict(ZERO, unverified=2)])
    names = _names(rs.account_from_session(session, extras(), Fake().readers()))
    # bites on: a verifier phase that had staged findings and never ran being skipped as empty
    assert VERIFIER in names and names[VERIFIER]["ran"] is False
    fake = Fake()
    out = send(tmp_path, session, fake, ci="green")
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert [m["name"] for m in rec["missingReviews"]] == [VERIFIER]
    assert out["status"] == "not-reviewed" and out["parked"] is True, out


@pytest.mark.parametrize("passes", [
    "absent",
    [],
    "not-a-list",
    ["not-a-dict"],
    [{k: v for k, v in ZERO.items() if k != "unverified"}],
    [dict(ZERO, REFUTED=None)],
    [dict(ZERO, CONFIRMED=False)],
    [dict(ZERO), "not-a-dict"],
], ids=["missing", "empty-list", "not-a-list", "non-dict-entry", "entry-lacks-a-count", "null-count", "bool-count", "one-bad-entry"])
def test_t3_a_verifyPasses_that_cannot_show_an_empty_phase_leaves_the_row_in_place(tmp_path, passes):
    session = _verifier_session(tmp_path, passes)
    names = _names(rs.account_from_session(session, extras(), Fake().readers()))
    # bites on: a missing or malformed verifyPasses read as proof that there was nothing to verify
    assert VERIFIER in names and names[VERIFIER]["ran"] is False
