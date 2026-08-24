import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN_ROOT = os.path.join(_LIB, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load():
    spec = importlib.util.spec_from_file_location(
        "version_skew",
        os.path.join(_LIB, "version_skew.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VS = _load()


def _write_manifest(base, name="superheroes"):
    path = base / "plugins" / "superheroes" / ".claude-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "version": "0.30.0"}), encoding="utf-8")


def _write_version_txt(base, version="0.31.0"):
    path = base / "plugins" / "superheroes" / "version.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(version + "\n", encoding="utf-8")


def _copy_semantics_to(base, suffix=""):
    lib = base / "plugins" / "superheroes" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        dst = lib / os.path.basename(entry)
        content = open(src, encoding="utf-8").read()
        if suffix and entry == "lib/model_registry.py":
            content = content + suffix
        dst.write_text(content, encoding="utf-8")


def _plugin_tree(tmp_path, suffix=""):
    root = tmp_path / "plugin"
    manifest = root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": "0.29.0"}), encoding="utf-8")
    lib = root / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        dst = lib / os.path.basename(entry)
        content = open(src, encoding="utf-8").read()
        if suffix and entry == "lib/model_registry.py":
            content = content + suffix
        dst.write_text(content, encoding="utf-8")
    return str(root)


def test_identity_gate_missing_manifest_returns_none(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = _plugin_tree(tmp_path)
    assert VS.detect(str(repo), plugin) is None


def test_identity_gate_wrong_name_returns_none(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, name="other-plugin")
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    assert VS.detect(str(repo), plugin) is None


def test_self_gate_repo_plugin_returns_none(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = str(repo / "plugins" / "superheroes")
    assert VS.detect(str(repo), plugin) is None


def test_no_skew_identical_semantics_returns_none(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    assert VS.detect(str(repo), plugin) is None


def test_skew_model_registry_divergent(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo, "0.31.0")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path, suffix="# skew marker\n")
    record = VS.detect(str(repo), plugin)
    assert record is not None
    assert record["constraint"] == "plugin-version-skew"
    assert record["detail"] == "semantics-divergent"
    assert "0.29.0" in record["reason"]
    assert "0.31.0" in record["reason"]


def test_skew_seat_map_divergent(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin_root = tmp_path / "plugin"
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": "0.29.0"}), encoding="utf-8")
    lib = plugin_root / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        content = open(src, encoding="utf-8").read()
        if entry == "lib/seat_map.py":
            content = content + "# seat-map skew marker\n"
        (lib / os.path.basename(entry)).write_text(content, encoding="utf-8")
    record = VS.detect(str(repo), str(plugin_root))
    assert record is not None
    assert record["detail"] == "semantics-divergent"
    assert "lib/seat_map.py" in record["reason"]


def test_evidence_unreadable_plugin_side_missing(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin_root = tmp_path / "plugin"
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": "0.29.0"}), encoding="utf-8")
    lib = plugin_root / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    src = os.path.join(_PLUGIN_ROOT, "lib/model_registry.py")
    (lib / "model_registry.py").write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    record = VS.detect(str(repo), str(plugin_root))
    assert record is not None
    assert record["detail"] == "evidence-unreadable"


def test_versions_unreadable_identical_semantics_returns_none(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    plugin = _plugin_tree(tmp_path)
    lib = repo / "plugins" / "superheroes" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (lib / os.path.basename(entry)).write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    assert VS.detect(str(repo), plugin) is None


def test_versions_unreadable_divergent_semantics_contains_unknown(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    lib = repo / "plugins" / "superheroes" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (lib / os.path.basename(entry)).write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    plugin_root = tmp_path / "plugin"
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{not json", encoding="utf-8")
    lib_p = plugin_root / "lib"
    lib_p.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        content = open(src, encoding="utf-8").read()
        if entry == "lib/model_registry.py":
            content = content + "# divergent\n"
        (lib_p / os.path.basename(entry)).write_text(content, encoding="utf-8")
    record = VS.detect(str(repo), str(plugin_root))
    assert record is not None
    assert "unknown" in record["reason"]
