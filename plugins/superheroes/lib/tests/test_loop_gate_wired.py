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

# The skills whose loops fix/revise and then must re-review until clean. (audit-debt's loop
# is loop-until-dry discovery, not fix-then-re-review; it is intentionally not in this set.)
LOOPING_SKILLS = ("review-code", "review-plan", "review-tasks", "review-spec")


def _read(skill):
    with open(os.path.join(SKILLS, skill, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


def test_looping_skills_invoke_the_continuation_gate():
    # Match the INVOCATION shape (`loop_state.py" --round`), not a bare mention — review-code
    # also references loop_state.py in prose (the Common-Mistakes row), which must not let a
    # skill that dropped the actual call pass vacuously.
    missing = [s for s in LOOPING_SKILLS if 'loop_state.py" --round' not in _read(s)]
    assert not missing, "continuation gate not actually invoked in: " + ", ".join(missing)


def test_loop_state_lib_exists():
    assert os.path.isfile(os.path.join(SKILLS, "..", "lib", "loop_state.py"))
