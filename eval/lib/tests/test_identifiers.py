"""Tests for the canonical §6.1 identifier reference impl (work_item_slug).

These double as the conformance check that the reference matches CONVENTIONS §6.1.

The GOLDEN-VALUE test is the load-bearing one: a pure-property suite (determinism,
sensitivity) stays green even if the byte-exact derivation drifts. The frozen golden value
pins the exact output, so any drift fails loudly. If §6.1 ever changes the derivation,
update the golden IN THE SAME COMMIT as the spec change (never to make a test pass).
"""
import re
import unicodedata

import identifiers as ids


# ---- §6.1 work_item_slug ---------------------------------------------------------

def test_slug_golden_value():
    # Frozen anchor: exact output for a fixed (title, nonce). Pins the full derivation.
    assert ids.work_item_slug("Add Dark Mode Toggle", "fixed-nonce-v1") == "add-dark-mode-toggle-50c082"


def test_slug_deterministic():
    assert ids.work_item_slug("Add dark mode toggle", "n1") == \
        ids.work_item_slug("Add dark mode toggle", "n1")


def test_slug_format_and_base():
    s = ids.work_item_slug("Add Dark Mode Toggle!!!", "n")
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]*-[0-9a-f]{6}", s), s
    base, _, suffix = s.rpartition("-")
    assert base == "add-dark-mode-toggle"
    assert re.fullmatch(r"[0-9a-f]{6}", suffix)


def test_slug_collision_resistance():
    # Identical titles, different creation nonces -> same base, different suffix.
    a = ids.work_item_slug("Same Title", "nonce-a")
    b = ids.work_item_slug("Same Title", "nonce-b")
    assert a != b
    assert a.rpartition("-")[0] == b.rpartition("-")[0]


def test_slug_caps_base_at_50_and_trims_after_slice():
    # 49 'a's, then a separator, then 'b's: the [:50] slice lands on the '-', and the
    # post-cap trim must drop it (no trailing '-' before the suffix).
    s = ids.work_item_slug("a" * 49 + " " + "b" * 10, "n")
    base = s.rpartition("-")[0]
    assert base == "a" * 49
    assert len(base) <= ids.SLUG_MAX_BASE
    assert not base.endswith("-")


def test_slug_collapses_and_trims():
    assert ids.work_item_slug("  Hello   World!  ", "n").rpartition("-")[0] == "hello-world"


def test_slug_empty_and_whitespace_title_fall_back():
    assert ids.work_item_slug("", "n").startswith("item-")
    assert ids.work_item_slug("   ", "n").startswith("item-")
    assert ids.work_item_slug("!!!", "n").startswith("item-")


def test_slug_unicode_nfc_nfd_equivalent():
    # Canonically-equivalent Unicode must produce the same slug (NFC normalization).
    title_nfc = unicodedata.normalize("NFC", "Café Menu")
    title_nfd = unicodedata.normalize("NFD", "Café Menu")
    assert title_nfc != title_nfd  # genuinely different byte sequences
    assert ids.work_item_slug(title_nfc, "n") == ids.work_item_slug(title_nfd, "n")
