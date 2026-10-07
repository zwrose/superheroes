"""Structural guard: every review-crew fix-then-re-review loop wires the deterministic
continuation gate (`loop_state.py`).

The loop-skipping defect was an orchestrator exiting a loop early by eye. The fix moves the
continue/exit/halt decision into `loop_state.py`, which the skills must call. This test fails
if any looping skill drops that call — so the enforcement can't silently regress out of a
skill the way an inlined-prose rule could.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", "..", "skills"))

# The one surviving review-crew fix-then-re-review loop, review-code (#507), collapsed its
# per-round choreography into the ONE entrypoint `round_driver.py`; its SKILL.md invocation is
# rewritten in a later order (phase 3), so this test pins the DRIVER'S OWN CONTRACT here (see
# test_round_driver_is_the_one_entrypoint) rather than the phase-3 SKILL prose. (The plan/tasks
# legs that called `loop_state.py" --round` directly retired in S1 train 2 (#469); spec review runs no loop —
# it follows the spec checks.)


def test_round_driver_is_the_one_entrypoint():
    """#507: review-code's per-round choreography collapsed into the ONE entrypoint round_driver.py.
    The driver must genuinely delegate its JUDGMENTS to the parity-locked pure deciders — the
    audit-keyed stall breaker, the #174 confirmation economics, per-finding verification, and the
    fix-audit fold — not reimplement them. Source-level pin so the wiring can't silently drop, and
    so the retired code_loop_plan is really gone."""
    lib = os.path.join(SKILLS, "..", "lib")
    assert not os.path.exists(os.path.join(lib, "code_loop_plan.py")), \
        "code_loop_plan.py must be retired — round_driver absorbed plan/record/decide"
    path = os.path.join(lib, "round_driver.py")
    assert os.path.isfile(path), "the ONE entrypoint round_driver.py must exist"
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert "import circuit_breaker" in src and "check_audit_breaker(" in src
    assert "import review_round_policy" in src and "confirmation_followup(" in src
    assert "import verification" in src and "apply_verdicts(" in src
    assert "import audits" in src and "apply_audit_results(" in src
    # the reviewer re-dispatch budget rides its single home, never a local literal.
    assert "loop_plan_common.REDISPATCH_BUDGET" in src


def test_loop_state_lib_exists():
    assert os.path.isfile(os.path.join(SKILLS, "..", "lib", "loop_state.py"))


from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_review_skills_reference_shared_loop_contract():
    for rel in [
        "skills/review-code/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "reference/review-loop.md" in text
        assert "coverage decisions" in text
