# Bite-proof record: C1-L5 WO-B, a ran panel reviewer with no well-formed read list reads nothing (#2209)

Detector: `plugins/superheroes/lib/tests/test_read_parts_c1l5.py`. Guarded surface: `review_record_session.py`
line 367, the `readParts` fill for a panel row whose seat ran. Command for each half:
`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_read_parts_c1l5.py -q -k <test>`; each run
selected exactly one test (`1 failed, 37 deselected` / `1 passed, 37 deselected`).
Nothing in the captures below needed redaction (no secrets, tokens, URLs or PII); the `UV_NATIVE_TLS` warning line the
launcher prints is dropped from each capture.

Unmodified line 367, quoted for the restore receipt:
`            row["readParts"] = reported if review_record._items_fault(reported, review_record._part_fault) is None else []`

## E1: the `[]` fill for a ran panel row whose payload has no `readParts`

- **guarded element:** `review_record_session.py:367`, the `[]` branch taken when `reported` is `None`. Axis: a
  ran panel reviewer that reported no list shows `readParts: []`, never an absent key.
- **neutralization:** line 367 became two lines, leaving the key off when the payload has none:
  ```
              if reported is not None:
                  row["readParts"] = reported if review_record._items_fault(reported, review_record._part_fault) is None else []
  ```
- **guarding test:** `test_a_ran_panel_reviewer_with_no_list_shows_nothing_read`
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_a_ran_panel_reviewer_with_no_list_shows_nothing_read ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_ran_panel_reviewer_with0')

    def test_a_ran_panel_reviewer_with_no_list_shows_nothing_read(tmp_path):
        # axis: E1 a panel reviewer that ran and reported no list shows readParts [], never an absent key
        rows = _rows(_round_one(tmp_path))
>       assert rows["security-reviewer (round 1)"].get("readParts", ABSENT) == []
E       AssertionError: assert '<no readParts key>' == []
E        +  where '<no readParts key>' = <built-in method get of dict object at 0x7fba011a3880>('readParts', '<no readParts key>')
E        +    where <built-in method get of dict object at 0x7fba011a3880> = {'name': 'security-reviewer (round 1)', 'planned': True, 'ran': True, 'vendor': 'codex', ...}.get

/home/user/wt-2209/plugins/superheroes/lib/tests/test_read_parts_c1l5.py:244: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_read_parts_c1l5.py::test_a_ran_panel_reviewer_with_no_list_shows_nothing_read
1 failed, 37 deselected in 2.56s
```

- **restore:** the inverse edit, folding the two lines back into the single line 367.
- **restore receipt:** a grep on `row\["readParts"\]` after both proofs returned exactly
  `367:            row["readParts"] = reported if review_record._items_fault(reported, review_record._part_fault) is None else []`;
  `git status --porcelain` and `git diff --stat` over `review_record_session.py` printed nothing (the file is byte-identical
  to its committed state).
- **raw green:**

```
.                                                                        [100%]
1 passed, 37 deselected in 2.46s
```

## E2: the `[]` fill for a malformed `readParts`

- **guarded element:** `review_record_session.py:367`, the `[]` branch taken when `_items_fault(reported, _part_fault)`
  is not `None`. Axis: a ran panel reviewer that reported a list the record would refuse shows `readParts: []`, the bad
  list never reaches the row.
- **neutralization:** line 367 became `            row["readParts"] = reported if reported is not None else []`
  (a malformed list is copied through unchanged).
- **guarding test:** `test_a_ran_panel_reviewer_with_a_malformed_list_shows_nothing_read`
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_ran_panel_reviewer_with_a_malformed_list_shows_nothing_read ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_a_ran_panel_reviewer_with0')

    def test_a_ran_panel_reviewer_with_a_malformed_list_shows_nothing_read(tmp_path):
        # axis: E2 a panel reviewer that ran and reported a list the record would refuse shows readParts []
        rows = _rows(_round_one(tmp_path))
>       assert rows["test-role (round 1)"].get("readParts", ABSENT) == []
E       AssertionError: assert [{'file': 'a....s': [[5, 2]]}] == []
E         
E         Left contains one more item: {'file': 'a.py', 'lines': [[5, 2]]}
E         Use -v to get more diff

/home/user/wt-2209/plugins/superheroes/lib/tests/test_read_parts_c1l5.py:250: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_read_parts_c1l5.py::test_a_ran_panel_reviewer_with_a_malformed_list_shows_nothing_read
1 failed, 37 deselected in 2.63s
```

- **restore:** the inverse edit, putting line 367 back to its original text.
- **restore receipt:** same as E1 (taken once, after both proofs): the grep returned the unmodified line 367 quoted
  above, and `git status --porcelain` / `git diff --stat` over the file printed nothing.
- **raw green:**

```
.                                                                        [100%]
1 passed, 37 deselected in 2.59s
```
