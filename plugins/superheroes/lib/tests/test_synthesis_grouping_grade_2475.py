"""Issue 2475: a non-empty synthesis grouping is not graded vacuous in a PR-body run.

Every case drives the real grader `ED._grade_review_attempt(run_dir, state, 1)` over a real opened
review run (`_grade_state_with_view_meta` opens it with `_manual_open_review_run`, whose expected
result kind is unpinned, so any of the four result kinds reaches the grader). "PR body staged" means
`viewMeta` carries `prBodyPath` and the `run-opened` record carries `prBodySourcePath`.

Guarded elements (one test function each):
  G1 non-empty grouping + PR body staged + no `investigated` -> ok (and ok without a staged PR body)
  G2 non-empty findings + PR body staged + no `investigated` -> vacuous forfeit
  G3 non-empty verdicts + PR body staged + no `investigated` -> vacuous forfeit
  G4 ruling + PR body staged + no `investigated` -> vacuous forfeit
  G5 empty grouping (None and []), staged or not, no `investigated` -> vacuous forfeit
"""
import json
import os
import time

import pytest

from bite_support import _stamp_ended_from_native_result
from test_engine_dispatch import (
    ED,
    _SV_MOD,
    _VALID_FINDINGS_STDOUT,
    _VALID_RULING_STDOUT,
    _VALID_VERDICTS_STDOUT,
    _grade_state_with_view_meta,
    _sync_native_review_result_from_stdout,
)
from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: F401  autouse: keeps views and journals under tmp_path


def _grade(tmp_path, payload, *, pr_body_staged, run_name="run"):
    """Open a real review run, stage `payload` as attempt 1's result, grade it with the real grader."""
    view_meta = (
        {"prBodyPath": _SV_MOD.PR_BODY_FILE_NAME, "headSha": "abc"} if pr_body_staged else None
    )
    run_dir, _ = _grade_state_with_view_meta(tmp_path, view_meta, run_name=run_name)
    stdout = json.dumps(payload)
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(stdout)
    _sync_native_review_result_from_stdout(run_dir, stdout)
    ended = _stamp_ended_from_native_result(run_dir, {
        "exit": 0, "timedOut": False, "signal": None,
        "refusal": None, "at": time.time(), "wallSeconds": 1.0, "stdoutBytes": len(stdout),
    })
    records, _ = ED._journal_read(run_dir)
    for rec in records:
        if rec.get("kind") == "run-opened" and pr_body_staged:
            rec["prBodySourcePath"] = os.path.join(str(tmp_path), "session", "pr-body.md")
    records = [
        rec for rec in records
        if not (rec.get("kind") == "attempt-ended" and rec.get("attempt") == 1)
    ]
    records.append({"kind": "attempt-ended", "attempt": 1, **ended})
    with open(ED._journal_path(run_dir), "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    return ED._grade_review_attempt(run_dir, state, 1)


def test_g1_nonempty_grouping_pr_body_staged_no_investigated_is_ok(tmp_path):
    # axis: result kind at the PR-body vacuous forfeit — a non-empty grouping is graded ok
    payload = {"grouping": [{"member_ids": ["f1", "f2"], "repeatOf": None}]}
    staged = _grade(tmp_path, payload, pr_body_staged=True, run_name="staged")
    assert staged.get("ok") is True
    assert staged.get("resultKind") == "grouping"
    assert staged["grouping"][0]["member_ids"] == ["f1", "f2"]
    assert "forfeit" not in staged
    assert "investigated" not in staged
    unstaged = _grade(tmp_path, payload, pr_body_staged=False, run_name="unstaged")
    assert unstaged.get("ok") is True
    assert unstaged.get("resultKind") == "grouping"
    assert unstaged["grouping"][0]["member_ids"] == ["f1", "f2"]
    assert "forfeit" not in unstaged


def test_g2_nonempty_findings_pr_body_staged_no_investigated_is_vacuous(tmp_path):
    # axis: result kind at the PR-body vacuous forfeit — findings are not exempt
    grade = _grade(tmp_path, json.loads(_VALID_FINDINGS_STDOUT), pr_body_staged=True)
    assert grade.get("forfeit") is True
    assert grade.get("reason") == ED.engine_adapter.REVIEW_FORFEIT_VACUOUS


def test_g3_nonempty_verdicts_pr_body_staged_no_investigated_is_vacuous(tmp_path):
    # axis: result kind at the PR-body vacuous forfeit — verdicts are not exempt
    grade = _grade(tmp_path, json.loads(_VALID_VERDICTS_STDOUT), pr_body_staged=True)
    assert grade.get("forfeit") is True
    assert grade.get("reason") == ED.engine_adapter.REVIEW_FORFEIT_VACUOUS


def test_g4_ruling_pr_body_staged_no_investigated_is_vacuous(tmp_path):
    # axis: result kind at the PR-body vacuous forfeit — a ruling is not exempt
    grade = _grade(tmp_path, json.loads(_VALID_RULING_STDOUT), pr_body_staged=True)
    assert grade.get("forfeit") is True
    assert grade.get("reason") == ED.engine_adapter.REVIEW_FORFEIT_VACUOUS


@pytest.mark.parametrize(
    "grouping, pr_body_staged",
    [
        pytest.param(None, True, id="none-pr-body-staged"),
        pytest.param(None, False, id="none-pr-body-not-staged"),
        pytest.param([], True, id="empty-list-pr-body-staged"),
        pytest.param([], False, id="empty-list-pr-body-not-staged"),
    ],
)
def test_g5_empty_grouping_no_investigated_is_vacuous(tmp_path, grouping, pr_body_staged):
    # axis: payload emptiness at the empty-payload forfeit — an empty grouping stays vacuous
    grade = _grade(tmp_path, {"grouping": grouping}, pr_body_staged=pr_body_staged)
    assert grade.get("forfeit") is True
    assert grade.get("reason") == ED.engine_adapter.REVIEW_FORFEIT_VACUOUS
