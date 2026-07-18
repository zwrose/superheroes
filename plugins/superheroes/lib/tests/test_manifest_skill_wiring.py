"""Every on-disk skill must be registered in the Codex plugin manifest's `skills` list.

The Claude host auto-discovers `skills/<name>/SKILL.md` directories, but the Codex
host reads the explicit `skills` array in `.codex-plugin/plugin.json` — a skill absent
from that array is invisible on Codex. `validate_hosts.py` only checks the field EXISTS,
not that it enumerates every skill, so a newly-added skill (e.g. `superheroes:review-code`)
can ship wired for Claude but silently unwired for Codex. This test is the wiring floor:
the Codex `skills` array must list exactly the on-disk skill directories.
"""
import json
import os

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILLS_DIR = os.path.join(_PLUGIN, "skills")
_CODEX_MANIFEST = os.path.join(_PLUGIN, ".codex-plugin", "plugin.json")


def _on_disk_skills():
    return sorted(
        d for d in os.listdir(_SKILLS_DIR)
        if os.path.isfile(os.path.join(_SKILLS_DIR, d, "SKILL.md"))
    )


def _codex_skills():
    with open(_CODEX_MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)["skills"]


def test_core_skill_is_registered_in_codex_manifest():
    # sentinel that a representative plugin skill is wired for Codex (the acceptance skill
    # deliberately left the plugin for the repo-local `.claude/skills/` — issue #237).
    assert "review-code" in _codex_skills()


def test_codex_manifest_lists_exactly_the_on_disk_skills():
    on_disk = _on_disk_skills()
    codex = _codex_skills()
    missing = sorted(set(on_disk) - set(codex))
    extra = sorted(set(codex) - set(on_disk))
    assert not missing, f"skills on disk but absent from Codex manifest: {missing}"
    assert not extra, f"skills in Codex manifest with no SKILL.md on disk: {extra}"


def test_codex_skills_list_has_no_duplicates():
    codex = _codex_skills()
    assert len(codex) == len(set(codex))
