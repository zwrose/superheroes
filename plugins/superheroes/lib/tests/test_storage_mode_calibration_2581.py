"""#2581 WO-1 — reviews read the layer and core.md the storage mode picks.

Every repository is a real `git init` repository under tmp_path (never committed to); every store
root is under tmp_path and passed explicitly where the API takes one. The session pin and the
calibration-read stamp take no root, so those tests use the default store root the conftest pins
under tmp_path. A "stale in-repo copy" is simply a file in the working tree.

Bite-proof record: wo1_2581_storage_mode_calibration
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import calibration_pin  # noqa: E402
import calibration_read  # noqa: E402
import calibration_resolve as cr  # noqa: E402
import cloud_setup_text  # noqa: E402
import core_md as cm  # noqa: E402
import mode_registry as mr  # noqa: E402
import model_tier_overrides  # noqa: E402
import store_core  # noqa: E402

CS = cloud_setup_text
ORIGIN = "https://github.com/acme/corner-shop.git"
SOURCE = "https://github.com/acme/superheroes.git"
COMMIT = "0123456789abcdef" * 2 + "01234567"
SUBDIR = "plugins/superheroes"
DAY_10_OCT = 1791633600.0  # 2026-10-10T12:00:00Z

_CORE_TEXT = cm.render_core(
    {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
    "confirmed", "2026-01-01", "2026-01-01")
_STALE_LAYER = "## Focus hints\n- stale: the old in-repo layer text that must not be read\n"
_GLOBAL_LAYER = "## Focus hints\n- global: the layer text of the global store\n"
_NEW_LAYER = "## Focus hints\n- fresh: a layer line written by configure after the switch\n"


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _repo(tmp_path, name="repo", remote=ORIGIN):
    path = tmp_path / name
    path.mkdir()
    _git(path, "init", "-q")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return str(path)


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _in_repo(cwd, name):
    return os.path.join(cwd, ".claude", "superheroes", name)


def _global(cwd, root, name):
    return os.path.join(mr.project_store_dir(cwd, root), "config", name)


def _register(cwd, root, mode):
    rec = mr.write_registry(cwd, mode, store_core.derive_identifiers(cwd)["remote_hash"], root=root)
    assert rec is not None and rec["storageMode"] == mode
    return rec


@pytest.fixture
def root(isolated_default_store_root):
    """The default store root the conftest pins, spelled as control_plane.store_root() spells it."""
    return os.path.realpath(isolated_default_store_root)


@pytest.fixture
def cwd(tmp_path):
    return _repo(tmp_path)


def test_r_layer_global(tmp_path, cwd, root):
    # axis: a stale in-repo layer never beats the global layer when the registry says global
    _register(cwd, root, mr.GLOBAL)
    _put(_global(cwd, root, "core.md"), _CORE_TEXT)
    layer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
    _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
    out = cr.resolve(cwd, root=root)
    assert out["dispatch_layer"] == layer
    assert out["layer_path"] == layer
    assert out["location"] == mr.GLOBAL
    assert cm.layer_path(cwd, "review-crew", root) == layer
    # a layer change written by configure reaches the session pin
    written = cm.write_layer(cwd, "review-crew", _NEW_LAYER, "confirmed", root=root)
    assert written["action"] == "written" and written["path"] == layer
    pin = calibration_pin.capture(cwd, str(tmp_path / "session-layer"))
    entry = pin["files"]["layer"]
    assert entry["source"] == layer
    with open(entry["path"], encoding="utf-8") as fh:
        assert "a layer line written by configure after the switch" in fh.read()


def test_r_layer_corner(cwd, root):
    # axis: the layer is the mode's, never the one beside a sole in-repo core.md
    _register(cwd, root, mr.GLOBAL)
    _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
    glayer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
    _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
    assert not os.path.exists(_global(cwd, root, "core.md"))
    assert cr.resolve(cwd, root=root)["dispatch_layer"] == glayer
    assert cm.layer_path(cwd, "review-crew", root) == glayer


def test_r_layer_legacy(cwd, root):
    # axis: a stale legacy in-repo profile never beats the global layer when the registry says global
    _register(cwd, root, mr.GLOBAL)
    _put(os.path.join(cwd, ".claude", "review-profile.md"), "## Threat model\nold legacy profile\n")
    glayer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
    _put(_global(cwd, root, "core.md"), _CORE_TEXT)
    assert cr.resolve(cwd, root=root)["dispatch_layer"] == glayer


def test_r_layer_inrepo(cwd, root):
    # axis: with the registry in-repo, the in-repo layer is the one read
    _register(cwd, root, mr.IN_REPO)
    ilayer = _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
    _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
    _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
    assert cr.resolve(cwd, root=root)["dispatch_layer"] == ilayer
    assert cm.layer_path(cwd, "review-crew", root) == ilayer


def _stamped_core(cwd, core):
    entries = calibration_read.stamp(cwd, "Read the calibration first: %s and then the diff." % core)
    named = [e for e in entries if e["label"] == calibration_read.LABEL_CORE]
    assert len(named) == 1, entries
    return named[0]


def test_r_core_p2(cwd, root):
    # axis: dispatch_core is the sole regular core.md, whichever layer is the dispatch layer
    _register(cwd, root, mr.GLOBAL)
    core = _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
    _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
    assert cr.resolve(cwd, root=root)["dispatch_core"] == core
    assert _stamped_core(cwd, core)["path"] == core


def test_r_core_p3(cwd):
    # axis: dispatch_core is the sole regular core.md, not the legacy profile that also exists
    core = _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
    _put(os.path.join(cwd, ".claude", "review-profile.md"), "## Threat model\nold legacy profile\n")
    assert not os.path.exists(_in_repo(cwd, "review-crew.md"))
    assert cr.resolve(cwd)["dispatch_core"] == core
    assert _stamped_core(cwd, core)["path"] == core


@pytest.mark.parametrize("layout", ["in-repo", "global", "legacy"])
def test_r_unchanged(cwd, root, layout):
    # axis: a project with one layer and one core.md resolves exactly as before
    if layout == "in-repo":
        core = _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
        layer = _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
        expected = {"location": mr.IN_REPO, "exists": True, "layout": "unified", "core_path": core,
                    "layer_path": layer, "legacy_path": None, "healed": False, "entry_id": None,
                    "dispatch_layer": layer, "dispatch_core": core}
        got = cr.resolve(cwd)
    elif layout == "global":
        _register(cwd, root, mr.GLOBAL)
        core = _put(_global(cwd, root, "core.md"), _CORE_TEXT)
        layer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
        expected = {"location": mr.GLOBAL, "exists": True, "layout": "unified", "core_path": core,
                    "layer_path": layer, "legacy_path": None, "healed": False, "entry_id": None,
                    "dispatch_layer": layer, "dispatch_core": core}
        got = cr.resolve(cwd, root=root)
    else:
        legacy = _put(os.path.join(cwd, ".claude", "review-profile.md"), "## Threat model\nx\n")
        expected = {"location": mr.IN_REPO, "exists": True, "layout": "legacy", "core_path": None,
                    "layer_path": None, "legacy_path": legacy, "healed": False, "entry_id": None,
                    "dispatch_layer": legacy, "dispatch_core": legacy}
        got = cr.resolve(cwd)
    assert got == expected


def test_r_pin_nonfile_peer(tmp_path, cwd, root):
    # axis: a regular core.md beats a non-file peer in the session pin
    _register(cwd, root, mr.GLOBAL)
    core = _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
    os.makedirs(_global(cwd, root, "core.md"))
    pin = calibration_pin.capture(cwd, str(tmp_path / "session-pin"))
    assert pin["files"]["core"]["source"] == core
    assert pin["files"]["core"]["reason"] is None


def test_r_gate(cwd, root):
    # axis: the model-tier gate reads the picked layer first
    _register(cwd, root, mr.GLOBAL)
    _put(_global(cwd, root, "core.md"), _CORE_TEXT)
    glayer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
    _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
    assert model_tier_overrides.resolve_profile_path_for_gate(cwd, root=root)[0] == glayer
    assert cr.candidate_profile_paths(cwd, root=root)[0] == glayer


def test_r_cloud_placed(tmp_path, cwd):
    # axis: the calibration a cloud setup places carries the registry, so a cloud session reads the placed layer
    root_a, root_b = str(tmp_path / "store-a"), str(tmp_path / "store-b")
    _register(cwd, root_a, mr.GLOBAL)
    _put(_global(cwd, root_a, "core.md"), _CORE_TEXT)
    _put(_global(cwd, root_a, "review-crew.md"), _GLOBAL_LAYER)
    files = CS.calibration_files(cwd, root_a)
    assert "registry.json" in files
    for rel, data in files.items():
        path = os.path.join(mr.project_store_dir(cwd, root_b), *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
    placed = _global(cwd, root_b, "review-crew.md")
    assert cr.resolve(cwd, root=root_b)["dispatch_layer"] == placed


class World:
    pass


def _world(tmp_path, mode):
    w = World()
    w.tmp = tmp_path
    w.cwd = _repo(tmp_path)
    w.root = str(tmp_path / "store-root")
    home = tmp_path / "home"
    home.mkdir()
    w.env = {"HOME": str(home), "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-config"),
             "PATH": os.environ.get("PATH", "")}
    if mode is not None:
        _register(w.cwd, w.root, mode)
    return w


def _w_put(w, rel, text):
    return _put(os.path.join(mr.project_store_dir(w.cwd, w.root), *rel.split("/")), text)


def _stamp(files):
    digest = hashlib.sha256(json.dumps(sorted((k, v.hex()) for k, v in files.items())).encode())
    return "2026-10-10:" + digest.hexdigest()[:12]


def _compose(w):
    return CS.compose(
        w.cwd, now=DAY_10_OCT, stamp_fn=_stamp, plugin_source=SOURCE, plugin_commit=COMMIT,
        plugin_subdir=SUBDIR, project_name="Corner Shop", root=w.root, env=w.env,
        source_dir=str(w.tmp / "opt" / "src"), plugin_dir=str(w.tmp / "opt" / "plugin"))


def _refusal(result, reason):
    assert result["action"] == "refused" and result["reason"] == reason, result
    assert "text" not in result


def _registryless_world(tmp_path):
    """A global store with a hero layer and a core.md, and no registry."""
    w = _world(tmp_path, None)
    _w_put(w, "config/core.md", "# Core\nline two\n")
    _w_put(w, "config/review-crew.md", "# Crew\nsecond\n")
    assert mr.read_registry(w.cwd, w.root) is None
    return w


def test_r_cloud_backfill(tmp_path):
    # axis: agreeing evidence is recorded before the calibration is placed
    w = _registryless_world(tmp_path)
    assert _compose(w)["action"] == "written"
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.GLOBAL
    assert "registry.json" in CS.calibration_files(w.cwd, w.root)


def _write_returns_none(*args, **kwargs):
    return None


def _write_raises(*args, **kwargs):
    raise OSError("store unwritable")


def _resolve_provisional(*args, **kwargs):
    return {"mode": "global", "authoritative": False, "source": "provisional", "evidence": "disagree"}


@pytest.mark.parametrize("attr,replacement", [
    pytest.param("write_registry", _write_returns_none, id="lock"),
    pytest.param("write_registry", _write_raises, id="raises"),
    pytest.param("resolve", _resolve_provisional, id="provisional"),
])
def test_r_cloud_unrecorded(tmp_path, monkeypatch, attr, replacement):
    # axis: a global store with a hero layer and no valid registry is never placed
    w = _registryless_world(tmp_path)
    monkeypatch.setattr(CS.mode_registry, attr, replacement)
    _refusal(_compose(w), "storage-mode-unrecorded")


def test_r_cloud_greenfield(tmp_path):
    # axis: a store with a core.md and no hero layer is placed as before, with no registry written
    w = _world(tmp_path, None)
    _w_put(w, "config/core.md", "# Core\nline two\n")
    result = _compose(w)
    assert result["action"] == "written", result
    assert mr.read_registry(w.cwd, w.root) is None


def test_r_stamped_files_readonly(tmp_path):
    # axis: the stamp's file view writes nothing, so it never records a registry
    w = _world(tmp_path, None)
    _w_put(w, "config/review-crew.md", "# Crew\nsecond\n")
    CS.stamped_files(w.cwd, w.root)
    assert not os.path.exists(mr.registry_path(w.cwd, w.root))
