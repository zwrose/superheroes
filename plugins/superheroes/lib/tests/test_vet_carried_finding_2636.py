"""The vet's leftover row reads the decided-for-you grounds from the review template, their one home (#2636).

Structural checks only: the doctrine surfaces' wording is not pinned (rubric/review-discipline.md, the pin rule)."""
import pathlib

PLUGIN = pathlib.Path(__file__).resolve().parents[2]
RECEIPT = (PLUGIN / "skills" / "showrunner" / "reference" / "vet-receipt.md").read_text(encoding="utf-8")
TEMPLATE = (PLUGIN / "theme" / "review-template.md").read_text(encoding="utf-8")
ROW = "| **No leftover skipped the owner's review** |"
LINK = "(../../../theme/review-template.md#decided-for-you)"


def test_the_leftover_row_is_one_row_and_links_the_template_grounds():
    # Axis: the vet receipt has exactly one leftover row, and it links the template's Decided for you section, which exists.
    # Bites on: the row duplicated or gone, its link to the grounds' home dropped, or the template heading the link names removed.
    rows = [line for line in RECEIPT.splitlines() if line.startswith(ROW)]
    assert len(rows) == 1
    assert LINK in rows[0]
    assert "### Decided for you" in TEMPLATE
