"""Plugin-version skew detection for seat_map compose (issue #677).

Detection only — never switches code sources, blocks, or changes decisions. Emits one
degradation record when the running plugin's semantics files differ from the repository
working tree at ``repo_root``, or returns ``None`` when no skew is provable.

Disclosed bound: comparison is against the **working tree** at ``repo_root``, so a checkout
deliberately parked on an old commit can read as no-skew; and the two files watched are the
seat-composition and family-resolution surfaces only (``lib/model_registry.py``,
``lib/seat_map.py``), not the whole library.
"""
from __future__ import annotations

import hashlib
import json
import os

SEMANTICS_FILES = ("lib/model_registry.py", "lib/seat_map.py")


def _read_json(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _file_digest(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _read_installed_version(plugin_root: str) -> str:
    manifest = _read_json(os.path.join(plugin_root, ".claude-plugin", "plugin.json"))
    if manifest is not None and isinstance(manifest.get("version"), str):
        return manifest["version"]
    return "unknown"


def _read_repo_version(repo_root: str) -> str:
    path = os.path.join(repo_root, "plugins", "superheroes", "version.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except (OSError, UnicodeDecodeError):
        return "unknown"


def _make_record(detail: str, reason: str) -> dict:
    return {
        "constraint": "plugin-version-skew",
        "detail": detail,
        "reason": reason,
    }


def detect(repo_root: str, plugin_root: str) -> dict | None:
    manifest_path = os.path.join(
        repo_root, "plugins", "superheroes", ".claude-plugin", "plugin.json",
    )
    manifest = _read_json(manifest_path)
    # bite-axis: silence outside the source repository — a consuming project's installed cache is
    # its only semantics source, so skew is not provable and this path returns None by design.
    if manifest is None or manifest.get("name") != "superheroes":
        return None

    repo_plugin = os.path.join(repo_root, "plugins", "superheroes")
    if os.path.realpath(plugin_root) == os.path.realpath(repo_plugin):
        return None

    installed_version = _read_installed_version(plugin_root)
    repo_version = _read_repo_version(repo_root)

    unreadable: list[str] = []
    differing: list[str] = []
    for entry in SEMANTICS_FILES:
        plugin_path = os.path.join(plugin_root, entry)
        repo_path = os.path.join(repo_root, "plugins", "superheroes", entry)
        plugin_digest = _file_digest(plugin_path)
        repo_digest = _file_digest(repo_path)
        if plugin_digest is None or repo_digest is None:
            unreadable.append(entry)
        # bite-axis: content divergence — digest comparison on semantics files, not a version-string
        # compare (release tooling only advances version.txt at merge, so versions match throughout
        # the skew window this guard exists for).
        elif plugin_digest != repo_digest:
            differing.append(entry)

    # bite-axis: fail-closed — once the identity gate has passed, unreadable evidence returns a
    # record, never None; a guard that falls silent on a missing file has fallen open.
    if unreadable:
        entries = ", ".join(unreadable)
        reason = (
            "plugin-version-skew: installed %s, repo main at %s — skew evidence unreadable "
            "(%s); cannot prove the running plugin matches this repository's semantics."
        ) % (installed_version, repo_version, entries)
        return _make_record("evidence-unreadable", reason)

    if differing:
        entries = ", ".join(differing)
        reason = (
            "plugin-version-skew: installed %s, repo main at %s — family/registry semantics "
            "may differ (%s differ between the running plugin and this repository). "
            "The guard cannot know the semantic delta, only that one may exist: apply "
            "ratified deltas by hand or wait for the release cut."
        ) % (installed_version, repo_version, entries)
        return _make_record("semantics-divergent", reason)

    return None
