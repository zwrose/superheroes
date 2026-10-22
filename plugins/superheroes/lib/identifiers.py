#!/usr/bin/env python3
"""Canonical reference implementations of the superheroes load-bearing identifiers (CONVENTIONS §6).

This is the single source of truth for §6.1 work_item_slug (the §6.3 content hash retired, #2050).
All plugins in the consolidated superheroes tree import from here. Dependency-free and
deterministic. All text inputs are NFC-normalized before use, so canonically-equivalent
Unicode (macOS-NFD vs Linux-NFC "café") yields the same identifier.
"""
import hashlib
import re
import unicodedata

# ---- §6.1  <work-item> — the frozen join key -------------------------------------

_NON_SLUG = re.compile(r"[^a-z0-9]+")
SLUG_MAX_BASE = 50


def work_item_slug(title, creation_nonce):
    """The frozen slug chosen ONCE at work-item creation (CONVENTIONS §6.1)."""
    title = unicodedata.normalize("NFC", title)
    base = _NON_SLUG.sub("-", title.lower()).strip("-")[:SLUG_MAX_BASE].strip("-")
    if not base:
        base = "item"
    suffix = hashlib.sha256((title + creation_nonce).encode("utf-8")).hexdigest()[:6]
    return f"{base}-{suffix}"
