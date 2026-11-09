"""A break-it test on a finding never sent for fixing does not block the certificate (#2397).

At the converge gate a break-it run whose finding has no disposition withholds the certificate, unless the
finding was never fix-bound and ends as `craft` or `left-for-owner`: then the kept step records a
`not-required` row naming that outcome and does not withhold. An absent disposition stays no waiver for a
fix-bound finding (one that went to a fixer, is queued, is blocking, is ruled, or was merged).

Cases:
- T1 a Minor code-quality finding converges, row `not-required` / `craft`, and the settle writes the same outcome
- T2 a Minor owner-facing finding converges, row `not-required` / `left-for-owner`, and the settle agrees
- T3 a Minor finding that once went to a fixer in a slice (history seq 0, no ruling) withholds, for both kinds
- T4 a Minor finding queued in the fix queue now withholds
- T5 a Minor finding with a ruling bound to it withholds
- T6 a blocking finding (Critical or Important) with no disposition withholds

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_a_2397_never_sent.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_driver as RD  # noqa: E402
from test_break_it_loop import World, _break_it_finding, _TEST_FAILING  # noqa: E402

CODE_QUALITY = RD.review_findings_schema.CODE_QUALITY
OUTCOMES = RD.review_findings_schema.OUTCOMES


def _converge(world):
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    return world.round_record["breakItKept"]


def _folded(tmp_path, **extra):
    world = World(tmp_path)
    world.fold_panel(_break_it_finding(_TEST_FAILING, **extra))
    key = world.key_of_failed_run()
    world.fix(None)
    return world, key


def _settled(world, key):
    by_key, fault = RD._disposition_ledger_by_key(world.state)
    assert fault is None
    return by_key[key]["disposition"]


def _ledger_row(world, key):
    """A copy of the finding's ledger row: a folded candidate is seeded there, not into `findings`."""
    by_key, fault = RD._disposition_ledger_by_key(world.state)
    assert fault is None and isinstance(by_key.get(key), dict)
    return dict(by_key[key])


def _withheld(world):
    (row,) = _converge(world)
    assert world.state["terminal"] == "cannot-certify"
    assert row["outcome"] == "unresolved" and row["reason"] == "no-disposition"


def test_t1_a_minor_code_quality_finding_never_sent_converges_as_craft(tmp_path):
    # bites on: G1 the waiver branch (helper returning None withholds), and the craft token (outcomes[2]) chosen by the code-quality kind
    world, key = _folded(tmp_path, severity="Minor", consequenceKind=CODE_QUALITY)
    (row,) = _converge(world)
    assert world.state["terminal"] == "converged"
    assert row["findingKey"] == key
    assert row["outcome"] == "not-required" and row["reason"] == OUTCOMES[2] == "craft"
    assert row["neverSentForFix"] is True
    # preview == settle: the disposition the terminal's settle wrote is the row's reason
    assert _settled(world, key) == row["reason"]


def test_t2_a_minor_owner_facing_finding_never_sent_converges_as_left_for_owner(tmp_path):
    # bites on: G1 the waiver branch (helper returning None withholds), and the left-for-owner token (outcomes[3]) for a non-code-quality consequence
    world, key = _folded(tmp_path, severity="Minor")
    (row,) = _converge(world)
    assert world.state["terminal"] == "converged"
    assert row["findingKey"] == key
    assert row["outcome"] == "not-required" and row["reason"] == OUTCOMES[3] == "left-for-owner"
    assert row["neverSentForFix"] is True
    assert _settled(world, key) == row["reason"]


@pytest.mark.parametrize("kind", [CODE_QUALITY, "real"])
def test_t3_a_minor_finding_sent_once_in_a_slice_still_withholds(tmp_path, kind):
    # bites on: G2 the E1 history leg (presence of the lineage root in sentUnderDecision, even at seq 0)
    world, key = _folded(tmp_path, severity="Minor", consequenceKind=kind)
    state = world.state
    row = _ledger_row(world, key)
    assert RD._queue_fix_batch(state, state["config"], [row], session_dir=str(world.session)) == "queued"
    root = RD._lineage_root(RD._lineage_map(state), key)
    assert state["sentUnderDecision"][root] == 0
    for field in ("_fixBatch", "_fixQueue", "fixBatch"):
        state[field] = []
    assert RD._disposition_ledger_by_key(state)[0].get(key, {}).get("disposition") is None
    _withheld(world)


def test_t4_a_minor_finding_in_the_fix_queue_now_withholds(tmp_path):
    # bites on: E2 the queued-now leg (a row in _fixQueue, no history entry)
    world, key = _folded(tmp_path, severity="Minor")
    world.state["_fixQueue"] = [_ledger_row(world, key)]
    assert not world.state.get("sentUnderDecision")
    _withheld(world)


def test_t5_a_minor_finding_with_a_bound_ruling_withholds(tmp_path):
    # bites on: E6 the bound-ruling leg (any ruling kind withholds)
    world, key = _folded(tmp_path, severity="Minor")
    seq = RD._next_ruling_seq(world.state)
    RD._writable_rulings_log(world.state).append(
        {"seq": seq, "round": world.state["round"], "findingKey": key, "ruling": "guidance",
         "reason": "r", "id": key, "guidance": "G"})
    assert RD._live_ruling_by_key(world.state).get(key) is not None
    assert not world.state.get("sentUnderDecision")
    _withheld(world)


@pytest.mark.parametrize("severity", ["Critical", "Important"])
def test_t6_a_blocking_finding_with_no_disposition_withholds(tmp_path, severity):
    # bites on: G3 the E3 severity leg (a blocking severity is fix-bound)
    world, key = _folded(tmp_path, severity=severity)
    assert not world.state.get("sentUnderDecision")
    _withheld(world)
