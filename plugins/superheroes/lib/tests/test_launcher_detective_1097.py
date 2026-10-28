"""Tests for the launcher's detective charter: the premise keys `charter` and `budget`, the prompt
each charter composes, the `charter` field on the `reserved` record, and the ledger's fold of it.

Nothing here touches the network. The launch tests spawn a stand-in child (a short Python
sleep), never a real session.
"""
import json
import os
import signal
import subprocess

import pytest

import charter_detect
import heartbeat as hb
import launch_ledger as ll
import wave_watch as ww
from test_cloud_builder import ENV_ID, SHA
from test_launcher_cloud import _cloud_repo, _fake_spawn as _fake_cloud_spawn, _launch as _cloud_launch
from test_launcher import (  # noqa: F401  (the two autouse fixtures apply to this module too)
    L,
    _all_checks,
    _autouse_isolated_ledger_root,
    _autouse_seat_config_matches_spawn,
    _init_repo,
    _ledger_env,
    _make_spawn_fn,
    _valid_premise,
)

BRANCH = "feature/adopted-1"
HEAD = "b" * 40
BUDGET = "until 18:00 local, no more than 3 hours of builder time"
DETECTIVE_HEAD = "/superheroes:detective\n\nIssue: #%s\nBudget: %s\n\n"

_BAD_CHARTERS = [None, "", "Detective", " detective", "detective ", "bogus", ["detective"], True, 7]
_BAD_BUDGETS = [
    None, "", "   ", " 1h", "1h ", "\t1h", "1h\n", "1h\n2h", "1h\r", "1h\r\n2h",
    "1\x00h", "1h\x00", "\x001h", "1\th", "1h\x7f", "1\x1bh", 5, True, ["1h"], {"a": 1},
]


def _local(repo, premise, issue=656):
    return L.compose_launch(repo, issue, premise)


def _cloud(premise, issue=1747):
    return L.compose_launch(
        ".", issue, premise, model="opus", place="cloud", cloud_environment=ENV_ID,
        session_name="issue-%s-probe" % issue)


def _reserved_of(repo):
    return [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"]


def _fold_rec(**extra):
    rec = {
        "event": "reserved", "launchId": "l1", "ts": 1.0, "schema": ll.SCHEMA, "batchId": "b1",
        "repoId": "test", "issue": 656, "surfaces": ["alpha"], "premise": {}, "preflight": {},
        "argv": [], "doctrineDigest": "abc123", "model": "test-model",
    }
    rec.update(extra)
    return rec


# ---------------------------------------------------------------- refusals at both doors


def _refusal_cases():
    cases = []
    for bad in _BAD_CHARTERS:
        cases.append(({"charter": bad}, "premise-charter-invalid"))
        cases.append(({"charter": bad, "budget": BUDGET}, "premise-charter-invalid"))
    cases.append(({"charter": "detective"}, "premise-detective-budget-missing"))
    cases.append(({"budget": BUDGET}, "premise-budget-without-detective"))
    cases.append(({"charter": "workhorse", "budget": BUDGET}, "premise-budget-without-detective"))
    for bad in _BAD_BUDGETS:
        cases.append(({"charter": "detective", "budget": bad}, "premise-budget-invalid"))
    return cases


@pytest.mark.parametrize("extra,reason", _refusal_cases())
def test_validate_premise_refuses_a_bad_charter_budget_pair(tmp_path, extra, reason):
    # axis: charter_premise_reason at the validate_premise door — each refusal token
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, **extra), repo)
    assert result["ok"] is False
    assert result["reason"] == reason


@pytest.mark.parametrize("extra,reason", _refusal_cases())
def test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing(tmp_path, extra, reason):
    # axis: charter_premise_reason at the compose_launch door — each refusal token, no prompt
    repo = _init_repo(tmp_path / "repo")
    result = _local(repo, _valid_premise(repo, **extra))
    assert result["ok"] is False
    assert result["reason"] == reason
    assert "prompt" not in result


def test_compose_refuses_a_cloud_detective_without_a_budget_and_composes_nothing():
    # axis: charter_premise_reason runs before the cloud composer, so a cloud detective is refused too
    result = _cloud({"baseCommit": SHA, "charter": "detective"})
    assert result["ok"] is False
    assert result["reason"] == "premise-detective-budget-missing"
    assert "prompt" not in result


def test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command(tmp_path):
    # axis: the DoD fixture — a detective premise with no budget composes nothing at all
    repo = _init_repo(tmp_path / "repo")
    result = _local(repo, _valid_premise(repo, charter="detective"))
    assert result["ok"] is False
    assert "prompt" not in result
    assert result["reason"] == "premise-detective-budget-missing"


def test_validate_premise_accepts_a_sound_detective_premise_untouched(tmp_path):
    # axis: charter_premise_reason accepts the sound pair and stamps it through unchanged
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, charter="detective", budget=BUDGET), repo)
    assert result["ok"] is True, result
    assert result["premise"]["charter"] == "detective"
    assert result["premise"]["budget"] == BUDGET
    explicit = L.validate_premise(_valid_premise(repo, charter="workhorse"), repo)
    assert explicit["ok"] is True, explicit


# ---------------------------------------------------------------- the prompts


def _without_command_and_budget(prompt):
    assert prompt.startswith("/superheroes:detective\n\n")
    return prompt.replace("/superheroes:detective", L._WORKHORSE_CMD, 1).replace(
        "\nBudget: %s" % BUDGET, "", 1)


def test_local_detective_prompt_starts_with_the_command_and_names_the_budget(tmp_path):
    # axis: the command choice and the budget line on the local prompt
    repo = _init_repo(tmp_path / "repo")
    detective = _local(repo, _valid_premise(repo, charter="detective", budget=BUDGET))
    workhorse = _local(repo, _valid_premise(repo))
    assert detective["ok"] is True, detective
    assert detective["prompt"].startswith(DETECTIVE_HEAD % (656, BUDGET))
    assert detective["charter"] == "detective"
    assert _without_command_and_budget(detective["prompt"]) == workhorse["prompt"]
    assert detective["prompt"] in detective["argv"]


def test_compose_refuses_a_cloud_detective_and_composes_nothing():
    # axis: the detective charter carries no cloud intake step, so a cloud detective is refused
    result = _cloud({"baseCommit": SHA, "charter": "detective", "budget": BUDGET})
    assert result["ok"] is False
    assert result["reason"] == "compose-detective-cloud-unsupported"
    assert "prompt" not in result


def test_local_adopt_detective_prompt_starts_with_the_command_and_names_the_budget(tmp_path):
    # axis: the command choice and the budget line on the local-adopt prompt
    repo = _init_repo(tmp_path / "repo")
    detective = _local(repo, _valid_premise(
        repo, charter="detective", budget=BUDGET, adoptsBranch=BRANCH, adoptsHead=HEAD))
    workhorse = _local(repo, _valid_premise(repo, adoptsBranch=BRANCH, adoptsHead=HEAD))
    assert detective["ok"] is True, detective
    assert detective["prompt"].startswith(DETECTIVE_HEAD % (656, BUDGET) + "Adopts branch: ")
    assert _without_command_and_budget(detective["prompt"]) == workhorse["prompt"]


def test_compose_refuses_a_cloud_adopt_detective_and_composes_nothing():
    # axis: the cloud refusal holds for an adopting detective too — no intake step selects the handed-over head
    adopt = {"adoptsBranch": BRANCH, "adoptsHead": HEAD}
    result = _cloud({"baseCommit": SHA, "charter": "detective", "budget": BUDGET, **adopt})
    assert result["ok"] is False
    assert result["reason"] == "compose-detective-cloud-unsupported"
    assert "prompt" not in result


def test_a_detective_lane_routed_to_the_cloud_leaves_an_accounted_refusal(tmp_path):
    # axis: launch_build refuses a cloud detective lane and the refusal is accounted in the ledger
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _cloud_launch(
        repo, tmp_path, _fake_cloud_spawn(calls=calls),
        premise=_valid_premise(repo, charter="detective", budget=BUDGET))
    assert result["ok"] is False
    assert result["reason"] == "compose-detective-cloud-unsupported"
    assert calls == []
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert len(reserved) == 1
    assert reserved[0]["charter"] == "detective"
    refused = [
        r for r in records
        if r.get("event") == "refused" and r.get("launchId") == reserved[0]["launchId"]
    ]
    assert len(refused) == 1
    assert refused[0]["reason"] == "compose-detective-cloud-unsupported"
    assert ll.fold(records)["ok"] is True


def test_workhorse_prompts_are_byte_identical_with_the_charter_absent_or_explicit(tmp_path):
    # axis: an explicit workhorse charter composes exactly what the absent key composes
    repo = _init_repo(tmp_path / "repo")
    absent = _local(repo, _valid_premise(repo))
    explicit = _local(repo, _valid_premise(repo, charter="workhorse"))
    assert absent["ok"] is True and explicit["ok"] is True
    assert absent["charter"] == "workhorse" and explicit["charter"] == "workhorse"
    assert explicit["prompt"] == absent["prompt"]
    assert absent["prompt"].startswith("%s\n\nIssue: #656\n\n" % L._WORKHORSE_CMD)
    assert "Budget:" not in absent["prompt"].split("\n\n")[1]
    cloud_absent = _cloud({"baseCommit": SHA})
    cloud_explicit = _cloud({"baseCommit": SHA, "charter": "workhorse"})
    assert cloud_explicit["prompt"] == cloud_absent["prompt"]
    assert cloud_absent["charter"] == "workhorse"
    assert cloud_absent["prompt"].startswith("%s\n\nIssue: #1747\n\n" % L._WORKHORSE_CMD)


def test_a_non_dict_premise_still_composes_as_workhorse_or_refuses_as_before():
    # axis: charter_premise_reason never raises on a non-dict premise
    assert L.charter_premise_reason(None) is None
    assert L.charter_premise_reason("detective") is None
    assert L.charter_premise_reason([]) is None


# ---------------------------------------------------------------- the command table


@pytest.mark.parametrize("name", sorted(ll.LAUNCH_CHARTERS))
def test_every_launchable_charter_carries_the_heartbeat_stamp_duty(name):
    # axis: a launcher-issued lane stamps its heartbeat, so each launchable charter's skill names the producer call
    root = os.path.dirname(os.path.dirname(os.path.realpath(L.__file__)))
    with open(os.path.join(root, "skills", name, "SKILL.md"), encoding="utf-8") as fh:
        assert 'lib/heartbeat.py" stamp' in fh.read()


@pytest.mark.parametrize("name", ["workhorse", "detective"])
def test_each_launchable_charter_is_a_shipped_skill_and_a_detected_charter(name):
    # axis: every launchable charter's command names a shipped skill that charter_detect reads back
    assert L._CHARTER_COMMANDS[name] == "/superheroes:%s" % name
    root = os.path.dirname(os.path.dirname(os.path.realpath(L.__file__)))
    with open(os.path.join(root, "skills", name, "SKILL.md"), encoding="utf-8") as fh:
        frontmatter = fh.read().split("---")[1]
    assert "name: %s" % name in frontmatter.splitlines()
    assert charter_detect.COMMAND_CHARTERS[name] == name


# ---------------------------------------------------------------- the ledger fold


@pytest.mark.parametrize("extra", [
    {"charter": "detective"},
    {"charter": "workhorse"},
    {},
    {"charter": "detective", "premise": {"charter": "detective", "budget": "1h"}},
    {"charter": "workhorse", "premise": {"charter": "workhorse"}},
    {"charter": "workhorse", "premise": {"surfaces": ["alpha"]}},
])
def test_fold_accepts_a_sound_or_absent_charter(extra):
    # axis: the reserved charter guard accepts the launchable names and an absent field
    folded = ll.fold([_fold_rec(**extra)])
    assert folded["ok"] is True, folded


@pytest.mark.parametrize("extra", [
    {"charter": "bogus"},
    {"charter": ""},
    {"charter": None},
    {"charter": "Detective"},
    {"charter": ["detective"]},
    {"charter": "detective", "premise": {"charter": "workhorse"}},
    {"charter": "workhorse", "premise": {"charter": "detective", "budget": "1h"}},
])
def test_fold_refuses_a_bad_or_disagreeing_charter(extra):
    # axis: the reserved charter guard — a string in LAUNCH_CHARTERS that agrees with the premise's
    folded = ll.fold([_fold_rec(**extra)])
    assert folded["ok"] is False
    assert folded["reason"] == "fold-bad-field:reserved:charter"


# ---------------------------------------------------------------- end to end, local


def _launch(repo, tmp_path, issue, premise, procs, name="logs"):
    def spawn(argv, cwd, out_fh, err_fh, child_env):
        proc = _make_spawn_fn("sleep")(argv, cwd, out_fh, err_fh, child_env)
        procs.append(proc)
        return proc
    return L.launch_build(
        repo, issue, premise, _all_checks(), str(tmp_path / name), spawn_fn=spawn,
        settle_seconds=0.3)


def _reap_all(procs):
    for proc in procs:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)


def test_a_detective_lane_launches_and_takes_every_ledger_door(tmp_path):
    # axis: the whole local path — compose, reserve, outcome, amend, count — on a detective lane
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, charter="detective", budget=BUDGET)
    assert L.declare_batch(repo, premise["batchId"], 1)["ok"] is True
    procs = []
    try:
        result = _launch(repo, tmp_path, 656, premise, procs)
        assert result["ok"] is True, result
        reserved = _reserved_of(repo)
        assert len(reserved) == 1
        assert reserved[0]["charter"] == "detective"
        assert reserved[0]["premise"]["charter"] == "detective"
        assert reserved[0]["premise"]["budget"] == BUDGET
        prompt = reserved[0]["argv"][-1]
        assert prompt.startswith(DETECTIVE_HEAD % (656, BUDGET))
        _reap_all(procs)
        launch_id = reserved[0]["launchId"]
        assert L.record_outcome(repo, launch_id, "handback", "diagnosis receipt posted")["ok"] is True
        assert L.amend(repo, launch_id, "vet", "ready", "the receipt demonstrates the cause")["ok"] is True
        counted = L.count_batch(repo, premise["batchId"])
        assert counted["ok"] is True, counted
        folded = ll.fold(ll.read(repo)["records"])
        assert folded["ok"] is True, folded
    finally:
        _reap_all(procs)


def _noop_gh_run(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([{"number": 1}]), stderr="")


def test_the_watch_reads_a_detective_lane_as_it_reads_a_workhorse_lane(tmp_path):
    # axis: the watch's ledger read does not branch on the lane's charter
    repo = _init_repo(tmp_path / "repo")
    procs = []
    seen = {}
    try:
        for issue, charter, extra in (
            (656, "workhorse", {}), (657, "detective", {"budget": BUDGET}),
        ):
            batch = "wave-%s" % charter
            premise = _valid_premise(
                repo, batchId=batch, issue=issue, surfaces=["lane-%s" % charter],
                charter=charter, **extra)
            assert L.declare_batch(repo, batch, 1)["ok"] is True
            launched = _launch(repo, tmp_path, issue, premise, procs, name="logs-%s" % charter)
            assert launched["ok"] is True, launched
            lane = [r for r in _reserved_of(repo) if r["batchId"] == batch][0]
            assert lane["charter"] == charter
            hb.stamp(repo, state="handback", phase="watch", launch_id=lane["launchId"])
            watched = ww.watch_arm(repo, batch, max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
            assert watched["ok"] is True, watched
            seen[charter] = (watched, lane["launchId"])
    finally:
        _reap_all(procs)
    (workhorse, workhorse_id), (detective, detective_id) = seen["workhorse"], seen["detective"]
    assert detective["event"] == workhorse["event"] == "lane-terminal"
    assert detective["launches"] == [{"launchId": detective_id, "state": "handback"}]
    assert workhorse["launches"] == [{"launchId": workhorse_id, "state": "handback"}]
    assert detective["degraded"] == workhorse["degraded"]


# ---------------------------------------------------------------- refusal accounting


def test_a_detective_lane_refused_at_preflight_is_accounted_with_its_charter(tmp_path):
    # axis: _try_reserve_for_refusal writes the charter, so a refused detective lane is a detective record
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    result = L.launch_build(
        repo, 656, _valid_premise(repo, charter="detective", budget=BUDGET), checks,
        str(tmp_path / "logs"))
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert len(reserved) == 1
    assert reserved[0]["charter"] == "detective"
    terminal = [
        r for r in records
        if r.get("launchId") == reserved[0]["launchId"] and r.get("event") in ("outcome", "refused")
    ]
    assert len(terminal) >= 1
    assert ll.fold(records)["ok"] is True


def test_an_invalid_charter_refusal_leaves_no_charter_on_the_record_and_the_ledger_folds(tmp_path):
    # axis: an invalid charter value is omitted from the accounting record, so the ledger still folds
    repo = _init_repo(tmp_path / "repo")
    result = L.launch_build(
        repo, 656, _valid_premise(repo, charter="bogus"), _all_checks(), str(tmp_path / "logs"))
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    for rec in records:
        if rec.get("event") == "reserved":
            assert "charter" not in rec
    assert ll.fold(records)["ok"] is True
