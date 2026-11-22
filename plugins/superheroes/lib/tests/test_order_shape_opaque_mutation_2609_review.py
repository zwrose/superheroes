"""An opaque payload-mutating helper must not disappear from the census."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_order_shape_grading_2609 as subject  # noqa: E402


def test_census_refuses_conditional_opaque_payload_mutation():
    # axis: a helper receiving the payload and adding an undeclared key causes a loud census refusal.
    source = subject._BRANCH.format(
        write='payload = {"a": 1}\n        if state.get("new_variant"):\n            extend_payload(payload)'
    )
    helpers = {
        "extend_payload": 'def extend_payload(payload):\n    payload["undeclared"] = True\n'
    }
    with pytest.raises(subject.UnreadableCensus):
        subject._census(source, lambda name: name, lambda name: helpers[name])
