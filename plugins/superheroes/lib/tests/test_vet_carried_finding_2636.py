"""The vet's leftover checks treat a finding a list-item card carries as shown only when that card asks the same decision,
and read the decided-for-you grounds from the review template, their one home (#2636)."""
import pathlib

PLUGIN = pathlib.Path(__file__).resolve().parents[2]
RECEIPT = (PLUGIN / "skills" / "showrunner" / "reference" / "vet-receipt.md").read_text(encoding="utf-8")
DRAFTER = (PLUGIN / "agents" / "vet-drafter.md").read_text(encoding="utf-8")
TEMPLATE = (PLUGIN / "theme" / "review-template.md").read_text(encoding="utf-8")


def _row(title):
    rows = [line for line in RECEIPT.splitlines() if line.startswith(f"| **{title}** |")]
    assert len(rows) == 1, f"the vet receipt has {len(rows)} rows titled {title!r}"
    return rows[0]


def test_the_leftover_row_counts_a_carried_finding_only_when_the_card_asks_the_same_decision():
    # Axis: the vet's leftover row names the carrying card as a place the owner sees a finding, and makes the vet read the finding's
    # consequence against the card's question and options first.
    # Bites on: the carried placement dropped from the row, or the same-decision reading removed from it.
    row = _row("No leftover skipped the owner's review")
    assert "a line under the list-item card that carries it" in row
    assert "the finding's consequence against the card's question and options" in row


def test_the_leftover_row_links_the_decided_for_you_grounds_and_restates_none():
    # Axis: the decided-for-you grounds live only in the review template; the vet row links them and lists none of its own.
    # Bites on: the row's local copy of the grounds coming back (it once listed three, one of them "another card carries it").
    row = _row("No leftover skipped the owner's review")
    assert "[the template's grounds](../../../theme/review-template.md#decided-for-you)" in row
    assert "### Decided for you" in TEMPLATE
    for copied in ("a Canon entry, cited by id, answers it", "a fix in another layer of the same stack", "another card on the same sheet carries it"):
        assert copied not in row


def test_the_drafters_stack_rule_reads_the_carrying_card_the_same_way():
    # Axis: the vet drafter's stack-layer rule counts a carried finding as having reached the owner only under the same-decision reading.
    # Bites on: the drafter rule counting any carried line as shown.
    assert "the list-item card that carries it when that card asks exactly the decision" in DRAFTER
    assert "the finding's consequence against the card's question and options" in DRAFTER
