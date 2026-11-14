# I2452 bite-proof: order lint reads its keywords outside path spans

Bite-proof record for the detectors issue 2452 adds in `order_lint.py` (`_mask_path_spans`, `_budget_ok`, `_timeout_warnings`), proven by `test_order_lint_path_spans_2452.py`.

**Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2452 -m pytest <node> -q -p no:cacheprovider`. The harness's `UV_NATIVE_TLS` deprecation line is omitted from each capture; every pytest line is as printed (the red captures keep the traceback of the first failing case of each node plus the summary, trimmed of the repeated parametrized cases). Each neutralization is a targeted Edit, each restore is the inverse Edit, and each green is the same node. No capture is redacted (no secrets or private URLs appear).

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| B1 | the mask in `_budget_ok`: a budget keyword inside a path span does not satisfy the budget rule | `test_e1_budget_word_only_inside_a_path_is_missing` | proven |
| B2 | the mask in `_timeout_warnings` for the flag read: a `--timeout` inside a path span is not the flag | `test_e4_timeout_flag_only_inside_a_path_warns` | proven (2 of 3 cases go red; see note) |
| B3 | the flag-token boundary: `--timeout` inside a longer word is not the flag | `test_e7_timeout_inside_a_longer_word_warns` | proven |

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
