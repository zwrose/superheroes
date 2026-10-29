"""A finding raised again keeps every break-it run it already held (#2251, C1-L6b).

S1 re-seeding a finding's ledger entry appends the new finding's runs after the held ones, none twice.
S2 a finding raised again without runs keeps the runs it held.
S3 a non-list `breakItRuns` on either side is left as supplied.
P1 the record writer's finding parts put the ledger row's runs first and the live row's new runs after them.
P2 the account built from a ledger entry and a live row for one key lists the runs of both, `changedWhy` intact.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract  # noqa: E402

RUNS = break_it.RUNS_FIELD
R1 = {"test": "tests/test_a.py", "commit": "abc1234", "status": "ran", "exitCode": 1,
      "output": "AssertionError: boom", "reason": None, "changedWhy": None}
R2 = dict(R1, commit="def5678", exitCode=0, output="ok", changedWhy="the import was misspelled")
R3 = dict(R1, commit="0123456", output="AssertionError: again")


def _finding(**over):
    return dict({"file": "src/charge.py", "line": 7, "title": "Charge twice", "severity": "Important",
                 "consequence": "a customer is billed twice", "consequenceKind": "real"}, **over)


def _seed(state, ledger, seen, finding, round_no):
    key = RD._finding_identity_key(finding)
    return RD._seed_ledger_entry(state, ledger, seen, finding, key, round_no)


def _seeded_twice(first_runs, second):
    """The ledger entry after round 1 seeds a finding holding ``first_runs`` and round 2 seeds ``second``."""
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    ledger, seen = [], {}
    _seed(state, ledger, seen, _finding(**{RUNS: first_runs}), 1)
    _seed(state, ledger, seen, second, 2)
    assert len(ledger) == 1
    return ledger[0]


# ---- S1 -----------------------------------------------------------------------------------------------------

def test_s1_a_finding_raised_again_with_a_new_run_keeps_the_runs_it_held():
    # bites on: the round-2 entry replacing the round-1 entry's run list with the new finding's own
    entry = _seeded_twice([R1, R2], _finding(**{RUNS: [R3]}))
    assert entry[RUNS] == [R1, R2, R3]
    assert entry[RUNS][1]["changedWhy"] == R2["changedWhy"]


def test_s1_a_run_already_held_is_not_listed_twice():
    # bites on: the new runs appended without the equality check against the held ones
    entry = _seeded_twice([R1, R2], _finding(**{RUNS: [R2, R3]}))
    assert entry[RUNS] == [R1, R2, R3]


# ---- S2 -----------------------------------------------------------------------------------------------------

def test_s2_a_finding_raised_again_without_runs_keeps_the_runs_it_held():
    # bites on: a re-raise carrying no run list wiping the held one
    entry = _seeded_twice([R1, R2], _finding())
    assert entry[RUNS] == [R1, R2]


# ---- S3 -----------------------------------------------------------------------------------------------------

def test_s3_a_non_list_value_on_either_side_is_left_as_supplied():
    # bites on: a non-list run value coerced to a list or dropped
    assert _seeded_twice([R1], _finding(**{RUNS: "not a list"}))[RUNS] == "not a list"
    assert _seeded_twice("not a list", _finding(**{RUNS: [R3]}))[RUNS] == [R3]


def test_s3_a_run_that_is_not_a_dict_is_compared_by_equality_and_never_raises():
    # bites on: a run compared as a dict (key lookup) rather than by equality
    entry = _seeded_twice([R1, "odd"], _finding(**{RUNS: ["odd", None, R3]}))
    assert entry[RUNS] == [R1, "odd", None, R3]


# ---- P1 -----------------------------------------------------------------------------------------------------

def test_p1_finding_parts_put_the_ledger_runs_first_and_the_live_rows_new_runs_after():
    # bites on: the live row's run list hiding the ledger row's earlier runs
    older = {"grade": {"verdict": "plausible"}, RUNS: [R1, R2]}
    row = {"grade": {"verdict": "confirmed"}, RUNS: [R3]}
    parts = rs._finding_parts(row, older)
    assert parts[RUNS] == [R1, R2, R3]
    assert parts["grade"] == {"verdict": "confirmed"}  # every other part stays row-first


def test_p1_finding_parts_list_a_run_both_rows_hold_once():
    # bites on: the merge appending a run the ledger row already holds
    assert rs._finding_parts({RUNS: [R2, R3]}, {RUNS: [R1, R2]})[RUNS] == [R1, R2, R3]


def test_p1_finding_parts_keep_todays_rule_for_a_non_list_value():
    # bites on: a non-list run value merged or dropped
    assert rs._finding_parts({RUNS: "odd"}, {RUNS: [R1]})[RUNS] == "odd"
    assert rs._finding_parts({RUNS: [R3]}, {RUNS: "odd"})[RUNS] == [R3]
    assert rs._finding_parts({}, {RUNS: [R1]})[RUNS] == [R1]


# ---- P2 -----------------------------------------------------------------------------------------------------

def test_p2_the_account_lists_the_ledger_runs_and_the_live_rows_new_run():
    # bites on: the account's finding listing only the live row's run
    live = _finding(**{RUNS: [R3]})
    key = RD._finding_identity_key(live)
    held = dict(live, **{RUNS: [R1, R2]})
    state = {session_contract.DISPOSITION_LEDGER_KEY: [held], "findings": [live]}
    (row,) = [f for f in rs._findings(state) if f["findingKey"] == key]
    assert row[RUNS] == [R1, R2, R3]
    assert row[RUNS][1]["changedWhy"] == R2["changedWhy"]
