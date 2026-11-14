# WO-2 (#2480) bite-proof — the queue-slots gate of `stack_merge.py`

Per-element bite proof for the slots gate added to `_linear_gate` in `plugins/superheroes/lib/stack_merge.py`: each guarded element is neutralized by a targeted Edit-tool edit inside `stack_merge.py`, its proving test(s) are run alone (`-k`) and must go red on the element's axis, the element is restored by the inverse edit, and the three stack_merge test files go green again. Line numbers are those of the restored file.

**Provenance:** claude (Claude Sonnet 5.5), implementer of WO-2.

**Commands.** *Red* (one per element, `<expr>` named in each entry; every red run used `--tb=line`):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2480b -m pytest plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py plugins/superheroes/lib/tests/test_stack_merge_linear.py -q -p no:cacheprovider --tb=line -k "<expr>"
```

*Green* (after each restore, the three files whole):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2480b -m pytest plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py plugins/superheroes/lib/tests/test_stack_merge_linear.py plugins/superheroes/lib/tests/test_stack_merge.py -q -p no:cacheprovider --tb=short
```

The sandbox accepted `-X pycache_prefix=...`; nothing was dropped. Every capture omits the one leading line `warning: The `UV_NATIVE_TLS` environment variable is deprecated ...`, which is uv's own notice. Nothing else is filtered or trimmed. No secret, token or private URL appears in any capture, so nothing was redacted. The restored green count is 212 passed until E-B2's detail test (`test_e4_a_dict_with_no_fits_key_says_so`, two cases) was added during this proof (disclosed under E-B), after which it is 214 passed.

**Guarded-element set.** The order declared "every `# axis:` line added or changed in `stack_merge.py`, at least the replaced linear-ok branch, the `fits is True` pass, the `slots-short` mapping and the catch-all `queue-slots-unreadable`". That is E-A to E-H below, one entry each (no equivalence classes), plus three unchanged branches that the new tests are the detectors for (E-X1 to E-X3). Elements in no entry: none left unproven.

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test(s) | Verdict |
|---|---|---|---|---|
| E-A | stack_merge.py:429-432 | a complete linear read on a queue base asks the queue for slots | `test_e1`, `test_e2`, `test_e3`, `test_e6`, `test_e7`, `..._held_slots_unreadable` | proven |
| E-B | stack_merge.py:434 (`not isinstance(slots, dict)`) | a slots answer that is not an object is `queue-slots-unreadable` | `test_e4_a_bad_argument_or_an_answer_*` | proven |
| E-B2 | stack_merge.py:434 (`"fits" not in slots`) | a dict with no `fits` key is `queue-slots-unreadable` and says so | `test_e4_a_dict_with_no_fits_key_says_so` | proven (see note) |
| E-C | stack_merge.py:438 | `fits is True` lets the merge go | `test_e1`, `test_e5_the_slot_*`, `test_e6`, `test_queue_base_with_linear_*`, `test_end_to_end_..._room_merge`, others | proven |
| E-C2 | stack_merge.py:438 | only an exact `True` passes (1, "yes" do not) | `test_e4_only_an_exact_true_fits_passes` | proven |
| E-D | stack_merge.py:441 | `slots-short` maps to `queue-slots-short` with the slots detail | `test_e2` | proven |
| E-D2 | stack_merge.py:441 (`fits is False`) | the short mapping needs `fits` exactly `False` | `test_e4_slots_short_with_a_fits_*` | proven |
| E-E | stack_merge.py:445-446 | every other slots answer is `queue-slots-unreadable`, naming reason and detail | `test_e3`, `test_e4_bad_argument_*`, `test_e4_fits_false_without_*`, `..._held_slots_unreadable` | proven |
| E-F1 | stack_merge.py:432 | the slot read gets `deadline_at=end` | `test_e5_the_slot_*` | proven |
| E-F2 | stack_merge.py:431 | the slot read gets the same `timeout` | `test_e5_the_slot_*` | proven |
| E-F3 | stack_merge.py:432 | the slot read gets the same `run` | `test_e5_the_slot_*` | proven |
| E-F4 | stack_merge.py:432 | the slot read gets the same `monotonic` | `test_e5_the_slot_*` | proven |
| E-G | stack_merge.py:431 | `layers` is the count of members at or below the top | `test_e6_*` | proven |
| E-H | stack_merge.py:431 | `branch` is the stack's `baseRefName` | `test_e7_*` | proven |
| E-X1 | stack_merge.py:485 (unchanged branch) | a slot read that spends the budget leaves the PUT unsent | `test_e5_a_slot_read_that_spends_*` | proven |
| E-X2 | stack_merge.py:423 (unchanged branch) | a base read as `queue: false` never reads slots | `test_e8_*` | proven |
| E-X3 | stack_merge.py:430 (the same branch, widened) | linearity is decided before slots (E9, E10) | `test_e9_*`, `test_e10_*` | proven |

Edges E1 (fits true merges) and E4's "only `fits is True` passes" are the E-C/E-C2 reds; E2 is E-D; E3 and E4 (bad-argument, non-dict, no `fits`) are E-E/E-B/E-B2; E5 is E-F1 to E-F4 and E-X1; E6 is E-G; E7 is E-H; E8 is E-X2; E9 and E10 are E-X3.

---

## E-A — a complete linear read on a queue base asks the queue for slots (stack_merge.py:429-432)

**neutralization:** `return None  # bite-proof` inserted as the first line of the branch (before `slots = merge_queue.slots(`), so the slots are never read.

**red** (`-k "test_e1 or test_e2 or test_e3 or test_e6 or test_e7 or held_slots_unreadable"`):
```
FFFFFF..F                                                                [100%]
=================================== FAILURES ===================================
E   AssertionError: assert ['read_member... 'check_rest'] == ['read_member...est', 'slots']
      
      Right contains one more item: 'slots'
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:241: AssertionError: assert ['read_member... 'check_rest'] == ['read_member...est', 'slots']
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert [] == [2]
      
      Right contains one more item: 2
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:365: assert [] == [2]
E   assert [] == [3]
      
      Right contains one more item: 3
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:371: assert [] == [3]
E   AssertionError: assert [] == ['release/1']
      
      Right contains one more item: 'release/1'
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:379: AssertionError: assert [] == ['release/1']
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e1_slots_fit_sends_the_put_and_merges_after_the_linear_check
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e2_slots_short_is_queue_slots_short_with_the_slots_detail_and_no_request
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e3_slots_unreadable_is_queue_slots_unreadable_naming_the_reason_and_detail
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e6_layers_is_the_count_of_members_at_or_below_the_top
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e6_layers_counts_every_member_when_the_top_is_the_last
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e7_slots_is_read_for_the_stack_base_branch
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_end_to_end_linear_layers_on_an_assumed_queue_base_are_held_slots_unreadable
7 failed, 2 passed, 61 deselected in 0.43s
```
(The two passes are the `test_e10_*` cases, which match `test_e1` as a prefix and never reach the slots branch. The end-to-end held test, with only `run` faked, goes red too, so the real `merge_queue.slots` and the recorded GraphQL refusal reach this branch.)

**restore:** the inverse edit (deleted the inserted line). **restored lines:**
```
    if linear.get("ok") is True:
        slots = merge_queue.slots(repo=repo, branch=base, layers=len(layers), timeout=timeout,
```
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
....................................................................     [100%]
212 passed in 1.09s
```

---

## E-B — a slots answer that is not an object is `queue-slots-unreadable` (stack_merge.py:434)

**neutralization:** `if not isinstance(slots, dict) or "fits" not in slots:` → `if False:  # bite-proof`

**red** (`-k "test_e4_a_bad_argument_or_an_answer"`):
```
.FFFF..                                                                  [100%]
=================================== FAILURES ===================================
E   AttributeError: 'NoneType' object has no attribute 'get'
/home/user/wt-2480/plugins/superheroes/lib/stack_merge.py:438: AttributeError: 'NoneType' object has no attribute 'get'
E   AttributeError: 'str' object has no attribute 'get'
/home/user/wt-2480/plugins/superheroes/lib/stack_merge.py:438: AttributeError: 'str' object has no attribute 'get'
E   AttributeError: 'list' object has no attribute 'get'
/home/user/wt-2480/plugins/superheroes/lib/stack_merge.py:438: AttributeError: 'list' object has no attribute 'get'
E   AttributeError: 'bool' object has no attribute 'get'
/home/user/wt-2480/plugins/superheroes/lib/stack_merge.py:438: AttributeError: 'bool' object has no attribute 'get'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_a_bad_argument_or_an_answer_that_is_not_a_fits_object_is_queue_slots_unreadable[none]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_a_bad_argument_or_an_answer_that_is_not_a_fits_object_is_queue_slots_unreadable[string]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_a_bad_argument_or_an_answer_that_is_not_a_fits_object_is_queue_slots_unreadable[list]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_a_bad_argument_or_an_answer_that_is_not_a_fits_object_is_queue_slots_unreadable[bool]
4 failed, 3 passed, 63 deselected in 0.39s
```
(The three passes are the dict cases: bad-argument, `{}`, and a dict without `fits`; under this neutralization they still end `queue-slots-unreadable` through the catch-all, which E-B2 separates.)

**restore:** the inverse edit. **restored line:** `        if not isinstance(slots, dict) or "fits" not in slots:`
**green** (after the E-B2 detail test was added, so 214):
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.00s
```
**Disclosed addition:** the first E-B red showed that a dict with no `fits` key reached the right reason through the catch-all, so `test_e4_a_dict_with_no_fits_key_says_so` (cases `empty-dict`, `dict-without-a-fits-key`) was added; it asserts the dedicated detail.

---

## E-B2 — a dict with no `fits` key is `queue-slots-unreadable` and says so (stack_merge.py:434)

**neutralization:** `if not isinstance(slots, dict) or "fits" not in slots:` → `if not isinstance(slots, dict) or False:  # bite-proof`

**red** (`-k "test_e4_a_dict_with_no_fits_key"`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'merge queue ...s: None: None' == 'merge queue ...th a fits key'
      
      - merge queue slots: the answer is not an object with a fits key
      + merge queue slots: None: None
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:304: AssertionError: assert 'merge queue ...s: None: None' == 'merge queue ...th a fits key'
E   AssertionError: assert 'merge queue ...s: None: None' == 'merge queue ...th a fits key'
      
      - merge queue slots: the answer is not an object with a fits key
      + merge queue slots: None: None
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:304: AssertionError: assert 'merge queue ...s: None: None' == 'merge queue ...th a fits key'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_a_dict_with_no_fits_key_says_so[empty-dict]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_a_dict_with_no_fits_key_says_so[dict-without-a-fits-key]
2 failed, 70 deselected in 0.40s
```
(The reason token is `queue-slots-unreadable` either way, because the catch-all answers it; the axis this half guards is the dedicated detail, which is what the test asserts.)

**restore:** the inverse edit. **restored line:** `        if not isinstance(slots, dict) or "fits" not in slots:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 0.96s
```

---

## E-C — `fits is True` lets the merge go (stack_merge.py:438)

**neutralization:** `if slots.get("fits") is True:` → `if False:  # bite-proof`

**red** (`-k "test_e1 or test_e5_the_slot or test_e6 or test_e7 or test_e8 or test_queue_base_with_linear or test_g5_queue_true_from_a_failed_read_with_linear or test_g9 or test_end_to_end_linear_layers_with_a_readable"`):
```
FFF.....FFFF                                                             [100%]
=================================== FAILURES ===================================
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:104: assert False is True
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:104: assert False is True
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:104: assert False is True
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e1_slots_fit_sends_the_put_and_merges_after_the_linear_check
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e5_the_slot_read_shares_the_one_deadline_and_the_one_run
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e6_layers_is_the_count_of_members_at_or_below_the_top
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_queue_base_with_linear_layers_sends_the_put_and_merges
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g5_queue_true_from_a_failed_read_with_linear_layers_merges
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g9_a_layer_above_the_top_carrying_a_merge_commit_is_ignored
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_end_to_end_linear_layers_with_a_readable_queue_that_has_room_merge
7 failed, 5 passed, 60 deselected in 0.46s
```
(The end-to-end room test, with only `run` faked and the unmeasured GraphQL slots body, goes red too.)

**restore:** the inverse edit. **restored line:** `        if slots.get("fits") is True:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 0.95s
```

---

## E-C2 — only an exact `True` passes (stack_merge.py:438)

**neutralization:** `if slots.get("fits") is True:` → `if slots.get("fits"):  # bite-proof`

**red** (`-k "test_e4_only_an_exact_true_fits_passes"`):
```
FFFFFF...F                                                               [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[1]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[yes]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[true]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[fits3]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[fits4]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[1.0]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_only_an_exact_true_fits_passes[no]
7 failed, 3 passed, 62 deselected in 0.38s
```
(The three passes are the falsy cases `None`, `0` and `""`, which are refused under either test.)

**restore:** the inverse edit. **restored line:** `        if slots.get("fits") is True:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 0.95s
```

---

## E-D — `slots-short` maps to `queue-slots-short` with the slots detail (stack_merge.py:441)

**neutralization:** `if slots.get("fits") is False and slots.get("reason") == merge_queue.REASON_SLOTS_SHORT:` → `if False:  # bite-proof`

**red** (`-k "test_e2"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'queue-slots-unreadable' == 'queue-slots-short'
      
      - queue-slots-short
      + queue-slots-unreadable
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:98: AssertionError: assert 'queue-slots-unreadable' == 'queue-slots-short'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e2_slots_short_is_queue_slots_short_with_the_slots_detail_and_no_request
1 failed, 71 deselected in 0.45s
```

**restore:** the inverse edit. **restored line:** `        if slots.get("fits") is False and slots.get("reason") == merge_queue.REASON_SLOTS_SHORT:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.04s
```

---

## E-D2 — the short mapping needs `fits` exactly `False` (stack_merge.py:441)

**neutralization:** `if slots.get("fits") is False and slots.get("reason") == merge_queue.REASON_SLOTS_SHORT:` → `if True and slots.get("reason") == merge_queue.REASON_SLOTS_SHORT:  # bite-proof`

**red** (`-k "test_e4_slots_short_with_a_fits"`):
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
      
      - queue-slots-unreadable
      + queue-slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:98: AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
E   AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
      
      - queue-slots-unreadable
      + queue-slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:98: AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
E   AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
      
      - queue-slots-unreadable
      + queue-slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:98: AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
E   AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
      
      - queue-slots-unreadable
      + queue-slots-short
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:98: AssertionError: assert 'queue-slots-short' == 'queue-slots-unreadable'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_slots_short_with_a_fits_that_is_not_exactly_false_is_unreadable[0]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_slots_short_with_a_fits_that_is_not_exactly_false_is_unreadable[no]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_slots_short_with_a_fits_that_is_not_exactly_false_is_unreadable[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_slots_short_with_a_fits_that_is_not_exactly_false_is_unreadable[]
4 failed, 68 deselected in 0.41s
```

**restore:** the inverse edit. **restored line:** `        if slots.get("fits") is False and slots.get("reason") == merge_queue.REASON_SLOTS_SHORT:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.09s
```

---

## E-E — every other slots answer is `queue-slots-unreadable`, naming reason and detail (stack_merge.py:445-446)

**neutralization:** the final `return (REASON_QUEUE_SLOTS_UNREADABLE, "merge queue slots: %s: %s" % (` / `slots.get("reason"), slots.get("detail")))` pair → `return None  # bite-proof`

**red** (`-k "test_e3 or test_e4_bad_argument or test_e4_fits_false_without or held_slots_unreadable"`):
```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e3_slots_unreadable_is_queue_slots_unreadable_naming_the_reason_and_detail
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_bad_argument_names_its_reason_and_detail
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_fits_false_without_the_slots_short_reason_is_unreadable[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_fits_false_without_the_slots_short_reason_is_unreadable[slots-unreadable]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e4_fits_false_without_the_slots_short_reason_is_unreadable[something-else]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_end_to_end_linear_layers_on_an_assumed_queue_base_are_held_slots_unreadable
6 failed, 66 deselected in 0.40s
```

**restore:** the inverse edit. **restored lines:**
```
        return (REASON_QUEUE_SLOTS_UNREADABLE, "merge queue slots: %s: %s" % (
            slots.get("reason"), slots.get("detail")))
```
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 0.98s
```

---

## E-F1 — the slot read gets `deadline_at=end` (stack_merge.py:432)

**neutralization:** `deadline_at=end, run=run, monotonic=monotonic)` → `deadline_at=None, run=run, monotonic=monotonic)  # bite-proof`

**red** (`-k "test_e5_the_slot"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert None == 30
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:350: assert None == 30
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e5_the_slot_read_shares_the_one_deadline_and_the_one_run
1 failed, 71 deselected in 0.49s
```

**restore:** the inverse edit. **restored line:** `                                  deadline_at=end, run=run, monotonic=monotonic)`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.13s
```

---

## E-F2 — the slot read gets the same `timeout` (stack_merge.py:431)

**neutralization:** `layers=len(layers), timeout=timeout,` → `layers=len(layers), timeout=GH_TIMEOUT,  # bite-proof`

**red** (`-k "test_e5_the_slot"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert 120 == 10
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:351: assert 120 == 10
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e5_the_slot_read_shares_the_one_deadline_and_the_one_run
1 failed, 71 deselected in 0.37s
```

**restore:** the inverse edit. **restored line:** `        slots = merge_queue.slots(repo=repo, branch=base, layers=len(layers), timeout=timeout,`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.20s
```

---

## E-F3 — the slot read gets the same `run` (stack_merge.py:432)

**neutralization:** `deadline_at=end, run=run, monotonic=monotonic)` → `deadline_at=end, run=subprocess.run, monotonic=monotonic)  # bite-proof`

**red** (`-k "test_e5_the_slot"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert <function run at 0x7f04cacccae0> is <function _make_run.<locals>._run at 0x7f04c96d3380>
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:352: assert <function run at 0x7f04cacccae0> is <function _make_run.<locals>._run at 0x7f04c96d3380>
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e5_the_slot_read_shares_the_one_deadline_and_the_one_run
1 failed, 71 deselected in 0.37s
```

**restore:** the inverse edit. **restored line:** `                                  deadline_at=end, run=run, monotonic=monotonic)`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.05s
```

---

## E-F4 — the slot read gets the same `monotonic` (stack_merge.py:432)

**neutralization:** `deadline_at=end, run=run, monotonic=monotonic)` → `deadline_at=end, run=run, monotonic=time.monotonic)  # bite-proof`

**red** (`-k "test_e5_the_slot"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert <built-in function monotonic> == monotonic
     +  where monotonic = <test_stack_merge_slots_2480._Clock object at 0x7ff987942630>.monotonic
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:353: assert <built-in function monotonic> == monotonic
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e5_the_slot_read_shares_the_one_deadline_and_the_one_run
1 failed, 71 deselected in 0.39s
```

**restore:** the inverse edit. **restored line:** `                                  deadline_at=end, run=run, monotonic=monotonic)`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.12s
```

---

## E-G — `layers` is the count of members at or below the top (stack_merge.py:431)

**neutralization:** `layers=len(layers), timeout=timeout,` → `layers=len(layers) + 1, timeout=timeout,  # bite-proof`

**red** (`-k "test_e6"`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   assert [3] == [2]
      
      At index 0 diff: 3 != 2
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:377: assert [3] == [2]
E   assert [4] == [3]
      
      At index 0 diff: 4 != 3
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:383: assert [4] == [3]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e6_layers_is_the_count_of_members_at_or_below_the_top
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e6_layers_counts_every_member_when_the_top_is_the_last
2 failed, 70 deselected in 0.41s
```

**restore:** the inverse edit. **restored line:** `        slots = merge_queue.slots(repo=repo, branch=base, layers=len(layers), timeout=timeout,`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.17s
```

---

## E-H — `branch` is the stack's `baseRefName` (stack_merge.py:431)

**neutralization:** `branch=base,` → `branch="main",  # bite-proof` (on the `merge_queue.slots(` line)

**red** (`-k "test_e7"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert ['main'] == ['release/1']
      
      At index 0 diff: 'main' != 'release/1'
      Use -v to get more diff
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:391: AssertionError: assert ['main'] == ['release/1']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e7_slots_is_read_for_the_stack_base_branch
1 failed, 71 deselected in 0.36s
```

**restore:** the inverse edit. **restored line:** `        slots = merge_queue.slots(repo=repo, branch=base, layers=len(layers), timeout=timeout,`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.08s
```

---

## E-X1 — a slot read that spends the budget leaves the PUT unsent (stack_merge.py:485, unchanged branch)

**neutralization:** `if put_left <= 0:` → `if False:  # bite-proof`

**red** (`-k "test_e5_a_slot_read"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e5_a_slot_read_that_spends_the_budget_leaves_the_put_unsent
1 failed, 71 deselected in 0.36s
```

**restore:** the inverse edit. **restored line:** `    if put_left <= 0:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.10s
```

---

## E-X2 — a base read as `queue: false` never reads slots (stack_merge.py:423, unchanged branch)

**neutralization:** `if queue.get("queue") is False:` → `if False:  # bite-proof`

**red** (`-k "test_e8"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert False is True
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:104: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e8_a_base_read_as_queue_false_never_reads_slots_and_merges
1 failed, 71 deselected in 0.37s
```

**restore:** the inverse edit. **restored line:** `    if queue.get("queue") is False:`
**green:**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.04s
```

---

## E-X3 — linearity is decided before slots (stack_merge.py:430)

**neutralization:** `if linear.get("ok") is True:` → `if True:  # bite-proof` (the slot read now runs after any commit-read answer)

**red** (`-k "test_e9 or test_e10"`):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
E   assert True is False
/home/user/wt-2480/plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py:96: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e9_a_stack_that_is_not_linear_on_a_queue_base_never_reads_slots
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e10_a_commit_read_that_is_unreadable_never_reads_slots[linearity-unreadable]
FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_e10_a_commit_read_that_is_unreadable_never_reads_slots[bad-argument]
3 failed, 69 deselected in 0.43s
```

**restore:** the inverse edit. **restored line:** `    if linear.get("ok") is True:`
**green (the last of the proof):**
```
........................................................................ [ 33%]
........................................................................ [ 67%]
......................................................................   [100%]
214 passed in 1.09s
```

---

## Restore receipt

A search for `bite-proof` over `plugins/superheroes/lib/stack_merge.py` after the last restore returns no matches, so no neutralization is left in the source. Every restore was the inverse edit through the Edit tool; no `git checkout`, `git restore`, `git reset` or `git stash` was used. The restored gate (lines 429-446) was read back and carries the five `# axis:` comments and the lines quoted in each entry above.
