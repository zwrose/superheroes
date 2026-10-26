# plugins/superheroes/lib/tests/test_launch_report.py
"""Conformance: the launch report, and the rules the "Still on your machine" line shares with it (the line
itself is tested from a ledger in test_launch_report_verbs.py). Every store, account file,
repository and record is built under tmp_path; no test touches the real home directory, clock,
clipboard or network. Requirement numbers in the test names are for the reader."""
import datetime
import functools
import json
import os
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_check as CC  # noqa: E402
import cloud_ready as CR  # noqa: E402
import cloud_setup as CS  # noqa: E402
import core_md as CM  # noqa: E402
import launch_place as LP  # noqa: E402
import launch_report as LR  # noqa: E402
import project_config as PC  # noqa: E402

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

ACCOUNT = "acct-fixture-one"
ENVIRONMENT = "env-fixture-one"
STAMP = "sha256:" + "ab" * 32
ADVISOR = "1.2.3"
TODAY = datetime.date(2026, 10, 11)
FUTURE = "2026-12-01"
PAST = "2026-10-10"
PHONE = "the phone simulator"
SETUP_TEXT_FIX = ('To fix it, paste the new setup text into the environment. '
                  'Say "setup text" and I\'ll write it.')


def _now(ready=True, reason=None, setting=True, cloud=ADVISOR, advisor=ADVISOR,
         environment=ENVIRONMENT, checked=None, conditions=None):
    if conditions is None:
        conditions = {name: True for name in CR.CONDITION_ORDER}
        for name, code in CR.REASON_FOR.items():
            if code == reason:
                conditions[name] = False
    return {"ready": ready, "reason": reason, "conditions": conditions, "setting": setting,
            "account": ACCOUNT, "environment": environment, "cloudVersion": cloud,
            "advisorVersion": advisor, "picksUpVersion": False, "checkedAt": checked}


def _fn(**kw):
    def readiness(cwd, reported=None, root=None, env=None):
        return _now(**kw)
    return readiness


def _no_needs(cwd, premise, root=None):
    return []


def _call(place="local", pointed=True, reason=None, by="setting", need=None, cloud=None,
          advisor=None, environment=None, reported=None):
    return {"place": place, "pointedAtCloud": pointed, "by": by, "reason": reason, "need": need,
            "cloudVersion": cloud, "advisorVersion": advisor, "environment": environment,
            "reported": reported}


def _lane(issue, call, title="auto"):
    return {"issue": issue, "title": "Build %d" % issue if title == "auto" else title,
            "placeCall": call}


# ---------------------------------------------------------------- fixtures: stores and worlds


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _setup_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def _record(repo, store, **over):
    values = {
        "account": ACCOUNT, "environment": ENVIRONMENT, "plugin_version": ADVISOR,
        "picks_up_version": False, "calibration_stamp": STAMP,
        "calibration_date": "2026-10-01", "pass_lapses": FUTURE, "checked_at": "2026-10-09",
    }
    values.update(over)
    got = CS.record_check(repo, root=store, **values)
    assert got["action"] in ("written", "noop"), got
    return got


def _account_env(tmp_path, account=ACCOUNT):
    home = tmp_path / ("home-" + account)
    home.mkdir(exist_ok=True)
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": account}}), encoding="utf-8")
    return {"HOME": str(home)}


def _on(tmp_path, **over):
    """A project with a passed check, cloud builds switched on, and the account's environment."""
    repo, store = _setup_repo(tmp_path)
    _record(repo, store, **over)
    assert PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)["action"] == "written"
    return repo, store, _account_env(tmp_path)


def _real(**over):
    args = {"advisor_version": ADVISOR, "today": TODAY, "stamp_fn": lambda cwd, root: STAMP}
    args.update(over)
    return functools.partial(CR.readiness, **args)


def _route(repo, store, env, premise=None, word=None, **kw):
    kw.setdefault("readiness_fn", _real())
    kw.setdefault("needs_fn", _no_needs)
    return LP.route(repo, premise if premise is not None else {}, word, root=store, env=env, **kw)


# ---------------------------------------------------------------- the launch report


BOARD_SUMMARY = (
    "Launched 4 builds, all on your machine. The cloud wasn't ready: its plugin is 0.41.0 and "
    "mine is 0.42.0.\n"
    'To fix it, paste the new setup text into the environment. Say "setup text" and I\'ll write it.')

BOARD_LIST = "\n".join([
    "Launched 5 builds.",
    "In the cloud: #412 Fix the export date format, #413 Add a low-stock badge, "
    "#417 Tidy the receipt email.",
    "On your machine:",
    "- #415 Phone checkout layout. It needs the phone simulator, which only your machine has.",
    '- #418 Speed up the orders list. You said "this one local".',
])

def _board_lanes():
    cloud = _call("cloud", environment=ENVIRONMENT)
    return [
        _lane(412, cloud, "Fix the export date format"),
        _lane(413, cloud, "Add a low-stock badge"),
        _lane(415, _call(reason="needs", need=PHONE), "Phone checkout layout"),
        _lane(417, cloud, "Tidy the receipt email"),
        _lane(418, _call(reason="local-word"), "Speed up the orders list"),
    ]


def test_R_board_the_two_launch_reports_are_byte_exact():
    version = _call(reason="version", cloud="0.41.0", advisor="0.42.0")
    four = [_lane(400 + i, version) for i in range(4)]
    assert LR.render_report(four) == BOARD_SUMMARY
    assert LR.render_report(_board_lanes()) == BOARD_LIST


def test_a_report_is_given_only_when_cloud_builds_are_on_or_a_launch_went_to_the_cloud():
    quiet = _call(pointed=False, by=None)
    assert LR.render_report([]) is None
    assert LR.render_report([_lane(1, quiet), _lane(2, quiet)]) is None
    assert LR.render_report([_lane(1, _call("cloud"))]) == (
        "Launched 1 build.\nIn the cloud: #1 Build 1.")
    word = _call("cloud", by="word")
    assert LR.render_report([_lane(1, word), _lane(2, quiet)]) is not None
    assert LR.render_report([_lane(1, _call(reason="local-word")), _lane(2, quiet)]) is not None


def test_a_lane_label_is_the_issue_and_its_title_when_it_has_one():
    cloud = _call("cloud")
    for title in (None, "", "   "):
        assert LR.render_report([_lane(7, cloud, title)]) == "Launched 1 build.\nIn the cloud: #7."
    assert LR.render_report([_lane(7, cloud, "  Padded title ")]) == (
        "Launched 1 build.\nIn the cloud: #7 Padded title.")


def test_the_summary_form_needs_one_shared_reason_with_the_same_words():
    lapsed = _call(reason="pass-lapsed")
    one = LR.render_report([_lane(1, lapsed)])
    assert one.startswith("Launched 1 build, all on your machine. The cloud wasn't ready: ")
    same_code_apart = [_lane(1, _call(reason="version", cloud="1", advisor="2")),
                       _lane(2, _call(reason="version", cloud="3", advisor="2"))]
    assert LR.render_report(same_code_apart).startswith("Launched 2 builds.\nOn your machine:\n")
    different = [_lane(1, lapsed), _lane(2, _call(reason="no-pass"))]
    assert LR.render_report(different).startswith("Launched 2 builds.\n")
    with_cloud = [_lane(1, lapsed), _lane(2, _call("cloud"))]
    assert LR.render_report(with_cloud).startswith("Launched 2 builds.\nIn the cloud: #2 Build 2.")
    unpointed = [_lane(1, lapsed), _lane(2, _call(pointed=False, by=None, reason=None))]
    assert LR.render_report(unpointed).startswith("Launched 2 builds.\n")
    non_fix = [_lane(1, _call(reason="needs", need=PHONE)), _lane(2, _call(reason="needs",
                                                                          need=PHONE))]
    assert LR.render_report(non_fix).startswith("Launched 2 builds.\n")


def test_a_local_lane_with_no_reason_is_listed_alone():
    lanes = [_lane(1, _call("cloud")), _lane(2, _call(pointed=False, by=None, reason=None), "Quiet")]
    assert LR.render_report(lanes) == (
        "Launched 2 builds.\nIn the cloud: #1 Build 1.\nOn your machine:\n- #2 Quiet.")


def test_the_list_form_adds_one_fix_per_distinct_reason_in_condition_order():
    lanes = [
        _lane(1, _call(reason="unreachable")),
        _lane(2, _call(reason="version", cloud="1.0.0", advisor="2.0.0")),
        _lane(3, _call(reason="no-pass")),
        _lane(4, _call(reason="unreachable")),
        _lane(5, _call(reason="no-setup")),
        _lane(6, _call(reason="pass-lapsed")),
        _lane(7, _call("cloud")),
    ]
    report = LR.render_report(lanes).split("\n")
    fixes = [LP.REASONS[code]["fix"] for code in
             ("no-setup", "no-pass", "pass-lapsed", "version", "unreachable")]
    assert report[-5:] == fixes
    assert report[0] == "Launched 7 builds."
    assert report[1] == "In the cloud: #7 Build 7."
    assert report[2] == "On your machine:"
    assert len(report) == 3 + 6 + 5


def test_a_fix_shared_by_two_reasons_is_given_once():
    lanes = [_lane(1, _call(reason="version", cloud="1.0.0", advisor="2.0.0")),
             _lane(2, _call(reason="calibration")), _lane(3, _call("cloud"))]
    report = LR.render_report(lanes)
    assert report.count(SETUP_TEXT_FIX) == 1


def test_a_report_has_no_trailing_newline_and_never_raises():
    assert not LR.render_report(_board_lanes()).endswith("\n")
    assert LR.render_report([{"nonsense": True}]) is None
    assert LR.render_report(None) is None


def test_R_FR37_a_cloud_that_does_not_pick_up_the_version_gets_the_setup_text_fix(tmp_path):
    repo, store, env = _on(tmp_path, plugin_version="1.2.2", picks_up_version=False)
    call = _route(repo, store, env)
    assert call["place"] == "local" and call["reason"] == "version"
    report = LR.render_report([_lane(1, call, "Fix it")])
    assert report.endswith(SETUP_TEXT_FIX)


# ---------------------------------------------------------------- one reason, from one table


def _fragments(code, cloud="0.41.0", advisor="0.42.0", need=PHONE):
    return {key: (None if text is None else LP._fill(text, cloud, advisor, need))
            for key, text in LP.REASONS[code].items()}


def _every_output():
    """(code, shape, text) for every string reason_text and render_report can make."""
    outputs = []
    for code in LP.REASON_CODES:
        call = _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                     need=PHONE if code == "needs" else None)
        outputs.append((code, "text", LP.reason_text(call)))
        outputs.append((code, "list", LR.render_report([_lane(1, call), _lane(2, _call("cloud"))])))
        outputs.append((code, "mixed", LR.render_report([_lane(1, call), _lane(2, _call(
            reason="local-word"))])))
        outputs.append((code, "summary", LR.render_report([_lane(1, call), _lane(2, call)])))
    return outputs


def test_R_eight_every_string_is_drawn_from_the_table():
    seen = set()
    for code, shape, text in _every_output():
        assert isinstance(text, str), (code, shape)
        parts = _fragments(code)
        others = [_fragments(other) for other in LP.REASON_CODES if other != code]
        if shape == "mixed":
            assert parts["words"] in text and LP.REASONS["local-word"]["words"] in text
        if shape in ("text", "list"):
            assert text.count(parts["words"]) >= 1, (code, shape, text)
            for other in others:
                assert other["words"] not in text, (code, shape, other["words"])
        if shape == "summary" and code in LP.NOT_READY_CODES:
            assert text.count(parts["wasnt"]) == 1
            assert parts["fix"] in text.split("\n")
            for other in others:
                assert other["wasnt"] is None or other["wasnt"] not in text
                assert other["words"] not in text
        if shape == "list" and code in LP.NOT_READY_CODES:
            assert parts["fix"] in text.split("\n")
        if shape == "text":
            assert text == parts["words"]
        seen.add((code, shape))
    assert {code for code, _ in seen} == set(LP.REASON_CODES)
    assert {shape for _, shape in seen} == {"text", "list", "mixed", "summary"}


def test_R_eight_every_line_of_a_report_is_scaffolding_or_a_table_fragment(tmp_path):
    allowed_fixes = {LP._fill(LP.REASONS[c]["fix"], "1", "2") for c in LP.NOT_READY_CODES}
    for code in LP.REASON_CODES:
        call = _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                     need=PHONE if code == "needs" else None)
        words = LP.reason_text(call)
        report = LR.render_report([_lane(1, call), _lane(2, _call("cloud"))])
        for line in report.split("\n"):
            assert (line.startswith("Launched ") or line.startswith("In the cloud: ")
                    or line == "On your machine:" or line in allowed_fixes
                    or line == "- #1 Build 1. " + words), (code, line)


# ---------------------------------------------------------------- the recheck step in the report


def _ends_with_fix_then(report, fix, status):
    """The fix line, then the status line, are the last two lines of the report."""
    assert report.split("\n")[-2:] == [fix, status], report


def test_a_failed_check_keeps_its_recheck_step_in_the_report():
    call = dict(_call(reason="calibration"), failedCheck=["calibration"])
    recheck = SETUP_TEXT_FIX + ' Then say "check again".'
    _ends_with_fix_then(LR.render_report([_lane(1, call)]), recheck, CS.PAUSED_LINE_ON)
    _ends_with_fix_then(LR.render_report([_lane(1, call), _lane(2, _call("cloud"))]), recheck,
                        CS.PAUSED_LINE_ON)


def test_a_failed_check_after_an_ordinary_fallback_keeps_its_recheck_step():
    plain = _call(reason="calibration")
    failed = dict(_call(reason="calibration", by="word"), failedCheck=["calibration"])
    recheck = SETUP_TEXT_FIX + ' Then say "check again".'
    _ends_with_fix_then(LR.render_report([_lane(1, plain), _lane(2, failed)]), recheck,
                        CS.PAUSED_LINE_WORD)
    assert LR.render_report([_lane(1, plain), _lane(2, plain)]).endswith(SETUP_TEXT_FIX)
    third = _call(reason="no-setup", pointed=True)
    _ends_with_fix_then(LR.render_report([_lane(1, plain), _lane(2, third), _lane(3, failed)]),
                        recheck, CS.PAUSED_LINE_WORD)
    same = _call(reason="calibration")
    _ends_with_fix_then(
        LR.render_report([_lane(1, same), _lane(2, dict(same, failedCheck=["calibration"]))]),
        recheck, CS.PAUSED_LINE_ON)


def test_the_paused_line_is_appended_once_in_both_forms_and_never_when_nothing_was_paused():
    failed = dict(_call(reason="calibration"), failedCheck=["calibration"])
    summary = LR.render_report([_lane(1, failed), _lane(2, failed)])
    listed = LR.render_report([_lane(1, failed), _lane(2, _call("cloud"))])
    for report in (summary, listed):
        assert report.count(CS.PAUSED_LINE_ON) == 1 and report.endswith(CS.PAUSED_LINE_ON)
        assert "switched" not in report and CS.PAUSED_RESUME in report
    assert summary.startswith("Launched 2 builds, all on your machine. The cloud wasn't ready: ")
    # a fallback that did not come from a failed check carries no paused line
    assert "paused" not in LR.render_report([_lane(1, _call(reason="calibration")),
                                             _lane(2, _call("cloud"))])
    # a failed check beside a build the cloud was not meant for adds nothing
    unpointed = dict(_call(pointed=False, by=None, reason=None), failedCheck=["calibration"])
    assert "paused" not in LR.render_report([_lane(1, unpointed), _lane(2, _call("cloud"))])
    # the setting line when any paused call was pointed by the setting, else the word line
    by_word = dict(_call(reason="calibration", by="word"), failedCheck=["calibration"])
    assert LR.render_report([_lane(1, by_word)]).endswith(CS.PAUSED_LINE_WORD)
    assert LR.render_report([_lane(1, by_word), _lane(2, failed)]).endswith(CS.PAUSED_LINE_ON)


def test_a_no_setup_placement_from_a_failed_check_reads_in_the_paused_words_in_the_report():
    call = dict(_call(reason="no-setup"), failedCheck=["reviewer"])
    report = LR.render_report([_lane(1, call)])
    assert report == (
        "Launched 1 build, all on your machine. The cloud wasn't ready: this account's last "
        "setup check failed on the reviewer pass.\n"
        'To fix it, paste a fresh pass into the environment, then say "check again".\n'
        + CS.PAUSED_LINE_ON)
    assert "no cloud setup" not in report


@pytest.mark.parametrize("reason,reported", [
    ("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
    ("version", {"pluginVersion": "0.41.0"}),
])
def test_E4_a_fallback_with_no_start_date_is_never_fixed_by_the_later_day_leg(reason, reported):
    candidate = {"reason": reason, "by": "setting", "cloudVersion": None, "advisorVersion": None,
                 "reported": reported, "failedCheck": None, "observedOn": None}
    for checked in (None, "2026-10-10", "2026-10-11", "2026-12-01", "garbage"):
        assert LR._fixed(candidate, _now(ready=True, checked=checked)) is False, checked
    dated = dict(candidate, observedOn="2026-10-11")
    assert LR._fixed(dated, _now(ready=True, checked="2026-10-12")) is True


PIN_WORDS = ("The plugin pin on the branch this build starts from doesn't name the plugin I run, "
             "or its pin hook is broken.")
PIN_FIX = ("To fix it, run cloud_plugin_pin.py write on this machine (it pins the plugin I run), "
           "commit and push the files it names on the branch the build starts from, then launch "
           "again.")


def test_the_plugin_pin_reason_renders_its_words_its_wasnt_and_its_fix():
    call = _call(reason="plugin-pin")
    listed = LR.render_report([_lane(1, call), _lane(2, _call("cloud"))])
    assert "- #1 Build 1. " + PIN_WORDS in listed.splitlines()
    assert listed.endswith(PIN_FIX)
    summary = LR.render_report([_lane(1, call), _lane(2, call)])
    assert summary == (
        "Launched 2 builds, all on your machine. The cloud wasn't ready: the plugin pin on the "
        "branch it starts from doesn't name my plugin.\n" + PIN_FIX)


def test_after_a_failed_check_the_plugin_pin_fix_in_the_report_asks_for_the_check_again():
    call = dict(_call(reason="plugin-pin"), failedCheck=["pin"])
    _ends_with_fix_then(LR.render_report([_lane(1, call)]), PIN_FIX + ' Then say "check again".',
                        CS.PAUSED_LINE_ON)
    _ends_with_fix_then(LR.render_report([_lane(1, call), _lane(2, _call("cloud"))]),
                        PIN_FIX + ' Then say "check again".', CS.PAUSED_LINE_ON)


def test_a_plugin_pin_fallback_clears_when_readiness_reads_the_pin_current_again():
    candidate = {"reason": "plugin-pin", "by": "setting", "cloudVersion": None,
                 "advisorVersion": None, "reported": None, "failedCheck": None, "observedOn": None}
    stands = _now(ready=False, reason="plugin-pin")
    assert stands["conditions"]["pluginPin"] is False
    assert LR._fixed(candidate, stands) is False
    # axis: a plugin-pin fallback clears from the pluginPin condition alone, with no later check
    fixed = dict(stands, conditions=dict(stands["conditions"], pluginPin=True))
    assert LR._fixed(candidate, fixed) is True
    other = dict(stands, conditions=dict(stands["conditions"], pluginPin=False, version=True))
    assert LR._fixed(candidate, other) is False


def test_a_report_renders_the_need_a_routing_result_carries():
    phone = _call(reason="needs", need=PHONE)
    canon = _call(reason="needs", need="this project's Canon and specs")
    got = LR.render_report([_lane(415, phone, title="Phone checkout layout"), _lane(416, canon)])
    lines = got.splitlines()
    assert "- #415 Phone checkout layout. It needs the phone simulator, which only your machine has." in lines
    assert ("- #416 Build 416. It needs this project's Canon and specs, "
            "which only your machine has.") in lines


# ---------------------------------------------------------------- a failed check pauses the account


def _fail_the_check(repo, store, parts):
    marker = {"schema": CC.FAILED_CHECK_SCHEMA, "account": ACCOUNT, "environment": ENVIRONMENT,
              "failedAt": "2026-10-10T00:00:00Z", "failedParts": parts}
    path = CC.failed_check_path(repo, ACCOUNT, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(marker, fh)


def test_T7_a_cloud_word_beside_a_failed_check_carries_the_word_line_with_the_setting_on(tmp_path):
    repo, store, env = _on(tmp_path)
    _fail_the_check(repo, store, ["reviewer"])
    call = _route(repo, store, env, word="cloud")
    assert call["place"] == "local" and call["by"] == "word" and call["failedCheck"] == ["reviewer"]
    report = LR.render_report([_lane(1, call)])
    assert report.endswith(CS.PAUSED_LINE_WORD) and CS.PAUSED_LINE_ON not in report
    assert "switched" not in report


def test_T7_a_cloud_word_beside_a_failed_check_carries_the_word_line_with_the_setting_off(tmp_path):
    repo, store, env = _on(tmp_path)
    assert PC.set_item(repo, "cloudBuilds", False, root=store)["action"] == "written"
    _fail_the_check(repo, store, ["reviewer"])
    call = _route(repo, store, env, word="cloud")
    assert call["place"] == "local" and call["by"] == "word" and call["failedCheck"] == ["reviewer"]
    report = LR.render_report([_lane(1, call)])
    assert report.endswith(CS.PAUSED_LINE_WORD) and CS.PAUSED_LINE_ON not in report
    # the setting off and no cloud word: the build was never pointed at the cloud, so no report
    quiet = _route(repo, store, env)
    assert quiet["pointedAtCloud"] is False and LR.render_report([_lane(1, quiet)]) is None


def test_T7_the_setting_on_with_no_word_carries_the_on_line(tmp_path):
    repo, store, env = _on(tmp_path)
    _fail_the_check(repo, store, ["reviewer"])
    call = _route(repo, store, env)
    assert call["by"] == "setting"
    report = LR.render_report([_lane(1, call)])
    assert report.endswith(CS.PAUSED_LINE_ON) and CS.PAUSED_LINE_WORD not in report


def test_a_failed_check_fallback_clears_once_the_marker_is_gone_and_its_condition_reads_true():
    candidate = {"reason": "no-pass", "by": "setting", "cloudVersion": None, "advisorVersion": None,
                 "reported": None, "failedCheck": ["reviewer"], "observedOn": "2026-10-11"}
    passed_same_day = _now(ready=True, checked="2026-10-11")
    passed_same_day["failedCheck"] = None
    # axis: a fallback that came from a failed check is fixed once a passing check has cleared the marker and its condition reads true now, on the same day too
    assert LR._fixed(candidate, passed_same_day) is True
    # the marker still there: not fixed, whatever else reads true
    still = dict(passed_same_day, failedCheck=["reviewer"])
    assert LR._fixed(candidate, still) is False
    # the marker gone but the condition still false: not fixed
    broken = _now(ready=False, reason="no-pass", checked="2026-10-11")
    broken["failedCheck"] = None
    assert LR._fixed(candidate, broken) is False
    # a candidate with no failed check keeps the later-day rule: the same day does not fix it
    plain = dict(candidate, failedCheck=None, reported={"noPass": True})
    assert LR._fixed(plain, passed_same_day) is False
