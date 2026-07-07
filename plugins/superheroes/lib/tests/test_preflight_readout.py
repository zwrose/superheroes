import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight_readout


def _claude_prefs():
    return {"reviewer": "claude", "implementation": "claude", "effort": {}}


def test_roster_phase_set_equals_spine_PHASES():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    phases = []
    for r in rows:
        if r["phase"] not in phases:
            phases.append(r["phase"])
    assert phases == list(preflight_readout.PHASES)  # PHASES imported from the spine roster


def test_build_phase_yields_four_roles():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    build = [r for r in rows if r["phase"] == "workhorse"]
    kinds = [r["kind"] for r in build]
    assert kinds == ["build", "review", "fix", "review-deep"]  # builder, per-task reviewer, fixer, final reviewer


def test_each_row_carries_engine_model_effort():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    for r in rows:
        assert set(("phase", "role", "roleLabel", "engine", "model", "effort", "kind",
                    "configuredOrDefault")) <= set(r)


def test_unconfigured_role_labeled_default_configured_role_labeled_configured():
    # FR-5 second criterion: an empty tier-override map -> every row is a "default"; an explicit
    # per-role override -> that row is "configured".
    default_rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    assert all(r["configuredOrDefault"] == "default" for r in default_rows)
    configured_rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {"reviewer": "opus"})
    rev = [r for r in configured_rows if r["role"] == "reviewer"][0]
    assert rev["configuredOrDefault"] == "configured"
    author = [r for r in configured_rows if r["role"] == "author"][0]
    assert author["configuredOrDefault"] == "default"


def test_claude_prefs_yield_claude_engine_and_none_effort():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    for r in rows:
        if r["kind"] != "orchestration":
            assert r["engine"] == "claude"
            assert r["effort"] is None  # engine_pref.resolve_effort returns None for claude


def test_orchestration_role_inherits_session_model():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    orch = [r for r in rows if r["kind"] == "orchestration"]
    assert len(orch) == 1
    assert orch[0]["model"] is None  # inherit
