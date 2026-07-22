from circuit_breaker import normalize_title, finding_identity, check_circuit_breaker


def rnd(num, findings):
    return {"round": num, "findings": findings}


def imp(title, file="src/a.ts"):
    return {"id": "x-001", "severity": "Important", "dimension": "Code",
            "title": title, "file": file, "line": 1, "body": "", "suggestion": None}


def minor(title, file="src/a.ts"):
    f = imp(title, file)
    f["severity"] = "Minor"
    return f


def test_normalize_title_lowercases_strips_punct_collapses_ws():
    assert normalize_title("Missing userId Filter!") == "missing userid filter"
    assert normalize_title("  Extra   spaces  ") == "extra spaces"
    assert normalize_title("Punctuation, removed.") == "punctuation removed"


def test_normalize_title_is_ascii_word_only():
    # JS \w is ASCII-only; the Python port must match (re.ASCII), so accented
    # letters are treated as punctuation and stripped.
    assert normalize_title("Café Über") == "caf ber"


def test_finding_identity_combines_file_and_title():
    assert finding_identity({"file": "src/a.ts", "title": "Missing Filter"}) == "src/a.ts::missing filter"


def test_finding_identity_falls_back_to_summary_when_title_missing():
    assert finding_identity({"file": "src/a.ts", "summary": "Missing Filter"}) == "src/a.ts::missing filter"


def test_finding_identity_null_file_is_empty_string():
    assert finding_identity({"file": None, "title": "X"}) == "::x"


def test_no_halt_with_no_rounds():
    assert check_circuit_breaker([], 7)["halt"] is False


def test_no_halt_single_round_in_progress():
    assert check_circuit_breaker([rnd(1, [imp("a"), imp("b")])], 7)["halt"] is False


def test_halts_on_recurring_finding():
    r = [rnd(1, [imp("Missing userId filter")]), rnd(2, [imp("Missing userId filter")])]
    res = check_circuit_breaker(r, 7)
    assert res["halt"] is True
    assert res["reason"] == "recurring-finding"


def test_ignores_minor_recurrence():
    r = [rnd(1, [minor("style x")]), rnd(2, [minor("style x")])]
    assert check_circuit_breaker(r, 7)["halt"] is False


def test_no_halt_when_blocking_strictly_decreases():
    r = [rnd(1, [imp("a"), imp("b"), imp("c")]), rnd(2, [imp("d"), imp("e")]), rnd(3, [imp("f")])]
    assert check_circuit_breaker(r, 7)["halt"] is False


def test_halts_on_no_net_progress_two_transitions():
    r = [rnd(1, [imp("a"), imp("b")]), rnd(2, [imp("c"), imp("d")]), rnd(3, [imp("e"), imp("g")])]
    res = check_circuit_breaker(r, 7)
    assert res["halt"] is True
    assert res["reason"] == "no-net-progress"


def test_no_halt_single_flat_transition():
    r = [rnd(1, [imp("a"), imp("b")]), rnd(2, [imp("c"), imp("d")])]
    assert check_circuit_breaker(r, 7)["halt"] is False


def test_halts_at_max_iterations_with_blocking():
    r = [rnd(1, [imp("a")]), rnd(2, [imp("a")])]
    res = check_circuit_breaker(r, 2)
    assert res["halt"] is True
    assert res["reason"] == "max-iterations"


def test_max_iterations_detail_reports_actual_round_and_no_fix():
    # The cap-halt fires right after a review, before the fix leg — the latest round carries no
    # recorded fix, so the detail must not claim any were committed (the #212 honest-reason class).
    r = [rnd(1, [imp("a")]), rnd(2, [imp("a")])]
    res = check_circuit_breaker(r, 2)
    assert res["detail"] == (
        "Reached round 2 (cap 2); the latest review still showed 1 blocking finding(s) "
        "(no fix was applied this round — the finding(s) remain unaddressed)."
    )


def test_max_iterations_detail_reports_round_past_cap_on_resume():
    # A resume can run past the cap: n (actual round) must appear, not the cap value (the round-count
    # bug — the message used to print the cap even when the loop was several rounds beyond it).
    r = [rnd(1, [imp("a")]), rnd(2, [imp("b")]), rnd(3, [imp("c")])]
    res = check_circuit_breaker(r, 2)
    assert res["halt"] is True
    assert res["reason"] == "max-iterations"
    assert res["detail"].startswith("Reached round 3 (cap 2);")
    assert "no fix was applied this round" in res["detail"]


def test_max_iterations_detail_claims_fix_only_when_round_recorded_one():
    # When the final round DID record applied fixes, the "committed but not re-reviewed" wording is
    # truthful and is emitted; the signal is rec['fix']['fixes'] on the latest round.
    latest = rnd(2, [imp("a")])
    latest["fix"] = {"fixes": [{"title": "a", "file": "src/a.ts"}]}
    r = [rnd(1, [imp("a")]), latest]
    res = check_circuit_breaker(r, 2)
    assert res["detail"] == (
        "Reached round 2 (cap 2); the latest review still showed 1 blocking finding(s) "
        "(the final round's fixes are committed but not yet re-reviewed)."
    )


def test_max_iterations_empty_fix_list_is_not_treated_as_a_recorded_fix():
    latest = rnd(2, [imp("a")])
    latest["fix"] = {"fixes": []}  # fix leg ran but recorded nothing → still "no fix applied"
    r = [rnd(1, [imp("a")]), latest]
    res = check_circuit_breaker(r, 2)
    assert "no fix was applied this round" in res["detail"]


def test_max_iterations_detail_does_not_overstate_reviews_when_a_round_was_unreviewed():
    # A transport-failed / all-missing round inflates n (which the gate uses), but the honest message
    # must not imply it was a real review — it names how many of the recorded rounds were reviewed.
    unreviewed = {"round": 1, "findings": [], "dimensions": {"code-reviewer": {"status": "missing"}}}
    r = [unreviewed, rnd(2, [imp("a")])]
    res = check_circuit_breaker(r, 2)
    assert res["reason"] == "max-iterations"
    assert res["detail"].startswith("Reached round 2 (cap 2, 1 reviewed);")


def test_max_iterations_detail_omits_reviewed_note_when_all_rounds_were_reviewed():
    # The qualifier only appears when it adds information; the common all-reviewed case stays clean.
    r = [rnd(1, [imp("a")]), rnd(2, [imp("a")])]
    res = check_circuit_breaker(r, 2)
    assert "reviewed)" not in res["detail"]
    assert res["detail"].startswith("Reached round 2 (cap 2);")


def test_no_halt_at_max_iterations_once_resolved():
    r = [rnd(1, [imp("a")]), rnd(2, [])]
    assert check_circuit_breaker(r, 2)["halt"] is False


def _run21_reviewers():
    return [
        "architecture-reviewer", "code-reviewer", "security-reviewer",
        "test-reviewer", "premortem-reviewer",
    ]


def _all_missing_dims():
    return {r: {"status": "missing", "findings": [], "confidence": "low"} for r in _run21_reviewers()}


def _all_run_dims():
    return {r: {"status": "run", "findings": [], "confidence": "high"} for r in _run21_reviewers()}


def _blocking_three(suffix=""):
    tag = f" {suffix}".rstrip()
    return [
        {"file": "plugins/superheroes/lib/acceptance_run.py", "title": f"layering{tag}", "severity": "Important", "dimension": "Architecture"},
        {"file": "plugins/superheroes/lib/acceptance_deps.py", "title": f"deps{tag}", "severity": "Critical", "dimension": "Security"},
        {"file": "plugins/superheroes/lib/acceptance_launch.py", "title": f"launch{tag}", "severity": "Important", "dimension": "Code"},
    ]


def test_ignores_transport_failed_round_for_no_net_progress():
    rounds = [
        {"round": 1, "findings": [], "dimensions": _all_missing_dims()},
        {"round": 2, "findings": _blocking_three("r2"), "dimensions": _all_run_dims()},
        {"round": 3, "findings": _blocking_three("r3"), "dimensions": _all_run_dims()},
    ]
    assert check_circuit_breaker(rounds, 7)["halt"] is False


def test_halts_on_three_real_review_round_plateau():
    rounds = [
        {"round": 1, "findings": _blocking_three("a"), "dimensions": _all_run_dims()},
        {"round": 2, "findings": _blocking_three("b"), "dimensions": _all_run_dims()},
        {"round": 3, "findings": _blocking_three("c"), "dimensions": _all_run_dims()},
    ]
    res = check_circuit_breaker(rounds, 7)
    assert res["halt"] is True
    assert res["reason"] == "no-net-progress"


# --- check_audit_breaker (#507) ----------------------------------------------

from circuit_breaker import check_audit_breaker


def a_round(num, outcomes):
    return {"round": num, "outcomes": outcomes}


def nd(identity, **extra):
    d = {"identity": identity, "ruling": "not-discharged"}
    d.update(extra)
    return d


def dis(identity, **extra):
    d = {"identity": identity, "ruling": "discharged"}
    d.update(extra)
    return d


def test_audit_breaker_empty_history_no_halt():
    res = check_audit_breaker([], 7)
    assert res["halt"] is False
    assert res["reason"] is None
    assert res["stalledIdentities"] == []


def test_audit_breaker_stalls_on_two_consecutive_not_discharged():
    rounds = [a_round(1, [nd("src/a.py::leak")]),
              a_round(2, [nd("src/a.py::leak")])]
    res = check_audit_breaker(rounds, 7)
    assert res["halt"] is True
    assert res["reason"] == "audit-stall"
    assert "src/a.py::leak" in res["stalledIdentities"]


def test_audit_breaker_no_stall_when_audits_alternate():
    rounds = [a_round(1, [nd("src/a.py::leak")]),
              a_round(2, [dis("src/a.py::leak")]),
              a_round(3, [nd("src/a.py::leak")])]
    res = check_audit_breaker(rounds, 7)
    assert res["halt"] is False


def test_audit_breaker_alias_retitle_still_stalls():
    # identity STRINGS differ (a retitle) but both share a stored classKey → alias-tolerant
    # matching still detects the stall.
    rounds = [
        a_round(1, [nd("src/a.py::leaks memory", classKey="Security::CWE-401::orig")]),
        a_round(2, [nd("src/a.py::memory not freed", classKey="Security::CWE-401::orig")]),
    ]
    res = check_audit_breaker(rounds, 7)
    assert res["halt"] is True
    assert res["reason"] == "audit-stall"


def test_audit_breaker_max_iterations_with_open_finding():
    rounds = [a_round(1, [nd("f::a")]),
              a_round(2, [dis("f::a"), nd("f::b")])]
    res = check_audit_breaker(rounds, 2)
    assert res["halt"] is True
    assert res["reason"] == "max-iterations"
    assert res["stalledIdentities"] == ["f::b"]


def test_audit_breaker_no_max_iterations_when_all_discharged():
    rounds = [a_round(1, [dis("f::a")]),
              a_round(2, [dis("f::a"), dis("f::b")])]
    # at the cap, but nothing is open → no halt
    res = check_audit_breaker(rounds, 2)
    assert res["halt"] is False


def test_audit_breaker_never_consults_counts():
    # RISING discharged counts each round, zero not-discharged → progressing, never a halt,
    # even though a count-based breaker would see the totals climb.
    rounds = [
        a_round(1, [dis("f::a")]),
        a_round(2, [dis("f::a"), dis("f::b"), dis("f::c")]),
        a_round(3, [dis("f::a"), dis("f::b"), dis("f::c"), dis("f::d"), dis("f::e")]),
    ]
    res = check_audit_breaker(rounds, 7)
    assert res["halt"] is False
    assert res["reason"] is None


def test_audit_breaker_malformed_round_fails_closed():
    # two consecutive malformed rounds (no outcomes list) → stall, never a silent pass
    res = check_audit_breaker([{"round": 1}, {"round": 2}], 7)
    assert res["halt"] is True
    assert res["reason"] == "audit-stall"


def test_audit_breaker_malformed_outcome_counts_as_not_discharged():
    rounds = [a_round(1, ["junk"]), a_round(2, [{"identity": "f::x"}])]
    # round 1 has a non-dict outcome (fail-closed not-discharged marker); round 2 has an
    # outcome with a MISSING ruling (also fail-closed not-discharged). Different identities,
    # so no consecutive stall here, but the malformed markers are counted, not dropped.
    res = check_audit_breaker(rounds, 7)
    assert res["halt"] is False  # different identities, single round each
    # at the cap, the malformed latest round is still "open"
    assert check_audit_breaker(rounds, 2)["halt"] is True
    assert check_audit_breaker(rounds, 2)["reason"] == "max-iterations"


def test_audit_breaker_two_consecutive_malformed_outcomes_stall():
    rounds = [a_round(1, ["junk"]), a_round(2, [None])]
    res = check_audit_breaker(rounds, 7)
    assert res["halt"] is True
    assert res["reason"] == "audit-stall"
