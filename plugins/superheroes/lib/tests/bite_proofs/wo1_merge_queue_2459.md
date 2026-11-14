# WO-1 (#2459) bite-proof — `merge_queue.py` guards

Per-guard bite proof for `plugins/superheroes/lib/merge_queue.py`: each `# axis:` clause is neutralized in source by a targeted edit (Edit tool), the proving test(s) must go red alone (`-k`), the clause is restored by the inverse edit (Edit tool), and the whole file goes green again.

**Register:** 25 guarded elements — one per `# axis:` line in the file. The order named one element per edge E1–E12 at least, plus the three decisions; E1 and E4 are one clause (`gh exits non-zero`, G4) proven by both edges' tests, and E2, E3, E9, E10 each have their own clause. Line numbers are those of the restored file. No element is left unproven; no `Unprovable as placed`, `Unreachable through this entry point` or `Unrunnable here` disclosure applies.

**Provenance:** claude (Claude Sonnet 5.5).

**Commands.** *Red* (one per element, `<expr>` named in each entry):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo1 -m pytest plugins/superheroes/lib/tests/test_merge_queue.py -q -p no:cacheprovider --tb=<mode> -k "<expr>"
```

*Green* (after each restore, the whole file, the order's named command unmodified):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo1 -m pytest plugins/superheroes/lib/tests/test_merge_queue.py -q -p no:cacheprovider --tb=short
```

**Disclosures about the captures.**
- Every capture omits the one leading line `warning: The `UV_NATIVE_TLS` environment variable is deprecated ...`, which is uv's own notice. The sandbox accepted `-X pycache_prefix`.
- `<mode>` is `--tb=short` for V1 (the order's named flag, and the only red run with the order's flag), `--tb=line` for most later reds, and `--tb=no` for Q5, M2, M4 and M5 (stated in each entry). `--tb` only changes how much traceback prints; no test is filtered by it. This deviates from the order's named command for those reds; the order's own command is used unmodified for every green. R3's capture elides 9 of 11 identical two-line pairs (said in place); V1's capture abbreviates repeated traceback frames in parentheses (said in place).
- Each green below shows its summary line. The two progress lines of every green run are identical (`.` x72 `[ 61%]`, `.` x45 `[100%]`) and are shown once, under V1; every later green printed the same two lines with its own timing.
- Command budget: 54 of 60 invocations — 52 pytest runs (1 first full run, 25 reds plus 1 extra red for Q4, 25 greens) and 2 `git status`.
- Redaction: nothing in these captures is a secret, token or private URL; the only host-like text is the fixture repo `owner/example`.

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| V1 | merge_queue.py:117 | repo is not an owner/name string (E12) | `test_e12_bad_repo` | proven (exception red) |
| V2 | merge_queue.py:121 | branch not a non-empty string without whitespace/control chars (E12) | `test_e12_bad_branch` | proven |
| V3 | merge_queue.py:127 | timeout not a positive finite number (E12) | `test_e12_bad_timeout` | proven |
| V4 | merge_queue.py:131 | deadline_at neither None nor a finite number (E12) | `test_e12_bad_deadline_at` | proven |
| G1 | merge_queue.py:169 | deadline passed: the call is not made, a failed read (E10) | `test_e10_deadline_*` | proven |
| G2 | merge_queue.py:173 | each call's timeout capped by the time left (E10) | `test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left` | proven |
| G3 | merge_queue.py:178 | run raises OSError / TimeoutExpired (E9) | `test_e9_*` | proven (exception red) |
| G4 | merge_queue.py:181 | gh exits non-zero (E1 and E4) | `test_e1_*`, `test_e4_*`, `test_graphql_failed_after_*`, `test_a_second_rules_page_*` | proven |
| P1 | merge_queue.py:191 | branch is percent-quoted into the rules path | `test_branch_is_percent_quoted_with_slashes_kept` | proven |
| R1 | merge_queue.py:199 | a rules page unreadable / not a JSON list fails the rules read (E2) | `test_e2_rules_page_not_a_json_list_is_read_failed` | proven (exception red) |
| R2 | merge_queue.py:204 | a rules row not an object with a string type (E3) | `test_e3_malformed_rules_row_is_read_failed` | proven (7 exception reds, 2 wrong-answer reds; see entry) |
| R3 | merge_queue.py:209 | a rules row of type merge_queue is a queue | `test_squash_queue_*`, `test_method_*`, `test_a_queue_row_*`, `test_two_pages_of_rules_the_queue_*` | proven |
| Q1 | merge_queue.py:226 | GraphQL stdout is not a JSON object (E5) | `test_e5_*` | proven (exception red) |
| Q2 | merge_queue.py:230 | GraphQL carries a non-empty errors key (E6) | `test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data` | proven |
| Q3 | merge_queue.py:236 | data.repository missing, null or not an object (E7) | `test_e7_*` | proven |
| Q4 | merge_queue.py:240 | mergeQueue key absent (E8) | `test_e8_mergequeue_key_absent_is_read_failed` | proven |
| Q5 | merge_queue.py:245 | a null mergeQueue is a successful no-queue read | `test_no_queue_*`, `test_queue_false_*`, `test_cli_no_queue_round_trip` | proven |
| Q6 | merge_queue.py:248 | a non-null mergeQueue object is a queue | `test_classic_protection_queue_is_caught_by_graphql` | proven (source/reads differ; queue stays true — see entry) |
| Q7 | merge_queue.py:251 | mergeQueue neither null nor an object is unreadable (E8b) | `test_e8_mergequeue_neither_null_nor_object_is_read_failed` | proven |
| M1 | merge_queue.py:274 | gh not on PATH (E11) | `test_e11_gh_not_on_path_fails_closed_with_no_call` | proven |
| M2 | merge_queue.py:286 | a rules queue row answers at once; GraphQL skipped | `test_squash_queue_in_rules_is_found_and_graphql_is_not_called` | proven |
| M3 | merge_queue.py:296 | a GraphQL queue answers queue true even when rules failed | `test_classic_protection_*`, `test_e1_rules_failed_but_graphql_*`, `test_queue_false_*` | proven |
| M4 | merge_queue.py:301 | any failed read answers queue true | all failed-read edge tests (51 reds) | proven |
| M5 | merge_queue.py:306 | both reads ok and none: the one path to queue false | `test_no_queue_*`, `test_queue_false_*` | proven |
| C1 | merge_queue.py:323 | the parse boundary | `test_cli_malformed_is_bad_argument_json_exit_one` | proven (exception red) |

---

## V1 — repo is not an owner/name string

**neutralization:** `if not isinstance(repo, str) or not _REPO_RE.match(repo):` → `if False:  # bite-proof`

**red** (`-k test_e12_bad_repo`, `--tb=short`):
```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
___________________________ test_e12_bad_repo[None] ____________________________
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:463: in test_e12_bad_repo
    _assert_bad_argument(mq.read(repo=repo, branch=BRANCH, run=run))
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:280: in read
    owner, name = repo.split("/")
                  ^^^^^^^^^^
E   AttributeError: 'NoneType' object has no attribute 'split'
_____________________________ test_e12_bad_repo[5] _____________________________
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:463: in test_e12_bad_repo
    _assert_bad_argument(mq.read(repo=repo, branch=BRANCH, run=run))
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:280: in read
    owner, name = repo.split("/")
                  ^^^^^^^^^^
E   AttributeError: 'int' object has no attribute 'split'
___________________________ test_e12_bad_repo[owner] ___________________________
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:463: in test_e12_bad_repo
    _assert_bad_argument(mq.read(repo=repo, branch=BRANCH, run=run))
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:280: in read
    owner, name = repo.split("/")
    ^^^^^^^^^^^
E   ValueError: not enough values to unpack (expected 2, got 1)
__________________________ test_e12_bad_repo[owner/] ___________________________
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:463: in test_e12_bad_repo
    _assert_bad_argument(mq.read(repo=repo, branch=BRANCH, run=run))
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:283: in read
    rules_state, method, rules_detail = _read_rules(gh, owner, name, branch)
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:198: in _read_rules
    rows = gh_pages.read(_fetch, path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/gh_pages.py:30: in read
    out = fetch(f"{path}{sep}per_page={PAGE_ROWS}&page={number}")
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:195: in _fetch
    proc = gh.call(["gh", "api", endpoint])
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:176: in call
    proc = self.run(argv, capture_output=True, text=True, timeout=call_timeout)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: in _run
    raise AssertionError("unexpected gh argv: %r" % (argv,))
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner//rules/branches/main?per_page=100&page=1']
___________________________ test_e12_bad_repo[/name] ___________________________
(same call chain as the previous block)
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos//name/rules/branches/main?per_page=100&page=1']
___________________________ test_e12_bad_repo[o/n/x] ___________________________
(call chain ends at merge_queue.py:280 `owner, name = repo.split("/")`)
E   ValueError: too many values to unpack (expected 2)
________________________ test_e12_bad_repo[own er/name] ________________________
(same call chain as the [owner/] block)
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/own er/name/rules/branches/main?per_page=100&page=1']
___________________________ test_e12_bad_repo[o/n\n] ___________________________
(same call chain as the [owner/] block)
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/o/n\n/rules/branches/main?per_page=100&page=1']
_____________________________ test_e12_bad_repo[] ______________________________
(call chain ends at merge_queue.py:280 `owner, name = repo.split("/")`)
E   ValueError: not enough values to unpack (expected 2, got 1)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[owner]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[owner/]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[/name]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[o/n/x]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[own er/name]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[o/n\n]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_repo[]
9 failed, 108 deselected in 0.43s
```
(Disclosure: in this one capture the lines in parentheses stand for the repeated frames of the traceback the run printed in full — `(same call chain as the previous block)` etc. — written here to keep the record short; every `E` line and the summary are verbatim. The reds are exceptions or a gh call that should not have happened, not a wrong-answer result.)

**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _bad_argument("repo must be owner/name")
```
**green:**
```
........................................................................ [ 61%]
.............................................                            [100%]
117 passed in 0.56s
```

---

## V2 — branch is not a non-empty string without whitespace or control characters

**neutralization:** the two-line `if (not isinstance(branch, str) or not branch or _BAD_BRANCH_CHAR_RE.search(branch)):` → `if False:  # bite-proof`

**red** (`-k "test_e12_bad_branch or test_cli_bad_argument"`, `--tb=line`; the `.` is `test_cli_bad_argument_value_exits_one`, which tests a bad repo and so rightly stays green):
```
FFFFFFFFFF.                                                              [100%]
=================================== FAILURES ===================================
E   TypeError: quote_from_bytes() expected bytes
/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/urllib/parse.py:957: TypeError: quote_from_bytes() expected bytes
E   TypeError: quote_from_bytes() expected bytes
/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/urllib/parse.py:957: TypeError: quote_from_bytes() expected bytes
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%20b?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%20b?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%09b?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%09b?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%0Ab?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%0Ab?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main%0A?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main%0A?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%00b?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%00b?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%7Fb?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%7Fb?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%C2%85b?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/a%C2%85b?per_page=100&page=1']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[a b]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[a\tb]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[a\nb]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[main\n]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[a\x00b]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[a\x7fb]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_branch[a\x85b]
10 failed, 1 passed, 106 deselected in 0.33s
```

**restored lines:**
```python
    if (not isinstance(branch, str) or not branch
            or _BAD_BRANCH_CHAR_RE.search(branch)):
        return _bad_argument("branch must be a non-empty string without whitespace or "
```
**green:** `117 passed in 0.59s`

---

## V3 — timeout is not a positive finite number

**neutralization:** `if not _is_positive_finite(timeout):` → `if False:  # bite-proof`

**red** (`-k test_e12_bad_timeout`, `--tb=line`; each of the 7 failures is the same `E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']` line plus its `test_merge_queue.py:67` location line, printed in full by the run):
```
FFFFFFF                                                                  [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[nan]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_timeout[inf]
7 failed, 110 deselected in 0.27s
```

**restored lines:**
```python
    if not _is_positive_finite(timeout):
        return _bad_argument("timeout must be a positive number of seconds")
```
**green:** `117 passed in 0.55s`

---

## V4 — deadline_at is neither None nor a finite number

**neutralization:** `if deadline_at is not None and not _is_finite_number(deadline_at):` → `if False:  # bite-proof`

**red** (`-k test_e12_bad_deadline_at`, `--tb=line`):
```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:448: assert True is False
E   TypeError: unsupported operand type(s) for -: 'str' and 'float'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:168: TypeError: unsupported operand type(s) for -: 'str' and 'float'
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
E   assert True is False
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:448: assert True is False
E   TypeError: unsupported operand type(s) for -: 'list' and 'float'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:168: TypeError: unsupported operand type(s) for -: 'list' and 'float'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_deadline_at[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_deadline_at[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_deadline_at[nan]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_deadline_at[inf]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_deadline_at[-inf]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e12_bad_deadline_at[deadline_at5]
6 failed, 111 deselected in 0.29s
```

**restored lines:**
```python
    if deadline_at is not None and not _is_finite_number(deadline_at):
        return _bad_argument("deadline_at must be None or a finite number")
```
**green:** `117 passed in 0.70s`

---

## G1 — the deadline has passed: the call is not made

**neutralization:** `if left <= 0:` (in `_Gh.call`) → `if False:  # bite-proof`

**red** (`-k test_e10_deadline`, `--tb=line`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_deadline_already_passed_makes_no_call_and_fails_closed
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_deadline_passing_between_the_reads_makes_no_graphql_call
2 failed, 115 deselected in 0.31s
```

**restored lines:**
```python
            if left <= 0:
                self.problem = "the time budget ran out before the gh call was made"
                return None
```
**green:** `117 passed in 0.66s`

---

## G2 — each call's timeout is capped by the time left

**neutralization:** `call_timeout = min(call_timeout, left)` → `call_timeout = call_timeout  # bite-proof`

**red** (`-k test_e10_each_calls_timeout`, `--tb=line`; the 2 passes are the cases where `timeout` is already the smaller value):
```
F..                                                                      [100%]
=================================== FAILURES ===================================
E   assert [120, 120] == [10.0, 10.0]
      
      At index 0 diff: 120 != 10.0
      Use -v to get more diff
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:430: assert [120, 120] == [10.0, 10.0]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-10.0-10.0]
1 failed, 2 passed, 114 deselected in 0.35s
```

**restored lines:**
```python
            call_timeout = min(call_timeout, left)
```
**green:** `117 passed in 0.58s`

---

## G3 — run raises OSError or TimeoutExpired (E9)

**neutralization:** the except body `self.problem = "gh call failed: ..."` + `return None` → `raise  # bite-proof`

**red** (`-k test_e9`, `--tb=line`; an exception propagates out of `read`, rather than a wrong answer):
```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   OSError: no gh
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:71: OSError: no gh
E   FileNotFoundError: gh
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:71: FileNotFoundError: gh
E   subprocess.TimeoutExpired: Command '['gh']' timed out after 5 seconds
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:71: subprocess.TimeoutExpired: Command '['gh']' timed out after 5 seconds
E   OSError: no gh
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:71: OSError: no gh
E   FileNotFoundError: gh
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:71: FileNotFoundError: gh
E   subprocess.TimeoutExpired: Command '['gh']' timed out after 5 seconds
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:71: subprocess.TimeoutExpired: Command '['gh']' timed out after 5 seconds
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_rules_read_is_read_failed[oserror]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_rules_read_is_read_failed[filenotfound]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_rules_read_is_read_failed[timeout]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_graphql_read_is_read_failed[oserror]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_graphql_read_is_read_failed[filenotfound]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_graphql_read_is_read_failed[timeout]
6 failed, 111 deselected in 0.43s
```

**restored lines:**
```python
            self.problem = "gh call failed: %s" % (exc or type(exc).__name__)
            return None
```
**green:** `117 passed in 0.51s`

---

## G4 — gh exits non-zero (E1 rules, E4 GraphQL incl. the cloud proxy's refusal)

**neutralization:** `if proc.returncode != 0:` → `if False:  # bite-proof`

**red** (`-k "test_e1_ or test_e4_ or test_graphql_failed_after or test_a_second_rules_page"`, `--tb=line`; the 3 `.` are passes, explained under the capture):
```
FF...FF                                                                  [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'gh: boom' in 'rules read failed: rules response was not a JSON list'
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:161: AssertionError: assert 'gh: boom' in 'rules read failed: rules response was not a JSON list'
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   AssertionError: assert '(HTTP 403)' in 'graphql read failed: graphql response has no data.repository object'
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:286: AssertionError: assert '(HTTP 403)' in 'graphql read failed: graphql response has no data.repository object'
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_second_rules_page_that_fails_fails_the_rules_read
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e1_rules_exit_nonzero_is_read_failed_even_with_a_list_on_stdout
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e4_cloud_proxy_graphql_refusal_is_read_failed_with_the_refusal_in_the_detail
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e4_graphql_exit_nonzero_with_a_no_queue_body_is_still_read_failed
4 failed, 3 passed, 110 deselected in 0.34s
```
(The two `assert False is True` lines are the clean wrong-answer reds: a non-zero exit with a well-formed body answered `queue: false`. The 3 passes are `test_e1_rules_failed_but_graphql_finds_a_queue_reports_graphql`, `test_e1_both_reads_failed_names_both` and `test_graphql_failed_after_a_clean_rules_read_is_read_failed`: their failing gh calls carry an empty stdout, so the not-a-list / not-an-object clauses still fail the read without this one.)

**restored lines:**
```python
        if proc.returncode != 0:
            self.problem = "gh exited %s: %s" % (proc.returncode,
```
**green:** `117 passed in 0.56s`

---

## P1 — the branch is percent-quoted into the rules path

**neutralization:** `urllib.parse.quote(branch, safe="/")` → `branch  # bite-proof` (the whole `% (owner, name, branch)` tail)

**red** (`-k test_branch_is_percent_quoted`, `--tb=line`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/release/1.0#x?y&per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/release/1.0#x?y&per_page=100&page=1']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_branch_is_percent_quoted_with_slashes_kept
1 failed, 116 deselected in 0.26s
```

**restored lines:**
```python
    path = "repos/%s/%s/rules/branches/%s" % (owner, name, urllib.parse.quote(branch, safe="/"))
```
**green:** `117 passed in 0.56s`

---

## R1 — a rules page unreadable / not a JSON list fails the rules read (E2)

**neutralization:** `if rows is None:` → `if False:  # bite-proof`

**red** (`-k test_e2_`, `--tb=line`; red by `TypeError` on the next loop, an exception rather than a wrong answer):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   TypeError: 'NoneType' object is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:203: TypeError: 'NoneType' object is not iterable
E   TypeError: 'NoneType' object is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:203: TypeError: 'NoneType' object is not iterable
E   TypeError: 'NoneType' object is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:203: TypeError: 'NoneType' object is not iterable
E   TypeError: 'NoneType' object is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:203: TypeError: 'NoneType' object is not iterable
E   TypeError: 'NoneType' object is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:203: TypeError: 'NoneType' object is not iterable
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[not json]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[{"message": "x"}]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[null]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[5]
5 failed, 112 deselected in 0.29s
```

**restored lines:**
```python
    if rows is None:
        return _FAILED, None, gh.problem or "rules response was not a JSON list"
```
**green:** `117 passed in 0.80s`

---

## R2 — a rules row that is not an object with a string type (E3)

**neutralization:** `if not isinstance(row, dict) or not isinstance(row.get("type"), str):` → `if False:  # bite-proof`

**red** (`-k test_e3_`, `--tb=line`; 7 exceptions and 2 wrong-answer reds (`rows6`, `rows7`: `assert False is True`)):
```
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
E   TypeError: string indices must be integers, not 'str'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: TypeError: string indices must be integers, not 'str'
E   TypeError: 'NoneType' object is not subscriptable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: TypeError: 'NoneType' object is not subscriptable
E   TypeError: 'int' object is not subscriptable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: TypeError: 'int' object is not subscriptable
E   TypeError: list indices must be integers or slices, not 'str'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: TypeError: list indices must be integers or slices, not str
E   KeyError: 'type'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: KeyError: 'type'
E   KeyError: 'type'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: KeyError: 'type'
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   TypeError: string indices must be integers, not 'str'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:210: TypeError: string indices must be integers, not 'str'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows4]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows6]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows7]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows8]
9 failed, 108 deselected in 0.78s
```

**restored lines:**
```python
        if not isinstance(row, dict) or not isinstance(row.get("type"), str):
            return _FAILED, None, "a rules row is not an object with a string type"
```
**green:** `117 passed in 1.19s`

---

## R3 — a rules row of type merge_queue is a queue

**neutralization:** `if row["type"] == "merge_queue":` → `if False:  # bite-proof`

**red** (`-k "squash_queue or two_pages_of_rules_the_queue or test_method or test_a_queue_row"`, `--tb=line`): 11 failures. The run printed, for each, the same two lines — `E   AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']` and the same text prefixed by `/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: ` — **11 times**. Elided here: 9 of those 11 identical pairs (the 2 shown below are verbatim). The progress line, the summary list and the totals are verbatim.
```
FFFFFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
E   AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']
E   AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){mergeQueue(branch:$branch){id}}}', '-f', 'owner=owner', '-f', 'name=example', '-f', 'branch=main']
(... 9 further identical pairs elided ...)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_squash_queue_in_rules_is_found_and_graphql_is_not_called
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_two_pages_of_rules_the_queue_row_on_page_two_is_found
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_method_is_reported_lower_cased[SQUASH-squash]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_method_is_reported_lower_cased[MERGE-merge]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_method_is_reported_lower_cased[REBASE-rebase]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_method_is_reported_lower_cased[squash-squash]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_queue_row_without_a_string_method_is_a_queue_with_method_null[row0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_queue_row_without_a_string_method_is_a_queue_with_method_null[row1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_queue_row_without_a_string_method_is_a_queue_with_method_null[row2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_queue_row_without_a_string_method_is_a_queue_with_method_null[row3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_queue_row_without_a_string_method_is_a_queue_with_method_null[row4]
11 failed, 106 deselected in 0.31s
```
(The red is the unmocked GraphQL call that a rules queue row must not make: the unfaked-argv assertion in `_make_run` fires.)

**restored lines:**
```python
        if row["type"] == "merge_queue":
            parameters = row.get("parameters")
```
**green:** `117 passed in 0.53s`

---

## Q1 — GraphQL stdout is not a JSON object (E5)

**neutralization:** `if body is None:` → `if False:  # bite-proof`

**red** (`-k test_e5_`, `--tb=line`; red by `AttributeError`, an exception):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   AttributeError: 'NoneType' object has no attribute 'get'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:231: AttributeError: 'NoneType' object has no attribute 'get'
E   AttributeError: 'NoneType' object has no attribute 'get'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:231: AttributeError: 'NoneType' object has no attribute 'get'
E   AttributeError: 'NoneType' object has no attribute 'get'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:231: AttributeError: 'NoneType' object has no attribute 'get'
E   AttributeError: 'NoneType' object has no attribute 'get'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:231: AttributeError: 'NoneType' object has no attribute 'get'
E   AttributeError: 'NoneType' object has no attribute 'get'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:231: AttributeError: 'NoneType' object has no attribute 'get'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[not json]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[[]]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[null]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[5]
5 failed, 112 deselected in 5.77s
```

**restored lines:**
```python
    if body is None:
        return _FAILED, "graphql response is not a JSON object"
```
**green:** `117 passed in 0.66s`

---

## Q2 — GraphQL carries a non-empty errors key (E6)

**neutralization:** `if body.get("errors"):` → `if False:  # bite-proof`

**red** (`-k test_e6_`, `--tb=line`; the 2 passes are `test_e6_an_empty_or_null_errors_key_does_not_fail_the_read`, which must pass both ways):
```
FFF..                                                                    [100%]
=================================== FAILURES ===================================
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data[errors0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data[boom]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data[errors2]
3 failed, 2 passed, 112 deselected in 0.28s
```
(Clean wrong-answer red: `queue: false` beside a GraphQL `errors` array.)

**restored lines:**
```python
    if body.get("errors"):
        return _FAILED, "graphql response carries errors: %s" % (body.get("errors"),)
```
**green:** `117 passed in 0.56s`

---

## Q3 — data.repository missing, null or not an object (E7)

**neutralization:** `if not isinstance(repository, dict):` → `if False:  # bite-proof`

**red** (`-k test_e7_`, `--tb=line`; bodies 0–4 raise `TypeError` at the next clause; bodies 5 and 6 (`[]`, `"x"`) are caught by the next clause (Q4) with a different detail, so they go red on the detail assertion only):
```
FFFFFFF                                                                  [100%]
=================================== FAILURES ===================================
E   TypeError: argument of type 'NoneType' is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:241: TypeError: argument of type 'NoneType' is not iterable
E   TypeError: argument of type 'NoneType' is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:241: TypeError: argument of type 'NoneType' is not iterable
E   TypeError: argument of type 'NoneType' is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:241: TypeError: argument of type 'NoneType' is not iterable
E   TypeError: argument of type 'NoneType' is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:241: TypeError: argument of type 'NoneType' is not iterable
E   TypeError: argument of type 'NoneType' is not iterable
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:241: TypeError: argument of type 'NoneType' is not iterable
E   AssertionError: assert 'data.repository' in 'graphql read failed: graphql repository carries no mergeQueue key'
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:345: AssertionError: assert 'data.repository' in 'graphql read failed: graphql repository carries no mergeQueue key'
E   AssertionError: assert 'data.repository' in 'graphql read failed: graphql repository carries no mergeQueue key'
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:345: AssertionError: assert 'data.repository' in 'graphql read failed: graphql repository carries no mergeQueue key'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body4]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body6]
7 failed, 110 deselected in 0.32s
```

**restored lines:**
```python
    if not isinstance(repository, dict):
        return _FAILED, "graphql response has no data.repository object"
```
**green:** `117 passed in 0.51s`

---

## Q4 — the mergeQueue key is absent (E8)

**first neutralization (exception red):** `if "mergeQueue" not in repository:` → `if False:  # bite-proof`. Run `-k test_e8_mergequeue_key_absent`, `--tb=line`:
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   KeyError: 'mergeQueue'
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:244: KeyError: 'mergeQueue'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_key_absent_is_read_failed
1 failed, 116 deselected in 0.27s
```

**second neutralization (clean wrong-answer red, the failure mode that matters — an absent key read as "no queue"):** the same `if False:  # bite-proof` plus `merge_queue = repository["mergeQueue"]` → `merge_queue = repository.get("mergeQueue")  # bite-proof`. Same `-k`, `--tb=line`:
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_key_absent_is_read_failed
1 failed, 116 deselected in 0.29s
```

**restored lines (both edits undone by inverse edits):**
```python
    if "mergeQueue" not in repository:
        return _FAILED, "graphql repository carries no mergeQueue key"

    merge_queue = repository["mergeQueue"]
```
**green:** `117 passed in 0.59s`

---

## Q5 — a null mergeQueue is a successful no-queue read

**neutralization:** `if merge_queue is None:` → `if False:  # bite-proof` (a null now falls to the "neither null nor an object" failure)

**red** (`-k "test_no_queue or test_e6_an_empty or test_queue_false or test_cli_no_queue or test_branch_is_percent or test_two_pages_of_rules_with_no_queue or test_e10_each"`, `--tb=no`):
```
FFFFFFFFFF                                                               [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_no_queue_when_both_reads_succeed_and_say_none
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_two_pages_of_rules_with_no_queue_row_reads_both_pages_then_graphql
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_branch_is_percent_quoted_with_slashes_kept
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_an_empty_or_null_errors_key_does_not_fail_the_read[errors0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_an_empty_or_null_errors_key_does_not_fail_the_read[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-10.0-10.0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[3-10.0-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-1000.0-120]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_queue_false_is_answered_only_when_both_reads_succeed_and_say_none
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_no_queue_round_trip
10 failed, 107 deselected in 0.29s
```

**restored lines:**
```python
    if merge_queue is None:
        return _NO_QUEUE, None
```
**green:** `117 passed in 0.53s`

---

## Q6 — a non-null mergeQueue object is a queue

**neutralization:** `if isinstance(merge_queue, dict):` → `if False:  # bite-proof` (an object now falls to the "neither null nor an object" failure)

**red** (`-k "classic_protection or test_queue_false"`, `--tb=line`; this red moves `source` and `reads` — `queue` stays true because the fail-closed fallthrough still answers it, which is the intended backstop; the decisive clean red for a wrong `queue` is M3):
```
F.                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'ok': True, ...d': None, ...} == {'ok': True, ...d': None, ...}
      
      Omitting 6 identical items, use -vv to show
      Differing items:
      {'reads': {'rules': 'ok', 'graphql': 'failed'}} != {'reads': {'rules': 'ok', 'graphql': 'ok'}}
      {'detail': 'graphql read failed: graphql mergeQueue is neither null nor an object'} != {'detail': None}
      {'source': 'read-failed'} != {'source': 'graphql'}
      Use -v to get more diff
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:127: AssertionError: assert {'ok': True, ...d': None, ...} == {'ok': True, ...d': None, ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_classic_protection_queue_is_caught_by_graphql
1 failed, 1 passed, 115 deselected in 0.30s
```

**restored lines:**
```python
    if isinstance(merge_queue, dict):
        return _QUEUE, None
```
**green:** `117 passed in 0.53s`

---

## Q7 — a mergeQueue neither null nor an object is unreadable

**neutralization:** `return _FAILED, "graphql mergeQueue is neither null nor an object"` → `return _NO_QUEUE, None  # bite-proof`

**red** (`-k test_e8_mergequeue_neither`, `--tb=line`):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
E   assert False is True
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:95: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[MQ_x]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[value1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[False]
5 failed, 112 deselected in 0.35s
```

**restored lines:**
```python
    return _FAILED, "graphql mergeQueue is neither null nor an object"
```
**green:** `117 passed in 0.67s`

---

## M1 — gh is not on PATH (E11)

**neutralization:** `if not shutil.which("gh"):` → `if False:  # bite-proof`

**red** (`-k "test_e11 or test_e12_bad_argument_comes"`, `--tb=line`; the `.` is the bad-argument-before-PATH-check test, which stays right):
```
F.                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:67: AssertionError: unexpected gh argv: ['gh', 'api', 'repos/owner/example/rules/branches/main?per_page=100&page=1']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e11_gh_not_on_path_fails_closed_with_no_call
1 failed, 1 passed, 115 deselected in 0.40s
```

**restored lines:**
```python
    if not shutil.which("gh"):
        return _result(repo, branch, queue=True, source=SOURCE_READ_FAILED,
```
**green:** `117 passed in 0.57s`

---

## M2 — a rules queue row answers at once; the GraphQL read is skipped

**neutralization:** `if rules_state == _QUEUE:` → `if False:  # bite-proof`

**red** (`-k "squash_queue or test_cli_round_trip"`, `--tb=no`):
```
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_squash_queue_in_rules_is_found_and_graphql_is_not_called
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_round_trip_prints_one_json_line_and_exits_zero
2 failed, 115 deselected in 0.32s
```

**restored lines:**
```python
    if rules_state == _QUEUE:
        return _result(repo, branch, queue=True, source=SOURCE_RULES, method=method,
```
**green:** `117 passed in 0.56s`

---

## M3 — a GraphQL queue answers queue true even when the rules read failed

**neutralization:** `if graphql_state == _QUEUE:` → `if False:  # bite-proof` (a real GraphQL queue now falls through to `queue: false`)

**red** (`-k "classic_protection or test_e1_rules_failed_but_graphql or test_queue_false"`, `--tb=line`):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'ok': True, ...d': None, ...} == {'ok': True, ...d': None, ...}
      
      Omitting 7 identical items, use -vv to show
      Differing items:
      {'source': 'none'} != {'source': 'graphql'}
      {'queue': False} != {'queue': True}
      Use -v to get more diff
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:127: AssertionError: assert {'ok': True, ...d': None, ...} == {'ok': True, ...d': None, ...}
E   AssertionError: assert 'read-failed' == 'graphql'
      
      - graphql
      + read-failed
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:220: AssertionError: assert 'read-failed' == 'graphql'
E   AssertionError: assert [('none', 'no...ne', 'queue')] == [('none', 'none')]
      
      Left contains one more item: ('none', 'queue')
      Use -v to get more diff
/home/user/wt-2459-wo1/plugins/superheroes/lib/tests/test_merge_queue.py:512: AssertionError: assert [('none', 'no...ne', 'queue')] == [('none', 'none')]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_classic_protection_queue_is_caught_by_graphql
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e1_rules_failed_but_graphql_finds_a_queue_reports_graphql
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_queue_false_is_answered_only_when_both_reads_succeed_and_say_none
3 failed, 114 deselected in 0.28s
```
(The first and third are the clean wrong-answer reds: `{'queue': False} != {'queue': True}`.)

**restored lines:**
```python
    if graphql_state == _QUEUE:
        return _result(repo, branch, queue=True, source=SOURCE_GRAPHQL, reads=reads,
```
**green:** `117 passed in 0.59s`

---

## M4 — any failed read answers queue true

**neutralization:** `if rules_state == _FAILED or graphql_state == _FAILED:` → `if False:  # bite-proof`

**red** (whole file, `--tb=no`; 51 failed, 66 passed — every failed-read edge test goes red, because the failed read now falls through to `queue: false`):
```
.....F..........F.FFFFFFFFFFFFFFFFFFFFFFFFFF..FFFFFFFFFFFFFFFFFFFFF..... [ 61%]
................................F..F.........                            [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_a_second_rules_page_that_fails_fails_the_rules_read
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e1_rules_exit_nonzero_is_read_failed_even_with_a_list_on_stdout
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e1_both_reads_failed_names_both
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_graphql_failed_after_a_clean_rules_read_is_read_failed
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[not json]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[{"message": "x"}]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[null]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e2_rules_page_not_a_json_list_is_read_failed[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows4]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows6]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows7]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e3_malformed_rules_row_is_read_failed[rows8]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e4_cloud_proxy_graphql_refusal_is_read_failed_with_the_refusal_in_the_detail
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e4_graphql_exit_nonzero_with_a_no_queue_body_is_still_read_failed
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[not json]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[[]]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[null]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e5_graphql_stdout_not_a_json_object_is_read_failed[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data[errors0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data[boom]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_graphql_errors_is_read_failed_even_beside_a_no_queue_data[errors2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body4]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e7_missing_or_null_repository_is_read_failed[body6]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_key_absent_is_read_failed
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[MQ_x]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[value1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[True]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e8_mergequeue_neither_null_nor_object_is_read_failed[False]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_rules_read_is_read_failed[oserror]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_rules_read_is_read_failed[filenotfound]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_rules_read_is_read_failed[timeout]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_graphql_read_is_read_failed[oserror]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_graphql_read_is_read_failed[filenotfound]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e9_run_raising_on_the_graphql_read_is_read_failed[timeout]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_deadline_already_passed_makes_no_call_and_fails_closed
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_deadline_passing_between_the_reads_makes_no_graphql_call
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_queue_false_is_answered_only_when_both_reads_succeed_and_say_none
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_read_failed_still_exits_zero_with_queue_true
51 failed, 66 passed in 0.61s
```

**restored lines:**
```python
    if rules_state == _FAILED or graphql_state == _FAILED:
        return _result(repo, branch, queue=True, source=SOURCE_READ_FAILED, reads=reads,
                       detail=detail)
```
**green:** `117 passed in 0.64s`

---

## M5 — both reads ok and none: the one path to queue false

**neutralization:** `return _result(repo, branch, queue=False, source=SOURCE_NONE, reads=reads)` → `queue=True, ...  # bite-proof`

**red** (`-k "test_no_queue or test_queue_false or test_cli_no_queue or test_two_pages_of_rules_with_no_queue or test_branch_is_percent or test_e6_an_empty or test_e10_each"`, `--tb=no`):
```
FFFFFFFFFF                                                               [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_no_queue_when_both_reads_succeed_and_say_none
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_two_pages_of_rules_with_no_queue_row_reads_both_pages_then_graphql
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_branch_is_percent_quoted_with_slashes_kept
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_an_empty_or_null_errors_key_does_not_fail_the_read[errors0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e6_an_empty_or_null_errors_key_does_not_fail_the_read[None]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-10.0-10.0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[3-10.0-3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_e10_each_calls_timeout_is_the_smaller_of_timeout_and_the_time_left[120-1000.0-120]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_queue_false_is_answered_only_when_both_reads_succeed_and_say_none
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_no_queue_round_trip
10 failed, 107 deselected in 0.46s
```

**restored lines:**
```python
    return _result(repo, branch, queue=False, source=SOURCE_NONE, reads=reads)
```
**green:** `117 passed in 0.68s`

---

## C1 — the parse boundary

**neutralization:** the except body `sys.stdout.write(json.dumps(_bad_argument(...)) + "\n")` + `return 1` → `raise  # bite-proof`

**red** (`-k test_cli_malformed`, `--tb=line`; exceptions escape `main` instead of the bad-argument JSON):
```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
E   merge_queue._ParseError: unknown or missing verb
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:321: merge_queue._ParseError: unknown or missing verb
E   argparse.ArgumentError: the following arguments are required: --repo, --branch

During handling of the above exception, another exception occurred:
E   merge_queue._ParseError: the following arguments are required: --repo, --branch
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:62: merge_queue._ParseError: the following arguments are required: --repo, --branch
E   argparse.ArgumentError: the following arguments are required: --branch

During handling of the above exception, another exception occurred:
E   merge_queue._ParseError: the following arguments are required: --branch
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:62: merge_queue._ParseError: the following arguments are required: --branch
E   argparse.ArgumentError: the following arguments are required: --repo

During handling of the above exception, another exception occurred:
E   merge_queue._ParseError: the following arguments are required: --repo
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:62: merge_queue._ParseError: the following arguments are required: --repo
E   argparse.ArgumentError: argument verb: invalid choice: 'write' (choose from read)

During handling of the above exception, another exception occurred:
E   merge_queue._ParseError: argument verb: invalid choice: 'write' (choose from read)
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:62: merge_queue._ParseError: argument verb: invalid choice: 'write' (choose from read)
E   merge_queue._ParseError: unrecognized arguments: --nope 1
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:62: merge_queue._ParseError: unrecognized arguments: --nope 1
E   merge_queue._ParseError
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:65: merge_queue._ParseError
E   merge_queue._ParseError
/home/user/wt-2459-wo1/plugins/superheroes/lib/merge_queue.py:65: merge_queue._ParseError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv0]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv1]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv2]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv3]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv4]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv5]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv6]
FAILED plugins/superheroes/lib/tests/test_merge_queue.py::test_cli_malformed_is_bad_argument_json_exit_one[argv7]
8 failed, 109 deselected in 0.27s
```

**restored lines:**
```python
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        sys.stdout.write(json.dumps(_bad_argument("invalid command-line arguments")) + "\n")
        return 1
```
**green** (final whole-file run, the order's named command): `117 passed in 0.51s`

---

## Restore receipt

A grep for `bite-proof` over `plugins/superheroes/lib/merge_queue.py` after the last restore returned `No matches found`, so no neutralization is left in the source. Every neutralization and every restore was an Edit-tool edit (the inverse edit); no `git checkout`, `git restore`, `git reset` or `git stash` was used.
