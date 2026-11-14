# I2452 bite-proof: order lint reads its keywords outside path spans

Bite-proof record for the detectors issue 2452 adds in `order_lint.py` (`_mask_path_spans`, `_budget_ok`, `_timeout_warnings`), proven by `test_order_lint_path_spans_2452.py`.

**Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2452 -m pytest <node> -q -p no:cacheprovider`. The harness's `UV_NATIVE_TLS` deprecation line is omitted from each capture; every pytest line is as printed (the red captures keep the traceback of the first failing case of each node plus the summary, trimmed of the repeated parametrized cases). Each neutralization is a targeted Edit, each restore is the inverse Edit, and each green is the same node. No capture is redacted (no secrets or private URLs appear).

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| B1 | the mask in `_budget_ok`: a budget keyword inside a path span does not satisfy the budget rule | `test_e1_budget_word_only_inside_a_path_is_missing` | proven |
| B2 | the mask in `_timeout_warnings` for the flag read: a `--timeout` inside a path span is not the flag | `test_e4_timeout_flag_only_inside_a_path_warns` | proven (2 of 3 cases go red; see note) |
| B3 | the flag-token boundary: `--timeout` inside a longer word is not the flag | `test_e7_timeout_inside_a_longer_word_warns` | proven |
| K1 | the kept runner segment: a path whose last segment is exactly a runner name is still a suite command | `test_f1_runner_invoked_by_path_without_timeout_warns` | proven |
| K2 | the sentence-final rule on the timeout read: a filename followed by a sentence period is still a path span | `test_f3_sentence_final_timeout_filename_is_not_the_flag` | proven |
| K3 | the exact-name test on the last segment: only a whole runner name stays visible, not a longer segment starting with it | `test_f7_runner_name_inside_a_longer_last_segment_does_not_warn` | proven |

## B1: the mask in `_budget_ok`

- **Neutralization.** In `order_lint.py`, `masked = _mask_path_spans(text)` (inside `_budget_ok`) replaced with `masked = text`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e1_budget_word_only_inside_a_path_is_missing`
- **Red:**

```
FFF                                                                      [100%]
_____ test_e1_budget_word_only_inside_a_path_is_missing[budget/v2-files0] ______
>       assert _tokens(r) == [OL.TOKEN_BUDGET_MISSING]
E       AssertionError: assert [] == ['order-budget-missing']
E         
E         Right contains one more item: 'order-budget-missing'
(the budget/v2.md and budget2.md cases fail with the identical assertion)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e1_budget_word_only_inside_a_path_is_missing[budget/v2-files0]
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e1_budget_word_only_inside_a_path_is_missing[budget/v2.md-files1]
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e1_budget_word_only_inside_a_path_is_missing[budget2.md-files2]
3 failed in 0.21s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
    masked = _mask_path_spans(text)
    return bool(_BUDGET_AT.search(masked) or _BUDGET.search(masked))
```

- **Green:**

```
...                                                                      [100%]
3 passed in 0.20s
```

## B2: the mask in `_timeout_warnings` for the flag read

- **Neutralization.** In `order_lint.py`, `if _TIMEOUT_FLAG.search(masked):` replaced with `if _TIMEOUT_FLAG.search(text):`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e4_timeout_flag_only_inside_a_path_warns`
- **Note.** The `notes--timeout.md` case stays green under this neutralization, because the boundary regex alone rejects `--timeout` preceded by a word character; it is the `docs/--timeout` and `docs/--timeout.md` cases that bite the mask.
- **Red:**

```
FF.                                                                      [100%]
________ test_e4_timeout_flag_only_inside_a_path_warns[docs/--timeout] _________
>       assert _warned(r)
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
_______ test_e4_timeout_flag_only_inside_a_path_warns[docs/--timeout.md] _______
>       assert _warned(r)
E       AssertionError: assert False
E        +  where False = _warned({'ok': False, 'kind': 'implementer', 'findings': [{'token': 'order-path-unresolved', 'detail': 'docs/--timeout.md'}], 'checked': {'paths': 1, 'placeholders': 0}, ...})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e4_timeout_flag_only_inside_a_path_warns[docs/--timeout]
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e4_timeout_flag_only_inside_a_path_warns[docs/--timeout.md]
2 failed, 1 passed in 0.26s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
    if _TIMEOUT_FLAG.search(masked):
```

- **Green:**

```
...                                                                      [100%]
3 passed in 0.19s
```

## B3: the flag-token boundary

- **Neutralization.** In `order_lint.py`, `if _TIMEOUT_FLAG.search(masked):` replaced with `if "--timeout" in masked:`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e7_timeout_inside_a_longer_word_warns`
- **Red:**

```
FFF                                                                      [100%]
_________ test_e7_timeout_inside_a_longer_word_warns[--timeout-notes] __________
>       assert _warned(r)
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
(the --timeouts and x--timeout cases fail with the identical assertion)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e7_timeout_inside_a_longer_word_warns[--timeout-notes]
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e7_timeout_inside_a_longer_word_warns[--timeouts]
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_e7_timeout_inside_a_longer_word_warns[x--timeout]
3 failed in 0.20s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
    if _TIMEOUT_FLAG.search(masked):
```

- **Green:**

```
...                                                                      [100%]
3 passed in 0.18s
```

## K1: the kept runner segment

- **Neutralization.** In `order_lint.py`, inside `_timeout_warnings`, `masked = _mask_path_spans(text, sentence_final=True, keep_runner=True)` replaced with `masked = _mask_path_spans(text, sentence_final=True)`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_f1_runner_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_f1_runner_invoked_by_path_without_timeout_warns _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-42/test_f1_runner_invoked_by_path0')

    def test_f1_runner_invoked_by_path_without_timeout_warns(tmp_path):
        # axis: a test runner named as the last segment of a path is still a suite command — see bite-proof record i2452_order_lint
        root = _repo(tmp_path)
        r = OL.check_text("# WO\n\nRun .venv/bin/pytest -q once.\n%s" % _BUDGET_LINE, repo_root=root)
>       assert _warned(r)
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})

/home/user/wt-2452/plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:135: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_f1_runner_invoked_by_path_without_timeout_warns
1 failed in 0.20s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
    masked = _mask_path_spans(text, sentence_final=True, keep_runner=True)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 12.79s
```

## K2: the sentence-final rule on the timeout read

- **Neutralization.** In `order_lint.py`, inside `_timeout_warnings`, `masked = _mask_path_spans(text, sentence_final=True, keep_runner=True)` replaced with `masked = _mask_path_spans(text, keep_runner=True)`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_f3_sentence_final_timeout_filename_is_not_the_flag`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_f3_sentence_final_timeout_filename_is_not_the_flag ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-44/test_f3_sentence_final_timeout0')

    def test_f3_sentence_final_timeout_filename_is_not_the_flag(tmp_path):
        # axis: on the timeout read, a filename followed by a sentence period is still a path span — see bite-proof record i2452_order_lint
        root = _repo(tmp_path)
        r = OL.check_text("# WO\n\nRun pytest. Read --timeout.md.\n%s" % _BUDGET_LINE, repo_root=root)
>       assert _warned(r)
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})

/home/user/wt-2452/plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:151: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_f3_sentence_final_timeout_filename_is_not_the_flag
1 failed in 0.25s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
    masked = _mask_path_spans(text, sentence_final=True, keep_runner=True)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.16s
```

## K3: the exact-name test on the last segment

- **Neutralization.** In `order_lint.py`, inside `_mask_path_spans`, `if keep_runner and _RUNNER_NAME.fullmatch(name):` replaced with `if keep_runner and name.startswith(("pytest", "jest", "vitest")):`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_f7_runner_name_inside_a_longer_last_segment_does_not_warn`
- **Note.** K3 guards the new last-segment test, a different element from B3's `--timeout` flag boundary.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_f7_runner_name_inside_a_longer_last_segment_does_not_warn ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-46/test_f7_runner_name_inside_a_l0')

    def test_f7_runner_name_inside_a_longer_last_segment_does_not_warn(tmp_path):
        # axis: only a last path segment that is exactly a runner name stays visible, never one that merely starts with it — see bite-proof record i2452_order_lint
        root = _repo(tmp_path)
        r = OL.check_text("# WO\n\nSee bin/pytest-watch for the watcher.\n%s" % _BUDGET_LINE,
                          repo_root=root)
>       assert r["warnings"] == []
E       AssertionError: assert [{'token': 'o...l': 'pytest'}] == []
E         
E         Left contains one more item: {'token': 'order-timeout-missing', 'detail': 'pytest'}
E         Use -v to get more diff

/home/user/wt-2452/plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:183: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_f7_runner_name_inside_a_longer_last_segment_does_not_warn
1 failed in 0.25s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
            if keep_runner and _RUNNER_NAME.fullmatch(name):
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.18s
```

## Addendum (issue 2452, order O-2466-S2): every suite command word run through a path

`_RUNNER_NAME` is widened to the nine suite command words (`pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make`) with `re.I`. The run command is the one above, on a single node per capture. Each red capture below keeps the test header, the failing assert and its `where` lines, and the summary, trimmed of the `tmp_path` repr line and the nested `_run_order(...)` argument line; the harness `UV_NATIVE_TLS` line is omitted. Each neutralization is a targeted Edit and each restore is its inverse Edit. No capture is redacted (no secrets or private URLs appear). Before the change, the new tests on the unmodified code gave `7 failed, 4 passed` (G1 to G7 red; G8 and H1 to H3 green).

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| L1 | `cargo` in `_RUNNER_NAME`: a path ending in `cargo` is still a suite command | `test_g1_cargo_invoked_by_path_without_timeout_warns` | proven |
| L2 | `go` in `_RUNNER_NAME` | `test_g2_go_invoked_by_path_without_timeout_warns` | proven |
| L3 | `npm` in `_RUNNER_NAME` | `test_g3_npm_invoked_by_path_without_timeout_warns` | proven |
| L4 | `yarn` in `_RUNNER_NAME` | `test_g4_yarn_invoked_by_path_without_timeout_warns` | proven |
| L5 | `pnpm` in `_RUNNER_NAME` | `test_g5_pnpm_invoked_by_path_without_timeout_warns` | proven |
| L6 | `make` in `_RUNNER_NAME` | `test_g6_make_invoked_by_path_without_timeout_warns` | proven |
| L7 | `re.I` on `_RUNNER_NAME`: the command word is matched case-insensitively, as `_SUITE_CMD` is | `test_g7_mixed_case_runner_invoked_by_path_without_timeout_warns` | proven |
| L8 | the period-stripped `name` in the runner check: a sentence-final period after the runner name | `test_g8_runner_name_with_sentence_final_period_warns` | proven |

The healthy siblings `test_h1_bare_toolchain_path_does_not_warn`, `test_h2_longer_last_segment_does_not_warn` and `test_h3_toolchain_path_with_timeout_does_not_warn` pass before and after the change; they guard against over-warning (a bare `bin/go`, a longer last segment, a real `--timeout`) and are not themselves neutralized here (H2's axis is K3 above).

### L1: `cargo`

- **Neutralization.** `_RUNNER_NAME` line: `...|pnpm|go|cargo|make", re.I)` replaced with `...|pnpm|go|make", re.I)`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g1_cargo_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
_____________ test_g1_cargo_invoked_by_path_without_timeout_warns ______________
>       assert _warned(_run_order(tmp_path, "Run ~/.cargo/bin/cargo test once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:194: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g1_cargo_invoked_by_path_without_timeout_warns
1 failed in 0.20s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.26s
```

### L2: `go`

- **Neutralization.** `_RUNNER_NAME` line: `...|pnpm|go|cargo|make", re.I)` replaced with `...|pnpm|cargo|make", re.I)`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g2_go_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
_______________ test_g2_go_invoked_by_path_without_timeout_warns _______________
>       assert _warned(_run_order(tmp_path, "Run /usr/local/go/bin/go test ./... once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:199: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g2_go_invoked_by_path_without_timeout_warns
1 failed in 0.25s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.21s
```

### L3: `npm`

- **Neutralization.** `_RUNNER_NAME` line: `...|vitest|npm|yarn|...` replaced with `...|vitest|yarn|...` (the `npm` alternative removed).
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g3_npm_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
______________ test_g3_npm_invoked_by_path_without_timeout_warns _______________
>       assert _warned(_run_order(tmp_path, "Run ./node_modules/.bin/npm test once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:204: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g3_npm_invoked_by_path_without_timeout_warns
1 failed in 0.21s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.17s
```

### L4: `yarn`

- **Neutralization.** `_RUNNER_NAME` line: `...|npm|yarn|pnpm|...` replaced with `...|npm|pnpm|...` (the `yarn` alternative removed).
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g4_yarn_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
______________ test_g4_yarn_invoked_by_path_without_timeout_warns ______________
>       assert _warned(_run_order(tmp_path, "Run ./node_modules/.bin/yarn test once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:209: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g4_yarn_invoked_by_path_without_timeout_warns
1 failed in 0.18s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.17s
```

### L5: `pnpm`

- **Neutralization.** `_RUNNER_NAME` line: `...|yarn|pnpm|go|...` replaced with `...|yarn|go|...` (the `pnpm` alternative removed).
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g5_pnpm_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
______________ test_g5_pnpm_invoked_by_path_without_timeout_warns ______________
>       assert _warned(_run_order(tmp_path, "Run ./node_modules/.bin/pnpm test once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:214: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g5_pnpm_invoked_by_path_without_timeout_warns
1 failed in 0.22s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.20s
```

### L6: `make`

- **Neutralization.** `_RUNNER_NAME` line: `...|cargo|make", re.I)` replaced with `...|cargo", re.I)`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g6_make_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
______________ test_g6_make_invoked_by_path_without_timeout_warns ______________
>       assert _warned(_run_order(tmp_path, "Run /usr/bin/make test once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:219: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g6_make_invoked_by_path_without_timeout_warns
1 failed in 0.20s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.24s
```

### L7: `re.I`

- **Neutralization.** `_RUNNER_NAME` line: `...|cargo|make", re.I)` replaced with `...|cargo|make")` (the flag dropped).
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g7_mixed_case_runner_invoked_by_path_without_timeout_warns`
- **Red:**

```
F                                                                        [100%]
_______ test_g7_mixed_case_runner_invoked_by_path_without_timeout_warns ________
>       assert _warned(_run_order(tmp_path, "Run .venv/bin/PyTest -q once."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:225: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g7_mixed_case_runner_invoked_by_path_without_timeout_warns
1 failed in 0.22s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
_RUNNER_NAME = re.compile(r"pytest|jest|vitest|npm|yarn|pnpm|go|cargo|make", re.I)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.19s
```

### L8: the period-stripped `name` in the runner check

- **Neutralization.** In `_mask_path_spans`, `if keep_runner and _RUNNER_NAME.fullmatch(name):` replaced with `if keep_runner and _RUNNER_NAME.fullmatch(last):`.
- **Node.** `plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g8_runner_name_with_sentence_final_period_warns`
- **Red:**

```
F                                                                        [100%]
_____________ test_g8_runner_name_with_sentence_final_period_warns _____________
>       assert _warned(_run_order(tmp_path, "Then run .venv/bin/pytest."))
E       AssertionError: assert False
E        +  where False = _warned({'ok': True, 'kind': 'implementer', 'findings': [], 'checked': {'paths': 0, 'placeholders': 0}, ...})
plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py:230: AssertionError
FAILED plugins/superheroes/lib/tests/test_order_lint_path_spans_2452.py::test_g8_runner_name_with_sentence_final_period_warns
1 failed in 0.17s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `order_lint.py`:

```
            if keep_runner and _RUNNER_NAME.fullmatch(name):
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.28s
```
