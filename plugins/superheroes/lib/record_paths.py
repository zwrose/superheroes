#!/usr/bin/env python3
"""Seat storage keys and store/envelope path composition — leaf module with no round_* imports."""
import hashlib
import os
import re

RESERVED_PREFIX = "_"

_SLUG_MAX = 40
_SHA_PREFIX = 16
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_NON_SLUG = re.compile(r"[^a-z0-9]+")

__all__ = (
    "storage_key",
    "store_path",
    "store_dir",
    "round_dir",
    "landing_dir",
    "landing_path",
    "bare_payload_path",
    "landing_entry_present",
    "RESERVED_PREFIX",
    "_guard_within",
    "_require_token",
    "_require_index",
    "_seat_filename",
    "_KEY_RE",
)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def storage_key(seat_key, occurrence=0):
    """Map a roster seat key onto a filename-safe, collision-resistant storage key."""
    if not isinstance(seat_key, str) or not seat_key:
        raise ValueError("seat_key must be a non-empty str, got %r" % (seat_key,))
    if seat_key.startswith(RESERVED_PREFIX):
        raise ValueError("seat_key may not start with %r (reserved namespace): %r"
                         % (RESERVED_PREFIX, seat_key))
    if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 0:
        raise ValueError("occurrence must be a non-negative int, got %r" % (occurrence,))
    digest = _sha256_text(seat_key)[:_SHA_PREFIX]
    slug = _NON_SLUG.sub("-", seat_key.lower()).strip("-")[:_SLUG_MAX].strip("-")
    key = ("%s-%s" % (slug, digest)) if slug else ("seat-%s" % digest)
    if occurrence:
        key = "%s-o%d" % (key, occurrence)
    if not _KEY_RE.match(key):
        key = "seat-%s" % digest
        if occurrence:
            key = "%s-o%d" % (key, occurrence)
    return key


def _require_token(name, value):
    if not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str, got %r" % (name, value))
    if value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise ValueError("%s is not a safe path component: %r" % (name, value))
    return value


def _require_index(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("%s must be a non-negative int, got %r" % (name, value))
    return value


def _guard_within(session_dir, path):
    if not isinstance(session_dir, str) or not session_dir:
        raise ValueError("session_dir must be a non-empty str, got %r" % (session_dir,))
    root = os.path.realpath(session_dir)
    candidate = os.path.abspath(path)
    resolved = os.path.realpath(candidate)
    try:
        common = os.path.commonpath([root, resolved])
    except ValueError:
        raise ValueError("path escapes the session dir: %r" % (path,))
    if common != root or resolved == root:
        raise ValueError("path escapes the session dir: %r" % (path,))
    return path


def round_dir(session_dir, rnd):
    _require_index("rnd", rnd)
    return _guard_within(session_dir, os.path.join(session_dir, "round-%d" % rnd))


def store_dir(session_dir, rnd, phase):
    _require_token("phase", phase)
    return _guard_within(session_dir,
                         os.path.join(round_dir(session_dir, rnd), "seats", phase))


def _seat_filename(skey, attempt):
    _require_token("skey", skey)
    _require_index("attempt", attempt)
    return "%s.a%d.json" % (skey, attempt)


def store_path(session_dir, rnd, phase, skey, attempt):
    return _guard_within(session_dir, os.path.join(store_dir(session_dir, rnd, phase),
                                                   _seat_filename(skey, attempt)))


def landing_dir(session_dir, rnd, phase):
    _require_token("phase", phase)
    return _guard_within(session_dir,
                         os.path.join(round_dir(session_dir, rnd), "landing", phase))


def landing_path(session_dir, rnd, phase, skey, attempt):
    return _guard_within(
        session_dir,
        os.path.join(landing_dir(session_dir, rnd, phase),
                     _seat_filename(skey, attempt)))


def bare_payload_path(session_dir, rnd, phase, skey, attempt):
    """Host-seat payload-only landing slot — sibling to the full-envelope `landing_path`."""
    _require_token("skey", skey)
    _require_index("attempt", attempt)
    return _guard_within(
        session_dir,
        os.path.join(landing_dir(session_dir, rnd, phase),
                     "%s.a%d.payload.json" % (skey, attempt)))


def landing_entry_present(path):
    """True when the directory entry exists; indeterminate errors count as present (fail closed)."""
    try:
        os.lstat(path)
        return True
    except FileNotFoundError:
        return False
    except NotADirectoryError:
        return False
    except OSError:
        # axis: an lstat error other than not-found counts as present
        return True
