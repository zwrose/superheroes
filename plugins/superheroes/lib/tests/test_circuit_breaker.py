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
