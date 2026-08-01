# Structural check that I2 wired the heroes into the registry record + coalesced nudge.
import os
import re
import pytest

from skill_surface import surface_text

_SKILLS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills")

ASK_RECORD_SKILLS = ["review-init",
                     "review-spec", "review-code", "audit-debt", "test-pilot-init"]
NUDGE_SKILLS = ["review-init", "review-code", "audit-debt",
                "test-pilot-init", "test-pilot-plan", "test-pilot-execute"]
# Snippet N uses $ROOT_DIR; these run skills must define it (the review-crew skills + test-pilot-init already do).
ROOTDIR_SKILLS = ["test-pilot-plan", "test-pilot-execute"]


def _skill(name):
    return surface_text(name)


# NOTE: Both test functions below are STRUCTURAL string-presence checks only.
# They verify the required substrings exist somewhere in the skill file, but do NOT
# verify correct placement or gating of the snippet (e.g. that Snippet R is inside
# the `if [ "$LOCATION" = "none" ]` block, or that Snippet N is in the resolver block).
@pytest.mark.parametrize("name", ASK_RECORD_SKILLS)
def test_ask_branch_records_greenfield_pick(name):
    body = _skill(name)
    assert "mode_reconcile.py" in body and "reconcile --mode" in body, \
        f"{name} must record the greenfield pick via mode_reconcile reconcile --mode (FR-3)"


@pytest.mark.parametrize("name", NUDGE_SKILLS)
def test_run_surfaces_coalesced_nudge(name):
    body = _skill(name)
    assert "mode_reconcile.py" in body and re.search(
        r'^[ \t]*NUDGE_MSG=[^\n]*mode_reconcile\.py"?[ \t]+signals\b',
        body,
        re.MULTILINE,
    ), f"{name} must surface the coalesced reconcile nudge via mode_reconcile signals (FR-7/8)"


@pytest.mark.parametrize("name", ROOTDIR_SKILLS)
def test_nudge_skill_defines_root_dir(name):
    assert "ROOT_DIR=" in _skill(name), \
        f"{name} must define ROOT_DIR before the nudge snippet uses $ROOT_DIR"


def test_review_code_declared_setup_variables_are_assigned():
    # axis: every variable SKILL.md declares reference/setup.md sets is actually assigned there
    skill_path = os.path.join(_SKILLS, "review-code", "SKILL.md")
    setup_path = os.path.join(_SKILLS, "review-code", "reference", "setup.md")

    with open(skill_path, encoding="utf-8") as fh:
        skill_text = fh.read()

    anchor_start = "Everything below depends on the variables that file sets:"
    anchor_end = ". A step below"
    start_idx = skill_text.find(anchor_start)
    if start_idx == -1:
        pytest.fail(
            "declaration sentence not found in review-code/SKILL.md: "
            "missing anchor 'Everything below depends on the variables that file sets:'"
        )
    decl_start = start_idx + len(anchor_start)
    end_idx = skill_text.find(anchor_end, decl_start)
    if end_idx == -1:
        pytest.fail(
            "declaration sentence not found in review-code/SKILL.md: "
            "missing anchor '. A step below'"
        )

    declaration = skill_text[decl_start:end_idx]
    declared = re.findall(r"`\$([A-Z_][A-Z0-9_]*)`", declaration)

    with open(setup_path, encoding="utf-8") as fh:
        setup_text = fh.read()
    assigned = set(re.findall(r"^\s*([A-Z_][A-Z0-9_]*)=", setup_text, re.MULTILINE))

    missing = sorted(set(declared) - assigned)
    assert not missing, (
        "declared variables not assigned in reference/setup.md: "
        + ", ".join(missing)
    )
