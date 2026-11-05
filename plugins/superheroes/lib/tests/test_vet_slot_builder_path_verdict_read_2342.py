"""#2342 (builder path): the slot a builder body's ``write`` composes starts on the line after the advisor-vet marker's own
``str.splitlines()`` line, and the write refuses ``write-failed`` unless the region's first line, as the merge train reads
it, is the new verdict. The twin of the bot-path vet-817 fix (test_vet_slot_no_build_record_2342.py, F1-F5). Fake-runner
only; no real gh, no network. The fixtures come from test_vet_slot.py and test_vet_slot_leftovers_2280.py."""
import pytest

import pr_body_regions
import stack_check
import vet_slot as vs
from test_vet_slot import BODY, RECEIPT, SLOT, FakeGh, _comment, _pages
from test_vet_slot_leftovers_2280 import record_comment
from test_vet_slot_no_build_record_2342 import _RawFakeGh

PR = 42
REPO = "owner/example"
MARKER = "<!-- superheroes:advisor-vet -->"
HEAD = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
READY_LINE = "**Verdict: READY** · " + HEAD
NOT_READY_LINE = "**Verdict: NOT-READY** · " + HEAD + " (old)"
NOT_READY_SLOT = "**Verdict: NOT-READY** · " + HEAD + "\n\nNew owner half.\n"
READY_SLOT = "**Verdict: READY** · " + HEAD + "\n\nNew owner half.\n"
OLD_SLOT = MARKER + "\nold slot text\n"

# the seven measured separators: each ends the marker's own splitlines() line, and none is "\n"
SEPARATORS = ["\r", " ", " ", "\x85", "\x0b", "\x0c", "\x1c"]
SEPARATOR_IDS = ["cr", "u2028", "u2029", "u0085", "vt", "ff", "fs"]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _body(separator, old_line):
    assert BODY.count(OLD_SLOT) == 1
    return BODY.replace(OLD_SLOT, MARKER + separator + old_line + "\n")


def _vet(body):
    return stack_check.read_vet_verdict(body, HEAD)[0]


def _evaluate_write(body, slot, comments=None):
    comments = [_comment(RECEIPT)] if comments is None else comments
    return vs.evaluate("write", body, comments, slot, advisor_login="advisor")


def _raw_fake(body):
    return _RawFakeGh([body], _pages([_comment(RECEIPT), record_comment([])]))


def _run_write(fake, tmp_path, slot):
    path = tmp_path / "slot.md"
    path.write_text(slot, encoding="utf-8")
    return vs.run_verb("write", PR, REPO, slot_file=str(path), run=fake)


# --- B1: a NOT-READY write over an old READY reads NOT-READY -------------------------------------------------------

@pytest.mark.parametrize("separator", SEPARATORS, ids=SEPARATOR_IDS)
def test_b1_a_not_ready_write_over_an_old_ready_reads_not_ready_through_evaluate(separator):
    body = _body(separator, READY_LINE)
    assert _vet(body) == stack_check.VERDICT_READY  # the old READY is what the merge train reads before the write
    result = _evaluate_write(body, NOT_READY_SLOT)
    assert result["ok"] is True, result
    new_body = result["newBody"]
    assert _vet(new_body) == stack_check.VERDICT_NOT_READY
    region, refusal = pr_body_regions.read_region(new_body, "advisor-vet")
    assert refusal is None and region is not None
    assert stack_check._first_nonempty_line(region) == stack_check._first_nonempty_line(NOT_READY_SLOT)
    # the slot sits right after the marker's own line; the old verdict line is gone; the build record is untouched
    assert new_body.startswith(BODY[:BODY.index(OLD_SLOT)] + MARKER + separator + "\n" + NOT_READY_SLOT.strip("\n"))
    assert READY_LINE not in new_body
    assert new_body.endswith(BODY[BODY.index("<!-- superheroes:build-record -->"):])


@pytest.mark.parametrize("separator", SEPARATORS, ids=SEPARATOR_IDS)
def test_b1_a_not_ready_write_over_an_old_ready_reads_not_ready_through_run_verb(separator, tmp_path):
    body = _body(separator, READY_LINE)
    fake = _raw_fake(body)
    result = _run_write(fake, tmp_path, NOT_READY_SLOT)
    assert result["ok"] is True, result
    assert len(fake.edited) == 1
    assert _vet(fake.edited[0]) == stack_check.VERDICT_NOT_READY


# --- B2: the reverse; a READY write over an old NOT-READY reads READY -----------------------------------------------

@pytest.mark.parametrize("separator", SEPARATORS, ids=SEPARATOR_IDS)
def test_b2_a_ready_write_over_an_old_not_ready_reads_ready_through_evaluate(separator):
    body = _body(separator, NOT_READY_LINE)
    assert _vet(body) == stack_check.VERDICT_NOT_READY
    result = _evaluate_write(body, READY_SLOT)
    assert result["ok"] is True, result
    assert _vet(result["newBody"]) == stack_check.VERDICT_READY


@pytest.mark.parametrize("separator", SEPARATORS, ids=SEPARATOR_IDS)
def test_b2_a_ready_write_over_an_old_not_ready_reads_ready_through_run_verb(separator, tmp_path):
    body = _body(separator, NOT_READY_LINE)
    fake = _raw_fake(body)
    result = _run_write(fake, tmp_path, READY_SLOT)
    assert result["ok"] is True, result
    assert len(fake.edited) == 1
    assert _vet(fake.edited[0]) == stack_check.VERDICT_READY


# --- B3: a normal LF builder body composes the same bytes as before ------------------------------------------------

def test_b3_a_normal_lf_builder_body_composes_byte_for_byte_as_before():
    result = _evaluate_write(BODY, SLOT)
    assert result["ok"] is True, result
    a = BODY.index(MARKER + "\n") + len(MARKER + "\n")
    b = BODY.index("<!-- superheroes:build-record -->")
    assert result["newBody"] == BODY[:a] + "\n" + SLOT.strip("\n") + "\n\n" + BODY[b:]


# --- B4: the builder path's read-back refuses when the region's first line is not the slot's --------------------

@pytest.mark.parametrize("region", [
    (READY_LINE + "\n\n" + NOT_READY_SLOT, None),
    (None, None),
    (None, "markers-invalid"),
    ("\n\n", None),
], ids=["first-line-is-the-old-verdict", "no-region", "region-refusal", "blank-region"])
def test_b4_a_region_whose_first_line_is_not_the_slots_refuses_write_failed_and_pushes_nothing(
        monkeypatch, tmp_path, region):
    monkeypatch.setattr(vs.pr_body_regions, "read_region", lambda _body, _name: region)
    result = _evaluate_write(BODY, NOT_READY_SLOT)
    assert result["ok"] is False and result["reason"] == "write-failed", result
    assert "advisor-vet region" in result["detail"], result
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]))
    result = _run_write(fake, tmp_path, NOT_READY_SLOT)
    assert result["ok"] is False and result["reason"] == "write-failed", result
    assert "advisor-vet region" in result["detail"], result
    assert fake.edit_calls() == []
