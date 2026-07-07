# plugins/superheroes/lib/tests/test_task_review.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import task_review as tr

OK = {"spec_compliance": "pass", "code_quality": "pass"}


def test_missing_verdict_re_requests():
    out = tr.decide({"spec_compliance": "pass"}, [], 1, 3, [])
    assert out["action"] == "re_request"


def test_clean_completes():
    out = tr.decide(OK, [], 1, 3, [])
    assert out["action"] == "complete"


def test_minor_only_completes_and_carries():
    out = tr.decide(OK, [{"severity": "Minor", "file": "a.py", "title": "nit"}], 1, 3, [])
    assert out["action"] == "complete"
    assert len(out["minors"]) == 1 and out["blocking"] == []


def test_blocking_triggers_review():
    out = tr.decide(OK, [{"severity": "Important", "file": "a.py", "title": "bug"}], 1, 3, [])
    assert out["action"] == "review"
    assert len(out["blocking"]) == 1


def test_cannot_verify_blocks_completion():
    out = tr.decide(OK, [{"severity": "Minor", "file": "a.py", "title": "x",
                          "cannot_verify_from_diff": True}], 1, 3, [])
    assert out["action"] == "review"
    assert len(out["cannot_verify"]) == 1


def test_cap_reached_with_blocker_parks():
    hist = [{"round": 1, "findings": [{"severity": "Important", "file": "a.py", "title": "bug"}]},
            {"round": 2, "findings": [{"severity": "Important", "file": "a.py", "title": "bug"}]}]
    out = tr.decide(OK, [{"severity": "Important", "file": "a.py", "title": "bug"}], 3, 3, hist)
    assert out["action"] == "park"


# --- #276: severity-vocabulary fail-closed + verdict gate --------------------

# The exact live escape (2026-07-06 run of #219): fail/fail verdicts + a foreign, mis-cased
# severity scale that the old case-sensitive `Critical/Important` partition demoted to Minor,
# so every per-task review "passed" while the whole feature was unimplemented.
LIVE_FINDINGS = [
    {"severity": "critical", "file": "README.md", "title": "Task 2 not implemented"},
    {"severity": "blocker", "file": "README.md", "title": "Tasks 2-5 were never implemented"},
]


def test_live_escape_lowercase_blockers_do_not_pass():
    out = tr.decide({"spec_compliance": "fail", "code_quality": "fail"}, LIVE_FINDINGS, 1, 3, [])
    assert out["action"] != "complete"
    assert len(out["blocking"]) == 2 and out["minors"] == []


def test_foreign_scale_fails_closed_to_blocking():
    # PASSING verdicts, so this isolates the _partition fail-close from the verdict gate.
    for sev in ("blocker", "high", "medium", "info", "MAJOR", "", None):
        out = tr.decide(OK, [{"severity": sev, "file": "a.py", "title": "x"}], 1, 3, [])
        assert out["action"] == "review", sev
        assert len(out["blocking"]) == 1 and out["minors"] == [], sev


def test_canonical_minor_and_nit_still_demote_case_insensitively():
    for sev in ("Minor", "minor", "Nit", "nit"):
        out = tr.decide(OK, [{"severity": sev, "file": "a.py", "title": "x"}], 1, 3, [])
        assert out["action"] == "complete", sev
        assert out["blocking"] == [] and len(out["minors"]) == 1, sev


def test_failing_verdict_gates_even_with_no_blocking_findings():
    # Vocabulary-independent backstop: a non-'pass' verdict can never complete, even with zero findings.
    out = tr.decide({"spec_compliance": "fail", "code_quality": "pass"}, [], 1, 3, [])
    assert out["action"] == "review"
    assert "spec_compliance" in out["reason"]


def test_failing_verdict_gates_with_only_minor_findings():
    out = tr.decide({"spec_compliance": "pass", "code_quality": "fail"},
                    [{"severity": "Minor", "file": "a.py", "title": "nit"}], 1, 3, [])
    assert out["action"] == "review"
    assert out["blocking"] == [] and len(out["minors"]) == 1


def test_both_pass_still_completes_clean():
    out = tr.decide(OK, [], 1, 3, [])
    assert out["action"] == "complete"
