# eval/lib/skills.py
"""Parse a SKILL.md, content-digest it, and enumerate skills. Stdlib-only.

The digest mirrors plugins/superheroes/lib/identifiers.py's normalization (NFC, \n line endings,
per-line trailing-whitespace strip) but over a skill's (description + body) rather
than a definition-doc's stable frontmatter fields — so a carve-out keyed to it
lapses the moment the skill's description or body changes.
"""
import glob
import hashlib
import os
import re
import unicodedata

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_DESCRIPTION = re.compile(r"^description:[ \t]*(.*)$", re.MULTILINE)


def frontmatter_block(text):
    """The raw frontmatter block of a SKILL.md, or None when there is no leading block.

    One definition of 'the frontmatter block' — parse_skill and validate_skills both read it."""
    m = _FRONTMATTER.match(text)
    return m.group(1) if m else None


def _unquote(value):
    """Strip one surrounding pair of matching YAML quotes from a single-line scalar.

    A description with a bare ``colon: space`` (e.g. ``gates.review: passed``) must be
    quoted or strict ``yaml.safe_load`` rejects it. This module stays stdlib-only so it
    works on interpreters with no PyYAML, while validate_skills.py delegates YAML validity
    to ``yaml.safe_load`` and fails closed when PyYAML is unavailable. SKILL descriptions
    are simple single-line scalars,
    so a minimal unquote (one pair, plus the escapes each quote style allows) is enough to
    keep the structural parser's view of a description in agreement with yaml.safe_load.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        inner = value[1:-1]
        if value[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        else:
            inner = inner.replace("''", "'")
        return inner
    return value


def parse_skill(text):
    frontmatter = frontmatter_block(text)
    if frontmatter is None:
        raise ValueError("SKILL.md has no leading frontmatter block")
    m = _FRONTMATTER.match(text)
    body = m.group(2)
    dm = _DESCRIPTION.search(frontmatter)
    description = _unquote(dm.group(1).strip()) if dm else ""
    return description, body


def read_skill(path):
    with open(path, encoding="utf-8") as fh:
        return parse_skill(fh.read())


def _normalize(text):
    unified = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in unified.split("\n"))


def skill_digest(description, body):
    payload = _normalize(description) + "\n" + _normalize(body)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def iter_skill_paths(plugins_root):
    return sorted(glob.glob(os.path.join(plugins_root, "*", "skills", "*", "SKILL.md")))


def skill_key(path):
    """``plugins/<plugin>/skills/<skill>/SKILL.md`` -> ``"<plugin>/<skill>"``."""
    parts = path.split(os.sep)
    return f"{parts[-4]}/{parts[-2]}"


import json


def load_registry(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
