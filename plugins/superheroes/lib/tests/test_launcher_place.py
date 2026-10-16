# plugins/superheroes/lib/tests/test_launcher_place.py
"""Conformance: the routing step in the launch path and the local fallback.

Every launch here goes through `launcher.main(["launch", ...])`. The cloud setup record, the
setting and the account are built under tmp_path and read by the real readiness reader; the
routing step is given a fixed advisor version, a fixed day, a fixed calibration stamp and a
needs reader that looks only at the premise. The platform command and the owner's machine are
stand-ins injected through the launcher's default spawn functions. No test touches the real
home directory, the network or the real platform command."""
import datetime
import functools
import json
import types

import pytest

import cloud_ready as CR
import cloud_setup as CS
import core_md as CM
import launch_ledger as ll
import launch_place as LP
import project_config as PC

from test_launcher import (  # noqa: E402
    L,
    _FakeIphoneRun,
    _all_checks,
    _init_repo,
    _make_spawn_fn,
    _slot_calibrated,
    _valid_premise,
    _write_json,
)
from test_launcher_cloud import (  # noqa: E402
    ENV_ID,
    _cloud_repo,
    _fake_spawn,
    _git,
    _local_remote_has,
    _spawned,
)

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

ACCOUNT = "acct-fixture-one"
ADVISOR = "1.2.3"
STAMP = "sha256:" + "ab" * 32
TODAY = datetime.date(2026, 10, 11)
FUTURE = "2026-12-01"
PAST = "2026-10-10"
BATCH = "wave-test"
BOUNDARY = {
    "slotRef": "slot-a@1", "result": "pass", "provenance": "observed", "strength": "strong",
    "match": True, "policyDigest": "digest123", "verifiedAt": "2026-01-01T00:00:00Z",
    "weakerAccepted": False, "acceptedBy": None, "acceptedAt": None, "acceptanceReason": None,
}
PHONE = "the phone simulator"
UNREACHABLE_WORDS = "The cloud platform couldn't be reached."


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    # The instance-pin gate applies only on a Claude-hosted seat; these tests are not one.
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
    # The base is kept on a local bare remote and asked of it, not of GitHub.
    monkeypatch.setattr(L, "_base_on_remote_fn", _local_remote_has)
    # A local child that is still alive after this long counts as started.
    monkeypatch.setattr(L, "_SETTLE_SECONDS", 0.3)


# ---------------------------------------------------------------- the owner's machine and the cloud


class _Machine:
    """The owner's machine: every local spawn is recorded and leaves a stand-in child behind."""

    def __init__(self):
        self.calls = []
        self.procs = []
        self.behavior = "sleep"

    def spawn(self, argv, cwd, out_fh, err_fh, child_env):
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": dict(child_env)})
        proc = _make_spawn_fn(self.behavior)(argv, cwd, out_fh, err_fh, child_env)
        self.procs.append(proc)
        return proc

    def stop_all(self):
        for proc in self.procs:
            proc.kill()
            proc.wait()


@pytest.fixture
def machine(monkeypatch):
    stand_in = _Machine()
    monkeypatch.setattr(L, "_default_spawn", stand_in.spawn)
    yield stand_in
    stand_in.stop_all()


def _cloud(monkeypatch, **kwargs):
    """Inject the platform command stand-in; the list of the calls made to it."""
    calls = []
    monkeypatch.setattr(L, "_default_cloud_spawn", _fake_spawn(calls=calls, **kwargs))
    return calls


# ---------------------------------------------------------------- the world: setting, record, account


def _judged_needs(cwd, premise, root=None):
    """What only the owner's machine has, read from the premise alone."""
    judged = premise.get("needs")
    found = [n for n in judged if isinstance(n, str) and n.strip()] if isinstance(judged, list) else []
    if premise.get("iphoneCheck") is True:
        found.append(PHONE)
    return found


def _account_env(tmp_path):
    home = tmp_path / "account-home"
    home.mkdir(exist_ok=True)
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": ACCOUNT}}), encoding="utf-8")
    return {"HOME": str(home)}


def _world(tmp_path, monkeypatch, *, setting=True, **record_over):
    """A repository whose HEAD the remote has, a passed cloud check, the cloud-builds setting, and
    the account, all read by the routing step the CLI calls."""
    repo = _cloud_repo(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    values = {
        "account": ACCOUNT, "environment": ENV_ID, "plugin_version": ADVISOR,
        "picks_up_version": False, "calibration_stamp": STAMP,
        "calibration_date": "2026-10-01", "pass_lapses": FUTURE, "checked_at": "2026-10-09",
    }
    values.update(record_over)
    got = CS.record_check(repo, root=store, **values)
    assert got["action"] in ("written", "noop"), got
    if setting:
        assert PC.set_item(
            repo, "cloudBuilds", True, root=store, account=ACCOUNT)["action"] == "written"
    env = _account_env(tmp_path)
    readiness = functools.partial(
        CR.readiness, advisor_version=ADVISOR, today=TODAY, stamp_fn=lambda cwd, root: STAMP)
    routed = []
    real_route = LP.route

    def route(cwd, premise, word=None):
        routed.append({"premise": dict(premise), "word": word})
        return real_route(
            cwd, premise, word, readiness_fn=readiness, needs_fn=_judged_needs, root=store, env=env)

    monkeypatch.setattr(L.launch_place, "route", route)
    return types.SimpleNamespace(repo=repo, store=store, routed=routed, tmp=tmp_path)


def _launch_args(world, issue, *flags):
    return [
        "launch", "--repo-root", world.repo, "--issue", str(issue),
        "--premise", str(world.tmp / ("premise-%s.json" % issue)),
        "--checks", str(world.tmp / "checks.json"),
        "--log-dir", str(world.tmp / "logs"), *flags,
    ]


def _launch(world, capsys, issue, *flags, premise=None, **premise_over):
    """One CLI launch: the exit status and the JSON it printed."""
    if premise is None:
        premise = _valid_premise(
            world.repo, issue=issue, batchId=BATCH, surfaces=["lane/%s" % issue], **premise_over)
    _write_json(world.tmp / ("premise-%s.json" % issue), premise)
    _write_json(world.tmp / "checks.json", _all_checks())
    capsys.readouterr()
    code = L.main(_launch_args(world, issue, *flags))
    lines = capsys.readouterr().out.strip().splitlines()
    return code, json.loads(lines[-1])


# ---------------------------------------------------------------- reading the ledger


def _records(repo, event=None):
    got = ll.read(repo)["records"]
    return [r for r in got if event is None or r.get("event") == event]


def _reserved(repo, launch_id):
    found = [r for r in _records(repo, "reserved") if r["launchId"] == launch_id]
    assert len(found) == 1, found
    return found[0]


def _lanes(repo):
    folded = ll.fold(ll.read(repo)["records"])
    assert folded["ok"], folded["reason"]
    return folded["launches"]


def _end_every_lane(world, machine):
    """The owners of the lanes record their outcomes, so the batch can be counted."""
    machine.stop_all()
    for launch_id, info in _lanes(world.repo).items():
        if not info["terminal"]:
            got = ll.record_outcome(world.repo, launch_id, "handback", "fixture ends the lane")
            assert got["ok"], got


# ---------------------------------------------------------------- FR-12: five launches


def test_five_launches_put_the_three_that_need_nothing_in_the_cloud(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    ll.declare_batch(world.repo, BATCH, 5)
    results = {}
    for issue in (201, 202, 203):
        code, results[issue] = _launch(world, capsys, issue)
        assert code == 0, results[issue]
    for issue in (204, 205):
        code, results[issue] = _launch(world, capsys, issue, needs=["a signed-in browser"])
        assert code == 0, results[issue]

    assert len(cloud_calls) == 3 and len(machine.calls) == 2
    for issue in (201, 202, 203):
        call = results[issue]["placeCall"]
        assert (call["place"], call["reason"], call["environment"]) == ("cloud", None, ENV_ID)
        assert results[issue]["place"] == "cloud"
        reserved = _reserved(world.repo, results[issue]["launchId"])
        assert reserved["premise"]["placeCall"] == call
        assert reserved["place"] == "cloud" and reserved["cloudEnvironment"] == ENV_ID
    for issue in (204, 205):
        call = results[issue]["placeCall"]
        assert (call["place"], call["reason"], call["need"]) == (
            "local", "needs", "a signed-in browser")
        assert LP.reason_text(call) == (
            "It needs a signed-in browser, which only your machine has.")
        reserved = _reserved(world.repo, results[issue]["launchId"])
        assert reserved["premise"]["placeCall"] == call
        assert "place" not in reserved and reserved["worktree"]
    assert [entry["word"] for entry in world.routed] == [None] * 5

    _end_every_lane(world, machine)
    counted = ll.count(world.repo, BATCH)
    assert counted["resolved"] is True, counted
    assert counted["lanes"] == {"declared": 5, "resolved": 5, "cloud": 3}


def test_the_router_is_called_once_per_launch_with_the_premise_as_the_owner_gave_it(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    _cloud(monkeypatch)
    code, result = _launch(world, capsys, 211)
    assert code == 0, result
    assert len(world.routed) == 1
    assert "placeCall" not in world.routed[0]["premise"]
    assert world.routed[0]["premise"]["issue"] == 211


# ---------------------------------------------------------------- UFR-4: never held or dropped


@pytest.mark.parametrize("case", ["ready", "lapsed", "version-mismatch", "spawn-failure"])
def test_n_launches_give_n_lanes_and_the_batch_counts_them(
    tmp_path, monkeypatch, capsys, machine, case,
):
    record = {"lapsed": {"pass_lapses": PAST}, "version-mismatch": {"plugin_version": "0.41.0"}}
    world = _world(tmp_path, monkeypatch, **record.get(case, {}))
    _cloud(monkeypatch, raises=OSError("no platform") if case == "spawn-failure" else None)
    ll.declare_batch(world.repo, BATCH, 3)
    results = []
    for issue in (221, 222, 223):
        code, result = _launch(world, capsys, issue)
        assert code == 0, result
        assert result["ok"] is True
        results.append(result)

    places = {r["placeCall"]["place"] for r in results}
    reasons = {r["placeCall"]["reason"] for r in results}
    expected = {
        "ready": ({"cloud"}, {None}),
        "lapsed": ({"local"}, {"pass-lapsed"}),
        "version-mismatch": ({"local"}, {"version"}),
        "spawn-failure": ({"local"}, {"unreachable"}),
    }[case]
    assert (places, reasons) == expected
    assert len(_lanes(world.repo)) == (6 if case == "spawn-failure" else 3)

    _end_every_lane(world, machine)
    counted = ll.count(world.repo, BATCH)
    assert counted["resolved"] is True, counted
    assert counted["lanes"]["declared"] == 3 and counted["lanes"]["resolved"] == 3
    assert counted["counts"]["total"] == 3


# ---------------------------------------------------------------- the fallback


def test_a_cloud_spawn_failure_runs_the_build_locally_and_says_unreachable(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch, raises=OSError("no platform"))
    ll.declare_batch(world.repo, BATCH, 1)
    code, result = _launch(world, capsys, 231)

    assert code == 0, result
    assert result["ok"] is True and result["fellBack"] is True
    assert len(cloud_calls) == 1 and len(machine.calls) == 1
    call = result["placeCall"]
    assert (call["place"], call["reason"], call["environment"]) == ("local", "unreachable", None)
    assert LP.reason_text(call) == UNREACHABLE_WORDS
    attempt = result["cloudAttempt"]
    assert attempt["ok"] is False and attempt["reason"] == "spawn-oserror"

    # The cloud attempt was ended as refused before any session could exist; the relaunch is a
    # separate, started local lane for the same issue.
    lanes = _lanes(world.repo)
    assert lanes[attempt["launchId"]]["terminalKind"] == "refused"
    assert lanes[result["launchId"]]["started"] is True
    assert _reserved(world.repo, attempt["launchId"])["premise"]["placeCall"]["place"] == "cloud"
    assert _reserved(world.repo, result["launchId"])["premise"]["placeCall"] == call

    _end_every_lane(world, machine)
    counted = ll.count(world.repo, BATCH)
    assert counted["resolved"] is True, counted
    assert counted["lanes"]["resolved"] == 1
    assert counted["attempts"]["total"] == 2 and counted["attempts"]["extra"] == 1
    assert counted["laneDetail"][0]["attempts"] == 2


def test_a_base_ref_that_moves_between_the_cloud_attempt_and_the_fallback_builds_the_first_commit(
    tmp_path, monkeypatch, capsys, machine,
):
    # axis: a premise's base names one commit for the cloud attempt and the local fallback alike — see bite-proof record wo_d_place_call
    world = _world(tmp_path, monkeypatch)
    _git(world.repo, "branch", "moving")
    first = _git(world.repo, "rev-parse", "moving").strip()
    cloud_calls = []

    def spawn_that_moves_the_ref_then_fails(argv, cwd, log_path, child_env, timeout):
        cloud_calls.append(argv)
        tree = _git(world.repo, "rev-parse", "moving^{tree}").strip()
        second = _git(
            world.repo, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
            "commit-tree", tree, "-p", first, "-m", "the ref moved").strip()
        _git(world.repo, "update-ref", "refs/heads/moving", second)
        raise OSError("no platform")

    monkeypatch.setattr(L, "_default_cloud_spawn", spawn_that_moves_the_ref_then_fails)
    code, result = _launch(world, capsys, 232, baseCommit="moving")

    assert code == 0, result
    assert result["ok"] is True and result["fellBack"] is True
    assert len(cloud_calls) == 1 and len(machine.calls) == 1
    assert _git(world.repo, "rev-parse", "moving").strip() != first
    attempt = result["cloudAttempt"]
    assert _reserved(world.repo, attempt["launchId"])["premise"]["baseCommit"] == first
    assert _reserved(world.repo, result["launchId"])["premise"]["baseCommit"] == first


def test_a_base_that_does_not_resolve_is_left_alone_and_refused_downstream(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 233, baseCommit="no-such-ref")

    assert code == 1
    assert result["ok"] is False and result["reason"] == "premise-base-commit-unresolved"
    assert world.routed[0]["premise"]["baseCommit"] == "no-such-ref"
    assert cloud_calls == [] and machine.calls == []


def test_a_log_that_cannot_be_opened_runs_the_build_locally_the_same_way(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    ids = iter(["a" * 16, "b" * 16])
    monkeypatch.setattr(L, "secrets", types.SimpleNamespace(token_hex=lambda n: next(ids)))
    # A directory where the cloud attempt's error log must be makes opening it fail.
    (world.tmp / "logs" / ("launch-%s.stderr" % ("a" * 16))).mkdir(parents=True)
    code, result = _launch(world, capsys, 241)

    assert code == 0, result
    assert result["fellBack"] is True and result["cloudAttempt"]["reason"] == "log-open-failed"
    assert cloud_calls == [] and len(machine.calls) == 1
    assert result["placeCall"]["place"] == "local"
    assert result["placeCall"]["reason"] == "unreachable"
    assert _lanes(world.repo)[result["cloudAttempt"]["launchId"]]["terminalKind"] == "refused"


def test_the_fallback_resources_go_to_the_local_relaunch_only(
    tmp_path, monkeypatch, capsys,
):
    world = _world(tmp_path, monkeypatch)
    _write_json(world.tmp / "boundary.json", BOUNDARY)
    calls = []

    def recorder(repo, issue, premise, checks, log_dir, **kwargs):
        calls.append({"premise": premise, **kwargs})
        if kwargs.get("place") == "cloud":
            return {"ok": False, "reason": "spawn-oserror", "launchId": "launch-cloud"}
        return {"ok": True, "reason": None, "launchId": "launch-local"}

    monkeypatch.setattr(L, "launch_build", recorder)
    code, result = _launch(
        world, capsys, 251, "--slot", "slot-a", "--generation", "1",
        "--boundary", str(world.tmp / "boundary.json"))

    assert code == 0, result
    cloud_call, local_call = calls
    assert cloud_call["place"] == "cloud" and cloud_call["cloud_environment"] == ENV_ID
    for held_back in ("slot", "generation", "boundary"):
        assert held_back not in cloud_call
    assert "place" not in local_call and "cloud_environment" not in local_call
    assert (local_call["slot"], local_call["generation"], local_call["boundary"]) == (
        "slot-a", 1, BOUNDARY)
    # The fallback used the resources, so none is handed back.
    assert "fallbackResourcesUnused" not in result
    assert cloud_call["premise"]["placeCall"]["place"] == "cloud"
    assert local_call["premise"]["placeCall"]["place"] == "local"
    assert local_call["premise"]["placeCall"]["reason"] == "unreachable"
    assert "placeCall" not in json.loads((world.tmp / "premise-251.json").read_text())


def test_a_fallback_that_is_refused_is_returned_with_the_cloud_attempt(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    _cloud(monkeypatch, raises=OSError("no platform"))
    machine.behavior = "exit1"
    code, result = _launch(world, capsys, 261)

    assert code == 1
    assert result["ok"] is False and result["reason"] == "settle-nonzero-exit"
    assert result["fellBack"] is True
    assert result["cloudAttempt"]["reason"] == "spawn-oserror"
    assert result["placeCall"]["place"] == "local"
    assert result["placeCall"]["reason"] == "unreachable"
    assert len(machine.calls) == 1


# ---------------------------------------------------------------- no fallback where a session may exist


def test_cloud_session_unconfirmed_makes_no_local_launch(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch, result=_spawned("the command printed no receipt"))
    code, result = _launch(world, capsys, 271)

    assert "fellBack" not in result and "cloudAttempt" not in result
    assert len(cloud_calls) == 1 and machine.calls == []
    assert code == 1
    assert result["ok"] is False and result["reason"] == "cloud-session-unconfirmed"
    assert result["placeCall"]["place"] == "cloud"
    lanes = _lanes(world.repo)
    assert list(lanes) == [result["launchId"]]
    assert lanes[result["launchId"]]["terminal"] is False


def _terminalization_fails(monkeypatch, world):
    monkeypatch.setattr(L, "_terminalize", lambda *a, **kw: {"ok": False, "reason": "fixture"})


def _base_off_the_remote(monkeypatch, world):
    monkeypatch.setattr(L, "_base_on_remote_fn", lambda *args, **kwargs: False)


@pytest.mark.parametrize("cloud_kwargs,prepare,reason", [
    ({"raises": OSError("no platform")}, _terminalization_fails, "terminalization-failed:fixture"),
    ({"result": "not a spawn result"}, None, "cloud-spawn-result-invalid"),
], ids=["terminalization-failed", "spawn-result-invalid"])
def test_no_other_cloud_result_falls_back(
    tmp_path, monkeypatch, capsys, machine, cloud_kwargs, prepare, reason,
):
    world = _world(tmp_path, monkeypatch)
    _cloud(monkeypatch, **cloud_kwargs)
    if prepare is not None:
        prepare(monkeypatch, world)
    code, result = _launch(world, capsys, 281)

    assert code == 1
    assert result["ok"] is False and result["reason"] == reason
    assert "fellBack" not in result and "cloudAttempt" not in result
    assert result["placeCall"]["place"] == "cloud"
    assert machine.calls == []
    assert len([r for r in _records(world.repo, "reserved")]) == 1


def _remote_not_asked(monkeypatch, world):
    monkeypatch.setattr(L, "_base_on_remote_fn", lambda *args, **kwargs: None)


@pytest.mark.parametrize("prepare,reason,need,words", [
    (_remote_not_asked, "unreachable", None, UNREACHABLE_WORDS),
    (_base_off_the_remote, "needs", "its base commit",
     "It needs its base commit, which only your machine has."),
], ids=["remote-unchecked", "base-not-on-remote"])
def test_a_base_refusal_before_the_cloud_command_runs_the_build_locally(
    tmp_path, monkeypatch, capsys, machine, prepare, reason, need, words,
):
    # axis: a refusal that ended the cloud attempt before any command ran leaves no session, so the build runs here
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    prepare(monkeypatch, world)
    code, result = _launch(world, capsys, 282)

    assert code == 0, result
    assert result["fellBack"] is True
    assert result["cloudAttempt"]["reason"].startswith("launch-cloud-base-")
    call = result["placeCall"]
    assert (call["place"], call["reason"], call["need"]) == ("local", reason, need)
    assert LP.reason_text(call) == words
    assert cloud_calls == [] and len(machine.calls) == 1


@pytest.mark.parametrize("prepare", [_remote_not_asked, _base_off_the_remote],
                         ids=["remote-unchecked", "base-not-on-remote"])
def test_a_base_refusal_whose_lane_could_not_be_ended_does_not_fall_back(
    tmp_path, monkeypatch, capsys, machine, prepare,
):
    # axis: a lane that was not terminalized may be live, so no second builder starts
    world = _world(tmp_path, monkeypatch)
    _cloud(monkeypatch)
    prepare(monkeypatch, world)
    _terminalization_fails(monkeypatch, world)
    code, result = _launch(world, capsys, 283)

    assert code == 1
    assert result["ok"] is False and result["reason"] == "terminalization-failed:fixture"
    assert "fellBack" not in result and "cloudAttempt" not in result
    assert result["placeCall"]["place"] == "cloud"
    assert machine.calls == []


# ---------------------------------------------------------------- what the advisor reported


def test_a_reported_cloud_version_runs_the_build_locally_and_names_both_versions(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 291, reportedCloud={"pluginVersion": "0.41.0"})

    assert code == 0, result
    call = result["placeCall"]
    assert (call["place"], call["reason"]) == ("local", "version")
    assert (call["cloudVersion"], call["advisorVersion"]) == ("0.41.0", ADVISOR)
    assert LP.reason_text(call) == "The cloud's plugin is 0.41.0 and mine is 1.2.3."
    assert cloud_calls == [] and len(machine.calls) == 1
    reserved = _reserved(world.repo, result["launchId"])
    assert reserved["premise"]["placeCall"] == call
    assert reserved["premise"]["reportedCloud"] == {"pluginVersion": "0.41.0"}


def test_a_reported_unreachable_platform_runs_the_build_locally(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 292, reportedCloud={"unreachable": True})

    assert code == 0, result
    assert (result["placeCall"]["place"], result["placeCall"]["reason"]) == (
        "local", "unreachable")
    assert LP.reason_text(result["placeCall"]) == UNREACHABLE_WORDS
    assert "fellBack" not in result and "cloudAttempt" not in result
    assert cloud_calls == [] and len(machine.calls) == 1


# ---------------------------------------------------------------- the launch word


def test_the_launch_word_local_runs_the_build_locally_with_the_word_as_the_reason(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 301, "--place", "local")

    assert code == 0, result
    assert world.routed[0]["word"] == "local"
    assert (result["placeCall"]["place"], result["placeCall"]["reason"]) == ("local", "local-word")
    assert LP.reason_text(result["placeCall"]) == 'You said "this one local".'
    assert cloud_calls == [] and len(machine.calls) == 1


def test_the_launch_word_cloud_on_an_iphone_check_runs_locally_and_names_the_phone(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch, setting=False)
    cloud_calls = _cloud(monkeypatch)
    monkeypatch.setattr(L, "_default_iphone_run", _FakeIphoneRun())
    code, result = _launch(world, capsys, 311, "--place", "cloud", iphoneCheck=True)

    assert code == 0, result
    call = result["placeCall"]
    assert world.routed[0]["word"] == "cloud"
    assert (call["place"], call["reason"], call["need"], call["by"]) == (
        "local", "needs", PHONE, "word")
    assert LP.reason_text(call) == "It needs the phone simulator, which only your machine has."
    assert cloud_calls == [] and len(machine.calls) == 1


def test_a_launch_with_the_setting_off_and_no_word_runs_locally_with_no_reason(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch, setting=False)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 321)

    assert code == 0, result
    assert (result["placeCall"]["place"], result["placeCall"]["reason"]) == ("local", None)
    assert result["placeCall"]["pointedAtCloud"] is False
    assert LP.reason_text(result["placeCall"]) is None
    assert cloud_calls == [] and len(machine.calls) == 1


# ---------------------------------------------------------------- slots, generations, boundaries


def test_a_cloud_launch_gets_no_slot_and_the_unused_resources_are_handed_back(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(world.repo, BATCH, 2)
    code, result = _launch(world, capsys, 331, "--slot", "slot-a", "--generation", "1")

    assert code == 0, result
    assert result["place"] == "cloud" and len(cloud_calls) == 1
    assert result["fallbackResourcesUnused"] == {"slot": "slot-a", "generation": 1}
    reserved = _reserved(world.repo, result["launchId"])
    assert "slot" not in reserved and "generation" not in reserved
    assert machine.calls == []

    # With no resources given, nothing is handed back.
    code, other = _launch(world, capsys, 332)
    assert code == 0, other
    assert "fallbackResourcesUnused" not in other


def test_a_local_launch_keeps_its_slot_generation_and_boundary(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch, setting=False)
    _cloud(monkeypatch)
    _write_json(world.tmp / "boundary.json", BOUNDARY)
    code, result = _launch(
        world, capsys, 341, "--slot", "slot-a", "--generation", "1",
        "--boundary", str(world.tmp / "boundary.json"))

    assert code == 0, result
    assert "fallbackResourcesUnused" not in result
    reserved = _reserved(world.repo, result["launchId"])
    assert (reserved["slot"], reserved["generation"]) == ("slot-a", 1)
    assert reserved["boundary"] == BOUNDARY


# ---------------------------------------------------------------- the environment comes from the record


def test_the_cloud_environment_comes_from_the_setup_record(
    tmp_path, monkeypatch, capsys, machine,
):
    recorded = "env_01RecordedOne"
    world = _world(tmp_path, monkeypatch, environment=recorded)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 351)

    assert code == 0, result
    assert result["placeCall"]["environment"] == recorded
    assert recorded in cloud_calls[0]["argv"][cloud_calls[0]["argv"].index("--settings") + 1]
    assert _reserved(world.repo, result["launchId"])["cloudEnvironment"] == recorded


def test_a_cloud_environment_flag_on_launch_is_refused_before_anything_is_decided(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 361, "--cloud-environment", ENV_ID)

    assert code == 1
    assert result["ok"] is False and result["reason"] == "launch-cloud-environment-routed"
    assert world.routed == [] and cloud_calls == [] and machine.calls == []
    assert _records(world.repo) == []


# ---------------------------------------------------------------- the premise carries the placeCall


def test_a_premise_file_that_already_carries_a_place_call_is_refused(
    tmp_path, monkeypatch, capsys, machine,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    premise = _valid_premise(world.repo, issue=371, batchId=BATCH)
    premise["placeCall"] = {"place": "cloud", "environment": ENV_ID}
    code, result = _launch(world, capsys, 371, premise=premise)

    assert code == 1
    assert result["ok"] is False and result["reason"] == "premise-place-call-caller-set"
    assert world.routed == [] and cloud_calls == [] and machine.calls == []
    assert _records(world.repo) == []


_NEEDS_INVALID = ["a signed-in browser", 7, None, {"a": 1}, [1], [""], ["  "], ["ok", None]]


@pytest.mark.parametrize("needs", _NEEDS_INVALID)
def test_a_needs_field_that_is_not_a_list_of_names_is_refused(tmp_path, needs):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-needs-invalid"


@pytest.mark.parametrize("needs", [[], ["a signed-in browser"], ["a", "b"]])
def test_a_needs_field_that_is_a_list_of_names_is_accepted(tmp_path, needs):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, needs=needs), repo)
    assert result["ok"] is True, result
    assert result["premise"]["needs"] == needs


_REPORTED_INVALID = [
    [], "x", 1, True, {"other": True}, {"noPass": False}, {"unreachable": 1},
    {"pluginVersion": 41}, {"pluginVersion": "0.41"}, {"pluginVersion": "v0.41.0"},
    {"noPass": True, "extra": 1},
]


@pytest.mark.parametrize("reported", _REPORTED_INVALID)
def test_a_reported_cloud_in_an_unknown_shape_is_refused(tmp_path, reported):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-reported-cloud-invalid"


@pytest.mark.parametrize("reported", [
    None, {}, {"pluginVersion": "0.41.0"}, {"noPass": True}, {"unreachable": True},
])
def test_a_reported_cloud_in_a_known_shape_is_accepted(tmp_path, reported):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, reportedCloud=reported), repo)
    assert result["ok"] is True, result
    assert result["premise"]["reportedCloud"] == reported


def test_validate_premise_passes_a_place_call_through_untouched(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    call = {"place": "local", "reason": "needs", "need": PHONE, "extra": ["kept"]}
    result = L.validate_premise(_valid_premise(repo, placeCall=call), repo)
    assert result["ok"] is True, result
    assert result["premise"]["placeCall"] == call


@pytest.mark.parametrize("field,value,reason", [
    ("needs", "a signed-in browser", "premise-needs-invalid"),
    ("reportedCloud", {"noPass": False}, "premise-reported-cloud-invalid"),
])
def test_a_launch_with_an_invalid_premise_field_is_refused_and_starts_no_builder(
    tmp_path, monkeypatch, capsys, machine, field, value, reason,
):
    world = _world(tmp_path, monkeypatch)
    cloud_calls = _cloud(monkeypatch)
    code, result = _launch(world, capsys, 381, **{field: value})

    assert code == 1
    assert result["ok"] is False and result["reason"] == reason
    assert "fellBack" not in result
    assert cloud_calls == [] and machine.calls == []
    assert _lanes(world.repo)[result["launchId"]]["terminalKind"] == "refused"
