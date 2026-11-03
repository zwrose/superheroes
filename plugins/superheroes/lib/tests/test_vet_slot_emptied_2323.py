"""#2323: ``vet_slot.py write`` refuses ``body-emptied`` for a PR body that has lost the builder's owner half.

Fake-runner units; no real gh, no network. The fixtures come from test_vet_slot.py."""
import json

import pytest

import vet_slot as vs
from test_vet_slot import BODY, RECEIPT, SLOT, VIEW, FakeGh, _comment, _pages

PR = 42
REPO = "owner/example"
REMEDY = "restore the builder's body from the PR's edit history before writing the slot"
NO_HEADING = 'PR body has no "What\'s changing, and why" heading'
HEADING = "## What's changing, and why\n\nThe builder's owner half.\n\n"
MARKER = "<!-- superheroes:advisor-vet -->\n"
BUILD_RECORD = BODY[BODY.index("<!-- superheroes:build-record -->"):]

# a body cut down to its tail: the build record survives, the owner half does not
TAIL_BODY = BUILD_RECORD
# the same tail with the advisor-vet marker re-stamped above the build record by hand
RESTAMPED_BODY = "## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


@pytest.fixture
def slot_file(tmp_path):
    path = tmp_path / "slot.md"
    path.write_text(SLOT, encoding="utf-8")
    return str(path)


def _fake(body, **kwargs):
    return FakeGh([body], _pages([_comment(RECEIPT)]), **kwargs)


def _write(fake, slot_path):
    return vs.run_verb("write", PR, REPO, slot_file=slot_path, run=fake)


def _assert_emptied(result, fake, detail):
    assert result["ok"] is False
    assert result["reason"] == "body-emptied"
    assert detail in result["detail"]
    assert result["detail"].endswith(REMEDY)
    assert set(result) == {"ok", "reason", "detail"}
    assert fake.edit_calls() == []  # E7
    assert fake.calls == [list(VIEW)]  # refused at the body read, before the login and comments reads


# --- E1: an empty or whitespace body, and the REST null body ----------------------------------------

@pytest.mark.parametrize("body", ["", "   \n\t\n", "\n"])
def test_e1_empty_or_whitespace_body_refuses_body_emptied(body, slot_file):
    fake = _fake(body)
    _assert_emptied(_write(fake, slot_file), fake, "PR body is empty")


def test_e1_null_rest_body_refuses_body_emptied(slot_file):
    fake = _fake(BODY, view_raw=json.dumps({"body": None}))
    _assert_emptied(_write(fake, slot_file), fake, "PR body is empty")


@pytest.mark.parametrize("body", ["", "  \n"])
def test_e1_evaluate_refuses_an_empty_body_body_emptied(body):
    result = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied"
    assert "PR body is empty" in result["detail"] and result["detail"].endswith(REMEDY)
    assert "newBody" not in result


# --- E2: a body cut to its tail, with no advisor-vet marker -------------------------------------------

def test_e2_marker_less_tail_body_refuses_body_emptied_not_markers_invalid(slot_file):
    fake = _fake(TAIL_BODY)
    result = _write(fake, slot_file)
    _assert_emptied(result, fake, NO_HEADING)
    assert "above the advisor-vet marker" not in result["detail"]


def test_e2_the_check_runs_before_any_marker_check(slot_file):
    # two advisor-vet markers and no owner half: body-emptied, not markers-invalid
    body = "## Advisor vet\n" + MARKER + MARKER + "\n" + BUILD_RECORD
    fake = _fake(body)
    _assert_emptied(_write(fake, slot_file), fake, NO_HEADING)


# --- E3: the same tail with the marker re-stamped above the build record ----------------------------

def test_e3_restamped_tail_body_refuses_body_emptied(slot_file):
    fake = _fake(RESTAMPED_BODY)
    _assert_emptied(_write(fake, slot_file), fake,
                    NO_HEADING + " above the advisor-vet marker")


def test_e3_evaluate_refuses_the_restamped_tail_body():
    result = vs.evaluate("write", RESTAMPED_BODY, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied"
    assert NO_HEADING + " above the advisor-vet marker" in result["detail"]
    assert "newBody" not in result


# --- E4: a heading that does not count -----------------------------------------------------------------

HEADING_ONLY_INSIDE = [
    pytest.param("<!--\n## What's changing, and why\n-->\n\n## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD,
                 id="html-comment"),
    pytest.param("<!-- draft\n\n## What's changing, and why\n\n## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD,
                 id="html-comment-never-closed"),
    pytest.param("```\n## What's changing, and why\n```\n\n## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD,
                 id="fenced-block"),
    pytest.param("~~~md\n## What's changing, and why\n\n## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD,
                 id="fence-never-closed"),
    pytest.param("## Advisor vet\n" + MARKER + "\n" + HEADING + BUILD_RECORD,
                 id="slot-span"),
    pytest.param("## Advisor vet\n" + HEADING.replace("##", "<!--\n##") + "-->\n" + MARKER + BUILD_RECORD,
                 id="comment-just-above-marker"),
    pytest.param("## Advisor vet\n" + MARKER + BUILD_RECORD + "\n" + HEADING,
                 id="below-the-build-record"),
]


@pytest.mark.parametrize("body", HEADING_ONLY_INSIDE)
def test_e4_a_heading_only_inside_a_comment_fence_or_slot_span_refuses(body, slot_file):
    fake = _fake(body)
    result = _write(fake, slot_file)
    assert result["ok"] is False and result["reason"] == "body-emptied"
    assert "heading" in result["detail"] and result["detail"].endswith(REMEDY)
    assert fake.edit_calls() == []
    assert fake.calls == [list(VIEW)]


@pytest.mark.parametrize("body", HEADING_ONLY_INSIDE)
def test_e4_evaluate_agrees(body):
    result = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied"


@pytest.mark.parametrize("line", [
    "What's changing, and why",
    "#What's changing, and why",
    "    ## What's changing, and why",
    "####### What's changing, and why",
    "## Why this changes",
    "## What is changing, and why",
])
def test_e4_a_line_that_is_not_an_owner_half_heading_does_not_count(line, slot_file):
    body = line + "\n\n## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD
    fake = _fake(body)
    result = _write(fake, slot_file)
    assert result["reason"] == "body-emptied"
    assert fake.edit_calls() == []


# --- E5: a normal body still writes, with the same new body as before -------------------------------------

def _expected_new_body(body):
    a = body.index(MARKER) + len(MARKER)
    b = body.index("<!-- superheroes:build-record -->")
    return body[:a] + "\n" + SLOT.strip("\n") + "\n\n" + body[b:]


def test_e5_a_normal_body_still_writes_the_same_new_body(slot_file):
    fake = _fake(BODY)
    result = _write(fake, slot_file)
    assert result == {"ok": True, "verb": "write", "followups": ["FU1", "FU2"], "receipt": "https://x/c/1"}
    assert len(fake.edit_calls()) == 1
    assert fake.edited == [_expected_new_body(BODY)]


@pytest.mark.parametrize("heading", [
    "## What's changing, and why",
    "## What’s changing, and why",
    "### what's changing",
    "#   WHAT'S   CHANGING, AND WHY ##",
    "   # What's changing",
    "## What’s changing, and why <!-- note -->",
])
def test_e5_every_spelling_of_the_heading_counts(heading, slot_file):
    body = BODY.replace("## What's changing, and why", heading, 1)
    assert body != BODY or heading == "## What's changing, and why"
    fake = _fake(body)
    result = _write(fake, slot_file)
    assert result["ok"] is True, result
    assert fake.edited == [_expected_new_body(body)]


def test_e5_a_heading_after_a_closed_comment_and_after_a_closed_fence_counts(slot_file):
    body = "<!-- note -->\n```\ncode\n```\n" + HEADING + "## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD
    fake = _fake(body)
    assert _write(fake, slot_file)["ok"] is True


def test_e5_a_body_with_no_advisor_vet_marker_but_the_heading_reaches_the_marker_check(slot_file):
    body = BODY.replace(MARKER, "")
    fake = _fake(body)
    result = _write(fake, slot_file)
    assert result["reason"] == "markers-invalid"
    assert "advisor-vet marker appears 0 times" in result["detail"]
    assert fake.edit_calls() == []


# --- E6: check and handback keep today's reasons on an emptied body ------------------------------------------

@pytest.mark.parametrize("body,reason", [
    ("", "read-failed"),
    ("   \n\t\n", "read-failed"),
    (TAIL_BODY, "markers-invalid"),
])
def test_e6_check_keeps_its_reasons_on_an_emptied_body(body, reason):
    fake = _fake(body)
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is False and result["reason"] == reason
    assert fake.edit_calls() == []


@pytest.mark.parametrize("body,reason", [
    ("", "read-failed"),
    ("   \n\t\n", "read-failed"),
    (TAIL_BODY, "markers-invalid"),
])
def test_e6_handback_keeps_its_reasons_on_an_emptied_body(body, reason, tmp_path):
    assert vs.check_handback(body)["reason"] == reason
    path = tmp_path / "body.md"
    path.write_text(body, encoding="utf-8")
    assert vs.run_verb("handback", None, None, body_file=str(path))["reason"] == reason
    fake = _fake(body)
    assert vs.run_verb("handback", PR, REPO, run=fake)["reason"] == reason
    assert fake.edit_calls() == []


def test_e6_check_still_passes_a_restamped_tail_body():
    fake = _fake(RESTAMPED_BODY)
    assert vs.run_verb("check", PR, REPO, run=fake)["ok"] is True


# --- the chokepoint itself ----------------------------------------------------------------------------------------

def test_check_not_emptied_leaves_a_non_string_body_to_analyze_body():
    vs.check_not_emptied(None)
    result = vs.evaluate("write", None, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result == {"ok": False, "reason": "read-failed", "detail": "PR body is not a string"}


def test_reason_constant_is_the_literal_token():
    assert vs.REASON_BODY_EMPTIED == "body-emptied"
