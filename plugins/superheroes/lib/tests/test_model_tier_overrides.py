import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(_HERE, "..", "model_tier_overrides.py")
    spec = importlib.util.spec_from_file_location("model_tier_overrides", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MTO = _load()

_BLOCK = """\
<!-- provenance -->
schema: 1
<!-- end provenance -->

## Threat model
single-user

## Model tiers
reviewer-deep: opus
mechanical: sonnet

## Conventions
See CLAUDE.md.
"""


def test_none_or_empty_path_returns_empty():
    assert MTO.load_overrides(None) == {}
    assert MTO.load_overrides("") == {}


def test_missing_file_returns_empty(tmp_path):
    assert MTO.load_overrides(str(tmp_path / "nope.md")) == {}


def test_reads_valid_block(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text(_BLOCK, encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {"reviewer-deep": "opus", "mechanical": "sonnet"}


def test_unknown_role_dropped(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\nbogus: opus\nreviewer: sonnet\n", encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {"reviewer": "sonnet"}


def test_empty_value_dropped(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\nreviewer-deep:\nmechanical: haiku\n", encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {"mechanical": "haiku"}


def test_block_ends_at_next_heading(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\nreviewer: sonnet\n\n## Other\nreviewer-deep: opus\n",
                 encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {"reviewer": "sonnet"}


def test_no_block_returns_empty(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Threat model\nsingle-user\n", encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {}


def test_cli_emits_json(tmp_path, capsys):
    p = tmp_path / "profile.md"
    p.write_text(_BLOCK, encoding="utf-8")
    rc = MTO.main(["model_tier_overrides.py", "--profile", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"reviewer-deep": "opus", "mechanical": "sonnet"}


def _chdir(monkeypatch, d):
    monkeypatch.chdir(d)


def _seed_inrepo_profile(root, body):
    """Write an in-repo review-crew profile that review_store.resolve will find."""
    d = os.path.join(str(root), ".claude")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "review-profile.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return p


def test_cli_autoresolves_profile_when_no_flag(tmp_path, monkeypatch, capsys):
    # (a) no --profile + a resolvable in-repo profile with a `## Model tiers` block ->
    # the feature now LOADS (pre-fix this returned {} because load_overrides(None)=={}).
    _seed_inrepo_profile(tmp_path, _BLOCK)
    _chdir(monkeypatch, tmp_path)
    rc = MTO.main(["model_tier_overrides.py"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"reviewer-deep": "opus", "mechanical": "sonnet"}


def test_cli_autoresolve_no_profile_is_noop(tmp_path, monkeypatch, capsys):
    # (b) no --profile + nothing resolvable -> {} (the eval no-op is preserved).
    _chdir(monkeypatch, tmp_path)
    rc = MTO.main(["model_tier_overrides.py"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {}


def test_cli_explicit_profile_still_wins(tmp_path, monkeypatch, capsys):
    # (c) an explicit --profile is honored even when an in-repo profile would also resolve.
    _seed_inrepo_profile(tmp_path, "## Model tiers\nreviewer: sonnet\n")
    explicit = tmp_path / "explicit.md"
    explicit.write_text("## Model tiers\nfixer: opus\n", encoding="utf-8")
    _chdir(monkeypatch, tmp_path)
    rc = MTO.main(["model_tier_overrides.py", "--profile", str(explicit)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"code-fixer": "opus"}


def test_cli_autoresolve_broken_profile_failsafe(tmp_path, monkeypatch, capsys):
    # (d) the resolver points at a profile path, but reading it raises -> {} (fail-safe, no
    # crash). Make .claude/review-profile.md a directory so resolve() sees it (os.path.exists)
    # but load_overrides() OSErrors on read.
    os.makedirs(os.path.join(str(tmp_path), ".claude", "review-profile.md"))
    _chdir(monkeypatch, tmp_path)
    rc = MTO.main(["model_tier_overrides.py"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {}


def test_known_roles_matches_core_default_tiers():
    # KNOWN_ROLES mirrors the model_tier core's ROLES (DEFAULT_TIERS keys) MINUS `orchestrator` —
    # deliberately excluded, since the session model has no config key and must never be silently
    # overridable. Guard against silent drift so a
    # renamed/added core role can't make this helper drop a valid override (fail-open would
    # otherwise mask it). Mirrors the sibling guard in test_model_tier_resolve.py. Repointed
    # from the old plugins/superheroes/lib/model_tier.py to the in-tree sibling core.
    core_path = os.path.join(_HERE, "..", "model_tier.py")
    spec = importlib.util.spec_from_file_location("model_tier_core", core_path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    assert set(MTO.KNOWN_ROLES) == set(core.ROLES) - {"orchestrator"}


def test_orchestrator_excluded_implementer_and_pilot_included():
    assert "orchestrator" not in MTO.KNOWN_ROLES
    assert "implementer" in MTO.KNOWN_ROLES
    assert "pilot" in MTO.KNOWN_ROLES


def test_implementer_and_pilot_override_block_takes_effect(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\nimplementer: opus\npilot: haiku\n", encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {"implementer": "opus", "pilot": "haiku"}
    effective = MTO.effective_tiers(str(p))
    assert effective["implementer"] == "opus"
    assert effective["pilot"] == "haiku"


def test_orchestrator_not_configurable_update_drops_it(tmp_path):
    # Negative: orchestrator has no config key — an attempted write is dropped with a warning
    # and never lands in the profile.
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    result = MTO.update_overrides(str(p), {"orchestrator": "opus"}, [])
    assert any("unknown role: orchestrator" in w for w in result["warnings"])
    text = p.read_text(encoding="utf-8")
    assert "orchestrator" not in text
    assert MTO.load_overrides(str(p)) == {}


def test_orchestrator_not_configurable_load_drops_it(tmp_path):
    # A hand-edited block containing `orchestrator: opus` is dropped on read (unknown role).
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\norchestrator: opus\n", encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {}


def test_effective_tiers_merges_defaults_with_profile_overrides(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\nreviewer: fable\n", encoding="utf-8")
    effective = MTO.effective_tiers(str(p))
    assert effective["reviewer"] == "fable"
    assert effective["synthesis"] == "opus"
    assert effective["mechanical"] == "haiku"


def test_legacy_fixer_alias_read_maps_to_code_fixer(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\nfixer: haiku\n", encoding="utf-8")
    assert MTO.load_overrides(str(p)) == {"code-fixer": "haiku"}


def test_legacy_fixer_alias_write_remaps_with_warning(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    result = MTO.update_overrides(str(p), {"fixer": "haiku"}, [])
    assert any("'fixer' is a legacy alias for 'code-fixer' (remapped)" in w
               for w in result["warnings"])
    text = p.read_text(encoding="utf-8")
    assert "code-fixer: haiku" in text
    assert not any(line.strip() == "fixer: haiku" for line in text.splitlines())
    assert MTO.load_overrides(str(p)) == {"code-fixer": "haiku"}


def test_legacy_fixer_alias_clear_remaps_to_code_fixer(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\ncode-fixer: haiku\n", encoding="utf-8")
    result = MTO.update_overrides(str(p), clear_roles=["fixer"])
    assert result["warnings"] == []
    text = p.read_text(encoding="utf-8")
    assert "code-fixer" not in text
    assert MTO.load_overrides(str(p)) == {}


def test_write_model_tiers_block_creates_and_preserves_other_sections(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Threat model\nsingle-user\n\n## Conventions\nkeep me\n", encoding="utf-8")
    result = MTO.update_overrides(str(p), {"reviewer": "fable", "code-fixer": "opus"}, [])
    text = p.read_text(encoding="utf-8")
    assert result["warnings"] == []
    assert "## Threat model\nsingle-user" in text
    assert "## Conventions\nkeep me" in text
    assert "## Model tiers\nreviewer: fable\ncode-fixer: opus\n" in text
    assert MTO.load_overrides(str(p)) == {"reviewer": "fable", "code-fixer": "opus"}


def test_write_model_tiers_block_replaces_clears_and_drops_unknown_roles(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("before\n\n## Model tiers\nreviewer: sonnet\nsynthesis: opus\n\n## After\nkept\n",
                 encoding="utf-8")
    result = MTO.update_overrides(str(p), {"bogus": "opus", "code-fixer": "haiku"}, ["reviewer"])
    text = p.read_text(encoding="utf-8")
    assert any("unknown role: bogus" in w for w in result["warnings"])
    assert "reviewer: sonnet" not in text
    assert "synthesis: opus" in text
    assert "code-fixer: haiku" in text
    assert text.startswith("before\n\n")
    assert "\n## After\nkept\n" in text
    assert MTO.load_overrides(str(p)) == {"synthesis": "opus", "code-fixer": "haiku"}


def test_write_unknown_model_warns_but_keeps_override(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    result = MTO.update_overrides(str(p), {"reviewer": "experimental-model"}, [])
    assert any("unknown model for reviewer: experimental-model" in w for w in result["warnings"])
    assert MTO.load_overrides(str(p)) == {"reviewer": "experimental-model"}


def test_resolve_profile_path_threads_root_to_calibration_resolve(monkeypatch):
    # Regression (#489): a caller-supplied `root` was dropped, so a global-store / custom-root
    # setup silently resolved tiers against the DEFAULT store while the core prefs read the custom
    # one. `root` must reach calibration_resolve so both read the same store.
    import calibration_resolve
    captured = {}

    def _fake(cwd=None, root=None):
        captured["cwd"] = cwd
        captured["root"] = root
        return "/resolved/layer.md"

    monkeypatch.setattr(calibration_resolve, "resolve_profile_path", _fake)
    assert MTO.resolve_profile_path("/proj", root="/store") == "/resolved/layer.md"
    assert captured == {"cwd": "/proj", "root": "/store"}


def _init_repo(path):
    import subprocess
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)


def _empty_store_root(tmp_path):
    d = tmp_path / "empty_store"
    d.mkdir()
    return str(d)


def _ensure_global_unified_layer(repo, store_root):
    import mode_registry as mr
    store = mr.ensure_project_store(repo, root=store_root)
    cfg = os.path.join(store, "config")
    os.makedirs(cfg, exist_ok=True)
    layer = os.path.join(cfg, "review-crew.md")
    with open(layer, "w") as fh:
        fh.write("## Focus hints\n- code: x\n")
    return layer


def test_resolve_profile_path_raises_on_unresolvable_root(tmp_path, isolated_default_store_root):
    import calibration_resolve as cr
    import pytest

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = isolated_default_store_root
    empty = _empty_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    with pytest.raises(cr.UnresolvableRootError):
        MTO.resolve_profile_path(str(repo), root=empty)


def test_resolve_profile_path_fallopen_when_calibration_resolve_unimportable(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "calibration_resolve", None)
    assert MTO.resolve_profile_path("/any/cwd", root="/any/root") is None


def test_resolve_profile_path_fallopen_when_unresolvable_root_error_missing(monkeypatch):
    import types
    import sys

    stub = types.ModuleType("calibration_resolve")

    def _boom(*_a, **_kw):
        raise RuntimeError("boom")

    stub.resolve_profile_path = _boom
    monkeypatch.setitem(sys.modules, "calibration_resolve", stub)
    assert MTO.resolve_profile_path("/any/cwd", root="/any/root") is None


def test_write_cli_refuses_fable_tier_on_external_engine(tmp_path, monkeypatch, capsys):
    import importlib.util

    cm_path = os.path.join(_HERE, "..", "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md", cm_path)
    CM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CM)

    cal = tmp_path / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    core_text = CM.render_core(
        {
            "verifyCommand": "npm test",
            "stackTags": [],
            "enginePreferences": {"implementation": "codex"},
            "threatModel": "t",
            "patterns": "",
        },
        "confirmed",
        "2026-01-01",
        "2026-01-01",
    )
    (cal / "core.md").write_text(core_text, encoding="utf-8")
    p = cal / "review-crew.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    rc = MTO.main(["model_tier_overrides.py", "write", "--profile", str(p), "--set", "implementer=fable"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["ok"] is False
    assert out["reason"] == "fable-on-external-engine"
    assert out["violations"][0]["reason"] == "fable-on-external-engine"
    assert MTO.load_overrides(str(p)) == {}


def test_write_cli_gate_reads_engine_prefs_from_profile_project_not_cwd(tmp_path, monkeypatch, capsys):
    import importlib.util

    cm_path = os.path.join(_HERE, "..", "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md", cm_path)
    CM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CM)

    project = tmp_path / "project"
    cal = project / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    core_text = CM.render_core(
        {
            "verifyCommand": "npm test",
            "stackTags": [],
            "enginePreferences": {"implementation": "codex"},
            "threatModel": "t",
            "patterns": "",
        },
        "confirmed",
        "2026-01-01",
        "2026-01-01",
    )
    (cal / "core.md").write_text(core_text, encoding="utf-8")
    profile = cal / "review-crew.md"
    profile.write_text("## Model tiers\n", encoding="utf-8")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(profile),
        "--set",
        "implementer=fable",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["reason"] == "fable-on-external-engine"
    assert MTO.load_overrides(str(profile)) == {}


def test_write_cli_clear_removes_fable_violation(tmp_path, monkeypatch, capsys):
    import importlib.util

    cm_path = os.path.join(_HERE, "..", "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md", cm_path)
    CM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CM)

    cal = tmp_path / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    core_text = CM.render_core(
        {
            "verifyCommand": "npm test",
            "stackTags": [],
            "enginePreferences": {"implementation": "codex"},
            "threatModel": "t",
            "patterns": "",
        },
        "confirmed",
        "2026-01-01",
        "2026-01-01",
    )
    (cal / "core.md").write_text(core_text, encoding="utf-8")
    p = cal / "review-crew.md"
    p.write_text("## Model tiers\nimplementer: fable\n", encoding="utf-8")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    rc = MTO.main(["model_tier_overrides.py", "write", "--profile", str(p), "--clear", "implementer"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert "implementer" not in MTO.load_overrides(str(p))


def test_read_engine_preferences_corrupt_core_beside_profile_is_evaluation_failure(tmp_path):
    project = tmp_path / "project"
    cal = project / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    (cal / "core.md").write_text("not valid core markdown\n", encoding="utf-8")
    profile = cal / "review-crew.md"
    profile.write_text("## Model tiers\n", encoding="utf-8")
    prefs, err = MTO._read_engine_preferences_for_gate(profile_path=str(profile))
    assert prefs == {}
    assert err is not None


def test_read_engine_preferences_unreadable_byte_identity(tmp_path):
    project = tmp_path / "project"
    cal = project / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    core_p = cal / "core.md"
    core_p.write_text("not valid core markdown\n", encoding="utf-8")
    profile = cal / "review-crew.md"
    profile.write_text("## Model tiers\n", encoding="utf-8")
    import core_md

    cfg = core_md._classify_core_md_at_path(str(core_p))
    prefs, err = MTO._read_engine_preferences_for_gate(profile_path=str(profile))
    assert prefs == {}
    assert err == {"reason": "core-md-unreadable", "detail": cfg.detail}


def test_read_engine_preferences_root_unavailable_returns_gate_err(tmp_path, monkeypatch):
    import store_core as sc

    repo = str(tmp_path)
    store = str(tmp_path / "store")
    real = sc.run_git_result

    def fake(cwd, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(None, sc.GIT_UNAVAILABLE, "FileNotFoundError: no git")
        return real(cwd, *args)

    monkeypatch.setattr(sc, "run_git_result", fake)
    prefs, err = MTO._read_engine_preferences_for_gate(cwd=repo, root=store)
    assert prefs == {}
    assert err is not None
    assert err["reason"] == "repo-root-unavailable"
    assert err["detail"]


def test_write_cli_refuses_when_core_beside_profile_corrupt(tmp_path, capsys):
    project = tmp_path / "project"
    cal = project / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    (cal / "core.md").write_text("corrupt {{{", encoding="utf-8")
    profile = cal / "review-crew.md"
    profile.write_text("## Model tiers\n", encoding="utf-8")
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(profile),
        "--set",
        "implementer=fable",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["reason"] == "core-md-unreadable"
    assert MTO.load_overrides(str(profile)) == {}


def test_write_cli_refuses_when_effective_tiers_raises(tmp_path, monkeypatch, capsys):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")

    def _boom(profile_path, set_overrides=None, clear_roles=None):
        raise RuntimeError("tier read failed")

    monkeypatch.setattr(MTO, "_candidate_effective_tiers", _boom)
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(p),
        "--set",
        "reviewer=sonnet",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["reason"] == "dispatch-gate-evaluation-failed"
    assert "tier read failed" in out["violations"][0]["detail"]


def test_gate_refusal_fallback_matches_core_md_shape():
    import core_md

    exc = RuntimeError("tier read failed")
    assert MTO._gate_refusal_fallback("r", "d") == core_md.gate_refusal("r", "d")
    assert MTO._gate_refusal_detail_fallback(exc) == core_md.gate_refusal_detail(exc)
    assert MTO._GATE_REASON_EVALUATION_FAILED_FALLBACK == core_md.GATE_REASON_EVALUATION_FAILED


def test_gate_refusal_fallback_needs_no_core_md_import(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "core_md":
            raise ImportError("simulated lazy import failure")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert MTO._gate_refusal_fallback("r", "d") == {"reason": "r", "detail": "d"}


def test_write_cli_gate_err_passed_through_not_reprojected(tmp_path, monkeypatch, capsys):
    import builtins

    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "core_md":
            raise ImportError("simulated lazy import failure")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(p),
        "--set",
        "reviewer=sonnet",
    ])
    out = json.loads(capsys.readouterr().out)
    expected_violation = {
        "reason": "dispatch-gate-evaluation-failed",
        "detail": "ImportError: simulated lazy import failure",
    }
    assert rc == 1
    assert out["violations"][0] == expected_violation
    assert out["reason"] == out["violations"][0]["reason"]


def test_write_cli_lazy_core_md_import_failure_writes_json(tmp_path, monkeypatch, capsys):
    import builtins

    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "core_md":
            raise ImportError("simulated lazy import failure")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(p),
        "--set",
        "reviewer=sonnet",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["reason"] == "dispatch-gate-evaluation-failed"
    assert "simulated lazy import failure" in out["violations"][0]["detail"]


def test_write_cli_no_core_beside_profile_proceeds_clean(tmp_path, capsys):
    p = tmp_path / "profile.md"
    p.write_text("## Model tiers\n", encoding="utf-8")
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(p),
        "--set",
        "reviewer=sonnet",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert MTO.load_overrides(str(p)) == {"reviewer": "sonnet"}


def _tier_gate_project(tmp_path, core_shape):
    import importlib.util

    cm_path = os.path.join(_HERE, "..", "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md_tg", cm_path)
    CM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CM)
    project = tmp_path / "project"
    cal = project / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    core_path = cal / "core.md"
    core_text = CM.render_core(
        {
            "verifyCommand": "npm test",
            "stackTags": [],
            "enginePreferences": {"reviewer": "cursor", "implementation": "codex"},
            "threatModel": "t",
            "patterns": "",
        },
        "confirmed",
        "2026-01-01",
        "2026-01-01",
    )
    if core_shape == "regular":
        core_path.write_text(core_text, encoding="utf-8")
    elif core_shape == "absent":
        pass
    elif core_shape == "directory":
        core_path.mkdir()
    elif core_shape == "dangling":
        core_path.symlink_to("/nonexistent/tier-gate-dangle")
    else:
        raise ValueError(core_shape)
    profile = cal / "review-crew.md"
    profile.write_text("## Model tiers\nimplementer: sonnet\n", encoding="utf-8")
    return profile


def test_tier_writer_gate_unreadable_directory_and_dangling(tmp_path, capsys):
    for shape in ("directory", "dangling"):
        profile = _tier_gate_project(tmp_path / shape, shape)
        rc = MTO.main([
            "model_tier_overrides.py",
            "write",
            "--profile",
            str(profile),
            "--set",
            "reviewer=fable",
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert out["reason"] == "core-md-unreadable"
        assert out["violations"][0]["reason"] == "core-md-unreadable"


def test_tier_writer_gate_absent_core_allowed(tmp_path, capsys):
    profile = _tier_gate_project(tmp_path, "absent")
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(profile),
        "--set",
        "reviewer=sonnet",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True


def test_tier_writer_gate_readable_still_fable_on_external(tmp_path, capsys):
    profile = _tier_gate_project(tmp_path, "regular")
    rc = MTO.main([
        "model_tier_overrides.py",
        "write",
        "--profile",
        str(profile),
        "--set",
        "reviewer=fable",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["reason"] == "fable-on-external-engine"
