"""Shared helper: read a skill's shipped surface (SKILL.md + linked reference/*.md)."""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILLS = os.path.normpath(os.path.join(_HERE, "..", "..", "skills"))

_REF = re.compile(
    r"\$\{CLAUDE_PLUGIN_ROOT:-\$\{PLUGIN_ROOT\}\}/skills/([A-Za-z0-9._-]+)/reference/([A-Za-z0-9._-]+\.md)"
)


def _skill_md_path(skill_name: str) -> str:
    path = os.path.join(_SKILLS, skill_name, "SKILL.md")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"skill SKILL.md not found: {path}")
    return path


def linked_reference_files(skill_name: str) -> list[str]:
    skill_md = _skill_md_path(skill_name)
    with open(skill_md, encoding="utf-8") as fh:
        text = fh.read()
    seen: set[str] = set()
    paths: list[str] = []
    for m in _REF.finditer(text):
        ref_skill, ref_file = m.group(1), m.group(2)
        if ref_skill != skill_name:
            continue
        ref_path = os.path.join(_SKILLS, skill_name, "reference", ref_file)
        if not os.path.isfile(ref_path):
            continue
        if ref_path in seen:
            continue
        seen.add(ref_path)
        paths.append(ref_path)
    return sorted(paths)


def surface_text(skill_name: str) -> str:
    skill_md = _skill_md_path(skill_name)
    with open(skill_md, encoding="utf-8") as fh:
        text = fh.read()
    refs = linked_reference_files(skill_name)
    if not refs:
        return text
    ref_by_name = {os.path.basename(path): path for path in refs}
    inserted: set[str] = set()
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        out.append(line)
        for m in _REF.finditer(line):
            if m.group(1) != skill_name:
                continue
            ref_path = ref_by_name.get(m.group(2))
            if ref_path is None or ref_path in inserted:
                continue
            with open(ref_path, encoding="utf-8") as fh:
                ref_text = fh.read()
            out.append(ref_text if ref_text.endswith("\n") else ref_text + "\n")
            inserted.add(ref_path)
    for ref_path in refs:
        if ref_path in inserted:
            continue
        with open(ref_path, encoding="utf-8") as fh:
            ref_text = fh.read()
        out.append(ref_text if ref_text.endswith("\n") else ref_text + "\n")
    return "".join(out)
