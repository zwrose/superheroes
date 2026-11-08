"""Raw HTML block tags must not expose hidden attribute words as visible."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("tag", ["<div ZQ1=>", "<div /ZQ1>"])
def test_html_recovery_tags_hide_attribute_words_on_their_line(tag):
    # axis: raw-block tag recognition -- HTML consumes these malformed attributes, so their words must read UNSURE while a later heading stays VISIBLE.
    body = "<div>\n" + tag + "\n</div>\n\n## ZQ9\n"
    rendering = md.scan(body)
    assert rendering.state_at(len("<div>\n")) == md.UNSURE, (
        tag, rendering.lines, rendering.unsure
    )
    assert rendering.state_at(body.index("## ZQ9")) == md.VISIBLE
