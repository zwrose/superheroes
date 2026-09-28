"""Wiring detector for the adopt-version skill roster surfaces (issue #1512 WO-B)."""
import json
import os
import re

import pytest

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILL_MD = os.path.join(_PLUGIN, "skills", "adopt-version", "SKILL.md")
_CODEX_MANIFEST = os.path.join(_PLUGIN, ".codex-plugin", "plugin.json")
_REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
_FIXTURE = os.path.join(_REPO, "eval", "skills", "fixtures", "superheroes__adopt-version.json")
_REPO_README = os.path.join(_REPO, "README.md")

_DOCTRINE_PREFIXES = ("rubric/", "skills/", "lib/", "agents/", "reference/")
_BACKTICK_PATH = re.compile(r"`([^`]+)`")


def _read_skill_text():
    with open(_SKILL_MD, encoding="utf-8") as fh:
        return fh.read()


def test_e1_adopt_version_skill_md_frontmatter():
    assert os.path.isfile(_SKILL_MD), "E1: plugins/superheroes/skills/adopt-version/SKILL.md missing"
    text = _read_skill_text()
    assert 'name: adopt-version' in text.split("---", 2)[1], "E1: frontmatter name must be adopt-version"
    assert "user-invocable: true" in text.split("---", 2)[1], "E1: user-invocable must be true"


def test_e2_codex_manifest_lists_adopt_version():
    with open(_CODEX_MANIFEST, encoding="utf-8") as fh:
        skills = json.load(fh)["skills"]
    assert "adopt-version" in skills, 'E2: .codex-plugin/plugin.json skills must contain "adopt-version"'


def test_e3_activation_fixture_nonempty():
    assert os.path.isfile(_FIXTURE), "E3: eval/skills/fixtures/superheroes__adopt-version.json missing"
    with open(_FIXTURE, encoding="utf-8") as fh:
        fx = json.load(fh)
    assert fx.get("should_fire"), "E3: should_fire must be non-empty"
    assert fx.get("should_not_fire"), "E3: should_not_fire must be non-empty"


def test_e4_readme_command_table_row():
    with open(_REPO_README, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("|") and "`/superheroes:adopt-version`" in line:
                return
    pytest.fail('E4: README.md must contain `/superheroes:adopt-version` in a table row')


def test_e5_doctrine_paths_resolve_and_helper_cited():
    text = _read_skill_text()
    assert "lib/adopt_version.py" in text, "E5: SKILL.md must cite lib/adopt_version.py (WO-A deliverable)"
    for match in _BACKTICK_PATH.finditer(text):
        rel = match.group(1)
        if not any(rel.startswith(p) for p in _DOCTRINE_PREFIXES):
            continue
        if rel == "lib/adopt_version.py":
            # WO-A lands adopt_version.py in a sibling worktree; path check deferred post-integration.
            continue
        target = os.path.join(_PLUGIN, rel)
        assert os.path.isfile(target), f"E5: doctrine path `{rel}` must resolve under plugins/superheroes"


def test_e6_adopt_version_not_a_charter_command():
    from charter_detect import COMMAND_CHARTERS

    assert "adopt-version" not in COMMAND_CHARTERS, (
        'E6: "adopt-version" must not be a key of charter_detect.COMMAND_CHARTERS'
    )
