import finding_outcomes as fo
import review_record as rr
import review_record_session as rs
from test_review_record_owner_ruling import U, W, X, readers
from test_review_record_session import Session, _merged, extras


def test_promotion_removes_a_stale_clause_with_a_merge_marker(tmp_path):
    # Axis: the record promotes a merged member, drops the stale clause, and preserves its merge marker.
    citation = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
    open_reason = "waits for the owner"
    settled = fo.settle(X, ruling={"decidedBy": citation}, sources={}, open_reason=open_reason)
    ledger = _merged({}, {
        "disposition": settled["outcome"],
        "settledReason": settled["reason"],
        "decidedBy": settled["decidedBy"],
    })
    session = Session(tmp_path, dispositionLedger=ledger)
    session.seat("code-reviewer")
    sources = readers()
    account = rs.account_from_session(session.save(), extras(repo="o/r"), sources)
    record = rr.build_record(account, sources)
    member = next(finding for finding in record["findings"] if finding["id"] == "m-1")
    merge_marker = rs.MERGED_INTO_FORMAT.format("rep-1")
    assert member["outcome"] == "ruling"
    assert member["reason"] == f'owner ruling "{W}" ({U}); {open_reason}{merge_marker}'
