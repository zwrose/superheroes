"""The review record's re-run line reads the driver's decision on a verify re-run and never works it out again.

A verify re-run entry carries the driver's `decision` (`went-on`, `head-moved`, `tree-changed`, `failed`) and, for
`head-moved`, the two heads the driver named. The line says "on unchanged code" only for `went-on`. The full line
adds a clause to a `head-moved` entry (the two heads) and a `tree-changed` entry (changed working-tree contents);
the compact lead drops "on unchanged code" unless every entry went on. An entry with no `decision` (a record an
earlier version wrote), or one the record cannot read, never says it.

Edges: a missing, null, empty or non-string head in `heads` is named `unknown`; the runs' own `head` keys are not
read at all; an entry that is not a dict gives no decision and the reader does not raise.

Bite-proof record: c1l9b_woc_rerun_heads (the heads reading this file first pinned) and
c1l10b_wo3_verify_rerun_seam (the decision reading that replaced it)
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
NO_CLAIM_FULL = "Re-run after one failure: round 2 `pytest -q tests/x.py`: failed (exit 1) then passed"
NO_CLAIM_COMPACT = "Re-run after one failure: 1 checks (listed in the full record)."
SUFFIX = f" — the second run was at a different head ({'1' * 12} then {'2' * 12})"
TREE_SUFFIX = " — the second run saw changed working-tree contents"


def verify_check(first_head=H1, second_head=H1, **over):
    runs = [run(code=1, head=first_head, headSource="run"), run(code=0, head=second_head, headSource="run")]
    return check(round=2, check="pytest -q tests/x.py", runs=runs, **over)


def rerun_lines(checks):
    record = build(account(rerunChecks=checks))
    full = [l for l in lines_of(rr._summary(record, 0)) if l.startswith("Re-run after")]
    compact = [l for l in lines_of(rr._summary(record, 1)) if l.startswith("Re-run after")]
    assert len(full) == 1 and len(compact) == 1
    return full[0], compact[0]


def test_1_a_head_moved_entry_names_the_two_heads_and_the_compact_lead_drops_unchanged_code():
    # axis: a re-run the driver halted at a moved head is never called unchanged code
    full, compact = rerun_lines([verify_check(decision="head-moved", heads=[H1, H2])])
    assert full == NO_CLAIM_FULL + SUFFIX
    assert H1[:13] not in full and H2[:13] not in full
    assert compact == NO_CLAIM_COMPACT
    assert "unchanged code" not in full and "unchanged code" not in compact


def test_1b_the_heads_come_from_the_entry_not_from_the_runs():
    # the runs' own heads agree here; the driver's decision is what the line reads
    full, compact = rerun_lines([verify_check(H1, H1, decision="head-moved", heads=[H1, H2])])
    assert full == NO_CLAIM_FULL + SUFFIX
    assert compact == NO_CLAIM_COMPACT


def test_1c_a_tree_changed_entry_names_the_changed_contents_and_is_not_unchanged_code():
    full, compact = rerun_lines([verify_check(decision="tree-changed")])
    assert full == NO_CLAIM_FULL + TREE_SUFFIX
    assert compact == NO_CLAIM_COMPACT


def test_1d_a_failed_entry_says_nothing_about_the_code():
    full, compact = rerun_lines([verify_check(decision="failed")])
    assert (full, compact) == (NO_CLAIM_FULL, NO_CLAIM_COMPACT)


def test_2_a_went_on_entry_renders_todays_text_and_the_record_does_not_look_at_the_runs_heads():
    for first, second in [(H1, H1), (H1, H2), (None, None), (H1, "")]:
        full, compact = rerun_lines([verify_check(first, second, decision="went-on")])
        assert (full, compact) == (TODAY_FULL, TODAY_COMPACT)


@pytest.mark.parametrize("heads", [None, [None, H2], [H1, None], [None, None]])
def test_3_an_unknown_head_in_a_head_moved_entry_is_named_unknown(heads):
    over = {} if heads is None else {"heads": heads}
    full, compact = rerun_lines([verify_check(decision="head-moved", **over)])
    assert "unchanged code" not in full and "unchanged code" not in compact
    first = H1[:12] if heads and heads[0] else "unknown"
    second = H2[:12] if heads and heads[1] else "unknown"
    assert f"different head ({first} then {second})" in full


def test_3b_an_entry_with_no_decision_never_says_unchanged_code():
    # axis: an entry an earlier version wrote claims nothing
    for first, second in [(H1, H1), (H1, H2), (None, None)]:
        full, compact = rerun_lines([verify_check(first, second)])
        assert (full, compact) == (NO_CLAIM_FULL, NO_CLAIM_COMPACT)
    full, compact = rerun_lines([check(round=2, check="pytest -q tests/x.py")])
    assert (full, compact) == (NO_CLAIM_FULL, NO_CLAIM_COMPACT)


def test_4_the_full_lead_and_the_compact_lead_claim_unchanged_code_only_when_every_entry_went_on():
    went_on = verify_check(decision="went-on")
    other = check(round=3, check="make test", decision="failed")
    full, compact = rerun_lines([went_on, dict(went_on, round=3, check="make test")])
    assert full.startswith("Re-run after one failure on unchanged code: ")
    assert compact == "Re-run after one failure on unchanged code: 2 checks (listed in the full record)."
    full, compact = rerun_lines([verify_check(decision="head-moved", heads=[H1, H2]), other])
    assert full == NO_CLAIM_FULL + SUFFIX + "; round 3 `make test`: failed (exit 1) then passed"
    assert full.count("different head") == 1
    assert compact == "Re-run after one failure: 2 checks (listed in the full record)."
    full, compact = rerun_lines([went_on, other])
    assert "unchanged code" not in full and "unchanged code" not in compact


@pytest.mark.parametrize("entry", [None, "x", 5, [], {}, {"decision": None}, {"decision": "moved"},
                                   {"decision": ["went-on"]}, {"decision": 3}])
def test_the_reader_gives_no_decision_and_does_not_raise_on_an_entry_it_cannot_read(entry):
    assert rr._decision(entry) is None


@pytest.mark.parametrize("decision", rr.RERUN_DECISIONS)
def test_the_reader_returns_the_four_decisions_the_driver_records(decision):
    assert rr._decision({"decision": decision}) == decision
    assert set(rr.RERUN_DECISIONS) == {"went-on", "head-moved", "tree-changed", "failed"}
