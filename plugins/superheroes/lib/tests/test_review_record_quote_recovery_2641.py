import canon
import review_record as rr
from test_review_record_owner_ruling import DOC, L2, U, X, account, readers, the_finding


def test_recovered_ruling_preserves_the_existing_quote_once():
    # Axis: the writer preserves a clause-shaped quotation when a demoted ruling resolves again.
    words = f"keep it; the cited decision is not on record: {L2}; and more"
    citation = f'owner ruling "{words}" ({U})'
    open_reason = "waits for the owner"
    ruled = {
        **X,
        "outcome": "ruling",
        "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": words}},
        "reason": f"{citation}; {open_reason}",
    }
    demoted = the_finding(rr.build_record(account([], [ruled]), readers(doc=None)))
    assert demoted["outcome"] == "left-for-owner"
    doc = dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))
    restored = the_finding(rr.build_record(account([], [demoted]), readers(doc=doc)))
    assert restored["outcome"] == "ruling"
    assert restored["reason"] == f"{citation}; {open_reason}"
