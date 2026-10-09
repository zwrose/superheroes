import json
import os
import subprocess
import sys
import time

import pytest

import iphone_reap as ir
import launch_ledger as ll

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(os.path.dirname(_HERE), "iphone_reap.py")

_PHONE_A = "E1F5C684-4D8F-4030-A7CE-1BFEFA9F153A"
_PHONE_B = "B2A6D795-5E90-4141-B8DF-2CAFAB0A264B"
_PHONE_C = "C3B7E8A6-6FA1-4252-89E0-3DB0BC1B375C"
_PHONE_D = "D4C8F9B7-70B2-4363-9AF1-4EC1CD2C486D"
_PHONE_OTHER = "F5D90AC8-81C3-4474-ABA2-5FD2DE3D597E"
_RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-27-0"
_DELETE_ARGV = ["xcrun", "simctl", "delete"]
_CENSUS_ARGV = ["xcrun", "simctl", "list", "devices", "-j"]


def _init_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "file.txt").write_text("x\n")
    identity = ["-c", "user.email=test@test.local", "-c", "user.name=test"]
    subprocess.run(["git", "-C", str(tmp_path), *identity, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), *identity, "commit", "-q", "-m", "init"], check=True,
    )
    return str(tmp_path)


def _ledger_env(tmp_path, monkeypatch):
    root = str(tmp_path / "ledger-root")
    os.makedirs(root, mode=0o700, exist_ok=True)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, root)
    return root


def _reserved(launch_id, issue, repo_root, udid=None):
    rec = {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "b1",
        "repoId": ll.repo_identity(repo_root) or "test",
        "issue": issue,
        "surfaces": ["surface-%s" % launch_id],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc123",
        "model": "test-model",
    }
    if udid is not None:
        rec["premise"] = {"iphoneCheck": True}
        rec["iphoneId"] = udid
    return rec


def _started(launch_id):
    return {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": 999999,
        "logPath": "/tmp/log",
        "errPath": "/tmp/err",
    }


def _launch(repo, launch_id, issue, udid=None, end=None):
    """Reserve a launch and end it: "refused" (never ran), "handback" (ran), or None (live)."""
    reserved = ll.reserve(repo, _reserved(launch_id, issue, repo, udid))
    assert reserved["ok"] is True, reserved
    if end == "refused":
        ended = ll.terminalize(repo, launch_id, stage="spawn", reason="engine-auth")
        assert ended["ok"] is True, ended
    elif end == "handback":
        assert ll.append(repo, _started(launch_id)) is True
        ended = ll.terminalize(repo, launch_id, outcome="handback", evidence="done")
        assert ended["ok"] is True, ended
    else:
        assert end is None


def _amendments(repo, launch_id):
    folded = ll.fold(ll.read(repo)["records"])
    assert folded["ok"] is True, folded
    return folded["launches"][launch_id]["amendments"]


def _reap_amendments(repo, launch_id):
    return [a for a in _amendments(repo, launch_id) if a["value"] == "reap"]


def _proc(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


def _census_json(udids):
    return json.dumps({"devices": {
        _RUNTIME: [
            {
                "dataPath": "/d/%s" % udid, "dataPathSize": 1, "deviceTypeIdentifier": "t",
                "isAvailable": True, "logPath": "/l/%s" % udid, "name": "n",
                "state": "Booted", "udid": udid,
            }
            for udid in sorted(udids)
        ],
        "com.apple.CoreSimulator.SimRuntime.tvOS-27-0": [],
    }})


class _Raw:
    """A census reply taken verbatim: stdout text and return code."""

    def __init__(self, stdout, returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class _FakeRun:
    """Records every (argv, timeout); delete replies are per udid, the census is one reply.

    A delete reply is an exception instance (raised) or a (returncode, text) pair; the default
    is (0, ""). The census is a set of udids, a _Raw, or an exception instance (raised).
    """

    def __init__(self, deletes=None, census=()):
        self.calls = []
        self.deletes = deletes or {}
        self.census = census

    def __call__(self, argv, timeout):
        self.calls.append((list(argv), timeout))
        if argv[:3] == _DELETE_ARGV:
            reply = self.deletes.get(argv[3], (0, ""))
            if isinstance(reply, Exception):
                raise reply
            return _proc(argv, reply[0], stderr=reply[1])
        assert argv == _CENSUS_ARGV, argv
        if isinstance(self.census, Exception):
            raise self.census
        if isinstance(self.census, _Raw):
            return _proc(argv, self.census.returncode, stdout=self.census.stdout)
        return _proc(argv, 0, stdout=_census_json(self.census))

    @property
    def argvs(self):
        return [argv for argv, _ in self.calls]

    @property
    def deleted(self):
        return [argv[3] for argv in self.argvs if argv[:3] == _DELETE_ARGV]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    path = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    return path


def _two_phone_lane(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="handback")


def _phone_ids(listing):
    return [p["iphoneId"] for p in listing["phones"]]


# ---- lane_phones: what the lane's records name ----

def test_phones_relaunch_lists_both_phones(repo):
    _two_phone_lane(repo)
    listing = ir.lane_phones(repo, 7)
    assert listing == {
        "ok": True, "reason": None, "issue": 7,
        "phones": [
            {"launchId": "l1", "iphoneId": _PHONE_A, "terminal": True},
            {"launchId": "l2", "iphoneId": _PHONE_B, "terminal": True},
        ],
        "liveLaunches": [],
    }


def test_phones_failed_launch_after_reserve_is_listed(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    listing = ir.lane_phones(repo, 7)
    assert _phone_ids(listing) == [_PHONE_A]
    assert listing["liveLaunches"] == []


def test_phones_other_issue_phone_is_excluded(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    _launch(repo, "l2", 8, _PHONE_OTHER, end="handback")
    assert _phone_ids(ir.lane_phones(repo, 7)) == [_PHONE_A]
    assert _phone_ids(ir.lane_phones(repo, 8)) == [_PHONE_OTHER]


def test_phones_same_issue_launch_without_phone_is_excluded(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, None, end="handback")
    listing = ir.lane_phones(repo, 7)
    assert [p["launchId"] for p in listing["phones"]] == ["l1"]
    assert listing["liveLaunches"] == []


def test_phones_non_terminal_launch_is_in_live_launches(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    _launch(repo, "l2", 7, None, end=None)
    listing = ir.lane_phones(repo, 7)
    assert listing["ok"] is True
    assert _phone_ids(listing) == [_PHONE_A]
    assert listing["liveLaunches"] == ["l2"]


def test_phones_live_launch_with_phone_is_listed_not_terminal(repo):
    _launch(repo, "l1", 7, _PHONE_A, end=None)
    listing = ir.lane_phones(repo, 7)
    assert listing["phones"] == [{"launchId": "l1", "iphoneId": _PHONE_A, "terminal": False}]
    assert listing["liveLaunches"] == ["l1"]


def test_phones_pre_iphone_record_has_no_phone(repo):
    _launch(repo, "l1", 7, None, end="handback")
    listing = ir.lane_phones(repo, 7)
    assert listing["ok"] is True
    assert listing["phones"] == []
    assert listing["liveLaunches"] == []


def test_phones_listed_set_is_exactly_the_issues_recorded_phones(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="handback")
    _launch(repo, "l3", 7, None, end="handback")
    _launch(repo, "l4", 8, _PHONE_OTHER, end="handback")
    _launch(repo, "l5", 7, _PHONE_C, end=None)
    # The expected set is read off the raw reserved records, not off the fold the helper uses.
    named = [
        rec["iphoneId"] for rec in ll.read(repo)["records"]
        if rec["event"] == "reserved" and rec["issue"] == 7 and rec.get("iphoneId")
    ]
    assert named == [_PHONE_A, _PHONE_B, _PHONE_C]
    listing = ir.lane_phones(repo, 7)
    assert _phone_ids(listing) == named
    assert _PHONE_OTHER not in _phone_ids(listing)


_BAD_ISSUES = [0, -1, True, False, "7", None, 7.0, [7]]


@pytest.mark.parametrize("issue", _BAD_ISSUES, ids=repr)
def test_phones_invalid_issue_refuses(repo, issue):
    _launch(repo, "l1", 1, _PHONE_A, end="handback")
    listing = ir.lane_phones(repo, issue)
    assert listing["ok"] is False
    assert listing["reason"] == "reap-issue-invalid"
    assert listing["phones"] == []


def test_phones_missing_ledger_is_unreadable(repo):
    listing = ir.lane_phones(repo, 7)
    assert ll.read(repo)["state"] == "missing"
    assert listing["ok"] is False
    assert listing["reason"] == "reap-ledger-unreadable:missing"


def test_phones_corrupt_ledger_is_unreadable(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    with open(ll.ledger_path(repo)["path"], "ab") as fh:
        fh.write(b"not json\n")
    state = ll.read(repo)["state"]
    assert state != "ok"
    listing = ir.lane_phones(repo, 7)
    assert listing["ok"] is False
    assert listing["reason"] == "reap-ledger-unreadable:%s" % state
    assert listing["phones"] == []


def test_phones_fold_refusal_is_carried(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    assert ll.append(repo, _started("ghost")) is True
    listing = ir.lane_phones(repo, 7)
    assert listing["ok"] is False
    assert listing["reason"] == "reap-ledger-fold-refused:fold-orphan-event:ghost"
    assert listing["phones"] == []


# ---- reap_lane: results ----

def test_reap_all_deleted(repo):
    _two_phone_lane(repo)
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result == {
        "ok": True, "reason": None, "issue": 7,
        "phones": [
            {"launchId": "l1", "iphoneId": _PHONE_A, "result": "deleted", "detail": None},
            {"launchId": "l2", "iphoneId": _PHONE_B, "result": "deleted", "detail": None},
        ],
        "leftRunning": [], "recordFailures": [],
    }
    assert run.argvs == [_DELETE_ARGV + [_PHONE_A], _DELETE_ARGV + [_PHONE_B]]


def test_reap_already_gone(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (148, "Invalid device: %s" % _PHONE_A)}, census={_PHONE_B})
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is True
    assert result["phones"][0]["result"] == "already-gone"
    assert result["leftRunning"] == []
    assert run.argvs == [_DELETE_ARGV + [_PHONE_A], _CENSUS_ARGV]


def test_reap_left_running(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (1, "NSCocoaErrorDomain code 513\nmore")}, census={_PHONE_A})
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-incomplete"
    assert result["phones"] == [{
        "launchId": "l1", "iphoneId": _PHONE_A, "result": "left-running",
        "detail": "NSCocoaErrorDomain code 513",
    }]
    assert result["leftRunning"] == [_PHONE_A]
    assert result["recordFailures"] == []


def test_reap_left_running_detail_is_first_line_cut_to_200(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (1, "x" * 500 + "\nsecond line")}, census={_PHONE_A})
    detail = ir.reap_lane(repo, 7, run=run)["phones"][0]["detail"]
    assert detail == "x" * 200


@pytest.mark.parametrize("raised", [
    subprocess.TimeoutExpired(["xcrun"], 60),
    OSError("no xcrun"),
], ids=["timeout", "oserror"])
def test_reap_delete_raises_and_phone_listed_is_left_running(repo, raised):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: raised}, census={_PHONE_A})
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["phones"][0]["result"] == "left-running"
    assert type(raised).__name__ in result["phones"][0]["detail"]
    assert result["leftRunning"] == [_PHONE_A]


@pytest.mark.parametrize("raised", [
    subprocess.TimeoutExpired(["xcrun"], 60),
    OSError("no xcrun"),
], ids=["timeout", "oserror"])
def test_reap_delete_raises_and_phone_absent_is_already_gone(repo, raised):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: raised}, census=set())
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is True
    assert result["phones"][0]["result"] == "already-gone"


_UNREADABLE_CENSUSES = {
    "runner-raises": OSError("simctl missing"),
    "timeout": subprocess.TimeoutExpired(_CENSUS_ARGV, 30),
    "nonzero-rc": _Raw(_census_json(set()), returncode=1),
    "not-json": _Raw("no devices here"),
    "empty-output": _Raw(""),
    "top-level-list": _Raw("[]"),
    "no-devices-key": _Raw(json.dumps({"other": {}})),
    "devices-is-list": _Raw(json.dumps({"devices": []})),
    "devices-value-not-list": _Raw(json.dumps({"devices": {_RUNTIME: {}}})),
    "element-not-object": _Raw(json.dumps({"devices": {_RUNTIME: ["x"]}})),
    "element-lacks-udid": _Raw(json.dumps({"devices": {_RUNTIME: [{"name": "n"}]}})),
    "udid-not-string": _Raw(json.dumps({"devices": {_RUNTIME: [{"udid": 7}]}})),
}


@pytest.mark.parametrize("census", list(_UNREADABLE_CENSUSES.values()),
                         ids=list(_UNREADABLE_CENSUSES))
def test_reap_census_unreadable_is_left_running_never_gone(repo, census):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (1, "could not delete")}, census=census)
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-incomplete"
    assert result["phones"] == [{
        "launchId": "l1", "iphoneId": _PHONE_A, "result": "left-running",
        "detail": "census-unreadable",
    }]
    assert result["leftRunning"] == [_PHONE_A]
    assert _reap_amendments(repo, "l1")[0]["note"] == (
        "reap: phone %s left running: census-unreadable" % _PHONE_A
    )


def test_reap_census_is_valid_with_empty_runtimes_and_other_phones(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (148, "Invalid device")}, census={_PHONE_OTHER})
    assert ir.reap_lane(repo, 7, run=run)["phones"][0]["result"] == "already-gone"


@pytest.mark.parametrize("live_has_phone", [True, False], ids=["phone", "no-phone"])
def test_reap_live_launch_refuses_with_no_runner_call(repo, live_has_phone):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    _launch(repo, "l2", 7, _PHONE_B if live_has_phone else None, end=None)
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-lane-not-terminal:l2"
    assert result["phones"] == []
    assert run.calls == []
    assert _reap_amendments(repo, "l1") == []


@pytest.mark.parametrize("issue", _BAD_ISSUES, ids=repr)
def test_reap_invalid_issue_runs_nothing(repo, issue):
    _launch(repo, "l1", 1, _PHONE_A, end="handback")
    run = _FakeRun()
    result = ir.reap_lane(repo, issue, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-issue-invalid"
    assert run.calls == []


def test_reap_unreadable_ledger_runs_nothing(repo):
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-ledger-unreadable:missing"
    assert run.calls == []


def test_reap_fold_refusal_runs_nothing(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    assert ll.append(repo, _started("ghost")) is True
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-ledger-fold-refused:fold-orphan-event:ghost"
    assert run.calls == []


def test_reap_no_launch_for_issue_is_ok_and_idle(repo):
    _launch(repo, "l1", 8, _PHONE_OTHER, end="handback")
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result == {
        "ok": True, "reason": None, "issue": 7,
        "phones": [], "leftRunning": [], "recordFailures": [],
    }
    assert run.calls == []
    assert _amendments(repo, "l1") == []


def test_reap_lane_without_any_phone_is_ok_and_idle(repo):
    _launch(repo, "l1", 7, None, end="handback")
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is True
    assert result["phones"] == []
    assert run.calls == []
    assert _amendments(repo, "l1") == []


def test_reap_duplicate_udid_is_deleted_once_and_amended_twice(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_A, end="handback")
    run = _FakeRun()
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is True
    assert run.deleted == [_PHONE_A]
    assert [(p["launchId"], p["result"]) for p in result["phones"]] == [
        ("l1", "deleted"), ("l2", "deleted"),
    ]
    note = "reap: phone %s deleted" % _PHONE_A
    for launch_id in ("l1", "l2"):
        assert [(a["kind"], a["value"], a["note"]) for a in _reap_amendments(repo, launch_id)] == [
            ("evidence", "reap", note),
        ]


def test_reap_duplicate_udid_left_running_is_listed_once(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (1, "busy")}, census={_PHONE_A})
    result = ir.reap_lane(repo, 7, run=run)
    assert result["leftRunning"] == [_PHONE_A]
    assert [p["result"] for p in result["phones"]] == ["left-running", "left-running"]
    assert run.argvs.count(_CENSUS_ARGV) == 1


def test_reap_one_failure_does_not_stop_the_others(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="refused")
    _launch(repo, "l3", 7, _PHONE_C, end="handback")
    run = _FakeRun(deletes={_PHONE_A: OSError("boom")}, census={_PHONE_A})
    result = ir.reap_lane(repo, 7, run=run)
    assert run.deleted == [_PHONE_A, _PHONE_B, _PHONE_C]
    assert [p["result"] for p in result["phones"]] == ["left-running", "deleted", "deleted"]
    assert result["leftRunning"] == [_PHONE_A]


def test_reap_amendments_are_read_back_from_the_ledger(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="handback")
    _launch(repo, "l3", 7, _PHONE_C, end="handback")
    run = _FakeRun(deletes={_PHONE_B: (148, "Invalid device"), _PHONE_C: (1, "busy\nx")},
                   census={_PHONE_C})
    ir.reap_lane(repo, 7, run=run)
    expected = {
        "l1": "reap: phone %s deleted" % _PHONE_A,
        "l2": "reap: phone %s already gone" % _PHONE_B,
        "l3": "reap: phone %s left running: busy" % _PHONE_C,
    }
    for launch_id, note in expected.items():
        assert [(a["kind"], a["value"], a["note"]) for a in _amendments(repo, launch_id)] == [
            ("evidence", "reap", note),
        ]


def test_reap_amendment_failure_is_a_record_failure(repo, monkeypatch):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="handback")
    real_amend = ll.amend

    def amend(repo_root, launch_id, *args, **kwargs):
        if launch_id == "l1":
            return {"ok": False, "reason": "lock-unavailable"}
        return real_amend(repo_root, launch_id, *args, **kwargs)

    monkeypatch.setattr(ll, "amend", amend)
    result = ir.reap_lane(repo, 7, run=_FakeRun())
    assert result["ok"] is False
    assert result["reason"] == "reap-incomplete"
    assert result["leftRunning"] == []
    assert result["recordFailures"] == [{
        "launchId": "l1", "iphoneId": _PHONE_A, "result": "deleted", "reason": "lock-unavailable",
    }]
    assert _reap_amendments(repo, "l1") == []
    assert len(_reap_amendments(repo, "l2")) == 1


def test_reap_amendment_failure_and_delete_failure_land_in_both_lists(repo, monkeypatch):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="handback")
    real_amend = ll.amend

    def amend(repo_root, launch_id, *args, **kwargs):
        if launch_id == "l1":
            return {"ok": False, "reason": "ledger-append-failed"}
        return real_amend(repo_root, launch_id, *args, **kwargs)

    monkeypatch.setattr(ll, "amend", amend)
    run = _FakeRun(deletes={_PHONE_A: (1, "busy")}, census={_PHONE_A})
    result = ir.reap_lane(repo, 7, run=run)
    assert result["ok"] is False
    assert result["reason"] == "reap-incomplete"
    assert result["leftRunning"] == [_PHONE_A]
    assert result["recordFailures"] == [{
        "launchId": "l1", "iphoneId": _PHONE_A, "result": "left-running",
        "reason": "ledger-append-failed",
    }]
    assert run.deleted == [_PHONE_A, _PHONE_B]
    assert [a["note"] for a in _reap_amendments(repo, "l2")] == [
        "reap: phone %s deleted" % _PHONE_B,
    ]


def test_reap_timeouts_are_pinned(repo):
    assert ir.DELETE_TIMEOUT == 60
    assert ir.CENSUS_TIMEOUT == 30
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun(deletes={_PHONE_A: (1, "busy")}, census={_PHONE_A})
    ir.reap_lane(repo, 7, run=run)
    assert run.calls == [
        (_DELETE_ARGV + [_PHONE_A], 60),
        (_CENSUS_ARGV, 30),
    ]


# ---- the argv census: the only commands the helper may send ----

def test_reap_every_argv_is_a_lane_delete_or_the_census(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="refused")
    _launch(repo, "l2", 7, _PHONE_B, end="refused")
    _launch(repo, "l3", 7, _PHONE_C, end="refused")
    _launch(repo, "l4", 7, _PHONE_D, end="handback")
    _launch(repo, "l5", 8, _PHONE_OTHER, end="handback")
    lane_set = {
        rec["iphoneId"] for rec in ll.read(repo)["records"]
        if rec["event"] == "reserved" and rec["issue"] == 7 and rec.get("iphoneId")
    }
    assert lane_set == {_PHONE_A, _PHONE_B, _PHONE_C, _PHONE_D}
    run = _FakeRun(
        deletes={
            _PHONE_B: (1, "busy"),
            _PHONE_C: subprocess.TimeoutExpired(["xcrun"], 60),
            _PHONE_D: (148, "Invalid device"),
        },
        census={_PHONE_B, _PHONE_C, _PHONE_OTHER},
    )
    result = ir.reap_lane(repo, 7, run=run)
    assert [p["result"] for p in result["phones"]] == [
        "deleted", "left-running", "left-running", "already-gone",
    ]
    assert run.argvs
    for argv in run.argvs:
        if argv == _CENSUS_ARGV:
            continue
        assert len(argv) == 4 and argv[:3] == _DELETE_ARGV, argv
        assert argv[3] in lane_set, argv
    assert sorted(a[3] for a in run.argvs if a != _CENSUS_ARGV) == sorted(
        [_PHONE_A, _PHONE_B, _PHONE_C, _PHONE_D]
    )
    assert _PHONE_OTHER not in [token for argv in run.argvs for token in argv]


# ---- CLI ----

def _cli(argv, capsys):
    code = ir.main(argv)
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    return code, json.loads(out)


def test_cli_reap_exits_zero_when_ok(repo, monkeypatch, capsys):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    run = _FakeRun()
    monkeypatch.setattr(ir, "_default_run", run)
    code, printed = _cli(["reap", "--repo-root", repo, "--issue", "7"], capsys)
    assert code == 0
    assert printed["ok"] is True
    assert printed["phones"][0]["result"] == "deleted"
    assert run.deleted == [_PHONE_A]


def test_cli_reap_exits_one_when_not_ok(repo, monkeypatch, capsys):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    monkeypatch.setattr(
        ir, "_default_run", _FakeRun(deletes={_PHONE_A: (1, "busy")}, census={_PHONE_A}),
    )
    code, printed = _cli(["reap", "--repo-root", repo, "--issue", "7"], capsys)
    assert code == 1
    assert printed["ok"] is False
    assert printed["reason"] == "reap-incomplete"
    assert printed["leftRunning"] == [_PHONE_A]


def test_cli_phones_lists_and_exits_zero(repo, capsys):
    _two_phone_lane(repo)
    code, printed = _cli(["phones", "--repo-root", repo, "--issue", "7"], capsys)
    assert code == 0
    assert [p["iphoneId"] for p in printed["phones"]] == [_PHONE_A, _PHONE_B]


@pytest.mark.parametrize("verb", ["phones", "reap"])
@pytest.mark.parametrize("issue", ["0", "-3", "abc", "7.5", ""])
def test_cli_invalid_issue_exits_one(repo, monkeypatch, capsys, verb, issue):
    run = _FakeRun()
    monkeypatch.setattr(ir, "_default_run", run)
    code, printed = _cli([verb, "--repo-root", repo, "--issue", issue], capsys)
    assert code == 1
    assert printed["ok"] is False
    assert printed["reason"] == "reap-issue-invalid"
    assert run.calls == []


def test_cli_script_entry_point_prints_one_json_line(repo):
    _launch(repo, "l1", 7, _PHONE_A, end="handback")
    proc = subprocess.run(
        [sys.executable, "-B", _SCRIPT, "phones", "--repo-root", repo, "--issue", "7"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("\n") == 1
    assert json.loads(proc.stdout)["phones"][0]["iphoneId"] == _PHONE_A
    bad = subprocess.run(
        [sys.executable, "-B", _SCRIPT, "reap", "--repo-root", repo, "--issue", "nope"],
        capture_output=True, text=True, check=False,
    )
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["reason"] == "reap-issue-invalid"
