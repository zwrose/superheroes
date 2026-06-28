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
    assert rc == 0 and out == {"fixer": "opus"}


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
    # KNOWN_ROLES mirrors the model_tier core's DEFAULT_TIERS keys; guard against
    # silent drift so a renamed/added core role can't make this helper drop a valid
    # override (fail-open would otherwise mask it). Mirrors the sibling guard in
    # test_model_tier_resolve.py (_FALLBACK == core.DEFAULT_TIERS). Repointed from the old
    # plugins/superheroes/lib/model_tier.py to the in-tree sibling core.
    core_path = os.path.join(_HERE, "..", "model_tier.py")
    spec = importlib.util.spec_from_file_location("model_tier_core", core_path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    assert set(MTO.KNOWN_ROLES) == set(core.DEFAULT_TIERS)
