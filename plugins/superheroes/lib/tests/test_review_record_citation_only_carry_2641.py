import review_record as rr
import review_record_session as rs
from test_review_record_owner_ruling import U, W, X, account, readers, the_finding


def test_recovered_carried_ruling_keeps_its_citation_once():
    # Axis: carrying a citation-only reason adds a marker and recovery preserves both once.
    citation = f'owner ruling "{W}" ({U})'
    ruled = {**X, "outcome": "ruling", "reason": citation,
             "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": W}}}
    demoted = the_finding(rr.build_record(account([], [ruled]), readers(doc=None)))
    assert demoted["outcome"] == "left-for-owner"
    later = account([], [])
    later["sessionId"] = "s-2"
    later["findings"] = rs._carried(later, [demoted])
    expected = citation + rs.CARRIED
    assert later["findings"][0]["reason"] == expected
    recovered = the_finding(rr.build_record(later, readers()))
    assert recovered["outcome"] == "ruling"
    assert recovered["reason"] == expected
