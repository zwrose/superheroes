"""A delimiter-shaped data row must not move an established table's header."""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_hidden as md  # noqa: E402


def test_later_delimiter_row_cannot_join_earlier_table_cells():
    # axis: established-table boundary -- a later delimiter-shaped data row must not let code spans cross earlier table rows and mask raw HTML.
    body = (
        "| a | b |\n"
        "| - | - |\n"
        "| `x | 1 |\n"
        "| <? > <!-- ?> | 2 |\n"
        "| y` | 3 |\n"
        "| z | 4 |\n"
        "| - | - |\n"
        "\n## ZQ1\n"
    )
    rendering = md.scan(body)
    assert rendering.state_at(body.index("## ZQ1")) in (md.HIDDEN, md.UNSURE), (
        rendering.lines, rendering.unsure
    )
