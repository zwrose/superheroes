"""Tests for `round_driver` — the ONE-entrypoint review-loop round driver (#507).

The driver collapses review-code's per-round script choreography into ONE entrypoint so the
mandated path is the easiest path. These pin BOTH layers over the shared core:

  - Layer 2 (next/submit CLI): the state-machine protocol — echo validation (stale attempt /
    hash mismatch rejected, exact-duplicate idempotent), v1-state refusal, per-call journalling.
  - Layer 1 (run_loop): the ported run-shape driven end-to-end with scripted seams.

Ported invariants from the retired test_code_loop_plan.py (round-1 full-deep baseline; the #174
confirmation economics incl. cap-parks-on-Critical; fail-toward-run-all on an unknown surface;
exits only off a qualifying round — now also expressible as an audited-chain certification), plus
the new #507 mechanics: audit-keyed stall + self-recovery + stall menu, delta rounds, degraded
independence, receipt-missing seats carried unverified, the author-justification POST-filter, and
the driver receipt + its validator.
"""
import importlib.util
import json
import os
import re
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
LPC = _load("loop_plan_common")

# --- diffs --------------------------------------------------------------------

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD = ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,3 @@\n-old\n+new\n+more\n+fixed\n")


def _headf(n):
    return ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1 +1,%d @@\n-old\n+new\n" % (n + 2)) + "".join("+z%d\n" % i for i in range(n))


# A brand-new file section — a genuinely-new surface (no fix batch line sits over it). Appended to a
# post-fix head diff so a delta round's scoped finder has a real surface to scan: post #507-WO-R2b an
# EMPTY new surface SKIPS the scoped dispatch, so a test that exercises the scoped finder must offer
# it one. The audited hunk (over the fixed line 1) stays an audit target; this is the new surface.
def _newsurf(tag=""):
    return ("diff --git a/newsurf.py b/newsurf.py\nindex 0..1 100644\n--- a/newsurf.py\n"
            "+++ b/newsurf.py\n@@ -0,0 +1,2 @@\n+ns%s\n+ns2\n" % tag)


HEAD_NEW_SURFACE = HEAD + _newsurf()


def _headf_ns(n):
    return _headf(n) + _newsurf(str(n))


def _big_diff(n_files=25):
    return "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 1..2 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1 @@\n-a\n+b\n" % (i, i, i, i) for i in range(n_files))


# --- default scripted seams ---------------------------------------------------

def _seams(reviewer=None, verifier=None, synthesis=None, auditor=None, fix_step=None,
           verify_runner=None, io=None):
    def default_reviewer(dim, tier, rnd, ctx):
        return []

    def default_verifier(clusters, rnd):
        return [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    def default_synthesis(findings, rnd):
        return None

    def default_auditor(targets, rnd):
        # Echo the selected independent auditor vendor so the discharge passes the provenance gate.
        return [{"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                 "evidence": "tests pass", "auditorVendor": t.get("auditorVendor")}
                for t in (targets or [])]

    def default_fix(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]}

    def default_verify(command, rnd):
        return "pass"

    return {
        "reviewer": reviewer or default_reviewer,
        "verifier": verifier or default_verifier,
        "synthesis": synthesis or default_synthesis,
        "auditor": auditor or default_auditor,
        "fix_step": fix_step or default_fix,
        "verify_runner": verify_runner or default_verify,
        "io": io or {},
    }


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


# =============================================================================
# Layer 2 — next/submit protocol
# =============================================================================

def _first_next(session_dir, cfg):
    return RD.cmd_next(session_dir, cfg)


def test_next_emits_round1_full_deep_panel(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    assert n["ok"] and n["action"] == RD.P_PANEL and n["round"] == 1
    # round-1 baseline is the full FIVE-seat reviewer-deep panel (the reversal upgrade).
    assert n["payload"]["tier"] == RD.DEEP
    assert sorted(n["payload"]["dimensions"]) == sorted(RD.DIMENSIONS)


def test_next_is_idempotent_before_submit(tmp_path):
    d = str(tmp_path)
    a = _first_next(d, _cfg())
    b = RD.cmd_next(d)
    assert a["phase"] == b["phase"] and a["attempt"] == b["attempt"]
    assert a["expectedStateHash"] == b["expectedStateHash"]  # hash reproduces on re-emit


def test_submit_stale_attempt_rejected(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"] + 3, n["expectedStateHash"], {"seats": {}})
    assert out["ok"] is False and "echo" in out["reason"]


def test_submit_hash_mismatch_rejected(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"], "deadbeef", {"seats": {}})
    assert out["ok"] is False and "hash" in out["reason"]


def test_submit_without_state_hash_rejected(tmp_path):
    """#507 v13: the state-hash echo is REQUIRED — a first-time fold with no hash is refused (never
    fold fail-open on an absent hash)."""
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    out = RD.cmd_submit(d, n["phase"], n["attempt"], None, {"seats": {}})
    assert out["ok"] is False and "state-hash" in out["reason"]


def test_submit_duplicate_is_idempotent(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    art = {"seats": {"code-reviewer": {"findings": []}}}
    first = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert first["ok"] is True and not first.get("duplicate")
    dup = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert dup == {"ok": True, "duplicate": True}


def test_v1_state_is_refused_with_fresh_start_message(tmp_path):
    d = str(tmp_path)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {}}, fh)
    out = RD.cmd_next(d)
    assert out["ok"] is False and "fresh session dir" in out["reason"]


def test_journal_appended_per_call(tmp_path):
    d = str(tmp_path)
    n = _first_next(d, _cfg())
    RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                  {"seats": {"code-reviewer": {"findings": []}}})
    journal = RD.read_journal(d)
    cmds = [e["cmd"] for e in journal]
    assert "next" in cmds and "submit" in cmds
    assert any(e.get("outcome") == "accepted" for e in journal)


# =============================================================================
# a scripted driver harness (CLI end-to-end)
# =============================================================================

def _drive_cli(session_dir, cfg, respond, max_steps=80):
    """Drive next/submit to a terminal using `respond(phase, payload, round) -> artifact`."""
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            return n["payload"]
        art = respond(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("driver did not reach a terminal within %d steps" % max_steps)


def _responder(round1_findings=None, scoped=None, audit="discharged", verify="pass",
               head=HEAD, verdict="CONFIRMED"):
    scoped_state = {"fired": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1 and round1_findings:
                seats["code-reviewer"] = {"findings": list(round1_findings)}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            out = []
            for c in payload.get("clusters", []):
                for i in c.get("ids", []):
                    v = {"id": i, "verdict": verdict}
                    if verdict == "CONFIRMED":
                        v["evidence"] = "ran"
                    out.append(v)
            return {"verdicts": out}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        if phase == RD.P_AUDITS:
            # The orchestrator records its dispatch manifest out-of-band from the results — the vendor
            # it seated per target, read off the dispatch payload (never the result echo).
            return {"results": [{"id": t["id"], "ruling": audit, "reason": "r", "evidence": "e",
                                 "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            if scoped and not scoped_state["fired"]:
                scoped_state["fired"] = True
                return {"findings": list(scoped)}
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": head, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": verify}
        return {}

    return respond


def test_happy_path_audited_chain_certification(tmp_path):
    """Round-1 panel → verify findings → fix → delta round → all discharged → audited-chain."""
    d = str(tmp_path)
    payload = _drive_cli(d, _cfg(), _responder(
        round1_findings=[{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]))
    assert payload["verdict"] == "converged"
    assert payload["certification"]["shape"] == "audited-chain"
    # receipt is written at the terminal and validates.
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    assert receipt["scriptRan"]["invocations"] > 0


def test_clean_round1_certifies_full_panel_confirmed(tmp_path):
    """A clean full-deep baseline certifies off the qualifying panel (full-panel-confirmed)."""
    d = str(tmp_path)
    payload = _drive_cli(d, _cfg(), _responder(round1_findings=None))
    assert payload["verdict"] == "converged"
    assert payload["certification"]["shape"] == "full-panel-confirmed"


def test_unknown_delta_surface_runs_full_panel(tmp_path):
    """A malformed/quoted-path head diff → unknown surface → a FULL reviewer-deep panel (the
    existing unknown→run-everything rule), not a scoped audit."""
    d = str(tmp_path)
    bad_head = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    seen = {"panel_r2": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            if rnd >= 2:
                seen["panel_r2"] = True
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "PLAUSIBLE"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": bad_head, "changedSubjects": []}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase in (RD.P_AUDITS, RD.P_SCOPED, RD.P_GAPSWEEP):
            return {"results": [], "findings": []}
        return {}

    payload = _drive_cli(d, _cfg(), respond)
    assert seen["panel_r2"] is True
    assert payload["verdict"] == "converged"


# =============================================================================
# scoped-finder new-surface payload + empty-surface skip (#507 WO-R2b)
# =============================================================================

# A multi-file post-fix head diff: f.py carries the fixed hunk (over the fix's line, an AUDIT
# target) PLUS a brand-new hunk far from it, and g.py is an entirely new surface. The split must
# route the two off-target hunks into `newSurface` — the scoped finder's real payload.
_R2B_REVIEWED = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                 "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
_R2B_HEAD_MF = ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
                "@@ -1 +1,2 @@\n-old\n+new\n+fixed\n"
                "@@ -50,0 +50,2 @@\n+brand\n+new\n"
                "diff --git a/g.py b/g.py\nindex 0..1 100644\n--- a/g.py\n+++ b/g.py\n"
                "@@ -0,0 +1,3 @@\n+alpha\n+beta\n+gamma\n")


def test_scoped_finder_payload_carries_computed_new_surface(tmp_path):
    """The dispatch-scoped-finder payload carries EXACTLY the split's computed `newSurface` hunks
    (file → hunk ranges + text) — a multi-file surface must arrive intact, not empty (#507 WO-R2b:
    the field-found defect was an empty `hunks: {}` payload despite a real computed surface)."""
    d = str(tmp_path)
    captured = {"payload": None}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            captured["payload"] = payload
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": _R2B_HEAD_MF, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}

    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    assert captured["payload"] is not None, "the scoped finder was never dispatched"
    hunks = captured["payload"]["hunks"]
    # exactly the split's computed new surface — a non-empty, multi-file map.
    expected = RD.delta_surface.split_fix_surface(
        _R2B_REVIEWED, _R2B_HEAD_MF, [{"file": "f.py", "line": 1}])["newSurface"]
    assert expected and set(expected) == {"f.py", "g.py"}, expected
    assert hunks == expected
    assert sum(len(v) for v in hunks.values()) == 2


def test_empty_new_surface_skips_scoped_finder_with_note(tmp_path):
    """A genuinely empty computed new surface (split `unknown: False`, no new hunks — the fix only
    touched the audited lines) SKIPS the scoped-finder dispatch with a receipt-visible
    `scopedFinder: skipped-empty-surface` note, never a vacuous scan over nothing (#507 WO-R2b)."""
    d = str(tmp_path)
    seen = {"scoped": False}

    base = _responder(round1_findings=[
        {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}])

    def respond(phase, payload, rnd):
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
        return base(phase, payload, rnd)

    payload = _drive_cli(d, _cfg(), respond)
    assert payload["verdict"] == "converged"
    assert seen["scoped"] is False, "the scoped finder was dispatched over an empty surface"
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    # the skip is journaled receipt-visibly: as a decision AND on the delta round record.
    kinds = [dc["kind"] for dc in receipt["decisions"]]
    assert "scoped-finder-skipped" in kinds, kinds
    delta_round = [r for r in receipt["rounds"] if r.get("scopedFinder")]
    assert delta_round and delta_round[0]["scopedFinder"] == "skipped-empty-surface", receipt["rounds"]


# =============================================================================
# dispatch-fixer head diff: inline OR absolute headDiffPath; unreadable → full panel (#507)
# =============================================================================

def _multifile_delta_respond(captured, fixer_artifact):
    """A CLI responder for the multi-file delta scenario: round-1 finds one Important at f.py:1,
    audits discharge, the scoped finder's payload is captured. The fixer's artifact (inline `headDiff`
    and/or `headDiffPath`) is supplied by the caller so each test exercises a different head-diff
    source."""
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            captured["payload"] = payload
            return {"findings": []}
        if phase == RD.P_FIXER:
            return dict(fixer_artifact)
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}
    return respond


def test_fixer_head_diff_path_form_end_to_end(tmp_path):
    """A `dispatch-fixer` artifact may carry the post-fix head diff as an ABSOLUTE `headDiffPath` the
    driver reads itself (a real git diff cannot inline into a JSON submit artifact). The delta split
    reads the file's content, so the scoped finder's payload carries that file's new surface (#507)."""
    d = str(tmp_path)
    head_file = tmp_path / "head-r1.txt"
    head_file.write_text(_R2B_HEAD_MF, encoding="utf-8")
    captured = {"payload": None}
    respond = _multifile_delta_respond(
        captured, {"fixes": [], "headDiffPath": str(head_file), "changedSubjects": ["Code"]})
    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    assert captured["payload"] is not None, "the scoped finder was never dispatched"
    expected = RD.delta_surface.split_fix_surface(
        _R2B_REVIEWED, _R2B_HEAD_MF, [{"file": "f.py", "line": 1}])["newSurface"]
    assert captured["payload"]["hunks"] == expected and set(expected) == {"f.py", "g.py"}
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "path" for r in receipt["rounds"]), receipt["rounds"]


def test_fixer_unreadable_head_diff_path_schedules_full_panel(tmp_path):
    """An unreadable `headDiffPath` (no inline diff) is an UNKNOWN surface, not an empty one: the
    delta round runs a FULL reviewer-deep panel (unknown→run-everything), never a silent scoped skip
    over nothing. The source is journaled `unknown` and an `unknown-surface` decision is recorded."""
    d = str(tmp_path)
    missing = str(tmp_path / "does-not-exist.txt")
    seen = {"panel_r2": False, "scoped": False}

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            if rnd >= 2:
                seen["panel_r2"] = True
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiffPath": missing, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
            return {"findings": []}
        if phase in (RD.P_AUDITS, RD.P_GAPSWEEP):
            return {"results": [], "findings": []}
        return {}

    payload = _drive_cli(d, _cfg(), respond)
    assert seen["panel_r2"] is True, "an unreadable head diff must run a full panel, not a scoped scan"
    assert seen["scoped"] is False
    assert payload["verdict"] == "converged"
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "unknown" for r in receipt["rounds"]), receipt["rounds"]
    assert any(dc["kind"] == "unknown-surface" for dc in receipt["decisions"]), receipt["decisions"]


def test_fixer_inline_head_diff_wins_over_path(tmp_path):
    """When BOTH inline `headDiff` and `headDiffPath` are present, inline wins: the scoped payload
    carries the inline diff's (multi-file) new surface, not the path file's (empty) one (#507)."""
    d = str(tmp_path)
    other = tmp_path / "other-head.txt"
    other.write_text(HEAD, encoding="utf-8")  # a single-file diff whose only hunk is over the fix
    captured = {"payload": None}
    respond = _multifile_delta_respond(captured, {
        "fixes": [], "headDiff": _R2B_HEAD_MF, "headDiffPath": str(other),
        "changedSubjects": ["Code"]})
    payload = _drive_cli(d, _cfg(diff=_R2B_REVIEWED), respond)
    assert payload["verdict"] == "converged"
    # inline won → the scoped finder fired over the inline diff's two-file surface.
    assert captured["payload"] is not None
    expected = RD.delta_surface.split_fix_surface(
        _R2B_REVIEWED, _R2B_HEAD_MF, [{"file": "f.py", "line": 1}])["newSurface"]
    assert captured["payload"]["hunks"] == expected and set(expected) == {"f.py", "g.py"}
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert any(r.get("headDiffSource") == "inline" for r in receipt["rounds"]), receipt["rounds"]


# =============================================================================
# Layer 1 — run_loop (library) on each leg shape
# =============================================================================

def test_run_loop_code_leg_end_to_end(tmp_path):
    receipt = RD.run_loop(_seams(reviewer=lambda dim, tier, rnd, ctx:
                                 ({"findings": [{"title": "bug", "severity": "Important",
                                                 "file": "f.py", "line": 1}]}
                                  if rnd == 1 and dim == "code-reviewer" else [])),
                          _cfg())
    assert receipt["verdict"] == "converged"
    ok, _ = RD.validate_receipt(receipt)
    assert ok


def test_run_loop_panel_leg_shape(tmp_path):
    """The panel leg-shape config also drives run_loop end-to-end (a clean panel certifies)."""
    receipt = RD.run_loop(_seams(), _cfg(leg="panel"))
    assert receipt["verdict"] == "converged"
    ok, _ = RD.validate_receipt(receipt)
    assert ok


# =============================================================================
# audit-keyed stall → self-recovery once → stall menu
# =============================================================================

def _persistent_not_discharged_seams(io=None):
    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

    return _seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=lambda targets, rnd: [{"id": t["id"], "ruling": "not-discharged", "reason": "broken"}
                                      for t in (targets or [])],
        fix_step=fix_step, io=io)


def test_not_discharged_twice_self_recovers_once_then_stall_menu(tmp_path):
    menu_shown = []

    def stall_menu(payload):
        menu_shown.append(payload)
        return "hold"

    seams = _persistent_not_discharged_seams(io={"stall_menu": stall_menu})
    receipt = RD.run_loop(seams, _cfg(maxRounds=20))
    kinds = [dd["kind"] for dd in receipt["decisions"]]
    # exactly one self-recovery, journalled as a decision.
    assert kinds.count("self-recovery") == 1
    # the stall menu was presented with exactly the four choices (accept-the-risk gated out here).
    assert len(menu_shown) == 1
    assert menu_shown[0]["choices"] == ["ship-smaller", "spend-more", "hold"]
    assert menu_shown[0]["acceptRiskEligible"] is False
    assert receipt["verdict"] == "held"


def test_accept_the_risk_gated_on_confirmed(tmp_path):
    """accept-the-disclosed-risk is offerable ONLY for a CONFIRMED-with-receipt finding."""
    state = RD.new_state(_cfg())
    # a CONFIRMED finding with a receipt is present → eligible.
    state["findings"] = [{"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"}]
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": ["v0"]})
    assert state["_acceptRiskEligible"] is True
    assert "accept-the-disclosed-risk" in state["_stallChoices"]
    # without a CONFIRMED finding → NOT eligible.
    state2 = RD.new_state(_cfg())
    state2["findings"] = [{"id": "v1", "verdict": "PLAUSIBLE"}]
    state2["selfRecovered"] = True
    RD._handle_stall(state2, state2["config"], {"reason": "audit-stall",
                                                "detail": "x", "stalledIdentities": ["v1"]})
    assert state2["_acceptRiskEligible"] is False
    assert "accept-the-disclosed-risk" not in state2["_stallChoices"]


_STALL_BREAKER = {"reason": "audit-stall", "detail": "stalled", "stalledIdentities": ["v0"]}


def test_stall_self_recovery_unknown_fixer_does_not_stamp_escalated_rung():
    """#608 review: unknown fixer → escalate returns None — must not set a truthy _escalatedRung."""
    state = RD.new_state({"leg": "code", "vendors": ["claude"]})
    assert state["config"]["fixerVendor"] is None
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert state["selfRecovered"] is True
    assert state["step"] == RD.P_FIXER
    assert state.get("_escalatedRung") is None
    # #620 R3a: the null-rung self-recovery decision detail must be honest — never "escalated to None".
    sr = [d for d in state["decisions"] if d["kind"] == "self-recovery"]
    assert len(sr) == 1
    assert "escalated to None" not in sr[0]["detail"]
    assert "no escalation rung available" in sr[0]["detail"]


def test_stall_self_recovery_known_fixer_stamps_escalated_rung():
    """#608 review contrast: known claude fixer at default sonnet-5/high has a next ladder rung."""
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    RD._handle_stall(state, state["config"], _STALL_BREAKER)
    assert state["selfRecovered"] is True
    assert state["step"] == RD.P_FIXER
    escalated = state.get("_escalatedRung")
    assert escalated is not None
    assert escalated["rung"] is not None
    assert escalated["vendor"] == "claude"
    # #620 R3a contrast: on the real-rung path the detail names the actual escalation target.
    sr = [d for d in state["decisions"] if d["kind"] == "self-recovery"]
    assert len(sr) == 1
    assert ("fixer escalated to %r" % (escalated["rung"],)) in sr[0]["detail"]


def test_eligible_owner_acceptance_converges_end_to_end(tmp_path):
    """#507 v9: exercise the eligible owner-acceptance stall path to its terminal — an eligible
    CONFIRMED-with-receipt stall, the owner submits `accept-the-disclosed-risk`, and the run
    converges (terminal, certification note records the accepted disclosed risk). Guards against a
    mutation that makes an eligible acceptance hold/park instead of converge."""
    state = RD.new_state(_cfg())
    state["findings"] = [{"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"}]
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], {"reason": "audit-stall", "detail": "x",
                                              "stalledIdentities": ["v0"]})
    assert state["_acceptRiskEligible"] is True
    RD._fold_stall(state, state["config"], {"choice": "accept-the-disclosed-risk"})
    assert state["terminal"] == "converged"
    assert state["step"] == RD.P_TERMINAL
    note = (state.get("certification") or {}).get("note") or ""
    assert "accepted the disclosed" in note, note


# =============================================================================
# confirmation economics: cap-parks-on-Critical, budget 2, re-arm
# =============================================================================

def _delta_state_ready(confirmations, surfaced, findings=None, not_discharged=None):
    state = RD.new_state(_cfg(maxRounds=20))
    state["confirmations"] = confirmations
    state["surfacedSinceLastPanel"] = list(surfaced)
    state["round"] = confirmations + 3
    state["findings"] = list(findings or [])
    state["fullPanelRan"] = False
    nd = not_discharged or []
    state["auditRounds"] = [{"round": 2, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": nd, "discharged": ["x"]}
    state["_changedSubjects"] = ["Code"]
    return state


def test_capped_with_open_critical_parks(tmp_path):
    """A Critical still owed at the 2-panel confirmation cap parks (certification withheld)."""
    state = _delta_state_ready(confirmations=RD.MAX_CONFIRMATIONS, surfaced=["Critical"])
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "capped-with-open-critical"
    assert state["certification"]["shape"] is None


def test_non_critical_at_cap_certifies(tmp_path):
    """A non-Critical at the cap resolves by scoped verify → certifies (audited-chain)."""
    state = _delta_state_ready(confirmations=RD.MAX_CONFIRMATIONS, surfaced=["Important"])
    RD._settle_delta(state, state["config"])
    assert state["terminal"] == "converged"
    assert state["certification"]["shape"] == "audited-chain"


def test_critical_rearms_one_more_confirmation_under_budget(tmp_path):
    """A Critical surfaced with confirmations under the cap re-arms one more FULL panel."""
    state = _delta_state_ready(confirmations=0, surfaced=["Critical"])
    RD._settle_delta(state, state["config"])
    assert state["terminal"] is None  # not certified — a confirmation is owed
    assert state["step"] == RD.P_PANEL
    assert any(dd["kind"] == "confirmation-rearm" for dd in state["decisions"])


def test_confirmation_budget_two_respected_end_to_end(tmp_path):
    """A Critical surfaced by a delta scoped-finder re-arms a full panel; a subsequent clean panel
    certifies as full-panel-confirmed (one re-arm, budget not exceeded)."""
    scoped_state = {"fired": False}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "scoped-finder" and not scoped_state["fired"]:
            scoped_state["fired"] = True
            return [{"title": "hole", "severity": "Critical", "file": "f.py", "line": 1}]
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
        return []

    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": _headf_ns(counter["n"]), "changedSubjects": ["Code"]}

    receipt = RD.run_loop(_seams(reviewer=reviewer, fix_step=fix_step), _cfg(maxRounds=20))
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] == "full-panel-confirmed"
    assert any(x["kind"] == "confirmation" for x in receipt["rounds"])


# =============================================================================
# big diff → sharded panel + gap-sweep; degraded independence; receipt-missing
# =============================================================================

def test_big_diff_shards_panel_with_wholediff_crosscutting_lenses(tmp_path):
    state = RD.new_state(_cfg(diff=_big_diff(25)))
    step = RD._advance(state, state["config"])
    payload = step["payload"]
    assert payload["big"] is True and "shards" in payload
    assert payload["shards"]["architecture-reviewer"]["wholeDiff"] is True
    assert payload["shards"]["premortem-reviewer"]["wholeDiff"] is True
    assert "shards" in payload["shards"]["code-reviewer"]  # a local lens gets sharded


def test_big_diff_schedules_gap_sweep(tmp_path):
    """A big diff schedules a gap-sweep after verification (before the fix leg)."""
    seen = {"gap": False}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            seen["gap"] = True
            return []
        return []

    RD.run_loop(_seams(reviewer=reviewer), _cfg(diff=_big_diff(25)))
    assert seen["gap"] is True


def test_degraded_single_vendor_flows_to_certification_shape(tmp_path):
    receipt = RD.run_loop(_seams(reviewer=lambda dim, tier, rnd, ctx:
                                 ({"findings": [{"title": "bug", "severity": "Important",
                                                 "file": "f.py", "line": 1}]}
                                  if rnd == 1 and dim == "code-reviewer" else [])),
                          _cfg(vendors=["claude"], fixerVendor="claude"))
    assert receipt["certificationShape"] == "audited-chain-degraded"
    assert receipt["degraded"], "the lost independence must be named in the receipt"


def test_independent_auditor_selection_two_vendor(tmp_path):
    """#507 v8: with two live vendors the fix's auditor is the NON-fixer vendor (independent). The
    auditor seam captures its targets so the selection is asserted directly — a mutation that
    returns the fixer vendor as `auditorVendor` (losing independence) fails this test."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), _cfg(vendors=["claude", "codex"], fixerVendor="claude"))
    assert receipt["verdict"] == "converged"
    assert captured["targets"], "the auditor must have received the fix's audit targets"
    t = captured["targets"][0]
    assert t["fixerVendor"] == "claude"
    assert t["auditorVendor"] == "codex"
    assert t["independence"] == "independent"
    assert receipt["certificationShape"] == "audited-chain"  # NOT -degraded


def test_unknown_fixer_vendor_degraded_end_to_end_two_vendor(tmp_path):
    """#608: omitting fixerVendor must not assume claude — unknown fixer degrades, never false independent."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF}
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), cfg)
    assert receipt["verdict"] == "converged"
    assert captured["targets"]
    t = captured["targets"][0]
    assert t["fixerVendor"] is None
    assert t["independence"] == "degraded"
    assert t["auditorVendor"] == "claude"
    assert receipt["certificationShape"] == "audited-chain-degraded"
    assert receipt["degraded"], "the lost independence must be named in the receipt"


def test_explicit_cross_family_fixer_still_independent_two_vendor(tmp_path):
    """#608 contrast: known codex fixer with two vendors still yields independent audit."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "codex"}
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), cfg)
    assert receipt["verdict"] == "converged"
    t = captured["targets"][0]
    assert t["independence"] == "independent"
    assert receipt["certificationShape"] == "audited-chain"


def test_audit_result_from_wrong_vendor_is_not_discharged(tmp_path):
    """#507 WO-FIX-RECOVERY (audits): a clearing ruling that the ORCHESTRATOR's dispatch manifest
    does not authenticate is rejected as not-discharged + unauthenticated, so it can never certify a
    fix the independent auditor did not clear. The result's own echo authenticates nothing."""
    import audits
    target = {"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important",
              "fixerVendor": "claude", "auditorVendor": "codex", "independence": "independent"}
    # the fixer vendor tries to self-clear — echoing "claude" proves nothing (no manifest either)
    out = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "trust me",
                    "auditorVendor": "claude"}])
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]
    # the orchestrator's manifest authenticates the codex dispatch → discharged, trusted vendor recorded
    ok = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "fix verified",
                    "auditorVendor": "codex"}],
        collection_manifest={"v0": "codex"})
    assert ok["discharged"] == ["v0"]
    assert ok["unauthenticated"] == []
    assert ok["audits"][0]["auditor"] == "codex"


def test_audit_round_outcomes_carry_class_keys_for_alias_stall(tmp_path):
    """#507 v0: the live audit-round outcomes carry classKey/dimension/taxonomy, so the audit-stall
    breaker's alias-tolerant match stalls a retitled-but-same-class not-discharged finding across
    two consecutive rounds (the contract `check_audit_breaker` advertises but the wire never fed)."""
    import circuit_breaker as CB
    state = RD.new_state(_cfg())
    f = {"title": "leaks memory", "severity": "Important", "file": "f.py", "line": 1,
         "dimension": "Security", "taxonomy": "CWE-401", "classKey": "Security::CWE-401::orig"}
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    assert tgt["classKey"] == "Security::CWE-401::orig"
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken"}]})
    round1 = state["auditRounds"][-1]
    assert round1["outcomes"][0]["classKey"] == "Security::CWE-401::orig"
    # a SECOND round: the finding is retitled (a different identity) but keeps its classKey.
    retitled = {"round": state["round"] + 1, "outcomes": [
        {"identity": "f.py::memory not freed", "ruling": "not-discharged",
         "classKey": "Security::CWE-401::orig", "dimension": "Security", "taxonomy": "CWE-401"}]}
    brk = CB.check_audit_breaker([round1, retitled], 20)
    assert brk["halt"] and brk["reason"] == "audit-stall", brk


def test_audit_outcome_carries_title_so_distinct_classkeys_dont_false_stall(tmp_path):
    """#507 R2 v2: two DISTINCT classKeys that share dimension+taxonomy must NOT collide into a
    false audit-stall. The live outcome now carries `title`, so the breaker's canonical class key is
    the full `dim::tax::title`, not the title-less `dim::tax::` alias that merged unrelated findings."""
    import circuit_breaker as CB

    def fold(title, classkey):
        state = RD.new_state(_cfg())
        state["fixBatch"] = [{"title": title, "severity": "Important", "file": "f.py", "line": 1,
                              "dimension": "Security", "taxonomy": "CWE-401", "classKey": classkey}]
        state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
        tgt = state["_auditTargets"][0]
        RD._fold_audits(state, state["config"], {"results": [
            {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken"}]})
        return state["auditRounds"][-1]

    r1 = fold("secret a", "Security::CWE-401::secret a")
    assert r1["outcomes"][0]["title"] == "secret a"
    r2 = {"round": 2, "outcomes": fold("secret b", "Security::CWE-401::secret b")["outcomes"]}
    brk = CB.check_audit_breaker([r1, r2], 20)
    assert not brk["halt"], brk  # two distinct classKeys → NOT a stall


def test_omitted_seat_zero_finding_withholds_certification(tmp_path):
    """#507 R2 residual-1: an omitted panel seat with ZERO findings must WITHHOLD certification — an
    incomplete panel is 'we did not look', never a clean audited-chain. The converge parks."""
    def reviewer(dim, tier, rnd, ctx):
        return None if dim == "premortem-reviewer" else []

    receipt = RD.run_loop(_seams(reviewer=reviewer), _cfg())
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None


def test_incomplete_panel_flag_cleared_by_complete_panel():
    """The outstanding-coverage-gap flag arms on an incomplete panel and is CLEARED only when a
    complete panel re-establishes coverage (a scoped delta leaves it untouched)."""
    state = RD.new_state(_cfg())
    RD._fold_panel(state, state["config"], {"seats": {
        d: {"findings": []} for d in RD.DIMENSIONS if d != "premortem-reviewer"}})
    assert state["_incompletePanel"] is True
    state["round"] = 3
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    assert state["_incompletePanel"] is False


def test_verify_skip_with_configured_command_halts(tmp_path):
    """#507 R2 residual-2: a skip result while a REAL verify command is configured means the gate
    did NOT run — fail closed to halt, never advance unverified into a round that could certify."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "skipped"), _cfg(verifyCommand="pytest -q"))
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None


def test_verify_skip_with_no_command_still_advances(tmp_path):
    """A skip result with NO verify command configured is a legitimate unverified advance."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "none"), _cfg(verifyCommand="none"))
    assert receipt["verdict"] == "converged"


def test_new_blocker_does_not_drop_unresolved_target_at_different_line():
    """#507 R2 residual-3: a new blocker sharing a not-discharged target's file+title at a DIFFERENT
    line is a distinct finding — the union keys on (identity, line), so the unresolved target is
    NEVER dropped when the new blocker has the same line-less identity."""
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["_auditTargets"] = [{"id": "f.py::same bug", "file": "f.py", "line": 1,
                               "title": "same bug", "severity": "Important"}]
    state["_auditOutcome"] = {"notDischarged": ["f.py::same bug"], "discharged": []}
    state["auditRounds"] = [{"round": 2, "outcomes": [
        {"identity": "f.py::same bug", "ruling": "not-discharged"}]}]
    state["findings"] = [{"title": "same bug", "severity": "Important", "file": "f.py", "line": 2}]
    RD._settle_delta(state, state["config"])
    assert state["step"] == RD.P_FIXER
    assert sorted(b.get("line") for b in state["_fixBatch"]) == [1, 2]


def test_journal_append_records_fault_on_oserror(tmp_path):
    """#507 R2 residual-4: a journal append failure is NOT swallowed — it records a durable fault
    marker (the driver's ran-evidence lost an entry)."""
    d = str(tmp_path)
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))  # a dir where the file should be → append OSErrors
    RD._journal_append(d, {"cmd": "next", "phase": "dispatch-panel"})
    assert RD._journal_faulted(d) is True


def test_journal_fault_makes_finalize_park(tmp_path):
    """A recorded journal fault makes finalization fail closed (park) — the scriptRan evidence is
    incomplete, so the terminal never certifies over a partial-journal gap."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))  # a real terminal + valid receipt
    RD._mark_journal_fault(d, {"cmd": "submit", "phase": "run-verify"}, OSError("disk full"))
    ok, state = RD.load_state(d)
    fail = RD._finalize_receipt(d, state)
    assert fail and "journal" in fail and "park" in fail


def _guard_argv(session_dir, *, fresh=True, mode="branch", base_fetch="fetched", write_meta=True):
    """#648: the extra argv that satisfies the base guard for a CLI `next` on `session_dir`.

    Builds a real two-commit git repo under the session dir, writes meta.json pinned to the first
    commit, and — on fresh state — the real ``git diff <pin>...HEAD`` round-1 diff. Idempotent.
    """
    repo = os.path.join(session_dir, "_gitrepo")
    if not os.path.isdir(os.path.join(repo, ".git")):
        os.makedirs(repo, exist_ok=True)
        subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
        subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
        subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
        subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
        pin = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
        with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        subprocess.check_call(["git", "-C", repo, "add", "f.py"], cwd=repo)
        subprocess.check_call(["git", "-C", repo, "commit", "-q", "-m", "change"], cwd=repo)
    else:
        pin = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD~1"], text=True).strip()
    toplevel = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], text=True).strip()
    meta_path = os.path.join(session_dir, "meta.json")
    if os.path.isfile(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
        if meta.get("baseRef"):
            pin = meta["baseRef"]
    meta = {"mode": mode, "baseRef": pin, "baseBranch": "main", "baseFetch": base_fetch,
            "repoRoot": toplevel}
    if write_meta:
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
    diffpath = os.path.join(session_dir, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diffpath), exist_ok=True)
    diff_text = subprocess.check_output(
        ["git", "-C", repo, "diff", "%s...HEAD" % pin], text=True)
    with open(diffpath, "w", encoding="utf-8") as fh:
        fh.write(diff_text)
    out = ["--repo-root", repo]
    if fresh:
        out += ["--diff-path", diffpath]
    return out


def test_journal_and_marker_both_unwritable_raises_unrecordable(tmp_path):
    """#507 WO-FIX-RECOVERY: when the journal AND its fault marker are BOTH unwritable there is no
    silent tier below the marker — `_journal_append` raises JournalFaultUnrecordable rather than
    swallowing (the R2 detectability gap one level down). Both writers fail: the target paths are
    directories, so each `open(..., "a")` raises OSError."""
    d = str(tmp_path)
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))        # journal append → OSError
    os.mkdir(os.path.join(d, RD.JOURNAL_FAULT_FILE))  # fault marker → OSError too
    with pytest.raises(RD.JournalFaultUnrecordable) as ei:
        RD._journal_append(d, {"cmd": "next", "phase": "dispatch-panel"})
    assert ei.value.journal_error is not None and ei.value.marker_error is not None


def test_cli_fails_loud_when_journal_fault_unrecordable(tmp_path, capsys):
    """The CLI invocation itself FAILS (nonzero) with reason `journal-fault-unrecordable` when both
    the journal and its fault marker are unwritable; the underlying errors go to stderr."""
    d = str(tmp_path)
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))
    os.mkdir(os.path.join(d, RD.JOURNAL_FAULT_FILE))
    rc = RD.main(["next", "--session-dir", d])
    assert rc == 1
    cap = capsys.readouterr()
    out = json.loads(cap.out.strip().splitlines()[-1])
    assert out["ok"] is False
    assert out["reason"] == "journal-fault-unrecordable"
    assert cap.err.strip()  # underlying errors reported to stderr


def test_run_loop_parks_cannot_certify_on_unrecordable_journal_fault():
    """#507 WO-FIX-RECOVERY: the library path never continues (or crashes the caller) on an
    unrecordable journal fault — run_loop parks cannot-certify. The last-resort exception is
    injected through a seam to exercise the loop's fail-closed guard."""
    def boom(*a, **k):
        raise RD.JournalFaultUnrecordable(OSError("journal"), OSError("marker"))
    receipt = RD.run_loop(_seams(reviewer=boom), _cfg())
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certification"]["shape"] is None
    assert "journal-fault-unrecordable" in receipt["certification"]["reason"]


# --- replayed-terminal receipt-fault re-check (#507) --------------------------------------------
# A REPLAYED terminal `next` (a `next` on a session already at its terminal step) re-emits the stored
# pending WITHOUT re-running _finalize_receipt — so a receipt fault recorded/surfaced AFTER the first
# emission (a fault marker, or a round-receipt.json corrupted/invalidated since) would be masked by
# the replay's ok. Every terminal `next` — first emission AND replays — now re-verifies the on-disk
# receipt and fails LOUD `receipt-fault` (nonzero) on any fault, never terminal-with-ok.

def _drive_to_terminating_submit(session_dir, cfg, respond, max_steps=80):
    """Drive next/submit until a submit's fold SETS the terminal, then STOP — WITHOUT calling the
    terminal `next`. Leaves the session at terminal with the receipt written by the terminating
    submit, so the caller can exercise the FIRST terminal `next` (e.g. after planting a fault)."""
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL, "reached the terminal `next` before a terminating submit"
        art = respond(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
        if s.get("nextStep") == RD.P_TERMINAL:
            return
    raise AssertionError("no terminating submit within %d steps" % max_steps)


def test_terminal_replay_with_intact_receipt_is_idempotent_ok(tmp_path):
    """A replayed terminal `next` with an intact on-disk receipt stays idempotent — same terminal
    payload, ok — the re-check adds no false alarm on a healthy receipt."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))  # terminal + valid receipt written
    replay = RD.cmd_next(d)
    assert replay["ok"] is True
    assert replay["action"] == RD.P_TERMINAL
    assert replay["payload"]["verdict"] == "converged"
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False)) == 0


def test_terminal_replay_after_receipt_corrupted_on_disk_is_receipt_fault(tmp_path):
    """A replayed terminal `next` re-reads the receipt FRESH: a round-receipt.json corrupted on disk
    since the first emission is caught (not masked by the replay's ok) → nonzero receipt-fault."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        fh.write("{ this is no longer valid json")
    replay = RD.cmd_next(d)
    assert replay["ok"] is False
    assert replay["reason"] == "receipt-fault"
    assert "unreadable" in replay["detail"]
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False)) == 1


def test_terminal_replay_with_fault_marker_is_receipt_fault(tmp_path):
    """A replayed terminal `next` re-checks the durable journal-fault marker too — a fault recorded
    after the first emission is caught → nonzero receipt-fault, never masked by the replay."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))
    RD._mark_journal_fault(d, {"cmd": "submit", "phase": "run-verify"}, OSError("disk full"))
    rc = RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False))
    assert rc == 1
    out = RD.cmd_next(d)
    assert out["ok"] is False
    assert out["reason"] == "receipt-fault"
    assert "journal" in out["detail"]


def test_first_terminal_emission_with_preexisting_fault_marker_is_receipt_fault(tmp_path):
    """No ordering hole: a fault marker present BEFORE the FIRST terminal `next` (planted after the
    terminating submit finalized) is caught by the terminal `next` re-verify → nonzero receipt-fault,
    not masked by the re-emit."""
    d = str(tmp_path)
    _drive_to_terminating_submit(d, _cfg(), _responder(round1_findings=None))
    RD._mark_journal_fault(d, {"cmd": "submit", "phase": "run-verify"}, OSError("disk full"))
    rc = RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False))
    assert rc == 1
    out = RD.cmd_next(d)
    assert out["ok"] is False
    assert out["reason"] == "receipt-fault"
    assert "journal" in out["detail"]


def test_replay_next_after_failed_terminating_submit_stays_receipt_fault(tmp_path):
    """The codex-audit path: a receipt fault produced at the TERMINATING SUBMIT (here the receipt
    write itself fails) must be DURABLE — a later replayed `next` must NOT re-write the receipt from
    state and answer ok. Once finalized-with-fault, every subsequent invocation re-verifies from disk
    and keeps answering receipt-fault (nonzero), even after the transient write condition clears."""
    d = str(tmp_path)
    cfg = _cfg()
    respond = _responder(round1_findings=None)
    term = None
    first = True
    for _ in range(80):
        n = RD.cmd_next(d, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL
        art = respond(n["phase"], n["payload"], n["round"])
        block = os.path.join(d, RD.RECEIPT_FILE)
        os.mkdir(block)  # os.replace onto a directory fails → the receipt WRITE OSErrors
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        os.rmdir(block)  # transient condition clears — a re-write WOULD now succeed (masking vector)
        if not s["ok"]:
            term = s
            break
    assert term is not None, "no terminating submit reached"
    assert term["reason"] == "receipt-fault"  # the terminating submit failed to write the receipt
    # a replayed `next` must NOT silently re-write the receipt from state and answer ok.
    replay = RD.cmd_next(d)
    assert replay["ok"] is False
    assert replay["reason"] == "receipt-fault"
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d, fresh=False)) == 1
    assert RD.cmd_next(d)["reason"] == "receipt-fault"  # and again


def test_receipt_carries_audit_provenance_per_round(tmp_path):
    """The manifest-keyed audit-provenance boundary (LEDGERS §3) is visible in the receipt: a round
    that ran fix audits records `auditProvenance: collection-manifest`, and validate_receipt accepts
    the field (build_receipt must project it, not leave it recorded in state only)."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(
        round1_findings=[{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]))
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    provs = [r.get("auditProvenance") for r in receipt["rounds"]]
    assert "collection-manifest" in provs, provs
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


# --- CLASS: every terminal-phase answer routes through the receipt gate (#507, third audit) --------
# The invariant: NO terminal-phase invocation may answer ok without a fresh on-disk receipt
# verification — first-emission next, replayed next, terminating submit, AND duplicate submit replay.

def _drive_capturing_terminating_submit(session_dir, plant_fault, max_steps=80):
    """Drive to the terminating submit and return (submit_args, submit_response). `submit_args` is the
    (phase, attempt, hash, artifact) tuple of the submit that reached terminal — replay it for the
    duplicate-submit path. When `plant_fault`, a durable journal fault marker is planted before every
    submit so the terminal receipt verifies FAULTED (inert on non-terminal submits — no finalize
    runs there; caught by the terminating submit's finalize)."""
    cfg = _cfg()
    respond = _responder(round1_findings=None)
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL
        art = respond(n["phase"], n["payload"], n["round"])
        args = (n["phase"], n["attempt"], n["expectedStateHash"], art)
        if plant_fault:
            RD._mark_journal_fault(session_dir, {"cmd": "submit", "phase": n["phase"]},
                                   OSError("disk full"))
        s = RD.cmd_submit(session_dir, *args)
        terminated = s.get("nextStep") == RD.P_TERMINAL or \
            (not s.get("ok") and s.get("reason") == "receipt-fault")
        if terminated:
            return args, s
    raise AssertionError("no terminating submit reached")


def _path_terminating_submit(d, plant_fault):
    _args, s = _drive_capturing_terminating_submit(d, plant_fault)
    return s


def _path_first_terminal_next(d, plant_fault):
    _drive_capturing_terminating_submit(d, plant_fault)
    return RD.cmd_next(d)


def _path_replayed_next(d, plant_fault):
    _drive_capturing_terminating_submit(d, plant_fault)
    RD.cmd_next(d)             # first terminal `next`
    return RD.cmd_next(d)      # the replay


def _path_duplicate_submit(d, plant_fault):
    args, _s = _drive_capturing_terminating_submit(d, plant_fault)
    return RD.cmd_submit(d, *args)  # re-send the terminating submit → duplicate replay


_TERMINAL_PATHS = [
    pytest.param(_path_terminating_submit, id="terminating-submit"),
    pytest.param(_path_first_terminal_next, id="first-terminal-next"),
    pytest.param(_path_replayed_next, id="replayed-next"),
    pytest.param(_path_duplicate_submit, id="duplicate-submit-replay"),
]


@pytest.mark.parametrize("path", _TERMINAL_PATHS)
def test_terminal_phase_answer_ok_on_intact_receipt(tmp_path, path):
    """Intact receipt → every terminal-phase answer path returns ok (the gate adds no false alarm)."""
    resp = path(str(tmp_path), plant_fault=False)
    assert resp["ok"] is True, resp


@pytest.mark.parametrize("path", _TERMINAL_PATHS)
def test_terminal_phase_answer_receipt_fault_on_persisted_fault(tmp_path, path):
    """Persisted fault → EVERY terminal-phase answer path (including the duplicate-submit replay)
    fails loud receipt-fault, never a masked ok — the CLASS the third audit demanded."""
    resp = path(str(tmp_path), plant_fault=True)
    assert resp["ok"] is False, resp
    assert resp["reason"] == "receipt-fault", resp


def test_duplicate_terminating_submit_fault_preserves_duplicate_flag_and_exits_nonzero(tmp_path):
    """The duplicate-submit replay at a persisted fault answers receipt-fault with the duplicate flag
    preserved (in the response AND the detail for honesty), and the CLI exits nonzero."""
    d = str(tmp_path)
    args, first = _drive_capturing_terminating_submit(d, plant_fault=True)
    assert first["ok"] is False and first["reason"] == "receipt-fault"
    phase, attempt, shash, artifact = args
    dup = RD.cmd_submit(d, *args)
    assert dup["ok"] is False
    assert dup["reason"] == "receipt-fault"
    assert dup["duplicate"] is True
    assert "duplicate" in dup["detail"]
    # nonzero exit through the CLI (submit via main, artifact from a file).
    art_path = os.path.join(d, "artifact.json")
    with open(art_path, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh)
    rc = RD.main(["submit", "--session-dir", d, "--phase", phase, "--attempt", str(attempt),
                  "--state-hash", shash, "--artifact", art_path])
    assert rc == 1


def test_changed_subjects_accumulate_across_delta_rounds_for_crosscut():
    """#507 R2 residual-5: cross-cutting rework accumulates across MULTIPLE post-panel delta fixes.
    Three delta fixes of one subject each cumulate to 3 distinct subjects → cross-cutting, even
    though no single fix is broad (the latest-only read under-fired)."""
    import review_round_policy as RRP
    state = RD.new_state(_cfg())
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    assert state["_changedSubjectsSincePanel"] == []
    for subj in (["Security"], ["Code"], ["Test"]):
        state["round"] = 2
        RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD},
                       lambda r, h, a, _s=subj: _s)
    assert sorted(state["_changedSubjectsSincePanel"]) == ["Code", "Security", "Test"]
    assert RRP.is_cross_cutting(state["_changedSubjectsSincePanel"]) is True


def test_panel_resets_accumulator_and_baseline_fix_excluded():
    """A full panel resets the cross-cutting accumulator (a broad fix BEFORE it does not count as the
    panel's rework), and a round-1 BASELINE fix never accumulates (it is not confirmation rework)."""
    # a broad ROUND-1 baseline fix is excluded
    state = RD.new_state(_cfg())
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    state["round"] = 1
    RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD},
                   lambda r, h, a: ["Code", "Security", "Test"])
    assert state["_changedSubjectsSincePanel"] == []
    # a broad delta fix accumulates, then a later panel resets it
    state["round"] = 2
    RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD},
                   lambda r, h, a: ["Code", "Security", "Test"])
    assert sorted(state["_changedSubjectsSincePanel"]) == ["Code", "Security", "Test"]
    state["round"] = 3
    RD._fold_panel(state, state["config"], {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}})
    assert state["_changedSubjectsSincePanel"] == []


def test_fold_audits_authenticates_against_recorded_auditor(tmp_path):
    """#507 R2 residual-6: _fold_audits passes the DRIVER-recorded auditor map, so a clearing result
    echoing the FIXER vendor (a self-audit) is rejected not-discharged — the claimant echo never
    authenticates, and the recorded auditor is the trusted driver value."""
    state = RD.new_state(_cfg())  # vendors claude+codex, fixer claude → the auditor is codex
    state["round"] = 2
    state["fixBatch"] = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    assert tgt["auditorVendor"] == "codex"
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "discharged", "reason": "self-clear",
         "auditorVendor": "claude"}]})  # echoes the FIXER, not the recorded codex
    assert state["_auditOutcome"]["unauthenticated"] == [tgt["id"]]
    assert state["_auditOutcome"]["discharged"] == []


def test_judgment_dispositions_distinct_for_same_title_different_lines():
    """#507 R2 v5: two same-title tradeoff blockers at DIFFERENT lines get DISTINCT disposition ids,
    so a skip for the one never collides onto the other (the line-less id collapsed them)."""
    a = {"title": "same choice", "severity": "Important", "file": "f.py", "line": 10,
         "tradeoff": True}
    b = {"title": "same choice", "severity": "Important", "file": "f.py", "line": 20,
         "tradeoff": True}
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(a), dict(b)])
    step = RD._advance(state, state["config"])
    ids = [f["id"] for f in step["payload"]["findings"]]
    assert len(set(ids)) == 2, ids
    id_a, id_b = ids
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": id_a, "disposition": "fix-as-suggested"},
        {"id": id_b, "disposition": "skip", "reason": "defer the line-20 choice"}]})
    assert state["step"] == RD.P_FIXER
    assert [f["line"] for f in state["_fixBatch"]] == [10]
    assert [s["line"] for s in state["_skippedBlockers"]] == [20]


def test_fixer_vendor_flag_rejects_unknown_and_wires_fresh(tmp_path):
    """#507 R2 v4: --fixer-vendor sets the ACTUAL fixer so the auditor is seated as a DIFFERENT
    vendor. An unknown vendor or a non-fresh state fails loud (nonzero), never a silent default."""
    d = str(tmp_path)
    assert RD.main(["next", "--session-dir", d, "--fixer-vendor", "nope"]) == 1
    assert RD.main(["next", "--session-dir", d, "--fixer-vendor", "codex",
                    "--vendors", "codex,cursor"] + _guard_argv(d)) == 0
    ok, state = RD.load_state(d)
    assert ok and state["config"]["fixerVendor"] == "codex"
    # non-fresh: a later --fixer-vendor cannot take effect → rejected loud
    assert RD.main(["next", "--session-dir", d, "--fixer-vendor", "cursor"]) == 1


def test_receipt_missing_seat_surfaces_unverified(tmp_path):
    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "security-reviewer":
            return {"findings": [{"title": "leak", "severity": "Important",
                                  "file": "f.py", "line": 1}],
                    "receiptMissing": True}
        return []

    receipt = RD.run_loop(_seams(reviewer=reviewer,
                                 verifier=lambda cl, rnd: [{"id": i, "verdict": "PLAUSIBLE"}
                                                           for c in (cl or []) for i in c.get("ids", [])]),
                          _cfg())
    r1 = [x for x in receipt["rounds"] if x["round"] == 1][0]
    assert r1["unverified"], "a receipt-missing seat's findings ride the record as unverified"


# =============================================================================
# author-justification POST-filter
# =============================================================================

def test_author_justification_post_filter():
    findings = [
        {"id": "v0", "file": "f.py", "line": 10, "title": "confirmed", "severity": "Important",
         "verdict": "CONFIRMED", "evidence": "e"},
        {"id": "v1", "file": "f.py", "line": 20, "title": "plausible", "severity": "Minor",
         "verdict": "PLAUSIBLE"},
        {"id": "v2", "file": "f.py", "line": 30, "title": "noverdict", "severity": "Important"},
        {"id": "v3", "file": "f.py", "line": 40, "title": "bare", "severity": "Minor",
         "verdict": "PLAUSIBLE"},
    ]
    prior = [
        {"file": "f.py", "line": 10, "body": "Intentional per the caching ADR-7; see the doc."},
        {"file": "f.py", "line": 20, "body": "Deliberate: linter rule disabled repo-wide by policy."},
        {"file": "f.py", "line": 30, "body": "Known longstanding decision documented in the wiki."},
        {"file": "f.py", "line": 40, "body": "wontfix"},  # too short → not substantive
    ]
    kept, drops = RD.author_justification_filter(findings, prior)
    kept_ids = {f["id"] for f in kept}
    # CONFIRMED survives, stamped author-justified.
    assert "v0" in kept_ids
    assert next(f for f in kept if f["id"] == "v0")["challenge"] == "author-justified"
    # non-CONFIRMED with a substantive justification is dropped, justification quoted.
    assert [d["id"] for d in drops] == ["v1"]
    assert drops[0]["justification"]
    # a no-verdict finding is never dropped.
    assert "v2" in kept_ids
    # a non-substantive justification does not drop.
    assert "v3" in kept_ids


# =============================================================================
# receipt validator
# =============================================================================

def test_validate_receipt_round_trip_and_rejections(tmp_path):
    receipt = RD.run_loop(_seams(), _cfg())
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason
    # missing scriptRan rejected.
    missing_scriptran = dict(receipt)
    del missing_scriptran["scriptRan"]
    ok2, why2 = RD.validate_receipt(missing_scriptran)
    assert ok2 is False and "scriptRan" in why2
    # missing seat map rejected.
    missing_seatmap = dict(receipt)
    del missing_seatmap["seatMap"]
    ok3, why3 = RD.validate_receipt(missing_seatmap)
    assert ok3 is False and "seatMap" in why3
    # a non-dict receipt is rejected, never raises.
    assert RD.validate_receipt(None)[0] is False


# =============================================================================
# verify-gate fail halts; mechanical compile
# =============================================================================

def test_verify_fail_halts(tmp_path):
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "fail"), _cfg())
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None


def test_verify_timeout_halts(tmp_path):
    """#507 v10: a verify result that is not `pass`/skip — here `timeout` — fails closed to a halt,
    never advancing into a delta round that could certify."""
    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        verify_runner=lambda cmd, rnd: "timeout"), _cfg())
    assert receipt["verdict"] == "halted"
    assert receipt["certificationShape"] is None


def test_omitted_panel_seat_cannot_certify_full_panel(tmp_path):
    """#507 v11: a configured dimension with NO seat in the panel artifact is a silent coverage gap
    → status `missing`, surfaced, and the clean finish can never be full-panel-confirmed."""
    def reviewer(dim, tier, rnd, ctx):
        if dim == "premortem-reviewer":
            return None  # omitted seat
        return []

    receipt = RD.run_loop(_seams(reviewer=reviewer), _cfg())
    assert receipt["certificationShape"] != "full-panel-confirmed"
    r1 = [x for x in receipt["rounds"] if x["round"] == 1][0]
    assert r1["seatStatus"]["premortem-reviewer"] == "missing"


def test_mechanical_compile_drops_uncited_and_out_of_scope():
    findings = [
        {"title": "cited", "severity": "Important", "file": "f.py", "line": 2},   # in diff scope
        {"title": "uncited", "severity": "Important", "file": None, "line": None},  # citation drop
        {"title": "off-scope", "severity": "Important", "file": "f.py", "line": 999},  # scope drop
    ]
    compiled, drops = RD.mechanical_compile(findings, DIFF)
    titles = {f.get("title") for f in compiled}
    assert "cited" in titles
    assert "uncited" not in titles and "off-scope" not in titles
    reasons = {d["reason"] for d in drops}
    assert any("uncited" in r for r in reasons)
    assert any("scope" in r for r in reasons)


def test_mechanical_compile_keeps_distinct_lines_same_title():
    """#507 v5: two findings sharing a title at DIFFERENT lines are distinct blockers and BOTH
    survive — the per-location anchor (file, line, title) no longer collapses them the way the
    line-less file::title identity did (it dropped the second line's blocker)."""
    findings = [
        {"title": "Same bug", "severity": "Important", "file": "f.py", "line": 1},
        {"title": "Same bug", "severity": "Important", "file": "f.py", "line": 2},
    ]
    compiled, _ = RD.mechanical_compile(findings, DIFF)
    assert sorted(f.get("line") for f in compiled) == [1, 2]


def test_mechanical_compile_nit_cap():
    findings = [{"title": "nit%d" % i, "severity": "Nit", "file": "f.py", "line": 1}
                for i in range(9)]
    compiled, _ = RD.mechanical_compile(findings, None)
    nits = [f for f in compiled if f.get("severity") == "Nit"]
    # 5 kept + 1 summary entry.
    assert sum(1 for f in nits if not f.get("summaryEntry")) <= RD._NIT_CAP
    assert any(f.get("summaryEntry") for f in nits)


def test_mechanical_compile_normalizes_list_dimension():
    findings = [
        {"title": "hole", "severity": "Important", "file": "f.py", "line": 2,
         "dimension": ["security", "perf"]},
    ]
    compiled, drops = RD.mechanical_compile(findings, DIFF)
    assert drops == []
    assert len(compiled) == 1
    assert compiled[0]["dimension"] == "security + perf"


def test_settle_delta_list_dimension_via_mechanical_compile(tmp_path):
    """#583: list-valued dimension must not crash _settle_delta's dim_map grouping."""
    raw = [{"title": "hole", "severity": "Important", "file": "f.py", "line": 2,
            "dimension": ["security", "perf"]}]
    compiled, _ = RD.mechanical_compile(raw, DIFF)
    state = _delta_state_ready(confirmations=0, surfaced=[], findings=compiled)
    RD._settle_delta(state, state["config"])
    record = (state.get("_records") or [])[-1]
    dim_map = record.get("dimensions") or {}
    assert dim_map
    assert all(isinstance(k, str) for k in dim_map)
    assert "security + perf" in dim_map


# =============================================================================
# the REDISPATCH_BUDGET single home (code-leg re-dispatch bound)
# =============================================================================

def test_reviewer_redispatch_bounded_by_single_home_budget(tmp_path):
    """A persistently receipt-missing reviewer is re-dispatched exactly REDISPATCH_BUDGET times,
    then recorded terminal `missing` (findings carried unverified). The budget read goes through
    loop_plan_common.REDISPATCH_BUDGET — the single home."""
    assert RD.REDISPATCH_BUDGET == LPC.REDISPATCH_BUDGET
    calls = {"n": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "code-reviewer" and rnd == 1:
            calls["n"] += 1
            return {"findings": [], "receiptMissing": True}
        return []

    RD.run_loop(_seams(reviewer=reviewer), _cfg())
    # 1 initial dispatch + REDISPATCH_BUDGET re-dispatches for the persistently-missing seat.
    assert calls["n"] == 1 + RD.REDISPATCH_BUDGET


# =============================================================================
# #507 WO-D: challenged-coverage breaker + resume/records seam
# =============================================================================

_CHALLENGED_FINDING = {"title": "coverage decision is false", "severity": "Important",
                       "file": "f.py", "line": 1, "dimension": "Test", "taxonomy": "coverage",
                       "classKey": "Test::coverage::x"}


def test_challenged_coverage_recurrence_cannot_certify(tmp_path):
    """A coverage decision recorded on a principle the reviewer keeps raising (challenged) whose
    class RECURS parks (cannot-certify) — never a silent clean (the wrong_principle property)."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")
    coverage = tmp_path / "coverage.json"

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-reviewer":
            return {"findings": [dict(_CHALLENGED_FINDING)]}
        if dim == "scoped-finder":
            return [dict(_CHALLENGED_FINDING)]
        return []

    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Test"],
                "coverageDecisions": [{"id": "RCD-x", "classKey": "Test::coverage::x"}]}

    receipt = RD.run_loop(
        _seams(reviewer=reviewer, fix_step=fix_step),
        _cfg(dimensions=["test-reviewer"], recordsPath=str(records),
             coveragePath=str(coverage), maxRounds=20))
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None
    assert any(d["kind"] == "cannot-certify" for d in receipt["decisions"])


def test_plain_recurring_finding_without_challenge_is_not_challenged_halt(tmp_path):
    """A recurring finding WITHOUT a challenged coverage decision is NOT parked by the challenged
    breaker (the driver's delta/audit path owns that case) — only the challenged path halts here."""
    records = tmp_path / "round-records.json"
    records.write_text("[]")

    fired = {"scoped": 0}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "test-reviewer":
            return {"findings": [dict(_CHALLENGED_FINDING)]}
        if dim == "scoped-finder" and fired["scoped"] == 0:
            fired["scoped"] += 1
            return [dict(_CHALLENGED_FINDING)]
        return []

    # No coverageDecisions recorded → the recurring class is never "challenged". The fix's head diff
    # carries a real new surface so the scoped finder legitimately fires and re-raises the finding.
    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": HEAD_NEW_SURFACE, "changedSubjects": ["Test"]}

    receipt = RD.run_loop(
        _seams(reviewer=reviewer, fix_step=fix_step),
        _cfg(dimensions=["test-reviewer"], recordsPath=str(records), maxRounds=20))
    assert receipt["verdict"] != "cannot-certify"
    assert fired["scoped"] == 1, "the scoped finder must fire over the real new surface"


def test_corrupt_resume_records_cannot_certify(tmp_path):
    """A corrupt durable round-records file fails closed in the resume seam — cannot-certify park,
    never a run off unreadable memory."""
    records = tmp_path / "round-records.json"
    records.write_text("{corrupt not-a-list")
    receipt = RD.run_loop(_seams(), _cfg(recordsPath=str(records)))
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None


def test_resume_degraded_confirmation_runs_fresh_panel(tmp_path):
    """Resuming with a seeded DEGRADED (low-confidence) confirmation panel + a pending-confirmation
    marker owes a fresh full confirmation panel — the degraded seed cannot anchor certification."""
    records = tmp_path / "round-records.json"
    seed = [
        {"schemaVersion": 2, "round": 1, "kind": "baseline", "confirmationPending": True,
         "dimensions": {"test-reviewer": {"status": "run", "confidence": "high",
                                          "tier": "reviewer-deep", "findings": []}},
         "findings": [], "coverageDecisions": []},
        {"schemaVersion": 2, "round": 2, "kind": "confirmation", "confirmationPending": True,
         "dimensions": {"test-reviewer": {"status": "run", "confidence": "low",
                                          "tier": "reviewer-deep", "findings": []}},
         "findings": [], "coverageDecisions": []},
    ]
    records.write_text(json.dumps(seed))
    receipt = RD.run_loop(_seams(), _cfg(dimensions=["test-reviewer"], recordsPath=str(records)))
    assert receipt["verdict"] == "converged"
    # A fresh full confirmation panel ran at the resume round (3), certifying as a full panel —
    # NOT anchored on the degraded round-2 seed.
    assert receipt["certificationShape"] == "full-panel-confirmed"
    assert any(r["round"] == 3 for r in receipt["rounds"])
    assert any(d["kind"] == "resume-confirmation" for d in receipt["decisions"])


# =============================================================================
# git-derived changed subjects (#507 finding v2) — the confirmation re-arm's
# cross-cutting input is SCRIPT-computed from git, never the fixer's self-report
# =============================================================================

def _file_diff(name, n_lines, idx="1..2"):
    """A single-file unified diff adding `n_lines` right-side lines (parseable header)."""
    return ("diff --git a/{f} b/{f}\nindex {i} 100644\n--- a/{f}\n+++ b/{f}\n"
            "@@ -1 +1,{n} @@\n-old\n".format(f=name, i=idx, n=n_lines)
            + "".join("+l%d\n" % j for j in range(n_lines)))


def test_derive_changed_subjects_crosscutting_three_subjects():
    """Three files' sections differ between the reviewed diff and the head diff; the accumulated
    findings attribute them to three distinct policy subjects → cross-cutting (re-arm)."""
    reviewed = _file_diff("a.py", 2) + _file_diff("b.py", 2) + _file_diff("c.py", 2)
    head = _file_diff("a.py", 3) + _file_diff("b.py", 3) + _file_diff("c.py", 3)
    findings = [
        {"file": "a.py", "dimension": "Security"},
        {"file": "b.py", "dimension": "Code"},
        {"file": "c.py", "dimension": "Test"},
    ]
    subjects = RD.derive_changed_subjects(reviewed, head, findings)
    assert subjects == ["Code", "Security", "Test"]
    assert RD.review_round_policy.is_cross_cutting(subjects) is True


def test_derive_changed_subjects_narrow_single_subject_not_crosscutting():
    """One file changed, one subject → below the cross-cutting threshold (no re-arm)."""
    reviewed = _file_diff("a.py", 2)
    head = _file_diff("a.py", 3)
    findings = [{"file": "a.py", "dimension": "Code"}]
    subjects = RD.derive_changed_subjects(reviewed, head, findings)
    assert subjects == ["Code"]
    assert RD.review_round_policy.is_cross_cutting(subjects) is False


def test_derive_changed_subjects_unparseable_is_unknown_runs_everything():
    """A quoted-path / unparseable diff header → None (unknown surface). Unknown fails toward the
    run-everything rule: is_cross_cutting treats it as cross-cutting (one more confirmation)."""
    garbage = 'diff --git "a/x y.py" "b/x y.py"\n@@ -1 +1 @@\n-a\n+b\n'
    subjects = RD.derive_changed_subjects(garbage, _file_diff("a.py", 3),
                                          [{"file": "a.py", "dimension": "Code"}])
    assert subjects is None
    assert RD.review_round_policy.is_cross_cutting(subjects) is True


def test_fold_fixer_derives_subjects_from_git_not_self_report():
    """The fixer LIES (self-reports one narrow subject); the driver derives the real cross-cutting
    set from the reviewed-vs-head diff through the accumulated findings, ignoring the self-report."""
    state = RD.new_state(_cfg())
    state["reviewedDiff"] = (_file_diff("a.py", 2) + _file_diff("b.py", 2)
                             + _file_diff("c.py", 2))
    state["findings"] = [
        {"file": "a.py", "dimension": "Security"},
        {"file": "b.py", "dimension": "Code"},
        {"file": "c.py", "dimension": "Test"},
    ]
    head = _file_diff("a.py", 3) + _file_diff("b.py", 3) + _file_diff("c.py", 3)
    artifact = {"fixes": [], "headDiff": head, "changedSubjects": ["Code"]}
    RD._fold_fixer(state, state["config"], artifact)
    assert state["_changedSubjects"] == ["Code", "Security", "Test"]


def test_run_loop_uses_injected_changed_subjects_seam(tmp_path):
    """run_loop routes the derivation through the injected `changed_subjects` seam (the eval-harness
    pattern). A seam that returns a cross-cutting set re-arms a confirmation even though the fixer's
    self-report and the synthetic diff are narrow — proving the self-report is never consulted."""
    calls = []

    def changed_subjects(reviewed, head, accumulated):
        calls.append((reviewed, head, accumulated))
        return ["Security", "Code", "Test"]

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important",
                                  "file": "f.py", "line": 1}]}
        return []

    seams = _seams(reviewer=reviewer)
    seams["changed_subjects"] = changed_subjects
    receipt = RD.run_loop(seams, _cfg(maxRounds=20))
    assert calls  # the seam was invoked (the self-report was never consulted)
    assert any(d["kind"] == "confirmation-rearm" for d in receipt["decisions"])


# =============================================================================
# #648 — CLI base guard (`next` only)
# =============================================================================

def _guard_repo_sha(session_dir):
    repo = os.path.join(session_dir, "_gitrepo")
    return subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()


def _cli_next_json(session_dir, extra_argv, capsys):
    rc = RD.main(["next", "--session-dir", session_dir] + list(extra_argv))
    cap = capsys.readouterr()
    lines = [ln for ln in cap.out.strip().splitlines() if ln.strip()]
    out = json.loads(lines[-1]) if lines else {}
    return rc, out


def test_base_guard_fresh_next_threads_pin(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    assert ok and state["config"]["baseRef"] == pin


def test_base_guard_no_meta_refuses_no_state(tmp_path, capsys):
    d = str(tmp_path)
    repo = os.path.join(d, "_gitrepo")
    os.makedirs(repo, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    diffpath = os.path.join(d, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diffpath), exist_ok=True)
    with open(diffpath, "w", encoding="utf-8") as fh:
        fh.write(DIFF)
    rc, out = _cli_next_json(d, ["--repo-root", repo, "--diff-path", diffpath], capsys)
    assert rc == 1 and out["reason"] == "base-meta-unreadable"
    ok, state = RD.load_state(d)
    assert ok and state is None


@pytest.mark.parametrize("base_ref", ["", "null", "main"])
def test_base_guard_unpinned_refuses(tmp_path, capsys, base_ref):
    d = str(tmp_path)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = base_ref
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-not-pinned"


def test_base_guard_unresolved_sha_refuses(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = "0" * 40
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-unresolved"


def test_base_guard_round_diff_required(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    ga = [x for x in ga if x != "--diff-path" and not x.endswith("diff.txt")]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-required"


def test_base_guard_round_diff_missing_file(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    ga[-1] = os.path.join(d, "no-such-diff.txt")
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-unreadable"


def test_base_guard_round_diff_empty(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    empty = os.path.join(d, "empty.txt")
    with open(empty, "w", encoding="utf-8") as fh:
        pass
    ga[-1] = empty
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-empty"


def test_base_guard_round_diff_whitespace_only(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    ws = os.path.join(d, "ws.txt")
    with open(ws, "w", encoding="utf-8") as fh:
        fh.write("   \n\t\n")
    ga[-1] = ws
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-empty"


def test_base_guard_pin_moved_refuses(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    stored = state["config"]["baseRef"]
    repo = os.path.join(d, "_gitrepo")
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "two"], cwd=repo)
    sha2 = _guard_repo_sha(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = sha2
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc2, out2 = _cli_next_json(d, _guard_argv(d, fresh=False), capsys)
    assert rc2 == 1 and out2["reason"] == "base-pin-moved"
    ok2, state2 = RD.load_state(d)
    assert state2["config"]["baseRef"] == stored


def test_base_guard_diff_path_on_non_fresh_refuses(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, _ = _cli_next_json(d, ga, capsys)
    assert rc == 0
    rc2, out2 = _cli_next_json(d, ga, capsys)
    assert rc2 == 1 and out2["reason"] == "diff-path-not-fresh-state"


def test_base_guard_pr_repo_mismatch(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d, mode="pr")
    repo = os.path.join(d, "_gitrepo")
    subprocess.check_call(["git", "remote", "add", "origin", "git@github.com:acme/widget.git"],
                          cwd=repo)
    with open(os.path.join(d, "pr.json"), "w", encoding="utf-8") as fh:
        json.dump({"url": "https://github.com/otherorg/widget/pull/7"}, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-repo-mismatch"


def test_base_guard_pr_repo_match(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d, mode="pr")
    repo = os.path.join(d, "_gitrepo")
    subprocess.check_call(["git", "remote", "add", "origin", "git@github.com:acme/widget.git"],
                          cwd=repo)
    with open(os.path.join(d, "pr.json"), "w", encoding="utf-8") as fh:
        json.dump({"url": "https://github.com/acme/widget/pull/7"}, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    assert state["config"]["baseRepoCheck"] == "matched"


def test_base_guard_refusal_is_journalled(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["baseRef"] = ""
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    _cli_next_json(d, ga, capsys)
    journal = RD.read_journal(d)
    assert any(e.get("outcome") == "refused-base-guard" and e.get("reason") == "base-not-pinned"
               for e in journal)


def test_base_guard_receipt_carries_base_block(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["base"]["baseRef"] == pin
    assert receipt["baseGuard"] == "checked-stat-bound"
    assert receipt["base"]["diffBinding"] == "file-set+line-counts"
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


def test_base_guard_wrong_base_diff_refuses_no_state(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    repo = os.path.join(d, "_gitrepo")
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    good = subprocess.check_output(["git", "-C", repo, "diff", "%s...HEAD" % pin], text=True)
    bad = os.path.join(d, "wrong-diff.txt")
    extra = (
        "\ndiff --git a/extra b/extra\nnew file mode 100644\n--- /dev/null\n+++ b/extra\n"
        "@@ -0,0 +1 @@\n+contam\n"
    )
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write(good + extra)
    ga = [x if not x.endswith("diff.txt") else bad for x in ga]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-base-mismatch"
    ok, state = RD.load_state(d)
    assert ok and state is None


def test_base_guard_healthy_next_stat_bound_receipt(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d) + ["--vendors", "codex,cursor"]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    pin = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["baseRef"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["baseGuard"] == "checked-stat-bound"
    assert receipt["base"]["diffBinding"] == "file-set+line-counts"
    assert receipt["certification"]["base"] == "fetched"
    assert not receipt["certificationShape"].endswith("-degraded")


def _guard_cli_to_terminal_receipt(d, capsys, guard_kwargs=None, next_extra=None):
    gkw = dict(guard_kwargs or {})
    ga = _guard_argv(d, **gkw)
    if next_extra:
        ga = ga + list(next_extra)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"], out
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def test_base_degraded_fetch_failed_cert_shape(tmp_path, capsys):
    d = str(tmp_path)
    bf = "fetch-failed (offline)"
    # Two-vendor pool is load-bearing: default single-vendor independence degradation
    # would satisfy -degraded even if base degradation were dropped from _cert_shape.
    receipt = _guard_cli_to_terminal_receipt(
        d, capsys, {"base_fetch": bf},
        next_extra=["--vendors", "codex,cursor"],
    )
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"].endswith("-degraded")
    assert receipt["certificationShape"].count("-degraded") == 1
    assert receipt["certification"]["independence"] == "independent"
    assert receipt["certification"]["base"] == "degraded"
    assert any("fetch-failed (offline)" in line for line in receipt["degraded"])


def test_base_degraded_absent_base_fetch(tmp_path, capsys):
    d = str(tmp_path)
    _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta.pop("baseFetch", None)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    repo = os.path.join(d, "_gitrepo")
    diffpath = os.path.join(d, "round-1", "diff.txt")
    ga = ["--repo-root", repo, "--diff-path", diffpath]
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 0 and out["ok"]
    for _ in range(80):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        art = _responder(round1_findings=None)(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["certification"]["base"] == "degraded"
    assert any("baseFetch absent" in line for line in receipt["degraded"])


def test_base_and_independence_both_degraded_one_suffix(tmp_path, capsys):
    d = str(tmp_path)
    receipt = _guard_cli_to_terminal_receipt(
        d, capsys, {"base_fetch": "fetch-failed (offline)"})
    assert receipt["certificationShape"].endswith("-degraded")
    assert receipt["certificationShape"].count("-degraded") == 1
    assert receipt["certification"]["independence"] == "degraded"
    assert receipt["certification"]["base"] == "degraded"


def test_base_degraded_does_not_false_claim_independence(tmp_path, capsys):
    d = str(tmp_path)
    receipt = _guard_cli_to_terminal_receipt(
        d, capsys,
        {"base_fetch": "fetch-failed (offline)"},
        next_extra=["--vendors", "codex,cursor"],
    )
    assert receipt["certificationShape"].endswith("-degraded")
    assert receipt["certification"]["independence"] == "independent"
    assert receipt["certification"]["base"] == "degraded"


def _panel_seat_map_with_same_family(seat="code-reviewer"):
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["degradations"] = [{
        "constraint": "same-family",
        "seat": seat,
        "reason": "seat %s seated the maker family claude — no alternative family is live" % seat,
    }]
    return seat_map


def test_same_family_seat_map_degrades_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    seat_map_clean = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    receipt_clean = RD.run_loop(_seams(io={"seatMap": seat_map_clean}), cfg)
    assert receipt_clean["verdict"] == "converged"
    assert "-degraded" not in receipt_clean["certificationShape"]
    seat_map_deg = _panel_seat_map_with_same_family()
    receipt_deg = RD.run_loop(_seams(io={"seatMap": seat_map_deg}), cfg)
    assert receipt_deg["verdict"] == "converged"
    assert receipt_deg["certificationShape"] == receipt_clean["certificationShape"] + "-degraded"
    assert receipt_deg["certificationShape"].count("-degraded") == 1


def test_same_family_disclosed_in_receipt_degraded_list():
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    state["seatMap"] = _panel_seat_map_with_same_family("security-reviewer")
    state["terminal"] = "converged"
    state["certification"] = {"shape": "full-panel-confirmed-degraded", "independence": "independent",
                              "base": "not-checked"}
    receipt = RD.build_receipt(state)
    sf_lines = [d for d in receipt["degraded"] if d.startswith("panel independence:")]
    assert len(sf_lines) == 1
    assert "security-reviewer" in sf_lines[0]


def test_same_family_malformed_seat_map_is_safe():
    for sm in (None, {}, {"degradations": "not-a-list"},
               {"degradations": [None, 42, {"constraint": "other"}]}):
        state = {"seatMap": sm}
        assert RD._same_family_degraded(state) is False
        assert RD._same_family_seats(state) == []
    state_missing_seat = {"seatMap": {"degradations": [{"constraint": "same-family"}]}}
    assert RD._same_family_degraded(state_missing_seat) is True
    assert RD._same_family_seats(state_missing_seat) == ["unnamed-seat"]
    state_missing_seat["terminal"] = "converged"
    state_missing_seat["config"] = {}
    receipt = RD.build_receipt(state_missing_seat)
    assert any("unnamed-seat" in line for line in receipt["degraded"])


def test_same_family_does_not_clear_other_degradations():
    state = RD.new_state(_cfg(vendors=["claude"]))
    state["independenceDegraded"] = True
    state["seatMap"] = _panel_seat_map_with_same_family()
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert state["certification"]["independence"] == "degraded"
    receipt = RD.build_receipt(state)
    indep_lines = [d for d in receipt["degraded"] if d.startswith("independence:")]
    sf_lines = [d for d in receipt["degraded"] if d.startswith("panel independence:")]
    assert len(indep_lines) == 1
    assert len(sf_lines) == 1


def _seat_map_receipt_with_unexcused_maker_family():
    """Hand-built receipt-shaped map: all-claude panel (no canary gap) + unexcused breach."""
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["violations"] = [{"constraint": "maker-family", "seat": "code-reviewer"}]
    seat_map["degradations"] = []
    return seat_map


def test_seat_map_unexcused_violation_constraint_violated_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    SM = _load("seat_map")
    assert SM.unexcused_violations(seat_map)
    receipt = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"].endswith("-constraint-violated")
    assert "-degraded" not in receipt["certificationShape"]
    assert receipt["certificationShape"].count("-constraint-violated") == 1


def test_seat_map_excused_only_violation_unchanged_cert_shape():
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state_clean = RD.new_state(cfg)
    RD._terminal_converged(state_clean, cfg, full_panel=True)
    shape_clean = state_clean["certification"]["shape"]
    SM = _load("seat_map")
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0)
    seat_map_excused = SM.to_receipt(m, "anthropic")
    state_excused = RD.new_state(cfg)
    state_excused["seatMap"] = seat_map_excused
    RD._terminal_converged(state_excused, cfg, full_panel=True)
    assert state_excused["certification"]["shape"] == shape_clean
    assert "-constraint-violated" not in state_excused["certification"]["shape"]


def test_seat_map_pin_excusal_degraded_shape_and_disclosure():
    SM = _load("seat_map")
    seats = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seats["violations"] = [{"constraint": "strong-tier", "seat": "security-reviewer"}]
    seats["liveVendors"] = ["claude", "codex", "cursor"]
    seats["livenessPinScoped"] = False
    seats["authorFamily"] = "xai"
    seats["seats"]["security-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "pinned",
    }
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state = RD.new_state(cfg)
    state["seatMap"] = seats
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-degraded")
    assert "seat-pin" in state["certification"]["shapeDrivers"]
    receipt = RD.build_receipt(state)
    pin_lines = [d for d in receipt["degraded"] if d.startswith("seat-map pin excusal:")]
    assert len(pin_lines) == 1
    assert "security-reviewer" in pin_lines[0]
    assert SM.classify_violations(seats)["excusedByPin"]


def test_seat_map_unproven_liveness_shape_driver():
    SM = _load("seat_map")
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["violations"] = [{"constraint": "critical-diversity"}]
    seat_map["liveVendors"] = ["claude", "codex"]
    seat_map["authorFamily"] = "anthropic"
    assert SM.unexcused_violations(seat_map)[0].get("evidence") == "unproven-liveness"
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    state = RD.new_state(cfg)
    state["seatMap"] = seat_map
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert "unproven-liveness" in state["certification"]["shapeDrivers"]
    assert state["certification"]["shape"].endswith("-constraint-violated")


def test_certification_shape_drivers_lists_every_fired_channel():
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    seat_map = dict(seat_map)
    seat_map["degradations"] = list(seat_map.get("degradations") or []) + [{
        "constraint": "same-family",
        "seat": "code-reviewer",
        "reason": "test",
    }]
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    cfg["baseDegraded"] = True
    state = RD.new_state(cfg)
    state["independenceDegraded"] = True
    state["seatMap"] = seat_map
    RD._terminal_converged(state, state["config"], full_panel=True)
    drivers = state["certification"]["shapeDrivers"]
    assert drivers == ["base", "independence", "same-family", "seat-map-violation"]
    assert state["certification"]["shape"].endswith("-constraint-violated")
    assert state["certification"]["shape"].count("-degraded") == 0


def test_seat_map_violations_round_field_and_degraded_disclosure():
    seat_map = _seat_map_receipt_with_unexcused_maker_family()
    cfg = _cfg(leg="panel", vendors=["codex", "cursor"])
    receipt = RD.run_loop(_seams(io={"seatMap": seat_map}), cfg)
    r1 = receipt["rounds"][0]
    assert r1.get("seatMapViolations")
    viol_lines = [d for d in receipt["degraded"] if "constraint-violated" in d]
    assert len(viol_lines) == 1
    assert "maker-family" in viol_lines[0]


def test_seat_map_violations_e8_sticky_across_round_map_overwrite():
    seat_map_r1 = _seat_map_receipt_with_unexcused_maker_family()
    SM = _load("seat_map")
    clean = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    clean["violations"] = []
    clean["degradations"] = []
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    state["rounds"] = {
        "1": {"seatMapViolations": SM.unexcused_violations(seat_map_r1)},
    }
    state["seatMap"] = clean
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["certification"]["shape"].endswith("-constraint-violated")


def test_library_receipt_omits_base_not_checked(tmp_path):
    receipt = RD.run_loop(_seams(), _cfg())
    assert "base" not in receipt
    assert receipt["baseGuard"] == "not-checked"
    assert receipt["certification"]["base"] == "not-checked"
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


def test_library_receipt_mode_without_cli_guard_stays_not_checked(tmp_path):
    """Guard-shaped config keys must not infer baseGuard=checked without the CLI guard."""
    receipt = RD.run_loop(_seams(), _cfg(mode="pr"))
    assert receipt["baseGuard"] == "not-checked"
    if "base" in receipt:
        assert receipt["baseGuard"] == "not-checked"


def test_certification_base_explicit_not_checked_token(tmp_path):
    state = {"config": {"baseGuard": "not-checked", "baseDegraded": False}}
    assert RD._certification_base(state) == "not-checked"


def test_base_guard_round_diff_malformed(tmp_path, capsys):
    d = str(tmp_path)
    ga = _guard_argv(d)
    bad = os.path.join(d, "bad.txt")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("fatal: bad revision 'null'\n")
    ga[-1] = bad
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "round-diff-malformed"


def test_base_guard_repo_root_mismatch(tmp_path, capsys):
    d = str(tmp_path)
    other = os.path.join(d, "other-checkout")
    os.makedirs(other, exist_ok=True)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=other)
    ga = _guard_argv(d)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta["repoRoot"] = subprocess.check_output(
        ["git", "-C", other, "rev-parse", "--show-toplevel"], text=True).strip()
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    rc, out = _cli_next_json(d, ga, capsys)
    assert rc == 1 and out["reason"] == "base-repo-root-mismatch"


def test_base_guard_terminal_replay_still_ok(tmp_path, capsys):
    """Lifecycle: a satisfied guard on replay must not disturb terminal replay."""
    d = str(tmp_path)
    _drive_cli(d, _cfg(), _responder(round1_findings=None))
    rc, out = _cli_next_json(d, _guard_argv(d, fresh=False), capsys)
    assert rc == 0 and out["ok"] and out["action"] == RD.P_TERMINAL


def test_v1_state_wins_over_base_guard(tmp_path, capsys):
    d = str(tmp_path)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {}}, fh)
    rc, out = _cli_next_json(d, [], capsys)
    assert rc == 0 and out["ok"] is False and "fresh session dir" in out["reason"]


# =============================================================================
# #507 R1c — `--vendors` must fail LOUD, never fall through to the ["claude"] default
#
# A non-JSON `--vendors` (e.g. `codex,cursor`) used to hit json.loads's ValueError → `pass` → the
# fresh state silently kept the single-vendor default, so every audit selected the fixer's own
# vendor and stamped `degraded` — cross-vendor independence lost silently when two vendors are live.
# =============================================================================

def _run_main(argv, capsys):
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


def test_vendors_comma_form_accepted(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", " codex , cursor "]
                        + _guard_argv(d), capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    assert ok and state["config"]["vendors"] == ["codex", "cursor"]
    # a two-vendor pool → the audit is independent, NOT the silent single-vendor degrade.
    assert state["independenceDegraded"] is False


def test_vendors_json_form_accepted(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", '["codex","cursor"]']
                        + _guard_argv(d), capsys)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(d)
    assert ok and state["config"]["vendors"] == ["codex", "cursor"]


def test_vendors_garbage_fails_loud_no_state(tmp_path, capsys):
    """Unparseable JSON (bracket form) → nonzero + `vendors-unparseable`, and NO state is written
    (never the old silent fall-through to a fresh single-vendor default)."""
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", '["codex"'], capsys)
    assert rc == 1 and out["ok"] is False and out["reason"] == "vendors-unparseable"
    ok, state = RD.load_state(d)
    assert ok and state is None  # nothing was created


def test_vendors_non_string_member_fails_loud(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", '["codex", 5]'], capsys)
    assert rc == 1 and out["reason"] == "vendors-unparseable"


def test_vendors_empty_result_fails_loud(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", " , "], capsys)
    assert rc == 1 and out["reason"] == "vendors-unparseable"


def test_vendors_unknown_fails_loud(tmp_path, capsys):
    d = str(tmp_path)
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", "codex,acme"], capsys)
    assert rc == 1 and out["reason"] == "vendors-unknown: acme"


def test_vendors_on_existing_state_rejected(tmp_path, capsys):
    """`--vendors` on non-fresh state cannot take effect (config is read once at new_state) — reject
    loudly rather than silently ignore the flag."""
    d = str(tmp_path)
    rc0, _ = _run_main(["next", "--session-dir", d, "--vendors", "codex,cursor"]
                        + _guard_argv(d), capsys)
    assert rc0 == 0
    rc, out = _run_main(["next", "--session-dir", d, "--vendors", "claude,codex"], capsys)
    assert rc == 1 and out["reason"] == "vendors-not-fresh-state"
    # the original pool is untouched
    ok, state = RD.load_state(d)
    assert state["config"]["vendors"] == ["codex", "cursor"]


def test_auditor_vendor_fixer_in_pool_is_independent():
    """Two-vendor pool, fixerVendor IN the pool → the auditor is the OTHER pool vendor, independent."""
    auditor, independence = RD._auditor_vendor({"vendors": ["claude", "codex"]}, "claude")
    assert auditor == "codex" and independence == "independent"


def test_auditor_vendor_fixer_outside_pool_is_independent():
    """#507 R1c: fixerVendor OUTSIDE the pool still yields an independent auditor — the first pool
    vendor, never the fixer. Pins the outside-pool branch explicitly."""
    auditor, independence = RD._auditor_vendor({"vendors": ["codex", "cursor"]}, "claude")
    assert auditor == "codex" and auditor != "claude" and independence == "independent"


def test_auditor_vendor_family_keyed_two_vendor_cross_family():
    """Family-keyed independence: openai != anthropic preserves cross-vendor selection."""
    assert RD._auditor_vendor({"vendors": ["claude", "codex"]}, "claude") == ("codex", "independent")


def test_auditor_vendor_family_keyed_single_vendor_same_family_degraded():
    """Single live vendor with same fixer/verifier family → degraded, never false independent."""
    assert RD._auditor_vendor({"vendors": ["claude"]}, "claude") == ("claude", "degraded")


# The #510-era `test_auditor_vendor_family_keyed_single_vendor_cross_family_independent` lived here.
# It asserted that a cursor-only env is cross-family (composer='cursor' vs grok='xai') and therefore
# independent. #651 (owner-ratified 2026-07-26) merged both cursor first-party models into the `xai`
# family, so that env is now same-family and DEGRADED. Its replacement —
# `test_cursor_fix_never_gets_an_independent_cursor_auditor`, at the end of this file — asserts the
# new expectation AND the cross-family branches the old test did not cover. One thing did go with
# it: that test was the only one reaching `_auditor_vendor`'s SECOND (same-vendor) loop on its
# `independent` return, and post-#651 no vendor can satisfy that branch — every vendor's
# `code-fixer` and `verifier` roles now resolve to the same family — so it is unreachable, not
# merely untested. #652 rider 4a deleted that loop; the invariant is pinned by
# test_verifier_and_code_fixer_families_match_per_vendor in test_model_registry.py.


def test_auditor_vendor_unknown_fixer_degraded():
    """#608: genuinely-unknown fixer vendor never yields a false-independent auditor stamp."""
    auditor, independence = RD._auditor_vendor({"vendors": ["claude", "codex"]}, None)
    assert auditor == "claude" and independence == "degraded"


def test_auditor_vendor_empty_string_fixer_degraded():
    """#608: empty-string fixer is unknown — same degraded path as None."""
    assert RD._auditor_vendor({"vendors": ["claude", "codex"]}, "")[1] == "degraded"


def test_auditor_vendor_family_keyed_pass1_prefers_different_cli():
    """Pass 1 picks a different CLI vendor for a cursor fix. Post-#651 the same-CLI candidate (grok)
    is same-family too, so codex is the only independent choice — pass 1 and pass 2 now agree here."""
    assert RD._auditor_vendor({"vendors": ["cursor", "codex"]}, "cursor") == ("codex", "independent")


def test_fixer_outside_pool_audits_independent_end_to_end(tmp_path):
    """The outside-pool independence threads through the whole loop to a non-degraded audited chain."""
    captured = {"targets": None}

    def auditor(targets, rnd):
        captured["targets"] = [dict(t) for t in (targets or [])]
        return [{"id": t["id"], "ruling": "discharged", "reason": "ok", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in (targets or [])]

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
             if rnd == 1 and dim == "code-reviewer" else []),
        auditor=auditor), _cfg(vendors=["codex", "cursor"], fixerVendor="claude"))
    assert receipt["verdict"] == "converged"
    t = captured["targets"][0]
    assert t["fixerVendor"] == "claude"
    assert t["auditorVendor"] == "codex" and t["auditorVendor"] != t["fixerVendor"]
    assert t["independence"] == "independent"


# =============================================================================
# the judgment gate is an INTERVENTION, not a terminal (#507 R2a)
# =============================================================================

_TRADEOFF = {"title": "widen the API", "severity": "Important",
             "file": "f.py", "line": 1, "tradeoff": True}
# The judgment disposition key is the per-LOCATION id (line-less finding_identity + line) so two
# same-title tradeoff blockers at different lines never collide (#507 R2 v5).
_TRADEOFF_ID = "f.py::widen the api@L1"


def test_tradeoff_blocker_routes_to_judgment_not_stall():
    """A tradeoff/product-choice blocker routes to the present-judgment gate — NEVER the terminal
    stall menu (the R2a defect: the stall menu dead-ended it so it could never be fixed)."""
    state = RD.new_state(_cfg())
    took = RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    assert took is True
    assert state["step"] == RD.P_JUDGMENT and state["step"] != RD.P_STALL
    step = RD._advance(state, state["config"])
    assert step["action"] == RD.P_JUDGMENT
    fnd = step["payload"]["findings"]
    assert len(fnd) == 1 and fnd[0]["id"] == _TRADEOFF_ID
    assert fnd[0]["dispositions"] == list(RD.JUDGMENT_DISPOSITIONS)
    kinds = [d["kind"] for d in state["decisions"]]
    assert "judgment-gate" in kinds


def test_fix_as_suggested_folds_to_fixer_batch():
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"],
                      {"dispositions": [{"id": _TRADEOFF_ID, "disposition": "fix-as-suggested"}]})
    assert state["step"] == RD.P_FIXER
    batch = state["_fixBatch"]
    assert len(batch) == 1 and batch[0]["title"] == "widen the API"
    assert batch[0]["judgmentDisposition"] == "fix-as-suggested"


def test_fix_with_guidance_attaches_guidance():
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-with-guidance",
         "guidance": "keep it backward compatible"}]})
    assert state["step"] == RD.P_FIXER
    b = state["_fixBatch"][0]
    assert b["judgmentDisposition"] == "fix-with-guidance"
    assert b["guidance"] == "keep it backward compatible"


def test_skip_with_reason_records_ledger_and_rides_disclosure():
    """A skip needs a citable reason: it lands in the decision ledger, rides the exit disclosure AND
    the dedicated top-level `skippedBlockers` channel. With nothing left to fix, the run converges —
    but CLEAN EXCEPT FOR SKIPPED, never a plain success (the reason leads with clean-except-skipped)."""
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "shipping v1 narrow on purpose"}]})
    assert state["terminal"] == "converged"
    kinds = [d["kind"] for d in state["decisions"]]
    assert "judgment-skip" in kinds
    # the certification is non-plain: shape unchanged (audited-chain) but the reason leads with
    # the exit_skipped invariant marker.
    cert = state.get("certification") or {}
    assert cert.get("shape") == "audited-chain"
    assert (cert.get("reason") or "").startswith("clean-except-skipped: 1 blocker(s) skipped")
    assert "owner-skipped" in (cert.get("note") or "")
    receipt = RD.build_receipt(state)
    # top-level dedicated channel — id/title/severity/reason
    assert receipt["skippedBlockers"] == [
        {"id": _TRADEOFF_ID, "title": "widen the API", "severity": "Important",
         "reason": "shipping v1 narrow on purpose"}]
    # AND the degraded disclosure prose still names it
    assert any("skipped-blocker" in dd and "shipping v1 narrow" in dd
               for dd in receipt["degraded"])
    ok, _ = RD.validate_receipt(receipt)
    assert ok


def test_receipt_always_carries_skipped_blockers_channel():
    """Every terminal receipt carries the `skippedBlockers` list (empty when no skip) and
    validate_receipt REQUIRES it — the channel can never be omitted (exit_skipped invariant)."""
    receipt = RD.run_loop(_seams(), _cfg())
    assert receipt["verdict"] == "converged"
    assert receipt["skippedBlockers"] == []
    ok, _ = RD.validate_receipt(receipt)
    assert ok
    # a receipt with the channel stripped is rejected
    stripped = dict(receipt)
    del stripped["skippedBlockers"]
    ok2, why = RD.validate_receipt(stripped)
    assert not ok2 and "skippedBlockers" in why
    # a non-list channel is rejected too
    bad = dict(receipt)
    bad["skippedBlockers"] = None
    ok3, why3 = RD.validate_receipt(bad)
    assert not ok3 and "skippedBlockers" in why3


def test_partial_skip_end_to_end_marks_clean_except_skipped(tmp_path):
    """A run that fixes one judgment finding and skips another converges CLEAN EXCEPT FOR SKIPPED:
    the skipped one rides the top-level channel and the certification reason leads with the marker,
    even though real fix-and-audit work ran."""
    trade_a = {"title": "widen the API", "severity": "Important",
               "file": "f.py", "line": 1, "tradeoff": True}
    trade_b = {"title": "drop the flag", "severity": "Important",
               "file": "f.py", "line": 2, "tradeoff": True}

    def judgment_gate(payload):
        out = []
        for f in payload["findings"]:
            if f["id"] == "f.py::widen the api@L1":
                out.append({"id": f["id"], "disposition": "fix-as-suggested"})
            else:
                out.append({"id": f["id"], "disposition": "skip", "reason": "deferred to v2"})
        return {"dispositions": out}

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [dict(trade_a), dict(trade_b)]}
             if rnd == 1 and dim == "code-reviewer" else []),
        io={"judgment_gate": judgment_gate}), _cfg())
    assert receipt["verdict"] == "converged"
    assert [s["title"] for s in receipt["skippedBlockers"]] == ["drop the flag"]
    reason = (receipt["certification"] or {}).get("reason") or ""
    assert reason.startswith("clean-except-skipped: 1 blocker(s) skipped")
    ok, _ = RD.validate_receipt(receipt)
    assert ok


def test_skip_without_reason_fails_closed_to_fix():
    """A skip with no citable reason is NOT honored — it fails closed to fix-as-suggested (a judgment
    blocker is never silently skipped)."""
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip"}]})
    assert state["step"] == RD.P_FIXER
    assert state["_fixBatch"][0]["judgmentFailClosed"] is True
    assert "judgment-fail-closed" in [d["kind"] for d in state["decisions"]]


def test_missing_or_unknown_disposition_fails_closed_to_fix():
    """A listed judgment finding with a MISSING disposition (or an UNKNOWN one) folds as
    fix-as-suggested, flagged failClosed — never silently skipped."""
    # missing: the artifact lists no disposition at all
    s1 = RD.new_state(_cfg())
    RD._route_judgment_blockers(s1, [dict(_TRADEOFF)])
    RD._fold_judgment(s1, s1["config"], {"dispositions": []})
    assert s1["step"] == RD.P_FIXER
    b1 = s1["_fixBatch"][0]
    assert b1["judgmentDisposition"] == "fix-as-suggested" and b1["judgmentFailClosed"] is True
    # unknown: a disposition string the gate does not recognize
    s2 = RD.new_state(_cfg())
    RD._route_judgment_blockers(s2, [dict(_TRADEOFF)])
    RD._fold_judgment(s2, s2["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "ship-it-anyway"}]})
    assert s2["step"] == RD.P_FIXER
    assert s2["_fixBatch"][0]["judgmentFailClosed"] is True


def test_mechanical_blocker_carried_through_judgment_gate():
    """A mechanical (non-tradeoff) blocker in the SAME batch is carried through the gate and rides
    the fix batch even when the tradeoff finding is skipped — never abandoned at the gate."""
    mech = {"title": "null deref", "severity": "Critical", "file": "f.py", "line": 2}
    state = RD.new_state(_cfg())
    took = RD._route_judgment_blockers(state, [mech, dict(_TRADEOFF)])
    assert took is True and state["step"] == RD.P_JUDGMENT
    # only the tradeoff finding is presented for judgment
    step = RD._advance(state, state["config"])
    assert [x["id"] for x in step["payload"]["findings"]] == [_TRADEOFF_ID]
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "deferred to v2"}]})
    assert state["step"] == RD.P_FIXER
    assert [b["title"] for b in state["_fixBatch"]] == ["null deref"]


def test_stall_menu_payload_carries_no_judgment_findings():
    """The stall menu is the audit-stall TERMINAL only — its payload never carries judgment
    findings (they route to present-judgment)."""
    state = RD.new_state(_cfg())
    state["findings"] = [{"id": "v0", "verdict": "PLAUSIBLE"}]
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], {"reason": "audit-stall", "detail": "x",
                                              "stalledIdentities": ["v0"]})
    assert state["step"] == RD.P_STALL
    step = RD._advance(state, state["config"])
    assert set(step["payload"].keys()) == {"choices", "acceptRiskEligible"}
    assert "judgmentFindings" not in step["payload"]


def test_migrate_old_stall_routed_judgment_state(tmp_path):
    """#507 R2a migration: a state persisted under the OLD routing (a judgment blocker parked at the
    present-stall-menu terminal) is re-pointed to present-judgment on load, and `next` re-emits the
    judgment action from state under the new contract (schemaVersion stays 2)."""
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["step"] = RD.P_STALL
    state["_judgmentFindings"] = [dict(_TRADEOFF)]
    state["_stallChoices"] = ["ship-smaller", "spend-more", "hold"]
    state["_acceptRiskEligible"] = False
    state["pending"] = {"action": RD.P_STALL, "round": 1, "phase": RD.P_STALL,
                        "attempt": 0, "payload": {"choices": []}}
    RD.save_state(d, state)
    ok, loaded = RD.load_state(d)
    assert ok and loaded["step"] == RD.P_JUDGMENT and loaded["pending"] is None
    out = RD.cmd_next(d)
    assert out["ok"] and out["action"] == RD.P_JUDGMENT
    assert out["payload"]["findings"][0]["dispositions"] == list(RD.JUDGMENT_DISPOSITIONS)


def test_tradeoff_finding_reaches_audited_chain_end_to_end(tmp_path):
    """End-to-end: one tradeoff blocking finding routes to the judgment gate, the owner disposes it
    fix-as-suggested, and the run fixes-and-audits it to an audited-chain certification — the very
    path the R2a defect made unreachable."""
    disposed = []

    def judgment_gate(payload):
        disposed.append(payload)
        return {"dispositions": [{"id": f["id"], "disposition": "fix-as-suggested"}
                                 for f in payload["findings"]]}

    receipt = RD.run_loop(_seams(
        reviewer=lambda dim, tier, rnd, ctx:
            ({"findings": [dict(_TRADEOFF)]} if rnd == 1 and dim == "code-reviewer" else []),
        io={"judgment_gate": judgment_gate}), _cfg())
    assert len(disposed) == 1 and disposed[0]["findings"][0]["id"] == _TRADEOFF_ID
    assert receipt["verdict"] == "converged"
    assert receipt["certificationShape"] == "audited-chain"
    assert "judgment-gate" in [d["kind"] for d in receipt["decisions"]]
    ok, _ = RD.validate_receipt(receipt)
    assert ok
    assert receipt["certificationShape"] == "audited-chain"  # NOT -degraded


# =============================================================================
# #563 DoD1 — loud fall-open dispatch provenance (machinery)
# =============================================================================

def _seat_map_vendors(vendors):
    return {"seats": {d: {"vendor": v} for d, v in vendors.items()}}


def _all_run_status(dims=None):
    dims = dims or RD.DIMENSIONS
    return {d: "run" for d in dims}


def test_fell_open_rows_codex_configured_claude_ran():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "run"})
    assert rows == [{"seat": "code-reviewer", "configured": "codex", "ran": "claude",
                     "reason": "forfeit-fell-open"}]
    assert miss == []


def test_fell_open_rows_claude_configured_claude_ran_no_row():
    seat_map = _seat_map_vendors({"code-reviewer": "claude"})
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "run"})
    assert rows == [] and miss == []


def test_fell_open_rows_missing_seat_no_row_not_provenance_missing():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    rows, miss = RD._fell_open_rows(
        seat_map, {"code-reviewer": "claude"}, {"code-reviewer": "missing"})
    assert rows == [] and miss == []


def test_fell_open_rows_cross_vendor_no_manifest_provenance_missing():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    rows, miss = RD._fell_open_rows(seat_map, None, {"code-reviewer": "run"})
    assert rows == [] and miss == ["code-reviewer"]


def test_fell_open_rows_partial_manifest_missing_seat():
    seat_map = _seat_map_vendors({"code-reviewer": "codex", "security-reviewer": "cursor"})
    status = {"code-reviewer": "run", "security-reviewer": "run"}
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "codex"}, status)
    assert rows == [] and miss == ["security-reviewer"]


def test_fell_open_rows_malformed_manifest_skipped_no_crash():
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    status = {"code-reviewer": "run"}
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": 123}, status)
    assert rows == [] and miss == ["code-reviewer"]
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "bogus-vendor"}, status)
    assert rows == [] and miss == ["code-reviewer"]
    rows, miss = RD._fell_open_rows(
        seat_map, {"unknown-dimension": "claude", "code-reviewer": "codex"}, status)
    assert rows == [] and miss == []


def test_fell_open_rows_manifest_governs():
    """ranManifest alone decides fell-open rows — varying manifest entries changes the outcome."""
    # Fold-level in-seat ranVendor echo coverage: test_fell_open_in_seat_ran_vendor_echo_ignored_at_fold
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    status = {"code-reviewer": "run"}
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "claude"}, status)
    assert rows and miss == []
    rows, miss = RD._fell_open_rows(seat_map, {"code-reviewer": "codex"}, status)
    assert rows == [] and miss == []


def test_fell_open_rows_absent_manifest_claude_only_no_disclosure_inputs():
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    rows, miss = RD._fell_open_rows(seat_map, None, _all_run_status())
    assert rows == [] and miss == []


def test_fell_open_panel_fold_receipt_disclosure():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "claude"},
    })
    assert state["rounds"]["1"]["fellOpen"] == [
        {"seat": "code-reviewer", "configured": "codex", "ran": "claude", "reason": "forfeit-fell-open"}]
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if "reviewer-fell-open (round 1):" in d]
    assert len(fo_lines) == 1
    assert "code-reviewer" in fo_lines[0]
    assert "codex" in fo_lines[0]
    assert "claude" in fo_lines[0]
    assert receipt["rounds"][0]["fellOpen"]


def test_fell_open_fold_receipt_provenance_unavailable_end_to_end():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {},
    })
    assert state["rounds"]["1"]["fellOpenProvenanceMissing"] == ["code-reviewer"]
    receipt = RD.build_receipt(state)
    prov_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-provenance-unavailable")]
    assert len(prov_lines) == 1
    assert "code-reviewer" in prov_lines[0]


def test_fell_open_fold_receipt_seatmap_unavailable():
    state = RD.new_state(_cfg(leg="panel", vendors=["claude", "codex"]))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats})
    assert state["rounds"]["1"]["seatMapUnavailable"] == ["codex"]
    receipt = RD.build_receipt(state)
    smu_lines = [d for d in receipt["degraded"]
                 if d.startswith("reviewer-fell-open-seatmap-unavailable")]
    assert len(smu_lines) == 1
    assert "codex" in smu_lines[0]


def test_fell_open_in_seat_ran_vendor_echo_ignored_at_fold():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "ranVendor": "claude"}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "codex"},
    })
    assert "fellOpen" not in state["rounds"]["1"]


def test_fell_open_clean_claude_panel_no_manifest_degraded_unchanged(tmp_path):
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    receipt = RD.run_loop(_seams(io={"seatMap": seat_map}), _cfg(leg="panel"))
    assert not any(d.startswith("reviewer-fell-open") for d in receipt["degraded"])
    ok, reason = RD.validate_receipt(receipt)
    assert ok, reason


def test_fell_open_multi_seat_deterministic_disclosure_order():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({
        "architecture-reviewer": "claude",
        "code-reviewer": "codex",
        "security-reviewer": "cursor",
        "test-reviewer": "codex",
        "premortem-reviewer": "cursor",
    })
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {
            "code-reviewer": "claude",
            "security-reviewer": "claude",
        },
    })
    assert state["rounds"]["1"]["fellOpen"] == [
        {"seat": "code-reviewer", "configured": "codex", "ran": "claude",
         "reason": "forfeit-fell-open"},
        {"seat": "security-reviewer", "configured": "cursor", "ran": "claude",
         "reason": "forfeit-fell-open"},
    ]
    assert state["rounds"]["1"]["fellOpenProvenanceMissing"] == [
        "premortem-reviewer", "test-reviewer"]
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if d.startswith("reviewer-fell-open (round")]
    assert len(fo_lines) == 2
    assert "code-reviewer" in fo_lines[0] and "codex" in fo_lines[0] and "claude" in fo_lines[0]
    assert "security-reviewer" in fo_lines[1] and "cursor" in fo_lines[1] and "claude" in fo_lines[1]
    prov_lines = [d for d in receipt["degraded"]
                  if d.startswith("reviewer-fell-open-provenance-unavailable")]
    assert len(prov_lines) == 1
    assert "premortem-reviewer, test-reviewer" in prov_lines[0]


def test_fell_open_two_rounds_deterministic_disclosure_order():
    state = RD.new_state(_cfg(leg="panel"))
    for rnd, dim in [(1, "code-reviewer"), (2, "security-reviewer")]:
        state["round"] = rnd
        seats = {d: {"findings": []} for d in RD.DIMENSIONS}
        seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
        seat_map["seats"][dim] = {"vendor": "codex"}
        RD._fold_panel(state, state["config"], {
            "seats": seats,
            "seatMap": seat_map,
            "ranManifest": {dim: "claude"},
        })
    receipt = RD.build_receipt(state)
    fo_lines = [d for d in receipt["degraded"] if d.startswith("reviewer-fell-open (round")]
    assert len(fo_lines) == 2
    assert "round 1" in fo_lines[0] and "code-reviewer" in fo_lines[0]
    assert "round 2" in fo_lines[1] and "security-reviewer" in fo_lines[1]


# =============================================================================
# #666 / #668 — vacuous seats + cross-vendor canary liveness (#668 cluster WO-4)
# =============================================================================

def _decision_kinds(state):
    return [d["kind"] for d in (state.get("decisions") or [])]


def test_vacuous_seat_vacuous_flag_classed_never_ran():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "vacuous": True}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["rounds"]["1"]["vacuousSeats"] == ["code-reviewer"]
    assert state["fullPanelRan"] is False
    assert "seat-vacuous" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["vacuousSeats"] == ["code-reviewer"]
    vac_lines = [d for d in receipt["degraded"] if d.startswith("vacuous-seat (round 1):")]
    assert len(vac_lines) == 1
    assert "code-reviewer" in vac_lines[0]


def test_forfeited_seat_reason_discriminant_classed_never_ran_not_vacuous():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "reason": "forfeited"}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert "vacuousSeats" not in state["rounds"]["1"]
    assert "seat-vacuous" not in _decision_kinds(state)
    assert state["fullPanelRan"] is False


def test_engaged_artifact_seat_recorded_not_vacuous():
    """axis: seat credit — engaged-artifact seats are not classed vacuous."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {
        "findings": [],
        "reason": "forfeit-with-engaged-artifact",
        "disclosure": "not credited",
    }
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["rounds"]["1"]["engagedArtifactSeats"] == ["code-reviewer"]
    assert "vacuousSeats" not in state["rounds"]["1"]
    assert "seat-engaged-artifact" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["engagedArtifactSeats"] == ["code-reviewer"]
    eng_lines = [d for d in receipt["degraded"] if d.startswith("engaged-artifact-seat (round 1):")]
    assert len(eng_lines) == 1
    assert "code-reviewer" in eng_lines[0]


def test_vacuous_seat_reason_discriminant_classed_never_ran():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [], "reason": "vacuous"}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["rounds"]["1"]["vacuousSeats"] == ["code-reviewer"]
    assert state["fullPanelRan"] is False
    assert "seat-vacuous" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["vacuousSeats"] == ["code-reviewer"]
    vac_lines = [d for d in receipt["degraded"] if d.startswith("vacuous-seat (round 1):")]
    assert len(vac_lines) == 1


def test_clean_claude_panel_empty_findings_not_vacuous():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert "vacuousSeats" not in state["rounds"]["1"]
    assert "seat-vacuous" not in _decision_kinds(state)
    assert state["fullPanelRan"] is True


def test_canary_unverified_when_cross_vendor_all_empty_no_probe():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert state["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is False
    assert state["_incompletePanel"] is True
    assert "canary-unverified" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["canaryUnverified"] == ["code-reviewer"]
    cu_lines = [d for d in receipt["degraded"] if d.startswith("canary-unverified (round 1):")]
    assert len(cu_lines) == 1
    assert "code-reviewer" in cu_lines[0]


def test_canary_failed_downgrades_cross_vendor_seats():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "no engagement",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "missing"
    assert state["fullPanelRan"] is False
    assert "canaryFailed" in state["rounds"]["1"]
    assert "canary-failed" in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    cf_lines = [d for d in receipt["degraded"] if d.startswith("canary-failed (round 1):")]
    assert len(cf_lines) == 1
    assert "code-reviewer" in cf_lines[0]


def test_canary_verified_cross_vendor_empty_stays_run():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 14980}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is True
    assert state["rounds"]["1"]["canaryVerified"] == {"tokens": 14980}
    assert "canary-verified" not in _decision_kinds(state)
    receipt = RD.build_receipt(state)
    assert receipt["rounds"][0]["canaryVerified"] == {"tokens": 14980}
    assert not any("canary-" in d for d in receipt["degraded"])


def test_canary_plant_miss_does_not_block_verification():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {}, "detectedPlant": False, "detail": "live but missed plant",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"
    assert state["fullPanelRan"] is True
    assert "canaryVerified" in state["rounds"]["1"]
    receipt = RD.build_receipt(state)
    assert not any("canary-" in d for d in receipt["degraded"])


def test_canary_per_vendor_codex_finding_cursor_empty_still_unverified():
    """Round-3 Critical: panel-wide emptiness must not suppress another vendor's probe."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [{"title": "issue", "severity": "Minor"}]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert sorted(r1["canaryUnverified"]) == ["security-reviewer"]
    assert "canaryVerified" not in r1
    assert "canaryFailed" not in r1
    assert state["fullPanelRan"] is False
    assert "canary-unverified" in _decision_kinds(state)
    assert "panel-seat-missing" not in _decision_kinds(state)
    assert r1.get("missingSeats") is None or r1.get("missingSeats") == []


def test_canary_not_required_claude_only_empty_panel():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    assert "canaryUnverified" not in state["rounds"]["1"]
    assert "canary-unverified" not in _decision_kinds(state)


def test_canary_mixed_panel_only_codex_probed_cursor_unverified():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 100}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    r1 = state["rounds"]["1"]
    assert sorted(r1["canaryUnverified"]) == ["security-reviewer"]
    assert r1["canaryVerified"] == {"codex": {"tokens": 100}}
    assert r1["seatStatus"]["code-reviewer"] == "run"
    assert r1["seatStatus"]["security-reviewer"] == "run"
    assert state["fullPanelRan"] is False
    assert state["_incompletePanel"] is True
    assert "canaryFailed" not in r1
    receipt = RD.build_receipt(state)
    rr = receipt["rounds"][0]
    assert "canaryUnverified" in rr and "canaryVerified" in rr
    cu = [d for d in receipt["degraded"] if d.startswith("canary-unverified (round 1):")]
    assert len(cu) == 1
    assert "security-reviewer" in cu[0]
    assert not any(d.startswith("canary-failed") for d in receipt["degraded"])


def test_canary_list_two_engaged_probes_full_panel():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    canary = [
        {
            "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "live",
        },
        {
            "engine": "cursor", "model": "c", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 2}, "detectedPlant": False, "detail": "live",
        },
    ]
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    r1 = state["rounds"]["1"]
    assert "canaryUnverified" not in r1
    assert "canaryFailed" not in r1
    assert r1["canaryVerified"] == {"codex": {"tokens": 1}, "cursor": {"tokens": 2}}
    assert state["fullPanelRan"] is True
    assert state["_incompletePanel"] is False
    receipt = RD.build_receipt(state)
    assert not any("canary-" in d for d in receipt["degraded"])


def test_canary_engine_matches_no_panel_vendor_all_unverified():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "cursor", "model": "c", "outcome": "ok", "engaged": True,
        "evidence": {}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    assert state["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
    assert "canaryVerified" not in state["rounds"]["1"]
    assert state["fullPanelRan"] is False


def test_canary_malformed_result_not_dict_or_list():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    for bad in (None, "oops", 42):
        st = RD.new_state(_cfg(leg="panel"))
        RD._fold_panel(st, st["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": bad,
        })
        assert st["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
        assert st["fullPanelRan"] is False


def test_canary_list_ignores_non_dict_members():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map,
        "canaryResult": [None, "x", {
            "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 9}, "detectedPlant": False, "detail": "live",
        }],
    })
    assert state["rounds"]["1"]["canaryVerified"] == {"tokens": 9}
    assert "canaryUnverified" not in state["rounds"]["1"]
    assert state["fullPanelRan"] is True


def test_canary_failed_one_vendor_only_downgrades_that_vendor_seats():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    seat_map["seats"]["test-reviewer"] = {"vendor": "codex"}
    canary = [
        {
            "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
            "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "live",
        },
        {
            "engine": "cursor", "model": "c", "outcome": "vacuous", "engaged": False,
            "evidence": {}, "detectedPlant": False, "detail": "dead",
        },
    ]
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    r1 = state["rounds"]["1"]
    assert r1["seatStatus"]["code-reviewer"] == "run"
    assert r1["seatStatus"]["test-reviewer"] == "run"
    assert r1["seatStatus"]["security-reviewer"] == "missing"
    assert sorted(r1["canaryFailed"]["seats"]) == ["security-reviewer"]
    assert r1["canaryVerified"] == {"codex": {"tokens": 1}}
    assert state["fullPanelRan"] is False


def test_canary_liveness_duplicate_codex_probes_dead_both_orders():
    dims = list(RD.DIMENSIONS)
    seat_map = _seat_map_vendors({d: "claude" for d in dims})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seats = {d: {"findings": []} for d in dims}
    status = {d: "run" for d in dims}
    engaged = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "live",
    }
    failed = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "dead",
    }
    for canary in ([engaged, failed], [failed, engaged]):
        out = RD.canary_liveness(dims, status, seats, seat_map, {}, canary)
        assert out["byVendor"]["codex"]["status"] == "dead"
        assert out["byDim"]["code-reviewer"] == "dead"


def test_canary_codex_configured_cursor_ran_needs_cursor_probe():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "cursor"},
    })
    assert state["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]


def test_canary_failed_record_includes_evidence():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0, "toolCalls": 0}, "detectedPlant": False, "detail": "no engagement",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    cf = state["rounds"]["1"]["canaryFailed"]
    assert cf["evidence"] == {"tokens": 0, "toolCalls": 0}
    assert cf["detail"] == "no engagement"


def test_canary_only_unverified_no_panel_seat_missing_decision():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert "canaryUnverified" in r1
    assert "panel-seat-missing" not in _decision_kinds(state)
    assert r1.get("missingSeats") is None or r1.get("missingSeats") == []


def test_fold_panel_malformed_reason_list_or_dict_classed_missing_no_raise():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    for bad_reason in (["forfeited"], {"code": "forfeited"}):
        st = RD.new_state(_cfg(leg="panel"))
        s = dict(seats)
        s["code-reviewer"] = {"findings": [], "reason": bad_reason}
        RD._fold_panel(st, st["config"], {"seats": s, "seatMap": seat_map})
        assert st["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"


def test_canary_liveness_no_in_scope_vendors_empty_by_vendor():
    dims = list(RD.DIMENSIONS)
    seat_map = _seat_map_vendors({d: "claude" for d in dims})
    out = RD.canary_liveness(dims, {d: "run" for d in dims}, {}, seat_map, {}, None)
    assert out["byVendor"] == {}
    assert all(out["byDim"].get(d) == "n/a" for d in dims)


def test_canary_mixed_panel_receipt_does_not_claim_no_probe_ran():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seat_map["seats"]["security-reviewer"] = {"vendor": "cursor"}
    canary = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 100}, "detectedPlant": False, "detail": "live",
    }
    RD._fold_panel(state, state["config"], {
        "seats": seats, "seatMap": seat_map, "canaryResult": canary,
    })
    receipt = RD.build_receipt(state)
    cu = [d for d in receipt["degraded"] if d.startswith("canary-unverified (round 1):")]
    assert len(cu) == 1
    line = cu[0].lower()
    assert "security-reviewer" in cu[0]
    assert "no control probe was run" not in line
    assert "every cross-vendor seat" not in line


def test_canary_fell_open_codex_configured_claude_ran_not_subject():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {
        "seats": seats,
        "seatMap": seat_map,
        "ranManifest": {"code-reviewer": "claude"},
    })
    r1 = state["rounds"]["1"]
    assert "canaryUnverified" not in r1
    assert "canaryVerified" not in r1
    assert "canaryFailed" not in r1
    assert "canary-unverified" not in _decision_kinds(state)
    assert state["fullPanelRan"] is True


def _codex_cross_vendor_canary_inputs(findings):
    dims = list(RD.DIMENSIONS)
    seat_map = _seat_map_vendors({d: "claude" for d in dims})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    seats = {d: {"findings": []} for d in dims}
    seats["code-reviewer"] = {"findings": findings}
    status = {d: "run" for d in dims}
    return dims, status, seats, seat_map


@pytest.mark.parametrize("findings,expected_dim_status", [
    ([None], "unproven"),
    ("garbage", "unproven"),
    ([None, {"title": "x"}], "n/a"),
    ([{}], "n/a"),
    ([], "unproven"),
])
def test_canary_liveness_usable_findings_only_dicts_count(findings, expected_dim_status):
    dims, status, seats, seat_map = _codex_cross_vendor_canary_inputs(
        findings if isinstance(findings, list) else [])
    seats["code-reviewer"] = {"findings": findings}
    out = RD.canary_liveness(dims, status, seats, seat_map, {}, None)
    assert out["byDim"]["code-reviewer"] == expected_dim_status


def test_fold_panel_null_finding_cross_vendor_unverified_not_full_panel():
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [None]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    r1 = state["rounds"]["1"]
    assert r1["canaryUnverified"] == ["code-reviewer"]
    assert state["fullPanelRan"] is False
    assert "canary-unverified" in _decision_kinds(state)


def test_fold_panel_null_finding_review_record_dim_findings_match_fold():
    """Per-dimension review record must use _usable_findings, not raw seat.findings."""
    state = RD.new_state(_cfg(leg="panel"))
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [None]}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})
    dim_map = state["_records"][-1]["dimensions"]
    assert dim_map["code-reviewer"]["findings"] == []


@pytest.mark.parametrize("dimensions", [
    1,
    [["code-reviewer"]],
    None,
    ["code-reviewer", 42],
])
def test_canary_liveness_malformed_dimensions_no_raise(dimensions):
    seat_map = _seat_map_vendors({"code-reviewer": "codex"})
    out = RD.canary_liveness(
        dimensions, {"code-reviewer": "run"},
        {"code-reviewer": {"findings": []}}, seat_map, {}, None)
    assert isinstance(out, dict) and "byDim" in out and "byVendor" in out


def test_fold_panel_malformed_config_dimensions_no_raise():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    for bad_dims in (1, [["code-reviewer"]], None, ["code-reviewer", 42]):
        st = RD.new_state(_cfg(leg="panel", dimensions=bad_dims))
        RD._fold_panel(st, st["config"], {"seats": seats, "seatMap": seat_map})
        assert st["rounds"]["1"]["canaryUnverified"] == ["code-reviewer"]
        assert st["fullPanelRan"] is False


def test_canary_verified_record_stable_two_engaged_probe_orders():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    probe_a = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 1}, "detectedPlant": False, "detail": "alpha",
    }
    probe_b = {
        "engine": "codex", "model": "gpt", "outcome": "ok", "engaged": True,
        "evidence": {"tokens": 2}, "detectedPlant": False, "detail": "beta",
    }
    records = []
    for canary in ([probe_a, probe_b], [probe_b, probe_a]):
        st = RD.new_state(_cfg(leg="panel"))
        RD._fold_panel(st, st["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": canary,
        })
        records.append(st["rounds"]["1"]["canaryVerified"])
    assert records[0] == records[1]


def test_canary_failed_record_stable_two_failing_probe_orders():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex"}
    probe_a = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 0}, "detectedPlant": False, "detail": "alpha",
    }
    probe_b = {
        "engine": "codex", "model": "gpt", "outcome": "vacuous", "engaged": False,
        "evidence": {"tokens": 9}, "detectedPlant": False, "detail": "beta",
    }
    records = []
    for canary in ([probe_a, probe_b], [probe_b, probe_a]):
        st = RD.new_state(_cfg(leg="panel"))
        RD._fold_panel(st, st["config"], {
            "seats": seats, "seatMap": seat_map, "canaryResult": canary,
        })
        records.append(st["rounds"]["1"]["canaryFailed"])
    assert records[0] == records[1]


_RETIRED_RUN_CONFIG_KEYS = ("docMode", "fixerModel", "fixerEffort")
_ROUND_DRIVER_PATH = os.path.join(_LIB, "round_driver.py")


def test_run_config_retired_keys_census():
    """Unreachable run-config keys must not reappear as config reads in round_driver."""
    cfg_keys = set(RD._default_config().keys())
    retired_in_defaults = cfg_keys & set(_RETIRED_RUN_CONFIG_KEYS)
    assert not retired_in_defaults, (
        "retired keys in _default_config: %s" % sorted(retired_in_defaults))
    with open(_ROUND_DRIVER_PATH, encoding="utf-8") as fh:
        source = fh.read()
    violations = []
    for key in _RETIRED_RUN_CONFIG_KEYS:
        if re.search(
                r'\b(?:config|cfg)(?:\.get\([\'"]%s[\'"](?:\)|,)|\[[\'"]%s[\'"]\])'
                % (re.escape(key), re.escape(key)),
                source):
            violations.append(key)
    assert not violations, (
        "retired run-config keys read in round_driver.py: %s" % violations)


def test_cursor_fix_never_gets_an_independent_cursor_auditor():
    """#651: composer and grok are ONE family, so a cursor-only panel auditing a cursor fix is
    DEGRADED, never independent. Under the old registry (composer='cursor', grok='xai') the
    same-vendor fallback loop returned ('cursor', 'independent') — a self-audit labelled
    independent. This pins that lane closed while leaving the real cross-family path intact."""
    vendor, independence = RD._auditor_vendor({"vendors": ["cursor"]}, "cursor")
    assert independence == "degraded"
    assert vendor == "cursor"
    for other in ("claude", "codex"):
        v, ind = RD._auditor_vendor({"vendors": [other, "cursor"]}, "cursor")
        assert ind == "independent", (other, v, ind)
        assert v == other
