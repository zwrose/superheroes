"""Raw HTML recovery must not expose non-rendered attribute words."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_recovered_open_tag_attribute_reads_unsure_locally():
    # axis: HTML recovery versus CommonMark tag grammar -- a slash before an
    # attribute name must not make discarded attribute text read visible.
    prefix = "<div>\n"
    body = prefix + "<span/ZQ1></span>\n</div>\n\n## ZQ2\n"
    rendering = md.scan(body)
    assert rendering.state_at(len(prefix)) == md.UNSURE, (
        rendering.lines, rendering.unsure
    )
    assert rendering.state_at(body.index("## ZQ2")) == md.VISIBLE
