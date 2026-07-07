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


# --- Task 2: the engine->model display rule + render (FR-2, NFR scannability) ---

def test_display_model_maps_external_engines():
    assert preflight_readout.display_model("codex", "sonnet") == "gpt-5.5"
    # cursor honors the SAME per-tier map build_argv uses: an unmapped tier shows the pinned default,
    # a mapped tier (today only fable/opus via _CURSOR_MODEL_BY_TIER) shows its resolved cursor id.
    assert preflight_readout.display_model("cursor", "sonnet") == "composer-2.5-fast"
    assert preflight_readout.display_model("cursor", None) == "composer-2.5-fast"
    assert preflight_readout.display_model("cursor", "fable") == "claude-fable-5-thinking-xhigh"
    assert preflight_readout.display_model("cursor", "opus") == "claude-opus-4-8-thinking-high"
    assert preflight_readout.display_model("claude", "opus") == "opus"
    assert preflight_readout.display_model("claude", None) == "inherit"


def _snapshot_default():
    # a minimal well-formed snapshot for the default claude pipeline (Task 4 shape)
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    return {"workItem": "wi", "phases": rows,
            "externalEngines": {}, "calibration": {"status": "confirmed", "provisional": False},
            "verify": {"command": "npm test"}, "storage": {"mode": "global", "docsPath": "/p/docs"},
            "degraded": [], "version": preflight_readout.READOUT_VERSION}


def test_render_is_str_and_names_every_phase():
    text = preflight_readout.render(_snapshot_default())
    assert isinstance(text, str)
    for phase in ("plan", "review-plan", "tasks", "review-tasks", "workhorse",
                  "review-code", "test-pilot", "ship"):
        assert phase in text


def test_render_orchestration_marked_expected():
    text = preflight_readout.render(_snapshot_default())
    assert "inherits session model" in text and "expected" in text


def test_render_default_pipeline_one_engine_is_at_most_40_lines():
    snap = _snapshot_default()
    snap["externalEngines"] = {"codex": {"authorized": True}}
    text = preflight_readout.render(snap)
    assert len([ln for ln in text.splitlines()]) <= 40


def test_render_shows_fallback_to_claude_flag_on_the_row():
    # FR-4 (premortem-001): a role whose engine is unauthorized is flagged on ITS OWN phase row
    # in render(), not only in the External-engines summary line.
    snap = _snapshot_default()
    snap["phases"][1]["fallbackToClaude"] = True  # a review row
    text = preflight_readout.render(snap)
    assert "falls back to Claude" in text


def test_render_shows_override_invalid_flag_on_the_row():
    # FR-14 (premortem-001): a recorded override that is no longer valid is shown flagged on its
    # row, not silently applied — asserted against render()'s actual output.
    snap = _snapshot_default()
    snap["phases"][1]["overrideInvalid"] = True
    text = preflight_readout.render(snap)
    assert "no longer valid" in text


def test_render_labels_a_default_row():
    # FR-5 second criterion: a row that fell back to a built-in default is labeled [default].
    snap = _snapshot_default()
    snap["phases"][0]["configuredOrDefault"] = "default"
    text = preflight_readout.render(snap)
    assert "[default]" in text


# --- Task 3: validate_override — the pure override gate (FR-10, UFR-6) ---

def _rows_by_role():
    return {r["role"]: r for r in preflight_readout.enumerate_dispatch(_claude_prefs(), {})}


def test_valid_engine_override_accepted():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "engine", "codex", snap)
    assert out["ok"] is True and out["accepted"] == "codex"


def test_invalid_engine_rejected_with_accepted_values():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "engine", "gpt", snap)
    assert out["ok"] is False
    assert set(out["acceptedValues"]) == set(preflight_readout.preflight_readout_engines())  # engine_pref.ENGINES


def test_invalid_model_rejected_with_accepted_values():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "model", "gpt5", snap)
    assert out["ok"] is False
    assert "sonnet" in out["acceptedValues"] and "opus" in out["acceptedValues"]


def test_orchestration_role_is_not_overridable():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("orchestrator", "model", "opus", snap)
    assert out["ok"] is False and "orchestration" in out["reason"].lower()


def test_effort_override_valid_for_codex():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "effort", "xhigh", snap)
    assert out["ok"] is True and out["accepted"] == "xhigh"


def test_unknown_field_rejected():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "storage", "x", snap)
    assert out["ok"] is False
