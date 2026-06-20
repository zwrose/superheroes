# plugins/superheroes/lib/tests/test_checkpoint.py
import json
import checkpoint as ck


def test_new_has_locked_43_fields():
    c = ck.new("wi", "superheroes/wi-abc123", issue=42, size="medium")
    for k in ("schemaVersion", "workItem", "issue", "size", "phase", "gates",
              "patternsPin", "branch", "lockGeneration", "pr", "lastGoodStep"):
        assert k in c
    assert c["workItem"] == "wi" and c["branch"] == "superheroes/wi-abc123"
    assert c["phase"] == "build" and c["lastGoodStep"] is None


def test_write_read_roundtrip_stamps_updatedat(tmp_path):
    p = str(tmp_path / "checkpoint.json")
    ck.write(p, ck.new("wi", "b"))
    got = ck.read(p)
    assert got["workItem"] == "wi" and got["updatedAt"]
    assert got["schemaVersion"] == ck.SCHEMA_VERSION


def test_read_missing_is_none(tmp_path):
    assert ck.read(str(tmp_path / "nope.json")) is None


def test_read_unparseable_is_none(tmp_path):
    p = tmp_path / "checkpoint.json"; p.write_text("{not json")
    assert ck.read(str(p)) is None


def test_read_unknown_schema_fails_closed(tmp_path):
    p = tmp_path / "checkpoint.json"
    p.write_text(json.dumps({"schemaVersion": 999, "workItem": "wi"}))
    assert ck.read(str(p)) is None   # newer schema -> ignore, world-derive
