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
        return [{"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                 "evidence": "tests pass"} for t in (targets or [])]

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
            return {"results": [{"id": t["id"], "ruling": audit, "reason": "r", "evidence": "e"}
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
