"""The cloud lane on the launch ledger: a lane's place is decided once, by its `reserved` record.

A cloud lane has no local process the build depends on, no session transcript, no worktree and
no heartbeat file, so no ledger reader concludes anything about one from a pid.
"""
import os

import pytest

import launch_ledger as ll

from test_launch_ledger import (  # noqa: E402
    _declare,
    _init_repo,
    _ledger_env,
    _reserved,
    _started,
)

SESSION_ID = "session_01AbCdEf123"


def _cloud_reserved(launch_id, batch="b", repo="/tmp", **extra):
    fields = {"place": "cloud", "cloudEnvironment": "env_abc", "pluginVersion": "1.2.3"}
    fields.update(extra)
    return _reserved(launch_id, batch, ["x"], repo, **fields)


def _cloud_started(launch_id, **extra):
    rec = _started(launch_id)
    rec["cloudSessionName"] = "lane-%s" % launch_id
    rec["cloudSessionId"] = SESSION_ID
    rec.update(extra)
    return rec


def _without(rec, *keys):
    return {k: v for k, v in rec.items() if k not in keys}


def _refusal(records):
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["launches"] == {}
    return result["reason"]


def _setup_cloud_lane(tmp_path, monkeypatch, launch_id="c1", pid=999999, started=True,
                      batch="b-cloud", issue=656):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(repo, batch, 1)["ok"]
    assert ll.append(repo, _cloud_reserved(launch_id, batch, repo, issue=issue))
    if started:
        rec = _cloud_started(launch_id)
        rec["pid"] = pid
        assert ll.append(repo, rec)
    return repo


# --- vocabulary ---------------------------------------------------------------


def test_places_are_local_and_cloud():
    assert ll.PLACES == (ll.PLACE_LOCAL, ll.PLACE_CLOUD)


# --- edge 1: place other than "cloud" -----------------------------------------


@pytest.mark.parametrize("place", ["local", "", None, True, "Cloud", 1])
def test_edge1_place_other_than_cloud_is_refused(place):
    # axis: a wrong place value is refused (the cloud fields are valid, so only `place` can refuse).
    rec = _cloud_reserved("a", place=place)
    assert _refusal([rec]) == "fold-bad-field:reserved:place"


# --- edge 2: cloud reserved needs environment and plugin version --------------


@pytest.mark.parametrize("field", ["cloudEnvironment", "pluginVersion"])
def test_edge2_cloud_reserved_missing_field(field):
    rec = _without(_cloud_reserved("a"), field)
    assert _refusal([rec]) == "fold-bad-field:reserved:%s" % field


@pytest.mark.parametrize("field", ["cloudEnvironment", "pluginVersion"])
@pytest.mark.parametrize("value", ["", "   ", 5, None, ["x"]])
def test_edge2_cloud_reserved_bad_field(field, value):
    rec = _cloud_reserved("a", **{field: value})
    assert _refusal([rec]) == "fold-bad-field:reserved:%s" % field


# --- edge 3: cloud reserved carries no local-only field -----------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"worktree": "/abs/worktree"},
        {"sessionId": "0f0e0d0c-0b0a-4908-8706-050403020100"},
        {"slot": "slot-a", "generation": 1},
        {"boundary": {}},
        {"iphoneId": "0F0E0D0C-0B0A-4908-8706-050403020100"},
    ],
    ids=["worktree", "sessionId", "slot-generation", "boundary", "iphoneId"],
)
def test_edge3_cloud_reserved_refuses_local_only_field(extra):
    rec = _cloud_reserved("a", **extra)
    assert _refusal([rec]) == "fold-bad-field:reserved:place-local-field"


# --- edge 4: local reserved carries no cloud field ----------------------------


@pytest.mark.parametrize("field,value", [("cloudEnvironment", "env_abc"), ("pluginVersion", "1.2.3")])
def test_edge4_local_reserved_refuses_cloud_field(field, value):
    rec = _reserved("a", "b", ["x"], "/tmp", **{field: value})
    assert _refusal([rec]) == "fold-bad-field:reserved:%s" % field


# --- edge 5: cloud started identity -------------------------------------------


def test_edge5_cloud_started_without_session_name_is_refused():
    started = _without(_cloud_started("a"), "cloudSessionName")
    assert _refusal([_cloud_reserved("a"), started]) == "fold-bad-field:started:cloudSessionName"


def test_edge5_cloud_started_with_neither_id_nor_unconfirmed_is_refused():
    # axis: an identity-less cloud start is refused.
    started = _without(_cloud_started("a"), "cloudSessionId")
    assert _refusal([_cloud_reserved("a"), started]) == "fold-bad-field:started:cloudSessionId"


def test_edge5_cloud_started_with_both_id_and_unconfirmed_is_refused():
    started = _cloud_started("a", cloudSessionUnconfirmed=True)
    assert _refusal([_cloud_reserved("a"), started]) == "fold-bad-field:started:cloudSessionId"


# --- edge 6: local started carries no cloud field -----------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("cloudSessionName", "lane-a"),
        ("cloudSessionId", SESSION_ID),
        ("cloudSessionUrl", "https://example.invalid/session"),
        ("cloudSessionUnconfirmed", True),
    ],
)
def test_edge6_local_started_refuses_cloud_field(field, value):
    started = dict(_started("a"), **{field: value})
    reason = _refusal([_reserved("a", "b", ["x"], "/tmp"), started])
    assert reason == "fold-bad-field:started:cloud-field-on-local-lane"


# --- edge 7: field shapes -----------------------------------------------------


@pytest.mark.parametrize("value", ["", "session_", "0f0e0d0c-0b0a-4908-8706-050403020100", 12, None, "session_ab-c",
                                   "session_abc\n", " session_abc"])
def test_edge7_bad_cloud_session_id_shape(value):
    started = _cloud_started("a", cloudSessionId=value)
    assert _refusal([_cloud_reserved("a"), started]) == "fold-bad-field:started:cloudSessionId"


@pytest.mark.parametrize("value", [False, "true", 1, None])
def test_edge7_bad_cloud_session_unconfirmed_shape(value):
    started = _cloud_started("a", cloudSessionUnconfirmed=value)
    started = _without(started, "cloudSessionId")
    reason = _refusal([_cloud_reserved("a"), started])
    assert reason == "fold-bad-field:started:cloudSessionUnconfirmed"


@pytest.mark.parametrize("field", ["cloudSessionName", "cloudSessionUrl"])
@pytest.mark.parametrize("value", ["", "  ", 3, None])
def test_edge7_bad_cloud_session_name_and_url_shape(field, value):
    started = _cloud_started("a", **{field: value})
    assert _refusal([_cloud_reserved("a"), started]) == "fold-bad-field:started:%s" % field


# --- fold output --------------------------------------------------------------


def test_fold_cloud_lane_confirmed_start():
    started = _cloud_started("a", cloudSessionUrl="https://example.invalid/s/1")
    folded = ll.fold([_cloud_reserved("a"), started])
    assert folded["ok"] is True
    lane = folded["launches"]["a"]
    assert lane["place"] == "cloud"
    assert lane["cloudEnvironment"] == "env_abc"
    assert lane["pluginVersion"] == "1.2.3"
    assert lane["cloudSessionId"] == SESSION_ID
    assert lane["cloudSessionName"] == "lane-a"
    assert lane["cloudSessionUrl"] == "https://example.invalid/s/1"
    assert lane["cloudSessionUnconfirmed"] is False
    assert lane["started"] is True


def test_fold_cloud_lane_unconfirmed_start():
    started = _without(_cloud_started("a"), "cloudSessionId")
    started["cloudSessionUnconfirmed"] = True
    lane = ll.fold([_cloud_reserved("a"), started])["launches"]["a"]
    assert lane["cloudSessionId"] is None
    assert lane["cloudSessionUnconfirmed"] is True
    assert lane["cloudSessionName"] == "lane-a"
    assert lane["cloudSessionUrl"] is None


def test_fold_cloud_lane_before_started_has_null_session_values():
    lane = ll.fold([_cloud_reserved("a")])["launches"]["a"]
    assert lane["place"] == "cloud"
    assert lane["cloudSessionId"] is None
    assert lane["cloudSessionName"] is None
    assert lane["cloudSessionUrl"] is None
    assert lane["cloudSessionUnconfirmed"] is False


# --- edge 11: a ledger with no `place` anywhere --------------------------------


def test_edge11_ledger_without_place_folds_every_lane_local():
    records = [
        _reserved("a", "b", ["x"], "/tmp"),
        _started("a"),
        _reserved("b2", "b", ["y"], "/tmp", issue=657),
    ]
    folded = ll.fold(records)
    assert folded["ok"] is True
    for lane in folded["launches"].values():
        assert lane["place"] == "local"
        assert lane["cloudEnvironment"] is None
        assert lane["pluginVersion"] is None
        assert lane["cloudSessionId"] is None
        assert lane["cloudSessionName"] is None
        assert lane["cloudSessionUrl"] is None
        assert lane["cloudSessionUnconfirmed"] is False


def test_edge11_count_of_a_local_batch_reports_zero_cloud(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(repo, "b-local", 1)["ok"]
    assert ll.append(repo, _reserved("l1", "b-local", ["x"], repo))
    assert ll.append(repo, _started("l1"))
    assert ll.record_outcome(repo, "l1", "handback", "done")["ok"]
    result = ll.count(repo, "b-local")
    assert result["resolved"] is True
    assert result["lanes"] == {"declared": 1, "resolved": 1, "cloud": 0}
    assert [lane["place"] for lane in result["laneDetail"]] == ["local"]


def test_count_indeterminate_reports_zero_cloud(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ll.count(repo, "no-such-batch")
    assert result["indeterminate"] is True
    assert result["lanes"] == {"declared": 0, "resolved": 0, "cloud": 0}


# --- edge 8: a cloud lane records its outcome with a live recorded pid --------


@pytest.mark.parametrize("outcome", ll.TERMINAL_OUTCOMES)
def test_edge8_cloud_lane_outcome_records_with_live_pid(tmp_path, monkeypatch, outcome):
    # axis: a cloud lane's outcome records with a live pid.
    repo = _setup_cloud_lane(tmp_path, monkeypatch, pid=os.getpid())
    result = ll.record_outcome(repo, "c1", outcome, "evidence text")
    assert result["ok"] is True
    assert result["recorded"] == "outcome"
    written = [r for r in ll.read(repo)["records"] if r.get("event") == "outcome"]
    assert [r["outcome"] for r in written] == [outcome]


def test_edge8_same_fixture_as_a_local_lane_still_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(repo, "b-local", 1)["ok"]
    assert ll.append(repo, _reserved("l1", "b-local", ["x"], repo))
    started = _started("l1")
    started["pid"] = os.getpid()
    assert ll.append(repo, started)
    result = ll.record_outcome(repo, "l1", "handback", "done")
    assert result["ok"] is False
    assert result["reason"].startswith("terminal-child-live:")


# --- edge 9: a cloud lane with no started --------------------------------------


def test_edge9_cloud_lane_without_started_refuses_outcome(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, started=False)
    result = ll.record_outcome(repo, "c1", "handback", "done")
    assert result["ok"] is False
    assert result["reason"] == "outcome-without-started"
    assert not any(r.get("event") == "outcome" for r in ll.read(repo)["records"])


# --- the repair path -----------------------------------------------------------


def _repair(**extra):
    rec = {"attempt": 1, "pid": os.getpid(), "logPath": "/tmp/log", "errPath": "/tmp/err"}
    rec.update(extra)
    return rec


def test_repair_path_on_cloud_lane_skips_probe_and_copies_cloud_fields(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, started=False)
    repair = _repair(
        cloudSessionName="lane-c1", cloudSessionId=SESSION_ID,
        cloudSessionUrl="https://example.invalid/s/1",
    )
    result = ll.terminalize(
        repo, "c1", child_ever_spawned=True, outcome="park", evidence="launch append failed",
        started_repair=repair,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    started = next(r for r in records if r.get("event") == "started")
    assert started["repaired"] is True
    assert started["cloudSessionName"] == "lane-c1"
    assert started["cloudSessionId"] == SESSION_ID
    assert started["cloudSessionUrl"] == "https://example.invalid/s/1"
    assert "cloudSessionUnconfirmed" not in started
    lane = ll.fold(records)["launches"]["c1"]
    assert lane["cloudSessionId"] == SESSION_ID
    assert lane["terminal"] is True


def test_repair_path_copies_unconfirmed_marker(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, started=False)
    repair = _repair(cloudSessionName="lane-c1", cloudSessionUnconfirmed=True)
    result = ll.terminalize(
        repo, "c1", child_ever_spawned=True, outcome="park", evidence="x", started_repair=repair,
    )
    assert result["ok"] is True
    lane = ll.fold(ll.read(repo)["records"])["launches"]["c1"]
    assert lane["cloudSessionUnconfirmed"] is True
    assert lane["cloudSessionId"] is None


def test_repair_path_cloud_lane_without_cloud_fields_is_refused_by_fold(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, started=False)
    before = len(ll.read(repo)["records"])
    result = ll.terminalize(
        repo, "c1", child_ever_spawned=True, outcome="park", evidence="x", started_repair=_repair(),
    )
    assert result["ok"] is False
    assert result["reason"] == "fold-bad-field:started:cloudSessionName"
    assert len(ll.read(repo)["records"]) == before


@pytest.mark.parametrize("extra", [
    {"cloudSessionId": "session_"},
    {"cloudSessionUnconfirmed": False},
    {"cloudSessionName": " "},
    {"cloudSessionUrl": ""},
])
def test_repair_path_bad_cloud_field_shape_is_unavailable(tmp_path, monkeypatch, extra):
    repo = _setup_cloud_lane(tmp_path, monkeypatch, started=False)
    before = len(ll.read(repo)["records"])
    repair = _repair(cloudSessionName="lane-c1", cloudSessionId=SESSION_ID)
    repair.update(extra)
    result = ll.terminalize(
        repo, "c1", child_ever_spawned=True, outcome="park", evidence="x", started_repair=repair,
    )
    assert result["ok"] is False
    assert result["reason"] == "terminal-repair-unavailable"
    assert len(ll.read(repo)["records"]) == before


def test_repair_path_local_lane_with_cloud_field_is_refused_by_fold(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert ll.append(repo, _reserved("l1", "b", ["x"], repo))
    repair = _repair(pid=999999, cloudSessionName="lane-l1", cloudSessionId=SESSION_ID)
    result = ll.terminalize(
        repo, "l1", child_ever_spawned=True, outcome="park", evidence="x", started_repair=repair,
    )
    assert result["ok"] is False
    assert result["reason"] == "fold-bad-field:started:cloud-field-on-local-lane"


# --- count --------------------------------------------------------------------


def _three_cloud_lanes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(repo, "b3", 3)["ok"]
    for n, outcome in enumerate(("handback", "park", "died")):
        launch_id = "c%d" % n
        assert ll.append(repo, _cloud_reserved(launch_id, "b3", repo, issue=700 + n))
        assert ll.append(repo, _cloud_started(launch_id))
        assert ll.record_outcome(repo, launch_id, outcome, "evidence")["ok"]
    return repo


def test_count_three_cloud_lanes(tmp_path, monkeypatch):
    # axis: a cloud lane is marked in count.
    repo = _three_cloud_lanes(tmp_path, monkeypatch)
    result = ll.count(repo, "b3")
    assert result["resolved"] is True
    assert result["indeterminate"] is False
    assert result["lanes"] == {"declared": 3, "resolved": 3, "cloud": 3}
    assert [lane["place"] for lane in result["laneDetail"]] == ["cloud", "cloud", "cloud"]
    assert result["counts"]["total"] == 3


def test_count_mixed_batch_counts_one_cloud(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(repo, "bm", 2)["ok"]
    assert ll.append(repo, _cloud_reserved("c1", "bm", repo, issue=801))
    assert ll.append(repo, _cloud_started("c1"))
    assert ll.record_outcome(repo, "c1", "handback", "done")["ok"]
    assert ll.append(repo, _reserved("l1", "bm", ["y"], repo, issue=802))
    assert ll.append(repo, _started("l1"))
    assert ll.record_outcome(repo, "l1", "handback", "done")["ok"]
    result = ll.count(repo, "bm")
    assert result["lanes"] == {"declared": 2, "resolved": 2, "cloud": 1}
    by_issue = {lane["issue"]: lane["place"] for lane in result["laneDetail"]}
    assert by_issue == {801: "cloud", 802: "local"}


def test_count_live_cloud_lane_stays_indeterminate(tmp_path, monkeypatch):
    repo = _setup_cloud_lane(tmp_path, monkeypatch)
    result = ll.count(repo, "b-cloud")
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-unresolved:c1"
    assert result["lanes"]["cloud"] == 0


def test_cloud_record_outcome_after_terminal_still_amends(tmp_path, monkeypatch):
    repo = _three_cloud_lanes(tmp_path, monkeypatch)
    result = ll.record_outcome(repo, "c0", "handback", "again")
    assert result["ok"] is True
    assert result["recorded"] in ("amendment", "amendment-existing")
