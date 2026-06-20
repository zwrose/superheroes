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
