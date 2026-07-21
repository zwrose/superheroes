"""Tests for `spec_loop_plan` — review-spec's script-owned round scheduler + continuation
gate (#164).

The point (same as `loop_state`): the convergence levers — which dimensions re-run each
round, at what tier, and whether a reduced round may exit — are decided by a script, not
by the orchestrator. These tests pin:
  - delegation to the parity-locked shared policy (`review_round_policy.plan_round`) so the
    prose path and the spine share ONE scheduler implementation;
  - the executed-evidence gate (a stale or missing findings file never counts as clean);
  - the escalation semantic (a missing/malformed findings file escalates ONCE to deep; a deep receipt
    miss retries ONCE; transport failures stay recorded as missing);
  - the changed-surface derivation (diff of the script's own per-round spec snapshots,
    never the reviser's self-report; any failure → run-all);
  - the full reviewer-deep confirmation round before any exit;
  - fail-safe direction: every corruption/shape mismatch fails toward MORE review.
"""
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SLP = _load(os.path.join(_HERE, "..", "spec_loop_plan.py"), "spec_loop_plan")

DIMS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
        "test-reviewer", "premortem-reviewer", "grounding-reviewer"]
SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
          "security-reviewer": "security", "test-reviewer": "test",
          "premortem-reviewer": "premortem", "grounding-reviewer": "grounding"}

SPEC_V1 = "# Spec\n\n## Requirements\n\nFR-1 the system shall foo.\n\n## Coverage\n\nEmpty state: N-A.\n"
SPEC_V2 = "# Spec\n\n## Requirements\n\nFR-1 the system shall foo precisely.\n\n## Coverage\n\nEmpty state: N-A.\n"


def _blocker(dim_label):
    return {"id": "x-001", "severity": "Important", "dimension": dim_label,
            "title": "vague requirement", "file": "spec.md", "line": 5,
            "body": "b", "confidence": "High"}


def _session(tmp_path, spec_text=SPEC_V1):
    d = tmp_path / "sess"
    d.mkdir()
    (d / "spec.md").write_text(spec_text, encoding="utf-8")
    return str(d)


def _write_findings(session_dir, dim, findings):
    path = os.path.join(session_dir, "findings-%s.json" % SUFFIX[dim])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(findings, fh)
    return path


def _write_compiled(session_dir, findings):
    path = os.path.join(session_dir, "compiled.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"summary": "s", "verdict": "v", "findings": findings}, fh)
    return path


def _run(capsys, *args):
    rc = SLP.main(list(args))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    return rc, out


def _plan(capsys, session_dir, rnd):
    return _run(capsys, "plan", "--session-dir", session_dir, "--round", str(rnd))[1]


def _record(capsys, session_dir, rnd):
    return _run(capsys, "record", "--session-dir", session_dir, "--round", str(rnd))[1]


def _decide(capsys, session_dir, rnd, skipped=0, max_rounds=7, compiled=None):
    compiled = compiled or os.path.join(session_dir, "compiled.json")
    return _run(capsys, "decide", "--session-dir", session_dir, "--round", str(rnd),
                "--max-rounds", str(max_rounds), "--compiled", compiled,
                "--skipped-blocking", str(skipped))[1]


def _dims_map(out):
    return {d["dimension"]: d for d in out["dims_to_run"]}


def _round1(capsys, session_dir, findings_by_dim=None):
    """Drive a full baseline round: plan, write findings files, record."""
    plan = _plan(capsys, session_dir, 1)
    findings_by_dim = findings_by_dim or {}
    for dim in DIMS:
        _write_findings(session_dir, dim, findings_by_dim.get(dim, []))
    rec = _record(capsys, session_dir, 1)
    return plan, rec


# --- plan ------------------------------------------------------------------

def test_plan_round1_is_baseline_full_deep(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _plan(capsys, session_dir, 1)
    assert out["ok"] is True
    assert out["roundKind"] == "baseline"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())
    assert out["skipped"] == []
    # the script snapshots the round-1 surface for the round-2 diff
    snap = os.path.join(session_dir, "spec-r1.md")
    assert os.path.isfile(snap)
    assert open(snap, encoding="utf-8").read() == SPEC_V1


def test_plan_reemits_persisted_plan(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    (tmp_path / "sess" / "spec.md").write_text(SPEC_V2, encoding="utf-8")
    decided = _decide(capsys, session_dir, 1)
    replay = _plan(capsys, session_dir, 2)
    assert _dims_map(replay) == _dims_map(decided)
    assert [s["dimension"] for s in replay["skipped"]] == [s["dimension"] for s in decided["skipped"]]


def test_plan_missing_state_fails_toward_run_all_deep(tmp_path, capsys):
    session_dir = _session(tmp_path)
    out = _plan(capsys, session_dir, 3)  # no state for round 3 — must not guess a skip
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())
    assert out["skipped"] == []


def test_custom_dimensions_list_is_honored(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _, out = _run(capsys, "plan", "--session-dir", session_dir, "--round", "1",
                  "--dimensions", '["architecture-reviewer"]')
    assert [d["dimension"] for d in out["dims_to_run"]] == ["architecture-reviewer"]


# --- sanctioned-subset guard (#515/#34) ---------------------------------------

def test_sanction_dimensions_defaults_to_full_roster_on_none():
    # missing input → the full sanctioned roster (all six seats), in DIMENSIONS order
    assert SLP.sanction_dimensions(None) == list(SLP.DIMENSIONS)


def test_sanction_dimensions_honors_a_proper_sanctioned_subset():
    # a proper subset of sanctioned seats is honored as-is (membership, not equality),
    # normalized to DIMENSIONS order
    kept = SLP.sanction_dimensions('["security-reviewer", "architecture-reviewer"]')
    assert kept == ["architecture-reviewer", "security-reviewer"]
    assert SLP.sanction_dimensions('["grounding-reviewer"]') == ["grounding-reviewer"]


def test_sanction_dimensions_drops_unsanctioned_but_keeps_sanctioned():
    # an unsanctioned entry never widens/corrupts the roster; the sanctioned member is kept
    assert SLP.sanction_dimensions(
        '["architecture-reviewer", "rogue-reviewer"]') == ["architecture-reviewer"]


def test_sanction_dimensions_fails_closed_when_no_sanctioned_entry():
    # all-unsanctioned, empty, non-list, and malformed inputs all fail closed to the full roster
    for raw in ('["rogue-reviewer"]', "[]", '"architecture-reviewer"', "{}", "not-json", ""):
        assert SLP.sanction_dimensions(raw) == list(SLP.DIMENSIONS), raw


def test_malformed_dimensions_falls_back_to_default_roster(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _, out = _run(capsys, "plan", "--session-dir", session_dir, "--round", "1",
                  "--dimensions", "not-json")
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())


# --- record: executed evidence + escalation ---------------------------------

def test_record_baseline_fresh_clean_is_high_confidence(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _, rec = _round1(capsys, session_dir)
    assert rec["ok"] is True and rec["escalate"] == []
    for dim in DIMS:
        d = rec["dimensions"][dim]
        assert d["status"] == "run"
        assert d["confidence"] == "high"
        assert d["hasFindings"] is False
        assert d["tier"] == "reviewer-deep"


def test_record_missing_file_retries_once_then_records_missing(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    for dim in DIMS[1:]:
        _write_findings(session_dir, dim, [])
    first = _record(capsys, session_dir, 1)
    assert [e["dimension"] for e in first["escalate"]] == ["architecture-reviewer"]
    assert first["escalate"][0]["tier"] == "reviewer-deep"
    second = _record(capsys, session_dir, 1)  # still missing — no retry loop
    assert second["escalate"] == []
    d = second["dimensions"]["architecture-reviewer"]
    assert d["status"] == "missing" and d["confidence"] == "low"


def test_record_malformed_file_treated_as_receipt_miss(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    for dim in DIMS[1:]:
        _write_findings(session_dir, dim, [])
    with open(os.path.join(session_dir, "findings-architecture.json"), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    first = _record(capsys, session_dir, 1)
    assert [e["dimension"] for e in first["escalate"]] == ["architecture-reviewer"]


def test_non_dict_findings_entry_is_receipt_miss(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    for dim in DIMS[1:]:
        _write_findings(session_dir, dim, [])
    _write_findings(session_dir, "architecture-reviewer", ["not-a-finding"])
    first = _record(capsys, session_dir, 1)
    assert [e["dimension"] for e in first["escalate"]] == ["architecture-reviewer"]


def _patch_dim_confidence(session_dir, round_no, dim, confidence):
    path = os.path.join(session_dir, "loop-state.json")
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    state["rounds"][str(round_no)]["dims"][dim]["confidence"] = confidence
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def test_invalid_object_confidence_is_ignored(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    for dim in DIMS[1:]:
        _write_findings(session_dir, dim, [])
    _write_findings(session_dir, "architecture-reviewer",
                    {"confidence": "maybe", "findings": []})
    rec = _record(capsys, session_dir, 1)
    assert rec["escalate"] == []
    d = rec["dimensions"]["architecture-reviewer"]
    assert d["status"] == "run" and d["confidence"] == "high"


def test_record_accepts_structured_object_shape(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    for dim in DIMS[1:]:
        _write_findings(session_dir, dim, [])
    _write_findings(session_dir, "architecture-reviewer",
                    {"confidence": "high", "findings": [_blocker("Architecture")]})
    rec = _record(capsys, session_dir, 1)
    assert rec["escalate"] == []
    d = rec["dimensions"]["architecture-reviewer"]
    assert d["hasFindings"] is True and d["confidence"] == "high"
    assert d["blockingCount"] == 1


def test_object_wrapper_confidence_is_ignored(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _plan(capsys, session_dir, 1)
    for dim in DIMS[1:]:
        _write_findings(session_dir, dim, [])
    _write_findings(session_dir, "architecture-reviewer",
                    {"confidence": "low", "findings": []})
    rec = _record(capsys, session_dir, 1)
    assert rec["escalate"] == []
    d = rec["dimensions"]["architecture-reviewer"]
    assert d["status"] == "run" and d["confidence"] == "high"
    _write_compiled(session_dir, [])
    out = _decide(capsys, session_dir, 1)
    assert out["action"] == "exit_clean"


def test_plan_overlays_pending_escalation_at_deep(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    # missing findings file → transport miss → escalation pending at deep
    rec = _record(capsys, session_dir, 2)
    assert [e["dimension"] for e in rec["escalate"]] == ["architecture-reviewer"]
    replay = _plan(capsys, session_dir, 2)
    dims = _dims_map(replay)
    assert dims["architecture-reviewer"]["tier"] == "reviewer-deep"


def _reach_round2_with_cheap_arch(tmp_path, capsys):
    """Round 1: architecture flags a blocker, rest clean. Decide → round 2 plan:
    architecture runs cheap, the clean four skip."""
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    (tmp_path / "sess" / "spec.md").write_text(SPEC_V2, encoding="utf-8")  # step-8 re-copy
    decided = _decide(capsys, session_dir, 1)
    return session_dir, decided


def test_decide_after_fix_schedules_intermediate_round(tmp_path, capsys):
    session_dir, out = _reach_round2_with_cheap_arch(tmp_path, capsys)
    assert out["action"] == "review" and out["mandatory"] is True
    assert out["nextRound"] == 2 and out["roundKind"] == "intermediate"
    dims = _dims_map(out)
    assert list(dims) == ["architecture-reviewer"]  # never skip the dim that flagged a blocker
    assert dims["architecture-reviewer"]["tier"] == "reviewer"
    skipped = {s["dimension"]: s for s in out["skipped"]}
    assert sorted(skipped) == sorted(set(DIMS) - {"architecture-reviewer"})
    assert all(s.get("carriedFromRound") == 1 for s in skipped.values())
    # the next-round surface was snapshotted by the script itself
    assert open(os.path.join(session_dir, "spec-r2.md"), encoding="utf-8").read() == SPEC_V2


def test_scheduled_run_dim_findings_file_is_archived(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    # round-1 architecture findings must not be readable as a round-2 result
    assert not os.path.exists(os.path.join(session_dir, "findings-architecture.json"))


def test_skipped_dim_file_also_archived_on_decide(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    assert not os.path.exists(os.path.join(session_dir, "findings-security.json"))


def test_stale_result_never_counts_as_executed(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    # the dispatched agent did zero work: no fresh file → receipt miss → retry, then missing
    first = _record(capsys, session_dir, 2)
    assert [e["dimension"] for e in first["escalate"]] == ["architecture-reviewer"]
    second = _record(capsys, session_dir, 2)
    assert second["dimensions"]["architecture-reviewer"]["status"] == "missing"


def test_cheap_nonempty_stands_without_escalation(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [_blocker("Architecture")])
    rec = _record(capsys, session_dir, 2)
    assert rec["escalate"] == []
    d = rec["dimensions"]["architecture-reviewer"]
    assert d["status"] == "run" and d["confidence"] == "high"
    assert d["tier"] == "reviewer" and d["escalated"] is False


def test_cheap_empty_result_stands_without_escalation(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    rec = _record(capsys, session_dir, 2)
    assert rec["escalate"] == []
    d = rec["dimensions"]["architecture-reviewer"]
    assert d["confidence"] == "high" and d["tier"] == "reviewer"


def test_skipped_dims_carry_forward(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    rec = _record(capsys, session_dir, 2)
    d = rec["dimensions"]["security-reviewer"]
    assert d["status"] == "skipped" and d["carriedFromRound"] == 1
    assert d["confidence"] == "high" and d["hasFindings"] is False


# --- decide: continuation gate + confirmation invariant ----------------------

def test_clean_full_deep_baseline_exits_clean(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    _write_compiled(session_dir, [])
    out = _decide(capsys, session_dir, 1)
    assert out["action"] == "exit_clean" and out["dims_to_run"] == []


def test_clean_reduced_round_requires_full_deep_confirmation(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, [])
    out = _decide(capsys, session_dir, 2)
    assert out["action"] == "review" and out["mandatory"] is True
    assert out["roundKind"] == "confirmation" and out["nextRound"] == 3
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())


def test_confirmation_round_clean_exits(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, [])
    _decide(capsys, session_dir, 2)  # schedules the confirmation round
    for dim in DIMS:
        _write_findings(session_dir, dim, [])
    rec = _record(capsys, session_dir, 3)
    assert rec["escalate"] == []
    out = _decide(capsys, session_dir, 3)
    assert out["action"] == "exit_clean"


def _finding(dim_label, severity):
    return {"id": "y-002", "severity": severity, "dimension": dim_label,
            "title": "new confirmation finding", "file": "spec.md", "line": 7,
            "body": "b", "confidence": "High"}


def _confirmation_round3_surfacing(tmp_path, capsys, severity):
    """Drive to a full-deep confirmation round (3) that surfaces one new blocking finding of the
    given severity, then a clean scoped round (4). Returns session_dir positioned to decide(4)."""
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, [])
    _decide(capsys, session_dir, 2)  # schedules the full-deep confirmation round 3
    for dim in DIMS:
        _write_findings(session_dir, dim,
                        [_finding("Architecture", severity)] if dim == "architecture-reviewer" else [])
    _record(capsys, session_dir, 3)
    _write_compiled(session_dir, [_finding("Architecture", severity)])
    _decide(capsys, session_dir, 3)  # blocking present → schedules scoped round 4
    for dim in DIMS:
        _write_findings(session_dir, dim, [])
    _record(capsys, session_dir, 4)
    _write_compiled(session_dir, [])
    return session_dir


def _record_with_escalation(capsys, session_dir, rnd, findings_by_dim):
    """Record a round; if record returns any escalation (a transport failure), re-write those
    dims and record again."""
    for dim in DIMS:
        _write_findings(session_dir, dim, findings_by_dim.get(dim, []))
    rec = _record(capsys, session_dir, rnd)
    if rec.get("escalate"):
        for esc in rec["escalate"]:
            _write_findings(session_dir, esc["dimension"], findings_by_dim.get(esc["dimension"], []))
        rec = _record(capsys, session_dir, rnd)
    return rec


def test_confirmation_surfacing_important_certifies_after_scoped_verify(tmp_path, capsys):
    # #174 req 1/2: a confirmation that surfaces a new Important does NOT forfeit certification —
    # the Important is fixed + scope-verified and the loop certifies without a second full panel.
    session_dir = _confirmation_round3_surfacing(tmp_path, capsys, "Important")
    out = _decide(capsys, session_dir, 4)
    assert out["action"] == "exit_clean", out
    assert out["nextRound"] is None
    # #174 finding 4: the honest-readout flag is COMPUTED from what the panel surfaced, not hardcoded.
    assert out["certification"]["fullPanels"] == 1
    assert out["certification"]["lastPanelSurfacedResolved"] is True


def test_spec_postconfirmation_scoped_critical_rearms(tmp_path, capsys):
    # #174 finding 2 (spec): a Critical surfaced by a post-confirmation SCOPED round (not the panel
    # itself) must re-arm one more full confirmation — the follow-up unions surfaced severities
    # across the panel and every later round, not the panel round alone.
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, [])
    _decide(capsys, session_dir, 2)  # → confirmation round 3
    for dim in DIMS:
        _write_findings(session_dir, dim,
                        [_finding("Architecture", "Important")] if dim == "architecture-reviewer" else [])
    _record(capsys, session_dir, 3)
    _write_compiled(session_dir, [_finding("Architecture", "Important")])
    _decide(capsys, session_dir, 3)  # review → scoped round 4
    _record_with_escalation(capsys, session_dir, 4, {"architecture-reviewer": [_finding("Architecture", "Critical")]})
    _write_compiled(session_dir, [_finding("Architecture", "Critical")])
    _decide(capsys, session_dir, 4)  # review (blocking present) → scoped round 5
    _record_with_escalation(capsys, session_dir, 5, {})
    _write_compiled(session_dir, [])
    out = _decide(capsys, session_dir, 5)
    assert out["action"] == "review" and out["roundKind"] == "confirmation", out


def test_spec_degraded_confirmation_owes_proper_panel(tmp_path, capsys):
    # #174 finding 3 (spec): a confirmation with a low-confidence dimension is NOT a qualifying full
    # panel (#167 bar) and must not anchor certification — the loop owes a proper panel.
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, [])
    _decide(capsys, session_dir, 2)  # → confirmation round 3
    # round 3 confirmation: architecture recorded clean, then state patched to low-confidence
    # (synthetic — tier+shape no longer derives low; round-gate/scheduling still read it)
    for dim in DIMS:
        if dim == "architecture-reviewer":
            path = os.path.join(session_dir, "findings-architecture.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"findings": [], "confidence": "low"}, fh)
        else:
            _write_findings(session_dir, dim, [])
    _record(capsys, session_dir, 3)
    _patch_dim_confidence(session_dir, 3, "architecture-reviewer", "low")
    _write_compiled(session_dir, [])
    out = _decide(capsys, session_dir, 3)
    assert out["action"] == "review" and out["roundKind"] == "confirmation", out


def test_spec_surfaced_severities_missing_criticalcount_fails_toward_critical():
    # #174 finding 5: state records written before this PR have no criticalCount; a surfaced blocker
    # with a missing criticalCount must read as Critical (fail-open), never silently as Important.
    entry = {"dims": {"architecture-reviewer": {"status": "run", "blockingCount": 1}}}
    assert SLP._surfaced_severities(entry) == ["Critical"]
    # present-and-zero criticalCount stays Important
    entry2 = {"dims": {"architecture-reviewer": {"status": "run", "blockingCount": 1, "criticalCount": 0}}}
    assert SLP._surfaced_severities(entry2) == ["Important"]


def test_confirmation_surfacing_critical_rearms_one_more_confirmation(tmp_path, capsys):
    # #174 req 2: a Critical surfaced by a confirmation triggers exactly one more full confirmation.
    session_dir = _confirmation_round3_surfacing(tmp_path, capsys, "Critical")
    out = _decide(capsys, session_dir, 4)
    assert out["action"] == "review", out
    assert out["roundKind"] == "confirmation"
    assert out["nextRound"] == 5


def test_cap_before_confirmation_halts(tmp_path, capsys):
    session_dir, _ = _reach_round2_with_cheap_arch(tmp_path, capsys)
    _write_findings(session_dir, "architecture-reviewer", [])
    _record(capsys, session_dir, 2)
    _write_compiled(session_dir, [])
    out = _decide(capsys, session_dir, 2, max_rounds=2)
    assert out["action"] == "halt" and out["mandatory"] is True
    assert "confirmation" in out["reason"]


def test_exit_skipped_from_full_deep_round(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    out = _decide(capsys, session_dir, 1, skipped=1)
    assert out["action"] == "exit_skipped" and out["dims_to_run"] == []


def test_blockers_fixed_at_cap_halts(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    out = _decide(capsys, session_dir, 7, max_rounds=7)
    assert out["action"] == "halt"


# --- fail-safe direction ------------------------------------------------------

def test_unreadable_compiled_fails_safe_to_review_run_all(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    out = _decide(capsys, session_dir, 1, compiled=os.path.join(session_dir, "nope.json"))
    assert out["action"] == "review" and out["mandatory"] is True
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())


def test_corrupt_state_fails_toward_run_all_deep(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        fh.write("{corrupt")
    out = _decide(capsys, session_dir, 1)
    assert out["action"] == "review"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())


def test_non_dict_round_entry_is_corrupt_state(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {"1": ["x"]}}, fh)
    out = _decide(capsys, session_dir, 1)
    assert out["action"] == "review"
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())


def test_missing_snapshot_means_unknown_surface_runs_all(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    os.unlink(os.path.join(session_dir, "spec-r1.md"))
    out = _decide(capsys, session_dir, 1)
    dims = _dims_map(out)
    assert sorted(dims) == sorted(DIMS)  # no snapshot → no skips
    assert all(d["tier"] == "reviewer-deep" for d in dims.values())
    assert out["skipped"] == []


def test_corrupt_state_blocks_exit_and_forces_confirmation(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    _write_compiled(session_dir, [])
    with open(os.path.join(session_dir, "loop-state.json"), "w", encoding="utf-8") as fh:
        fh.write("{corrupt")
    out = _decide(capsys, session_dir, 1)
    assert out["action"] == "review" and out["roundKind"] == "confirmation"


# --- shared-policy delegation (drift pin) -------------------------------------

def test_decide_delegates_to_shared_round_policy(tmp_path, capsys):
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir, {"architecture-reviewer": [_blocker("Architecture")]})
    _write_compiled(session_dir, [_blocker("Architecture")])
    (tmp_path / "sess" / "spec.md").write_text(SPEC_V2, encoding="utf-8")
    calls = {}
    real = SLP.review_round_policy.plan_round
    sentinel_plan = {
        "roundKind": "intermediate",
        "dimensions": {
            "architecture-reviewer": {"action": "run", "tier": "reviewer",
                                      "reason": "sentinel-plan"},
            "code-reviewer": {"action": "skip", "tier": "reviewer-deep",
                              "reason": "sentinel-skip", "carriedFromRound": 1},
            "security-reviewer": {"action": "skip", "tier": "reviewer-deep",
                                  "reason": "sentinel-skip", "carriedFromRound": 1},
            "test-reviewer": {"action": "skip", "tier": "reviewer-deep",
                              "reason": "sentinel-skip", "carriedFromRound": 1},
            "premortem-reviewer": {"action": "skip", "tier": "reviewer-deep",
                                   "reason": "sentinel-skip", "carriedFromRound": 1},
            "grounding-reviewer": {"action": "skip", "tier": "reviewer-deep",
                                   "reason": "sentinel-skip", "carriedFromRound": 1},
        },
        "escalationPolicy": "cheap-first",
    }

    def spy(state):
        calls["state"] = state
        return sentinel_plan

    SLP.review_round_policy.plan_round = spy
    try:
        out = _decide(capsys, session_dir, 1)
    finally:
        SLP.review_round_policy.plan_round = real
    assert calls["state"]["round"] == 2
    assert sorted(calls["state"]["dimensions"]) == sorted(DIMS)
    # the changed surface is the script's own snapshot diff — section-title strings
    assert calls["state"]["changedSubjects"] == ["Requirements"]
    prev = calls["state"]["previous"]
    assert prev["architecture-reviewer"]["hasFindings"] is True
    assert prev["security-reviewer"]["confidence"] == "high"
    assert out["dims_to_run"] == [{"dimension": "architecture-reviewer", "tier": "reviewer",
                                   "reason": "sentinel-plan"}]
    assert all(s["reason"] == "sentinel-skip" for s in out["skipped"])


def test_gate_decision_delegates_to_loop_state(tmp_path, capsys):
    """The continue/exit decision itself must come from loop_state.decide."""
    session_dir = _session(tmp_path)
    _round1(capsys, session_dir)
    _write_compiled(session_dir, [])
    calls = {}
    real = SLP.loop_state.decide

    def spy(*args, **kwargs):
        calls["args"] = args
        return ("halt", True, "sentinel-halt")

    SLP.loop_state.decide = spy
    try:
        out = _decide(capsys, session_dir, 1)
    finally:
        SLP.loop_state.decide = real
    assert calls["args"][0] == 0  # blocking fixed derived from compiled.json, not self-reported
    assert out["action"] == "halt"
    assert out["mandatory"] is True
    assert out["reason"] == "sentinel-halt"
    assert out["dims_to_run"] == []


# --- changed-section diff ------------------------------------------------------

def test_changed_sections_lists_touched_headings():
    old = "# T\n\n## A\n\nsame\n\n## B\n\nold\n"
    new = "# T\n\n## A\n\nsame\n\n## B\n\nnew\n\n## C\n\nadded\n"
    assert SLP.changed_sections(old, new) == ["B", "C"]


def test_changed_sections_identical_is_known_empty():
    text = "# T\n\n## A\n\nsame\n"
    assert SLP.changed_sections(text, text) == []


def test_changed_sections_preamble_change_is_named():
    old = "intro\n\n## A\n\nsame\n"
    new = "intro changed\n\n## A\n\nsame\n"
    assert SLP.changed_sections(old, new) == ["(preamble)"]


def test_tiers_are_roles_never_model_names(tmp_path, capsys):
    session_dir, out = _reach_round2_with_cheap_arch(tmp_path, capsys)
    for entry in out["dims_to_run"]:
        assert entry["tier"] in ("reviewer", "reviewer-deep")
