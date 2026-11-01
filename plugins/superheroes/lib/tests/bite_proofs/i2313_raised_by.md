# Bite-proof record — each finding carries `raisedBy`, the run that first raised it (#2313)

Detector file: `plugins/superheroes/lib/tests/test_raised_by_2313.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_raised_by_2313.py -q -k <test> [--tb=short]`. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. No secret, token, URL or personal data appears in any capture, so nothing else is redacted. The five guarded elements are the five the order declared; none is grouped. A `-k` selector that matches a parametrized test runs every parameter, so some reds show several failures for one element.

Disclosure: the red capture of entry 1 is **incomplete**. That run was piped through `tail -30` by mistake, so only its last 30 lines were seen; the head of the output (the first six failure bodies) was not kept. Entries 2-5 are whole captures. One `-k` run (merge, before its neutralization had applied) was a wasted green run: the edit tool refused the first two `old_string`s, so the test ran against unneutralized code and passed. It proves nothing and is not used below.

## 1. The account validator's refusal (`lib/review_record.py`, `_validate`, per-finding loop)

- **Axis:** `raisedBy` is a non-blank string or absent; an empty, whitespace-only, null or non-string value is refused `review-account-invalid` naming `findings[i].raisedBy`.
- **Detector:** `test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused` (`-k test_v1_an_empty_whitespace`, 8 parameters).
- **Neutralization:** `chk(session_contract.RAISED_BY_FIELD not in f or (...` became `chk(True or session_contract.RAISED_BY_FIELD not in f or (...`.

**Raw red** (exit 1; INCOMPLETE — the last 30 lines only, from `| tail -30`):

```
        out = rr.write(put(tmp_path, acct(findings=[record_finding(**{RAISED: bad})])), str(tmp_path), RecordFake().readers())
>       assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "findings[0].raisedBy"), out
                           ^^^^^^^^^^^^^
E       KeyError: 'reason'

/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:305: KeyError
______ test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[bad7] _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_v1_an_empty_whitespace_or7')
bad = {'a': 1}

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n", None, 5, True, ["code-reviewer"], {"a": 1}])
    def test_v1_an_empty_whitespace_or_non_string_raiser_is_refused(tmp_path, bad):
        # axis: raisedBy is a non-blank string or absent
        out = rr.write(put(tmp_path, acct(findings=[record_finding(**{RAISED: bad})])), str(tmp_path), RecordFake().readers())
>       assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "findings[0].raisedBy"), out
                           ^^^^^^^^^^^^^
E       KeyError: 'reason'

/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:305: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[   ]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[\t\n]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[None]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[5]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[True]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[bad6]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_v1_an_empty_whitespace_or_non_string_raiser_is_refused[bad7]
8 failed, 49 deselected in 3.00s
```

(`KeyError: 'reason'` is the red: the write succeeded, so the result has no `reason`.)

**Restore:** the inverse edit removed `True or `.
**Restore receipt** (the restored lines, `review_record.py:741-743`):

```
        chk(session_contract.RAISED_BY_FIELD not in f or (isinstance(f[session_contract.RAISED_BY_FIELD], str)
                                                          and f[session_contract.RAISED_BY_FIELD].strip() != ""),
            f"findings[{i}].{session_contract.RAISED_BY_FIELD}")
```

**Raw green** (exit 0):

```
........                                                                 [100%]
8 passed, 49 deselected in 2.95s
```

## 2. The compile strip of a seat-sent `raisedBy` (`lib/round_driver.py`, `mechanical_compile`)

- **Axis:** a `raisedBy` the seat sent never survives compile; with neither `sources` nor `source` the field is absent.
- **Detector:** `test_raised_by_2313.py::test_c1_with_neither_sources_nor_source_the_field_is_absent` (`-k test_c1_with_neither_sources_nor_source --tb=short`, 5 parameters).
- **Neutralization:** the line `fc.pop(session_contract.RAISED_BY_FIELD, None)` was deleted (the `raiser = sources.get(id(f))` line after it stayed).

**Raw red** (exit 1):

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_ test_c1_with_neither_sources_nor_source_the_field_is_absent[premortem-reviewer] _
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:82: in test_c1_with_neither_sources_nor_source_the_field_is_absent
    assert RAISED not in out
E   AssertionError: assert 'raisedBy' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
________ test_c1_with_neither_sources_nor_source_the_field_is_absent[] _________
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:82: in test_c1_with_neither_sources_nor_source_the_field_is_absent
    assert RAISED not in out
E   AssertionError: assert 'raisedBy' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
_______ test_c1_with_neither_sources_nor_source_the_field_is_absent[  ] ________
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:82: in test_c1_with_neither_sources_nor_source_the_field_is_absent
    assert RAISED not in out
E   AssertionError: assert 'raisedBy' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
______ test_c1_with_neither_sources_nor_source_the_field_is_absent[None] _______
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:82: in test_c1_with_neither_sources_nor_source_the_field_is_absent
    assert RAISED not in out
E   AssertionError: assert 'raisedBy' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
________ test_c1_with_neither_sources_nor_source_the_field_is_absent[7] ________
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:82: in test_c1_with_neither_sources_nor_source_the_field_is_absent
    assert RAISED not in out
E   AssertionError: assert 'raisedBy' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_c1_with_neither_sources_nor_source_the_field_is_absent[premortem-reviewer]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_c1_with_neither_sources_nor_source_the_field_is_absent[]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_c1_with_neither_sources_nor_source_the_field_is_absent[  ]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_c1_with_neither_sources_nor_source_the_field_is_absent[None]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_c1_with_neither_sources_nor_source_the_field_is_absent[7]
5 failed, 52 deselected in 2.81s
```

**Restore:** the inverse edit put the deleted line back, above `raiser = sources.get(id(f))`.
**Restore receipt** (the restored lines, `round_driver.py:1198-1200`):

```
        # axis: a raiser the seat supplied itself never survives compile — only the driver's own roster key or stage name is stamped, and with neither the field is absent
        fc.pop(session_contract.RAISED_BY_FIELD, None)
        raiser = sources.get(id(f))
```

**Raw green** (exit 0):

```
.....                                                                    [100%]
5 passed, 52 deselected in 2.91s
```

## 3. The first-raiser keep in `_seed_ledger_entry` (`lib/round_driver.py`)

- **Axis:** a re-raise never changes the ledger row's first raiser, and a row with no raiser never gains one from a re-raise.
- **Detector:** `test_raised_by_2313.py::test_l1_a_re_raise_by_another_seat_keeps_the_first_raiser` and `::test_l1_an_existing_row_without_a_raiser_stays_without_one` (`-k test_l1 --tb=short`; both go red on the one neutralization).
- **Neutralization:** the guard `if isinstance(existing, dict):` over the raiser block became `if False:`.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
__________ test_l1_a_re_raise_by_another_seat_keeps_the_first_raiser ___________
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:166: in test_l1_a_re_raise_by_another_seat_keeps_the_first_raiser
    assert second[RAISED] == "code-reviewer"
E   AssertionError: assert 'premortem-reviewer' == 'code-reviewer'
E     
E     - code-reviewer
E     + premortem-reviewer
__________ test_l1_an_existing_row_without_a_raiser_stays_without_one __________
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:177: in test_l1_an_existing_row_without_a_raiser_stays_without_one
    assert RAISED not in second
E   AssertionError: assert 'raisedBy' not in {'title': 'Retry without a cap', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_l1_a_re_raise_by_another_seat_keeps_the_first_raiser
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_l1_an_existing_row_without_a_raiser_stays_without_one
2 failed, 55 deselected in 3.23s
```

**Restore:** the inverse edit put `if isinstance(existing, dict):` back.
**Restore receipt** (the restored lines, `round_driver.py:2299-2304`):

```
    if isinstance(existing, dict):
        # axis: a re-raise never changes the first raiser, and a ledger row with no raiser never gains one from it
        if session_contract.RAISED_BY_FIELD in existing:
            entry[session_contract.RAISED_BY_FIELD] = existing[session_contract.RAISED_BY_FIELD]
        else:
            entry.pop(session_contract.RAISED_BY_FIELD, None)
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed, 55 deselected in 2.85s
```

## 4. The first-raiser keep in `_merge_same_finding` (`lib/round_driver.py`)

- **Axis:** the merged row's `raisedBy` is `existing`'s, even when `incoming` wins the base on severity; `incoming` never supplies one.
- **Detector:** `test_raised_by_2313.py::test_c2_merge_same_finding_keeps_existings_raiser_when_incoming_wins` (`--tb=short`).
- **Neutralization:** the five-line `if session_contract.RAISED_BY_FIELD in existing: ... else: merged.pop(...)` block became `pass`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_c2_merge_same_finding_keeps_existings_raiser_when_incoming_wins _____
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:128: in test_c2_merge_same_finding_keeps_existings_raiser_when_incoming_wins
    assert merged["severity"] == "Critical" and merged[RAISED] == "code-reviewer"
E   AssertionError: assert ('Critical' == 'Critical'
E     
E       Critical and 'premortem-reviewer' == 'code-reviewer'
E     
E     - code-reviewer
E     + premortem-reviewer)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_c2_merge_same_finding_keeps_existings_raiser_when_incoming_wins
1 failed, 56 deselected in 2.79s
```

**Restore:** the inverse edit put the block back.
**Restore receipt** (the restored lines, `round_driver.py:1053-1058`):

```
    # axis: the first raiser survives a merge — `existing`'s, whichever side wins the base; `incoming` never supplies one and a row with none stays without
    if session_contract.RAISED_BY_FIELD in existing:
        merged[session_contract.RAISED_BY_FIELD] = existing[session_contract.RAISED_BY_FIELD]
    else:
        merged.pop(session_contract.RAISED_BY_FIELD, None)
    seqs = [f.get(session_contract.RAISED_SEQ_FIELD) for f in (existing, incoming)]
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 56 deselected in 2.82s
```

## 5. `TRANSIENT_FINDING_FIELDS` membership (`lib/session_contract.py`)

- **Axis:** `raisedBy` is a loop-stamped field kept out of `finding_content_canonical` / `content_hash_suffix`, so content identity does not vary by seat.
- **Detector:** `test_raised_by_2313.py::test_h1_two_findings_that_differ_only_in_raiser_share_a_content_hash` (`-k test_h1 --tb=short`).
- **Neutralization:** `RAISED_BY_FIELD` was deleted from the `TRANSIENT_FINDING_FIELDS` set literal (`RAISED_ROUND_FIELD, RAISED_SEQ_FIELD, DISPOSITION_SEQ_FIELD,`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_h1_two_findings_that_differ_only_in_raiser_share_a_content_hash _____
/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:323: in test_h1_two_findings_that_differ_only_in_raiser_share_a_content_hash
    assert RAISED in SC.TRANSIENT_FINDING_FIELDS
E   AssertionError: assert 'raisedBy' in frozenset({'challenge', 'disposition', 'dispositionReceipt', 'dispositionRound', 'dispositionSeq', 'evidence', ...})
E    +  where frozenset({'challenge', 'disposition', 'dispositionReceipt', 'dispositionRound', 'dispositionSeq', 'evidence', ...}) = SC.TRANSIENT_FINDING_FIELDS
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_h1_two_findings_that_differ_only_in_raiser_share_a_content_hash
1 failed, 56 deselected in 2.75s
```

The red fires on the membership assertion, which is first in the test; the hash-equality assertions after it were not reached in this run, so this red does not by itself show that they would also fail.

**Restore:** the inverse edit put `RAISED_BY_FIELD` back into the set.
**Restore receipt** (the restored lines, `session_contract.py:111-113`):

```
    RAISED_ROUND_FIELD, RAISED_SEQ_FIELD, RAISED_BY_FIELD, DISPOSITION_SEQ_FIELD,
})
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 56 deselected in 2.73s
```

## Not proven (outside the declared set)

The stamping of a panel finding by its roster seat (`test_c1_a_panel_finding_is_stamped_with_its_roster_seat_not_its_lens`, `test_c1_a_panel_fold_stamps_each_staged_finding_with_its_seat`), the stage names, the carried merge in `_with_carried`, the sweep stamp (`sweep_hit_finding`, the fold's per-part seat map), the record writer's copy in `_findings_and_merges`, `_fill`, `_carried` and the two abandoned-session recovery rows have detectors in the file (`test_c1_*`, `test_l2_*`, `test_w1_*`, `test_r1_*`, `test_r2_*`, `test_a1_*`) but no neutralization was run for them, so their bite is unproven here.
