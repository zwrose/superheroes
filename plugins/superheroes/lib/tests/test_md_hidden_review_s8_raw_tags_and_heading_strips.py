"""Review on 17046c62, round 1: raw-block tags read as HTML reads them, and ATX heading strips match the inline pass."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_a_doubled_equals_open_tag_in_an_html_block_reads_unsure():
    # axis: HTML recovery versus CommonMark tag grammar -- `<div ZQ1==x>` fails the inline open-tag grammar, but HTML
    # still reads ZQ1 as an attribute name, so the line must not read visible.
    body = "<div ZQ1==x>\n</div>\n\n## ZQ9\n"
    rendering = md.scan(body)
    assert rendering.state_at(0) == md.UNSURE, (rendering.lines, rendering.unsure)
    assert rendering.state_at(body.index("## ZQ9")) == md.VISIBLE


def test_a_split_tag_with_a_quoted_gt_reads_unsure_from_its_first_line():
    # axis: tag boundary and quote state -- the `>` inside the open title value does not end the tag, so ZQ1 on the
    # first line is inside the attribute and the first line must not read visible.
    body = '<div title="ZQ1>\nZQ2">\n</div>\n\n## ZQ9\n'
    rendering = md.scan(body)
    assert rendering.state_at(0) == md.UNSURE, (rendering.lines, rendering.unsure)
    assert rendering.state_at(body.index("ZQ2")) != md.VISIBLE


def test_a_closed_tag_in_an_html_block_still_ends_at_its_gt():
    # control: a plain tag and the text after it keep their answers.
    body = "<div>\n<span>ZQ1</span>\n</div>\n\n## ZQ9\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("<span>")) == md.VISIBLE
    assert rendering.state_at(body.index("## ZQ9")) == md.VISIBLE


@pytest.mark.parametrize("heading", [
    "## <3>Advisor vet",
    "## <!-->Other --> Advisor vet",
    "## <!--->Other --> Advisor vet",
    "## `<b>`Advisor vet",
    "## \\<b>Advisor vet",
])
def test_a_heading_strip_that_is_not_one_inline_construct_reads_unsure(heading):
    # axis: heading_text strips every <...> run and every comment run; one the inline pass did not read as exactly one
    # construct is text GitHub shows, so the heading's text is not GitHub's and its line reads unsure.
    body = heading + "\n\nZQ1\n"
    rendering = md.scan(body)
    assert rendering.state_at(0) == md.UNSURE, (rendering.lines, rendering.headings)
    assert all(state != md.VISIBLE for _, _, state in rendering.headings), rendering.headings
    assert rendering.state_at(body.index("ZQ1")) == md.VISIBLE


@pytest.mark.parametrize("heading, text", [
    ("## Advisor <!-- note --> vet", "Advisor  vet"),
    ("## <b>Advisor</b> vet", "Advisor vet"),
])
def test_a_heading_whose_strips_are_inline_constructs_stays_visible(heading, text):
    # control: a real comment and real tags are each one construct, so the heading keeps reading visible.
    rendering = md.scan(heading + "\n")
    assert rendering.state_at(0) == md.VISIBLE
    assert [(t.split(), s) for _, t, s in rendering.headings] == [(text.split(), md.VISIBLE)]
