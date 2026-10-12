# plugins/superheroes/lib/tests/test_launch_report.py
"""Conformance: the launch report and the "Still on your machine" line. Every store, account file,
repository and record is built under tmp_path; no test touches the real home directory, clock,
clipboard or network. Requirement numbers in the test names are for the reader."""
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
import core_md as CM  # noqa: E402
import launch_place as LP  # noqa: E402
import launch_report as LR  # noqa: E402
import mode_registry  # noqa: E402
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


def _gitdir(tmp_path):
    repo = str(tmp_path / "repo")
    subprocess.run(["git", "init", "-q", repo], check=True)
    return repo, str(tmp_path / "store")


def _store_dir(repo, store):
    return mode_registry.project_store_dir(repo, store)


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _sub(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
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

BOARD_STILL = ("Still on your machine\n"
               "The cloud's plugin is 0.41.0 and mine is 0.42.0. Paste the new setup text to fix it.")


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


def test_R_board_the_still_line_is_byte_exact(tmp_path):
    repo, store = _gitdir(tmp_path)
    LR.record_still(repo, [_call(reason="version", cloud="0.41.0", advisor="0.42.0")],
                    root=store, today=TODAY)
    line = LR.still_line(repo, root=store, today=TODAY,
                         readiness_fn=_fn(ready=False, reason="version"))
    assert line == BOARD_STILL


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


def _every_output(tmp_path):
    """(code, shape, text) for every string reason_text, render_report and still_line can make."""
    outputs = []
    repo, store = _gitdir(tmp_path)
    for code in LP.REASON_CODES:
        call = _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                     need=PHONE if code == "needs" else None)
        outputs.append((code, "text", LP.reason_text(call)))
        outputs.append((code, "list", LR.render_report([_lane(1, call), _lane(2, _call("cloud"))])))
        outputs.append((code, "mixed", LR.render_report([_lane(1, call), _lane(2, _call(
            reason="local-word"))])))
        outputs.append((code, "summary", LR.render_report([_lane(1, call), _lane(2, call)])))
        if code in LP.NOT_READY_CODES:
            LR.record_still(repo, [call], root=store, today=TODAY)
            outputs.append((code, "still", LR.still_line(
                repo, root=store, today=TODAY, readiness_fn=_fn(ready=False, reason=code))))
    return outputs


def test_R_eight_every_string_is_drawn_from_the_table(tmp_path):
    seen = set()
    for code, shape, text in _every_output(tmp_path):
        assert isinstance(text, str), (code, shape)
        parts = _fragments(code)
        others = [_fragments(other) for other in LP.REASON_CODES if other != code]
        if shape == "mixed":
            assert parts["words"] in text and LP.REASONS["local-word"]["words"] in text
        if shape in ("text", "list", "still"):
            assert text.count(parts["words"]) >= 1, (code, shape, text)
            for other in others:
                assert other["words"] not in text, (code, shape, other["words"])
        if shape == "summary" and code in LP.NOT_READY_CODES:
            assert text.count(parts["wasnt"]) == 1
            assert parts["fix"] in text.split("\n")
            for other in others:
                assert other["wasnt"] is None or other["wasnt"] not in text
                assert other["words"] not in text
        if shape == "still":
            assert text == "Still on your machine\n%s %s" % (parts["words"], parts["short"])
        if shape == "list" and code in LP.NOT_READY_CODES:
            assert parts["fix"] in text.split("\n")
        if shape == "text":
            assert text == parts["words"]
        seen.add((code, shape))
    assert {code for code, _ in seen} == set(LP.REASON_CODES)
    assert {shape for _, shape in seen} == {"text", "list", "mixed", "summary", "still"}


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


# ---------------------------------------------------------------- the line at the top of later messages


def _still_path(repo, store):
    return LR._still_path(repo, store)


def _stored(repo, store):
    with open(_still_path(repo, store), encoding="utf-8") as fh:
        return json.load(fh)


def test_record_still_writes_the_first_reason_in_condition_order(tmp_path):
    repo, store = _gitdir(tmp_path)
    calls = [
        _call(reason="local-word"), _call(reason="needs", need=PHONE),
        _call(pointed=False, by=None, reason="no-pass"),
        _call(reason="unreachable", by="word"),
        _call(reason="version", cloud="0.41.0", advisor="0.42.0", reported={"pluginVersion": "0.41.0"}),
        _call(reason="calibration"),
    ]
    got = LR.record_still(repo, calls, root=store, today=TODAY)
    assert got == {"action": "written", "reason": "version"}
    assert _stored(repo, store) == {
        "schema": LR._STILL_SCHEMA, "reason": "version", "by": "setting",
        "cloudVersion": "0.41.0", "advisorVersion": "0.42.0",
        "reported": {"pluginVersion": "0.41.0"}, "observedOn": "2026-10-11"}
    again = LR.record_still(repo, [_call(reason="no-pass", reported={"noPass": True})],
                            root=store, today=TODAY + datetime.timedelta(days=1))
    assert again == {"action": "written", "reason": "no-pass"}
    state = _stored(repo, store)
    assert state["reason"] == "no-pass" and state["observedOn"] == "2026-10-12"
    assert state["reported"] == {"noPass": True} and state["cloudVersion"] is None


def test_record_still_writes_the_word_as_the_pointing(tmp_path):
    repo, store = _gitdir(tmp_path)
    LR.record_still(repo, [_call(reason="unreachable", by="word")], root=store, today=TODAY)
    assert _stored(repo, store)["by"] == "word"


def test_a_failed_check_keeps_its_recheck_step_in_the_report_and_the_still_line(tmp_path):
    repo, store = _gitdir(tmp_path)
    call = dict(_call(reason="calibration"), failedCheck=["calibration"])
    assert LR.render_report([_lane(1, call)]).endswith(SETUP_TEXT_FIX + ' Then say "check again".')
    assert LR.render_report([_lane(1, call), _lane(2, _call("cloud"))]).endswith(
        SETUP_TEXT_FIX + ' Then say "check again".')
    LR.record_still(repo, [call], root=store, today=TODAY)
    assert _stored(repo, store)["failedCheck"] == ["calibration"]
    line = LR.still_line(repo, root=store, today=TODAY, readiness_fn=_fn(
        ready=False, reason="calibration"))
    assert line.endswith(SETUP_TEXT_FIX + ' Then say "check again".')


def test_a_failed_check_after_an_ordinary_fallback_keeps_its_recheck_step(tmp_path):
    repo, store = _gitdir(tmp_path)
    plain = _call(reason="calibration")
    failed = dict(_call(reason="calibration", by="word"), failedCheck=["calibration"])
    recheck = SETUP_TEXT_FIX + ' Then say "check again".'
    assert LR.render_report([_lane(1, plain), _lane(2, failed)]).endswith(recheck)
    assert LR.render_report([_lane(1, plain), _lane(2, plain)]).endswith(SETUP_TEXT_FIX)
    third = _call(reason="no-setup", pointed=True)
    assert LR.render_report([_lane(1, plain), _lane(2, third), _lane(3, failed)]).endswith(recheck)
    same = _call(reason="calibration")
    assert LR.render_report([_lane(1, same), _lane(2, dict(same, failedCheck=["calibration"]))]
                            ).endswith(recheck)
    LR.record_still(repo, [plain, failed], root=store, today=TODAY)
    assert _stored(repo, store)["failedCheck"] == ["calibration"]
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=_fn(
        ready=False, reason="calibration")).endswith(recheck)


def test_a_word_directed_fallback_beside_a_setting_directed_one_stays_word_directed(tmp_path):
    repo, store = _gitdir(tmp_path)
    calls = [_call(reason="calibration", by="setting"), _call(reason="calibration", by="word")]
    LR.record_still(repo, calls, root=store, today=TODAY)
    assert _stored(repo, store)["by"] == "word"
    line = _line(repo, store, ready=False, reason="calibration", setting=False)
    assert line is not None and line.startswith("Still on your machine\n")
    assert os.path.exists(_still_path(repo, store))


@pytest.mark.parametrize("reported_first", [True, False])
def test_a_reported_version_beside_a_setup_record_fallback_still_needs_a_later_check(
        tmp_path, reported_first):
    repo, store = _gitdir(tmp_path)
    plain = _call(reason="version", cloud="0.41.0", advisor="0.42.0")
    reported = _call(reason="version", cloud="0.41.0", advisor="0.42.0",
                     reported={"pluginVersion": "0.41.0"})
    LR.record_still(repo, [reported, plain] if reported_first else [plain, reported],
                    root=store, today=TODAY)
    assert _stored(repo, store)["reported"] == {"pluginVersion": "0.41.0"}
    same_day = _now(ready=True, checked=TODAY.isoformat())
    assert LR.still_line(repo, root=store, today=TODAY,
                         readiness_fn=lambda *a, **k: dict(same_day)) is not None
    assert os.path.exists(_still_path(repo, store))
    later = _now(ready=True, checked="2026-10-12")
    assert LR.still_line(repo, root=store, today=TODAY,
                         readiness_fn=lambda *a, **k: dict(later)) is None


def test_record_still_clears_when_a_build_went_to_the_cloud(tmp_path):
    repo, store = _gitdir(tmp_path)
    LR.record_still(repo, [_call(reason="no-setup")], root=store, today=TODAY)
    got = LR.record_still(repo, [_call("cloud"), _call(reason="needs", need=PHONE)],
                          root=store, today=TODAY)
    assert got == {"action": "cleared", "reason": None}
    assert not os.path.exists(_still_path(repo, store))
    assert LR.record_still(repo, [_call("cloud")], root=store, today=TODAY) == {
        "action": "unchanged", "reason": None}


def test_record_still_leaves_the_file_alone_when_nothing_decides(tmp_path):
    repo, store = _gitdir(tmp_path)
    LR.record_still(repo, [_call(reason="no-setup")], root=store, today=TODAY)
    before = open(_still_path(repo, store), "rb").read()
    for calls in ([], [_call(reason="local-word")], [_call(reason="needs", need=PHONE)],
                  [_call(pointed=False, by=None, reason=None)]):
        assert LR.record_still(repo, calls, root=store, today=TODAY) == {
            "action": "unchanged", "reason": None}
    assert open(_still_path(repo, store), "rb").read() == before


def test_E17_a_write_that_fails_is_refused_and_leaves_no_file(tmp_path, monkeypatch):
    repo, store = _gitdir(tmp_path)

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    got = LR.record_still(repo, [_call(reason="no-setup")], root=store, today=TODAY)
    assert got["action"] == "refused"
    state_dir = os.path.dirname(_still_path(repo, store))
    assert os.listdir(state_dir) == [] if os.path.isdir(state_dir) else True


def test_a_write_into_a_blocked_folder_is_refused(tmp_path):
    repo, store = _gitdir(tmp_path)
    _put(os.path.join(_store_dir(repo, store), "state"), "a file where the folder belongs")
    got = LR.record_still(repo, [_call(reason="no-setup")], root=store, today=TODAY)
    assert got["action"] == "refused"
    assert LR.clear_still(repo, root=store)["action"] in ("unchanged", "refused")


def _still_with(tmp_path, call, observed=TODAY):
    repo, store = _gitdir(tmp_path)
    assert LR.record_still(repo, [call], root=store, today=observed)["action"] == "written"
    return repo, store


def _line(repo, store, **kw):
    return LR.still_line(repo, root=store, today=TODAY, readiness_fn=_fn(**kw))


def test_R_still_no_state_means_no_line(tmp_path):
    repo, store = _gitdir(tmp_path)

    asked = []

    def record_the_ask(*args, **kwargs):
        asked.append((args, kwargs))
        return _now()

    # still_line swallows an exception from the readiness read, so the callback records, not raises
    assert LR.still_line(repo, root=store, readiness_fn=record_the_ask) is None
    assert asked == []


def test_R_still_leg_a_the_setting_switched_off_clears_it(tmp_path):
    repo, store = _still_with(tmp_path, _call(reason="unreachable", by="setting"))
    assert _line(repo, store, ready=False, reason="unreachable", setting=True) is not None
    assert _line(repo, store, ready=False, reason="unreachable", setting=False) is None
    assert not os.path.exists(_still_path(repo, store))
    word_repo, word_store = _still_with(
        _sub(tmp_path, "word"), _call(reason="unreachable", by="word"))
    assert _line(word_repo, word_store, ready=False, reason="unreachable", setting=False) is not None


def test_R_still_leg_a_an_unreadable_setting_does_not_clear_it(tmp_path, monkeypatch):
    repo, store = _still_with(tmp_path, _call(reason="no-setup", by="setting"))

    def unreadable(*args, **kwargs):
        raise OSError("config unreadable")

    monkeypatch.setattr(PC, "get_item", unreadable)
    assert _line(repo, store, ready=False, reason="no-setup", setting=False) is not None
    assert os.path.exists(_still_path(repo, store))


@pytest.mark.parametrize("damage", ["corrupt", "directory"])
def test_R_still_leg_a_a_profile_the_reader_could_not_read_does_not_clear_it(tmp_path, damage):
    repo, store = _still_with(tmp_path, _call(reason="no-setup", by="setting"))
    path = CM.core_path(repo, store)
    if damage == "corrupt":
        _put(path, "not a profile\n")
    else:
        os.makedirs(path)
    assert PC.get_item(repo, PC.CLOUD_BUILDS_SLUG, root=store)["effective"] is False
    assert _line(repo, store, ready=False, reason="no-setup", setting=False) is not None
    assert os.path.exists(_still_path(repo, store))


@pytest.mark.parametrize("code,condition", [("no-setup", "setup"), ("pass-lapsed", "passLive"),
                                            ("calibration", "calibration")])
def test_R_still_leg_b_the_matching_condition_holding_again_clears_it(tmp_path, code, condition):
    repo, store = _still_with(tmp_path, _call(reason=code))
    stands = _now(ready=False, reason=code)
    assert stands["conditions"][condition] is False
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=lambda *a, **k: stands)
    other = {name: (name != condition) for name in CR.CONDITION_ORDER}
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=_fn(
        ready=False, reason=code, conditions=other)) is not None
    fixed = dict(stands, conditions=dict(stands["conditions"], **{condition: True}))
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=lambda *a, **k: fixed) is None
    assert not os.path.exists(_still_path(repo, store))


def test_R_still_leg_c_a_version_that_agrees_again_clears_it(tmp_path):
    repo, store = _still_with(tmp_path, _call(reason="version", cloud="1.0.0", advisor="2.0.0"))
    assert _line(repo, store, ready=False, reason="version") is not None
    assert _line(repo, store, ready=True) is None
    assert not os.path.exists(_still_path(repo, store))


def test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check(tmp_path):
    cases = [("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
             ("version", {"pluginVersion": "0.41.0"})]
    for index, (code, reported) in enumerate(cases):
        repo, store = _still_with(_sub(tmp_path, str(index)), _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                                              reported=reported))
        ready = _now(ready=True)
        for checked in (None, "2026-10-10", "2026-10-11", "garbage"):
            assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=lambda *a, **k: dict(
                ready, checkedAt=checked)) is not None, (code, checked)
        assert os.path.exists(_still_path(repo, store))
        assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=lambda *a, **k: dict(
            ready, checkedAt="2026-10-12")) is None, code
        assert not os.path.exists(_still_path(repo, store))


def test_R_still_a_report_then_a_same_day_passed_check_leaves_the_line_standing(tmp_path):
    repo, store, env = _on(tmp_path, checked_at=TODAY.isoformat())
    premise = {"reportedCloud": {"noPass": True}}
    call = _route(repo, store, env, premise=premise)
    assert call["reason"] == "no-pass"
    assert LR.record_still(repo, [call], root=store, today=TODAY)["action"] == "written"
    real = functools.partial(CR.readiness, advisor_version=ADVISOR, today=TODAY,
                             stamp_fn=lambda cwd, root: STAMP, env=env)
    line = LR.still_line(repo, root=store, today=TODAY, readiness_fn=real)
    assert line == ("Still on your machine\nThere is no reviewer pass in the cloud environment. "
                    'Paste a pass into the environment and say "check again" to fix it.')
    _record(repo, store, checked_at="2026-10-12")
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=real) is None


def test_R_still_write_then_fix_then_clear_with_real_readiness(tmp_path):
    repo, store, env = _on(tmp_path, pass_lapses=PAST)
    call = _route(repo, store, env)
    assert call["reason"] == "pass-lapsed"
    LR.record_still(repo, [call], root=store, today=TODAY)
    real = functools.partial(CR.readiness, advisor_version=ADVISOR, today=TODAY,
                             stamp_fn=lambda cwd, root: STAMP, env=env)
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=real) == (
        'Still on your machine\nThe reviewer pass has lapsed. Paste a fresh pass and say '
        '"check again" to fix it.')
    assert CS.confirm_pass(repo, ACCOUNT, FUTURE, root=store)["action"] == "written"
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=real) is None
    assert not os.path.exists(_still_path(repo, store))


def test_R_still_clear_still_removes_the_line(tmp_path):
    repo, store = _still_with(tmp_path, _call(reason="no-setup"))
    assert LR.clear_still(repo, root=store) == {"action": "cleared"}
    assert not os.path.exists(_still_path(repo, store))
    assert LR.clear_still(repo, root=store) == {"action": "unchanged"}
    assert _line(repo, store, ready=False, reason="no-setup") is None


def test_clear_still_that_cannot_delete_is_refused(tmp_path, monkeypatch):
    repo, store = _still_with(tmp_path, _call(reason="no-setup"))

    def boom(path):
        raise PermissionError("not yours")

    monkeypatch.setattr(os, "unlink", boom)
    assert LR.clear_still(repo, root=store) == {"action": "refused"}


_GOOD = {"schema": LR._STILL_SCHEMA, "reason": "no-setup", "by": "setting", "cloudVersion": None,
         "advisorVersion": None, "reported": None, "observedOn": "2026-10-11"}


@pytest.mark.parametrize("text", [
    "", "{not json", "[]", "null", "42",
    json.dumps(dict(_GOOD, schema=LR._STILL_SCHEMA + "-other")),
    json.dumps({k: v for k, v in _GOOD.items() if k != "schema"}),
    json.dumps(dict(_GOOD, reason="needs")),
    json.dumps(dict(_GOOD, reason="local-word")),
    json.dumps(dict(_GOOD, reason=None)),
    json.dumps(dict(_GOOD, by="nobody")),
    json.dumps(dict(_GOOD, by=None)),
    json.dumps(dict(_GOOD, cloudVersion=41)),
    json.dumps(dict(_GOOD, advisorVersion=[])),
    json.dumps(dict(_GOOD, reported={"other": True})),
    json.dumps(dict(_GOOD, reported="x")),
    json.dumps(dict(_GOOD, observedOn="yesterday")),
    json.dumps(dict(_GOOD, observedOn="2026-13-40")),
    json.dumps(dict(_GOOD, observedOn=None)),
])
def test_E16_a_state_file_in_the_wrong_shape_is_deleted_and_gives_no_line(tmp_path, text):
    repo, store = _gitdir(tmp_path)
    path = _put(_still_path(repo, store), text)
    assert _line(repo, store, ready=False, reason="no-setup") is None
    assert not os.path.exists(path)


def test_a_state_file_that_cannot_be_read_is_kept_and_named_not_deleted(tmp_path, monkeypatch):
    repo, store = _still_with(tmp_path, _call(reason="no-setup"))
    path = _still_path(repo, store)
    real_open = open

    def deny(file, *args, **kwargs):
        if str(file) == path:
            raise PermissionError("not readable")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", deny)
    got = LR.still_check(repo, root=store, today=TODAY, readiness_fn=_fn(
        ready=False, reason="no-setup"))
    assert got == {"line": None, "refused": LR.STILL_UNREADABLE}
    assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=_fn(
        ready=False, reason="no-setup")) is None
    monkeypatch.undo()
    assert os.path.exists(path)
    assert _line(repo, store, ready=False, reason="no-setup").startswith("Still on your machine")


def test_a_good_state_file_written_by_hand_gives_its_line(tmp_path):
    repo, store = _gitdir(tmp_path)
    _put(_still_path(repo, store), json.dumps(_GOOD))
    assert _line(repo, store, ready=False, reason="no-setup") == (
        'Still on your machine\nThis project has no cloud setup on this Claude account. '
        'Say "set up cloud builds" to fix it.')


def test_a_readiness_that_raises_leaves_the_line_standing(tmp_path):
    repo, store = _still_with(tmp_path, _call(reason="no-setup"))

    def boom(*args, **kwargs):
        raise RuntimeError("readiness exploded")

    line = LR.still_line(repo, root=store, today=TODAY, readiness_fn=boom)
    assert line.startswith("Still on your machine\nThis project has no cloud setup")
    assert os.path.exists(_still_path(repo, store))


def test_the_line_for_an_unreproduced_version_uses_the_stored_versions(tmp_path):
    repo, store = _still_with(tmp_path, _call(reason="version", cloud=None, advisor="0.42.0"))
    line = _line(repo, store, ready=False, reason="version", cloud="9.9.9", advisor="8.8.8")
    assert line == ("Still on your machine\nThe cloud's plugin is unknown and mine is 0.42.0. "
                    "Paste the new setup text to fix it.")


def test_still_line_and_clear_still_never_raise_without_a_repository(tmp_path):
    plain = str(tmp_path / "not-a-repository")
    os.mkdir(plain)
    store = str(tmp_path / "store")
    assert LR.still_line(plain, root=store) is None or isinstance(
        LR.still_line(plain, root=store), str)
    assert LR.clear_still(plain, root=store)["action"] in ("cleared", "unchanged", "refused")
    assert LR.record_still(plain, [_call(reason="no-setup")], root=store)["action"] in (
        "written", "refused")


# ---------------------------------------------------------------- the launcher's report verb feeds these


def test_a_report_renders_the_need_a_routing_result_carries():
    phone = _call(reason="needs", need=PHONE)
    canon = _call(reason="needs", need="this project's Canon and specs")
    got = LR.render_report([_lane(415, phone, title="Phone checkout layout"), _lane(416, canon)])
    lines = got.splitlines()
    assert "- #415 Phone checkout layout. It needs the phone simulator, which only your machine has." in lines
    assert ("- #416 Build 416. It needs this project's Canon and specs, "
            "which only your machine has.") in lines


def test_record_still_clears_when_a_cloud_build_sits_beside_a_local_not_ready_fallback(tmp_path):
    repo, store = _gitdir(tmp_path)
    mixed = [_call(reason="version", cloud="0.41.0", advisor="0.42.0"), _call("cloud")]
    LR.record_still(repo, [_call(reason="no-setup")], root=store, today=TODAY)
    assert LR.record_still(repo, mixed, root=store, today=TODAY) == {
        "action": "cleared", "reason": None}
    assert not os.path.exists(_still_path(repo, store))
    assert LR.record_still(repo, mixed, root=store, today=TODAY) == {
        "action": "unchanged", "reason": None}
    assert not os.path.exists(_still_path(repo, store))


def test_R_still_a_reported_fact_needs_the_reader_ready_as_well_as_a_later_check(tmp_path):
    repo, store = _still_with(tmp_path, _call(reason="version", cloud="0.41.0", advisor="0.42.0",
                                              reported={"pluginVersion": "0.41.0"}))
    not_ready = _now(ready=False, reason="version", checked="2026-10-12")
    assert not_ready["conditions"]["version"] is False
    assert LR.still_line(repo, root=store, today=TODAY,
                         readiness_fn=lambda *a, **k: dict(not_ready)) is not None
    assert os.path.exists(_still_path(repo, store))
    ready = _now(ready=True, checked="2026-10-12")
    assert LR.still_line(repo, root=store, today=TODAY,
                         readiness_fn=lambda *a, **k: dict(ready)) is None
    assert not os.path.exists(_still_path(repo, store))
