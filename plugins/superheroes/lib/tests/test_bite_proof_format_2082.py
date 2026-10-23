"""#2082: an implementer order that names a bite-proof carries the record format inline.

Invariant: ``bite_proof_format.block_for`` returns the record format cut from
``rubric/bite-proof.md`` when the authored order names a bite-proof, nothing when it does not
(every verbatim implementer-template copy masked), and a refusal when the format cannot be cut.

Detector axes (bite-proof):
- F1 test_drift_* — drift: every record field and every cannot-produce shape the rubric carries
  appears verbatim in the inserted text, read from the rubric by this test's own parse
- F2 test_generated_* — source: the text follows the rubric file, never a kept copy
- F3 test_asks_* / test_template_* — mapping: asks only on authored text, never the template
- F4 test_unreadable_* — refusal: an order that asks never gets an empty format
"""
import os
import re

import bite_proof_format as BPF

_RUBRIC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "rubric", "bite-proof.md")
_TEMPLATE = os.path.join(os.path.dirname(_RUBRIC), "..", "agents", "implementer.md")


def _rubric():
    with open(_RUBRIC, encoding="utf-8") as fh:
        return fh.read()


def _entry_fields(text):
    """The bullets under the rubric's 'One bite-proof entry ... must contain:' line."""
    after = text.split("**One bite-proof entry, per guarded element, must contain:**", 1)[1]
    block = after.strip().split("\n\n", 1)[0]
    bullets = re.split(r"\n(?=- )", block)
    return [b for b in bullets if b.startswith("- ")]


def _shapes(text):
    """The three '**<Shape>.**' paragraphs under the cannot-produce heading."""
    section = text.split("\n## When the proof cannot be produced\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = [p.strip() for p in section.split("\n\n")]
    return [p for p in paragraphs if re.match(r"\*\*[A-Z][^*]+\.\*\*", p)]


def _template_body():
    with open(_TEMPLATE, encoding="utf-8") as fh:
        raw = fh.read()
    return raw[raw.find("\n---\n", 4) + 5:].strip()


def test_drift_every_record_field_appears_verbatim():
    # axis: drift — a field the rubric's record carries and the inserted text lacks fails here
    text, reason = BPF.block_for("Return a bite-proof record for the new guard.")
    assert reason is None
    fields = _entry_fields(_rubric())
    assert [f.split("**")[1] for f in fields] == [
        "guarded element", "neutralization", "raw red", "restore", "restore receipt", "raw green"]
    for field in fields:
        assert field in text


def test_drift_every_cannot_produce_shape_appears_verbatim():
    # axis: drift — a disclosure shape the rubric carries and the inserted text lacks fails here
    text, _ = BPF.block_for("Return a bite-proof record.")
    shapes = _shapes(_rubric())
    assert [s.split("**")[1] for s in shapes] == [
        "Unprovable as placed.", "Unreachable through this entry point.", "Unrunnable here."]
    for shape in shapes:
        assert shape in text
    assert "**Raw captures are bounded:**" in text and "**Bounded volume shape:**" in text


def test_generated_text_follows_the_rubric_file(tmp_path):
    # axis: source — a field added to the rubric reaches the inserted text with no code change
    edited = _rubric().replace(
        "- **raw green** — output after restore.",
        "- **raw green** — output after restore;\n- **novel field** — planted by this test.")
    assert edited != _rubric()
    path = tmp_path / "bite-proof.md"
    path.write_text(edited, encoding="utf-8")
    text, reason = BPF.block_for("Return a bite-proof record.", path=str(path))
    assert reason is None
    assert "- **novel field** — planted by this test." in text


def test_asks_on_either_spelling_and_not_otherwise():
    # axis: mapping — the scan reads 'bite-proof' and 'bite proof', any case
    assert BPF.block_for("Change a.txt and add a test.") == ("", None)
    for order in ("Record the Bite-Proof.", "Run a bite proof for each guard."):
        text, reason = BPF.block_for(order)
        assert reason is None
        assert text.startswith(
            "## Bite-proof record format (from the plugin's rubric/bite-proof.md)\n\n"
            "**The bite-proof record for every detector your order adds or changes**")


def test_template_copy_alone_never_asks():
    # axis: mapping — the template names bite-proofs on every order; only authored text asks
    body = _template_body()
    assert "bite-proof" in body
    assert BPF.block_for("# Order\nChange a.txt.\n\n" + body + "\n") == ("", None)
    text, _ = BPF.block_for("# Order\nAdd a guard; return its bite-proof.\n\n" + body + "\n")
    assert text.startswith("## Bite-proof record format")


def test_unreadable_rubric_refuses_an_order_that_asks(tmp_path):
    # axis: refusal — an order that asks never dispatches with the format missing
    missing = str(tmp_path / "absent.md")
    assert BPF.block_for("Return a bite-proof record.", path=missing) == (
        None, "bite-proof-format-unreadable")
    assert BPF.block_for("Change a.txt.", path=missing) == ("", None)


def test_unreadable_rubric_refuses_when_a_marker_is_missing_or_doubled(tmp_path):
    # axis: refusal — a cut whose start marker is gone or appears twice never guesses
    rubric = _rubric()
    gone = rubric.replace("**Where each part lives", "**Where the parts live")
    doubled = rubric + "\n## When the proof cannot be produced\n\nagain\n\n## End\n"
    for i, text in enumerate((gone, doubled)):
        path = tmp_path / ("r%d.md" % i)
        path.write_text(text, encoding="utf-8")
        assert BPF.block_for("Return a bite-proof record.", path=str(path)) == (
            None, "bite-proof-format-unreadable")
