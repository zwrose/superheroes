import pytest

import test_pilot_artifacts as artifacts


def _records():
    return [{
        "branch": "feat/x",
        "slot": None,
        "scenarios": [{"id": "scenario-a",
                       "config": {"password": "secret", "url": "/dashboard"}}],
        "steps": [
            {"id": "step-1", "instruction": "Open /dashboard",
             "expected": "The dashboard loads", "scenarioIds": ["scenario-a"]},
            {"id": "step-2", "instruction": "Click Save",
             "expected": "Success toast appears", "scenarioIds": ["scenario-a"]},
        ],
        "coverageRationale": "Covers the primary browser path",
    }]


def test_render_plan_includes_scenarios_steps_instructions_and_expected_outcomes():
    body = artifacts.render_plan(_records())
    assert "scenario-a" in body
    assert "step-1" in body
    assert "- [ ] step-1: Open /dashboard" in body
    assert "Expected: The dashboard loads" in body
    assert "Covers the primary browser path" in body


def test_render_plan_omits_raw_seed_configs_and_secret_material():
    body = artifacts.render_plan(_records())
    assert "password" not in body.lower()
    assert "secret" not in body.lower()
    assert "config" not in body.lower()


def test_render_results_includes_pass_fail_scrubbed_notes_fix_shas_and_rationale():
    status = {
        "records": [
            {"stepId": "step-1", "status": "pass", "notes": "ok"},
            {"stepId": "step-2", "status": "fail",
             "notes": "Authorization: Bearer abc123def456"},
        ],
        "fixes": [{"sha": "abc1234", "summary": "Fix save button"}],
        "coverageRationale": "Covered checkout and retry flows",
    }
    body = artifacts.render_results(status)
    assert "step-1: pass" in body
    assert "step-2: fail" in body
    assert "abc1234" in body
    assert "Covered checkout and retry flows" in body
    assert "abc123def456" not in body
    assert "[REDACTED]" in body


def test_render_results_omits_request_details_cookies_and_protected_personal_data():
    status = {
        "records": [{
            "stepId": "step-1",
            "status": "fail",
            "notes": "Cookie: session=abc123\nrequest headers include x-api-key: key123456",
            "request": {"headers": {"cookie": "session=abc123"}},
            "protected": {"target": "main"},
            "personal": {"email": "person@example.com"},
        }]
    }
    body = artifacts.render_results(status)
    assert "session=abc123" not in body
    assert "key123456" not in body
    assert "person@example.com" not in body
    assert "protected" not in body.lower()
    assert "headers" not in body.lower()


class Poster:
    def __init__(self, fail_family=None):
        self.fail_family = fail_family
        self.calls = []

    def upsert(self, pr, family, key, body):
        self.calls.append((pr, family, key, body))
        if family == self.fail_family:
            raise RuntimeError("%s post failed" % family)
        return {"action": "created", "id": len(self.calls)}


class Fallbacks:
    def __init__(self):
        self.writes = []

    def write_fallback(self, plans_dir, key, family, body):
        self.writes.append((plans_dir, key, family, body))
        return "/tmp/%s.%s.md" % (key, family)


def test_ensure_artifacts_posts_both_comments_without_fallbacks():
    poster = Poster()
    fallback = Fallbacks()
    result = artifacts.ensure_artifacts(90, "feat%2Fx", "plan", "results",
                                        poster, fallback)
    assert result["posting"]["ok"] is True
    assert [call[1] for call in poster.calls] == ["plan", "results"]
    assert fallback.writes == []


def test_ensure_artifacts_writes_both_fallbacks_if_either_post_fails():
    poster = Poster(fail_family="results")
    fallback = Fallbacks()
    result = artifacts.ensure_artifacts(90, "feat%2Fx", "plan", "results",
                                        poster, fallback)
    assert result["posting"]["ok"] is False
    assert {write[2] for write in fallback.writes} == {"plan", "results"}
    assert result["fallback"]["plan"]
    assert result["fallback"]["results"]


def test_ensure_artifacts_parks_when_post_and_required_fallback_fail():
    poster = Poster(fail_family="plan")

    class BrokenFallback:
        def write_fallback(self, plans_dir, key, family, body):
            raise RuntimeError("disk full")

    result = artifacts.ensure_artifacts(90, "feat%2Fx", "plan", "results",
                                        poster, BrokenFallback())
    assert result["action"] == "park"
    assert "fallback" in result["reason"]
