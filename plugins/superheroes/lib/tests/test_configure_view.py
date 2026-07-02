import os
import subprocess

import core_md
import configure_view as cv
import mode_registry as mr
import store_core as sc


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def test_render_shows_core_layers_and_is_read_only(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "x"},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    before = sorted(os.listdir(cdir))
    screen = cv.render(str(tmp_path), root=root)
    assert "pytest" in screen and "review-crew" in screen and "single-user" in screen
    assert sorted(os.listdir(cdir)) == before   # render wrote nothing (FR-18)


def test_render_shows_storage_health_line(tmp_path):
    import json
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, "rk", root=root)  # mints the live store
    orphan = os.path.join(root, "projects", "eeee000000000001")
    os.makedirs(orphan)
    sc.atomic_write(os.path.join(orphan, "meta.json"),
                    json.dumps({"schemaVersion": 1, "sourcePath": str(tmp_path / "gone")}))
    screen = cv.render(str(tmp_path), root=root)
    assert "storage health" in screen
    assert "1 orphaned" in screen


def test_render_shows_effective_model_tiers(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": ""},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    sc.atomic_write(os.path.join(str(tmp_path), ".claude", "review-profile.md"),
                    "## Model tiers\nreviewer: fable\n")
    screen = cv.render(str(tmp_path), root=root)
    assert "## Model tiers" in screen
    assert "reviewer: fable" in screen
    assert "synthesis: opus" in screen
    assert "mechanical: haiku" in screen
