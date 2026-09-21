"""#1272 layer 2h: verify submit resolves head before fold — refusal detectors."""
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

import round_records as RR
from round_certification_fixtures import write_session

FIX_PATH = "src/guard.py"
_FIX_BYTES = b"fix still present\n"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RC = _load("round_certification")


def _init_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    path = repo / FIX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_FIX_BYTES)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return str(repo), proc.stdout.strip()


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _journal_line_count(session_dir):
    path = os.path.join(session_dir, RD.JOURNAL_FILE)
    if not os.path.isfile(path):
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _session_at_pending_verify(tmp_path, repo_root, *, advance_used=False, name="verify",
                               post_audits_verify=False):
    state = RD.new_state({"fixerVendor": "claude", "baseGuard": RC.BASE_GUARD_CHECKED})
    state["round"] = 1
    state["step"] = RD.P_VERIFY
    state["pending"] = {
        "action": RD.P_VERIFY,
        "round": 1,
        "phase": RD.P_VERIFY,
        "attempt": 0,
        "payload": {"command": "none"},
    }
    if post_audits_verify:
        state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
        state["auditRounds"] = []
        state["_auditOutcome"] = {"notDischarged": [], "discharged": []}
        state["findings"] = []
        state["_changedSubjects"] = []
        state["_changedSubjectsSincePanel"] = []
        state["surfacedSinceLastPanel"] = []
        state["fullPanelRan"] = True
    if advance_used:
        state["_advanceUsed"] = True
    return write_session(
        tmp_path,
        name=name,
        state=state,
        journal_lines=[],
        meta={"repoRoot": repo_root},
        faithful_session=False,
    )


def _echo_and_submit_pass(session_dir):
    echo = RD.cmd_next(session_dir)
    assert echo["ok"], echo
    answer = RD.cmd_submit(
        session_dir,
        echo["phase"],
        echo["attempt"],
        echo["expectedStateHash"],
        {"result": "pass"},
    )
    return echo, answer


def _fake_git(gitdir, head="a" * 40):
    def run(cwd, *args):
        if args[:2] == ("rev-parse", "--absolute-git-dir"):
            return gitdir
        if args == ("rev-parse", "HEAD"):
            return head
        if args[:3] == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "feature/x"
        if args[0] == "rev-parse" and "--verify" in args:
            return "b" * 40
        if args[:2] == ("remote", "get-url"):
            return "github.com/o/r"
        return None
    return run


def _gitdir(tmp_path, name="_gitdir"):
    path = str(tmp_path / name)
    os.makedirs(path, exist_ok=True)
    return path


def _advance(session_dir, tmp_path, **kw):
    return RD.cmd_advance(session_dir, git=_fake_git(_gitdir(tmp_path)), **kw)


def _pending_at_run_verify(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state["step"] = RD.P_VERIFY
    state["_advanceUsed"] = True
    state["pending"] = {
        "action": RD.P_VERIFY,
        "round": state["round"],
        "phase": RD.P_VERIFY,
        "attempt": 0,
        "payload": {"command": "none"},
    }
    RD.save_state(session_dir, state)


def _write_verify_payload(session_dir, payload, attempt=None):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    pend = state["pending"]
    attempt = pend["attempt"] if attempt is None else attempt
    skey = RR.storage_key("verify")
    path = RR.bare_payload_path(session_dir, pend["round"], pend["phase"], skey, attempt)
    RR.atomic_write_json(path, payload)
    return path


def _state_verified_head_refused_anywhere(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    for rec in (state.get("rounds") or {}).values():
        if isinstance(rec, dict) and rec.get("verifiedHeadRefused"):
            return True
    return False


def test_verify_submit_forwards_the_resolved_head_through_the_fold(tmp_path):
    """axis: verify submit forwards the resolved head through the verify fold."""
    repo_root, head_sha = _init_git_repo(tmp_path)
    session_dir = _session_at_pending_verify(tmp_path, repo_root)
    echo, answer = _echo_and_submit_pass(session_dir)
    assert answer["ok"] is True
    assert answer.get("foldLanded") is True
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    SC = _load("session_contract")
    rec = state["rounds"].get(str(echo["round"])) or {}
    assert rec.get(SC.VERIFIED_HEAD_FIELD) == head_sha
    assert "verifiedHeadRefused" not in rec


def test_verify_submit_refuses_an_unresolvable_head_and_accepts_the_same_artifact_after(tmp_path):
    """axis: unresolvable head refuses with byte-identical state; same artifact folds after repair."""
    non_git = tmp_path / "not-git"
    non_git.mkdir()
    session_dir = _session_at_pending_verify(tmp_path, str(non_git))
    echo1 = RD.cmd_next(session_dir)
    assert echo1["ok"], echo1
    before_state = _state_bytes(session_dir)
    before_journal = _journal_line_count(session_dir)
    answer1 = RD.cmd_submit(
        session_dir,
        echo1["phase"],
        echo1["attempt"],
        echo1["expectedStateHash"],
        {"result": "pass"},
    )
    assert answer1["ok"] is False
    assert answer1["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert "foldLanded" not in answer1
    assert _state_bytes(session_dir) == before_state
    assert _journal_line_count(session_dir) == before_journal + 1
    journal = RD.read_journal(session_dir)
    assert journal[-1]["outcome"] == "verified-head-unresolved"
    assert not _state_verified_head_refused_anywhere(session_dir)

    repair = tmp_path / "repair"
    repair.mkdir()
    repo_root, head_sha = _init_git_repo(repair)
    meta_path = os.path.join(session_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    meta["repoRoot"] = repo_root
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
    echo2 = RD.cmd_next(session_dir)
    assert echo2["ok"], echo2
    assert echo2["phase"] == echo1["phase"]
    assert echo2["attempt"] == echo1["attempt"]
    assert echo2["expectedStateHash"] == echo1["expectedStateHash"]
    answer2 = RD.cmd_submit(
        session_dir,
        echo2["phase"],
        echo2["attempt"],
        echo2["expectedStateHash"],
        {"result": "pass"},
    )
    assert answer2["ok"] is True
    assert "duplicate" not in answer2
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    assert state["lastAccepted"]["attempt"] == echo2["attempt"]
    SC = _load("session_contract")
    rec = state["rounds"].get(str(echo2["round"])) or {}
    assert rec.get(SC.VERIFIED_HEAD_FIELD) == head_sha


def test_verify_submit_refuses_when_persisting_the_resolved_head_raises(tmp_path, monkeypatch):
    """axis: OSError while persisting the resolved head refuses with byte-identical state."""
    repo_root, _head_sha = _init_git_repo(tmp_path)
    session_dir = _session_at_pending_verify(tmp_path, repo_root)

    def _raise_disk_full(session_dir_arg, state, head):
        raise OSError("disk full")

    monkeypatch.setattr(RD, "_persist_fix_fold_head_sha", _raise_disk_full)
    before_state = _state_bytes(session_dir)
    _, answer = _echo_and_submit_pass(session_dir)
    assert answer["ok"] is False
    assert answer["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert _state_bytes(session_dir) == before_state


def test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries(tmp_path):
    """axis: advance surfaces verified-head-unresolved as fold-refused; repair then folds."""
    non_git = tmp_path / "not-git"
    non_git.mkdir()
    session_dir = _session_at_pending_verify(
        tmp_path, str(non_git), advance_used=True, post_audits_verify=True,
    )
    _pending_at_run_verify(session_dir)
    _write_verify_payload(session_dir, {"result": "pass"})
    before_state = _state_bytes(session_dir)
    out1 = _advance(session_dir, tmp_path)
    assert out1["ok"] is False
    assert out1["reason"] == "fold-refused"
    assert out1["detail"] == "verified-head-unresolved"
    assert _state_bytes(session_dir) == before_state

    repair = tmp_path / "repair"
    repair.mkdir()
    repo_root, head_sha = _init_git_repo(repair)
    meta_path = os.path.join(session_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    meta["repoRoot"] = repo_root
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
    _write_verify_payload(session_dir, {"result": "pass"})
    out2 = _advance(session_dir, tmp_path)
    assert out2["ok"] is True, out2
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    SC = _load("session_contract")
    rec = state["rounds"].get("1") or {}
    assert rec.get(SC.VERIFIED_HEAD_FIELD) == head_sha
