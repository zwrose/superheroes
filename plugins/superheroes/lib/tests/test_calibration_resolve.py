import json
import os
import subprocess
import sys

import pytest

import calibration_resolve as cr
import core_md as cm
import mode_registry as mr

_MODULE_PATH = os.path.abspath(cr.__file__)


def _default_store_root(tmp_path):
    return str(tmp_path / "_store_isolation")


def _empty_store_root(tmp_path):
    d = tmp_path / "empty_store"
    d.mkdir()
    return str(d)


def _ensure_global_unified_layer(repo, store_root):
    store = mr.ensure_project_store(repo, root=store_root)
    cfg = os.path.join(store, "config")
    os.makedirs(cfg, exist_ok=True)
    layer = os.path.join(cfg, "review-crew.md")
    with open(layer, "w") as fh:
        fh.write("## Focus hints\n- code: x\n")
    return layer


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


def test_dispatch_core_falls_back_to_layer_without_core_md(tmp_path):
    """Headless bootstrap: layer exists without core.md — dispatch_core must not be null."""
    _init_repo(tmp_path)
    layer = tmp_path / ".claude" / "superheroes" / "review-crew.md"
    layer.parent.mkdir(parents=True)
    layer.write_text("## Threat model\npublic\n## Focus hints\n- code: x\n")
    out = cr.resolve(str(tmp_path))
    assert out["dispatch_core"] == str(layer)
    assert out["dispatch_layer"] == str(layer)


def test_migrated_unified_dispatch_core_carries_threat_model(tmp_path):
    """Migrated layout: specialists must receive core.md (threat model + patterns), not layer-only."""
    _init_repo(tmp_path)
    layer = tmp_path / ".claude" / "superheroes" / "review-crew.md"
    layer.parent.mkdir(parents=True)
    layer.write_text("## Focus hints\n- security: x\n")
    core = tmp_path / ".claude" / "superheroes" / "core.md"
    core.write_text(cm.render_core(
        {"verifyCommand": "npm test", "stackTags": [], "threatModel": "multi-tenant",
         "patterns": "- auth: src/a:1"},
        "confirmed", "2026-01-01", "2026-01-01"))
    out = cr.resolve(str(tmp_path))
    assert out["dispatch_core"] == str(core)
    assert out["dispatch_layer"] == str(layer)
    assert "multi-tenant" in core.read_text()
    assert out["dispatch_core"] != out["dispatch_layer"]


def test_supplied_root_empty_default_store_holds_unified_global_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = _default_store_root(tmp_path)
    empty = _empty_store_root(tmp_path)
    layer = _ensure_global_unified_layer(str(repo), default_store)
    with pytest.raises(cr.UnresolvableRootError) as excinfo:
        cr.resolve(str(repo), root=empty)
    exc = excinfo.value
    assert exc.reason == cr.REASON_UNRESOLVABLE_ROOT
    assert exc.root == empty
    assert exc.default_location == mr.GLOBAL
    assert exc.default_layer_path == layer


def test_supplied_root_empty_heal_true_still_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = _default_store_root(tmp_path)
    empty = _empty_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    with pytest.raises(cr.UnresolvableRootError):
        cr.resolve(str(repo), root=empty, heal=True)


def test_neither_root_has_calibration_returns_none(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    empty = _empty_store_root(tmp_path)
    out = cr.resolve(str(repo), root=empty)
    assert out["location"] == "none"
    assert out["exists"] is False


def test_root_none_calibrated_default_no_raise(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = _default_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    out = cr.resolve(str(repo))
    assert out["exists"] is True
    assert out["location"] == mr.GLOBAL


def test_supplied_root_resolves_even_when_default_also_calibrated(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo, "git@github.com:o/r.git")
    default_store = _default_store_root(tmp_path)
    supplied_store = tmp_path / "supplied_store"
    supplied_store.mkdir()
    _ensure_global_unified_layer(str(repo), default_store)
    supplied_layer = _ensure_global_unified_layer(str(repo), str(supplied_store))
    out = cr.resolve(str(repo), root=str(supplied_store))
    assert out["exists"] is True
    assert out["location"] == mr.GLOBAL
    assert out["layer_path"] == supplied_layer


def test_in_repo_layer_bogus_supplied_root_no_raise(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    empty = _empty_store_root(tmp_path)
    default_store = _default_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    layer = repo / ".claude" / "superheroes" / "review-crew.md"
    layer.parent.mkdir(parents=True)
    layer.write_text("## Focus hints\n- code: x\n")
    out = cr.resolve(str(repo), root=empty)
    assert out["exists"] is True
    assert out["location"] == mr.IN_REPO


def test_resolve_profile_path_propagates_unresolvable_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = _default_store_root(tmp_path)
    empty = _empty_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    with pytest.raises(cr.UnresolvableRootError):
        cr.resolve_profile_path(str(repo), root=empty)


def test_unresolvable_root_error_payload_keys(tmp_path):
    exc = cr.UnresolvableRootError(
        root="/bad", cwd="/repo", hero=cr.REVIEW_CREW,
        default_location=mr.GLOBAL, default_layer_path="/layer",
    )
    payload = exc.payload()
    assert set(payload.keys()) == {
        "refusal", "reason", "root", "cwd", "hero",
        "default_location", "default_layer_path", "remedy",
    }
    assert payload["refusal"] == "unresolvable-root"


def test_cli_resolve_root_empty_returns_2_stderr_refusal(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = _default_store_root(tmp_path)
    empty = _empty_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    proc = subprocess.run(
        [sys.executable, "-B", _MODULE_PATH, "resolve", "--root", empty],
        cwd=str(repo), capture_output=True, text=True,
        env={**os.environ, "WORKHORSE_STORE_ROOT": default_store},
    )
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
    payload = json.loads(proc.stderr)
    assert payload["reason"] == cr.REASON_UNRESOLVABLE_ROOT


def test_cli_resolve_bare_calibrated_returns_0_stdout_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    default_store = _default_store_root(tmp_path)
    _ensure_global_unified_layer(str(repo), default_store)
    proc = subprocess.run(
        [sys.executable, "-B", _MODULE_PATH, "resolve"],
        cwd=str(repo), capture_output=True, text=True,
        env={**os.environ, "WORKHORSE_STORE_ROOT": default_store},
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["exists"] is True
