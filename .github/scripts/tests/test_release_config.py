import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))  # repo root from .github/scripts/tests/
PLUGINS = ["review-crew", "test-pilot", "the-architect", "workhorse"]


def _load(rel):
    with open(os.path.join(_ROOT, rel)) as fh:
        return json.load(fh)


def test_manifest_seeds_match_plugin_json():
    manifest = _load(".release-please-manifest.json")
    for name in PLUGINS:
        pj = _load(f"plugins/{name}/.claude-plugin/plugin.json")
        assert manifest[f"plugins/{name}"] == pj["version"], name


def test_version_txt_matches_plugin_json():
    for name in PLUGINS:
        pj = _load(f"plugins/{name}/.claude-plugin/plugin.json")
        with open(os.path.join(_ROOT, f"plugins/{name}/version.txt")) as fh:
            assert fh.read().strip() == pj["version"], name


def test_config_is_separate_prs_and_well_formed():
    cfg = _load("release-please-config.json")
    assert cfg.get("separate-pull-requests") is True
    pkgs = cfg["packages"]
    for name in PLUGINS:
        key = f"plugins/{name}"
        assert key in pkgs, key
        p = pkgs[key]
        assert p["release-type"] == "simple"
        assert p["component"] == name
        assert p["changelog-path"] == "CHANGELOG.md"
        # release-please resolves a package's extra-files RELATIVE TO THE PACKAGE DIR
        # (the `key`), so the paths are package-relative, not repo-root-relative.
        paths = [e["path"] for e in p["extra-files"]]
        assert ".claude-plugin/plugin.json" in paths
        assert ".codex-plugin/plugin.json" in paths
        for e in p["extra-files"]:
            assert e["type"] == "json" and e["jsonpath"] == "$.version"
            # verify the path as release-please resolves it: <package-dir>/<extra-file path>
            resolved = os.path.join(_ROOT, key, e["path"])
            assert os.path.exists(resolved), resolved


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
