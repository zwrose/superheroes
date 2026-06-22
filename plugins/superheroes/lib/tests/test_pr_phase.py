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
