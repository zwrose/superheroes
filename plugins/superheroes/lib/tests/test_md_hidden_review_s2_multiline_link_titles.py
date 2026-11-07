"""Inline-link title continuation lines are metadata, not visible PR text."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("opener, closer", [('"', '"'), ("'", "'"), ("(", ")")])
def test_multiline_link_title_cannot_report_its_contents_visible(opener, closer):
    # axis: link-title visibility -- a title-only continuation line is emitted in an HTML attribute and must never read VISIBLE without any raw-HTML or backtick trigger.
    body = "[a](/u " + opener + "title\nZQ1\n" + closer + ")\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (
        opener, rendering.lines, rendering.unsure
    )
