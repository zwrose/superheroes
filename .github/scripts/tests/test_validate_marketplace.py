import json
import os

import pytest
import validate_marketplace as vm


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Point the validator at a scratch repo and reset module-level accumulators."""
    # R3: errors/notes are module-level lists — reset each test or state leaks.
    monkeypatch.setattr(vm, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vm, "MARKETPLACE", tmp_path / ".claude-plugin" / "marketplace.json")
    monkeypatch.setattr(vm, "errors", [])
    monkeypatch.setattr(vm, "notes", [])
    return tmp_path


def _scaffold_plugin(root, name="myplugin", version="1.0.0", source="./plugins/myplugin"):
    _write(
        root,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "metadata": {"version": "1.0.0"},
                "plugins": [{"name": name, "source": source}],
            }
        ),
    )
    _write(
        root,
        "plugins/myplugin/.claude-plugin/plugin.json",
        json.dumps({"name": name, "version": version}),
    )


def test_well_formed_catalog_and_manifest_returns_zero(fake_repo):
    _scaffold_plugin(fake_repo)
    assert vm.main() == 0
    assert vm.errors == []


def test_missing_top_level_name_is_error(fake_repo):
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps({"plugins": [{"name": "p", "source": "./plugins/p"}]}),
    )
    _write(
        fake_repo,
        "plugins/p/.claude-plugin/plugin.json",
        json.dumps({"name": "p", "version": "1.0.0"}),
    )
    assert vm.main() == 1
    assert any("missing top-level `name`" in e for e in vm.errors)


def test_metadata_version_semver_validation(fake_repo):
    _scaffold_plugin(fake_repo)
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "metadata": {"version": "not-semver"},
                "plugins": [{"name": "myplugin", "source": "./plugins/myplugin"}],
            }
        ),
    )
    assert vm.main() == 1
    assert any("metadata.version" in e and "not valid SemVer" in e for e in vm.errors)

    # Full SemVer 2.0.0 — prerelease + build metadata must be accepted.
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "metadata": {"version": "1.2.3-rc.1+build.42"},
                "plugins": [{"name": "myplugin", "source": "./plugins/myplugin"}],
            }
        ),
    )
    vm.errors.clear()
    assert vm.main() == 0
    assert vm.errors == []


@pytest.mark.parametrize(
    "catalog_body",
    [
        {},
        {"name": "test-market"},
        {"name": "test-market", "plugins": "not-a-list"},
        {"name": "test-market", "plugins": []},
    ],
)
def test_plugins_must_be_nonempty_list(fake_repo, catalog_body):
    _write(fake_repo, ".claude-plugin/marketplace.json", json.dumps(catalog_body))
    assert vm.main() == 1
    assert any("`plugins` must be a non-empty array" in e for e in vm.errors)


def test_plugin_entry_missing_name_and_missing_source(fake_repo):
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "plugins": [{"source": "./plugins/a"}, {"name": "b"}],
            }
        ),
    )
    assert vm.main() == 1
    assert any("missing `name`" in e for e in vm.errors)
    assert any("b: missing `source`" in e for e in vm.errors)


def test_source_path_does_not_exist(fake_repo):
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "plugins": [{"name": "ghost", "source": "./plugins/ghost"}],
            }
        ),
    )
    assert vm.main() == 1
    assert any("ghost: source path does not exist: ./plugins/ghost" in e for e in vm.errors)


def test_plugin_root_resolves_relative_source(fake_repo):
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "metadata": {"pluginRoot": "plugins"},
                "plugins": [{"name": "myplugin", "source": "myplugin"}],
            }
        ),
    )
    _write(
        fake_repo,
        "plugins/myplugin/.claude-plugin/plugin.json",
        json.dumps({"name": "myplugin", "version": "1.0.0"}),
    )
    resolved = vm.resolve_source("myplugin", "plugins")
    assert resolved == (fake_repo / "plugins" / "myplugin").resolve()
    assert vm.main() == 0
    assert vm.errors == []


def test_non_string_source_recorded_as_note_not_error(fake_repo):
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "plugins": [
                    {
                        "name": "remote",
                        "source": {"source": "github", "repo": "org/pkg"},
                    }
                ],
            }
        ),
    )
    assert vm.main() == 0
    assert vm.errors == []
    assert any("remote: remote source" in n for n in vm.notes)


def test_catalog_name_mismatch_with_plugin_json(fake_repo):
    _scaffold_plugin(fake_repo, name="catalog-name")
    _write(
        fake_repo,
        "plugins/myplugin/.claude-plugin/plugin.json",
        json.dumps({"name": "manifest-name", "version": "1.0.0"}),
    )
    assert vm.main() == 1
    assert any("name mismatch" in e for e in vm.errors)


def test_plugin_json_version_required_and_semver(fake_repo):
    _scaffold_plugin(fake_repo)
    _write(
        fake_repo,
        "plugins/myplugin/.claude-plugin/plugin.json",
        json.dumps({"name": "myplugin"}),
    )
    assert vm.main() == 1
    assert any("plugin.json has no `version`" in e for e in vm.errors)

    _write(
        fake_repo,
        "plugins/myplugin/.claude-plugin/plugin.json",
        json.dumps({"name": "myplugin", "version": "bad"}),
    )
    vm.errors.clear()
    assert vm.main() == 1
    assert any("plugin.json version 'bad' is not valid SemVer" in e for e in vm.errors)


def test_duplicate_version_in_catalog_and_plugin_json_is_error(fake_repo):
    _scaffold_plugin(fake_repo)
    _write(
        fake_repo,
        ".claude-plugin/marketplace.json",
        json.dumps(
            {
                "name": "test-market",
                "plugins": [
                    {
                        "name": "myplugin",
                        "source": "./plugins/myplugin",
                        "version": "9.9.9",
                    }
                ],
            }
        ),
    )
    assert vm.main() == 1
    assert any(
        "`version` is set in BOTH plugin.json and the marketplace entry" in e
        for e in vm.errors
    )


def test_malformed_and_missing_marketplace_json(fake_repo):
    _write(fake_repo, ".claude-plugin/marketplace.json", "{not json")
    assert vm.main() == 1
    assert any("invalid JSON" in e for e in vm.errors)

    (fake_repo / ".claude-plugin" / "marketplace.json").unlink()
    vm.errors.clear()
    assert vm.main() == 1
    assert any("missing file:" in e for e in vm.errors)
