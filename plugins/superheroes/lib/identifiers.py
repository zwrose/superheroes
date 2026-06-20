#!/usr/bin/env python3
"""Canonical reference implementations of the superheroes load-bearing identifiers (CONVENTIONS §6).

These are the single source of truth for §6.1 work_item_slug and §6.3 content_hash.
All plugins in the consolidated superheroes tree import from here. Dependency-free and
deterministic. All text inputs are NFC-normalized before use, so canonically-equivalent
Unicode (macOS-NFD vs Linux-NFC "café") yields the same identifier — the §6.3
"byte-identical across hosts" guarantee.
"""
import hashlib
import json
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


# ---- §6.3  <content-hash> — the exactly-once key ---------------------------------

STABLE_FIELDS = ("docType", "parent", "size", "workItem")


def _normalize_body(body):
    # NFC-normalize, normalize line endings to \n, then strip trailing whitespace per line.
    unified = unicodedata.normalize("NFC", body).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in unified.split("\n"))


def content_hash(frontmatter, body):
    """Content-address the work branch from the APPROVED tasks doc (CONVENTIONS §6.3).

    Fails closed if a stable field is absent (CONVENTIONS §6.4 posture).
    """
    missing = [k for k in STABLE_FIELDS if k not in frontmatter]
    if missing:
        raise ValueError("content_hash: missing required stable field(s): " + ", ".join(missing))
    stable = {k: frontmatter[k] for k in STABLE_FIELDS}
    fm_json = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload = fm_json + "\n" + _normalize_body(body)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
