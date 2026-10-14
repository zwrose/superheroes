"""C8a-WO2 / C6 MUST-FIX and FU3: one guarded home for the calibration paths, and every writer and
mover goes through it. In a cloud session (CLAUDE_CODE_REMOTE == "true") no calibration file is
written, moved, copied or removed. Outside it nothing changes.

Residual, not covered here by design: the Canon writers (`definition_doc.py`, and `project_config.py`'s
Canon creation), which write into the documents location the owner chooses."""
import json
import os
import pathlib
import subprocess

import pytest

import calibration_paths as cp
import calibration_resolve as cr
import core_md as cm
import mode_migrate as mm
import mode_registry as mr
import model_tier_overrides as mto
import store_core as sc
from test_mode_migrate import _init_repo, _seed_flip_inputs, _stage_to_phase

_BLOCK = "## Model tiers\nreviewer-deep: opus\n"
_REFUSAL = {"status": "blocked", "reason": "calibration-write-in-cloud-session"}


def _cloud(monkeypatch, value="true"):
    if value is None:
        monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", value)


def _snapshot(base):
    """Every path under `base` (directories too) mapped to its bytes (a symlink to its target),
    `.git` left out: the same set of paths and the same bytes is "unchanged"."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(str(base)):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        out[dirpath] = None
        for name in filenames + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]:
            path = os.path.join(dirpath, name)
            out[path] = ("->" + os.readlink(path)) if os.path.islink(path) else pathlib.Path(path).read_bytes()
    return out


# ------------------------------------------------------------------ classification table

_TABLE = [
    # (id, path under tmp_path, is calibration)
    ("in-repo-core", "repo/.claude/superheroes/core.md", True),
    ("in-repo-layer", "repo/.claude/superheroes/review-crew.md", True),
    ("in-repo-nested-md", "repo/.claude/superheroes/sub/x.md", False),
    ("in-repo-non-md", "repo/.claude/superheroes/x.json", False),
    ("in-repo-md-elsewhere", "repo/.claude/x/core.md", False),
    ("legacy-inrepo-profile", "repo/.claude/review-profile.md", True),
    ("legacy-inrepo-other-md", "repo/.claude/other.md", False),
    ("legacy-inrepo-deeper", "repo/.claude/sub/review-profile.md", False),
    ("legacy-inrepo-no-claude-dir", "repo/review-profile.md", False),
    ("legacy-store-profile", "legacy/entries/abc123/review-profile.md", True),
    ("legacy-store-other-file", "legacy/entries/abc123/review-decisions.json", False),
    ("legacy-store-no-entry-dir", "legacy/entries/review-profile.md", False),
    ("legacy-store-too-deep", "legacy/entries/abc123/sub/review-profile.md", False),
    ("legacy-store-not-entries", "legacy/other/abc123/review-profile.md", False),
    ("store-registry", "store/projects/k/registry.json", True),
    ("store-meta", "store/projects/k/meta.json", True),
    ("store-doc-policy", "store/projects/k/doc-policy.json", True),
    ("store-config-md", "store/projects/k/config/core.md", True),
    ("store-config-txt", "store/projects/k/config/notes.txt", False),
    ("store-config-nested-md", "store/projects/k/config/a/b.md", False),
    ("store-permission-rules", "store/projects/k/permission/rules.json", True),
    ("store-permission-other", "store/projects/k/permission/other.json", False),
    ("store-reviews", "store/projects/k/reviews/x.json", False),
    ("store-registry-not-under-key", "store/projects/registry.json", False),
    ("store-other-dir", "store/other/k/registry.json", False),
]


@pytest.mark.parametrize("rel,expected", [(r, e) for _, r, e in _TABLE], ids=[i for i, _, _ in _TABLE])
def test_classification_table(tmp_path, rel, expected):
    # axis: each path kind is (or is not) classified as calibration, the two legacy review-profile
    # locations included — see bite-proof record c8a_wo2.md
    assert cp.is_calibration_path(str(tmp_path / rel)) is expected


def test_classification_follows_a_symlinked_store_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    os.symlink(real, link)
    assert cp.is_calibration_path(str(link / "projects/k/registry.json")) is True
    assert cp.is_calibration_path(str(link / "entries/h/review-profile.md")) is True
    assert cp.is_calibration_path(str(link / "projects/k/reviews/x.json")) is False


def test_classification_sees_a_symlink_standing_where_a_calibration_file_belongs(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("keep\n")
    store = tmp_path / "store" / "projects" / "k"
    store.mkdir(parents=True)
    os.symlink(outside, store / "registry.json")
    assert cp.is_calibration_path(str(store / "registry.json")) is True


def test_classification_of_an_unresolvable_path_does_not_raise(tmp_path):
    loop = tmp_path / "store" / "projects" / "k"
    loop.mkdir(parents=True)
    os.symlink(str(loop / "registry.json"), str(loop / "registry.json"))   # a link to itself
    assert cp.is_calibration_path(str(loop / "registry.json")) is True
    assert cp.is_calibration_path(str(loop / "other.json")) is False
    assert cp.is_calibration_path(str(tmp_path / "projects/k/regis\0try.json")) is False
    assert cp.is_calibration_path(str(tmp_path / "projects/k/registry.json\0")) is False


def test_store_core_names_are_the_new_homes_names():
    assert sc.is_calibration_path is cp.is_calibration_path
    assert sc.REGISTRY_FILENAME == cp.REGISTRY_FILENAME
    assert sc.META_FILENAME == cp.META_FILENAME
    assert sc.POLICY_FILENAME == cp.POLICY_FILENAME
    assert sc.CONFIG_DIRNAME == cp.CONFIG_DIRNAME
    assert sc.PERMISSION_DIRNAME == cp.PERMISSION_DIRNAME
    assert sc.PERMISSION_RULES_FILENAME == cp.PERMISSION_RULES_FILENAME
    assert os.path.dirname(cm.in_repo_core_rel_path()) == cp.IN_REPO_DIR


def test_legacy_in_repo_name_equals_mode_registrys_review_crew_entry():
    # the review-crew key of mode_registry._HERO_LEGACY_INREPO maps to the review profile
    assert cp.LEGACY_INREPO_REVIEW_PROFILE == mr._HERO_LEGACY_INREPO["review-crew"]


def test_legacy_store_name_matches_calibration_resolves_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    legacy_root = tmp_path / "legacy-root"
    path = cr._legacy_global_profile_path(str(repo), legacy_root=str(legacy_root))
    parts = pathlib.PurePath(path).parts
    assert parts[-3] == cp.LEGACY_STORE_ENTRIES_DIRNAME     # entries/<hash>/
    assert parts[-1] == cp.LEGACY_STORE_PROFILE_FILENAME    # review-profile.md
    assert cp.is_calibration_path(path) is True


# ------------------------------------------------------------------ store_core.atomic_write

@pytest.mark.parametrize("rel", [r for i, r, e in _TABLE if e], ids=[i for i, r, e in _TABLE if e])
def test_atomic_write_refuses_every_calibration_kind_and_leaves_bytes(tmp_path, monkeypatch, rel):
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_bytes(b"before\n")
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(str(path), "after\n")
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("value", [None, "false", "TRUE", "True", "1", ""])
def test_atomic_write_refuses_only_on_the_exact_string_true(tmp_path, monkeypatch, value):
    path = tmp_path / "store/projects/k/registry.json"
    _cloud(monkeypatch, value)
    sc.atomic_write(str(path), "after\n")
    assert path.read_text() == "after\n"


def test_atomic_write_does_not_create_the_missing_parent_of_a_refused_legacy_path(
        tmp_path, monkeypatch):
    path = tmp_path / "legacy" / "entries" / "h" / "review-profile.md"
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(str(path), "x\n")
    assert not (tmp_path / "legacy").exists()


def test_atomic_write_refuses_through_a_symlinked_store_root(tmp_path, monkeypatch):
    real = tmp_path / "real"
    (real / "projects/k").mkdir(parents=True)
    (real / "projects/k/registry.json").write_bytes(b"before\n")
    os.symlink(real, tmp_path / "link")
    before = _snapshot(real)
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(str(tmp_path / "link/projects/k/registry.json"), "after\n")
    assert _snapshot(real) == before


def test_atomic_write_refuses_a_symlink_at_the_calibration_path_and_leaves_its_target(
        tmp_path, monkeypatch):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"keep\n")
    store = tmp_path / "store/projects/k"
    store.mkdir(parents=True)
    os.symlink(outside, store / "registry.json")
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(str(store / "registry.json"), "after\n")
    assert outside.read_bytes() == b"keep\n"
    assert os.path.islink(store / "registry.json")


def test_atomic_write_refuses_a_self_linked_calibration_path(tmp_path, monkeypatch):
    store = tmp_path / "store/projects/k"
    store.mkdir(parents=True)
    os.symlink(str(store / "registry.json"), str(store / "registry.json"))
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        sc.atomic_write(str(store / "registry.json"), "after\n")


def test_atomic_write_writes_text_as_utf8(tmp_path, monkeypatch):
    _cloud(monkeypatch, None)
    path = tmp_path / "x.txt"
    sc.atomic_write(str(path), "café — ok\n")
    assert path.read_bytes() == "café — ok\n".encode("utf-8")


# ------------------------------------------------------------------ model_tier_overrides

def _profile_layers(tmp_path):
    """name -> the profile path a model-tier write can target."""
    return {
        "in-repo-layer": tmp_path / "repo/.claude/superheroes/review-crew.md",
        "store-layer": tmp_path / "store/projects/k/config/review-crew.md",
        "legacy-in-repo": tmp_path / "repo/.claude/review-profile.md",
        "legacy-store": tmp_path / "legacy/entries/h/review-profile.md",
    }


@pytest.mark.parametrize("layer", ["in-repo-layer", "store-layer", "legacy-in-repo", "legacy-store"])
def test_update_overrides_refuses_in_a_cloud_session_for_every_layer(tmp_path, monkeypatch, layer):
    # axis: the model-tier writer goes through the guarded atomic_write, not a private os.replace —
    # see bite-proof record c8a_wo2.md
    path = _profile_layers(tmp_path)[layer]
    path.parent.mkdir(parents=True)
    path.write_bytes(_BLOCK.encode())
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        mto.update_overrides(str(path), {"reviewer-deep": "sonnet"}, [])
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("layer", ["store-layer", "legacy-store"])
def test_update_overrides_refuses_without_creating_a_missing_parent(tmp_path, monkeypatch, layer):
    path = _profile_layers(tmp_path)[layer]
    _cloud(monkeypatch)
    with pytest.raises(sc.CalibrationWriteRefused):
        mto.update_overrides(str(path), {"reviewer-deep": "sonnet"}, [])
    assert not path.parent.exists()


@pytest.mark.parametrize("layer", ["in-repo-layer", "store-layer", "legacy-in-repo", "legacy-store"])
def test_update_overrides_still_writes_outside_a_cloud_session(tmp_path, monkeypatch, layer):
    path = _profile_layers(tmp_path)[layer]
    path.parent.mkdir(parents=True)
    path.write_bytes(_BLOCK.encode())
    _cloud(monkeypatch, None)
    res = mto.update_overrides(str(path), {"reviewer-deep": "sonnet"}, [])
    assert res["ok"] is True
    assert mto.load_overrides(str(path)) == {"reviewer-deep": "sonnet"}


def test_update_overrides_still_writes_a_non_calibration_path_in_a_cloud_session(
        tmp_path, monkeypatch):
    path = tmp_path / "elsewhere" / "profile.md"
    path.parent.mkdir()
    path.write_bytes(_BLOCK.encode())
    _cloud(monkeypatch)
    assert mto.update_overrides(str(path), {"reviewer-deep": "sonnet"}, [])["ok"] is True
    assert mto.load_overrides(str(path)) == {"reviewer-deep": "sonnet"}


def _cli_profile(tmp_path):
    cal = tmp_path / "repo" / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    core = cm.render_core({"verifyCommand": "npm test", "stackTags": [], "threatModel": "t",
                           "patterns": ""}, "confirmed", "2026-01-01", "2026-01-01")
    (cal / "core.md").write_text(core, encoding="utf-8")
    profile = cal / "review-crew.md"
    profile.write_bytes(_BLOCK.encode())
    return profile


def test_cli_write_prints_one_json_refusal_line_and_exits_1_in_a_cloud_session(
        tmp_path, monkeypatch, capsys):
    # axis: the CLI turns the cloud refusal into one JSON line and exit 1, not a traceback — see
    # bite-proof record c8a_wo2.md
    profile = _cli_profile(tmp_path)
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    rc = mto.main(["model_tier_overrides.py", "write", "--profile", str(profile),
                   "--set", "reviewer-deep=sonnet"])
    out = capsys.readouterr().out
    assert rc == 1
    assert len(out.splitlines()) == 1
    assert json.loads(out) == {"ok": False, "reason": "calibration-write-in-cloud-session"}
    assert _snapshot(tmp_path) == before


def test_cli_write_still_succeeds_outside_a_cloud_session(tmp_path, monkeypatch, capsys):
    profile = _cli_profile(tmp_path)
    _cloud(monkeypatch, None)
    rc = mto.main(["model_tier_overrides.py", "write", "--profile", str(profile),
                   "--set", "reviewer-deep=sonnet"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert mto.load_overrides(str(profile)) == {"reviewer-deep": "sonnet"}


# ------------------------------------------------------------------ mode_migrate movers

def _rebind_scenario(tmp_path, monkeypatch):
    """A git repo whose pre-remote (common-dir) store holds a registry and config, a remote added
    since, and a remote-keyed store that already holds an entry. Not a cloud session yet."""
    _cloud(monkeypatch, None)
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    root = str(tmp_path / "store")
    mr.write_registry(str(repo), mr.GLOBAL, None, root=root)
    common = os.path.join(root, "projects", sc.derive_identifiers(str(repo))["gitdir_hash"])
    sc.atomic_write(os.path.join(common, "config", "core.md"), "OLD core\n")
    sc.atomic_write(os.path.join(common, "config", "review-crew.md"), "crew\n")
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:o/r.git"],
                   check=True)
    remote = os.path.join(root, "projects", sc.derive_identifiers(str(repo))["remote_hash"])
    sc.atomic_write(os.path.join(remote, "config", "notes.md"), "NEW notes\n")
    return repo, root, common


def test_rebind_refuses_in_a_cloud_session_before_any_mutation(tmp_path, monkeypatch):
    # axis: rebind moves the registry and config tree only outside a cloud session; in one both
    # trees are untouched — see bite-proof record c8a_wo2.md
    repo, root, common = _rebind_scenario(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    refused = mm.rebind(str(repo), root=root)
    assert _snapshot(tmp_path) == before
    assert refused == _REFUSAL
    # the same scenario does rebind outside a cloud session, so the refusal above is not vacuous
    _cloud(monkeypatch, None)
    assert mm.rebind(str(repo), root=root)["status"] == "rebound"
    assert _snapshot(tmp_path) != before


def test_recover_of_a_rebind_journal_refuses_in_a_cloud_session(tmp_path, monkeypatch):
    repo, root, common = _rebind_scenario(tmp_path, monkeypatch)
    sc.atomic_write(os.path.join(common, "migration-journal.json"),
                    json.dumps({"kind": "rebind", "phase": "copying", "files": []}))
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    refused = mm.recover(str(repo), root=root)
    assert _snapshot(tmp_path) == before
    assert refused == _REFUSAL
    _cloud(monkeypatch, None)
    assert mm.recover(str(repo), root=root)["status"] == "recovered"


@pytest.mark.parametrize("phase,flip_registry", [("deleting", True), ("copying", False)])
def test_recover_of_a_flip_journal_refuses_in_a_cloud_session(
        tmp_path, monkeypatch, phase, flip_registry):
    # axis: recover removes calibration sources (finish) or copies (back out) only outside a cloud
    # session — see bite-proof record c8a_wo2.md
    _cloud(monkeypatch, None)
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    _seed_flip_inputs(tmp_path, root)
    _stage_to_phase(tmp_path, root, phase, flip_registry=flip_registry)
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    refused = mm.recover(str(tmp_path), root=root)
    assert _snapshot(tmp_path) == before
    assert refused == _REFUSAL
    _cloud(monkeypatch, None)
    assert mm.recover(str(tmp_path), root=root)["status"] == "recovered"
    assert _snapshot(tmp_path) != before


def test_recover_with_no_journal_refuses_in_a_cloud_session_and_skips_the_store_root_rename(
        tmp_path, monkeypatch):
    _init_repo(tmp_path)
    calls = []
    monkeypatch.setattr(mm.control_plane, "migrate_store_root", lambda: calls.append(1) or {})
    _cloud(monkeypatch)
    assert mm.recover(str(tmp_path), root=None) == _REFUSAL
    assert calls == []


@pytest.mark.parametrize("value", [None, "false", "TRUE"])
def test_mode_migrate_only_refuses_on_the_exact_string_true(tmp_path, monkeypatch, value):
    _init_repo(tmp_path)
    _cloud(monkeypatch, value)
    assert mm.recover(str(tmp_path), root=str(tmp_path / "store")) == {"status": "noop"}
    assert mm.rebind(str(tmp_path), root=str(tmp_path / "store")) == {"status": "noop"}


# ------------------------------------------------------------------ store_sweep (orphan removal)

def _orphan_store(tmp_path):
    root = tmp_path / "store"
    key = root / "projects" / "orphan-key"
    key.mkdir(parents=True)
    (key / "meta.json").write_text(json.dumps({"schemaVersion": 1, "sourcePath": str(tmp_path / "gone")}))
    (key / "registry.json").write_text("{}")
    (key / "doc-policy.json").write_text("{}")
    return root, key


def test_sweep_removes_nothing_in_a_cloud_session(tmp_path, monkeypatch):
    # axis: store_sweep.sweep refuses to remove an orphan store (calibration files) in a cloud
    # session — see bite-proof record c8a_wo2.md
    import store_sweep as ss
    root, key = _orphan_store(tmp_path)
    before = _snapshot(tmp_path)
    _cloud(monkeypatch)
    out = ss.sweep(root=str(root), include_unknown=True)
    assert _snapshot(tmp_path) == before
    assert out["deleted"] == [] and out["errors"] == []
    assert out["refused"] == "calibration-write-in-cloud-session"
    assert set(out) >= {"projectsRoot", "deleted", "kept", "includeUnknown", "errors"}


def test_sweep_still_removes_an_orphan_store_outside_a_cloud_session(tmp_path, monkeypatch):
    import store_sweep as ss
    root, key = _orphan_store(tmp_path)
    _cloud(monkeypatch, None)
    out = ss.sweep(root=str(root))
    assert out["deleted"] == [str(key)]
    assert "refused" not in out
    assert not key.exists()
