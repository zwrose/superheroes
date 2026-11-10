"""#2418: characterization of `audits.apply_audit_results`, pinned on the unsplit function.

A later change splits the function into helpers; these tests prove it changed no behaviour. The
invariant: for every input, `apply_audit_results(...)` returns a value equal to the value the base code
returns, including the order of every list in the result and every key of every `audits` entry.

Pins, each at the place the rule is enforced:

T1  a target id on two targets with no result for it reads "duplicate audit target id — honoring none";
T2  an allowed unnamed change on a `discharged-but-new-issue` result is recorded as `allowedChange`;
G   every scenario of `SCENARIOS` (one per arm of the function, plus multi-target orderings) returns
    exactly the value stored in `fixtures/apply_audit_results_golden_2418.json`.

Regenerate the golden on the code as it stands with:
    scripts/pinned-python -B plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py --write-golden

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
"""
import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402

GOLDEN_PATH = os.path.join(_HERE, "fixtures", "apply_audit_results_golden_2418.json")

PROSE_MD = "plugins/superheroes/rubric/some-doctrine.md"
CODE_PY = "src/a.py"
UNNAMED = "also drops the log line"


# --- builders -----------------------------------------------------------------------------------

def _checks(**answers):
    return {name: {"answer": answers.get(name, "yes"), "why": "checked: %s" % name}
            for name in ("right", "brokeNothing", "testWouldFail")}


def _result(fid="t1", ruling="discharged", reason="the fix resolves it", checks=True, **extra):
    out = {"id": fid, "ruling": ruling, "reason": reason}
    if checks is True:
        out["checks"] = _checks()
    elif checks is not None:
        out["checks"] = checks
    out.update(extra)
    return out


def _target(fid="t1", **extra):
    row = {"id": fid, "file": CODE_PY, "line": 2, "title": "Retry without a cap", "severity": "Important"}
    row.update(extra)
    return row


def _delta(*files):
    out = []
    for name in files:
        out.append("diff --git a/%s b/%s" % (name, name))
        out.extend(["--- a/%s" % name, "+++ b/%s" % name, "@@ -1 +1 @@", "-old", "+new"])
    return out


def _kind(*lines):
    return {"kind": "uncapped retry", "places": [{"file": CODE_PY, "line": n} for n in lines]}


def _row(line, fixed, file=CODE_PY):
    return {"file": file, "line": line, "fixed": fixed}


def _issue(title):
    return {"file": "g.py", "line": 3, "title": title, "severity": "Minor"}


def _claim_target(fid="t1", **extra):
    return _target(fid, roundFindings=[{"id": "m", "file": "g.py", "line": 3, "title": "other"}],
                   reportedUnnamedChanges=[{"ref": "r2:a", "round": 2, "id": fid, "text": "earlier"}],
                   **extra)


def _scenario(name, audited, results, **kwargs):
    return {"name": name, "audited": audited, "results": results, "kwargs": kwargs}


# --- the scenarios ------------------------------------------------------------------------------

def _build_scenarios():
    s = []
    s.append(_scenario("S01_silence_idless_target",
                       [{"title": "no id", "file": "a.py", "line": 1}, _target(7)], []))
    s.append(_scenario("S02_silence_unaudited", [_target("t1")], []))
    s.append(_scenario("S03_silence_ambiguous_result_id", [_target("t1")],
                       [_result("t1"), _result("t1", reason="a second claim")]))
    s.append(_scenario("S04_duplicate_target_with_a_result",
                       [_target("t1"), _target("t1", line=9)], [_result("t1")]))
    s.append(_scenario("S05_unmatched_result", [_target("t1")], [_result("t1"), _result("zzz")]))
    s.append(_scenario("S06_provenance_no_auditor_recorded", [_target("t1")], [_result("t1")],
                       expected_auditors={"other": "codex"}, collection_manifest={"t1": "codex"}))
    s.append(_scenario("S07_provenance_manifest_entry_missing", [_target("t1")], [_result("t1")],
                       expected_auditors={"t1": "codex"}))
    s.append(_scenario("S08_provenance_manifest_vendor_mismatch", [_target("t1")], [_result("t1")],
                       expected_auditors={"t1": "codex"}, collection_manifest={"t1": "claude"}))
    s.append(_scenario("S09_provenance_authenticated_echo_mismatch", [_target("t1")],
                       [_result("t1", auditorVendor="gemini")],
                       expected_auditors={"t1": "codex"}, collection_manifest={"t1": "codex"}))
    s.append(_scenario("S10_blocking_break_it_match_keeps_new_issues",
                       [_target("t1", breakIt={"match": "missing", "path": "tests/test_a.py"})],
                       [_result("t1", ruling="not-discharged", reason="still broken", checks=None,
                                testMatch={"answer": "matches", "why": "same"},
                                newIssues=[_issue("kept one")])]))
    s.append(_scenario("S11_three_checks_fault", [_target("t1")], [_result("t1", checks=None)]))
    s.append(_scenario("S12_places_collected_a_place_ignored", [_target("t1", kindOfMistake=_kind(3, 19))],
                       [_result("t1", places=[_row(3, True), _row(19, True),
                                              _row(5, True, file="src/other.py")])]))
    s.append(_scenario("S13_weakened_explained_test_precedes_places",
                       [_target("t1", breakIt={"match": "changed-explained", "path": "tests/test_a.py"},
                                kindOfMistake=_kind(3, 19))],
                       [_result("t1", testMatch={"answer": "weakened", "why": "dropped an assertion"})]))
    s.append(_scenario("S14_incomplete_places_with_unnamed_change",
                       [_target("t1", kindOfMistake=_kind(3, 19))],
                       [_result("t1", places=[_row(3, True), _row(19, False)], unnamedChange=UNNAMED)]))
    s.append(_scenario("S15_failed_check", [_target("t1")],
                       [_result("t1", ruling="discharged-but-new-issue", checks=_checks(right="no"),
                                newIssues=[_issue("fresh")])]))
    s.append(_scenario("S16_review_guarded_refused",
                       [_target("t1", fixerDelta=_delta(PROSE_MD, CODE_PY))],
                       [_result("t1", checks=_checks(testWouldFail=audits.REVIEW_GUARDED))]))
    s.append(_scenario("S17_review_guarded_cleared",
                       [_target("t1", fixerDelta=_delta(PROSE_MD))],
                       [_result("t1", checks=_checks(testWouldFail=audits.REVIEW_GUARDED))]))
    s.append(_scenario("S18_unnamed_change_not_a_string", [_target("t1")], [_result("t1", unnamedChange=5)]))
    s.append(_scenario("S19_unnamed_change_seq_not_an_int", [_target("t1")],
                       [_result("t1", unnamedChange=UNNAMED, unnamedChangeAllowedBySeq="1")]))
    s.append(_scenario("S20_claim_fault", [_target("t1")], [_result("t1", unnamedChangeFixes=[""])]))
    s.append(_scenario("S21_discharged_unnamed_change_refused", [_claim_target("t1")],
                       [_result("t1", unnamedChange=UNNAMED)]))
    s.append(_scenario("S22_discharged_attributed", [_claim_target("t1")],
                       [_result("t1", unnamedChange=" %s " % UNNAMED, unnamedChangeFixes=["m"],
                                unnamedChangeReverts=["r2:a"])]))
    s.append(_scenario("S23_discharged_allowed_change_with_evidence_and_carry_fields",
                       [_target("t1", marker="carry-me")],
                       [_result("t1", unnamedChange=UNNAMED, evidence="ran the suite")],
                       carry_fields=["marker"], change_allowed_ids=["t1"]))
    s.append(_scenario("S24_discharged_with_no_reason", [_target("t1")], [_result("t1", reason="   ")]))
    s.append(_scenario("S25_new_issue_unnamed_change_refused", [_claim_target("t1")],
                       [_result("t1", ruling="discharged-but-new-issue", unnamedChange=UNNAMED,
                                newIssues=[_issue("fresh")])]))
    s.append(_scenario("S26_new_issue_attributed", [_claim_target("t1")],
                       [_result("t1", ruling="discharged-but-new-issue", unnamedChange=UNNAMED,
                                unnamedChangeFixes=["m"], newIssues=[_issue("fresh")])]))
    s.append(_scenario("S27_new_issue_no_usable_candidates", [_target("t1")],
                       [_result("t1", ruling="discharged-but-new-issue", newIssues=[])]))
    s.append(_scenario("S28_not_discharged_by_selected_auditor",
                       [_target("t1", auditorVendor="codex")],
                       [_result("t1", ruling="not-discharged", reason="still broken", unnamedChange=UNNAMED,
                                newIssues=[_issue("kept")])],
                       collection_manifest={"t1": "codex"}))
    s.append(_scenario("S29_unknown_ruling", [_target("t1")], [_result("t1", ruling="maybe")]))
    s.append(_scenario("S30_results_not_a_list", [_target("t1")], None))
    s.append(_scenario("S31_audited_not_a_list", None, [_result("t1")]))
    # The two branches no other test reached (T1 and T2 assert them directly as well).
    s.append(_scenario("T1_duplicate_target_without_a_result", [_target("d1"), _target("d1", line=9)], []))
    s.append(_scenario("T2_allowed_change_on_a_new_issue_result", [_target("t1")],
                       [_result("t1", ruling="discharged-but-new-issue", unnamedChange="  %s  " % UNNAMED,
                                newIssues=[_issue("fresh")])],
                       change_allowed_ids=["t1"]))

    # M1: ids out of sorted order, results in another order, mixed outcomes, two unmatched results.
    s.append(_scenario(
        "M1_unsorted_targets_results_in_another_order_mixed_outcomes",
        [_target("t5"), _target("t2"), _target("t9"), _target("t1"), _target("t7"), _target("t3")],
        [_result("t7", ruling="maybe"),
         _result("z2"),
         _result("t3", checks=None),
         _result("t5", ruling="discharged-but-new-issue", newIssues=[_issue("from t5")]),
         _result("t9", ruling="not-discharged", reason="still broken"),
         _result("z1"),
         _result("t2")]))

    # M2: a review-guarded clear never leaks to the next target, in either order.
    guarded = _checks(testWouldFail=audits.REVIEW_GUARDED)
    s.append(_scenario(
        "M2_review_guarded_then_plain_then_plain_then_guarded",
        [_target("g1", fixerDelta=_delta(PROSE_MD)), _target("p1"), _target("p2"),
         _target("g2", fixerDelta=_delta(PROSE_MD))],
        [_result("g1", checks=guarded), _result("p1"), _result("p2"), _result("g2", checks=guarded)]))

    # M3: keeps-new-issues is recomputed per target, in either order.
    s.append(_scenario(
        "M3_kept_then_dropped_then_dropped_then_kept_new_issues",
        [_target("k1"), _target("k2"), _target("k3"), _target("k4")],
        [_result("k1", ruling="not-discharged", reason="no", newIssues=[_issue("kept 1")]),
         _result("k2", ruling="not-discharged", reason="no", newIssues=[_issue("dropped 2")]),
         _result("k3", ruling="not-discharged", reason="no", newIssues=[_issue("dropped 3")]),
         _result("k4", ruling="not-discharged", reason="no", newIssues=[_issue("kept 4")])],
        expected_auditors={"k1": "codex", "k2": "codex", "k3": "codex", "k4": "codex"},
        collection_manifest={"k1": "codex", "k4": "codex"}))

    # M4: the order of `newIssues` across a new-issue target and a blocking-test target.
    s.append(_scenario(
        "M4_new_issue_and_blocking_test_targets_order_new_issues",
        [_target("b1"), _target("b2", breakIt={"match": "missing", "path": "tests/test_a.py"}),
         _target("b3", breakIt={"match": "changed-unexplained", "path": "tests/test_a.py"}), _target("b4")],
        [_result("b4", ruling="discharged-but-new-issue", newIssues=[_issue("from b4")]),
         _result("b3", ruling="not-discharged", reason="no", checks=None, newIssues=[_issue("from b3")]),
         _result("b2", ruling="not-discharged", reason="no", checks=None, newIssues=[_issue("from b2")]),
         _result("b1", ruling="discharged-but-new-issue", newIssues=[_issue("from b1")])]))
    return s


SCENARIOS = _build_scenarios()


def _run(scenario):
    value = audits.apply_audit_results(copy.deepcopy(scenario["audited"]), copy.deepcopy(scenario["results"]),
                                       **copy.deepcopy(scenario["kwargs"]))
    return value


def _golden():
    with open(GOLDEN_PATH, encoding="utf-8") as handle:
        return json.load(handle)


# --- T1 and T2: the two branches no other test reaches --------------------------------------------

def test_t1_a_duplicated_target_id_with_no_result_reads_duplicate_target():
    # axis: a duplicated target id with no result reads "duplicate audit target id — honoring none"
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
    out = audits.apply_audit_results([_target("d1"), _target("d1", line=9)], [])
    assert [e["ruling"] for e in out["audits"]] == ["not-discharged", "not-discharged"]
    assert [e["reason"] for e in out["audits"]] == ["duplicate audit target id — honoring none"] * 2
    assert out["notDischarged"] == ["d1", "d1"]
    assert out["ambiguous"] == ["d1"]
    assert out["unaudited"] == []


def test_t2_an_allowed_unnamed_change_on_a_new_issue_result_is_recorded_as_allowed_change():
    # axis: an allowed unnamed change on a discharged-but-new-issue result is recorded as `allowedChange`
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
    result = _result("t1", ruling="discharged-but-new-issue", unnamedChange="  %s  " % UNNAMED,
                     newIssues=[_issue("fresh")])
    out = audits.apply_audit_results([_target("t1")], [result], change_allowed_ids=["t1"])
    (entry,) = out["audits"]
    assert entry["ruling"] == "discharged-but-new-issue"
    assert entry["allowedChange"] == UNNAMED
    assert entry["reportedUnnamedChange"] == UNNAMED
    assert "attributedChange" not in entry
    assert out["discharged"] == ["t1"]
    assert out["unnamedChange"] == []


# --- the golden table -----------------------------------------------------------------------------

@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_golden_scenario_returns_exactly_the_recorded_value(scenario):
    # axis: the whole returned value (every list, its order, every audit key) equals the recorded golden
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
    golden = _golden()
    assert scenario["name"] in golden, "scenario %s has no golden entry — regenerate" % scenario["name"]
    assert _run(scenario) == golden[scenario["name"]]


def test_golden_fixture_names_exactly_the_scenarios_of_this_module():
    # axis: scenario names are unique and golden keys exactly match them, rejecting missing or extra fixture entries.
    names = [s["name"] for s in SCENARIOS]
    assert len(names) == len(set(names))
    assert sorted(_golden()) == sorted(names)


if __name__ == "__main__":
    if "--write-golden" in sys.argv[1:]:
        table = {s["name"]: _run(s) for s in SCENARIOS}
        with open(GOLDEN_PATH, "w", encoding="utf-8") as handle:
            json.dump(table, handle, sort_keys=True, indent=1, ensure_ascii=False)
            handle.write("\n")
