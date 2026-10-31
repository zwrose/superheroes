# #1745 WO-B bite-proof: the setup sitting's check (`cloud_check.py`)

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/cloud_check.py` (`judge` and its helpers), detectors in `plugins/superheroes/lib/tests/test_cloud_check.py` (`T`).

**Status.** The implementer ran every proof (B1 to B9): each neutralization is a targeted Edit in `cloud_check.py`, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the full pytest output of each run, unfiltered. Absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret (the fixtures hold stamps, a fixture environment id and a fixture nonce), so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`, output redirected to a scratch file outside the repository and then printed whole.
- **Restore receipt, every element.** The restored line is quoted back from the file after the inverse Edit; `git status --porcelain` after the last restore listed only the two new untracked files of this order (`cloud_check.py`, `test_cloud_check.py`) and no other path.
- **Pinned condition.** The tests pass an explicit `now` (2026-10-10 12:00 UTC) and an explicit `env` mapping with `HOME` under `tmp_path`; the reviewer's answer is a fake that returns a fixed confirmation with a lapse date of 2099-12-31; the record writer and reader are the real ones against the fixture store. The pin makes unobservable: the real wall clock (a real pass lapses on the real calendar, so the lapse comparison is exercised only against the pinned date), the process environment, and the real reviewer tool, which is never run.
- **Fixture condition.** The cloud machine in each test is a second fixture project whose placed files carry the same bytes as the local one, as the setup text writes them. A fixture built independently differs in its registry and meta files and never matches.

## Declared guarded-element set

B1 the nonce binding; B2 the environment match; B3 the version match; B4 the placed-stamp match (condition a); B5 the stamp-file rule (condition b); B6 the repository-calibration match (condition c); B7 the reviewer answer is exactly true and the pass has not lapsed; B8 a refused record write is never reported as passed; B9 a failed check switches the setting off; C1 `start` refuses without a well-formed environment id; C2 `start` never reports started without a receipt for its own session name; C3 the launch names the id the caller gave (WO-C, below).

## Per-element receipts

### B1: the nonce binding (edge 1): `_nonce_is`, used both to pick the report line and to re-check the chosen object. Axis: refusal: a report made for another check is unread

- **Neutralization applied.** `return isinstance(obj, dict) and obj.get("nonce") == nonce` replaced with `return isinstance(obj, dict)`.
- **Node.** `T::test_judge_edge1_a_report_with_another_nonce_is_unread`
- **Where the red landed.** Red landed on the first assertion after the judge call: `action` was `passed`, not `unread`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_judge_edge1_a_report_with_another_nonce_is_unread ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1037/test_judge_edge1_a_report_with0')

    def test_judge_edge1_a_report_with_another_nonce_is_unread(tmp_path):
        local, cloud = _pair(tmp_path)
        other = CC.report(env={cloud_pass.ENVIRONMENT_ENV: ENV_ID}, cwd=cloud.cwd, root=cloud.root,
                          nonce="zzzzzzzz9999", confirm_fn=_confirm())
        # axis: a report answers only the check that was started with its nonce
        result = _judge(local, other)
>       assert result["action"] == "unread" and result["failedParts"] == ["unread"]
E       AssertionError: assert ('passed' == 'unread'
E         
E         - unread
E         + passed)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:378: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge1_a_report_with_another_nonce_is_unread
1 failed in 1.93s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
263:    return isinstance(obj, dict) and obj.get("nonce") == nonce
```

- **Green.**

```
.                                                                        [100%]
1 passed in 2.39s
```

### B2: the environment match (edge 3): `environment_ok` in `_judge_parts`. Axis: equality: the check ran in the environment whose id was given

- **Neutralization applied.** `environment_ok = obj["environment"] == environment` replaced with `environment_ok = True`.
- **Node.** `T::test_judge_edge3_a_wrong_or_missing_environment_fails_on_environment`
- **Where the red landed.** Red landed on `action`: `passed`, not `failed`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_judge_edge3_a_wrong_or_missing_environment_fails_on_environment _____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1039/test_judge_edge3_a_wrong_or_mi0')

    def test_judge_edge3_a_wrong_or_missing_environment_fails_on_environment(tmp_path):
        local, cloud = _pair(tmp_path)
        for bad in (None, OTHER_ENV_ID):
            # axis: the check must have run in the environment whose id the owner gave
            result = _judge(local, _cloud_report(cloud, environment=bad))
>           _failed_on(result, ["environment"], "**The check failed on one part.** The check ran in a "
                       "different environment from the one whose id you gave me, or that environment "
                       "has no pass block in it yet.")

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:405: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
parts = ['environment']
first_paragraph = '**The check failed on one part.** The check ran in a different environment from the one whose id you gave me, or that environment has no pass block in it yet.'

    def _failed_on(result, parts, first_paragraph):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge3_a_wrong_or_missing_environment_fails_on_environment
1 failed in 2.19s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
313:    environment_ok = obj["environment"] == environment
```

- **Green.**

```
.                                                                        [100%]
1 passed in 2.23s
```

### B3: the version match (edge 4): `version_ok` in `_judge_parts`. Axis: equality: the cloud's plugin version is this machine's

- **Neutralization applied.** `version_ok = isinstance(obj["pluginVersion"], str) and obj["pluginVersion"] == local_version` replaced with `version_ok = True`.
- **Node.** `T::test_judge_edge4_a_different_or_missing_cloud_version_fails_on_version`
- **Where the red landed.** Red landed on `action`: `passed`, not `failed`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_judge_edge4_a_different_or_missing_cloud_version_fails_on_version ____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1041/test_judge_edge4_a_different_o0')

    def test_judge_edge4_a_different_or_missing_cloud_version_fails_on_version(tmp_path):
        local, cloud = _pair(tmp_path)
        for bad in ("0.0.1", None, 42):
            # axis: the cloud's plugin must be the version this machine runs
            result = _judge(local, _cloud_report(cloud, pluginVersion=bad))
>           assert result["action"] == "failed" and result["failedParts"] == ["version"]
E           AssertionError: assert ('passed' == 'failed'
E             
E             - failed
E             + passed)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:417: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge4_a_different_or_missing_cloud_version_fails_on_version
1 failed in 1.87s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
315:    version_ok = isinstance(obj["pluginVersion"], str) and obj["pluginVersion"] == local_version
```

- **Green.**

```
.                                                                        [100%]
1 passed in 2.60s
```

### B4: the placed-stamp match (edge 5, first case): condition (a), `placed_ok`. Axis: equality: the cloud's placed calibration stamp is this machine's

- **Neutralization applied.** `placed_ok = obj["placedStamp"] == local_placed` replaced with `placed_ok = True`.
- **Node.** `T::test_judge_edge5_a_different_placed_stamp_fails_on_calibration`
- **Where the red landed.** Red landed on `action`: `passed`, not `failed`. Only `placedStamp` differs in that test, so no other condition could have caught it.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_judge_edge5_a_different_placed_stamp_fails_on_calibration ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1043/test_judge_edge5_a_different_p0')

    def test_judge_edge5_a_different_placed_stamp_fails_on_calibration(tmp_path):
        local, cloud = _pair(tmp_path)
        result = _judge(local, _cloud_report(cloud, placedStamp=OTHER_STAMP))
>       _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
                   "doesn't match this machine's.")

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:426: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
parts = ['calibration']
first_paragraph = "**The check failed on one part.** The cloud's calibration doesn't match this machine's."

    def _failed_on(result, parts, first_paragraph):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge5_a_different_placed_stamp_fails_on_calibration
1 failed in 1.79s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
318:    placed_ok = obj["placedStamp"] == local_placed
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.88s
```

### B5: the stamp-file rule (edge 5, absent-file case): condition (b), `file_ok`. Axis: equality, and absence exactly when nothing was placed

- **Neutralization applied.** `file_ok = obj["stampFile"] is None if local_placed == "none" else obj["stampFile"] == local_placed` replaced with `file_ok = True`.
- **Node.** `T::test_judge_accepts_an_absent_stamp_file_only_when_nothing_was_placed`
- **Where the red landed.** Red landed on the first rejection in the test, the in-repository case where nothing was placed and the report carries a stamp-file value (`failedParts` was `[]`, not `['calibration']`). The same test's later case (files placed, stamp file absent) is guarded by the same line and is reached only after that first assertion, so its own red was not observed separately.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_judge_accepts_an_absent_stamp_file_only_when_nothing_was_placed _____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1045/test_judge_accepts_an_absent_s0')

    def test_judge_accepts_an_absent_stamp_file_only_when_nothing_was_placed(tmp_path):
        local, cloud = _pair(tmp_path / "in", mode_registry.IN_REPO)
        # axis: the stamp file is absent exactly when nothing was placed
        absent = _cloud_report(cloud)
        assert absent["stampFile"] is None
        wrongly_there = _judge(local, _cloud_report(cloud, stampFile=OTHER_STAMP))
>       assert wrongly_there["failedParts"] == ["calibration"]
E       AssertionError: assert [] == ['calibration']
E         
E         Right contains one more item: 'calibration'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:679: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_accepts_an_absent_stamp_file_only_when_nothing_was_placed
1 failed in 1.79s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
320:    file_ok = obj["stampFile"] is None if local_placed == "none" else obj["stampFile"] == local_placed
```

- **Green.**

```
.                                                                        [100%]
1 passed in 3.75s
```

### B6: the repository-calibration match: condition (c), `repo_ok`. Axis: equality: the calibration the repository carries is this machine's

- **Neutralization applied.** `repo_ok = obj["repoStamp"] == local_repo` replaced with `repo_ok = True`.
- **Node.** `T::test_judge_in_repository_project_fails_when_a_core_layer_differs`
- **Where the red landed.** Red landed on `action`: `passed`, not `failed`, with the placed stamps both `none`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_judge_in_repository_project_fails_when_a_core_layer_differs _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1047/test_judge_in_repository_proje0')

    def test_judge_in_repository_project_fails_when_a_core_layer_differs(tmp_path):
        local, cloud = _pair(tmp_path, mode_registry.IN_REPO, cloud_patterns="- other: b.ts:2")
        obj = _cloud_report(cloud)
        assert obj["placedStamp"] == local.stamp == "none" and obj["stampFile"] is None
        assert obj["repoStamp"] != CC.repo_calibration_stamp(local.cwd)
        # axis: the calibration the repository carries must match this machine's
        result = _judge(local, obj)
>       _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
                   "doesn't match this machine's.")

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:666: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
parts = ['calibration']
first_paragraph = "**The check failed on one part.** The cloud's calibration doesn't match this machine's."

    def _failed_on(result, parts, first_paragraph):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_in_repository_project_fails_when_a_core_layer_differs
1 failed in 1.76s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
322:    repo_ok = obj["repoStamp"] == local_repo
```

- **Green.**

```
.                                                                        [100%]
1 passed in 3.28s
```

### B7: the reviewer answer is exactly true and the pass has not lapsed (edge 6): `reviewer` in `_judge_parts`. Axis: refusal: an unanswered reviewer, or a pass whose lapse date is missing, malformed or past

- **Neutralization applied.** `reviewer = confirmation["reviewerAnswered"] is True and _lapses_ok(confirmation.get("passLapses"), today)` replaced with `reviewer = bool(confirmation["reviewerAnswered"])`.
- **Node.** `T::test_judge_edge6_a_reviewer_that_did_not_answer_or_a_lapsed_pass_fails_on_reviewer`
- **Where the red landed.** Red landed on the second case of the loop (answered, `passLapses` None): the reviewer part passed, so the run went on to the record write, which refused the missing date, and `failedParts` was `['record']`, not `['reviewer']`. Disclosure for the exact-`True` half of the element: a truthy non-bool reviewer answer (`"true"`, `1`) never reaches this line, because `_readable` (row 4 of the reading) turns it into `unread` first, so this neutralization cannot show that half red. That half is guarded where it can be reached, by `isinstance(..., bool)` in `_readable`, and the same test's second loop (`truthy` values) asserts `unread` for it; that second loop was not itself neutralized in this record.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_judge_edge6_a_reviewer_that_did_not_answer_or_a_lapsed_pass_fails_on_reviewer _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1049/test_judge_edge6_a_reviewer_th0')

    def test_judge_edge6_a_reviewer_that_did_not_answer_or_a_lapsed_pass_fails_on_reviewer(tmp_path):
        local, cloud = _pair(tmp_path)
        first = "**The check failed on one part.** The reviewer did not answer, so the pass is " \
                "missing or was pasted wrong."
        cases = [
            {"reviewerAnswered": False, "passLapses": FAR},
            {"reviewerAnswered": True, "passLapses": None},
            {"reviewerAnswered": True, "passLapses": "soon"},
            {"reviewerAnswered": True, "passLapses": "2026-13-45"},
            {"reviewerAnswered": True, "passLapses": "2026-10-09"},
            {"reviewerAnswered": True, "passLapses": 20261231},
            {"reviewerAnswered": True},
        ]
        for case in cases:
            confirmation = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reason": None}
            confirmation.update(case)
            # axis: the pass is accepted only when the reviewer answered and the pass has not lapsed
            result = _judge(local, _cloud_report(cloud, confirmation=confirmation))
>           _failed_on(result, ["reviewer"], first)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:503: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'failed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': ['record'], 'recordWritten': False, ...}
parts = ['reviewer']
first_paragraph = '**The check failed on one part.** The reviewer did not answer, so the pass is missing or was pasted wrong.'

    def _failed_on(result, parts, first_paragraph):
        assert result["action"] == "failed", result
>       assert result["failedParts"] == parts, result
E       AssertionError: {'action': 'failed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': ['record'], 'recordWritten': False, ...}
E       assert ['record'] == ['reviewer']
E         
E         At index 0 diff: 'record' != 'reviewer'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:123: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge6_a_reviewer_that_did_not_answer_or_a_lapsed_pass_fails_on_reviewer
1 failed in 2.11s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
    reviewer = confirmation["reviewerAnswered"] is True and _lapses_ok(
        confirmation.get("passLapses"), today)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 5.26s
```

### B8: a refused record write is never reported as passed (edge 8): the `written` assignment in `judge`. Axis: refusal: only `{"action": "written"}` counts as written

- **Neutralization applied.** `written = isinstance(got, dict) and got.get("action") == "written"` replaced with `written = True`.
- **Node.** `T::test_judge_edge8_a_refused_or_raising_record_write_fails_on_record`
- **Where the red landed.** Red landed on `action`: `passed`, not `failed`, for the first fake (a refused write).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_judge_edge8_a_refused_or_raising_record_write_fails_on_record ______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1051/test_judge_edge8_a_refused_or_0')

    def test_judge_edge8_a_refused_or_raising_record_write_fails_on_record(tmp_path):
        local, cloud = _pair(tmp_path)
    
        def raising(*a, **k):
            raise OSError("disk")
    
        for fake in (lambda *a, **k: {"action": "refused", "reason": "store-locked"},
                     lambda *a, **k: {"action": "noop"}, lambda *a, **k: None, raising):
            # axis: a record write that did not report written is never reported as a pass
            result = _judge(local, _ok_report(cloud), record_fn=fake)
>           _failed_on(result, ["record"], "**The check failed on one part.** The check passed, but I "
                       "could not write the setup record on this machine.")

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:541: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
parts = ['record']
first_paragraph = '**The check failed on one part.** The check passed, but I could not write the setup record on this machine.'

    def _failed_on(result, parts, first_paragraph):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge8_a_refused_or_raising_record_write_fails_on_record
1 failed in 1.76s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
400:                written = isinstance(got, dict) and got.get("action") == "written"
```

- **Green.**

```
.                                                                        [100%]
1 passed in 3.25s
```

### B9: a failed check switches the setting off (edge 9): the call in the failed branch of `judge`. Axis: side effect: the cloud-builds setting is off after a failure

- **Neutralization applied.** `was_on, off = _switch_off(cwd, account, root, name, set_fn)` in the failed branch (the one after the line `# axis: a failed check leaves cloud builds off`) replaced with `was_on, off = False, False`.
- **Node.** `T::test_judge_edge9_a_failure_switches_an_on_setting_off`
- **Where the red landed.** Red landed on `settingSwitchedOff` (`False`, not `True`).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_judge_edge9_a_failure_switches_an_on_setting_off _____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1053/test_judge_edge9_a_failure_swi0')

    def test_judge_edge9_a_failure_switches_an_on_setting_off(tmp_path):
        local, cloud = _pair(tmp_path)
        _turn_on(local)
        # axis: a failed check leaves cloud builds off
        result = _judge(local, _cloud_report(cloud, confirmation=_confirm(answered=False)(None)))
        assert result["action"] == "failed" and result["failedParts"] == ["reviewer"]
>       assert result["settingSwitchedOff"] is True and result["recordWritten"] is False
E       assert (False is True)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:565: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge9_a_failure_switches_an_on_setting_off
1 failed in 1.95s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore:

```
374:        was_on, off = _switch_off(cwd, account, root, name, set_fn)
408:        was_on, off = _switch_off(cwd, account, root, name, set_fn)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 2.51s
```

## WO-C (issue 1745): `start`, the check session's launch

Detectors in `plugins/superheroes/lib/tests/test_cloud_check.py` (`T`), guarded code in `plugins/superheroes/lib/cloud_check.py` (`start`). Same method as above: each neutralization is a targeted Edit in `cloud_check.py`, the red is the single named test run alone (a parametrized test is run whole, by its name), the restore is the inverse Edit, and the green is the same test. Reds and greens are the full pytest output of each run. No fake spawn function starts a cloud session; the pinned condition is the fixture project, the fixture environment id and the fixture nonce `abcd1234efgh`. Nothing is redacted: no fixture holds a secret.

### C1: `start` refuses without a well-formed environment id (edge 1): the grammar check at the top of `start`. Axis: refusal: nothing is spawned unless the id fully matches the grammar

- **Neutralization applied.** `if not _environment_ok(environment):` (in `start`) replaced with `if environment is not None and not _environment_ok(environment):`.
- **Node.** `T::test_start_refuses_without_an_environment_id`
- **Where the red landed.** Red landed on the `None` case: `reason` was `check-launch-refused` (the argv builder's own refusal caught it one step later), not `check-environment-invalid`. The other nine cases (empty, malformed, non-string) still passed, because the grammar check was only skipped for `None`; that is the neutralization's scope.
- **Red:**

```
F.........                                                               [100%]
=================================== FAILURES ===================================
______________ test_start_refuses_without_an_environment_id[None] ______________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1063/test_start_refuses_without_an_0')
bad = None

    @pytest.mark.parametrize("bad", [None, "", "env_", "env-01ABC", "env_01 ABC", "xenv_01ABC",
                                     "env_01ABC\n", 42, ["env_01ABC"], b"env_01ABC"])
    def test_start_refuses_without_an_environment_id(tmp_path, bad):
        local = _build(tmp_path)
        spawner = Spawner()
        result = _start(local, spawner, environment=bad)
>       assert result["action"] == "refused" and result["reason"] == "check-environment-invalid"
E       AssertionError: assert ('refused' == 'refused'
E         
E           refused and 'check-launch-refused' == 'check-environment-invalid'
E         
E         - check-environment-invalid
E         + check-launch-refused)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:931: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_refuses_without_an_environment_id[None]
1 failed, 9 passed in 7.70s
```

- **Restore.** The inverse Edit put the line back; quoted from `cloud_check.py` after the restore (the first match, line 271, is `report`'s own check, untouched):

```
271:    if not _environment_ok(environment):
499:    if not _environment_ok(environment):
```

- **Green.**

```
..........                                                               [100%]
10 passed in 9.74s
```

### C2: `start` never reports started without a receipt (edge 4): the `got is None` branch. Axis: refusal: a session is started only on a receipt for this launch's own session name

- **Neutralization applied.** `if got is None:` (before the `check-session-unconfirmed` refusal) replaced with the two lines `got = got or (None, None)` and `if False:`, so a missing receipt falls through to `started`.
- **Node.** `T::test_start_never_reports_started_without_a_receipt`
- **Where the red landed.** All three no-receipt cases went red on `action`: `started`, not `refused` (empty output; a receipt for another session name; a timed-out launch that printed none).
- **Red:**

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
__________ test_start_never_reports_started_without_a_receipt[-False] __________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1065/test_start_never_reports_start0')
output = '', timed_out = False

    @pytest.mark.parametrize("output,timed_out", [
        ("", False),
        (_receipt("cloud-check-zzzzzzzz"), False),
        ("Starting...\n", True),
    ])
    def test_start_never_reports_started_without_a_receipt(tmp_path, output, timed_out):
        local = _build(tmp_path)
        spawner = Spawner(output=output, timed_out=timed_out)
        result = _start(local, spawner)
>       assert result["action"] == "refused" and result["reason"] == "check-session-unconfirmed"
E       AssertionError: assert ('started' == 'refused'
E         
E         - refused
E         + started)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:982: AssertionError
_ test_start_never_reports_started_without_a_receipt[Created cloud session: cloud-check-zzzzzzzz\nView: https://claude.ai/code/session_01ABCdef?from=cli\nResume with: claude --teleport session_01ABCdef\n-False] _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1065/test_start_never_reports_start1')
output = 'Created cloud session: cloud-check-zzzzzzzz\nView: https://claude.ai/code/session_01ABCdef?from=cli\nResume with: claude --teleport session_01ABCdef\n'
timed_out = False

    @pytest.mark.parametrize("output,timed_out", [
        ("", False),
        (_receipt("cloud-check-zzzzzzzz"), False),
        ("Starting...\n", True),
    ])
    def test_start_never_reports_started_without_a_receipt(tmp_path, output, timed_out):
        local = _build(tmp_path)
        spawner = Spawner(output=output, timed_out=timed_out)
        result = _start(local, spawner)
>       assert result["action"] == "refused" and result["reason"] == "check-session-unconfirmed"
E       AssertionError: assert ('started' == 'refused'
E         
E         - refused
E         + started)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:982: AssertionError
____ test_start_never_reports_started_without_a_receipt[Starting...\n-True] ____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1065/test_start_never_reports_start2')
output = 'Starting...\n', timed_out = True

    @pytest.mark.parametrize("output,timed_out", [
        ("", False),
        (_receipt("cloud-check-zzzzzzzz"), False),
        ("Starting...\n", True),
    ])
    def test_start_never_reports_started_without_a_receipt(tmp_path, output, timed_out):
        local = _build(tmp_path)
        spawner = Spawner(output=output, timed_out=timed_out)
        result = _start(local, spawner)
>       assert result["action"] == "refused" and result["reason"] == "check-session-unconfirmed"
E       AssertionError: assert ('started' == 'refused'
E         
E         - refused
E         + started)

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:982: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_never_reports_started_without_a_receipt[-False]
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_never_reports_started_without_a_receipt[Created cloud session: cloud-check-zzzzzzzz\nView: https://claude.ai/code/session_01ABCdef?from=cli\nResume with: claude --teleport session_01ABCdef\n-False]
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_never_reports_started_without_a_receipt[Starting...\n-True]
3 failed in 2.90s
```

- **Restore.** The inverse Edit put the lines back; quoted from `cloud_check.py` after the restore:

```
535-    if got is None:
536:        return _refusal("check-session-unconfirmed", _UNCONFIRMED.format(name=name),
```

- **Green.**

```
...                                                                      [100%]
3 passed in 3.95s
```

### C3: the launch names the id the caller gave (the invariant): the `environment` argument of the argv builder call in `start`. Axis: equality: the id spawned is the id given

- **Neutralization applied.** In the `claude_cloud_builder_argv` call in `start`, the argument `environment` replaced with the fixed other id `"env_FixedOther1"`.
- **Node.** `T::test_start_names_the_environment_in_the_launch`
- **Where the red landed.** Red landed on the argv equality: the settings argument at index 4 carried `env_FixedOther1`, not `env_01ABCdef`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_start_names_the_environment_in_the_launch ________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1068/test_start_names_the_environme0')

    def test_start_names_the_environment_in_the_launch(tmp_path):
        local = _build(tmp_path)
        spawner = Spawner()
        result = _start(local, spawner)
        assert result["action"] == "started" and len(spawner.calls) == 1
        argv = spawner.calls[0]["argv"]
        cell = model_registry.resolve_dispatch("mechanical", "claude", None)
>       assert argv == engine_adapter.claude_cloud_builder_argv(
            cell["dispatch_token"], cell["effort"], _prompt(spawner), ENV_ID,
            "cloud-check-" + NONCE[:8])["argv"]
E       assert ['claude', '-...--model', ...] == ['claude', '-...--model', ...]
E         
E         At index 4 diff: '{"remote":{"defaultEnvironmentId":"env_FixedOther1"}}' != '{"remote":{"defaultEnvironmentId":"env_01ABCdef"}}'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1745-035dde805e265dbb/plugins/superheroes/lib/tests/test_cloud_check.py:917: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_names_the_environment_in_the_launch
1 failed in 1.08s
```

- **Restore.** The inverse Edit put the argument back; quoted from `cloud_check.py` after the restore:

```
519:        cell["dispatch_token"], cell["effort"], _check_prompt(nonce, number), environment, name)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 0.94s
```
