"""#2434: a fix that only removes worthless test lines clears its audit on a `worthless-test-removed` answer.

Pins, each at the place the rule is enforced:

T1  a whole-function removal tied to the target's line clears; the entry records `testRemoval` and the id is listed
    in `testRemovalCleared` and `discharged`;
T2  `discharged-but-new-issue` clears the same way and keeps its new issue;
C1  a non-test file (or no readable delta) in the delta refuses;
C2  an absent, `unreadable` or malformed removal record refuses;
C3  a removal record and a delta that name different files refuse;
C4  a file that added a line, or removed none, refuses;
C5  a target that is not a Test finding with a worthless smell and a usable body refuses;
C6  a removal that holds none of the target's own cited lines refuses;
C7  a removed range that holds no cited line refuses, unless a worthless-smell sibling whose `citationFresh` is
    exactly True cites it (a stale, absent, string or int `citationFresh` lends nothing);
C8  a changed file in a language the test-opening reader does not support refuses;
C9  a test the base file opens inside a removed range on a line no finding cites refuses (the adjacent unflagged
    test, a whole file with one test cited, a boundary line, an opening only a stale sibling cites); every deleted
    test cited clears;
C10 a target whose `citationFresh` is not exactly True refuses;
O   `audits.test_openings` reads Python and JavaScript/TypeScript test openings, and nothing else;
G   `review-guarded` is judged exactly as before; the new answer is a fault on `right` and `brokeNothing`;
S   the strict-mode schema lists the answer for `testWouldFail` only;
R   `_fixer_removal` reads a real `git diff`: removed ranges (one per hunk whatever `diff.interHunkContext` says),
    additions, test openings of the base blob, binary files, an unreadable base blob, a missing commit, a configured
    textconv, and an explicit head older than the checkout;
D   the review record names the evidence; `_audit_targets` puts the record and the citation freshness on every
    target, and the citation freshness (alone) on every sibling of its `batchFindings`.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import review_record_session as RS  # noqa: E402
import session_contract as SC  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

TEST_FILE = "plugins/superheroes/lib/tests/test_widget_2434.py"
OTHER_TEST_FILE = "plugins/superheroes/lib/tests/test_gadget_2434.py"
RB_TEST_FILE = "plugins/superheroes/lib/tests/test_widget_2434.rb"
LIB_PY = "plugins/superheroes/lib/widget_2434.py"
RUBRIC_MD = "plugins/superheroes/rubric/some-doctrine-2434.md"
BODY = "The test asserts the exact prose of an error message, which is not a contract."
BAD_BASE = "0" * 40
NO_KEY = object()  # a row field left out altogether


def _delta(*files):
    """A driver-built `fixerDelta`: per file one `diff --git a/<f> b/<f>` header, then that file's lines."""
    out = []
    for name in files:
        out.append("diff --git a/%s b/%s" % (name, name))
        out.extend(["--- a/%s" % name, "+++ b/%s" % name, "@@ -1 +0,0 @@", "-old"])
    return out


def _row(path=TEST_FILE, removed=((10, 14),), added=False, openings=(12,)):
    """A removal row; `openings` is the base file's test openings (a tuple becomes the list the driver builds)."""
    if isinstance(removed, (tuple, list)):
        removed = [list(r) if isinstance(r, tuple) else r for r in removed]
    row = {"path": path, "removed": removed, "added": added,
           "testOpenings": list(openings) if isinstance(openings, tuple) else openings}
    if openings is NO_KEY:
        del row["testOpenings"]
    return row


def _record(*rows):
    return {"base": "a" * 40, "head": "b" * 40, "files": list(rows or [_row()])}


def _checks(**answers):
    return {name: {"answer": answers.get(name, "yes"), "why": "checked: %s" % name}
            for name in audits.CHECK_NAMES}


def _removed(**extra):
    return dict({"id": "t0", "ruling": "discharged", "reason": "the fix resolves it",
                 "checks": _checks(testWouldFail=audits.WORTHLESS_TEST_REMOVED)}, **extra)


def _target(files=(TEST_FILE,), record=None, **extra):
    target = {"id": "t0", "title": "T", "file": TEST_FILE, "line": 12, "auditorVendor": "codex",
              "dimension": "Test", "taxonomy": "wording pin", "body": BODY,
              "fixerDelta": _delta(*files), "fixerRemoval": record if record is not None else _record(),
              "citationFresh": True}
    target.update(extra)
    for key in [k for k, v in target.items() if v is NO_KEY]:
        del target[key]
    return target


def _fold(results, target):
    return audits.apply_audit_results([target], results, collection_manifest={"t0": "codex"})


def _only(outcome):
    (entry,) = outcome["audits"]
    return entry


def _refused(outcome, condition):
    entry = _only(outcome)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["testRemovalRefused"] == ["t0"] and outcome["testRemovalCleared"] == []
    assert entry["ruling"] == "not-discharged" and "testRemoval" not in entry
    prefix = ("audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test "
              "lines a worthless-test finding cites; %s: " % condition)
    assert entry["reason"].startswith(prefix), entry["reason"]
    return entry["reason"]


def _no_record(target):
    del target["fixerRemoval"]
    return target


# --- T1, T2 -------------------------------------------------------------------------------------------------------

def test_t1_a_whole_function_removal_tied_to_the_targets_line_clears():
    # axis: G1 — the clear arm for a test-removing `worthless-test-removed` result
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    result = _removed()
    result["checks"]["testWouldFail"]["why"] = "  the test only pinned wording  "
    outcome = _fold([result], _target())
    entry = _only(outcome)
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["testRemovalCleared"] == ["t0"] and outcome["testRemovalRefused"] == []
    assert entry["ruling"] == "discharged"
    assert entry["testRemoval"] == {
        "answer": audits.WORTHLESS_TEST_REMOVED, "why": "the test only pinned wording",
        "evidence": {"source": "finding", "finding": "t0", "taxonomy": "wording-pin", "reason": BODY,
                     "removed": [{"file": TEST_FILE, "ranges": [[10, 14]]}],
                     "cited": [{"file": TEST_FILE, "line": 12}],
                     "openings": [{"file": TEST_FILE, "lines": [12]}]}}


def test_t1_the_reason_is_the_stripped_body_cut_to_500_characters():
    outcome = _fold([_removed()], _target(body="  " + "x" * 600 + "  "))
    assert _only(outcome)["testRemoval"]["evidence"]["reason"] == "x" * 500


def test_t1_a_place_of_the_kind_of_mistake_inside_a_removed_range_ties_the_removal():
    target = _target(line=3, record=_record(_row(openings=(11,))), kindOfMistake={"kind": "pins prose", "places": [
        {"file": TEST_FILE, "line": 11}, {"file": TEST_FILE, "line": None}]})
    # a target that names places owes an answer for each of them (`fixed`), whatever the removal answer
    places = [{"file": TEST_FILE, "line": 11, "fixed": True}, {"file": TEST_FILE, "line": None, "fixed": True}]
    outcome = _fold([_removed(places=places)], target)
    assert outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["testRemoval"]["evidence"]["cited"] == [
        {"file": TEST_FILE, "line": 3}, {"file": TEST_FILE, "line": 11}]


@pytest.mark.parametrize("label,smell", [
    ("Wording pin", "wording-pin"), ("duplicate test", "duplicate-test"), ("mock-echo", "mock-echo"),
    ("Cannot fail", "cannot-fail"), ("  CANNOT--FAIL! ", "cannot-fail")])
def test_t1_every_worthless_smell_clears_after_normalizing(label, smell):
    assert audits.normalize_smell(label) == smell and smell in audits.WORTHLESS_TEST_SMELLS
    outcome = _fold([_removed()], _target(taxonomy=label))
    assert outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["testRemoval"]["evidence"]["taxonomy"] == smell


def test_t2_a_new_issue_ruling_clears_on_the_same_answer_and_keeps_its_new_issue():
    result = _removed(ruling="discharged-but-new-issue", newIssues=[{"title": "leak", "file": "f.py", "line": 2}])
    outcome = _fold([result], _target())
    assert outcome["discharged"] == ["t0"] and outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["ruling"] == "discharged-but-new-issue"
    assert _only(outcome)["testRemoval"]["answer"] == audits.WORTHLESS_TEST_REMOVED
    assert [i["title"] for i in outcome["newIssues"]] == ["leak"]


def test_t2_a_refused_new_issue_ruling_keeps_its_new_issue():
    result = _removed(ruling="discharged-but-new-issue", newIssues=[{"title": "leak"}])
    outcome = _fold([result], _target(files=(LIB_PY,)))
    _refused(outcome, "C1")
    assert [i["title"] for i in outcome["newIssues"]] == ["leak"]


# --- C1 -----------------------------------------------------------------------------------------------------------

def test_c1_a_non_test_file_in_the_delta_refuses_naming_it():
    # axis: G2 — C1, every file of the delta is a test path
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    record = _record(_row(), _row(LIB_PY))
    reason = _refused(_fold([_removed()], _target(files=(TEST_FILE, LIB_PY), record=record)), "C1")
    assert LIB_PY in reason


@pytest.mark.parametrize("target", [
    pytest.param(lambda: _no_record(_target()) | {"fixerDelta": []}, id="empty-delta"),
    pytest.param(lambda: _target() | {"fixerDelta": ["diff --git a/x.py b/y.py"]}, id="unreadable-header"),
    pytest.param(lambda: _target() | {"fixerDelta": None}, id="no-delta"),
])
def test_c1_an_absent_or_unreadable_delta_refuses(target):
    _refused(_fold([_removed()], target()), "C1")


# --- C2 -----------------------------------------------------------------------------------------------------------

def _with(record):
    return _target(record=None) | {"fixerRemoval": record}


@pytest.mark.parametrize("record", [
    pytest.param(None, id="none"),
    pytest.param("absent", id="absent"),
    pytest.param({"unreadable": "git failed", "base": None, "head": None}, id="unreadable"),
    pytest.param({"base": "a", "head": "b", "files": []}, id="no-files"),
    pytest.param({"base": "a", "head": "b", "files": "x"}, id="files-not-a-list"),
    pytest.param(_record(_row(removed=[[5, 3]])), id="start-after-end"),
    pytest.param(_record(_row(removed=[[0, 3]])), id="zero-start"),
    pytest.param(_record(_row(removed=[[True, 3]])), id="bool-start"),
    pytest.param(_record(_row(removed=[[1, True]])), id="bool-end"),
    pytest.param(_record(_row(removed=[["1", 3]])), id="string-start"),
    pytest.param(_record(_row(removed=[[1.0, 3]])), id="float-start"),
    pytest.param(_record(_row(removed=[[1]])), id="short-range"),
    pytest.param(_record(_row(removed=[[10, 14, 15]])), id="long-range"),
    pytest.param(_record(_row(removed=["10-14"])), id="range-not-a-list"),
    pytest.param(_record(_row(removed=None)), id="removed-not-a-list"),
    pytest.param(_record(_row(path="")), id="blank-path"),
    pytest.param(_record(_row(path=None)), id="path-not-a-string"),
    pytest.param(_record(_row(added=None)), id="added-not-a-bool"),
    pytest.param(_record(_row(), "not a row"), id="row-not-a-dict"),
    pytest.param(_record(_row(), _row()), id="path-twice"),
    pytest.param(_record(_row(openings=NO_KEY)), id="openings-absent"),
    pytest.param(_record(_row(openings="12")), id="openings-a-string"),
    pytest.param(_record(_row(openings=12)), id="openings-an-int"),
    pytest.param(_record(_row(openings={"12": True})), id="openings-a-dict"),
    pytest.param(_record(_row(openings=[12, True])), id="openings-holds-a-bool"),
    pytest.param(_record(_row(openings=[0])), id="openings-holds-zero"),
    pytest.param(_record(_row(openings=[-3])), id="openings-holds-a-negative"),
    pytest.param(_record(_row(openings=["12"])), id="openings-holds-a-string"),
    pytest.param(_record(_row(openings=[12.0])), id="openings-holds-a-float"),
    pytest.param(_record(_row(openings=[[12]])), id="openings-holds-a-list"),
])
def test_c2_an_absent_unreadable_or_malformed_removal_record_refuses(record):
    # axis: G3 — C2, the removal record must be readable and well formed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    target = _no_record(_target()) if record == "absent" else _with(record)
    _refused(_fold([_removed()], target), "C2")


# --- C3 -----------------------------------------------------------------------------------------------------------

def test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse():
    # axis: G4 — C3, the removal record and the delta name the same files
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    _refused(_fold([_removed()], _target(record=_record(_row(OTHER_TEST_FILE)))), "C3")
    _refused(_fold([_removed()], _target(record=_record(_row(), _row(OTHER_TEST_FILE)))), "C3")
    _refused(_fold([_removed()], _target(files=(TEST_FILE, OTHER_TEST_FILE))), "C3")


# --- C4 -----------------------------------------------------------------------------------------------------------

def test_c4_a_file_that_added_a_line_refuses():
    # axis: G5 — C4, the fix added nothing
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    reason = _refused(_fold([_removed()], _target(record=_record(_row(added=True)))), "C4")
    assert TEST_FILE in reason


def test_c4_a_file_with_no_removed_range_refuses():
    reason = _refused(_fold([_removed()], _target(record=_record(_row(removed=())))), "C4")
    assert TEST_FILE in reason


# --- C5 -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [
    pytest.param({"dimension": "Code"}, id="wrong-dimension"),
    pytest.param({"dimension": None}, id="no-dimension"),
    pytest.param({"dimension": "test"}, id="dimension-case"),
    pytest.param({"taxonomy": "brittle test"}, id="unknown-taxonomy"),
    pytest.param({"taxonomy": "wording pin extra"}, id="near-taxonomy"),
    pytest.param({"taxonomy": None}, id="no-taxonomy"),
    pytest.param({"taxonomy": 7}, id="taxonomy-not-a-string"),
    pytest.param({"body": "   "}, id="blank-body"),
    pytest.param({"body": None}, id="no-body"),
    pytest.param({"body": ["a reason"]}, id="body-not-a-string"),
])
def test_c5_a_target_that_is_not_a_worthless_test_finding_refuses(change):
    # axis: G6 — C5, the target is a Test finding with a worthless smell and a usable body
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    _refused(_fold([_removed()], _target(**change)), "C5")


# --- C6 -----------------------------------------------------------------------------------------------------------

def test_c6_a_removal_holding_none_of_the_targets_lines_refuses():
    # axis: G7 — C6, one of the target's own cited lines lies in a removed range
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    _refused(_fold([_removed()], _target(line=30)), "C6")
    _refused(_fold([_removed()], _target(file=OTHER_TEST_FILE, line=12)), "C6")


@pytest.mark.parametrize("line", [None, True, "12", 12.0])
def test_c6_a_line_that_is_not_a_plain_integer_cites_nothing(line):
    # a bool is an int to Python: `True` must not tie line 1
    record = _record(_row(removed=((1, 3),)))
    _refused(_fold([_removed()], _target(record=record, line=line)), "C6")


def test_c6_a_siblings_line_does_not_tie_a_removal_the_target_does_not_cite():
    sibling = {"id": "s1", "file": TEST_FILE, "line": 12, "dimension": "Test", "taxonomy": "mock-echo", "body": BODY,
               "citationFresh": True}
    _refused(_fold([_removed()], _target(line=30, batchFindings=[sibling])), "C6")


# --- C7 -----------------------------------------------------------------------------------------------------------

def _two_ranges(openings=(12,)):
    return _record(_row(removed=((10, 14), (30, 34)), openings=openings))


def _sibling(line=31, **over):
    """A qualifying batch sibling: a worthless-test finding whose driver-built `citationFresh` is True."""
    out = {"id": "s1", "file": TEST_FILE, "line": line, "title": "S", "dimension": "Test",
           "taxonomy": "duplicate test", "body": BODY, "citationFresh": True}
    out.update(over)
    for key in [k for k, v in out.items() if v is NO_KEY]:
        del out[key]
    return out


def test_c7_a_removed_range_holding_no_cited_line_refuses():
    # axis: G8 — C7, every removed range holds a cited line
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    reason = _refused(_fold([_removed()], _target(record=_two_ranges())), "C7")
    assert "30-34" in reason and "10-14" not in reason


def test_c7_the_same_range_passes_when_a_worthless_smell_sibling_cites_it():
    outcome = _fold([_removed()], _target(record=_two_ranges((12, 31)), batchFindings=[_sibling()]))
    assert outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["testRemoval"]["evidence"] == {
        "source": "finding", "finding": "t0", "taxonomy": "wording-pin", "reason": BODY,
        "removed": [{"file": TEST_FILE, "ranges": [[10, 14], [30, 34]]}],
        "cited": [{"file": TEST_FILE, "line": 12}, {"file": TEST_FILE, "line": 31}],
        "openings": [{"file": TEST_FILE, "lines": [12, 31]}]}


def test_c7_a_sibling_place_of_its_kind_of_mistake_ties_a_range_too():
    sibling = _sibling(line=1, kindOfMistake={"kind": "k", "places": [{"file": TEST_FILE, "line": 33}]})
    outcome = _fold([_removed()], _target(record=_two_ranges((12, 33)), batchFindings=[sibling]))
    assert outcome["testRemovalCleared"] == ["t0"]


def test_c7_an_uncited_stretch_with_no_test_opening_still_refuses():
    # an uncited helper or fixture opens no test, so C9 has nothing to say about it: C7 is what refuses it
    reason = _refused(_fold([_removed()], _target(record=_two_ranges((12,)))), "C7")
    assert "30-34" in reason


@pytest.mark.parametrize("change", [
    pytest.param({"dimension": "Code"}, id="wrong-dimension"),
    pytest.param({"taxonomy": "brittle test"}, id="unknown-taxonomy"),
    pytest.param({"taxonomy": None}, id="no-taxonomy"),
    pytest.param({"body": " "}, id="blank-body"),
    pytest.param({"file": OTHER_TEST_FILE}, id="other-file"),
])
def test_c7_a_sibling_that_is_not_a_worthless_test_finding_ties_nothing(change):
    _refused(_fold([_removed()], _target(record=_two_ranges(), batchFindings=[_sibling(**change)])), "C7")


def test_c7_a_sibling_that_is_not_a_dict_ties_nothing():
    _refused(_fold([_removed()], _target(record=_two_ranges(), batchFindings=["s1", None])), "C7")


# a sibling's citation counts only when the driver found it fresh too: `citationFresh` exactly True
STALE_SIBLING = [
    pytest.param(False, id="false"),
    pytest.param(NO_KEY, id="absent"),
    pytest.param("yes", id="a-string"),
    pytest.param(1, id="a-truthy-int"),
]


def test_c7_a_fresh_sibling_alone_ties_a_stretch_that_opens_no_test():
    # the healthy twin of the refusals below: the stretch 30-34 opens no test and only the sibling's line 31 ties it
    target = _target(record=_two_ranges((12,)), batchFindings=[_sibling(line=31, citationFresh=True)])
    outcome = _fold([_removed()], target)
    assert outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["testRemoval"]["evidence"]["cited"] == [
        {"file": TEST_FILE, "line": 12}, {"file": TEST_FILE, "line": 31}]


@pytest.mark.parametrize("fresh", STALE_SIBLING)
def test_c7_a_sibling_whose_citation_is_not_exactly_fresh_ties_no_stretch(fresh):
    # axis: G20 — a stale sibling as the only tie of a stretch lends nothing to C7 (the stretch opens no test)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    target = _target(record=_two_ranges((12,)), batchFindings=[_sibling(line=31, citationFresh=fresh)])
    assert target["citationFresh"] is True  # the target's own citation is fresh; only the sibling's line is needed
    reason = _refused(_fold([_removed()], target), "C7")
    assert "30-34" in reason and "10-14" not in reason


def test_c7_a_stale_sibling_does_not_cancel_a_fresh_one_and_lends_nothing_to_the_evidence():
    stale = _sibling(line=12, citationFresh=False, id="s2")  # redundant: the target already cites line 12
    fresh = _sibling(line=31, id="s3")
    outcome = _fold([_removed()], _target(record=_two_ranges((12,)), batchFindings=[stale, fresh]))
    assert outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["testRemoval"]["evidence"]["cited"] == [
        {"file": TEST_FILE, "line": 12}, {"file": TEST_FILE, "line": 31}]
    only_stale = _sibling(line=40, citationFresh=False, id="s4")
    outcome = _fold([_removed()], _target(batchFindings=[only_stale]))
    assert _only(outcome)["testRemoval"]["evidence"]["cited"] == [{"file": TEST_FILE, "line": 12}]


# --- C8 -----------------------------------------------------------------------------------------------------------

def test_c8_a_changed_file_in_an_unsupported_language_refuses_naming_it():
    # axis: G13 — C8, every changed file is in a language the test-opening reader supports
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    only = _target(files=(RB_TEST_FILE,), file=RB_TEST_FILE, record=_record(_row(RB_TEST_FILE, openings=None)))
    assert RB_TEST_FILE in _refused(_fold([_removed()], only), "C8")
    # one supported file beside it does not rescue the unsupported one, even when a sibling cites its stretch
    both = _target(files=(TEST_FILE, RB_TEST_FILE), batchFindings=[_sibling(file=RB_TEST_FILE, line=12)],
                   record=_record(_row(), _row(RB_TEST_FILE, openings=None)))
    assert RB_TEST_FILE in _refused(_fold([_removed()], both), "C8")


# --- C9 -----------------------------------------------------------------------------------------------------------

def test_c9_a_stretch_that_removes_a_cited_test_and_the_uncited_test_after_it_refuses():
    # axis: G14 — C9, every test the base file opens inside a removed stretch opens on a cited line
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    record = _record(_row(removed=((10, 20),), openings=(10, 15)))
    reason = _refused(_fold([_removed()], _target(line=10, record=record)), "C9")
    assert TEST_FILE in reason and "line 15 " in reason


def test_c9_a_whole_file_removal_with_one_cited_test_of_four_refuses():
    record = _record(_row(removed=((1, 20),), openings=(1, 6, 11, 16)))
    reason = _refused(_fold([_removed()], _target(line=6, record=record)), "C9")
    assert TEST_FILE in reason and "line 1 " in reason  # the first uncited opening, in file order


def test_c9_a_sibling_that_is_not_a_worthless_test_finding_cites_no_opening():
    record = _record(_row(removed=((10, 20),), openings=(10, 15)))
    sibling = _sibling(line=15, taxonomy="brittle test")
    assert "line 15 " in _refused(_fold([_removed()], _target(line=10, record=record, batchFindings=[sibling])), "C9")


def test_c9_every_deleted_test_cited_by_the_target_and_a_qualifying_sibling_clears():
    record = _record(_row(removed=((10, 20),), openings=(10, 15)))
    outcome = _fold([_removed()], _target(line=10, record=record, batchFindings=[_sibling(line=15)]))
    assert outcome["testRemovalCleared"] == ["t0"] and outcome["testRemovalRefused"] == []
    evidence = _only(outcome)["testRemoval"]["evidence"]
    assert evidence["cited"] == [{"file": TEST_FILE, "line": 10}, {"file": TEST_FILE, "line": 15}]
    assert evidence["openings"] == [{"file": TEST_FILE, "lines": [10, 15]}]


@pytest.mark.parametrize("fresh", STALE_SIBLING)
def test_c9_a_sibling_whose_citation_is_not_exactly_fresh_cites_no_opening(fresh):
    # axis: G20 — a sibling whose driver-built `citationFresh` is not exactly True lends its cited line to nothing
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    record = _record(_row(removed=((10, 20),), openings=(10, 15)))
    target = _target(line=10, record=record, batchFindings=[_sibling(line=15, citationFresh=fresh)])
    assert target["citationFresh"] is True  # the target's own citation is fresh; only the sibling's line is needed
    assert "line 15 " in _refused(_fold([_removed()], target), "C9")


def test_c9_a_fresh_sibling_counts_beside_a_stale_one_that_cites_another_opening():
    record = _record(_row(removed=((10, 20),), openings=(10, 15, 18)))
    fresh, stale = _sibling(line=15, id="s2"), _sibling(line=18, id="s3", citationFresh=False)
    reason = _refused(_fold([_removed()], _target(line=10, record=record, batchFindings=[fresh, stale])), "C9")
    assert "line 18 " in reason  # the fresh sibling's line 15 is tied; only the stale sibling's line 18 is not
    healed = _fold([_removed()], _target(line=10, record=record, batchFindings=[fresh, dict(stale, citationFresh=True)]))
    assert healed["testRemovalCleared"] == ["t0"]


@pytest.mark.parametrize("removed,openings,line", [
    pytest.param(((10, 14),), (10,), 10, id="first-line"),
    pytest.param(((10, 14),), (14,), 14, id="last-line"),
    pytest.param(((12, 12),), (12,), 12, id="single-line-range"),
    pytest.param(((10, 14),), (9, 12, 15), 12, id="openings-just-outside-the-range-are-not-inside-it"),
])
def test_c9_a_cited_opening_on_a_range_boundary_clears(removed, openings, line):
    outcome = _fold([_removed()], _target(line=line, record=_record(_row(removed=removed, openings=openings))))
    assert outcome["testRemovalCleared"] == ["t0"]
    (rng,) = removed
    inside = [n for n in openings if rng[0] <= n <= rng[1]]
    assert _only(outcome)["testRemoval"]["evidence"]["openings"] == [{"file": TEST_FILE, "lines": inside}]


@pytest.mark.parametrize("openings,uncited", [
    pytest.param((10, 12), 10, id="first-line"),
    pytest.param((12, 14), 14, id="last-line"),
])
def test_c9_an_uncited_opening_on_a_range_boundary_refuses(openings, uncited):
    record = _record(_row(removed=((10, 14),), openings=openings))
    reason = _refused(_fold([_removed()], _target(line=12, record=record)), "C9")
    assert "line %d " % uncited in reason


def test_c9_names_the_file_of_the_uncited_opening():
    record = _record(_row(), _row(OTHER_TEST_FILE, openings=(11, 12)))
    target = _target(files=(TEST_FILE, OTHER_TEST_FILE), record=record,
                     batchFindings=[_sibling(file=OTHER_TEST_FILE, line=12)])
    reason = _refused(_fold([_removed()], target), "C9")
    assert OTHER_TEST_FILE in reason and "line 11 " in reason


# --- C10 ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("fresh", [
    pytest.param(False, id="false"),
    pytest.param(NO_KEY, id="absent"),
    pytest.param("yes", id="a-string"),
    pytest.param(None, id="none"),
    pytest.param(1, id="a-truthy-int"),
])
def test_c10_a_target_whose_citation_is_not_exactly_fresh_refuses(fresh):
    # axis: G15 — C10, `citationFresh` is exactly True
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    reason = _refused(_fold([_removed()], _target(citationFresh=fresh)), "C10")
    assert reason.endswith("C10: the cited lines may have moved since the finding was raised")


def test_c10_is_judged_after_the_conditions_before_it():
    record = _record(_row(removed=((10, 20),), openings=(10, 15)))
    _refused(_fold([_removed()], _target(line=10, record=record, citationFresh=False)), "C9")


# --- the test-opening reader --------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    pytest.param("def test_a():\n    pass\n", [1], id="def-test"),
    pytest.param("import x\n\nasync def test_b(client):\n    pass\n", [3], id="async-def-test"),
    pytest.param("class TestX:\n    def test_m(self):\n        pass\n", [1, 2], id="class-and-method"),
    pytest.param("class Test:\n    pass\n", [1], id="class-test-alone"),
    pytest.param("\tdef test_tab(self):\n", [1], id="tab-indented"),
    pytest.param("def  test_spaced (x):\n", [1], id="spaces-around-the-name"),
    pytest.param("def test_a():\r\n    pass\r\n", [1], id="crlf"),
    pytest.param("def helper():\n    pass\n", [], id="def-helper-is-no-opening"),
    pytest.param("class Helper:\n    pass\n", [], id="class-helper-is-no-opening"),
    pytest.param("x = 'def test_x():'\n", [], id="a-def-inside-a-string-at-column-above-zero"),
    pytest.param("def test_x\n", [], id="no-opening-parenthesis"),
    pytest.param("def Test_x():\n", [], id="the-case-matters"),
    pytest.param("@pytest.mark.parametrize('a', [1])\ndef helper_test(a):\n", [], id="decorator-and-a-helper-named-test-last"),
    # the reader matches a line, not a parse: these look like openings and count as openings (the safe direction)
    pytest.param("def testify(x):\n", [1], id="a-name-that-begins-with-test-counts"),
    pytest.param('"""\n    def test_in_a_docstring(self):\n"""\n', [2], id="an-indented-def-inside-a-docstring-counts"),
])
def test_o_the_python_reader_reads_def_test_and_class_test_lines(text, expected):
    # axis: G17 — the Python reader names the lines that open a test
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    assert audits.test_openings("tests/test_a.py", text) == expected


@pytest.mark.parametrize("text,expected", [
    pytest.param("it('adds', () => {\n});\n", [1], id="it"),
    pytest.param("describe('suite', () => {\n  test('a', () => {});\n  it.each([1])('b', () => {});\n});\n",
                 [1, 2, 3], id="describe-test-it-each"),
    pytest.param("  test.only('x', () => {});\n", [1], id="test-only"),
    pytest.param("test.skip.each([1])('x', () => {});\n", [1], id="test-skip-each"),
    pytest.param("describe.each([[1, 2]])('adds %i', (a) => {});\n", [1], id="describe-each-call"),
    pytest.param("test ('spaced', () => {});\n", [1], id="space-before-the-parenthesis"),
    pytest.param("const t = test\n", [], id="a-test-alias-is-no-opening"),
    pytest.param("item('x');\ntesting('y');\nxit('z');\nexpect(a).toBe(1);\n", [], id="longer-names-are-no-opening"),
    pytest.param("  await it('x');\n", [], id="not-at-the-start-of-the-line"),
    pytest.param("test.each`table`('x', () => {});\n", [], id="a-template-call-is-not-read"),
])
def test_o_the_js_reader_reads_it_test_and_describe_calls(text, expected):
    # axis: G18 — the JavaScript and TypeScript reader names the lines that open a test
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    assert audits.test_openings("tests/a.test.js", text) == expected


@pytest.mark.parametrize("path", ["a.py", "a.PY", "dir/b.test.js", "a.jsx", "a.mjs", "a.cjs", "a.ts", "a.tsx",
                                  "a.mts", "a.cts", "A.TS"])
def test_o_every_supported_extension_has_a_reader(path):
    extensions = audits.PYTHON_TEST_EXTENSIONS | audits.JS_TEST_EXTENSIONS
    assert path[path.rindex("."):].lower() in extensions
    assert audits.test_openings(path, "x\n") == []


@pytest.mark.parametrize("path", ["a.rb", "a.go", "a.java", "a.rs", "a.pyc", "a.json", "a", "Makefile", "", "dir.py/x"])
def test_o_any_other_extension_has_no_reader(path):
    assert audits.test_openings(path, "def test_a():\nit('x', () => {})\n") is None


def test_o_the_extension_sets_are_the_ones_the_reader_documents():
    assert audits.PYTHON_TEST_EXTENSIONS == {".py"}
    assert audits.JS_TEST_EXTENSIONS == {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}


def test_o_lines_are_cut_at_newlines_only_as_git_counts_them():
    # a form feed or a line separator does not start a new line for git, so it must not for the reader either
    text = "a = '\x0c\x0b\x1c\x85" + chr(0x2028) + "'\ndef test_a():\n    pass\n"
    assert audits.test_openings("t.py", text) == [2]


# --- the neighbouring answers and rulings ---------------------------------------------------------------------------

def test_g_review_guarded_on_a_test_only_delta_refuses_exactly_as_before():
    result = _removed(checks=_checks(testWouldFail=audits.REVIEW_GUARDED))
    outcome = _fold([result], _target())
    entry = _only(outcome)
    assert outcome["notDischarged"] == ["t0"] and outcome["reviewGuardRefused"] == ["t0"]
    assert outcome["testRemovalRefused"] == [] and outcome["testRemovalCleared"] == []
    assert entry["reason"] == ("audit check failed: testWouldFail: review-guarded clears only a fix whose whole "
                               "delta is prose; this fix's delta touches %s" % TEST_FILE)


def test_g_review_guarded_on_a_prose_delta_still_clears_without_a_removal_record():
    result = _removed(checks=_checks(testWouldFail=audits.REVIEW_GUARDED))
    target = _no_record(_target(files=(RUBRIC_MD,)))
    outcome = _fold([result], target)
    assert outcome["reviewGuarded"] == ["t0"] and outcome["testRemovalCleared"] == []
    assert "testRemoval" not in _only(outcome)


def test_g_the_removal_answer_on_a_prose_only_delta_refuses_as_c1():
    outcome = _fold([_removed()], _target(files=(RUBRIC_MD,), record=_record(_row(RUBRIC_MD))))
    assert RUBRIC_MD in _refused(outcome, "C1")
    assert outcome["reviewGuardRefused"] == [] and outcome["reviewGuarded"] == []


@pytest.mark.parametrize("name", ["right", "brokeNothing"])
def test_g_the_removal_answer_is_a_fault_on_any_check_but_test_would_fail(name):
    result = _removed(checks=_checks(**{name: audits.WORTHLESS_TEST_REMOVED}))
    fault = audits.audit_checks_fault(result)
    assert fault is not None and "checks.%s" % name in fault and audits.WORTHLESS_TEST_REMOVED in fault, fault
    outcome = _fold([result], _target())
    assert outcome["malformed"] == ["t0"] and outcome["notDischarged"] == ["t0"]
    assert outcome["discharged"] == [] and outcome["testRemovalCleared"] == [] and outcome["testRemovalRefused"] == []
    assert _only(outcome)["reason"] == "audit refused: %s" % fault


def test_g_each_check_has_its_own_answer_set():
    assert audits.check_answers("right") == audits.CHECK_ANSWERS
    assert audits.check_answers("brokeNothing") == audits.CHECK_ANSWERS
    assert audits.check_answers("testWouldFail") == audits.CHECK_ANSWERS + (
        audits.REVIEW_GUARDED, audits.WORTHLESS_TEST_REMOVED)
    assert audits.audit_checks_fault(_removed()) is None


def test_g_a_not_discharged_ruling_with_the_answer_is_accepted_as_is_and_listed_nowhere():
    outcome = _fold([_removed(ruling="not-discharged", reason="still wrong")], _no_record(_target(files=(LIB_PY,))))
    assert outcome["notDischarged"] == ["t0"] and outcome["malformed"] == []
    assert outcome["testRemovalRefused"] == [] and outcome["testRemovalCleared"] == []
    assert _only(outcome)["reason"] == "still wrong"


def test_g_a_no_on_another_check_wins_over_the_removal_answer():
    result = _removed(checks=_checks(right="no", testWouldFail=audits.WORTHLESS_TEST_REMOVED))
    outcome = _fold([result], _target())
    assert outcome["notDischarged"] == ["t0"] and outcome["testRemovalCleared"] == []
    assert outcome["testRemovalRefused"] == []
    assert _only(outcome)["reason"] == "audit check failed: right: checked: right"


def test_g_a_yes_answer_clears_whatever_the_record_says():
    outcome = _fold([_removed(checks=_checks())], _no_record(_target(files=(LIB_PY,))))
    assert outcome["discharged"] == ["t0"] and outcome["testRemovalCleared"] == []
    assert outcome["testRemovalRefused"] == [] and "testRemoval" not in _only(outcome)


def test_g_an_id_refused_later_in_the_same_pass_is_not_listed_as_cleared():
    outcome = _fold([_removed(unnamedChange="also reworks the retry policy")], _target())
    entry = _only(outcome)
    assert outcome["unnamedChange"] == ["t0"] and outcome["notDischarged"] == ["t0"]
    assert outcome["testRemovalCleared"] == [] and "testRemoval" not in entry
    outcome = _fold([_removed(unnamedChange=7)], _target())
    assert outcome["malformed"] == ["t0"] and outcome["testRemovalCleared"] == []
    assert "testRemoval" not in _only(outcome)


def test_g_a_clear_does_not_leak_to_the_next_target():
    clearing, plain = _target(), dict(_target(id="t1"), fixerRemoval=None)
    results = [_removed(), dict(_removed(id="t1"), checks=_checks())]
    outcome = audits.apply_audit_results([clearing, plain], results, collection_manifest={"t0": "codex", "t1": "codex"})
    first, second = outcome["audits"]
    assert "testRemoval" in first and "testRemoval" not in second
    assert outcome["testRemovalCleared"] == ["t0"]


# --- the strict-mode schema ----------------------------------------------------------------------------------------

def _find_key(node, key):
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


def test_s_the_strict_schema_lists_the_answers_for_test_would_fail_only():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, "ruling")
    for name in audits.CHECK_NAMES:
        entry = _find_key(schema, name)
        assert entry is not None, name
        assert entry["properties"]["answer"]["enum"] == list(audits.check_answers(name))
    enum = _find_key(schema, "testWouldFail")["properties"]["answer"]["enum"]
    assert enum == list(audits.check_answers("testWouldFail")) and audits.WORTHLESS_TEST_REMOVED in enum
    for name in ("right", "brokeNothing"):
        assert audits.WORTHLESS_TEST_REMOVED not in _find_key(schema, name)["properties"]["answer"]["enum"]


# --- the removal record, from real git ----------------------------------------------------------------------------

_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]  # a throwaway fixture repo
LINES = "".join("l%d\n" % n for n in range(1, 9))
TFILE = "tests/test_a.py"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _write(repo, name, body):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        path.write_bytes(body)
    else:
        path.write_text(body, encoding="utf-8")


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *(_ID + ["commit", "-q", "-m", message]))
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path, files=None):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for name, body in (files or {TFILE: LINES}).items():
        _write(repo, name, body)
    return repo, _commit(repo, "base")


def _removal(repo, base, head):
    return RD._fixer_removal({"repoRoot": str(repo)}, base, head)


def _files(record):
    return {f["path"]: (f["removed"], f["added"]) for f in record["files"]}


def test_r_a_pure_removal_reads_the_removed_ranges_and_adds_nothing(tmp_path):
    repo, base = _repo(tmp_path, {TFILE: LINES, "tests/test_gone.py": "a\nb\nc\n"})
    _write(repo, TFILE, "l1\nl2\nl5\nl6\nl8\n")
    (repo / "tests" / "test_gone.py").unlink()
    head = _commit(repo, "remove")
    record = _removal(repo, base, head)
    assert "unreadable" not in record and record["base"] == base and record["head"] == head
    assert _files(record) == {TFILE: ([[3, 4], [7, 7]], False), "tests/test_gone.py": ([[1, 3]], False)}


def test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to(tmp_path):
    # axis: G9 — a hunk that adds a line marks its file `added`
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, base = _repo(tmp_path)
    _write(repo, TFILE, LINES.replace("l2\n", "changed\n"))
    _write(repo, "tests/test_new.py", "x\ny\n")
    head = _commit(repo, "edit")
    assert _files(_removal(repo, base, head)) == {TFILE: ([[2, 2]], True), "tests/test_new.py": ([], True)}


def test_r_a_binary_file_makes_the_whole_record_unreadable(tmp_path):
    # axis: G10 — a binary file makes the whole record unreadable
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, base = _repo(tmp_path, {TFILE: LINES, "tests/blob.bin": b"\x00\x01\x02"})
    _write(repo, TFILE, "l1\n")
    _write(repo, "tests/blob.bin", b"\x00\x01\x03\x04")
    head = _commit(repo, "edit")
    record = _removal(repo, base, head)
    assert "unreadable" in record and "files" not in record
    assert record["base"] == base and record["head"] == head


@pytest.mark.parametrize("base,head", [
    pytest.param(BAD_BASE, "HEAD", id="base-unknown"),
    pytest.param("HEAD", BAD_BASE, id="head-unknown"),
    pytest.param(None, "HEAD", id="base-none"),
    pytest.param("HEAD", None, id="head-none"),
    pytest.param("", "HEAD", id="base-blank"),
    pytest.param("HEAD", "", id="head-blank"),
    pytest.param("-p", "HEAD", id="base-option"),
])
def test_r_a_missing_base_or_head_is_unreadable_and_never_raises(tmp_path, base, head):
    # axis: G10 (grouped) — a missing or unresolvable base or head makes the whole record unreadable
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, _ = _repo(tmp_path)
    record = _removal(repo, base, head)
    assert "unreadable" in record and "files" not in record


def test_r_no_repository_is_unreadable_and_never_raises():
    for config in (None, {}, {"repoRoot": ""}, {"repoRoot": 7}):
        assert "unreadable" in RD._fixer_removal(config, "a" * 40, "b" * 40)


def _fake_git(diff_bytes, resolved=b"c" * 40 + b"\n", blob=b""):
    def fake(repo_root, *args):
        if args[0] == "cat-file":
            return blob
        return resolved if args[0] == "rev-parse" else diff_bytes
    return fake


@pytest.mark.parametrize("diff", [
    pytest.param(b"diff --git a/x.py b/y.py\n--- a/x.py\n+++ b/y.py\n@@ -1 +1 @@\n-a\n+b\n", id="two-path-header"),
    pytest.param(b'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n@@ -1 +0,0 @@\n-a\n', id="quoted-header"),
    pytest.param(b"diff --git a/x.py b/x.py\nBinary files a/x.py and b/x.py differ\n", id="binary-files-line"),
    pytest.param(b"diff --git a/x.py b/x.py\nGIT binary patch\nliteral 3\nIcmZQz\n", id="git-binary-patch"),
    pytest.param(b"diff --git a/x.py b/x.py\n@@ -1 +0,0 @@\n-\xff\n", id="not-utf8"),
    pytest.param(b"diff --git a/x.py b/x.py\n@@ nonsense @@\n", id="unreadable-hunk-header"),
    pytest.param(b"@@ -1 +0,0 @@\n-a\n", id="hunk-before-any-header"),
    pytest.param(b"diff --git a/x.py b/x.py\n@@ -1 +0,0 @@\n-a\ndiff --git a/x.py b/x.py\n@@ -1 +0,0 @@\n-a\n",
                 id="path-twice"),
    pytest.param(None, id="git-diff-failed"),
])
def test_r_every_unreadable_form_makes_the_whole_record_unreadable(monkeypatch, diff):
    # axis: G10 — the unreadable forms of the diff make the whole record unreadable
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    monkeypatch.setattr(RD, "_git_bytes", _fake_git(diff))
    record = RD._fixer_removal({"repoRoot": "/r"}, "a" * 40, "b" * 40)
    assert "unreadable" in record and "files" not in record
    assert record["base"] == "a" * 40 and record["head"] == "b" * 40


def test_r_a_clean_fake_diff_reads_and_an_empty_diff_names_no_file(monkeypatch):
    clean = b"diff --git a/t.py b/t.py\nindex 1..2 100644\n--- a/t.py\n+++ b/t.py\n@@ -4,2 +3,0 @@\n-a\n-b\n"
    monkeypatch.setattr(RD, "_git_bytes", _fake_git(clean))
    assert RD._fixer_removal({"repoRoot": "/r"}, "a" * 40, "b" * 40) == {
        "base": "c" * 40, "head": "c" * 40,
        "files": [{"path": "t.py", "removed": [[4, 5]], "added": False, "testOpenings": []}]}
    monkeypatch.setattr(RD, "_git_bytes", _fake_git(b""))
    assert RD._fixer_removal({"repoRoot": "/r"}, "a" * 40, "b" * 40)["files"] == []


def test_r_the_diff_is_asked_for_in_the_raw_pinned_form(monkeypatch):
    calls = []

    def fake(repo_root, *args):
        calls.append(args)
        return b"c" * 40 + b"\n" if args[0] == "rev-parse" else b""

    monkeypatch.setattr(RD, "_git_bytes", fake)
    RD._fixer_removal({"repoRoot": "/r"}, "base", "head")
    (diff,) = [c for c in calls if c[0] == "diff"]
    assert diff == ("diff", "--no-ext-diff", "--no-textconv", "--no-color", "--src-prefix=a/", "--dst-prefix=b/",
                    "--no-renames", "--unified=0", "--inter-hunk-context=0", "c" * 40, "c" * 40)
    assert [c[3] for c in calls if c[0] == "rev-parse"] == ["base^{commit}", "head^{commit}"]


def test_r_a_configured_textconv_never_hides_an_added_line(tmp_path):
    # axis: G11 — `--no-textconv`: a configured textconv never shapes the record
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, _ = _repo(tmp_path, {".gitattributes": "*.txt diff=hide\n", "tests/test_a.txt": "one\ntwo\n"})
    _git(repo, "config", "diff.hide.textconv", "true")
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, "tests/test_a.txt", "one\ntwo\nadded\n")
    head = _commit(repo, "add")
    assert "added" not in _git(repo, "diff", "--no-ext-diff", base, head)  # the setting does hide it from a plain diff
    assert _files(_removal(repo, base, head)) == {"tests/test_a.txt": ([], True)}


def test_r_the_record_describes_the_explicit_head_not_the_checkout(tmp_path):
    # axis: G12 — the explicit head commit: the record describes `base..head`, never the live checkout HEAD
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, base = _repo(tmp_path, {TFILE: "a\nb\nc\n"})
    _write(repo, TFILE, "a\nb\nc\nd\n")
    audited = _commit(repo, "the audited head adds a line")
    _write(repo, TFILE, "b\nc\n")
    checkout = _commit(repo, "a later deletion-only commit")
    assert _git(repo, "rev-parse", "HEAD") == checkout
    record = _removal(repo, base, audited)
    assert record["head"] == audited and record["head"] != checkout
    assert _files(record) == {TFILE: ([], True)}
    assert _files(_removal(repo, base, checkout)) == {TFILE: ([[1, 1]], False)}


def test_r_a_real_record_clears_through_the_fold(tmp_path):
    repo, base = _repo(tmp_path, {TFILE: LINES})
    _write(repo, TFILE, "l1\nl2\nl6\nl7\nl8\n")
    head = _commit(repo, "remove a test")
    record = _removal(repo, base, head)
    assert _files(record) == {TFILE: ([[3, 5]], False)}
    outcome = _fold([_removed()], _target(files=(TFILE,), record=record, file=TFILE, line=4))
    assert outcome["testRemovalCleared"] == ["t0"]
    assert _only(outcome)["testRemoval"]["evidence"]["openings"] == [{"file": TFILE, "lines": []}]


def test_r_two_deletions_with_a_kept_line_between_them_stay_two_ranges_whatever_git_is_configured_to(tmp_path):
    # axis: G16 — `--inter-hunk-context=0`: a configured `diff.interHunkContext` never merges two ranges into one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, base = _repo(tmp_path)
    _git(repo, "config", "diff.interHunkContext", "1")
    _write(repo, TFILE, "l1\nl3\nl5\nl6\nl7\nl8\n")  # old lines 2 and 4 deleted, old line 3 kept
    head = _commit(repo, "delete lines 2 and 4")
    plain = _git(repo, "diff", "--no-ext-diff", "--unified=0", base, head)
    assert len([ln for ln in plain.splitlines() if ln.startswith("@@ ")]) == 1  # the setting does merge a plain diff
    assert _files(_removal(repo, base, head)) == {TFILE: ([[2, 2], [4, 4]], False)}


def test_r_the_test_openings_come_from_the_base_blob_of_each_file_with_a_removed_range(tmp_path):
    # `testOpenings` is the base file's openings, not the head file's
    py_base = ("import x\n\ndef test_a():\n    pass\n\nasync def test_b():\n    pass\n\nclass TestC:\n"
               "    def test_m(self):\n        pass\n")
    repo, base = _repo(tmp_path, {TFILE: py_base, "tests/a.test.js": "it('a', () => {\n});\n",
                                  "tests/test_spec.rb": "x\ny\n", "tests/test_keep.py": "def test_keep():\n    pass\n"})
    _write(repo, TFILE, "import x\n\nasync def test_b():\n    pass\n\nclass TestC:\n    def test_m(self):\n        pass\n")
    (repo / "tests" / "a.test.js").unlink()
    _write(repo, "tests/test_spec.rb", "x\n")
    _write(repo, "tests/test_new.py", "def test_new():\n    pass\n")  # added to only: no removed range
    head = _commit(repo, "remove")
    record = _removal(repo, base, head)
    rows = {f["path"]: f for f in record["files"]}
    assert rows[TFILE]["testOpenings"] == [3, 6, 9, 10]  # the base file's lines, test_a included
    assert rows["tests/a.test.js"]["testOpenings"] == [1]
    assert rows["tests/test_spec.rb"]["testOpenings"] is None  # no reader for the language
    assert rows["tests/test_new.py"] == {"path": "tests/test_new.py", "removed": [], "added": True, "testOpenings": []}
    assert "tests/test_keep.py" not in rows


def test_r_a_base_blob_that_is_not_utf8_makes_the_whole_record_unreadable(tmp_path):
    # axis: G19 — a base file that cannot be read as UTF-8 text makes the whole record unreadable
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, base = _repo(tmp_path, {TFILE: b"\xff\nl2\nl3\n"})
    _write(repo, TFILE, b"\xff\nl2\n")  # the removed line is text: the diff itself reads, the base blob does not
    head = _commit(repo, "remove")
    record = _removal(repo, base, head)
    assert "unreadable" in record and "files" not in record
    assert record["base"] == base and record["head"] == head


def test_r_a_base_blob_that_cannot_be_read_makes_the_whole_record_unreadable(monkeypatch):
    diff = b"diff --git a/t.py b/t.py\n--- a/t.py\n+++ b/t.py\n@@ -4,2 +3,0 @@\n-a\n-b\n"
    monkeypatch.setattr(RD, "_git_bytes", _fake_git(diff, blob=b"def test_a():\n"))
    assert "unreadable" not in RD._fixer_removal({"repoRoot": "/r"}, "a" * 40, "b" * 40)
    monkeypatch.setattr(RD, "_git_bytes", _fake_git(diff, blob=None))
    record = RD._fixer_removal({"repoRoot": "/r"}, "a" * 40, "b" * 40)
    assert "unreadable" in record and "files" not in record
    assert record["base"] == "a" * 40 and record["head"] == "b" * 40


def test_r_the_base_blob_is_read_at_the_resolved_base_commit_and_path(monkeypatch):
    calls = []

    def fake(repo_root, *args):
        calls.append(args)
        if args[0] == "cat-file":
            return b"def test_a():\n"
        return b"c" * 40 + b"\n" if args[0] == "rev-parse" else (
            b"diff --git a/t.py b/t.py\n@@ -1 +0,0 @@\n-x\ndiff --git a/n.py b/n.py\n@@ -0,0 +1 @@\n+y\n")

    monkeypatch.setattr(RD, "_git_bytes", fake)
    record = RD._fixer_removal({"repoRoot": "/r"}, "base", "head")
    assert [c for c in calls if c[0] == "cat-file"] == [("cat-file", "blob", "c" * 40 + ":t.py")]  # not for n.py
    assert [f["testOpenings"] for f in record["files"]] == [[1], []]


# --- the review record and the audit targets ----------------------------------------------------------------------

def _fixed_row(receipt, **over):
    # an unmerged finding is its own representative: the row that decides carries the disposition itself
    own = {"file": TEST_FILE, "line": 12, "title": "T", SC.RAISED_SEQ_FIELD: 1, "disposition": "fixed",
           "dispositionRound": 3, "dispositionReceipt": receipt, SC.DISPOSITION_SEQ_FIELD: 2}
    own.update(over)
    return own, {SC.finding_identity_key(own): own}


def test_d_a_fixed_row_cleared_as_a_removal_names_its_evidence_in_the_review_record():
    outcome = _fold([_removed()], _target(record=_two_ranges(), batchFindings=[_sibling()]))
    receipt = {"headSha": "h", "testRemoval": _only(outcome)["testRemoval"]}
    own, by_key = _fixed_row(receipt)
    result, reason, _rep = RS._decide(own, by_key, {})
    assert result == RS._FIXED
    assert reason == ("fixed and audited in round 3; cleared as the removal of a worthless test: wording-pin "
                      "finding t0, removed %s lines 10-14, %s lines 30-34" % (TEST_FILE, TEST_FILE))


def test_d_an_ordinary_fixed_row_keeps_its_reason():
    for receipt in ({"headSha": "h"}, {}, {"testRemoval": "not a dict"}, {"testRemoval": {"answer": "x"}}):
        own, by_key = _fixed_row(receipt)
        assert RS._decide(own, by_key, {})[:2] == (RS._FIXED, "fixed and audited in round 3")


def test_d_the_full_panel_receipt_keeps_its_precedence():
    receipt = {"kind": SC.FULL_PANEL_NOT_RERAISED, "panelRound": 4, "testRemoval": {"evidence": {}}}
    own, by_key = _fixed_row(receipt)
    assert RS._decide(own, by_key, {})[1] == "fixed; the full panel in round 4 did not raise it again"


def _finding(title, line, **extra):
    out = {"file": TEST_FILE, "line": line, "title": title, "severity": "Important"}
    out.update(extra)
    return out


def test_w_every_audit_target_carries_the_removal_record_and_siblings_their_smell():
    state = RD.new_state(TRD._cfg(fixerVendor="claude"))
    state["fixBatch"] = [_finding("A", 3, dimension="Test", taxonomy="mock-echo", body=BODY),
                         _finding("B", 9, dimension="Test", taxonomy="cannot-fail", body=BODY),
                         _finding("C", 20)]
    rows = RD._audit_targets(state, state["config"], {})
    assert len(rows) == 3
    for row in rows:
        assert "unreadable" in row["fixerRemoval"]  # no base or head given: the fold fails closed
        assert row["citationFresh"] is False  # and no head to compare the cited lines at
        assert row["citationCheck"] == {"raisedHead": None, "base": None, "files": [TEST_FILE]}
    first = rows[0]
    siblings = {s["id"]: s for s in first["batchFindings"]}
    assert [s["title"] for s in first["batchFindings"]] == ["B", "C"]
    (b,) = [s for s in first["batchFindings"] if s["title"] == "B"]
    (c,) = [s for s in first["batchFindings"] if s["title"] == "C"]
    assert (b["dimension"], b["taxonomy"], b["body"]) == ("Test", "cannot-fail", BODY)
    assert "dimension" not in c and "taxonomy" not in c and len(siblings) == 2


def test_w_the_record_is_built_from_the_given_base_and_head(tmp_path):
    repo, base = _repo(tmp_path)
    _write(repo, TFILE, "l1\nl2\nl5\nl6\nl7\nl8\n")
    head = _commit(repo, "remove")
    state = RD.new_state(TRD._cfg(fixerVendor="claude", repoRoot=str(repo)))
    state["fixBatch"] = [_finding("A", 3), _finding("B", 4)]
    rows = RD._audit_targets(state, state["config"], {}, removal_base=base, removal_head=head)
    assert len(rows) == 2
    for row in rows:
        assert row["fixerRemoval"] == {"base": base, "head": head, "files": [
            {"path": TFILE, "removed": [[3, 4]], "added": False, "testOpenings": []}]}
    assert rows[0]["fixerRemoval"] is not rows[1]["fixerRemoval"]


def test_w_the_attempt_start_head_is_recorded_by_the_first_slice_only(tmp_path):
    repo, first = _repo(tmp_path)
    state = RD.new_state(TRD._cfg(fixerVendor="claude", repoRoot=str(repo)))
    state["_fixBatch"] = []
    rows = [_finding("A", 3, severity="Blocker")]
    assert RD._queue_fix_batch(state, state["config"], rows) == "queued"
    assert state["_fixStepHead"] == first and state["_fixAttemptStartHead"] == first
    _write(repo, TFILE, "l1\n")
    second = _commit(repo, "slice one's fix")
    assert RD._queue_fix_batch(state, state["config"], [_finding("B", 4, severity="Blocker")],
                               reset_accumulator=False, batch_index=1) == "queued"
    assert state["_fixStepHead"] == second and state["_fixAttemptStartHead"] == first


# --- citation freshness -------------------------------------------------------------------------------------------

OTHER = "tests/other.py"


def _stage(tmp_path, between=None, remove=None):
    """A throwaway repo with the raised head, then (when `between` writes files) a fix start head after it, then
    the fix's removal head (`remove` writes files, else it empties `tests/other.py`). Returns `(repo, raised,
    base, head)`; with nothing between, base IS the raised head."""
    tmp_path.mkdir(exist_ok=True)
    repo, raised = _repo(tmp_path, {TFILE: LINES, OTHER: "x\n"})
    base = raised
    if between:
        for name, body in between.items():
            _write(repo, name, body)
        base = _commit(repo, "between the raised head and the fix start")
    for name, body in (remove or {OTHER: ""}).items():
        _write(repo, name, body)
    return repo, raised, base, _commit(repo, "the fix")


def _targets(repo, raised, base, head, findings, rounds=None, **config):
    state = RD.new_state(TRD._cfg(fixerVendor="claude", repoRoot=str(repo), **config))
    state["config"]["headSha"] = raised
    state["rounds"].update(rounds or {})
    state["fixBatch"] = findings
    return RD._audit_targets(state, state["config"], {}, removal_base=base, removal_head=head)


def _raised(round_no, line=3, **extra):
    return _finding("A", line, file=TFILE, **{SC.RAISED_ROUND_FIELD: round_no}, **extra)


def test_f_a_cited_file_unchanged_between_the_raised_head_and_the_base_is_fresh(tmp_path):
    # a cited file that did not change between the raised head and the base keeps its citation fresh
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    assert raised != base
    (row,) = _targets(repo, raised, base, head, [_raised(1)])
    assert row["citationFresh"] is True
    assert row["citationCheck"] == {"raisedHead": raised, "base": base, "files": [TFILE]}


def test_f_a_cited_file_changed_between_the_raised_head_and_the_base_is_stale(tmp_path):
    # axis: G23 — a cited file that changed between the raised head and the base makes the citation stale
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, raised, base, head = _stage(tmp_path, {TFILE: "new first line\n" + LINES})
    (row,) = _targets(repo, raised, base, head, [_raised(1)])
    assert row["citationFresh"] is False
    assert row["citationCheck"] == {"raisedHead": raised, "base": base, "files": [TFILE]}


def test_f_a_place_of_the_kind_of_mistake_in_a_changed_file_makes_the_citation_stale(tmp_path):
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    kind = {"kind": "k", "places": [{"file": OTHER, "line": 1}, {"file": TFILE, "line": 5}]}
    (row,) = _targets(repo, raised, base, head, [_raised(1, kindOfMistake=kind)])
    assert row["citationFresh"] is False
    assert row["citationCheck"]["files"] == [TFILE, OTHER]


def test_f_equal_heads_are_fresh_without_asking_git_for_a_diff(tmp_path, monkeypatch):
    repo, raised, base, head = _stage(tmp_path)
    assert raised == base
    asked = []
    original = RD._git_bytes
    monkeypatch.setattr(RD, "_git_bytes", lambda root, *args: asked.append(args) or original(root, *args))
    (row,) = _targets(repo, raised, base, head, [_raised(1)])
    assert row["citationFresh"] is True
    assert not [a for a in asked if a[:4] == ("diff", "--no-ext-diff", "--no-textconv", "--quiet")]


def test_f_unequal_heads_are_compared_over_the_cited_files_only(tmp_path, monkeypatch):
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    asked = []
    original = RD._git_bytes
    monkeypatch.setattr(RD, "_git_bytes", lambda root, *args: asked.append(args) or original(root, *args))
    _targets(repo, raised, base, head, [_raised(1)])
    assert [a for a in asked if a[:4] == ("diff", "--no-ext-diff", "--no-textconv", "--quiet")] == [
        ("diff", "--no-ext-diff", "--no-textconv", "--quiet", raised, base, "--", TFILE)]


def test_f_equal_heads_with_no_cited_file_are_not_fresh(tmp_path):
    # axis: G22 — a target that cites no file is never fresh, even when the heads are equal
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, raised, base, head = _stage(tmp_path)
    assert raised == base
    (row,) = _targets(repo, raised, base, head, [_finding("A", None, file=None, **{SC.RAISED_ROUND_FIELD: 1})])
    assert row["citationFresh"] is False
    assert row["citationCheck"] == {"raisedHead": raised, "base": base, "files": []}


def test_f_a_later_rounds_finding_is_judged_from_the_previous_rounds_fix_fold_head(tmp_path):
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    # round 2: the session-setup head is deliberately unresolvable, so reading it would give False
    (row,) = _targets(repo, "f" * 40, base, head, [_raised(2)], rounds={"1": {"fixFoldHead": raised}})
    assert row["citationFresh"] is True and row["citationCheck"]["raisedHead"] == raised
    # round 1: the round-1 fold head is deliberately unresolvable, so reading it would give False
    (row,) = _targets(repo, raised, base, head, [_raised(1)], rounds={"1": {"fixFoldHead": "f" * 40}})
    assert row["citationFresh"] is True and row["citationCheck"]["raisedHead"] == raised


@pytest.mark.parametrize("round_no,rounds,setup", [
    pytest.param(NO_KEY, {}, True, id="no-raised-round"),
    pytest.param(0, {}, True, id="round-zero"),
    pytest.param(True, {}, True, id="round-is-a-bool"),
    pytest.param("1", {}, True, id="round-is-a-string"),
    pytest.param(None, {}, True, id="round-is-none"),
    pytest.param(1, {}, False, id="round-1-with-no-setup-head"),
    pytest.param(2, {}, True, id="round-2-with-no-recorded-head"),
    pytest.param(2, {"1": {}}, True, id="round-2-with-a-blank-record"),
    pytest.param(2, {"1": {"fixFoldHead": ""}}, True, id="round-2-with-an-empty-head"),
    pytest.param(2, {"1": {"fixFoldHead": "0" * 40}}, True, id="round-2-with-an-unresolvable-head"),
    pytest.param(1, {}, "0" * 40, id="round-1-with-an-unresolvable-setup-head"),
])
def test_f_a_finding_with_no_usable_raised_head_is_not_fresh(tmp_path, round_no, rounds, setup):
    repo, raised, base, head = _stage(tmp_path)
    finding = _raised(1)
    if round_no is NO_KEY:
        del finding[SC.RAISED_ROUND_FIELD]
    else:
        finding[SC.RAISED_ROUND_FIELD] = round_no
    state = RD.new_state(TRD._cfg(fixerVendor="claude", repoRoot=str(repo)))
    if setup is True:
        state["config"]["headSha"] = raised
    elif setup:
        state["config"]["headSha"] = setup
    state["rounds"].update(rounds)
    state["fixBatch"] = [finding]
    (row,) = RD._audit_targets(state, state["config"], {}, removal_base=base, removal_head=head)
    assert row["citationFresh"] is False and row["citationCheck"]["files"] == [TFILE]


def test_f_a_finding_carried_from_an_earlier_session_has_no_removal_head_and_is_not_fresh(tmp_path):
    # axis: G21 — a target with no removal head is never fresh, even when the heads are equal and resolve
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_test_removal_2434.md
    repo, raised, base, _head = _stage(tmp_path)
    (row,) = _targets(repo, raised, base, None, [_raised(1)])
    assert row["citationFresh"] is False and "unreadable" in row["fixerRemoval"]


@pytest.mark.parametrize("base", [None, "", "-p", "0" * 40])
def test_f_a_removal_base_that_does_not_resolve_is_not_fresh(tmp_path, base):
    repo, raised, _base, head = _stage(tmp_path)
    (row,) = _targets(repo, raised, base, head, [_raised(1)])
    assert row["citationFresh"] is False and row["citationCheck"]["base"] is None


def test_f_no_repository_is_not_fresh(tmp_path):
    repo, raised, base, head = _stage(tmp_path)
    state = RD.new_state(TRD._cfg(fixerVendor="claude"))
    state["config"]["headSha"] = raised
    state["fixBatch"] = [_raised(1)]
    (row,) = RD._audit_targets(state, state["config"], {}, removal_base=base, removal_head=head)
    assert row["citationFresh"] is False


def test_f_a_git_failure_is_not_fresh(tmp_path, monkeypatch):
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    original = RD._git_bytes
    monkeypatch.setattr(RD, "_git_bytes",
                        lambda root, *args: None if args[:1] == ("diff",) and "--quiet" in args else original(root, *args))
    (row,) = _targets(repo, raised, base, head, [_raised(1)])
    assert row["citationFresh"] is False


def test_f_every_target_of_the_batch_carries_its_own_freshness(tmp_path):
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    rows = _targets(repo, raised, base, head, [_raised(1), dict(_raised(1, line=9), title="B")])
    assert [r["citationFresh"] for r in rows] == [True, True]


def _sibling_of(row, title):
    (sibling,) = [s for s in row["batchFindings"] if s["title"] == title]
    return sibling


def test_f_every_sibling_of_the_batch_carries_the_freshness_the_driver_judged_it_by(tmp_path):
    # the stage changes TFILE between the raised head and the base: a finding citing TFILE is stale, one citing OTHER fresh
    repo, raised, base, head = _stage(tmp_path, {TFILE: "new first line\n" + LINES})
    findings = [dict(_raised(1), title="A", file=OTHER, line=1),
                dict(_raised(1), title="B", file=OTHER, line=1),
                dict(_raised(1), title="C"),  # cites TFILE, which changed: stale
                dict(_raised(1), title="D", file=OTHER, line=1, **{SC.RAISED_ROUND_FIELD: 0}),  # no usable raised head
                dict(_finding("E", None, file=None), **{SC.RAISED_ROUND_FIELD: 1})]  # cites no file
    rows = _targets(repo, raised, base, head, findings)
    assert [r["citationFresh"] for r in rows] == [True, True, False, False, False]
    for row in rows:
        siblings = {s["title"]: s for s in row["batchFindings"]}
        assert set(siblings) == {"A", "B", "C", "D", "E"} - {row["title"]}
        for title, sibling in siblings.items():
            assert sibling["citationFresh"] is {"A": True, "B": True, "C": False, "D": False, "E": False}[title]
            assert "citationCheck" not in sibling  # the check's facts stay on the target rows


def test_f_a_siblings_freshness_is_what_citation_freshness_returns_for_its_own_row_and_finding(tmp_path, monkeypatch):
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"})
    calls = []

    def spy(state, config, finding, row, removal_base, removal_head, cache):
        calls.append((finding, dict(row), removal_base, removal_head, cache, "batchFindings" in row))
        return finding["title"] == "B", {"raisedHead": None, "base": None, "files": []}

    monkeypatch.setattr(RD, "_citation_freshness", spy)
    findings = [_raised(1, line=3), dict(_raised(1, line=9, kindOfMistake={"kind": "k", "places": [
        {"file": OTHER, "line": 2}]}), title="B")]
    rows = _targets(repo, raised, base, head, findings)
    assert [_sibling_of(r, t)["citationFresh"] for r, t in ((rows[0], "B"), (rows[1], "A"))] == [True, False]
    sibling_calls = [c for c in calls if not c[5]]
    target_calls = [c for c in calls if c[5]]
    assert [c[0]["title"] for c in sibling_calls] == ["A", "B"] and [c[0]["title"] for c in target_calls] == ["A", "B"]
    for finding, row, call_base, call_head, _cache, _is_target in calls:
        assert (call_base, call_head) == (base, head)
    # the sibling row handed over is the sibling entry itself: it carries the cited file, line and kind of mistake
    (b_row,) = [c[1] for c in sibling_calls if c[0]["title"] == "B"]
    assert (b_row["file"], b_row["line"], b_row["kindOfMistake"]["places"]) == (TFILE, 9, [{"file": OTHER, "line": 2}])
    assert "citationCheck" not in b_row
    # one cache object serves the siblings and the targets alike
    assert len({id(c[4]) for c in calls}) == 1


def test_f_the_drivers_freshness_and_record_reach_the_fold(tmp_path):
    cut = "l1\nl2\nl5\nl6\nl7\nl8\n"
    repo, raised, base, head = _stage(tmp_path, {OTHER: "x\ny\n"}, remove={TFILE: cut})
    (row,) = _targets(repo, raised, base, head, [_raised(1)])
    target = _target(files=(TFILE,), record=row["fixerRemoval"], file=TFILE, line=3,
                     citationFresh=row["citationFresh"])
    assert row["citationFresh"] is True and row["fixerRemoval"]["files"][0]["testOpenings"] == []
    assert _fold([_removed()], target)["testRemovalCleared"] == ["t0"]
    # the cited file changed after the finding was raised: the same removal refuses
    repo, raised, base, head = _stage(tmp_path / "stale", {TFILE: "new first line\n" + LINES},
                                      remove={TFILE: "new first line\n" + cut})
    (row,) = _targets(repo, raised, base, head, [_raised(1, line=4)])
    target = _target(files=(TFILE,), record=row["fixerRemoval"], file=TFILE, line=4,
                     citationFresh=row["citationFresh"])
    assert row["citationFresh"] is False
    _refused(_fold([_removed()], target), "C10")
