# plugins/superheroes/lib/tests/test_launch_report_verbs.py
"""Conformance: the launcher's `report` and `still` verbs. Every ledger, store and repository is built
under tmp_path; `_issue_title` is never run for real (tests pass `title_fn`, or patch `subprocess.run`),
and readiness is always injected, never read from a real home directory."""
import datetime
import functools
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_ready as CR  # noqa: E402
import cloud_setup as CS  # noqa: E402
import control_plane  # noqa: E402
import core_md as CM  # noqa: E402
import launch_ledger as ll  # noqa: E402
import launch_place as LP  # noqa: E402
import launch_report as LR  # noqa: E402
import launcher  # noqa: E402
import mode_registry  # noqa: E402
import project_config as PC  # noqa: E402

from test_launch_ledger import (  # noqa: E402
    _declare,
    _init_repo,
    _ledger_env,
    _reserved,
    _started,
)
from test_launch_report import (  # noqa: E402
    _CORE_FACTS,
    ACCOUNT,
    ADVISOR,
    FUTURE,
    PAST,
    SETUP_TEXT_FIX,
    STAMP,
    _account_env,
    _now,
    _put,
    _record,
    _route,
)

import test_cloud_check as TCC  # noqa: E402

BATCH = "b-report"
PHONE = "the phone simulator"
DAY = datetime.date(2026, 10, 11)


def _ts(day):
    """Noon UTC on that day, as the ledger writes its times."""
    return datetime.datetime(day.year, day.month, day.day, 12, tzinfo=datetime.timezone.utc).timestamp()


def _call(place="local", pointed=True, reason=None, by="setting", need=None, cloud=None,
          advisor=None, reported=None):
    return {"place": place, "pointedAtCloud": pointed, "by": by, "reason": reason, "need": need,
            "cloudVersion": cloud, "advisorVersion": advisor, "environment": None,
            "reported": reported}


def _titles(repo_root, issue):
    return "Title %s" % issue


def _fn(**kw):
    """An injected readiness reader. It takes the keyword `persist_backfill` (and any other) the real
    reader takes, and ignores it."""
    def readiness(cwd, reported=None, root=None, env=None, **kwargs):
        return _now(**kw)
    return readiness


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A repository, a ledger root and a project store root, all under tmp_path."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    store = str(tmp_path / "store")
    monkeypatch.setattr(control_plane, "store_root", lambda: store)
    assert _declare(repo, BATCH, 4)["ok"]
    return repo, store


# Unmeasured — verify before use: the reserved/started record shapes below follow
# test_launch_ledger_cloud.py; every writer here is checked by `ll.fold` accepting the result.
def _reserve(repo, launch_id, issue, place="local", premise=None, batch=BATCH, ts=None):
    fields = {"issue": issue}
    if ts is not None:
        fields["ts"] = ts
    if place == "cloud":
        fields.update(place="cloud", cloudEnvironment="env_abc", pluginVersion="1.2.3")
    if premise is not None:
        fields["premise"] = premise
    result = ll.reserve(repo, _reserved(launch_id, batch, ["x"], repo, **fields))
    assert result["ok"], result


def _start(repo, launch_id, place="local", ts=None):
    rec = _started(launch_id)
    if ts is not None:
        rec["ts"] = ts
    if place == "cloud":
        rec["cloudSessionName"] = "lane-%s" % launch_id
        rec["cloudSessionId"] = "session_01AbCdEf123"
    assert ll.append_under_lock(repo, rec)["ok"]


def _refuse(repo, launch_id):
    assert ll.terminalize(repo, launch_id, reason="engine-auth", stage="preflight")["ok"]


def _finish(repo, launch_id):
    assert ll.terminalize(repo, launch_id, child_ever_spawned=True, outcome="park",
                          evidence="x")["ok"]


def _launch(repo, launch_id, issue, place="local", call="auto", ts=None):
    if call == "auto":
        call = _call(place, pointed=True, reason=None if place == "cloud" else "no-setup")
    premise = None if call is None else {"placeCall": call}
    _reserve(repo, launch_id, issue, place, premise, ts=ts)
    _start(repo, launch_id, place, ts=ts)


def _report(repo, **kw):
    return launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles, **kw)


def _folds(repo):
    assert ll.fold(ll.read(repo)["records"])["ok"]


def _snapshot(*roots):
    """Every folder and file under these roots, with each file's bytes."""
    seen = {}
    for root in roots:
        for dirpath, dirs, files in os.walk(root):
            for name in dirs:
                seen[os.path.join(dirpath, name)] = None
            for name in files:
                with open(os.path.join(dirpath, name), "rb") as fh:
                    seen[os.path.join(dirpath, name)] = fh.read()
    return seen


def _real_world(tmp_path, monkeypatch, **over):
    """A repository whose cloud is set up and switched on, with the real readiness reader's inputs."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    store = str(tmp_path / "store")
    assert _declare(repo, BATCH, 4)["ok"]
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    _record(repo, store, **over)
    assert PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)["action"] == "written"
    return repo, store, _account_env(tmp_path)


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
    repo, _store = world
    _reserve(repo, "r", 33, premise={"placeCall": _call()})
    _refuse(repo, "r")
    _folds(repo)
    assert _report(repo) == {"ok": True, "report": None, "lanes": 0}


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
    repo, _store = world
    _reserve(repo, "a", 11, premise=premise)
    _start(repo, "a")
    _reserve(repo, "b", 22, "cloud", premise)
    _start(repo, "b", "cloud")
    _folds(repo)
    got = _report(repo)
    # The local lane is synthesized pointed at nothing and the cloud lane as a cloud build: neither
    # carries a reason, so the report names none.
    assert got["lanes"] == 2
    assert got["report"] == ("Launched 2 builds.\nIn the cloud: #22 Title 22.\nOn your machine:\n"
                             "- #11 Title 11.")


def test_I2_a_synthesized_local_call_alone_prints_no_report(world):
    repo, _store = world
    _reserve(repo, "a", 11, premise={})
    _start(repo, "a")
    got = _report(repo)
    assert got == {"ok": True, "report": None, "lanes": 1}


# ---------------------------------------------------------------- the ledger edges


def test_E1_a_missing_ledger_is_an_ok_empty_report(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": True, "report": None, "lanes": 0}


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
            "ok": True, "report": None, "lanes": 0}


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


# ---------------------------------------------------------------- the report has no stored state


def test_B11_the_report_result_has_no_still_key(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _launch(repo, "b", 22, "cloud")
    got = _report(repo)
    assert set(got) == {"ok", "report", "lanes"}
    assert got["lanes"] == 2


def test_B10_one_store_report_and_still_write_nothing(world):
    # axis: report and still write nothing under the store, the repository or the ledger root — see bite-proof record c8a_wo3.md
    repo, _store = world
    ledger_root = os.environ[ll.LEDGER_ROOT_ENV]
    state = os.path.join(mode_registry.project_store_dir(repo, None), "state")
    os.makedirs(state)
    with open(os.path.join(state, "stale-reminder.json"), "wb") as fh:
        fh.write(b"left behind by an older build")
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _launch(repo, "b", 22, "local", _call(reason="unreachable"))
    before = _snapshot(mode_registry.project_store_dir(repo, None), repo, ledger_root)
    assert _report(repo)["report"] is not None
    got = LR.still_check(repo, readiness_fn=_fn(ready=False, reason="no-setup"))
    assert got["line"].startswith("Still on your machine\n") and got["refused"] is None
    assert _snapshot(mode_registry.project_store_dir(repo, None), repo, ledger_root) == before


# ---------------------------------------------------------------- the line comes from the ledger


def _line(repo, **kw):
    return LR.still_line(repo, readiness_fn=_fn(**kw))


def _day_launch(repo, launch_id, issue, day, call):
    """A launch that started on `day` and was reserved the day before, so a day read from the
    reservation is not the start day."""
    premise = None if call is None else {"placeCall": call}
    _reserve(repo, launch_id, issue, "local", premise, ts=_ts(day - datetime.timedelta(days=1)))
    _start(repo, launch_id, "local", ts=_ts(day))
    info = ll.fold(ll.read(repo)["records"])["launches"][launch_id]
    assert LR.launch_day(info) == day


def test_B1_no_deciding_launch_means_no_line_and_readiness_is_not_read(world):
    repo, _store = world
    asked = []

    def readiness(cwd, reported=None, root=None, env=None, **kwargs):
        asked.append(cwd)
        return _now()

    assert LR.still_check(repo, readiness_fn=readiness) == {"line": None, "refused": None}
    _launch(repo, "a", 11, "local", _call(pointed=False, reason=None))
    _launch(repo, "b", 22, "local", _call(reason="local-word"))
    _launch(repo, "c", 33, "local", _call(reason="needs", need=PHONE))
    _launch(repo, "d", 44, "local", None)
    _reserve(repo, "r", 55, premise={"placeCall": _call(reason="no-setup")})
    _refuse(repo, "r")
    _reserve(repo, "n", 66, premise={"placeCall": _call(reason="no-setup")})
    assert LR.still_check(repo, readiness_fn=readiness) == {"line": None, "refused": None}
    assert asked == []


def test_B1_readiness_is_read_once_however_many_fallbacks_stand(world):
    repo, _store = world
    asked = []

    def readiness(cwd, reported=None, root=None, env=None, **kwargs):
        asked.append(cwd)
        return _now(ready=False, reason="no-setup")

    for index, reason in enumerate(("no-setup", "unreachable", "version")):
        _launch(repo, "l%d" % index, 10 + index, "local", _call(reason=reason))
    assert LR.still_line(repo, readiness_fn=readiness) is not None
    assert len(asked) == 1


def test_R_board_the_still_line_is_byte_exact(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="version", cloud="0.41.0", advisor="0.42.0"))
    assert _line(repo, ready=False, reason="version") == (
        "Still on your machine\n"
        "The cloud's plugin is 0.41.0 and mine is 0.42.0. Paste the new setup text to fix it.")


@pytest.mark.parametrize("code", LP.NOT_READY_CODES)
def test_R_eight_every_still_line_is_drawn_from_the_table(world, code):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason=code, cloud="0.41.0", advisor="0.42.0"))
    parts = {key: (None if text is None else LP._fill(text, "0.41.0", "0.42.0"))
             for key, text in LP.REASONS[code].items()}
    assert _line(repo, ready=False, reason=code) == (
        "Still on your machine\n%s %s" % (parts["words"], parts["short"]))


def test_B3_a_confirmed_cloud_launch_after_a_fallback_clears_the_line(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    assert _line(repo, ready=False, reason="no-setup") is not None
    _launch(repo, "b", 22, "cloud")
    assert _line(repo, ready=False, reason="no-setup") is None


def test_B3_an_unconfirmed_cloud_launch_after_a_fallback_leaves_the_line(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _reserve(repo, "b", 22, "cloud", {"placeCall": _call("cloud", reason=None)})
    rec = _started("b")
    rec.update(cloudSessionName="lane-b", cloudSessionUnconfirmed=True)
    assert ll.append_under_lock(repo, rec)["ok"]
    _folds(repo)
    got = _report(repo)
    assert got["lanes"] == 1 and "#22" not in got["report"]
    assert _line(repo, ready=False, reason="no-setup").startswith("Still on your machine\nThis project")


def test_B3_a_fallback_after_a_cloud_launch_shows_its_line(world):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    _finish(repo, "a")
    _launch(repo, "b", 22, "local", _call(reason="unreachable"))
    assert _line(repo, ready=False, reason="unreachable").startswith("Still on your machine\n")


def test_B3_only_the_fallbacks_after_the_last_cloud_launch_count(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _launch(repo, "b", 22, "cloud")
    _launch(repo, "c", 33, "local", _call(reason="unreachable"))
    line = _line(repo, ready=False, reason="no-setup")
    assert "couldn't be reached" in line and "no cloud setup" not in line


def test_an_earlier_cloud_launch_of_a_retried_issue_still_clears_the_old_line(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _launch(repo, "b", 22, "cloud")
    _finish(repo, "b")
    _launch(repo, "c", 22, "local", _call(reason=None, pointed=False))
    assert _line(repo, ready=False, reason="no-setup") is None


def test_overlapping_launches_are_ordered_by_when_they_started_not_when_they_reserved(world):
    repo, _store = world
    premise = {"placeCall": _call(reason="unreachable")}
    # the local fallback reserves first, the cloud lane reserves second and runs to the end, and
    # only then does the fallback spawn: the fallback is the newer launch and its line stands
    result = ll.reserve(repo, _reserved("a", BATCH, ["x"], repo, issue=22, premise=premise))
    assert result["ok"], result
    result = ll.reserve(repo, _reserved(
        "b", BATCH, ["y"], repo, issue=11, place="cloud", cloudEnvironment="env_abc",
        pluginVersion="1.2.3", premise={"placeCall": _call("cloud", reason=None)}))
    assert result["ok"], result
    _start(repo, "b", "cloud")
    _finish(repo, "b")
    _start(repo, "a")
    _folds(repo)
    assert _line(repo, ready=False, reason="unreachable").startswith("Still on your machine\n")


def test_the_line_is_the_same_whichever_batch_a_fallback_launched_in(world):
    repo, _store = world
    assert _declare(repo, "b-newer", 4)["ok"]
    _launch(repo, "a", 11, "cloud")
    _reserve(repo, "b", 22, "local", {"placeCall": _call(reason="unreachable")}, batch="b-newer")
    _start(repo, "b")
    _launch(repo, "c", 33, "local", _call(reason="no-setup"))
    for batch in (BATCH, "b-newer"):
        assert launcher.launch_report_for_batch(repo, batch, title_fn=_titles)["ok"] is True
    assert "no cloud setup" in _line(repo, ready=False, reason="no-setup")


# ---------------------------------------------------------------- the clearing legs


def test_B4_a_setting_directed_fallback_clears_once_the_setting_reads_off(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="unreachable", by="setting"))
    assert _line(repo, ready=False, reason="unreachable", setting=True) is not None
    assert _line(repo, ready=False, reason="unreachable", setting=False) is None


def test_B4_a_setting_directed_fallback_stays_when_the_setting_is_unreadable(world, monkeypatch):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup", by="setting"))

    def unreadable(*args, **kwargs):
        raise OSError("config unreadable")

    monkeypatch.setattr(PC, "get_item", unreadable)
    assert _line(repo, ready=False, reason="no-setup", setting=False) is not None


@pytest.mark.parametrize("damage", ["corrupt", "directory"])
def test_B4_a_profile_the_reader_could_not_read_does_not_clear_the_line(world, damage):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup", by="setting"))
    path = CM.core_path(repo, None)
    if damage == "corrupt":
        _put(path, "not a profile\n")
    else:
        os.makedirs(path)
    assert PC.get_item(repo, PC.CLOUD_BUILDS_SLUG, root=None)["effective"] is False
    assert _line(repo, ready=False, reason="no-setup", setting=False) is not None


@pytest.mark.parametrize("damaged", ["[]", '"off"', "3"])
def test_B4_a_wrongly_typed_configuration_does_not_clear_the_line(world, damaged):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup", by="setting"))
    _put(CM.core_path(repo, None), (
        '```json superheroes-core\n{"schemaVersion": 1, "verifyCommand": null, "stackTags": [], '
        '"enginePreferences": {}, "projectConfiguration": %s}\n```\n' % damaged))
    assert PC.get_item(repo, PC.CLOUD_BUILDS_SLUG, root=None)["effective"] is False
    assert _line(repo, ready=False, reason="no-setup", setting=False) is not None


def test_B4_a_word_directed_fallback_stays_when_the_setting_is_off(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="unreachable", by="word"))
    assert _line(repo, ready=False, reason="unreachable", setting=False) is not None


@pytest.mark.parametrize("code,condition", [("no-setup", "setup"), ("pass-lapsed", "passLive"),
                                            ("calibration", "calibration"), ("version", "version")])
def test_B5_a_condition_this_machine_can_read_clears_the_line_once_it_holds(world, code, condition):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason=code, cloud="1.0.0", advisor="2.0.0"))
    stands = _now(ready=False, reason=code)
    assert stands["conditions"][condition] is False
    assert LR.still_line(repo, readiness_fn=lambda *a, **k: stands) is not None
    other = {name: (name != condition) for name in CR.CONDITION_ORDER}
    assert _line(repo, ready=False, reason=code, conditions=other) is not None
    fixed = dict(stands, conditions=dict(stands["conditions"], **{condition: True}))
    assert LR.still_line(repo, readiness_fn=lambda *a, **k: fixed) is None


@pytest.mark.parametrize("code,reported", [
    ("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
    ("version", {"pluginVersion": "0.41.0"}),
])
def test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready(
        world, code, reported):
    repo, _store = world
    _day_launch(repo, "a", 11, DAY, _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                                          reported=reported))
    ready = _now(ready=True)
    for checked in (None, "garbage", "2026-10-10", "2026-10-11"):
        assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(ready, checkedAt=checked)
                             ) is not None, (code, checked)
    after = "2026-10-12"
    assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(ready, checkedAt=after)) is None
    not_ready = _now(ready=False, reason=code, checked=after)
    assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(not_ready)) is not None


def test_E4_a_fallback_with_no_start_time_is_never_fixed_by_a_later_check(world):
    repo, _store = world
    # a timestamp no calendar holds: the ledger takes it, and the launch has no start day
    _launch(repo, "a", 11, "local", _call(reason="no-pass", reported={"noPass": True}), ts=1e30)
    assert LR.launch_day(ll.fold(ll.read(repo)["records"])["launches"]["a"]) is None
    for checked in ("2026-10-12", "2099-01-01"):
        assert LR.still_line(repo, readiness_fn=_fn(ready=True, checked=checked)) is not None


def test_B6_a_report_then_a_same_day_passed_check_leaves_the_line_standing(tmp_path, monkeypatch):
    repo, store, env = _real_world(tmp_path, monkeypatch, checked_at=DAY.isoformat())
    call = _route(repo, store, env, premise={"reportedCloud": {"noPass": True}})
    assert call["reason"] == "no-pass"
    _day_launch(repo, "a", 11, DAY, call)
    real = functools.partial(CR.readiness, advisor_version=ADVISOR, today=DAY,
                             stamp_fn=lambda cwd, root: STAMP, env=env)
    assert LR.still_line(repo, root=store, readiness_fn=real) == (
        "Still on your machine\nThere is no reviewer pass in the cloud environment. "
        'Paste a pass into the environment and say "check again" to fix it.')
    _record(repo, store, checked_at="2026-10-12")
    assert LR.still_line(repo, root=store, readiness_fn=real) is None


def test_B5_a_lapsed_pass_is_fixed_by_a_fresh_one_with_real_readiness(tmp_path, monkeypatch):
    repo, store, env = _real_world(tmp_path, monkeypatch, pass_lapses=PAST)
    call = _route(repo, store, env)
    assert call["reason"] == "pass-lapsed"
    _day_launch(repo, "a", 11, DAY, call)
    real = functools.partial(CR.readiness, advisor_version=ADVISOR, today=DAY,
                             stamp_fn=lambda cwd, root: STAMP, env=env)
    assert LR.still_line(repo, root=store, readiness_fn=real) == (
        'Still on your machine\nThe reviewer pass has lapsed. Paste a fresh pass and say '
        '"check again" to fix it.')
    assert CS.confirm_pass(repo, ACCOUNT, FUTURE, root=store)["action"] == "written"
    assert LR.still_line(repo, root=store, readiness_fn=real) is None


# ---------------------------------------------------------------- which fallback shows


def test_B7_two_unfixed_fallbacks_show_the_higher_ranked_reason(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="unreachable"))
    _launch(repo, "b", 22, "local", _call(reason="no-setup"))
    line = _line(repo, ready=False, reason="no-setup")
    assert line.startswith("Still on your machine\nThis project has no cloud setup")


def test_B7_a_higher_ranked_fallback_that_is_fixed_is_skipped(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _launch(repo, "b", 22, "local", _call(reason="version", cloud="0.41.0", advisor="0.42.0"))
    got = _line(repo, ready=False, reason="version")
    assert got == ("Still on your machine\n"
                   "The cloud's plugin is 0.41.0 and mine is 0.42.0. Paste the new setup text to fix it.")


def test_B7_every_fallback_fixed_means_no_line(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _launch(repo, "b", 22, "local", _call(reason="version", cloud="0.41.0", advisor="0.42.0"))
    assert _line(repo, ready=True) is None


def test_B8_a_failed_check_fallback_carries_the_recheck_step(world):
    repo, _store = world
    recheck = SETUP_TEXT_FIX + ' Then say "check again".'
    _launch(repo, "a", 11, "local", dict(_call(reason="calibration"), failedCheck=["calibration"]))
    assert _line(repo, ready=False, reason="calibration").endswith(recheck)


@pytest.mark.parametrize("failed_first", [True, False])
def test_B8_E6_of_two_fallbacks_with_one_reason_the_failed_check_one_shows(world, failed_first):
    repo, _store = world
    plain = _call(reason="calibration")
    failed = dict(_call(reason="calibration", by="word"), failedCheck=["calibration"])
    for index, call in enumerate([failed, plain] if failed_first else [plain, failed]):
        _launch(repo, "l%d" % index, 10 + index, "local", call)
    assert _line(repo, ready=False, reason="calibration").endswith(
        SETUP_TEXT_FIX + ' Then say "check again".')


def test_E6_of_two_fallbacks_with_one_reason_the_latest_started_shows(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="version", cloud="0.40.0", advisor="0.42.0"))
    _launch(repo, "b", 22, "local", _call(reason="version", cloud="0.41.0", advisor="0.42.0"))
    assert "The cloud's plugin is 0.41.0 and mine is 0.42.0." in _line(repo, ready=False, reason="version")


def test_E6_a_word_directed_fallback_beside_a_setting_directed_one_stays_when_the_setting_is_off(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="calibration", by="setting"))
    _launch(repo, "b", 22, "local", _call(reason="calibration", by="word"))
    assert _line(repo, ready=False, reason="calibration", setting=False) is not None


def test_E6_a_reported_version_beside_a_setup_record_fallback_still_needs_a_later_check(world):
    repo, _store = world
    _day_launch(repo, "a", 11, DAY, _call(reason="version", cloud="0.41.0", advisor="0.42.0"))
    _day_launch(repo, "b", 22, DAY, _call(reason="version", cloud="0.41.0", advisor="0.42.0",
                                          reported={"pluginVersion": "0.41.0"}))
    same_day = _now(ready=True, checked=DAY.isoformat())
    assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(same_day)) is not None
    later = _now(ready=True, checked="2026-10-12")
    assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(later)) is None


def test_the_line_for_an_unreproduced_version_uses_the_launchs_own_versions(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="version", cloud=None, advisor="0.42.0"))
    assert _line(repo, ready=False, reason="version", cloud="9.9.9", advisor="8.8.8") == (
        "Still on your machine\nThe cloud's plugin is unknown and mine is 0.42.0. "
        "Paste the new setup text to fix it.")


def _judged_world(tmp_path, monkeypatch, passed_first):
    """A real project the real check ran on, with a ledger beside it and cloud builds switched on:
    (local, cloud, a readiness reader that works as the line's own does)."""
    local, cloud = TCC._pair(tmp_path)
    _ledger_env(tmp_path, monkeypatch)
    assert _declare(local.cwd, BATCH, 4)["ok"]
    if passed_first:
        assert TCC._judge(local, TCC._ok_report(cloud))["action"] == "passed"
    TCC._turn_on(local)
    env = TCC._account_env(local, TCC.ACCOUNT)
    ready = functools.partial(CR.readiness, advisor_version=TCC.VERSION, today=TCC.CHECK_DAY,
                              stamp_fn=lambda cwd, root: local.stamp, env=env)
    return local, cloud, env, ready


def _reviewer_fails(cloud):
    return TCC._cloud_report(cloud, confirmation=TCC._confirm(answered=False)(None))


def test_T8_a_same_day_passing_check_clears_the_still_line_after_a_reviewer_failure(
        tmp_path, monkeypatch):
    local, cloud, env, ready = _judged_world(tmp_path, monkeypatch, passed_first=True)
    assert TCC._judge(local, _reviewer_fails(cloud))["action"] == "failed"
    call = TCC._place(local, env)
    assert call["place"] == "local" and call["reason"] == "no-pass"
    assert call["failedCheck"] == ["reviewer"]
    # the launch started on the same UTC day the passing check below runs on
    _day_launch(local.cwd, "a", 11, TCC.CHECK_DAY, call)
    standing = LR.still_line(local.cwd, root=local.root, readiness_fn=ready)
    assert standing.startswith("Still on your machine\n") and 'say "check again"' in standing
    # a check that failed again leaves the marker, so the line stands
    assert TCC._judge(local, _reviewer_fails(cloud), now=TCC.LATER)["action"] == "failed"
    assert LR.still_line(local.cwd, root=local.root, readiness_fn=ready) == standing
    # axis: a fallback that came from a failed check is fixed once a passing check has cleared the marker and its condition reads true now, on the same day too
    passed = TCC._judge(local, TCC._ok_report(cloud), now=TCC.LATER + 60)
    assert passed["action"] == "passed" and passed["markerWritten"] is False
    assert LR.still_line(local.cwd, root=local.root, readiness_fn=ready) is None


def test_T8_an_account_whose_first_check_failed_reads_paused_and_clears_on_a_same_day_pass(
        tmp_path, monkeypatch):
    local, cloud, env, ready = _judged_world(tmp_path, monkeypatch, passed_first=False)
    assert TCC._judge(local, _reviewer_fails(cloud))["action"] == "failed"
    call = TCC._place(local, env)
    assert call["reason"] == "no-setup" and call["failedCheck"] == ["reviewer"]
    _day_launch(local.cwd, "a", 11, TCC.CHECK_DAY, call)
    assert LR.still_line(local.cwd, root=local.root, readiness_fn=ready) == (
        "Still on your machine\nThis account's last setup check failed on the reviewer pass. "
        'To fix it, paste a fresh pass into the environment, then say "check again".')
    assert TCC._judge(local, TCC._ok_report(cloud), now=TCC.LATER)["action"] == "passed"
    assert LR.still_line(local.cwd, root=local.root, readiness_fn=ready) is None


def test_E5_a_readiness_that_raises_leaves_the_line_standing(world):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))

    def boom(*args, **kwargs):
        raise RuntimeError("readiness exploded")

    assert LR.still_line(repo, readiness_fn=boom).startswith(
        "Still on your machine\nThis project has no cloud setup")


# ---------------------------------------------------------------- the ledger edges


def test_E1_an_empty_ledger_gives_no_line(world):
    repo, _store = world
    open(ll.ledger_path(repo)["path"], "wb").close()
    assert LR.still_check(repo, readiness_fn=_fn()) == {"line": None, "refused": None}


def test_E2_a_missing_ledger_gives_no_line(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert ll.read(repo)["state"] == "missing"
    assert LR.still_check(repo, readiness_fn=_fn()) == {"line": None, "refused": None}


def _spoil(repo, how):
    path = ll.ledger_path(repo)["path"]
    with open(path, "ab") as fh:
        if how == "torn":
            fh.write(b'{"event": "reserved", "launchId"')
        elif how == "corrupt":
            fh.write(b"not json\n")
        else:
            fh.write((json.dumps({"event": "started", "launchId": "ghost", "ts": 1.0,
                                  "schema": ll.SCHEMA, "attempt": 1, "pid": 999999, "logPath": "l",
                                  "errPath": "e"}) + "\n").encode("utf-8"))


@pytest.mark.parametrize("how", ["torn", "corrupt", "fold"])
def test_B9_E3_an_unreadable_ledger_gives_the_refusal(world, how):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _spoil(repo, how)
    assert LR.still_check(repo, readiness_fn=_fn(ready=False, reason="no-setup")) == {
        "line": None, "refused": "still-ledger-unreadable"}
    assert LR.still_line(repo, readiness_fn=_fn(ready=False, reason="no-setup")) is None


def test_still_check_never_raises_without_a_repository(tmp_path, monkeypatch):
    _ledger_env(tmp_path, monkeypatch)
    plain = str(tmp_path / "not-a-repository")
    os.mkdir(plain)
    assert LR.still_line(plain, readiness_fn=_fn()) is None


@pytest.mark.parametrize("error", [
    FileNotFoundError("No usable temporary directory found"),
    RecursionError("maximum recursion depth exceeded"),
    RuntimeError("ledger reader exploded"),
])
def test_B9_a_ledger_reader_that_raises_gives_the_refusal(world, monkeypatch, error):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))

    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr(ll, "read", boom)
    assert LR.still_check(repo, readiness_fn=_fn(ready=False, reason="no-setup")) == {
        "line": None, "refused": "still-ledger-unreadable"}
    assert LR.still_line(repo, readiness_fn=_fn(ready=False, reason="no-setup")) is None


# ---------------------------------------------------------------- the CLI


def test_cli_report_prints_the_json_and_exits_zero(world, monkeypatch, capsys):
    repo, _store = world
    _launch(repo, "a", 11, "cloud")
    monkeypatch.setattr(launcher, "_issue_title", lambda repo_root, issue: "Phone checkout layout")
    assert launcher.main(["report", "--repo-root", repo, "--batch", BATCH]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "report": "Launched 1 build.\nIn the cloud: #11 Phone checkout layout.",
                   "lanes": 1}


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
    monkeypatch.setattr(CR, "readiness", lambda *a, **k: {
        "ready": False, "setting": True, "conditions": {"setup": False}, "checkedAt": None})
    assert launcher.main(["still", "--repo-root", repo]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["line"].startswith("Still on your machine\n")


def test_cli_still_through_the_real_readiness_reader_reminds_clears_and_writes_nothing(
        tmp_path, monkeypatch, capsys):
    repo, store, env = _real_world(tmp_path, monkeypatch, pass_lapses=PAST)
    monkeypatch.setattr(control_plane, "store_root", lambda: store)
    monkeypatch.setenv("HOME", env["HOME"])
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    call = _route(repo, store, env)
    assert call["reason"] == "pass-lapsed"
    _day_launch(repo, "a", 11, DAY, call)
    # no registry yet: a read that resolved the mode with its default would write one
    assert mode_registry.read_registry(repo, store) is None
    before = _snapshot(mode_registry.project_store_dir(repo, None), repo, store)
    assert launcher.main(["still", "--repo-root", repo]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "line": (
        'Still on your machine\nThe reviewer pass has lapsed. Paste a fresh pass and say '
        '"check again" to fix it.')}
    assert _snapshot(mode_registry.project_store_dir(repo, None), repo, store) == before
    assert mode_registry.read_registry(repo, store) is None
    assert CS.confirm_pass(repo, ACCOUNT, "2099-01-01", root=store)["action"] == "written"
    repaired = _snapshot(mode_registry.project_store_dir(repo, None), repo, store)
    assert launcher.main(["still", "--repo-root", repo]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "line": None}
    assert _snapshot(mode_registry.project_store_dir(repo, None), repo, store) == repaired


def test_B9_cli_still_on_an_unreadable_ledger_refuses_and_exits_one(world, capsys):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))
    _spoil(repo, "corrupt")
    assert launcher.main(["still", "--repo-root", repo]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "still-ledger-unreadable"}


def test_B9_cli_still_on_a_ledger_reader_that_raises_refuses_and_exits_one(world, monkeypatch, capsys):
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(reason="no-setup"))

    def boom(*args, **kwargs):
        raise FileNotFoundError("No usable temporary directory found")

    monkeypatch.setattr(ll, "read", boom)
    assert launcher.main(["still", "--repo-root", repo]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "still-ledger-unreadable"}


# ---------------------------------------------------------------- a read writes nothing


def test_cli_still_with_hero_evidence_and_no_core_md_writes_no_mode_record(
        tmp_path, monkeypatch, capsys):
    # axis: the readiness read behind `still` never backfills the storage-mode record — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    store = str(tmp_path / "store")
    monkeypatch.setattr(control_plane, "store_root", lambda: store)
    monkeypatch.setenv("HOME", _account_env(tmp_path)["HOME"])
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    # a cloud session never writes calibration, which would hide a write this test looks for
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    assert _declare(repo, BATCH, 4)["ok"]
    # hero evidence (a review-crew layer in the repository), no core.md, no registry
    layer = os.path.join(repo, ".claude", "superheroes", "review-crew.md")
    os.makedirs(os.path.dirname(layer))
    with open(layer, "w", encoding="utf-8") as fh:
        fh.write("a calibrated hero\n")
    assert not os.path.exists(CM.core_path(repo, None, persist_backfill=False))
    assert mode_registry.read_registry(repo, store) is None
    # the world is one that a default read would write a record for
    assert mode_registry.resolve(repo, store, persist_backfill=False)["source"] == "evidence"
    assert mode_registry.read_registry(repo, store) is None
    _day_launch(repo, "a", 11, DAY, _call(reason="no-setup", by="setting"))
    before = _snapshot(mode_registry.project_store_dir(repo, None), repo, store, ledger_root)
    assert launcher.main(["still", "--repo-root", repo]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert mode_registry.read_registry(repo, store) is None
    assert _snapshot(mode_registry.project_store_dir(repo, None), repo, store, ledger_root) == before


# ---------------------------------------------------------------- a read makes no ledger directory


def _repo_dir(repo, root):
    return os.path.join(root, ll.repo_identity(repo))


def test_still_and_report_do_not_create_a_missing_ledger_root(tmp_path, monkeypatch):
    # axis: a read of a ledger whose root does not exist reports an empty ledger and makes nothing — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    missing = tmp_path / "no-such-ledger-root"
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(missing))
    assert LR.still_check(repo, readiness_fn=_fn()) == {"line": None, "refused": None}
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": True, "report": None, "lanes": 0}
    assert not missing.exists()
    assert ll.read(repo, create=False) == {"state": "missing", "records": []}
    assert not missing.exists()


def test_still_and_report_do_not_create_a_missing_repo_directory(tmp_path, monkeypatch):
    # axis: a read with the ledger root present and the repository directory absent makes no directory — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    assert LR.still_check(repo, readiness_fn=_fn()) == {"line": None, "refused": None}
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": True, "report": None, "lanes": 0}
    assert os.listdir(root) == []


def test_a_read_that_may_create_still_makes_the_directories(tmp_path, monkeypatch):
    # axis: the default read is unchanged — it makes the root and the repository directory, then reads an empty ledger — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    missing = tmp_path / "ledger-made-by-a-default-read"
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(missing))
    assert ll.read(repo) == {"state": "missing", "records": []}
    assert os.path.isdir(_repo_dir(repo, str(missing)))
    assert ll.read(repo, create=False) == {"state": "missing", "records": []}


def test_a_read_that_may_not_create_still_refuses_a_root_with_the_wrong_mode(tmp_path, monkeypatch):
    # axis: an existing ledger root that others can reach is still refused when the read may not create — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    os.chmod(root, 0o755)
    assert ll.read(repo, create=False) == {"state": "unreadable", "records": []}
    assert LR.still_check(repo, readiness_fn=_fn()) == {
        "line": None, "refused": LR.STILL_LEDGER_UNREADABLE}
    assert launcher.launch_report_for_batch(repo, BATCH, title_fn=_titles) == {
        "ok": False, "reason": "report-ledger-unreadable"}
    assert os.listdir(root) == []


def test_a_read_that_may_not_create_still_refuses_a_repo_directory_that_is_a_symlink(
        tmp_path, monkeypatch):
    # axis: an existing repository directory that is a symlink is still refused when the read may not create — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    os.symlink(str(elsewhere), _repo_dir(repo, root))
    assert ll.read(repo, create=False) == {"state": "unreadable", "records": []}
    assert LR.still_check(repo, readiness_fn=_fn()) == {
        "line": None, "refused": LR.STILL_LEDGER_UNREADABLE}


def test_a_read_that_may_not_create_still_refuses_a_repo_directory_with_the_wrong_mode(
        tmp_path, monkeypatch):
    # axis: an existing repository directory that others can reach is still refused when the read may not create — see bite-proof record c8a_wo3.md
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    os.mkdir(_repo_dir(repo, root), 0o755)
    os.chmod(_repo_dir(repo, root), 0o755)
    assert ll.read(repo, create=False) == {"state": "unreadable", "records": []}
    assert LR.still_check(repo, readiness_fn=_fn()) == {
        "line": None, "refused": LR.STILL_LEDGER_UNREADABLE}


# ---------------------------------------------------------------- the report looks up titles only for a report


def _counting_titles(asked):
    def lookup(repo_root, issue):
        asked.append(issue)
        return "Title %s" % issue
    return lookup


def test_a_batch_with_no_report_looks_up_no_titles(world):
    # axis: no title lookup for a batch whose place calls leave no report (cloud builds neither on nor used) — see bite-proof record c8a_wo3.md
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(pointed=False, reason=None))
    _launch(repo, "b", 22, "local", None)
    asked = []
    got = launcher.launch_report_for_batch(repo, BATCH, title_fn=_counting_titles(asked))
    assert got == {"ok": True, "report": None, "lanes": 2}
    assert asked == []


def test_a_batch_with_a_report_looks_up_a_title_for_each_lane(world):
    # axis: a batch that does report still gets a title for each lane — see bite-proof record c8a_wo3.md
    repo, _store = world
    _launch(repo, "a", 11, "local", _call(pointed=False, reason=None))
    _launch(repo, "b", 22, "cloud")
    asked = []
    got = launcher.launch_report_for_batch(repo, BATCH, title_fn=_counting_titles(asked))
    assert got["report"] is not None and got["lanes"] == 2
    assert sorted(asked) == [11, 22]
    assert "#22 Title 22" in got["report"]


def test_the_report_and_the_title_lookup_share_one_predicate():
    # axis: the title lookup and the renderer decide by the one predicate, so they cannot drift — see bite-proof record c8a_wo3.md
    calls = [_call(pointed=False, reason=None), _call("cloud", pointed=True)]
    assert LR.yields_report(calls[:1]) is False
    assert LR.yields_report(calls) is True
    assert LR.render_report([{"issue": 1, "title": None, "placeCall": c} for c in calls[:1]]) is None
    assert LR.render_report([{"issue": 1, "title": None, "placeCall": c} for c in calls]) is not None
