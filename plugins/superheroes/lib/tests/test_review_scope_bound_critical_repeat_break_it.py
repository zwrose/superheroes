"""Critical findings cannot inherit scope rulings or advisor bounds."""

import pytest

import review_record as rr
from test_review_record_scope_bound_2532 import (
    BW, SW, build, chat, cite, doc_of, finding,
)


@pytest.mark.parametrize("kind", ["scope-ruling", "advisor-bound"])
@pytest.mark.parametrize("recipient", ["repeat", "member"])
def test_critical_recipient_keeps_its_owner_card(kind, recipient):
    # Axis: a Critical repeat or merged member cannot inherit either new decision kind from an Important finding.
    words = SW if kind == "scope-ruling" else BW
    earlier = finding(cite(kind, words=words))
    critical = finding(
        id="f-3", title="Critical recipient", line=30, severity="Critical",
    )
    if recipient == "repeat":
        critical["id"] = "f-2"
        repeated = critical
        findings = [earlier, repeated]
    else:
        repeated = finding(id="f-2", title="Kept repeat", line=20)
        findings = [earlier, repeated, critical]

    kept = {"outcome": "left-for-owner", "verdict": "confirmed"}
    if recipient == "member":
        kept["members"] = [rr._key(critical)]
    repeated["repeatOf"] = {
        "findingKey": rr._key(earlier),
        "id": earlier["id"],
        "fixHolds": None,
        "kept": kept,
    }

    record = build(findings, doc=doc_of(chat(words)))
    rows = {row["id"]: row for row in record["findings"]}
    assert rows[earlier["id"]]["outcome"] == "ruling"
    assert rows[critical["id"]]["outcome"] == "left-for-owner"
    assert critical["id"] in record["leftForOwner"]
