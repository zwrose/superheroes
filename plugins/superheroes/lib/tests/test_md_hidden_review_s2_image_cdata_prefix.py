"""A literal less-than sign before an image does not make it CDATA."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("prefix", ["<", "\\<"])
def test_literal_less_than_does_not_exclude_image_metadata(prefix):
    # axis: CDATA exclusion boundary -- an image after a literal or escaped less-than sign still hides its multiline description.
    body = prefix + "![alt\nZQ1](https://example.com/a.png)\n"
    rendering = md.scan(body)
    assert rendering.state_at(body.index("ZQ1")) in (md.HIDDEN, md.UNSURE), (
        body, rendering.lines, rendering.unsure
    )
