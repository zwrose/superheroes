"""CI gate: the committed activation-result.json must be green.

No live model calls — this is a deterministic gate over the already-recorded
observations.  The test:

1.  Loads eval/skills/activation-result.json (observations) and
    eval/skills/baseline.json.
2.  Loads every eval/skills/fixtures/<plugin>__<skill>.json and derives the
    in-scope skill key (<plugin>/<skill>) from the filename.
3.  Builds current_digests from the live SKILL.md files so that a carve-out
    keyed to stale content is exercised honestly.
4.  Scores with activation_score.score() and asserts every verdict is "pass"
    or "carved-out".
5.  Asserts COVERAGE: every fixture skill, and every phrase in each direction,
    has at least one observation in the recorded result — so adding or removing
    a fixture (or a phrase) without re-recording fails CI deterministically.
"""
import glob
import json
import os

import activation_score
import skills as skills_mod

# ---------------------------------------------------------------------------
# Repo root: test file lives at eval/lib/tests/ so go up 3 levels.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))

_RESULT_PATH = os.path.join(_REPO, "eval", "skills", "activation-result.json")
_BASELINE_PATH = os.path.join(_REPO, "eval", "skills", "baseline.json")
_FIXTURES_DIR = os.path.join(_REPO, "eval", "skills", "fixtures")
_PLUGINS_ROOT = os.path.join(_REPO, "plugins")


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_fixtures():
    """Return {skill_key: fixture_dict} keyed by <plugin>/<skill>."""
    result = {}
    for path in glob.glob(os.path.join(_FIXTURES_DIR, "*.json")):
        stem = os.path.splitext(os.path.basename(path))[0]
        key = stem.replace("__", "/")
        result[key] = _load_json(path)
    return result


def _build_current_digests(plugins_root):
    """Return {skill_key: digest} for all SKILL.md files found under plugins_root."""
    digests = {}
    for path in skills_mod.iter_skill_paths(plugins_root):
        parts = path.replace("\\", "/").split("/")
        # path ends with: .../plugins/<plugin>/skills/<skill>/SKILL.md
        skill_name = parts[-2]
        plugin_name = parts[-4]
        key = f"{plugin_name}/{skill_name}"
        description, body = skills_mod.read_skill(path)
        digests[key] = skills_mod.skill_digest(description, body)
    return digests


# ---------------------------------------------------------------------------
# Fixtures loaded once at module import (fast, no IO on test parametrize)
# ---------------------------------------------------------------------------
_result = _load_json(_RESULT_PATH)
_observations = _result["observations"]
assert _observations, "no recorded observations — activation gate would be vacuous"
_baseline = _load_json(_BASELINE_PATH)
_fixtures = _load_fixtures()
assert _fixtures, "no fixtures found — activation gate would be vacuous"
_current_digests = _build_current_digests(_PLUGINS_ROOT)
_verdicts = activation_score.score(_observations, _fixtures, _baseline, _current_digests)
assert _verdicts, "no per-skill verdicts computed — activation gate would be vacuous"

# Pre-compute observation index for coverage checks
_obs_index: set[tuple[str, str, str]] = {
    (o["skill"], o["direction"], o["phrase"])
    for o in _observations
}


def test_every_skill_verdict_is_green():
    """A committed result that contains a 'fail' or 're-run' must break CI."""
    bad = {
        skill: info
        for skill, info in _verdicts.items()
        if info["verdict"] not in ("pass", "carved-out")
    }
    assert not bad, (
        "Recorded activation-result.json has non-green verdicts — re-run the "
        f"eval harness and commit a fresh result.  Failing skills: {bad}"
    )


def test_coverage_every_fixture_skill_has_observations():
    """Every fixture skill must appear at least once in the recorded observations."""
    observed_skills = {o["skill"] for o in _observations}
    missing = {skill for skill in _fixtures if skill not in observed_skills}
    assert not missing, (
        "These fixture skills have NO observations in activation-result.json — "
        f"re-run the eval harness: {sorted(missing)}"
    )


def test_coverage_every_fixture_phrase_has_observations():
    """Every phrase (in every direction) for every fixture skill must be observed."""
    missing = []
    for skill, fx in _fixtures.items():
        for direction in ("should_fire", "should_not_fire"):
            for phrase in fx.get(direction, []):
                if (skill, direction, phrase) not in _obs_index:
                    missing.append(f"{skill}:{direction}:{phrase!r}")
    assert not missing, (
        "These fixture phrases have NO observations in activation-result.json — "
        "add/remove of a phrase or fixture without re-recording the eval result "
        f"now fails CI: {missing}"
    )
