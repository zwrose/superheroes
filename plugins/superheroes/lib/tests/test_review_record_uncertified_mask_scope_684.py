"""The certificate exemption must not exempt another summary field with identical text."""
import review_record as rr

from test_review_record_uncertified_2395 import _cert, _ended, _write


def test_identical_certificate_text_in_lane_reason_is_still_checked(tmp_path):
    """axis: only the certificate occurrence in Left is exempt; identical forbidden text in Lane is refused before posting."""
    reason = "the kept bug-free check errored at setup"
    session, fake, body = _ended(tmp_path, "cannot-certify", _cert(reason))
    lane_reason = rr.uncertified_line({"terminal": "cannot-certify", "reason": reason})
    out = _write(tmp_path, session, fake, body, laneReason=lane_reason)
    assert out["ok"] is False and out["reason"] == "review-record-forbidden-claim", out
    assert fake.comments == []
