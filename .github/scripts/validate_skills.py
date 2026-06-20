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
        if not os.path.exists(os.path.join(plugin_dir, rel)):
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


_TOC = re.compile(r"^#+\s+(contents|table of contents)\b", re.IGNORECASE)


def check_toc(reference_path):
    with open(reference_path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if len(lines) <= 100:
        return []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("#"):
            if _TOC.match(stripped):
                return []
            break
    rel = os.path.relpath(reference_path, REPO)
    return [f"table-of-contents: {rel}: file is >100 lines but does not open with a Contents heading"]


def check_phrases(skill_key, description, required_phrases):
    return [
        f"trigger-phrase: {skill_key}: description no longer contains required phrase {p!r}"
        for p in required_phrases if p not in description
    ]


def check_depth(skill_key, text, plugin_dir):
    out = []
    seen = set()
    for m in _REF.finditer(text):
        rel = m.group(1)
        if rel in seen:
            continue
        seen.add(rel)
        target = os.path.join(plugin_dir, rel)
        if not os.path.isfile(target):
            continue  # resolution is check_links' job
        with open(target, encoding="utf-8") as fh:
            if _REF.search(fh.read()):
                out.append(
                    f"reference-depth: {skill_key}: {rel} itself references another "
                    f"file (chain deeper than one hop)")
    return out


import argparse

sys.path.insert(0, os.path.join(REPO, "eval", "lib"))
import skills  # noqa: E402

REGISTRY = os.path.join(REPO, "eval", "skills", "registry.json")
BASELINE = os.path.join(REPO, "eval", "skills", "baseline.json")
CONVENTIONS = os.path.join(REPO, "CONVENTIONS.md")


def _skill_key(path):
    parts = path.split(os.sep)
    return f"{parts[-4]}/{parts[-2]}"


def known_red_ceilings(baseline):
    return set(baseline.get("knownRedCeilings", []))


def gather_violations(plugins_root, registry, red_set, conv_secs, combined_before=None,
                      allowed_unresolved=frozenset()):
    """Walk skills under plugins_root and collect per-skill + combined-size violations.

    Pure over its inputs (no global file reads) so it is unit-testable on a temp tree.
    red_set suppresses the line-count rule for known-red skills (FR-8).
    allowed_unresolved is a set of "<skill_key>:<relpath>" strings; any reference-link
    violation whose skill+relpath is in that set is suppressed (deliberate sentinels).
    Returns (errors, combined_description_chars).
    """
    errors = []
    combined_now = 0
    for path in skills.iter_skill_paths(plugins_root):
        key = _skill_key(path)
        plugin_dir = os.path.join(plugins_root, key.split("/")[0])
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        description, _ = skills.parse_skill(raw)
        combined_now += len(description)
        total_lines = raw.count("\n") + (0 if raw.endswith("\n") else 1)

        if key not in red_set:
            errors += check_line_count(key, total_lines, registry["bodyCeilings"])
        for v in check_links(key, raw, plugin_dir):
            # Suppress deliberate sentinel references listed in allowed_unresolved.
            # Violation format: "reference-link: <key>: unresolved reference <relpath>"
            if allowed_unresolved and v.startswith("reference-link: "):
                suffix = v[len("reference-link: "):]  # "<key>: unresolved reference <relpath>"
                parts = suffix.split(": unresolved reference ", 1)
                if len(parts) == 2 and f"{parts[0]}:{parts[1]}" in allowed_unresolved:
                    continue
            errors.append(v)
        errors += check_conventions_refs(key, raw, conv_secs)
        errors += check_depth(key, raw, plugin_dir)
        errors += check_phrases(key, description, registry["requiredPhrases"].get(key, []))

    # FR-10: combined description size strictly smaller than the recorded pre-change baseline.
    if combined_before is not None and combined_now >= combined_before:
        errors.append(
            f"description-size: combined description chars {combined_now} "
            f"is not smaller than baseline {combined_before}")
    return errors, combined_now


def main(argv=None):
    argparse.ArgumentParser(description="validate skill token-shape").parse_args(argv or [])
    registry = skills.load_registry(REGISTRY)
    if os.path.isfile(BASELINE):
        with open(BASELINE, encoding="utf-8") as fh:
            baseline = json.load(fh)
    else:
        baseline = {}
    with open(CONVENTIONS, encoding="utf-8") as fh:
        conv_secs = conventions_section_numbers(fh.read())

    allowed_unresolved = set(baseline.get("allowedUnresolvedRefs", []))
    errors, _ = gather_violations(
        PLUGINS, registry, known_red_ceilings(baseline), conv_secs,
        baseline.get("combinedDescriptionChars"),
        allowed_unresolved=allowed_unresolved)

    # FR-6: TOC on long reference files (any .md under a plugin's reference/ dirs)
    import glob as _glob
    for ref in _glob.glob(os.path.join(PLUGINS, "*", "**", "reference", "*.md"), recursive=True):
        errors += check_toc(ref)

    if errors:
        sys.stderr.write(f"\n✗ {len(errors)} skill problem(s):\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1
    print("✓ skills meet token-shape rules")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
