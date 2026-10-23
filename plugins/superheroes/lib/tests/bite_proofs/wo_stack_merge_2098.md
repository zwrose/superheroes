# WO-B (#2098) bite-proof — `stack_merge.py` guards

Per-guard bite proof for `plugins/superheroes/lib/stack_merge.py`: each `# axis:` clause is neutralized in source by a targeted edit, the proving test(s) must go red alone (`-k`), the clause is restored by the inverse edit, and the whole file goes green again.

**Register:** 28 guards — one per `# axis:` line in the file; the single place that decides `merged` is S1. Line numbers are those of the restored file.

**Provenance:** claude (Claude Sonnet 5.5), re-dispatch attempt 2.

**Commands.** *Red* (one per element, `<expr>` named in each entry):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2098 -m pytest plugins/superheroes/lib/tests/test_stack_merge.py -q -p no:cacheprovider --tb=no -k "<expr>"
```

*Green* (after each restore, the whole file):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2098 -m pytest plugins/superheroes/lib/tests/test_stack_merge.py -q -p no:cacheprovider --tb=no
```

`--tb=no` only suppresses pytest's traceback bodies; it filters nothing. Every capture below omits the one leading line `warning: The UV_NATIVE_TLS environment variable is deprecated ...`, which is uv's own notice, and the progress-dot line is kept. The sandbox accepted the `-X pycache_prefix` flag.

Two tests were added to the test file during this proof because the first red run showed a clause was not proven by the tests then present (disclosed under E8 and P2). The green counts below are 125 passed before the first addition, 127 after it, 128 after the second.

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| V1 | stack_merge.py:121 | repo is not an owner/name string | `test_m13_bad_repo` | proven |
| V2 | stack_merge.py:125 | top is not a positive int (bool is not an int) | `test_m13_bad_top` | proven |
| V3 | stack_merge.py:129 | sha is not exactly 40 hex characters | `test_m13_bad_sha` | proven |
| V4 | stack_merge.py:133 | uuid (poll) is not 1-64 letters, digits, hyphens | `test_m13_bad_uuid_for_poll` | proven |
| V5 | stack_merge.py:137 | poll_timeout is not a positive finite number | `test_m13_bad_poll_timeout` | proven |
| V6 | stack_merge.py:141 | poll_interval is not a positive finite number | `test_m13_bad_poll_interval` | proven |
| V7 | stack_merge.py:145 | timeout is not a positive finite number | `test_m13_bad_timeout` | proven |
| R1 | stack_merge.py:191 | response body is not JSON or not an object | `test_m11_unreadable_put_body_is_never_merged[not-json/empty/array]` | proven |
| R2 | stack_merge.py:197 | status is not one of the four | `test_m11_unknown_status_is_refused_at_the_read_and_not_echoed`, `test_m12_unreadable_poll_body_then_merged_is_ok` | proven |
| R3 | stack_merge.py:203 | details is missing or not an object | `test_m11_unreadable_put_body_is_never_merged[details-*]`, `test_m11_details_missing_is_unreadable_even_for_merged` | proven |
| R4 | stack_merge.py:211 | expected_head_sha present but not a string | `test_m11_unreadable_put_body_is_never_merged[expected-*]` | proven |
| R5 | stack_merge.py:216 | expected_head_sha differs from the pin | `test_m9_*`, `test_m10_*` | proven |
| R6 | stack_merge.py:222 | pending response has no usable uuid | `test_m11_unreadable_put_body_is_never_merged[pending-no-uuid/pending-bad-uuid]` | proven |
| R7 | stack_merge.py:226 | pending response has no expected_head_sha | `test_m11_unreadable_put_body_is_never_merged[pending-no-expected]` | proven |
| S1 | stack_merge.py:245 | the single place that decides merged: only status == merged is success | `test_m15_*` | proven |
| S2 | stack_merge.py:251 | status failed is a refusal carrying GitHub's message | `test_m4_*` | proven |
| S3 | stack_merge.py:255 | status enqueued is not merged | `test_m5_*` | proven |
| S4 | stack_merge.py:260 | any status the function does not name is not merged | `test_m15_settle_unnamed_status_is_unreadable_not_merged` | proven |
| P1 | stack_merge.py:278 | a poll call that raises is remembered, polling continues | `test_m12_poll_call_*` | proven |
| P2 | stack_merge.py:282 | a poll GET that exits non-zero is remembered, polling continues | `test_m12_recorded_404_every_poll_is_poll_timeout_with_the_404_text`, `test_m12_poll_get_exiting_nonzero_with_a_merged_body_is_never_merged` | proven |
| P3 | stack_merge.py:289 | a poll body naming a different head ends the loop | `test_m10_poll_with_other_expected_head_ends_the_loop_as_head_mismatch` | proven |
| P4 | stack_merge.py:293 | an unreadable poll body is remembered, polling continues | `test_m12_unreadable_poll_body_*` | proven |
| P5 | stack_merge.py:304 | pending when the poll budget ran out is not merged | `test_m6_*`, `test_m15_no_non_merged_outcome_reads_as_ok_or_merged` | proven |
| G1 | stack_merge.py:322 | gh is not on PATH (merge) | `test_m13_gh_not_on_path_is_gh_unavailable` | proven |
| G2 | stack_merge.py:329 | run raises OSError or TimeoutExpired on the PUT | `test_m13_put_run_raising_is_merge_request_refused` | proven |
| G3 | stack_merge.py:333 | the PUT exits non-zero: refused, an existing request is never adopted or polled | `test_m7_*`, `test_m8_*` | proven |
| G4 | stack_merge.py:364 | gh is not on PATH (poll) | `test_m13_gh_not_on_path_blocks_poll_too` | proven |
| G5 | stack_merge.py:396 | the parse boundary | `test_cli_malformed_is_bad_argument_json_exit_one` | proven |

---

## V1 — repo is not an owner/name string

**neutralization:** `if not isinstance(repo, str) or not _REPO_RE.match(repo):` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_repo`; this one run used `--tb=line`, so the assertion lines also show):
```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/None/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/None/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/5/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/5/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/owner/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/owner/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/owner//pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/owner//pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos//name/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos//name/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/o/n/x/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/o/n/x/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/own er/name/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/own er/name/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
E   AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/o/n\n/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
/home/user/wt-2098-b/plugins/superheroes/lib/tests/test_stack_merge.py:55: AssertionError: unexpected gh argv: ['gh', 'api', '-X', 'PUT', 'repos/o/n\n/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[5]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[owner]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[owner/]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[/name]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[o/n/x]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[own er/name]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_repo[o/n\n]
8 failed, 117 deselected in 0.28s
```

**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _bad_argument("repo must be owner/name")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.50s
```

---

## V2 — top is not a positive int

**neutralization:** `if not _is_int(top) or top < 1:` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_top`):
```
FFFFFF                                                                   [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_top[0]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_top[-1]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_top[True]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_top[5]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_top[5.0]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_top[None]
6 failed, 119 deselected in 0.20s
```

**restored lines:**
```python
    if not _is_int(top) or top < 1:
        return _bad_argument("top must be a positive integer")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.48s
```

---

## V3 — sha is not exactly 40 hex characters

**neutralization:** `if not isinstance(sha, str) or not _SHA40_RE.match(sha):` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_sha`):
```
FFFFFF                                                                   [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_sha[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_sha[0123456789abcdef0123456789abcdef0123456]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_sha[0123456789abcdef0123456789abcdef012345670]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_sha[gggggggggggggggggggggggggggggggggggggggg]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_sha[123]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_sha[0123456789abcdef0123456789abcdef01234567\n]
6 failed, 119 deselected in 0.16s
```

**restored lines:**
```python
    if not isinstance(sha, str) or not _SHA40_RE.match(sha):
        return _bad_argument("sha must be a 40-character hex string")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.58s
```

---

## V4 — uuid (poll) is not 1-64 letters, digits, hyphens

**neutralization:** `if require_uuid and (not isinstance(uuid, str) or not _UUID_RE.match(uuid)):` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_uuid_for_poll`):
```
FFFFFFF                                                                  [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[abc/def]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[../x]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[a b]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_uuid_for_poll[5]
7 failed, 118 deselected in 0.22s
```

**restored lines:**
```python
    if require_uuid and (not isinstance(uuid, str) or not _UUID_RE.match(uuid)):
        return _bad_argument("uuid must be 1-64 letters, digits or hyphens")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.94s
```

---

## V5 — poll_timeout is not a positive finite number

**neutralization:** `if not _is_positive_finite(poll_timeout):` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_poll_timeout`):
```
FFFFFFF                                                                  [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[0]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[-3]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[True]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[5]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[nan]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_timeout[inf]
7 failed, 118 deselected in 0.32s
```

**restored lines:**
```python
    if not _is_positive_finite(poll_timeout):
        return _bad_argument("poll_timeout must be a positive number of seconds")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.47s
```

---

## V6 — poll_interval is not a positive finite number

**neutralization:** `if not _is_positive_finite(poll_interval):` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_poll_interval`):
```
FFFFFFF                                                                  [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[0]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[-3]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[True]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[5]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[nan]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_poll_interval[inf]
7 failed, 118 deselected in 0.22s
```

**restored lines:**
```python
    if not _is_positive_finite(poll_interval):
        return _bad_argument("poll_interval must be a positive number of seconds")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.50s
```

---

## V7 — timeout is not a positive finite number

**neutralization:** `if not _is_positive_finite(timeout):` → `if False:  # bite-proof`

**red** (`-k test_m13_bad_timeout`):
```
FFFFFFF                                                                  [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[0]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[-3]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[True]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[5]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[nan]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_bad_timeout[inf]
7 failed, 118 deselected in 0.25s
```

**restored lines:**
```python
    if not _is_positive_finite(timeout):
        return _bad_argument("timeout must be a positive number of seconds")
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.54s
```

---

## R1 — response body is not JSON or not an object

**neutralization:** `if body is None:` → `if False:  # bite-proof`

**red** (`-k "test_m11_unreadable_put_body_is_never_merged and (not-json or empty or array)"`):
```
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[not-json]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[empty]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[array]
3 failed, 122 deselected in 0.18s
```
(The red is by an `AttributeError` on `None.get`, an exception rather than a wrong-reason result.)

**restored lines:**
```python
    if body is None:
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response is not a JSON object", None)
```
**green:**
```
........................................................................ [ 57%]
.....................................................                    [100%]
125 passed in 0.51s
```

---

## R2 — status is not one of pending, merged, enqueued, failed

**neutralization:** `if not isinstance(status, str) or status not in STATUSES:` → `if False:  # bite-proof`

**first attempt, disclosed:** with only the existing M11 cases (`-k "test_m11_unreadable_put_body_is_never_merged and (unknown-status or status-not-string)"`) the neutralized clause stayed **green**, because `_settle`'s unnamed-status fallback (S4) returns the same `merge-response-unreadable` reason:
```
..                                                                       [100%]
2 passed, 123 deselected in 0.19s
```
The poll-path test already bit (`-k test_m12_unreadable_poll_body_then_merged_is_ok` → `1 failed, 124 deselected in 0.27s`, `FAILED ...::test_m12_unreadable_poll_body_then_merged_is_ok`). I then **added** `test_m11_unknown_status_is_refused_at_the_read_and_not_echoed` (asserts `status` is null and the detail names a known status) so the PUT path bites too.

**red** (`-k "test_m11_unknown_status_is_refused_at_the_read_and_not_echoed or test_m12_unreadable_poll_body_then_merged_is_ok"`):
```
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unknown_status_is_refused_at_the_read_and_not_echoed[done]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unknown_status_is_refused_at_the_read_and_not_echoed[7]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_unreadable_poll_body_then_merged_is_ok
3 failed, 124 deselected in 0.16s
```

**restored lines:**
```python
    if not isinstance(status, str) or status not in STATUSES:
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response status is missing or not a known status", None)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.59s
```

---

## R3 — details is missing or not an object

**neutralization:** `if not isinstance(details, dict):` → `if False:  # bite-proof`

**red** (`-k "test_m11_details_missing_is_unreadable_even_for_merged or (test_m11_unreadable_put_body_is_never_merged and details)"`):
```
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[details-missing]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[details-not-object]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_details_missing_is_unreadable_even_for_merged
3 failed, 124 deselected in 0.22s
```

**restored lines:**
```python
    if not isinstance(details, dict):
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response details is missing or not an object", status)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.56s
```

---

## R4 — expected_head_sha present but not a string

**neutralization:** `if "expected_head_sha" in details and not isinstance(expected, str):` → `if False:  # bite-proof`

**red** (`-k "test_m11_unreadable_put_body_is_never_merged and expected-"`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[expected-not-string]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[expected-null]
2 failed, 125 deselected in 0.19s
```
(`expected-null` is the clean red: a `merged` body with `expected_head_sha: null` is accepted as merged without the clause. `expected-not-string` goes red by an `AttributeError` on `int.lower`.)

**restored lines:**
```python
    if "expected_head_sha" in details and not isinstance(expected, str):
        return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                      "response expected_head_sha is not a string", status)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.54s
```

---

## R5 — expected_head_sha differs from the pinned sha

**neutralization:** `if expected is not None and expected.lower() != pin.lower():` → `if False:  # bite-proof`

**red** (`-k "test_m9 or test_m10"`):
```
FF.F                                                                     [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m9_pending_with_other_expected_head_is_head_mismatch_and_never_polled
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m10_merged_with_other_expected_head_is_head_mismatch
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m10_poll_with_other_expected_head_ends_the_loop_as_head_mismatch
3 failed, 1 passed, 123 deselected in 0.26s
```
(The one pass is `test_m10_expected_head_matches_case_insensitively`, which must pass both ways.)

**restored lines:**
```python
    if expected is not None and expected.lower() != pin.lower():
        return None, (REASON_HEAD_MISMATCH,
                      "GitHub expected head %s but the pin is %s" % (expected, pin), status)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.52s
```

---

## R6 — pending response has no usable uuid

**neutralization:** `if not _valid_uuid(uuid):` (inside `if require_pending_fields and status == STATUS_PENDING:`) → `if False:  # bite-proof`

**red** (`-k "test_m11_unreadable_put_body_is_never_merged and (pending-no-uuid or pending-bad-uuid)"`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[pending-no-uuid]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[pending-bad-uuid]
2 failed, 125 deselected in 0.19s
```

**restored lines:**
```python
        if not _valid_uuid(uuid):
            return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                          "pending response has no usable uuid", status)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.54s
```

---

## R7 — pending response has no expected_head_sha

**neutralization:** `if expected is None:` (inside the same pending block) → `if False:  # bite-proof`

**red** (`-k "test_m11_unreadable_put_body_is_never_merged and pending-no-expected"`):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m11_unreadable_put_body_is_never_merged[pending-no-expected]
1 failed, 126 deselected in 0.21s
```

**restored lines:**
```python
        if expected is None:
            return None, (REASON_MERGE_RESPONSE_UNREADABLE,
                          "pending response has no expected_head_sha", status)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.62s
```

---

## S1 — the single place that decides merged

**neutralization:** `if status == STATUS_MERGED:` → `if True:  # bite-proof` (every status now settles as merged: the failure the census exists to catch)

**red** (`-k test_m15`):
```
FFFFFFFFFFFFF.                                                           [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_no_non_merged_outcome_reads_as_ok_or_merged[pending]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_no_non_merged_outcome_reads_as_ok_or_merged[enqueued]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_no_non_merged_outcome_reads_as_ok_or_merged[failed]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_no_non_merged_outcome_reads_as_ok_or_merged[poll-timeout]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[pending]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[enqueued]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[failed]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[done]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[MERGED]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_reads_only_the_merged_status_as_merged[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_pending_is_not_final
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_unnamed_status_is_unreadable_not_merged
13 failed, 1 passed, 113 deselected in 0.22s
```

**restored lines:**
```python
    if status == STATUS_MERGED:
        return _result(repo, top, sha, merged=True, status=status, uuid=uuid,
                       commit=read["commit"])
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.61s
```

---

## S2 — status failed is a refusal carrying GitHub's message

**neutralization:** `if status == STATUS_FAILED:` → `if False:  # bite-proof`

**red** (`-k test_m4`):
```
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m4_put_failed_is_merge_failed_with_message
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m4_poll_failed_is_merge_failed_with_message
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m4_failed_without_a_message_still_refuses
3 failed, 124 deselected in 0.23s
```

**restored lines:**
```python
    if status == STATUS_FAILED:
        return _result(repo, top, sha, status=status, reason=REASON_MERGE_FAILED,
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.60s
```

---

## S3 — status enqueued is not merged

**neutralization:** `if status == STATUS_ENQUEUED:` → `if False:  # bite-proof`

**red** (`-k test_m5`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m5_put_enqueued_is_not_merged
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m5_poll_enqueued_is_not_merged
2 failed, 125 deselected in 0.18s
```

**restored lines:**
```python
    if status == STATUS_ENQUEUED:
        return _result(repo, top, sha, status=status, reason=REASON_MERGE_ENQUEUED,
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.58s
```

---

## S4 — any status `_settle` does not name is not merged

**neutralization:** the final `return _result(repo, top, sha, status=status, reason=REASON_MERGE_RESPONSE_UNREADABLE, detail="unhandled status", uuid=uuid)` → `return None  # bite-proof` (an unnamed status would read as still pending)

**red** (`-k test_m15_settle_unnamed_status_is_unreadable_not_merged`):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_settle_unnamed_status_is_unreadable_not_merged
1 failed, 126 deselected in 0.22s
```

**restored lines:**
```python
    return _result(repo, top, sha, status=status, reason=REASON_MERGE_RESPONSE_UNREADABLE,
                   detail="unhandled status", uuid=uuid)
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.50s
```

---

## P1 — a poll call that raises is remembered and polling continues

**neutralization:** the except body `last_error = "poll call failed: ..."` + `continue` → `raise  # bite-proof`

**red** (`-k test_m12_poll_call`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_poll_call_that_raises_then_merged_is_ok
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_poll_call_that_always_raises_is_poll_timeout_with_the_error
2 failed, 125 deselected in 0.22s
```

**restored lines:**
```python
            last_error = "poll call failed: %s" % (exc or type(exc).__name__)
            continue
```
**green:**
```
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 0.73s
```

---

## P2 — a poll GET that exits non-zero is remembered and polling continues

**neutralization:** `if proc.returncode != 0:` (poll loop) → `if False:  # bite-proof`

**first attempt, disclosed:** with only the existing test (`-k test_m12_recorded_404`) this was red on the detail text alone (`1 failed, 1 passed, 125 deselected in 0.18s`, `FAILED ...::test_m12_recorded_404_every_poll_is_poll_timeout_with_the_404_text`): a non-zero exit with a *merged-looking* body was not covered. I **added** `test_m12_poll_get_exiting_nonzero_with_a_merged_body_is_never_merged`.

**red** (`-k "test_m12_recorded_404_every or test_m12_poll_get_exiting_nonzero"`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_recorded_404_every_poll_is_poll_timeout_with_the_404_text
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_poll_get_exiting_nonzero_with_a_merged_body_is_never_merged
2 failed, 126 deselected in 0.17s
```

**restored lines:**
```python
        if proc.returncode != 0:
            # axis: a poll GET that exits non-zero is remembered and polling continues
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.53s
```

---

## P3 — a poll body naming a different head ends the loop

**neutralization:** `if reason == REASON_HEAD_MISMATCH:` → `if False:  # bite-proof`

**red** (`-k test_m10_poll_with_other_expected_head`):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m10_poll_with_other_expected_head_ends_the_loop_as_head_mismatch
1 failed, 127 deselected in 0.16s
```

**restored lines:**
```python
            if reason == REASON_HEAD_MISMATCH:
                return _result(repo, top, sha, status=problem_status, reason=reason,
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.56s
```

---

## P4 — an unreadable poll body is remembered and polling continues

**neutralization:** `last_error = "poll response unreadable: %s" % detail` + `continue` → `return _result(repo, top, sha, status=problem_status, reason=reason, detail=detail, uuid=uuid)  # bite-proof` (the loop ends on the first unreadable body)

**red** (`-k test_m12_unreadable_poll_body`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_unreadable_poll_body_then_merged_is_ok
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m12_unreadable_poll_body_every_time_is_poll_timeout_with_the_error
2 failed, 126 deselected in 0.36s
```

**restored lines:**
```python
            last_error = "poll response unreadable: %s" % detail
            continue
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.61s
```

---

## P5 — pending when the poll budget ran out is not merged

**neutralization:** the final `return _result(..., reason=REASON_POLL_TIMEOUT, ...)` → `return _result(repo, top, sha, merged=True, status=status, uuid=uuid)  # bite-proof` (a budget-end pending reads as merged)

**red** (`-k "test_m6 or test_m15_no_non_merged"`):
```
FFFF..F                                                                  [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m6_pending_until_budget_ends_is_poll_timeout
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m6_poll_call_timeout_is_capped_by_the_time_left
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m6_main_poll_timeout_exits_one
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_no_non_merged_outcome_reads_as_ok_or_merged[pending]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m15_no_non_merged_outcome_reads_as_ok_or_merged[poll-timeout]
5 failed, 2 passed, 121 deselected in 0.18s
```

**restored lines:**
```python
    return _result(repo, top, sha, status=status, reason=REASON_POLL_TIMEOUT,
                   detail=detail, uuid=uuid)
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.56s
```

---

## G1 — gh is not on PATH (merge)

**neutralization:** `if not shutil.which("gh"):` (in `merge`) → `if False:  # bite-proof`

**red** (`-k test_m13_gh_not_on_path_is_gh_unavailable`):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_gh_not_on_path_is_gh_unavailable
1 failed, 127 deselected in 0.23s
```

**restored lines:**
```python
    if not shutil.which("gh"):
        return _result(repo, top, sha, reason=REASON_GH_UNAVAILABLE, detail="gh not on PATH")
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.48s
```

---

## G2 — run raises OSError or TimeoutExpired on the PUT

**neutralization:** the except body `return _result(... REASON_MERGE_REQUEST_REFUSED ...)` → `raise  # bite-proof`

**red** (`-k test_m13_put_run_raising`):
```
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_put_run_raising_is_merge_request_refused[oserror]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_put_run_raising_is_merge_request_refused[filenotfound]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_put_run_raising_is_merge_request_refused[timeout]
3 failed, 125 deselected in 6.67s
```

**restored lines:**
```python
        return _result(repo, top, sha, reason=REASON_MERGE_REQUEST_REFUSED,
                       detail="merge request call failed: %s" % (exc or type(exc).__name__))
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.51s
```

---

## G3 — the PUT exits non-zero: refused, an existing request is never adopted or polled

**neutralization:** `if proc.returncode != 0:` (after the PUT) → `if False:  # bite-proof`

**red** (`-k "test_m7 or test_m8"`):
```
FFFFF                                                                    [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m7_put_409_with_existing_request_is_refused_and_never_polled
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m7_put_409_with_unusable_uuid_does_not_carry_it
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m8_put_400_with_message_is_refused_with_the_message
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m8_put_nonzero_without_a_body_is_refused_with_stderr
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m8_put_nonzero_with_a_merged_looking_body_is_still_refused
5 failed, 123 deselected in 0.25s
```

**restored lines:**
```python
    if proc.returncode != 0:
        detail, uuid = _refused_parts(proc)
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.49s
```

---

## G4 — gh is not on PATH (poll)

**neutralization:** `if not shutil.which("gh"):` (in `poll`) → `if False:  # bite-proof`

**red** (`-k test_m13_gh_not_on_path_blocks_poll_too`):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_m13_gh_not_on_path_blocks_poll_too
1 failed, 127 deselected in 5.23s
```

**restored lines:**
```python
    if not shutil.which("gh"):
        return _result(repo, top, sha, reason=REASON_GH_UNAVAILABLE, detail="gh not on PATH",
                       uuid=uuid)
```
**green:**
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.55s
```

---

## G5 — the parse boundary

**neutralization:** the except body `sys.stdout.write(json.dumps(_bad_argument(...)) + "\n")` + `return 1` → `raise  # bite-proof`

**red** (`-k test_cli_malformed_is_bad_argument_json_exit_one`):
```
FFFFFFFF                                                                 [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv0]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv1]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv2]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv3]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv4]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv5]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv6]
FAILED plugins/superheroes/lib/tests/test_stack_merge.py::test_cli_malformed_is_bad_argument_json_exit_one[argv7]
8 failed, 120 deselected in 0.25s
```

**restored lines:**
```python
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        sys.stdout.write(json.dumps(_bad_argument("invalid command-line arguments")) + "\n")
        return 1
```
**green** (final whole-file run, the command named by the order, without `--tb=no`):
```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 0.51s
```

---

## Restore receipt

A grep for `bite-proof` over `plugins/superheroes/lib/stack_merge.py` after the last restore returns no matches, so no neutralization is left in the source. Every restore was the inverse edit through the Edit tool; no `git checkout`, `git restore`, `git reset` or `git stash` was used.
