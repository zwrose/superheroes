"""Closing-tag attribute values must not count as visible body text."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


@pytest.mark.parametrize("tag", [
    '</div title="ZQ1">',
    "</DIV title='ZQ1'>",
    '</div title=ZQ1>',
])
def test_closing_tag_attribute_text_reads_unsure_on_its_line(tag):
    # axis: closing-tag attribute visibility -- HTML discards these values, so their source line must read UNSURE without making later lines unsure.
    body = '<div>\n' + tag + '\n\n## ZQ2\n'
    rendering = md.scan(body)
    assert rendering.state_at(len('<div>\n')) == md.UNSURE, (
        tag, rendering.lines, rendering.unsure
    )
    assert rendering.state_at(body.index('## ZQ2')) == md.VISIBLE
