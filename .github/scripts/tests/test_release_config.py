import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))  # repo root from .github/scripts/tests/
PLUGIN = "superheroes"
PKG = "plugins/superheroes"


def _load(rel):
    with open(os.path.join(_ROOT, rel)) as fh:
        return json.load(fh)


def test_manifest_seeds_match_plugin_json():
    manifest = _load(".release-please-manifest.json")
    pj = _load(f"{PKG}/.claude-plugin/plugin.json")
    assert manifest[PKG] == pj["version"]


def test_version_txt_matches_plugin_json():
    pj = _load(f"{PKG}/.claude-plugin/plugin.json")
    with open(os.path.join(_ROOT, f"{PKG}/version.txt")) as fh:
        assert fh.read().strip() == pj["version"]


def test_config_is_separate_prs_and_well_formed():
    cfg = _load("release-please-config.json")
    assert cfg.get("separate-pull-requests") is True
    pkgs = cfg["packages"]
    assert set(pkgs) == {PKG}
    p = pkgs[PKG]
    assert p["release-type"] == "simple"
    assert p["component"] == PLUGIN
    assert p["changelog-path"] == "CHANGELOG.md"
    assert p["bump-minor-pre-major"] is True
    paths = [e["path"] for e in p["extra-files"]]
    assert ".claude-plugin/plugin.json" in paths
    assert ".codex-plugin/plugin.json" in paths
    for e in p["extra-files"]:
        assert e["type"] == "json" and e["jsonpath"] == "$.version"
        # extra-files are package-relative: <package-dir>/<path>
        assert os.path.exists(os.path.join(_ROOT, PKG, e["path"]))


def test_config_keeps_default_tag_scheme():
    # The retained tag scheme `<plugin>-vX.Y.Z` relies on release-please's component-tag
    # defaults (component + `-` separator + `v` prefix). Assert nothing overrides them,
    # so the proposed tags stay consistent with the existing tags (the dry-run below
    # confirms the actual rendering once, with the App token).
    cfg = _load("release-please-config.json")
    override_keys = ("include-component-in-tag", "include-v-in-tag", "tag-separator")
    for k in override_keys:
        assert k not in cfg, f"top-level {k} would change the tag scheme"
    for name, p in cfg["packages"].items():
        for k in override_keys:
            assert k not in p, f"{name}: {k} would change the tag scheme"
