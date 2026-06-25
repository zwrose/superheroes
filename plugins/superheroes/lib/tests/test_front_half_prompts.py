import os

_EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "eval")


def _read(name):
    with open(os.path.join(_EVAL, name), encoding="utf-8") as f:
        return f.read()


def test_produce_leaf_prompt_present_and_versioned():
    t = _read("produce-leaf.md")
    assert "produce-leaf-version: 1" in t
    assert "author-only" in t.lower()
    assert "do not" in t.lower() and "review" in t.lower()      # no review fan-out
    assert "completion signal" in t.lower()                      # records completion (FR-8/UFR-4)


def test_doc_reviser_leaf_prompt_present_and_versioned():
    t = _read("doc-reviser-leaf.md")
    assert "doc-reviser-version: 1" in t
    assert "parentOrigin" in t                                   # FR-4 / UFR-2 extras seam
    assert "resolved" in t.lower() and "deferred" in t.lower()   # the report shape
