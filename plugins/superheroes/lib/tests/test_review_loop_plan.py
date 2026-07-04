"""Tests for `review_loop_plan` — the showrunner review-panel deciders (#211).

The #211 architecture moves the review loop's decisions off the JS shell's in-memory `records`
copy and onto Python deciders that read the durable `round-records.json` from disk and answer
small, meaningful JSON. These pin, for each of the four deciders (`entry-bootstrap`, `plan-round`,
`tally-round`, `compose-fix-context`):

  - the answer SHAPE and the #211 SIZE invariant — every decider answer stays < 2 KB even for a
    50-verbose-finding × 3-round fixture (no courier-answer payload scales with run size);
  - a faithful port of the shell's in-memory consumers — resume round, previous-dimension state,
    carry-forward, the confirmation-bar economics, the breaker input, the fix worklist;
  - delegation to the parity-locked twins (plan_round / check_circuit_breaker /
    confirmation_followup / recurrent_classes) — policy lives ONLY in the twins;
  - fail-closed direction — every unreadable/corrupt/empty input fails toward cannot-certify or
    run-all-deep, never toward a silent skip or a premature clean.

Fixtures are built through the REAL `review_memory` write path (record_from_dimension_results →
summarize_record), so the on-disk records are byte-identical to what the shell persists.
"""
import json
import os

import pytest

import circuit_breaker
import review_loop_plan as rlp
import review_memory
import review_round_policy

DIMS = ["code-reviewer", "security-reviewer"]
FULL_ROSTER = ["architecture-reviewer", "code-reviewer", "security-reviewer",
               "test-reviewer", "premortem-reviewer"]


# ── fixture builders (through the real review_memory write path) ──
def _dim(status="run", confidence="high", tier="reviewer-deep", findings=None):
    return {"status": status, "confidence": confidence, "tier": tier,
            "dimension": None, "findings": findings or []}


def _skeleton_round(round_no, dim_results, kind="baseline", changed_subjects=None,
                    coverage=None, confirmation_pending=False):
    """One durable skeleton record, exactly as persistRoundRecord would write it."""
    results = {}
    for name, spec in dim_results.items():
        results[name] = dict(spec, dimension=name)
    rec = review_memory.record_from_dimension_results(
        round_no, kind, results, changed_subjects, coverage or [], {}, confirmation_pending)
    return review_memory.summarize_record(rec)


def _write_records(tmp_path, records, name="round-records.json"):
    p = tmp_path / name
    p.write_text(json.dumps(records))
    return str(p)


def _run(*argv):
    """Invoke a decider in-process the way the CLI does; return the parsed answer + its byte size."""
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rlp.main(["review_loop_plan.py", *argv])
    out = buf.getvalue().strip()
    return json.loads(out), len(out.encode("utf-8"))


def _max_list_len(value):
    """Deepest list length anywhere in an answer — an anti-leak guard: no decider answer field may
    grow with finding count, so on a big fixture every list must stay small (bounded by roster)."""
    if isinstance(value, list):
        return max([len(value)] + [_max_list_len(v) for v in value])
    if isinstance(value, dict):
        return max([0] + [_max_list_len(v) for v in value.values()])
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# entry-bootstrap
# ─────────────────────────────────────────────────────────────────────────────
def test_entry_bootstrap_missing_is_round_one_empty_hash(tmp_path):
    ans = rlp.entry_bootstrap(str(tmp_path / "nope.json"), DIMS)
    assert ans["ok"] is True
    assert ans["state"] == "missing"
    assert ans["round"] == 1
    # sha256 of "" — the shell's contentHash('') for a first-persist CAS match.
    assert ans["contentHash"] == review_memory.content_hash("")
    assert ans["confirmationPending"] is False
    assert ans["markedRound"] is None
    assert "records" not in ans and "findings" not in ans, "entry-bootstrap must NOT ship records/findings"


def test_entry_bootstrap_resume_round_and_markers(tmp_path):
    recs = [
        _skeleton_round(1, {"code-reviewer": _dim()}, changed_subjects=["Code"]),
        _skeleton_round(2, {"code-reviewer": _dim()}, kind="confirmation",
                        confirmation_pending=True),
    ]
    path = _write_records(tmp_path, recs)
    ans = rlp.entry_bootstrap(path, DIMS)
    assert ans["ok"] is True
    assert ans["round"] == 3, "resume round = max persisted round + 1"
    assert ans["confirmationPending"] is True
    assert ans["markedRound"] == 2
    assert ans["roundCount"] == 2
    # contentHash matches the on-disk bytes (first-persist CAS relies on this).
    assert ans["contentHash"] == review_memory.content_hash(open(path).read())


def test_entry_bootstrap_reads_extras(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    extras_path = tmp_path / "last-extras.json"
    extras_path.write_text(json.dumps({"changedSubjects": ["Code", "Security"]}))
    ans = rlp.entry_bootstrap(path, DIMS, str(extras_path))
    assert ans["extras"] == {"changedSubjects": ["Code", "Security"]}


def test_entry_bootstrap_corrupt_fails_closed(tmp_path):
    path = tmp_path / "round-records.json"
    path.write_text("{not json")
    ans = rlp.entry_bootstrap(str(path), DIMS)
    assert ans["ok"] is False, "a corrupt records file must fail closed (caller cannot-certify)"
    assert ans["state"] in ("unreadable", "corrupt")


# ─────────────────────────────────────────────────────────────────────────────
# plan-round
# ─────────────────────────────────────────────────────────────────────────────
def test_plan_round_baseline_is_all_deep(tmp_path):
    path = _write_records(tmp_path, [])
    ans = rlp.plan_round_decider(path, 1, DIMS, None, just_marked=False)
    assert ans["roundKind"] == "baseline"
    assert ans["enterConfirmation"] is False
    assert all(d["action"] == "run" and d["tier"] == "reviewer-deep"
               for d in ans["dimensions"].values())
    assert ans["carried"] == {}


def test_plan_round_intermediate_skips_clean_untouched(tmp_path):
    # Round 1: security clean+untouched, code had a finding. Round 2 over changedSubjects=["Code"].
    recs = [_skeleton_round(1, {
        "code-reviewer": _dim(findings=[{"title": "bug", "file": "a.js", "severity": "Critical",
                                         "dimension": "Code"}]),
        "security-reviewer": _dim(findings=[]),
    }, changed_subjects=["Code"])]
    path = _write_records(tmp_path, recs)
    ans = rlp.plan_round_decider(path, 2, DIMS, ["Code"], just_marked=False)
    assert ans["roundKind"] == "intermediate"
    assert ans["dimensions"]["security-reviewer"]["action"] == "skip"
    assert ans["dimensions"]["code-reviewer"]["action"] == "run"
    # a skipped dim carries its most-recent prior state, stamped skipped
    assert "security-reviewer" in ans["carried"]
    assert ans["carried"]["security-reviewer"]["status"] == "skipped"
    assert ans["carried"]["security-reviewer"]["carriedFromRound"] == \
        ans["dimensions"]["security-reviewer"]["carriedFromRound"]


def test_plan_round_unknown_surface_runs_all_deep(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    ans = rlp.plan_round_decider(path, 2, DIMS, None, just_marked=False)  # changedSubjects unknown
    assert all(d["tier"] == "reviewer-deep" for d in ans["dimensions"].values())


def test_plan_round_unreadable_memory_runs_all_deep(tmp_path):
    path = tmp_path / "round-records.json"
    path.write_text("{corrupt")
    ans = rlp.plan_round_decider(str(path), 2, DIMS, ["Code"], just_marked=False)
    assert ans.get("memoryUnreadable") is True
    assert ans["enterConfirmation"] is False
    assert all(d["action"] == "run" and d["tier"] == "reviewer-deep"
               for d in ans["dimensions"].values())


def test_plan_round_just_marked_blocks_immediate_confirmation(tmp_path):
    # A fix at round 1 marked confirmation; the within-run round 2 is the mandatory intermediate
    # re-review (NOT the confirmation) — just_marked must suppress the confirmation entry.
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()},
                            confirmation_pending=True, changed_subjects=["Code"])]
    path = _write_records(tmp_path, recs)
    ans_marked = rlp.plan_round_decider(path, 2, DIMS, ["Code"], just_marked=True)
    assert ans_marked["enterConfirmation"] is False
    # A RESUME at round 2 (fresh session, just_marked=False, no round-2 record) enters the owed
    # confirmation immediately — disk state alone cannot tell these apart.
    ans_resume = rlp.plan_round_decider(path, 2, DIMS, ["Code"], just_marked=False)
    assert ans_resume["enterConfirmation"] is True
    assert ans_resume["roundKind"] == "confirmation"
    assert all(d["tier"] == "reviewer-deep" for d in ans_resume["dimensions"].values())


def test_plan_round_delegates_to_plan_round_twin(tmp_path, monkeypatch):
    recs = [_skeleton_round(1, {"code-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    seen = {}
    real = review_round_policy.plan_round

    def _spy(state):
        seen["state"] = state
        return real(state)
    monkeypatch.setattr(rlp.review_round_policy, "plan_round", _spy)
    rlp.plan_round_decider(path, 2, DIMS, ["Code"], just_marked=False)
    assert seen["state"]["round"] == 2
    assert seen["state"]["dimensions"] == DIMS
    assert seen["state"]["changedSubjects"] == ["Code"]
    assert "previous" in seen["state"], "plan_round must receive the disk-derived previous state"


# ─────────────────────────────────────────────────────────────────────────────
# tally-round
# ─────────────────────────────────────────────────────────────────────────────
def _tally(path, round_no, **kw):
    kw.setdefault("roster", DIMS)
    kw.setdefault("max_rounds", 7)
    kw.setdefault("gate", "clean")
    kw.setdefault("confidence", "high")
    kw.setdefault("missing", [])
    kw.setdefault("present_blocking", 0)
    kw.setdefault("deferred_path", None)
    kw.setdefault("fix_status", "completed")
    kw.setdefault("verify_result", None)
    kw.setdefault("enter_confirmation", False)
    return rlp.tally_round_decider(path, round_no, **kw)


def test_tally_clean_baseline_exits_clean_with_certification(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 1, gate="clean", present_blocking=0)
    assert ans["terminal"] == "clean"
    assert ans["breaker"]["halt"] is False
    # honest certification summary rides on a certifying terminal (#174 req 4)
    assert "certification" in ans and "fullPanels" in ans["certification"]
    assert "findings" not in ans, "tally-round answer must not carry findings"


def test_tally_blocking_continues(tmp_path):
    recs = [_skeleton_round(1, {
        "code-reviewer": _dim(findings=[{"title": "bug", "file": "a.js", "severity": "Critical",
                                         "dimension": "Code"}]),
        "security-reviewer": _dim(),
    })]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 1, gate="blocking", present_blocking=1)
    assert ans["terminal"] == "continue"


def test_tally_cannot_certify_gate_fails_closed(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 1, gate="cannot-certify", confidence="low",
                 missing=["security-reviewer"], present_blocking=0)
    assert ans["terminal"] == "cannot-certify"
    assert "security-reviewer" in ans["reason"]


def test_tally_verify_fail_halts_a_clean_round(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 1, gate="clean", present_blocking=0, verify_result="fail")
    assert ans["terminal"] == "halted"
    assert "verify" in ans["reason"]


def test_tally_empty_roster_cannot_certify(tmp_path):
    path = _write_records(tmp_path, [])
    ans = rlp.tally_round_decider(path, 1, roster=[], max_rounds=7, gate="clean",
                                  confidence="high", missing=[], present_blocking=0,
                                  deferred_path=None, fix_status="completed",
                                  verify_result=None, enter_confirmation=False)
    assert ans["terminal"] == "cannot-certify"


def test_tally_unreadable_memory_cannot_certify(tmp_path):
    path = tmp_path / "round-records.json"
    path.write_text("{corrupt")
    ans = _tally(str(path), 1, gate="clean", present_blocking=0)
    assert ans["terminal"] == "cannot-certify"
    assert "round-memory" in ans["reason"]


def test_tally_breaker_halt_on_recurring_finding(tmp_path):
    # The same blocking class recurs across two reviewed rounds after a fix — the breaker halts.
    finding = {"title": "same bug", "file": "a.js", "severity": "Critical", "dimension": "Code",
               "classKey": "Code::x::same bug"}
    recs = [
        _skeleton_round(1, {"code-reviewer": _dim(findings=[finding])}, changed_subjects=["Code"]),
        _skeleton_round(2, {"code-reviewer": _dim(findings=[finding])}, changed_subjects=["Code"]),
    ]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 2, gate="blocking", present_blocking=1)
    assert ans["breaker"]["halt"] is True
    assert ans["terminal"] == "halted"
    assert ans["reason"] == ans["breaker"]["detail"]


def test_tally_delegates_breaker_and_terminal(tmp_path, monkeypatch):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    seen = {}
    real_brk = circuit_breaker.check_circuit_breaker

    def _spy_brk(rounds, max_rounds):
        seen["rounds"] = rounds
        seen["max_rounds"] = max_rounds
        return real_brk(rounds, max_rounds)
    monkeypatch.setattr(rlp.circuit_breaker, "check_circuit_breaker", _spy_brk)
    _tally(path, 1, gate="clean", present_blocking=0)
    assert seen["max_rounds"] == 7
    assert isinstance(seen["rounds"], list) and seen["rounds"][-1]["round"] == 1


# ── confirmation-bar economics (#174) through tally-round ──
def test_tally_clean_intermediate_owes_a_confirmation_panel(tmp_path):
    # A fix ran (confirmationPending on round 1), a clean intermediate round 2 followed — before any
    # QUALIFYING full panel, a confirmation is owed → continue "awaiting final confirmation round".
    recs = [
        _skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()},
                        confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(2, {"code-reviewer": _dim(), "security-reviewer": _dim()},
                        kind="intermediate", changed_subjects=["Code"]),
    ]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 2, gate="clean", present_blocking=0, enter_confirmation=False)
    assert ans["terminal"] == "continue"
    assert ans["reason"] == "awaiting final confirmation round"


def test_tally_parks_when_critical_surfaces_at_confirmation_cap(tmp_path):
    # The fail-closed direction of the #174 economics: two QUALIFYING full-deep confirmation panels
    # have run (the hard cap) and a Critical surfaced since the last one — certification must be
    # WITHHELD (halted), never certified clean. A dropped park branch would certify a should-halt run.
    crit = [{"title": "still critical", "file": "a.js", "severity": "Critical", "dimension": "Code"}]
    recs = [
        _skeleton_round(1, {n: _dim() for n in FULL_ROSTER}, changed_subjects=["Code"]),
        _skeleton_round(2, {n: _dim() for n in FULL_ROSTER}, kind="confirmation",
                        confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(3, {n: _dim() for n in FULL_ROSTER}, kind="intermediate",
                        changed_subjects=["Code"]),
        # second qualifying confirmation panel that surfaces a Critical
        _skeleton_round(4, dict({n: _dim() for n in FULL_ROSTER},
                                **{"code-reviewer": _dim(findings=crit)}),
                        kind="confirmation", confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(5, {n: _dim() for n in FULL_ROSTER}, kind="intermediate",
                        changed_subjects=["Code"]),
    ]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 5, roster=FULL_ROSTER, gate="clean", present_blocking=0,
                 enter_confirmation=False)
    assert ans["terminal"] == "halted"
    assert "withheld" in ans["reason"]


def test_tally_challenged_coverage_decision_changes_breaker_verdict(tmp_path):
    # tally-round threads each round's coverageDecisions into the breaker; a challenged-and-recurring
    # coverage decision must produce the distinct `challenged-principle-recurring` halt, not the plain
    # `recurring-finding` one. Pins that the decider actually forwards coverageDecisions to the breaker.
    finding = {"title": "recurs", "file": "a.js", "severity": "Critical", "dimension": "Code",
               "classKey": "Code::x::recurs"}
    challenged_cov = [{"id": "RCD-1", "classKey": "Code::x::recurs", "challengedBy": "code-reviewer"}]

    def _fixture(coverage):
        recs = [
            _skeleton_round(1, {"code-reviewer": _dim(findings=[finding])}, changed_subjects=["Code"]),
            _skeleton_round(2, {"code-reviewer": _dim(findings=[finding])},
                            coverage=coverage, changed_subjects=["Code"]),
        ]
        return _write_records(tmp_path, recs, name=f"rr-{'ch' if coverage else 'plain'}.json")

    challenged = _tally(_fixture(challenged_cov), 2, gate="blocking", present_blocking=1)
    plain = _tally(_fixture([]), 2, gate="blocking", present_blocking=1)
    assert challenged["breaker"]["reason"] == "challenged-principle-recurring"
    assert plain["breaker"]["reason"] == "recurring-finding"


def test_tally_deferred_blocker_does_not_block_a_clean_round(tmp_path):
    # The deferred set removes a present blocker from the terminal accounting (present − deferred).
    # With deferral the round exits; without it, the same present blocker forces continue.
    finding = {"title": "known issue", "file": "a.js", "severity": "Critical", "dimension": "Code"}
    recs = [_skeleton_round(1, {"code-reviewer": _dim(findings=[finding]),
                                "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    identity = circuit_breaker.finding_identity(finding)
    deferred = tmp_path / "deferred-set.json"
    deferred.write_text(json.dumps({identity: "Critical"}))

    with_defer = _tally(path, 1, gate="clean", present_blocking=1, deferred_path=str(deferred))
    assert with_defer["presentDeferred"] == 1
    assert with_defer["terminal"] in ("clean", "clean-with-skips")
    without = _tally(path, 1, gate="clean", present_blocking=1, deferred_path=None)
    assert without["presentDeferred"] == 0
    assert without["terminal"] == "continue", "the deferral is what let the round exit"


def test_tally_fix_failed_halts(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 1, gate="clean", present_blocking=0, fix_status="failed")
    assert ans["terminal"] == "halted"
    assert "fix step" in ans["reason"]


def test_tally_internal_error_fails_closed(tmp_path, monkeypatch):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})]
    path = _write_records(tmp_path, recs)

    def _boom(*_a, **_k):
        raise RuntimeError("breaker exploded")
    monkeypatch.setattr(rlp.circuit_breaker, "check_circuit_breaker", _boom)
    ans = _tally(path, 1, gate="clean", present_blocking=0)
    assert ans["terminal"] == "halted"
    assert ans["reason"].startswith("tally failed")


def test_tally_answer_bounded_even_on_recurring_finding_halt(tmp_path):
    # The premortem hole: on a recurring-finding halt the breaker detail joins EVERY recurring class
    # key. With 40 verbose-keyed recurring blockers the unclamped detail is multi-KB — the answer
    # must stay < 2 KB and keep the machine-readable breaker.reason intact.
    findings = [{"title": ("recurring blocker %d " % i) + ("x" * 120), "file": f"m{i}.js",
                 "severity": "Critical", "dimension": "Code",
                 "classKey": f"Code::cls{i}::recurring blocker {i} " + ("x" * 120)} for i in range(40)]
    recs = [
        _skeleton_round(1, {"code-reviewer": _dim(findings=findings)}, changed_subjects=["Code"]),
        _skeleton_round(2, {"code-reviewer": _dim(findings=findings)}, changed_subjects=["Code"]),
    ]
    path = _write_records(tmp_path, recs)
    ans, size = _run("tally-round", "--path", path, "--round", "2", "--roster", json.dumps(DIMS),
                     "--gate", "blocking", "--confidence", "high", "--present-blocking", "40")
    assert ans["terminal"] == "halted"
    assert ans["breaker"]["reason"] == "recurring-finding"
    assert size < LIMIT, f"a 40-recurring-class halt answer is {size}B — must clamp to < {LIMIT}B"
    assert len(ans["breaker"]["detail"]) <= rlp._MAX_REASON + 32


def test_tally_certifies_after_qualifying_confirmation(tmp_path):
    # Round 1 fix marked confirmation; round 2 is a QUALIFYING full-deep confirmation panel that is
    # clean → the confirmation obligation is satisfied → certify (no repeat-until-pristine ratchet).
    recs = [
        _skeleton_round(1, {n: _dim() for n in FULL_ROSTER},
                        confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(2, {n: _dim() for n in FULL_ROSTER}, kind="confirmation",
                        changed_subjects=["Code"]),
    ]
    path = _write_records(tmp_path, recs)
    ans = _tally(path, 2, roster=FULL_ROSTER, gate="clean", present_blocking=0,
                 enter_confirmation=True)
    assert ans["terminal"] == "clean"
    assert ans["certification"]["fullPanels"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# compose-fix-context
# ─────────────────────────────────────────────────────────────────────────────
def test_compose_fix_context_writes_worklist_and_answers_pointer(tmp_path):
    recs = [_skeleton_round(1, {"code-reviewer": _dim(findings=[
        {"title": "prior bug", "file": "a.js", "severity": "Critical", "dimension": "Code",
         "classKey": "Code::x::prior bug"}])}, changed_subjects=["Code"])]
    records_path = _write_records(tmp_path, recs)
    # the shell stages this round's FULL findings (with evidence bodies) down to a file
    cur = tmp_path / "current-findings.json"
    cur.write_text(json.dumps([{"title": "live bug", "file": "b.js", "line": 3,
                                "severity": "Important", "dimension": "Code",
                                "evidence": "x" * 500}]))
    out = tmp_path / "fix-context-r2.json"
    ans = rlp.compose_fix_context(records_path, str(cur), None, "code", 2, DIMS, str(out))
    assert ans["ok"] is True
    assert ans["path"] == str(out)
    assert ans["sha256"] == review_memory.content_hash(out.read_text())
    worklist = json.loads(out.read_text())
    titles = [f["title"] for f in worklist["priorFindings"]]
    assert "prior bug" in titles and "live bug" in titles, "prior skeletons + current full findings"
    # the current finding keeps its evidence body (staged full), the prior one is a skeleton
    live = next(f for f in worklist["priorFindings"] if f["title"] == "live bug")
    assert live.get("evidence") == "x" * 500
    assert worklist["changedSubjects"] == ["Code"]


def test_compose_fix_context_generalize_required_via_recurrence(tmp_path, monkeypatch):
    recs = [_skeleton_round(1, {"code-reviewer": _dim()})]
    records_path = _write_records(tmp_path, recs)
    out = tmp_path / "fc.json"
    seen = {}
    real = review_memory.recurrent_classes

    def _spy(records, coverage):
        seen["called"] = True
        return real(records, coverage)
    monkeypatch.setattr(rlp.review_memory, "recurrent_classes", _spy)
    rlp.compose_fix_context(records_path, None, None, "code", 2, DIMS, str(out))
    assert seen.get("called"), "generalizeRequired must come from recurrent_classes, not a reimpl"


def test_compose_fix_context_unreadable_fails_closed(tmp_path):
    path = tmp_path / "round-records.json"
    path.write_text("{corrupt")
    out = tmp_path / "fc.json"
    ans = rlp.compose_fix_context(str(path), None, None, "code", 1, DIMS, str(out))
    assert ans["ok"] is False


# ─────────────────────────────────────────────────────────────────────────────
# the #211 SIZE invariant — no decider answer scales with run size
# ─────────────────────────────────────────────────────────────────────────────
def _verbose_fixture(tmp_path):
    """3 rounds × 50 verbose findings each (long titles + evidence bodies), through the real
    write path — the issue's explicit scaling fixture."""
    recs = []
    for r in (1, 2, 3):
        findings = [{
            "title": f"finding {i} round {r} " + ("lorem ipsum dolor sit amet " * 8),
            "file": f"path/to/module_{i}.js", "line": i, "severity": "Critical" if i % 5 == 0 else "Minor",
            "dimension": "Code", "classKey": f"Code::cls{i}::finding {i}",
            "summary": "S" * 300, "evidence": "E" * 600,
        } for i in range(50)]
        recs.append(_skeleton_round(r, {"code-reviewer": _dim(findings=findings),
                                        "security-reviewer": _dim()},
                                    kind="intermediate" if r > 1 else "baseline",
                                    changed_subjects=["Code"]))
    return _write_records(tmp_path, recs)


LIMIT = 2000  # bytes — the issue's < 2 KB decider-answer assertion


def test_entry_bootstrap_answer_is_small(tmp_path):
    path = _verbose_fixture(tmp_path)
    _ans, size = _run("entry-bootstrap", "--path", path, "--dimensions", json.dumps(DIMS))
    assert size < LIMIT, f"entry-bootstrap answer {size}B must stay < {LIMIT}B on a big fixture"


def test_plan_round_answer_is_small(tmp_path):
    path = _verbose_fixture(tmp_path)
    ans, size = _run("plan-round", "--path", path, "--round", "4",
                     "--dimensions", json.dumps(DIMS), "--changed-subjects", json.dumps(["Code"]))
    assert size < LIMIT, f"plan-round answer {size}B must stay < {LIMIT}B on a big fixture"
    # anti-leak: with 50 findings/round on disk, no answer list may approach the finding count
    assert _max_list_len(ans) < 50, "a decider answer list must not scale with finding count"


def test_tally_round_answer_is_small(tmp_path):
    path = _verbose_fixture(tmp_path)
    ans, size = _run("tally-round", "--path", path, "--round", "3", "--roster", json.dumps(DIMS),
                     "--gate", "blocking", "--confidence", "high", "--present-blocking", "30")
    assert size < LIMIT, f"tally-round answer {size}B must stay < {LIMIT}B on a big fixture"
    assert _max_list_len(ans) < 50, "a decider answer list must not scale with finding count"


def test_compose_fix_context_answer_is_small(tmp_path):
    # The worklist FILE is large; the ANSWER is only a pointer (path/bytes/sha256) → trivially small.
    path = _verbose_fixture(tmp_path)
    out = tmp_path / "fc.json"
    ans, size = _run("compose-fix-context", "--records-path", path, "--round", "3",
                     "--dimensions", json.dumps(DIMS), "--out-path", str(out))
    assert size < LIMIT
    assert ans["bytes"] > LIMIT, "the worklist file itself is large — the point is the ANSWER is not"
