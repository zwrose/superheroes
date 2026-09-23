"""The verify submit resolves the head BEFORE it mutates anything.

A verify submit whose head cannot be resolved is refused at the submit chokepoint with the pending
step and `lastAccepted` intact, and the same artifact resubmits once the head resolves — there is
never a refusal record followed by an advance. Everything here drives the REAL driver and the REAL
adapters over a real session dir and a real git repository: `advance` folds through `cmd_submit`,
the one fold chokepoint, so the submit path under test is the path every orchestrator takes.
"""
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_certification  # noqa: E402
import round_driver  # noqa: E402
import round_records  # noqa: E402
import session_contract  # noqa: E402
import test_round_driver_integration as harness  # noqa: E402

_CODEX_SEAT_MAP = {
    "seats": {dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
              for dim in round_driver.DIMENSIONS}
}


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


def _real_session(tmp_path, monkeypatch, name="s"):
    """A session over a REAL git repository holding every path the fixture's diffs name.

    cwd moves to `tmp_path` so the driver's cwd fallback can never resolve the developer's
    checkout: the only head this session can resolve is the fixture repo's own. Returns
    (session_dir, gitdir, head_diff_path, repo_root, head)."""
    monkeypatch.chdir(str(tmp_path))
    repo = harness._fixture_repo(tmp_path, name)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    head = _git(repo, "rev-parse", "HEAD")
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir)
    with open(os.path.join(session_dir, round_records.META_FILE), "w", encoding="utf-8") as fh:
        json.dump({"headSha": head, "repoRoot": repo}, fh, sort_keys=True)
    gitdir = str(tmp_path / (name + "-gitdir"))
    os.makedirs(gitdir)
    head_diff_path = str(tmp_path / (name + "-head.diff"))
    with open(head_diff_path, "w", encoding="utf-8") as fh:
        fh.write(harness.HEAD_DIFF)
    out = round_driver.cmd_next(session_dir, harness._cfg(
        repoRoot=repo, vendors=["codex"], seatMap=_CODEX_SEAT_MAP,
        baseGuard=round_certification.BASE_GUARD_CHECKED))
    assert out["ok"], out
    return session_dir, gitdir, head_diff_path, repo, head


def _finding():
    return harness._blocking_finding("missing bounds guard", 2)


def _drive_to_verify(session_dir, gitdir, head_diff_path):
    folded = harness._drive_to_phase(session_dir, gitdir, [_finding()], head_diff_path,
                                     round_driver.P_VERIFY)
    assert round_driver.P_FIXER in folded, folded
    return folded


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, round_driver.STATE_FILE), "rb") as fh:
        return fh.read()


def _set_meta_repo_root(session_dir, repo_root):
    path = os.path.join(session_dir, round_records.META_FILE)
    with open(path, encoding="utf-8") as fh:
        meta = json.load(fh)
    meta["repoRoot"] = repo_root
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)


def _verify_round_record(session_dir):
    state = harness._state(session_dir)
    for key in sorted(state["rounds"], key=int, reverse=True):
        rec = state["rounds"][key]
        if isinstance(rec, dict) and "verifyResult" in rec:
            return rec
    raise AssertionError("no round recorded a verify result: %r" % state["rounds"])


def _never_records_a_refusal(state):
    for rec in (state.get("rounds") or {}).values():
        assert "verifiedHeadRefused" not in rec, rec


# --- the wiring: the P_VERIFY arm of `_fold` forwards the resolved head --------------------

def test_verify_submit_records_the_head_it_resolved(tmp_path, monkeypatch):
    """axis: the head the submit resolved reaches the verify fold through the real submit path.

    The P_VERIFY arm of `_fold` is the only wire between the submit's resolution and the fold's
    record. With the wire cut the fold records no `verifiedHead` and this reads None."""
    session_dir, gitdir, head_path, _repo, head = _real_session(tmp_path, monkeypatch)
    _drive_to_verify(session_dir, gitdir, head_path)
    phase, out = harness._drive_one_phase(session_dir, gitdir, [_finding()], head_path)
    assert phase == round_driver.P_VERIFY
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_VERIFY
    rec = _verify_round_record(session_dir)
    assert rec.get("verifyResult") == "pass"
    assert rec.get(session_contract.VERIFIED_HEAD_FIELD) == head
    _never_records_a_refusal(harness._state(session_dir))


# --- the invariant: resolve before mutate; refuse recoverably -----------------------------

def test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits(
        tmp_path, monkeypatch):
    """axis: a head-resolution failure refuses the submit with nothing mutated, and recovers.

    The repo root is pointed at a directory that is not a git repository, so `rev-parse HEAD`
    cannot resolve. The submit must refuse `verified-head-unresolved` BEFORE the fold: the state
    file is byte-identical (pending step and `lastAccepted` intact), no round record carries a
    verify result or a refusal record, and the step has not advanced. Restoring the repo root and
    re-running the same fold lands it with the resolved head."""
    session_dir, gitdir, head_path, repo, head = _real_session(tmp_path, monkeypatch)
    _drive_to_verify(session_dir, gitdir, head_path)
    before = harness._state(session_dir)
    assert before["pending"]["phase"] == round_driver.P_VERIFY
    # The fix batch is live at the verify step, so the resolver reads the repo — not a pin.
    assert round_driver._fix_batch_paths(before), before.get("fixBatch")
    not_a_repo = str(tmp_path / "not-a-repo")
    os.makedirs(not_a_repo)
    _set_meta_repo_root(session_dir, not_a_repo)
    state_before = _state_bytes(session_dir)

    phase, out = harness._drive_one_phase(session_dir, gitdir, [_finding()], head_path)

    assert phase == round_driver.P_VERIFY
    assert out["ok"] is False, out
    assert out["reason"] == "fold-refused", out
    assert out["detail"] == round_driver.VERIFIED_HEAD_UNRESOLVED, out
    assert _state_bytes(session_dir) == state_before
    after = harness._state(session_dir)
    assert after["pending"] == before["pending"]
    assert after.get("lastAccepted") == before.get("lastAccepted")
    assert after["step"] == round_driver.P_VERIFY
    pending_round = after["rounds"].get(str(after["pending"]["round"])) or {}
    assert "verifyResult" not in pending_round, pending_round
    _never_records_a_refusal(after)
    journal = round_driver.read_journal(session_dir)
    refused = [row for row in journal if row.get("cmd") == "submit"
               and row.get("outcome") == round_driver.VERIFIED_HEAD_UNRESOLVED]
    assert len(refused) == 1, journal
    assert refused[0]["phase"] == round_driver.P_VERIFY

    _set_meta_repo_root(session_dir, repo)
    out = round_driver.cmd_advance(session_dir, git=harness._fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_VERIFY
    rec = _verify_round_record(session_dir)
    assert rec.get("verifyResult") == "pass"
    assert rec.get(session_contract.VERIFIED_HEAD_FIELD) == head
    _never_records_a_refusal(harness._state(session_dir))


# --- the positive certification fixture, through the real loop ----------------------------

def test_real_loop_certifies_the_fixed_finding_at_the_verified_head(tmp_path, monkeypatch):
    """axis: a fixed finding certifies at the head the verify gate ran against — real loop only.

    The session reaches its terminal state through `advance` alone: panel, verifiers, synthesis,
    gap sweep, fixer, audits, the verify submit (which resolves the head), the scoped finder. No
    state is hand-written or restored; the fix fold and the verify fold land in different rounds
    exactly as the loop produces them, and certification binds the fixed receipt to that head."""
    session_dir, gitdir, head_path, _repo, head = _real_session(tmp_path, monkeypatch)
    folded = harness._drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, [_finding()], head_path, evidence_read="engaged")
    assert round_driver.P_VERIFY in folded, folded
    assert round_driver.P_FIXER in folded, folded
    state = harness._state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    fix_rounds = [k for k, r in state["rounds"].items() if r.get("fixFoldHead")]
    verify_rounds = [k for k, r in state["rounds"].items()
                     if r.get(session_contract.VERIFIED_HEAD_FIELD)]
    assert fix_rounds and verify_rounds and set(fix_rounds).isdisjoint(verify_rounds), state["rounds"]
    _never_records_a_refusal(state)

    receipt, refusal = round_certification.certify(session_dir)

    assert refusal is None, refusal
    fixed = [f for f in receipt.get("findings") or [] if f.get("disposition") == "fixed"]
    assert len(fixed) == 1, receipt.get("findings")
    proof = fixed[0]["dispositionReceipt"]
    assert proof["headSha"] == head
    assert proof["verifyResult"] == "pass"
