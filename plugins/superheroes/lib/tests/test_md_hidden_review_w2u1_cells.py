"""Raw HTML constructs must respect GFM table-cell boundaries."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_a_tag_cannot_hide_raw_html_in_another_table_cell():
    # axis: raw-HTML cell boundaries -- a tag split across cells cannot consume a different cell's comment-opening processing instruction.
    # Checked against GFM section 4.10: each pipe-delimited cell is inline-parsed separately.
    body = (
        "| a | b | c |\n"
        "| - | - | - |\n"
        '| <a title=" | <? > <!-- ?> | "> |\n'
        "\n## ZQ1\n"
    )
    rendering = md.scan(body)
    assert rendering.state_at(body.index("## ZQ1")) in (md.HIDDEN, md.UNSURE), (
        rendering.lines, rendering.unsure)


def test_the_same_complete_attribute_in_a_paragraph_stays_visible():
    # axis: paragraph control -- without table-cell boundaries the complete quoted attribute contains no HTML comment.
    body = 'Text <a title=" | <? > <!-- ?> | "> end\n\n## ZQ1\n'
    rendering = md.scan(body)
    assert rendering.state_at(body.index("## ZQ1")) == md.VISIBLE
