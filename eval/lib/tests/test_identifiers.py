"""Tests for the canonical §6 identifier reference impls.

These double as the conformance check that the reference matches CONVENTIONS §6.1/§6.3,
and as the dogfooding that surfaces any remaining ambiguity in the spec.

The GOLDEN-VALUE tests are the load-bearing ones: a pure-property suite (determinism,
sensitivity) stays green even if the byte-exact canonicalization drifts — which would
silently change the §4.4 exactly-once branch key. The frozen golden values pin the
exact output, so any drift fails loudly. If §6.1/§6.3 ever changes the canonicalization,
update these goldens IN THE SAME COMMIT as the spec change (never to make a test pass).
"""
import re
import unicodedata

import pytest

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


# ---- §6.3 content_hash -----------------------------------------------------------

BASE_FM = {
    "workItem": "add-toggle-abc123",
    "docType": "tasks",
    "parent": {"workItem": "add-toggle-abc123", "docType": "plan"},
    "size": "medium",
}
BODY = "# Tasks\n\n- [ ] do the thing\n"

GOLDEN_FM = {
    "workItem": "add-dark-mode-toggle-aa11bb",
    "docType": "tasks",
    "parent": {"workItem": "add-dark-mode-toggle-aa11bb", "docType": "plan"},
    "size": "medium",
}
GOLDEN_BODY = "# Tasks\n\n- [ ] write the failing test\n- [ ] make it pass\n"


def test_content_hash_golden_value():
    # Frozen anchor: pins the exact byte-level canonicalization (separators, ensure_ascii,
    # concatenation, 16-hex truncation). Drift here breaks the cross-plugin branch key.
    assert ids.content_hash(GOLDEN_FM, GOLDEN_BODY) == "083de7d3d98af005"


def test_content_hash_deterministic():
    assert ids.content_hash(BASE_FM, BODY) == ids.content_hash(dict(BASE_FM), BODY)


def test_content_hash_is_16_hex():
    assert re.fullmatch(r"[0-9a-f]{16}", ids.content_hash(BASE_FM, BODY))


def test_content_hash_ignores_volatile_fields():
    noisy = dict(BASE_FM, updated="2026-06-14", created="2025-01-01", status="approved",
                 gates={"review": "passed"}, issue=42, producedBy="the-architect@9.9.9")
    assert ids.content_hash(noisy, BODY) == ids.content_hash(BASE_FM, BODY)


def test_content_hash_changes_on_stable_fields():
    assert ids.content_hash(dict(BASE_FM, size="large"), BODY) != ids.content_hash(BASE_FM, BODY)
    assert ids.content_hash(dict(BASE_FM, workItem="other-def456"), BODY) != ids.content_hash(BASE_FM, BODY)
    assert ids.content_hash(dict(BASE_FM, parent=None), BODY) != ids.content_hash(BASE_FM, BODY)


def test_content_hash_changes_on_body():
    assert ids.content_hash(BASE_FM, BODY + "- [ ] another\n") != ids.content_hash(BASE_FM, BODY)


def test_content_hash_key_order_irrelevant():
    reordered = {"size": "medium", "parent": {"docType": "plan", "workItem": "add-toggle-abc123"},
                 "docType": "tasks", "workItem": "add-toggle-abc123"}
    assert ids.content_hash(reordered, BODY) == ids.content_hash(BASE_FM, BODY)


def test_content_hash_normalizes_line_endings():
    assert ids.content_hash(BASE_FM, "a\r\nb\n") == ids.content_hash(BASE_FM, "a\nb\n")


def test_content_hash_strips_trailing_whitespace_per_line():
    assert ids.content_hash(BASE_FM, "a   \nb\t\n") == ids.content_hash(BASE_FM, "a\nb\n")


def test_content_hash_unicode_nfc_nfd_equivalent():
    # The §6.3 "byte-identical across hosts" guarantee: canonically-equivalent Unicode in
    # the body must hash the same (NFC normalization). This is the macOS-NFD/Linux-NFC gap.
    body_nfc = BODY + unicodedata.normalize("NFC", "café\n")
    body_nfd = BODY + unicodedata.normalize("NFD", "café\n")
    assert body_nfc != body_nfd  # genuinely different bytes
    assert ids.content_hash(BASE_FM, body_nfc) == ids.content_hash(BASE_FM, body_nfd)


def test_content_hash_fails_closed_on_missing_stable_field():
    incomplete = {"docType": "tasks", "size": "medium", "parent": None}  # no workItem
    with pytest.raises(ValueError):
        ids.content_hash(incomplete, BODY)
