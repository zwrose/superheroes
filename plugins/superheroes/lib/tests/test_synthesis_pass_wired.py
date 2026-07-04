"""Structural guard: standalone review-code (#174 PR 3) runs the fail-closed synthesis pass in
its compile step, delegating the keep/drop rules to `lib/loop_synthesis.py` (never reimplementing
them), and always surfaces a dropped blocker.

The spine's panel path already runs `loop_synthesis` over its merged findings; the standalone
prose path used to be mechanical-only (dedupe/citation/diff-scope). These pins fail if the
wiring silently drops out of the SKILL/reference — the same discipline as `test_loop_gate_wired`
for the continuation gate.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SKILL = os.path.join(ROOT, "skills", "review-code", "SKILL.md")
REF = os.path.join(ROOT, "skills", "review-code", "reference", "synthesis-pass.md")
LIB = os.path.join(ROOT, "lib", "loop_synthesis.py")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_synthesis_pass_reference_and_lib_exist():
    assert os.path.isfile(REF), "the synthesis-pass contract file must exist"
    assert os.path.isfile(LIB), "loop_synthesis.py (the shared fail-closed consumer) must exist"


def test_skill_compile_invokes_the_synthesis_pass():
    text = _read(SKILL)
    # The compile step wires the pass and points at its full contract.
    assert "loop_synthesis.py" in text, "SKILL.md compile step must invoke loop_synthesis.py"
    assert "reference/synthesis-pass.md" in text, "SKILL.md must reference the synthesis-pass contract"
    # The verdict is computed on post-synthesis survivors, and the raw-compile fallback is stated.
    assert "post-synthesis" in text
    assert "no findings dropped" in text.lower()


def test_skill_resolves_the_synthesis_tier_not_the_session_model():
    text = _read(SKILL)
    # Model resolved via the synthesis tier (--role synthesis), like the spine's synthesis leaf.
    assert "--role synthesis" in text and "SYNTH_MODEL" in text
    assert "model: $SYNTH_MODEL" in text, "the synthesis judge must dispatch at the synthesis tier"


def test_skill_records_and_surfaces_drops():
    text = _read(SKILL)
    # compiled.json carries drops, and the End-of-Loop Summary surfaces blocking-tagged drops.
    assert '"drops"' in text, "compiled.json must carry the synthesis drops"
    assert "was_blocking_tagged" in text, "a dropped blocker must be surfaced distinctly"
    assert "dropped as unsubstantiated" in text.lower()


def test_reference_states_the_fail_closed_contract():
    text = _read(REF)
    for phrase in ("KEEP-ON-UNCERTAIN", "DROP-WITH-REASON", "was_blocking_tagged"):
        assert phrase in text, "synthesis-pass.md must state the %s guarantee" % phrase
    # Fallback: synthesis failure / no result → raw compile with no drops.
    assert "no findings dropped" in text.lower()
    # Model resolution: the synthesis tier, never the session model.
    assert "never the session model" in text


def test_reference_delegates_the_rules_never_reimplements_them():
    text = _read(REF)
    assert "loop_synthesis.py" in text, "the pass must apply verdicts through the shared script"
    # Explicitly delegates rather than reimplementing the fail-closed rules in prose/a 2nd module.
    lowered = text.lower()
    assert "do not reimplement" in lowered or "live only in" in lowered
