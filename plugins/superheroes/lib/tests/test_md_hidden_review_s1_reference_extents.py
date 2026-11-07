"""Reference-definition backticks must not mask subsequent raw comments."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("prefix", [
    "[r`]: /u\n",
    '[r]:\n/u\n"title`"\n',
    '[r\\]s]: /u "`"\n',
    '[r\ns]: /u "`"\n',
], ids=["label", "third-line-title", "escaped-label", "multiline-label"])
def test_consumed_reference_backtick_cannot_mask_a_comment(prefix):
    # axis: reference-definition extent -- a backtick consumed with a definition must not create a code span around subsequent raw HTML.
    body = prefix + "x <!-- hidden\nZQ1\n--> tail `\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (
        rendering.lines, rendering.unsure
    )
