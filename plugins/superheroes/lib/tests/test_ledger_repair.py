"""Repairing a never-started lane under the ledger lock, and reading the ledger before naming a remedy.

A never-started lane is a `reserved` record with no `started` and no terminal event. One locked
operation, `repair_never_started`, brings it to a readable state (restores its `started` from a
pending record, or records its terminal event) and refuses every lane that is not never-started.
When a cloud launch's `started` append reports failure, the launcher re-reads the ledger before it
names a remedy: a lane whose record actually landed is a normal success.
"""
import json
import os
import time

import pytest

import launch_ledger as ll

from test_launch_ledger import _declare, _init_repo, _ledger_env, _reserved, _started  # noqa: E402
from test_launch_ledger_cloud import (  # noqa: E402
    _cloud_reserved,
    _cloud_started,
    _setup_cloud_lane,
)
from test_launcher import L  # noqa: E402
from test_launcher_cloud import (  # noqa: E402,F401
    SESSION_ID,
    _cloud_repo,
    _fake_spawn,
    _isolated,
    _launch,
    _lanes,
    _records,
    _spawned,
)


@pytest.fixture(autouse=True)
def _git_ignores_the_machine_config(tmp_path, monkeypatch):
    # The repos these tests commit into must not pick up the machine's signing or hook settings.
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _local_lane(tmp_path, monkeypatch, launch_id="l1", batch="b-local"):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(repo, batch, 1)["ok"]
    assert ll.append(repo, _reserved(launch_id, batch, ["x"], repo))
    return repo


def _cloud_lane(tmp_path, monkeypatch, launch_id="c1"):
    return _setup_cloud_lane(tmp_path, monkeypatch, launch_id, started=False)


def _aged(place):
    """A clock reading past the launch window of a lane of this place, reserved just now."""
    return time.time() + ll.launch_window_seconds(place) + 1


def _age_the_clock(monkeypatch, place):
    """Move the ledger's clock past the launch window, for the CLI verb that takes no clock."""
    aged_by = ll.launch_window_seconds(place) + 1
    real_time = time.time
    monkeypatch.setattr(ll.time, "time", lambda: real_time() + aged_by)


def _lane(repo, launch_id):
    folded = ll.fold(ll.read(repo)["records"])
    assert folded["ok"], folded["reason"]
    return folded["launches"][launch_id]


def _events(repo, launch_id):
    return [r["event"] for r in ll.read(repo)["records"] if r.get("launchId") == launch_id]


# --- the repair restores `started` -------------------------------------------------------------


def test_repair_restores_started_for_a_cloud_lane_then_record_outcome_succeeds(
    tmp_path, monkeypatch,
):
    repo = _cloud_lane(tmp_path, monkeypatch)
    assert _lane(repo, "c1")["started"] is False
    pending = _cloud_started("c1")
    result = ll.repair_never_started(repo, "c1", pending_started=pending)
    assert result == {"ok": True, "repaired": "started", "launchId": "c1"}
    lane = _lane(repo, "c1")
    assert lane["started"] is True and lane["terminal"] is False
    assert lane["cloudSessionId"] == pending["cloudSessionId"]
    assert _events(repo, "c1").count("started") == 1
    ended = ll.record_outcome(repo, "c1", "died", "no such session in the listing")
    assert ended["ok"] is True, ended
    assert _lane(repo, "c1")["terminal"] is True


def test_repair_restores_the_pending_started_a_failed_cloud_launch_returned(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    real_append = ll.append
    with monkeypatch.context() as patched:
        patched.setattr(
            ll, "append",
            lambda r, rec, env=None: False if rec.get("event") == "started"
            else real_append(r, rec, env=env),
        )
        failed = _launch(repo, tmp_path, _fake_spawn())
    assert failed["reason"] == "cloud-started-append-failed"
    launch_id = failed["launchId"]
    assert _lane(repo, launch_id)["started"] is False
    result = ll.repair_never_started(repo, launch_id, pending_started=failed["pendingStarted"])
    assert result == {"ok": True, "repaired": "started", "launchId": launch_id}
    assert _lane(repo, launch_id)["cloudSessionId"] == SESSION_ID
    assert L.record_outcome(repo, launch_id, "died", "no such session in the listing")["ok"]


def test_repair_restores_started_for_a_local_lane(tmp_path, monkeypatch):
    repo = _local_lane(tmp_path, monkeypatch)
    pending = _started("l1", attempt=1, pid=999999)
    result = ll.repair_never_started(repo, "l1", pending_started=pending)
    assert result == {"ok": True, "repaired": "started", "launchId": "l1"}
    lane = _lane(repo, "l1")
    assert lane["started"] is True and lane["terminal"] is False
    assert _events(repo, "l1") == ["reserved", "started"]


# --- the repair without a pending record records the terminal event ----------------------------


@pytest.mark.parametrize("place", ["cloud", "local"])
def test_repair_without_pending_records_the_terminal_event(tmp_path, monkeypatch, place):
    repo = (
        _cloud_lane(tmp_path, monkeypatch) if place == "cloud"
        else _local_lane(tmp_path, monkeypatch)
    )
    launch_id = "c1" if place == "cloud" else "l1"
    result = ll.repair_never_started(
        repo, launch_id, evidence="the launch command never ran", now=_aged(place),
    )
    assert result == {
        "ok": True, "repaired": "terminal", "launchId": launch_id, "kind": "refused",
    }
    lane = _lane(repo, launch_id)
    assert lane["terminal"] is True and lane["started"] is False
    assert _events(repo, launch_id) == ["reserved", "refused"]
    refused = [r for r in ll.read(repo)["records"] if r["event"] == "refused"][0]
    assert refused["stage"] == "never-started" and refused["reason"] == "never-started"
    assert refused["evidence"] == "the launch command never ran"


# --- the launch window: a fresh reservation is never terminalized ------------------------------


@pytest.mark.parametrize("place", ["cloud", "local"])
def test_repair_without_pending_refuses_a_lane_still_inside_its_launch_window(
    tmp_path, monkeypatch, place,
):
    # axis: lane-may-be-launching — the launcher may still spawn and append `started`.
    repo = (
        _cloud_lane(tmp_path, monkeypatch) if place == "cloud"
        else _local_lane(tmp_path, monkeypatch)
    )
    launch_id = "c1" if place == "cloud" else "l1"
    before = ll.read(repo)["records"]
    reserved_ts = _lane(repo, launch_id)["reservedTs"]
    window = ll.launch_window_seconds(place)
    just_inside = reserved_ts + window - 1
    result = ll.repair_never_started(repo, launch_id, evidence="never ran", now=just_inside)
    assert result == {"ok": False, "reason": ll.REPAIR_LANE_MAY_BE_LAUNCHING}
    assert result["reason"] == "lane-may-be-launching"
    assert ll.read(repo)["records"] == before
    # The aged side of the same lane repairs.
    aged = ll.repair_never_started(
        repo, launch_id, evidence="never ran", now=reserved_ts + window + 1,
    )
    assert aged["ok"] is True and aged["repaired"] == "terminal"


@pytest.mark.parametrize("place", ["cloud", "local"])
def test_repair_restores_a_pending_started_inside_the_launch_window(tmp_path, monkeypatch, place):
    repo = (
        _cloud_lane(tmp_path, monkeypatch) if place == "cloud"
        else _local_lane(tmp_path, monkeypatch)
    )
    launch_id = "c1" if place == "cloud" else "l1"
    pending = _cloud_started(launch_id) if place == "cloud" else _started(launch_id)
    result = ll.repair_never_started(repo, launch_id, pending_started=pending)
    assert result == {"ok": True, "repaired": "started", "launchId": launch_id}


def test_the_launch_window_reads_the_launchers_own_timeouts():
    import launcher
    assert ll.launch_window_seconds("cloud") == launcher._CLOUD_SPAWN_TIMEOUT_SECONDS
    assert ll.launch_window_seconds("local") == (
        launcher._TOTAL_DEADLINE_SECONDS + launcher._IPHONE_CEILING_SECONDS
    )


# --- refusals ----------------------------------------------------------------------------------


def test_repair_refuses_a_lane_that_already_has_started(tmp_path, monkeypatch):
    # axis: lane-already-started — a started lane is ended with `record-outcome`, never repaired.
    repo = _setup_cloud_lane(tmp_path, monkeypatch, "c1", started=True)
    before = ll.read(repo)["records"]
    for kwargs in (
        {"pending_started": _cloud_started("c1")},
        {"evidence": "ending it by repair"},
    ):
        result = ll.repair_never_started(repo, "c1", **kwargs)
        assert result == {"ok": False, "reason": "lane-already-started"}
    assert ll.read(repo)["records"] == before


def test_repair_refuses_a_terminal_lane(tmp_path, monkeypatch):
    repo = _cloud_lane(tmp_path, monkeypatch)
    assert ll.repair_never_started(repo, "c1", evidence="never ran", now=_aged("cloud"))["ok"]
    before = ll.read(repo)["records"]
    for kwargs in ({"pending_started": _cloud_started("c1")}, {"evidence": "again"}):
        result = ll.repair_never_started(repo, "c1", **kwargs)
        assert result == {"ok": False, "reason": "outcome-already-terminal"}
    assert ll.read(repo)["records"] == before


def test_repair_refuses_an_unknown_launch(tmp_path, monkeypatch):
    repo = _cloud_lane(tmp_path, monkeypatch)
    result = ll.repair_never_started(repo, "nope", evidence="never ran")
    assert result == {"ok": False, "reason": "terminal-unknown-launch"}


def test_repair_refuses_a_pending_record_for_another_launch(tmp_path, monkeypatch):
    # axis: the pending record's launchId must be the lane's — `c2` is a real never-started lane,
    # so a record for it would fold and be written if the match were skipped.
    repo = _cloud_lane(tmp_path, monkeypatch, "c1")
    assert _declare(repo, "b-two", 1)["ok"]
    assert ll.append(repo, _cloud_reserved("c2", "b-two", repo))
    before = ll.read(repo)["records"]
    result = ll.repair_never_started(repo, "c1", pending_started=_cloud_started("c2"))
    assert result == {"ok": False, "reason": ll.REPAIR_PENDING_STARTED_INVALID}
    assert ll.read(repo)["records"] == before


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rec: rec.update(event="outcome"),
        lambda rec: rec.pop("pid"),
        lambda rec: rec.pop("logPath"),
        lambda rec: rec.update(cloudSessionId="not a session id"),
        lambda rec: rec.update(cloudSessionUnconfirmed=False),
        lambda rec: rec.update(cloudSessionName=""),
    ],
    ids=["wrong-event", "no-pid", "no-log-path", "bad-session-id", "bad-unconfirmed", "bad-name"],
)
def test_repair_refuses_a_malformed_pending_record(tmp_path, monkeypatch, mutate):
    repo = _cloud_lane(tmp_path, monkeypatch)
    pending = _cloud_started("c1")
    mutate(pending)
    before = ll.read(repo)["records"]
    result = ll.repair_never_started(repo, "c1", pending_started=pending)
    assert result == {"ok": False, "reason": ll.REPAIR_PENDING_STARTED_INVALID}
    assert ll.read(repo)["records"] == before


@pytest.mark.parametrize("pending", ["a string", ["x"], 7])
def test_repair_refuses_a_pending_record_that_is_not_an_object(tmp_path, monkeypatch, pending):
    repo = _cloud_lane(tmp_path, monkeypatch)
    result = ll.repair_never_started(repo, "c1", pending_started=pending)
    assert result == {"ok": False, "reason": ll.REPAIR_PENDING_STARTED_INVALID}


def test_repair_refuses_a_pending_record_that_fails_the_fold_and_writes_nothing(
    tmp_path, monkeypatch,
):
    # A cloud lane's `started` must carry the cloud identity; the local-shaped record lacks it.
    repo = _cloud_lane(tmp_path, monkeypatch)
    before = ll.read(repo)["records"]
    result = ll.repair_never_started(repo, "c1", pending_started=_started("c1"))
    assert result["ok"] is False
    assert result["reason"].startswith("fold-")
    assert ll.read(repo)["records"] == before


def test_repair_reports_a_failed_append(tmp_path, monkeypatch):
    repo = _cloud_lane(tmp_path, monkeypatch)
    monkeypatch.setattr(ll, "append", lambda *a, **k: False)
    result = ll.repair_never_started(repo, "c1", pending_started=_cloud_started("c1"))
    assert result == {"ok": False, "reason": "ledger-append-failed"}


@pytest.mark.parametrize("evidence", [None, "", "   ", 5])
def test_repair_without_pending_refuses_empty_evidence(tmp_path, monkeypatch, evidence):
    repo = _cloud_lane(tmp_path, monkeypatch)
    before = ll.read(repo)["records"]
    result = ll.repair_never_started(repo, "c1", evidence=evidence)
    assert result == {"ok": False, "reason": "outcome-evidence-empty"}
    assert ll.read(repo)["records"] == before


def test_repair_refuses_an_unreadable_ledger_and_writes_nothing(tmp_path, monkeypatch):
    repo = _cloud_lane(tmp_path, monkeypatch)
    path = ll.ledger_path(repo)["path"]
    with open(path, "ab") as fh:
        fh.write(b"not json\n")
    with open(path, "rb") as fh:
        before = fh.read()
    result = ll.repair_never_started(repo, "c1", evidence="never ran")
    assert result == {"ok": False, "reason": "ledger-unreadable:interiorCorrupt"}
    with open(path, "rb") as fh:
        assert fh.read() == before


def test_repair_refuses_when_the_lock_is_held_by_another_holder(tmp_path, monkeypatch):
    repo = _cloud_lane(tmp_path, monkeypatch)
    before = ll.read(repo)["records"]
    lock = ll._ensure_lock_file(repo)
    assert lock["ok"]
    assert ll._acquire_lock(lock["path"], 1)
    try:
        result = ll.repair_never_started(repo, "c1", evidence="never ran", lock_timeout=0.2)
    finally:
        ll._release_lock(lock["path"])
    assert result == {"ok": False, "reason": "lock-unavailable"}
    assert ll.read(repo)["records"] == before
    assert ll.repair_never_started(
        repo, "c1", evidence="never ran", now=_aged("cloud"),
    )["ok"] is True


# --- the launcher reads the ledger before it names a remedy ------------------------------------


def _fsync_fails_during_started_appends(monkeypatch, repo):
    """`os.fsync` as `launch_ledger` sees it raises for the ledger file, but only inside a `started` append.

    The line is written and flushed before the sync, so the record lands and the append reports
    failure. Every other sync (the lock file's) is the real one. Returns the list the failing calls
    are counted in.
    """
    syncs = []
    real_fsync = ll.os.fsync
    real_append_under_lock = L._append_under_lock
    ledger = ll.ledger_path(repo)["path"]

    def failing_fsync(fd):
        if os.fstat(fd).st_ino != os.stat(ledger).st_ino:
            return real_fsync(fd)
        syncs.append(fd)
        raise OSError(5, "sync failed")

    def scoped(repo_root, record, env=None):
        if record.get("event") != "started":
            return real_append_under_lock(repo_root, record, env=env)
        with monkeypatch.context() as patched:
            patched.setattr(ll.os, "fsync", failing_fsync)
            return real_append_under_lock(repo_root, record, env=env)

    monkeypatch.setattr(L, "_append_under_lock", scoped)
    return syncs


def test_a_started_that_landed_before_its_sync_failed_stays_a_failure(tmp_path, monkeypatch):
    # axis: a reported storage error stands — the record is visible, but a clean cached page after a failed writeback proves nothing.
    repo = _cloud_repo(tmp_path)
    syncs = _fsync_fails_during_started_appends(monkeypatch, repo)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert syncs, "the failing sync was never reached"
    assert result["ok"] is False, result
    assert result["reason"] == "cloud-started-append-failed"
    assert "pendingStarted" in result and "startedAppend" in result
    launch_id = result["launchId"]
    assert len(_records(repo, launch_id, "started")) == 1


def test_a_started_whose_sync_stays_failed_is_not_reported_as_a_success(tmp_path, monkeypatch):
    # axis: visible is not durable — a re-read that finds the record is no proof it reached storage.
    repo = _cloud_repo(tmp_path)
    real_fsync = ll.os.fsync
    ledger = ll.ledger_path(repo)["path"]
    real_append_under_lock = L._append_under_lock
    state = {"broken": False}

    def failing_fsync(fd):
        if state["broken"] and os.fstat(fd).st_ino == os.stat(ledger).st_ino:
            raise OSError(5, "sync failed")
        return real_fsync(fd)

    def scoped(repo_root, record, env=None):
        if record.get("event") == "started":
            state["broken"] = True
        return real_append_under_lock(repo_root, record, env=env)

    monkeypatch.setattr(ll.os, "fsync", failing_fsync)
    monkeypatch.setattr(L.os, "fsync", failing_fsync)
    monkeypatch.setattr(L, "_append_under_lock", scoped)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is False, result
    assert "pendingStarted" in result and "startedAppend" in result
    assert len(_records(repo, result["launchId"], "started")) == 1


def test_a_started_that_landed_keeps_its_failure_and_is_not_appended_again(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, "c1", started=True)
    calls = []

    def failing(repo_root, record, env=None):
        calls.append(record)
        return {"ok": False, "reason": "ledger-append-failed", "path": None}

    monkeypatch.setattr(L, "_append_under_lock", failing)
    monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
    result = L._append_started(repo, _cloud_started("c1"), None)
    assert result == {"ok": False, "reason": "ledger-append-failed", "path": None}
    assert len(calls) == 1


def test_a_failed_append_with_nothing_landed_keeps_the_failure_and_names_the_repair(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    monkeypatch.setattr(
        ll, "append_under_lock",
        lambda *a, **k: {"ok": False, "reason": "lock-unavailable", "path": None},
    )
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is False
    assert result["reason"] == "cloud-started-append-failed"
    assert result["startedAppend"] == "lock-unavailable"
    assert "A reported write failure does not prove the record is absent." in result["remedy"]
    assert "launcher.py repair-lane --pending-file" in result["remedy"]
    assert "refuses a lane" not in result["remedy"]
    assert result["pendingStarted"]["cloudSessionId"] == SESSION_ID
    assert _records(repo, result["launchId"], "started") == []


def test_an_unconfirmed_launch_whose_append_failed_names_the_repair_too(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    monkeypatch.setattr(
        ll, "append_under_lock",
        lambda *a, **k: {"ok": False, "reason": "lock-unavailable", "path": None},
    )
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("", rc=None, timed_out=True)))
    assert result["reason"] == "cloud-session-unconfirmed"
    assert result["remedy"] == L._CLOUD_UNCONFIRMED_APPEND_REMEDY
    assert "launcher.py repair-lane --pending-file" in result["remedy"]
    assert result["pendingStarted"]["cloudSessionUnconfirmed"] is True


def test_a_re_read_that_fails_leaves_the_failure_standing(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, "c1", started=True)
    calls = []

    def failing(repo_root, record, env=None):
        calls.append(record)
        return {"ok": False, "reason": "lock-unavailable", "path": None}

    monkeypatch.setattr(L, "_append_under_lock", failing)
    monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
    monkeypatch.setattr(ll, "read", lambda *a, **k: {"state": "unreadable", "records": []})
    result = L._append_started(repo, _cloud_started("c1"), None)
    assert result == {"ok": False, "reason": "lock-unavailable", "path": None}
    assert len(calls) == L._CLOUD_APPEND_TRIES


# --- the `repair-lane` verb --------------------------------------------------------------------


def test_cli_repair_lane_restores_started_from_a_pending_file(tmp_path, monkeypatch, capsys):
    repo = _cloud_lane(tmp_path, monkeypatch)
    pending_file = tmp_path / "pending.json"
    pending_file.write_text(json.dumps(_cloud_started("c1")), encoding="utf-8")
    code = L.main([
        "repair-lane", "--repo-root", repo, "--launch-id", "c1",
        "--pending-file", str(pending_file),
    ])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out == {"ok": True, "repaired": "started", "launchId": "c1"}
    assert _lane(repo, "c1")["started"] is True


def test_cli_repair_lane_records_the_terminal_event_from_evidence(tmp_path, monkeypatch, capsys):
    repo = _cloud_lane(tmp_path, monkeypatch)
    _age_the_clock(monkeypatch, "cloud")
    code = L.main([
        "repair-lane", "--repo-root", repo, "--launch-id", "c1", "--evidence", "never ran",
    ])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["ok"] is True and out["repaired"] == "terminal"
    assert _lane(repo, "c1")["terminal"] is True


def test_cli_repair_lane_refuses_a_started_lane_with_exit_1(tmp_path, monkeypatch, capsys):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, "c1", started=True)
    code = L.main([
        "repair-lane", "--repo-root", repo, "--launch-id", "c1", "--evidence", "never ran",
    ])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out == {"ok": False, "reason": "lane-already-started"}


@pytest.mark.parametrize("body", [None, "not json"])
def test_cli_repair_lane_refuses_an_unreadable_pending_file(tmp_path, monkeypatch, capsys, body):
    repo = _cloud_lane(tmp_path, monkeypatch)
    pending_file = tmp_path / "pending.json"
    if body is not None:
        pending_file.write_text(body, encoding="utf-8")
    code = L.main([
        "repair-lane", "--repo-root", repo, "--launch-id", "c1",
        "--pending-file", str(pending_file),
    ])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out == {"ok": False, "reason": "pending-file-unreadable"}
    assert _lane(repo, "c1")["started"] is False


def test_cli_repair_lane_refuses_a_null_pending_file_without_closing_the_lane(
    tmp_path, monkeypatch, capsys,
):
    repo = _cloud_lane(tmp_path, monkeypatch)
    pending_file = tmp_path / "pending.json"
    pending_file.write_text("null", encoding="utf-8")
    before = ll.read(repo)["records"]
    code = L.main([
        "repair-lane", "--repo-root", repo, "--launch-id", "c1",
        "--pending-file", str(pending_file), "--evidence", "never ran",
    ])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out == {"ok": False, "reason": ll.REPAIR_PENDING_STARTED_INVALID}
    assert ll.read(repo)["records"] == before
    assert _lane(repo, "c1")["terminal"] is False


# --- the slot remedy ---------------------------------------------------------------------------


def test_the_slot_remedy_names_the_repair_verb():
    assert "no CLI transition today" not in L._SLOT_REMEDY
    assert "a reserved-but-never-started lane reaches one with `launcher.py repair-lane`" in (
        L._SLOT_REMEDY
    )
