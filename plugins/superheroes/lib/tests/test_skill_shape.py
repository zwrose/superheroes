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


def _parse_severity_enum_from_rubric(text):
    match = re.search(r'"severity":\s*"([^"]+)"', text)
    assert match, "review-base.md: severity enum pipe-list not found"
    return {part.strip() for part in match.group(1).split("|")}


def _extract_json_specimens_from_rubric(text):
    specimens = []
    for match in re.finditer(r"```json\n(.*?)\n```", text, re.DOTALL):
        block = match.group(1).strip()
        try:
            specimens.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    return specimens


def _severity_values_in_specimen(specimen):
    values = []
    if isinstance(specimen, list):
        for item in specimen:
            values.extend(_severity_values_in_specimen(item))
    elif isinstance(specimen, dict):
        severity = specimen.get("severity")
        if isinstance(severity, str):
            if "|" in severity:
                values.extend(part.strip() for part in severity.split("|") if part.strip())
            else:
                values.append(severity)
        for value in specimen.values():
            if isinstance(value, (list, dict)):
                values.extend(_severity_values_in_specimen(value))
    return values


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
    res = engine_adapter.parse_result("codex", "review", specimen)
    assert res["ok"] is True
    for key, value in specimen_obj.items():
        if key == "findings":
            assert res["findings"] == value
        else:
            assert res.get(key) == value


def test_review_base_specimen_severity_values_in_declared_enum():
    text = _read_review_base()
    declared = _parse_severity_enum_from_rubric(text)
    specimens = _extract_json_specimens_from_rubric(text)
    assert specimens, "review-base.md: no JSON specimens found"
    severity_values = []
    for specimen in specimens:
        severity_values.extend(_severity_values_in_specimen(specimen))
    assert severity_values, "review-base.md: specimens contain no severity values to guard"
    for value in severity_values:
        assert value in declared, f"specimen severity {value!r} not in declared enum {sorted(declared)}"
