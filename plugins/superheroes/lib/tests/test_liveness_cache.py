import json
import os

import pytest

import liveness_cache as lc
import mode_registry


def _good_liveness():
    return {
        "codex": {
            "live": True,
            "models": {
                "gpt-5.6-sol": {"ok": True, "detail": "READY"},
                "gpt-5.6-terra": {"ok": True, "detail": "READY"},
            },
        },
        "claude": {"live": True, "models": {}},
    }


def _good_needed():
    return {
        "codex": [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]],
        "claude": [],
    }


# --- ttl_seconds ---


def test_ttl_seconds_default(monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    assert lc.ttl_seconds() == 600


def test_ttl_seconds_env_positive_override(monkeypatch):
    monkeypatch.setenv(lc._ENV_TTL, "120")
    assert lc.ttl_seconds() == 120


@pytest.mark.parametrize("val", ["abc", "0", "-5", ""])
def test_ttl_seconds_env_invalid_falls_back(monkeypatch, val):
    if val == "":
        monkeypatch.delenv(lc._ENV_TTL, raising=False)
    else:
        monkeypatch.setenv(lc._ENV_TTL, val)
    assert lc.ttl_seconds() == 600


# --- receipt_path ---


def test_receipt_path_under_state(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "project_store_dir", lambda cwd, root=None: str(tmp_path))
    p = lc.receipt_path("/any/cwd")
    assert p == os.path.join(str(tmp_path), "state", "composition-liveness.json")
    assert p.endswith(os.path.join("state", "composition-liveness.json"))


# --- write / read round trip ---


def test_write_read_round_trip(tmp_path):
    path = str(tmp_path / "receipt.json")
    now = 1_000_000.0
    liveness = _good_liveness()
    needed = _good_needed()
    assert lc.write(liveness, needed, path=path, now=now) is True
    got = lc.read(path, now=now + 1)
    assert got is not None
    assert got["schemaVersion"] == lc.SCHEMA_VERSION
    assert got["probedAt"] == now
    assert got["liveness"] == liveness
    assert got["needed"]["codex"] == [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]]


def test_write_atomic_single_receipt_file(tmp_path):
    path = str(tmp_path / "state" / "composition-liveness.json")
    now = 500.0
    assert lc.write(_good_liveness(), _good_needed(), path=path, now=now) is True
    assert os.path.isfile(path)
    siblings = [f for f in os.listdir(os.path.dirname(path)) if not f.startswith(".")]
    assert siblings == ["composition-liveness.json"]
    data = json.load(open(path))
    assert data["schemaVersion"] == lc.SCHEMA_VERSION
    assert "liveness" in data


# --- read MISS cases ---


def test_read_miss_missing_file(tmp_path):
    assert lc.read(str(tmp_path / "nope.json"), now=100.0) is None


def test_read_miss_bad_json(tmp_path):
    path = str(tmp_path / "bad.json")
    open(path, "wb").write(b"{not json")
    assert lc.read(path, now=100.0) is None


def test_read_miss_schema_version(tmp_path):
    path = str(tmp_path / "r.json")
    json.dump({"schemaVersion": 999, "probedAt": 0, "liveness": {}, "needed": {}}, open(path, "w"))
    assert lc.read(path, now=1000.0) is None


def test_read_miss_probed_at_future(tmp_path):
    path = str(tmp_path / "r.json")
    now = 2000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 1000)
    assert lc.read(path, now=now) is None


def test_read_miss_stale(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 10_000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 601)
    assert lc.read(path, now=now) is None


def test_read_miss_model_ok_string(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = _good_liveness()
    liv["codex"]["models"]["gpt-5.6-sol"]["ok"] = "false"
    lc.write(liv, _good_needed(), path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_miss_model_ok_int(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = _good_liveness()
    liv["codex"]["models"]["gpt-5.6-sol"]["ok"] = 1
    lc.write(liv, _good_needed(), path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_miss_liveness_not_dict(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    payload = {
        "schemaVersion": lc.SCHEMA_VERSION,
        "probedAt": now - 10,
        "ttl": 600,
        "needed": {},
        "liveness": "nope",
    }
    json.dump(payload, open(path, "w"))
    assert lc.read(path, now=now) is None


def test_read_miss_model_entry_not_dict(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = {"codex": {"live": True, "models": {"m": "bad"}}}
    lc.write(liv, {"codex": [["m", None]]}, path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_hit_within_ttl(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 50_000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 599)
    got = lc.read(path, now=now)
    assert got is not None
    assert got["liveness"]["codex"]["models"]["gpt-5.6-sol"]["ok"] is True


# --- covers ---


def test_covers_exact():
    need = {"codex": [["gpt-5.6-sol", "high"]]}
    rec = {"codex": [["gpt-5.6-sol", None]]}
    assert lc.covers(rec, need) is True


def test_covers_broad_receipt_narrow_need():
    rec = {"codex": [["a", None], ["b", None], ["c", None]]}
    need = {"codex": [["b", "low"]]}
    assert lc.covers(rec, need) is True


def test_covers_missing_vendor():
    assert lc.covers({}, {"codex": [["m", None]]}) is False


def test_covers_missing_model():
    rec = {"codex": [["a", None]]}
    need = {"codex": [["b", None]]}
    assert lc.covers(rec, need) is False


def test_covers_empty_need():
    assert lc.covers({"codex": [["a", None]]}, {}) is True


def test_covers_malformed():
    assert lc.covers(None, {"codex": []}) is False
    assert lc.covers({"codex": "x"}, {"codex": []}) is False


# --- live_vendors_from ---


def test_live_vendors_claude_always_present():
    live, notes = lc.live_vendors_from({}, {})
    assert live == ["claude"]
    assert notes == []


def test_live_vendors_all_ok():
    liv = _good_liveness()
    need = {"codex": [["gpt-5.6-sol", None], ["gpt-5.6-terra", None]]}
    live, notes = lc.live_vendors_from(liv, need)
    assert live == ["claude", "codex"]
    assert notes == []


def test_live_vendors_one_model_not_ok():
    liv = _good_liveness()
    liv["codex"]["models"]["gpt-5.6-terra"]["ok"] = False
    need = {"codex": [["gpt-5.6-sol", None], ["gpt-5.6-terra", None]]}
    live, notes = lc.live_vendors_from(liv, need)
    assert live == ["claude"]
    assert len(notes) == 1
    assert notes[0]["constraint"] == "liveness-cache"
    assert "codex" in notes[0]["reason"]


def test_live_vendors_empty_model_list_not_live():
    live, notes = lc.live_vendors_from(_good_liveness(), {"codex": []})
    assert "codex" not in live
    assert any("codex" in n["reason"] for n in notes)


def test_live_vendors_missing_vendor_in_liveness():
    need = {"cursor": [["grok", None]]}
    live, notes = lc.live_vendors_from(_good_liveness(), need)
    assert "cursor" not in live
    assert any("cursor" in n["reason"] for n in notes)


def test_live_vendors_ok_string_not_live():
    liv = {"codex": {"live": True, "models": {"m": {"ok": "true", "detail": ""}}}}
    need = {"codex": [["m", None]]}
    live, notes = lc.live_vendors_from(liv, need)
    assert "codex" not in live
    assert notes


# --- write failure ---


def test_write_returns_false_when_dir_blocked(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    path = str(blocker / "state" / "composition-liveness.json")
    assert lc.write(_good_liveness(), _good_needed(), path=path, now=1.0) is False
