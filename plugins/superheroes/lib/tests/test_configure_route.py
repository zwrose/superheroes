import os
import subprocess

import pytest

import configure_route as crt
import core_md
import mode_registry as mr
import store_core as sc


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def _seed_core(repo, status="confirmed"):
    cdir = os.path.join(str(repo), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "x"},
                                        status, "2026-06-27", "2026-06-27"))
    return cdir


def _seed_light_layers(cdir):
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")


@pytest.fixture(autouse=True)
def _isolate_hero_globals(monkeypatch, tmp_path):
    # route() reaches hero_evidence via resolve/gather_signals, which probes the REAL global
    # store (root redirects only the project store). Pin it so a stray global hero entry for
    # the fixed remote can't flip healthy->fix — the same isolation the mode_registry tests use.
    monkeypatch.setattr(mr, "_hero_global_root", lambda name: str(tmp_path / "heroglobal"))


def test_fresh_project_routes_to_set_up(tmp_path):
    _init_repo(tmp_path)
    out = crt.route(str(tmp_path), interactive=True, root=str(tmp_path / "store"))
    assert out["path"] == "set-up"


def test_healthy_project_with_layers_routes_to_view(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_light_layers(_seed_core(tmp_path))
    out = crt.route(str(tmp_path), interactive=True, root=root)
    assert out["path"] == "view"


def test_incomplete_set_up_layers_missing_routes_to_fix(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_core(tmp_path)
    out = crt.route(str(tmp_path), interactive=True, root=root)
    assert out["path"] == "fix" and "incomplete" in " ".join(out["reasons"]).lower()


def test_provisional_calibration_routes_to_fix(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_light_layers(_seed_core(tmp_path, status="provisional"))
    out = crt.route(str(tmp_path), interactive=True, root=root)
    assert out["path"] == "fix" and "provisional" in " ".join(out["reasons"]).lower()


def test_work_in_flight_false_when_no_control_plane(tmp_path):
    _init_repo(tmp_path)
    assert crt.work_in_flight(str(tmp_path), root=str(tmp_path / "store")) is False


def test_work_in_flight_true_when_an_issue_is_in_progress(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(crt, "_current_work", lambda cwd, root: {"workItem": "wi", "phase": "build"})
    assert crt.work_in_flight(str(tmp_path), root=str(tmp_path / "store")) is True


def test_structural_signal_routes_to_fix(tmp_path, monkeypatch):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_light_layers(_seed_core(tmp_path))   # otherwise healthy
    monkeypatch.setattr(crt.mode_reconcile, "gather_signals",
                        lambda cwd, root=None: [{"type": "migration-pending", "identity": "x", "detail": {}}])
    out = crt.route(str(tmp_path), interactive=True, root=root)
    assert out["path"] == "fix" and "structural" in " ".join(out["reasons"]).lower()


def test_staleness_drift_stays_in_view(tmp_path, monkeypatch):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_light_layers(_seed_core(tmp_path))   # healthy; a non-structural drift signal stays in view
    monkeypatch.setattr(crt.mode_reconcile, "gather_signals",
                        lambda cwd, root=None: [{"type": "hero-behind", "identity": "x", "detail": {}}])
    out = crt.route(str(tmp_path), interactive=True, root=root)
    assert out["path"] == "view"
