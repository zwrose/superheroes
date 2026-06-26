import pytest

import test_pilot_results as results


def _raw():
    return {
        "source": "browser",
        "coverageRationale": "Exercises the user-visible save path",
        "steps": [
            {"id": "step-1", "status": "pass", "notes": "Loaded page"},
            {"id": "step-2", "status": "fail",
             "notes": "Authorization: Bearer abc123def456"},
        ],
        "fixes": [{"sha": "abc1234", "summary": "Fix button"}],
    }


def test_aggregate_accepts_browser_evidence_and_scrubs_byte_capped_diagnostics():
    result = results.aggregate_browser_results(_raw(), lambda s: s.replace("abc123def456", "[REDACTED]"),
                                               {"diagnostics": 2000, "renderedBytes": 20000})
    assert result["action"] == "aggregated"
    assert result["records"][1]["stepId"] == "step-2"
    assert result["records"][1]["status"] == "fail"
    assert "abc123def456" not in result["records"][1]["notes"]
    assert result["fixes"][0]["sha"] == "abc1234"
    assert result["coverageRationale"] == "Exercises the user-visible save path"


def test_aggregate_preserves_browser_failure_classification_and_summary():
    raw = dict(_raw(), steps=[{
        "id": "step-2",
        "status": "failed",
        "failureType": "test_bug",
        "summary": "Selector changed",
        "message": "Expected save button to exist",
        "notes": "No app regression observed",
    }])

    result = results.aggregate_browser_results(raw, lambda s: s, {"diagnostics": 2000})

    record = result["records"][0]
    assert record["failureType"] == "test_bug"
    assert record["summary"] == "Selector changed"
    assert record["message"] == "Expected save button to exist"


@pytest.mark.parametrize("source", ["synthetic", "unit", None])
def test_aggregate_rejects_synthetic_or_non_browser_evidence(source):
    raw = dict(_raw(), source=source)
    result = results.aggregate_browser_results(raw, lambda s: s, {"diagnostics": 2000})
    assert result["action"] == "park"
    assert "browser-derived" in result["reason"]


def test_aggregate_parks_on_scrub_failure():
    def boom(text):
        raise RuntimeError("scrubber broke")

    result = results.aggregate_browser_results(_raw(), boom, {"diagnostics": 2000})
    assert result["action"] == "park"
    assert "scrub" in result["reason"]


def test_aggregate_parks_on_oversized_diagnostics():
    raw = dict(_raw(), steps=[{"id": "step-1", "status": "fail", "notes": "x" * 50}])
    result = results.aggregate_browser_results(raw, lambda s: s, {"diagnostics": 10})
    assert result["action"] == "park"
    assert "diagnostics" in result["reason"]


def test_aggregate_omits_seed_configs_credentials_auth_headers_and_cookies():
    raw = dict(_raw(), steps=[{
        "id": "step-1",
        "status": "fail",
        "notes": "Cookie: session=abc123\nAuthorization: Bearer abc123def456",
        "seedConfig": {"password": "secret"},
        "request": {"headers": {"authorization": "Bearer abc123def456"}},
        "cookies": [{"name": "session", "value": "abc123"}],
    }])
    result = results.aggregate_browser_results(raw, lambda s: s.replace("abc123def456", "[REDACTED]").replace("abc123", "[REDACTED]"),
                                               {"diagnostics": 2000})
    assert result["action"] == "aggregated"
    text = str(result)
    assert "seedConfig" not in text
    assert "headers" not in text
    assert "cookies" not in text
    assert "secret" not in text
    assert "abc123def456" not in text
