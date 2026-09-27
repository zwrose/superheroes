"""Wiring detector for the adopt-version skill (issue #1512 WO-B).

Guarded elements E1–E6 — one assertion each; the orchestrator neutralizes elements separately.
"""
import json
import os
import re
import sys

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO = os.path.dirname(os.path.dirname(_PLUGIN))
_SKILL_MD = os.path.join(_PLUGIN, "skills", "adopt-version", "SKILL.md")
_CODEX_MANIFEST = os.path.join(_PLUGIN, ".codex-plugin", "plugin.json")
_FIXTURE = os.path.join(_REPO, "eval", "skills", "fixtures", "superheroes__adopt-version.json")
_README = os.path.join(_REPO, "README.md")

sys.path.insert(0, os.path.join(_PLUGIN, "lib"))

_DOCTRINE_PREFIXES = ("rubric/", "skills/", "lib/", "agents/", "reference/")
_BACKTICK_PATH = re.compile(r"`([^`]+)`")


def _read_skill_md():
    with open(_SKILL_MD, encoding="utf-8") as fh:
        return fh.read()


def test_e1_skill_md_exists_with_frontmatter():
    """E1 — plugins/superheroes/skills/adopt-version/SKILL.md frontmatter."""
    assert os.path.isfile(_SKILL_MD), "E1: adopt-version SKILL.md missing"
    text = _read_skill_md()
    assert text.startswith("---\n"), "E1: SKILL.md missing opening frontmatter fence"
    end = text.index("\n---\n", 4)
    block = text[4:end]
    assert 'name: adopt-version' in block, "E1: frontmatter name must be adopt-version"
    assert "user-invocable: true" in block, "E1: user-invocable must be true"


def test_e2_adopt_version_in_codex_manifest():
    """E2 — .codex-plugin/plugin.json lists adopt-version."""
    with open(_CODEX_MANIFEST, encoding="utf-8") as fh:
        skills = json.load(fh)["skills"]
    assert "adopt-version" in skills, 'E2: Codex manifest must contain literal "adopt-version"'


def test_e3_fixture_nonempty():
    """E3 — eval/skills/fixtures/superheroes__adopt-version.json."""
    assert os.path.isfile(_FIXTURE), "E3: adopt-version fixture missing"
    with open(_FIXTURE, encoding="utf-8") as fh:
        fx = json.load(fh)
    assert fx.get("should_fire"), "E3: should_fire must be non-empty"
    assert fx.get("should_not_fire"), "E3: should_not_fire must be non-empty"


def test_e4_readme_command_table_row():
    """E4 — README.md table row for /superheroes:adopt-version."""
    with open(_README, encoding="utf-8") as fh:
        lines = fh.readlines()
    hit = [
        ln
        for ln in lines
        if ln.startswith("|") and "`/superheroes:adopt-version`" in ln
    ]
    assert hit, "E4: README must contain a table row with `/superheroes:adopt-version`"


def _skill_body_without_fences(text):
    """Drop fenced code blocks so inline `path` tokens are not swallowed by ``` spans."""
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def test_e5_doctrine_paths_resolve_and_helper_cited():
    """E5 — backtick doctrine paths in prose resolve; lib/adopt_version.py cited in prose."""
    text = _read_skill_md()
    prose = _skill_body_without_fences(text)
    paths = []
    for match in _BACKTICK_PATH.finditer(prose):
        path = match.group(1)
        if any(path.startswith(p) for p in _DOCTRINE_PREFIXES):
            paths.append(path.split("#", 1)[0])
    assert paths, "E5: expected at least one guarded doctrine path in backticks"
    assert "lib/adopt_version.py" in paths, (
        "E5: SKILL.md must cite lib/adopt_version.py in prose (outside fenced blocks)"
    )
    for path in paths:
        full = os.path.join(_PLUGIN, path)
        assert os.path.isfile(full), f"E5: doctrine path does not resolve: {path!r}"


def test_e6_not_a_charter_command():
    """E6 — adopt-version must not appear in charter_detect.COMMAND_CHARTERS."""
    import charter_detect

    assert "adopt-version" not in charter_detect.COMMAND_CHARTERS, (
        "E6: adopt-version must not be a key of COMMAND_CHARTERS"
    )
