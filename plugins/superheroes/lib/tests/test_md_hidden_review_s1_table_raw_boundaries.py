"""Raw inline HTML must respect GFM table-cell boundaries."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_cross_cell_tag_cannot_mask_a_raw_comment_opener():
    # axis: raw-HTML cell boundaries -- an incomplete tag in one cell cannot absorb a processing instruction in the next cell.
    for quote in ('"', "'"):
        body = (
            "| a | b |\n"
            "| - | - |\n"
            f"| x <a title={quote} | <? > <!-- ?> {quote}> |\n"
            "\n## ZQ1\n"
        )
        rendering = md.scan(body)
        assert rendering.state_at(body.index("## ZQ1")) in (md.HIDDEN, md.UNSURE), (
            quote, rendering.lines, rendering.unsure
        )
