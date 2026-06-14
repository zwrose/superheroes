#!/usr/bin/env python3
"""Canonical reference implementations of the superheroes load-bearing identifiers.

These are the executable spec of CONVENTIONS.md §6 — the two NEW pure functions the
conventions pin. Plugins (define, producer, …) should consume these rather than
re-implement them, so two implementers cannot drift (the #1 theme of the convention
reviews). The storage-key derivations (`<config-key>`, `<absolute-git-dir-key>`) are
NOT here — they already live in store.py / review_store.py and get unified in Phase 2a.

All text inputs are NFC-normalized before use, so canonically-equivalent Unicode
(e.g. macOS-NFD vs Linux-NFC "café") yields the same identifier — the §6.3
"byte-identical across hosts" guarantee. Dependency-free and deterministic.
"""
import hashlib
import json
import re
import unicodedata

# ---- §6.1  <work-item> — the frozen join key -------------------------------------

_NON_SLUG = re.compile(r"[^a-z0-9]+")
SLUG_MAX_BASE = 50


def work_item_slug(title, creation_nonce):
    """The frozen slug chosen ONCE at work-item creation (CONVENTIONS §6.1).

    title is NFC-normalized first; base = lowercased, non-[a-z0-9] runs collapsed to
    '-', trimmed, capped at 50, trimmed again (so the cap cannot leave a trailing '-');
    suffix = first 6 hex of sha256(normalized-title + creation-nonce) so two
    similar/identical titles never collide. The caller stores the result and never
    re-derives it.
    """
    title = unicodedata.normalize("NFC", title)
    base = _NON_SLUG.sub("-", title.lower()).strip("-")[:SLUG_MAX_BASE].strip("-")
    if not base:
        base = "item"
    suffix = hashlib.sha256((title + creation_nonce).encode("utf-8")).hexdigest()[:6]
    return f"{base}-{suffix}"


# ---- §6.3  <content-hash> — the exactly-once key ---------------------------------

# Stable frontmatter fields that feed the hash, in canonical (sorted) form. Everything
# else — updated/created/status/gates/issue/producedBy/provenance — is volatile and
# MUST NOT affect the hash, or a metadata touch would spuriously read as a new attempt.
STABLE_FIELDS = ("docType", "parent", "size", "workItem")


def _normalize_body(body):
    # NFC-normalize, normalize line endings to \n, then strip trailing whitespace per line.
    unified = unicodedata.normalize("NFC", body).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in unified.split("\n"))


def content_hash(frontmatter, body):
    """Content-address the work branch from the APPROVED tasks doc (CONVENTIONS §6.3).

    Byte-identical across plugins/hosts/sessions:
      1. take the stable frontmatter fields only, serialize as JSON with sorted keys;
      2. normalize the body (NFC, \\n line endings, per-line trailing-whitespace strip);
      3. payload = <frontmatter-json> + "\\n" + <normalized-body>;
      4. sha256(payload), first 16 hex.
    `frontmatter` is the already-parsed mapping; `body` is the doc body (no frontmatter).
    Fails closed if a stable field is absent (CONVENTIONS §6.4 posture).
    """
    missing = [k for k in STABLE_FIELDS if k not in frontmatter]
    if missing:
        raise ValueError("content_hash: missing required stable field(s): " + ", ".join(missing))
    stable = {k: frontmatter[k] for k in STABLE_FIELDS}
    fm_json = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # DEFERRED (canon-version): this canonicalization is implicitly v1. A breaking change
    # to it counts as a define-doc schemaVersion bump (CONVENTIONS §6.4, fail-closed). When
    # the first consumer lands (producer/define, Phase 1), decide whether to also embed an
    # explicit canon-version in the stored branch key. Tracked in eval/gate.md.
    payload = fm_json + "\n" + _normalize_body(body)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
