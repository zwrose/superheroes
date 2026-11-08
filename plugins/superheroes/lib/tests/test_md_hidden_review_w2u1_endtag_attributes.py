"""Regression for attribute values on raw HTML end tags."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_html_block_end_tag_attribute_value_reads_unsure():
    # axis: HTML-block attribute visibility -- a value on an end tag is not visible text.
    # Uncertainty belongs to this line only; the following heading must stay visible.
    prefix = "<div>\n"
    body = prefix + '</div title="ZQ1">\n\n## ZQ2\n'
    rendering = md.scan(body)
    assert rendering.state_at(len(prefix)) == md.UNSURE, (
        rendering.lines, rendering.unsure
    )
    assert rendering.state_at(body.index("## ZQ2")) == md.VISIBLE
