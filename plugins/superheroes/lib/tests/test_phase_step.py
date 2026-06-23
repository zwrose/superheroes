# plugins/superheroes/lib/tests/test_phase_step.py
import phase_step as ps


def a(pr, gate):
    return ps.decide(pr, gate)["action"]


def test_proceed_on_passed_high_no_assumptions():
    assert a({"confidence": "high", "assumptions": []}, "passed") == "proceed"


def test_authoring_phase_none_gate_proceeds():
    assert a({"confidence": "high", "assumptions": []}, None) == "proceed"


def test_assumption_parks():
    assert a({"confidence": "high", "assumptions": ["unverified premise"]}, "passed") == "park_assumption"


def test_low_confidence_parks():
    assert a({"confidence": "low", "assumptions": []}, "passed") == "park_low_confidence"


def test_changes_requested_parks():
    assert a({"confidence": "high", "assumptions": []}, "changes-requested") == "park_changes_requested"


def test_pending_parks():
    assert a({"confidence": "high", "assumptions": []}, "pending") == "park_pending"


def test_unexpected_or_unreadable_gate_parks():
    assert a({"confidence": "high", "assumptions": []}, "weird-value") == "park_unexpected_gate"
    assert a({"confidence": "high", "assumptions": []}, "") == "park_unexpected_gate"


# ordering (the safety contract): the assumption / low-confidence parks are evaluated BEFORE the
# gate, so they win even over a *parking* gate. A gate-first decider would return
# park_changes_requested here — these cases are what distinguish the correct ordering.
def test_assumption_beats_a_parking_gate():
    assert a({"confidence": "high", "assumptions": ["x"]}, "changes-requested") == "park_assumption"


def test_low_confidence_beats_a_parking_gate():
    assert a({"confidence": "low", "assumptions": []}, "changes-requested") == "park_low_confidence"
