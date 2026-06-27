import json
import os
import subprocess

import pytest

import core_md
import mode_migrate as mm
import mode_registry as mr
import store_core as sc


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def _seed_in_repo_calibration(repo):
    cdir = os.path.join(str(repo), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "x"},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nbody\n")


def _seed_flip_inputs(tmp_path, root):
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec\n")


def _stage_to_phase(tmp_path, root, phase, flip_registry):
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=True)
    gdir = os.path.join(mr.project_store_dir(str(tmp_path), root), "config")
    os.makedirs(gdir, exist_ok=True)
    for f in m.files:
        with open(f["src"], encoding="utf-8") as fh:
            sc.atomic_write(f["dst"], fh.read())
    if flip_registry:
        mr.write_registry(str(tmp_path), mr.GLOBAL, "rk", root=root, allow_migration=True)
    sc.atomic_write(os.path.join(mr.project_store_dir(str(tmp_path), root), "migration-journal.json"),
                    json.dumps({"kind": "flip", "target": mr.GLOBAL, "phase": phase,
                                "files": [dict(x, done=True) for x in m.files]}))
    return m


# --------------------------------------------------------------------------- A3 plan


def test_plan_enumerates_calibration_and_defdocs_and_marks_bookkeeping_not_moved(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec body\n")
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=True)
    moved = {os.path.basename(f["src"]) for f in m.files}
    assert {"core.md", "review-crew.md", "spec.md"} <= moved
    assert not any("registry.json" in f["src"] or "config.lock" in f["src"] for f in m.files)
    assert m.kind == "flip" and m.target == mr.GLOBAL
    assert m.cwd == str(tmp_path) and m.root == root
    assert m.remote_key == sc.derive_identifiers(str(tmp_path))["remote_hash"]


def test_plan_refuses_when_not_interactive(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=False)
    assert m.blocked is True and "unattended" in m.reason.lower()


# --------------------------------------------------------------------------- A4 preview


def test_preview_lists_calibration_and_defdocs(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec\n")
    pv = mm.preview(mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=True))
    assert pv["target"] == mr.GLOBAL
    assert any("core.md" in c for c in pv["calibration"])
    assert any("spec.md" in d for d in pv["definitionDocs"])
    assert "collaborator" in pv["disclosure"].lower() or "repo" in pv["disclosure"].lower()


# --------------------------------------------------------------------------- A5 execute


def test_execute_flip_moves_everything_and_flips_mode(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=True)
    res = mm.execute(m, root=root)
    assert res["status"] == "done"
    assert mr.resolve(str(tmp_path), root=root)["mode"] == mr.GLOBAL
    assert not os.path.exists(os.path.join(str(tmp_path), ".claude", "superheroes", "core.md"))
    gdir = os.path.join(mr.project_store_dir(str(tmp_path), root), "config")
    assert os.path.isfile(os.path.join(gdir, "core.md"))
    assert mm.active_journal(str(tmp_path), root=root) is None


def test_execute_aborts_before_delete_when_registry_write_fails(tmp_path, monkeypatch):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=True)
    monkeypatch.setattr(mm, "_commit_registry", lambda *a, **k: False)
    res = mm.execute(m, root=root)
    assert res["status"] == "blocked"
    assert mr.resolve(str(tmp_path), root=root)["mode"] == mr.IN_REPO
    assert os.path.exists(os.path.join(str(tmp_path), ".claude", "superheroes", "core.md"))


def test_execute_busy_when_lock_held(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, interactive=True)
    with mr.config_lock(str(tmp_path), root=root) as got:
        assert got is True
        res = mm.execute(m, root=root)
    assert res["status"] == "busy"
    assert mr.resolve(str(tmp_path), root=root)["mode"] == mr.IN_REPO


# --------------------------------------------------------------------------- A6 recover


def test_recover_finishes_a_half_done_flip(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    _seed_flip_inputs(tmp_path, root)
    _stage_to_phase(tmp_path, root, "deleting", flip_registry=True)
    res = mm.recover(str(tmp_path), root=root)
    assert res["status"] in ("recovered", "noop")
    assert not os.path.exists(os.path.join(str(tmp_path), ".claude", "superheroes", "core.md"))
    assert not os.path.exists(os.path.join(str(tmp_path), "docs", "superheroes", "wi", "spec.md"))
    assert mm.active_journal(str(tmp_path), root=root) is None
    assert mm.recover(str(tmp_path), root=root)["status"] == "noop"


def test_recover_backs_out_a_pre_commit_flip(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    _seed_flip_inputs(tmp_path, root)
    _stage_to_phase(tmp_path, root, "copying", flip_registry=False)
    res = mm.recover(str(tmp_path), root=root)
    assert res["status"] in ("recovered", "noop")
    assert os.path.exists(os.path.join(str(tmp_path), ".claude", "superheroes", "core.md"))
    assert mr.resolve(str(tmp_path), root=root)["mode"] == mr.IN_REPO
    assert mm.active_journal(str(tmp_path), root=root) is None


def test_recover_noop_without_journal(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    assert mm.recover(str(tmp_path), root=root)["status"] == "noop"


# --------------------------------------------------------------------------- A7 rebind


def test_rebind_rekeys_store_and_mode_record_under_remote_key(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "git@github.com:o/r.git"], check=True)
    cdir = os.path.join(root, "projects", sc.derive_identifiers(str(tmp_path))["gitdir_hash"])
    res = mm.rebind(str(tmp_path), root=root)
    assert res["status"] in ("rebound", "noop")
    r = mr.resolve(str(tmp_path), root=root)
    assert r["mode"] == mr.GLOBAL and r["authoritative"] is True
    assert not os.path.isfile(os.path.join(cdir, "migration-journal.json"))


def test_rebind_conflict_is_surfaced_and_not_clobbered_on_disk(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "git@github.com:o/r.git"], check=True)
    rk = sc.derive_identifiers(str(tmp_path))["remote_hash"]
    rdir = os.path.join(root, "projects", rk)
    os.makedirs(rdir, exist_ok=True)
    sc.atomic_write(os.path.join(rdir, "registry.json"),
                    json.dumps({"schemaVersion": 1, "storageMode": "in-repo",
                                "remoteKey": rk, "createdAt": "2026-06-01T00:00:00Z"}))
    res = mm.rebind(str(tmp_path), root=root, interactive=True)
    assert res["status"] == "conflict" and res.get("applied") is not True
    assert "detail" in res
    survived = json.load(open(os.path.join(rdir, "registry.json")))
    assert survived["storageMode"] == "in-repo"


def test_rebind_refuses_conflict_headless(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "git@github.com:o/r.git"], check=True)
    rk = sc.derive_identifiers(str(tmp_path))["remote_hash"]
    rdir = os.path.join(root, "projects", rk)
    os.makedirs(rdir, exist_ok=True)
    sc.atomic_write(os.path.join(rdir, "registry.json"),
                    json.dumps({"schemaVersion": 1, "storageMode": "in-repo",
                                "remoteKey": rk, "createdAt": "2026-06-01T00:00:00Z"}))
    res = mm.rebind(str(tmp_path), root=root, interactive=False)
    assert res["status"] == "conflict" and res.get("applied") is not True


def test_interrupted_rebind_recovers_via_recover(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    cdir_key = sc.derive_identifiers(str(tmp_path))["gitdir_hash"]
    cdir = os.path.join(root, "projects", cdir_key)
    os.makedirs(cdir, exist_ok=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "git@github.com:o/r.git"], check=True)
    sc.atomic_write(os.path.join(cdir, "migration-journal.json"),
                    json.dumps({"kind": "rebind", "phase": "copying", "files": []}))
    res = mm.recover(str(tmp_path), root=root)
    assert res["status"] == "recovered"
    assert not os.path.isfile(os.path.join(cdir, "migration-journal.json"))


# --------------------------------------------------------------------------- A8 CLI


def test_cli_recover_noop_outputs_json(tmp_path, capsys):
    _init_repo(tmp_path)
    rc = mm.main(["recover", "--cwd", str(tmp_path), "--root", str(tmp_path / "store")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "noop"
