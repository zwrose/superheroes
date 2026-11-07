"""Regression for an invalid declaration before a multiline HTML tag."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_invalid_declaration_prefix_does_not_swallow_a_multiline_tag():
    # axis: declaration-prefix validity -- an uppercase name without following whitespace must not consume the subsequent tag.
    body = 'x <!X<a title=">\nZQ1\n"> y\n\n## ZQ2\n'
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (rendering.lines, rendering.unsure)
