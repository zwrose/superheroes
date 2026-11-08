"""Unicode whitespace must not invent a GFM table inside an inline comment."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("separator", [chr(0xA0), chr(0x85), chr(0x2028)])
def test_non_gfm_whitespace_cannot_split_a_hidden_comment(separator):
    # axis: delimiter whitespace -- a character outside cmark's table whitespace keeps the multiline comment in one paragraph.
    body = "text <!--\n| - " + separator + "|\nZQ1\n-->\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (
        repr(separator), rendering.lines, rendering.unsure
    )
