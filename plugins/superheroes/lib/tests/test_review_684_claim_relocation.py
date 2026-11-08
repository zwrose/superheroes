"""#684: equal claims in different acceptance items cannot cancel.

Bites on: flattening claim comparisons across acceptance spans.
Axis: check_leftovers refuses leftover-not-accepted when one item loses a
fixed-above claim while another manufactures the identical claim. Uses the
real scanner and record reader; the owned membership seam prevents I/O.
"""
import pytest

import vet_slot as vs
from test_vet_slot_leftovers_2280 import F1, PR, REPO, body, record_comment


def test_identical_claims_in_different_items_cannot_cancel():
    source = body(
        "- Example syntax: fixed-<!---->above #99 abcdef0\n"
        "- f-1 the retry loop never backs off <b>fixed-above #99 abcdef0\n"
    )

    def unexpected_membership_read(_pr, _repo):
        pytest.fail("changed claims must be refused before stack membership is read")

    with pytest.raises(vs._Refusal) as caught:
        vs.check_leftovers(
            PR,
            REPO,
            source,
            [record_comment([F1])],
            membership_reader=unexpected_membership_read,
        )

    assert caught.value.reason == "leftover-not-accepted"
