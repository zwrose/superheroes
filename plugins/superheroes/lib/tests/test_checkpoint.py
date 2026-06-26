# plugins/superheroes/lib/tests/test_checkpoint.py
import json
import os
import subprocess
import sys
import pytest
import checkpoint as ck
import control_plane


def test_new_has_locked_43_fields():
    c = ck.new("wi", "superheroes/wi-abc123", issue=42, size="medium")
    for k in ("schemaVersion", "workItem", "issue", "size", "phase", "gates",
              "patternsPin", "branch", "lockGeneration", "pr", "lastGoodStep",
              "lastGoodPhase"):
        assert k in c
    assert c["workItem"] == "wi" and c["branch"] == "superheroes/wi-abc123"
    assert c["phase"] == "build" and c["lastGoodStep"] is None and c["lastGoodPhase"] is None


def test_write_read_roundtrip_stamps_updatedat(tmp_path):
    p = str(tmp_path / "checkpoint.json")
    c = ck.new("wi", "b", last_good_step=2, last_good_phase="tasks")
    ck.write(p, c)
    got = ck.read(p)
    assert got["workItem"] == "wi" and got["updatedAt"]
    assert got["schemaVersion"] == ck.SCHEMA_VERSION
    assert got["lastGoodStep"] == 2 and got["lastGoodPhase"] == "tasks"


def test_read_missing_is_none(tmp_path):
    assert ck.read(str(tmp_path / "nope.json")) is None


def test_read_unparseable_is_none(tmp_path):
    p = tmp_path / "checkpoint.json"; p.write_text("{not json")
    assert ck.read(str(p)) is None


def test_read_unknown_schema_fails_closed(tmp_path):
    p = tmp_path / "checkpoint.json"
    p.write_text(json.dumps({"schemaVersion": 999, "workItem": "wi"}))
    got = ck.read(str(p))
    assert got["_incompatible"] is True
    assert "schema" in got["reason"]


def test_read_legacy_numeric_cursor_without_phase_infers_previous_phase(tmp_path):
    p = tmp_path / "checkpoint.json"
    c = ck.new("wi", "b", last_good_step=2)
    c.pop("lastGoodPhase")
    p.write_text(json.dumps(c))
    got = ck.read(str(p))
    assert got["lastGoodStep"] == 2
    assert got["lastGoodPhase"] == "tasks"


def test_read_legacy_cursor_shifted_by_test_pilot_insert_moves_to_current_phase_index(tmp_path):
    p = tmp_path / "checkpoint.json"
    c = ck.new("wi", "b")
    c["lastGoodStep"] = 7
    c.pop("lastGoodPhase")
    p.write_text(json.dumps(c))
    got = ck.read(str(p))
    assert got["lastGoodStep"] == 8
    assert got["lastGoodPhase"] == "mark-ready"


def test_read_allows_missing_phase_when_no_cursor(tmp_path):
    p = tmp_path / "checkpoint.json"
    c = ck.new("wi", "b")
    c.pop("lastGoodPhase")
    p.write_text(json.dumps(c))
    got = ck.read(str(p))
    assert got["lastGoodStep"] is None
    assert got["lastGoodPhase"] is None


def test_checkpoint_entry_writes_phase_with_step(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    entry = os.path.join(os.path.dirname(__file__), "..", "checkpoint_entry.py")
    out = subprocess.check_output(
        [sys.executable, entry, "--work-item", "wi", "--step", "4", "--phase", "workhorse"],
        cwd=os.getcwd(),
        text=True,
    )
    assert json.loads(out)["ok"] is True
    got = ck.read(control_plane.paths(os.getcwd(), "wi")["checkpoint"])
    assert got["lastGoodStep"] == 4
    assert got["lastGoodPhase"] == "workhorse"


@pytest.mark.parametrize("phase", ["plan", "tasks"])
def test_front_half_phase_roundtrips(tmp_path, phase):
    import checkpoint
    p = str(tmp_path / "checkpoint.json")
    ck2 = checkpoint.new("wi", "")          # checkpoint.new(work_item, branch) — branch is required
    ck2["phase"] = phase
    ck2["lastGoodStep"] = 1
    ck2["lastGoodPhase"] = phase
    checkpoint.write(p, ck2)
    assert checkpoint.read(p)["phase"] == phase
