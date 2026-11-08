"""Regression for cmark-gfm's inline backtick boundary."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_backtick_limit_does_not_mask_a_raw_html_comment():
    # axis: delimiter length -- 80 backticks form code, while 81 stay literal and expose the raw comment.
    for width in (80, 81):
        ticks = "`" * width
        body = "a " + ticks + " <!-- b\nZQ1\nc --> " + ticks + "\n\n## ZQ2\n"
        rendering = md.scan(body)
        allowed = (md.VISIBLE,) if width == 80 else (md.HIDDEN, md.UNSURE)
        assert rendering.state_at(body.index("ZQ1")) in allowed, (width, rendering.lines, rendering.unsure)
