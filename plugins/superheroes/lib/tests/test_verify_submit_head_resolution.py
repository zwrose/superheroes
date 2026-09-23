"""The verify submit resolves the head before it mutates anything.

A verify result that would ADVANCE with no resolvable head is refused at the submit chokepoint:
the state file is untouched, the pending step and `lastAccepted` survive, and the same artifact
resubmits once the head resolves. A halting result still folds and halts. Every session here is
driven to its pending verify step through the real `next`/`submit` loop.
"""
import importlib.util
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_TRD_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver", os.path.join(_HERE, "test_round_driver.py"))
_TRD = importlib.util.module_from_spec(_TRD_SPEC)
_TRD_SPEC.loader.exec_module(_TRD)
RD = _TRD.RD

_META = "meta.json"


def _git_repo(path):
    os.makedirs(path)
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "test"]):
        subprocess.run(["git", "-C", path] + args, check=True, capture_output=True)
    with open(os.path.join(path, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", path, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", path, "commit", "-q", "-m", "init"], check=True,
                   capture_output=True)
    return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def _point_meta_at(session_dir, repo_root):
    path = os.path.join(session_dir, _META)
    meta = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            meta = json.load(fh)
    meta["repoRoot"] = repo_root
    meta.pop(RD.FIX_FOLD_HEAD_KEY, None)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)


def _pending_verify(tmp_path, repo_root):
    """A session at its pending verify step whose head must be resolved from `repo_root`: meta
    points there and the fix-fold pin is cleared from meta and config, so no persisted value
    answers for it. Returns (session_dir, the `next` answer carrying the current state hash)."""
    session_dir, _ = _TRD._at(tmp_path / "session", RD.P_VERIFY)
    _point_meta_at(session_dir, repo_root)
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["config"].pop(RD.FIX_FOLD_HEAD_KEY, None)
    RD.save_state(session_dir, state)
    nxt = RD.cmd_next(session_dir)
    assert nxt["ok"] and nxt["phase"] == RD.P_VERIFY, nxt
    return session_dir, nxt


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _submit(session_dir, nxt, artifact):
    return RD.cmd_submit(session_dir, nxt["phase"], nxt["attempt"], nxt["expectedStateHash"],
                         artifact)


def _verify_record(session_dir, nxt):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state, (state.get("rounds") or {}).get(str(nxt["round"])) or {}


def test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits(tmp_path):
    """axis: the invariant — refusal BEFORE any mutation, then a clean resubmit of the same
    artifact on the same phase/attempt/state-hash."""
    not_a_repo = str(tmp_path / "not-a-repo")
    os.makedirs(not_a_repo)
    session_dir, nxt = _pending_verify(tmp_path, not_a_repo)
    before = _state_bytes(session_dir)
    ok, state_before = RD.load_state(session_dir)
    assert ok, state_before
    artifact = {"result": "pass"}

    out = _submit(session_dir, nxt, artifact)

    assert out["ok"] is False, out
    assert out["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE == "verified-head-unresolved"
    assert "rev-parse" in out["detail"], out
    assert _state_bytes(session_dir) == before
    state, rec = _verify_record(session_dir, nxt)
    assert state["pending"] == state_before["pending"]
    assert state.get("lastAccepted") == state_before.get("lastAccepted")
    assert "verifyResult" not in rec and "verifiedHeadRefused" not in rec
    journal = RD.read_journal(session_dir)
    assert journal[-1]["outcome"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE

    head = _git_repo(str(tmp_path / "repo"))
    _point_meta_at(session_dir, str(tmp_path / "repo"))
    again = _submit(session_dir, nxt, artifact)

    assert again["ok"] is True, again
    _, rec = _verify_record(session_dir, nxt)
    assert rec.get("verifyResult") == "pass"
    assert rec.get(RD.session_contract.VERIFIED_HEAD_FIELD) == head


def test_verify_submit_records_the_resolved_head_through_cmd_submit(tmp_path):
    """axis: the `P_VERIFY` arm of `_fold` forwards the head `cmd_submit` resolved to
    `_fold_verify` — the verify round records exactly that head."""
    head = _git_repo(str(tmp_path / "repo"))
    session_dir, nxt = _pending_verify(tmp_path, str(tmp_path / "repo"))

    out = _submit(session_dir, nxt, {"result": "pass"})

    assert out["ok"] is True, out
    _, rec = _verify_record(session_dir, nxt)
    assert rec.get("verifyResult") == "pass"
    assert rec.get(RD.session_contract.VERIFIED_HEAD_FIELD) == head
    assert RD.session_contract.verify_result_for_head(RD.load_state(session_dir)[1], head) == "pass"


def test_halting_verify_result_with_unresolvable_head_still_halts(tmp_path):
    """axis: the refusal is scoped to results that would ADVANCE — an honest `fail` with no
    resolvable head still folds and halts, and records no head."""
    not_a_repo = str(tmp_path / "not-a-repo")
    os.makedirs(not_a_repo)
    session_dir, nxt = _pending_verify(tmp_path, not_a_repo)

    out = _submit(session_dir, nxt, {"result": "fail"})

    assert out["ok"] is True, out
    state, rec = _verify_record(session_dir, nxt)
    assert state["terminal"] == "halted"
    assert rec.get("verifyResult") == "fail"
    assert RD.session_contract.VERIFIED_HEAD_FIELD not in rec


def test_resolver_raise_maps_to_the_structured_refusal(tmp_path, monkeypatch):
    """axis: a resolver that RAISES (the fix-fold pin write) refuses like any resolution failure —
    structured answer, untouched state — and the same artifact resubmits once the write works."""
    head = _git_repo(str(tmp_path / "repo"))
    session_dir, nxt = _pending_verify(tmp_path, str(tmp_path / "repo"))
    before = _state_bytes(session_dir)
    real_write = RD.round_commit.atomic_write_bytes

    def failing_meta_write(path, data):
        if os.path.basename(path) == _META:
            raise OSError("injected meta write failure")
        return real_write(path, data)

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", failing_meta_write)
    out = _submit(session_dir, nxt, {"result": "pass"})

    assert out["ok"] is False, out
    assert out["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert "OSError: injected meta write failure" in out["detail"], out
    assert _state_bytes(session_dir) == before

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", real_write)
    again = _submit(session_dir, nxt, {"result": "pass"})

    assert again["ok"] is True, again
    _, rec = _verify_record(session_dir, nxt)
    assert rec.get(RD.session_contract.VERIFIED_HEAD_FIELD) == head
