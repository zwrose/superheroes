#!/usr/bin/env python3
"""Fail-closed CI check: a change to the SET of plugin entries in
`.claude-plugin/marketplace.json` must bump `metadata.version` (spec FR-8).

Kept OUT of validate_marketplace.py (a pure working-tree reader that must stay
locally runnable). This check needs the PR base ref, so it lives here and runs
only in CI with a base-ref-fetching checkout. It FAILS CLOSED: if the base
catalog can't be resolved, it errors rather than passing silently (plan R4).

Usage: check_catalog_membership.py <base-ref>   (default base ref: origin/main)
"""
from __future__ import annotations

import json
import subprocess
import sys

CATALOG = ".claude-plugin/marketplace.json"


def _version(catalog: dict) -> str | None:
    """Resolve the catalog version with the same precedence validate_marketplace.py uses."""
    metadata = catalog.get("metadata") or {}
    return catalog.get("version") or metadata.get("version")


def _plugin_names(catalog: dict) -> set[str]:
    return {e.get("name") for e in catalog.get("plugins", []) if e.get("name")}


def compare_membership(base: dict, head: dict) -> list[str]:
    """Return a list of errors. If the plugin-name set changed between `base` and
    `head` but the catalog version did not, that is an error (FR-8)."""
    if _plugin_names(base) != _plugin_names(head):
        if _version(base) == _version(head):
            return [
                "the set of plugin entries changed but metadata.version did not — "
                "bump marketplace.json metadata.version (spec FR-8)"
            ]
    return []


def _read_base(ref: str) -> dict:
    """Read the catalog from the git base ref. Raises on any failure (fail closed)."""
    out = subprocess.run(
        ["git", "show", f"{ref}:{CATALOG}"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def main(argv: list[str]) -> int:
    base_ref = argv[0] if argv else "origin/main"
    try:
        with open(CATALOG) as fh:
            head = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"error: cannot read {CATALOG}: {e}\n")
        return 1
    try:
        base = _read_base(base_ref)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as e:
        sys.stderr.write(
            f"error: cannot resolve base catalog at {base_ref!r} — failing closed: {e}\n"
        )
        return 1
    errors = compare_membership(base, head)
    for msg in errors:
        sys.stderr.write("error: " + msg + "\n")
    if errors:
        return 1
    print("✓ catalog membership / metadata.version consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
