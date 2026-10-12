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
import launch_ledger  # noqa: E402

SESSION = "builder-1748"
RELAY_ID = "5534cbe0-5d2a-4783-8980-09c4bafd22ad"
BEFORE = "2000-01-01T00:00:00.000Z"
AFTER = "2999-01-01T00:00:00.000Z"
TEXT = "Use the narrow fix.\nSecond line ✓ \"quoted\" & <angle>\n"


class FakeRun:
    """Scripted answers: `lists` is consumed one per `agents --json`; `start` is the exit code of
    `claude --bg`. Every call's argv, env and cwd are recorded."""

    def __init__(self, lists=(), start=0, list_code=0):
        self.calls = []
        self.lists = list(lists)
        self.start = start
        self.list_code = list_code

    def __call__(self, argv, **kwargs):
        self.calls.append(SimpleNamespace(argv=list(argv), env=kwargs.get("env"),
                                          cwd=kwargs.get("cwd")))
        if argv[:3] == ["claude", "agents", "--json"]:
            out = self.lists.pop(0) if len(self.lists) > 1 else (self.lists[0] if self.lists else "[]")
            if isinstance(out, BaseException):
                raise out
            return SimpleNamespace(returncode=self.list_code, stdout=out)
        return SimpleNamespace(returncode=self.start, stdout="backgrounded")

    def starts(self):
        return [c for c in self.calls if c.argv[:2] == ["claude", "--bg"]]


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
    run = FakeRun(lists=[json.dumps([_entry(cr.relay_name(world.config))])])
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


def test_missing_record_is_reported_after_the_wait(world):
    msg = _composed(world)
    out, _ = _check(world, msg["msgId"], wait=4, interval=2)
    assert out["reason"] == "relay-record-missing" and out["delivered"] is False


def test_exact_text_refused_by_the_session_is_send_failed(world):
    msg = _composed(world)
    _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z",
                                     success=False))
    out, clock = _check(world, msg["msgId"])
    assert out["ok"] is False and out["reason"] == "relay-send-failed"
    assert "No agent named" in out["say"] and clock.t == 0


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
    assert name == "superheroes-relay-claude-two"
    run = FakeRun(lists=[json.dumps([_entry("superheroes-relay-claude-three"), _entry(name)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out == {"ok": True, "reason": None, "name": name, "sessionId": RELAY_ID, "started": False}
    assert run.starts() == []
    assert run.calls[0].argv == ["claude", "agents", "--json"]
    assert run.calls[0].env["CLAUDE_CONFIG_DIR"] == world.config


def test_none_alive_starts_the_relay_with_the_exact_argv(world):
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, state="done")]),
                         json.dumps([_entry(name, state="done"), _entry(name, startedAt=5)])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is True and out["started"] is True and out["sessionId"] == RELAY_ID
    (start,) = run.starts()
    assert start.argv == ["claude", "--bg", "-n", name, "--model", "haiku", "--effort", "low",
                          cr.RELAY_PROMPT]
    assert start.env["CLAUDE_CONFIG_DIR"] == world.config
    assert start.cwd == os.path.join(os.path.dirname(_state_file(world)), "relay-" + name)
    assert os.path.isdir(start.cwd)
    assert len(cr.RELAY_PROMPT.splitlines()) < 25
    state = json.load(open(_state_file(world)))
    assert state["relays"][name]["sessionId"] == RELAY_ID and state["relays"][name]["startedAt"] == 5


def test_another_accounts_relay_is_not_taken_as_alive(world):
    other = _entry("superheroes-relay-claude-three")
    run = FakeRun(lists=[json.dumps([other]), json.dumps([other, _entry(cr.relay_name(world.config))])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["started"] is True and len(run.starts()) == 1


@pytest.mark.parametrize("run", [
    FakeRun(lists=["[]"], list_code=1),
    FakeRun(lists=[subprocess.TimeoutExpired("claude", 30)]),
    FakeRun(lists=[FileNotFoundError("claude")]),
    FakeRun(lists=['{"not": "an array"}']),
    FakeRun(lists=["garbage"]),
    FakeRun(lists=[json.dumps([_entry("superheroes-relay-claude-two", state=None)])]),
])
def test_unreadable_listing_refuses_and_never_starts(world, run):
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["ok"] is False and out["reason"] == "relay-listing-failed"
    assert run.starts() == []


def test_failed_start_and_no_entry_after_start_refuse(world):
    run = FakeRun(lists=["[]"], start=1)
    assert cr.ensure(world.repo, world.config, env=world.env, run=run)["reason"] == "relay-start-failed"
    run = FakeRun(lists=["[]", "[]"])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["reason"] == "relay-start-failed" and len(run.starts()) == 1


def test_two_alive_entries_are_ambiguous(world):
    name = cr.relay_name(world.config)
    run = FakeRun(lists=[json.dumps([_entry(name, sessionId="s-1"), _entry(name, sessionId="s-2")])])
    out = cr.ensure(world.repo, world.config, env=world.env, run=run)
    assert out["reason"] == "relay-ambiguous" and out["sessionIds"] == ["s-1", "s-2"]
    assert run.starts() == []


# ---- compose --------------------------------------------------------------------------------

def test_compose_formats_and_records_the_pending_message(world):
    out = _compose(world, text="hello  \n\n", session=SESSION)
    forward = "Message from the superheroes advisor (id %s):\n\nhello" % out["msgId"]
    assert out["forward"] == forward and len(out["msgId"]) == 12
    assert out["relay"] == "superheroes-relay-claude-two"
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
