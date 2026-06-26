# plugins/superheroes/lib/tests/test_pr_phase.py
import pr_phase


def test_already_ready_pr_skips_flip():
    # world-read says the PR is already non-draft -> idempotent skip
    assert pr_phase.mark_ready_action({"number": 7, "isDraft": False}) == "skip"


def test_draft_pr_flips():
    assert pr_phase.mark_ready_action({"number": 7, "isDraft": True}) == "flip"


def test_unreadable_pr_gates():
    assert pr_phase.mark_ready_action("unknown") == "gate"
    assert pr_phase.mark_ready_action({"number": 7}) == "gate"            # missing isDraft -> don't guess
    assert pr_phase.mark_ready_action({"number": 7, "isDraft": None}) == "gate"  # null isDraft -> don't guess


def test_status_guard_blocks_mark_ready_when_not_ok():
    decision = pr_phase.mark_ready_status_action({"ok": False, "reason": "test-pilot stale"})
    assert decision == {"action": "gate", "reason": "test-pilot stale"}


def test_status_guard_allows_mark_ready_when_ok():
    assert pr_phase.mark_ready_status_action({"ok": True}) == {"action": "proceed"}


def test_status_guard_gates_malformed_result():
    decision = pr_phase.mark_ready_status_action("oops")
    assert decision["action"] == "gate"
    assert "test-pilot status" in decision["reason"]
