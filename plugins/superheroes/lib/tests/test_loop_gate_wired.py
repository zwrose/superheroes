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

# Every surviving review-crew fix-then-re-review loop runs THROUGH a script-owned scheduler
# that wraps the deterministic continuation deciders and emits the next round's schedule.
# review-spec via `spec_loop_plan.py decide` (#164). review-code (#507) collapsed its per-round
# choreography into the ONE entrypoint `round_driver.py`; its SKILL.md invocation is rewritten in
# a later order (phase 3), so this test pins the DRIVER'S OWN CONTRACT here (see
# test_round_driver_is_the_one_entrypoint) rather than the phase-3 SKILL prose. (The plan/tasks
# legs that called `loop_state.py" --round` directly retired in S1 train 2 (#469); audit-debt's
# loop is loop-until-dry discovery, intentionally not gate-wrapped.)
GATE_WRAPPED_SKILLS = {
    "review-spec": [
        'spec_loop_plan.py" decide --session-dir',
        'spec_loop_plan.py" record --session-dir',
        'spec_loop_plan.py" plan --session-dir',
    ],
}


def _read(skill):
    with open(os.path.join(SKILLS, skill, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


def test_gate_wrapped_skills_invoke_their_wrapper():
    missing = []
    for skill, markers in GATE_WRAPPED_SKILLS.items():
        text = _read(skill)
        for marker in markers:
            if marker not in text:
                missing.append("%s: %s" % (skill, marker))
    assert not missing, "gate wrapper not actually invoked — missing: " + ", ".join(missing)


def test_spec_loop_plan_wires_the_continuation_gate():
    """The wrapper must genuinely delegate the continue/exit decision to loop_state (and the
    round schedule to the parity-locked shared policy) — not reimplement either. A source-level
    pin so the wiring can't silently drop while the SKILL.md marker still matches."""
    path = os.path.join(SKILLS, "..", "lib", "spec_loop_plan.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert "import loop_state" in src and "loop_state.decide(" in src
    assert "import review_round_policy" in src and "review_round_policy.plan_round(" in src


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
        "skills/review-spec/SKILL.md",
        "skills/review-code/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "reference/review-loop.md" in text
        assert "coverage decisions" in text
