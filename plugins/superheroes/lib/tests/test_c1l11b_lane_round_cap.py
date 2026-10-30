"""C1-L11b (FR-52): the record writer refuses a light or micro record over the round cap.

Each test drives `review_record.write` through the same injected readers the record writer's own tests use and
asserts the refusal token and that nothing was posted.
"""
import pytest

import review_record as rr
import round_phases
from test_review_record import Fake, account, put

TOKEN = "review-record-round-cap-exceeded"
CAP = round_phases.ROUND_CAP
EXTRA = {"why": "the advisor ordered one more audit round"}


def _rounds(count, extra=False):
    rounds = {"count": count, "cap": CAP, "stoppedAtCap": False}
    if extra:
        rounds["extraAudit"] = dict(EXTRA)
    return rounds


def _write(tmp_path, lane, count, extra=False):
    fake = Fake()
    out = rr.write(put(tmp_path, account(lane=lane, rounds=_rounds(count, extra))), str(tmp_path), fake.readers())
    return out, fake


def _refused(out, fake, lane, count):
    assert out["ok"] is False and out["reason"] == TOKEN, out
    assert lane in out["detail"] and str(count) in out["detail"] and str(CAP) in out["detail"]
    assert fake.writes == [] and fake.comments == []


def _written(out, fake):
    assert out["ok"], out
    assert len(fake.marked()) == 1


def test_e1_a_light_record_over_the_cap_without_the_extra_audit_round_is_refused(tmp_path):
    out, fake = _write(tmp_path, "light", CAP + 1)
    _refused(out, fake, "light", CAP + 1)


def test_e2_a_light_record_counts_at_most_the_cap_whether_or_not_it_ran_the_extra_audit_round(tmp_path):
    # `rounds.count` already leaves the extra audit round out, so the cap is held to the count as it stands
    out, fake = _write(tmp_path, "light", CAP, extra=True)
    _written(out, fake)
    over, fake_over = _write(tmp_path, "light", CAP + 1, extra=True)
    _refused(over, fake_over, "light", CAP + 1)
    assert "the extra audit round is not counted" in over["detail"], over


@pytest.mark.parametrize("count,extra,written", [(CAP + 1, False, False), (CAP, True, True), (CAP + 1, True, False)])
def test_e3_the_micro_lane_follows_the_same_rule(tmp_path, count, extra, written):
    out, fake = _write(tmp_path, "micro", count, extra)
    if written:
        _written(out, fake)
    else:
        _refused(out, fake, "micro", count)


def test_e4_the_full_lane_is_not_capped_here(tmp_path):
    out, fake = _write(tmp_path, "full", CAP + 1)
    _written(out, fake)


@pytest.mark.parametrize("lane", ["medium", None])
def test_e5_an_unknown_or_missing_lane_is_not_capped(tmp_path, lane):
    out, fake = _write(tmp_path, lane, CAP + 1)
    _written(out, fake)


@pytest.mark.parametrize("lane", ["light", "micro"])
def test_e6_a_count_at_the_cap_is_written(tmp_path, lane):
    out, fake = _write(tmp_path, lane, CAP)
    _written(out, fake)
