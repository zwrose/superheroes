"""Escaped pipes must retain cmark-gfm's table boundaries."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("where", ["header", "cell"])
def test_paired_backslashes_cannot_mask_a_table_comment(where):
    # axis: escaped-pipe boundaries -- paired backslashes before a pipe must not change table recognition or split one raw PI into literal fragments.
    slashes = chr(92) * 2
    if where == "header":
        body = (
            "| a " + slashes + "|\n"
            "| - |\n"
            "| `x |\n"
            "| <? > <!-- ?> |\n"
            "| y` |\n"
            "\n## ZQ1\n"
        )
    else:
        body = (
            "| a |\n"
            "| - |\n"
            "| x <? " + slashes + "| > <!-- ?> |\n"
            "\n## ZQ1\n"
        )
    rendering = md.scan(body)
    assert rendering.state_at(body.index("## ZQ1")) in (md.HIDDEN, md.UNSURE), (
        where, rendering.lines, rendering.unsure
    )
