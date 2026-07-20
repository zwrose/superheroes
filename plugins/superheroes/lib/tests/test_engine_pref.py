import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_pref", os.path.join(_HERE, "..", "engine_pref.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EP = _load()


def test_resolve_engine_maps_role_to_key():
    prefs = {"reviewer": "codex", "implementation": "cursor"}
    assert EP.resolve_engine("review", prefs) == "codex"
    assert EP.resolve_engine("build", prefs) == "cursor"
    assert EP.resolve_engine("fix", prefs) == "cursor"   # fix follows implementation


def test_resolve_engine_mixed_reviewer_ne_implementation():
    prefs = {"reviewer": "codex", "implementation": "cursor"}
    assert EP.resolve_engine("review", prefs) == "codex"
    assert EP.resolve_engine("build", prefs) == "cursor"


def test_resolve_engine_falls_open_to_claude():
    assert EP.resolve_engine("review", {}) == "claude"                    # absent key
    assert EP.resolve_engine("review", {"reviewer": "bogus"}) == "claude" # unknown engine
    assert EP.resolve_engine("review", {"reviewer": 7}) == "claude"        # non-str
    assert EP.resolve_engine("review", "not-a-dict") == "claude"           # non-dict prefs
    assert EP.resolve_engine("review", None) == "claude"
    assert EP.resolve_engine("bogus-role", {"reviewer": "codex"}) == "claude"  # unknown role


def test_resolve_effort_defaults():
    assert EP.resolve_effort("codex", "review") == "high"
    assert EP.resolve_effort("codex", "review-deep") == "xhigh"   # deep reviewers (security/architecture)
    assert EP.resolve_effort("codex", "build") == "high"
    assert EP.resolve_effort("codex", "fix") == "high"
    assert EP.resolve_effort("cursor", "review") == "composer"
    assert EP.resolve_effort("cursor", "fix") == "composer"
    assert EP.resolve_effort("claude", "build") is None
    assert EP.resolve_effort("bogus", "build") is None   # unknown engine → None


def test_resolve_effort_override_wins_else_default():
    assert EP.resolve_effort("codex", "review", {"review": "medium"}) == "medium"
    assert EP.resolve_effort("codex", "review-deep", {"review-deep": "high"}) == "high"  # deep override wins
    assert EP.resolve_effort("codex", "review-deep") == "xhigh"                          # deep default
    assert EP.resolve_effort("codex", "review", {"review": ""}) == "high"    # empty → default
    assert EP.resolve_effort("codex", "review", {"review": 7}) == "high"      # non-str → default
    assert EP.resolve_effort("codex", "review", "not-a-dict") == "high"
    assert EP.resolve_effort("codex", "review", ["review"]) == "high"         # list (non-dict) → default


def test_resolve_engine_brief_check_defaults_to_codex():
    # The ratified cross-vendor pre-code check: brief-check fails open to codex, not claude.
    assert EP.resolve_engine("brief-check", {}) == "codex"
    assert EP.resolve_engine("brief-check", {"briefCheck": "cursor"}) == "cursor"
    assert EP.resolve_engine("brief-check", {"briefCheck": "bogus"}) == "codex"   # invalid -> default
    assert EP.resolve_engine("brief-check", {"briefCheck": "claude"}) == "claude"  # disclosed degrade


def test_resolve_engine_pilot_fails_open_to_claude():
    assert EP.resolve_engine("pilot", {}) == "claude"
    assert EP.resolve_engine("pilot", {"pilot": "codex"}) == "codex"


def test_resolve_engine_build_unchanged_no_regression():
    assert EP.resolve_engine("build", {}) == "claude"
    assert EP.resolve_engine("bogus-role", {}) == "claude"   # unknown role_kind still returns claude


def test_engine_role_keys_schema():
    assert EP.ENGINE_ROLE_KEYS == ("reviewer", "implementation", "briefCheck", "pilot")
    assert "orchestrator" not in EP.ENGINE_ROLE_KEYS
    assert "planAuthor" not in EP.ENGINE_ROLE_KEYS


def test_engine_role_keys_are_all_surfaced_by_loader():
    # ARCH-2: ENGINE_ROLE_KEYS is the single home the §11 drift guard reads; the loader's
    # degenerate (absent-block) dict must carry every one of them, else a role key added to the
    # schema home that the loader forgets to surface would silently vanish from load_engine_prefs.
    degenerate = EP.load_engine_prefs("/nonexistent/xyz")
    assert set(EP.ENGINE_ROLE_KEYS) <= set(degenerate.keys())


def test_implementer_and_pilot_are_codex_pin_roles():
    assert "implementer" in EP.CODEX_PIN_ROLES
    assert "pilot" in EP.CODEX_PIN_ROLES


def test_codex_model_pin_on_implementer():
    assert EP.resolve_engine_model("codex", "implementer", "sonnet",
                                   {"codexModels": {"implementer": "gpt-5.6-terra"}}) == "gpt-5.6-terra"


def test_load_engine_prefs_surfaces_brief_check_and_pilot_keys(tmp_path):
    # On an absent enginePreferences block, briefCheck and pilot normalize to claude alongside
    # the existing keys (raw normalization; resolve_engine applies the codex default at read time).
    got = EP.load_engine_prefs(str(tmp_path), root=str(tmp_path / "store"))
    assert got["briefCheck"] == "claude"
    assert got["pilot"] == "claude"
    assert got["reviewer"] == "claude"
    assert got["implementation"] == "claude"


def test_brief_check_claude_fallback_tier_is_opus():
    assert EP.BRIEF_CHECK_CLAUDE_FALLBACK_TIER == "opus"


def test_resolve_engine_model_maps_shared_tiers_to_gpt_5_6_family():
    assert EP.resolve_engine_model("codex", "mechanical", "haiku", {}) == "gpt-5.6-terra"
    assert EP.resolve_engine_model("codex", "reviewer", "sonnet", {}) == "gpt-5.6-terra"
    assert EP.resolve_engine_model("codex", "reviewer-deep", "opus", {}) == "gpt-5.6-sol"
    assert EP.resolve_engine_model("codex", "implementer", "fable", {}) is None


def test_resolve_engine_model_persistent_codex_pin_wins_per_role():
    prefs = {"codexModels": {"reviewer": "gpt-5.6-terra", "implementer": "gpt-5.6-terra"}}
    assert EP.resolve_engine_model("codex", "reviewer", "sonnet", prefs) == "gpt-5.6-terra"
    assert EP.resolve_engine_model("codex", "implementer", "opus", prefs) == "gpt-5.6-terra"
    # A sibling role still derives from its tier; pins never become global.
    assert EP.resolve_engine_model("codex", "reviewer-deep", "opus", prefs) == "gpt-5.6-sol"


def test_resolve_engine_model_is_provider_isolated_and_fails_capable():
    prefs = {"codexModels": {"reviewer": "gpt-5.6-terra"}}
    assert EP.resolve_engine_model("claude", "reviewer", "sonnet", prefs) is None
    assert EP.resolve_engine_model("cursor", "reviewer", "sonnet", prefs) is None
    assert EP.resolve_engine_model("codex", "reviewer", "experimental-tier", {}) == "gpt-5.6-sol"
    assert EP.resolve_engine_model("codex", "reviewer", "sonnet",
                                   {"codexModels": {"reviewer": "not-a-model"}}) == "gpt-5.6-terra"


def test_codex_model_effort_validation_keeps_max_opt_in_and_5_6_only():
    assert EP.valid_codex_model_effort("gpt-5.6-sol", "max") is True
    assert EP.valid_codex_model_effort("gpt-5.6-terra", "max") is True
    assert EP.valid_codex_model_effort("gpt-5.6-luna", "max") is False
    assert EP.valid_codex_model_effort("gpt-5.5", "xhigh") is False
    assert EP.valid_codex_model_effort("gpt-5.5", "max") is False
    assert EP.valid_codex_model_effort("not-a-model", "high") is False


def test_resolve_timeout_default_and_override():
    # Legacy back-compat: NO role supplied -> the finite 300s default (engine_authz probe path).
    assert EP.resolve_timeout() == EP.DEFAULT_STALL_LIMIT_SECONDS == 300
    assert EP.resolve_timeout({"timeout": 5}) == 5
    assert EP.resolve_timeout({"timeout": 0}) == 300       # non-positive → default
    assert EP.resolve_timeout({"timeout": -1}) == 300
    assert EP.resolve_timeout({"timeout": "5"}) == 300      # non-int → default
    assert EP.resolve_timeout("not-a-dict") == 300


def test_resolve_timeout_role_ceilings():
    # #309: write roles get the HIGH ceiling, read roles the moderate one (owner policy: high
    # ceilings, never borderline limits). These are the values the production dispatch sites pass.
    for role in ("build", "fix"):
        assert EP.resolve_timeout(None, role) == EP.WRITE_TIMEOUT_SECONDS == 2400
    for role in ("review", "review-deep"):
        assert EP.resolve_timeout(None, role) == EP.READ_TIMEOUT_SECONDS == 900
    # An unknown role falls to the legacy default (never a borderline surprise).
    assert EP.resolve_timeout(None, "mechanical") == 300


def test_resolve_timeout_owner_override_wins_over_role_ceiling():
    # The owner `timeout` override (the UFR-5 channel) beats the role ceiling at real dispatch —
    # BOTH higher and lower than the ceiling, so a project can raise OR tighten it deliberately.
    assert EP.resolve_timeout({"timeout": 3600}, "build") == 3600
    assert EP.resolve_timeout({"timeout": 120}, "review") == 120
    # A malformed override does NOT leak past — it falls back to the role ceiling, not the 300 default.
    assert EP.resolve_timeout({"timeout": 0}, "build") == 2400
    assert EP.resolve_timeout({"timeout": True}, "build") == 2400   # bool rejected, ceiling stands


def test_load_engine_prefs_surfaces_positive_timeout_override(tmp_path, monkeypatch):
    # #309 owner channel end to end: a positive-int enginePreferences.timeout is surfaced by
    # load_engine_prefs so resolve_timeout(prefs, role) honors it; a bool/non-positive is dropped.
    import core_md
    monkeypatch.setattr(core_md, "read", lambda *a, **k: {"enginePreferences": {"timeout": 1800}})
    prefs = EP.load_engine_prefs(str(tmp_path))
    assert prefs.get("timeout") == 1800
    assert EP.resolve_timeout(prefs, "review") == 1800
    monkeypatch.setattr(core_md, "read", lambda *a, **k: {"enginePreferences": {"timeout": True}})
    assert "timeout" not in EP.load_engine_prefs(str(tmp_path))
    monkeypatch.setattr(core_md, "read", lambda *a, **k: {"enginePreferences": {}})
    assert "timeout" not in EP.load_engine_prefs(str(tmp_path))


def test_resolve_idle_role_windows_and_default():
    # #309 the stall-monitor half of the ceiling+monitor pair. WRITE roles get the longer idle window,
    # READ roles the shorter; both under their role ceiling (monitor ≤ ceiling). These are the values
    # the production dispatch sites pass alongside resolve_timeout.
    for role in ("build", "fix"):
        assert EP.resolve_idle(None, role) == EP.WRITE_IDLE_SECONDS == 600
        assert EP.resolve_idle(None, role) < EP.resolve_timeout(None, role)   # monitor < ceiling
    for role in ("review", "review-deep"):
        assert EP.resolve_idle(None, role) == EP.READ_IDLE_SECONDS == 300
        assert EP.resolve_idle(None, role) < EP.resolve_timeout(None, role)
    # No role / unknown role -> the conservative default idle window.
    assert EP.resolve_idle() == EP.DEFAULT_IDLE_SECONDS == 300
    assert EP.resolve_idle(None, "mechanical") == 300


def test_resolve_idle_owner_override_wins_over_role_window():
    # The owner `idleTimeout` override beats the role window at dispatch (same guard shape as `timeout`).
    assert EP.resolve_idle({"idleTimeout": 45}, "build") == 45
    assert EP.resolve_idle({"idleTimeout": 120}, "review") == 120
    # A malformed override falls back to the role window (never leaks past), and bool is rejected.
    assert EP.resolve_idle({"idleTimeout": 0}, "build") == 600
    assert EP.resolve_idle({"idleTimeout": -5}, "build") == 600
    assert EP.resolve_idle({"idleTimeout": "60"}, "build") == 600
    assert EP.resolve_idle({"idleTimeout": True}, "review") == 300
    assert EP.resolve_idle("not-a-dict") == 300


def test_load_engine_prefs_surfaces_positive_idle_override(tmp_path, monkeypatch):
    # #309 owner stall-monitor channel end to end: a positive-int enginePreferences.idleTimeout is
    # surfaced by load_engine_prefs so resolve_idle(prefs, role) honors it; a bool/non-positive is dropped.
    import core_md
    monkeypatch.setattr(core_md, "read", lambda *a, **k: {"enginePreferences": {"idleTimeout": 90}})
    prefs = EP.load_engine_prefs(str(tmp_path))
    assert prefs.get("idleTimeout") == 90
    assert EP.resolve_idle(prefs, "review") == 90
    monkeypatch.setattr(core_md, "read", lambda *a, **k: {"enginePreferences": {"idleTimeout": True}})
    assert "idleTimeout" not in EP.load_engine_prefs(str(tmp_path))
    monkeypatch.setattr(core_md, "read", lambda *a, **k: {"enginePreferences": {"idleTimeout": -1}})
    assert "idleTimeout" not in EP.load_engine_prefs(str(tmp_path))


def test_dispatch_calibration_rows_codex_implementer_reports_gpt_model_not_claude_tier():
    # Fix A: honest per-engine provenance — a codex implementer reports the RESOLVED Codex model
    # (the sonnet->GPT tier map), never the Claude tier it would show if engine were ignored.
    rows = EP.dispatch_calibration_rows(
        {"implementation": "codex"},
        {"implementer": "sonnet", "pilot": "sonnet", "reviewer": "sonnet", "reviewer-deep": "opus"})
    by_role = {r["role"]: r for r in rows}
    assert by_role["implementer"]["engine"] == "codex"
    assert by_role["implementer"]["model"] == "gpt-5.6-terra"


def test_dispatch_calibration_rows_codex_implementer_honors_persistent_pin():
    rows = EP.dispatch_calibration_rows(
        {"implementation": "codex", "codexModels": {"implementer": "gpt-5.6-sol"}},
        {"implementer": "sonnet", "pilot": "sonnet", "reviewer": "sonnet", "reviewer-deep": "opus"})
    by_role = {r["role"]: r for r in rows}
    assert by_role["implementer"]["model"] == "gpt-5.6-sol"


def test_dispatch_calibration_rows_cursor_implementer_reports_composer_literal():
    rows = EP.dispatch_calibration_rows(
        {"implementation": "cursor"},
        {"implementer": "sonnet", "pilot": "sonnet", "reviewer": "sonnet", "reviewer-deep": "opus"})
    by_role = {r["role"]: r for r in rows}
    assert by_role["implementer"]["model"] == "(cursor composer)"


def test_dispatch_calibration_rows_claude_implementer_unchanged():
    rows = EP.dispatch_calibration_rows(
        {},
        {"implementer": "sonnet", "pilot": "sonnet", "reviewer": "sonnet", "reviewer-deep": "opus"})
    by_role = {r["role"]: r for r in rows}
    assert by_role["implementer"]["engine"] == "claude"
    assert by_role["implementer"]["model"] == "sonnet"


def test_dispatch_calibration_rows_brief_check_reports_effective_provider_model():
    # Fix 1: the brief-check row is no longer special-cased to "(engine default)" — it routes
    # through the SAME _effective_model helper as the other rows, so codex/cursor show the real
    # provider model instead of a placeholder.
    tiers = {"implementer": "sonnet", "pilot": "sonnet", "reviewer": "sonnet", "reviewer-deep": "opus"}
    rows = EP.dispatch_calibration_rows({"briefCheck": "codex"}, tiers)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "codex"
    assert by_role["brief-check"]["model"] == "gpt-5.6-sol"   # opus-tier codex peer

    rows = EP.dispatch_calibration_rows({"briefCheck": "cursor"}, tiers)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "cursor"
    assert by_role["brief-check"]["model"] == "(cursor composer)"

    # {} -> brief-check fails open to its codex default (see _ROLE_DEFAULT_ENGINE)
    rows = EP.dispatch_calibration_rows({}, tiers)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "codex"
    assert by_role["brief-check"]["model"] == "gpt-5.6-sol"

    # explicit claude fallback is unchanged: the opus tier literal
    rows = EP.dispatch_calibration_rows({"briefCheck": "claude"}, tiers)
    by_role = {r["role"]: r for r in rows}
    assert by_role["brief-check"]["engine"] == "claude"
    assert by_role["brief-check"]["model"] == "opus"


def test_never_raises_on_garbage():
    assert EP.resolve_engine(None, None) == "claude"
    assert EP.resolve_effort(None, None, None) is None
    assert EP.resolve_timeout(None) == 300
    assert EP.resolve_idle(None) == 300


import subprocess
import sys

_LIB = os.path.join(_HERE, "..")


def _write_core_with_prefs_at(repo, store, prefs):
    import importlib.util as _u
    spec = _u.spec_from_file_location("core_md", os.path.join(_LIB, "core_md.py"))
    cm = _u.module_from_spec(spec)
    spec.loader.exec_module(cm)
    cm.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                    "patterns": "", "enginePreferences": prefs}, "confirmed",
             root=store, now="2026-06-30")


def _write_core_with_prefs(repo, prefs):
    _write_core_with_prefs_at(repo, os.path.join(repo, "store"), prefs)


def test_load_engine_prefs_reads_core_md(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "cursor"})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert got == {"reviewer": "codex", "implementation": "cursor",
                   "briefCheck": "claude", "pilot": "claude", "effort": {}}


def test_load_engine_prefs_absent_is_both_claude(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {})   # core.md exists but no engine prefs
    assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store")) == \
        {"reviewer": "claude", "implementation": "claude",
         "briefCheck": "claude", "pilot": "claude", "effort": {}}


def test_load_engine_prefs_greenfield_is_both_claude(tmp_path):
    # no core.md at all → both claude (fail-open, never raises)
    assert EP.load_engine_prefs(str(tmp_path), root=str(tmp_path / "store")) == \
        {"reviewer": "claude", "implementation": "claude",
         "briefCheck": "claude", "pilot": "claude", "effort": {}}


def test_load_engine_prefs_store_base_none_vs_repo_root_regression(tmp_path, monkeypatch):
    """#221 regression: the startup gather passed the repo ROOT into load_engine_prefs's SECOND arg —
    the store-base override (the ~/.claude/superheroes test seam) — instead of None. For an OUT-OF-REPO
    core.md that resolves core.md to a nonexistent <repo>/projects/<key>/config/core.md, so the deliberate
    fail-open silently degraded EVERY run to all-claude. This pins BOTH sides of the fix: store-base=None
    (the default store, via the SUPERHEROES_STORE_ROOT seam) round-trips the owner's prefs, while passing
    the repo root degrades to all-claude. A fresh repo with no calibration evidence resolves to GLOBAL
    (out-of-repo) mode, so the write lands in the store — the copy only reachable via the default store."""
    repo = str(tmp_path / "repo")
    store = str(tmp_path / "store")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    _write_core_with_prefs_at(repo, store, {"reviewer": "codex", "implementation": "cursor"})
    # The FIXED gather call: store-base=None -> the default store (the env seam) -> round-trips.
    fixed = EP.load_engine_prefs(repo, None)
    assert (fixed["reviewer"], fixed["implementation"]) == ("codex", "cursor")
    # The BUG: the repo root in the store-base slot -> <repo>/projects/<key>/config/core.md (absent) ->
    # OSError -> the fail-open degenerate all-claude map.
    degraded = EP.load_engine_prefs(repo, repo)
    assert (degraded["reviewer"], degraded["implementation"]) == ("claude", "claude")


def test_load_engine_prefs_normalizes_bad_values(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "bogus", "implementation": "cursor"})
    assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store")) == \
        {"reviewer": "claude", "implementation": "cursor",
         "briefCheck": "claude", "pilot": "claude", "effort": {}}


def test_load_engine_prefs_surfaces_effort_submap_and_resolve_effort_honors_it(tmp_path):
    # FR-9 round-trip: an effort override written into core.md's enginePreferences.effort is
    # surfaced by load_engine_prefs and honored by resolve_effort keyed by role_kind.
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                  "effort": {"review": "medium", "fix": "high"}})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert got["effort"] == {"review": "medium", "fix": "high"}
    # resolve_effort keyed by role_kind reads THIS effort sub-map (not the model-tier overrides).
    assert EP.resolve_effort("codex", "review", got["effort"]) == "medium"   # override wins
    assert EP.resolve_effort("codex", "fix", got["effort"]) == "high"        # override wins
    assert EP.resolve_effort("codex", "build", got["effort"]) == "high"      # no override -> default


def test_load_engine_prefs_remaps_legacy_fixer_pin_to_code_fixer(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"codexModels": {"fixer": "gpt-5.6-terra"}})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert got["codexModels"] == {"code-fixer": "gpt-5.6-terra"}
    assert "fixer" not in got.get("invalidCodexModels", {})
    assert "code-fixer" not in got.get("invalidCodexModels", {})


def test_load_engine_prefs_canonical_code_fixer_wins_over_legacy_fixer(tmp_path):
    for i, codex_models in enumerate((
        {"fixer": "gpt-5.6-terra", "code-fixer": "gpt-5.6-sol"},
        {"code-fixer": "gpt-5.6-sol", "fixer": "gpt-5.6-terra"},
    )):
        repo = str(tmp_path / str(i))
        _write_core_with_prefs(repo, {"codexModels": codex_models})
        got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
        assert got["codexModels"] == {"code-fixer": "gpt-5.6-sol"}


def test_dispatch_calibration_rows_fable_tier_on_codex_shows_unsupported_marker():
    rows = EP.dispatch_calibration_rows(
        {"implementation": "codex"},
        {"implementer": "fable", "pilot": "sonnet", "reviewer": "sonnet", "reviewer-deep": "opus"})
    by_role = {r["role"]: r for r in rows}
    assert by_role["implementer"]["engine"] == "codex"
    assert "unsupported" in by_role["implementer"]["model"]
    assert by_role["implementer"]["model"] != "fable"


def test_load_engine_prefs_surfaces_only_valid_per_role_codex_model_pins(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                  "codexModels": {"reviewer": "gpt-5.6-terra",
                                                  "reviewer-deep": "gpt-5.6-sol",
                                                  "implementer": "gpt-5.6-sol",
                                                  "code-fixer": "gpt-5.6-terra",
                                                  "pilot": "gpt-5.6-terra",
                                                  "bogus-role": "gpt-5.6-terra",
                                                  }})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert got["codexModels"] == {"reviewer": "gpt-5.6-terra",
                                  "reviewer-deep": "gpt-5.6-sol",
                                  "implementer": "gpt-5.6-sol",
                                  "code-fixer": "gpt-5.6-terra",
                                  "pilot": "gpt-5.6-terra"}
    assert got["invalidCodexModels"]["bogus-role"] == "unknown role 'bogus-role' rejected"
    invalid_repo = str(tmp_path / "invalid")
    _write_core_with_prefs(invalid_repo, {"codexModels": {"code-fixer": "gpt-5.6-solar"}})
    invalid_got = EP.load_engine_prefs(invalid_repo, root=os.path.join(invalid_repo, "store"))
    assert invalid_got.get("codexModels", {}) == {}
    assert invalid_got["invalidCodexModels"]["code-fixer"] == (
        "unknown model 'gpt-5.6-solar' rejected"
    )


def test_codex_model_strength_covers_every_valid_model():
    # #409 drift guard: CODEX_MODEL_STRENGTH must stay a superset of CODEX_MODELS, else a valid pin
    # would be unrankable and silently dropped from the write-auth probe's model selection.
    assert set(EP.CODEX_MODEL_STRENGTH) == set(EP.CODEX_MODELS)


def test_codex_write_probe_model_covers_the_implementation_dispatch_ceiling():
    # #409: the write-auth probe dispatches the strongest model the codex implementation (build/fix)
    # role will actually run — its pins, else the sol floor for any UNPINNED write role.
    floor = EP.CODEX_MODEL_BY_TIER["opus"]  # gpt-5.6-sol
    # no pins at all -> the sol capability floor (both write roles unpinned)
    assert EP.codex_write_probe_model(None) == floor
    assert EP.codex_write_probe_model({}) == floor
    assert EP.codex_write_probe_model({"codexModels": {}}) == floor
    assert EP.codex_write_probe_model({"codexModels": "nope"}) == floor
    # BOTH write roles pinned to unregistered gpt-5.5 -> treated as unpinned -> sol floor
    assert EP.codex_write_probe_model(
        {"codexModels": {"implementer": "gpt-5.5", "code-fixer": "gpt-5.5"}}) == floor
    # PARTIAL pin: one write role unpinned derives a GPT-5.6 tier model, so the probe clamps up to the
    # sol floor rather than under-testing at gpt-5.5 (the premortem fail-direction regression, closed).
    assert EP.codex_write_probe_model({"codexModels": {"implementer": "gpt-5.5"}}) == floor
    # a reviewer pin is irrelevant to the WRITE probe — it does not lower or raise the write ceiling
    assert EP.codex_write_probe_model(
        {"codexModels": {"implementer": "gpt-5.5", "code-fixer": "gpt-5.5",
                         "reviewer": "gpt-5.6-sol"}}) == floor
    # both write roles pinned to valid 5.6 family -> the stronger of the two
    assert EP.codex_write_probe_model(
        {"codexModels": {"implementer": "gpt-5.6-terra", "code-fixer": "gpt-5.6-terra"}}) == "gpt-5.6-terra"
    # implementer is the ceiling (stronger than code-fixer) -> the probe dispatches implementer's model.
    # Proves the probe covers BOTH write roles, not just code-fixer (drops-a-write-role mutant dies here).
    assert EP.codex_write_probe_model(
        {"codexModels": {"implementer": "gpt-5.6-sol", "code-fixer": "gpt-5.6-terra"}}) == "gpt-5.6-sol"


def test_load_engine_prefs_rejects_unregistered_model_before_dispatch(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "claude",
                                  "effort": {"review": "max"},
                                  "codexModels": {"reviewer": "gpt-5.5"}})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert "reviewer" not in got.get("codexModels", {})
    assert got["invalidCodexModels"]["reviewer"] == "unknown model 'gpt-5.5' rejected"


def test_load_engine_prefs_effort_non_dict_normalizes_to_empty(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                  "effort": "not-a-dict"})
    assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))["effort"] == {}


def test_cli_engine_pref_load_emits_json(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "claude",
                                  "effort": {"build": "low"}})
    out = subprocess.run(
        [sys.executable, os.path.join(_LIB, "engine_pref_load.py"),
         "--cwd", repo, "--root", os.path.join(repo, "store")],
        capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout) == {"reviewer": "codex", "implementation": "claude",
                                      "briefCheck": "claude",
                                      "pilot": "claude", "effort": {"build": "low"}}


def test_engine_pref_load_error_path_degenerate_carries_every_role_key(capsys, monkeypatch):
    # main()'s fail-open degenerate (load_engine_prefs raised / returned non-dict) must match the
    # happy-path schema: briefCheck and pilot included, else a fail-open readout hands the spine a
    # shape the happy path never would.
    spec = importlib.util.spec_from_file_location(
        "engine_pref_load", os.path.join(_LIB, "engine_pref_load.py"))
    epl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(epl)
    import engine_pref as _ep  # the sys.modules instance main() imports at runtime

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(_ep, "load_engine_prefs", _boom)
    assert epl.main(["engine_pref_load", "--cwd", "."]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(EP.ENGINE_ROLE_KEYS) <= set(out)
    assert out["briefCheck"] == "claude"
    assert out["pilot"] == "claude"
