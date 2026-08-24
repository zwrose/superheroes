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
    assert record["status"] == "not-checked"
    assert record["detail"] == "not-source-repo"
    assert record["inspectedRoot"] == ""


def test_identity_gate_wrong_name_not_checked(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, name="other-plugin")
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == "not-checked"
    assert record["detail"] == "not-source-repo"
    assert record["inspectedRoot"] == ""


def test_identity_gate_manifest_symlink_not_checked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    real_manifest = tmp_path / "real-plugin.json"
    real_manifest.write_text(json.dumps({"name": "superheroes", "version": "0.30.0"}), encoding="utf-8")
    manifest_dir = repo / "plugins" / "superheroes" / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    os.symlink(real_manifest, manifest_dir / "plugin.json")
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == "not-checked"
    assert record["detail"] == "not-source-repo"


def test_self_gate_repo_plugin_not_checked(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = str(repo / "plugins" / "superheroes")
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == "not-checked"
    assert record["detail"] == "self"
    assert record["inspectedRoot"] == ""


def test_no_skew_identical_semantics_checked_clean(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == "checked-clean"
    assert record["detail"] == "no-divergence"
    assert record["inspectedRoot"] == os.path.abspath(str(repo))
    assert "0.29.0" in record["reason"]
    assert "0.31.0" in record["reason"]


def test_skew_model_registry_divergent(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo, "0.31.0")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path, suffix="# skew marker\n")
    record = VS.detect(str(repo), plugin)
    _assert_record_shape(record)
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "semantics-divergent"
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
    assert record["status"] == "checked-degraded"
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
    _assert_record_shape(record)
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "evidence-unreadable"
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
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "evidence-unreadable"
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
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "evidence-unreadable"
    assert record["status"] != "checked-clean"


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
    assert record["status"] == "checked-clean"
    assert "unknown" in record["reason"]


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
    assert record["status"] == "checked-degraded"
    assert "unknown" in record["reason"]


def test_repo_root_missing_not_checked(tmp_path):
    repo = tmp_path / "missing-repo"
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == "not-checked"
    assert record["detail"] == "not-source-repo"


def test_version_txt_absent_reason_uses_unknown(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == "checked-clean"
    assert "unknown" in record["reason"]


def test_version_txt_symlink_refused_not_in_reason(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _copy_semantics_to(repo)
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET_LEAKED_CONTENT", encoding="utf-8")
    version_path = repo / "plugins" / "superheroes" / "version.txt"
    version_path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(secret, version_path)
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == "checked-clean"
    assert "SECRET_LEAKED_CONTENT" not in record["reason"]
    assert "unknown" in record["reason"]


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
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "evidence-unreadable"


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
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "evidence-unreadable"


def test_oversized_watched_file_refused(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _write_version_txt(repo)
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    model_path = repo / "plugins" / "superheroes" / "lib" / "model_registry.py"
    model_path.write_bytes(b"x" * (VS._MAX_READ_BYTES + 1))
    record = VS.detect(str(repo), plugin)
    assert record["status"] == "checked-degraded"
    assert record["detail"] == "evidence-unreadable"


def test_version_sanitization_multiline_oversized_non_printable(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo)
    _copy_semantics_to(repo)
    version_path = repo / "plugins" / "superheroes" / "version.txt"
    version_path.parent.mkdir(parents=True, exist_ok=True)
    bad = "0.99.0\nsecond line ignored\x00\x07" + ("Z" * 200)
    version_path.write_text(bad, encoding="utf-8")
    plugin = _plugin_tree(tmp_path)
    record = VS.detect(str(repo), plugin)
    assert record["status"] == "checked-clean"
    assert "second line ignored" not in record["reason"]
    assert "0.99.0" in record["reason"]
    assert "\x00" not in record["reason"]
