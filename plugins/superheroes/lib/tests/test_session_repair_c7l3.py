"""C7 L3 (WO-3): a review session whose `loop-state.json` is damaged after a committed state write is
repaired from its mirror and carries on to the same terminal; a session that cannot be repaired gets
the refusal it always got; repair never runs outside the session lock and never resumes an
earlier-version session.

Drives the real round driver over a real session dir: `cmd_next` / `cmd_advance` through the
integration harness for the damaged-session test, and `cmd_next` over a bootstrapped session for each
fail-closed edge.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c7l3_wo3_driver.md
"""
import ast
import hashlib
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record_session as rs  # noqa: E402
import round_commit  # noqa: E402
import round_driver as RD  # noqa: E402
import test_review_record_session as TRS  # noqa: E402
import test_round_driver_integration as TI  # noqa: E402

REFUSAL = "loop-state.json is unreadable — start a fresh session dir"
DRIVER_SOURCE = os.path.join(_LIB, "round_driver.py")


# --- helpers ------------------------------------------------------------------------------------

def _state_path(session_dir):
    return os.path.join(session_dir, RD.STATE_FILE)


def _mirror_path(session_dir):
    return os.path.join(session_dir, RD.MIRROR_FILE)


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


def _repair_rows(session_dir):
    return [row for row in RD.read_journal(session_dir) if row.get("cmd") == "repair"]


def _session(tmp_path, name="s"):
    session_dir, _gitdir, _head = TI._bootstrap(tmp_path, name=name)
    return session_dir


def _forge_mirror(session_dir, state, session_id="from-meta", sha=None):
    """Replace the mirror with an envelope around `state` (a dict, or the exact text)."""
    text = state if isinstance(state, str) else RD._canonical(state)
    if session_id == "from-meta":
        session_id = RD._meta_session_id(session_dir)
    envelope = {"schema": RD.MIRROR_SCHEMA, "sessionId": session_id,
                "stateSha256": sha or hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "state": text}
    _write(_mirror_path(session_dir), RD._canonical(envelope).encode("utf-8"))


def _truncate(path):
    data = _read(path)
    _write(path, data[: len(data) // 2])


def _assert_refused_as_before(session_dir, damaged_bytes):
    out = RD.cmd_next(session_dir)
    assert out == {"ok": False, "reason": REFUSAL}, out
    assert _read(_state_path(session_dir)) == damaged_bytes
    assert _repair_rows(session_dir) == []


# --- the mirror ---------------------------------------------------------------------------------

def test_every_state_write_leaves_a_mirror_of_the_exact_bytes(tmp_path):
    session_dir = _session(tmp_path)
    envelope = json.loads(_read(_mirror_path(session_dir)))
    state_bytes = _read(_state_path(session_dir))
    assert envelope["schema"] == RD.MIRROR_SCHEMA
    assert envelope["sessionId"] == RD._meta_session_id(session_dir)
    assert envelope["stateSha256"] == hashlib.sha256(state_bytes).hexdigest()
    assert envelope["state"].encode("utf-8") == state_bytes


def test_a_direct_save_refreshes_the_mirror_so_repair_restores_the_new_bytes(tmp_path):
    session_dir = _session(tmp_path)
    _ok, state = RD.load_state(session_dir)
    state["directSaveMarker"] = "after-bootstrap"
    RD.save_state(session_dir, state)
    saved = _read(_state_path(session_dir))
    assert b"directSaveMarker" in saved
    envelope = json.loads(_read(_mirror_path(session_dir)))
    assert envelope["state"].encode("utf-8") == saved
    assert envelope["stateSha256"] == hashlib.sha256(saved).hexdigest()
    _truncate(_state_path(session_dir))
    assert RD.cmd_next(session_dir)["ok"] is True
    assert _read(_state_path(session_dir)) == saved


def test_the_mirror_of_a_state_with_no_session_id_names_none(tmp_path):
    state_bytes = b'{"round":1}'
    envelope = json.loads(RD._mirror_bytes(str(tmp_path), state_bytes))
    assert envelope["sessionId"] is None
    assert envelope["state"] == '{"round":1}'


def _all_state_writes_in(tree):
    """{function name: [call line]} for each call in `tree` that writes the state file."""
    writers = {"add_replace_file", "atomic_write_bytes", "atomic_write_json", "replace", "rename",
               "move", "unlink", "remove", "write_text", "write_bytes"}
    found = {}
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        state_names = {n.id for n in ast.walk(func) if isinstance(n, ast.Name) and n.id == "STATE_FILE"}
        if not state_names:
            continue
        tainted = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and any(
                    isinstance(n, ast.Name) and n.id == "STATE_FILE" for n in ast.walk(node.value)):
                tainted |= {t.id for t in node.targets if isinstance(t, ast.Name)}

        def touches_state(expr):
            return any(isinstance(n, ast.Name) and (n.id == "STATE_FILE" or n.id in tainted)
                       for n in ast.walk(expr))

        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            args = list(node.args) + [kw.value for kw in node.keywords]
            if callee in writers and any(touches_state(a) for a in args):
                found.setdefault(func.name, []).append(node.lineno)
            elif callee == "open" and args and touches_state(args[0]):
                mode = node.args[1] if len(node.args) > 1 else next(
                    (kw.value for kw in node.keywords if kw.arg == "mode"), None)
                if isinstance(mode, ast.Constant) and any(c in str(mode.value) for c in "wax+"):
                    found.setdefault(func.name, []).append(node.lineno)
    return found


def test_no_code_writes_the_state_file_but_through_the_one_stager():
    """axis: no write site of the state file can skip its mirror — the census names every function
    that writes it — see bite-proof record c7l3_wo3_driver"""
    with open(DRIVER_SOURCE, encoding="utf-8") as fh:
        writes = _all_state_writes_in(ast.parse(fh.read()))
    assert set(writes) == {"_stage_state"}, writes


def test_the_census_sees_a_state_write_it_is_not_told_about():
    source = (
        "def sneaky(session_dir, data):\n"
        "    with open(os.path.join(session_dir, STATE_FILE), 'w') as fh:\n"
        "        fh.write(data)\n"
        "def sneaky_commit(c, session_dir, data):\n"
        "    path = os.path.join(session_dir, STATE_FILE)\n"
        "    c.add_replace_file(path, data)\n"
        "def reads(session_dir):\n"
        "    with open(os.path.join(session_dir, STATE_FILE)) as fh:\n"
        "        return fh.read()\n")
    assert set(_all_state_writes_in(ast.parse(source))) == {"sneaky", "sneaky_commit"}


# --- repair: a damaged state is restored byte for byte -------------------------------------------

def test_a_state_that_reads_is_left_alone(tmp_path):
    session_dir = _session(tmp_path)
    before = _read(_state_path(session_dir))
    assert RD.cmd_next(session_dir)["ok"] is True
    assert _read(_state_path(session_dir)) == before
    assert _repair_rows(session_dir) == []


def _damage(session_dir, kind):
    path = _state_path(session_dir)
    if kind == "missing":
        os.remove(path)
    elif kind == "not-json":
        _truncate(path)
    elif kind == "not-an-object":
        _write(path, b"[1, 2, 3]")
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["missing", "not-json", "not-an-object"])
def test_a_damaged_state_is_restored_from_the_mirror_and_journalled(tmp_path, kind):
    session_dir = _session(tmp_path)
    before = _read(_state_path(session_dir))
    rnd = json.loads(before)["round"]
    _damage(session_dir, kind)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True, out
    assert _read(_state_path(session_dir)) == before
    rows = _repair_rows(session_dir)
    assert len(rows) == 1, rows
    assert rows[0]["outcome"] == "session-repaired"
    assert rows[0]["damaged"] == kind
    assert rows[0]["round"] == rnd


def test_cli_next_repairs_a_missing_state_before_the_fresh_session_checks(tmp_path, monkeypatch, capsys):
    session_dir = _session(tmp_path)
    before = _read(_state_path(session_dir))
    os.remove(_state_path(session_dir))
    monkeypatch.setattr(RD.review_base_guard, "check_base",
                        lambda *a, **k: {"ok": True, "baseRef": "main"})
    RD.main(["next", "--session-dir", session_dir])
    assert "round-diff-required" not in capsys.readouterr().out
    assert _read(_state_path(session_dir)) == before
    assert len(_repair_rows(session_dir)) == 1


@pytest.mark.parametrize("via", ["cmd_next", "cli"])
def test_a_repair_commit_that_fails_after_the_state_lands_stops_the_command(
        tmp_path, monkeypatch, capsys, via):
    session_dir = _session(tmp_path)
    before = _read(_state_path(session_dir))
    os.remove(_state_path(session_dir))

    def state_lands_then_mirror_fails(sd, state_bytes):
        _write(_state_path(sd), state_bytes)
        raise OSError("mirror replace failed")

    monkeypatch.setattr(RD, "_write_state_bytes", state_lands_then_mirror_fails)
    if via == "cmd_next":
        out = RD.cmd_next(session_dir)
    else:
        assert RD.main(["next", "--session-dir", session_dir]) == 1
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False and out["reason"] == "commit-recovery-failed", out
    assert _repair_rows(session_dir) == []


def test_a_repair_that_fails_while_the_state_is_still_missing_stops_the_command(tmp_path, monkeypatch):
    session_dir = _session(tmp_path)
    os.remove(_state_path(session_dir))

    def fails_before_landing(sd, state_bytes):
        raise OSError("replace failed")

    monkeypatch.setattr(RD, "_write_state_bytes", fails_before_landing)
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False and out["reason"] == "commit-recovery-failed", out
    assert not os.path.exists(_state_path(session_dir))


def test_a_state_that_cannot_be_read_is_classed_unreadable_and_refused_as_before(tmp_path):
    session_dir = _session(tmp_path)
    os.remove(_state_path(session_dir))
    os.mkdir(_state_path(session_dir))                 # a read of it raises an OSError
    assert RD._state_damage(session_dir) == "unreadable"
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False and out["reason"] == REFUSAL
    assert os.path.isdir(_state_path(session_dir))
    assert _repair_rows(session_dir) == []


def test_a_repaired_session_is_repaired_once(tmp_path):
    session_dir = _session(tmp_path)
    _truncate(_state_path(session_dir))
    assert RD.cmd_next(session_dir)["ok"] is True
    assert RD.cmd_next(session_dir)["ok"] is True
    assert len(_repair_rows(session_dir)) == 1


def test_a_mirror_with_no_session_id_still_repairs(tmp_path):
    session_dir = _session(tmp_path)
    state_text = _read(_state_path(session_dir)).decode("utf-8")
    _forge_mirror(session_dir, state_text, session_id=None)
    _truncate(_state_path(session_dir))
    assert RD.cmd_next(session_dir)["ok"] is True
    assert _read(_state_path(session_dir)).decode("utf-8") == state_text


# --- repair: the mirror that cannot be trusted changes nothing -----------------------------------

def test_a_damaged_state_with_no_mirror_is_refused_as_before(tmp_path):
    session_dir = _session(tmp_path)
    os.remove(_mirror_path(session_dir))
    _truncate(_state_path(session_dir))
    _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))


def test_a_torn_mirror_file_is_refused_as_before(tmp_path):
    session_dir = _session(tmp_path)
    _truncate(_mirror_path(session_dir))
    _truncate(_state_path(session_dir))
    _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))


def test_a_mirror_whose_state_does_not_hash_to_its_hash_is_refused_as_before(tmp_path):
    """axis: a mirror whose bytes do not hash to the hash it carries is torn, so it restores nothing —
    see bite-proof record c7l3_wo3_driver"""
    session_dir = _session(tmp_path)
    state = json.loads(_read(_state_path(session_dir)))
    honest_sha = hashlib.sha256(RD._canonical(state).encode("utf-8")).hexdigest()
    state["round"] = 9                                 # the text no longer says what the hash covers
    _forge_mirror(session_dir, state, sha=honest_sha)
    _truncate(_state_path(session_dir))
    _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))


def test_a_mirror_whose_state_is_not_an_object_is_refused_as_before(tmp_path):
    session_dir = _session(tmp_path)
    _forge_mirror(session_dir, "[1, 2, 3]")
    _truncate(_state_path(session_dir))
    _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))


def test_a_mirror_whose_state_has_an_unsupported_schema_version_is_refused_as_before(tmp_path):
    session_dir = _session(tmp_path)
    state = json.loads(_read(_state_path(session_dir)))
    state["schemaVersion"] = 99
    _forge_mirror(session_dir, state)
    _truncate(_state_path(session_dir))
    _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))


def test_a_mirror_of_another_session_is_refused_as_before(tmp_path):
    session_dir = _session(tmp_path)
    state = json.loads(_read(_state_path(session_dir)))
    _forge_mirror(session_dir, state, session_id="a-different-session")
    _truncate(_state_path(session_dir))
    _assert_refused_as_before(session_dir, _read(_state_path(session_dir)))


def test_a_mirror_of_an_unfinished_earlier_version_session_gets_the_restart_refusal(tmp_path):
    """axis: a mirror of an unfinished earlier-version session is refused with the restart answer,
    never restored — see bite-proof record c7l3_wo3_driver"""
    session_dir = _session(tmp_path)
    state = json.loads(_read(_state_path(session_dir)))
    assert not state.get("terminal")
    state["schemaVersion"] = RD.STATE_SCHEMA_VERSION - 1
    assert state["schemaVersion"] in RD.SUPPORTED_STATE_VERSIONS
    _forge_mirror(session_dir, state)
    _truncate(_state_path(session_dir))
    damaged = _read(_state_path(session_dir))
    out = RD.cmd_next(session_dir)
    assert out["ok"] is False and out["reason"] == RD.SESSION_FROM_EARLIER_VERSION, out
    assert _read(_state_path(session_dir)) == damaged
    assert _repair_rows(session_dir) == []


# --- repair: only inside the lock, and after commit recovery -------------------------------------

def test_a_read_outside_the_lock_never_repairs(tmp_path):
    session_dir = _session(tmp_path)
    _truncate(_state_path(session_dir))
    damaged, mirror = _read(_state_path(session_dir)), _read(_mirror_path(session_dir))
    journal = _read(os.path.join(session_dir, RD.JOURNAL_FILE))
    ok, reason = RD.load_state(session_dir)
    assert ok is False and reason == REFUSAL
    assert _read(_state_path(session_dir)) == damaged
    assert _read(_mirror_path(session_dir)) == mirror
    assert _read(os.path.join(session_dir, RD.JOURNAL_FILE)) == journal


def _calls_with_ancestors(tree, name):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name:
            chain, cur = [], node
            while cur in parents:
                cur = parents[cur]
                chain.append(cur)
            yield node, chain


def test_repair_is_reached_only_through_commit_recovery_and_every_recovery_holds_the_lock():
    with open(DRIVER_SOURCE, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    repair_callers = {next(a.name for a in chain if isinstance(a, ast.FunctionDef))
                      for _, chain in _calls_with_ancestors(tree, "_repair_state_if_damaged")}
    assert repair_callers == {"_commit_recover_or_refuse"}
    recoveries = list(_calls_with_ancestors(tree, "_commit_recover_or_refuse"))
    assert len(recoveries) >= 8, len(recoveries)
    for call, chain in recoveries:
        held = [a for a in chain if isinstance(a, ast.With) and any(
            "session_lock" in ast.dump(item.context_expr) for item in a.items)]
        assert held, "recovery at line %d runs outside the session lock" % call.lineno


def test_a_sealed_commit_replays_before_repair_so_no_repair_is_needed(tmp_path):
    session_dir = _session(tmp_path)
    state = json.loads(_read(_state_path(session_dir)))
    state["_replayedMarker"] = "sealed-commit"
    new_bytes = RD._canonical(state).encode("utf-8")
    commit = round_commit.begin(session_dir, "test", stop_at="sealed")
    RD._stage_state(commit, session_dir, new_bytes)
    with pytest.raises(round_commit.StopPoint):
        commit.run()
    _truncate(_state_path(session_dir))                # the state is damaged while the commit waits
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True, out
    assert _read(_state_path(session_dir)) == new_bytes
    assert json.loads(_read(_mirror_path(session_dir)))["state"].encode("utf-8") == new_bytes
    assert _repair_rows(session_dir) == []


# --- the damaged session carries on to the same terminal -----------------------------------------

PANEL_FINDING = TI._blocking_finding("missing bounds guard", 2)
SECOND_FINDING = {"file": TI.NEW_SURFACE_FILE, "line": 2, "title": "unchecked return",
                  "severity": "Important", "detail": "unchecked return at %s:2" % TI.NEW_SURFACE_FILE,
                  "consequence": "a reviewer-found defect stays in the change"}
FIRST_KEY = "%s::missing bounds guard@L2" % TI.FIXED_FILE
SECOND_KEY = "%s::unchecked return@L2" % TI.NEW_SURFACE_FILE


@pytest.fixture
def second_round_script(monkeypatch, tmp_path):
    """Round 2's scoped finder raises a second finding on the new surface, and round 2's fixer lands a
    further change to that surface: two rounds each raise a finding and record a disposition."""
    second_head = TI.HEAD_DIFF.replace("+fresh\n", "+fresh-fixed\n")
    assert second_head != TI.HEAD_DIFF
    second_head_path = str(tmp_path / "head2.diff")
    with open(second_head_path, "w", encoding="utf-8") as fh:
        fh.write(second_head)
    original = TI._payload_for

    def scripted(session_dir, state, pend, seat, panel_findings, head_diff_path):
        if pend["phase"] == RD.P_SCOPED and state["round"] == 2:
            return {"findings": [dict(SECOND_FINDING)]}
        if pend["phase"] == RD.P_APPLY_FIXES and state["round"] == 2:
            head_diff_path = second_head_path
        return original(session_dir, state, pend, seat, panel_findings, head_diff_path)

    monkeypatch.setattr(TI, "_payload_for", scripted)


def _run_session(tmp_path, name, damage):
    """Drive a session through two rounds that each raise a finding, damage (or not) its state when
    round 3 opens, then carry on to the terminal with the same scripted steps."""
    session_dir, gitdir, head_path = TI._bootstrap(tmp_path, name=name)
    touched = False
    for _ in range(60):
        state = TI._state(session_dir)
        if state.get("terminal"):
            return session_dir
        if state["round"] >= 3 and not touched:
            touched = True
            ledger = {e["findingKey"]: e for e in state["dispositionLedger"]}
            assert ledger[FIRST_KEY]["disposition"] == "fixed"
            assert SECOND_KEY in ledger
            before = _read(_state_path(session_dir))
            if damage:
                _truncate(_state_path(session_dir))
            out = RD.cmd_next(session_dir)             # the orchestrator's next move: a locked command
            assert out["ok"] is True, out
            assert _read(_state_path(session_dir)) == before
            continue
        phase, out = TI._drive_one_phase(session_dir, gitdir, [PANEL_FINDING], head_path)
        assert out["ok"], (phase, out)
    raise AssertionError("did not reach a terminal")


def _account(session_dir):
    return rs.account_from_session(session_dir, TRS.extras(), TRS.Fake().readers())


def test_a_session_damaged_after_two_rounds_carries_on_to_the_terminal_its_twin_reaches(
        tmp_path, second_round_script):
    twin = _run_session(tmp_path, "twin", damage=False)
    hurt = _run_session(tmp_path, "hurt", damage=True)

    twin_state, hurt_state = TI._state(twin), TI._state(hurt)
    assert hurt_state["terminal"] == twin_state["terminal"] == "converged"
    assert hurt_state["round"] == twin_state["round"] >= 3

    twin_account, hurt_account = _account(twin), _account(hurt)
    outcomes = {f["findingKey"]: f["outcome"] for f in hurt_account["findings"]}
    assert outcomes == {FIRST_KEY: "fixed", SECOND_KEY: "fixed"}, outcomes
    assert hurt_account["findings"] == twin_account["findings"]
    assert hurt_account["rounds"] == twin_account["rounds"]

    def ledger_facts(state):
        return sorted((e["findingKey"], e["disposition"], e["dispositionRound"], e["raisedRound"])
                      for e in state["dispositionLedger"])
    assert ledger_facts(hurt_state) == ledger_facts(twin_state)

    rows = _repair_rows(hurt)
    assert len(rows) == 1 and rows[0]["outcome"] == "session-repaired", rows
    assert rows[0]["damaged"] == "not-json" and rows[0]["round"] == 3
    assert _repair_rows(twin) == []
