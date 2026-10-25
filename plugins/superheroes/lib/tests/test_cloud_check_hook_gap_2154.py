"""Tests for #2154: the cloud check fails on a stale committed dependency hook, and the gap and its
fix reach the owner-facing words (the check's message, the place call, the launch report).

The fixture world is the real-git one of test_cloud_branch_hook_2021 (every git call pins its global
and system configuration away and passes its identity inline; every store and home is under
tmp_path). No test reads the real home directory or the network.
"""
import os
import sys
from datetime import datetime, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import cloud_check as CC  # noqa: E402
import cloud_dependency_hook as hook  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_setup_text  # noqa: E402
import launch_place  # noqa: E402
import launch_report  # noqa: E402
import store_core  # noqa: E402
import test_cloud_branch_hook_2021 as T  # noqa: E402
import test_launch_report as TLR  # noqa: E402

ENV_ID = "env_01ABCdef"
NONCE = "abcd1234efgh"
FAR = "2099-12-31"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc).timestamp()
CHECK_AGAIN = 'Then say "check again".'


def _report_line(w):
    """The check session's report for the fixture project itself, so every other part matches."""
    obj = CC.report(env={cloud_pass.ENVIRONMENT_ENV: ENV_ID}, cwd=w.cwd, root=w.root, nonce=NONCE,
                    confirm_fn=lambda env: {"schema": cloud_pass.CONFIRMATION_SCHEMA,
                                            "reviewerAnswered": True, "passLapses": FAR,
                                            "reason": None},
                    identity_fn=lambda cwd: {"author": True, "committer": True})
    # the fixture's calibration is a global one with no placed stamp file, so the file is the stamp
    obj["stampFile"] = obj["placedStamp"]
    return CC.report_line(obj)


def _judge(w, line=None):
    return CC.judge(w.cwd, _report_line(w) if line is None else line, environment=ENV_ID,
                    nonce=NONCE, account=T.ACCOUNT, root=w.root, env=w.env, now=NOW,
                    project_name="demo")


def _commit_script(w, text):
    w.script.write_text(text)
    return T._commit(w.cwd, "script bytes")


def _commit_settings(w, text):
    w.settings.write_text(text)
    return T._commit(w.cwd, "settings")


def _refused(*a, **k):
    raise cloud_setup_text._Refused("setup-commands-unreadable", "x")


def _unavailable(*a, **k):
    raise store_core.RepoRootUnavailable("no repository")


def _boom(*a, **k):
    raise RuntimeError("boom")


def _stale(w, monkeypatch, gap):
    """Makes the checkout's HEAD (or the hook test itself) read as `gap`."""
    if gap == "script-missing":
        T._drop_hook_files(w)
    elif gap == "script-differs":
        _commit_script(w, "#!/bin/bash\necho an older plugin's hook\n")
    elif gap == "settings-not-registered":
        _commit_settings(w, "{}\n")
    elif gap == "commit-unreadable":
        monkeypatch.setattr(store_core, "repo_root", _unavailable)
    elif gap == "settings-unreadable":
        monkeypatch.setattr(cloud_setup_text, "branch_hook_gap", _refused)
    else:
        raise AssertionError(gap)


GAPS = ("script-missing", "script-differs", "settings-not-registered", "commit-unreadable",
        "settings-unreadable")


# ---------------------------------------------------------------- the judge


@pytest.mark.parametrize("gap", GAPS)
def test_judge_fails_on_the_hook_part_with_the_gap_and_its_fix(tmp_path, monkeypatch, gap):
    w, bare, with_hook = T._hooked(tmp_path)
    line = _report_line(w)
    _stale(w, monkeypatch, gap)
    result = _judge(w, line)
    assert result["action"] == "failed", result
    assert "hook" in result["failedParts"]
    assert result["results"]["dependencyHookMatches"] is False
    assert result["dependencyHookGap"] == gap
    assert result["recordWritten"] is False
    sentence, fix = hook.GAP_TEXT[gap]
    assert "(`%s`): %s." % (gap, sentence) in result["message"]
    assert fix in result["message"]
    assert result["message"].endswith('and say "check again".')


def test_judge_failure_leaves_a_marker_carrying_the_hook_part(tmp_path, monkeypatch):
    w, bare, with_hook = T._hooked(tmp_path)
    line = _report_line(w)
    T._drop_hook_files(w)
    assert "hook" in _judge(w, line)["failedParts"]
    marker = CC.read_failed_check(w.cwd, T.ACCOUNT, w.root)
    assert marker is not None and "hook" in marker["failedParts"]


def test_judge_gives_an_unexpected_failure_in_the_hook_test_as_commit_unreadable(
        tmp_path, monkeypatch):
    w, bare, with_hook = T._hooked(tmp_path)
    line = _report_line(w)
    monkeypatch.setattr(cloud_setup_text, "branch_hook_gap", _boom)
    result = _judge(w, line)
    assert result["action"] == "failed" and "hook" in result["failedParts"]
    assert result["dependencyHookGap"] == "commit-unreadable"
    assert result["results"]["dependencyHookMatches"] is False


def test_judge_with_the_hook_off_passes_and_reads_no_gap(tmp_path):
    w = T._world(tmp_path)
    T._lock(w)
    T._set_ok(w, T.COMMANDS_SLUG, list(T.COMMANDS))
    T._commit(w.cwd, "bare")
    result = _judge(w)
    assert result["action"] == "passed", result
    assert result["results"]["dependencyHookMatches"] is True
    assert result["dependencyHookGap"] is None


def test_judge_with_a_matching_committed_hook_passes(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)
    result = _judge(w)
    assert result["action"] == "passed", result
    assert result["results"]["dependencyHookMatches"] is True
    assert result["dependencyHookGap"] is None
    assert result["failedParts"] == []


def test_judge_unread_report_carries_the_hook_keys_as_none(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)
    result = _judge(w, "not a report")
    assert result["action"] == "unread"
    assert result["results"]["dependencyHookMatches"] is None
    assert result["dependencyHookGap"] is None


# ---------------------------------------------------------------- readiness


def test_a_failed_check_marker_with_the_hook_part_forces_only_the_hook_condition(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)
    assert T._ready(w)["ready"] is True
    assert CC._write_failed_check(w.cwd, T.ACCOUNT, w.root, ENV_ID, ["hook"], NOW)
    got = T._ready(w)
    assert got["ready"] is False and got["reason"] == "dependency-hook"
    assert got["failedCheck"] == ["hook"]
    assert got["conditions"]["dependencyHook"] is False
    assert all(got["conditions"][name] is True for name in T.OTHERS)
    assert got["conditions"]["setup"] is True


def test_readiness_reports_the_gap_token_on_a_hookless_head(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)
    assert T._ready(w)["dependencyHookGap"] is None
    T._drop_hook_files(w)
    got = T._ready(w)
    assert got["dependencyHookGap"] == "script-missing"
    assert got["conditions"]["dependencyHook"] is False


# ---------------------------------------------------------------- the place call and the words


def _hook_call(**over):
    call = {"place": "local", "pointedAtCloud": True, "by": "word", "reason": "dependency-hook",
            "need": None, "cloudVersion": None, "advisorVersion": None, "environment": None,
            "reported": None, "failedCheck": None, "hookGap": None}
    call.update(over)
    return call


def test_route_on_a_base_commit_lacking_the_hook_carries_the_gap_into_the_words(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)
    T._record_for_routing(w)
    call = T._account_route(w, {"baseCommit": bare})
    assert call["place"] == "local" and call["reason"] == "dependency-hook"
    assert call["hookGap"] == "script-missing"
    assert "`script-missing`" in launch_place.reason_text(call)
    assert "`script-missing`" in launch_place.wasnt_text(call)
    report = launch_report.render_report([{"issue": 1, "title": "t", "placeCall": call}])
    assert "`script-missing`" in report
    assert hook._REWRITE_FIX in report


def test_a_cloud_placement_carries_no_gap(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)
    T._record_for_routing(w)
    call = T._account_route(w, {"baseCommit": with_hook})
    assert call["place"] == "cloud" and call["hookGap"] is None


def test_a_reason_other_than_the_dependency_hook_never_carries_a_gap(tmp_path):
    w, bare, with_hook = T._hooked(tmp_path)

    def fake(cwd, reported=None, root=None, env=None):
        return {"ready": False, "reason": "version", "setting": True, "environment": "e",
                "dependencyHookGap": "script-missing"}

    call = T._account_route(w, {}, readiness_fn=fake)
    assert call["reason"] == "version" and call["hookGap"] is None


def test_a_dependency_hook_call_with_no_gap_keeps_the_generic_words():
    call = _hook_call()
    reasons = launch_place.REASONS["dependency-hook"]
    assert launch_place.reason_text(call) == reasons["words"]
    assert launch_place.fix_text(call) == reasons["fix"]
    assert launch_place.wasnt_text(call) == reasons["wasnt"]


@pytest.mark.parametrize("gap", ["not-a-known-token", None, 7])
def test_an_unknown_gap_token_keeps_the_generic_words(gap):
    call = _hook_call(hookGap=gap)
    reasons = launch_place.REASONS["dependency-hook"]
    assert launch_place.reason_text(call) == reasons["words"]
    assert launch_place.fix_text(call) == reasons["fix"]
    assert launch_place.wasnt_text(call) == reasons["wasnt"]


def test_a_gap_on_another_reason_is_ignored_by_the_words():
    call = _hook_call(reason="version", hookGap="script-missing", cloudVersion="1.0.0",
                      advisorVersion="2.0.0")
    assert launch_place.reason_text(call) == "The cloud's plugin is 1.0.0 and mine is 2.0.0."
    assert launch_place.wasnt_text(call) == "its plugin is 1.0.0 and mine is 2.0.0."


def test_wasnt_text_gives_none_for_an_unknown_reason():
    assert launch_place.wasnt_text(_hook_call(reason="nonsense")) is None
    assert launch_place.wasnt_text(None) is None


@pytest.mark.parametrize("gap", [None, "script-missing"])
def test_a_failed_hook_part_adds_check_again_to_the_fix(gap):
    base = launch_place.fix_text(_hook_call(hookGap=gap))
    got = launch_place.fix_text(_hook_call(hookGap=gap, failedCheck=["hook"]))
    assert got == base + launch_place._CHECK_AGAIN_SUFFIX
    assert got.endswith(CHECK_AGAIN)


@pytest.mark.parametrize("gap", [None, "script-missing"])
def test_another_failed_part_adds_no_check_again_to_the_dependency_hook_fix(gap):
    base = launch_place.fix_text(_hook_call(hookGap=gap))
    assert launch_place.fix_text(_hook_call(hookGap=gap, failedCheck=["calibration"])) == base
    assert not base.endswith(CHECK_AGAIN)


def test_the_gap_fix_names_the_gap_step():
    sentence, fix = hook.GAP_TEXT["adopted-inputs-differ"]
    got = launch_place.fix_text(_hook_call(hookGap="adopted-inputs-differ"))
    assert got == "To fix it, %s. Then launch again." % fix


def test_two_lanes_with_different_gaps_print_both_fixes():
    lanes = [
        {"issue": 1, "title": "a", "placeCall": _hook_call(hookGap="script-missing")},
        {"issue": 2, "title": "b", "placeCall": _hook_call(hookGap="adopted-inputs-differ")},
    ]
    report = launch_report.render_report(lanes)
    for gap in ("script-missing", "adopted-inputs-differ"):
        assert "`%s`" % gap in report
        assert launch_place.fix_text(_hook_call(hookGap=gap)) in report


def test_two_lanes_with_one_gap_print_the_fix_once():
    lanes = [
        {"issue": 1, "title": "a", "placeCall": _hook_call(hookGap="script-missing")},
        {"issue": 2, "title": "b", "placeCall": _hook_call(hookGap="script-missing")},
    ]
    report = launch_report.render_report(lanes)
    fix = launch_place.fix_text(_hook_call(hookGap="script-missing"))
    assert report.count(fix) == 1
    assert "`script-missing`" in report


def test_a_plain_and_a_failed_lane_with_one_reason_print_only_the_recheck_fix():
    plain = TLR._call(reason="calibration")
    failed = dict(TLR._call(reason="calibration", by="word"), failedCheck=["calibration"])
    third = TLR._call(reason="no-setup", pointed=True)
    recheck = TLR.SETUP_TEXT_FIX + " " + CHECK_AGAIN
    report = launch_report.render_report([TLR._lane(1, failed), TLR._lane(2, third),
                                          TLR._lane(3, plain)])
    assert report.endswith(recheck)
    assert report.count(TLR.SETUP_TEXT_FIX) == 1


def test_one_gap_with_a_failed_hook_part_prints_only_the_recheck_fix():
    lanes = [
        {"issue": 1, "title": "a",
         "placeCall": _hook_call(hookGap="script-differs", failedCheck=["hook"])},
        {"issue": 2, "title": "b", "placeCall": _hook_call(hookGap="script-differs")},
        TLR._lane(3, TLR._call("cloud")),
    ]
    report = launch_report.render_report(lanes)
    recheck = launch_place.fix_text(_hook_call(hookGap="script-differs", failedCheck=["hook"]))
    plain = launch_place.fix_text(_hook_call(hookGap="script-differs"))
    assert recheck.endswith(CHECK_AGAIN)
    assert report.endswith(recheck)
    assert report.count(plain) == 1


def test_a_ledger_gap_that_is_not_a_string_still_renders_the_report():
    lanes = [
        {"issue": 1, "title": "a", "placeCall": _hook_call(hookGap=["script-missing"])},
        TLR._lane(2, TLR._call("cloud")),
    ]
    report = launch_report.render_report(lanes)
    assert isinstance(report, str)
    assert launch_place.REASONS["dependency-hook"]["fix"] in report
