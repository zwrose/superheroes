# new file: test_calibration_cloud_guard.py
"""C6-WO-C: in a cloud session (CLAUDE_CODE_REMOTE == "true") no plugin code writes a calibration
file. The guard is store_core.atomic_write; outside a cloud session nothing changes."""
import json
import os
import subprocess

import pytest

import architect_config as ac
import core_md as cm
import mode_registry as mr
import store_core as sc

_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"],
          "threatModel": "single-user", "patterns": "- x: a.ts:1"}


def _project(tmp_path, monkeypatch):
    """A git repo plus a primed store (meta.json placed), store root pinned by env, not a cloud
    session yet. Returns (repo, store)."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    store = str(tmp_path / "store")
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    assert mr.ensure_project_store(repo, store) is not None
    return repo, os.path.realpath(store)


def _cloud(monkeypatch, value="true"):
    if value is None:
        monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", value)


def _rules_path(repo, store):
    return os.path.join(mr.project_store_dir(repo, store), "permission", "rules.json")


def _in_repo_core(repo):
    return os.path.join(repo, cm.in_repo_core_rel_path())


def _writers(repo, store):
    """name -> (write callable, the calibration file it targets)."""
    reg = mr.registry_path(repo, store)
    pol = ac.policy_path(repo, store)
    rules = _rules_path(repo, store)
    core = _in_repo_core(repo)
    return {
        "registry": (lambda: mr.write_registry(repo, mr.GLOBAL, "rk", root=store), reg),
        "doc-policy": (lambda: ac.write_policy(
            repo, {"location": "docs/specs", "visibility": ac.COMMITTED, "confirmed": True},
            root=store), pol),
        "rules": (lambda: sc.atomic_write(rules, "{}\n"), rules),
        "in-repo-core": (lambda: sc.atomic_write(core, "x\n"), core),
    }


def test_calibration_write_from_cloud_session_is_refused(tmp_path, monkeypatch):
    # GLOBAL-mode project: no registry, no in-repo evidence, so core.md lives in the store.
    repo, store = _project(tmp_path, monkeypatch)
    assert cm.write(repo, dict(_FACTS), "confirmed", root=store, now="2026-10-11")["action"] == "written"
    core = cm.core_path(repo, store)
    assert core.startswith(store + os.sep)
    before = open(core, "rb").read()
    src = tmp_path / "incoming-core.md"
    src.write_text("replacement\n")

    _cloud(monkeypatch)
    # core_md.relocate_file is the public core_md writer that lets the refusal propagate (the
    # other public writers catch OSError and defer; see the next test).
    with pytest.raises(sc.CalibrationWriteRefused) as exc:
        cm.relocate_file(str(src), core)
    assert str(exc.value) == "calibration-write-in-cloud-session: %s" % core
    assert isinstance(exc.value, PermissionError) and isinstance(exc.value, OSError)
    assert open(core, "rb").read() == before
    assert src.exists()  # F2: the guard raised at the write, so the remove was never reached


def test_core_md_deferring_writer_leaves_calibration_unchanged_in_cloud(tmp_path, monkeypatch):
    repo, store = _project(tmp_path, monkeypatch)
    cm.write(repo, dict(_FACTS), "confirmed", root=store, now="2026-10-11")
    core = cm.core_path(repo, store)
    before = open(core, "rb").read()

    _cloud(monkeypatch)
    res = cm.write_project_config_item(repo, "lint", {"enabled": True}, root=store)
    assert res["action"] == "deferred"
    assert open(core, "rb").read() == before


@pytest.mark.parametrize("name", ["registry", "doc-policy", "rules", "in-repo-core"])
def test_calibration_writers_refuse_in_cloud_and_leave_target_absent(tmp_path, monkeypatch, name):
    repo, store = _project(tmp_path, monkeypatch)
    write, target = _writers(repo, store)[name]
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        write()
    assert not os.path.exists(target)


def test_existing_in_repo_core_bytes_unchanged_when_write_refused(tmp_path, monkeypatch):
    repo, store = _project(tmp_path, monkeypatch)
    core = _in_repo_core(repo)
    os.makedirs(os.path.dirname(core))
    with open(core, "w") as fh:
        fh.write("original\n")
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(core, "changed\n")
    assert open(core).read() == "original\n"


@pytest.mark.parametrize("env", [None, "false", "", "1", "TRUE"])
@pytest.mark.parametrize("name", ["registry", "doc-policy", "rules", "in-repo-core"])
def test_calibration_writers_write_normally_outside_a_cloud_session(tmp_path, monkeypatch, name, env):
    # F5: only the exact string "true" arms the guard.
    repo, store = _project(tmp_path, monkeypatch)
    write, target = _writers(repo, store)[name]
    _cloud(monkeypatch, env)
    write()
    assert os.path.isfile(target)


def test_non_calibration_writes_stay_allowed_in_cloud(tmp_path, monkeypatch):
    repo, store = _project(tmp_path, monkeypatch)
    key_dir = os.path.join(store, "projects", "k")
    other = {
        os.path.join(key_dir, "reviews", "x.json"): "{}",
        os.path.join(key_dir, "config", "notes.txt"): "n",
        os.path.join(key_dir, "config", "sub", "deep.md"): "d",
        os.path.join(key_dir, "permission", "other.json"): "{}",
        os.path.join(key_dir, "migration-journal.json"): "{}",
        os.path.join(repo, ".claude", "other", "core.md"): "o",
        os.path.join(repo, ".claude", "superheroes", "x.txt"): "t",
        os.path.join(repo, "docs", "superheroes", "canon.md"): "c",
        os.path.join(repo, ".gitignore"): "node_modules/\n",
    }
    _cloud(monkeypatch)
    for path, text in other.items():
        sc.atomic_write(path, text)
        assert open(path).read() == text


def test_ensure_ignored_gitignore_rule_is_written_in_cloud(tmp_path, monkeypatch):
    repo, store = _project(tmp_path, monkeypatch)
    _cloud(monkeypatch)
    assert ac.ensure_ignored(repo, "docs/specs") is True
    assert "docs/specs/" in open(os.path.join(repo, ".gitignore")).read()


def test_cloud_session_still_writes_and_clears_pending_marker(tmp_path, monkeypatch):
    # F3: calibration-pending.json is in the project store but is none of the calibration names.
    repo, store = _project(tmp_path, monkeypatch)
    _cloud(monkeypatch)
    cm.mark_pending(repo, store, detail={"reason": "x"})
    pending = cm._pending_path(repo, store)
    assert os.path.isfile(pending)
    cm.clear_pending(repo, store)
    assert not os.path.exists(pending)


def test_symlinked_store_root_compares_equal(tmp_path, monkeypatch):
    # F4: realpath on both sides.
    repo, store = _project(tmp_path, monkeypatch)
    link = str(tmp_path / "store-link")
    os.symlink(store, link)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", link)
    via_link = os.path.join(link, "projects", "k", "registry.json")
    via_real = os.path.join(store, "projects", "k", "registry.json")
    _cloud(monkeypatch)
    for path in (via_link, via_real):
        with pytest.raises(sc.CalibrationWriteRefused):
            sc.atomic_write(path, "{}")
    assert not os.path.exists(via_real)


@pytest.mark.parametrize("meta_first", [True, False])
def test_resolve_backfill_read_in_cloud_returns_its_answer_and_writes_nothing(
        tmp_path, monkeypatch, meta_first):
    # F1: with meta.json placed the registry write itself is reached and refused; without it
    # ensure_project_store defers first. Either way the read answers.
    repo, store = _project(tmp_path, monkeypatch)
    if not meta_first:
        os.remove(os.path.join(mr.project_store_dir(repo, store), "meta.json"))
    os.makedirs(os.path.join(repo, ".claude"))
    with open(os.path.join(repo, ".claude", "review-profile.md"), "w") as fh:
        fh.write("x")
    monkeypatch.setattr(mr, "_hero_global_root", lambda n: str(tmp_path / ("g_" + n)))
    _cloud(monkeypatch)
    r = mr.resolve(repo, root=store, persist_backfill=True)
    assert r["mode"] == mr.IN_REPO and r["source"] == "backfilled" and r["authoritative"] is False
    assert not os.path.exists(mr.registry_path(repo, store))
    if not meta_first:
        assert not os.path.exists(os.path.join(mr.project_store_dir(repo, store), "meta.json"))


@pytest.mark.parametrize("rel,expected", [
    ("projects/k/registry.json", True),
    ("projects/k/meta.json", True),
    ("projects/k/doc-policy.json", True),
    ("projects/k/config/core.md", True),
    ("projects/k/config/review-crew.md", True),
    ("projects/k/permission/rules.json", True),
    ("projects/k/config/notes.txt", False),
    ("projects/k/config/a/b.md", False),
    ("projects/k/reviews/x.json", False),
    ("projects/k/calibration-pending.json", False),
    ("projects/registry.json", False),
    ("projects/k/sub/registry.json", False),
    ("other/k/registry.json", False),
    ("projects-extra/k/registry.json", False),
])
def test_is_calibration_path_store_rules(tmp_path, monkeypatch, rel, expected):
    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(store))
    assert sc.is_calibration_path(str(store / rel)) is expected


def test_explicit_store_root_differing_from_the_ambient_root_is_still_calibration(
        tmp_path, monkeypatch):
    ambient = tmp_path / "ambient"
    ambient.mkdir()
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(ambient))
    explicit = tmp_path / "explicit"
    assert sc.is_calibration_path(str(explicit / "projects/k/config/core.md")) is True
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(str(explicit / "projects/k/registry.json"), "{}")
    assert not (explicit / "projects").exists()


def test_guard_layout_names_are_the_writers_names():
    import architect_config as ac
    assert mr.REGISTRY_FILENAME == sc.REGISTRY_FILENAME
    assert mr.META_FILENAME == sc.META_FILENAME
    assert mr.CONFIG_DIRNAME == sc.CONFIG_DIRNAME
    assert os.path.basename(ac.policy_path("/x", "/r")) == sc.POLICY_FILENAME
