import json
import os
import re

import engine_adapter


def _review_base_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    return os.path.join(root, "plugins/superheroes/rubric/review-base.md")


def _read_review_base():
    return open(_review_base_path(), encoding="utf-8").read()


def _extract_stdout_channel_specimen(text):
    m = re.search(
        r"\*\*stdout channel\*\*.*?`(\{[^`]+\})`",
        text,
        re.DOTALL,
    )
    assert m, "stdout channel specimen not found in review-base.md"
    return m.group(1)


def test_review_base_has_doc_severity_addendum():
    text = _read_review_base()
    first_line = text.splitlines()[0] if text else ""
    match = re.fullmatch(r"<!-- rubric-version: (\d+) -->", first_line)
    assert match is not None, "rubric-version marker is missing or malformed"
    assert int(match.group(1)) >= 8, f"rubric-version {match.group(1)} is below the addendum floor of 8"
    assert "## Document-review severity" in text
    # docType-gated, states the plan-vs-tasks asymmetry and the fail-closed rule
    assert "docType" in text and "plan" in text and "tasks" in text
    assert "granularity" in text.lower()
    assert "ambiguity" in text.lower() or "fail closed" in text.lower()
    # the incident-anchored "always blocking" security carve-out must not be silently dropped —
    # it is the one clause protecting genuine security findings from demotion into the hand-off
    assert "unauthenticated" in text.lower()
    assert "security exemption" in text.lower() and "corrupt or lose data" in text.lower()


def test_review_base_stdout_specimen_accepted_by_stdout_parser():
    text = _read_review_base()
    specimen = _extract_stdout_channel_specimen(text)
    specimen_obj = json.loads(specimen)
    for finding in specimen_obj.get("findings", []):
        severity = finding.get("severity")
        if severity in ("Critical", "Important"):
            assert finding.get("evidence") is not None
            assert finding.get("suggestion") is not None
    res = engine_adapter.parse_result("codex", "review", specimen)
    assert res["ok"] is True
    for key, value in specimen_obj.items():
        if key == "findings":
            assert res["findings"] == value
        else:
            assert res.get(key) == value
