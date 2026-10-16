# Bite-proof: a Canon id two different entries share puts nothing on record (C7 L3a, WO-8)

Declared guarded-element set (exactly one): the distinct-entry count in `canon_decides`.

## Element: the distinct-entry count, `finding_outcomes.py:70` (`return len(held) == 1`)

**Axis:** the number of *distinct complete entries* carrying the cited id. Two different entries
sharing an id must decide nothing; the same entry written twice is one distinct entry and still
decides. The axis line sits in each new test's docstring, not at the guard, because
`finding_outcomes.py` was outside this order's editable surface apart from the neutralization.

**Detectors (node ids confirmed by collection, 3 tests collected):**

- `plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_e4_two_different_entries_sharing_an_id_decide_nothing`
- `plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_a_ruling_citing_an_id_two_different_canon_entries_share_goes_to_the_owner`
- sibling, expected to stay green under the neutralization (pins the distinct-entry rule, not "any duplicate"):
  `plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_e4_the_same_entry_twice_is_one_distinct_entry_and_still_decides`

**Neutralization** (target asserted to occur exactly once first; original file copied to
`/tmp/claude-0/wo8-backup/finding_outcomes.py`):

```
-    return len(held) == 1
+    return len(held) >= 1
```

**Raw red** (detectors unedited; the three node ids run together, pycache redirected by the wrapper):

```
F.F                                                                      [100%]
=================================== FAILURES ===================================
__________ test_e4_two_different_entries_sharing_an_id_decide_nothing __________

    def test_e4_two_different_entries_sharing_an_id_decide_nothing():
        # axis: the distinct-entry count in canon_decides; an id held by two different complete entries
        # resolving as on record, when it must resolve for no reader
        text = _conflicting_canon()
>       assert FO.canon_decides(text, CANON_ID) is False
E       assert True is False
E        +  where True = <function canon_decides at 0x7f7e2c7e74c0>('# Canon\n\nThis file is the project\'s Canon, the record of the owner\'s decisions. Its rules live in the\nsuperheroe...d\n- **2026-01-02-abcd1234-1** · 2026-01-02 · standing · a ruling · owner\'s words: "no, stop" · where: issue thread\n', '2026-01-02-abcd1234-1')
E        +    where <function canon_decides at 0x7f7e2c7e74c0> = FO.canon_decides

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:160: AssertionError
_ test_a_ruling_citing_an_id_two_different_canon_entries_share_goes_to_the_owner _

    def test_a_ruling_citing_an_id_two_different_canon_entries_share_goes_to_the_owner():
        # axis: the write-time re-check follows canon_decides' distinct-entry count; a ruling kept
        # when two different complete entries share the id it cites
        first = canon.entry_line(CANON_ID, "2026-01-02", "standing", "a ruling", 'owner\'s words: "go"', "issue thread")
        second = canon.entry_line(CANON_ID, "2026-01-02", "standing", "a ruling", 'owner\'s words: "no, stop"', "issue thread")
        assert first != second
        sources = {"canonText": canon.HEADER + first + "\n" + second + "\n"}
        rec = build(account(findings=[ruling("r-1", CANON_ID)]), Fake(sources=sources))
        f = rec["findings"][0]
>       assert f["outcome"] == "left-for-owner"
E       AssertionError: assert 'ruling' == 'left-for-owner'
E         
E         - left-for-owner
E         + ruling

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py:374: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_e4_two_different_entries_sharing_an_id_decide_nothing
FAILED plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_a_ruling_citing_an_id_two_different_canon_entries_share_goes_to_the_owner
2 failed, 1 passed in 0.94s
```

The red is on the stated axis: a conflicting id resolving as on record (`canon_decides` returned
`True`; the writer kept the finding a `ruling`). The byte-duplicate sibling passed, as designed.

**Restore:** the inverse edit, `return len(held) >= 1` back to `return len(held) == 1`.

**Restore receipt:** the restored line, read back with `grep -n "return len(held)"`:

```
70:    return len(held) == 1
```

Supplementary: `diff /tmp/claude-0/wo8-backup/finding_outcomes.py plugins/superheroes/lib/finding_outcomes.py`
printed nothing (exit 0), and `git diff --quiet -- plugins/superheroes/lib/finding_outcomes.py`
exited 0.

**Raw green** (same three node ids, after the restore):

```
...                                                                      [100%]
3 passed in 0.85s
```

No secrets, tokens, URLs or personal data appear in these captures; nothing was redacted.
