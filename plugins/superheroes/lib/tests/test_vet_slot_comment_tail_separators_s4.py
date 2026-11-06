"""Closing-comment tails retain Markdown line boundaries through Unicode separators.

Fake gh and a NOT-READY slot isolate owner-heading visibility from transport and
READY leftover checks. Builder markers are present; an HTML wrapper is optional
and deliberately absent so the inline-code exemption is exercised.
"""
import pytest

import vet_slot as vs
from test_vet_slot import FakeGh, _comment, _pages


@pytest.mark.parametrize("entrypoint", ["evaluate", "run_verb"])
@pytest.mark.parametrize("separator, hidden", [
    ("\n", False),
    (chr(0x2028), True),
    (chr(0x85), True),
    ("\f", True),
], ids=["lf", "u2028", "nel", "formfeed"])
def test_comment_tail_preserves_markdown_line_boundaries(
        entrypoint, separator, hidden, tmp_path, monkeypatch):
    # axis: non-Markdown separators after a comment closer must not exempt the
    # later opener on that Markdown line; its hidden owner heading must refuse
    # body-emptied through evaluate and run_verb. A real LF permits the write.
    body = (
        "<!-- done --> " + separator + "`<!--` note\n"
        + "## What's changing, and why\n\nOwner-facing scope.\n\n"
        + "## Advisor vet\n<!-- superheroes:advisor-vet -->\n**Verdict: NOT-READY** · old\n\nold slot\n\n"
        + "<!-- superheroes:build-record -->\n"
        + "<!-- superheroes:followups none -->\n"
    )
    receipt = (
        "<!-- superheroes:vet-receipt -->\n**Vet 1: NOT-READY.**\n"
        "<!-- superheroes:dispositions none -->\n"
    )
    slot = "**Verdict: NOT-READY** · " + "a" * 40 + "\n\nNew owner half.\n"
    comments = [_comment(receipt)]
    fake = None
    if entrypoint == "evaluate":
        result = vs.evaluate("write", body, comments, slot, advisor_login="advisor")
    else:
        # Transport and scratch isolation do not supply the visibility condition.
        monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
        monkeypatch.setattr(vs.tempfile, "tempdir", str(tmp_path))
        slot_file = tmp_path / "slot.md"
        slot_file.write_text(slot, encoding="utf-8")
        fake = FakeGh([body], _pages(comments))
        result = vs.run_verb("write", 42, "owner/example", slot_file=str(slot_file), run=fake)
    if hidden:
        assert result["ok"] is False, result
        assert result["reason"] == "body-emptied", result
        if fake is not None:
            assert fake.edit_calls() == []
    else:
        assert result["ok"] is True, result
