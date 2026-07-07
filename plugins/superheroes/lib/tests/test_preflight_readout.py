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


# --- Task 4: assemble — compose the snapshot from the real readers (FR-4/5/6/7, UFR-2/3) ---

def _fake_readers(**over):
    base = {
        "prefs": {"reviewer": "claude", "implementation": "claude", "effort": {}},
        "tier_overrides": {},
        "authz": {"codex": {"installed": True, "authed": True, "error": None},
                  "cursor": {"installed": True, "authed": True, "error": None}},
        "calibration": {"status": "provisional"},
        "verify": "npm test",
        "storage": {"mode": "global", "docsPath": "/proj/docs"},
    }
    base.update(over)
    return base


def test_assemble_returns_snapshot_shape():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers())
    for key in ("workItem", "phases", "externalEngines", "calibration",
                "verify", "storage", "degraded", "version"):
        assert key in snap
    assert snap["version"] == preflight_readout.READOUT_VERSION


def test_provisional_calibration_flagged():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers())
    assert snap["calibration"]["provisional"] is True


def test_unverified_when_command_is_none():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers(verify="none"))
    assert snap["verify"]["command"] in ("none", None)


def test_storage_mode_and_docs_path_present():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers())
    assert snap["storage"]["mode"] == "global"
    assert snap["storage"]["docsPath"] == "/proj/docs"


def test_external_engine_authorization_reported():
    readers = _fake_readers(prefs={"reviewer": "codex", "implementation": "claude", "effort": {}},
                            authz={"codex": {"installed": True, "authed": False, "error": None},
                                   "cursor": {"installed": False, "authed": False, "error": None}})
    snap = preflight_readout.assemble("wi", "/root", readers=readers)
    assert snap["externalEngines"]["codex"]["authorized"] is False
    # a role whose engine is unauthorized is flagged fallbackToClaude
    review = [r for r in snap["phases"] if r["kind"] == "review"][0]
    assert review.get("fallbackToClaude") is True


def test_one_field_error_degrades_not_fails(monkeypatch=None):
    readers = _fake_readers(storage=preflight_readout._RAISE)  # sentinel: this reader raises
    snap = preflight_readout.assemble("wi", "/root", readers=readers)
    assert any(d for d in snap["degraded"] if d.get("field") == "storage")
    assert snap["storage"].get("unavailable") is True


def test_total_failure_returns_failure_sentinel():
    snap = preflight_readout.assemble("wi", "/root", readers=None, _force_total_failure=True)
    assert snap.get("ok") is False and snap.get("reason")


# --- Task 5: Apply run overrides + re-validate on relaunch (FR-11, FR-14, UFR-5) ---


def test_override_marks_row_and_takes_value():
    ro = {"reviewer": {"engine": "codex", "effort": "xhigh"}}
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    rev = [r for r in rows if r["role"] == "reviewer" and r["phase"] == "review-plan"][0]
    assert rev["engine"] == "codex" and rev["effort"] == "xhigh"
    assert rev["overridden"] is True


def test_non_overridden_rows_unchanged():
    ro = {"reviewer": {"engine": "codex"}}
    base = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    with_ov = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    author_base = [r for r in base if r["phase"] == "plan"][0]
    author_ov = [r for r in with_ov if r["phase"] == "plan"][0]
    assert author_base == author_ov  # no override on author -> byte-identical


def test_unrecognized_engine_marked_not_dropped():
    ro = {"reviewer": {"engine": "quantum"}}  # not in ENGINES
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    rev = [r for r in rows if r["role"] == "reviewer" and r["phase"] == "review-plan"][0]
    assert rev["engine"] == "quantum" and rev.get("unrecognized") is True


def test_reapply_revalidate_flags_now_invalid_override():
    # a recorded override that is no longer a valid option is flagged, not silently applied (FR-14)
    ro = {"reviewer": {"model": "gpt5"}}  # not in KNOWN_MODELS
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    rev = [r for r in rows if r["role"] == "reviewer" and r["phase"] == "review-plan"][0]
    assert rev.get("overrideInvalid") is True


# --- Task 6: UFR-4 — flag an unexpected inherit (a non-orchestration role that resolves to None) ---

def test_non_orchestration_none_model_flagged_unexpected():
    # a tier override that maps a normal role to None (session inherit) must be shown flagged
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {"author": None})
    author = [r for r in rows if r["role"] == "author"][0]
    assert author["model"] is None
    assert author.get("unexpectedInherit") is True


def test_orchestration_none_is_not_unexpected():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    orch = [r for r in rows if r["kind"] == "orchestration"][0]
    assert orch["model"] is None
    assert not orch.get("unexpectedInherit")


# --- Task 7: The JSON CLI (main) — the verified interface the skill shells (FR-1 plumbing, UFR-3) ---

import io, json, contextlib


def _run_cli(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = preflight_readout.main(argv)
    return code, buf.getvalue()


def test_cli_assemble_emits_snapshot_json_exit_0_even_when_degraded(tmp_path):
    # a real assemble over an empty root degrades fields but must still exit 0 with a snapshot
    code, out = _run_cli(["assemble", "--work-item", "wi", "--root", str(tmp_path)])
    obj = json.loads(out)
    assert code == 0
    assert "phases" in obj  # a snapshot, not a total-failure sentinel


def test_cli_validate_override_emits_verdict():
    code, out = _run_cli(["validate-override", "--role", "reviewer",
                          "--field", "engine", "--value", "gpt"])
    obj = json.loads(out)
    assert obj["ok"] is False and "acceptedValues" in obj


# --- Task 12: End-to-end assemble->render golden test + the <=40-line bound under a full
# external pipeline ---

def test_full_external_pipeline_render_within_bound_and_complete():
    readers = _fake_readers(
        prefs={"reviewer": "codex", "implementation": "cursor", "effort": {"review": "high"}},
        authz={"codex": {"installed": True, "authed": True, "error": None},
               "cursor": {"installed": True, "authed": False, "error": None}},
        calibration={"status": "provisional"}, verify="npm test",
        storage={"mode": "global", "docsPath": "/proj/docs"})
    snap = preflight_readout.assemble("wi", "/root", readers=readers)
    text = preflight_readout.render(snap)
    lines = text.splitlines()
    assert len(lines) <= 40                       # NFR scannability
    assert "provisional" in text                  # FR-5
    assert "npm test" in text                      # FR-6
    assert "global" in text and "/proj/docs" in text  # FR-7
    assert "External engines" in text              # FR-4
    # cursor unauthorized -> the affected phase ROW itself shows the fallback flag (FR-4,
    # premortem-001), not merely the External-engines summary line.
    assert "falls back to Claude" in text
    builder = [r for r in snap["phases"] if r["kind"] == "build"][0]
    assert builder.get("fallbackToClaude") is True
    # and the whole-run summary line still names the unauthorized engine
    assert "NOT authorized" in text
