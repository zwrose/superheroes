# I2489 WO-1 bite-proof — an audit answers each finding merged into its target

**Provenance:** claude / sonnet-5.5 (implementer, work order WO-1b). Detector file: `plugins/superheroes/lib/tests/test_merged_member_audit_2489.py`.
Worktree `/home/user/wt-2489-wo1`, branch `wo/2489-1`, head at the start `ebd816b0`.
Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-pyc -m pytest plugins/superheroes/lib/tests/test_merged_member_audit_2489.py -q -p no:cacheprovider -k <selector>`,
the detector unedited, one selector per run. Each neutralization is one targeted Edit on one source file, undone by the inverse Edit.
The restore receipt is the restored lines quoted back from a Grep, plus `git status --porcelain <neutralized file>`, which printed nothing for each of the four files.
Captures are far under the 32 KiB / 128 KiB ceilings.
Redaction: the E4 red capture below carries a synthetic credential-like test value (built at run time in the test from `"sk-" + "a" * 48`); it is shortened in this record to `sk-<a x48>` and the long echoes of it are elided.
Nothing else was redacted. Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line.

## Guarded elements (declared in the order)

| ID | Element and axis | Neutralized at | Detector |
|---|---|---|---|
| E1 | `audits.judge_members` counts a member fixed only on an answer `fixed: true`; an unanswered member reads not fixed | `audits.py:611` | `test_edge1_members_absent_or_null_is_no_shape_fault_and_every_member_reads_unanswered` |
| E2 | `audits.member_answers_fault`'s `fixed` must be exactly a boolean | `audits.py:559` | `test_edge4_fixed_that_is_not_exactly_a_boolean_is_a_shape_fault` |
| E3 | the members shape check in `round_driver._audit_result_entry_fault` refuses a malformed `members` at submit | `round_driver.py:7954` | `test_the_submit_guard_refuses_each_bad_members_shape_and_accepts_a_good_or_absent_one` |
| E4 | `engine_adapter._scrub_ruling_object` scrubs each member answer's free-text `why` | `engine_adapter.py:1994` | `test_edge10_a_credential_like_value_in_a_member_why_is_scrubbed_and_id_and_fixed_are_unchanged` |

Four elements, four neutralizations, four reds. No grouping, no element left unproven.

## E1 — an unanswered member reads not fixed

**neutralization** (`audits.py:611`): `fixed = answers.get(mid) is True` → `fixed = answers.get(mid, True) is True  # E1 NEUTRALIZED` (an unanswered member counts fixed).

**raw red** (`-k test_edge1_members_absent_or_null`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge1_members_absent_or_null_is_no_shape_fault_and_every_member_reads_unanswered _

    def test_edge1_members_absent_or_null_is_no_shape_fault_and_every_member_reads_unanswered():
        # axis: a member counts fixed only when an answer says `fixed: true`, so an absent or null `members` leaves every member unfixed — see bite-proof record i2489_member_answers
        target = _target("m1", "m2")
        for result in (_result(target), dict(_result(target), members=None)):
            assert audits.member_answers_fault(result) is None
            judged = audits.judge_members(target, result)
>           assert judged["rows"] == [_unanswered("m1"), _unanswered("m2")]
E           AssertionError: assert [{'id': 'm1',... 'why': None}] == [{'id': 'm1',... 'why': None}]
E             
E             At index 0 diff: {'id': 'm1', 'fixed': True, 'why': None} != {'id': 'm1', 'fixed': False, 'why': None}
E             Use -v to get more diff

/home/user/wt-2489-wo1/plugins/superheroes/lib/tests/test_merged_member_audit_2489.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_audit_2489.py::test_edge1_members_absent_or_null_is_no_shape_fault_and_every_member_reads_unanswered
1 failed, 12 deselected in 0.43s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `fixed = answers\.get\(mid\)|NEUTRALIZED` over `audits.py`: `611:        fixed = answers.get(mid) is True` and nothing for `NEUTRALIZED`; `git status --porcelain plugins/superheroes/lib/audits.py` printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 12 deselected in 1.27s
```

## E2 — `fixed` must be exactly a boolean

**neutralization** (`audits.py:559`): `if not isinstance(row.get("fixed"), bool):` → `if False and not isinstance(row.get("fixed"), bool):  # E2 NEUTRALIZED`.

**raw red** (`-k test_edge4_fixed_that_is_not_exactly_a_boolean`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_edge4_fixed_that_is_not_exactly_a_boolean_is_a_shape_fault ________

    def test_edge4_fixed_that_is_not_exactly_a_boolean_is_a_shape_fault():
        # axis: `fixed` must be exactly true or false — a string or a number is not an answer — see bite-proof record i2489_member_answers
        for bad in ("true", "false", "yes", 1, 0, None):
            fault = audits.member_answers_fault({"members": [{"id": "m1", "fixed": bad, "why": "w"}]})
>           assert fault == "`members[0]` `fixed` is not true or false", bad
E           AssertionError: true
E           assert None == '`members[0]` `fixed` is not true or false'

/home/user/wt-2489-wo1/plugins/superheroes/lib/tests/test_merged_member_audit_2489.py:106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_audit_2489.py::test_edge4_fixed_that_is_not_exactly_a_boolean_is_a_shape_fault
1 failed, 12 deselected in 0.91s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `fixed. is not true or false|NEUTRALIZED` over `audits.py`: `559:    if not isinstance(row.get("fixed"), bool):` then `560:        return "`fixed` is not true or false"` (the other hit, `502`/`503`, is the `places` check), nothing for `NEUTRALIZED`; `git status --porcelain plugins/superheroes/lib/audits.py` printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 12 deselected in 0.39s
```

## E3 — the submit guard refuses a malformed `members`

**neutralization** (`round_driver.py:7954`): `if members_fault is not None:` → `if False and members_fault is not None:  # E3 NEUTRALIZED` (the shape check is skipped).
The payload contract alone did not refuse the first bad shape (`"m1"`, a string), so this turns the detector red; E3 is not shadowed by the contract.

**raw red** (`-k test_the_submit_guard_refuses_each_bad_members_shape`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_submit_guard_refuses_each_bad_members_shape_and_accepts_a_good_or_absent_one _

    def test_the_submit_guard_refuses_each_bad_members_shape_and_accepts_a_good_or_absent_one():
        # axis: the submit guard refuses a malformed `members` answer through the judge the fold uses — see bite-proof record i2489_member_answers
        target = _target("m1")
        good = {"results": [_result(target, [_answer("m1")], ruling="not-discharged")]}
        assert RD.audit_results_fault(good, [target]) is None
        assert RD.audit_results_fault({"results": [_result(target, ruling="not-discharged")]}, [target]) is None
        entry = good["results"][0]
        for bad in ("m1", {"id": "m1"}, ["m1"], [None], [{"fixed": True, "why": "w"}],
                    [{"id": "", "fixed": True, "why": "w"}], [{"id": "m1", "fixed": "true", "why": "w"}],
                    [{"id": "m1", "fixed": 1, "why": "w"}], [{"id": "m1", "fixed": True}],
                    [{"id": "m1", "fixed": True, "why": "  "}], [{"id": "m1", "fixed": True, "why": 3}]):
            fault = RD.audit_results_fault({"results": [dict(entry, members=bad)]}, [target])
>           assert fault is not None and "members" in fault, bad
E           AssertionError: m1
E           assert (None is not None)

/home/user/wt-2489-wo1/plugins/superheroes/lib/tests/test_merged_member_audit_2489.py:255: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_audit_2489.py::test_the_submit_guard_refuses_each_bad_members_shape_and_accepts_a_good_or_absent_one
1 failed, 12 deselected in 0.35s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `members_fault|NEUTRALIZED` over `round_driver.py`: `7953:    members_fault = audits.member_answers_fault(entry)`, `7954:    if members_fault is not None:`, and the message line `7956`, nothing for `NEUTRALIZED`; `git status --porcelain plugins/superheroes/lib/round_driver.py` printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 12 deselected in 0.35s
```

## E4 — the scrub of each member answer's `why`

**neutralization** (`engine_adapter.py:1994-1996`): the branch `out[field] = [_scrub_mapping(x) if isinstance(x, dict) else _scrub_finding_value(x) for x in val]` → `out[field] = val` (line suffixed `# E4 NEUTRALIZED`), so `members` passes through unscrubbed.

**raw red** (`-k test_edge10_a_credential_like_value`; the credential-like test value is shortened to `sk-<a x48>`, redacted as stated above, and the diff echo lines that repeat it are elided):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge10_a_credential_like_value_in_a_member_why_is_scrubbed_and_id_and_fixed_are_unchanged _

    def test_edge10_a_credential_like_value_in_a_member_why_is_scrubbed_and_id_and_fixed_are_unchanged():
        # axis: `members[].why` is free text the auditor wrote, so it is scrubbed at the parse boundary like `newIssues` — see bite-proof record i2489_member_answers
        secret = "sk-" + "a" * 48
        ruling = {"id": "f1", "ruling": "discharged", "reason": "resolved in diff", "checks": CHECKS,
                  "members": [{"id": "m1", "fixed": True, "why": "the log line printed token %s before" % secret},
                              {"id": "m2", "fixed": False, "why": "still open"}]}
        res = EA.parse_result("codex", "review", json.dumps(ruling))
        assert res["ok"] is True and res["resultKind"] == "ruling"
        members = res["ruling"]["members"]
>       assert secret not in json.dumps(res)
E       assert 'sk-<a x48>' not in '{"ok": true...igated": []}'
E         [… the value is contained in the serialized result unscrubbed; the repeated echo lines are elided and redacted …]

/home/user/wt-2489-wo1/plugins/superheroes/lib/tests/test_merged_member_audit_2489.py:221: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_audit_2489.py::test_edge10_a_credential_like_value_in_a_member_why_is_scrubbed_and_id_and_fixed_are_unchanged
1 failed, 12 deselected in 0.41s
```

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `field == "members"|NEUTRALIZED` over `engine_adapter.py`:
```
1994:        elif field == "members" and isinstance(val, list):
1995-            out[field] = [_scrub_mapping(x) if isinstance(x, dict) else _scrub_finding_value(x)
1996-                          for x in val]
```
and nothing for `NEUTRALIZED`; `git status --porcelain plugins/superheroes/lib/engine_adapter.py` printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 12 deselected in 0.36s
```

## Final run — nothing neutralized

The seven files named in the order (`test_merged_member_audit_2489.py`, `test_engine_result_channel.py`, `test_audits.py`, `test_c1l10_audit_checks.py`, `test_c4_kind_of_mistake.py`, `test_apply_audit_results_characterization_2418.py`, `test_engine_adapter.py`), `-q -n auto`:
```
825 passed in 12.27s
```
(The same run before the four neutralizations also gave `825 passed`; it followed adding `"members": None,` beside the three `"places": None,` lines of `_valid_review_branch()` in `test_engine_result_channel.py`.)
The golden characterization `test_apply_audit_results_characterization_2418.py` is in that run.
