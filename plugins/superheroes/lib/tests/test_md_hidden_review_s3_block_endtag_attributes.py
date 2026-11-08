"""Closing-tag attribute payloads in raw HTML must not read visible."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_html_block_end_tag_attribute_payload_reads_unsure_locally():
    # axis: closing-tag attribute visibility -- catches an attribute guard that excludes end tags and incorrectly exposes their discarded payload.
    body = '<div>\n</div title="ZQ1">\n\n## ZQ2\n'
    rendering = md.scan(body)
    assert rendering.state_at(len("<div>\n")) == md.UNSURE, (
        rendering.lines, rendering.unsure
    )
    assert rendering.state_at(body.index("## ZQ2")) == md.VISIBLE
