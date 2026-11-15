"""Merged members keep their own outcome when a kept repeat follows an earlier fixed finding to fixed."""
import review_record as rr

from test_review_record_repeats_c1l8 import (
    OTHER_KEY,
    by_id,
    earlier_row,
    mark,
    repeat_row,
    session_record,
)
from test_review_record_session import KEY, WRONG, ledger_row


def test_following_a_kept_representative_to_fixed_leaves_its_merged_member_at_its_own_outcome(tmp_path):
    # axis: a kept representative that moves to fixed does not take its merged member with it (no audit ruled the
    # member's own part fixed), and the member gains no kept stamp of its own.
    left = rr.rfs.LEFT_FOR_OWNER
    member = ledger_row(
        "m.py::member@L1",
        id="m-1",
        title="member",
        file="m.py",
        line=1,
        consequence="c",
        disposition=None,
        mergedInto=OTHER_KEY,
        repeatOf=mark(KEY, id="f-1"),
    )
    rec, _ = session_record(
        tmp_path,
        [
            earlier_row(),
            repeat_row(left, disposition=left, grade=WRONG),
            member,
        ],
    )
    rows = by_id(rec)
    fixed = rr.rfs.OUTCOMES[0]
    assert rows["f-2"]["outcome"] == fixed
    assert rr.REPEAT_KEPT_FIELD not in rows["m-1"]["repeatOf"]
    assert rows["m-1"]["outcome"] == left  # it keeps the outcome it inherited from the kept repeat, not fixed
    assert rows["m-1"]["outcome"] != fixed
    assert rec["leftForOwner"] == ["m-1"]  # the member still waits on the owner
