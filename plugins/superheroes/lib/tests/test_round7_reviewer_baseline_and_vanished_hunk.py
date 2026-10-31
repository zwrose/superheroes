"""Round-7 review fixes in round_driver.

A1 a finding raised again with the identical test block keeps the reviewer original it held.
B1 a fix that removes a whole PR hunk does not anchor the removal on an untouched sibling hunk.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import round_driver as RD  # noqa: E402

CORRECTED = "def test_x():\n    assert True\n"
ORIGINAL = "def test_x():\n    assert False\n"


def _finding(**over):
    base = {"file": "tests/test_charge.py", "line": 1, "title": "Retry charges twice",
            "severity": "Important", "taxonomy": "break-it-test",
            "consequence": "a customer is billed twice", "consequenceKind": "real",
            "suggestion": RD._break_it_block_text({"path": "tests/test_charge.py", "run": "pytest"},
                                                  CORRECTED)}
    base.update(over)
    return base


def test_a1_an_identical_test_block_raised_again_keeps_the_reviewer_original():
    # bites on: the identical-block re-raise dropping the held REVIEWER_TEST_FIELD baseline
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    ledger, seen = [], {}
    held = _finding(**{RD.REVIEWER_TEST_FIELD: ORIGINAL,
                       RD.break_it.RUNS_FIELD: [{"test": "tests/test_charge.py",
                                                 "changedWhy": "the draft missed an import"}]})
    key = RD._finding_identity_key(held)
    RD._seed_ledger_entry(state, ledger, seen, held, key, 1)
    entry = RD._seed_ledger_entry(state, ledger, seen, _finding(), key, 2)
    assert entry[RD.REVIEWER_TEST_FIELD] == ORIGINAL
    assert entry[RD.break_it.RUNS_FIELD][0]["changedWhy"] == "the draft missed an import"


_REVIEWED = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
             "@@ -10,1 +10,1 @@\n-a\n+b\n"
             "@@ -100,1 +100,1 @@\n-x\n+y\n")
_HEAD = ("diff --git a/f.py b/f.py\nindex 1..3 100644\n--- a/f.py\n+++ b/f.py\n"
         "@@ -100,1 +100,1 @@\n-x\n+y\n")


def test_b1_a_fully_reverted_hunk_is_removal_only_not_anchored_on_a_sibling():
    # bites on: _removal_anchor adopting the next surviving hunk when the removed lines' own hunk is gone
    surface, _text = RD._fix_delta_surface(RD.new_state({"leg": "code", "vendors": ["claude"],
                                                          "fixerVendor": "claude"}), _REVIEWED, _HEAD)
    entries = surface["f.py"]
    assert [(h["start"], h["end"], h.get("removedOnly")) for h in entries] == [(0, 0, True)], entries
