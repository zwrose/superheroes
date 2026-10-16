# wo_g_1795_head-moved — a head read and found moved makes the record not-reviewed

Declared guarded-element set (from the work order): **N1** the moved-head not-reviewed line in `_lane_lines`. The
element was neutralized once, the single detector node run alone, restored by the inverse edit, and the node re-run
green. Redaction: the worktree's absolute path and the pytest tmp directory are as printed by pytest (a local
temp path); nothing else was secret.

## N1 — the `headMoved` branch of `_lane_lines`

**Guarded element:** `plugins/superheroes/lib/review_record.py` `_lane_lines`, the `if basis.get("headMoved"):` branch.
Axis: a record whose PR head was read and found to differ from the recorded final commit reads `not-reviewed` and
says so in fixed prose (status and `whatIsMissing`), never `reviewed`.

**Detector:** `test_review_record.py::test_a_head_that_moves_between_the_meta_read_and_the_files_read_gives_the_unavailable_basis`
(unedited; the head-moving readers return `HEAD`, then a different head, on the second `pr_meta` read).

**Neutralization:** `    if basis.get("headMoved"):` → `    if False and basis.get("headMoved"):` (the branch can never
be taken, so the moved-head line is never added).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_head_that_moves_between_the_meta_read_and_the_files_read_gives_the_unavailable_basis _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1558/test_a_head_that_moves_between0')

    def test_a_head_that_moves_between_the_meta_read_and_the_files_read_gives_the_unavailable_basis(tmp_path):
        # axis: the changed-file evidence bound to the recorded commit; files of a newer head judged against the earlier one
        repo = risk_repo(tmp_path)
        rec = rr.build_record(account(repoRoot=repo), _head_moving_readers([HEAD, "f" * 40]))
        basis = rec["laneBasis"]
        assert basis["source"] == "unavailable" and basis["floor"] == "full"
        assert basis["why"][0] == "risk-unclear-no-paths: the PR head moved while its changed files were read"
        assert rec["finalCommit"]["sha"] == HEAD
        assert basis["headMoved"] is True
>       assert rec["status"] == "not-reviewed"
E       AssertionError: assert 'reviewed' == 'not-reviewed'
E         
E         - not-reviewed
E         ? ----
E         + reviewed

plugins/superheroes/lib/tests/test_review_record.py:1725: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_head_that_moves_between_the_meta_read_and_the_files_read_gives_the_unavailable_basis
1 failed in 4.58s
```
The red is on the claimed axis: the status stays `reviewed` with the branch dead, while the lane-basis assertions above it
(source, floor, reason, `headMoved`) pass.

**Restore:** inverse edit, `    if False and basis.get("headMoved"):` → `    if basis.get("headMoved"):`.

**Restore receipt** (restored line, quoted from `review_record.py:530`):
```
    if basis.get("headMoved"):
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 5.32s
```
