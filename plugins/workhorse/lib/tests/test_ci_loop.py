import ci_loop


def test_novel_failure_under_cap_says_fix():
    action, _ = ci_loop.decide(["lint"], history=[], rnd=1)
    assert action == "fix"


def test_round_cap_reverts_and_gates():
    action, reason = ci_loop.decide(["lint"], history=[["x"], ["y"]], rnd=5,
                                    max_rounds=5)
    assert action == "revert_and_gate" and "cap" in reason


def test_recurring_failure_set_reverts_and_gates():
    # the same red set seen before -> no net progress -> halt
    action, reason = ci_loop.decide(["lint", "types"],
                                    history=[["types", "lint"]], rnd=3)
    assert action == "revert_and_gate" and "recurring" in reason


def test_empty_failures_fail_closed():
    action, _ = ci_loop.decide([], history=[], rnd=1)
    assert action == "revert_and_gate"


def test_bad_input_fails_closed():
    action, _ = ci_loop.decide(None, history=[], rnd=1)
    assert action == "revert_and_gate"
