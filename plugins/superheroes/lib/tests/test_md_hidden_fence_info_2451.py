"""#2451 / vet 897 V897-1: ``md_hidden.scan`` never reads a fenced code block's opening line as ``VISIBLE`` when that line
carries an info string.

The invariant: a fence opener line with an info string (any non-blank text after the opening run of three or more backticks
or tildes) reads ``UNSURE``, because GitHub renders an info string only as attributes (``lang``, ``data-meta``) and shows
no word on that line. The reading is per line, not sticky: it adds no entry to ``Rendering.unsure``. A line another rule
already reads ``HIDDEN`` or ``UNSURE`` keeps that reading. A fence opener with no info string (only the run, optionally
followed by spaces or tabs) is unchanged, and so is a fenced content line that merely looks like an opener.

Why it matters: once order o1 removed the sticky "image description that may span lines" point from a badge table, nothing
kept an acceptance written only in a fence opener's info string out of ``leftover_accepting``'s check; fixing it in
``md_hidden`` means every caller inherits it.

Guard tests are named ``test_e7_*`` (E7: the fence-opener info-string reading, the ``fence_info`` add at the opener and the
``_scan`` override); the bite-proof record is ``bite_proofs/i2451_md_hidden_image_same_line.md`` (section E7). Fake data
only: no real gh, no network."""
import pytest

import leftover_accepting as la
import md_hidden

V = md_hidden.VISIBLE

_ROWS = "".join("| [example-pkg-%s](https://example.invalid/p/%s) | [![age](https://example.invalid/b/%d.svg)](https://example.invalid/d) |\n"
                % (c, c, i) for i, c in enumerate("abc"))
TABLE = "| Package | Age |\n|---|---|\n" + _ROWS
FENCE = "```text F-1 Slow retry loop\n```\n"
RECORD = {"ok": True, "leftForOwner": ["F-1"],
          "findings": [{"id": "F-1", "title": "Slow retry loop", "outcome": "left-for-owner"}]}
ACCEPTING = "\n## What we're accepting\n\n"


def test_e7_info_string_acceptance_under_a_badge_table_is_missing():
    """V897 (a): an acceptance written only in a fence opener's info string is never shown, so F-1 is still missing."""
    body = TABLE + ACCEPTING + FENCE
    assert la.missing(RECORD, body) == [{"id": "F-1", "title": "Slow retry loop"}]


def test_e7_plain_acceptance_under_the_same_table_still_counts():
    """V897 (b): the same table and fence, with a plain bullet naming F-1, still counts as accepted."""
    body = TABLE + ACCEPTING + FENCE + "\n- F-1 Slow retry loop: merging accepts slower recovery.\n"
    assert la.missing(RECORD, body) == []


def _line_start(body, line_text):
    at = body.index(line_text)
    assert at == 0 or body[at - 1] == "\n", "the opener text must start a line"
    return at


@pytest.mark.parametrize("body, bare, opener", [
    (FENCE, "```\n```\n", "```text F-1 Slow retry loop"),
    (TABLE + "\n" + FENCE, TABLE + "\n```\n```\n", "```text F-1 Slow retry loop"),
    ("- ```text x\n  y\n  ```\n", "- ```\n  y\n  ```\n", "- ```text x"),
    ("> ```text x\n> y\n> ```\n", "> ```\n> y\n> ```\n", "> ```text x"),
    ("~~~ x\ny\n~~~\n", "~~~\ny\n~~~\n", "~~~ x"),
], ids=["bare-document", "image-above", "list-item", "blockquote", "tilde"])
def test_e7_fence_opener_with_info_string_is_not_visible(body, bare, opener):
    """V897 (c), F7, F8: the opener line is not VISIBLE, and the reading is per line: ``unsure`` holds no entry (by reason)
    that the same body with the info string removed does not hold."""
    rendering = md_hidden.scan(body)
    assert rendering.state_at(_line_start(body, opener)) != V
    assert {why for _, why in rendering.unsure} <= {why for _, why in md_hidden.scan(bare).unsure}


def test_e7_bare_opener_and_lookalike_content_stay_visible():
    """F9: a bare opener (run only, trailing spaces allowed) reads VISIBLE. F10: a content line that looks like an opener,
    inside an open fence, is not an opener and reads VISIBLE."""
    for body in ("```\ny\n```\n", "~~~   \ny\n~~~\n"):
        assert md_hidden.scan(body).state_at(0) == V
    body = "````\n```text x\n````\n"
    assert md_hidden.scan(body).state_at(_line_start(body, "```text x")) == V


@pytest.mark.parametrize("example, kept", [
    ("```text\nsample\n```\n", "```"),
    ("```bash\nrun a command\n```\n", "```"),
    ("- ```text\n  sample\n  ```\n", "- ```"),
    ("~~~ text\nsample\n~~~\n", "~~~"),
], ids=["backtick", "bash", "list-item", "tilde"])
def test_e8_a_language_tagged_example_above_the_section_keeps_its_fence(example, kept):
    """Review finding (scoped finder, round 1 of the vet-897 review): a code example tagged with a language above "What
    we're accepting" must not make the section disappear. The leftover reader blanks lines md_hidden does not read
    VISIBLE and re-reads the fences from what is left; the opener keeps its fence run, so its closer still closes it and
    the plain acceptance below counts. Oracle (cmark-gfm 0.29.0.gfm.13): the example renders as a code block and the
    heading and bullet render as shown text."""
    body = example + ACCEPTING + "- F-1 Slow retry loop\n"
    assert la.missing(RECORD, body) == []
    assert la._visible(body).split("\n")[0] == kept  # the opener keeps its fence run; its info string is blanked


@pytest.mark.parametrize("section", [
    "```text x\n```\nF-1 Slow retry loop\n",
    "```bash\nrun a command\n```\n\n- F-1 Slow retry loop: merging accepts slower recovery.\n",
], ids=["paragraph-after-fence", "bullet-after-fence"])
def test_e9_a_language_tagged_example_inside_the_section_does_not_stop_the_acceptance(section):
    """Review finding (same): inside the section, the opener's kept fence run is markup only, so the line reads shown and
    does not end the item before the acceptance that follows the fence. Oracle (cmark-gfm 0.29.0.gfm.13): the fence renders
    as a code block and "F-1 Slow retry loop" as shown text after it."""
    assert la.missing(RECORD, ACCEPTING.lstrip("\n") + section) == []


def test_e10_an_opener_whose_whole_fence_is_hidden_is_not_named():
    """Fix audit (round 2 of the vet-897 review): a tagged fence inside a raw HTML comment is hidden whole, opener and
    closer alike, so ``fence_info`` does not name its opener; the leftover reader blanks both delimiters together and the
    visible section after the comment still counts. Oracle (cmark-gfm 0.29.0.gfm.13 read as HTML5): the fence sits inside
    the comment, and the heading and bullet after it are shown."""
    body = ("<div><!--\n\n```text\nhidden\n```\n\n<div>--></div>\n" + ACCEPTING + "- F-1 Slow retry loop\n")
    assert md_hidden.scan(body).fence_info == frozenset()
    assert la.missing(RECORD, body) == []
