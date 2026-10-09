"""Reporting-script guidance sync: the guidance states the interface lib/iphone_check.py implements."""
import json
import os
import re

import iphone_check as ic

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))
_GUIDANCE = "skills/test-pilot-init/reference/reporting-script.md"
_TOKEN = "ab12"


def _read_plugin(rel):
    with open(os.path.join(_PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


def _examples():
    blocks = re.findall(r"^```json\n(.*?)^```", _read_plugin(_GUIDANCE), re.DOTALL | re.MULTILINE)
    assert len(blocks) == 2, "guidance must hold exactly two json blocks, found %d" % len(blocks)
    return [json.loads(b) for b in blocks]


def _fixture_script():
    page = _read_plugin("lib/tests/fixtures/iphone/reading-page.html")
    m = re.search(r"<script>(.*?)</script>", page, re.DOTALL)
    assert m and m.group(1).strip(), "fixture <script> not found or empty"
    return m.group(1)


def _literal_keys(body, name):
    """Top-level keys of the `name = {...}` object literal in body (depth-0 split, quotes respected)."""
    m = re.search(r"\b%s\s*=\s*\{" % re.escape(name), body)
    assert m, "buildReading() builds no `%s = {...}` literal" % name
    items, depth, quote, cur = [], 0, None, ""
    for ch in body[m.end():]:
        if quote:
            cur += ch
            quote = None if ch == quote else quote
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                items.append(cur)
                break
            depth -= 1
        if ch == "," and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    keys = set()
    for item in items:
        km = re.match(r"\s*(\w+)\s*:", item)
        if km:
            keys.add(km.group(1))
    return keys


def _reading_shape():
    """(sent top-level keys, focused keys), parsed from buildReading() in the fixture, the declared home."""
    script = _fixture_script()
    m = re.search(r"function buildReading\(\)\s*\{(.*?)\n\}", script, re.DOTALL)
    assert m, "fixture has no buildReading()"
    body = m.group(1)
    sent = _literal_keys(body, "r") | set(re.findall(r"\br\.(\w+)\s*=", body))
    return sent, _literal_keys(body, "focused")


def _accepted(ex):
    return ic.accept_reading(ex, "/" + _TOKEN, _TOKEN, ex.get("where"), ex.get("takenAt"))


# Axis: the guidance stops naming the parameter, its one home, or the file that holds it
def test_guidance_names_the_parameter_and_its_home():
    text = _read_plugin(_GUIDANCE)
    for token in ("`%s`" % ic.READING_PARAM, "`READING_PARAM`", "`lib/iphone_check.py`"):
        assert token in text, "guidance missing %s" % token


# Axis: the text example's keys drift from the fixture's buildReading() shape, lacks a key read needs, read would refuse it, or it shows a password field's value
def test_guidance_text_field_example_is_a_reading_read_accepts():
    ex = _examples()[0]
    assert ic._complete_reading(ex)
    sent, focused_keys = _reading_shape()
    assert set(ex["focused"]) == focused_keys
    assert set(ex) <= sent
    assert ex["focused"]["type"].lower() != "password"
    assert ex["valueWithheld"] is False
    assert "value" in ex
    assert _accepted(ex)


# Axis: the password example's keys drift from buildReading()'s shape, carries a value, loses valueWithheld, or read would refuse it
def test_guidance_password_example_carries_no_value():
    ex = _examples()[1]
    sent, focused_keys = _reading_shape()
    assert set(ex["focused"]) == focused_keys
    assert set(ex) <= sent
    assert ex["focused"]["type"].lower() == "password"
    assert "value" not in ex
    assert ex["valueWithheld"] is True
    assert ic._complete_reading(ex)
    assert _accepted(ex)


# Axis: buildReading() no longer sends a top-level or focused key either guidance example names
def test_fixture_sends_every_key_the_guidance_example_names():
    sent, focused_keys = _reading_shape()
    missing = []
    for ex in _examples():
        missing += sorted(set(ex) - sent)
        missing += sorted(set(ex["focused"]) - focused_keys)
    assert not missing, "fixture buildReading() never sends: %r" % missing


# Axis: the test-pilot set-up stops pointing at the guidance
def test_set_up_points_at_the_guidance():
    assert "${CLAUDE_PLUGIN_ROOT}/" + _GUIDANCE in _read_plugin("skills/test-pilot-init/SKILL.md")


# Axis: the "lacks its reporting script" stop stops pointing at the guidance
def test_lacks_script_stop_points_at_the_guidance():
    assert _GUIDANCE in _read_plugin("skills/test-pilot-execute/reference/execution-steps.md")


# Axis: the guidance stops stating the literal line the pilot reports for a missing script
def test_guidance_states_the_did_not_run_line():
    line = ic.did_not_run_lines({"whole": "the app lacks its reporting script"})[0]
    assert line in _read_plugin(_GUIDANCE)
