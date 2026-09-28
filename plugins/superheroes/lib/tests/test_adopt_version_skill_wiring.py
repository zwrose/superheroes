"""The `adopt-version` skill must be wired into every roster surface the gates read.

One assertion per guarded element, each failing with a message that names the element:
the SKILL.md front door, the Codex manifest entry, the activation fixture, the README
command-table row, the doctrine paths the skill cites, and the charter-detection table
(running the skill must not change which charter a seat is detected as).
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

_DOCTRINE_PATH = re.compile(r"(?:rubric|skills|lib|agents|reference)/[A-Za-z0-9_./-]*[A-Za-z0-9_]")
# WO-A's deliverable: cited by the skill, not required on disk in this worktree.
_NEW_HELPER = "lib/adopt_version.py"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _frontmatter(text):
    lines = text.split("\n")
    assert lines and lines[0] == "---", "SKILL.md has no frontmatter opening"
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def test_e1_skill_md_exists_and_is_a_user_invocable_adopt_version():
    assert os.path.isfile(_SKILL), "E1: skills/adopt-version/SKILL.md does not exist"
    fields = _frontmatter(_read(_SKILL))
    assert fields.get("name") == "adopt-version", (
        "E1: SKILL.md frontmatter name is not 'adopt-version': %r" % fields.get("name"))
    assert fields.get("user-invocable") == "true", (
        "E1: SKILL.md frontmatter user-invocable is not true: %r" % fields.get("user-invocable"))


def test_e2_codex_manifest_lists_adopt_version():
    skills = json.loads(_read(_CODEX_MANIFEST))["skills"]
    assert "adopt-version" in skills, (
        "E2: .codex-plugin/plugin.json `skills` does not contain 'adopt-version'")


def test_e3_activation_fixture_has_both_directions():
    assert os.path.isfile(_FIXTURE), (
        "E3: eval/skills/fixtures/superheroes__adopt-version.json does not exist")
    fixture = json.loads(_read(_FIXTURE))
    assert fixture.get("should_fire"), "E3: fixture `should_fire` is missing or empty"
    assert fixture.get("should_not_fire"), "E3: fixture `should_not_fire` is missing or empty"


def test_e4_readme_command_table_has_an_adopt_version_row():
    rows = [
        line for line in _read(_README).split("\n")
        if line.startswith("|") and "`/superheroes:adopt-version`" in line
    ]
    assert rows, "E4: README.md has no table row naming `/superheroes:adopt-version`"


def test_e5_cited_doctrine_paths_resolve():
    text = _read(_SKILL)
    cited = set()
    for span in re.findall(r"`([^`\n]+)`", text):
        if _DOCTRINE_PATH.fullmatch(span):
            cited.add(span)
    assert _NEW_HELPER in text, "E5: SKILL.md does not cite %s" % _NEW_HELPER
    checked = cited - {_NEW_HELPER}
    assert checked, "E5: SKILL.md cites no plugin-relative doctrine path to resolve"
    missing = sorted(p for p in checked if not os.path.isfile(os.path.join(_PLUGIN, p)))
    assert not missing, "E5: cited doctrine paths do not resolve under plugins/superheroes/: %s" % missing


def test_e6_adopt_version_is_not_a_charter_command():
    sys.path.insert(0, os.path.join(_PLUGIN, "lib"))
    try:
        import charter_detect
    finally:
        sys.path.pop(0)
    assert "adopt-version" not in charter_detect.COMMAND_CHARTERS, (
        "E6: 'adopt-version' is a key of charter_detect.COMMAND_CHARTERS, so running it "
        "would change the charter a seat is detected as")
