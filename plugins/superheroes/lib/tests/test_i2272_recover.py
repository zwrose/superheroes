# plugins/superheroes/lib/tests/test_i2272_recover.py
"""Conformance (#2272): the builders' account hitting its usage limit is stop evidence for the lane that ran on it,
a work-order branch the lane's own branch already contains is passed over by `successor`, a handed-back lane that
a fix order reopened is assessed like a live lane, and the cloud helper's read posts only the four fields the
takeover check reads. Same fixtures as test_cloud_recover.py: a real bare remote and a clone per side, only `gh`
faked through `run=`. `cloud_relay.account_limit` is replaced by `monkeypatch.setattr(..., raising=False)`.

Bites on: `limited is True` (a lapsed limit stops nothing), `start < recordedAt` (a lane launched after the limit
was recorded is not stopped by it), the placement after the parked leg, the containment rule that passes over a
contained branch, the refusal of a branch that is diverged from or ahead of the lane's own, the refusal when the
ancestry read fails, the primary requirement (one pull request names the lane's branch), the reopened-handback
leg, and the four-field restriction of the helper's prompt.
Residual blind spots: the pull request read trusts GitHub's `head` filter; a branch whose head contains the lane's
own is never passed over, so work found only there always refuses.
"""
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder  # noqa: E402
import cloud_recover as CR  # noqa: E402
import cloud_relay  # noqa: E402
import launch_ledger as ll  # noqa: E402
from test_cloud_recover import (  # noqa: E402,F401
    BATCH, REPO, _assess, _clean_env, _comment, _died, _git, _lane, _premise, _state, _state_file, w,
)
from test_cloud_recover_parked import PARK, _pushed_at  # noqa: E402

LANE = "issue-17-x"
WO = "wo/17-wo1"
CFG = "/cfg/acct"
FOUR = ["id", "title", "session_status", "status_bucket", "archived"]  # five fields; the name is kept for the bite-proof records


def _reading(*, limited=True, ok=True, recorded_ago=3600, resets_in=1800):
    if not ok:
        return {"ok": False, "reason": "config-dir-invalid"}
    return {"ok": True, "limited": limited, "configDir": CFG, "relay": "cloud-relay", "limitType": "five_hour",
            "resetsAt": time.time() + resets_in, "recordedAt": time.time() - recorded_ago}


def _limit(monkeypatch, reading):
    """Replace `cloud_relay.account_limit`; the calls are recorded."""
    calls = []

    def fake(repo_root, config_dir, *, env=None, now=None):
        calls.append({"repo_root": repo_root, "config_dir": config_dir, "env": env, "now": now})
        return reading

    monkeypatch.setattr(cloud_relay, "account_limit", fake, raising=False)
    return calls


def _no_limit_call(monkeypatch):
    def fake(*args, **kwargs):
        raise AssertionError("account_limit must not be called for this lane")

    monkeypatch.setattr(cloud_relay, "account_limit", fake, raising=False)


def _lane_without_config(w, launch_id, issue=17, start_age=7200):
    assert ll.append(w.root, {
        "event": "reserved", "launchId": launch_id, "ts": time.time() - start_age - 60, "schema": ll.SCHEMA,
        "batchId": BATCH, "repoId": ll.repo_identity(w.root), "issue": issue, "surfaces": ["plugins/x-%s" % launch_id],
        "premise": _premise(w, issue), "preflight": {}, "argv": [], "doctrineDigest": "abc123", "model": "test-model",
        "place": ll.PLACE_CLOUD, "cloudEnvironment": "env-1", "pluginVersion": "1.2.3"})
    assert ll.append(w.root, {
        "event": "started", "launchId": launch_id, "ts": time.time() - start_age, "schema": ll.SCHEMA, "attempt": 1,
        "pid": 999999999, "logPath": "/tmp/log", "errPath": "/tmp/err", "cloudSessionName": "cloud-%s" % launch_id,
        "cloudSessionId": "session_%s" % launch_id, "cloudSessionUrl": "https://claude.ai/code/session_x"})


# ---------------------------------------------------------------- the account's limit as stop evidence


def test_1_a_limit_recorded_after_the_lane_started_stops_it_and_names_the_limit(w, monkeypatch):
    _lane(w, "l1")
    reading = _reading()
    calls = _limit(monkeypatch, reading)
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("stopped", "account-limited")
    assert out["limitType"] == "five_hour" and out["limitResetsAt"] == reading["resetsAt"]
    assert out["stoppedAt"] == reading["recordedAt"]
    assert [(c["repo_root"], c["config_dir"]) for c in calls] == [(w.root, CFG)] and "now" in calls[0] and "env" in calls[0]
    assert _state(w)["assessed"]["l1"] == {
        "verdict": "stopped", "evidence": "account-limited", "at": _state(w)["assessed"]["l1"]["at"],
        "stoppedAt": reading["recordedAt"], "handoverSha": None, "limitResetsAt": reading["resetsAt"]}


def test_1_the_other_evidences_keep_their_entries_and_result_keys(w, monkeypatch):
    _lane(w, "l1")
    _limit(monkeypatch, _reading())
    out = _assess(w, state="failed")
    assert (out["verdict"], out["evidence"]) == ("stopped", "session-failed")
    assert out["limitType"] is None and out["limitResetsAt"] is None
    assert "limitResetsAt" not in _state(w)["assessed"]["l1"]


def test_1_a_failed_session_and_a_handover_still_win_over_the_limit(w, monkeypatch):
    _lane(w, "l1")
    sha = "a" * 40
    w.gh.comments = [_comment(cloud_builder.handover_text(sha), age=500, cid=3)]
    calls = _limit(monkeypatch, _reading())
    out = _assess(w, state="idle")
    assert (out["verdict"], out["evidence"]) == ("stopped", "handover") and calls == []


# ---------------------------------------------------------------- break-its: the limit that does not count


def test_2_a_limit_that_has_lapsed_is_not_stop_evidence_and_withdraws_an_earlier_stop(w, monkeypatch):
    _lane(w, "l1")
    _limit(monkeypatch, _reading())
    assert _assess(w, state="unread")["verdict"] == "stopped"
    _limit(monkeypatch, _reading(limited=False))
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")
    assert _state(w)["assessed"] == {}


def test_2_a_limit_recorded_before_the_lane_started_is_not_stop_evidence(w, monkeypatch):
    _lane(w, "l1", start_age=7200)
    _limit(monkeypatch, _reading(recorded_ago=9000))
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")
    assert not os.path.exists(_state_file(w))


def test_2_a_reading_that_is_not_ok_is_not_stop_evidence(w, monkeypatch):
    _lane(w, "l1")
    _limit(monkeypatch, _reading(ok=False))
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")
    assert not os.path.exists(_state_file(w))


@pytest.mark.parametrize("stamp", [None, 0, 2, True, "1"], ids=["absent", "zero", "two", "bool", "string"])
def test_2_a_lane_without_a_valid_stand_down_stamp_is_not_stopped_by_the_limit(w, monkeypatch, stamp):
    # axis: the limit is stop evidence only for a lane whose premise carries standDown == 1 (an int), the launcher's own rule
    premise = _premise(w, 17)
    premise.pop("standDown")
    if stamp is not None:
        premise["standDown"] = stamp
    _lane(w, "l1", premise=premise)
    _limit(monkeypatch, _reading())
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")
    assert not os.path.exists(_state_file(w))


def test_2_a_lane_with_no_config_dir_never_asks_for_a_reading(w, monkeypatch):
    _lane_without_config(w, "l1")
    _no_limit_call(monkeypatch)
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("unresolved", "session-unread")


def test_2_a_fresh_working_session_is_working_whatever_the_limit(w, monkeypatch):
    _lane(w, "l1")
    _limit(monkeypatch, _reading())
    out = _assess(w, state="working", age=60)
    assert out["verdict"] == "working" and out["evidence"] is None
    assert not os.path.exists(_state_file(w))


def test_2_a_builder_park_newer_than_the_pushed_work_is_parked_whatever_the_limit(w, monkeypatch):
    _lane(w, "l1")
    _pushed_at(w, 1500)
    w.gh.comments = [_comment(PARK, age=600, cid=12)]
    _limit(monkeypatch, _reading())
    out = _assess(w, state="idle")
    assert (out["verdict"], out["evidence"]) == ("parked", "builder-park")
    assert not os.path.exists(_state_file(w))


# ---------------------------------------------------------------- a handed-back lane a fix order reopened


def _handed_back(w, launch_id="l1"):
    _lane(w, launch_id)
    _died(w, launch_id, "handback")


def _relay_fix_order(w, session):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    path, why = cloud_relay._state_path(w.root, os.environ)
    assert why is None
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    pending = {"m1": {"session": session, "forward": "f", "configDir": CFG, "relay": "r", "sentAfter": stamp,
                      "fixOrder": True, "decision": {"delivered": True, "reason": None, "at": stamp}}}
    with open(path, "w") as fh:
        json.dump({"relays": {}, "pending": pending}, fh)


def test_3x_a_handed_back_lane_a_vet_not_ready_reopened_is_stopped_by_the_limit(w, monkeypatch):
    _handed_back(w)
    assert ll.amend(w.root, "l1", "vet", "not-ready", "needs the narrow fix")["ok"] is True
    _limit(monkeypatch, _reading())
    out = _assess(w, state="unread")
    assert out["ok"] is True and (out["verdict"], out["evidence"]) == ("stopped", "account-limited")
    assert _state(w)["assessed"]["l1"]["evidence"] == "account-limited"


def test_3x_a_handed_back_lane_a_fix_order_relay_reopened_is_stopped_by_the_limit(w, monkeypatch):
    _handed_back(w)
    _relay_fix_order(w, "cloud-l1")
    _limit(monkeypatch, _reading())
    out = _assess(w, state="unread")
    assert (out["verdict"], out["evidence"]) == ("stopped", "account-limited")


def test_3x_a_handed_back_lane_no_fix_order_reopened_stays_ended(w, monkeypatch):
    _handed_back(w)
    calls = _limit(monkeypatch, _reading())
    out = _assess(w, state="unread")
    assert out["verdict"] == "ended" and calls == []
    assert not os.path.exists(_state_file(w))


def test_3x_a_fix_order_closed_by_a_later_ready_vet_leaves_the_lane_ended(w, monkeypatch):
    _handed_back(w)
    assert ll.amend(w.root, "l1", "vet", "not-ready", "needs the narrow fix")["ok"] is True
    assert ll.amend(w.root, "l1", "vet", "ready", "fixed")["ok"] is True
    _limit(monkeypatch, _reading())
    assert _assess(w, state="unread")["verdict"] == "ended"


def test_3x_a_reopened_handback_already_replaced_stays_ended(w, monkeypatch):
    _handed_back(w)
    assert ll.amend(w.root, "l1", "vet", "not-ready", "needs the narrow fix")["ok"] is True
    assert CR._record(w.root, "superseded", "l1", {"at": "2026-10-12T10:00:00Z", "branch": None, "sha": None})["ok"]
    _lane(w, "l2")
    _limit(monkeypatch, _reading())
    assert _assess(w, state="unread")["verdict"] == "ended"


def test_3x_a_refusal_outcome_is_never_reopened(w, monkeypatch):
    _lane(w, "l1")
    _died(w, "l1", "refusal")
    assert ll.amend(w.root, "l1", "vet", "not-ready", "needs the narrow fix")["ok"] is True
    _limit(monkeypatch, _reading())
    assert _assess(w, state="unread")["verdict"] == "ended"


# ---------------------------------------------------------------- successor: a branch the lane's own contains


def _commit_branch(w, branch, start, name):
    """Commit `name` on `branch` (created at `start`) in the builder's clone and push it; its head."""
    env = dict(_clean_env(), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    _git(w.builder, "checkout", "-q", "-B", branch, start, env=env)
    with open(os.path.join(w.builder, name + ".txt"), "w") as fh:
        fh.write(name)
    _git(w.builder, "add", ".", env=env)
    _git(w.builder, "commit", "-q", "-m", name, env=env)
    _git(w.builder, "push", "-q", "origin", branch, env=env)
    return _git(w.builder, "rev-parse", "HEAD", env=env)


def _contained_pair(w):
    """The work-order branch's head is the first commit of the lane's own branch: (work-order head, lane head)."""
    wo = _commit_branch(w, WO, w.base, "a")
    return wo, _commit_branch(w, LANE, wo, "b")


def _runner(w, *, pulls=None, pulls_read=None, ancestry=None):
    """`w.gh` with the pull request read per head branch (`pulls`: branch -> pull request numbers), or answered by
    `pulls_read(argv)`; and the ancestry read answered by `ancestry` (an exit code, or "raise") when given."""
    seen = SimpleNamespace(pulls=[], ancestry=[])

    def run(argv, **kw):
        if argv[0] == "gh" and "/pulls?" in argv[-1] and "state=all" in argv[-1]:
            seen.pulls.append(argv[-1])
            if pulls_read is not None:
                return pulls_read(argv)
            head = parse_qs(urlparse(argv[-1]).query)["head"][0]
            owner, _, branch = head.partition(":")
            assert owner == REPO.split("/")[0]
            body = [{"number": n, "head": {"repo": {"full_name": REPO}}} for n in (pulls or {}).get(branch, [])]
            return subprocess.CompletedProcess(argv, 0, json.dumps(body), "")
        if argv[0] == "git" and "merge-base" in argv:
            seen.ancestry.append(list(argv))
            if ancestry == "raise":
                raise OSError("git could not run")
            if ancestry is not None:
                return subprocess.CompletedProcess(argv, ancestry, "", "fatal")
        return w.gh(argv, **kw)

    run.seen = seen
    return run


def _stopped(w, monkeypatch, *, premise=None):
    """Lane l1 assessed stopped on the account's limit, then ended."""
    _lane(w, "l1", premise=premise)
    _limit(monkeypatch, _reading())
    assert _assess(w, state="unread")["evidence"] == "account-limited"
    _died(w, "l1")


def _no_stack(w, **extra):
    premise = dict(_premise(w, 17), **extra)
    premise.pop("layerPosition"), premise.pop("stack")
    return premise


def _refused(w, run):
    got = CR.successor(w.root, "l1", repo=REPO, run=run)
    assert got == {"ok": False, "reason": "pushed-branch-ambiguous"}
    assert _state(w)["superseded"] == {}


def test_3a_the_lanes_branch_with_a_pull_request_is_adopted_and_the_contained_work_order_branch_passed_over(w, monkeypatch):
    wo, head = _contained_pair(w)
    _stopped(w, monkeypatch, premise=_no_stack(w))
    run = _runner(w, pulls={LANE: [5]})
    got = CR.successor(w.root, "l1", repo=REPO, run=run)
    assert got["ok"] is True and got["branch"] == LANE and got["sha"] == head
    assert got["premise"]["adoptsBranch"] == LANE and got["premise"]["adoptsHead"] == head
    assert got["passedOver"] == [{"branch": WO, "sha": wo}]
    assert _state(w)["superseded"]["l1"]["passedOver"] == [{"branch": WO, "sha": wo}]
    assert _state(w)["superseded"]["l1"]["branch"] == LANE
    assert any(a[-2:] == [wo, head] for a in run.seen.ancestry)


def test_3a2_the_branch_the_premise_adopts_is_the_lanes_own_and_no_pull_request_is_read(w, monkeypatch):
    wo, head = _contained_pair(w)
    _stopped(w, monkeypatch, premise=_no_stack(w, adoptsBranch=LANE))
    run = _runner(w)
    got = CR.successor(w.root, "l1", repo=REPO, run=run)
    assert got["ok"] is True and got["branch"] == LANE and got["sha"] == head
    assert got["passedOver"] == [{"branch": WO, "sha": wo}]
    assert run.seen.pulls == []


def test_3b_a_work_order_branch_with_work_found_nowhere_else_refuses(w, monkeypatch):
    _commit_branch(w, WO, w.base, "a")
    _commit_branch(w, LANE, w.base, "b")
    _stopped(w, monkeypatch, premise=_no_stack(w))
    _refused(w, _runner(w, pulls={LANE: [5]}))


def test_3b2_a_work_order_branch_strictly_ahead_of_the_lanes_branch_refuses(w, monkeypatch):
    head = _commit_branch(w, LANE, w.base, "a")
    _commit_branch(w, WO, head, "b")
    _stopped(w, monkeypatch, premise=_no_stack(w))
    _refused(w, _runner(w, pulls={LANE: [5]}))


@pytest.mark.parametrize("later", [
    {"limited": False},                        # the reset passed after the assess
    {"ok": False},                             # the limit can no longer be read
    {"recorded_ago": 9000},                    # the limit on record predates the lane's start
])
def test_3c_an_account_limit_stop_expires_before_the_successor_reads_any_pushed_work(w, monkeypatch, later):
    _stopped(w, monkeypatch, premise=_no_stack(w))
    _limit(monkeypatch, _reading(**later))
    calls = []

    def run(argv, **kw):
        calls.append(list(argv))
        raise AssertionError("no remote read may happen once the stop evidence expired")

    got = CR.successor(w.root, "l1", repo=REPO, run=run, never_pushed_evidence="checked the remote")
    assert got == {"ok": False, "reason": "stop-evidence-expired"} and calls == []
    assert _state(w)["superseded"] == {}


def test_3c_a_limit_that_expires_during_the_pushed_work_read_refuses_before_the_supersession_is_recorded(w, monkeypatch):
    # axis: the limit is read again after the pushed-work reads, so a reset during them never relaunches
    _commit_branch(w, LANE, w.base, "a")
    _stopped(w, monkeypatch, premise=_no_stack(w))
    holds, lapsed = _reading(), _reading(limited=False)
    readings = iter([holds, lapsed])

    def fake(repo_root, config_dir, *, env=None, now=None):
        return next(readings)

    monkeypatch.setattr(cloud_relay, "account_limit", fake, raising=False)
    got = CR.successor(w.root, "l1", repo=REPO, run=_runner(w, pulls={LANE: [5]}))
    assert got == {"ok": False, "reason": "stop-evidence-expired"}
    assert _state(w)["superseded"] == {}


def test_3c_an_account_limit_stop_that_still_holds_is_adopted_and_the_limit_is_reread(w, monkeypatch):
    _commit_branch(w, LANE, w.base, "a")
    _stopped(w, monkeypatch, premise=_no_stack(w))
    calls = _limit(monkeypatch, _reading())
    got = CR.successor(w.root, "l1", repo=REPO, run=_runner(w, pulls={LANE: [5]}))
    assert got["ok"] is True and got["branch"] == LANE
    assert [(c["repo_root"], c["config_dir"]) for c in calls] == [(w.root, CFG), (w.root, CFG)]


# ---------------------------------------------------------------- the builder's stand-down comment as stop evidence


def _stand_down(age, cid=7):
    return _comment(cloud_builder.stand_down_text("https://github.com/o/r/issues/17#issuecomment-9"), age=age, cid=cid)


@pytest.mark.parametrize("age", [500, 9000])
@pytest.mark.parametrize("state", ["idle", "unread"])
def test_5_a_stand_down_comment_is_not_stop_evidence(w, monkeypatch, age, state):
    # a stand-down comment may be an older builder's, posted after a replacement started, so it never stops the lane
    _lane(w, "l1", start_age=7200)
    w.gh.comments = [_stand_down(age)]
    _limit(monkeypatch, _reading(limited=False))
    out = _assess(w, state=state)
    assert out["verdict"] != "stopped" and out["evidence"] != "stand-down"


def test_5_limit_relief_edges():
    ok = {"ok": True, "limited": True, "recordedAt": 100.0}
    stamped = {"standDown": 1}
    assert CR.limit_relief(ok, stamped, 50) is True
    for premise in ({}, None, {"standDown": 0}, {"standDown": 2}, {"standDown": True}, {"standDown": "1"}, {"standDown": 1.0}):
        assert CR.limit_relief(ok, premise, 50) is False
    for reading in (None, "x", {}, dict(ok, ok=False), dict(ok, ok=1), dict(ok, limited=False), dict(ok, limited=1),
                    dict(ok, recordedAt=None), dict(ok, recordedAt=True), dict(ok, recordedAt=float("nan")),
                    dict(ok, recordedAt=float("inf"))):
        assert CR.limit_relief(reading, stamped, 50) is False
    for start in (None, True, "50", float("nan"), float("inf"), 100.0, 101):
        assert CR.limit_relief(ok, stamped, start) is False


def test_3b2_ahead_refuses_even_when_the_premise_names_the_lanes_branch(w, monkeypatch):
    head = _commit_branch(w, LANE, w.base, "a")
    _commit_branch(w, WO, head, "b")
    _stopped(w, monkeypatch, premise=_no_stack(w, adoptsBranch=LANE))
    _refused(w, _runner(w))


@pytest.mark.parametrize("ancestry", [128, 2, "raise"], ids=["exit-128", "exit-2", "git-could-not-run"])
def test_3c_an_ancestry_read_that_fails_refuses(w, monkeypatch, ancestry):
    _contained_pair(w)
    _stopped(w, monkeypatch, premise=_no_stack(w))
    run = _runner(w, pulls={LANE: [5]}, ancestry=ancestry)
    _refused(w, run)
    assert run.seen.ancestry != []


@pytest.mark.parametrize("pulls", [{}, {LANE: [5], WO: [6]}], ids=["no-branch-has-one", "two-branches-have-one"])
def test_3c2_no_single_branch_with_a_pull_request_refuses(w, monkeypatch, pulls):
    _contained_pair(w)
    _stopped(w, monkeypatch, premise=_no_stack(w))
    _refused(w, _runner(w, pulls=pulls))


@pytest.mark.parametrize("answer", [
    lambda argv: subprocess.CompletedProcess(argv, 1, "", "boom"),
    lambda argv: subprocess.CompletedProcess(argv, 0, "not json", ""),
    lambda argv: subprocess.CompletedProcess(argv, 0, '{"number": 5}', ""),
    lambda argv: subprocess.CompletedProcess(argv, 0, '[5]', ""),
], ids=["call-fails", "unparseable", "not-a-list", "not-pull-requests"])
def test_3c2_a_pull_request_read_that_fails_refuses(w, monkeypatch, answer):
    _contained_pair(w)
    _stopped(w, monkeypatch, premise=_no_stack(w))
    _refused(w, _runner(w, pulls_read=answer))


def test_3c3_a_branch_that_could_not_be_read_cleanly_keeps_todays_refusal(w, monkeypatch):
    wo, head = _contained_pair(w)
    _stopped(w, monkeypatch, premise=_no_stack(w, adoptsBranch=LANE))
    entries = [{"branch": LANE, "sha": head, "committedAt": 1, "pushedAt": 1, "pushTimeSource": "push"},
               {"branch": WO, "sha": wo, "reason": "branch-moved-during-read"}]
    monkeypatch.setattr(CR, "pushed", lambda *a, **k: {"ok": True, "issue": 17, "branches": entries,
                                                       "newest": None, "ambiguous": True})
    run = _runner(w)
    _refused(w, run)
    assert run.seen.ancestry == []


def test_3d_a_work_order_branch_at_the_same_head_as_the_lanes_branch_is_passed_over(w, monkeypatch):
    head = _commit_branch(w, LANE, w.base, "a")
    _git(w.builder, "push", "-q", "origin", "%s:refs/heads/%s" % (LANE, WO))
    _stopped(w, monkeypatch, premise=_no_stack(w))
    got = CR.successor(w.root, "l1", repo=REPO, run=_runner(w, pulls={LANE: [5]}))
    assert got["ok"] is True and got["branch"] == LANE and got["sha"] == head
    assert got["passedOver"] == [{"branch": WO, "sha": head}]


def test_3e_a_handover_head_still_names_the_entry_and_passes_nothing_over(w, monkeypatch):
    wo, head = _contained_pair(w)
    _lane(w, "l1", premise=_no_stack(w))
    w.gh.comments = [_comment(cloud_builder.handover_text(wo), age=500, cid=3)]
    _limit(monkeypatch, _reading())
    assert _assess(w, state="idle")["evidence"] == "handover"
    _died(w, "l1")
    run = _runner(w, pulls={LANE: [5]})
    got = CR.successor(w.root, "l1", repo=REPO, run=run)
    assert got["ok"] is True and got["branch"] == WO and got["sha"] == wo
    assert "passedOver" not in got and "passedOver" not in _state(w)["superseded"]["l1"]
    assert run.seen.pulls == [] and run.seen.ancestry == []


def test_3e_a_handover_head_that_names_no_pushed_branch_still_refuses(w, monkeypatch):
    _contained_pair(w)
    _lane(w, "l1", premise=_no_stack(w))
    w.gh.comments = [_comment(cloud_builder.handover_text("e" * 40), age=500, cid=3)]
    assert _assess(w, state="idle")["evidence"] == "handover"
    _died(w, "l1")
    assert CR.successor(w.root, "l1", repo=REPO, run=_runner(w, pulls={LANE: [5]})) == {
        "ok": False, "reason": "handover-head-not-pushed"}


# ---------------------------------------------------------------- the helper read


def test_4_the_helper_read_names_the_four_fields_the_takeover_check_reads_and_no_others():
    got = CR.helper_read(REPO, 17, ["session_abc", "session_d-e_f"])
    assert got["ok"] is True and got["fields"] == FOUR and list(CR.HELPER_READ_FIELDS) == FOUR
    prompt = got["prompt"]
    for name in FOUR:
        assert name in prompt
    for other in ("usage", "cost", "model", "environment_id"):
        assert other not in prompt
    for fragment in ("get_session", "session_abc", "session_d-e_f", "one JSON array in a fenced json block",
                     "issue #17 of " + REPO, "nothing else", "Change, archive or message no session"):
        assert fragment in prompt


@pytest.mark.parametrize("ids", [[], None, "session_a", ["session_a", ""], ["abc"], ["session_"], ["session_a b"],
                                 ["session_a\n"], ["session_a", 5], [None]],
                         ids=["empty", "none", "a-string", "blank", "no-prefix", "bare-prefix", "space", "newline",
                              "non-string", "none-id"])
def test_4_empty_or_malformed_session_ids_are_refused(ids):
    assert CR.helper_read(REPO, 17, ids) == {"ok": False, "reason": "session-ids-invalid"}


def test_4_the_repo_and_the_issue_are_checked_first():
    assert CR.helper_read("not a repo", 17, ["session_a"]) == {"ok": False, "reason": "repo-invalid"}
    assert CR.helper_read(REPO, 0, ["session_a"]) == {"ok": False, "reason": "issue-invalid"}
    assert CR.helper_read(REPO, True, ["session_a"]) == {"ok": False, "reason": "issue-invalid"}


def test_4_the_cli_prints_the_same_json(capsys):
    argv = ["helper-read", "--repo", REPO, "--issue", "17", "--session-id", "session_abc", "--session-id", "session_def"]
    assert CR.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == CR.helper_read(REPO, 17, ["session_abc", "session_def"])
    assert CR.main(["helper-read", "--repo", REPO, "--issue", "17", "--session-id", "bad"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "session-ids-invalid"}
    assert CR.main(["helper-read", "--repo", REPO, "--issue", "17"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "usage"}
