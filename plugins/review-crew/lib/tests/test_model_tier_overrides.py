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


def test_known_roles_matches_core_default_tiers():
    # KNOWN_ROLES mirrors the-architect core's DEFAULT_TIERS keys; guard against
    # silent drift so a renamed/added core role can't make this helper drop a valid
    # override (fail-open would otherwise mask it). Mirrors the sibling guard in
    # test_model_tier_resolve.py (_FALLBACK == core.DEFAULT_TIERS).
    root = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
    core_path = os.path.join(root, "plugins", "the-architect", "lib", "model_tier.py")
    spec = importlib.util.spec_from_file_location("model_tier_core", core_path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    assert set(MTO.KNOWN_ROLES) == set(core.DEFAULT_TIERS)
