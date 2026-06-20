#!/usr/bin/env python3
"""Deterministic structural validator for published skills (stdlib only).

Run from the repo root in CI, after validate_hosts.py. Enforces the token-shape
rules for SKILL.md bodies and their one-hop reference files, reading ceilings and
required description phrases from eval/skills/registry.json and the known-red set
from eval/skills/baseline.json. Exits non-zero, naming each <rule>: <skill>: <detail>.
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGINS = os.path.join(REPO, "plugins")


def check_line_count(skill_key, total_lines, ceilings):
    ceiling = ceilings.get(skill_key)
    if ceiling is None or total_lines <= ceiling:
        return []
    return [f"line-count: {skill_key}: {total_lines} lines > ceiling {ceiling}"]


import re

_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT:-\$\{PLUGIN_ROOT\}\}/([A-Za-z0-9._/\-]+)")
_HEADING = re.compile(r"^#+\s+(\d+(?:\.\d+)*)\b", re.MULTILINE)
# Only CONVENTIONS-qualified citations are validated. A bare "§N" is ambiguous — skills
# also use §N for their OWN internal section cross-references (e.g. review-code's §12),
# which are not CONVENTIONS headings — so matching bare §N would false-positive. We never
# edit CONVENTIONS.md, so the qualified citations are the ones whose resolution matters.
_CONV_REF = re.compile(r"CONVENTIONS\s+`?§\s*(\d+(?:\.\d+)*)")


def check_links(skill_key, text, plugin_dir):
    out = []
    for m in _REF.finditer(text):
        rel = m.group(1)
        if not os.path.isfile(os.path.join(plugin_dir, rel)):
            out.append(f"reference-link: {skill_key}: unresolved reference {rel}")
    return out


def conventions_section_numbers(conventions_text):
    return {m.group(1) for m in _HEADING.finditer(conventions_text)}


def check_conventions_refs(skill_key, text, conventions_sections):
    out = []
    for m in _CONV_REF.finditer(text):
        sec = m.group(1)
        if sec not in conventions_sections:
            out.append(f"conventions-ref: {skill_key}: §{sec} resolves to no CONVENTIONS heading")
    return out


def check_depth(skill_key, text, plugin_dir):
    out = []
    for m in _REF.finditer(text):
        target = os.path.join(plugin_dir, m.group(1))
        if not os.path.isfile(target):
            continue  # resolution is check_links' job
        with open(target, encoding="utf-8") as fh:
            if _REF.search(fh.read()):
                out.append(
                    f"reference-depth: {skill_key}: {m.group(1)} itself references another "
                    f"file (chain deeper than one hop)")
    return out
