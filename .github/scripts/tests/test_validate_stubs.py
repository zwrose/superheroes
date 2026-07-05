import os

import validate_stubs as vst


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_clean_tree_has_no_violations(tmp_path):
    root = str(tmp_path)
    _write(root, "plugins/superheroes/lib/a.py", "x = 0  # STUB(#231): ceiling inert in live runs\n")
    _write(root, "plugins/superheroes/lib/b.js", "const y = 1  // no marker here\n")
    assert vst.gather_violations(root) == []


def test_flags_marker_missing_issue(tmp_path):
    root = str(tmp_path)
    _write(root, "plugins/superheroes/lib/a.py", "def sampler():  # STUB(): fake\n")
    errors = vst.gather_violations(root)
    assert len(errors) == 1
    assert "a.py:1:" in errors[0] and "no issue reference" in errors[0]


def test_flags_malformed_ref(tmp_path):
    root = str(tmp_path)
    _write(root, "plugins/superheroes/lib/a.js", "let z = 2  // STUB(TODO): unwired\n")
    errors = vst.gather_violations(root)
    assert len(errors) == 1 and "malformed" in errors[0]


def test_skips_test_trees_and_bundles(tmp_path):
    root = str(tmp_path)
    # a malformed marker inside a tests/ tree is a fixture, not a production seam
    _write(root, "plugins/superheroes/lib/tests/test_x.py", "s = '# STUB(): fixture'\n")
    _write(root, "plugins/superheroes/lib/showrunner.bundle.js", "// STUB(): generated\n")
    _write(root, "plugins/superheroes/lib/test_helper.py", "# STUB(): also skipped by name\n")
    assert vst.gather_violations(root) == []


def test_placeholder_token_is_exempt(tmp_path):
    root = str(tmp_path)
    # a doc/example using the reserved #NNN placeholder must NOT be flagged
    _write(root, "plugins/superheroes/lib/doc.py", '"""Mark a seam # STUB(#NNN): what is unwired."""\n')
    assert vst.gather_violations(root) == []


def test_main_returns_zero_on_real_repo():
    # The real plugin tree must stay clean (this is what CI runs).
    assert vst.main([]) == 0
