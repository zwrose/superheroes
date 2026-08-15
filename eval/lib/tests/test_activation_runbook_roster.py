"""CI gate: eval/skills/README.md step-1 roster matches live plugin skills.

The activation runbook's step-1 block is load-bearing — judgment is a selection among
competing skills, so a roster missing competitors is judged against the wrong field.
This test pins the enumerated paths and the prose skill count to iter_skill_paths().
"""
import os
import re

import skills as skills_mod

# ---------------------------------------------------------------------------
# Repo root: test file lives at eval/lib/tests/ so go up 3 levels.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))

_README_PATH = os.path.join(_REPO, "eval", "skills", "README.md")
_PLUGINS_ROOT = os.path.join(_REPO, "plugins")

_STEP1_HEADING = re.compile(
    r"^### 1\. Load all (\d+) skill descriptions\s*$",
    re.MULTILINE,
)
_STEP1_ALL_DESCRIPTIONS = re.compile(
    r"Judgment must be made in the context of ALL (\d+) descriptions simultaneously",
)
_FENCED_BLOCK = re.compile(r"```\n(.*?)```", re.DOTALL)
_SKILL_PATH = re.compile(r"^plugins/[^\s]+/SKILL\.md$")


def _repo_relative(path):
    return os.path.relpath(path, _REPO).replace("\\", "/")


def _load_readme():
    with open(_README_PATH, encoding="utf-8") as fh:
        return fh.read()


def _parse_step1_heading_count(text):
    match = _STEP1_HEADING.search(text)
    if match is None:
        return None
    return int(match.group(1))


def _parse_all_descriptions_count(text):
    match = _STEP1_ALL_DESCRIPTIONS.search(text)
    if match is None:
        return None
    return int(match.group(1))


def _parse_step1_roster_paths(text):
    heading = _STEP1_HEADING.search(text)
    if heading is None:
        return None

    after_heading = text[heading.end() :]
    block_match = _FENCED_BLOCK.search(after_heading)
    if block_match is None:
        return None

    block = block_match.group(1)
    paths = []
    for line in block.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if _SKILL_PATH.fullmatch(candidate) is None:
            continue
        paths.append(candidate)
    if not paths:
        return None
    return set(paths)


def _expected_skill_paths():
    return {_repo_relative(path) for path in skills_mod.iter_skill_paths(_PLUGINS_ROOT)}


def test_activation_runbook_step1_roster_matches_disk():
    """Step-1 enumerated paths must equal iter_skill_paths under plugins/."""
    readme = _load_readme()
    roster_paths = _parse_step1_roster_paths(readme)
    assert roster_paths is not None, (
        "Could not locate eval/skills/README.md step-1 roster block — the runbook's "
        "shape changed; restore the fenced path list under "
        "'### 1. Load all N skill descriptions'."
    )

    expected_paths = _expected_skill_paths()
    assert expected_paths, (
        "iter_skill_paths found no SKILL.md files under plugins/ — roster guard would "
        "be vacuous; verify plugins layout before trusting this gate."
    )

    missing_from_readme = expected_paths - roster_paths
    extra_in_readme = roster_paths - expected_paths
    assert not missing_from_readme and not extra_in_readme, (
        "eval/skills/README.md step-1 roster drifted from iter_skill_paths — re-run the "
        "roster against iter_skill_paths and update the fenced block.  "
        f"Missing from README: {sorted(missing_from_readme)}  "
        f"Extra in README: {sorted(extra_in_readme)}"
    )


def test_activation_runbook_step1_prose_counts_match_roster():
    """Both prose skill counts must match the enumerated roster size."""
    readme = _load_readme()
    roster_paths = _parse_step1_roster_paths(readme)
    assert roster_paths is not None, (
        "Could not locate eval/skills/README.md step-1 roster block — the runbook's "
        "shape changed; restore the fenced path list under "
        "'### 1. Load all N skill descriptions'."
    )

    heading_count = _parse_step1_heading_count(readme)
    assert heading_count is not None, (
        "Could not locate eval/skills/README.md step-1 heading count — the runbook's "
        "shape changed; restore '### 1. Load all N skill descriptions'."
    )

    all_descriptions_count = _parse_all_descriptions_count(readme)
    assert all_descriptions_count is not None, (
        "Could not locate eval/skills/README.md 'ALL N descriptions' prose count — "
        "the runbook's shape changed; restore the simultaneous-judgment sentence."
    )

    roster_size = len(roster_paths)
    assert roster_size > 0, (
        "Step-1 roster parsed empty — the runbook's shape changed; restore the fenced "
        "path list under '### 1. Load all N skill descriptions'."
    )

    assert heading_count == roster_size, (
        "eval/skills/README.md step-1 heading count drifted from the enumerated roster — "
        "re-run the roster against iter_skill_paths and update 'Load all N skill "
        f"descriptions'.  Heading says {heading_count}; roster has {roster_size} paths."
    )

    assert all_descriptions_count == roster_size, (
        "eval/skills/README.md 'ALL N descriptions' count drifted from the enumerated "
        "roster — re-run the roster against iter_skill_paths and update the prose "
        f"count.  Prose says {all_descriptions_count}; roster has {roster_size} paths."
    )

    assert heading_count == all_descriptions_count, (
        "eval/skills/README.md step-1 prose counts disagree — re-run the roster against "
        "iter_skill_paths and make both counts match.  Heading says "
        f"{heading_count}; simultaneous-judgment prose says {all_descriptions_count}."
    )
