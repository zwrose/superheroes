#!/usr/bin/env python3
"""#1272 layer 2d — round economy: fix-batch cap, post-fix verify gate, scoped verify budget."""
import importlib.util
import json
import os
import re
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


# axis: ceiling round runs verify before round-ceiling park
def test_t3_ceiling_gate_runs_then_parks(tmp_path):
    d = str(tmp_path)
    scoped_b = [{"title": "delta-b", "severity": "Important", "file": "newsurf.py", "line": 1}]
    cfg = _cfg(maxRoundsAbsolute=2, maxRounds=2, verifyCommand="pytest -q")
    respond = _responder(round1_findings=_A_FINDING, scoped=scoped_b, head=HEAD_NEW_SURFACE)
    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["round"] == 1
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["round"] == 2
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Code"]})
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["ok"] and n2["phase"] == RD.P_VERIFY, n2
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"], {"result": "pass"})
    assert s2["ok"], s2
    n3 = RD.cmd_next(d)
    assert n3["action"] == RD.P_TERMINAL
    assert n3["payload"]["verdict"] == "halted"
    ok, state = RD.load_state(d)
    assert ok
    assert state["rounds"]["2"]["verifyResult"] == "pass"
    assert any(dec["kind"] == "round-ceiling" for dec in state["decisions"])


# axis: unknown surface — verify then full panel in the new round
def test_t4_unknown_surface_verify_then_panel(tmp_path):
    d = str(tmp_path)
    bad_head = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    cfg = _cfg(verifyCommand="pytest -q")

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


def _six_findings():
    return [{"title": "bug%d" % i, "severity": "Important", "file": "f%d.py" % i, "line": 1}
            for i in range(6)]


def _four_findings():
    return [{"title": "bug%d" % i, "severity": "Important", "file": "f%d.py" % i, "line": 1}
            for i in range(4)]


def _five_findings():
    return [{"title": "bug%d" % i, "severity": "Important", "file": "f%d.py" % i, "line": 1}
            for i in range(5)]


def _multi_head(n):
    return "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 2..3 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1,3 @@\n-old\n+new\n+more\n+fixed\n" % (i, i, i, i) for i in range(n)) + _newsurf()


def _newsurf():
    return ("diff --git a/newsurf.py b/newsurf.py\nindex 0..1 100644\n--- a/newsurf.py\n"
            "+++ b/newsurf.py\n@@ -0,0 +1,2 @@\n+ns\n+ns2\n")


# axis: six findings split across two fixer dispatches in one round
def test_t5_fix_batch_split_six_findings(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    d = str(tmp_path)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(6))
    seen_batches = []

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER:
            seen_batches.append(list(payload.get("batch") or []))
        return _responder(round1_findings=_six_findings(), head=_multi_head(6))(
            phase, payload, rnd)

    n = _drive_to_phase(d, cfg, respond, RD.P_FIXER)
    assert n["attempt"] == 0
    assert len(n["payload"]["batch"]) == cap
    head = _multi_head(6)
    s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                      {"fixes": [{"file": "x"}], "headDiff": head,
                       "changedSubjects": ["Code"]})
    assert s["ok"], s
    n2 = RD.cmd_next(d)
    assert n2["phase"] == RD.P_FIXER and n2["round"] == 1 and n2["attempt"] == 1
    assert len(n2["payload"]["batch"]) == 6 - cap
    s2 = RD.cmd_submit(d, n2["phase"], n2["attempt"], n2["expectedStateHash"],
                       {"fixes": [{"file": "y"}], "headDiff": head,
                        "changedSubjects": ["Code"]})
    assert s2["ok"], s2
    ok, state = RD.load_state(d)
    assert ok
    assert any(d_["kind"] == "fix-batch-split" for d_ in state["decisions"])
    n3 = RD.cmd_next(d)
    assert n3["phase"] == RD.P_AUDITS
    assert len(n3["payload"]["targets"]) == 6
    assert len(state["rounds"]["1"]["fix"]["fixes"]) == 2
    batches = state["rounds"]["1"]["fixBatches"]
    assert batches == [{"index": 0, "size": cap, "fixes": 1},
                       {"index": 1, "size": 6 - cap, "fixes": 1}]
    split = [d_ for d_ in state["decisions"] if d_["kind"] == "fix-batch-split"]
    assert split == [{"round": 1, "kind": "fix-batch-split",
                      "detail": "fix batch slice 1 of this round dispatched (%d findings; %d queued)"
                                  % (cap, len(_six_findings()) - cap - min(cap, 6 - cap))}]


# axis: exactly cap findings — one slice, no split decision
def test_t5_fix_batch_exact_cap_no_split(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    d = str(tmp_path)
    head = _multi_head(4)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(4))
    n = _drive_to_phase(d, cfg,
                        _responder(round1_findings=_four_findings(), head=head),
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
    n = _drive_to_phase(d, cfg, _responder(round1_findings=_five_findings(), head=head),
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
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path, verifyCommand="pytest -q", diff=_multi_file_diff(6))
    with open(head_path, "w", encoding="utf-8") as fh:
        fh.write(_multi_head(6))
    findings = _six_findings()
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


_CAP_DEFAULT_CITATION_RE = re.compile(r"round_phases\.FIX_BATCH_CAP_DEFAULT")


# axis: default cap constant and reference prose stay aligned
def test_t9_cap_default_and_reference_aligned():
    ref = os.path.join(os.path.dirname(_LIB), "skills", "review-code", "reference",
                       "round-driver.md")
    with open(ref, encoding="utf-8") as fh:
        text = fh.read()
    economy_start = text.index("## Round economy")
    economy_end = text.index("## Lens coverage beside counts", economy_start)
    economy = text[economy_start:economy_end]
    if not _CAP_DEFAULT_CITATION_RE.search(economy):
        raise AssertionError(
            "§ Round economy must cite round_phases.FIX_BATCH_CAP_DEFAULT by name; "
            "no match in sentence block starting: %s" % economy.strip()[:200])
    assert re.search(r"FIX_BATCH_CAP_DEFAULT\s*\(\s*\d+\s*\)", economy) is None


# axis: escalated self-recovery split — both fixer slices carry escalatedRung
def test_t5_escalated_split_carries_rung_on_both_slices(tmp_path):
    cap = round_phases.FIX_BATCH_CAP_DEFAULT
    d = str(tmp_path)
    findings = _five_findings()
    head = _multi_head(5)
    cfg = _cfg(verifyCommand="pytest -q", diff=_multi_file_diff(5))
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
    assert len(n2["payload"]["batch"]) == 5 - cap


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
