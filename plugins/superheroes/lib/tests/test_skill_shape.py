import os


def test_review_base_has_doc_severity_addendum():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    text = open(os.path.join(root, "plugins/superheroes/rubric/review-base.md"), encoding="utf-8").read()
    assert "<!-- rubric-version: 7 -->" in text
    assert "## Document-review severity" in text
    # docType-gated, states the plan-vs-tasks asymmetry and the fail-closed rule
    assert "docType" in text and "plan" in text and "tasks" in text
    assert "granularity" in text.lower()
    assert "ambiguity" in text.lower() or "fail closed" in text.lower()
    # the incident-anchored "always blocking" security carve-out must not be silently dropped —
    # it is the one clause protecting genuine security findings from demotion into the hand-off
    assert "unauthenticated" in text.lower()
    assert "security exemption" in text.lower() and "corrupt or lose data" in text.lower()
