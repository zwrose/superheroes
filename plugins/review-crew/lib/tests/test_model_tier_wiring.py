"""FR-7 (half a): every review-crew skill that dispatches specialists is wired to the
model-tier knob with overrides, and the skills that dispatch specialists are exactly the
wired set. The workhorse half of FR-7 lives in plugins/workhorse/lib/tests/ (separate
process)."""
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", "..", "skills"))

# The in-scope registry: review-crew skills that dispatch specialists and must be wired.
WIRED = ("review-code", "review-spec", "review-plan", "review-tasks", "audit-debt")

# A skill that dispatches specialists carries this section heading.
DISPATCH_MARKER = "Dispatch Specialists"

RESOLVE_MARKERS = ("model_tier_resolve.py", "model_tier_overrides.py", "--overrides")
APPLY_MARKER = "model: $DEEP_MODEL"


def _read(skill):
    with open(os.path.join(SKILLS, skill, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("skill", WIRED)
def test_wired_skill_resolves_and_applies(skill):
    t = _read(skill)
    for marker in RESOLVE_MARKERS:
        assert marker in t, f"{skill}: missing resolve marker {marker!r}"
    assert APPLY_MARKER in t, f"{skill}: missing apply marker {APPLY_MARKER!r}"


def test_dispatchers_are_exactly_the_wired_set():
    """The skills carrying the dispatch marker must be EXACTLY the wired set. Set-equality
    (not just 'no extras') so the guard also fails if the heuristic ever stops matching a
    wired skill — otherwise it could pass vacuously and miss the unwired point it exists
    to catch."""
    dispatchers = set()
    for name in sorted(os.listdir(SKILLS)):
        skill_md = os.path.join(SKILLS, name, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        with open(skill_md, encoding="utf-8") as fh:
            if DISPATCH_MARKER in fh.read():
                dispatchers.add(name)
    assert dispatchers == set(WIRED), (
        "skills carrying the dispatch marker must be exactly the wired set; "
        f"unwired/new: {sorted(dispatchers - set(WIRED))}; "
        f"wired-but-marker-missing: {sorted(set(WIRED) - dispatchers)}"
    )
