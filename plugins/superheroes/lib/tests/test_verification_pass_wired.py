"""Structural guard: standalone review-code (#506) runs per-finding verification in its
compile step, delegating verdict rules to `lib/verification.py` (never reimplementing them),
and always surfaces a dropped blocker.

The spine's panel path already runs verification over its merged findings; the standalone
prose path used to be mechanical-only (dedupe/citation/diff-scope). These pins fail if the
wiring silently drops out of the SKILL/reference — the same discipline as `test_loop_gate_wired`
for the continuation gate.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SKILL = os.path.join(ROOT, "skills", "review-code", "SKILL.md")
REF = os.path.join(ROOT, "skills", "review-code", "reference", "verification-pass.md")
LIB = os.path.join(ROOT, "lib", "verification.py")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_verification_pass_reference_and_lib_exist():
    assert os.path.isfile(REF), "the verification-pass contract file must exist"
    assert os.path.isfile(LIB), "verification.py (the shared fail-closed consumer) must exist"


def test_skill_compile_invokes_verification():
    text = _read(SKILL)
    # The compile step wires per-finding verification and points at its full contract.
    assert (
        "verification.apply_verdicts" in text
        or ("verification.py" in text and "apply_verdicts" in text)
    ), "SKILL.md compile step must invoke verification.apply_verdicts"
    assert "reference/verification-pass.md" in text, (
        "SKILL.md must reference the verification-pass contract"
    )


def test_skill_resolves_the_verifier_tier_not_the_session_model():
    text = _read(SKILL)
    # Model resolved via the verifier tier (--role verifier), not the session model.
    assert "--role verifier" in text and "VERIFIER_MODEL" in text


def test_three_state_verdict_tokens_present_in_skill_and_reference():
    skill = _read(SKILL)
    ref = _read(REF)
    for token in ("CONFIRMED", "PLAUSIBLE", "REFUTED"):
        assert token in skill, "SKILL.md must name the %s verdict token" % token
        assert token in ref, "verification-pass.md must name the %s verdict token" % token


def test_skill_records_and_surfaces_drops():
    text = _read(SKILL)
    # compiled.json carries drops, and the End-of-Loop Summary surfaces blocking-tagged drops.
    assert '"drops"' in text, "compiled.json must carry the verification drops"
    assert "was_blocking_tagged" in text, "a dropped blocker must be surfaced distinctly"
    assert "verification dropped (REFUTED)" in text, (
        "End-of-Loop Summary must surface REFUTED drops distinctly"
    )


def test_skill_records_and_surfaces_downgrades():
    text = _read(SKILL)
    # compiled.json carries the downgrades, and the End-of-Loop Summary surfaces them for scrutiny
    # (a blocking→non-blocking demotion is a silent-drop equivalent, #186).
    assert '"downgrades"' in text, "compiled.json must carry the verification downgrades"
    assert "downgraded from blocking to non-blocking" in text.lower()


def test_reference_synthesis_narrowed_to_merge_and_rank():
    text = _read(REF)
    lowered = text.lower()
    normalized = " ".join(lowered.split())
    assert "merge_and_rank" in text, "verification-pass.md must wire synthesis via merge_and_rank"
    assert "drops nothing" in lowered, "synthesis must not drop findings"
    assert "coverage guarantee" in normalized, "merge_and_rank must carry a coverage guarantee"


def test_evidence_or_silence_wired_in_skill_and_reference():
    skill = _read(SKILL)
    ref = _read(REF)
    for label, text in (("SKILL.md", skill), ("verification-pass.md", ref)):
        assert "advisory" in text, "%s must wire the advisory disposition" % label
        assert "CONFIRMED" in text, "%s must name CONFIRMED for evidence-or-silence" % label
    ref_lower = ref.lower()
    assert "confirming probe" in ref_lower, (
        "verification-pass.md must describe the confirming probe path"
    )
    assert "never gates" in ref_lower or "never interrupts" in ref_lower, (
        "verification-pass.md must state PLAUSIBLE Critical never GATEs/interrupts"
    )


def test_reference_states_keep_on_uncertain():
    text = _read(REF).lower()
    assert "keep-on-uncertain" in text, "verification-pass.md must state KEEP-ON-UNCERTAIN"
    assert "never drops a finding" in text, (
        "verification-pass.md must guarantee a model's silence never drops a finding"
    )


def test_reference_states_the_fail_closed_fallback():
    text = _read(REF).lower()
    assert "no findings dropped" in text, (
        "verification-pass.md must state the no-findings-dropped fallback"
    )
