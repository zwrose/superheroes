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


def _accepted(ex):
    return ic.accept_reading(ex, "/" + _TOKEN, _TOKEN, ex.get("where"), ex.get("takenAt"))


# Axis: the guidance stops naming the parameter, its one home, or the file that holds it
def test_guidance_names_the_parameter_and_its_home():
    text = _read_plugin(_GUIDANCE)
    for token in ("`%s`" % ic.READING_PARAM, "`READING_PARAM`", "`lib/iphone_check.py`"):
        assert token in text, "guidance missing %s" % token


# Axis: the text example lacks a key read needs, or read would refuse it (stale, wrong path, wrong context)
def test_guidance_text_field_example_is_a_reading_read_accepts():
    ex = _examples()[0]
    assert ic._complete_reading(ex)
    assert set(ex["focused"]) == {"tag", "type", "id", "name"}
    assert "value" in ex
    assert _accepted(ex)


# Axis: the password example carries a value, or loses valueWithheld, or read would refuse it
def test_guidance_password_example_carries_no_value():
    ex = _examples()[1]
    assert ex["focused"]["type"].lower() == "password"
    assert "value" not in ex
    assert ex["valueWithheld"] is True
    assert ic._complete_reading(ex)
    assert _accepted(ex)


# Axis: the fixture no longer sends a key the guidance names
def test_fixture_sends_every_key_the_guidance_example_names():
    script = _fixture_script()
    keys = list(_examples()[0]) + ["valueWithheld", "tag", "type", "id", "name"]
    missing = [k for k in keys
               if not (re.search(r"\b%s\s*:" % re.escape(k), script) or re.search(r"\.%s\s*=" % re.escape(k), script))]
    assert not missing, "fixture script never sends: %r" % missing


# Axis: the test-pilot set-up stops pointing at the guidance
def test_set_up_points_at_the_guidance():
    assert "${CLAUDE_PLUGIN_ROOT}/" + _GUIDANCE in _read_plugin("skills/test-pilot-init/SKILL.md")


# Axis: the "lacks its reporting script" stop stops pointing at the guidance
def test_lacks_script_stop_points_at_the_guidance():
    assert _GUIDANCE in _read_plugin("skills/test-pilot-execute/reference/execution-steps.md")


# Axis: the guidance stops stating the literal line the pilot reports for a missing script
def test_guidance_states_the_did_not_run_line():
    assert "iPhone check did not run — whole check: the app lacks its reporting script" in _read_plugin(_GUIDANCE)
