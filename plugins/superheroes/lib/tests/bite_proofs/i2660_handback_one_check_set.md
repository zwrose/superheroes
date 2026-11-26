# Bite-proof record: i2660_handback_one_check_set (#2660) every `vet_slot.py handback` path with a PR runs the same checks, through one function

Detector under proof: `plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py` (unedited between each red and its green).
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`_handback_checks`, `run_verb`, `_run_verb`). Base `7d10cb4e`.
Each neutralization was one targeted edit made with the Edit tool (the target text occurring exactly once, which the Edit tool enforces) and undone by the inverse Edit. No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command shape (run from the worktree root; node ids exact, listed per element):
`scripts/pinned-python -B -X pycache_prefix=/tmp/i2660-pyc -m pytest <node ids> -q -p no:cacheprovider`
Node ids below are written as `T::name`, where `T` is `plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py`.

Guarded-element set (5): G1 combined-form routing through `_handback_checks`; G2 the `check_caught_up` call; G3 the `check_leftovers` call; G4 the `check_calibration_disclosures` call; G5 the `notRun` attach in `run_verb`. No grouping: five elements, five neutralizations, five reds.

Disclosures: captures are the runner's output. The temp directory prefix `/tmp/claude-0/pytest-of-root/` is kept as printed; the worktree path prefix `/home/user/superheroes/.claude/worktrees/b2660/` is shortened to nothing (paths shown relative to the worktree root); the interpreter launcher's `UV_NATIVE_TLS` warning line is dropped. Nothing else was redacted; nothing needed redaction.

## G1: the combined form routes through `_handback_checks`

- **Guarded element / axis:** `vet_slot.py`, `_run_verb`, `return _handback_checks(source, payload, pr, repo, run)`. Axis: `handback --pr --repo --body-file` runs caught-up, leftovers and calibration on the file's body, exactly as the `--pr` path does.
- **Neutralization:** `return _handback_checks(source, payload, pr, repo, run)` became `return _handback_file(body_file) if body_file is not None else _handback_checks(source, payload, pr, repo, run)` (the combined form falls back to the file-only checks).
- **Nodes:** `T::test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path`, `T::test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string`, `T::test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted`, `T::test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses`, `T::test_row5_leftovers_refuse_before_calibration_on_both_paths`.
- **Raw red:**

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_ test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path _

capsys = <_pytest.capture.CaptureFixture object at 0x7f24e4968470>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_row1_a_stacked_head_behin0')

    def test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), fake_c, _ = _both(capsys, tmp_path, HEALTHY, HEALTHY, HEALTHY, LEAVES_F1,
                                                        base_ref="lower", behind=2)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 1) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:120: AssertionError
_ test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string _

capsys = <_pytest.capture.CaptureFixture object at 0x7f24e4632f00>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_row2_caught_up_runs_befor0')

    def test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, HEALTHY, 5, 5, LEAVES_F1, base_ref="lower",
                                                   behind=2)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 1) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:131: AssertionError
_ test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted _

capsys = <_pytest.capture.CaptureFixture object at 0x7f24e4969f70>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_row3_a_file_body_that_lea0')

    def test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, FAILS_LEFTOVER, HEALTHY, FAILS_LEFTOVER, LEAVES_F1)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 1) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:140: AssertionError
_____ test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses _____

capsys = <_pytest.capture.CaptureFixture object at 0x7f24e4630da0>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_row4_a_file_body_with_a_c0')

    def test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, CAL_CONTRADICTED, C.body(None), CAL_CONTRADICTED,
                                                   CAL_RECORD)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 1) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:150: AssertionError
_________ test_row5_leftovers_refuse_before_calibration_on_both_paths __________

capsys = <_pytest.capture.CaptureFixture object at 0x7f24e4651220>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_row5_leftovers_refuse_bef0')

    def test_row5_leftovers_refuse_before_calibration_on_both_paths(capsys, tmp_path):
        both_failing = C.bullet(C.mark(C.CODE1, "core.md"))  # accepts the bullet's text, never names f-1
        record = [C.record_comment([C.row(C.CODE1), C.row(C.SEC1)], findings=[L.F1], left=["f-1"])]
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, both_failing, C.body(None), both_failing, record)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 1) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:161: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row5_leftovers_refuse_before_calibration_on_both_paths
5 failed in 0.52s
```

- **Restore:** inverse Edit, back to `return _handback_checks(source, payload, pr, repo, run)`.
- **Restore receipt:** `vet_slot.py:1174` reads `        return _handback_checks(source, payload, pr, repo, run)`.
- **Raw green** (same nodes):

```
.....                                                                    [100%]
5 passed in 0.53s
```

## G2: `check_caught_up` runs before any body is read

- **Guarded element / axis:** `vet_slot.py`, `_handback_checks`, `check_caught_up(run, repo, payload)`. Axis: a stacked head behind its lower branch refuses `stack-not-caught-up` before the body is read, on the combined form as on the `--pr` path.
- **Neutralization:** `check_caught_up(run, repo, payload)` became `pass  # check_caught_up(run, repo, payload)`.
- **Nodes:** `T::test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path`, `T::test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string`.
- **Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path _

capsys = <_pytest.capture.CaptureFixture object at 0x7fc572c65fa0>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_row1_a_stacked_head_behin0')

    def test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), fake_c, _ = _both(capsys, tmp_path, HEALTHY, HEALTHY, HEALTHY, LEAVES_F1,
                                                        base_ref="lower", behind=2)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 0) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:120: AssertionError
_ test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string _

capsys = <_pytest.capture.CaptureFixture object at 0x7fc572c674d0>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_row2_caught_up_runs_befor0')

    def test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, HEALTHY, 5, 5, LEAVES_F1, base_ref="lower",
                                                   behind=2)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 1) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:131: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string
2 failed in 0.79s
```

- **Restore:** inverse Edit, back to `check_caught_up(run, repo, payload)`.
- **Restore receipt:** `vet_slot.py:753` reads `        check_caught_up(run, repo, payload)`.
- **Raw green** (same nodes):

```
..                                                                       [100%]
2 passed in 0.43s
```

## G3: `check_leftovers` runs on the combined form's file body

- **Guarded element / axis:** `vet_slot.py`, `_handback_checks`, `check_leftovers(pr, repo, body, comments, run)`. Axis: a finding the latest record leaves for the owner that the checked body does not name refuses `leftover-not-accepted`, and it refuses before the calibration check.
- **Neutralization:** `check_leftovers(pr, repo, body, comments, run)` became `# check_leftovers(pr, repo, body, comments, run)`.
- **Nodes:** `T::test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted`, `T::test_row5_leftovers_refuse_before_calibration_on_both_paths`.
- **Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted _

capsys = <_pytest.capture.CaptureFixture object at 0x7f107d5cb290>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_row3_a_file_body_that_lea0')

    def test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, FAILS_LEFTOVER, HEALTHY, FAILS_LEFTOVER, LEAVES_F1)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 0) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:140: AssertionError
_________ test_row5_leftovers_refuse_before_calibration_on_both_paths __________

capsys = <_pytest.capture.CaptureFixture object at 0x7f107d5cbec0>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_row5_leftovers_refuse_bef0')

    def test_row5_leftovers_refuse_before_calibration_on_both_paths(capsys, tmp_path):
        both_failing = C.bullet(C.mark(C.CODE1, "core.md"))  # accepts the bullet's text, never names f-1
        record = [C.record_comment([C.row(C.CODE1), C.row(C.SEC1)], findings=[L.F1], left=["f-1"])]
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, both_failing, C.body(None), both_failing, record)
        assert (rc_c, rc_p) == (1, 1)
>       assert out_c["reason"] == "leftover-not-accepted"
E       AssertionError: assert 'calibration-...-contradicted' == 'leftover-not-accepted'
E         
E         - leftover-not-accepted
E         + calibration-disclosure-contradicted

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:162: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row5_leftovers_refuse_before_calibration_on_both_paths
2 failed in 0.49s
```

- **Restore:** inverse Edit, back to `check_leftovers(pr, repo, body, comments, run)`.
- **Restore receipt:** `vet_slot.py:760` reads `        check_leftovers(pr, repo, body, comments, run)`.
- **Raw green** (same nodes):

```
..                                                                       [100%]
2 passed in 0.45s
```

## G4: `check_calibration_disclosures` runs on the combined form's file body

- **Guarded element / axis:** `vet_slot.py`, `_handback_checks`, `check_calibration_disclosures(pr, repo, body, comments)`. Axis: a calibration marker in the checked body that the latest record contradicts refuses `calibration-disclosure-contradicted`, on the combined form as on the `--pr` path.
- **Neutralization:** `check_calibration_disclosures(pr, repo, body, comments)` became `# check_calibration_disclosures(pr, repo, body, comments)`.
- **Node:** `T::test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses _____

capsys = <_pytest.capture.CaptureFixture object at 0x7fcf23046360>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_row4_a_file_body_with_a_c0')

    def test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses(capsys, tmp_path):
        (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, CAL_CONTRADICTED, C.body(None), CAL_CONTRADICTED,
                                                   CAL_RECORD)
>       assert (rc_c, rc_p) == (1, 1)
E       assert (0, 0) == (1, 1)
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:150: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses
1 failed in 0.44s
```

- **Restore:** inverse Edit, back to `check_calibration_disclosures(pr, repo, body, comments)`.
- **Restore receipt:** `vet_slot.py:762` reads `        check_calibration_disclosures(pr, repo, body, comments)`.
- **Raw green** (same node):

```
.                                                                        [100%]
1 passed in 0.44s
```

## G5: a passing file-only handback names the three checks it did not run

- **Guarded element / axis:** `vet_slot.py`, `run_verb`, `result["notRun"] = list(HANDBACK_PR_CHECKS)`. Axis: `handback --body-file` alone, when it passes, carries `notRun` with `caught-up`, `leftovers`, `calibration-disclosures` in that order.
- **Neutralization:** `result["notRun"] = list(HANDBACK_PR_CHECKS)` became `pass  # result["notRun"] = list(HANDBACK_PR_CHECKS)`.
- **Node:** `T::test_row8_file_only_pass_says_which_three_checks_it_did_not_run`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_row8_file_only_pass_says_which_three_checks_it_did_not_run ________

capsys = <_pytest.capture.CaptureFixture object at 0x7f4f2abc5010>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_row8_file_only_pass_says_0')

    def test_row8_file_only_pass_says_which_three_checks_it_did_not_run(capsys, tmp_path):
        fake = Gh(HEALTHY)
        rc, out = _go(capsys, ["handback", "--body-file", _file(tmp_path, HEALTHY)], fake)
        assert rc == 0
>       assert out == {"ok": True, "verb": "handback", "followups": [], "notRun": NOT_RUN}
E       AssertionError: assert {'ok': True, ...ollowups': []} == {'ok': True, ...disclosures']}
E         
E         Omitting 3 identical items, use -vv to show
E         Right contains 1 more item:
E         {'notRun': ['caught-up', 'leftovers', 'calibration-disclosures']}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py:190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_handback_body_file_parity_2660.py::test_row8_file_only_pass_says_which_three_checks_it_did_not_run
1 failed in 0.51s
```

- **Restore:** inverse Edit, back to `result["notRun"] = list(HANDBACK_PR_CHECKS)`.
- **Restore receipt:** `vet_slot.py:1153` reads `                result["notRun"] = list(HANDBACK_PR_CHECKS)`.
- **Raw green** (same node):

```
.                                                                        [100%]
1 passed in 0.42s
```
