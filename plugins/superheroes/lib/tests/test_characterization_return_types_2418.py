"""Check that characterization preserves Python return-value differences."""
import copy

import pytest

import test_apply_audit_results_characterization_2418 as characterization


def test_golden_comparison_rejects_a_tuple_return(monkeypatch):
    # axis: the golden assertion rejects a tuple substituted for an expected output list.
    scenario = next(
        item for item in characterization.SCENARIOS
        if item["name"] == "S29_unknown_ruling"
    )
    expected = characterization._golden()[scenario["name"]]
    returned = copy.deepcopy(expected)
    returned["malformed"] = tuple(returned["malformed"])
    assert returned != expected
    monkeypatch.setattr(
        characterization.audits,
        "apply_audit_results",
        lambda *_args, **_kwargs: returned,
    )
    with pytest.raises(AssertionError):
        characterization.test_golden_scenario_returns_exactly_the_recorded_value(scenario)
