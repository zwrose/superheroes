"""The two session-move verbs are gone, and the damaged-journal guard that outlived them still bites (#1721)."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_ROUND_DRIVER = os.path.join(_LIB, "round_driver.py")
_SPEC = importlib.util.spec_from_file_location("round_driver", _ROUND_DRIVER)
RD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RD)

import round_adapters  # noqa: E402

_TDI_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_TDI_SPEC)
_TDI_SPEC.loader.exec_module(_TDI)


# --- the removed verbs -------------------------------------------------------------------------

def _run_cli(*argv):
    return subprocess.run([sys.executable, "-B", _ROUND_DRIVER, *argv],
                          capture_output=True, text=True, timeout=60)


def test_relocate_is_not_a_subcommand(tmp_path):
    # bites on: a `relocate` subparser still registered in the round driver's command line
    proc = _run_cli("relocate", "--session-dir", str(tmp_path), "--repo-root", str(tmp_path),
                    "--by", "tester")
    assert proc.returncode != 0
    assert "invalid choice: 'relocate'" in proc.stderr, proc.stderr
    assert not hasattr(RD, "cmd_relocate")


def test_re_emit_is_not_a_subcommand(tmp_path):
    # bites on: a `re-emit` subparser still registered in the round driver's command line
    proc = _run_cli("re-emit", "--session-dir", str(tmp_path), "--by", "tester")
    assert proc.returncode != 0
    assert "invalid choice: 're-emit'" in proc.stderr, proc.stderr
    assert not hasattr(RD, "cmd_re_emit")


# --- the damaged-journal guard -----------------------------------------------------------------

def _repo(tmp_path):
    root = str(tmp_path / "repo")
    os.makedirs(root)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=root)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=root)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=root)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=root)
    pin = subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
    with open(os.path.join(root, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a\n")
    subprocess.check_call(["git", "-C", root, "add", "f.py"])
    subprocess.check_call(["git", "-C", root, "commit", "-q", "-m", "change"])
    head = subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(
        ["git", "-C", root, "remote", "add", "origin", "https://github.com/o/r.git"])
    toplevel = subprocess.check_output(
        ["git", "-C", root, "rev-parse", "--show-toplevel"], text=True).strip()
    branch = subprocess.check_output(
        ["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    diff_text = subprocess.check_output(["git", "-C", root, "diff", "%s...HEAD" % pin], text=True)
    return {"root": toplevel, "pin": pin, "head": head, "branch": branch, "diff_text": diff_text}


def _session(tmp_path, repo):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    diff_path = os.path.join(session_dir, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diff_path))
    with open(diff_path, "w", encoding="utf-8") as fh:
        fh.write(repo["diff_text"])
    meta = {
        "mode": "branch",
        "baseRef": repo["pin"],
        "baseBranch": "main",
        "baseFetch": "fetched",
        "repoRoot": repo["root"],
        "headSha": repo["head"],
        "branch": repo["branch"],
        "sessionDir": os.path.realpath(session_dir),
    }
    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc = RD.main(["next", "--session-dir", session_dir, "--repo-root", repo["root"],
                  "--diff-path", diff_path, "--vendors", '["codex","cursor"]'])
    assert rc == 0, "bootstrap next must exit 0 with pending dispatch-panel"
    return session_dir, diff_path


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _journal_rows(session_dir):
    return RD.read_journal(session_dir)


def _panel_roster(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None, reason
    return state, pend, roster


def _first_seat(roster):
    seat = roster[0]
    if isinstance(seat, tuple):
        return seat[0], seat[1]
    return seat, 0


def _land_first_panel_seat(session_dir, diff_path):
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _TDI._land(session_dir, state, pend, seat,
               _TDI._payload_for(session_dir, state, pend, seat, [], diff_path),
               occurrence=occurrence)
    return state, pend, seat, occurrence


def _panel_hand_artifact(session_dir):
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    dims = RD._panel_dimensions(state["config"])
    return {"seats": {dim: {"findings": [], "confidence": "high", "tier": RD.DEEP}
                      for dim in dims}}


def _seat_store_tree(session_dir):
    snap = {}
    round_root = os.path.join(session_dir, "round-1", "seats")
    if not os.path.isdir(round_root):
        return snap
    for phase in os.listdir(round_root):
        pdir = os.path.join(round_root, phase)
        if not os.path.isdir(pdir):
            continue
        for name in os.listdir(pdir):
            path = os.path.join(pdir, name)
            if os.path.isfile(path):
                snap[os.path.relpath(path, session_dir)] = _read_bytes(path)
    return snap


def _damage_journal(session_dir, kind):
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    if kind == "unparseable":
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write("{not-json\n")
    elif kind == "null":
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write("null\n")
    elif kind == "list":
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write("[]\n")
    elif kind == "number":
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write("42\n")
    elif kind == "string":
        with open(journal_path, "a", encoding="utf-8") as fh:
            fh.write('"hello"\n')
    elif kind == "invalid-utf8":
        with open(journal_path, "ab") as fh:
            fh.write(b"\xff\n")
    elif kind == "unopenable":
        os.remove(journal_path)
        os.mkdir(journal_path)
    else:
        raise ValueError("unknown damage kind %r" % kind)


_CALLERS = ("hand-submit", "record-result", "record-sweep", "advance")

_DAMAGE_KINDS = ("unparseable", "null", "list", "number", "string", "invalid-utf8", "unopenable")


def _call(caller, session_dir, state, pend, seat, occurrence):
    if caller == "hand-submit":
        return RD.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                             RD.state_hash(state), _panel_hand_artifact(session_dir))
    if caller == "record-result":
        return RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    if caller == "record-sweep":
        return RD.cmd_record_result(session_dir, sweep=True)
    if caller == "advance":
        return RD.cmd_advance(session_dir)
    raise ValueError(caller)


@pytest.mark.parametrize("kind", _DAMAGE_KINDS)
@pytest.mark.parametrize("caller", _CALLERS)
def test_damaged_journal_refuses_every_caller(tmp_path, kind, caller):
    # bites on: a record, sweep, advance or hand submit of a dispatch phase going ahead over a journal it cannot read
    repo = _repo(tmp_path)
    session_dir, diff_path = _session(tmp_path, repo)
    state, pend, seat, occurrence = _land_first_panel_seat(session_dir, diff_path)
    _damage_journal(session_dir, kind)
    store_before = _seat_store_tree(session_dir)
    state_before = _read_bytes(os.path.join(session_dir, RD.STATE_FILE))
    out = _call(caller, session_dir, state, pend, seat, occurrence)
    assert out["ok"] is False
    assert out["reason"] == RD.JOURNAL_DAMAGED_CAUSE == "journal-damaged"
    assert out["detail"] == RD.JOURNAL_DAMAGED_DETAIL
    assert _seat_store_tree(session_dir) == store_before
    assert _read_bytes(os.path.join(session_dir, RD.STATE_FILE)) == state_before


@pytest.mark.parametrize("marker", (False, True))
def test_healthy_journal_is_not_refused_with_or_without_a_fault_marker(tmp_path, marker):
    # bites on: the guard refusing a readable journal because a journal-fault marker file sits beside it
    repo = _repo(tmp_path)
    session_dir, diff_path = _session(tmp_path, repo)
    state, pend, seat, occurrence = _land_first_panel_seat(session_dir, diff_path)
    if marker:
        open(os.path.join(session_dir, RD.JOURNAL_FAULT_FILE), "w", encoding="utf-8").close()
    assert RD._journal_damaged(session_dir) is False
    out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"] is True, out
