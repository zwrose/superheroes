"""Reference-definition metadata must not mask a raw inline comment."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("definition", [
    "[r`x]: /url\n",
    "[r\\]x]: /u`v\n",
    "[r\nx]: /u`v\n",
    '[r]: /url "title\ncontinued\n`"\n',
], ids=["label-backtick", "escaped-bracket-label", "multiline-label", "multiline-title"])
def test_reference_metadata_cannot_mask_an_inline_comment(definition):
    # axis: reference-metadata extent -- backticks consumed by a reference definition cannot hide the following raw comment from scan.
    # Checked against CommonMark 0.29 sections 4.7 and 6.5: labels allow escaped brackets and line endings, and titles allow multiple lines.
    body = definition + "text <!-- hidden\nZQ1\n--> tail `\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (
        definition, rendering.lines, rendering.unsure)
