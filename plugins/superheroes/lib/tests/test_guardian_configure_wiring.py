"""Guardian configure bootstrap wiring — _HEROES, offerable set, real-seam write-layer.

Copy-holders (name every copy per CONVENTIONS §11):
  - plugins/superheroes/skills/configure/reference/set-up.md
  - plugins/superheroes/skills/configure/reference/view-and-tune.md
Authoritative home:
  - core_md._HEROES (optional subset: minus hero_setup.MANDATORY)
"""
import json
import os
import re
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PLUGIN = os.path.abspath(os.path.join(_LIB, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import configure_view as cv
import core_md
import guardian_lens as gl
import guardian_sweep as gs
import hero_setup as HS
import mode_registry as mr
import store_core as sc
from guardian_fixtures import ensure_store, init_calibrated_repo, write_guardian_layer

_SET_UP = os.path.join(_PLUGIN, "skills", "configure", "reference", "set-up.md")
_VIEW_TUNE = os.path.join(_PLUGIN, "skills", "configure", "reference", "view-and-tune.md")
_CORE_MD_CLI = os.path.join(_LIB, "core_md.py")

_HERO_SLUG_RE = re.compile(
    r"\b(" + "|".join(re.escape(h) for h in core_md._HEROES) + r")\b"
)


def _optional_heroes():
    return set(core_md._HEROES) - HS.MANDATORY


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _optional_mentioned_in(text):
    """Optional heroes cited in configure prose — fail-closed anchor for the §11 drift guard."""
    return {h for h in _HERO_SLUG_RE.findall(text) if h not in HS.MANDATORY}


def test_optional_hero_roster_named_in_configure_reference_docs():
    """§11 drift guard: every optional hero in _HEROES appears in both configure reference docs."""
    optional = _optional_heroes()
    assert optional, "core_md._HEROES minus MANDATORY is empty — no authoritative optional roster"
    set_up = _read(_SET_UP)
    view_tune = _read(_VIEW_TUNE)
    for label, text in (("set-up.md", set_up), ("view-and-tune.md", view_tune)):
        mentioned = _optional_mentioned_in(text)
        assert mentioned, (
            "%s: parsed NO optional heroes — refusing to pass vacuously (file moved or reworded?)"
            % label
        )
        missing = optional - mentioned
        assert not missing, "%s missing optional hero name(s): %s" % (label, sorted(missing))


def test_guardian_is_offerable_not_mandatory(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = ensure_store(repo, str(tmp_path / "store"))
    expected = _optional_heroes()
    assert set(HS.offerable(repo, store)) == expected
    assert "guardian" in expected
    write_guardian_layer(tmp_path, {"thresholds": {"complexity": 50}})
    off = set(HS.offerable(repo, store))
    assert "guardian" not in off
    assert off == (expected - {"guardian"})


def test_declined_guardian_not_offered(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = ensure_store(repo, str(tmp_path / "store"))
    HS.mark_declined(repo, "guardian", store)
    assert "guardian" not in HS.offerable(repo, store)


def _run_write_layer(repo, store, body, *, status="provisional"):
    proc = subprocess.run(
        [sys.executable, _CORE_MD_CLI, "write-layer",
         "--cwd", repo, "--root", store, "--hero", "guardian", "--status", status],
        input=body, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _guardian_layer_body(thresholds=None):
    if thresholds is None:
        thresholds = {"complexity": 50}
    return "```json guardian-config\n%s\n```\n" % json.dumps(
        {"thresholds": thresholds}, indent=2)


def test_write_layer_guardian_in_repo_seam(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = ensure_store(repo, str(tmp_path / "store"))
    mr.write_registry(repo, mr.IN_REPO, "rk", root=store)
    out = _run_write_layer(repo, store, _guardian_layer_body())
    assert out["action"] == "written"
    screen = cv.render(repo, root=store)
    assert "## Layer: guardian" in screen
    cfg = gs.read_config(repo, root=store)
    assert cfg["thresholds"]["complexity"] == 50


def test_write_layer_guardian_global_seam(tmp_path):
    repo = init_calibrated_repo(tmp_path, remote="git@github.com:o/r.git")
    store = ensure_store(repo, str(tmp_path / "store"))
    project_store = mr.ensure_project_store(repo, root=store)
    cfg_dir = os.path.join(project_store, "config")
    os.makedirs(cfg_dir, exist_ok=True)
    sc.atomic_write(
        os.path.join(cfg_dir, "core.md"),
        core_md.render_core(
            {"verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": ""},
            "confirmed", "2026-01-01", "2026-01-01"))
    mr.write_registry(repo, mr.GLOBAL, "rk", root=store, now="2026-06-21T00:00:00Z")
    out = _run_write_layer(repo, store, _guardian_layer_body({"complexity": 75}))
    assert out["action"] == "written"
    screen = cv.render(repo, root=store)
    assert "## Layer: guardian" in screen
    cfg = gs.read_config(repo, root=store)
    assert cfg["thresholds"]["complexity"] == 75


def test_empty_guardian_layer_yields_defaults(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = ensure_store(repo, str(tmp_path / "store"))
    mr.write_registry(repo, mr.IN_REPO, "rk", root=store)
    out = _run_write_layer(repo, store, "")
    assert out["action"] == "written"
    cfg = gs.read_config(repo, root=store)
    assert cfg["thresholds"] == dict(gl.RED_LINE_THRESHOLDS)
    assert cfg["coverage"] == []


@pytest.mark.parametrize("mode,remote", [(mr.IN_REPO, None), (mr.GLOBAL, "git@github.com:o/r.git")])
def test_bootstrap_both_storage_modes(tmp_path, mode, remote):
    if mode == mr.GLOBAL:
        repo = init_calibrated_repo(tmp_path, remote=remote)
        store = ensure_store(repo, str(tmp_path / "store"))
        project_store = mr.ensure_project_store(repo, root=store)
        cfg_dir = os.path.join(project_store, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        sc.atomic_write(
            os.path.join(cfg_dir, "core.md"),
            core_md.render_core(
                {"verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": ""},
                "confirmed", "2026-01-01", "2026-01-01"))
        mr.write_registry(repo, mode, "rk", root=store, now="2026-06-21T00:00:00Z")
    else:
        repo = init_calibrated_repo(tmp_path)
        store = ensure_store(repo, str(tmp_path / "store"))
        mr.write_registry(repo, mode, "rk", root=store)
    out = _run_write_layer(repo, store, _guardian_layer_body({"complexity": 42}))
    assert out["action"] == "written"
    assert "## Layer: guardian" in cv.render(repo, root=store)
    assert gs.read_config(repo, root=store)["thresholds"]["complexity"] == 42
