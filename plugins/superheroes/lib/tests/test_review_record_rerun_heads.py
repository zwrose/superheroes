"""The review record's re-run line never calls a re-run across two different heads "unchanged code".

A verify re-run entry carries `head` on each of its two runs. When both are known and differ, the full line adds
a clause to that entry and the compact lead drops "on unchanged code"; every other entry (equal heads, an unknown
head, no `head` keys at all) renders exactly as before.

Edges: a missing, null, empty or non-string head is unknown and never counts as moved; equal heads are not moved;
a `runs` list that is not two dicts gives no comparison and the helper does not raise.

Bite-proof record: c1l9b_woc_rerun_heads
"""
import pytest

import review_record as rr
# The record builders are the seam test's own (which re-exports the base test's), imported rather than copied.
from test_review_record_seam_c1l1 import account, build, check, lines_of, run

H1 = "1" * 12 + "a" * 28
H2 = "2" * 12 + "b" * 28
TODAY_FULL = ("Re-run after one failure on unchanged code: "
              "round 2 `pytest -q tests/x.py`: failed (exit 1) then passed")
TODAY_COMPACT = "Re-run after one failure on unchanged code: 1 checks (listed in the full record)."
SUFFIX = f" — the second run was at a different head ({'1' * 12} then {'2' * 12}), not on unchanged code"


def verify_check(first_head, second_head):
    runs = [run(code=1, head=first_head, headSource="run"), run(code=0, head=second_head, headSource="run")]
    return check(round=2, check="pytest -q tests/x.py", runs=runs)


def rerun_lines(checks):
    record = build(account(rerunChecks=checks))
    full = [l for l in lines_of(rr._summary(record, 0)) if l.startswith("Re-run after")]
    compact = [l for l in lines_of(rr._summary(record, 1)) if l.startswith("Re-run after")]
    assert len(full) == 1 and len(compact) == 1
    return full[0], compact[0]


def test_1_moved_heads_add_the_suffix_and_the_compact_lead_drops_unchanged_code():
    # axis: a re-run across two different heads is never called unchanged code
    full, compact = rerun_lines([verify_check(H1, H2)])
    assert full == TODAY_FULL + SUFFIX
    assert H1[:13] not in full and H2[:13] not in full
    assert compact == "Re-run after one failure: 1 checks (listed in the full record)."
    assert "on unchanged code" not in compact


def test_2_equal_heads_render_exactly_todays_text():
    full, compact = rerun_lines([verify_check(H1, H1)])
    assert (full, compact) == (TODAY_FULL, TODAY_COMPACT)


@pytest.mark.parametrize("first,second", [(H1, None), (None, H2), (None, None), (H1, ""), ("", H2), (H1, 12345)])
def test_3_an_unknown_head_renders_todays_text(first, second):
    full, compact = rerun_lines([verify_check(first, second)])
    assert (full, compact) == (TODAY_FULL, TODAY_COMPACT)


def test_3b_runs_with_no_head_key_render_todays_text():
    full, compact = rerun_lines([check(round=2, check="pytest -q tests/x.py")])
    assert (full, compact) == (TODAY_FULL, TODAY_COMPACT)


def test_4_an_entry_without_head_keys_is_unchanged_next_to_a_moved_verify_entry():
    full, compact = rerun_lines([verify_check(H1, H2), check(round=3, check="make test")])
    assert full == TODAY_FULL + SUFFIX + "; round 3 `make test`: failed (exit 1) then passed"
    assert full.count("different head") == 1
    assert compact == "Re-run after one failure: 2 checks (listed in the full record)."


@pytest.mark.parametrize("entry", [
    None, "x", {}, {"runs": None}, {"runs": []}, {"runs": [{"head": H1}]},
    {"runs": [{"head": H1}, {"head": H2}, {"head": "3" * 12}]}, {"runs": [{"head": H1}, "x"]},
    {"runs": [{"head": H1}, None]},
])
def test_the_helper_does_not_raise_on_a_runs_list_that_is_not_two_dicts(entry):
    assert rr._moved_heads(entry) is None


def test_the_helper_returns_the_two_heads_only_when_both_are_known_and_differ():
    assert rr._moved_heads({"runs": [{"head": H1}, {"head": H2}]}) == (H1, H2)
    assert rr._moved_heads({"runs": [{"head": H1}, {"head": H1}]}) is None
