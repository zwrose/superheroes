import importlib.util
import json
import os
import stat
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


def _write_manifest(base, name="superheroes", version="0.30.0"):
    path = base / "plugins" / "superheroes" / ".claude-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")


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


def _assert_record_shape(record):
    assert isinstance(record, dict)
    assert set(record.keys()) == {"constraint", "status", "detail", "reason", "inspectedRoot"}
    assert record["constraint"] == VS.CONSTRAINT
    assert record["reason"]


def test_identity_gate_missing_manifest_not_checked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_NOT_CHECKED
    assert record["detail"] == VS.DETAIL_NOT_SOURCE_REPO
    assert record["inspectedRoot"] == ""


def test_identity_gate_wrong_name_not_checked(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, name="other-plugin")
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_NOT_CHECKED
    assert record["detail"] == VS.DETAIL_NOT_SOURCE_REPO
    assert record["inspectedRoot"] == ""


def test_identity_gate_manifest_symlink_evidence_unreadable(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    real_manifest = tmp_path / "real-plugin.json"
    real_manifest.write_text(json.dumps({"name": "superheroes", "version": "0.30.0"}), encoding="utf-8")
    manifest_dir = repo / "plugins" / "superheroes" / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    os.symlink(real_manifest, manifest_dir / "plugin.json")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE


def test_self_gate_repo_plugin_not_checked(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = str(repo / "plugins" / "superheroes")
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_NOT_CHECKED
    assert record["detail"] == VS.DETAIL_SELF
    assert record["inspectedRoot"] == ""


def test_no_skew_identical_semantics_checked_clean(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert record["detail"] == VS.DETAIL_NO_DIVERGENCE
    assert record["inspectedRoot"] == os.path.abspath(str(repo))
    assert "0.29.0" in record["reason"]
    assert "0.30.0" in record["reason"]


def test_skew_model_registry_divergent(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, version="0.31.0")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path, suffix="# skew marker\n")
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_SEMANTICS_DIVERGENT
    assert record["inspectedRoot"] == os.path.abspath(str(repo))
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
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_SEMANTICS_DIVERGENT
    assert "lib/seat_map.py" in record["reason"]


def test_skew_version_skew_divergent(tmp_path):
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
        if entry == "lib/version_skew.py":
            content = content + "# version-skew home skew marker\n"
        (lib / os.path.basename(entry)).write_text(content, encoding="utf-8")
    record = VS.detect(str(repo), str(plugin_root))
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_SEMANTICS_DIVERGENT
    assert "lib/version_skew.py" in record["reason"]
    assert "family/registry" not in record["reason"]
    assert "watched review semantics differ" in record["reason"]
    assert (
        "lib/version_skew.py differ between the running plugin and this repository"
        in record["reason"]
    )


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
    _assert_record_shape(record)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE
    assert record["inspectedRoot"] == os.path.abspath(str(repo))


def test_evidence_unreadable_one_watched_refused(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    real_file = tmp_path / "real-seat-map.py"
    real_file.write_text("not the real seat map", encoding="utf-8")
    seat_map_path = repo / "plugins" / "superheroes" / "lib" / "seat_map.py"
    seat_map_path.unlink()
    os.symlink(real_file, seat_map_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE
    assert "lib/seat_map.py" in record["reason"]


def test_fail_closed_unreadable_never_checked_clean(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    seat_map_path = repo / "plugins" / "superheroes" / "lib" / "seat_map.py"
    seat_map_path.unlink()
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE
    assert record["status"] != VS.STATUS_CHECKED_CLEAN


def test_versions_unreadable_identical_semantics_checked_clean(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    plugin = _plugin_tree(tmp_path)
    lib = repo / "plugins" / "superheroes" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (lib / os.path.basename(entry)).write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert "0.30.0" in record["reason"]
    assert "0.29.0" in record["reason"]


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
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert "unknown" in record["reason"]


def test_repo_root_missing_not_checked(tmp_path):
    repo = tmp_path / "missing-repo"
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_NOT_CHECKED
    assert record["detail"] == VS.DETAIL_NOT_SOURCE_REPO


def test_version_txt_absent_reason_uses_manifest_not_unknown(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert "0.30.0" in record["reason"]
    assert "unknown" not in record["reason"]


def test_version_txt_ignored_when_manifest_present(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _copy_semantics_to(repo)
    _write_version_txt(repo, "9.99.9-IGNORED")
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert "9.99.9-IGNORED" not in record["reason"]
    assert "0.30.0" in record["reason"]


def test_watched_file_symlink_refused(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    real_file = tmp_path / "outside.py"
    real_file.write_text("symlink target", encoding="utf-8")
    model_path = repo / "plugins" / "superheroes" / "lib" / "model_registry.py"
    model_path.unlink()
    os.symlink(real_file, model_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="mkfifo unavailable")
def test_watched_file_fifo_refused(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    fifo_path = repo / "plugins" / "superheroes" / "lib" / "model_registry.py"
    fifo_path.unlink()
    os.mkfifo(fifo_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE


def test_oversized_watched_file_refused(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    model_path = repo / "plugins" / "superheroes" / "lib" / "model_registry.py"
    model_path.write_bytes(b"x" * (VS._MAX_READ_BYTES + 1))
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE


def test_version_sanitization_truncates_long_first_line(tmp_path):
    repo = tmp_path / "repo"
    long_version = "1." + ("2" * VS._MAX_VERSION_CHARS)
    _write_manifest(repo, version=long_version)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert long_version[:VS._MAX_VERSION_CHARS] in record["reason"]
    assert long_version not in record["reason"]


def test_version_sanitization_strips_non_printable_before_newline(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, version="0.\x0099.0")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert "\x00" not in record["reason"]
    assert "0.99.0" in record["reason"]


def test_version_sanitization_multiline_ignores_second_line(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, version="0.99.0\nsecond line ignored")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert "second line ignored" not in record["reason"]
    assert "0.99.0" in record["reason"]


def test_repo_plugin_dir_symlink_refused_not_in_reason(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    secret = tmp_path / "outside"
    secret.mkdir()
    manifest = secret / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": "0.30.0"}), encoding="utf-8")
    (secret / "version.txt").write_text("SECRET_LEAKED_CONTENT\n", encoding="utf-8")
    secret_lib = secret / "lib"
    secret_lib.mkdir()
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (secret_lib / os.path.basename(entry)).write_text(
            open(src, encoding="utf-8").read(),
            encoding="utf-8",
        )
    plugins_dir = repo / "plugins"
    plugins_dir.mkdir(parents=True)
    os.symlink(secret, plugins_dir / "superheroes")
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert "SECRET_LEAKED_CONTENT" not in record["reason"]


def test_containment_valid_read_when_repo_root_is_symlink(tmp_path):
    real_repo = tmp_path / "real-repo"
    _write_manifest(real_repo)
    _write_version_txt(real_repo)
    _copy_semantics_to(real_repo)
    link_repo = tmp_path / "link-repo"
    os.symlink(real_repo, link_repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(link_repo), plugin)
    assert record["status"] == VS.STATUS_CHECKED_CLEAN
    assert record["detail"] == VS.DETAIL_NO_DIVERGENCE
