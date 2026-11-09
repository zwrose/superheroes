"""#2401: the leftover refusal says when a missing finding shares one acceptance with another. The rule and the grouping are
unchanged (``missing`` refuses and passes exactly as before); only the refusal detail gains the sentence. No real gh."""
import pytest

import leftover_accepting as la
import vet_slot as vs
from test_vet_slot_leftovers_2280 import Fake, PR, REPO, body, read_ok, record_comment

F1 = {"id": "f-1", "title": "the retry loop never backs off", "outcome": "left-for-owner"}
F2 = {"id": "f-2", "title": "a stale cache entry survives restart", "outcome": "left-for-owner"}
F3 = {"id": "f-3", "title": "the export drops empty rows", "outcome": "left-for-owner"}

LINE1 = "f-1 %s: merging accepts slower recovery." % F1["title"]
LINE2 = "f-2 %s: merging accepts one stale read." % F2["title"]
LINE3 = "f-3 %s: merging accepts a short export." % F3["title"]

LEAD = "- Merging accepts these review findings:\n"
SUB_ALL = LEAD + "".join("  - %s\n" % line for line in (LINE1, LINE2, LINE3))
SUB_TWO = LEAD + "".join("  - %s\n" % line for line in (LINE1, LINE2))
NAMED_NOWHERE = "- %s\n" % LINE1
FLAT_ALL = "".join("- %s\n" % line for line in (LINE1, LINE2, LINE3))

SENTENCE = ("One acceptance counts for one finding: give each finding left for the owner its own top-level bullet "
            "carrying its id and its title, never a sub-bullet under a lead-in bullet.")
TODAY = ("What we're accepting does not name these findings left for the owner, each by its record id and its title in "
         "one line, matched as lib/leftover_accepting.py states: ")


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def handback(pr_body):
    return vs.run_verb("handback", PR, REPO, run=Fake(pr_body, [record_comment([F1, F2, F3])]))


def rec():
    return read_ok(F1, F2, F3)


def gap(f):
    return {"id": f["id"], "title": f["title"]}


def test_t1_sub_bullets_refuse_with_the_shared_acceptance_named():
    b = body(SUB_ALL)
    assert la.missing(rec(), b) == [gap(F2), gap(F3)]
    result = handback(b)
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted"
    for f in (F2, F3):
        assert "%s (%s) shares one acceptance with f-1 (%s)" % (f["id"], f["title"], F1["title"]) in result["detail"]
    assert SENTENCE in result["detail"]


def test_t2_named_nowhere_keeps_todays_wording_byte_for_byte():
    result = handback(body(NAMED_NOWHERE))
    assert result["reason"] == "leftover-not-accepted"
    assert result["detail"] == TODAY + "f-2 (%s); f-3 (%s)" % (F2["title"], F3["title"])
    assert "shares one acceptance" not in result["detail"] and "top-level bullet" not in result["detail"]


def test_t3_flat_bullets_pass():
    b = body(FLAT_ALL)
    assert la.missing(rec(), b) == []
    assert handback(b)["ok"] is True


def test_t4_mixed_shared_and_named_nowhere():
    b = body(SUB_TWO)
    result = handback(b)
    assert result["reason"] == "leftover-not-accepted"
    assert result["detail"] == (TODAY + "f-2 (%s) shares one acceptance with f-1 (%s); f-3 (%s). " % (
        F2["title"], F1["title"], F3["title"]) + SENTENCE)
    assert result["detail"].count(SENTENCE) == 1


def test_t5_describe_without_a_holder_is_todays_string():
    today = TODAY + "f-2 (t2)"
    assert la.describe([{"id": "f-2", "title": "t2"}]) == today
    assert la.describe([{"id": "f-2", "title": "t2", "sharedWith": []}]) == today


def test_e2_a_title_less_gap_and_holder_render_as_bare_ids():
    gaps = [{"id": "f-2", "title": None, "sharedWith": [{"id": "f-1", "title": None}, {"id": "f-4", "title": "t4"}]}]
    assert la.describe(gaps) == TODAY + "f-2 shares one acceptance with f-1 and f-4 (t4). " + SENTENCE


def test_e4_an_unheld_acceptance_adds_no_holder():
    """Under maximum matching an acceptance naming a gap is always held; a gap named by none keeps today's wording."""
    b = body(SUB_TWO)
    gaps = la.missing(rec(), b, shared=True)
    assert gaps[1] == {"id": "f-3", "title": F3["title"], "sharedWith": []}


@pytest.mark.parametrize("accepting", [SUB_ALL, NAMED_NOWHERE, FLAT_ALL, SUB_TWO])
def test_t6_which_leftovers_are_missing_never_changes(accepting):
    b = body(accepting)
    assert [{"id": g["id"], "title": g["title"]} for g in la.missing(rec(), b, shared=True)] == la.missing(rec(), b)
