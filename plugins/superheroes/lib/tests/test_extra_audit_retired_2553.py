"""The extra audit round is retired (issue 2553, layer 2 of 2497): nothing begins one, a session that holds one
finishes it, and an old record that shows one still reads.

The library function `cmd_extra_audit` refuses `extra-audit-retired` at once, naming the bounded pass: before the
session lock, any gate and commit recovery, and before it reads any state, receipt or order file. The CLI applies
the shared upgrade gate first, as for every command: on a folder of an earlier version it refuses
`session-from-earlier-version`, and on a current folder it reaches the function. The verb posts nothing. Its
one write is the journal row of the refusal, and only when the session folder exists. A session whose state holds
`extraAudit` (saved inside an ordered round) finishes it and its record says so; a session that holds none never
writes `rounds.extraAudit`.

Bite-proof record: i2553_extra_audit_retired
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as RR  # noqa: E402
import test_c1l4b_extra_audit as X  # noqa: E402
import test_review_record as TRR  # noqa: E402
import test_session_pickup_and_upgrade_1721 as U  # noqa: E402

RD = X.RD
PR = X.PR
WHY = X.WHY
RETIRED = "extra-audit-retired"


def _boom(*_args, **_kwargs):
    raise AssertionError("the retired verb must read and post nothing")


READERS = {"create_comment": _boom, "list_comments": _boom, "repo_name": _boom}


def _snapshot(d):
    """Name and sha256 of every file in the session folder but the driver journal."""
    files = X._files(d)
    lock = os.path.join(d, RD.round_records.LOCK_FILE)
    if os.path.exists(lock):
        files[RD.round_records.LOCK_FILE] = X._read(d, RD.round_records.LOCK_FILE)
    return files


def _journal(d):
    path = os.path.join(d, RD.JOURNAL_FILE)
    if not os.path.exists(path):
        return b""
    with open(path, "rb") as fh:
        return fh.read()


def _nothing_runs(monkeypatch):
    """The lock, the upgrade gates, commit recovery and every state load fail the test if reached."""
    for target, name in ((RD.round_records, "session_lock"), (RD, "_upgrade_gate"),
                         (RD, "_upgrade_gate_unlocked"), (RD, "_commit_recover_or_refuse"),
                         (RD, "load_state")):
        monkeypatch.setattr(target, name, _boom)


def _assert_one_refusal_row(d, before_rows, before_bytes):
    after = _journal(d)
    assert after.startswith(before_bytes), "the journal rows already there changed"
    rows = RD.read_journal(d)
    assert len(rows) == len(before_rows) + 1, rows[len(before_rows):]
    assert rows[:len(before_rows)] == before_rows
    assert (rows[-1]["cmd"], rows[-1]["outcome"], rows[-1]["reason"]) == ("extra-audit", "refused", RETIRED)


# --- (a) the verb refuses and changes nothing but its journal row ------------------------------------

def test_a_the_verb_refuses_extra_audit_retired_naming_the_bounded_pass_and_changes_nothing(tmp_path, monkeypatch):
    # axis: the verb refuses every call at once with the retired token and writes one journal row and nothing
    # else, so no order reopens a capped session — see bite-proof record i2553_extra_audit_retired (E-retired)
    d = X._capped(tmp_path)
    files, rows, raw = _snapshot(d), RD.read_journal(d), _journal(d)
    state_before = X._state(d)
    assert state_before["decisions"][-1]["kind"] == "round-cap" and "extraAudit" not in state_before
    _nothing_runs(monkeypatch)
    out = RD.cmd_extra_audit(d, str(tmp_path / "order.json"), "advisor", PR, readers=READERS)
    assert out["ok"] is False and out["reason"] == RETIRED, out
    assert "bounded pass" in out["detail"], out
    assert _snapshot(d) == files
    _assert_one_refusal_row(d, rows, raw)
    monkeypatch.undo()
    assert X._state(d) == state_before


_WATCHING = False  # an audit hook cannot be removed: it records only while this is true
_OPENED = []


def _watch_opens(event, args):
    if _WATCHING and event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        _OPENED.append(os.path.abspath(os.fsdecode(args[0])))


sys.addaudithook(_watch_opens)


@pytest.mark.parametrize("make", ["missing-order", "garbage-order", "valid-order"])
def test_a_the_order_file_is_never_read(tmp_path, make):
    # axis: the retired verb never opens the order file, so it fails when the verb opens it and then refuses — see
    # bite-proof record i2554_bounded_pass_record (E-no-read)
    global _WATCHING
    d = X._capped(tmp_path)
    order = str(tmp_path / "order.json")
    if make == "garbage-order":
        with open(order, "w", encoding="utf-8") as fh:
            fh.write("{why")
    elif make == "valid-order":
        with open(order, "w", encoding="utf-8") as fh:
            json.dump({"why": WHY}, fh)
    files, rows, raw = _snapshot(d), RD.read_journal(d), _journal(d)
    del _OPENED[:]
    _WATCHING = True
    try:
        out = RD.cmd_extra_audit(d, order, "advisor", PR, readers=READERS)
    finally:
        _WATCHING = False
    assert os.path.abspath(order) not in _OPENED, "the verb opened the order file"
    assert out["ok"] is False and out["reason"] == RETIRED, out
    assert _snapshot(d) == files
    _assert_one_refusal_row(d, rows, raw)


def test_a_an_unreadable_state_still_refuses_retired_with_one_journal_row(tmp_path):
    d = str(tmp_path / "torn")
    os.makedirs(d)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    files, rows, raw = _snapshot(d), RD.read_journal(d), _journal(d)
    out = RD.cmd_extra_audit(d, str(tmp_path / "absent.json"), "advisor", PR, readers=READERS)
    assert out["ok"] is False and out["reason"] == RETIRED, out
    assert _snapshot(d) == files
    _assert_one_refusal_row(d, rows, raw)


def test_a_a_session_folder_that_does_not_exist_returns_the_refusal_and_writes_nothing(tmp_path):
    missing = str(tmp_path / "absent")
    out = RD.cmd_extra_audit(missing, str(tmp_path / "order.json"), "advisor", PR, readers=READERS)
    assert out["ok"] is False and out["reason"] == RETIRED and "bounded pass" in out["detail"], out
    assert not os.path.exists(missing)
    assert sorted(os.listdir(str(tmp_path))) == []


# --- (b) the same refusal through the CLI entry ------------------------------------------------------

def test_b_the_cli_entry_refuses_extra_audit_retired_on_a_current_session(tmp_path, capsys):
    d = X._capped(tmp_path)
    files, rows, raw = _snapshot(d), RD.read_journal(d), _journal(d)
    rc = RD.main(["extra-audit", "--session-dir", d, "--order-file", str(tmp_path / "order.json"),
                  "--by", "advisor", "--pr", str(PR)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False and out["reason"] == RETIRED and "bounded pass" in out["detail"], out
    assert _snapshot(d) == files
    _assert_one_refusal_row(d, rows, raw)


def test_b_the_cli_entry_refuses_an_earlier_version_folder_like_every_command(tmp_path, capsys):
    session_dir = U._earlier_version_folder(tmp_path)
    argv = U._required_argv("extra-audit", session_dir, str(tmp_path / "scratch"))
    RD.build_parser().parse_args(argv)
    before = U._snapshot(session_dir)
    rc, out = U._main(capsys, argv)
    assert rc != 0
    assert out["reason"] == U.TOKEN, out
    assert U._snapshot(session_dir, exclude=(U.MARKER,)) == before


# --- (c) an old record that carries rounds.extraAudit still reads ------------------------------------

def test_c_an_old_record_carrying_rounds_extra_audit_validates_and_its_summary_says_the_extra_round():
    rounds = {"count": 3, "cap": 4, "stoppedAtCap": False, "extraAudit": {"why": WHY}}
    account = TRR.account(rounds=rounds)
    RR._validate(account)
    line = RR._extra_audit_line(account["rounds"], False)
    assert line == "Extra audit round: ran, ordered at the vet and not counted in the 4 rounds: %s." % WHY, line


def test_c_the_writer_still_refuses_a_second_sessions_account_that_shows_the_round(tmp_path):
    fake = TRR.Fake()
    rounds = {"count": 3, "cap": 4, "stoppedAtCap": False, "extraAudit": {"why": WHY}}
    assert RR.write(TRR.put(tmp_path, TRR.account(sessionId="s-A", rounds=rounds)), str(tmp_path),
                    fake.readers())["ok"]
    out = RR.write(TRR.put(tmp_path, TRR.account(sessionId="s-B", rounds=rounds), "second.json"),
                   str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-record-extra-audit-repeated", out


# --- (d) a session that never held extraAudit never writes it ----------------------------------------

def test_d_a_session_that_never_held_extra_audit_writes_an_account_with_no_rounds_extra_audit(tmp_path):
    # axis: the account carries `rounds.extraAudit` only when the state holds `extraAudit` — see bite-proof record
    # i2553_extra_audit_retired (E-noemit)
    d = X._capped(tmp_path)
    state = X._state(d)
    assert "extraAudit" not in state
    account = X._account(tmp_path / "none", state)
    assert "extraAudit" not in account["rounds"], account["rounds"]
    RR._validate(account)
    # A/B: the same state holding an ordered round does carry it
    held = dict(state, extraAudit={"why": WHY, "round": state["round"] + 1})
    assert X._account(tmp_path / "held", held)["rounds"]["extraAudit"] == {"why": WHY}


# --- (e) the legacy resume holds on this head --------------------------------------------------------

def test_e_a_session_saved_inside_an_ordered_extra_round_resumes_and_finishes_with_its_record(tmp_path):
    d, batch = X._ordered(tmp_path)
    state = X._state(d)
    assert state["extraAudit"]["round"] == X.CAP + 1 and "boundedPass" not in state and not state.get("terminal")
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_AUDITS and [t["id"] for t in n["payload"]["targets"]] == batch, n
    terminal, emitted = X._finish(d, X._respond())
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "converged" and final["decisions"][-1]["kind"] == "converged"
    assert "boundedPass" not in final
    account = X._account(tmp_path / "rec", final)
    assert account["rounds"]["extraAudit"] == {"why": WHY} and account["rounds"]["count"] == X.CAP
    RR._validate(account)
