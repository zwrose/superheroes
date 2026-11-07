"""#684: a raw HTML comment inside apparent backticks is not an acceptance.

Bites on: G2 retaining the entire apparent code span containing an opener.
Axis: missing reports the finding when its id and title are inside the raw
comment, before the closing backtick. Real scanner and record reader; no network.
"""
import leftover_accepting as la
from test_vet_slot_leftovers_2280 import F1, body, read_ok


def test_raw_comment_inside_apparent_code_span_does_not_accept_finding():
    source = body(
        "<div>Quoting `<!-- f-1 the retry loop never backs off -->`</div>\n"
    )
    assert la.missing(read_ok(F1), source) == [
        {"id": F1["id"], "title": F1["title"]}
    ]
