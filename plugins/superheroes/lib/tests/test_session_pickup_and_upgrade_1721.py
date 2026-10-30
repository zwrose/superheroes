#!/usr/bin/env python3
"""#1721 — a review in flight at upgrade restarts once, in a fresh session; a review picked back up
in the same session is untouched.

The earlier-version folders below are built by driving a real review with this driver and then
rewriting ``loop-state.json`` without ``sessionGeneration`` — which is exactly what an earlier
version's saved state looks like to the gate.
"""
import argparse
import gc
import hashlib
import json
import os
import shutil
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import round_records  # noqa: E402

from session_checkout import enter_checkout  # noqa: E402
from test_round_driver import (  # noqa: E402
    _cfg, _drive_cli, _guard_argv, _responder, _seed_repo_root_if_missing,
)
from test_round_driver_no_records_seed_1721 import _recording  # noqa: E402

TOKEN = RD.SESSION_FROM_EARLIER_VERSION
MARKER = RD.UPGRADE_RESTART_MARKER_FILE
_FINDINGS = [
    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
     "consequence": "a reviewer-found defect stays in the change"},
    {"title": "nit", "severity": "Minor", "file": "f.py", "line": 2,
     "consequence": "a reviewer-found defect stays in the change"},
]
_CERT_FILES = {
    "certification-receipt.json": b'{"fixture": "earlier-version receipt", "bytes": 4711}\n',
    "certification-refusal.json": b'{"fixture": "earlier-version refusal", "bytes": 4712}\n',
    "head-content-blobs.json": b'{"fixture": "earlier-version head blobs", "bytes": 4713}\n',
}
_SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5.5", "engine": "claude"}
                       for dim in RD.DIMENSIONS}}
_ABSENT = object()


# --- set-up --------------------------------------------------------------------------------

def _state_path(session_dir):
    return os.path.join(session_dir, RD.STATE_FILE)


def _read_state_file(session_dir):
    with open(_state_path(session_dir), encoding="utf-8") as fh:
        return json.load(fh)


def _write_state_file(session_dir, state):
    with open(_state_path(session_dir), "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _strip_generation(session_dir):
    """Rewrite the saved state the way an earlier version left it: no `sessionGeneration`."""
    state = _read_state_file(session_dir)
    assert state["sessionGeneration"] == RD.SESSION_GENERATION
    del state["sessionGeneration"]
    _write_state_file(session_dir, state)


def _add_certification_files(session_dir):
    for name, data in _CERT_FILES.items():
        with open(os.path.join(session_dir, name), "wb") as fh:
            fh.write(data)


def _drive_to_round(session_dir, round_no, respond):
    """Drive a real review, one driver call at a time, until round `round_no`'s first step is
    pending. Returns that `next`."""
    checkout = os.path.join(session_dir, "checkout")
    enter_checkout(checkout)
    _seed_repo_root_if_missing(session_dir, checkout)
    n = RD.cmd_next(session_dir, _cfg())
    for _ in range(80):
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL, "reached a terminal before round %d" % round_no
        if n["round"] >= round_no:
            return n
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
        n = RD.cmd_next(session_dir)
    raise AssertionError("round %d never began" % round_no)


def _earlier_version_folder(base):
    """A real review driven past round 1, rewritten as an earlier version left it, with the three
    certification files beside it. Returns the session directory."""
    session_dir = str(base / "session")
    os.makedirs(session_dir)
    n = _drive_to_round(session_dir, 2, _responder(round1_findings=list(_FINDINGS)))
    assert n["round"] == 2 and n["phase"] and n["expectedStateHash"]
    _strip_generation(session_dir)
    _add_certification_files(session_dir)
    return session_dir


def _light_folder(base, generation=_ABSENT, terminal=None):
    """A minimal unfinished (or finished) saved state, for the edges that need no driven review."""
    session_dir = str(base / "light")
    os.makedirs(session_dir)
    state = RD.new_state(_cfg())
    state["terminal"] = terminal
    if generation is _ABSENT:
        del state["sessionGeneration"]
    else:
        state["sessionGeneration"] = generation
    _write_state_file(session_dir, state)
    return session_dir


def _bootstrap_args(session_dir, guard_dir, scratch):
    """The flags a real start passes (SKILL.md Bootstrap): the guard flags carry `--repo-root` and
    `--diff-path`; `guard_dir` is where the base-guard repo lives."""
    os.makedirs(scratch, exist_ok=True)
    prior = os.path.join(scratch, "prior-comments.json")
    seat_map = os.path.join(scratch, "seat-map.json")
    with open(prior, "w", encoding="utf-8") as fh:
        json.dump([], fh)
    with open(seat_map, "w", encoding="utf-8") as fh:
        json.dump(_SEAT_MAP, fh)
    return (["next", "--session-dir", session_dir] + _guard_argv(guard_dir, fresh=True)
            + ["--verify-command", "none", "--vendors", "claude,codex",
               "--prior-comments", prior, "--max-rounds", "4", "--seat-map", seat_map])


def _main(capsys, argv):
    capsys.readouterr()
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    return rc, json.loads(out.splitlines()[-1])


def _snapshot(session_dir, exclude=()):
    """Every path under the folder with its size, content hash and modification time."""
    snap = {}
    for root, dirs, files in os.walk(session_dir):
        for name in dirs + files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, session_dir)
            if rel in exclude:
                continue
            if os.path.islink(path):
                snap[rel] = ("link", os.readlink(path))
            elif os.path.isdir(path):
                snap[rel] = ("dir",)
            else:
                with open(path, "rb") as fh:
                    data = fh.read()
                snap[rel] = ("file", len(data), hashlib.sha256(data).hexdigest(),
                             os.stat(path).st_mtime_ns)
    return snap


def _marker_path(session_dir):
    return os.path.join(session_dir, MARKER)


def _assert_refusal(out, already_restarted):
    assert out["ok"] is False, out
    assert out["reason"] == TOKEN, out
    assert out["restart"] == "fresh-session", out
    assert out["alreadyRestarted"] is already_restarted, out
    assert isinstance(out["detail"], str) and out["detail"], out
    assert "markerWritten" not in out, out


def _journal_rows(session_dir):
    path = os.path.join(session_dir, RD.JOURNAL_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _stop_next_commit_at(monkeypatch, kind, stop_at):
    real = RD.round_commit.begin

    def wrapper(session_dir, commit_kind, **kw):
        if commit_kind == kind:
            kw["stop_at"] = stop_at
        return real(session_dir, commit_kind, **kw)

    monkeypatch.setattr(RD.round_commit, "begin", wrapper)


def _half_done_commit(tmp_path, monkeypatch):
    """A real `submit` interrupted after its commit was sealed: the commit is left in staging."""
    session_dir = str(tmp_path / "half")
    os.makedirs(session_dir)
    respond = _responder(round1_findings=list(_FINDINGS))
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"] and n["phase"] == RD.P_PANEL, n
    _stop_next_commit_at(monkeypatch, "submit-accept", "sealed")
    with pytest.raises(RD.round_commit.StopPoint):
        RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                      respond(n["phase"], n["payload"], n["round"]))
    monkeypatch.undo()
    staged = os.path.join(session_dir, "commits")
    assert os.path.isdir(staged) and os.listdir(staged), "no half-done commit was left"
    return session_dir, n


# --- the parser's own subcommands ----------------------------------------------------------

def _subcommand_parsers():
    for action in RD.build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    raise AssertionError("the parser registers no subcommands")


_SUBCOMMANDS = sorted(_subcommand_parsers())


def _required_argv(name, session_dir, scratch):
    """The subcommand's own required arguments, read off the parser."""
    os.makedirs(scratch, exist_ok=True)
    real_file = os.path.join(scratch, "argument.json")
    with open(real_file, "w", encoding="utf-8") as fh:
        json.dump({}, fh)
    argv = [name]
    for action in _subcommand_parsers()[name]._actions:
        if not action.required:
            continue
        flag = action.option_strings[0] if action.option_strings else None
        if flag == "--session-dir":
            value = session_dir
        elif action.choices:
            value = str(list(action.choices)[0])
        elif action.type is int:
            value = "1"
        elif flag in ("--artifact", "--ruling-file"):
            value = real_file
        else:
            value = "x"
        argv += ([flag] if flag else []) + [value]
    return argv


# --- the earlier-version refusal -----------------------------------------------------------

# U1 — axis: `next` with the bootstrap flags on an unfinished earlier-version folder answers the
# named refusal, exits non-zero, and leaves the once-only marker.
def test_u1_next_on_an_earlier_version_folder_refuses_and_writes_the_marker(tmp_path, capsys):
    session_dir = _earlier_version_folder(tmp_path)
    argv = _bootstrap_args(session_dir, str(tmp_path / "guard"), str(tmp_path / "scratch"))
    rc, out = _main(capsys, argv)
    assert rc != 0
    _assert_refusal(out, already_restarted=False)
    assert os.path.isfile(_marker_path(session_dir))
    with open(_marker_path(session_dir), encoding="utf-8") as fh:
        marker = json.load(fh)
    assert marker["schema"] == RD.UPGRADE_RESTART_MARKER_SCHEMA
    assert marker["cmd"] == "next"
    assert isinstance(marker["at"], str) and marker["at"].endswith("Z")


# U2 — axis: the marker is written once; a second `next` says the restart already happened and
# never rewrites or touches the marker.
def test_u2_second_next_says_already_restarted_and_leaves_the_marker_alone(tmp_path, capsys):
    session_dir = _earlier_version_folder(tmp_path)
    argv = _bootstrap_args(session_dir, str(tmp_path / "guard"), str(tmp_path / "scratch"))
    _main(capsys, argv)
    marker = _marker_path(session_dir)
    with open(marker, "rb") as fh:
        before_bytes = fh.read()
    before_stat = os.stat(marker)
    rc, out = _main(capsys, argv)
    assert rc != 0
    _assert_refusal(out, already_restarted=True)
    with open(marker, "rb") as fh:
        assert fh.read() == before_bytes
    after_stat = os.stat(marker)
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
    assert after_stat.st_ino == before_stat.st_ino
    assert [n for n in os.listdir(session_dir) if "restarted" in n] == [MARKER]


# U3 — axis: nothing in the old folder changes except the marker; the certification files are
# byte for byte what the earlier version left.
def test_u3_the_old_folder_is_otherwise_untouched(tmp_path, capsys):
    session_dir = _earlier_version_folder(tmp_path)
    argv = _bootstrap_args(session_dir, str(tmp_path / "guard"), str(tmp_path / "scratch"))
    before = _snapshot(session_dir)
    assert set(_CERT_FILES) <= set(before)
    _main(capsys, argv)
    _main(capsys, argv)
    assert _snapshot(session_dir, exclude=(MARKER,)) == before
    for name, data in _CERT_FILES.items():
        with open(os.path.join(session_dir, name), "rb") as fh:
            assert fh.read() == data, name


# U4 — axis: no certification file is opened, and `loop-state.json` is the only file of the
# folder opened for reading, across both calls.
def test_u4_only_the_saved_state_is_opened_for_reading(tmp_path, capsys):
    session_dir = _earlier_version_folder(tmp_path)
    argv = _bootstrap_args(session_dir, str(tmp_path / "guard"), str(tmp_path / "scratch"))
    with _recording() as reads:
        _main(capsys, argv)
        _main(capsys, argv)
    certification = {os.path.realpath(os.path.join(session_dir, name)) for name in _CERT_FILES}
    assert not (set(reads) & certification)
    folder = os.path.realpath(session_dir)
    in_folder = {r for r in reads if r == folder or r.startswith(folder + os.sep)}
    assert in_folder == {os.path.realpath(_state_path(session_dir))}


# U5 — axis: every subcommand the parser registers answers the refusal on an earlier-version
# folder and leaves the folder as it was.
@pytest.mark.parametrize("name", _SUBCOMMANDS)
def test_u5_every_command_refuses_an_earlier_version_folder(name, tmp_path, capsys):
    assert _SUBCOMMANDS
    session_dir = _earlier_version_folder(tmp_path)
    argv = _required_argv(name, session_dir, str(tmp_path / "scratch"))
    RD.build_parser().parse_args(argv)
    before = _snapshot(session_dir)
    rc, out = _main(capsys, argv)
    assert out["reason"] == TOKEN, out
    assert rc != 0
    assert _snapshot(session_dir, exclude=(MARKER,)) == before


# U6 — axis: the gate comes before commit recovery; a half-done commit in staging is left exactly
# as it was.
def test_u6_a_half_done_commit_in_staging_is_not_recovered(tmp_path, capsys, monkeypatch):
    session_dir, _n = _half_done_commit(tmp_path, monkeypatch)
    _strip_generation(session_dir)
    before = _snapshot(session_dir)
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    _assert_refusal(out, already_restarted=False)
    assert _snapshot(session_dir, exclude=(MARKER,)) == before
    assert os.listdir(os.path.join(session_dir, "commits"))


# U6b — axis: called directly, `cmd_next` gates before commit recovery; staging stays byte-identical.
def test_u6b_cmd_next_called_directly_gates_before_commit_recovery(tmp_path, monkeypatch):
    session_dir, _n = _half_done_commit(tmp_path, monkeypatch)
    _strip_generation(session_dir)
    staged = os.path.join(session_dir, "commits")
    before = _snapshot(staged)
    assert before
    out = RD.cmd_next(session_dir)
    _assert_refusal(out, already_restarted=False)
    assert _snapshot(staged) == before


# U7 — axis: a finished earlier-generation session is left alone — `next` re-emits its terminal
# answer and no marker is made.
def test_u7_a_finished_earlier_version_session_still_replays_its_terminal(tmp_path):
    session_dir = str(tmp_path / "finished")
    os.makedirs(session_dir)
    cfg = _cfg()
    payload = _drive_cli(session_dir, cfg, _responder(round1_findings=None, vendors=cfg["vendors"]))
    assert payload["verdict"] == "converged"
    replay_before = RD.cmd_next(session_dir)
    assert replay_before["ok"] and replay_before["action"] == RD.P_TERMINAL, replay_before
    _strip_generation(session_dir)
    before = _snapshot(session_dir)
    replay_after = RD.cmd_next(session_dir)
    # the state hash covers the whole saved state, so it moves with the rewrite; nothing else does
    assert {k: v for k, v in replay_after.items() if k != "expectedStateHash"} == {
        k: v for k, v in replay_before.items() if k != "expectedStateHash"}
    assert not os.path.exists(_marker_path(session_dir))
    # a replay may save the state it loaded, but it never gives a loaded state the key
    assert "sessionGeneration" not in _read_state_file(session_dir)
    assert _read_state_file(session_dir)["terminal"]
    assert _snapshot(session_dir).keys() - before.keys() == set()


# U8 — axis: the token leads to a new session, not a stop: the same bootstrap in a fresh folder
# starts round 1 at the current generation, and the old folder keeps answering the refusal.
def test_u8_the_refusal_leads_to_a_fresh_session_that_starts_round_one(tmp_path, capsys):
    old = _earlier_version_folder(tmp_path)
    scratch = str(tmp_path / "scratch")
    rc, out = _main(capsys, _bootstrap_args(old, str(tmp_path / "guard"), scratch))
    assert rc != 0
    _assert_refusal(out, already_restarted=False)

    fresh = str(tmp_path / "fresh")
    os.makedirs(fresh)
    rc, started = _main(capsys, _bootstrap_args(fresh, fresh, scratch))
    assert rc == 0 and started["ok"] is True, started
    assert started["round"] == 1 and started["phase"] == RD.P_PANEL, started
    assert started["expectedStateHash"]
    state = _read_state_file(fresh)
    assert state["sessionGeneration"] == RD.SESSION_GENERATION
    assert state["pending"]["phase"] == RD.P_PANEL

    rc, again = _main(capsys, _bootstrap_args(old, str(tmp_path / "guard"), scratch))
    assert rc != 0
    _assert_refusal(again, already_restarted=True)
    assert not os.path.exists(_marker_path(fresh))


# U9 — axis: the shipped prose names the refusal token and the marker file.
def test_u9_the_skill_and_the_reference_name_the_token_and_the_marker():
    skill = os.path.join(_PLUGIN, "skills", "review-code")
    with open(os.path.join(skill, "SKILL.md"), encoding="utf-8") as fh:
        skill_text = fh.read()
    with open(os.path.join(skill, "reference", "round-driver.md"), encoding="utf-8") as fh:
        reference_text = fh.read()
    assert TOKEN in skill_text
    assert TOKEN in reference_text
    assert MARKER in reference_text


# --- the edges -----------------------------------------------------------------------------

# E1 — axis: no saved state at all passes the gate; a fresh `next` bootstraps and stamps the
# current generation.
def test_e1_a_missing_state_file_bootstraps_a_current_session(tmp_path):
    session_dir = str(tmp_path / "empty")
    os.makedirs(session_dir)
    out = RD.cmd_next(session_dir, _cfg())
    assert out["ok"] is True and out["round"] == 1, out
    assert _read_state_file(session_dir)["sessionGeneration"] == RD.SESSION_GENERATION
    assert not os.path.exists(_marker_path(session_dir))


# E2 — axis: a state file that cannot be read as a JSON object passes the gate, and the refusal
# that already exists for it answers.
@pytest.mark.parametrize("raw", [b"\xff\xfe not utf-8", b"{not json", b"[1, 2]", b"2", b"null"],
                         ids=["not-utf-8", "not-json", "list", "number", "null"])
def test_e2_an_unreadable_state_keeps_its_existing_refusal(raw, tmp_path):
    session_dir = str(tmp_path / "broken")
    os.makedirs(session_dir)
    with open(_state_path(session_dir), "wb") as fh:
        fh.write(raw)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False
    assert out["reason"] != TOKEN
    assert "loop-state.json" in out["reason"]
    assert not os.path.exists(_marker_path(session_dir))


# E3 — axis: an unfinished state with no `sessionGeneration` is refused.
def test_e3_an_unfinished_state_without_the_key_is_refused(tmp_path, capsys):
    session_dir = _light_folder(tmp_path)
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    _assert_refusal(out, already_restarted=False)


# E4 — axis: only the driver's current integer generation is current; any other value, including
# the ones that compare equal to a number, is refused.
@pytest.mark.parametrize("generation", [1, 2, "3", None, True, 5, 8, float(RD.SESSION_GENERATION)],
                         ids=["one", "two", "string-three", "null", "true", "five-previous",
                              "eight-next", "float-current"])
def test_e4_a_generation_that_is_not_the_current_integer_is_refused(generation, tmp_path, capsys):
    session_dir = _light_folder(tmp_path, generation=generation)
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    _assert_refusal(out, already_restarted=False)


# E4 — axis: a generation-2 unfinished session holding a degraded same-family auditor target (the
# previous auditor policy) is refused at the upgrade gate, not resumed and credited.
def test_e4_a_generation_two_session_with_a_degraded_same_family_auditor_is_refused(tmp_path, capsys):
    session_dir = _light_folder(tmp_path, generation=2)
    state = _read_state_file(session_dir)
    state["config"]["fixerVendor"] = "codex"
    state["_auditTargets"] = [dict(id="f.py::bug@L1", findingKey="f.py::bug@L1", file="f.py", line=1,
                                   title="bug", severity="Important", auditorVendor="codex",
                                   independence="degraded")]
    _write_state_file(session_dir, state)
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    _assert_refusal(out, already_restarted=False)


# E4 — axis: the current generation is not refused.
def test_e4_the_current_generation_passes_the_gate(tmp_path):
    session_dir = _light_folder(tmp_path, generation=RD.SESSION_GENERATION)
    out = RD.cmd_next(session_dir)
    assert out.get("reason") != TOKEN, out
    assert not os.path.exists(_marker_path(session_dir))


# The version matrix is derived from the driver's own constants, never restated here.
EARLIER_VERSIONS = [v for v in RD.SUPPORTED_STATE_VERSIONS if v < RD.STATE_SCHEMA_VERSION]
FUTURE_VERSION = RD.STATE_SCHEMA_VERSION + 1


# E4b — axis: an unfinished state of the current generation but an earlier schema version
# is refused by `next`, `submit` and `record-result`; none of them reads it. Only the integer
# `STATE_SCHEMA_VERSION` is current.
@pytest.mark.parametrize("version", EARLIER_VERSIONS)
@pytest.mark.parametrize("name", ["next", "submit", "record-result"])
def test_e4b_an_unfinished_earlier_schema_version_is_refused(name, version, tmp_path):
    session_dir = _light_folder(tmp_path, generation=RD.SESSION_GENERATION)
    state = _read_state_file(session_dir)
    state["schemaVersion"] = version
    _write_state_file(session_dir, state)
    before = _snapshot(session_dir, exclude=(MARKER,))
    out = _DIRECT_CALLS[name](session_dir, None)
    _assert_refusal(out, already_restarted=False)
    assert _journal_rows(session_dir) == []
    assert _snapshot(session_dir, exclude=(MARKER,)) == before
    assert os.path.exists(_marker_path(session_dir))


# E4b — axis: an unfinished state of the current generation whose `schemaVersion` is not a
# supported earlier integer (1, a later one, null, a string, a float, a boolean) is not an earlier
# session: no marker is written, and `next` gives the refusal `load_state` gives for it.
@pytest.mark.parametrize(
    "version", [1, FUTURE_VERSION, None, str(RD.STATE_SCHEMA_VERSION),
                float(RD.STATE_SCHEMA_VERSION), float(EARLIER_VERSIONS[0]), True],
    ids=["one", "future", "null", "string-current", "float-current", "float-earlier", "true"])
def test_e4b_an_unsupported_schema_version_gets_the_loader_refusal_and_no_marker(version, tmp_path):
    session_dir = _light_folder(tmp_path, generation=RD.SESSION_GENERATION)
    state = _read_state_file(session_dir)
    state["schemaVersion"] = version
    _write_state_file(session_dir, state)
    out = RD.cmd_next(session_dir)
    assert out == {"ok": False, "reason": (
        "loop-state.json is schemaVersion %r, not one of %s — session dirs are "
        "per-invocation with no migration; start a fresh session dir"
        % (version, ", ".join(str(v) for v in RD.SUPPORTED_STATE_VERSIONS)))}
    assert not os.path.exists(_marker_path(session_dir))


# E4c — axis: a finished state of an earlier schema version passes the gate, and `next` answers its
# terminal again.
@pytest.mark.parametrize("version", EARLIER_VERSIONS)
def test_e4c_a_finished_earlier_schema_version_replays_its_terminal(version, tmp_path):
    session_dir = str(tmp_path / "finished")
    os.makedirs(session_dir)
    cfg = _cfg()
    payload = _drive_cli(session_dir, cfg, _responder(round1_findings=None, vendors=cfg["vendors"]))
    assert payload["verdict"] == "converged"
    replay_before = RD.cmd_next(session_dir)
    assert replay_before["ok"] and replay_before["action"] == RD.P_TERMINAL, replay_before
    state = _read_state_file(session_dir)
    state["schemaVersion"] = version
    _write_state_file(session_dir, state)
    assert RD._upgrade_gate_unlocked(session_dir, "next") is None
    replay_after = RD.cmd_next(session_dir)
    assert {k: v for k, v in replay_after.items() if k != "expectedStateHash"} == {
        k: v for k, v in replay_before.items() if k != "expectedStateHash"}
    assert not os.path.exists(_marker_path(session_dir))
    assert _read_state_file(session_dir)["schemaVersion"] == version


# E5 — axis: a finished earlier-generation state passes the gate (U7 drives one end to end).
def test_e5_a_finished_state_without_the_key_passes_the_gate(tmp_path):
    session_dir = _light_folder(tmp_path, terminal={"verdict": "converged"})
    assert RD._upgrade_gate_unlocked(session_dir, "next") is None
    assert not os.path.exists(_marker_path(session_dir))


# E6 — axis: a marker that already exists is reported and left byte for byte as it was.
def test_e6_an_existing_marker_means_already_restarted(tmp_path, capsys):
    session_dir = _light_folder(tmp_path)
    with open(_marker_path(session_dir), "wb") as fh:
        fh.write(b"left by hand\n")
    before = os.stat(_marker_path(session_dir))
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    _assert_refusal(out, already_restarted=True)
    with open(_marker_path(session_dir), "rb") as fh:
        assert fh.read() == b"left by hand\n"
    assert os.stat(_marker_path(session_dir)).st_mtime_ns == before.st_mtime_ns


# E7 — axis: a marker that cannot be created still leaves the command refused, with
# `markerWritten` false.
@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0,
                    reason="a read-only folder does not stop root")
def test_e7_a_marker_that_cannot_be_written_still_refuses(tmp_path, capsys):
    session_dir = _light_folder(tmp_path)
    os.chmod(session_dir, 0o500)
    try:
        rc, out = _main(capsys, ["next", "--session-dir", session_dir])
        assert not os.path.exists(_marker_path(session_dir))
    finally:
        os.chmod(session_dir, 0o700)
    assert rc != 0
    assert out["ok"] is False and out["reason"] == TOKEN, out
    assert out["alreadyRestarted"] is False
    assert out["markerWritten"] is False


class _FailingFile:
    """The marker's file object with one step made to raise `OSError`."""

    def __init__(self, real, step):
        self._real = real
        self._step = step

    def __enter__(self):
        self._real.__enter__()
        return self

    def __exit__(self, *exc):
        return self._real.__exit__(*exc)

    def write(self, data):
        if self._step == "write":
            raise OSError(5, "injected write failure")
        return self._real.write(data)

    def flush(self):
        if self._step == "flush":
            raise OSError(5, "injected flush failure")
        return self._real.flush()

    def fileno(self):
        return self._real.fileno()


# E7b — axis: a marker that was created but could not be written (write, flush or fsync fails) is
# removed again, the refusal says `markerWritten` false and `alreadyRestarted` false, and the next
# refusal, with the fault gone, writes the marker and answers `alreadyRestarted` false.
@pytest.mark.parametrize("step", ["write", "flush", "fsync"])
def test_e7b_a_marker_that_fails_to_write_is_removed_and_reported(step, tmp_path, capsys,
                                                                  monkeypatch):
    session_dir = _light_folder(tmp_path)
    real_fdopen, real_fsync = os.fdopen, os.fsync

    def is_marker(fd):
        # The session lock file goes through the same calls; only the marker is made to fail.
        try:
            return os.fstat(fd).st_ino == os.stat(_marker_path(session_dir)).st_ino
        except OSError:
            return False

    def faulty_fdopen(fd, *a, **kw):
        real = real_fdopen(fd, *a, **kw)
        return _FailingFile(real, step) if is_marker(fd) else real

    def faulty_fsync(fd):
        if is_marker(fd):
            raise OSError(5, "injected fsync failure")
        return real_fsync(fd)

    with monkeypatch.context() as faulty:
        faulty.setattr(RD.os, "fsync" if step == "fsync" else "fdopen",
                       faulty_fsync if step == "fsync" else faulty_fdopen)
        rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    assert out["ok"] is False and out["reason"] == TOKEN, out
    assert out["alreadyRestarted"] is False, out
    assert out["markerWritten"] is False, out
    assert not os.path.exists(_marker_path(session_dir))
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    _assert_refusal(out, already_restarted=False)
    assert os.path.exists(_marker_path(session_dir))
    with open(_marker_path(session_dir), encoding="utf-8") as fh:
        assert json.load(fh)["schema"] == RD.UPGRADE_RESTART_MARKER_SCHEMA


# E8 — axis: a session lock held by another process answers the lock-held refusal, as it does
# for every command.
def test_e8_a_held_lock_answers_the_lock_held_refusal(tmp_path, capsys):
    session_dir = _light_folder(tmp_path)
    with open(os.path.join(session_dir, round_records.LOCK_FILE), "w", encoding="utf-8") as fh:
        json.dump({"pid": 999999, "createdAt": "2026-01-01T00:00:00Z"}, fh)
    journal = os.path.join(session_dir, RD.JOURNAL_FILE)
    assert not os.path.exists(journal)
    rc, out = _main(capsys, ["next", "--session-dir", session_dir])
    assert rc != 0
    assert out["ok"] is False and out["reason"] == "next-locked", out
    assert out["holder"] == {"pid": 999999, "createdAt": "2026-01-01T00:00:00Z"}, out
    assert not os.path.exists(_marker_path(session_dir))
    assert not os.path.exists(journal), "the locked refusal journaled into the old folder"


# E9 — axis: a current-generation session with a half-done commit in staging is recovered, as
# before.
def test_e9_a_current_session_still_recovers_its_half_done_commit(tmp_path, monkeypatch):
    session_dir, _n = _half_done_commit(tmp_path, monkeypatch)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True, out
    assert not os.listdir(os.path.join(session_dir, "commits"))
    assert _read_state_file(session_dir)["sessionGeneration"] == RD.SESSION_GENERATION
    assert not os.path.exists(_marker_path(session_dir))


# E9b — axis: an earlier version that stopped after SEALING its first emit (no installed state file
# yet) is refused, not recovered: the staged state is judged by the same generation rule.
def _sealed_first_emit(tmp_path, monkeypatch, generation):
    session_dir = str(tmp_path / "first-emit")
    os.makedirs(session_dir)
    monkeypatch.setattr(RD, "SESSION_GENERATION", generation)
    _stop_next_commit_at(monkeypatch, "orders-emit", "sealed")
    with pytest.raises(RD.round_commit.StopPoint):
        RD.cmd_next(session_dir, _cfg())
    monkeypatch.undo()
    assert not os.path.exists(_state_path(session_dir))
    assert os.listdir(os.path.join(session_dir, "commits"))
    return session_dir


def test_e9b_a_sealed_first_emit_of_an_earlier_version_is_refused_not_recovered(tmp_path, monkeypatch):
    # bites on: _earlier_generation_unfinished returning False when loop-state.json is absent
    session_dir = _sealed_first_emit(tmp_path, monkeypatch, generation=1)
    staged = os.path.join(session_dir, "commits")
    before = _snapshot(staged)
    out = RD.cmd_next(session_dir)
    _assert_refusal(out, already_restarted=False)
    assert _snapshot(staged) == before
    assert not os.path.exists(_state_path(session_dir))


def test_e9c_a_sealed_first_emit_of_the_current_version_is_still_recovered(tmp_path, monkeypatch):
    session_dir = _sealed_first_emit(tmp_path, monkeypatch, generation=RD.SESSION_GENERATION)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True, out
    assert _read_state_file(session_dir)["sessionGeneration"] == RD.SESSION_GENERATION
    assert not os.path.exists(_marker_path(session_dir))


# E10 — axis: `advance`, called straight at its own entry (even with `break_lock`), is refused
# before it reconciles, breaks a lock or journals anything.
@pytest.mark.parametrize("break_lock", [False, True], ids=["plain", "break-lock"])
def test_e10_advance_is_refused_at_its_own_entry(break_lock, tmp_path):
    session_dir = _earlier_version_folder(tmp_path)
    before = _snapshot(session_dir)
    rows = _journal_rows(session_dir)
    out = RD.cmd_advance(session_dir, break_lock=break_lock)
    _assert_refusal(out, already_restarted=False)
    assert _journal_rows(session_dir) == rows
    assert _snapshot(session_dir, exclude=(MARKER,)) == before


# E11 — axis: each of the other seven `cmd_*` entries, called straight at its own function with its
# required arguments, answers the refusal at that entry and leaves the folder as it was (`main`'s
# own gate would otherwise answer first and hide a missing gate call).
_DIRECT_CALLS = {
    "next": lambda d, ruling: RD.cmd_next(d),
    "rule": lambda d, ruling: RD.cmd_rule(d, ruling, "x"),
    "submit": lambda d, ruling: RD.cmd_submit(d, RD.P_PANEL, 1, "x", {}),
    "record-result": lambda d, ruling: RD.cmd_record_result(d),
    "record-missing": lambda d, ruling: RD.cmd_record_missing(d, "x", 1, "x"),
    "attest": lambda d, ruling: RD.cmd_attest(d, "x", "x"),
    "checkpoint": lambda d, ruling: RD.cmd_checkpoint(d, "tripwire"),
}


@pytest.mark.parametrize("name", sorted(_DIRECT_CALLS))
def test_e11_each_entry_refuses_an_earlier_version_folder_when_called_directly(name, tmp_path):
    session_dir = _earlier_version_folder(tmp_path)
    ruling = str(tmp_path / "ruling.json")
    with open(ruling, "w", encoding="utf-8") as fh:
        json.dump({}, fh)
    before = _snapshot(session_dir)
    out = _DIRECT_CALLS[name](session_dir, ruling)
    _assert_refusal(out, already_restarted=False)
    assert _snapshot(session_dir, exclude=(MARKER,)) == before


# --- a session picked back up --------------------------------------------------------------

# P1 — axis: a review interrupted and picked back up with `next` in the same session keeps its
# findings, round, decisions and pending step, and carries on.
def test_p1_a_session_picked_back_up_is_unchanged_and_carries_on(tmp_path):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    respond = _responder(round1_findings=list(_FINDINGS))
    pending = _drive_to_round(session_dir, 2, respond)
    assert pending["round"] == 2

    state_path = _state_path(session_dir)
    with open(state_path, "rb") as fh:
        state_bytes = fh.read()
    state = json.loads(state_bytes)
    findings = state["findings"]
    assert len({f["severity"] for f in findings}) >= 2, findings
    round_one = state["rounds"]["1"]
    decisions = state["decisions"]
    outcomes = [(row.get("cmd"), row.get("outcome")) for row in _journal_rows(session_dir)]
    assert outcomes
    del state
    expected = {key: pending[key] for key in ("phase", "round", "attempt", "expectedStateHash")}

    # the interruption: nothing in memory survives
    del pending
    gc.collect()

    resumed = RD.cmd_next(session_dir)
    assert resumed["ok"] is True, resumed
    assert {key: resumed[key] for key in expected} == expected
    with open(state_path, "rb") as fh:
        assert fh.read() == state_bytes
    reloaded = _read_state_file(session_dir)
    assert reloaded["findings"] == findings
    assert reloaded["rounds"]["1"] == round_one
    assert reloaded["decisions"] == decisions
    assert reloaded["sessionGeneration"] == RD.SESSION_GENERATION
    after_outcomes = [(row.get("cmd"), row.get("outcome")) for row in _journal_rows(session_dir)]
    assert after_outcomes[:len(outcomes)] == outcomes
    assert not os.path.exists(_marker_path(session_dir))

    # carry on: the pending round-2 step is accepted and the driver moves to the following step
    submitted = RD.cmd_submit(session_dir, resumed["phase"], resumed["attempt"],
                              resumed["expectedStateHash"],
                              respond(resumed["phase"], resumed["payload"], resumed["round"]))
    assert submitted["ok"] is True, submitted
    following = RD.cmd_next(session_dir)
    assert following["ok"] is True, following
    assert following["expectedStateHash"] != expected["expectedStateHash"]
    assert (following["phase"], following["round"], following["attempt"]) != (
        expected["phase"], expected["round"], expected["attempt"])
