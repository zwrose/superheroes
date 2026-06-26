import json
import subprocess
import sys

import test_pilot_applicability as applicability


def test_applicable_signals_win_over_docs_only():
    result = applicability.decide(
        diff={"files": ["docs/usage.md"]},
        detectors={"docs_only": True, "routes": ["/settings"]},
        profile={},
    )
    assert result["verdict"] == "applicable"
    assert "route" in result["reason"]


def test_not_applicable_requires_positive_no_browser_evidence():
    result = applicability.decide(
        diff={"files": ["README.md", "docs/install.md"]},
        detectors={},
        profile={},
    )
    assert result["verdict"] == "not_applicable"
    assert "docs-only" in result["reason"]


def test_internal_only_parks_when_user_facing_signal_is_present():
    result = applicability.decide(
        diff={"files": ["lib/internal.py"]},
        detectors={"internal_only": True, "user_facing": True},
        profile={},
    )
    assert result["verdict"] == "applicable"


def test_uncertain_inputs_park():
    result = applicability.decide(diff={"files": ["misc/unknown.py"]}, detectors={}, profile={})
    assert result["verdict"] == "park"
    assert "uncertain" in result["reason"]


def test_malformed_inputs_park():
    assert applicability.decide(diff="not a dict")["verdict"] == "park"
    assert applicability.decide(detectors=[])["verdict"] == "park"
    assert applicability.decide(profile=False)["verdict"] == "park"


def test_failed_or_empty_applicable_plan_derivation_parks():
    failed = applicability.decide(
        diff={"files": ["web/app.jsx"]},
        detectors={"frontend": True},
        profile={"baseUrl": "http://localhost:3000"},
        plan_result={"ok": False, "reason": "planner failed"},
    )
    assert failed["verdict"] == "park"
    assert "planner failed" in failed["reason"]

    empty = applicability.decide(
        diff={"files": ["web/app.jsx"]},
        detectors={"frontend": True},
        profile={"baseUrl": "http://localhost:3000"},
        plan_result={"ok": True, "applicable": True, "steps": []},
    )
    assert empty["verdict"] == "park"
    assert "empty" in empty["reason"]


def test_missing_required_setup_for_applicable_work_parks():
    result = applicability.decide(
        diff={"files": ["web/app.jsx"]},
        detectors={"frontend": True, "requires_setup": ["baseUrl"]},
        profile={},
    )
    assert result["verdict"] == "park"
    assert "missing required setup" in result["reason"]


def test_cli_decide_prints_verdict_json(tmp_path):
    diff = tmp_path / "diff.json"
    detectors = tmp_path / "detectors.json"
    profile = tmp_path / "profile.json"
    diff.write_text(json.dumps({"files": ["README.md"]}))
    detectors.write_text(json.dumps({"docs_only": True}))
    profile.write_text(json.dumps({}))

    out = subprocess.run(
        [
            sys.executable,
            "plugins/superheroes/lib/test_pilot_applicability_cli.py",
            "decide",
            "--diff-json",
            str(diff),
            "--detectors-json",
            str(detectors),
            "--profile-json",
            str(profile),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout)["verdict"] == "not_applicable"
