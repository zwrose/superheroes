"""Plugin-version skew detection for seat_map compose (issue #677).

Detection only — never switches code sources, blocks, or changes decisions. Always returns a
labelled record describing whether skew was checked and what was found.

Disclosed bound: comparison is against the **working tree** at ``repo_root``, so a checkout
deliberately parked on an old commit can read as no-skew; and the three files watched are the
seat-composition surface (``lib/seat_map.py``), the family-resolution surface
(``lib/model_registry.py``), and this module itself (``lib/version_skew.py``) — which owns the
skew status vocabulary and the append-to-degradations rule — not the whole library.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import string

CONSTRAINT = "plugin-version-skew"
SEMANTICS_FILES = (
    "lib/model_registry.py",
    "lib/seat_map.py",
    "lib/version_skew.py",
)

STATUS_NOT_CHECKED = "not-checked"
STATUS_CHECKED_DEGRADED = "checked-degraded"
STATUS_CHECKED_CLEAN = "checked-clean"
STATUSES = frozenset({
    STATUS_NOT_CHECKED,
    STATUS_CHECKED_DEGRADED,
    STATUS_CHECKED_CLEAN,
})

# Per-member degrading disposition — every STATUSES member must appear here; the census test
# iterates STATUSES and fails on an undispositioned member (#1107).
STATUS_DISPOSITIONS = {
    STATUS_NOT_CHECKED: False,
    STATUS_CHECKED_DEGRADED: True,
    STATUS_CHECKED_CLEAN: False,
}


def is_degrading(status: object) -> bool:
    """True when ``status`` is a degrading skew disclosure. Unknown statuses and members with no
    disposition fail closed (read as degrading) so a future enum member cannot ship silently
    non-degrading (#1107). Unhashable values (malformed seat maps) fail closed too."""
    try:
        known = status in STATUSES
    except TypeError:
        return True
    if not known:
        return True
    if status not in STATUS_DISPOSITIONS:
        return True
    return STATUS_DISPOSITIONS[status]

DETAIL_NOT_SOURCE_REPO = "not-source-repo"
DETAIL_SELF = "self"
DETAIL_NOT_COMPOSED = "not-composed"
DETAIL_SEMANTICS_DIVERGENT = "semantics-divergent"
DETAIL_EVIDENCE_UNREADABLE = "evidence-unreadable"
DETAIL_NO_DIVERGENCE = "no-divergence"

DETAILS = frozenset({
    DETAIL_NOT_SOURCE_REPO,
    DETAIL_SELF,
    DETAIL_NOT_COMPOSED,
    DETAIL_SEMANTICS_DIVERGENT,
    DETAIL_EVIDENCE_UNREADABLE,
    DETAIL_NO_DIVERGENCE,
})
DEGRADING_DETAILS = frozenset({
    DETAIL_SEMANTICS_DIVERGENT,
    DETAIL_EVIDENCE_UNREADABLE,
})
APPENDS_DEGRADATION = frozenset({STATUS_CHECKED_DEGRADED})


# bite-axis: closed membership — a non-string, None, or unhashable argument returns False
# (only statuses declared here append); a set-membership home beats scattered == at call sites
# so a future fourth status is decided here, not silently non-appending elsewhere (#1151).
def appends_degradation(status) -> bool:
    try:
        return status in APPENDS_DEGRADATION
    except TypeError:
        return False

# bite-axis: bounded reads — streamed rather than read-whole so a repo-controlled symlink to an
# endless device cannot hang compose or exhaust the reviewer (#677).
# Max bytes read from any single evidence file; comfortably above legitimate semantics files.
_MAX_READ_BYTES = 512 * 1024

# Max length of the sanitized first-line version string embedded in reason prose.
_MAX_VERSION_CHARS = 64


def _repo_plugin_dir(repo_root: str) -> str:
    return os.path.join(repo_root, "plugins", "superheroes")


def _path_contained(path: str, root: str) -> bool:
    resolved_path = os.path.realpath(path)
    resolved_root = os.path.realpath(root)
    try:
        return os.path.commonpath([resolved_path, resolved_root]) == resolved_root
    except ValueError:
        return False


def _open_regular_file(path: str, *, expected_root: str | None = None) -> int | None:
    """Open a regular file read-only without following symlinks."""
    # bite-axis: symlink and non-regular-file refusal — O_NOFOLLOW refuses a symlink only at the
    # final path component, so the fstat regular-file check is what stops a fifo or device file (#677).
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return None
    except OSError:
        return None
    try:
        # O_NONBLOCK prevents blocking on a fifo swapped in between lstat and open; without it the
        # post-open fstat check never runs.
        fd = os.open(
            path,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return None
    except OSError:
        os.close(fd)
        return None
    # bite-axis: parent-directory symlink containment — final-component guards alone cannot stop a
    # plugins/superheroes directory symlink from redirecting every evidence read outside repo_root
    # (#677).
    if expected_root is not None and not _path_contained(path, expected_root):
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


def _read_json(path: str, *, expected_root: str | None = None) -> dict | None:
    fd = _open_regular_file(path, expected_root=expected_root)
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


def _file_digest(path: str, *, expected_root: str | None = None) -> str | None:
    fd = _open_regular_file(path, expected_root=expected_root)
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
    manifest = _read_json(
        os.path.join(plugin_root, ".claude-plugin", "plugin.json"),
        expected_root=plugin_root,
    )
    if manifest is not None and isinstance(manifest.get("version"), str):
        return _sanitize_version_text(manifest["version"].encode("utf-8"))
    return "unknown"


def _read_repo_version(manifest: dict | None) -> str:
    """Repo-side version from the plugin manifest ``detect()`` already read — ``plugin.json`` is
    the single source of truth (CLAUDE.md); ``version.txt`` is never consulted."""
    if manifest is not None and isinstance(manifest.get("version"), str):
        return _sanitize_version_text(manifest["version"].encode("utf-8"))
    return "unknown"


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
        _repo_plugin_dir(repo_root), ".claude-plugin", "plugin.json",
    )
    manifest_exists = os.path.lexists(manifest_path)
    manifest = (
        _read_json(manifest_path, expected_root=repo_root) if manifest_exists else None
    )
    # bite-axis: refused manifest read — a symlink escaping repo_root or a non-regular file must
    # not collapse into not-source-repo; the honest label is checked-degraded / evidence-unreadable
    # (#1107; same fail-closed class as unreadable semantics evidence below).
    if manifest_exists and manifest is None:
        inspected_root = os.path.abspath(repo_root)
        reason = (
            "plugin-version-skew: installed %s, this repository's version at %s — skew evidence "
            "unreadable (plugins/superheroes/.claude-plugin/plugin.json); cannot prove the running "
            "plugin matches this repository's semantics."
        ) % (_read_installed_version(plugin_root), "unknown")
        return _make_record(
            STATUS_CHECKED_DEGRADED, DETAIL_EVIDENCE_UNREADABLE, reason, inspected_root,
        )
    # bite-axis: silence outside the source repository — a consuming project's installed cache is
    # its only semantics source, so skew is not provable here; this path returns a not-checked /
    # not-source-repo record rather than checked-clean (#677).
    if manifest is None or manifest.get("name") != "superheroes":
        return _make_record(
            STATUS_NOT_CHECKED,
            DETAIL_NOT_SOURCE_REPO,
            (
                "plugin-version-skew: this path is not a superheroes source repository, "
                "so installed-plugin semantics cannot be compared against a repo working tree."
            ),
            "",
        )

    repo_plugin = _repo_plugin_dir(repo_root)
    if os.path.realpath(plugin_root) == os.path.realpath(repo_plugin):
        return _make_record(
            STATUS_NOT_CHECKED,
            DETAIL_SELF,
            (
                "plugin-version-skew: the running plugin is this repository's own "
                "plugins/superheroes tree, so there is no separate installed copy to compare."
            ),
            "",
        )

    inspected_root = os.path.abspath(repo_root)
    installed_version = _read_installed_version(plugin_root)
    repo_version = _read_repo_version(manifest)

    unreadable: list[str] = []
    differing: list[str] = []
    for entry in SEMANTICS_FILES:
        plugin_path = os.path.join(plugin_root, entry)
        repo_path = os.path.join(_repo_plugin_dir(repo_root), entry)
        plugin_digest = _file_digest(plugin_path, expected_root=plugin_root)
        repo_digest = _file_digest(repo_path, expected_root=repo_root)
        if plugin_digest is None or repo_digest is None:
            unreadable.append(entry)
        # bite-axis: content divergence — digest comparison on the watched semantics files, not a
        # version-string compare (release tooling only advances version.txt at merge, so versions
        # match throughout the skew window this guard exists for) (#677).
        elif plugin_digest != repo_digest:
            differing.append(entry)

    # bite-axis: fail-closed — once the identity gate has passed, unreadable or unsafe evidence
    # returns checked-degraded / evidence-unreadable, never checked-clean and never not-checked;
    # a guard that falls silent on a refused read has fallen open (#677).
    if unreadable:
        entries = ", ".join(unreadable)
        reason = (
            "plugin-version-skew: installed %s, this repository's version at %s — skew evidence "
            "unreadable (%s); cannot prove the running plugin matches this repository's semantics."
        ) % (installed_version, repo_version, entries)
        return _make_record(
            STATUS_CHECKED_DEGRADED, DETAIL_EVIDENCE_UNREADABLE, reason, inspected_root,
        )

    if differing:
        entries = ", ".join(differing)
        reason = (
            "plugin-version-skew: installed %s, this repository's version at %s — "
            "watched review semantics differ (%s differ between the running plugin and "
            "this repository). The guard cannot know the semantic delta, only that one may exist: "
            "apply ratified deltas by hand or wait for the release cut."
        ) % (installed_version, repo_version, entries)
        return _make_record(
            STATUS_CHECKED_DEGRADED, DETAIL_SEMANTICS_DIVERGENT, reason, inspected_root,
        )

    reason = (
        "plugin-version-skew: installed %s, this repository's version at %s — the watched "
        "semantics files are identical between the running plugin and this repository's "
        "working tree."
    ) % (installed_version, repo_version)
    return _make_record(STATUS_CHECKED_CLEAN, DETAIL_NO_DIVERGENCE, reason, inspected_root)
