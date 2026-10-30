"""A finding raised again without its test keeps the test it held (audit comparison gate).

K1 re-seeding an unresolved attached-test finding with a plain suggestion keeps the held test block,
   run stamp and reviewer original, so the next audit still requires the test comparison.
K2 a finding that held no test takes the new finding's suggestion as supplied.
K3 a re-raise that carries its own test keeps its own block.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402

BLOCK = "\n".join(["break-it-test v1", "path: tests/test_a.py", "run: pytest tests/test_a.py", "---",
                   "def test_a():\n    assert False\n"])
OTHER = BLOCK.replace("assert False", "assert 1 == 2")
STAMP = {"test": "tests/test_a.py", "commit": "abc1234", "status": "ran", "exitCode": 1}


def _finding(**over):
    return dict({"file": "src/charge.py", "line": 7, "title": "Charge twice", "severity": "Important",
                 "consequence": "a customer is billed twice", "consequenceKind": "real"}, **over)


def _seeded_twice(first, second):
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    ledger, seen = [], {}
    key = RD._finding_identity_key(first)
    RD._seed_ledger_entry(state, ledger, seen, first, key, 1)
    RD._seed_ledger_entry(state, ledger, seen, second, key, 2)
    assert len(ledger) == 1
    return ledger[0]


def test_k1_a_re_raise_without_its_test_keeps_block_stamp_and_reviewer_original():
    # bites on: the round-2 entry replacing the held entry and dropping its test
    held = _finding(suggestion=BLOCK, **{break_it.RUN_FIELD: STAMP, RD.REVIEWER_TEST_FIELD: "orig"})
    assert break_it.carries_test(held)
    entry = _seeded_twice(held, _finding(suggestion="tighten the guard"))
    assert entry["suggestion"] == BLOCK
    assert entry[break_it.RUN_FIELD] == STAMP
    assert entry[RD.REVIEWER_TEST_FIELD] == "orig"
    assert break_it.carries_test(entry)


def test_k2_a_finding_that_held_no_test_takes_the_new_suggestion():
    # bites on: the restore firing for a finding that never carried a test
    entry = _seeded_twice(_finding(suggestion="old"), _finding(suggestion="new"))
    assert entry["suggestion"] == "new"
    assert break_it.RUN_FIELD not in entry


def test_k3_a_re_raise_carrying_its_own_test_keeps_its_own_block():
    # bites on: the held block overwriting a test the new finding carries
    held = _finding(suggestion=BLOCK)
    entry = _seeded_twice(held, _finding(suggestion=OTHER))
    assert entry["suggestion"] == OTHER
