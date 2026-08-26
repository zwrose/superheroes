import json
import os
import subprocess

import pytest

import core_md
import mode_migrate as mm
import mode_registry as mr
import store_core as sc

# The expected classification, written out rather than read from the constants under test.
# Deriving these from mm._DEFINITION_DOCS / mm._WORK_ITEM_RECORDS would make every bucketing
# assertion below pass under a coordinated narrowing of both the constant and its home of record
# (review probe 8, issue #935).
_EXPECTED_DEFINITION_DOCS = ("spec.md", "plan.md", "tasks.md")
_EXPECTED_WORK_ITEM_RECORDS = ("findings.md",)


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
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
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
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    moved = {os.path.basename(f["src"]) for f in m.files}
    assert {"core.md", "review-crew.md", "spec.md"} <= moved
    assert not any("registry.json" in f["src"] or "config.lock" in f["src"] for f in m.files)
    assert m.kind == "flip" and m.target == mr.GLOBAL
    assert m.cwd == str(tmp_path) and m.root == root
    assert m.remote_key == sc.derive_identifiers(str(tmp_path))["remote_hash"]


def test_plan_moves_findings_md_and_preview_buckets_it_as_a_work_item_record(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec body\n")
    sc.atomic_write(os.path.join(ddir, "findings.md"), "owner ratification\n")
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    moved = {f["src"] for f in m.files}
    spec_src = os.path.join(ddir, "spec.md")
    findings_src = os.path.join(ddir, "findings.md")
    assert spec_src in moved
    assert findings_src in moved
    pv = mm.preview(m)
    assert spec_src in pv["definitionDocs"]
    assert findings_src in pv["workItemRecords"]
    assert findings_src not in pv["definitionDocs"]
    assert findings_src not in pv["calibration"]


def test_preview_buckets_are_disjoint_and_cover_every_moved_file(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec\n")
    sc.atomic_write(os.path.join(ddir, "plan.md"), "plan\n")
    sc.atomic_write(os.path.join(ddir, "tasks.md"), "tasks\n")
    sc.atomic_write(os.path.join(ddir, "findings.md"), "findings\n")
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    pv = mm.preview(m)
    cal, defs, records = pv["calibration"], pv["definitionDocs"], pv["workItemRecords"]
    assert not (set(cal) & set(defs))
    assert not (set(cal) & set(records))
    assert not (set(defs) & set(records))
    assert set(cal) | set(defs) | set(records) == {f["src"] for f in m.files}


def test_calibration_bucket_excludes_every_work_item_doc(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec\n")
    sc.atomic_write(os.path.join(ddir, "plan.md"), "plan\n")
    sc.atomic_write(os.path.join(ddir, "tasks.md"), "tasks\n")
    sc.atomic_write(os.path.join(ddir, "findings.md"), "findings\n")
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    pv = mm.preview(m)
    assert pv["calibration"], "calibration bucket empty — the exclusion assertion would be vacuous"
    work_item_basenames = {"spec.md", "plan.md", "tasks.md", "findings.md"}
    for path in pv["calibration"]:
        assert os.path.basename(path) not in work_item_basenames


def test_plan_refuses_without_owner_authorization(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=False)
    assert m.blocked is True and "authorization" in m.reason.lower()


def test_execute_refuses_blocked_migration_and_leaves_registry_unchanged(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    reg_path = mr.registry_path(str(tmp_path), root)
    reg_before = open(reg_path, encoding="utf-8").read()
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=False)
    res = mm.execute(m, root=root)
    assert res["status"] == "blocked"
    assert "authorization" in res.get("reason", "").lower()
    reg_after = open(reg_path, encoding="utf-8").read()
    assert reg_before == reg_after


def test_preview_enumerates_without_owner_authorization_and_execute_stays_blocked(tmp_path, capsys):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec\n")
    capsys.readouterr()
    rc = mm.main(["preview", "--cwd", str(tmp_path), "--root", root, "--target", mr.GLOBAL])
    preview_out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert preview_out.get("blocked") is not True
    assert preview_out.get("calibration") or preview_out.get("definitionDocs")
    capsys.readouterr()
    rc = mm.main(["execute", "--cwd", str(tmp_path), "--root", root, "--target", mr.GLOBAL])
    execute_out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert execute_out.get("status") == "blocked"
    assert "FR-14" in execute_out.get("reason", "")


# --------------------------------------------------------------------------- WO-A #1136 read-only preview + execute authorization


def test_preview_leaves_absent_registry_absent(tmp_path, monkeypatch):
    # axis: preview path must not create the project store or write registry.json.
    _init_repo(tmp_path, "git@github.com:o/r.git")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "review-profile.md").write_text("x")
    root = str(tmp_path / "store")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    store_dir = mr.project_store_dir(str(tmp_path), root)
    reg_path = mr.registry_path(str(tmp_path), root)
    assert not os.path.isdir(store_dir)
    assert not os.path.isfile(reg_path)
    m = mm.enumerate_flip(str(tmp_path), mr.GLOBAL, root=root)
    pv = mm.preview(m)
    assert pv["target"] == mr.GLOBAL
    assert not os.path.isdir(store_dir)
    assert not os.path.isfile(reg_path)


def test_preview_migration_cannot_be_executed(tmp_path, monkeypatch):
    # axis: a preview Migration is unauthorized and execute must refuse without moving files.
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    spec_src = os.path.join(ddir, "spec.md")
    sc.atomic_write(spec_src, "spec\n")
    core_src = os.path.join(str(tmp_path), ".claude", "superheroes", "core.md")
    m = mm.enumerate_flip(str(tmp_path), mr.GLOBAL, root=root)
    res = mm.execute(m, root=root)
    assert res["status"] == "blocked"
    assert "authorization" in res.get("reason", "").lower()
    assert os.path.isfile(spec_src)
    assert os.path.isfile(core_src)


def test_plan_authorized_migration_still_executes(tmp_path):
    # axis: plan()'s authorized Migration still executes — positive control for execute gate.
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    assert m.owner_authorized is True
    res = mm.execute(m, root=root)
    assert res["status"] == "done"
    assert mr.resolve(str(tmp_path), root=root)["mode"] == mr.GLOBAL


# --------------------------------------------------------------------------- A4 preview


def test_preview_buckets_every_definition_doc_basename_by_name(tmp_path):
    # Narrowing _is_definition_doc to spec.md alone must go red here: each of the three
    # definition-doc basenames is asserted into definitionDocs by name, and findings.md is
    # asserted out of it.
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    for name in ("spec.md", "plan.md", "tasks.md", "findings.md"):
        sc.atomic_write(os.path.join(ddir, name), name + " body\n")
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    pv = mm.preview(m)
    for name in _EXPECTED_DEFINITION_DOCS:
        src = os.path.join(ddir, name)
        assert src in pv["definitionDocs"], name
        assert src not in pv["workItemRecords"], name
        assert src not in pv["calibration"], name
    for name in _EXPECTED_WORK_ITEM_RECORDS:
        src = os.path.join(ddir, name)
        assert src in pv["workItemRecords"], name
        assert src not in pv["definitionDocs"], name
        assert src not in pv["calibration"], name


def test_preview_disclosure_names_every_non_empty_bucket(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")

    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    for name in ("spec.md", "plan.md", "tasks.md", "findings.md"):
        sc.atomic_write(os.path.join(ddir, name), name + " body\n")
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    pv = mm.preview(m)
    disc = pv["disclosure"].lower()
    if pv["workItemRecords"]:
        assert "work-item record" in disc
    if pv["definitionDocs"]:
        assert "definition document" in disc
    if pv["calibration"]:
        assert "calibration" in disc

    mr.write_registry(str(tmp_path), mr.GLOBAL, "rk", root=root)
    gdir = os.path.join(mr.project_store_dir(str(tmp_path), root), "config")
    os.makedirs(gdir, exist_ok=True)
    sc.atomic_write(os.path.join(gdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "x"},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(gdir, "review-crew.md"), "<!-- review-crew: v1 -->\nbody\n")
    gdocs = os.path.join(mr.project_store_dir(str(tmp_path), root), "docs", "wi")
    os.makedirs(gdocs, exist_ok=True)
    for name in ("spec.md", "plan.md", "tasks.md", "findings.md"):
        sc.atomic_write(os.path.join(gdocs, name), name + " body\n")
    m = mm.plan(str(tmp_path), mr.IN_REPO, root=root, owner_authorized=True)
    pv = mm.preview(m)
    disc = pv["disclosure"].lower()
    if pv["workItemRecords"]:
        assert "work-item record" in disc
    if pv["definitionDocs"]:
        assert "definition document" in disc
    if pv["calibration"]:
        assert "calibration" in disc


def test_definition_docs_constant_tracks_definition_doc_doc_types():
    # _DEFINITION_DOCS is the *classification* set; DOC_TYPES is its home. A new definition-doc
    # type that is not added here would be silently bucketed as a work-item record.
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(mm.__file__)), "definition_doc.py")
    spec = importlib.util.spec_from_file_location("definition_doc_mm_test", path)
    dd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dd)
    assert set(mm._DEFINITION_DOCS) == {t + ".md" for t in dd.DOC_TYPES}


def test_expected_definition_docs_match_the_home_of_record():
    # Third leg of the coordinated-narrow guard: _EXPECTED_* (test-owned literal) vs DOC_TYPES
    # (home of record) vs _DEFINITION_DOCS (classification set). Narrowing any two of the three
    # leaves the third disagreeing.
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(mm.__file__)), "definition_doc.py")
    spec = importlib.util.spec_from_file_location("definition_doc_mm_test_expected", path)
    dd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dd)
    assert set(_EXPECTED_DEFINITION_DOCS) == {t + ".md" for t in dd.DOC_TYPES}


def test_preview_lists_calibration_and_defdocs(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    ddir = os.path.join(str(tmp_path), "docs", "superheroes", "wi")
    os.makedirs(ddir, exist_ok=True)
    sc.atomic_write(os.path.join(ddir, "spec.md"), "spec\n")
    pv = mm.preview(mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True))
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
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
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
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
    monkeypatch.setattr(mm, "_commit_registry", lambda *a, **k: False)
    res = mm.execute(m, root=root)
    assert res["status"] == "blocked"
    assert mr.resolve(str(tmp_path), root=root)["mode"] == mr.IN_REPO
    assert os.path.exists(os.path.join(str(tmp_path), ".claude", "superheroes", "core.md"))


def test_commit_registry_repo_root_unavailable_returns_false(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, "rk", root=root)
    real_atomic = sc.atomic_write

    def boom(path, text, **kw):
        if str(path).endswith("registry.json"):
            raise sc.RepoRootUnavailable("simulated")
        return real_atomic(path, text, **kw)

    monkeypatch.setattr(sc, "atomic_write", boom)
    assert mm._commit_registry(str(tmp_path), mr.IN_REPO, "rk", root=root) is False


def test_rebind_deferred_when_commit_registry_repo_root_unavailable(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    common = os.path.join(root, "projects", sc.derive_identifiers(str(tmp_path))["gitdir_hash"])
    os.makedirs(os.path.join(common, "config"), exist_ok=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "git@github.com:o/r.git"], check=True)
    real_atomic = sc.atomic_write

    def boom(path, text, **kw):
        if str(path).endswith("registry.json"):
            raise sc.RepoRootUnavailable("simulated")
        return real_atomic(path, text, **kw)

    monkeypatch.setattr(sc, "atomic_write", boom)
    res = mm.rebind(str(tmp_path), root=root)
    assert res["status"] == "deferred"


def test_execute_busy_when_lock_held(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    m = mm.plan(str(tmp_path), mr.GLOBAL, root=root, owner_authorized=True)
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
    assert res["status"] == "recovered"   # a real half-done flip was finished, not a no-op
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
    assert res["status"] == "recovered"   # a real pre-commit flip was backed out, not a no-op
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
    assert res["status"] == "rebound"   # a real re-key happened, not a no-op
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
    res = mm.rebind(str(tmp_path), root=root)
    assert res["status"] == "conflict" and res.get("applied") is not True
    assert "detail" in res
    survived = json.load(open(os.path.join(rdir, "registry.json")))
    assert survived["storageMode"] == "in-repo"   # surfaced for the owner, never clobbered (FR-9/FR-17)


def test_rebind_surfaces_kept_collisions_without_clobber(tmp_path):
    # the remote store already has a same-named, same-mode entry — rebind keeps it (no clobber)
    # and reports it in keptExisting so the owner knows the merge did not move everything.
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)   # common-dir store, mode global
    common = os.path.join(root, "projects", sc.derive_identifiers(str(tmp_path))["gitdir_hash"])
    sc.atomic_write(os.path.join(common, "config", "core.md"), "OLD core\n")
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "git@github.com:o/r.git"], check=True)
    rk = sc.derive_identifiers(str(tmp_path))["remote_hash"]
    rdir = os.path.join(root, "projects", rk)
    sc.atomic_write(os.path.join(rdir, "config", "core.md"), "NEW core\n")  # collision, same name
    res = mm.rebind(str(tmp_path), root=root)
    assert res["status"] == "rebound"
    assert os.path.join("config", "core.md") in res.get("keptExisting", [])
    assert open(os.path.join(rdir, "config", "core.md")).read() == "NEW core\n"  # dst kept, not clobbered


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


def test_cli_fr14_blocked_without_owner_authorized(tmp_path, capsys):
    """FR-14: plan/execute without --owner-authorized must refuse; preview enumerates read-only."""
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    _seed_in_repo_calibration(tmp_path)
    for cmd in ("plan", "execute"):
        capsys.readouterr()
        rc = mm.main([cmd, "--cwd", str(tmp_path), "--root", root, "--target", mr.GLOBAL])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0, cmd
        assert out.get("blocked") is True or out.get("status") == "blocked", (
            f"FR-14: {cmd} without --owner-authorized must be blocked")
        assert "FR-14" in out.get("reason", "")


def test_cli_recover_noop_outputs_json(tmp_path, capsys):
    _init_repo(tmp_path)
    rc = mm.main(["recover", "--cwd", str(tmp_path), "--root", str(tmp_path / "store")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "noop"


def test_recover_triggers_store_root_migration_only_on_a_real_run(monkeypatch, tmp_path):
    # #121 Part B: the one-time store-root rename auto-fires on a real run (root is None), never
    # when an explicit root override is in play (tests / pinned roots) — so the suite never moves
    # the real ~/.claude store.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))  # hermetic store reads
    calls = []
    monkeypatch.setattr(mm.control_plane, "migrate_store_root",
                        lambda: calls.append(1) or {"migrated": False})
    mm.recover(str(tmp_path), root=str(tmp_path / "store2"))  # explicit root → skip
    assert calls == []
    mm.recover(str(tmp_path), root=None)                      # real run → trigger once
    assert calls == [1]
