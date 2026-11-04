"""Fixed-above accounting follows the whole-body leftover assignment."""
import leftover_accepting as la
import pr_sheet
from test_pr_sheet_fixed_above_2332 import (
    ACCEPTING, COMMIT, NONE_BODY, TITLE, finding, make, stack_input, stack_records,
)


def test_fixed_above_bullet_keeps_automatic_accounting_after_reassignment():
    # Bites on: re-matching a fixed-above bullet alone changes its assigned leftover.
    # Axis: a bullet assigned as fixed above by the whole-body matching needs no accounting entry after an augmenting path.
    records = stack_records(low=[finding("f-1"), finding("f-2")])
    pr_body = ACCEPTING + (
        f"- f-1 and f-2 {TITLE} — fixed-above #11 {COMMIT}: fixed.\n"
        f"- f-1 {TITLE}: accepted.\n"
    )
    readable = {"ok": True, **records[0], "leftForOwner": ["f-1", "f-2"]}
    assert [claim["id"] for claim in la.fixed_above(readable, pr_body)] == ["f-2"]
    ordinary_bullet = pr_sheet.listed_bullets(10, pr_body)[1][0]
    advisor = stack_input(
        leftovers={"10:f-1": {
            "why": "Only the owner can say.",
            "context": "The first finding remains.",
            "options": "none",
        }},
        accounting={ordinary_bullet: {"leftover": "10:f-1"}},
    )
    sheet = make(records, advisor, {10: pr_body, 11: NONE_BODY})
    assert sheet["prSheet"]["whatChanged"]["caught"] == [
        f"#10: {TITLE} (fixed above in #11 at {COMMIT})"
    ]
    assert len(sheet["cards"]) == 1
    assert "nothingListed" not in sheet["prSheet"]
