"""Inline-token brackets must not truncate a possible image description."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("description", [
    "`alt]`",
    '<span title="]">alt</span>',
])
def test_inline_token_bracket_does_not_close_image_description(description):
    # axis: image-description boundary -- a bracket consumed by a code span or HTML tag cannot expose later alt text as VISIBLE.
    body = "![" + description + "\nZQ1](https://example.com/a.png)\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (
        body, rendering.lines, rendering.unsure
    )
