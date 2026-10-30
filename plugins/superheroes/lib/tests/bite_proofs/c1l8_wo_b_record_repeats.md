# C1-L8 WO-B record-repeats bite-proof

Detector: `plugins/superheroes/lib/tests/test_review_record_repeats_c1l8.py`. Six guarded elements, H1 to H6, declared by
the order. One neutralization, one red and one green per element, each by a targeted edit undone by the inverse edit.
Every run used this command from the worktree root, narrowed to the detector node(s) with `-k`:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-c1l8-b -m pytest plugins/superheroes/lib/tests/test_review_record_repeats_c1l8.py -q -n 4 -k "<node>"
```

Redaction: none needed; the captures hold no secrets, tokens or private URLs. The `UV_NATIVE_TLS` warning line and the
`bringing up nodes...` lines are kept as printed where quoted. Long tracebacks are cut to the decisive lines; each cut
says what was elided.

Restore receipt shape: the work is uncommitted in the worktree, so `git status --porcelain` cannot show a clean file; the
restored lines are quoted back instead (by `grep -n`), and each green run follows the restore.

## H1: J4's carried-key admission

**Guarded element:** `review_record.py` `_wrong_ungraded`, the `via in carried` term of `through`. Axis: a kept
shown-wrong repeat passes through an earlier finding the latest earlier record lists as shown-wrong.

**Neutralization:** `(via in carried or via in closed_here)` became `(False or via in closed_here)`.

**Raw red** (nodes `test_j4_a_kept_shown_wrong_repeat_passes_through_the_carried…` and `test_j5_a_session_record_over_a_carried…`; 2 failed; tracebacks trimmed to the assertion lines):

```
FF                                                                       [100%]
_ test_j4_a_kept_shown_wrong_repeat_passes_through_the_carried_earlier_finding _
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[1] is shown-wrong without the verifier's grade"}
_ test_j5_a_session_record_over_a_carried_earlier_finding_and_its_kept_shown_wrong_repeat_holds_both _
>       rec, _ = session_record(second_root, [again], fake)
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
2 failed in 3.82s
```

**Restore:** inverse edit. **Restore receipt:** `2376:        through = via is not None and via != _key(f) and (via in carried or via in closed_here)`.

**Raw green:**

```
..                                                                       [100%]
2 passed in 1.09s
```

## H2: J4's narrowness

**Guarded element:** `review_record.py` `_wrong_ungraded`, the `through` expression. Axis: only a mark naming a carried key
or another finding verifier-closed in this account admits; a mark alone admits nothing.

**Neutralization:** `through = via is not None and via != _key(f) and (...)` became
`through = isinstance(f.get("repeatOf"), dict)` (any shown-wrong row carrying a `repeatOf` object is admitted).

**Raw red** (node `test_j4_a_shown_wrong_repeat_naming_anything_else`; 3 failed, 1 passed — the `no-mark` case is judged as
before and still passes; the three failures are the same assertion, shown once; the red is a `KeyError` because the
writer returned ok and so has no `detail`):

```
.FFF                                                                     [100%]
>       assert (out["ok"], out["detail"]) == (False, "findings[1] is shown-wrong without the verifier's grade")
E       KeyError: 'detail'
FAILED ...::test_j4_a_shown_wrong_repeat_naming_anything_else_is_still_refused[a-key-no-finding-holds]
FAILED ...::test_j4_a_shown_wrong_repeat_naming_anything_else_is_still_refused[a-finding-that-is-not-shown-wrong]
FAILED ...::test_j4_a_shown_wrong_repeat_naming_anything_else_is_still_refused[its-own-key]
3 failed, 1 passed in 1.11s
```

**Restore:** inverse edit. **Restore receipt:** `2376:        through = via is not None and via != _key(f) and (via in carried or via in closed_here)`.

**Raw green:**

```
....                                                                     [100%]
4 passed in 1.03s
```

## H3: J3 in `_finding_lines`

**Guarded element:** `review_record.py` `_finding_lines`, the `repeat_held_elsewhere` call. Axis: a held left-for-owner
repeat adds no leftover line.

**Neutralization:** `elif f["outcome"] == _LEFT_FOR_OWNER and not repeat_held_elsewhere(f, findings):` became
`elif f["outcome"] == _LEFT_FOR_OWNER:`.

**Raw red** (node `test_j3_a_held_repeat_adds_no_leftover_line`; 1 failed):

```
F                                                                        [100%]
>       assert rec["whatIsMissing"] == [rr.leftover_line(earlier)]
E       assert ["finding e-1...r's decision"] == ["finding e-1...r's decision"]
E         Left contains one more item: "finding r-1 waits for the owner's decision"
1 failed in 1.07s
```

**Restore:** inverse edit. **Restore receipt:** `1140:        elif f["outcome"] == _LEFT_FOR_OWNER and not repeat_held_elsewhere(f, findings):`.

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.14s
```

## H4: J3 in `leftForOwner`

**Guarded element:** `review_record.py` `build_record`, the `leftForOwner` list. Axis: a held repeat is not listed beside the
earlier finding that holds it.

**Neutralization:** the comprehension's condition lost `and not repeat_held_elsewhere(f, findings)`.

**Raw red** (node `test_j3_a_held_repeat_adds_no_left_for_owner_entry…`; 1 failed):

```
F                                                                        [100%]
>       assert rec["leftForOwner"] == ["e-1"]
E       AssertionError: assert ['e-1', 'r-1'] == ['e-1']
E         Left contains one more item: 'r-1'
1 failed in 1.03s
```

**Restore:** inverse edit. **Restore receipt:** `1412:                         if f.get("outcome") == _LEFT_FOR_OWNER and not repeat_held_elsewhere(f, findings)],`.

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.03s
```

## H5: J3 in the sheet's card creation

**Guarded element:** `pr_sheet.py` card loop (`if f["outcome"] != _LEFT or review_record.repeat_held_elsewhere(...)`). Axis:
a held repeat adds no sheet card. The advisor-entry requirement (the earlier loop) still skips the repeat, so the
neutralized card loop reaches a repeat with no leftovers entry.

**Neutralization:** `if f["outcome"] != _LEFT or review_record.repeat_held_elsewhere(f, r["findings"]):` became
`if f["outcome"] != _LEFT:`.

**Raw red** (node `test_j3_a_held_repeat_adds_no_sheet_card…`; 1 failed; the `build` docstring and the requirement loop
printed in the traceback are elided):

```
F                                                                        [100%]
>       sheet = sheet_build(records, advisor)
...
                call = _leftover_call(kind, r["pr"], f, leftovers)
>               options = _options(call["options"], words, True)
E               KeyError: 'options'
/home/user/wt-2212-b/plugins/superheroes/lib/pr_sheet.py:1121: KeyError
1 failed in 1.13s
```

**Restore:** inverse edit. **Restore receipt:** `1112:            if f["outcome"] != _LEFT or review_record.repeat_held_elsewhere(f, r["findings"]):`.

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.04s
```

## H6: J1's `repeatKept` branch

**Guarded element:** `review_record_session.py` `_decide`, the `repeatKept` branch. Axis: a kept repeat reads the outcome and
reason it keeps, before any disposition logic.

**Neutralization:** `if isinstance(kept, dict) and kept.get("outcome") in` became `if False and isinstance(kept, dict) and kept.get("outcome") in`.

**Raw red** (node `test_j1_a_kept_repeat_reads_the_outcome_and_reason_it_keeps`; 5 failed, one per outcome; the first 80 lines of the
output were read, which shows four of the five failures in full and the fifth, `ruling`, cut at its assertion; the failing
summary line was not captured):

```
FFFFF                                                                    [100%]
>       assert decide(row) == (outcome, KEPT_REASON.format(outcome))
E       AssertionError: assert ('fixed', 'fi...d in round 2') == ('left-for-ow...t-for-owner)')
E       AssertionError: assert ('fixed', 'fi...d in round 2') == ('shown-wrong...shown-wrong)')
E       AssertionError: assert ('fixed', 'fi...d in round 2') == ('craft', 're...come (craft)')
E       AssertionError: assert ('fixed', 'fi...d in round 2') == ('fixed', 're...come (fixed)')   # reason differs
(the `ruling` case: cut)
```

**Restore:** inverse edit. **Restore receipt:** `406:    if isinstance(kept, dict) and kept.get("outcome") in review_findings_schema.OUTCOMES and _text(kept.get("reason")):`.

**Raw green:**

```
.....                                                                    [100%]
5 passed in 1.02s
```
