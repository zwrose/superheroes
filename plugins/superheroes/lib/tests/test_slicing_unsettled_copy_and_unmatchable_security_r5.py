"""Round-5 fixes: an unsettled unproven copy keeps its measured whole-file size, and unmatchable slice paths seat security."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import countable_lines as cl  # noqa: E402
import risk_areas  # noqa: E402
import round_driver  # noqa: E402
import slicing  # noqa: E402

BAR = cl.COUNTABLE_LINES_BAR


def test_an_unsettled_unproven_copy_keeps_its_measured_size():
    diff = ("diff --git a/src.py b/copy.py\nsimilarity index 100%\ncopy from src.py\ncopy to copy.py\n")
    rows = [{"file": "copy.py", "lines": 1200, "counted": False, "why": "unsettled"}]
    cr = {"countable": 0, "bar": BAR, "files": rows, "unsettled": [{"file": "copy.py", "reason": "attribute-unreadable"}]}
    pl = slicing.plan(diff, cr, ())
    assert pl["sliced"] is True
    assert pl["countable"] == 1200
    assert [p for s in pl["slices"] for p in s["parts"]] == [
        {"file": "copy.py", "lines": [[1, 1000]]}, {"file": "copy.py", "lines": [[1001, 1200]]}]


def test_unmatchable_slice_paths_seat_the_security_lens(monkeypatch):
    monkeypatch.setattr(risk_areas, "touched", lambda root, files: {
        "riskAreas": "set", "touched": [], "unmatchable": ["\\charge.py"]})
    assert round_driver._slice_security(["security-reviewer"], ".", [{"file": "\\charge.py"}]) is True


def test_matchable_untouched_slice_paths_do_not_seat_the_security_lens(monkeypatch):
    monkeypatch.setattr(risk_areas, "touched", lambda root, files: {
        "riskAreas": "set", "touched": [], "unmatchable": []})
    assert round_driver._slice_security(["security-reviewer"], ".", [{"file": "a.py"}]) is False
