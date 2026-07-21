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
            return {"results": [{"id": t["id"], "ruling": audit, "reason": "r", "evidence": "e",
                                 "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])]}
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
        return {"fixes": [], "headDiff": _headf(counter["n"]), "changedSubjects": ["Code"]}

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


def test_audit_result_from_wrong_vendor_is_not_discharged(tmp_path):
    """#507 v2 (audits): a clearing ruling that does NOT echo the selected independent auditor
    (fixer or a misrouted worker) is rejected as not-discharged and disclosed as unauthenticated,
    so it can never certify a fix the independent auditor did not clear."""
    import audits
    target = {"id": "v0", "file": "f.py", "line": 1, "title": "bug", "severity": "Important",
              "fixerVendor": "claude", "auditorVendor": "codex", "independence": "independent"}
    # the fixer vendor tries to self-clear
    out = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "trust me",
                    "auditorVendor": "claude"}])
    assert out["discharged"] == []
    assert out["notDischarged"] == ["v0"]
    assert out["unauthenticated"] == ["v0"]
    # the correct independent auditor clears it
    ok = audits.apply_audit_results(
        [target], [{"id": "v0", "ruling": "discharged", "reason": "fix verified",
                    "auditorVendor": "codex"}])
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
        return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Test"],
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

    # No coverageDecisions recorded → the recurring class is never "challenged".
    receipt = RD.run_loop(
        _seams(reviewer=reviewer), _cfg(dimensions=["test-reviewer"],
                                        recordsPath=str(records), maxRounds=20))
    assert receipt["verdict"] != "cannot-certify"


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
