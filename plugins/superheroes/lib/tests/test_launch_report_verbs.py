# plugins/superheroes/lib/tests/test_launch_report_verbs.py
"""Conformance: the launcher's `report` and `still` verbs. Every ledger, store and repository is built
under tmp_path; `_issue_title` is never run for real (tests pass `title_fn`, or patch `subprocess.run`)."""
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import control_plane  # noqa: E402
import launch_ledger as ll  # noqa: E402
import launch_report as LR  # noqa: E402
import launcher  # noqa: E402

from test_launch_ledger import (  # noqa: E402
    _declare,
    _init_repo,
    _ledger_env,
    _reserved,
    _started,
)

BATCH = "b-report"
PHONE = "the phone simulator"


def _call(place="local", pointed=True, reason=None, by="setting", need=None):
    return {"place": place, "pointedAtCloud": pointed, "by": by, "reason": reason, "need": need,
            "cloudVersion": None, "advisorVersion": None, "environment": None, "reported": None}


def _titles(repo_root, issue):
    return "Title %s" % issue


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A repository, a ledger root and a still-state store root, all under tmp_path."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    store = str(tmp_path / "store")
    monkeypatch.setattr(control_plane, "store_root", lambda: store)
    assert _declare(repo, BATCH, 4)["ok"]
    return repo, store


# Unmeasured — verify before use: the reserved/started record shapes below follow
# test_launch_ledger_cloud.py; every writer here is checked by `ll.fold` accepting the result.
def _reserve(repo, launch_id, issue, place="local", premise=None, batch=BATCH):
    fields = {"issue": issue}
    if place == "cloud":
        fields.update(place="cloud", cloudEnvironment="env_abc", pluginVersion="1.2.3")
    if premise is not None:
        fields["premise"] = premise
    result = ll.reserve(repo, _reserved(launch_id, batch, ["x"], repo, **fields))
    assert result["ok"], result


def _start(repo, launch_id, place="local"):
    rec = _started(launch_id)
    if place == "cloud":
        rec["cloudSessionName"] = "lane-%s" % launch_id
        rec["cloudSessionId"] = "session_01AbCdEf123"
    assert ll.append_under_lock(repo, rec)["ok"]


def _refuse(repo, launch_id):
    assert ll.terminalize(repo, launch_id, reason="engine-auth", stage="preflight")["ok"]


def _finish(repo, launch_id):
    assert ll.terminalize(repo, launch_id, child_ever_spawned=True, outcome="park",
                          evidence="x")["ok"]


def _launch(repo, launch_id, issue, place="local", call="auto"):
    if call == "auto":
        call = _call(place, pointed=True, reason=None if place == "cloud" else "no-setup")
    premise = None if call is None else {"placeCall": call}
    _reserve(repo, launch_id, issue, place, premise)
    _start(repo, launch_id, place)


def _report(repo, **kw):
    return launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles, **kw)


def _folds(repo):
    assert ll.fold(ll.read(repo)["records"])["ok"]


def _stored(repo, store):
    name = os.path.basename(LR._still_path(repo, store))
    for dirpath, _dirs, files in os.walk(store):
        if name in files:
            with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                return json.load(fh)
    return None


# ---------------------------------------------------------------- I1: exactly the builds that launched


def test_I1_one_line_per_started_issue_in_first_reservation_order(world):
    repo, _store = world
    _launch(repo, "a", 11)
    _launch(repo, "b", 22, "cloud")
    _folds(repo)
    got = _report(repo)
    assert got["ok"] is True and got["lanes"] == 2
    assert got["report"].splitlines()[:3] == [
        "Launched 2 builds.", "In the cloud: #22 Title 22.", "On your machine:"]
    assert "- #11 Title 11." in got["report"]


def test_I1_a_refused_launch_is_never_listed_E5(world):
    repo, store = world
    _reserve(repo, "r", 33, premise={"placeCall": _call()})
    _refuse(repo, "r")
    _folds(repo)
    assert _report(repo) == {"ok": True, "report": None, "still": {"action": "unchanged", "reason": None},
                             "lanes": 0}
    assert _stored(repo, store) is None


def test_I1_a_refused_launch_beside_a_started_one_is_not_counted(world):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    _reserve(repo, "r", 33, premise={"placeCall": _call()})
    _refuse(repo, "r")
    got = _report(repo)
    assert got["lanes"] == 1
    assert "#33" not in got["report"]


def test_I1_the_last_started_launch_of_an_issue_is_the_one_listed(world):
    repo, _store = world
    _launch(repo, "c1", 44, "cloud")
    _finish(repo, "c1")
    _launch(repo, "l1", 44, "local", _call(reason="needs", need=PHONE))
    _launch(repo, "z", 55, "cloud")
    _folds(repo)
    got = _report(repo)
    assert got["lanes"] == 2
    assert got["report"].splitlines() == [
        "Launched 2 builds.", "In the cloud: #55 Title 55.", "On your machine:",
        "- #44 Title 44. It needs the phone simulator, which only your machine has."]


def test_I1_the_issue_order_is_its_first_reservation_not_its_last(world):
    repo, _store = world
    _launch(repo, "c1", 44, "cloud")
    _finish(repo, "c1")
    _launch(repo, "m1", 55, "local", _call(reason="needs", need=PHONE))
    _launch(repo, "l1", 44, "local", _call(reason="needs", need=PHONE))
    _folds(repo)
    got = _report(repo)
    assert got["lanes"] == 2
    # both issues land under "On your machine", so their relative order is observed: first reservation
    # puts 44 ahead of 55, last reservation would put 55 ahead of 44
    lines = got["report"].splitlines()
    assert lines[1] == "On your machine:"
    assert lines[2].startswith("- #44 ") and lines[3].startswith("- #55 ")


def test_E6_a_refused_last_reservation_leaves_the_earlier_started_launch_listed(world):
    repo, _store = world
    _launch(repo, "c1", 44, "cloud")
    _finish(repo, "c1")
    _reserve(repo, "l1", 44, premise={"placeCall": _call()})
    _refuse(repo, "l1")
    _folds(repo)
    got = _report(repo)
    assert got["lanes"] == 1
    assert got["report"] == "Launched 1 build.\nIn the cloud: #44 Title 44."


def test_another_batchs_launches_are_not_listed(world):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    assert _declare(repo, "other", 1)["ok"]
    _reserve(repo, "o", 99, "cloud", {"placeCall": _call("cloud", reason=None)}, batch="other")
    _start(repo, "o", "cloud")
    got = _report(repo)
    assert got["lanes"] == 1 and "#99" not in got["report"]


# ---------------------------------------------------------------- I2: the folded place is the authority


def test_I2_a_matching_place_call_prints_its_reason(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="needs", need=PHONE))
    assert "- #11 Title 11. It needs the phone simulator, which only your machine has." in (
        _report(repo)["report"])


@pytest.mark.parametrize("premise", [
    None,                                                       # E7: premise absent
    "not a dict",                                               # E7: premise not a dict
    {},                                                         # E8: placeCall absent
    {"placeCall": "local"},                                     # E8: placeCall not a dict
    {"placeCall": _call("cloud", reason=None)},                 # E8: place disagrees with the fold
    {"placeCall": dict(_call(reason="needs", need=PHONE), pointedAtCloud="yes")},  # E8: not a bool
], ids=["no-premise", "premise-not-dict", "no-placeCall", "placeCall-not-dict", "place-disagrees",
        "pointed-not-bool"])
def test_I2_E7_E8_an_unusable_place_call_is_synthesized_without_a_reason(world, premise):
    repo, store = world
    _reserve(repo, "a", 11, premise=premise)
    _start(repo, "a")
    _reserve(repo, "b", 22, "cloud", premise)
    _start(repo, "b", "cloud")
    _folds(repo)
    got = _report(repo)
    # The local lane is synthesized pointed at nothing and the cloud lane as a cloud build: neither
    # carries a reason, so the report names none and the still state records none.
    assert got["lanes"] == 2
    assert got["report"] == ("Launched 2 builds.\nIn the cloud: #22 Title 22.\nOn your machine:\n"
                             "- #11 Title 11.")
    assert got["still"] == {"action": "unchanged", "reason": None}
    assert _stored(repo, store) is None


def test_I2_a_synthesized_local_call_alone_prints_no_report(world):
    repo, _store = world
    _reserve(repo, "a", 11, premise={})
    _start(repo, "a")
    got = _report(repo)
    assert got == {"ok": True, "report": None, "still": {"action": "unchanged", "reason": None},
                   "lanes": 1}


# ---------------------------------------------------------------- the ledger edges


def test_E1_a_missing_ledger_is_an_ok_empty_report(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": True, "report": None, "still": None, "lanes": 0}


def test_E2_a_torn_ledger_is_refused(world):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    path = ll.ledger_path(repo)["path"]
    with open(path, "ab") as fh:
        fh.write(b'{"event": "reserved", "launchId"')
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": False, "reason": "report-ledger-tornTail"}


def test_E2_an_interior_corrupt_ledger_is_refused(world):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    path = ll.ledger_path(repo)["path"]
    with open(path, "ab") as fh:
        fh.write(b"not json\n")
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": False, "reason": "report-ledger-interiorCorrupt"}


def test_E3_a_ledger_the_fold_refuses_is_refused(world):
    repo, _store = world
    with open(ll.ledger_path(repo)["path"], "ab") as fh:
        fh.write((json.dumps({"event": "started", "launchId": "ghost", "ts": 1.0,
                              "schema": ll.SCHEMA, "attempt": 1, "pid": 999999, "logPath": "l",
                              "errPath": "e"}) + "\n").encode("utf-8"))
    got = launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles)
    assert got == {"ok": False, "reason": "report-ledger-fold:fold-orphan-event:ghost"}


def test_E4_a_batch_with_no_launches_is_an_ok_empty_report(world):
    repo, _store = world
    for batch in (BATCH, "never-seen"):
        assert launcher.launch_report_for_batch(repo, batch, title_fn=_titles) == {
            "ok": True, "report": None, "still": {"action": "unchanged", "reason": None},
            "lanes": 0}


# ---------------------------------------------------------------- titles


@pytest.mark.parametrize("title_fn", [
    lambda repo_root, issue: (_ for _ in ()).throw(RuntimeError("gh is down")),
    lambda repo_root, issue: "",
    lambda repo_root, issue: None,
    lambda repo_root, issue: 415,
], ids=["raises", "empty", "none", "not-a-string"])
def test_E9_a_missing_title_gives_the_bare_issue_label(world, title_fn):
    repo, _store = world
    _launch(repo, "a", 415, "cloud")
    got = launcher.launch_report_for_batch(repo, BATCH, title_fn=title_fn)
    assert got["report"] == "Launched 1 build.\nIn the cloud: #415."


@pytest.mark.parametrize("failure", [FileNotFoundError("gh"), subprocess.TimeoutExpired("gh", 15)],
                         ids=["gh-absent", "gh-times-out"])
def test_E10_issue_title_never_raises_when_gh_is_absent_or_slow(monkeypatch, failure):
    def boom(*a, **k):
        raise failure

    monkeypatch.setattr(subprocess, "run", boom)
    assert launcher._issue_title("/nowhere", 415) is None


def test_issue_title_reads_gh_stdout_and_refuses_a_failed_call(monkeypatch):
    seen = []

    def run(argv, **kw):
        seen.append((argv, kw))
        return subprocess.CompletedProcess(argv, run.rc, run.out, "")

    monkeypatch.setattr(subprocess, "run", run)
    run.rc, run.out = 0, "Cloud C5b — the launch report and the still line\n"
    assert launcher._issue_title("/repo", 1775) == "Cloud C5b — the launch report and the still line"
    assert seen[0][0] == ["gh", "api", "repos/{owner}/{repo}/issues/1775", "--jq", ".title"]
    assert seen[0][1] == {"cwd": "/repo", "capture_output": True, "text": True, "timeout": 15}
    run.rc, run.out = 1, ""
    assert launcher._issue_title("/repo", 1775) is None
    run.rc, run.out = 0, "\n"
    assert launcher._issue_title("/repo", 1775) is None


def test_the_default_title_reader_is_issue_title(world, monkeypatch):
    repo, _store = world
    _launch(repo, "a", 415, "cloud")
    monkeypatch.setattr(launcher, "_issue_title", lambda repo_root, issue: "Phone checkout layout")
    assert launcher.launch_report_for_batch(repo, BATCH)["report"] == (
        "Launched 1 build.\nIn the cloud: #415 Phone checkout layout.")


# ---------------------------------------------------------------- the still state follows the report


def test_E11_a_cloud_build_beside_a_local_not_ready_fallback_clears_the_still_state(world):
    repo, store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    got = _report(repo)
    assert got["still"] == {"action": "written", "reason": "no-setup"}
    assert _stored(repo, store)["reason"] == "no-setup"
    _launch(repo, "b", 22, "cloud")
    got = _report(repo)
    assert got["still"] == {"action": "cleared", "reason": None}
    assert _stored(repo, store) is None


def test_a_finished_cloud_build_before_a_local_fallback_does_not_hide_the_fallback(world):
    repo, store = world
    _launch(repo, "a", 11, "cloud")
    _finish(repo, "a")
    _launch(repo, "b", 22, "local", _call(reason="unreachable"))
    assert _report(repo)["still"] == {"action": "written", "reason": "unreachable"}
    assert _stored(repo, store)["reason"] == "unreachable"


def test_an_earlier_cloud_launch_of_a_retried_issue_still_clears_the_old_reminder(world):
    repo, store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    assert _report(repo)["still"] == {"action": "written", "reason": "no-setup"}
    _launch(repo, "b", 22, "cloud")
    _finish(repo, "b")
    _launch(repo, "c", 22, "local", _call(reason=None, pointed=False))
    assert _report(repo)["still"] == {"action": "cleared", "reason": None}
    assert _stored(repo, store) is None


def test_replaying_an_older_batch_report_does_not_undo_a_newer_batchs_reminder(world):
    repo, store = world
    assert _declare(repo, "b-newer", 4)["ok"]
    _launch(repo, "a", 11, "cloud")
    _finish(repo, "a")
    _reserve(repo, "b", 22, "local", {"placeCall": _call(reason="unreachable")}, batch="b-newer")
    _start(repo, "b")
    newer = launcher.launch_report_for_batch(repo, "b-newer", title_fn=_titles)
    assert newer["still"] == {"action": "written", "reason": "unreachable"}
    assert _report(repo)["still"] == {"action": "unchanged", "reason": None}
    assert _stored(repo, store)["reason"] == "unreachable"


def test_replaying_the_same_batch_report_keeps_the_day_it_first_observed(world, monkeypatch):
    repo, store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    first = _report(repo)
    assert first["still"] == {"action": "written", "reason": "no-setup"}
    observed = _stored(repo, store)["observedOn"]
    monkeypatch.setattr(LR, "_today", lambda given: given or LR.datetime.date(2001, 1, 1))
    assert _report(repo)["still"] == {"action": "written", "reason": "no-setup"}
    assert _stored(repo, store)["observedOn"] == observed


def test_an_unconfirmed_cloud_session_is_not_reported_and_leaves_the_still_state(world):
    repo, store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    assert _report(repo)["still"] == {"action": "written", "reason": "no-setup"}
    _reserve(repo, "b", 22, "cloud", {"placeCall": _call("cloud", reason=None)})
    rec = _started("b")
    rec.update(cloudSessionName="lane-b", cloudSessionUnconfirmed=True)
    assert ll.append_under_lock(repo, rec)["ok"]
    _folds(repo)
    got = _report(repo)
    assert got["lanes"] == 1
    assert "#22" not in got["report"] and "In the cloud" not in got["report"]
    assert got["still"] == {"action": "written", "reason": "no-setup"}
    assert _stored(repo, store)["reason"] == "no-setup"


# ---------------------------------------------------------------- the CLI


def test_cli_report_prints_the_json_and_exits_zero(world, monkeypatch, capsys):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    monkeypatch.setattr(launcher, "_issue_title", lambda repo_root, issue: "Phone checkout layout")
    assert launcher.main(["report", "--repo-root", repo, "--batch", BATCH]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["lanes"] == 1
    assert out["report"] == "Launched 1 build.\nIn the cloud: #11 Phone checkout layout."


def test_cli_report_on_a_refused_ledger_exits_one(world, capsys):
    repo, _store = world
    with open(ll.ledger_path(repo)["path"], "ab") as fh:
        fh.write(b"not json\n")
    assert launcher.main(["report", "--repo-root", repo, "--batch", BATCH]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False, "reason": "report-ledger-interiorCorrupt"}


def test_cli_still_prints_the_line_or_null_and_exits_zero(world, monkeypatch, capsys):
    repo, _store = world
    assert launcher.main(["still", "--repo-root", repo]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "line": None}
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    assert _report(repo)["still"]["action"] == "written"
    monkeypatch.setattr(LR.cloud_ready, "readiness", lambda *a, **k: {
        "ready": False, "setting": True, "conditions": {"setup": False}, "checkedAt": None})
    assert launcher.main(["still", "--repo-root", repo]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["line"].startswith("Still on your machine\n")


def test_cli_still_names_a_state_file_it_cannot_read_and_keeps_it(world, monkeypatch, capsys):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    assert _report(repo)["still"]["action"] == "written"
    path = LR._still_path(repo, None)
    real_open = open

    def deny(file, *args, **kwargs):
        if str(file) == path:
            raise PermissionError("not readable")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", deny)
    assert launcher.main(["still", "--repo-root", repo]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": LR.STILL_UNREADABLE}
    monkeypatch.undo()
    assert os.path.exists(path)
