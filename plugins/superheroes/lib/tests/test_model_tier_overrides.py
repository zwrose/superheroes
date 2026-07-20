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
