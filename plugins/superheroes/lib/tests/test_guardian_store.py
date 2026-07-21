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
    assert gs.snapshot_identity(snap) == sc.short_hash(json.dumps(snap, sort_keys=True))


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
        {"id": "good", "disposition": "filed", "issue": "n/a"},
        {"id": "trade", "disposition": "accepted", "reason": "owner trade"},
        {"id": "bad"},
    ]
    text = (
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": 1, "records": records}))
    )
    sc.atomic_write(gs.ledger_path(repo), text)
    out = gs.read_ledger(repo)
    assert "good" in out["byId"]
    assert "trade" in out["byId"]
    assert "bad" not in out["byId"]
    assert out["status"] == "partial"
    assert "skipped" in (out["note"] or "")


def test_read_ledger_excludes_wont_fix_without_reason(tmp_path):
    """Shared validate_record: accepted/declined without reason must not enter byId."""
    repo = init_calibrated_repo(tmp_path)
    records = [
        {"id": "valid-filed", "disposition": "filed", "issue": "#1"},
        {"id": "mute-trade", "disposition": "accepted", "issue": None,
         "metricAtDisposition": {"metric": 5}},
    ]
    text = (
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": 1, "records": records}))
    )
    sc.atomic_write(gs.ledger_path(repo), text)
    out = gs.read_ledger(repo)
    assert out["status"] == "partial"
    assert "valid-filed" in out["byId"]
    assert "mute-trade" not in out["byId"]
    assert "mute-trade" not in [r.get("id") for r in out["records"]]


def test_read_ledger_unreadable_existing_file(tmp_path):
    """CRITICAL: existing-but-unreadable is unreadable, never absent."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    owner_text = (
        "# Owner prose\n\n```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({
            "schemaVersion": 1,
            "records": [{
                "id": "fixture:trade",
                "disposition": "accepted",
                "date": "2026-07-01",
                "issue": None,
                "metricAtDisposition": {"metric": 5},
                "reason": "owner accepted this trade",
                "reraiseWhen": None,
            }],
            "sweeps": [],
        }, indent=2))
    )
    sc.atomic_write(path, owner_text)
    os.chmod(path, 0)
    try:
        out = gs.read_ledger(repo)
        if out["status"] == "ok":
            pytest.skip("cannot make the ledger unreadable in this environment")
        assert out["status"] == "unreadable"
        assert out["records"] == []
        assert out["byId"] == {}
        assert out["note"]
    finally:
        os.chmod(path, 0o644)


def test_read_ledger_drops_unknown_disposition(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [
        {"id": "known", "disposition": "filed", "issue": "#1"},
        {"id": "unknown", "disposition": "not-a-state", "issue": "#2"},
    ]
    text = (
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({"schemaVersion": 1, "records": records}))
    )
    sc.atomic_write(gs.ledger_path(repo), text)
    out = gs.read_ledger(repo)
    assert out["status"] == "partial"
    assert "known" in out["byId"]
    assert "unknown" not in out["byId"]


def test_snapshot_keys_match_ssot(tmp_path):
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {},
    }
    assert set(snap) == set(gs.SNAPSHOT_KEYS)


def _write_ledger_block(repo, payload):
    text = (
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps(payload, indent=2))
    )
    sc.atomic_write(gs.ledger_path(repo), text)


def test_read_ledger_list_block_malformed_not_attribute_error(tmp_path):
    """Regression: list block used to raise AttributeError on block.get."""
    repo = init_calibrated_repo(tmp_path)
    _write_ledger_block(repo, [{"id": "x", "disposition": "filed"}])
    out = gs.read_ledger(repo)
    assert out["status"] == "malformed"
    assert out["records"] == []
    assert out["byId"] == {}
    assert "not an object" in (out["note"] or "")


def test_read_ledger_string_block_malformed_not_attribute_error(tmp_path):
    """Regression: string block used to raise AttributeError on block.get."""
    repo = init_calibrated_repo(tmp_path)
    _write_ledger_block(repo, "not-an-object")
    out = gs.read_ledger(repo)
    assert out["status"] == "malformed"
    assert out["records"] == []
    assert out["byId"] == {}
    assert "not an object" in (out["note"] or "")


def test_read_ledger_unhashable_id_skipped_not_type_error(tmp_path):
    """Regression: list id used to raise TypeError: unhashable type: 'list'."""
    repo = init_calibrated_repo(tmp_path)
    records = [
        {"id": ["unhashable"], "disposition": "filed", "issue": "#1"},
        {"id": "good", "disposition": "filed", "issue": "#2"},
    ]
    _write_ledger_block(repo, {"schemaVersion": 1, "records": records})
    out = gs.read_ledger(repo)
    assert out["status"] == "partial"
    assert "good" in out["byId"]
    assert len(out["byId"]) == 1


def test_read_ledger_duplicate_ids_do_not_suppress(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [
        {"id": "dup", "disposition": "accepted", "issue": None, "reason": "a"},
        {"id": "dup", "disposition": "declined", "issue": None, "reason": "b"},
        {"id": "unique", "disposition": "filed", "issue": "#1"},
    ]
    _write_ledger_block(repo, {"schemaVersion": 1, "records": records})
    out = gs.read_ledger(repo)
    assert out["status"] == "partial"
    assert "dup" not in out["byId"]
    assert "unique" in out["byId"]
    assert out["note"] and "duplicate" in out["note"]
    assert "dup" in out["note"]
