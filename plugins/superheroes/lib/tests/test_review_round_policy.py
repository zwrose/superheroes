import importlib.util
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load():
    spec = importlib.util.spec_from_file_location("review_round_policy", os.path.join(LIB, "review_round_policy.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RP = load()


def test_malformed_previous_dimension_is_fail_safe():
    out = RP.plan_round({
        "round": 2,
        "dimensions": ["architecture-reviewer"],
        "changedSubjects": ["Test"],
        "previous": {"architecture-reviewer": []},
    })
    assert out["dimensions"]["architecture-reviewer"]["action"] == "run"
    assert out["escalationPolicy"] == "cheap-first"


def test_fractional_round_string_is_malformed():
    out = RP.plan_round({
        "round": "2.5",
        "dimensions": ["test-reviewer"],
        "changedSubjects": ["Test"],
        "previous": {},
    })
    assert out["dimensions"]["test-reviewer"]["reason"] == "malformed round state"
    assert out["escalationPolicy"] == "deep-only"


def test_object_changed_subjects_from_live_doc_fix_still_schedule_skips():
    out = RP.plan_round({
        "round": 2,
        "dimensions": ["architecture-reviewer", "security-reviewer"],
        "changedSubjects": [{"section": "Components > lib/acceptance_launch.py", "reason": "fixed architecture finding"}],
        "previous": {
            "architecture-reviewer": {
                "status": "run",
                "confidence": "high",
                "hasFindings": True,
                "subjects": ["Architecture"],
                "round": 1,
            },
            "security-reviewer": {
                "status": "run",
                "confidence": "high",
                "hasFindings": False,
                "subjects": ["Security"],
                "round": 1,
            },
        },
    })
    assert out["escalationPolicy"] == "cheap-first"
    assert out["dimensions"]["architecture-reviewer"]["tier"] == "reviewer"
    assert out["dimensions"]["security-reviewer"]["action"] == "skip"
