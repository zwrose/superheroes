import os
import subprocess

import configure_view as cv
import core_md
import mode_registry as mr
import store_core as sc


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


_VET_BODY = (
    "### Gate check\n"
    "- **Evidence:** PR vet section\n"
    "- **The vet records:** gate receipt"
)


def test_render_vet_checks_when_declared(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(
        os.path.join(cdir, "core.md"),
        core_md.render_core(
            {"verifyCommand": "pytest", "stackTags": ["py"],
             "threatModel": "single-user", "patterns": "x",
             "vetChecks": _VET_BODY},
            "confirmed", "2026-06-27", "2026-06-27",
        ),
    )
    screen = cv.render(str(tmp_path), root=root)
    assert "### Vet checks" in screen
    assert "- Gate check" in screen
    assert "  evidence: PR vet section" in screen
    assert "  the vet records: gate receipt" in screen


def test_render_vet_checks_none_declared_line(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(
        os.path.join(cdir, "core.md"),
        core_md.render_core(
            {"verifyCommand": "pytest", "stackTags": ["py"],
             "threatModel": "single-user", "patterns": "x"},
            "confirmed", "2026-06-27", "2026-06-27",
        ),
    )
    screen = cv.render(str(tmp_path), root=root)
    assert "(none declared — the vet runs no project vet checks)" in screen


def test_render_vet_checks_malformed_line(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    bad_body = "### X\n- **The vet records:** only"
    sc.atomic_write(
        os.path.join(cdir, "core.md"),
        core_md.render_core(
            {"verifyCommand": "pytest", "stackTags": ["py"],
             "threatModel": "single-user", "patterns": "x",
             "vetChecks": bad_body},
            "confirmed", "2026-06-27", "2026-06-27",
        ),
    )
    screen = cv.render(str(tmp_path), root=root)
    assert "⚠ malformed: X — evidence-missing" in screen


def test_render_vet_checks_unreadable_when_core_corrupt(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    path = os.path.join(cdir, "core.md")
    sc.atomic_write(
        path,
        core_md.render_core(
            {"verifyCommand": "pytest", "stackTags": ["py"],
             "threatModel": "single-user", "patterns": "x",
             "vetChecks": _VET_BODY},
            "confirmed", "2026-06-27", "2026-06-27",
        ),
    )
    text = open(path, encoding="utf-8").read()
    sc.atomic_write(path, text.replace('"schemaVersion": 2', '"schemaVersion": "bad"'))
    screen = cv.render(str(tmp_path), root=root)
    assert "⚠ vet checks unreadable: core-md-unparseable" in screen


def test_render_vet_checks_unreadable_when_core_not_utf8(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    path = os.path.join(cdir, "core.md")
    with open(path, "wb") as fh:
        fh.write(b"\xff")
    screen = cv.render(str(tmp_path), root=root)
    assert "⚠ vet checks unreadable: core-md-unparseable" in screen
