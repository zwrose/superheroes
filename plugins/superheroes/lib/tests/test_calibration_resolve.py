import os
import subprocess

import calibration_resolve as cr
import core_md as cm
import mode_registry as mr


def _init_repo(path, remote=None):
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)


def test_resolve_unified_in_repo(tmp_path):
    _init_repo(tmp_path)
    layer = tmp_path / ".claude" / "superheroes" / "review-crew.md"
    layer.parent.mkdir(parents=True)
    layer.write_text("## Focus hints\n- code: x\n")
    core = tmp_path / ".claude" / "superheroes" / "core.md"
    core.write_text(cm.render_core(
        {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
        "confirmed", "2026-01-01", "2026-01-01"))
    out = cr.resolve(str(tmp_path))
    assert out["exists"] is True
    assert out["layout"] == "unified"
    assert out["location"] == mr.IN_REPO
    assert out["layer_path"] == str(layer)
    assert out["core_path"] == str(core)


def test_resolve_legacy_in_repo_when_no_layer(tmp_path):
    _init_repo(tmp_path)
    legacy = tmp_path / ".claude" / "review-profile.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("## Threat model\nx\n")
    out = cr.resolve(str(tmp_path))
    assert out["exists"] is True
    assert out["layout"] == "legacy"
    assert out["legacy_path"] == str(legacy)
    assert out["dispatch_core"] == str(legacy)
    assert out["dispatch_layer"] == str(legacy)


def test_resolve_global_unified_layer_direct(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    registry = str(tmp_path / "registry")
    import mode_registry as mr
    store = mr.ensure_project_store(str(tmp_path), root=registry)
    cfg = os.path.join(store, "config")
    os.makedirs(cfg, exist_ok=True)
    layer = os.path.join(cfg, "review-crew.md")
    open(layer, "w").write("## Focus hints\n- code: x\n")
    out = cr.resolve(str(tmp_path), root=registry)
    assert out["exists"] is True
    assert out["layout"] == "unified"
    assert out["location"] == mr.GLOBAL
    assert out["layer_path"] == layer
    assert out["dispatch_layer"] == layer


def test_resolve_none_on_greenfield(tmp_path):
    _init_repo(tmp_path)
    out = cr.resolve(str(tmp_path))
    assert out["exists"] is False
    assert out["location"] == "none"
