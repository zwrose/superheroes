"""Tests for cloud_relay (#1748 C7-WO-B): the relay session and its exact-text check.

No test runs a real `claude` command: `run` is a fake that answers `claude agents --json` and
`claude --bg ...` from scripted outputs and records argv, env and cwd. The relay's session record
is a fixture file written in the measured shape under a temporary config dir. `check` runs on a
fake clock whose sleep advances it.
"""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_relay as cr  # noqa: E402
import engine_adapter  # noqa: E402
import launch_ledger  # noqa: E402

SESSION = "builder-1748"
RELAY_ID = "5534cbe0-5d2a-4783-8980-09c4bafd22ad"
BEFORE = "2000-01-01T00:00:00.000Z"
AFTER = "2999-01-01T00:00:00.000Z"
TEXT = "Use the narrow fix.\nSecond line ✓ \"quoted\" & <angle>\n"


class FakeRun:
    """Scripted answers: `lists` is consumed one per `agents --json`; `start` is the exit code of
    `claude --bg`, with `start_out` and `start_err` as what it printed. Every call's argv, env and
    cwd are recorded. `claude --version` prints `version_out` (exit `version_code`); `claude stop`
    exits `stop` and prints `stop_err`."""

    def __init__(self, lists=(), start=0, list_code=0, start_out="backgrounded", start_err="",
                 version_out="2.1.316 (Claude Code)", version_code=0, stop=0, stop_err=""):
        self.calls = []
        self.lists = list(lists)
        self.start = start
        self.list_code = list_code
        self.start_out = start_out
        self.start_err = start_err
        self.version_out = version_out
        self.version_code = version_code
        self.stop = stop
        self.stop_err = stop_err

    def __call__(self, argv, **kwargs):
        self.calls.append(SimpleNamespace(argv=list(argv), env=kwargs.get("env"),
                                          cwd=kwargs.get("cwd")))
        if argv == ["claude", "--version"]:
            return SimpleNamespace(returncode=self.version_code, stdout=self.version_out, stderr="")
        if argv[:2] == ["claude", "stop"]:
            return SimpleNamespace(returncode=self.stop, stdout="", stderr=self.stop_err)
        if argv[:3] == ["claude", "agents", "--json"]:
            out = self.lists.pop(0) if len(self.lists) > 1 else (self.lists[0] if self.lists else "[]")
            if isinstance(out, BaseException):
                raise out
            return SimpleNamespace(returncode=self.list_code, stdout=out)
        return SimpleNamespace(returncode=self.start, stdout=self.start_out,
                               stderr=self.start_err)

    def starts(self):
        return [c for c in self.calls if c.argv[:2] == ["claude", "--bg"]]

    def stops(self):
        return [c for c in self.calls if c.argv[:2] == ["claude", "stop"]]

    def versions(self):
        return [c for c in self.calls if c.argv == ["claude", "--version"]]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def _entry(name, state="working", **extra):
    entry = {"id": "daf1d3b4", "cwd": "/x", "kind": "background", "startedAt": 1789474395431,
             "sessionId": RELAY_ID, "name": name}
    if state is not None:
        entry["state"] = state
    entry.update(extra)
    return entry


@pytest.fixture
def world(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    root = tmp_path / "ledger-root"
    root.mkdir(mode=0o700)
    config = tmp_path / ".claude-two"
    (config / "projects" / "-some-dir").mkdir(parents=True)
    env = {launch_ledger.LEDGER_ROOT_ENV: str(root), "PATH": os.environ.get("PATH", "")}
    return SimpleNamespace(repo=str(repo), config=str(config), env=env,
                           record=str(config / "projects" / "-some-dir" / (RELAY_ID + ".jsonl")),
                           state=None)


def _state_file(world):
    path, why = cr._state_path(world.repo, world.env)
    assert why is None
    return path


def _ensure_alive(world):
    run = FakeRun(lists=[json.dumps([_entry(cr.relay_name(world.config), pid=4242, status="busy")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True
    return out


def _compose(world, text=TEXT, session=SESSION):
    tf = os.path.join(os.path.dirname(world.record), "text.txt")
    with open(tf, "w", encoding="utf-8") as fh:
        fh.write(text)
    out = cr.compose(world.repo, world.config, session, open(tf, encoding="utf-8").read(),
                     env=world.env)
    assert out["ok"] is True
    return out


def _backdate(world, msg_id, stamp):
    path = _state_file(world)
    state = json.load(open(path))
    state["pending"][msg_id]["sentAfter"] = stamp
    json.dump(state, open(path, "w"))


def _send_lines(tool_id, to, message, stamp, success=True, result=True, result_text=None):
    lines = [{"type": "assistant", "timestamp": stamp, "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": "SendMessage",
         "input": {"to": to, "message": message, "summary": "s"}}]}}]
    if result:
        text = result_text if result_text is not None else json.dumps(
            {"success": success, "message": "sent" if success else "No agent named 'x' is reachable"})
        lines.append({"type": "user", "timestamp": stamp, "message": {"content": [
            {"type": "tool_result", "tool_use_id": tool_id,
             "content": [{"type": "text", "text": text}]}]}})
    return lines


def _write_record(world, *line_groups, raw=()):
    with open(world.record, "w", encoding="utf-8") as fh:
        for line in raw:
            fh.write(line + "\n")
        for group in line_groups:
            for rec in group:
                fh.write(json.dumps(rec) + "\n")


def _check(world, msg_id, wait=60, interval=2):
    clock = Clock()
    out = cr.check(world.repo, msg_id, wait=wait, interval=interval, env=world.env,
                   clock=clock, sleep=clock.sleep)
    return out, clock


def _composed(world, stamp=BEFORE):
    _ensure_alive(world)
    msg = _compose(world)
    _backdate(world, msg["msgId"], stamp)
    return msg


# ---- the exact-text check -------------------------------------------------------------------

def test_exact_text_with_success_is_delivered(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"])
    assert out["ok"] is True and out["delivered"] is True and out["reason"] is None
    state = json.load(open(_state_file(world)))
    assert state["pending"][msg["msgId"]]["decision"]["delivered"] is True


def test_one_character_difference_is_a_mismatch(world):
    # Exact text, not a normalized comparison: a dropped letter and a dropped newline (which a
    # whitespace-normalizing comparison would hide) are each one character short of the forward text.
    for needle, offset in (("narrow", 0), ("\n\nUse", 1)):
        msg = _composed(world)
        sent = msg["forward"]
        cut = sent.index(needle) + offset
        altered = sent[:cut] + sent[cut + 1:]
        _write_record(world, _send_lines("toolu_1", SESSION, altered, "2026-10-12T10:00:00.000Z"))
        out, clock = _check(world, msg["msgId"])
        assert out["ok"] is False and out["delivered"] is False
        assert out["reason"] == "relay-text-mismatch"
        assert out["firstDifference"]["index"] == cut
        assert out["firstDifference"]["expected"] == sent[cut:cut + 20]
        assert out["firstDifference"]["sent"] == altered[cut:cut + 20]
        assert "not delivered" in out["say"] and msg["msgId"] in out["say"]
        assert clock.t == 0  # decided at once, no waiting


def test_trailing_difference_is_a_mismatch(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"] + " ", "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"])
    assert out["reason"] == "relay-text-mismatch"
    assert out["firstDifference"]["index"] == len(msg["forward"])


def test_silent_relay_is_reported_after_the_wait(world):
    msg = _composed(world)
    _write_record(world, [])
    out, clock = _check(world, msg["msgId"], wait=10, interval=2)
    assert out["ok"] is False and out["delivered"] is False and out["reason"] == "relay-silent"
    assert "within 10 seconds" in out["say"] and "not delivered" in out["say"]
    assert clock.t >= 10


def test_missing_record_is_reported_as_silent_after_the_wait(world):
    msg = _composed(world)
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "within 4 seconds" in out["say"] and "not delivered" in out["say"]


def test_exact_text_refused_by_the_session_is_send_failed(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z",
                                     success=False))
    out, clock = _check(world, msg["msgId"])
    assert out["ok"] is False and out["reason"] == "relay-send-failed"
    assert "No agent named" in out["say"] and clock.t >= 60


def test_exact_send_without_result_is_unconfirmed_at_the_end(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z",
                                     result=False))
    out, clock = _check(world, msg["msgId"], wait=6, interval=2)
    assert out["reason"] == "relay-send-unconfirmed" and clock.t >= 6


def test_result_arriving_during_the_wait_is_delivered(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z",
                                     result=False))
    clock = Clock()

    def sleep(seconds):
        clock.sleep(seconds)
        _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"],
                                         "2026-10-12T10:00:00.000Z"))

    out = cr.check(world.repo, msg["msgId"], wait=30, interval=2, env=world.env,
                   clock=clock, sleep=sleep)
    assert out["delivered"] is True and clock.t == 2


STAMP = "2026-10-12T10:00:00.000Z"


def test_a_failed_attempt_then_a_recorded_retry_success_is_delivered(world):
    # axis: retry success — a failed send followed by a recorded successful retry is delivered — a failure that sticks makes it fail
    msg = _composed(world)
    _write_record(world,
                  _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                  _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))
    out, clock = _check(world, msg["msgId"], wait=60)
    assert out["ok"] is True and out["delivered"] is True and out["reason"] is None
    assert clock.t == 0


def test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered(world):
    # axis: retry success during the wait — a retry success that lands mid-wait is delivered — a failure that ends the wait early makes it fail
    msg = _composed(world)
    failed = _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False)
    _write_record(world, failed)
    clock = Clock()

    def sleep(seconds):
        clock.sleep(seconds)
        _write_record(world, failed, _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))

    out = cr.check(world.repo, msg["msgId"], wait=30, interval=2, env=world.env,
                   clock=clock, sleep=sleep)
    assert out["delivered"] is True and clock.t == 2


def test_only_failed_attempts_are_send_failed_at_the_end_of_the_wait(world):
    # axis: failure only at the end of the wait — send-failed is reported after the full wait, not before — a failure reported early makes it fail
    msg = _composed(world)
    _write_record(world,
                  _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                  _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP, success=False))
    out, clock = _check(world, msg["msgId"], wait=10, interval=2)
    assert out["ok"] is False and out["reason"] == "relay-send-failed"
    assert "No agent named" in out["say"] and clock.t >= 10


def test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed(world):
    # axis: unconfirmed over failed — a retry with no result outranks an earlier failure at the end of the wait — a failed verdict makes it fail
    msg = _composed(world)
    _write_record(world,
                  _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                  _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP, result=False))
    out, clock = _check(world, msg["msgId"], wait=6, interval=2)
    assert out["reason"] == "relay-send-unconfirmed" and clock.t >= 6


@pytest.mark.parametrize("to", [
    "someone-else [3fa9c1]", "[3fa9c1]", "3fa9c1", SESSION + " []", SESSION + "  [x]",
    SESSION + " [a b]", SESSION + " [x]y", SESSION + " [x[y]", SESSION + "x [3fa9c1]",
    SESSION + " [3fa9c1] ", SESSION + "[3fa9c1]"])
def test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send(world, to):
    # axis: strict recipient form — only `<session> [<ref>]` is this session's send — a loose bracket match makes it fail
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", to, msg["forward"], STAMP))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False


def test_a_bracketed_send_with_altered_text_is_a_mismatch(world):
    # axis: text check — altered text to a bracketed recipient is a mismatch — a text check skipped for the bracketed form makes it fail
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION + " [3fa9c1]", msg["forward"][:-1], STAMP))
    out, clock = _check(world, msg["msgId"])
    assert out["reason"] == "relay-text-mismatch" and out["delivered"] is False and clock.t == 0


def test_the_disambiguated_recipient_form_is_session_space_bracketed_ref(world):
    # axis: literal pin — the host SendMessage `to` form is `<session> [<ref>]` — a changed form makes it fail
    # Literal pin of the host SendMessage tool's `to` form: `worker [3fa9c1]` (CONVENTIONS §11.3).
    assert "%s [3fa9c1]" % SESSION == "builder-1748 [3fa9c1]"
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", "%s [3fa9c1]" % SESSION, msg["forward"], STAMP))
    out, _ = _check(world, msg["msgId"])
    assert out["delivered"] is True


def test_send_to_another_session_is_ignored(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", "someone-else", msg["forward"][:-3],
                                     "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent"


def test_send_stamped_before_sent_after_is_ignored(world):
    msg = _composed(world, stamp=AFTER)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False


@pytest.mark.parametrize("stamp, aware", [
    ("2026-10-12T10:00:00.000Z", True), ("2026-10-12T10:00:00+00:00", True),
    ("2026-10-12T10:00:00+02:00", True), ("2026-10-12T10:00:00", False),
    ("not a time", False), ("", False), (None, False), (12, False)])
def test_a_relay_stamp_reads_as_a_time_only_when_it_carries_a_zone(stamp, aware):
    when = cr._time(stamp)
    assert (when is not None) is aware
    assert when is None or when.tzinfo is not None


# axis: a record stamped without a zone is skipped, not compared with the aware sentAfter — see bite-proof record c8a_wo4.md
def test_a_send_stamped_without_a_zone_neither_raises_nor_counts_as_delivered(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent"


def test_a_sent_after_without_a_zone_reads_every_send_as_not_after_it(world):
    # `_sends` is skipped altogether when `sentAfter` is unreadable: nothing is attributed, the message is silent.
    msg = _composed(world, stamp="2000-01-01T00:00:00")
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent"


def test_altered_send_beats_an_exact_send_for_the_same_message(world):
    # E6: one successful altered send plus one successful exact send is a mismatch, not delivered.
    msg = _composed(world)
    sent = msg["forward"]
    cut = sent.index("narrow")
    altered = sent[:cut] + sent[cut + 1:]
    _write_record(world,
                  _send_lines("toolu_1", SESSION, altered, "2026-10-12T10:00:00.000Z"),
                  _send_lines("toolu_2", SESSION, sent, "2026-10-12T10:00:01.000Z"))
    out, clock = _check(world, msg["msgId"])
    assert out["ok"] is False and out["delivered"] is False
    assert out["reason"] == "relay-text-mismatch" and out["firstDifference"]["index"] == cut
    assert clock.t == 0


def test_another_pending_messages_send_is_not_this_messages_mismatch(world):
    # E7: a send carrying another pending message's id is that message's, even when altered.
    _ensure_alive(world)
    first = _compose(world, text="first body")
    second = _compose(world, text="second body")
    for msg in (first, second):
        _backdate(world, msg["msgId"], BEFORE)
    other = second["forward"]
    altered_other = other.replace("second", "secnd")
    _write_record(world,
                  _send_lines("toolu_1", SESSION, other, "2026-10-12T10:00:00.000Z"),
                  _send_lines("toolu_2", SESSION, altered_other, "2026-10-12T10:00:01.000Z"),
                  _send_lines("toolu_3", SESSION, first["forward"], "2026-10-12T10:00:02.000Z"))
    out, _ = _check(world, first["msgId"])
    assert out["delivered"] is True and out["reason"] is None
    out, _ = _check(world, second["msgId"])
    assert out["reason"] == "relay-text-mismatch"  # its own altered send still counts against it


def test_send_with_no_header_is_not_attributed_to_the_message(world):
    # E8: a send to the session that does not open with this message's header line is not its send;
    # with no send attributed the message ends silent, not mismatched.
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, "Use the narrow fix.", "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "firstDifference" not in out


# axis: a send is this message's only when it starts with this message's own header line — see bite-proof record c8a_wo4.md
def test_a_body_that_quotes_another_messages_id_does_not_fool_that_messages_check(world):
    _ensure_alive(world)
    a = _compose(world, text="first body")
    b = _compose(world, text="second body")
    # message A's forwarded text quotes B's id in its body
    quoting = "%s\n\nsee (id %s)" % (cr.FORWARD_HEADER % a["msgId"], b["msgId"])
    state = json.load(open(_state_file(world)))
    state["pending"][a["msgId"]]["forward"] = quoting
    json.dump(state, open(_state_file(world), "w"))
    for msg in (a, b):
        _backdate(world, msg["msgId"], BEFORE)
    # only A's send exists: B must not take it as its own (a mismatch)
    _write_record(world, _send_lines("toolu_1", SESSION, quoting, "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, b["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent"
    out, _ = _check(world, a["msgId"])
    assert out["delivered"] is True
    # an exact delivery of B is read as delivered, with A's quoting send alongside
    _write_record(world,
                  _send_lines("toolu_1", SESSION, quoting, "2026-10-12T10:00:00.000Z"),
                  _send_lines("toolu_2", SESSION, b["forward"], "2026-10-12T10:00:01.000Z"))
    out, _ = _check(world, b["msgId"])
    assert out["delivered"] is True and out["reason"] is None


def test_leading_whitespace_before_the_header_still_attributes_the_send(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, "  \n" + msg["forward"], "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"])
    assert out["reason"] == "relay-text-mismatch"  # attributed, but not the exact text


def test_a_send_quoting_this_messages_header_mid_text_is_not_its_send(world):
    # axis: a send is this message's only when its header line is at the start, not quoted mid-text — see bite-proof record c8c_wo_a.md
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, "Note first.\n" + msg["forward"],
                                     "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent"
    assert "firstDifference" not in out


def test_a_send_opening_with_the_header_minus_its_colon_is_not_this_messages_send(world):
    # axis: the header line's final colon is part of the match, so a send without it is not attributed — see bite-proof record c8c_wo_a.md
    msg = _composed(world)
    header = cr.FORWARD_HEADER % msg["msgId"]
    assert header.endswith(":")
    _write_record(world, _send_lines("toolu_1", SESSION, header[:-1] + "\n\nbody",
                                     "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent"
    assert "firstDifference" not in out


def test_a_send_whose_header_line_carries_more_text_is_attributed_and_a_mismatch(world):
    # axis: a send opening with the complete header line is attributed even with more text after it on that line, so it is a mismatch and never silent — see bite-proof record c8c_wo_a.md
    msg = _composed(world)
    header = cr.FORWARD_HEADER % msg["msgId"]
    _write_record(world, _send_lines("toolu_1", SESSION, header + " extra\n\nbody",
                                     "2026-10-12T10:00:00.000Z"))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-text-mismatch"
    assert "firstDifference" in out


def _header_dropped(msg):
    """The forward text with its header line dropped: the body, as the relay's record showed it."""
    return msg["forward"].split("\n\n", 1)[1]


@pytest.mark.parametrize("to", [SESSION, SESSION + " [8af960]"], ids=["bare", "bracketed"])
def test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered(world, to):
    # axis: header-dropped attribution — a send of exactly the forward text minus its header line is this message sent altered, never delivered — a send the header rule drops as foreign makes it read silent
    # The recorded shape of relay message 817905576fcf: right session, success true, header line gone.
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", to, _header_dropped(msg), STAMP))
    out, clock = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["ok"] is False and out["delivered"] is False
    assert out["reason"] == "relay-text-mismatch" and out["headerDropped"] is True
    assert "header line dropped" in out["say"] and "not delivered" in out["say"]
    assert "character" not in out["say"] and msg["msgId"] in out["say"]
    assert clock.t >= 4  # provisional while the wait runs
    assert out["firstDifference"]["index"] == 0
    assert out["firstDifference"]["sent"] == _header_dropped(msg)[:20]


def test_a_header_dropped_send_after_leading_whitespace_is_still_header_dropped(world):
    # axis: header-dropped attribution ignores leading whitespace — the exact suffix from the blank line on is the same send — a whitespace-sensitive match makes it read silent
    msg = _composed(world)
    header = cr.FORWARD_HEADER % msg["msgId"]
    suffix = msg["forward"][len(header):]
    assert suffix.startswith("\n\n")
    _write_record(world, _send_lines("toolu_1", SESSION, suffix, STAMP))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-text-mismatch" and out["headerDropped"] is True
    assert out["delivered"] is False


@pytest.mark.parametrize("text", [
    "A different body entirely.",
    TEXT.rstrip().replace("narrow", "narrov"),
    TEXT.rstrip()[:-1],
    TEXT.rstrip() + "!"], ids=["different-body", "one-character-changed", "body-minus-last", "body-plus-one"])
def test_a_send_that_is_not_this_messages_body_is_not_a_header_dropped_send(world, text):
    # axis: header-dropped match is exact — only this message's own body, header dropped, counts — a prefix or loose match makes it fail
    msg = _composed(world)
    assert text != _header_dropped(msg)
    _write_record(world, _send_lines("toolu_1", SESSION, text, STAMP))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "headerDropped" not in out and "firstDifference" not in out


def test_a_header_dropped_send_is_provisional_while_a_retry_may_still_arrive(world):
    # axis: header-dropped is provisional during the wait — an exact retry success landing mid-wait is delivered — a header-dropped verdict returned early makes it fail
    msg = _composed(world)
    dropped = _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP)
    _write_record(world, dropped)
    clock = Clock()

    def sleep(seconds):
        clock.sleep(seconds)
        _write_record(world, dropped, _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))

    out = cr.check(world.repo, msg["msgId"], wait=30, interval=2, env=world.env,
                   clock=clock, sleep=sleep)
    assert out["delivered"] is True and out["reason"] is None and clock.t == 2
    assert "headerDropped" not in out


def test_a_header_dropped_send_for_another_pending_message_with_the_same_body_does_not_spoil_delivery(world):
    # axis: delivered outranks header-dropped — another message's header-dropped send of the same body never blocks an exact success — a header-dropped check ahead of the delivered check makes it fail
    _ensure_alive(world)
    a = _compose(world)
    b = _compose(world)
    for msg in (a, b):
        _backdate(world, msg["msgId"], BEFORE)
    _write_record(world,
                  _send_lines("toolu_1", SESSION, _header_dropped(a), STAMP),
                  _send_lines("toolu_2", SESSION, b["forward"], "2026-10-12T10:00:01.000Z"))
    out, _ = _check(world, b["msgId"], wait=0)
    assert out["delivered"] is True and out["reason"] is None and "headerDropped" not in out
    out, _ = _check(world, a["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-text-mismatch"
    assert out["headerDropped"] is True


def test_an_altered_send_with_the_header_still_wins_at_once_over_a_header_dropped_send(world):
    # axis: header-carrying mismatch first — an altered send that carries the header returns at once with its own difference — a header-dropped verdict ahead of it makes it fail
    msg = _composed(world)
    altered = msg["forward"][:-1]
    _write_record(world,
                  _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP),
                  _send_lines("toolu_2", SESSION, altered, "2026-10-12T10:00:01.000Z"))
    out, clock = _check(world, msg["msgId"])
    assert out["reason"] == "relay-text-mismatch" and out["delivered"] is False
    assert out["firstDifference"]["index"] == len(msg["forward"]) - 1
    assert "headerDropped" not in out and "header line dropped" not in out["say"]
    assert clock.t == 0


@pytest.mark.parametrize("case", ["header-dropped", "unattributable"])
def test_the_mismatch_sentences_name_only_the_relays_send_against_the_stored_text(world, case):
    # axis: a mismatch sentence names only the relay's send against the stored text, never which step changed it — a sentence saying the relay changed or sent altered text makes it fail
    # unattributable: the recorded shape of 5f1414592a29, header kept and the body changed, which the
    # advisor's own send did before the relay received it.
    msg = _composed(world)
    mid = msg["msgId"]
    sent = (_header_dropped(msg) if case == "header-dropped"
            else msg["forward"].replace("narrow", "narrov"))
    _write_record(world, _send_lines("toolu_1", SESSION, sent, STAMP))
    out, _ = _check(world, mid, wait=4, interval=2)
    assert out["reason"] == "relay-text-mismatch" and out["delivered"] is False
    if case == "header-dropped":
        assert out["headerDropped"] is True
        assert out["say"] == ("The relay's send of message %s is the stored text with its header "
                              "line dropped; it was not delivered." % mid)
    else:
        assert "headerDropped" not in out
        index = msg["forward"].index("narrow") + 5
        assert out["firstDifference"]["index"] == index
        assert out["say"] == ("The relay's send of message %s differs from the stored text (first "
                              "difference at character %s); this check sees only that send, so it "
                              "cannot tell which step changed the text; it was not delivered."
                              % (mid, index))
    for blame in ("The relay sent", "relay changed", "relay dropped", "from yours"):
        assert blame not in out["say"]


@pytest.mark.parametrize("success, result", [(False, True), (True, False), (True, True)],
                         ids=["failed", "no-result", "success"])
def test_a_header_dropped_send_is_a_mismatch_whatever_its_result_says(world, success, result):
    # axis: header-dropped reads mismatch whatever its own result says — it was sent, altered — a verdict read from the send's own result makes it fail
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP,
                                     success=success, result=result))
    out, clock = _check(world, msg["msgId"], wait=6, interval=2)
    assert out["reason"] == "relay-text-mismatch" and out["headerDropped"] is True
    assert out["delivered"] is False and out["ok"] is False and clock.t >= 6


@pytest.mark.parametrize("success, result", [(False, True), (True, False)], ids=["failed", "no-result"])
def test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result(world, success, result):
    # axis: header-dropped outranks a competing exact send that failed or has no result at the end of the wait — the altered send is the verdict — a failed or unconfirmed verdict ahead of it makes it fail
    msg = _composed(world)
    _write_record(world,
                  _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP),
                  _send_lines("toolu_2", SESSION, msg["forward"], STAMP, success=success, result=result))
    out, clock = _check(world, msg["msgId"], wait=6, interval=2)
    assert out["reason"] == "relay-text-mismatch"
    assert out["headerDropped"] is True
    assert out["delivered"] is False
    assert clock.t >= 6


def test_a_header_dropped_send_stamped_before_sent_after_is_not_this_messages(world):
    # axis: header-dropped sends are read through the same time window — one stamped before sentAfter is not this message's — a window skipped for them makes it fail
    msg = _composed(world, stamp=AFTER)
    _write_record(world, _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "headerDropped" not in out


def test_a_header_dropped_send_to_another_session_is_not_this_messages(world):
    # axis: header-dropped sends are read through the same recipient match — one to another session is not this message's — a recipient check skipped for them makes it fail
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", "someone-else", _header_dropped(msg), STAMP))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "headerDropped" not in out


def test_an_empty_body_is_never_a_header_dropped_send(world):
    # axis: header-dropped needs a non-empty body — an empty or blank send is not this message sent altered — an unguarded empty match makes it fail
    msg = _composed(world)
    state = json.load(open(_state_file(world)))
    state["pending"][msg["msgId"]]["forward"] = cr.FORWARD_HEADER % msg["msgId"]
    json.dump(state, open(_state_file(world), "w"))
    _write_record(world, _send_lines("toolu_1", SESSION, "", STAMP),
                  _send_lines("toolu_2", SESSION, " \n\n ", STAMP))
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "headerDropped" not in out


def test_results_and_calls_need_their_ids(world):
    # E9: a call without an id, or a result without its call's id, confirms nothing.
    msg = _composed(world)
    stamp = "2026-10-12T10:00:00.000Z"
    cases = []
    for call_id in (None, ""):
        lines = _send_lines("toolu_1", SESSION, msg["forward"], stamp)
        lines[0]["message"]["content"][0]["id"] = call_id
        lines[1]["message"]["content"][0]["tool_use_id"] = call_id
        cases.append(lines)
    unbound = _send_lines("toolu_1", SESSION, msg["forward"], stamp)
    del unbound[0]["message"]["content"][0]["id"]
    del unbound[1]["message"]["content"][0]["tool_use_id"]
    cases.append(unbound)
    for lines in cases:
        _write_record(world, lines)
        out, _ = _check(world, msg["msgId"], wait=4, interval=2)
        assert out["delivered"] is False and out["reason"] == "relay-silent"
    # a result for another call's id does not confirm this call
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], stamp, result=False),
                  _send_lines("toolu_2", SESSION, "unrelated", stamp)[1:])
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-send-unconfirmed"


def test_every_check_refusal_says_it_was_not_delivered(world, monkeypatch, tmp_path):
    # E13: delivered false, and a sentence that names the message and ends "; it was not delivered."
    msg = _composed(world)
    mid = msg["msgId"]
    refusals = [_check(world, mid, wait="-1")[0], _check(world, "nope")[0]]
    plain = tmp_path / "plain"
    plain.mkdir()
    refusals.append(cr.check(str(plain), mid, env=world.env))
    path = _state_file(world)
    good = open(path).read()
    state = json.loads(good)
    state["relays"][msg["relay"]]["sessionId"] = None
    json.dump(state, open(path, "w"))
    refusals.append(_check(world, mid)[0])
    open(path, "w").write("{not json")
    refusals.append(_check(world, mid)[0])
    open(path, "w").write(good)
    assert [r["reason"] for r in refusals] == [
        "wait-invalid", "message-unknown", "ledger-repo-identity-unavailable", "relay-unknown",
        "relay-state-unreadable"]
    for r in refusals:
        assert r["ok"] is False and r["delivered"] is False
        assert r["say"].endswith("; it was not delivered.")
    for r in refusals[:1] + refusals[2:]:
        assert mid in r["say"]
    assert "nope" in refusals[1]["say"]


def test_verified_delivery_survives_an_unwritable_decision(world, monkeypatch):
    msg = _composed(world)
    monkeypatch.setattr(cr, "_save", lambda p, s: False)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z"))
    out = _check(world, msg["msgId"])[0]
    assert out["ok"] is True and out["delivered"] is True and out["decisionSaved"] is False


def test_accounts_sharing_a_basename_get_distinct_relay_names(tmp_path):
    one, two = tmp_path / "one" / ".claude", tmp_path / "two" / ".claude"
    assert cr.relay_name(str(one)) != cr.relay_name(str(two))
    assert cr.relay_name(str(one)) == cr.relay_name(str(one) + "/")


# axis: every relay name fits the builder's session-name pattern, and a cut keeps names distinct — see bite-proof record c8a_wo4.md
@pytest.mark.parametrize("base", ["a" * 200, "my account \u00e9\u4e2d x", "x" * 46, "x" * 47])
def test_a_relay_name_fits_the_builders_session_name_pattern(tmp_path, base):
    name = cr.relay_name(str(tmp_path / base))
    assert engine_adapter._CLOUD_SESSION_NAME_RE.fullmatch(name)
    assert len(name) <= 64


def test_two_long_config_dirs_that_differ_only_after_the_cut_get_different_names(tmp_path):
    one, two = tmp_path / ("a" * 100 + "1"), tmp_path / ("a" * 100 + "2")
    assert cr.relay_name(str(one)) != cr.relay_name(str(two))
    assert len(cr.relay_name(str(one))) == len(cr.relay_name(str(two))) == 64


def test_an_all_dots_config_dir_is_refused_as_invalid(world, tmp_path):
    dots = str(tmp_path / "...")
    assert cr.relay_name(dots) is None
    out = cr.ensure(world.repo, dots, env=world.env, run=FakeRun(lists=["[]"]))
    assert out["ok"] is False and out["reason"] == "config-dir-invalid"
    out = cr.compose(world.repo, dots, SESSION, "x", env=world.env)
    assert out["ok"] is False and out["reason"] == "config-dir-invalid"


def test_record_noise_is_skipped(world):
    msg = _composed(world)
    noise = [
        "not json at all",
        json.dumps(["a", "list"]),
        json.dumps({"timestamp": "2026-10-12T10:00:00.000Z", "message": {"content": ["str", 3]}}),
        json.dumps({"timestamp": "2026-10-12T10:00:00.000Z", "message": {"content": [
            {"type": "tool_use", "id": "t0", "name": "SendMessage", "input": {"message": "x"}},
            {"type": "tool_use", "id": "t0b", "name": "SendMessage", "input": {"to": SESSION}},
            {"type": "tool_use", "id": "t0c", "name": "SendMessage", "input": "oops"}]}}),
        json.dumps({"timestamp": "2026-10-12T10:00:00.000Z", "message": {"content": "plain text"}}),
    ]
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z",
                                     result_text="not json"), raw=noise)
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-send-unconfirmed"


def test_check_refusals(world):
    msg = _composed(world)
    assert _check(world, "nope")[0]["reason"] == "message-unknown"
    for bad in ("-1", "abc", "nan", None):
        assert _check(world, msg["msgId"], wait=bad)[0]["reason"] == "wait-invalid"
    for bad in (0, "-2", "x"):
        assert _check(world, msg["msgId"], interval=bad)[0]["reason"] == "wait-invalid"
    path = _state_file(world)
    state = json.load(open(path))
    state["relays"][msg["relay"]]["sessionId"] = None
    json.dump(state, open(path, "w"))
    assert _check(world, msg["msgId"])[0]["reason"] == "relay-unknown"


# ---- ensure ---------------------------------------------------------------------------------

def test_alive_relay_is_found_by_name_and_account_without_a_start(world):
    name = cr.relay_name(world.config)
    assert name.startswith("superheroes-relay-claude-two-")
    run = FakeRun(lists=[json.dumps([_entry("superheroes-relay-claude-three"),
                                        _entry(name, pid=4242, status="busy")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out == {"ok": True, "reason": None, "name": name, "sessionId": RELAY_ID, "started": False}
    assert run.starts() == []
    assert run.calls[0].argv == engine_adapter.claude_agents_list_argv()["argv"]
    assert run.calls[0].env["CLAUDE_CONFIG_DIR"] == world.config


def test_none_alive_starts_the_relay_with_the_exact_argv(world):
    name = cr.relay_name(world.config)
    run = FakeRun(lists=["[]", json.dumps([_entry(name, startedAt=5, pid=4242, status="busy")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["started"] is True and out["sessionId"] == RELAY_ID
    (start,) = run.starts()
    assert start.argv == engine_adapter.claude_relay_argv(name, cr.RELAY_PROMPT)["argv"]
    assert start.env["CLAUDE_CONFIG_DIR"] == world.config
    assert len(cr.RELAY_PROMPT.splitlines()) < 25
    state = json.load(open(_state_file(world)))
    assert state["relays"][name]["sessionId"] == RELAY_ID and state["relays"][name]["startedAt"] == 5


def test_another_accounts_relay_is_not_taken_as_alive(world):
    other = _entry("superheroes-relay-claude-three")
    run = FakeRun(lists=[json.dumps([other]), json.dumps([other, _entry(cr.relay_name(world.config), pid=4242, status="busy")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["started"] is True and len(run.starts()) == 1


@pytest.mark.parametrize("run", [
    FakeRun(lists=["[]"], list_code=1),
    FakeRun(lists=[subprocess.TimeoutExpired("claude", 30)]),
    FakeRun(lists=[FileNotFoundError("claude")]),
    FakeRun(lists=['{"not": "an array"}']),
    FakeRun(lists=["garbage"]),
])
def test_unreadable_listing_refuses_and_never_starts(world, run):
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-listing-failed"
    assert run.starts() == []


def test_relay_starts_in_the_repository_root(world, tmp_path):
    # The account trusts a repository it has been run in and refuses a fresh directory, so the
    # start runs at the real path of the repository root and creates no directory of its own.
    link = tmp_path / "repo-link"
    link.symlink_to(world.repo)
    name = cr.relay_name(world.config)
    run = FakeRun(lists=["[]", json.dumps([_entry(name, pid=4242, status="busy")])])
    out = cr.ensure(str(link), world.config, env=world.env, run=run)
    assert out["ok"] is True and out["started"] is True
    (start,) = run.starts()
    assert start.cwd == os.path.realpath(world.repo) != str(link)
    assert [n for n in os.listdir(os.path.dirname(_state_file(world))) if n.startswith("relay-")] == []


def test_untrusted_workspace_start_failure_carries_the_first_line(world):
    # E1: the start exits non-zero; the first non-empty line of what it printed reaches the advisor.
    said = "Workspace not trusted. Run `claude` in /x once and accept the trust prompt, then retry."
    run = FakeRun(lists=["[]"], start=1, start_err="\n" + said + "\nsecond line\n")
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-start-failed"
    assert out["detail"] == said and out["name"] == cr.relay_name(world.config)
    run = FakeRun(lists=["[]"], start=1, start_out="x" * 300, start_err="")
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["detail"] == "x" * 200
    run = FakeRun(lists=["[]"], start=1, start_out="", start_err="")
    assert cr.ensure(world.repo, world.config, env=world.env, run=run)["detail"] == ""


def test_listed_entry_is_alive_whatever_its_state(world):
    # E5: `done` with a pid is a session waiting for its next message, not a dead one.
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, state="done", pid=50504, status="idle")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out == {"ok": True, "reason": None, "name": name, "sessionId": RELAY_ID, "started": False}
    assert run.starts() == []
    run = FakeRun(lists=[json.dumps([_entry(name, state=None)])])
    assert cr.ensure(world.repo, world.config, env=world.env, run=run)["started"] is False
    assert run.starts() == []


def test_a_refusing_argv_builder_refuses_the_verb(world, monkeypatch):
    # E14: the start refuses when the builder refuses; the listing refuses when its builder does.
    # Neither runs a command past the one listing. The refusal is injected: a config dir's name can no
    # longer be one the builder refuses, because `relay_name` sanitizes it.
    monkeypatch.setattr(engine_adapter, "claude_relay_argv",
                        lambda name, prompt: {"argv": [], "reason": "cloud-session-name-invalid", "detail": "d"})
    run = FakeRun(lists=["[]"])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-start-failed" and out["detail"]
    assert run.starts() == [] and len(run.calls) == 1
    monkeypatch.setattr(engine_adapter, "claude_agents_list_argv",
                        lambda: {"argv": [], "reason": "cloud-session-name-invalid", "detail": "d"})
    run = FakeRun(lists=["[]"])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["reason"] == "relay-listing-failed" and out["detail"] == "d" and run.calls == []


def test_failed_start_and_no_entry_after_start_refuse(world):
    run = FakeRun(lists=["[]"], start=1)
    assert cr.ensure(world.repo, world.config, env=world.env, run=run)["reason"] == "relay-start-failed"
    run = FakeRun(lists=["[]", "[]"])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["reason"] == "relay-start-failed" and len(run.starts()) == 1


def test_two_alive_entries_are_ambiguous(world):
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, sessionId="s-1", pid=4242, status="busy"),
                                     _entry(name, sessionId="s-2", pid=4243, status="busy")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["reason"] == "relay-ambiguous" and out["sessionIds"] == ["s-1", "s-2"]
    assert run.starts() == []


# ---- a relay a usage limit left dead (#2294) -------------------------------------------------

def _dead(name, **extra):
    """A job record a usage limit left behind: blocked, no process field."""
    return _entry(name, state="blocked", sessionId="dead-1", id="d1", **extra)


def _fresh(name, **extra):
    """The relay a start brings up: a new session id, a live process, waiting for a message."""
    return _entry(name, state="done", sessionId=RELAY_ID, id="f1", pid=4242, status="idle", **extra)


def _plain(name):
    return {"ok": True, "reason": None, "name": name, "sessionId": RELAY_ID, "started": False}


def _agents_indexes(run):
    return [i for i, c in enumerate(run.calls) if c.argv[:3] == ["claude", "agents", "--json"]]


@pytest.mark.parametrize("version_out", ["2.1.302 (Claude Code)", "2.1.310 (Claude Code)", "2.1.316 (Claude Code)",
                                         "2.2.0 (Claude Code)", "10.0.1 (Claude Code)"])
def test_a_dead_relay_is_replaced_and_the_dead_entry_stopped(world, version_out):
    # axis: a blocked job record with no process field is dead — it is replaced by a fresh start and then stopped by its id, after the fresh relay is listed — see bite-proof record wo_2294_dead_relay.md (G1)
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_dead(name)]), json.dumps([_dead(name), _fresh(name)])],
                  version_out=version_out)
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    (start,) = run.starts()
    assert start.argv == engine_adapter.claude_relay_argv(name, cr.RELAY_PROMPT)["argv"]
    (stop,) = run.stops()
    assert stop.argv == ["claude", "stop", "d1"] and stop.env["CLAUDE_CONFIG_DIR"] == world.config
    assert run.calls.index(stop) > _agents_indexes(run)[1]
    assert out["ok"] is True and out["started"] is True and out["replaced"] is True
    assert out["sessionId"] == RELAY_ID
    assert out["deadEntries"] == [{"sessionId": "dead-1", "id": "d1", "state": "blocked", "stopped": True}]
    record = json.load(open(_state_file(world)))["relays"][name]
    assert record == {"sessionId": RELAY_ID, "startedAt": 1789474395431, "configDir": world.config}


@pytest.mark.parametrize("extra", [{"pid": 4242, "status": "waiting"}, {"pid": 4242}])
def test_a_blocked_entry_with_a_process_is_alive(world, extra):
    # axis: a pid is never dead — a blocked entry with a pid (with or without a status) is a live relay, left alone — see bite-proof record wo_2294_dead_relay.md (G2)
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, state="blocked", **extra)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out == _plain(name)
    assert run.starts() == [] and run.stops() == [] and run.versions() == []


@pytest.mark.parametrize("state,extra", [
    ("done", {}), ("done", {"pid": 50504, "status": "idle"}), ("working", {"pid": 50504, "status": "busy"}),
])
def test_working_and_done_relays_are_left_alone(world, state, extra):
    # axis: a relay with a process field, or `done`, is alive — nothing is started, stopped or version-read
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, state=state, **extra)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out == _plain(name)
    assert run.starts() == [] and run.stops() == [] and run.versions() == []


@pytest.mark.parametrize("state,extra", [
    ("failed", {}), ("stopped", {}), (None, {}), ("stopped", {"pid": 4242}), (None, {"pid": 4242}),
    ("blocked", {"status": "waiting"}), ("working", {}),
])
def test_an_unknown_or_missing_state_is_kept_and_said(world, state, extra):
    # axis: a state the listing contract does not name, or a `working` entry with no process field, is neither alive nor dead — the entry is kept, nothing is started or stopped, and the record and result say so — see bite-proof record wo_2294_dead_relay.md (G8)
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, state=state, **extra)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["started"] is False and out["sessionId"] == RELAY_ID
    assert out["undetermined"] == {"sessionId": RELAY_ID, "state": state}
    assert "could not tell whether relay %s is alive" % name in out["say"]
    assert run.starts() == [] and run.stops() == []
    record = json.load(open(_state_file(world)))["relays"][name]
    assert record["liveness"] == "undetermined" and record["listedState"] == state


@pytest.mark.parametrize("kwargs", [
    {"version_out": "2.1.301 (Claude Code)"}, {"version_out": "garbage"}, {"version_code": 1},
])
def test_a_claude_whose_listing_contract_is_not_known_never_makes_a_relay_dead(world, kwargs):
    # axis: the contract gate — a version older than the oldest one whose listing was read (2.1.302), unparseable, or unreadable leaves a blocked job record undetermined — see bite-proof record wo_2294_dead_relay.md (G3)
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_dead(name)])], **kwargs)
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["started"] is False and out["sessionId"] == "dead-1"
    assert out["undetermined"] == {"sessionId": "dead-1", "state": "blocked"}
    assert "replaced" not in out and "deadEntries" not in out
    assert run.starts() == [] and run.stops() == [] and len(run.versions()) == 1


def test_a_blocked_entry_without_an_id_is_not_a_job_record_and_never_dead(world):
    # axis: dead needs the job-record shape — a blocked no-process entry with no id is undetermined, without even reading the version
    name = cr.relay_name(world.config)
    entry = _dead(name)
    del entry["id"]
    run = FakeRun(lists=[json.dumps([entry])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["undetermined"] == {"sessionId": "dead-1", "state": "blocked"}
    assert run.starts() == [] and run.stops() == [] and run.versions() == []


def _start_failure_runs(name):
    dead = json.dumps([_dead(name)])
    return {
        "start-exits-1": FakeRun(lists=[dead], start=1, start_err="boom"),
        "second-listing-only-dead": FakeRun(lists=[dead, dead]),
        "second-listing-empty": FakeRun(lists=[dead, "[]"]),
        "second-listing-unreadable": FakeRun(lists=[dead, "garbage"]),
    }


@pytest.mark.parametrize("case", ["start-exits-1", "second-listing-only-dead", "second-listing-empty",
                                  "second-listing-unreadable"])
def test_a_fresh_start_that_fails_refuses_names_the_dead_and_stops_nothing(world, case):
    # axis: no stop on a start-failure path — the dead entry is the only relay there is, so it is named, never stopped — see bite-proof record wo_2294_dead_relay.md (G6)
    name = cr.relay_name(world.config)
    run = _start_failure_runs(name)[case]
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-start-failed" and out["name"] == name
    assert out["deadEntries"] == [{"sessionId": "dead-1", "id": "d1", "state": "blocked"}]
    assert run.stops() == []
    if case == "start-exits-1":
        assert out["detail"] == "boom"


def test_a_relay_listed_under_the_dead_sessions_id_is_not_a_fresh_one(world):
    # axis: freshness — the replacement must carry a session id the first listing's dead entries did not — see bite-proof record wo_2294_dead_relay.md (G4)
    name = cr.relay_name(world.config)
    back = _entry(name, state="done", sessionId="dead-1", id="d1", pid=4242, status="idle")
    run = FakeRun(lists=[json.dumps([_dead(name)]), json.dumps([back])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-start-failed"
    assert out["deadEntries"] == [{"sessionId": "dead-1", "id": "d1", "state": "blocked"}]
    assert len(run.starts()) == 1 and run.stops() == []


def test_an_old_entry_turned_live_next_to_a_fresh_one_is_ambiguous_and_nothing_is_stopped(world):
    # axis: two non-dead entries after the start are ambiguous, and an ambiguous refusal stops nothing
    name = cr.relay_name(world.config)
    back = _entry(name, state="done", sessionId="dead-1", id="d1", pid=4242, status="idle")
    run = FakeRun(lists=[json.dumps([_dead(name)]), json.dumps([back, _fresh(name)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-ambiguous"
    assert out["sessionIds"] == ["dead-1", RELAY_ID]
    assert run.stops() == []


def test_a_live_relay_beside_a_dead_entry_stops_the_dead_one_and_starts_nothing(world):
    # axis: a dead remnant beside a live relay is stopped, nothing is started, nothing is reported replaced — see bite-proof record wo_2294_dead_relay.md (G9)
    name = cr.relay_name(world.config)
    live = _entry(name, sessionId=RELAY_ID, pid=4242, status="busy")
    run = FakeRun(lists=[json.dumps([live, _dead(name)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["started"] is False and "replaced" not in out
    assert out["sessionId"] == RELAY_ID
    assert run.starts() == []
    (stop,) = run.stops()
    assert stop.argv == ["claude", "stop", "d1"] and stop.env["CLAUDE_CONFIG_DIR"] == world.config
    assert out["deadEntries"] == [{"sessionId": "dead-1", "id": "d1", "state": "blocked", "stopped": True}]
    record = json.load(open(_state_file(world)))["relays"][name]
    assert record == {"sessionId": RELAY_ID, "startedAt": 1789474395431, "configDir": world.config}


def test_a_failed_stop_does_not_fail_ensure(world):
    # axis: a stop that exits non-zero is reported on the dead entry (stopped false, the first line of what it printed) and ensure stays ok
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_dead(name)]), json.dumps([_dead(name), _fresh(name)])],
                  stop=1, stop_err="no such session")
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["replaced"] is True and out["sessionId"] == RELAY_ID
    assert out["deadEntries"][0]["stopped"] is False
    assert out["deadEntries"][0]["detail"] == "no such session"


def test_only_the_dead_entries_of_the_first_listing_are_stopped(world):
    # axis: stop targets come from the latest listing but only those already dead in the first — a job record that turned up blocked after the start is not stopped — see bite-proof record wo_2294_dead_relay.md (G5)
    name = cr.relay_name(world.config)
    late = _entry(name, state="blocked", sessionId="dead-2", id="d2")
    run = FakeRun(lists=[json.dumps([_dead(name)]), json.dumps([_dead(name), _fresh(name), late])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert [c.argv for c in run.stops()] == [["claude", "stop", "d1"]]
    assert out["ok"] is True and out["replaced"] is True
    assert [d["sessionId"] for d in out["deadEntries"]] == ["dead-1"]


def test_a_dead_entry_no_longer_listed_is_replaced_without_a_stop(world):
    # axis: an empty target set omits deadEntries while replaced still applies
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_dead(name)]), json.dumps([_fresh(name)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["replaced"] is True and out["started"] is True
    assert run.stops() == [] and "deadEntries" not in out


def test_a_stop_the_builder_refuses_is_reported_and_does_not_fail_ensure(world):
    # axis: a dead entry whose id the stop builder refuses is reported unstopped with the refusal's reason, and nothing is run for it
    name = cr.relay_name(world.config)
    bad = dict(_dead(name), id="-rf")
    run = FakeRun(lists=[json.dumps([bad]), json.dumps([bad, _fresh(name)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and run.stops() == []
    assert out["deadEntries"] == [{"sessionId": "dead-1", "id": "-rf", "state": "blocked",
                                   "stopped": False, "detail": engine_adapter.REFUSAL_RELAY_STOP_ID_INVALID}]


def _silent_message(world, **relay_extra):
    msg = _composed(world)
    path = _state_file(world)
    state = json.load(open(path))
    state["relays"][msg["relay"]].update(relay_extra)
    json.dump(state, open(path, "w"))
    _write_record(world, [])
    return msg


def test_check_says_when_the_silent_relays_liveness_was_undetermined(world):
    # axis: a silent relay whose record says ensure could not tell it was alive gets the one appended sentence; a relay recorded without it keeps today's sentence — see bite-proof record wo_2294_dead_relay.md (G7)
    msg = _silent_message(world, liveness="undetermined", listedState="failed")
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    today = "The relay did not send message %s within 4 seconds; it was not delivered." % msg["msgId"]
    assert out["reason"] == "relay-silent"
    assert out["say"] == today + (" ensure could not tell whether the relay was alive "
                                  "(listed state failed), which may be why.")
    plain = _silent_message(world)
    out, _ = _check(world, plain["msgId"], wait=4, interval=2)
    assert out["say"] == "The relay did not send message %s within 4 seconds; it was not delivered." % plain["msgId"]


# ---- compose --------------------------------------------------------------------------------

def test_compose_formats_and_records_the_pending_message(world):
    out = _compose(world, text="hello  \n\n", session=SESSION)
    forward = "Message from the superheroes advisor (id %s):\n\nhello" % out["msgId"]
    assert out["forward"] == forward and len(out["msgId"]) == 12
    assert out["relay"] == cr.relay_name(world.config)
    assert out["relayMessage"] == "RELAY to %s (id %s):\n%s" % (SESSION, out["msgId"], forward)
    pending = json.load(open(_state_file(world)))["pending"][out["msgId"]]
    assert pending["session"] == SESSION and pending["forward"] == forward
    assert pending["configDir"] == world.config and pending["relay"] == out["relay"]
    assert len(pending["sentAfter"]) == 24 and pending["sentAfter"].endswith("Z")


def test_compose_refusals(world):
    for session in ("", "a\nb", None):
        out = cr.compose(world.repo, world.config, session, "x", env=world.env)
        assert out["reason"] == "session-name-invalid"
    for text in ("", " \n\t"):
        assert cr.compose(world.repo, world.config, SESSION, text, env=world.env)["reason"] == "text-empty"


def test_compose_refuses_a_session_id_and_names_where_to_read_the_name(world):
    # axis: refusal — a `session_` id refuses `session-id-not-name` with the name shape and where to read it, writing no state — see bite-proof record wo_2166_session_id.md (G1)
    out = cr.compose(world.repo, world.config, "session_01AbCdEf", "x", env=world.env)
    assert out["ok"] is False and out["reason"] == "session-id-not-name"
    assert out["session"] == "session_01AbCdEf"
    assert "issue-<n>-<hash>" in out["message"] and "cloudSessionName" in out["message"]
    assert not os.path.exists(_state_file(world))


@pytest.mark.parametrize("session", ["issue-2166-3fa9c1d2", SESSION, "Session_x", "my-session_1", "session"])
def test_compose_still_accepts_a_name_and_every_other_value(world, session):
    # axis: boundary — only the exact case-sensitive leading `session_` is refused; another case, an embedded `session_` or a bare `session` composes — see bite-proof record wo_2166_session_id.md (G2, G3)
    out = _compose(world, session=session)
    assert out["relayMessage"].startswith("RELAY to %s (id " % session)


@pytest.mark.parametrize("junk", ["{not json", "[]", '{"relays": {}}', '{"relays": [], "pending": {}}'])
def test_unreadable_state_refuses_every_verb_and_is_never_overwritten(world, junk):
    path = _state_file(world)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(junk)
    run = FakeRun(lists=["[]"])
    results = [cr.ensure(world.repo, world.config, env=world.env, run=run),
               cr.compose(world.repo, world.config, SESSION, "x", env=world.env),
               cr.check(world.repo, "abc", env=world.env)]
    assert [r["reason"] for r in results] == ["relay-state-unreadable"] * 3
    assert run.calls == []
    assert open(path).read() == junk


def test_cli_prints_one_json_object_and_exits_1_on_refusal(world, capsys, monkeypatch):
    for key, value in world.env.items():
        monkeypatch.setenv(key, value)
    tf = os.path.join(world.config, "t.txt")
    open(tf, "w").write("hi\n")
    code = cr.main(["compose", "--repo-root", world.repo, "--config-dir", world.config,
                    "--session", SESSION, "--text-file", tf])
    assert code == 0 and json.loads(capsys.readouterr().out)["ok"] is True
    code = cr.main(["check", "--repo-root", world.repo, "--msg-id", "nope"])
    assert code == 1 and json.loads(capsys.readouterr().out)["reason"] == "message-unknown"


# ---- fix orders (#2148) ---------------------------------------------------------------------

def _decide(world, msg_id, decision):
    path = _state_file(world)
    state = json.load(open(path))
    state["pending"][msg_id]["decision"] = decision
    json.dump(state, open(path, "w"))


def test_compose_records_fix_order_true_only_when_asked(world):
    plain = _compose(world)
    flagged = cr.compose(world.repo, world.config, SESSION, "fix it", env=world.env, fix_order=True)
    pending = json.load(open(_state_file(world)))["pending"]
    assert "fixOrder" not in pending[plain["msgId"]]
    assert pending[flagged["msgId"]]["fixOrder"] is True


def test_fix_orders_lists_only_flagged_records_whose_text_may_have_reached_the_builder(world):
    def flagged(decision, **kwargs):
        out = cr.compose(world.repo, world.config, SESSION, "fix it", env=world.env,
                         fix_order=kwargs.get("fix_order", True))
        _decide(world, out["msgId"], decision)
        return out["msgId"]

    stamp = "2099-10-24T01:02:03.456Z"  # the check's stamp: long after every compose below
    listed = {
        flagged({"delivered": True, "reason": None, "at": stamp}),
        flagged({"delivered": False, "reason": "relay-silent", "at": stamp}),
        flagged({"delivered": False, "reason": "relay-text-mismatch", "at": stamp}),
        flagged({"delivered": False, "reason": "relay-send-unconfirmed", "at": stamp}),
    }
    flagged({"delivered": False, "reason": "relay-send-failed", "at": stamp})
    flagged({"delivered": False, "reason": "wait-invalid", "at": stamp})
    flagged({"delivered": True, "reason": None, "at": stamp}, fix_order=False)
    flagged("delivered")
    draft = cr.compose(world.repo, world.config, SESSION, "fix it", env=world.env, fix_order=True)
    before = open(_state_file(world)).read()
    out = cr.fix_orders(world.repo, env=world.env)
    assert out["ok"] is True and draft["msgId"] not in {r["msgId"] for r in out["records"]}
    assert {r["msgId"] for r in out["records"]} == listed
    # axis: the exported `at` is the message's own sentAfter, which a decision stamped later does not move — see bite-proof record wo_2148_fix_order.md
    sent = {m: e["sentAfter"] for m, e in json.load(open(_state_file(world)))["pending"].items()}
    assert all(r == {"msgId": r["msgId"], "session": SESSION, "configDir": world.config,
                     "at": sent[r["msgId"]]} for r in out["records"])
    assert all(r["at"] != stamp for r in out["records"])
    assert open(_state_file(world)).read() == before


def test_fix_orders_reads_a_missing_state_as_empty_and_an_unreadable_one_as_a_refusal(world):
    path = _state_file(world)
    assert cr.fix_orders(world.repo, env=world.env) == {"ok": True, "records": []}
    assert not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("{not json")
    assert cr.fix_orders(world.repo, env=world.env) == {"ok": False, "reason": "relay-state-unreadable"}
    assert open(path).read() == "{not json"


def test_cli_compose_fix_order_flag_passes_through(world, monkeypatch):
    for key, value in world.env.items():
        monkeypatch.setenv(key, value)
    tf = os.path.join(world.config, "t.txt")
    open(tf, "w").write("hi\n")
    base = ["compose", "--repo-root", world.repo, "--config-dir", world.config,
            "--session", SESSION, "--text-file", tf]
    assert cr.main(base + ["--fix-order"]) == 0
    assert cr.main(base) == 0
    pending = json.load(open(_state_file(world)))["pending"].values()
    assert sorted("fixOrder" in entry for entry in pending) == [False, True]


@pytest.mark.parametrize("entry", [
    None, "x", ["y"], {"fixOrder": "yes"}, {"fixOrder": 1}, {"fixOrder": None},
])
def test_fix_orders_refuses_a_malformed_pending_entry_only_when_unchecked_are_included(world, entry):
    # axis: with include_unchecked, an entry that cannot be read as a fix order or not refuses the read; the default read is unchanged — see bite-proof record i2254_original_session
    assert cr.compose(world.repo, world.config, SESSION, "fix it", env=world.env, fix_order=True)["ok"]
    path = _state_file(world)
    state = json.load(open(path))
    state["pending"]["m"] = entry
    json.dump(state, open(path, "w"))
    assert cr.fix_orders(world.repo, env=world.env, include_unchecked=True) == {
        "ok": False, "reason": "relay-state-malformed"}
    default = cr.fix_orders(world.repo, env=world.env)
    assert default["ok"] is True and default["records"] == []


def test_fix_orders_does_not_list_an_entry_without_a_fix_order_when_unchecked_are_included(world):
    # axis: with include_unchecked, an entry composed without fix_order is not listed as a fix order — see bite-proof record i2254_original_session
    out = cr.compose(world.repo, world.config, SESSION, "just a note", env=world.env)
    assert out["ok"]
    listed = cr.fix_orders(world.repo, env=world.env, include_unchecked=True)
    assert listed == {"ok": True, "records": []}
