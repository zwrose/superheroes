"""The adopt-version skill is wired into every roster surface the gates read.

One assertion per guarded element, each failing with a message that names the element:
the SKILL.md and its frontmatter, the Codex manifest entry, the activation fixture, the
README command-table row, the skill's plugin-relative doctrine citations, and the charter
command table (adopt-version must not change which charter a seat is detected as).
"""
import json
import os
import re
import sys

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO = os.path.dirname(os.path.dirname(_PLUGIN))
_SKILL = os.path.join(_PLUGIN, "skills", "adopt-version", "SKILL.md")
_CODEX_MANIFEST = os.path.join(_PLUGIN, ".codex-plugin", "plugin.json")
_FIXTURE = os.path.join(_REPO, "eval", "skills", "fixtures", "superheroes__adopt-version.json")
_README = os.path.join(_REPO, "README.md")

sys.path.insert(0, os.path.join(_PLUGIN, "lib"))

# lib/adopt_version.py is a separate deliverable that lands with this skill; the citation
# check requires it in the text and does not require the file on disk.
_CITED_NOT_YET_ON_DISK = {"lib/adopt_version.py"}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "E1: adopt-version SKILL.md has no frontmatter block"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_e1_skill_exists_with_name_and_user_invocable():
    assert os.path.isfile(_SKILL), "E1: plugins/superheroes/skills/adopt-version/SKILL.md is missing"
    fields = _frontmatter(_read(_SKILL))
    assert fields.get("name") == "adopt-version", "E1: SKILL.md frontmatter name is not adopt-version"
    assert fields.get("user-invocable") == "true", "E1: SKILL.md frontmatter user-invocable is not true"


def test_e2_codex_manifest_lists_adopt_version():
    with open(_CODEX_MANIFEST, encoding="utf-8") as fh:
        skills = json.load(fh)["skills"]
    assert "adopt-version" in skills, "E2: .codex-plugin/plugin.json skills lacks adopt-version"


def test_e3_activation_fixture_has_both_directions():
    assert os.path.isfile(_FIXTURE), "E3: eval/skills/fixtures/superheroes__adopt-version.json is missing"
    with open(_FIXTURE, encoding="utf-8") as fh:
        fixture = json.load(fh)
    assert fixture.get("should_fire"), "E3: fixture should_fire is empty or missing"
    assert fixture.get("should_not_fire"), "E3: fixture should_not_fire is empty or missing"


def test_e4_readme_table_row_names_the_command():
    rows = [
        line for line in _read(_README).splitlines()
        if line.startswith("|") and "`/superheroes:adopt-version`" in line
    ]
    assert rows, "E4: README.md has no table row naming `/superheroes:adopt-version`"


def test_e5_cited_doctrine_paths_resolve():
    text = _read(_SKILL)
    cited = set(re.findall(r"`((?:rubric|skills|lib|agents|reference)/[^`\s]+)`", text))
    assert "lib/adopt_version.py" in text, "E5: SKILL.md does not cite lib/adopt_version.py"
    unresolved = sorted(
        path for path in cited
        if path not in _CITED_NOT_YET_ON_DISK
        and not os.path.isfile(os.path.join(_PLUGIN, path.split(" ")[0]))
    )
    assert not unresolved, f"E5: SKILL.md cites doctrine paths that do not resolve: {unresolved}"


def test_e6_adopt_version_is_not_a_charter_command():
    import charter_detect
    assert "adopt-version" not in charter_detect.COMMAND_CHARTERS, (
        "E6: adopt-version is a key of charter_detect.COMMAND_CHARTERS"
    )
