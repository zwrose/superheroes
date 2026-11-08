"""A single-line image description is attribute metadata, not visible text."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("body", [
    "![ZQ1](https://example.com/a.png)\n",
    "![ZQ1][r]\n\n[r]: https://example.com/a.png\n",
])
def test_single_line_image_description_is_not_visible(body):
    # axis: image metadata visibility -- a sentinel occurring only in an image's alt attribute must not read VISIBLE.
    rendering = md.scan(body)
    assert rendering.state_at(0) in (md.HIDDEN, md.UNSURE), (
        body, rendering.lines, rendering.unsure
    )
