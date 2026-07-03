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
# review-spec's gate runs THROUGH its script-owned scheduler (#164): `spec_loop_plan.py decide`
# wraps loop_state.decide and additionally emits the next round's dims_to_run.
LOOPING_SKILLS = ("review-code", "review-plan", "review-tasks")
GATE_WRAPPED_SKILLS = {"review-spec": 'spec_loop_plan.py" decide --session-dir'}


def _read(skill):
    with open(os.path.join(SKILLS, skill, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


def test_looping_skills_invoke_the_continuation_gate():
    # Match the INVOCATION shape (`loop_state.py" --round`), not a bare mention — review-code
    # also references loop_state.py in prose (the Common-Mistakes row), which must not let a
    # skill that dropped the actual call pass vacuously.
    missing = [s for s in LOOPING_SKILLS if 'loop_state.py" --round' not in _read(s)]
    assert not missing, "continuation gate not actually invoked in: " + ", ".join(missing)


def test_gate_wrapped_skills_invoke_their_wrapper():
    missing = [s for s, marker in GATE_WRAPPED_SKILLS.items() if marker not in _read(s)]
    assert not missing, "gate wrapper not actually invoked in: " + ", ".join(missing)


def test_spec_loop_plan_wires_the_continuation_gate():
    """The wrapper must genuinely delegate the continue/exit decision to loop_state (and the
    round schedule to the parity-locked shared policy) — not reimplement either. A source-level
    pin so the wiring can't silently drop while the SKILL.md marker still matches."""
    path = os.path.join(SKILLS, "..", "lib", "spec_loop_plan.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert "import loop_state" in src and "loop_state.decide(" in src
    assert "import review_round_policy" in src and "review_round_policy.plan_round(" in src


def test_loop_state_lib_exists():
    assert os.path.isfile(os.path.join(SKILLS, "..", "lib", "loop_state.py"))


from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_review_skills_reference_shared_loop_contract():
    for rel in [
        "skills/review-spec/SKILL.md",
        "skills/review-plan/SKILL.md",
        "skills/review-tasks/SKILL.md",
        "skills/review-code/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "reference/review-loop.md" in text
        assert "coverage decisions" in text
