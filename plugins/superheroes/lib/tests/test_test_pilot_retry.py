import json
import subprocess
import sys

import test_pilot_retry as retry


def _pass_result(*steps):
    return {"steps": list(steps)}


def _failed(step_id, summary="Button is missing", file="web/app.js"):
    return {
        "id": step_id,
        "status": "failed",
        "failureType": "app_bug",
        "summary": summary,
        "files": [file],
    }


def _passed(step_id):
    return {"id": step_id, "status": "passed"}


def _batch(summary, before=None, after=None):
    return {
        "type": "browser_fix_batch",
        "summary": summary,
        "before": before or {},
        "after": after or {},
    }


def test_app_bug_failures_are_collected_into_one_fix_batch():
    result = retry.decide(
        _pass_result(
            _failed("login-submit", "Submit button throws"),
            _failed("settings-save", "Save button throws"),
        ),
        history=[],
    )

    assert result["action"] == "fix_batch"
    assert result["failedStepIds"] == ["login-submit", "settings-save"]
    assert "login-submit" in result["summary"]
    assert "settings-save" in result["summary"]


def test_records_payload_failures_are_collected_into_fix_batch():
    result = retry.decide(
        {"records": [{"stepId": "login-submit", "status": "failed", "failureType": "app_bug"}]},
        history=[],
    )

    assert result["action"] == "fix_batch"
    assert result["failedStepIds"] == ["login-submit"]


def test_after_three_fix_batches_remaining_failed_step_parks():
    history = [_batch("a"), _batch("b"), _batch("c")]
    result = retry.decide(_pass_result(_failed("login-submit")), history=history)

    assert result["action"] == "park_cap_reached"
    assert "3" in result["reason"]


def test_two_same_scrubbed_fix_summaries_without_browser_progress_park():
    history = [
        _batch(
            "Fix login button at /tmp/worktree-123/web/app.js:41",
            before={"login-submit": "failed", "settings-save": "failed"},
            after={"login-submit": "failed", "settings-save": "failed"},
        ),
        _batch(
            "fix login button at /private/tmp/worktree-999/web/app.js:88",
            before={"login-submit": "failed", "settings-save": "failed"},
            after={"login-submit": "failed", "settings-save": "failed"},
        ),
    ]

    result = retry.decide(_pass_result(_failed("login-submit")), history=history)

    assert result["action"] == "park_no_progress"
    assert "login button" in result["reason"]


def test_recurring_failure_does_not_park_when_another_failed_or_affected_step_progressed():
    history = [
        _batch(
            "Fix login button",
            before={"login-submit": "failed", "settings-save": "failed"},
            after={"login-submit": "failed", "settings-save": "failed"},
        ),
        _batch(
            "Fix login button",
            before={"login-submit": "failed", "settings-save": "failed"},
            after={"login-submit": "failed", "settings-save": "passed"},
        ),
    ]

    result = retry.decide(_pass_result(_failed("login-submit")), history=history)

    assert result["action"] == "fix_batch"
    assert result["failedStepIds"] == ["login-submit"]


def test_previous_batch_progress_prevents_same_summary_no_progress_park():
    history = [
        _batch(
            "Fix login button",
            before={"login-submit": "failed", "settings-save": "failed"},
            after={"login-submit": "failed", "settings-save": "passed"},
        ),
        _batch(
            "Fix login button",
            before={"login-submit": "failed"},
            after={"login-submit": "failed"},
        ),
    ]

    result = retry.decide(_pass_result(_failed("login-submit")), history=history)

    assert result["action"] == "fix_batch"


def test_unknown_affected_coverage_reruns_all_after_a_fix_batch():
    result = retry.decide(
        _pass_result(_failed("login-submit")),
        history=[_batch("Fix login button")],
        changed_files=["web/app.js"],
        dependency_map=None,
    )

    assert result["action"] == "rerun_all"
    assert result["failedStepIds"] == ["login-submit"]


def test_known_affected_coverage_reruns_failed_and_affected_subset():
    result = retry.decide(
        _pass_result(_failed("login-submit"), _passed("home-load")),
        history=[_batch("Fix login button")],
        changed_files=["web/app.js"],
        dependency_map={"web/app.js": ["home-load", "settings-save"]},
    )

    assert result["action"] == "rerun_subset"
    assert result["stepIds"] == ["home-load", "login-submit", "settings-save"]
    assert result["failedStepIds"] == ["login-submit"]
    assert result["affectedStepIds"] == ["home-load", "settings-save"]


def test_retry_cli_decide_prints_decision_json(tmp_path):
    pass_path = tmp_path / "pass.json"
    history_path = tmp_path / "history.json"
    dependency_path = tmp_path / "dependencies.json"
    pass_path.write_text(json.dumps(_pass_result(_failed("login-submit"))))
    history_path.write_text(json.dumps([_batch("Fix login button")]))
    dependency_path.write_text(json.dumps({"web/app.js": ["home-load"]}))

    out = subprocess.run(
        [
            sys.executable,
            "plugins/superheroes/lib/test_pilot_retry_cli.py",
            "decide",
            "--pass-json",
            str(pass_path),
            "--history-json",
            str(history_path),
            "--changed-file",
            "web/app.js",
            "--dependency-json",
            str(dependency_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout)["action"] == "rerun_subset"
