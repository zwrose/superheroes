#!/usr/bin/env python3
"""#1272 layer 2d — round economy: fix-batch cap, post-fix verify gate, scoped verify budget."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases  # noqa: E402
import round_records  # noqa: E402
import session_contract as SC  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

from test_round_driver import (  # noqa: E402
    DIFF, HEAD, HEAD_NEW_SURFACE, _cfg, _drive_cli, _drive_to_phase, _responder,
)

_bootstrap = _TDI._bootstrap
_land = _TDI._land
_write_dispatch_manifest = _TDI._write_dispatch_manifest
_slots_of = _TDI._slots_of
_payload_for = _TDI._payload_for
_auditor_vendor_for = _TDI._auditor_vendor_for
_blocking_finding = _TDI._blocking_finding
_state = _TDI._state
_fake_git = _TDI._fake_git
REVIEWED_DIFF = _TDI.REVIEWED_DIFF
HEAD_DIFF = _TDI.HEAD_DIFF
FIXED_FILE = _TDI.FIXED_FILE


def _drive_integration_to_audits(tmp_path, panel_findings=None, **cfg_over):
    """Drive the durable-record path to round-2 ``dispatch-audits`` pending."""
    findings = panel_findings if panel_findings is not None else [_blocking_finding("bug", 2)]
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path, verifyCommand="pytest -q", **cfg_over)
    _TDI._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_AUDITS)
    state = _state(session_dir)
    assert state["round"] == 2, state
    pend = state["pending"]
    assert pend["phase"] == RD.P_AUDITS, pend
    return session_dir, gitdir, head_path, state, pend


def _round_record_keys(state, rnd):
    rec = dict(state.get("rounds", {}).get(str(rnd), {}))
    for key in ("ts",):
        rec.pop(key, None)
    return rec


def _advance_audits(session_dir, gitdir, head_path, state, pend, findings):
    roster, reason = round_adapters.roster_for(RD.P_AUDITS, state, state.get("config") or {})
    assert reason is None, reason
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        payload = _payload_for(session_dir, state, pend, seat, findings, head_path)
        _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        assert round_driver_record(session_dir, seat, occurrence)["ok"] is True
    return RD.cmd_advance(session_dir, git=_fake_git(gitdir))


def round_driver_record(session_dir, seat, occurrence=0):
    if occurrence:
        return RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    return RD.cmd_record_result(session_dir, seat)


def _write_verify_landing(landing_path):
    os.makedirs(os.path.dirname(landing_path), exist_ok=True)
    round_records.atomic_write_json(landing_path, {"result": "pass"})


def _assert_verify_payload(verify, session_dir):
    assert verify["phase"] == RD.P_VERIFY
    assert verify["command"] == "pytest -q"
    assert verify["round"] == 2
    assert isinstance(verify["attempt"], int)
    assert os.path.isabs(verify["landingPath"])
    assert verify["landingPath"].startswith(session_dir)


def _finish_post_audits_verify(session_dir, gitdir, head_path, state, pend, findings,
                               verify_first):
    verify = pend["payload"]["verify"]
    _assert_verify_payload(verify, session_dir)
    if verify_first:
        _write_verify_landing(verify["landingPath"])
        out = _advance_audits(session_dir, gitdir, head_path, state, pend, findings)
    else:
        out = _advance_audits(session_dir, gitdir, head_path, state, pend, findings)
        _write_verify_landing(verify["landingPath"])
    assert out["ok"] is True, out
    out2 = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out2["ok"] is True, out2
    assert out2["folded"]["phase"] == RD.P_VERIFY
    final = _state(session_dir)
    assert final["rounds"]["2"]["verifyResult"] == "pass"
    return final


# axis: durable-record path — verify lands before audits, then both fold in order
def test_t1a_verify_before_audits_lands_first(tmp_path):
    session_dir, gitdir, head_path, state, pend = _drive_integration_to_audits(tmp_path)
    findings = [_blocking_finding("bug", 2)]
    _finish_post_audits_verify(session_dir, gitdir, head_path, state, pend, findings, True)


# axis: durable-record path — audits land before verify, same terminal state as T1a
def test_t1b_audits_before_verify_lands_first(tmp_path):
    sa, ga, ha, sta, pa = _drive_integration_to_audits(tmp_path / "a")
    sb, gb, hb, stb, pb = _drive_integration_to_audits(tmp_path / "b")
    findings = [_blocking_finding("bug", 2)]
    fa = _finish_post_audits_verify(sa, ga, ha, sta, pa, findings, True)
    fb = _finish_post_audits_verify(sb, gb, hb, stb, pb, findings, False)
    for key in ("step", "round"):
        assert fa[key] == fb[key]
    assert _round_record_keys(fa, 2) == _round_record_keys(fb, 2)


# axis: hand-submit path — audits then run-verify then scoped finder
def test_t1c_hand_submit_audits_then_verify(tmp_path):
    d = str(tmp_path)
    cfg = _cfg(verifyCommand="pytest -q")
    n = _drive_to_phase(d, cfg, _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE),
                        RD.P_AUDITS)
    assert n["round"] == 2
    assert "verify" in n["payload"]
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                    "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                   for t in n["payload"]["targets"]],
                       "collectionManifest": {t["id"]: t.get("auditorVendor")
                                              for t in n["payload"]["targets"]}})
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["ok"] and n2["phase"] == RD.P_VERIFY
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"], {"result": "pass"})
    assert s2["ok"], s2
    n3 = RD.cmd_next(d)
    assert n3["ok"] and n3["phase"] in (RD.P_SCOPED, RD.P_VERIFIERS, RD.P_TERMINAL)


_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]


# axis: verify fail after audits halts — no scoped finder or panel afterward
def test_t2_verify_fail_after_audits_halts(tmp_path):
    d = str(tmp_path)
    cfg = _cfg(verifyCommand="pytest -q")
    n = _drive_to_phase(d, cfg, _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE),
                        RD.P_AUDITS)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                    "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                   for t in n["payload"]["targets"]],
                       "collectionManifest": {t["id"]: t.get("auditorVendor")
                                              for t in n["payload"]["targets"]}})
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_VERIFY
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"], {"result": "fail"})
    assert s2["ok"], s2
    n3 = RD.cmd_next(d)
    assert n3["action"] == RD.P_TERMINAL
    assert n3["payload"]["verdict"] == "halted"
    assert n3["payload"]["certification"]["shape"] is None


# axis: ceiling round with no prior gate runs verify before round-ceiling park
def test_t3_ceiling_gate_runs_then_parks(tmp_path):
    d = str(tmp_path)
    cfg = _cfg(maxRoundsAbsolute=1, maxRounds=1, verifyCommand="pytest -q")
    respond = _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE)
    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["round"] == 1
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    ok, state = RD.load_state(d)
    assert state["rounds"]["1"].get("verifyResult") is None
    n2 = RD.cmd_next(d)
    assert n2["ok"] and n2["phase"] == RD.P_VERIFY, n2
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"], {"result": "pass"})
    assert s2["ok"], s2
    n3 = RD.cmd_next(d)
    assert n3["action"] == RD.P_TERMINAL
    assert n3["payload"]["verdict"] == "halted"
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"]["1"]["verifyResult"] == "pass"
    assert any(dec["kind"] == "round-ceiling" for dec in state["decisions"])


def _git_rev_parse(repo):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _init_ceiling_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                   check=True, capture_output=True)
    (repo / "f.py").write_text("old\n", encoding="utf-8")
    (repo / "newsurf.py").write_text("ns\nns2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=repo, check=True, capture_output=True)
    return str(repo), _git_rev_parse(repo)


def _commit_in_repo(repo, message):
    marker = os.path.join(repo, ".ceiling-head-marker")
    with open(marker, "a", encoding="utf-8") as fh:
        fh.write(message + "\n")
    subprocess.run(["git", "add", marker], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", message],
        cwd=repo, check=True, capture_output=True)
    return _git_rev_parse(repo)


def _bootstrap_session_with_repo(tmp_path, repo, head_sha):
    d = str(tmp_path / "session")
    os.makedirs(d, exist_ok=True)
    meta_path = os.path.join(d, round_records.META_FILE)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump({"headSha": head_sha, "repoRoot": repo}, fh, sort_keys=True)
        fh.write("\n")
    return d


def _drive_ceiling_round_two_fixer(tmp_path, cfg, respond, repo, init_head, *, move_head=True):
    d = _bootstrap_session_with_repo(tmp_path, repo, init_head)
    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["round"] == 1
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["round"] == 2
    ok, state = RD.load_state(d)
    assert ok
    head_a = state["rounds"]["2"].get(SC.VERIFIED_HEAD_FIELD)
    assert head_a
    head_b = head_a
    if move_head:
        head_b = _commit_in_repo(cfg["repoRoot"], "ceiling post-fix head")
        assert head_b != head_a
    return d, n, head_a, head_b


# axis: ceiling round reuses the gate when post-fix head matches a prior pass
def test_t3_ceiling_gate_reused_when_prior_verify_on_same_head(tmp_path):
    repo, init_head = _init_ceiling_git_repo(tmp_path)
    scoped_b = [{"title": "delta-b", "severity": "Important", "file": "newsurf.py", "line": 1}]
    cfg = _cfg(maxRoundsAbsolute=2, maxRounds=2, verifyCommand="pytest -q", repoRoot=repo)
    respond = _responder(round1_findings=_A_FINDING, scoped=scoped_b, head=HEAD_NEW_SURFACE)
    d, n, head_a, _head_b = _drive_ceiling_round_two_fixer(
        tmp_path, cfg, respond, repo, init_head, move_head=False)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n3 = RD.cmd_next(d)
    assert n3["action"] == RD.P_TERMINAL, n3
    assert n3["payload"]["verdict"] == "halted"
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"]["2"]["verifyResult"] == "pass"
    assert state["rounds"]["2"]["ceilingGateReused"] == head_a
    assert state["rounds"]["2"][SC.VERIFIED_HEAD_FIELD] == head_a
    assert any(dec["kind"] == "round-ceiling" for dec in state["decisions"])
    verify_nexts = [e for e in RD.read_journal(d)
                    if e.get("cmd") == "next" and e.get("phase") == RD.P_VERIFY
                    and e.get("round") == 2]
    assert len(verify_nexts) == 1


# axis: ceiling round runs verify on post-fix head even when concurrent gate already ran
def test_t3_ceiling_gate_runs_on_post_fix_head_after_prior_verify(tmp_path):
    repo, init_head = _init_ceiling_git_repo(tmp_path)
    scoped_b = [{"title": "delta-b", "severity": "Important", "file": "newsurf.py", "line": 1}]
    cfg = _cfg(maxRoundsAbsolute=2, maxRounds=2, verifyCommand="pytest -q", repoRoot=repo)
    respond = _responder(round1_findings=_A_FINDING, scoped=scoped_b, head=HEAD_NEW_SURFACE)
    d, n, head_a, head_b = _drive_ceiling_round_two_fixer(
        tmp_path, cfg, respond, repo, init_head)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n3 = RD.cmd_next(d)
    assert n3["ok"] and n3["phase"] == RD.P_VERIFY, n3
    s2 = RD.cmd_submit(d, n3["phase"], n3["attempt"], n3["expectedStateHash"], {"result": "pass"})
    assert s2["ok"], s2
    n4 = RD.cmd_next(d)
    assert n4["action"] == RD.P_TERMINAL
    assert n4["payload"]["verdict"] == "halted"
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"]["2"]["verifyResult"] == "pass"
    _skip_key = "".join(("ceiling", "Gate", "Skipped"))
    assert _skip_key not in state["rounds"]["2"]
    assert state["rounds"]["2"][SC.VERIFIED_HEAD_FIELD] == head_b
    assert state["rounds"]["2"][SC.VERIFIED_HEAD_FIELD] != head_a
    assert any(dec["kind"] == "round-ceiling" for dec in state["decisions"])
    verify_nexts = [e for e in RD.read_journal(d)
                    if e.get("cmd") == "next" and e.get("phase") == RD.P_VERIFY
                    and e.get("round") == 2]
    assert len(verify_nexts) == 2


# axis: unresolvable post-fix head at the ceiling still runs the gate
def test_t3_ceiling_gate_runs_when_post_fix_head_unresolvable(tmp_path):
    repo, init_head = _init_ceiling_git_repo(tmp_path)
    scoped_b = [{"title": "delta-b", "severity": "Important", "file": "newsurf.py", "line": 1}]
    cfg = _cfg(maxRoundsAbsolute=2, maxRounds=2, verifyCommand="pytest -q", repoRoot=repo)
    respond = _responder(round1_findings=_A_FINDING, scoped=scoped_b, head=HEAD_NEW_SURFACE)
    d, n, head_a, _head_b = _drive_ceiling_round_two_fixer(
        tmp_path, cfg, respond, repo, init_head)
    shutil.rmtree(repo)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n3 = RD.cmd_next(d)
    assert n3["ok"] and n3["phase"] == RD.P_VERIFY, n3
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"]["2"].get("fixFoldHeadRefused")
    assert "ceilingGateReused" not in state["rounds"]["2"]
    assert state["rounds"]["2"][SC.VERIFIED_HEAD_FIELD] == head_a


def test_t3b_ceiling_gate_reuse_requires_pass():
    head = "abc" * 13 + "a"
    state = {"round": 2,
             "config": {"maxRoundsAbsolute": 2, "maxRounds": 2, RD.FIX_FOLD_HEAD_KEY: head},
             "rounds": {"2": {"verifyResult": "fail", SC.VERIFIED_HEAD_FIELD: head}}}
    assert RD._try_reuse_ceiling_verify_gate(state, state["config"], None) is False
    assert "ceilingGateReused" not in state["rounds"]["2"]


def test_t3b_ceiling_gate_reuse_taken_on_pass():
    head = "abc" * 13 + "a"
    state = {"round": 2, "decisions": [],
             "config": {"maxRoundsAbsolute": 2, "maxRounds": 2, RD.FIX_FOLD_HEAD_KEY: head},
             "rounds": {"2": {"verifyResult": "pass", SC.VERIFIED_HEAD_FIELD: head}}}
    assert RD._try_reuse_ceiling_verify_gate(state, state["config"], None) is True
    assert state["rounds"]["2"]["ceilingGateReused"] == head


# axis: ceiling gate fail on post-fix head halts — never a clean park
def test_t3_ceiling_gate_fail_on_post_fix_head_halts(tmp_path):
    repo, init_head = _init_ceiling_git_repo(tmp_path)
    scoped_b = [{"title": "delta-b", "severity": "Important", "file": "newsurf.py", "line": 1}]
    cfg = _cfg(maxRoundsAbsolute=2, maxRounds=2, verifyCommand="pytest -q", repoRoot=repo)
    respond = _responder(round1_findings=_A_FINDING, scoped=scoped_b, head=HEAD_NEW_SURFACE)
    d, n, _head_a, _head_b = _drive_ceiling_round_two_fixer(
        tmp_path, cfg, respond, repo, init_head)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n3 = RD.cmd_next(d)
    assert n3["ok"] and n3["phase"] == RD.P_VERIFY, n3
    s2 = RD.cmd_submit(d, n3["phase"], n3["attempt"], n3["expectedStateHash"], {"result": "fail"})
    assert s2["ok"], s2
    n4 = RD.cmd_next(d)
    assert n4["action"] == RD.P_TERMINAL
    assert n4["payload"]["verdict"] == "halted"
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"]["2"]["verifyResult"] == "fail"


# axis: unknown surface — verify then full panel in the new round
def test_t4_unknown_surface_verify_then_panel(tmp_path):
    repo, init_head = _init_ceiling_git_repo(tmp_path)
    _commit_in_repo(repo, "t4-head")
    d = str(tmp_path)
    bad_head = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    cfg = _cfg(verifyCommand="pytest -q", repoRoot=repo, baseRef=init_head)

    def respond(phase, payload, rnd):
        r = _responder(round1_findings=_A_FINDING, head=bad_head)(phase, payload, rnd)
        return r

    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": bad_head, "changedSubjects": []})
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_VERIFY
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"], {"result": "pass"})
    assert s2["ok"], s2
    n3 = RD.cmd_next(d)
    assert n3["phase"] == RD.P_PANEL
    ok, state = RD.load_state(d)
    assert ok
    panel_round = str(state["round"])
    assert state["rounds"][panel_round]["roundKind"] == "full-panel-unknown-surface"


def _multi_file_diff(n):
    return "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 1..2 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n" % (i, i, i, i) for i in range(n))


def _n_findings(n):
    return [{"title": "bug%d" % i, "severity": "Important", "file": "f%d.py" % i, "line": 1}
            for i in range(n)]


def _multi_head(n):
    return "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 2..3 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1,3 @@\n-old\n+new\n+more\n+fixed\n" % (i, i, i, i) for i in range(n)) + _newsurf()


def _newsurf():
    return ("diff --git a/newsurf.py b/newsurf.py\nindex 0..1 100644\n--- a/newsurf.py\n"
            "+++ b/newsurf.py\n@@ -0,0 +1,2 @@\n+ns\n+ns2\n")


# axis: cap+2 findings split across two fixer dispatches in one round
def test_t5_fix_batch_split_six_findings(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    over = cap + 2
    d = str(tmp_path)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(over))
    seen_batches = []

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER:
            seen_batches.append(list(payload.get("batch") or []))
        return _responder(round1_findings=_n_findings(over), head=_multi_head(over))(
            phase, payload, rnd)

    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["attempt"] == 0
    assert len(n["payload"]["batch"]) == cap
    head = _multi_head(over)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [{"file": "x"}], "headDiff": head,
                       "changedSubjects": ["Code"]})
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_FIXER and n2["round"] == 1 and n2["attempt"] == 1
    assert len(n2["payload"]["batch"]) == over - cap
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"],
                       {"fixes": [{"file": "y"}], "headDiff": head,
                        "changedSubjects": ["Code"]})
    assert s2["ok"], s2
    ok, state = RD.load_state(d)
    assert ok
    assert any(d_["kind"] == "fix-batch-split" for d_ in state["decisions"])
    n3 = RD.cmd_next(d)
    assert n3["phase"] == RD.P_AUDITS
    assert len(n3["payload"]["targets"]) == over
    assert len(state["rounds"]["1"]["fix"]["fixes"]) == 2
    batches = state["rounds"]["1"]["fixBatches"]
    assert batches == [{"index": 0, "size": cap, "fixes": 1},
                       {"index": 1, "size": over - cap, "fixes": 1}]
    split = [d_ for d_ in state["decisions"] if d_["kind"] == "fix-batch-split"]
    assert split == [{"round": 1, "kind": "fix-batch-split",
                      "detail": "fix batch slice 1 of this round dispatched (%d findings; %d queued)"
                                  % (cap, len(_n_findings(over)) - cap - min(cap, over - cap))}]


# axis: exactly cap findings — one slice, no split decision
def test_t5_fix_batch_exact_cap_no_split(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    d = str(tmp_path)
    head = _multi_head(cap)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(cap))
    n = _drive_to_phase(d, cfg,
                        _responder(round1_findings=_n_findings(cap), head=head),
                        RD.P_FIXER)
    assert len(n["payload"]["batch"]) == cap
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [{"file": "x"}], "headDiff": head,
                       "changedSubjects": ["Code"]})
    assert s["ok"], s
    ok, state = RD.load_state(d)
    assert not any(d_["kind"] == "fix-batch-split" for d_ in state["decisions"])
    assert state["rounds"]["1"]["fixBatches"] == [{"index": 0, "size": cap, "fixes": 1}]


# axis: a configured cap below the default governs the slice size
def test_t5_fix_batch_cap_config_governs_slices(tmp_path):
    d = str(tmp_path)
    head = _multi_head(5)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(5), fixBatchCap=2)
    n = _drive_to_phase(d, cfg, _responder(round1_findings=_n_findings(5), head=head),
                        RD.P_FIXER)
    for expected_attempt, expected_size in enumerate((2, 2, 1)):
        assert n["attempt"] == expected_attempt
        assert len(n["payload"]["batch"]) == expected_size
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                          {"fixes": [], "headDiff": head, "changedSubjects": ["Code"]})
        assert s["ok"], s
        n = RD.cmd_next(d)
    assert n["phase"] == RD.P_AUDITS
    ok, state = RD.load_state(d)
    assert ok
    assert [b["size"] for b in state["rounds"]["1"]["fixBatches"]] == [2, 2, 1]


# axis: durable path — fix-batch.json and fix-batch.1.json for split slices
def test_t5_durable_fix_batch_files(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    over = cap + 2
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path, verifyCommand="pytest -q", diff=_multi_file_diff(over))
    with open(head_path, "w", encoding="utf-8") as fh:
        fh.write(_multi_head(over))
    findings = _n_findings(over)
    for phase in (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SYNTHESIS):
        _TDI._drive_one_phase(session_dir, gitdir, findings, head_path)
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == RD.P_FIXER and pend["attempt"] == 0
    assert len(pend["payload"]["batch"]) == cap
    _TDI._drive_one_phase(session_dir, gitdir, findings, head_path)
    state = _state(session_dir)
    assert os.path.isfile(os.path.join(session_dir, "round-1", "fix-batch.json"))
    pend = state["pending"]
    assert pend["phase"] == RD.P_FIXER and pend["attempt"] == 1
    _TDI._drive_one_phase(session_dir, gitdir, findings, head_path)
    assert os.path.isfile(os.path.join(session_dir, "round-1", "fix-batch.1.json"))


# axis: fixBatch accumulator resets each round — round 3 audits target B only
def test_t6_fix_batch_resets_per_round(tmp_path):
    d = str(tmp_path)
    cfg = _cfg(verifyCommand="pytest -q")
    finding_a = [{"title": "A", "severity": "Important", "file": "f.py", "line": 1}]
    finding_b = [{"title": "B", "severity": "Important", "file": "newsurf.py", "line": 1}]
    scoped_once = {"done": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": list(finding_a)}
            return {"seats": seats}
        if phase == RD.P_SCOPED and not scoped_once["done"]:
            scoped_once["done"] = True
            return {"findings": list(finding_b)}
        return _responder(head=HEAD_NEW_SURFACE)(phase, payload, rnd)

    n = _drive_to_phase(d, cfg, respond, RD.P_AUDITS)
    while n["round"] < 3:
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
        n = RD.cmd_next(d)
        if n["action"] == RD.P_TERMINAL:
            break
    assert n["phase"] == RD.P_AUDITS and n["round"] == 3
    files = {t.get("file") for t in n["payload"]["targets"]}
    assert files == {"newsurf.py"}


@pytest.mark.parametrize("value,ok", [
    (0, False), (-1, False), ("4", False), (True, False), (2.5, False),
    (4, True), (None, True),
])
def test_t7_fix_batch_cap_validation(tmp_path, value, ok):
    d = str(tmp_path)
    overrides = {"fixBatchCap": value} if value is not None else {}
    out = RD.cmd_next(d, _cfg(**overrides))
    if ok:
        assert out["ok"] is True
    else:
        assert out["ok"] is False
        assert out["reason"] == "fix-batch-cap-invalid"


# axis: _fixBatch assignment census — exactly one site in _queue_fix_batch
def test_t8_fix_batch_chokepoint_census():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    sites = re.findall(r'state\["_fixBatch"\] = ', text)
    assert len(sites) == 1
    idx = text.index('state["_fixBatch"] = ')
    before = text[:idx]
    func_name = re.findall(r"def (\w+)\(", before)[-1]
    assert func_name == "_queue_fix_batch"


# axis: escalated self-recovery split — both fixer slices carry escalatedRung
def test_t5_escalated_split_carries_rung_on_both_slices(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    over = cap + 1
    d = str(tmp_path)
    findings = _n_findings(over)
    head = _multi_head(over)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(over))
    respond = _responder(round1_findings=findings, head=head)
    n = _drive_to_phase(d, cfg, respond, RD.P_SYNTHESIS)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      respond(n["phase"], n["payload"], n["round"]))
    assert s["ok"], s
    ok, state = RD.load_state(d)
    assert ok
    rung = {"rung": "opus-5-thinking-high", "vendor": "claude"}
    state["_escalatedRung"] = rung
    RD.save_state(d, state)
    n1 = RD.cmd_next(d)
    assert n1["phase"] == RD.P_FIXER
    assert n1["payload"]["escalatedRung"] == rung
    assert len(n1["payload"]["batch"]) == cap
    s1 = RD.cmd_submit(d, n1["phase"], n1["attempt"], n1["expectedStateHash"],
                       {"fixes": [], "headDiff": head, "changedSubjects": ["Code"]})
    assert s1["ok"], s1
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_FIXER
    assert n2["payload"]["escalatedRung"] == rung
    assert len(n2["payload"]["batch"]) == over - cap


# axis: VERIFY_BUDGET placeholder — sorted files, no VERIFY_COMMAND
def test_t10_fixer_verify_budget_placeholder():
    batch = [{"file": "b.py", "line": 1}, {"file": "a.py", "line": 2}]
    cfg = {"verifyCommand": "pytest -q"}
    budget = RD._fixer_verify_budget(batch, cfg)
    assert budget.startswith("Scoped verify budget for this batch — target files: a.py, b.py.")
    assert "NOT yours to run" in budget
    assert budget.endswith("pytest -q")
    assert RD._fixer_verify_budget(batch, {}).endswith("none")


# axis: unregistered decision kind — _decision refuses before append
def test_t11_decision_refuses_unregistered_kind():
    state = RD.new_state()
    with pytest.raises(ValueError, match="decision-kind-unregistered:not-a-registered-kind"):
        RD._decision(state, "not-a-registered-kind", "x")
    RD._decision(state, "fix-batch-split", "detail")


def _guided_judgment(key, title, file, line, guidance):
    return {
        "id": key,
        SC.FINDING_KEY_FIELD: key,
        "title": title,
        "file": file,
        "line": line,
        "disposition": "fix-with-guidance",
        RD.GATE_GUIDANCE_RECORD_KEY: guidance,
    }


def _fix_batch_row(key, title, file, line):
    return {
        SC.FINDING_KEY_FIELD: key,
        "title": title,
        "file": file,
        "line": line,
        "severity": "Important",
    }


# axis: owner-gate guidance is rendered only for findings in the active fixer slice
def test_t12_guidance_rendered_per_slice():
    k1 = "a.py::finding one@L1"
    k2 = "b.py::finding two@L2"
    k3 = "c.py::finding three@L3"
    rows = [
        _fix_batch_row(k1, "finding one", "a.py", 1),
        _fix_batch_row(k2, "finding two", "b.py", 2),
        _fix_batch_row(k3, "finding three", "c.py", 3),
    ]
    rnd = 1
    config = {"fixBatchCap": 2}
    state = {
        "config": config,
        "round": rnd,
        "rounds": {
            str(rnd): {
                "judgmentDispositions": [
                    _guided_judgment(k1, "finding one", "a.py", 1, "guidance one"),
                    _guided_judgment(k2, "finding two", "b.py", 2, "guidance two"),
                    _guided_judgment(k3, "finding three", "c.py", 3, "guidance three"),
                ],
            },
        },
    }
    unsliced = {
        "config": config,
        "round": rnd,
        "rounds": state["rounds"],
        "_fixBatch": [],
    }
    entries_unsliced = RD._gate_guidance_entries(unsliced, rnd)
    assert {e["id"] for e in entries_unsliced} == {k1, k2, k3}
    RD._queue_fix_batch(state, config, rows)
    assert state["_fixQueue"]
    entries = RD._gate_guidance_entries(state, rnd)
    assert {e["id"] for e in entries} == {k1, k2}
    state["_fixBatch"] = [rows[2]]
    state["_fixBatchIndex"] = 1
    state["_fixQueue"] = []
    entries_slice2 = RD._gate_guidance_entries(state, rnd)
    assert {e["id"] for e in entries_slice2} == {k3}
