"""Tests for the canonical §6 identifier reference impls.

These double as the conformance check that the reference matches CONVENTIONS §6.1/§6.3,
and as the dogfooding that surfaces any remaining ambiguity in the spec.
"""
import re

import identifiers as ids


# ---- §6.1 work_item_slug ---------------------------------------------------------

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


def test_slug_caps_base_at_50():
    base = ids.work_item_slug("x" * 100, "n").rpartition("-")[0]
    assert len(base) <= ids.SLUG_MAX_BASE


def test_slug_collapses_and_trims():
    assert ids.work_item_slug("  Hello   World!  ", "n").rpartition("-")[0] == "hello-world"


def test_slug_empty_title_falls_back():
    assert ids.work_item_slug("!!!", "n").startswith("item-")


# ---- §6.3 content_hash -----------------------------------------------------------

BASE_FM = {
    "workItem": "add-toggle-abc123",
    "docType": "tasks",
    "parent": {"workItem": "add-toggle-abc123", "docType": "plan"},
    "size": "medium",
}
BODY = "# Tasks\n\n- [ ] do the thing\n"


def test_content_hash_deterministic():
    assert ids.content_hash(BASE_FM, BODY) == ids.content_hash(dict(BASE_FM), BODY)


def test_content_hash_is_16_hex():
    assert re.fullmatch(r"[0-9a-f]{16}", ids.content_hash(BASE_FM, BODY))


def test_content_hash_ignores_volatile_fields():
    noisy = dict(BASE_FM, updated="2026-06-14", created="2025-01-01", status="approved",
                 gates={"review": "passed"}, issue=42, producedBy="define@9.9.9")
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
