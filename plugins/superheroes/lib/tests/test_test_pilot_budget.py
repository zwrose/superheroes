import json
import subprocess
import sys

import test_pilot_budget as budget


def test_default_limits_are_the_task_3_limits():
    assert budget.DEFAULT_LIMITS == {
        "planRecords": 20,
        "browserSteps": 80,
        "browserPasses": 4,
        "browserFixBatches": 3,
        "uniqueScenarios": 40,
        "seedOperations": 120,
        "elapsedSeconds": 3600,
        "renderedBytes": 200000,
    }


def test_within_budget_defaults_missing_count_dimensions_to_zero():
    assert budget.decide({"planRecords": 20}) == {"action": "within_budget"}


def test_parks_when_a_count_exceeds_its_limit():
    result = budget.decide({"browserSteps": 81})
    assert result["action"] == "park_budget_exceeded"
    assert "browserSteps" in result["reason"]
    assert "80" in result["reason"]


def test_in_lock_operation_vector_recheck_catches_resumed_seed_operations():
    dry_run_counts = {"planRecords": 3, "seedOperations": 119}
    assert budget.decide(dry_run_counts)["action"] == "within_budget"

    resumed_counts = dict(dry_run_counts, seedOperations=121)
    result = budget.decide(resumed_counts)

    assert result["action"] == "park_budget_exceeded"
    assert "seedOperations" in result["reason"]


def test_malformed_numeric_values_park_instead_of_normalizing():
    for counts in (
        {"browserSteps": "7"},
        {"browserSteps": True},
        {"browserSteps": -1},
        {"browserSteps": float("nan")},
    ):
        result = budget.decide(counts)
        assert result["action"] == "park_budget_exceeded"
        assert "malformed" in result["reason"]


def test_custom_limits_are_validated_and_used():
    assert budget.decide({"browserSteps": 6}, {"browserSteps": 6})["action"] == "within_budget"

    result = budget.decide({"browserSteps": 7}, {"browserSteps": 6})
    assert result["action"] == "park_budget_exceeded"
    assert "browserSteps" in result["reason"]

    malformed = budget.decide({"browserSteps": 1}, {"browserSteps": "6"})
    assert malformed["action"] == "park_budget_exceeded"
    assert "malformed" in malformed["reason"]


def test_budget_cli_decide_prints_decision_json(tmp_path):
    counts = tmp_path / "counts.json"
    limits = tmp_path / "limits.json"
    counts.write_text(json.dumps({"browserSteps": 2}))
    limits.write_text(json.dumps({"browserSteps": 1}))

    out = subprocess.run(
        [
            sys.executable,
            "plugins/superheroes/lib/test_pilot_budget_cli.py",
            "decide",
            "--counts-json",
            str(counts),
            "--limits-json",
            str(limits),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout)["action"] == "park_budget_exceeded"
