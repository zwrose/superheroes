# eval/lib/skills.py
"""Parse a SKILL.md, content-digest it, and enumerate skills. Stdlib-only.

The digest mirrors eval/lib/identifiers.py's normalization (NFC, \n line endings,
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


def parse_skill(text):
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError("SKILL.md has no leading frontmatter block")
    frontmatter, body = m.group(1), m.group(2)
    dm = _DESCRIPTION.search(frontmatter)
    description = dm.group(1).strip() if dm else ""
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


import json


def load_registry(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
