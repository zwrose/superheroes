# C1 L1 WO-A bite-proof record: the review record writer's new optional parts

Thirteen entries: the twelve guarded elements the order declared (BP1-BP12) and one the order named as a detector but
left out of its set (BP13, the claim-check exclusion). None is grouped. Every red and green below is the raw output of
the single test node run alone (`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "<node>" -q`,
run from the worktree root); nothing is filtered. Each neutralization was one targeted `Edit` to
`plugins/superheroes/lib/review_record.py`, restored by the inverse `Edit` (the restored line is quoted back in each
entry). The captures are unredacted: they hold no secret, token or private URL.

Node file for every entry: `plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py`.

What the reds do and do not show, stated once:

- Each `_validate` element is guarded by one `chk(...)` line over a fault helper. The neutralization replaces that
  `chk` condition with `True`, so every aspect of the element is neutralized together. The node loops over the
  malformed shapes of that element, so the red names the first shape the table lists; the other shapes are not each
  neutralized on their own. The same shapes also run one by one in the `test_e2_` to `test_e8_` parametrized nodes.
- BP11 neutralizes the computing half of the element (the tokens read). The second half (the trim steps never touch
  `cost`) has a guarding assertion in `test_e12_the_trim_steps_keep_every_rows_cost` but was not neutralized: the test
  budget of 40 commands ran out of room for a second pair. It is listed as unproven by neutralization.
- BP12 neutralizes the record-JSON side (an absent key written as `null`). The summary side (no heading when absent) is
  guarded by the same node but was not neutralized; it is listed as unproven by neutralization.
- The order's guarded-element set omitted the claim-check exclusion although the order names it as a detector it adds;
  BP13 is that element, run the same way.

## BP1. `rounds.extraAudit` validation

- Axis: `why` non-blank, no other key.
- Neutralization (`review_record.py`, `_validate`): `chk(isinstance(extra, dict) and set(extra) == {"why"} and _nb(extra["why"]), "rounds.extraAudit")` became `chk(True, "rounds.extraAudit")`.
- Node: `test_bp1_extra_audit_is_a_reason_and_nothing_else`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_bp1_extra_audit_is_a_reason_and_nothing_else _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_bp1_extra_audit_is_a_reas0')

    def test_bp1_extra_audit_is_a_reason_and_nothing_else(tmp_path):
        # axis: rounds.extraAudit refuses a blank or missing reason and any other key
>       every_variant_refused(tmp_path, "extraAudit")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:183: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_bp1_extra_audit_is_a_reas0')
path = 'rounds.extraAudit'
over = {'rounds': {'count': 3, 'cap': 4, 'stoppedAtCap': False, 'extraAudit': {'why': '  '}}}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('rounds.extraAudit', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp1_extra_audit_is_a_reason_and_nothing_else
1 failed in 2.01s
```

Restore: the inverse edit. Restored line quoted back:

```
        chk(isinstance(extra, dict) and set(extra) == {"why"} and _nb(extra["why"]), "rounds.extraAudit")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.86s
```

## BP2. `rerunChecks` validation

- Axis: exactly two runs; the exit code goes with the status.
- Neutralization: `chk(fault is None, f"rerunChecks{fault}")` became `chk(True, f"rerunChecks{fault}")`.
- Node: `test_bp2_a_rerun_check_has_exactly_two_coherent_runs`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_bp2_a_rerun_check_has_exactly_two_coherent_runs _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_bp2_a_rerun_check_has_exa0')

    def test_bp2_a_rerun_check_has_exactly_two_coherent_runs(tmp_path):
        # axis: rerunChecks refuses a run count other than two and an exit code that does not match the status
>       every_variant_refused(tmp_path, "rerunChecks")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:188: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_bp2_a_rerun_check_has_exa0')
path = 'rerunChecks', over = {'rerunChecks': 'x'}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('rerunChecks', {'ok': False, 'reason': 'review-record-internal-error', 'detail': "AttributeError: 'str' object has no attribute 'get'"})
E       assert (False, 'revi...ternal-error') == (False, 'revi...ount-invalid')
E         
E         At index 1 diff: 'review-record-internal-error' != 'review-account-invalid'
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp2_a_rerun_check_has_exactly_two_coherent_runs
1 failed in 1.54s
```

Restore: the inverse edit. Restored line quoted back:

```
        chk(fault is None, f"rerunChecks{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.32s
```

## BP3. `synthesisRounds` validation

- Axis: distinct ints >= 1, ascending.
- Neutralization: the two-line `chk(isinstance(sr, list) and all(_is_int(n) and n >= 1 for n in sr) and all(x < y for x, y in zip(sr, sr[1:])), "synthesisRounds")` became `chk(True, "synthesisRounds")`.
- Node: `test_bp3_synthesis_rounds_are_distinct_ascending_rounds`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_bp3_synthesis_rounds_are_distinct_ascending_rounds ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_bp3_synthesis_rounds_are_0')

    def test_bp3_synthesis_rounds_are_distinct_ascending_rounds(tmp_path):
        # axis: synthesisRounds refuses non-ints, bools, rounds below 1, repeats and a descending order
>       every_variant_refused(tmp_path, "synthesisRounds")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:193: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_bp3_synthesis_rounds_are_0')
path = 'synthesisRounds', over = {'synthesisRounds': 1}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('synthesisRounds', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp3_synthesis_rounds_are_distinct_ascending_rounds
1 failed in 1.49s
```

Restore: the inverse edit. Restored lines quoted back:

```
        chk(isinstance(sr, list) and all(_is_int(n) and n >= 1 for n in sr)
            and all(x < y for x, y in zip(sr, sr[1:])), "synthesisRounds")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.76s
```

## BP4. `outsideThisPR` validation

- Axis: the sweep id goes with the source kind; hits are non-empty.
- Neutralization: `chk(fault is None, f"outsideThisPR{fault}")` became `chk(True, f"outsideThisPR{fault}")`.
- Node: `test_bp4_an_outside_entry_names_its_source_and_a_hit`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_bp4_an_outside_entry_names_its_source_and_a_hit _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_bp4_an_outside_entry_name0')

    def test_bp4_an_outside_entry_names_its_source_and_a_hit(tmp_path):
        # axis: outsideThisPR refuses a sweep with no sweep id, a reviewer with one, and an entry with no hit
>       every_variant_refused(tmp_path, "outsideThisPR")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:198: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_bp4_an_outside_entry_name0')
path = 'outsideThisPR', over = {'outsideThisPR': {}}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('outsideThisPR', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp4_an_outside_entry_names_its_source_and_a_hit
1 failed in 1.51s
```

Restore: the inverse edit. Restored line quoted back:

```
        chk(fault is None, f"outsideThisPR{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.76s
```

## BP5. `unreadShare` validation

- Axis: unread <= countable; every range is 1 <= start <= end.
- Neutralization: `chk(fault is None, f"unreadShare{fault}")` became `chk(True, f"unreadShare{fault}")`.
- Node: `test_bp5_the_unread_share_is_within_the_countable_lines`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_bp5_the_unread_share_is_within_the_countable_lines ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_bp5_the_unread_share_is_w0')

    def test_bp5_the_unread_share_is_within_the_countable_lines(tmp_path):
        # axis: unreadShare refuses unread above countable and a range that is not 1 <= start <= end
>       every_variant_refused(tmp_path, "unreadShare")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:203: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_bp5_the_unread_share_is_w0')
path = 'unreadShare', over = {'unreadShare': []}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('unreadShare', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp5_the_unread_share_is_within_the_countable_lines
1 failed in 1.62s
```

Restore: the inverse edit. Restored line quoted back:

```
        chk(fault is None, f"unreadShare{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.45s
```

## BP6. `readParts` validation

- Axis: a list of files with real line ranges.
- Neutralization: `chk(fault is None, f"reviewers[{i}].readParts{fault}")` became `chk(True, f"reviewers[{i}].readParts{fault}")`.
- Node: `test_bp6_read_parts_are_files_with_real_ranges`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_bp6_read_parts_are_files_with_real_ranges ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_bp6_read_parts_are_files_0')

    def test_bp6_read_parts_are_files_with_real_ranges(tmp_path):
        # axis: readParts refuses a non-list, a blank file and a range that is not 1 <= start <= end
>       every_variant_refused(tmp_path, "readParts")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:208: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_bp6_read_parts_are_files_0')
path = 'reviewers[0].readParts'
over = {'reviewers': [{'name': 'code-reviewer', 'vendor': 'codex', 'model': 'gpt-5.6-sol', 'planned': True, ...}]}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('reviewers[0].readParts', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp6_read_parts_are_files_with_real_ranges
1 failed in 1.34s
```

Restore: the inverse edit. Restored line quoted back:

```
            chk(fault is None, f"reviewers[{i}].readParts{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.41s
```

## BP7. `grade` validation

- Axis: the verdict vocabulary; a non-blank reason.
- Neutralization: `chk(fault is None, f"findings[{i}].grade{fault}")` became `chk(True, f"findings[{i}].grade{fault}")`.
- Node: `test_bp7_a_grade_is_a_verdict_with_a_reason`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_bp7_a_grade_is_a_verdict_with_a_reason __________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_bp7_a_grade_is_a_verdict_0')

    def test_bp7_a_grade_is_a_verdict_with_a_reason(tmp_path):
        # axis: grade refuses a verdict outside the vocabulary and a blank reason
>       every_variant_refused(tmp_path, "grade")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:213: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_bp7_a_grade_is_a_verdict_0')
path = 'findings[0].grade.verdict'
over = {'findings': [{'id': 'code-001', 'title': 't', 'severity': 'Minor', 'file': 'a.py', ...}]}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('findings[0].grade.verdict', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp7_a_grade_is_a_verdict_with_a_reason
1 failed in 1.95s
```

Restore: the inverse edit. Restored line quoted back:

```
            chk(fault is None, f"findings[{i}].grade{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.46s
```

## BP8. `repeatOf.findingKey` required

- Axis: a repeat names the earlier finding by its stored key.
- Neutralization (`_repeat_fault`): `if not _nb(g.get("findingKey")):` became `if False:` (the narrow edit: only the findingKey condition, not the whole `repeatOf` check).
- Node: `test_bp8_a_repeat_names_the_earlier_finding_by_its_key`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_bp8_a_repeat_names_the_earlier_finding_by_its_key ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_bp8_a_repeat_names_the_ea0')

    def test_bp8_a_repeat_names_the_earlier_finding_by_its_key(tmp_path):
        # axis: repeatOf refuses a missing, blank or non-string findingKey
        for edge, path, over in BAD["repeatOf"]:
            if edge == "E8":
>               refused(tmp_path, path, over)

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:220: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_bp8_a_repeat_names_the_ea0')
path = 'findings[0].repeatOf.findingKey'
over = {'findings': [{'id': 'code-001', 'title': 't', 'severity': 'Minor', 'file': 'a.py', ...}]}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('findings[0].repeatOf.findingKey', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp8_a_repeat_names_the_earlier_finding_by_its_key
1 failed in 1.84s
```

Restore: the inverse edit. Restored lines quoted back:

```
    if not _nb(g.get("findingKey")):
        return ".findingKey"
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.46s
```

## BP9. `breakItRuns` validation

- Axis: the exit code goes with the status.
- Neutralization: `chk(fault is None, f"findings[{i}].breakItRuns{fault}")` became `chk(True, f"findings[{i}].breakItRuns{fault}")`.
- Node: `test_bp9_a_break_it_run_has_an_exit_code_exactly_when_it_ran`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_bp9_a_break_it_run_has_an_exit_code_exactly_when_it_ran _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_bp9_a_break_it_run_has_an0')

    def test_bp9_a_break_it_run_has_an_exit_code_exactly_when_it_ran(tmp_path):
        # axis: breakItRuns refuses an exit code that does not match the status, a bool exit code and a blank test
>       every_variant_refused(tmp_path, "breakItRuns")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:225: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_bp9_a_break_it_run_has_an0')
path = 'findings[0].breakItRuns'
over = {'findings': [{'id': 'code-001', 'title': 't', 'severity': 'Minor', 'file': 'a.py', ...}]}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('findings[0].breakItRuns', {'ok': False, 'reason': 'review-record-internal-error', 'detail': "AttributeError: 'str' object has no attribute 'get'"})
E       assert (False, 'revi...ternal-error') == (False, 'revi...ount-invalid')
E         
E         At index 1 diff: 'review-record-internal-error' != 'review-account-invalid'
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp9_a_break_it_run_has_an_exit_code_exactly_when_it_ran
1 failed in 1.58s
```

Restore: the inverse edit. Restored line quoted back:

```
            chk(fault is None, f"findings[{i}].breakItRuns{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.45s
```

## BP10. `kindOfMistake` validation

- Axis: a kind and well-formed places.
- Neutralization: `chk(fault is None, f"findings[{i}].kindOfMistake{fault}")` became `chk(True, f"findings[{i}].kindOfMistake{fault}")`.
- Node: `test_bp10_a_kind_of_mistake_names_its_kind_and_places`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_bp10_a_kind_of_mistake_names_its_kind_and_places _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_bp10_a_kind_of_mistake_na0')

    def test_bp10_a_kind_of_mistake_names_its_kind_and_places(tmp_path):
        # axis: kindOfMistake refuses a blank kind, a missing places list and a place with no file
>       every_variant_refused(tmp_path, "kindOfMistake")

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:230: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:171: in every_variant_refused
    refused(tmp_path, path, over)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_bp10_a_kind_of_mistake_na0')
path = 'findings[0].kindOfMistake.kind'
over = {'findings': [{'id': 'code-001', 'title': 't', 'severity': 'Minor', 'file': 'a.py', ...}]}

    def refused(tmp_path, path, over):
        fake = Fake()
        out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
>       assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
E       AssertionError: ('findings[0].kindOfMistake.kind', {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...})
E       assert (True, None) == (False, 'revi...ount-invalid')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:164: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_bp10_a_kind_of_mistake_names_its_kind_and_places
1 failed in 1.78s
```

Restore: the inverse edit. Restored line quoted back:

```
            chk(fault is None, f"findings[{i}].kindOfMistake{fault}")
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.45s
```

## BP11. `cost` computed from the credited engine record (computing half only)

- Axis: a row's cost is read from the run record that credited it; a bool or absent measure is null.
- Neutralization (`_reviewer`): `out["cost"] = {"tokens": obs.get("tokens") if _is_int(obs.get("tokens")) else None,` became `out["cost"] = {"tokens": None,`.
- Node: `test_the_cost_of_a_credited_row_comes_from_its_engine_record`
- Not neutralized: the trim steps never touching `cost` (see the note at the top).

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_cost_of_a_credited_row_comes_from_its_engine_record _________

    def test_the_cost_of_a_credited_row_comes_from_its_engine_record():
        # axis: cost is read from the credited run's observation, tokens as an int and minutes as wallSeconds / 60 to one place
        record = build(account(reviewers=[reviewer("a"), reviewer("b"), reviewer("c", ran=False, runDir=None)]),
                       Fake(runs={"/run/a": (dict(GOOD_RUN, observation={"tokens": 100, "wallSeconds": 125, "read": "engaged"}), None)}))
>       assert costs(record) == [{"tokens": 100, "minutes": 2.1}, {"tokens": 100, "minutes": 2.0},
                                 {"tokens": None, "minutes": None}]
E       AssertionError: assert [{'tokens': N...nutes': None}] == [{'tokens': 1...nutes': None}]
E         
E         At index 0 diff: {'tokens': None, 'minutes': 2.1} != {'tokens': 100, 'minutes': 2.1}
E         Use -v to get more diff

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:497: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_the_cost_of_a_credited_row_comes_from_its_engine_record
1 failed in 1.51s
```

Restore: the inverse edit. Restored line quoted back:

```
    out["cost"] = {"tokens": obs.get("tokens") if _is_int(obs.get("tokens")) else None,
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.56s
```

## BP12. Absent add-on keys leave no JSON key (record side only)

- Axis: an add-on part shows in the record exactly when the account carries it.
- Neutralization (`build_record`): `**{k: a[k] for k in _ROUND_PARTS if k in a},` became `**{k: a.get(k) for k in _ROUND_PARTS},`.
- Node: `test_dod_an_account_with_no_add_on_field_renders_nothing_of_them`
- Not neutralized: the summary side (no heading when the part is absent), see the note at the top.

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_dod_an_account_with_no_add_on_field_renders_nothing_of_them _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_dod_an_account_with_no_ad0')

    def test_dod_an_account_with_no_add_on_field_renders_nothing_of_them(tmp_path):
        # axis: absent add-on parts leave no heading and no JSON key — see bite-proof record c1l1_wo_a_record_seam
        record = build(account(findings=[finding("F-1")], rounds=ROUNDS))
        summary = rr._summary(record, 0)
        for text in ("Outside this PR", "kind of mistake", "Left unread", "Re-run after", "Extra audit round"):
            assert text not in summary, text
        for key in ("outsideThisPR", "unreadShare", "rerunChecks", "synthesisRounds"):
>           assert key not in record, key
E           AssertionError: outsideThisPR
E           assert 'outsideThisPR' not in {'schema': 'review-record/1', 'pr': 7, 'sessionId': 's1', 'lane': {'value': 'full', 'source': 'reported by the session', 'reason': 'big'}, ...}

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:403: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_dod_an_account_with_no_add_on_field_renders_nothing_of_them
1 failed in 1.26s
```

Restore: the inverse edit. Restored line quoted back:

```
        **{k: a[k] for k in _ROUND_PARTS if k in a},
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.56s
```

## BP13. The claim-check exclusion for the findings block, the outside list and the reviewer header

- Axis: those lines carry reviewers' and the session's own text, so they are left out of the claim check by line object; every other line is still checked.
- Neutralization (`_summary`, the `_assert_no_bug_free_claim` call): `... and l not in wider_lines and all(l is not q for q in quoted_lines)))` became `... and l not in wider_lines))`.
- Node: `test_e16_the_findings_block_and_the_outside_list_are_out_of_the_claim_check`

Red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e16_the_findings_block_and_the_outside_list_are_out_of_the_claim_check __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_e16_the_findings_block_an0')

    def test_e16_the_findings_block_and_the_outside_list_are_out_of_the_claim_check(tmp_path):
        # axis: a grade reason and a hit title are reviewers' own text, so the phrase in them does not refuse the write — see bite-proof record c1l1_wo_a_record_seam
        out, fake = write_posted(
            tmp_path, findings=[finding(grade={"verdict": "plausible", "reason": "the author calls it bug-free"},
                                        kindOfMistake={"kind": "no bugs here claim", "places": []})],
            outsideThisPR=[outside(hits=[hit(title="a bug free claim")])])
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-record-forbidden-claim', 'detail': 'no bugs'}
E       assert False

/home/user/wt/build/plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py:595: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_seam_c1l1.py::test_e16_the_findings_block_and_the_outside_list_are_out_of_the_claim_check
1 failed in 1.61s
```

Restore: the inverse edit. Restored line quoted back:

```
                  and l is not transit_line and l not in wider_lines and all(l is not q for q in quoted_lines)))
```

Green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.72s
```
