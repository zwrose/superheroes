"""Check empty-result declarations independently of the investigation floor."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_order_shape_grading_2609 as subject  # noqa: E402
from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: E402,F401 -- autouse fixture keeps views and journals under tmp_path


@pytest.mark.parametrize("shape_id", ["verifiers", "second-test", "second-test-correction"])
@pytest.mark.parametrize("pr_body_staged", [False, True])
def test_empty_result_declaration_with_accepted_investigation(tmp_path, shape_id, pr_body_staged):
    # axis: an empty collection with valid investigation grades as its row declares, independently of vacuity.
    row = next(item for item in subject.RUNNER_ROWS if item["id"] == shape_id)
    answer = copy.deepcopy(subject.FIXTURES[shape_id]["empty"])
    answer["investigated"] = list(subject.INV)
    assert subject._fault(row, answer) is None
    grade = subject._grade(
        tmp_path, answer,
        expected_result_kind=row["expectedResultKind"],
        nothing_to_group=row["nothingToGroup"],
        tool_calls=1,
        pr_body_staged=pr_body_staged,
    )
    assert (grade.get("ok") is True) == row["emptyAnswerValid"], grade
