import json
import os
import subprocess

import pytest

import core_md as cm
import guardian_store as gs
import mode_registry as mr
import store_core as sc
from guardian_fixtures import init_calibrated_repo


def _store_root(tmp_path):
    return str(tmp_path / "store")


def test_guardian_paths_in_repo(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gdir = gs.guardian_dir(repo)
    assert gdir == os.path.join(repo, ".claude", "superheroes", "guardian")
    assert gs.report_path(repo).endswith(os.path.join("guardian", "report.md"))
    assert gs.snapshot_path(repo).endswith(os.path.join("guardian", "latest.json"))
    assert gs.ledger_path(repo).endswith(os.path.join("guardian", "ledger.md"))
    assert gs.guardian_layer_path(repo).endswith(
        os.path.join(".claude", "superheroes", "guardian.md"))


def test_guardian_paths_global_mode(tmp_path):
    repo = init_calibrated_repo(tmp_path, remote="git@github.com:o/r.git")
    root = _store_root(tmp_path)
    store = mr.ensure_project_store(repo, root=root)
    cfg = os.path.join(store, "config")
    os.makedirs(cfg, exist_ok=True)
    core = os.path.join(cfg, "core.md")
    sc.atomic_write(core, cm.render_core(
        {"verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": ""},
        "confirmed", "2026-01-01", "2026-01-01"))
    mr.write_registry(repo, mr.GLOBAL, "rk", root=root, now="2026-06-21T00:00:00Z")
    gdir = gs.guardian_dir(repo, root=root)
    assert gdir == os.path.join(cfg, "guardian")


def test_snapshot_round_trip(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc123",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "1", "digest": {"v": 1}}},
    }
    sc.atomic_write(gs.snapshot_path(repo), json.dumps(snap, indent=2))
    assert gs.read_snapshot(repo) == snap
    assert gs.snapshot_identity(snap) == "abc123"


def test_snapshot_identity_hash_when_no_sha(tmp_path):
    snap = {"schemaVersion": 1, "vitals": {}, "lenses": {}}
    ident = gs.snapshot_identity(snap)
    assert ident == sc.short_hash(json.dumps(snap, sort_keys=True))


def test_read_snapshot_malformed_returns_none(tmp_path, capsys):
    repo = init_calibrated_repo(tmp_path)
    sc.atomic_write(gs.snapshot_path(repo), "{ not json")
    assert gs.read_snapshot(repo) is None
    assert "malformed" in capsys.readouterr().err


def test_read_snapshot_newer_raises(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    sc.atomic_write(gs.snapshot_path(repo), json.dumps({"schemaVersion": 999}))
    with pytest.raises(gs.UnknownSnapshotVersion):
        gs.read_snapshot(repo)


def test_write_snapshot_cas_success(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    snap = {"schemaVersion": 1, "sweptSha": "a", "vitals": {}, "lenses": {}}
    result = gs.write_snapshot_cas(repo, snap, None)
    assert result["ok"] is True
    assert gs.read_snapshot(repo)["sweptSha"] == "a"


def test_write_snapshot_cas_raced_aborts(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    first = {"schemaVersion": 1, "sweptSha": "first", "vitals": {}, "lenses": {}}
    gs.write_snapshot_cas(repo, first, None)
    second = {"schemaVersion": 1, "sweptSha": "second", "vitals": {}, "lenses": {}}
    result = gs.write_snapshot_cas(repo, second, None)
    assert result["ok"] is False
    assert result["reason"] == "raced"
    assert gs.read_snapshot(repo)["sweptSha"] == "first"


def test_read_ledger_absent(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    out = gs.read_ledger(repo)
    assert out["status"] == "absent"
    assert out["records"] == []
    assert out["byId"] == {}


def test_read_ledger_valid(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [{"id": "x", "disposition": "filed", "issue": "#1"}]
    text = (
        "# ledger\n\n```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": 1, "records": records}))
    )
    sc.atomic_write(gs.ledger_path(repo), text)
    out = gs.read_ledger(repo)
    assert out["status"] == "ok"
    assert out["byId"]["x"]["issue"] == "#1"


def test_read_ledger_malformed_never_suppresses(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    sc.atomic_write(gs.ledger_path(repo), "# bad\n```json %s\n{ broken\n```\n" % gs.LEDGER_FENCE)
    out = gs.read_ledger(repo)
    assert out["status"] == "malformed"
    assert out["records"] == []
    assert out["byId"] == {}


def test_read_ledger_newer_is_opaque(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    text = (
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": 99, "records": []}))
    )
    sc.atomic_write(gs.ledger_path(repo), text)
    out = gs.read_ledger(repo)
    assert out["status"] == "newer"
    assert out["records"] == []


def test_read_ledger_drops_incomplete_records(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [
        {"id": "good", "disposition": "accepted", "issue": "n/a"},
        {"id": "bad", "disposition": "accepted"},
    ]
    text = (
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": 1, "records": records}))
    )
    sc.atomic_write(gs.ledger_path(repo), text)
    out = gs.read_ledger(repo)
    assert "good" in out["byId"]
    assert "bad" not in out["byId"]
