"""#1388: verify submit refuses when head is unresolvable before any fold mutation."""
import copy
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


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD = ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,3 @@\n-old\n+new\n+more\n+fixed\n")
_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
_GOOD_VERIFY = {"result": "pass"}
_VERIFY_WITH_PROV = {"result": "pass", "provenance": {"adapterTrust": "runner-recorded"}}


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _init_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    for key, val in (("user.email", "t@example.com"), ("user.name", "test")):
        subprocess.run(
            ["git", "config", key, val],
            cwd=repo,
            check=True,
            capture_output=True,
        )
    path = repo / "f.py"
    path.write_text("content\n", encoding="utf-8")
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


def _merge_meta(session_dir, **fields):
    meta_path = os.path.join(session_dir, SC.META_FILE)
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            meta = loaded
    meta.update(fields)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
        fh.write("\n")


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _responder(**over):
    verify = over.pop("verify", "pass")

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": list(_A_FINDING)}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            out = []
            for c in payload.get("clusters", []):
                for i in c.get("ids", []):
                    out.append({"id": i, "verdict": "CONFIRMED", "reason": "checked", "evidence": "ran"})
            return {"verdicts": out}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
                                 "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": verify}
        return {}

    return respond


def _drive_to_phase(session_dir, cfg, respond, target_phase, max_steps=80):
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n.get("phase") == target_phase:
            return n
        assert n["action"] != RD.P_TERMINAL, "reached terminal before %s" % target_phase
        art = respond(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("never reached %s within %d steps" % (target_phase, max_steps))


def _refresh_verify_pending(session_dir):
    n = RD.cmd_next(session_dir)
    assert n["ok"], n
    assert n.get("phase") == RD.P_VERIFY
    return n


def _clear_persisted_head(session_dir):
    """Drop fixFoldHead so verify submit must re-resolve through repo discovery."""
    ok, state = RD.load_state(session_dir)
    assert ok
    cfg = state.get("config") or {}
    if isinstance(cfg, dict):
        cfg.pop(RD.FIX_FOLD_HEAD_KEY, None)
        state["config"] = cfg
    RD.save_state(session_dir, state)
    meta_path = os.path.join(session_dir, SC.META_FILE)
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        if isinstance(meta, dict):
            meta.pop(RD.FIX_FOLD_HEAD_KEY, None)
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, sort_keys=True)
                fh.write("\n")


def _open_session_at_verify(tmp_path, repo_root):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    cfg = _cfg()
    n = _drive_to_phase(session_dir, cfg, _responder(), RD.P_VERIFY)
    _merge_meta(session_dir, repoRoot=repo_root)
    return session_dir, n


def test_t1_verify_submit_forwards_resolved_head(tmp_path):
    repo, expected_head = _init_git_repo(tmp_path)
    session_dir, n = _open_session_at_verify(tmp_path, repo)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], _GOOD_VERIFY)
    assert out["ok"] is True, out
    ok, state = RD.load_state(session_dir)
    assert ok
    rec = state["rounds"].get(str(n["round"])) or {}
    assert rec.get(SC.VERIFIED_HEAD_FIELD) == expected_head


def test_t2_refusal_leaves_state_intact(tmp_path):
    bad_root = str(tmp_path / "missing-repo")
    session_dir, n = _open_session_at_verify(tmp_path, bad_root)
    before = _state_bytes(session_dir)
    ok, state_before = RD.load_state(session_dir)
    assert ok
    pending_before = copy.deepcopy(state_before.get("pending"))
    last_before = copy.deepcopy(state_before.get("lastAccepted"))
    artifact = copy.deepcopy(_VERIFY_WITH_PROV)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert out["ok"] is False
    assert out["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert isinstance(out.get("detail"), str) and out["detail"]
    assert _state_bytes(session_dir) == before
    ok, state_after = RD.load_state(session_dir)
    assert ok
    assert state_after.get("pending") == pending_before
    assert state_after.get("lastAccepted") == last_before
    assert artifact == _VERIFY_WITH_PROV
    journal = RD.read_journal(session_dir)
    assert journal[-1]["outcome"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE


def test_t3_resubmit_after_refusal_accepts_same_artifact(tmp_path):
    repo, expected_head = _init_git_repo(tmp_path)
    bad_root = str(tmp_path / "missing-repo")
    session_dir, n = _open_session_at_verify(tmp_path, bad_root)
    artifact = copy.deepcopy(_VERIFY_WITH_PROV)
    refused = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert refused["ok"] is False
    _merge_meta(session_dir, repoRoot=repo)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert out["ok"] is True, out
    ok, state = RD.load_state(session_dir)
    assert ok
    rec = state["rounds"].get(str(n["round"])) or {}
    assert rec.get(SC.VERIFIED_HEAD_FIELD) == expected_head


def test_t4_repo_discovery_refusal(tmp_path, monkeypatch):
    repo, _ = _init_git_repo(tmp_path)
    session_dir, n = _open_session_at_verify(tmp_path, repo)
    _clear_persisted_head(session_dir)
    meta_path = os.path.join(session_dir, SC.META_FILE)
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    meta.pop("repoRoot", None)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
        fh.write("\n")
    n = _refresh_verify_pending(session_dir)

    def _raise_unavailable(_cwd):
        raise RD.store_core.RepoRootUnavailable("injected for test")

    monkeypatch.setattr(RD.store_core, "repo_root", _raise_unavailable)
    before = _state_bytes(session_dir)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], _GOOD_VERIFY)
    assert out["ok"] is False
    assert out["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert _state_bytes(session_dir) == before


def test_t5_meta_persistence_oserror_refusal(tmp_path, monkeypatch):
    repo, _ = _init_git_repo(tmp_path)
    session_dir, n = _open_session_at_verify(tmp_path, repo)
    _clear_persisted_head(session_dir)
    n = _refresh_verify_pending(session_dir)
    before = _state_bytes(session_dir)
    real_atomic = RD.round_commit.atomic_write_bytes

    def _fail_on_meta(path, data):
        if path.endswith(SC.META_FILE):
            raise OSError("injected meta write failure")
        return real_atomic(path, data)

    monkeypatch.setattr(RD.round_commit, "atomic_write_bytes", _fail_on_meta)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], _GOOD_VERIFY)
    assert out["ok"] is False
    assert out["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert _state_bytes(session_dir) == before


def test_t6_fail_result_also_refuses_with_unresolvable_head(tmp_path):
    bad_root = str(tmp_path / "missing-repo")
    session_dir, n = _open_session_at_verify(tmp_path, bad_root)
    before = _state_bytes(session_dir)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                        {"result": "fail"})
    assert out["ok"] is False
    assert out["reason"] == RD.VERIFIED_HEAD_UNRESOLVED_CAUSE
    assert _state_bytes(session_dir) == before


def test_t7_in_process_fold_records_no_verified_head():
    state = RD.new_state({"fixerVendor": "claude"})
    state["round"] = 1
    RD._fold(state, state["config"], RD.P_VERIFY, {"result": "pass"}, session_dir=None)
    rec = state["rounds"].get("1") or {}
    assert SC.VERIFIED_HEAD_FIELD not in rec
    assert "verifiedHeadRefused" not in rec
    assert state.get("step") != RD.P_TERMINAL
