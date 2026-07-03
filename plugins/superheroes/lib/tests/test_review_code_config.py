import importlib.util, json, os
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(_HERE, "..", "review_code_config.py")
    spec = importlib.util.spec_from_file_location("review_code_config", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RC = _load()


def test_verify_command_from_profile(tmp_path):
    p = tmp_path / "review-profile.md"
    p.write_text("## Threat model\nsingle-user\n\n## Verify\ncommand: pytest -q\n")
    assert RC.resolve_verify_command(str(p)) == "pytest -q"


def test_verify_command_none_when_absent_or_unreadable(tmp_path):
    assert RC.resolve_verify_command(str(tmp_path / "missing.md")) == "none"
    p = tmp_path / "p.md"
    p.write_text("## Threat model\nsingle-user\n")
    assert RC.resolve_verify_command(str(p)) == "none"
    assert RC.resolve_verify_command(None) == "none"


def test_resolve_verify_from_profile_review_only(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("## Verify\nmode: review-only\n")
    mode, cmd = RC.resolve_verify_from_profile(str(p))
    assert mode == "review-only"
    assert cmd == "none"


def test_resolve_verify_from_profile_unverified(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("## Verify\nmode: unverified\n")
    mode, cmd = RC.resolve_verify_from_profile(str(p))
    assert mode == "unverified"
    assert cmd == "none"


def test_tiers_default_policy():
    assert RC.resolve_tiers({}) == {
        "reviewer": "sonnet", "reviewerDeep": "opus", "synthesis": "opus", "fixer": "sonnet"}


def test_tiers_honor_override():
    t = RC.resolve_tiers({"reviewer-deep": "sonnet", "fixer": "haiku"})
    assert t["reviewerDeep"] == "sonnet" and t["fixer"] == "haiku"


def test_resolve_composes_verify_and_tiers(tmp_path, monkeypatch):
    # resolve(cwd) is what reviewCodePhase calls — exercise the layer-exists wiring + overrides.
    import subprocess
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    repo = str(tmp_path)
    layer = tmp_path / ".claude" / "superheroes" / "review-crew.md"
    layer.parent.mkdir(parents=True)
    layer.write_text("## Model tiers\nreviewer-deep: sonnet\n")
    core = tmp_path / ".claude" / "superheroes" / "core.md"
    core.write_text(
        __import__("core_md").render_core(
            {"verifyCommand": "pytest -q", "stackTags": [], "threatModel": "x", "patterns": ""},
            "confirmed", "2026-06-26", "2026-06-26"))
    out = RC.resolve(repo)
    assert out["verifyCommand"] == "pytest -q"
    assert out["tiers"]["reviewerDeep"] == "sonnet"   # layer override honored
    assert out["tiers"]["fixer"] == "sonnet"           # FR-7 code-context default


def test_resolve_failopen_when_no_profile(tmp_path, monkeypatch):
    import calibration_resolve as cr
    monkeypatch.setattr(cr, "resolve",
                        lambda cwd, root=None, **kw: {"exists": False, "dispatch_layer": None,
                                                      "legacy_path": None})
    out = RC.resolve(str(tmp_path))
    assert out["verifyCommand"] == "none"
    assert out["tiers"] == {"reviewer": "sonnet", "reviewerDeep": "opus", "synthesis": "opus", "fixer": "sonnet"}


def test_resolve_failopen_on_calibration_error(tmp_path, monkeypatch):
    import calibration_resolve as cr
    import mode_registry as mr

    def boom(*a, **k):
        raise mr.UnknownSchemaVersion(99)

    monkeypatch.setattr(cr, "resolve", boom)
    out = RC.resolve(str(tmp_path))
    assert out["verifyCommand"] == "none"
    assert out["verifyMode"] is None
    assert out["tiers"]["fixer"] == "sonnet"
