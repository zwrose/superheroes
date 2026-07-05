import importlib.util, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = os.path.join(_HERE, "..", "classify_release.py")
_spec = importlib.util.spec_from_file_location("classify_release", _M)
CR = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(CR)


# --- spine axis ---------------------------------------------------------------------------

def test_bundle_change_is_spine_carrying():
    r = CR.classify(["plugins/superheroes/lib/showrunner.bundle.js"])
    assert r["class"] == "spine-carrying"
    assert r["owed"] == ["acceptance"]
    assert r["spine"] and not r["reviewer"]

def test_spine_entry_and_bundler_are_spine():
    for p in ("plugins/superheroes/lib/showrunner.js",
              "plugins/superheroes/lib/bundle_showrunner.js"):
        assert CR.classify([p])["spine"], p

def test_loop_machinery_is_spine():
    for p in ("plugins/superheroes/lib/loop_state.js",
              "plugins/superheroes/lib/loop_synthesis.py",
              "plugins/superheroes/lib/ci_loop.py",
              "plugins/superheroes/lib/review_loop_plan.py"):
        assert CR.classify([p])["spine"], p

def test_phase_machinery_is_spine():
    for p in ("plugins/superheroes/lib/phase_step.js",
              "plugins/superheroes/lib/ship_phase.py",
              "plugins/superheroes/lib/build_phase.js"):
        assert CR.classify([p])["spine"], p

def test_review_round_policy_is_spine():
    assert CR.classify(["plugins/superheroes/lib/review_round_policy.js"])["spine"]
    assert CR.classify(["plugins/superheroes/lib/review_round_policy.py"])["spine"]


# --- reviewer axis ------------------------------------------------------------------------

def test_reviewer_agent_is_reviewer_touching():
    r = CR.classify(["plugins/superheroes/agents/code-reviewer.md"])
    assert r["class"] == "reviewer-touching"
    assert r["owed"] == ["benchmark"]
    assert r["reviewer"] and not r["spine"]

def test_rubric_change_is_reviewer_touching():
    assert CR.classify(["plugins/superheroes/rubric/review-base.md"])["reviewer"]

def test_non_reviewer_agent_is_not_reviewer():
    # a non-reviewer agent (e.g. courier) does not touch a reviewer seat
    r = CR.classify(["plugins/superheroes/agents/courier.md"])
    assert not r["reviewer"]
    assert r["class"] == "neither"


# --- both / neither -----------------------------------------------------------------------

def test_both_axes():
    r = CR.classify([
        "plugins/superheroes/lib/showrunner.bundle.js",
        "plugins/superheroes/rubric/review-base.md",
    ])
    assert r["class"] == "spine-carrying+reviewer-touching"
    assert r["owed"] == ["acceptance", "benchmark"]  # stable order: spine then reviewer

def test_docs_only_is_neither():
    r = CR.classify(["README.md", "RELEASING.md", "docs/plan.md",
                     "plugins/superheroes/skills/showrunner/SKILL.md"])
    assert r["class"] == "neither"
    assert r["owed"] == []

def test_version_bump_files_are_neither():
    # a release-please PR's own diff is only these — must not by itself owe anything
    r = CR.classify([
        "CHANGELOG.md",
        "version.txt",
        "plugins/superheroes/.claude-plugin/plugin.json",
        "plugins/superheroes/.codex-plugin/plugin.json",
        ".release-please-manifest.json",
    ])
    assert r["class"] == "neither"

def test_empty_and_none_are_neither():
    assert CR.classify([])["class"] == "neither"
    assert CR.classify(None)["class"] == "neither"

def test_unrelated_lib_change_is_neither():
    # a lib change outside the spine globs (e.g. a test-pilot seed helper) owes nothing
    r = CR.classify(["plugins/superheroes/lib/test_pilot_seed.py"])
    assert r["class"] == "neither"


# --- hits are surfaced for the readout ----------------------------------------------------

def test_hits_recorded_and_sorted():
    r = CR.classify([
        "plugins/superheroes/lib/showrunner.bundle.js",
        "plugins/superheroes/lib/loop_state.js",
        "plugins/superheroes/agents/security-reviewer.md",
    ])
    assert r["spine_hits"] == [
        "plugins/superheroes/lib/loop_state.js",
        "plugins/superheroes/lib/showrunner.bundle.js",
    ]
    assert r["reviewer_hits"] == ["plugins/superheroes/agents/security-reviewer.md"]


# --- commands -----------------------------------------------------------------------------

def test_commands_cover_owed_instruments():
    cmds = CR.instrument_commands()
    assert "acceptance" in cmds and "benchmark" in cmds
    assert "--spine-lib" in cmds["acceptance"]
    assert "acceptance_run.py" in cmds["acceptance"]
    assert "RESULTS.md" in cmds["benchmark"]
