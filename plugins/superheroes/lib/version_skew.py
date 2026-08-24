"""Plugin-version skew detection for seat_map compose (issue #677).

Detection only — never switches code sources, blocks, or changes decisions. Always returns a
labelled record describing whether skew was checked and what was found.

Disclosed bound: comparison is against the **working tree** at ``repo_root``, so a checkout
deliberately parked on an old commit can read as no-skew; and the two files watched are the
seat-composition and family-resolution surfaces only (``lib/model_registry.py``,
``lib/seat_map.py``), not the whole library.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import string

CONSTRAINT = "plugin-version-skew"
SEMANTICS_FILES = ("lib/model_registry.py", "lib/seat_map.py")

# Max bytes read from any single evidence file; comfortably above legitimate semantics files.
_MAX_READ_BYTES = 512 * 1024

# Max length of the sanitized first-line version string embedded in reason prose.
_MAX_VERSION_CHARS = 64


def _open_regular_file(path: str) -> int | None:
    """Open a regular file read-only without following symlinks."""
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return None
    except OSError:
        return None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return None
    except OSError:
        os.close(fd)
        return None
    return fd


def _read_bounded(fd: int, max_bytes: int) -> bytes | None:
    chunks: list[bytes] = []
    total = 0
    while total < max_bytes:
        try:
            chunk = os.read(fd, min(8192, max_bytes - total))
        except OSError:
            return None
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    else:
        try:
            if os.read(fd, 1):
                return None
        except OSError:
            return None
    return b"".join(chunks)


def _read_json(path: str) -> dict | None:
    fd = _open_regular_file(path)
    if fd is None:
        return None
    try:
        raw = _read_bounded(fd, _MAX_READ_BYTES)
        if raw is None:
            return None
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    finally:
        os.close(fd)


def _file_digest(path: str) -> str | None:
    fd = _open_regular_file(path)
    if fd is None:
        return None
    try:
        hasher = hashlib.sha256()
        total = 0
        while total < _MAX_READ_BYTES:
            try:
                chunk = os.read(fd, min(8192, _MAX_READ_BYTES - total))
            except OSError:
                return None
            if not chunk:
                break
            hasher.update(chunk)
            total += len(chunk)
        else:
            try:
                if os.read(fd, 1):
                    return None
            except OSError:
                return None
        return hasher.hexdigest()
    finally:
        os.close(fd)


def _sanitize_version_text(raw: bytes) -> str:
    first_line = raw.split(b"\n", 1)[0]
    try:
        text = first_line.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    text = text.strip()
    if not text:
        return "unknown"
    text = text[:_MAX_VERSION_CHARS]
    printable = "".join(ch if ch in string.printable and ch not in "\r\n\t" else "" for ch in text)
    printable = printable.strip()
    return printable if printable else "unknown"


def _read_installed_version(plugin_root: str) -> str:
    manifest = _read_json(os.path.join(plugin_root, ".claude-plugin", "plugin.json"))
    if manifest is not None and isinstance(manifest.get("version"), str):
        return _sanitize_version_text(manifest["version"].encode("utf-8"))
    return "unknown"


def _read_repo_version(repo_root: str) -> str:
    path = os.path.join(repo_root, "plugins", "superheroes", "version.txt")
    fd = _open_regular_file(path)
    if fd is None:
        return "unknown"
    try:
        raw = _read_bounded(fd, _MAX_READ_BYTES)
        if raw is None:
            return "unknown"
        return _sanitize_version_text(raw)
    finally:
        os.close(fd)


def _make_record(
    status: str,
    detail: str,
    reason: str,
    inspected_root: str,
) -> dict:
    return {
        "constraint": CONSTRAINT,
        "status": status,
        "detail": detail,
        "reason": reason,
        "inspectedRoot": inspected_root,
    }


def detect(repo_root: str, plugin_root: str) -> dict:
    manifest_path = os.path.join(
        repo_root, "plugins", "superheroes", ".claude-plugin", "plugin.json",
    )
    manifest = _read_json(manifest_path)
    if manifest is None or manifest.get("name") != "superheroes":
        return _make_record(
            "not-checked",
            "not-source-repo",
            (
                "plugin-version-skew: this path is not a superheroes source repository, "
                "so installed-plugin semantics cannot be compared against a repo working tree."
            ),
            "",
        )

    repo_plugin = os.path.join(repo_root, "plugins", "superheroes")
    if os.path.realpath(plugin_root) == os.path.realpath(repo_plugin):
        return _make_record(
            "not-checked",
            "self",
            (
                "plugin-version-skew: the running plugin is this repository's own "
                "plugins/superheroes tree, so there is no separate installed copy to compare."
            ),
            "",
        )

    inspected_root = os.path.abspath(repo_root)
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
        elif plugin_digest != repo_digest:
            differing.append(entry)

    if unreadable:
        entries = ", ".join(unreadable)
        reason = (
            "plugin-version-skew: installed %s, this repository's version at %s — skew evidence "
            "unreadable (%s); cannot prove the running plugin matches this repository's semantics."
        ) % (installed_version, repo_version, entries)
        return _make_record("checked-degraded", "evidence-unreadable", reason, inspected_root)

    if differing:
        entries = ", ".join(differing)
        reason = (
            "plugin-version-skew: installed %s, this repository's version at %s — "
            "family/registry semantics may differ (%s differ between the running plugin and "
            "this repository). The guard cannot know the semantic delta, only that one may exist: "
            "apply ratified deltas by hand or wait for the release cut."
        ) % (installed_version, repo_version, entries)
        return _make_record("checked-degraded", "semantics-divergent", reason, inspected_root)

    reason = (
        "plugin-version-skew: installed %s, this repository's version at %s — the watched "
        "semantics files are identical between the running plugin and this repository's "
        "working tree."
    ) % (installed_version, repo_version)
    return _make_record("checked-clean", "no-divergence", reason, inspected_root)
