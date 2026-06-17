"""Anti-drift guard: the vendored identifiers must behave IDENTICALLY to the band reference.

This is what makes vendoring safe (CONVENTIONS' "plugins consume the reference impl"
decision): plugins/the-architect/lib/identifiers.py is a copy of eval/lib/identifiers.py, and if
the two ever diverge in behavior, this test fails loudly. We compare behavior (outputs),
not bytes, so the vendored copy may carry its own header/docstring.

The two modules are both named `identifiers`, so we load them from explicit paths under
distinct names rather than importing.
"""
import importlib.util
import os

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _load(rel_path, mod_name):
    path = os.path.join(_REPO_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VENDORED = _load("plugins/the-architect/lib/identifiers.py", "architect_vendored_identifiers")
BAND = _load("eval/lib/identifiers.py", "band_reference_identifiers")


SLUG_CASES = [
    ("Add Dark Mode Toggle", "fixed-nonce-v1"),   # golden
    ("", "n"),                                      # empty -> item fallback
    ("   ", "n"),                                   # whitespace-only
    ("!!!", "n"),                                   # all-punctuation
    ("Café Menu", "n"),                             # non-ASCII (NFC/NFD path)
    ("x" * 100, "n"),                               # over the 50-char cap
    ("a" * 49 + " " + "b" * 10, "n"),               # cap lands on a separator (trim-after-slice)
    ("Same Title", "nonce-a"),                      # collision-suffix
    ("Some Example Title", "nonce"),
]

FM = {
    "workItem": "add-toggle-abc123",
    "docType": "tasks",
    "parent": {"workItem": "add-toggle-abc123", "docType": "plan"},
    "size": "medium",
}
HASH_CASES = [
    (FM, "# Tasks\n\n- [ ] do the thing\n"),                       # golden-ish
    (FM, "café\n"),                                                # non-ASCII body
    (FM, "a\r\nb\n"),                                              # CRLF normalization
    (dict(FM, size="large"), "# Tasks\n"),                        # stable-field change
    (dict(FM, parent=None), "body\n"),                            # null parent
]


def test_constants_match():
    assert VENDORED.STABLE_FIELDS == BAND.STABLE_FIELDS
    assert VENDORED.SLUG_MAX_BASE == BAND.SLUG_MAX_BASE


def test_work_item_slug_behaves_identically():
    for title, nonce in SLUG_CASES:
        assert VENDORED.work_item_slug(title, nonce) == BAND.work_item_slug(title, nonce), (title, nonce)


def test_content_hash_behaves_identically():
    for fm, body in HASH_CASES:
        assert VENDORED.content_hash(fm, body) == BAND.content_hash(fm, body), (fm, body)


def test_content_hash_fail_closed_behaves_identically():
    incomplete = {"docType": "tasks", "size": "medium", "parent": None}  # no workItem
    with pytest.raises(ValueError):
        VENDORED.content_hash(incomplete, "body")
    with pytest.raises(ValueError):
        BAND.content_hash(incomplete, "body")
