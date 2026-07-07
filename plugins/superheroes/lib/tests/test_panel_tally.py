"""Tests for the deterministic review-panel tally (`panel_tally`).

These pin the per-round gate/confidence, the 4-terminal continuation + precedence, the
present-∩-deferred accounting with the severity ceiling, the fail-safe across every read
(never a silent `clean`), and the durable record — all deterministically, no agents.
"""
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PT = _load(os.path.join(_HERE, "..", "panel_tally.py"), "panel_tally")


def _f(file, line, title, severity, dimension="Code", evidence="repro"):
    return {"file": file, "line": line, "title": title, "severity": severity,
            "dimension": dimension, "evidence": evidence}


def test_layout_helpers_compose_run_key_dir():
    assert PT.findings_path("/run", 2, "security").endswith("/run/round-2/findings-security.json")
    assert PT.deferred_set_path("/run").endswith("/run/deferred-set.json")
    assert PT.verdict_path("/run", 3).endswith("/run/round-3/verdict.json")


def test_compile_dedupes_by_location_keeps_higher_severity_unions_dimensions():
    findings = [
        _f("a.py", 10, "Off-by-one", "Minor", "Code"),
        _f("a.py", 10, "Off-by-one", "Important", "Security"),
    ]
    out = PT.compile_findings(findings)
    assert len(out) == 1
    assert out[0]["severity"] == "Important"
    assert "Code" in out[0]["dimension"] and "Security" in out[0]["dimension"]


def test_compile_drops_uncited_and_out_of_context():
    findings = [
        _f("a.py", None, "No line", "Important"),     # citation check
        _f(None, 5, "No file", "Important"),          # citation check
        _f("z.py", 5, "Outside", "Important"),        # out of context
        _f("a.py", 5, "Real", "Important"),
    ]
    out = PT.compile_findings(findings, context_files=["a.py"])
    assert [x["title"] for x in out] == ["Real"]


def test_compile_classifies_tradeoff_as_judgment_else_mechanical():
    j = _f("a.py", 1, "Trade-off call", "Important")
    j["tradeoff"] = True
    m = _f("b.py", 2, "One fix", "Important")
    out = {x["title"]: x for x in PT.compile_findings([j, m])}
    assert out["Trade-off call"]["classification"] == "judgment"
    assert out["One fix"]["classification"] == "mechanical"


def test_round_gate_clean_when_all_complete_no_blockers():
    gate, conf, missing = PT.round_gate([_f("a.py", 1, "nit", "Nit")], ["code", "security"], ["code", "security"])
    assert gate == "clean" and conf == "high" and missing == []


def test_round_gate_blocking_when_blocker_present():
    gate, conf, missing = PT.round_gate([_f("a.py", 1, "bug", "Important")], ["code"], ["code"])
    assert gate == "blocking" and conf == "high" and missing == []


def test_round_gate_cannot_certify_when_a_reviewer_did_not_complete():
    gate, conf, missing = PT.round_gate([], ["code", "security"], ["code"])
    assert gate == "cannot-certify" and conf == "low"


def test_round_gate_names_the_missing_review_angles():
    gate, conf, missing = PT.round_gate([], ["code", "security", "architecture"], ["code"])
    assert missing == ["security", "architecture"]


def test_confidence_low_when_a_finding_lacks_verification_evidence():
    bad = _f("a.py", 1, "bug", "Minor")
    bad["evidence"] = ""
    gate, conf, missing = PT.round_gate([bad], ["code"], ["code"])
    assert conf == "low"


def test_present_deferred_counts_same_identity_same_severity():
    f = _f("a.py", 1, "bug", "Important")
    deferred = {PT._identity(f): "Important"}
    assert PT.present_deferred([f], deferred) == 1


# #276: the blocking partition routes through circuit_breaker.is_blocking (fail-closed). These pin the
# panel-gate CONSUMER wiring — a revert to the pre-#276 case-sensitive `severity in BLOCKING` would let
# a foreign / mis-cased blocking severity (the 2026-07-06 live-escape vocabulary) read as non-blocking,
# minting a false clean. Canonical-only tests do not catch that revert; these do.
def test_round_gate_blocks_on_foreign_scale_severity():
    for sev in ("critical", "blocker", "high"):
        gate, conf, missing = PT.round_gate([_f("a.py", 1, "bug", sev)], ["code"], ["code"])
        assert gate == "blocking", sev


def test_present_deferred_counts_foreign_scale_blocker():
    f = _f("a.py", 1, "bug", "blocker")
    deferred = {PT._identity(f): "blocker"}
    assert PT.present_deferred([f], deferred) == 1


def test_present_blocking_from_dimension_results_counts_foreign_scale():
    results = {"code": {"status": "run", "dimension": "Code",
                        "findings": [_f("a.py", 1, "bug", "critical")]}}
    assert PT.present_blocking_from_dimension_results(results) == 1


def test_minor_and_nit_still_do_not_block_case_insensitively():
    for sev in ("Minor", "minor", "Nit", "nit"):
        gate, conf, missing = PT.round_gate([_f("a.py", 1, "nit", sev)], ["code"], ["code"])
        assert gate == "clean", sev


def test_present_deferred_excludes_severity_escalation():
    # deferred at Important; re-flagged at Critical → NOT deferred (severity ceiling)
    f = _f("a.py", 1, "bug", "Critical")
    deferred = {PT._identity(f): "Important"}
    assert PT.present_deferred([f], deferred) == 0


def test_present_deferred_counts_severity_downgrade():
    f = _f("a.py", 1, "bug", "Important")
    deferred = {PT._identity(f): "Critical"}
    assert PT.present_deferred([f], deferred) == 1


def test_present_deferred_ignores_identities_not_present_this_round():
    f = _f("a.py", 1, "bug", "Important")
    deferred = {"other.py::stale": "Important"}
    assert PT.present_deferred([f], deferred) == 0


def test_present_deferred_excludes_different_issue_at_same_location():
    # deferral is keyed by file::normalized_title, so a DIFFERENT issue at the same file is a
    # new, non-deferred blocker (FR-10) — not silently inheriting the earlier deferral.
    deferred = {PT._identity(_f("a.py", 1, "bug one", "Important")): "Important"}
    other = _f("a.py", 1, "a different bug", "Important")
    assert PT.present_deferred([other], deferred) == 0


def _terminal(gate="blocking", present=0, deferred=0, fix="completed", rnd=1, mx=7, brk=False):
    return PT.decide_terminal(gate, present, deferred, fix, rnd, mx, brk)[0]


def test_terminal_cannot_certify_with_no_fixable_blocker_parks():
    # #212 fix-before-park: cannot-certify parks IMMEDIATELY only when there is nothing to fix
    # (no blocker, or every blocker already deferred) — coverage is then the sole gap.
    assert _terminal(gate="cannot-certify", present=0, deferred=0) == "cannot-certify"
    assert _terminal(gate="cannot-certify", present=2, deferred=2) == "cannot-certify"


def test_terminal_cannot_certify_with_unresolved_blockers_routes_to_fix():
    # #212: a cannot-certify round that STILL holds unresolved blockers routes to the fix leg like a
    # blocking round — the findings are real regardless of the uncertified seat. Certification stays
    # withheld (the next round's gate re-dooms the seat); it is NOT parked-without-fix here.
    assert _terminal(gate="cannot-certify", present=2, deferred=0, rnd=1, mx=7) == "continue"


def test_terminal_cannot_certify_blockers_still_halt_at_cap_and_on_fix_failure():
    # routing to the fix leg never converts cannot-certify into a clean exit: it can only continue
    # (under cap) or halt (cap / failed fix / breaker).
    assert _terminal(gate="cannot-certify", present=2, deferred=0, rnd=7, mx=7) == "halted"
    assert _terminal(gate="cannot-certify", present=2, deferred=0, fix="failed") == "halted"
    assert _terminal(gate="cannot-certify", present=2, deferred=0, brk=True) == "halted"


def test_terminal_fix_failed_is_halted_before_loop_state():
    assert _terminal(gate="blocking", present=1, deferred=0, fix="failed") == "halted"


def test_terminal_clean_when_no_blockers():
    assert _terminal(gate="clean", present=0, deferred=0) == "clean"


def test_terminal_continue_when_nondeferred_blockers_and_under_cap():
    assert _terminal(gate="blocking", present=2, deferred=0, rnd=1, mx=7) == "continue"


def test_terminal_clean_with_skips_when_all_blockers_deferred():
    assert _terminal(gate="blocking", present=2, deferred=2, rnd=1, mx=7) == "clean-with-skips"


def test_terminal_halted_at_cap_with_nondeferred_blockers():
    assert _terminal(gate="blocking", present=2, deferred=0, rnd=7, mx=7) == "halted"


def test_terminal_halted_when_breaker_halt_set():
    assert _terminal(gate="blocking", present=1, deferred=0, fix="completed", rnd=1, mx=7, brk=True) == "halted"


def _seed(tmp_path, rnd, per_reviewer):
    rd = os.path.join(str(tmp_path), "round-%d" % rnd)
    os.makedirs(rd, exist_ok=True)
    for reviewer, findings in per_reviewer.items():
        with open(os.path.join(rd, "findings-%s.json" % reviewer), "w") as fh:
            json.dump(findings, fh)


def test_tally_empty_roster_rejected_as_cannot_certify(tmp_path):
    v = PT.tally(str(tmp_path), 1, [], context_files=None)
    assert v["terminal"] == "cannot-certify" and v["gate"] == "cannot-certify"


def test_tally_clean_round_writes_durable_record(tmp_path):
    _seed(tmp_path, 1, {"code": [], "security": []})
    v = PT.tally(str(tmp_path), 1, ["code", "security"])
    assert v["terminal"] == "clean" and v["gate"] == "clean"
    rec = json.load(open(PT.result_path(str(tmp_path))))
    assert rec["action"] == "exit_clean" and "clean" in rec["reason"]


def test_tally_missing_findings_file_biases_cannot_certify_not_clean(tmp_path):
    # security file absent → that reviewer did not complete → coverage gap, never silent clean
    _seed(tmp_path, 1, {"code": []})
    v = PT.tally(str(tmp_path), 1, ["code", "security"])
    assert v["terminal"] == "cannot-certify"


def test_tally_malformed_findings_file_is_failsafe_non_clean(tmp_path):
    rd = os.path.join(str(tmp_path), "round-1")
    os.makedirs(rd, exist_ok=True)
    open(os.path.join(rd, "findings-code.json"), "w").write("{ not json")
    v = PT.tally(str(tmp_path), 1, ["code"])
    assert v["terminal"] == "cannot-certify"


def test_tally_fix_failed_yields_halted(tmp_path):
    _seed(tmp_path, 2, {"code": [_f("a.py", 1, "bug", "Important")]})
    v = PT.tally(str(tmp_path), 2, ["code"], fix_status="failed")
    assert v["terminal"] == "halted"


def test_tally_is_deterministic_and_idempotent(tmp_path):
    _seed(tmp_path, 1, {"code": [_f("a.py", 1, "bug", "Important")]})
    a = PT.tally(str(tmp_path), 1, ["code"])
    b = PT.tally(str(tmp_path), 1, ["code"])
    assert a == b


def test_tally_clean_with_skips_when_present_blocker_is_deferred(tmp_path):
    blocker = _f("a.py", 1, "known issue", "Important")
    _seed(tmp_path, 1, {"code": [blocker]})
    with open(PT.deferred_set_path(str(tmp_path)), "w") as fh:
        json.dump({PT._identity(blocker): "Important"}, fh)
    v = PT.tally(str(tmp_path), 1, ["code"])
    assert v["terminal"] == "clean-with-skips"


def test_tally_malformed_deferred_set_does_not_mint_clean_with_skips(tmp_path):
    # the most dangerous silent-clean vector: a corrupt deferred-set must NOT read as
    # "everything deferred" → the present blocker still counts → never clean/clean-with-skips.
    _seed(tmp_path, 1, {"code": [_f("a.py", 1, "known issue", "Important")]})
    open(PT.deferred_set_path(str(tmp_path)), "w").write("{ not json")
    v = PT.tally(str(tmp_path), 1, ["code"])
    assert v["terminal"] == "continue" and v["gate"] == "blocking"


def test_tally_cannot_certify_names_missing_angle_and_reports_finishers(tmp_path):
    _seed(tmp_path, 1, {"code": [_f("a.py", 1, "bug", "Minor")]})  # security absent
    v = PT.tally(str(tmp_path), 1, ["code", "security"])
    assert v["terminal"] == "cannot-certify"
    assert v["missing"] == ["security"] and "security" in v["reason"]
    assert any(f["title"] == "bug" for f in v["findings"])  # the finisher's findings still reported


def test_schema_version_on_every_verdict(tmp_path):
    _seed(tmp_path, 1, {"code": []})
    v = PT.tally(str(tmp_path), 1, ["code"])
    assert v["schemaVersion"] == PT.SCHEMA_VERSION


def test_synthesized_findings_used_instead_of_compiling(tmp_path):
    # raw findings on disk have a blocker; the synthesized set dropped it -> clean
    _seed(tmp_path, 1, {"code": [_f("a.py", 1, "bug", "Important")]})
    synth = {"findings": [], "drops": [{"id": "a.py::bug", "title": "bug",
             "reason": "stale", "was_blocking_tagged": True}]}
    v = PT.tally(str(tmp_path), 1, ["code"], synthesized=synth)
    assert v["terminal"] == "clean"
    assert v["drops"][0]["was_blocking_tagged"] is True


def test_verify_fail_blocks_clean(tmp_path):
    _seed(tmp_path, 1, {"code": []})  # would be clean
    v = PT.tally(str(tmp_path), 1, ["code"], verify_result="fail")
    assert v["terminal"] == "halted" and "verify" in v["reason"].lower()


def test_verify_timeout_named_distinctly(tmp_path):
    _seed(tmp_path, 1, {"code": []})
    v = PT.tally(str(tmp_path), 1, ["code"], verify_result="timeout")
    assert v["terminal"] == "halted" and "timed out" in v["reason"].lower()


def test_verify_pass_allows_clean(tmp_path):
    _seed(tmp_path, 1, {"code": []})
    assert PT.tally(str(tmp_path), 1, ["code"], verify_result="pass")["terminal"] == "clean"


def test_verify_skipped_allows_clean_unverified(tmp_path):
    _seed(tmp_path, 1, {"code": []})
    assert PT.tally(str(tmp_path), 1, ["code"], verify_result="skipped")["terminal"] == "clean"


def test_resume_round_is_one_when_empty(tmp_path):
    assert PT.resume_round(str(tmp_path)) == 1


def test_resume_round_skips_partial_round(tmp_path):
    # round 1 fully saved (verdict.json), round 2 partial (dir only) -> resume at 2
    _seed(tmp_path, 1, {"code": []})
    PT.tally(str(tmp_path), 1, ["code"])              # writes round-1/verdict.json
    os.makedirs(os.path.join(str(tmp_path), "round-2"), exist_ok=True)  # partial, no verdict
    assert PT.resume_round(str(tmp_path)) == 2


def test_recurring_blocker_halts_via_internal_breaker(tmp_path):
    blk = [_f("a.py", 1, "bug", "Important")]
    _seed(tmp_path, 1, {"code": blk}); PT.tally(str(tmp_path), 1, ["code"])
    _seed(tmp_path, 2, {"code": blk}); v = PT.tally(str(tmp_path), 2, ["code"])
    assert v["terminal"] == "halted"  # same blocker recurred -> circuit breaker


def test_extras_threaded_into_verdict(tmp_path):
    _seed(tmp_path, 1, {"code": []})
    extras = {"fixes": ["did a thing"], "parentOrigin": "plan"}
    v = PT.tally(str(tmp_path), 1, ["code"], extras=extras)
    assert v["fixes"] == ["did a thing"] and v["parentOrigin"] == "plan"


def test_extras_cannot_override_decision_fields(tmp_path):
    # a caller's extras must never overwrite terminal/gate (UFR-9: keep the sentinel fail-closed)
    _seed(tmp_path, 1, {"code": [_f("a.py", 1, "bug", "Important")]})  # would be `continue`
    v = PT.tally(str(tmp_path), 1, ["code"], extras={"terminal": "clean", "gate": "clean"})
    assert v["terminal"] == "continue" and v["gate"] == "blocking"


def test_no_net_progress_halts_via_internal_breaker(tmp_path):
    # distinct blockers each round (no recurrence) but a non-decreasing count -> criterion 2 halt
    v = None
    for n, titles in [(1, ["a", "b"]), (2, ["c", "d"]), (3, ["e", "f"])]:
        _seed(tmp_path, n, {"code": [_f("f%d.py" % i, 1, t, "Important")
                                     for i, t in enumerate(titles)]})
        v = PT.tally(str(tmp_path), n, ["code"])
    assert v["terminal"] == "halted"  # blocking count 2 -> 2 -> 2, no net progress


def test_write_failure_fails_closed_with_record_missing(tmp_path, monkeypatch):
    _seed(tmp_path, 1, {"code": []})
    monkeypatch.setattr(PT, "_atomic_write_json",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    v = PT.tally(str(tmp_path), 1, ["code"])
    assert v["terminal"] == "halted" and v.get("recordMissing") is True


def test_round_gate_low_when_final_clean_lacks_receipt():
    result = {"status": "run", "findings": [], "confidence": "high"}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_baseline_clean_is_low_confidence():
    result = {"status": "run", "findings": [], "confidence": "low"}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=False)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_confidence_missing():
    result = {"status": "run", "findings": []}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=False)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_high_when_final_clean_has_receipt():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "run-1:round-3", "chain": [{"step": "citation", "evidence": "reviewed source citations"}, {"step": "reachability", "evidence": "validated changed call path"}, {"step": "missing-check", "evidence": "searched for uncovered FRs"}, {"step": "tooling", "evidence": "pytest smoke passed"}], "coverageDecisionIds": ["RCD-1"]}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True, receipt_context={"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]})
    assert gate == "clean"
    assert conf == "high"


def test_round_gate_high_when_final_clean_is_external_review_without_receipt():
    # externalReview (#38/receipt-fabrication fix): an external-engine reviewer structurally has
    # no native chain-of-verification receipt to offer. It must still pass the final-confirmation
    # check as an honestly-labeled alternate confirmation path, not fail closed for lacking one.
    result = {"status": "run", "findings": [], "confidence": "high", "externalReview": "codex"}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True)
    assert gate == "clean"
    assert conf == "high"


def test_round_gate_low_when_receipt_has_labels_without_evidence():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"chain": ["citation", "reachability", "missing-check", "tooling"]}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_receipt_artifact_is_stale():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "old-run", "chain": [{"step": "citation", "evidence": "x"}, {"step": "reachability", "evidence": "x"}, {"step": "missing-check", "evidence": "x"}, {"step": "tooling", "evidence": "x"}], "coverageDecisionIds": ["RCD-1"]}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True, receipt_context={"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]})
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_receipt_omits_current_decision():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "run-1:round-3", "chain": [{"step": "citation", "evidence": "x"}, {"step": "reachability", "evidence": "x"}, {"step": "missing-check", "evidence": "x"}, {"step": "tooling", "evidence": "x"}], "coverageDecisionIds": []}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True, receipt_context={"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]})
    assert gate == "cannot-certify"
    assert conf == "low"


def test_carried_blocker_counts_but_is_marked_carried():
    carried = {"status": "skipped", "carriedFromRound": 1, "findings": [{"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}]}
    compiled = PT.compile_dimension_results({"code": carried})
    assert compiled[0]["carried"] is True
    assert compiled[0]["sourceRound"] == 1


# ── uncertified_reason: honest cannot-certify reason (#212) ──
def test_uncertified_reason_names_receipt_missing_seat():
    results = {"premortem-reviewer": {"status": "run", "confidence": "low", "receiptMissing": True, "findings": []}}
    reason = PT.uncertified_reason(results, ["premortem-reviewer"])
    assert reason == "premortem-reviewer returned no verification receipt after retry (receipt-missing — uncertifiable)"


def test_uncertified_reason_distinguishes_the_defect_classes():
    assert "receipt-stale" in PT.uncertified_reason({"s": {"status": "run", "confidence": "low", "receiptStale": True}}, ["s"])
    assert "malformed" in PT.uncertified_reason({"s": {"status": "missing", "confidence": "low", "malformed": True}}, ["s"])
    assert "genuinely-incomplete" in PT.uncertified_reason({"s": {"status": "run", "confidence": "low"}}, ["s"])
    assert "coverage-gap" in PT.uncertified_reason({}, ["s"])  # seat absent entirely


def test_uncertified_reason_none_when_every_seat_certified():
    results = {"code": {"status": "run", "confidence": "high"},
               "ext": {"status": "run", "confidence": "high", "externalReview": "codex"},
               "carried": {"status": "skipped", "confidence": "high"}}
    assert PT.uncertified_reason(results, ["code", "ext", "carried"]) is None


def test_uncertified_reason_joins_multiple_uncertifiable_seats_and_skips_certified():
    results = {"code": {"status": "run", "confidence": "high"},
               "premortem-reviewer": {"status": "run", "confidence": "low", "receiptMissing": True},
               "test-reviewer": {"status": "missing", "confidence": "low", "malformed": True}}
    reason = PT.uncertified_reason(results, ["code", "premortem-reviewer", "test-reviewer"])
    assert "code" not in reason.split("—")[0]  # the certified seat is not named
    assert "premortem-reviewer returned no verification receipt" in reason
    assert "test-reviewer did not return a usable result" in reason
    assert "; " in reason
