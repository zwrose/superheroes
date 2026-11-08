"""HTML-block constructs must not report their hidden payload as visible."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("body,offset", [
    ("<!-- ZQ1 -->\n\n## ZQ2\n", 0),
    ("<div>\n<!-- ZQ1 -->\n</div>\n", 6),
    ("<?ZQ1?>\n", 0),
    ("<![CDATA[ZQ1]]>\n", 0),
    ("<!DOCTYPE ZQ1>\n", 0),
])
def test_html_block_hidden_payload_is_not_visible(body, offset):
    # axis: opening-line visibility -- a complete raw HTML hiding construct must not expose its payload as VISIBLE.
    rendering = md.scan(body)
    assert rendering.state_at(offset) in (md.HIDDEN, md.UNSURE), (
        body, rendering.lines, rendering.unsure
    )
