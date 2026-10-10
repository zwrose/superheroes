"""The heartbeat sweep and the cloud lane: a cloud lane has no heartbeat file, so the sweep decides
it by its folded `place` and never reads a file under its launch id."""
import launch_ledger as ll
import heartbeat as hb

from test_heartbeat import (  # noqa: E402
    _base_record,
    _init_repo,
    _ledger_env,
    _reserved,
    _started,
    _write_heartbeat_file,
)

NOW = 1_000_000.0
SESSION_ID = "session_01AbCdEf123"


def _cloud_lane(repo, launch_id, batch, issue):
    reserved = _reserved(
        launch_id, batch, ["plugins/superheroes/lib"], repo,
        place="cloud", cloudEnvironment="env_abc", pluginVersion="1.2.3", issue=issue,
    )
    assert ll.append(repo, reserved)
    started = _started(launch_id)
    started["cloudSessionName"] = "lane-%s" % launch_id
    started["cloudSessionId"] = SESSION_ID
    assert ll.append(repo, started)


def _local_lane(repo, launch_id, batch, issue):
    reserved = _reserved(launch_id, batch, ["plugins/superheroes/lib"], repo, issue=issue)
    assert ll.append(repo, reserved)
    assert ll.append(repo, _started(launch_id))


def _setup(tmp_path, monkeypatch, expected):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert ll.declare_batch(repo, "batch-cloud", expected)["ok"]
    return repo


def _entry(result, launch_id):
    assert result["ok"] is True
    return next(e for e in result["launches"] if e["launchId"] == launch_id)


CLOUD_ENTRY = {
    "class": "nonterminal",
    "place": "cloud",
    "state": None,
    "phase": None,
    "lastDispatch": None,
    "ageSeconds": None,
    "note": None,
    "reason": hb.REASON_CLOUD_LANE,
}


def test_reason_constant_literal():
    assert hb.REASON_CLOUD_LANE == "cloud-lane-no-heartbeat"


def test_edge10_live_cloud_lane_without_heartbeat_file_is_nonterminal(tmp_path, monkeypatch):
    # axis: a cloud lane never reads unknown for lacking a heartbeat.
    repo = _setup(tmp_path, monkeypatch, 1)
    _cloud_lane(repo, "cloud-a", "batch-cloud", 901)
    entry = _entry(hb.sweep(repo, now=NOW), "cloud-a")
    assert entry == dict(CLOUD_ENTRY, launchId="cloud-a")
    assert "actionable" not in entry
    assert "pendingAction" not in entry


def test_edge10_stray_handback_file_under_a_cloud_lane_is_not_read(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch, 1)
    _cloud_lane(repo, "cloud-a", "batch-cloud", 901)
    _write_heartbeat_file(repo, "cloud-a", _base_record("cloud-a", state="handback"))
    entry = _entry(hb.sweep(repo, now=NOW + 5), "cloud-a")
    assert entry == dict(CLOUD_ENTRY, launchId="cloud-a")
    assert "actionable" not in entry
    assert "pendingAction" not in entry


def test_local_lane_entry_gains_only_place(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch, 2)
    _cloud_lane(repo, "cloud-a", "batch-cloud", 901)
    _local_lane(repo, "local-a", "batch-cloud", 902)
    _write_heartbeat_file(repo, "local-a", _base_record("local-a", state="handback"))
    result = hb.sweep(repo, now=NOW + 5)
    local = _entry(result, "local-a")
    assert local["place"] == "local"
    assert local["class"] == "terminal"
    assert local["actionable"] is True
    assert local["pendingAction"] == "record-outcome"
    assert local["state"] == "handback"
    assert _entry(result, "cloud-a") == dict(CLOUD_ENTRY, launchId="cloud-a")


def test_local_lane_without_file_still_reads_unknown(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch, 1)
    _local_lane(repo, "local-a", "batch-cloud", 902)
    entry = _entry(hb.sweep(repo, now=NOW), "local-a")
    assert entry["place"] == "local"
    assert entry["class"] == "unknown"
    assert entry["reason"] == "heartbeat-missing"


def test_ledger_live_launches_reports_places(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch, 2)
    _cloud_lane(repo, "cloud-a", "batch-cloud", 901)
    _local_lane(repo, "local-a", "batch-cloud", 902)
    live = hb._ledger_live_launches(repo)
    assert live["ok"] is True
    assert sorted(live["live"]) == ["cloud-a", "local-a"]
    assert live["places"] == {"cloud-a": "cloud", "local-a": "local"}
    assert sorted(ll.live_launches(ll.read(repo)["records"])) == ["cloud-a", "local-a"]


def test_terminal_cloud_lane_is_not_swept(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch, 1)
    _cloud_lane(repo, "cloud-a", "batch-cloud", 901)
    assert ll.record_outcome(repo, "cloud-a", "handback", "done")["ok"]
    result = hb.sweep(repo, now=NOW)
    assert result["ok"] is True
    assert result["launches"] == []
