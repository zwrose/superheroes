"""iPhone check driver — every subprocess is faked through iphone_check._run; read runs on a real loopback.

The one exempt subprocess is `node`, which runs the fixture page's own script (FR-13)."""
import hashlib
import io
import json
import math
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

import pytest

import iphone_check as ic
import launcher

U = "0A1B2C3D-4E5F-6789-ABCD-0123456789AB"
V = "11111111-2222-3333-4444-555555555555"
DT17 = "com.apple.CoreSimulator.SimDeviceType.iPhone-17"
RT27 = "com.apple.CoreSimulator.SimRuntime.iOS-27-0"
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "iphone", "reading-page.html")
DASH = "—"
SHA = "ab" * 32
UFR5_LITERAL = "iPhone check did not run — whole check: no phone for this lane"


def inventory(*devices):
    """devices: (udid, state[, deviceTypeIdentifier]) tuples, all under one iOS 27.0 runtime."""
    return json.dumps({"devices": {RT27: [
        {"udid": d[0], "state": d[1], "deviceTypeIdentifier": d[2] if len(d) > 2 else DT17, "name": "n"}
        for d in devices]}})


class FakeRun:
    def __init__(self, responder=None):
        self.calls = []
        self.responder = responder

    def __call__(self, argv, timeout, env=None):
        self.calls.append((list(argv), timeout, env))
        return self.responder(list(argv)) if self.responder else (True, 0, "")


@pytest.fixture
def fake(monkeypatch):
    def install(responder=None):
        f = FakeRun(responder)
        monkeypatch.setattr(ic, "_run", f)
        return f
    return install


def sim(inv, pgrep=(True, 0, "42"), screenshot=(True, 0, "")):
    """A responder that plays the inventory, pgrep and screenshot; anything else succeeds."""
    def respond(argv):
        if argv[:3] == ["xcrun", "simctl", "list"]:
            return (True, 0, inv) if isinstance(inv, str) else inv
        if argv[0] == "pgrep":
            return pgrep
        if "screenshot" in argv and screenshot[0] and screenshot[1] == 0:
            with open(argv[-1], "wb") as fh:
                fh.write(b"png-bytes")
        if "screenshot" in argv:
            return screenshot
        return True, 0, ""
    return respond


def _fixture(name):
    with open(os.path.join(os.path.dirname(FIXTURE), name)) as fh:
        return fh.read()


HELPER_UP = _fixture("launchctl-list-dtuhidd-running.txt")
HELPER_STOPPED = _fixture("launchctl-list-dtuhidd-stopped.txt")


def helper_sim(states, axe=(True, 0, ""), kickstart=(True, 0, "")):
    """A responder that plays `launchctl list` from `states` in order (the last repeats), `kickstart` and `axe`.

    A state is "up" (the running fixture), "down" (the stopped fixture, still exit 0), "never", or an exit code."""
    queue = list(states)

    def respond(argv):
        if argv[0] == "axe":
            return axe
        if argv[5] == "kickstart":
            return kickstart
        state = queue.pop(0) if len(queue) > 1 else queue[0]
        if state == "never":
            return False, None, ""
        if isinstance(state, int):
            return True, state, ""
        return True, 0, HELPER_UP if state == "up" else HELPER_STOPPED
    return respond


def verbs(f):
    """The recorded calls as short names: list, kickstart or axe."""
    return [c[0][0] if c[0][0] == "axe" else c[0][5] for c in f.calls]


def axe_calls(f):
    return [c for c in f.calls if c[0][0] == "axe"]


# ---------------------------------------------------------------- literal pins
def test_literal_pins():
    assert ic.IPHONE_ID_ENV == "SUPERHEROES_IPHONE_ID"
    assert ic.DEVICE_HUB_ENV == "SUPERHEROES_DEVICE_HUB"
    assert ic.READING_PARAM == "superheroes-reading"
    assert ic.UFR5 == UFR5_LITERAL
    assert ic.UFR5 == "iPhone check did not run — whole check: no phone for this lane"
    assert ic._line("whole check", "Device Hub unavailable") == \
        "iPhone check did not run — whole check: Device Hub unavailable"
    assert ic.GAPS == ("**What a simulator cannot show:** a real finger's touch (the timing and imprecision of "
                       "a human tap, and multi-finger gestures) and real-device speed.")
    env = {"SUPERHEROES_IPHONE_ID": "none", "SUPERHEROES_DEVICE_HUB": "available"}
    assert ic.classify_env(env) == ("did-not-run", UFR5_LITERAL)
    env = {"SUPERHEROES_IPHONE_ID": U, "SUPERHEROES_DEVICE_HUB": "unavailable"}
    assert ic.classify_env(env) == ("did-not-run", "iPhone check did not run — whole check: Device Hub unavailable")
    env = {"SUPERHEROES_IPHONE_ID": U, "SUPERHEROES_DEVICE_HUB": "available"}
    assert ic.classify_env(env) == ("pending", None)


def test_launch_contract_names_are_the_launchers_own():
    for name in ("IPHONE_ID_ENV", "DEVICE_HUB_ENV", "IPHONE_NONE", "DEVICE_HUB_AVAILABLE",
                 "DEVICE_HUB_UNAVAILABLE", "DEVICE_HUB_PROCESS"):
        assert getattr(ic, name) is getattr(launcher, name), name


def test_where_line_for_both_parts_chosen_by_the_issue():
    check = {"where": ["browser", "installed"], "chosenBy": "issue", "parts": {}, "evidence": []}
    _, section = ic.render(check)
    assert ("**Where the check ran:** in the browser and in the installed web app — chosen by the issue."
            in section.split("\n\n"))
    assert "**What a simulator cannot show:** a real finger's touch" in section


def test_where_line_for_each_single_part_chosen_by_the_lane():
    for where, text in ((["browser"], "in the browser"), (["installed"], "in the installed web app")):
        _, section = ic.render({"where": where, "chosenBy": "lane", "parts": {}, "evidence": []})
        assert f"**Where the check ran:** {text} — chosen by the lane." in section.split("\n\n")


# ---------------------------------------------------------------- UFR-4 (judge_step)
def rd(value=None, focus="input", ftype="text", where="browser"):
    r = {"visibleHeight": 700, "focused": {"tag": focus, "type": ftype, "id": "name", "name": "name"} if focus else None,
         "valueWithheld": False, "where": where, "visibility": "visible", "page": "http://x.test/", "takenAt": 1}
    if value is not None:
        r["value"] = value
    return r


def step(**kw):
    base = {"kind": "other", "step": "s", "before": None, "after": None, "keyboardSeen": None, "screenChanged": None,
            "expected": None, "expectedSeen": None, "password": False}
    base.update(kw)
    return base


def test_ufr4_tap_with_no_field_focused_is_not_completed():
    done, reason = ic.judge_step(step(kind="tap-field", after=rd(focus=None), keyboardSeen=True))
    assert done is False and "no field focused" in reason


def test_ufr4_tap_with_no_keyboard_seen_is_not_completed():
    done, reason = ic.judge_step(step(kind="tap-field", after=rd(), keyboardSeen=False))
    assert done is False and "no keyboard" in reason


def test_ufr4_tap_that_leaves_another_field_focused_is_not_completed():
    # Name stays focused (reading id "name") when Secret was the target
    done, reason = ic.judge_step(step(kind="tap-field", target="secret", before=rd(), after=rd(), keyboardSeen=True))
    assert done is False and "intended field" in reason


def test_ufr4_tap_with_no_target_is_not_completed():
    for target in (None, "", 7):
        done, reason = ic.judge_step(step(kind="tap-field", target=target, after=rd(), keyboardSeen=True))
        assert done is False and "intended field" in reason
    bare = step(kind="tap-field", after=rd(), keyboardSeen=True)
    assert "target" not in bare and ic.judge_step(bare)[0] is False


def test_ufr4_typing_with_value_unchanged_is_not_completed():
    done, _ = ic.judge_step(step(kind="type", before=rd(value="a"), after=rd(value="a")))
    assert done is False


def focused_as(r, fid, name):
    r["focused"] = {"tag": "input", "type": "text", "id": fid, "name": name}
    return r


def test_ufr4_typing_that_moves_focus_to_another_prefilled_field_is_not_completed():
    done, reason = ic.judge_step(step(kind="type", before=focused_as(rd(value="Alice"), "name", "name"),
                                      after=focused_as(rd(value="existing@example.test"), "email", "email")))
    assert done is False and "another field" in reason


def test_ufr4_tap_on_a_field_with_no_id_is_matched_by_name_form_target():
    after = focused_as(rd(), None, "email")
    assert ic.judge_step(step(kind="tap-field", target="name:email", after=after, keyboardSeen=True))[0] is True
    done, reason = ic.judge_step(step(kind="tap-field", target="email", after=after, keyboardSeen=True))
    assert done is False and "intended field" in reason


def test_ufr4_name_target_matches_the_focused_fields_name_even_when_it_has_an_id():
    after = focused_as(rd(), ":r1:", "email")
    assert ic.judge_step(step(kind="tap-field", target="name:email", after=after, keyboardSeen=True))[0] is True
    done, reason = ic.judge_step(step(kind="tap-field", target="name:other", after=after, keyboardSeen=True))
    assert done is False and reason == "the intended field did not receive focus"
    assert ic.judge_step(step(kind="tap-field", target="email", after=after, keyboardSeen=True))[0] is False
    assert ic.judge_step(step(kind="tap-field", target=":r1:", after=after, keyboardSeen=True))[0] is True


def test_ufr4_name_target_with_no_name_or_a_focused_field_with_no_name_is_not_completed():
    for target, after in (("name:", focused_as(rd(), "a", "email")), ("name:", focused_as(rd(), "a", "")),
                          ("name:email", focused_as(rd(), "email", None)), ("name:email", focused_as(rd(), None, None))):
        done, reason = ic.judge_step(step(kind="tap-field", target=target, after=after, keyboardSeen=True))
        assert done is False and "intended field" in reason


def test_ufr4_typing_on_an_unkeyed_field_is_not_completed():
    done, reason = ic.judge_step(step(kind="type", before=focused_as(rd(value="a"), None, None),
                                      after=focused_as(rd(value="ab"), None, None)))
    assert done is False and "could not be identified" in reason


def test_ufr4_password_typing_with_screen_unchanged_is_not_completed():
    done, _ = ic.judge_step(step(kind="type", password=True, before=rd(ftype="password"),
                                 after=rd(ftype="password"), screenChanged=False))
    assert done is False


def test_ufr4_password_typing_that_moves_focus_between_two_password_fields_is_not_completed():
    before, after = focused_as(rd(), "secret", "secret"), focused_as(rd(), "secret2", "secret2")
    before["focused"]["type"] = after["focused"]["type"] = "password"
    done, reason = ic.judge_step(step(kind="type", password=True, before=before, after=after, screenChanged=True))
    assert done is False and "another field" in reason


def test_ufr4_password_typing_on_an_unkeyed_field_is_not_completed():
    unkeyed = focused_as(rd(), None, None)
    unkeyed["focused"]["type"] = "password"
    keyed = focused_as(rd(), "secret", "secret")
    keyed["focused"]["type"] = "password"
    for before, after in ((unkeyed, unkeyed), (keyed, unkeyed), (unkeyed, keyed)):
        done, reason = ic.judge_step(step(kind="type", password=True, before=before, after=after, screenChanged=True))
        assert done is False and "could not be identified" in reason


def test_ufr4_password_typing_on_the_same_field_with_screen_changed_is_completed():
    before, after = focused_as(rd(), "secret", "secret"), focused_as(rd(), "secret", "secret")
    before["focused"]["type"] = after["focused"]["type"] = "password"
    done, reason = ic.judge_step(step(kind="type", password=True, before=before, after=after, screenChanged=True))
    assert done is True and "screen changed" in reason


def test_ufr4_password_typing_with_no_before_reading_is_not_completed():
    after = focused_as(rd(), "secret", "secret")
    after["focused"]["type"] = "password"
    done, reason = ic.judge_step(step(kind="type", password=True, before=None, after=after, screenChanged=True))
    assert done is False and "could not be identified" in reason


def test_ufr4_other_input_with_expected_change_not_seen_is_not_completed():
    done, reason = ic.judge_step(step(kind="other", expected="the menu opens", expectedSeen=False))
    assert done is False and "not seen" in reason


def test_ufr4_step_naming_no_expected_change_is_not_completed():
    for expected in (None, "", "   "):
        done, reason = ic.judge_step(step(kind="other", expected=expected, expectedSeen=True))
        assert done is False and "no expected change" in reason


def test_ufr4_positive_rows_are_completed():
    assert ic.judge_step(step(kind="tap-field", target="name", after=rd(), keyboardSeen=True))[0] is True
    assert ic.judge_step(step(kind="type", before=rd(value=""), after=rd(value="hi")))[0] is True
    assert ic.judge_step(step(kind="type", password=True, before=rd(ftype="password"),
                              after=rd(ftype="password"), screenChanged=True))[0] is True
    assert ic.judge_step(step(kind="other", expected="menu", expectedSeen=True))[0] is True


@pytest.mark.parametrize("bad", [
    step(kind="tap-field", after=None, keyboardSeen=True),
    step(kind="tap-field", target="name", after=rd(), keyboardSeen=None),
    step(kind="type", before=None, after=rd(value="x")),
    step(kind="type", before=rd(value="a"), after=None),
    step(kind="type", before=rd(), after=rd()),
    step(kind="type", password=True, screenChanged=None),
    step(kind="other", expected="menu", expectedSeen=None),
    step(kind="mystery"),
    {},
], ids=["tap-after-null", "tap-keyboard-null", "type-before-null", "type-after-null", "type-value-missing",
        "password-screen-null", "other-seen-null", "unknown-kind", "empty-step"])
def test_ufr4_null_or_missing_field_is_not_completed(bad):
    assert ic.judge_step(bad)[0] is False


# ---------------------------------------------------------------- UFR-2/UFR-5 line selection
def ev_reading(part="installed", where="installed", lwhere=None):
    return {"kind": "reading", "part": part, "caption": "c", "labels": labels(where=lwhere or where),
            "reading": rd(value="v", where=where)}


def labels(**kw):
    base = {"phone": U, "model": "iPhone 17", "iOS": "27.0", "page": "http://x.test/", "where": "browser",
            "source": "Simulator"}
    base.update(kw)
    return base


def ev_shot(part="browser", **lb):
    return {"kind": "screenshot", "part": part, "caption": "Home", "labels": labels(where=part, **lb), "path": "/r/a.png",
            "sha256": SHA}


def part(included=True, completed=False, reason=""):
    return {"included": included, "completed": completed, "reason": reason}


def chk(**kw):
    base = {"noPhone": False, "whole": None, "where": ["browser", "installed"], "chosenBy": "issue",
            "parts": {"browser": part(), "installed": part()}, "evidence": [], "commit": "abc1234"}
    base.update(kw)
    return base


def test_no_phone_gives_exactly_the_ufr5_line():
    assert ic.did_not_run_lines(chk(noPhone=True)) == [UFR5_LITERAL]


def test_no_phone_with_a_whole_reason_still_only_the_ufr5_line():
    assert ic.did_not_run_lines(chk(noPhone=True, whole="Device Hub unavailable")) == [UFR5_LITERAL]


def test_whole_reason_gives_exactly_one_whole_line():
    assert ic.did_not_run_lines(chk(whole="Device Hub unavailable")) == [
        "iPhone check did not run — whole check: Device Hub unavailable"]


def test_each_included_part_that_failed_gets_its_own_line_in_order():
    c = chk(parts={"browser": part(reason="a screenshot never returned"),
                   "installed": part(reason="the Home Screen install failed")})
    assert ic.did_not_run_lines(c) == [
        "iPhone check did not run — browser check: a screenshot never returned",
        "iPhone check did not run — installed-app check: the Home Screen install failed"]


def test_installed_never_attempted_gets_the_not_attempted_line():
    c = chk(parts={"browser": part(completed=True), "installed": part()}, evidence=[ev_reading("browser", "browser")])
    assert ic.did_not_run_lines(c) == ["iPhone check did not run — installed-app check: not attempted"]


def test_a_part_not_included_gets_no_line():
    c = chk(where=["browser"], parts={"browser": part(completed=True), "installed": part(included=False)})
    assert ic.did_not_run_lines(c) == []
    c = chk(where=["installed"], parts={"browser": part(included=False), "installed": part(reason="x")})
    assert ic.did_not_run_lines(c) == ["iPhone check did not run — installed-app check: x"]


def test_fr9_installed_completed_without_an_installed_reading_is_a_line():
    c = chk(parts={"browser": part(completed=True), "installed": part(completed=True)},
            evidence=[ev_reading("browser", "browser"), ev_shot("installed")])
    assert ic.did_not_run_lines(c) == [
        "iPhone check did not run — installed-app check: no page reading from the installed app"]


def test_fr9_a_reading_labelled_installed_but_reading_browser_does_not_satisfy_it():
    c = chk(parts={"browser": part(completed=True), "installed": part(completed=True)},
            evidence=[{**ev_reading("installed", "browser"), "labels": labels(where="installed")}])
    assert ic.did_not_run_lines(c) == [
        "iPhone check did not run — installed-app check: no page reading from the installed app"]


def test_fr9_installed_completed_with_an_installed_reading_has_no_line():
    c = chk(parts={"browser": part(completed=True), "installed": part(completed=True)},
            evidence=[ev_reading("browser", "browser"), ev_reading("installed", "installed")])
    assert ic.did_not_run_lines(c) == []


# ---------------------------------------------------------------- classify_env / preflight
OFF = {}
PRE = "iPhone check did not run — whole check: "


def env(phone=U, hub="available"):
    e = {}
    if phone is not None:
        e["SUPERHEROES_IPHONE_ID"] = phone
    if hub is not None:
        e["SUPERHEROES_DEVICE_HUB"] = hub
    return e


def test_both_unset_is_off_and_with_the_issue_naming_the_check_is_ufr5(fake):
    f = fake()
    assert ic.preflight({}) == {"ok": False, "state": "off", "phone": None, "line": None}
    out = ic.preflight({}, issue_names_check=True)
    assert out == {"ok": False, "state": "did-not-run", "phone": None, "line": UFR5_LITERAL}
    assert f.calls == []


def test_none_is_the_ufr5_line_and_nothing_else_even_with_the_hub_unavailable(fake):
    f = fake()
    assert ic.preflight(env("none", "available"))["line"] == UFR5_LITERAL
    out = ic.preflight(env("none", "unavailable"))
    assert out == {"ok": False, "state": "did-not-run", "phone": None, "line": UFR5_LITERAL}
    assert f.calls == []


def test_preflight_none_dominates_hub_unavailable(fake):
    fake()
    assert ic.preflight(env("none", "unavailable"))["line"] == UFR5_LITERAL
    assert ic.classify_env(env("none", "unavailable")) == ("did-not-run", UFR5_LITERAL)


@pytest.mark.parametrize("e", [env(U, None), env(None, "available"), env(U, "maybe"), env("iPhone 17", "available"),
                               env("", "available"), env(U, ""), env(U[:-1], "available"), env(U, "Available"),
                               env(U.lower(), "available")],
                         ids=["only-id", "only-hub", "hub-maybe", "id-name", "id-empty", "hub-empty", "id-short",
                              "hub-case", "id-lower-case"])
def test_classify_env_invalid_values(fake, e):
    f = fake()
    assert ic.classify_env(e) == ("did-not-run", PRE + "launch values unreadable")
    out = ic.preflight(e, issue_names_check=True)
    assert out == {"ok": False, "state": "did-not-run", "phone": None, "line": PRE + "launch values unreadable"}
    assert f.calls == []


def test_preflight_hub_unavailable_is_the_device_hub_line(fake):
    f = fake()
    assert ic.preflight(env(U, "unavailable"))["line"] == PRE + "Device Hub unavailable"
    assert f.calls == []


@pytest.mark.parametrize("pgrep", [(True, 1, ""), (False, None, ""), (True, 127, "")], ids=["exit1", "timeout", "missing"])
def test_preflight_pgrep_failing_is_the_device_hub_line(fake, monkeypatch, pgrep):
    f = fake(sim(inventory((U, "Booted")), pgrep=pgrep))
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/axe")
    out = ic.preflight(env())
    assert out["state"] == "did-not-run" and out["line"] == PRE + "Device Hub unavailable" and out["phone"] is None
    assert f.calls[0][0] == ["pgrep", "-x", "DeviceHub"]


def test_preflight_axe_missing_is_the_axe_line(fake, monkeypatch):
    fake(sim(inventory((U, "Booted"))))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert ic.preflight(env())["line"] == PRE + "the driver tool (AXe) is missing"


def test_preflight_udid_absent_from_the_inventory_is_the_not_on_this_mac_line(fake, monkeypatch):
    fake(sim(inventory((V, "Booted"))))
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/axe")
    assert ic.preflight(env())["line"] == PRE + "the phone is not on this Mac"


@pytest.mark.parametrize("bad", [(False, None, ""), (True, 1, ""), (True, 0, "not json")],
                         ids=["timeout", "exit1", "not-json"])
def test_preflight_failed_inventory_call_is_the_inventory_line(fake, monkeypatch, bad):
    fake(sim(bad))
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/axe")
    assert ic.preflight(env())["line"] == PRE + "the simulator inventory could not be read"


def test_preflight_unreadable_inventory_is_never_ready(fake, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/axe")
    for bad in ((True, 1, ""), (False, None, ""), (True, 0, "not json")):
        fake(sim(bad))
        out = ic.preflight(env())
        assert out["ok"] is False and out["state"] == "did-not-run"


def test_preflight_all_good_is_ready(fake, monkeypatch):
    f = fake(sim(inventory((V, "Shutdown"), (U, "Shutdown"))))
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/axe")
    assert ic.preflight(env()) == {"ok": True, "state": "ready", "phone": U, "line": None}
    assert ["xcrun", "simctl", "list", "devices", "-j"] in [c[0] for c in f.calls]


def test_preflight_cli_reads_the_environment_and_exits_by_ok(fake, monkeypatch, capsys):
    fake(sim(inventory((U, "Booted"))))
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/axe")
    monkeypatch.setenv("SUPERHEROES_IPHONE_ID", U)
    monkeypatch.setenv("SUPERHEROES_DEVICE_HUB", "available")
    assert ic.main(["preflight"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "ready"
    monkeypatch.setenv("SUPERHEROES_IPHONE_ID", "none")
    assert ic.main(["preflight"]) == 1
    assert json.loads(capsys.readouterr().out)["line"] == UFR5_LITERAL


# ---------------------------------------------------------------- never returns
def test_timeout_is_never_returned(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(ic.subprocess, "run", boom)
    assert ic._run(["x"], 1) == (False, None, "")


def test_drive_shot_boot_and_open_that_never_return_are_returned_false(fake, tmp_path):
    fake(lambda argv: (False, None, ""))
    d = ic.drive(U, ["tap", "-x", "1", "-y", "2"], 5)
    assert d == {"ok": False, "returned": False, "exit": None, "stdout": ""}
    s = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
    assert s["ok"] is False and s["returned"] is False and s["labels"] is None and s["sha256"] is None
    assert s["labelNote"] is None
    b = ic.boot(U, 5)
    assert b == {"ok": False, "returned": False, "line": PRE + "the phone's boot never returned"}
    o = ic.open_url(U, "http://x.test/", str(tmp_path), 5)
    assert o["ok"] is False and o["returned"] is False
    assert not os.path.exists(tmp_path / "sessions")


def test_shot_whose_inventory_never_returns_is_returned_false_with_no_labels(fake, tmp_path):
    fake(sim((False, None, "")))
    s = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
    assert s["ok"] is False and s["returned"] is False and s["labels"] is None and s["sha256"] is None


def test_a_driver_exit_code_zero_is_not_a_step_passing_and_nonzero_is_not_ok(fake):
    fake(helper_sim(["up"], axe=(True, 3, "oops")))
    assert ic.drive(U, ["type", "hello"], 5) == {"ok": False, "returned": True, "exit": 3, "stdout": "oops",
                                                 "helper": "up"}


def test_boot_runs_boot_then_bootstatus_and_only_bootstatus_decides(fake):
    f = fake(lambda argv: (True, 149, "") if argv[2] == "boot" else (True, 0, ""))
    assert ic.boot(U, 60) == {"ok": True, "returned": True, "line": None}
    assert [c[0] for c in f.calls] == [["xcrun", "simctl", "boot", U], ["xcrun", "simctl", "bootstatus", U, "-b"]]
    fake(lambda argv: (True, 0, "") if argv[2] == "boot" else (True, 1, ""))
    assert ic.boot(U, 60) == {"ok": False, "returned": True, "line": PRE + "the phone did not boot"}


# ---------------------------------------------------------------- AXe workaround
def test_drive_tap_gets_stabilization_env_and_a_post_delay_before_the_udid(fake):
    f = fake(helper_sim(["up"]))
    out = ic.drive(U, ["tap", "-x", "1", "-y", "2"], 30)
    argv, timeout, env_ = axe_calls(f)[0]
    assert argv == ["axe", "tap", "-x", "1", "-y", "2", "--post-delay", "1", "--udid", U]
    assert env_["AXE_HID_STABILIZATION_MS"] == "2000" and 0 < timeout <= 30
    assert out["ok"] is True and out["returned"] is True and out["exit"] == 0


def test_drive_tap_keeps_the_callers_post_delay(fake):
    f = fake(helper_sim(["up"]))
    ic.drive(U, ["tap", "--post-delay", "2", "-x", "1", "-y", "2"], 30)
    assert axe_calls(f)[0][0] == ["axe", "tap", "--post-delay", "2", "-x", "1", "-y", "2", "--udid", U]
    ic.drive(U, ["tap", "-x", "1", "--post-delay=3"], 30)
    assert axe_calls(f)[1][0] == ["axe", "tap", "-x", "1", "--post-delay=3", "--udid", U]


def test_drive_non_tap_gets_no_post_delay_and_still_ends_with_the_udid(fake):
    f = fake(helper_sim(["up"]))
    ic.drive(U, ["type", "hello"], 30)
    ic.drive(U, ["swipe", "--start-x", "1"], 30)
    for argv, _, env_ in [c for c in f.calls if c[0][0] == "axe"]:
        assert "--post-delay" not in argv and argv[-2:] == ["--udid", U]
        assert env_["AXE_HID_STABILIZATION_MS"] == "2000"
    assert axe_calls(f)[0][0] == ["axe", "type", "hello", "--udid", U]


def test_drive_button_names_reach_axe_in_lower_case(fake):
    f = fake(helper_sim(["up"]))
    ic.drive(U, ["button", "HOME"], 30)
    ic.drive(U, ["button", "home"], 30)
    ic.drive(U, ["button", "Side-Button", "--duration", "1"], 30)
    assert [c[0] for c in axe_calls(f)] == [["axe", "button", "home", "--udid", U],
                                            ["axe", "button", "home", "--udid", U],
                                            ["axe", "button", "side-button", "--duration", "1", "--udid", U]]


def test_drive_only_lower_cases_a_button_name_not_other_arguments(fake):
    f = fake(helper_sim(["up"]))
    ic.drive(U, ["type", "HOME"], 30)
    ic.drive(U, ["button"], 30)
    assert [c[0] for c in axe_calls(f)] == [["axe", "type", "HOME", "--udid", U], ["axe", "button", "--udid", U]]


def test_drive_cli_splits_axe_args_after_the_double_dash(fake, capsys):
    f = fake(helper_sim(["up"]))
    assert ic.main(["drive", "--phone", U, "--timeout", "9", "--", "tap", "-x", "1", "-y", "2"]) == 0
    assert axe_calls(f)[0][0] == ["axe", "tap", "-x", "1", "-y", "2", "--post-delay", "1", "--udid", U]
    assert 0 < axe_calls(f)[0][1] <= 9
    assert json.loads(capsys.readouterr().out)["exit"] == 0
    with pytest.raises(SystemExit) as e:
        ic.main(["boot"])
    assert e.value.code == 2


# ---------------------------------------------------------------- typing helper
REFUSED = {"ok": False, "returned": True, "exit": None, "stdout": "", "helper": "down",
           "reason": "the phone's typing helper is not running"}
NEVER = {"ok": False, "returned": False, "exit": None, "stdout": ""}


def test_drive_with_the_helper_running_checks_once_then_runs_axe(fake):
    f = fake(helper_sim(["up"]))
    out = ic.drive(U, ["type", "hello"], 30)
    assert out == {"ok": True, "returned": True, "exit": 0, "stdout": "", "helper": "up"}
    assert verbs(f) == ["list", "axe"]


def test_drive_restarts_a_stopped_helper_and_runs_axe_once_it_is_up(fake):
    f = fake(helper_sim(["down", "up"]))
    out = ic.drive(U, ["type", "hello"], 30)
    assert out["ok"] is True and out["helper"] == "restarted"
    assert verbs(f) == ["list", "kickstart", "list", "axe"]
    assert f.calls[1][0] == ["xcrun", "simctl", "spawn", U, "launchctl", "kickstart", "system/com.apple.coredevice.dtuhidd"]


def test_drive_with_the_helper_still_down_refuses_and_never_runs_axe(fake):
    f = fake(helper_sim(["down", "down"]))
    assert ic.drive(U, ["type", "hello"], 30) == REFUSED
    assert verbs(f) == ["list", "kickstart", "list"]


def test_a_dropped_keystroke_is_never_reported_as_ok(fake):
    fake(helper_sim(["down"], axe=(True, 0, "")))
    assert ic.drive(U, ["type", "hello"], 30)["ok"] is False


@pytest.mark.parametrize("state", ["down", 113, 149])
def test_a_helper_that_is_stopped_or_unlisted_is_not_running_and_is_restarted(fake, state):
    f = fake(helper_sim([state, "up"]))
    assert ic.drive(U, ["type", "hello"], 30)["helper"] == "restarted"
    assert verbs(f) == ["list", "kickstart", "list", "axe"]


def test_the_kickstarts_exit_code_does_not_decide_the_recheck_does(fake):
    fake(helper_sim(["down", "up"], kickstart=(True, 1, "")))
    assert ic.drive(U, ["type", "hello"], 30)["helper"] == "restarted"
    fake(helper_sim(["down", "down"], kickstart=(True, 0, "")))
    assert ic.drive(U, ["type", "hello"], 30) == REFUSED


@pytest.mark.parametrize("states,kickstart,calls", [
    (["never"], (True, 0, ""), ["list"]),
    (["down", "up"], (False, None, ""), ["list", "kickstart"]),
    (["down", "never"], (True, 0, ""), ["list", "kickstart", "list"]),
])
def test_a_helper_call_that_never_returns_is_returned_false_and_axe_does_not_run(fake, states, kickstart, calls):
    f = fake(helper_sim(states, kickstart=kickstart))
    assert ic.drive(U, ["type", "hello"], 30) == NEVER
    assert verbs(f) == calls


@pytest.mark.parametrize("verb", ["describe-ui", "list-simulators", "screenshot"])
def test_a_read_only_verb_makes_no_helper_call_and_keeps_the_callers_timeout(fake, verb):
    f = fake(helper_sim(["down"]))
    out = ic.drive(U, [verb], 30)
    assert verbs(f) == ["axe"] and f.calls[0][1] == 30
    assert out == {"ok": True, "returned": True, "exit": 0, "stdout": ""}


@pytest.mark.parametrize("verb", ["type", "key", "key-sequence", "key-combo", "button", "tap", "swipe", "touch",
                                  "drag", "gesture", "batch", "frobnicate"])
def test_every_verb_outside_the_read_only_set_checks_the_helper_first(fake, verb):
    f = fake(helper_sim(["up"]))
    ic.drive(U, [verb], 30)
    assert verbs(f) == ["list", "axe"]
    assert f.calls[0][0] == ["xcrun", "simctl", "spawn", U, "launchctl", "list", "com.apple.coredevice.dtuhidd"]


@pytest.mark.parametrize("states,kickstart", [
    (["up"], (True, 0, "")), (["down", "up"], (True, 0, "")), (["down", "down"], (True, 0, "")),
    (["never"], (True, 0, "")), (["down", "up"], (False, None, "")), (["down", "never"], (True, 0, "")),
])
def test_drive_only_runs_axe_or_launchctl_inside_the_handed_phone(fake, states, kickstart):
    f = fake(helper_sim(states, kickstart=kickstart))
    ic.drive(U, ["type", "hello"], 30)
    for argv, _, _ in f.calls:
        assert argv[0] == "axe" or (argv[:3] == ["xcrun", "simctl", "spawn"] and argv[3] == U and argv[4] == "launchctl")
        assert not {"shutdown", "erase", "delete", "kill", "bootout", "booted"} & set(argv)


def ticking(monkeypatch, responder, steps):
    """Wrap a responder so each recorded call advances a controllable clock by the next amount in `steps` (seconds)."""
    now, queue = [0.0], list(steps)
    monkeypatch.setattr(ic.time, "monotonic", lambda: now[0])

    def respond(argv):
        now[0] += queue.pop(0) if queue else 0
        return responder(argv)
    return respond


def test_every_call_in_a_checked_drive_gets_exactly_the_time_remaining_on_the_callers_deadline(fake, monkeypatch):
    f = fake(ticking(monkeypatch, helper_sim(["down", "up"]), [2, 3, 5]))
    assert ic.drive(U, ["type", "hello"], 30)["helper"] == "restarted"
    assert verbs(f) == ["list", "kickstart", "list", "axe"]
    assert [t for _, t, _ in f.calls] == pytest.approx([30, 28, 25, 20])


def test_a_spent_deadline_stops_a_checked_drive_before_axe(fake, monkeypatch):
    f = fake(ticking(monkeypatch, helper_sim(["up"]), [31]))
    assert ic.drive(U, ["type", "hello"], 30) == NEVER
    assert verbs(f) == ["list"]


@pytest.mark.parametrize("steps,calls", [([30], ["list"]), ([0, 30], ["list", "kickstart"])])
def test_a_spent_deadline_stops_a_checked_drive_before_the_kickstart_and_before_the_recheck(fake, monkeypatch, steps, calls):
    f = fake(ticking(monkeypatch, helper_sim(["down", "up"]), steps))
    assert ic.drive(U, ["type", "hello"], 30) == NEVER
    assert verbs(f) == calls


@pytest.mark.parametrize("states", [["up"], ["down", "up"]])
def test_an_axe_call_that_never_returns_after_a_checked_helper_carries_no_helper(fake, states):
    f = fake(helper_sim(states, axe=(False, None, "")))
    assert ic.drive(U, ["type", "hello"], 30) == NEVER
    assert verbs(f)[-1] == "axe"


# ---------------------------------------------------------------- labels / shot
def test_device_labels_map_the_device_type_and_runtime_key():
    inv = json.loads(inventory((U, "Booted")))
    assert ic.device_labels(inv, U) == {"model": "iPhone 17", "iOS": "27.0", "state": "Booted"}
    assert ic.device_labels(inv, U.lower())["model"] == "iPhone 17"
    inv2 = {"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-18-6": [
        {"udid": V, "state": "Shutdown", "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-16-Pro-Max"}]}}
    assert ic.device_labels(inv2, V) == {"model": "iPhone 16 Pro Max", "iOS": "18.6", "state": "Shutdown"}
    assert ic.device_labels(inv, V) is None
    assert ic.device_labels({"devices": {"com.apple.CoreSimulator.SimRuntime.watchOS-11-0": inv2["devices"][
        "com.apple.CoreSimulator.SimRuntime.iOS-18-6"]}}, V) is None
    assert ic.device_labels(None, V) is None


def test_shot_labels_the_phone_from_the_inventory_not_the_environment(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERHEROES_IPHONE_ID", U)
    f = fake(sim(inventory((U, "Booted", "com.apple.CoreSimulator.SimDeviceType.iPhone-16"), (V, "Booted"))))
    out = str(tmp_path / "a.png")
    with Phone(make_session(tmp_path, V), page="http://x.test/p"):
        r = ic.shot(V, out, str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["returned"] is True and r["path"] == out
    assert r["labels"] == {"phone": V, "model": "iPhone 17", "iOS": "27.0", "page": "http://x.test/p",
                           "where": "browser", "source": "Simulator"}
    assert r["sha256"] == hashlib.sha256(b"png-bytes").hexdigest()
    assert f.calls[0][0] == ["xcrun", "simctl", "io", V, "screenshot", out]


def test_shot_refuses_a_phone_that_is_not_booted(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERHEROES_IPHONE_ID", U)
    fake(sim(inventory((U, "Booted"), (V, "Shutdown"))))
    with Phone(make_session(tmp_path, V)):
        r = ic.shot(V, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is False and r["labels"] is None and r["sha256"] is None


def test_shot_with_a_failed_screenshot_is_not_ok_and_has_no_labels(fake, tmp_path):
    fake(sim(inventory((U, "Booted")), screenshot=(True, 1, "")))
    r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is False and r["returned"] is True and r["labels"] is None and r["labelNote"] is None


def test_open_appends_the_reading_param_and_writes_the_session(fake, tmp_path):
    f = fake()
    r = ic.open_url(U, "http://x.test/p?a=1#frag", str(tmp_path), 30)
    assert r["ok"] is True and re.fullmatch(r"[0-9a-f]{16}", r["token"])
    want = f"http://x.test/p?a=1&{ic.READING_PARAM}=http://127.0.0.1:{r['port']}/{r['token']}#frag"
    assert r["url"] == want and f.calls[0][0] == ["xcrun", "simctl", "openurl", U, want]
    sess = json.loads((tmp_path / "sessions" / (r["token"] + ".json")).read_text())
    assert sess == {"token": r["token"], "port": r["port"], "phone": U, "url": want}


# ---------------------------------------------------------------- read (real loopback)
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def reading(**kw):
    r = {"visibleHeight": 700, "focused": None, "valueWithheld": False, "where": "installed",
         "visibility": "visible", "page": "http://x.test/p", "takenAt": int(time.time() * 1000) + 50}
    r.update(kw)
    return r


class Session:
    def __init__(self, tmp_path, monkeypatch, fake, where="installed", timeout=3, state="Booted"):
        fake(sim(inventory((U, state))))
        self.token, self.port, self.result = "abc123", _free_port(), {}
        os.makedirs(tmp_path / "sessions")
        (tmp_path / "sessions" / "abc123.json").write_text(json.dumps(
            {"token": "abc123", "port": self.port, "phone": U, "url": "u"}))
        self.thread = threading.Thread(
            target=lambda: self.result.update(ic.read(str(tmp_path), "abc123", where, timeout)))
        self.thread.start()
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.02)

    def post(self, body, token=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/{token or self.token}", method="POST",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "text/plain"})
        try:
            urllib.request.urlopen(req, timeout=3).close()
        except OSError:
            pass  # a server that already accepted a reading has closed: the assertion on the result decides

    def finish(self):
        self.thread.join(10)
        assert not self.thread.is_alive()
        return self.result


def test_read_accepts_a_matching_fresh_visible_reading(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake)
    s.post(reading(visibleHeight=321, focused={"tag": "input", "type": "text", "id": "name", "name": "name"}, value="hi"))
    r = s.finish()
    assert r["ok"] is True and r["returned"] is True and r["reading"]["visibleHeight"] == 321
    assert r["reading"]["value"] == "hi" and r["reading"]["valueWithheld"] is False
    assert r["labels"] == {"phone": U, "model": "iPhone 17", "iOS": "27.0", "page": "http://x.test/p",
                           "where": "installed", "source": "Simulator"}


def test_read_ignores_reading_from_the_wrong_context(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake, where="installed", timeout=1)
    s.post(reading(where="browser"))
    r = s.finish()
    assert r["returned"] is False and r["ok"] is False and r["reading"] is None and r["labels"] is None


def test_read_ignores_a_hidden_reading(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake)
    s.post(reading(visibleHeight=111, visibility="hidden"))
    s.post(reading(visibleHeight=222))
    assert s.finish()["reading"]["visibleHeight"] == 222


def test_read_ignores_a_post_with_the_wrong_token(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake)
    s.post(reading(visibleHeight=111), token="deadbeef")
    s.post(reading(visibleHeight=222))
    assert s.finish()["reading"]["visibleHeight"] == 222


def test_read_ignores_a_reading_taken_before_the_call_started(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake)
    s.post(reading(visibleHeight=111, takenAt=int(time.time() * 1000) - 60000))
    s.post(reading(visibleHeight=222))
    assert s.finish()["reading"]["visibleHeight"] == 222


def test_read_with_no_usable_reading_by_the_deadline_returns_false(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake, timeout=1)
    s.post({"where": "installed", "visibility": "visible"})
    s.post(reading(takenAt="now"))
    r = s.finish()
    assert r["returned"] is False and r["ok"] is False and r["reading"] is None


def test_read_strips_the_value_of_a_password_focused_reading(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake)
    s.post(reading(focused={"tag": "input", "type": "password", "id": "secret", "name": "secret"}, value="s3cret-hello"))
    r = s.finish()
    assert r["ok"] is True and "value" not in r["reading"] and r["reading"]["valueWithheld"] is True
    assert "s3cret" not in json.dumps(r)


def test_read_strips_the_reading_param_from_the_page_label(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake)
    s.post(reading(page=f"http://x.test/p?a=1&{ic.READING_PARAM}=http://127.0.0.1:9/abc123&b=2#top"))
    assert s.finish()["labels"]["page"] == "http://x.test/p?a=1&b=2#top"
    assert ic._page_label(f"http://x.test/p?{ic.READING_PARAM}=http://127.0.0.1:9/t") == "http://x.test/p"
    assert ic._page_label("http://x.test/p") == "http://x.test/p"


def test_read_of_a_phone_that_is_not_booted_yields_no_reading(tmp_path, monkeypatch, fake):
    s = Session(tmp_path, monkeypatch, fake, state="Shutdown")
    s.post(reading())
    r = s.finish()
    assert r["ok"] is False and r["reading"] is None and r["labels"] is None


def test_read_without_a_session_is_not_ok(tmp_path):
    r = ic.read(str(tmp_path), "abc123", "installed", 1)
    assert r["ok"] is False and r["reading"] is None
    assert ic.read(str(tmp_path), "../x", "installed", 1)["ok"] is False


def test_accept_reading_and_strip_password_value_directly():
    now = 1000
    ok = reading(takenAt=now)
    assert ic.accept_reading(ok, "/t", "t", "installed", now) is True
    assert ic.accept_reading(ok, "/t", "t", "installed", now + 1) is False
    assert ic.accept_reading(ok, "/u", "t", "installed", now) is False
    assert ic.accept_reading(ok, "/t", "t", "browser", now) is False
    assert ic.accept_reading({**ok, "visibility": "hidden"}, "/t", "t", "installed", now) is False
    assert ic.accept_reading({**ok, "takenAt": True}, "/t", "t", "installed", 0) is False
    assert ic.accept_reading([], "/t", "t", "installed", now) is False
    pw = reading(focused={"tag": "input", "type": "PASSWORD"}, value="x")
    out = ic.strip_password_value(pw)
    assert "value" not in out and out["valueWithheld"] is True and pw["value"] == "x"


# ---------------------------------------------------------------- shot (real loopback, the phone's page played by a thread)
PAGE_A, PAGE_B = "http://x.test/a", "http://x.test/b"
MISSING = object()
NE = ic.NOT_ESTABLISHED


def make_session(tmp_path, phone=U, token="abc123", **override):
    """Write a session file for `token` and return its port; `override` replaces (or, with MISSING, drops) keys."""
    port = _free_port()
    sess = {"token": token, "port": port, "phone": phone, "url": "u", **override}
    os.makedirs(tmp_path / "sessions", exist_ok=True)
    (tmp_path / "sessions" / f"{token}.json").write_text(
        json.dumps({k: v for k, v in sess.items() if v is not MISSING}))
    return port


def _post(port, token, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/{token}", method="POST", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "text/plain"})
    try:
        urllib.request.urlopen(req, timeout=1).close()
        return True
    except OSError:
        return False  # no listener (yet, or any more): the page's fetch fails and the page tries again


class Phone:
    """The phone's page: posts a reading to the session's port every ~50 ms. `page` and `where` may be switched live;
    a MISSING value drops the key; `max_posts` stops it after that many accepted posts."""

    def __init__(self, port, page=PAGE_A, where="browser", token="abc123", max_posts=None, **extra):
        self.port, self.token, self.page, self.where, self.max_posts, self.extra = port, token, page, where, max_posts, extra
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def reading(self):
        r = reading(takenAt=math.ceil(time.time() * 1000), **self.extra)  # rounded up: never below the call-start `shot` races
        r["page"], r["where"] = self.page, self.where
        return {k: v for k, v in r.items() if v is not MISSING}

    def _run(self):
        # Wait for a listener first: a reading built before `shot` began is stale and would be dropped though it was posted
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()
                break
            except OSError:
                if self.stop.wait(0.01):
                    return
        posted = 0
        while not self.stop.is_set() and (self.max_posts is None or posted < self.max_posts):
            if _post(self.port, self.token, self.reading()):
                posted += 1
            self.stop.wait(0.05)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(5)


def on_screenshot(during):
    """A responder that plays the inventory and the screenshot, and runs `during()` while the screenshot is taken."""
    base = sim(inventory((U, "Booted")))

    def respond(argv):
        if "screenshot" in argv:
            during()
        return base(argv)
    return respond


def established(page, where):
    return {"phone": U, "model": "iPhone 17", "iOS": "27.0", "page": page, "where": where, "source": "Simulator"}


@pytest.fixture
def quick(monkeypatch):
    """Pinned condition: READING_WAIT is 0.4 s. Production shape the pin makes unobservable: the 3 s patience for a slow page."""
    monkeypatch.setattr(ic, "READING_WAIT", 0.4)


def test_shot_labels_follow_the_page_the_phone_shows_now_not_the_one_before(fake, tmp_path):
    f = fake(sim(inventory((U, "Booted"))))
    port, out = make_session(tmp_path), str(tmp_path / "a.png")
    with Phone(port, page=PAGE_A, where="browser") as phone:
        first = ic.shot(U, out, str(tmp_path), "abc123", 30)
        phone.page = PAGE_B
        second = ic.shot(U, out, str(tmp_path), "abc123", 30)
    assert first["ok"] is True and first["labels"] == established(PAGE_A, "browser") and first["labelNote"] is None
    assert second["ok"] is True and second["labels"] == established(PAGE_B, "browser") and second["labelNote"] is None
    assert f.calls[0][0] == ["xcrun", "simctl", "io", U, "screenshot", out]


def test_shot_where_is_installed_when_the_readings_come_from_the_installed_app(fake, tmp_path):
    fake(sim(inventory((U, "Booted"))))
    port = make_session(tmp_path, phone=U.lower())
    with Phone(port, where="installed"):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(PAGE_A, "installed") and r["labelNote"] is None


def test_shot_with_a_session_from_another_phone_establishes_nothing_and_starts_no_listener(fake, tmp_path):
    f = fake(sim(inventory((U, "Booted"))))
    port = make_session(tmp_path, phone=V)
    with Phone(port):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and r["labelNote"]
    assert f.calls[0][0][:5] == ["xcrun", "simctl", "io", U, "screenshot"]
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), 0.2).close()


@pytest.mark.parametrize("write", [None, "not json", '{"token": "abc123", "phone": "%s"}' % U, '["abc123"]'],
                         ids=["no-file", "malformed", "no-port", "not-an-object"])
def test_shot_without_a_usable_session_still_captures_and_establishes_nothing(fake, tmp_path, write):
    f = fake(sim(inventory((U, "Booted"))))
    out = str(tmp_path / "a.png")
    if write is not None:
        os.makedirs(tmp_path / "sessions")
        (tmp_path / "sessions" / "abc123.json").write_text(write)
    r = ic.shot(U, out, str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and r["labelNote"]
    assert f.calls[0][0] == ["xcrun", "simctl", "io", U, "screenshot", out]


@pytest.mark.parametrize("token", ["../x", "ABC", ""], ids=["traversal", "upper-case", "empty"])
def test_shot_with_a_bad_token_still_captures_and_establishes_nothing(fake, tmp_path, token):
    fake(sim(inventory((U, "Booted"))))
    make_session(tmp_path)
    r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), token, 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and r["labelNote"]


def test_shot_with_no_reading_at_all_establishes_nothing(fake, tmp_path, quick):
    fake(sim(inventory((U, "Booted"))))
    make_session(tmp_path)
    r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and "before" in r["labelNote"]


def test_shot_with_a_reading_before_the_capture_and_none_after_establishes_nothing(fake, tmp_path, quick):
    fake(sim(inventory((U, "Booted"))))
    port = make_session(tmp_path)
    with Phone(port, max_posts=1):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and "after" in r["labelNote"]


def test_shot_when_the_page_changes_during_the_capture_establishes_no_page(fake, tmp_path):
    port = make_session(tmp_path)
    with Phone(port) as phone:
        fake(on_screenshot(lambda: setattr(phone, "page", PAGE_B)))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, "browser") and "page" in r["labelNote"]


def test_shot_when_the_page_goes_away_and_comes_back_establishes_no_page(fake, tmp_path):
    port = make_session(tmp_path)

    def away_and_back():
        phone.page = PAGE_B
        time.sleep(0.3)  # readings for the other page are received mid-capture
        phone.page = PAGE_A
    with Phone(port) as phone:
        fake(on_screenshot(away_and_back))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, "browser")


@pytest.mark.parametrize("page", [MISSING, None, "", "   ", 7, {"href": PAGE_A}, f"?{ic.READING_PARAM}=http://127.0.0.1:9/abc123"],
                         ids=["missing", "null", "empty", "blank", "number", "object", "only-the-reading-param"])
def test_shot_with_an_unusable_page_in_the_readings_establishes_no_page(fake, tmp_path, page):
    fake(sim(inventory((U, "Booted"))))
    port = make_session(tmp_path)
    with Phone(port, page=page):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, "browser") and r["labelNote"]


def test_shot_with_a_where_outside_browser_and_installed_establishes_no_where_but_keeps_the_page(fake, tmp_path):
    fake(sim(inventory((U, "Booted"))))
    port = make_session(tmp_path)
    with Phone(port, where="Safari"):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(PAGE_A, NE) and r["labelNote"]


def test_shot_does_not_count_a_late_pre_capture_packet_as_the_reading_after(fake, tmp_path, quick):
    port, late = make_session(tmp_path), []

    def during():
        time.sleep(0.02)
        # taken before the screenshot returned, but received only after it
        packet = reading(page=PAGE_A, where="browser", takenAt=int(time.time() * 1000) - 1)
        late.append(threading.Thread(target=lambda: (time.sleep(0.15), _post(port, "abc123", packet))))
        late[0].start()
    fake(on_screenshot(during))
    with Phone(port, max_posts=1):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    late[0].join(5)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and "after" in r["labelNote"]


def test_shot_does_not_count_a_reading_received_before_the_capture_returned_as_the_reading_after(fake, tmp_path, quick):
    port = make_session(tmp_path)
    # a page clock running ahead: taken "after" the capture, but received while it was still being taken
    fake(on_screenshot(lambda: _post(port, "abc123", reading(page=PAGE_A, where="browser",
                                                              takenAt=int(time.time() * 1000) + 60000))))
    with Phone(port, max_posts=1):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE) and "after" in r["labelNote"]


def test_shot_returns_within_its_budget_when_a_post_stalls(fake, tmp_path):
    fake(sim(inventory((U, "Booted"))))
    port, release = make_session(tmp_path), threading.Event()

    def stall():
        for _ in range(100):
            try:
                conn = socket.create_connection(("127.0.0.1", port), 0.2)
            except OSError:
                time.sleep(0.02)
                continue
            with conn:  # headers and a promised body, then silence
                conn.sendall(b"POST /abc123 HTTP/1.1\r\nHost: x\r\nContent-Length: 1000\r\n\r\n{")
                release.wait(8)
            return
    thread = threading.Thread(target=stall)
    thread.start()
    began = time.monotonic()
    r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 0.5)
    elapsed = time.monotonic() - began
    release.set()
    thread.join(5)
    assert elapsed < 0.5 + 1, elapsed  # inside timeout + 3 s, and short of a fixed 2 s socket timeout
    assert r["ok"] is True and r["labels"] == established(NE, NE)


def test_shot_establishes_nothing_when_a_token_matched_reading_starts_during_the_capture_and_never_completes(fake, tmp_path):
    port, release = make_session(tmp_path), threading.Event()
    conns = []

    def stall():  # a token-matched POST begins mid-capture: headers and a partial body, then silence until the call ends
        conn = socket.create_connection(("127.0.0.1", port), 1)
        conns.append(conn)
        conn.sendall(b"POST /abc123 HTTP/1.1\r\nHost: x\r\nContent-Length: 1000\r\n\r\n{")
        time.sleep(0.2)
    with Phone(port, page=PAGE_A, where="browser"):  # steady visible page-A readings before and after the capture
        fake(on_screenshot(stall))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
        release.set()
        for conn in conns:
            conn.close()
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "cut off" in r["labelNote"]


def test_shot_when_the_page_leaves_the_foreground_during_the_capture_establishes_nothing(fake, tmp_path):
    port = make_session(tmp_path)

    def away_and_back():
        phone.extra["visibility"] = "hidden"
        time.sleep(0.3)  # hidden readings are posted mid-capture
        phone.extra["visibility"] = "visible"
    with Phone(port) as phone:
        fake(on_screenshot(away_and_back))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "foreground" in r["labelNote"]


def test_shot_when_the_page_was_already_hidden_as_the_capture_began_establishes_nothing(fake, tmp_path):
    port = make_session(tmp_path)
    captured, stop = threading.Event(), threading.Event()

    def post(**kw):
        _post(port, "abc123", reading(page=PAGE_A, where="browser", takenAt=math.ceil(time.time() * 1000), **kw))

    def phone_page():
        for _ in range(100):  # wait for the listener
            try:
                socket.create_connection(("127.0.0.1", port), 0.2).close()
                break
            except OSError:
                time.sleep(0.02)
        older_visible = reading(page=PAGE_A, where="browser", takenAt=math.ceil(time.time() * 1000))
        time.sleep(0.01)
        post(visibility="hidden")  # the newer hidden reading lands first ...
        _post(port, "abc123", older_visible)  # ... then the older visible packet is delivered late
        captured.wait(10)  # the screenshot is taken while the page is hidden
        while not stop.is_set():  # the page returns to the foreground after the capture
            post()
            stop.wait(0.05)

    def screenshot():
        time.sleep(0.2)
        captured.set()

    thread = threading.Thread(target=phone_page)
    thread.start()
    fake(on_screenshot(screenshot))
    try:
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    finally:
        captured.set()
        stop.set()
        thread.join(5)
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "foreground" in r["labelNote"]


def test_shot_establishes_nothing_when_a_connection_stalls_inside_the_request_headers(fake, tmp_path):
    port, conns = make_session(tmp_path), []

    def stall():  # request bytes arrive, but the headers never finish: no reading was ever delivered
        conn = socket.create_connection(("127.0.0.1", port), 1)
        conns.append(conn)
        conn.sendall(b"POST /abc123 HTTP/1.1\r\nHost: x\r\nContent-Len")
        time.sleep(0.2)
    with Phone(port, page=PAGE_A, where="browser"):
        fake(on_screenshot(stall))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
        for conn in conns:
            conn.close()
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "cut off" in r["labelNote"]


def test_shot_establishes_nothing_when_a_token_matched_reading_during_the_capture_has_no_visibility(fake, tmp_path):
    port = make_session(tmp_path)

    def unknown():
        r = reading(page=PAGE_A, where="browser", takenAt=int(time.time() * 1000))
        del r["visibility"]
        _post(port, "abc123", r)
        time.sleep(0.2)
    with Phone(port, page=PAGE_A, where="browser"):
        fake(on_screenshot(unknown))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "foreground" in r["labelNote"]


def test_shot_establishes_nothing_when_an_other_context_reading_during_the_capture_has_no_visibility(fake, tmp_path):
    port = make_session(tmp_path)

    def unknown_other_context():
        r = reading(page=PAGE_B, where="installed", takenAt=int(time.time() * 1000))
        del r["visibility"]
        _post(port, "abc123", r)
        time.sleep(0.2)
    with Phone(port, page=PAGE_A, where="browser"):
        fake(on_screenshot(unknown_other_context))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "foreground" in r["labelNote"]


def test_shot_establishes_nothing_when_a_visible_and_a_hidden_reading_share_the_latest_pre_capture_time(fake, tmp_path):
    port = make_session(tmp_path)
    captured, stop, tied_at, capture_ms = threading.Event(), threading.Event(), [], []

    def post(**kw):
        _post(port, "abc123", reading(page=PAGE_A, where="browser", **kw))

    def phone_page():
        for _ in range(100):  # wait for the listener
            try:
                socket.create_connection(("127.0.0.1", port), 0.2).close()
                break
            except OSError:
                time.sleep(0.02)
        tied = math.ceil(time.time() * 1000)
        tied_at.append(tied)
        time.sleep(0.01)  # the listener receives the pair, and `shot` can start capturing, only after the tied instant
        post(takenAt=tied, visibility="visible")  # visible delivered first ...
        post(takenAt=tied, visibility="hidden")  # ... then the hidden reading taken at the very same moment
        captured.wait(10)
        while not stop.is_set():  # the page is visible again after the capture
            post(takenAt=math.ceil(time.time() * 1000))
            stop.wait(0.05)

    def screenshot():
        capture_ms.append(time.time() * 1000)
        time.sleep(0.2)
        captured.set()

    thread = threading.Thread(target=phone_page)
    thread.start()
    fake(on_screenshot(screenshot))
    try:
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    finally:
        captured.set()
        stop.set()
        thread.join(5)
    # The pair is tied strictly before the capture began, so the hidden one meets the tie check, not the during-capture check
    assert len(tied_at) == 1 and len(capture_ms) == 1 and tied_at[0] < capture_ms[0], (tied_at, capture_ms)
    assert r["ok"] is True and r["labels"] == established(NE, NE)
    assert r["labelNote"] and "foreground" in r["labelNote"]


def test_shot_ignores_a_hidden_reading_from_the_other_context_during_the_capture(fake, tmp_path):
    port = make_session(tmp_path)

    def safari_hidden():
        _post(port, "abc123", reading(page=PAGE_B, where="browser", visibility="hidden", takenAt=int(time.time() * 1000)))
        time.sleep(0.2)
    with Phone(port, page=PAGE_A, where="installed"):
        fake(on_screenshot(safari_hidden))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 5)
    assert r["ok"] is True and r["labels"] == established(PAGE_A, "installed")
    assert r["labelNote"] is None


def test_shot_counts_a_reading_taken_during_the_capture_that_lands_after_the_reading_after(fake, tmp_path, monkeypatch):
    port, late, froze, in_flight = make_session(tmp_path), [], [], threading.Event()
    frozen = threading.Event()

    class FreezeSignalling(ic.Listener):
        def shutdown(self):  # `shot` shuts the listener down only once it has the reading after the capture: the window freezes
            super().shutdown()
            frozen.set()
    monkeypatch.setattr(ic, "Listener", FreezeSignalling)

    def during():
        packet = json.dumps(reading(page=PAGE_B, where="browser", takenAt=int(time.time() * 1000))).encode()

        def slow_post():
            with socket.create_connection(("127.0.0.1", port), 2) as c:
                c.sendall(b"POST /abc123 HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(packet) + packet[:5])
                in_flight.set()
                # Release the rest of the body only once the listener is shutting down, i.e. the window is frozen
                froze.append(frozen.wait(10))
                c.sendall(packet[5:])
                c.recv(100)
        late.append(threading.Thread(target=slow_post, daemon=True))
        late[0].start()
        assert in_flight.wait(10)  # the partial request is in flight before the screenshot returns
    with Phone(port, page=PAGE_A, where="browser") as phone:
        fake(on_screenshot(during))
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    late[0].join(5)
    assert froze == [True]
    assert r["ok"] is True and r["labels"] == established(NE, "browser") and "page changed" in r["labelNote"]


def test_shot_returns_within_its_budget_when_a_post_body_keeps_trickling(fake, tmp_path):
    fake(sim(inventory((U, "Booted"))))
    port, release = make_session(tmp_path), threading.Event()

    def trickle():  # a promised 1000-byte body, one byte every 100 ms: never idle long enough for a socket timeout
        for _ in range(100):
            try:
                conn = socket.create_connection(("127.0.0.1", port), 0.2)
            except OSError:
                time.sleep(0.02)
                continue
            with conn:
                try:
                    conn.sendall(b"POST /abc123 HTTP/1.1\r\nHost: x\r\nContent-Length: 1000\r\n\r\n")
                    for _ in range(100):
                        conn.sendall(b" ")
                        if release.wait(0.1):
                            break
                except OSError:
                    pass
            return
    thread = threading.Thread(target=trickle)
    thread.start()
    began = time.monotonic()
    r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 0.5)
    elapsed = time.monotonic() - began
    release.set()
    thread.join(5)
    assert elapsed < 1.5, elapsed
    assert r["ok"] is True and r["labels"] == established(NE, NE)


def test_shot_never_returns_a_reading_value(fake, tmp_path):
    fake(sim(inventory((U, "Booted"))))
    port = make_session(tmp_path)
    with Phone(port, value="s3cret", focused={"tag": "input", "type": "text", "id": "name", "name": "name"}):
        r = ic.shot(U, str(tmp_path / "a.png"), str(tmp_path), "abc123", 30)
    assert r["labels"] == established(PAGE_A, "browser")
    assert "s3cret" not in json.dumps(r)


@pytest.mark.parametrize("retired", [["--page", "http://x.test/"], ["--where", "browser"]], ids=["--page", "--where"])
def test_shot_takes_no_page_or_where_argument(fake, tmp_path, capsys, retired):
    argv = ["shot", "--phone", U, "--out", str(tmp_path / "a.png"), "--run-dir", str(tmp_path), "--token", "abc123",
            "--timeout", "2"]
    with pytest.raises(SystemExit) as e:
        ic.main([*argv, *retired])
    assert e.value.code == 2
    fake(sim(inventory((U, "Booted"))))
    assert ic.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["labels"] == established(NE, NE) and isinstance(out["labelNote"], str)


# ---------------------------------------------------------------- render
@pytest.mark.parametrize("missing", ["phone", "model", "iOS", "page", "where", "source"])
def test_render_refuses_a_piece_missing_a_label(missing):
    lb = labels()
    del lb[missing]
    with pytest.raises(ValueError):
        ic.render(chk(where=["browser"], evidence=[{**ev_shot("browser"), "labels": lb}]))
    blank = labels(**{missing: " "})
    with pytest.raises(ValueError):
        ic.render(chk(where=["browser"], evidence=[{**ev_shot("browser"), "labels": blank}]))


def test_render_refuses_a_source_other_than_simulator():
    with pytest.raises(ValueError):
        ic.render(chk(where=["browser"], evidence=[ev_shot("browser", source="Device")]))


def test_render_refuses_a_reading_whose_where_label_disagrees_with_the_reading():
    with pytest.raises(ValueError):
        ic.render(chk(where=["installed"], evidence=[ev_reading("installed", where="browser", lwhere="installed")]))


def test_render_refuses_a_reading_without_a_reading_and_a_screenshot_without_a_location():
    with pytest.raises(ValueError):
        ic.render(chk(where=["installed"], evidence=[{**ev_reading(), "reading": None}]))
    with pytest.raises(ValueError):
        ic.render(chk(where=["browser"], evidence=[{**ev_shot("browser"), "path": None}]))


@pytest.mark.parametrize("bad", [{"where": "installed"}, {**rd(where="installed"), "visibleHeight": None},
                                 {**rd(where="installed"), "visibleHeight": "700"},
                                 {k: v for k, v in rd(where="installed").items() if k != "focused"}],
                         ids=["truncated", "height-null", "height-string", "focused-missing"])
def test_render_refuses_an_incomplete_reading_and_it_never_counts_as_installed_evidence(bad):
    ev = {**ev_reading(), "reading": bad}
    c = chk(where=["installed"], parts={"browser": part(included=False), "installed": part(completed=True)},
            evidence=[ev])
    with pytest.raises(ValueError):
        ic.render(c)
    assert ic.did_not_run_lines(c) == [
        "iPhone check did not run — installed-app check: no page reading from the installed app"]


def test_render_refuses_a_reading_whose_where_is_neither_browser_nor_installed():
    ev = {**ev_reading(), "reading": rd(where="other"), "labels": labels(where="other")}
    with pytest.raises(ValueError):
        ic.render(chk(where=["installed"], evidence=[ev]))


def test_render_accepts_a_reading_whose_focused_is_null():
    ev = {**ev_reading(), "reading": rd(focus=None, where="installed")}
    _, section = ic.render(chk(where=["installed"], parts={"browser": part(included=False),
                                                           "installed": part(completed=True)}, evidence=[ev]))
    assert "focused none" in section


def test_render_prints_a_screenshot_whose_page_and_where_are_not_established_and_refuses_a_foreign_where():
    ev = {**ev_shot("browser"), "labels": labels(page=ic.NOT_ESTABLISHED, where=ic.NOT_ESTABLISHED)}
    _, section = ic.render(chk(where=["browser"], evidence=[ev]))
    assert f"`page` {ic.NOT_ESTABLISHED} · `where` {ic.NOT_ESTABLISHED}" in section
    with pytest.raises(ValueError, match="evidence 1"):
        ic.render(chk(where=["browser"], evidence=[{**ev_shot("browser"), "labels": labels(where="Safari")}]))


def test_render_a_screenshot_with_only_a_path_is_a_plain_line_never_an_image():
    _, section = ic.render(chk(where=["browser"], evidence=[ev_shot("browser")]))
    assert f"screenshot file (on the capturing Mac, not posted): /r/a.png · sha256 {SHA}" in section
    assert "![" not in section


def test_render_a_screenshot_with_a_url_is_an_image():
    ev = {**ev_shot("browser"), "url": "https://files.example/a.png"}
    _, section = ic.render(chk(where=["browser"], evidence=[ev]))
    assert "![Home](https://files.example/a.png)" in section
    assert "screenshot file" not in section


@pytest.mark.parametrize("drop", [("url", "sha256", "path"), ("url", "sha256"), ("url", "path")])
def test_render_refuses_a_screenshot_with_neither_url_nor_path_and_sha256(drop):
    ev = {k: v for k, v in ev_shot("browser").items() if k not in drop}
    with pytest.raises(ValueError):
        ic.render(chk(where=["browser"], evidence=[ev]))


def test_render_never_shows_a_password_value_even_if_the_evidence_carries_one():
    r = rd(value="s3cret-hello", ftype="password", where="installed")
    ev = {**ev_reading(), "reading": r}
    _, section = ic.render(chk(where=["installed"], evidence=[ev]))
    assert "s3cret" not in section and "value withheld" in section


def test_render_lays_out_one_screenshot_and_one_reading_exactly():
    check = chk(where=["browser"], parts={"browser": part(completed=True), "installed": part(included=False)},
                evidence=[{**ev_shot("browser"), "url": "https://files.example/a.png"},
                          {**ev_reading("browser", "browser"), "caption": "After typing"}])
    opening, section = ic.render(check)
    assert opening == ""
    label_line = ("`phone` 0A1B2C3D-4E5F-6789-ABCD-0123456789AB · `model` iPhone 17 · `iOS` 27.0 · "
                  "`page` http://x.test/ · `where` browser · `source` Simulator")
    assert section == "\n\n".join([
        "### iPhone check",
        "**Where the check ran:** in the browser — chosen by the issue.",
        "**Checked at commit:** `abc1234`",
        "**What a simulator cannot show:** a real finger's touch (the timing and imprecision of a human tap, and "
        "multi-finger gestures) and real-device speed.",
        "#### iPhone evidence 1 — screenshot (browser): Home",
        label_line,
        "![Home](https://files.example/a.png)",
        "#### iPhone evidence 2 — reading (browser): After typing",
        label_line,
        'visible height 700 · focused input#name (text) · value "v"',
    ])


def test_render_reading_lines_for_withheld_none_and_no_focus():
    def line_for(r):
        _, section = ic.render(chk(where=["browser"], evidence=[{**ev_reading("browser", "browser"), "reading": r}]))
        return section.split("\n\n")[-1]
    pw = {**rd(ftype="password", where="browser"), "valueWithheld": True}
    assert line_for(pw) == "visible height 700 · focused input#name (password) · value withheld"
    assert line_for(rd(focus=None, where="browser")) == "visible height 700 · focused none · value none"


def test_render_puts_each_did_not_run_line_in_its_own_paragraph_and_keeps_earlier_evidence():
    c = chk(parts={"browser": part(completed=True), "installed": part(reason="the Home Screen install failed")},
            evidence=[ev_reading("browser", "browser")])
    opening, section = ic.render(c)
    assert opening == "iPhone check did not run — installed-app check: the Home Screen install failed"
    assert "#### iPhone evidence 1 — reading (browser): c" in section
    both = chk(parts={"browser": part(reason="a"), "installed": part(reason="b")})
    assert ic.render(both)[0] == ("iPhone check did not run — browser check: a\n\n"
                                  "iPhone check did not run — installed-app check: b")


def installed_done():
    return {"browser": part(completed=True), "installed": part(completed=True)}


def test_a_superseded_installed_reading_never_completes_the_installed_part():
    old = {**ev_reading("installed", "installed"), "superseded": True}
    c = chk(parts=installed_done(), evidence=[ev_reading("browser", "browser"), old])
    assert ic.did_not_run_lines(c) == [
        "iPhone check did not run — installed-app check: no page reading from the installed app"]
    opening, _ = ic.render(c)
    assert opening == "iPhone check did not run — installed-app check: no page reading from the installed app"
    live = chk(parts=installed_done(), evidence=[old, ev_reading("installed", "installed")])
    assert ic.did_not_run_lines(live) == []


def test_render_lists_superseded_attempts_after_the_live_evidence_and_never_in_the_opening():
    parts = {"browser": {**part(completed=True), "superseded": ["the keyboard tip covered the field"]},
             "installed": {**part(completed=True), "superseded": ["Safari fell back to its Start Page", "second"]}}
    old_shot = {**ev_shot("browser"), "caption": "First try", "superseded": True}
    old_read = {**ev_reading("installed", "installed"), "caption": "Old read", "superseded": True}
    c = chk(parts=parts, evidence=[old_shot, ev_reading("browser", "browser"), old_read,
                                   {**ev_reading("installed", "installed"), "caption": "Final", "superseded": False}])
    opening, section = ic.render(c)
    assert opening == ""
    paras = section.split("\n\n")
    heads = [x for x in paras if x.startswith("#### ")]
    assert heads == ["#### iPhone evidence 1 — reading (browser): c",
                     "#### iPhone evidence 2 — reading (installed): Final",
                     "#### Superseded attempts",
                     "#### Superseded evidence 1 — screenshot (browser): First try",
                     "#### Superseded evidence 2 — reading (installed): Old read"]
    at = paras.index("#### Superseded attempts")
    assert paras[at + 1:at + 4] == [
        "`browser check`: earlier attempt did not complete — the keyboard tip covered the field",
        "`installed-app check`: earlier attempt did not complete — Safari fell back to its Start Page",
        "`installed-app check`: earlier attempt did not complete — second"]
    assert "First try" not in "\n\n".join(paras[:at])


def test_render_without_any_superseded_attempt_has_no_superseded_heading():
    _, section = ic.render(chk(where=["browser"], evidence=[ev_shot("browser")]))
    assert "Superseded" not in section


@pytest.mark.parametrize("bad", ["keyboard tip", ["ok", " "], [""], [7], {"a": "b"}, None],
                         ids=["string", "blank-entry", "empty-string", "non-string", "dict", "null"])
def test_render_refuses_a_malformed_superseded_list(bad):
    c = chk(parts={"browser": {**part(completed=True), "superseded": bad}, "installed": part(included=False)},
            where=["browser"], evidence=[ev_shot("browser")])
    with pytest.raises(ValueError, match="superseded"):
        ic.render(c)


@pytest.mark.parametrize("bad", ["true", 1, None, "no"])
def test_render_refuses_a_piece_whose_superseded_is_not_a_bool(bad):
    with pytest.raises(ValueError, match="superseded"):
        ic.render(chk(where=["browser"], evidence=[{**ev_shot("browser"), "superseded": bad}]))


def test_render_validates_a_superseded_piece_like_any_other():
    old = {**ev_shot("browser", source="Device"), "superseded": True}
    with pytest.raises(ValueError, match="Simulator"):
        ic.render(chk(where=["browser"], evidence=[ev_shot("browser"), old]))
    lb = labels(where="browser")
    del lb["page"]
    with pytest.raises(ValueError, match="six labels"):
        ic.render(chk(where=["browser"], evidence=[{**ev_shot("browser"), "labels": lb, "superseded": True}]))


def test_render_prints_the_commit_right_after_the_where_line():
    _, section = ic.render(chk(where=["browser"], commit="0123abc", evidence=[ev_shot("browser")]))
    paras = section.split("\n\n")
    assert paras[1].startswith("**Where the check ran:**") and paras[2] == "**Checked at commit:** `0123abc`"
    _, section = ic.render(chk(where=["browser"], commit="a" * 40, evidence=[ev_shot("browser")]))
    assert "`" + "a" * 40 + "`" in section


@pytest.mark.parametrize("bad", [None, "", "HEAD", "abcdef", "ABC1234", "abc123g", "a" * 41, 1234567, "abc1234\n"],
                         ids=["null", "empty", "HEAD", "six-hex", "upper-case", "non-hex", "too-long", "non-string",
                              "newline"])
def test_render_refuses_evidence_without_a_usable_commit(bad):
    c = chk(where=["browser"], evidence=[ev_shot("browser")])
    c["commit"] = bad
    with pytest.raises(ValueError, match="commit"):
        ic.render(c)
    del c["commit"]
    with pytest.raises(ValueError, match="commit"):
        ic.render(c)


def test_render_needs_no_commit_without_evidence():
    no_commit = {"noPhone": True, "whole": None, "where": [], "parts": {}, "evidence": []}
    assert ic.render(no_commit) == (UFR5_LITERAL, "")
    opening, section = ic.render({"noPhone": False, "whole": "Device Hub unavailable", "where": ["browser"],
                                  "parts": {}, "evidence": []})
    assert opening.endswith("Device Hub unavailable") and section == ""
    _, section = ic.render({"where": ["browser"], "chosenBy": "lane", "parts": {}, "evidence": []})
    assert "Checked at commit" not in section


def test_render_no_phone_is_the_ufr5_line_alone_with_no_section():
    assert ic.render({"noPhone": True, "whole": None, "where": [], "parts": {}, "evidence": []}) == (UFR5_LITERAL, "")


def test_judge_and_render_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(step(kind="other", expected="menu", expectedSeen=False))))
    assert ic.main(["judge"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["completed"] is False and isinstance(out["reason"], str)
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert ic.main(["judge"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    path = tmp_path / "check.json"
    path.write_text(json.dumps(chk(where=["browser"], evidence=[ev_shot("browser", source="Device")])), encoding="utf-8")
    assert ic.main(["render", "--in", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    path.write_text(json.dumps(chk(where=["browser"], evidence=[ev_shot("browser")])), encoding="utf-8")
    assert ic.main(["render", "--in", str(path)]) == 0
    section = json.loads(capsys.readouterr().out)["section"]
    assert f"screenshot file (on the capturing Mac, not posted): /r/a.png · sha256 {SHA}" in section


def test_judge_cli_hands_back_the_shared_part_reason_only_for_a_not_completed_named_step(monkeypatch, capsys):
    def judged(st):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(st)))
        ic.main(["judge"])
        return json.loads(capsys.readouterr().out)
    assert ic.NO_RESPONSE == "no response to input"
    out = judged(step(kind="other", step="tap Save", expected="menu", expectedSeen=False))
    assert out["completed"] is False and out["partReason"] == "no response to input (tap Save)"
    assert "partReason" not in judged(step(kind="other", step="tap Save", expected="menu", expectedSeen=True))
    for nameless in ("", None, 7):
        out = judged(step(kind="other", step=nameless, expected="menu", expectedSeen=False))
        assert out["completed"] is False and "partReason" not in out
    no_key = step(kind="other", expected="menu", expectedSeen=False)
    del no_key["step"]
    assert "partReason" not in judged(no_key)


# ---------------------------------------------------------------- the fixture page
def test_fixture_page_has_the_fields_and_ships_no_external_resource():
    html = open(FIXTURE, encoding="utf-8").read()
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "<h1>" in html
    assert re.search(r'<input[^>]*type="text"[^>]*id="name"[^>]*style="font-size:14px"', html)
    assert re.search(r'<input[^>]*type="password"[^>]*id="secret"[^>]*style="font-size:14px"', html)
    assert 'for="name"' in html and 'for="secret"' in html
    assert "manifest" not in html and "<link" not in html and "src=" not in html
    assert "keepalive:true" in html.replace(" ", "") and "mode:'no-cors'" in html.replace(" ", "")


def _need_node():
    if shutil.which("node") is None:
        if os.environ.get("CI"):
            pytest.fail("node is required to run the fixture page's reporting script in CI")
        pytest.skip("node is not on PATH")


_RUNNER = r"""
const vm = require('vm'), fs = require('fs');
const [, , scriptPath, kind, param] = process.argv;
let accesses = 0;
const el = kind === 'password'
  ? Object.defineProperty({tagName: 'INPUT', type: 'password', id: 'secret', name: 'secret'}, 'value',
      {get() { accesses++; return 's3cret-hello'; }})
  : {tagName: 'INPUT', type: 'text', id: 'name', name: 'name', value: 'hello'};
const listeners = {}, bodies = [], intervals = [];
const doc = {activeElement: el, body: {tagName: 'BODY'}, visibilityState: 'visible',
  addEventListener(t, f) { (listeners[t] = listeners[t] || []).push(f); }};
const search = kind === 'absent' ? '' : '?' + param + '=http://127.0.0.1:9/tok';
const sb = {document: doc, location: {search, href: 'http://x.test/' + search},
  visualViewport: {height: 612.4, addEventListener(t, f) { (listeners['vv-' + t] = listeners['vv-' + t] || []).push(f); }},
  innerHeight: 800, navigator: {standalone: false}, matchMedia: () => ({matches: false}), URLSearchParams,
  setInterval(f, ms) { intervals.push(ms); }, fetch(u, o) { bodies.push(o.body); return Promise.resolve(); }};
sb.window = sb;
vm.createContext(sb);
vm.runInContext(fs.readFileSync(scriptPath, 'utf8'), sb);
const afterLoad = bodies.length;
(listeners.focusin || []).forEach(f => f());
console.log(JSON.stringify({bodies, afterLoad, accesses, intervals, events: Object.keys(listeners).sort(),
  built: vm.runInContext('buildReading()', sb)}));
"""


_PARAM_PLACEHOLDER = "__READING_PARAM__"


def _run_fixture_script(tmp_path, kind):
    _need_node()
    script = re.search(r"<script>(.*?)</script>", open(FIXTURE, encoding="utf-8").read(), re.S).group(1)
    assert script.count(_PARAM_PLACEHOLDER) == 1, f"the page script must carry {_PARAM_PLACEHOLDER} exactly once"
    script = script.replace(_PARAM_PLACEHOLDER, ic.READING_PARAM)
    (tmp_path / "page.js").write_text(script, encoding="utf-8")
    (tmp_path / "runner.js").write_text(_RUNNER, encoding="utf-8")
    proc = subprocess.run(["node", str(tmp_path / "runner.js"), str(tmp_path / "page.js"), kind, ic.READING_PARAM],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_fixture_script_withholds_password_value(tmp_path):
    out = _run_fixture_script(tmp_path, "password")
    secret = "s3cret-hello"
    assert out["accesses"] == 0, "the script read the password field's .value"
    assert len(out["bodies"]) >= 2
    for body in out["bodies"] + [json.dumps(out["built"])]:
        r = json.loads(body)
        assert r["valueWithheld"] is True and "value" not in r
        assert r["focused"] == {"tag": "input", "type": "password", "id": "secret", "name": "secret"}
        # the focused identity (id "secret") and the key valueWithheld legitimately share letters with the secret
        rest = json.dumps({k: v for k, v in r.items() if k not in ("focused", "valueWithheld")})
        assert secret not in body and "hello" not in body
        assert not [secret[i:i + 3] for i in range(len(secret) - 2) if secret[i:i + 3] in rest]


def test_fixture_script_sends_a_text_value_and_the_reading_shape(tmp_path):
    out = _run_fixture_script(tmp_path, "text")
    r = json.loads(out["bodies"][-1])
    assert r["value"] == "hello" and r["valueWithheld"] is False
    assert r["focused"] == {"tag": "input", "type": "text", "id": "name", "name": "name"}
    assert r["visibleHeight"] == 612 and r["where"] == "browser" and r["visibility"] == "visible"
    assert r["page"].startswith("http://x.test/") and isinstance(r["takenAt"], int)
    assert out["afterLoad"] == 1 and out["intervals"] == [500]
    assert {"focusin", "focusout", "input", "visibilitychange", "vv-resize"} <= set(out["events"])


def test_fixture_script_does_nothing_when_the_reading_param_is_absent(tmp_path):
    out = _run_fixture_script(tmp_path, "absent")
    assert out["bodies"] == [] and out["events"] == [] and out["intervals"] == [] and out["accesses"] == 0
