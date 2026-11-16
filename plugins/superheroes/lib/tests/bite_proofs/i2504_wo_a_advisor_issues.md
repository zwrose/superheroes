# #2504 bite-proof — calibration item 20 `advisorIssues` (WO-A: validator, total reader, read path)

Per-element bite-proof for the detectors in `plugins/superheroes/lib/tests/test_advisor_issues_2504.py`. Each element was neutralized with one targeted, reversible edit to production code (never to a test), the guarding test(s) ran alone and went red, the edit was undone by the inverse edit, the restored line was quoted back, and the same selection ran green. No test file was edited between a red and its green.

Command for every run (from the worktree root; `<sel>` is the `-k` selection named in each section):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2504a -m pytest plugins/superheroes/lib/tests/test_advisor_issues_2504.py -q -p no:cacheprovider -k <sel>
```

Declared guarded-element set: E1–E6, R1–R4, V1 (11 elements). Redaction: none needed; local temp paths are left as printed. Each capture below omits only the first line the runner prints, `warning: The UV_NATIVE_TLS environment variable is deprecated ...`; everything else is verbatim.

`P` = `plugins/superheroes/lib/project_config.py`, `C` = `plugins/superheroes/lib/core_md.py`.

## Summary

| ID | Guarded element | Axis | Neutralization | Selection | Red |
|---|---|---|---|---|---|
| E1 | `P::_validate_advisor_issues` not-a-dict refusal | value is not a dict | `if not isinstance(value, dict):` → `if False and not isinstance(value, dict):` | `test_e1` | 1 failed (`test_e1_null_and_scalar_refuse`), 1 passed |
| E2 | `P::_validate_advisor_issues` exact key set | missing or extra key | `if set(value) != {...}:` → `if False and set(value) != {...}:` | `test_e2` | 2 failed |
| E3 | `P::_validate_advisor_issues` collector positive int | non-int, zero, negative, bool | `if not _positive_int(collector):` → `if False and not _positive_int(collector):` | `test_e3` | 2 failed |
| E4 | `P::_validate_advisor_issues` inboxes list of positive ints | non-list, bad entry | the whole condition wrapped as `if False and (...)` | `test_e4` | 3 failed |
| E5 | `P::_validate_advisor_issues` duplicate inbox | same number twice | `if len(set(inboxes)) != len(inboxes):` → `if False and ...` | `test_e5` | 1 failed |
| E6 | `P::_validate_advisor_issues` inbox equals collector | collector is also an inbox | `if collector in inboxes:` → `if False and collector in inboxes:` | `test_e6` | 1 failed |
| R1 | `C::read_project_config_value` non-object `projectConfiguration` | reads unreadable, never a missing key | `if PROJECT_CONFIGURATION_KEY in block and ...` → `if False and PROJECT_CONFIGURATION_KEY in block and ...` | `test_r1` | `'unset' == 'unreadable'` |
| R2 | `P::_advisor_issues_resolve` stored `null` | a present null reads unreadable, never unset | `if not got["present"]:` → `if not got["present"] or got["value"] is None:` | `test_r2` | `{'status': 'unset'} != {'status': 'unreadable'}` |
| R3 | `C::read_project_config_value` malformed `verifyCommand` | reads unreadable, never "nothing declared" | the `except VerifyCommandMalformed` return → `return dict(base)` | `test_r3` | `'unset' == 'unreadable'` |
| R4 | `C::read_project_config_value` duplicate core key (two layers) | reads unreadable, never last-value-wins | both duplicate-key layers disabled together (quoted below) | `test_r4` | detail `core-md-unparseable: json block is not an object ...` != `duplicate-core-key:advisorIssues` |
| V1 | `P::_advisor_issues_entry` unreadable → `malformed: True` | `read()` reports unreadable item 20 as malformed, not unset | `"malformed": True` → `"malformed": False` in the unreadable branch | `"test_v1 and object"` (the non-object case) | `assert False is True` |

All six `-k` selections use the file `test_advisor_issues_2504.py`. A malformed `verifyCommand` through `get_item` / `view` is not covered by V1: `read()` raises `VerifyCommandMalformed` there for every item today (existing behaviour, out of scope); R3 proves that case at the `advisor_issues` / `read_project_config_value` level.

Findings from the proofs:

- E1: `test_e1_not_a_dict_refuses` (a list value) stays green under the E1 neutralization, because E2 also refuses a list. The test that bites is `test_e1_null_and_scalar_refuse`, which goes red because `set(None)` raises `TypeError`.
- E2 (missing key) and E4 (non-list `inboxes`) go red as a raised `KeyError` / `TypeError` rather than a wrong verdict; the extra-key and bad-entry cases go red on `{'action': 'written'} != {'action': 'refused'}`.
- R4: with both duplicate-key layers disabled, the read still reports `unreadable` through a third path: `_loads_rejecting_duplicate_keys` returns no block for a duplicate, so the "json block is not an object" branch fires. `test_r4` therefore bites only on the `detail` string (`duplicate-core-key:advisorIssues`), not on `status`. The status-level protection against "last value wins" rests on that third path.

## E1 — not-a-dict refusal

Guarded element: `P:387` `_validate_advisor_issues`, `# axis: E1 the value is not a dict`.

Neutralization: `if not isinstance(value, dict):` → `if False and not isinstance(value, dict):`.

Raw red (`-k test_e1`):

```
.F                                                                       [100%]
=================================== FAILURES ===================================
________________________ test_e1_null_and_scalar_refuse ________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_e1_null_and_scalar_refuse0')

    def test_e1_null_and_scalar_refuse(tmp_path):
        for value in (None, 11, "11"):
>           assert PC.validate_item_value(PC._item_by_slug(SLUG), value) == "malformed-value"
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:163: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:430: in validate_item_value
    return validator(value)
           ^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

value = None

    def _validate_advisor_issues(value):
        # axis: E1 the value is not a dict — see bite-proof record i2504_wo_a_advisor_issues E1
        if False and not isinstance(value, dict):
            return REASON_MALFORMED_VALUE
        # axis: E2 the key set is not exactly collector and inboxes (missing or extra key) — see bite-proof record i2504_wo_a_advisor_issues E2
>       if set(value) != {"collector", "inboxes"}:
           ^^^^^^^^^^
E       TypeError: 'NoneType' object is not iterable

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:390: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e1_null_and_scalar_refuse
1 failed, 1 passed, 55 deselected in 0.67s
```

Restore: inverse edit. Restored line quoted back (`P:387`): `    if not isinstance(value, dict):`.

Raw green (`-k test_e1`):

```
..                                                                       [100%]
2 passed, 55 deselected in 0.70s
```

## E2 — exact key set

Guarded element: `P:390` `_validate_advisor_issues`, `# axis: E2 the key set is not exactly collector and inboxes`.

Neutralization: `if set(value) != {"collector", "inboxes"}:` → `if False and set(value) != {"collector", "inboxes"}:`.

Raw red (`-k test_e2`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________________________ test_e2_missing_key_refuses __________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_e2_missing_key_refuses0')

    def test_e2_missing_key_refuses(tmp_path):
>       _assert_set_refused_and_unchanged(tmp_path, {"collector": 11})

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:167: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:151: in _assert_set_refused_and_unchanged
    got = PC.set_item(repo, SLUG, value, root=store)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:1107: in set_item
    reason = validate_item_value(item, value)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:430: in validate_item_value
    return validator(value)
           ^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

value = {'collector': 11}

    def _validate_advisor_issues(value):
        # axis: E1 the value is not a dict — see bite-proof record i2504_wo_a_advisor_issues E1
        if not isinstance(value, dict):
            return REASON_MALFORMED_VALUE
        # axis: E2 the key set is not exactly collector and inboxes (missing or extra key) — see bite-proof record i2504_wo_a_advisor_issues E2
        if False and set(value) != {"collector", "inboxes"}:
            return REASON_MALFORMED_VALUE
        collector = value["collector"]
        # axis: E3 the collector is not a positive int, a bool included — see bite-proof record i2504_wo_a_advisor_issues E3
        if not _positive_int(collector):
            return REASON_MALFORMED_VALUE
>       inboxes = value["inboxes"]
                  ^^^^^^^^^^^^^^^^
E       KeyError: 'inboxes'

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:396: KeyError
__________________________ test_e2_extra_key_refuses ___________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_e2_extra_key_refuses0')
value = {'collector': 11, 'inboxes': [], 'note': 'x'}

    def _assert_set_refused_and_unchanged(tmp_path, value):
        repo, store = _setup_repo(tmp_path)
        before = _core_text(repo, store)
        got = PC.set_item(repo, SLUG, value, root=store)
>       assert got == {"action": "refused", "reason": "malformed-value"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...formed-value'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'malformed-value'}
E         Use -v to get more diff

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e2_missing_key_refuses
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e2_extra_key_refuses
2 failed, 55 deselected in 4.10s
```

Restore: inverse edit. Restored line quoted back (`P:390`): `    if set(value) != {"collector", "inboxes"}:`.

Raw green (`-k test_e2`):

```
..                                                                       [100%]
2 passed, 55 deselected in 0.99s
```

## E3 — collector positive int

Guarded element: `P:394` `_validate_advisor_issues`, `# axis: E3 the collector is not a positive int, a bool included`.

Neutralization: `if not _positive_int(collector):` → `if False and not _positive_int(collector):`.

Raw red (`-k test_e3`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________________ test_e3_collector_not_a_positive_int_refuses _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_e3_collector_not_a_positi0')

    def test_e3_collector_not_a_positive_int_refuses(tmp_path):
>       _assert_set_refused_and_unchanged(tmp_path, {"collector": "11", "inboxes": []})

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:175: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_e3_collector_not_a_positi0')
value = {'collector': '11', 'inboxes': []}

    def _assert_set_refused_and_unchanged(tmp_path, value):
        repo, store = _setup_repo(tmp_path)
        before = _core_text(repo, store)
        got = PC.set_item(repo, SLUG, value, root=store)
>       assert got == {"action": "refused", "reason": "malformed-value"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...formed-value'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'malformed-value'}
E         Use -v to get more diff

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:152: AssertionError
_______________ test_e3_collector_zero_negative_and_bool_refuse ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_e3_collector_zero_negativ0')

    def test_e3_collector_zero_negative_and_bool_refuse(tmp_path):
        item = PC._item_by_slug(SLUG)
        for bad in (0, -3, True, 1.5, None):
>           assert PC.validate_item_value(item, {"collector": bad, "inboxes": []}) == "malformed-value"
E           AssertionError: assert None == 'malformed-value'
E            +  where None = <function validate_item_value at 0x7f86b151e5c0>({'number': 20, 'slug': 'advisorIssues', 'name': 'Advisor issues', 'home': 'projectConfiguration', ...}, {'collector': 0, 'inboxes': []})
E            +    where <function validate_item_value at 0x7f86b151e5c0> = PC.validate_item_value

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:181: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e3_collector_not_a_positive_int_refuses
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e3_collector_zero_negative_and_bool_refuse
2 failed, 55 deselected in 0.94s
```

Restore: inverse edit. Restored line quoted back (`P:394`): `    if not _positive_int(collector):`.

Raw green (`-k test_e3`):

```
..                                                                       [100%]
2 passed, 55 deselected in 0.66s
```

## E4 — inboxes a list of positive ints

Guarded element: `P:398` `_validate_advisor_issues`, `# axis: E4 inboxes is not a list, or an entry is not a positive int`.

Neutralization: `if not isinstance(inboxes, list) or not all(_positive_int(n) for n in inboxes):` → `if False and (not isinstance(inboxes, list) or not all(_positive_int(n) for n in inboxes)):`.

Raw red (`-k test_e4`):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
______________________ test_e4_inboxes_not_a_list_refuses ______________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_e4_inboxes_not_a_list_ref0')

    def test_e4_inboxes_not_a_list_refuses(tmp_path):
>       _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": 12})

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:185: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:151: in _assert_set_refused_and_unchanged
    got = PC.set_item(repo, SLUG, value, root=store)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:1107: in set_item
    reason = validate_item_value(item, value)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:430: in validate_item_value
    return validator(value)
           ^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

value = {'collector': 11, 'inboxes': 12}

    def _validate_advisor_issues(value):
        # axis: E1 the value is not a dict — see bite-proof record i2504_wo_a_advisor_issues E1
        if not isinstance(value, dict):
            return REASON_MALFORMED_VALUE
        # axis: E2 the key set is not exactly collector and inboxes (missing or extra key) — see bite-proof record i2504_wo_a_advisor_issues E2
        if set(value) != {"collector", "inboxes"}:
            return REASON_MALFORMED_VALUE
        collector = value["collector"]
        # axis: E3 the collector is not a positive int, a bool included — see bite-proof record i2504_wo_a_advisor_issues E3
        if not _positive_int(collector):
            return REASON_MALFORMED_VALUE
        inboxes = value["inboxes"]
        # axis: E4 inboxes is not a list, or an entry is not a positive int — see bite-proof record i2504_wo_a_advisor_issues E4
        if False and (not isinstance(inboxes, list) or not all(_positive_int(n) for n in inboxes)):
            return REASON_MALFORMED_VALUE
        # axis: E5 inboxes holds the same number twice — see bite-proof record i2504_wo_a_advisor_issues E5
>       if len(set(inboxes)) != len(inboxes):
               ^^^^^^^^^^^^
E       TypeError: 'int' object is not iterable

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/project_config.py:401: TypeError
________________ test_e4_inbox_entry_not_a_positive_int_refuses ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_e4_inbox_entry_not_a_posi0')
value = {'collector': 11, 'inboxes': [12, '13']}

    def _assert_set_refused_and_unchanged(tmp_path, value):
        repo, store = _setup_repo(tmp_path)
        before = _core_text(repo, store)
        got = PC.set_item(repo, SLUG, value, root=store)
>       assert got == {"action": "refused", "reason": "malformed-value"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...formed-value'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'malformed-value'}
E         Use -v to get more diff

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:152: AssertionError
___________________ test_e4_inbox_entry_zero_or_bool_refuses ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_e4_inbox_entry_zero_or_bo0')

    def test_e4_inbox_entry_zero_or_bool_refuses(tmp_path):
        item = PC._item_by_slug(SLUG)
        for bad in (0, -1, True):
>           assert PC.validate_item_value(item, {"collector": 11, "inboxes": [12, bad]}) == "malformed-value"
E           AssertionError: assert None == 'malformed-value'
E            +  where None = <function validate_item_value at 0x7f6bdf926700>({'number': 20, 'slug': 'advisorIssues', 'name': 'Advisor issues', 'home': 'projectConfiguration', ...}, {'collector': 11, 'inboxes': [12, 0]})
E            +    where <function validate_item_value at 0x7f6bdf926700> = PC.validate_item_value

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:195: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e4_inboxes_not_a_list_refuses
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e4_inbox_entry_not_a_positive_int_refuses
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e4_inbox_entry_zero_or_bool_refuses
3 failed, 54 deselected in 1.27s
```

Restore: inverse edit. Restored line quoted back (`P:398`): `    if not isinstance(inboxes, list) or not all(_positive_int(n) for n in inboxes):`.

Raw green (`-k test_e4`):

```
...                                                                      [100%]
3 passed, 54 deselected in 1.04s
```

## E5 — duplicate inbox number

Guarded element: `P:401` `_validate_advisor_issues`, `# axis: E5 inboxes holds the same number twice`.

Neutralization: `if len(set(inboxes)) != len(inboxes):` → `if False and len(set(inboxes)) != len(inboxes):`.

Raw red (`-k test_e5`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_e5_duplicate_inbox_refuses ________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_e5_duplicate_inbox_refuse0')

    def test_e5_duplicate_inbox_refuses(tmp_path):
>       _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": [12, 13, 12]})

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:199: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_e5_duplicate_inbox_refuse0')
value = {'collector': 11, 'inboxes': [12, 13, 12]}

    def _assert_set_refused_and_unchanged(tmp_path, value):
        repo, store = _setup_repo(tmp_path)
        before = _core_text(repo, store)
        got = PC.set_item(repo, SLUG, value, root=store)
>       assert got == {"action": "refused", "reason": "malformed-value"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...formed-value'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'malformed-value'}
E         Use -v to get more diff

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e5_duplicate_inbox_refuses
1 failed, 56 deselected in 0.96s
```

Restore: inverse edit. Restored line quoted back (`P:401`): `    if len(set(inboxes)) != len(inboxes):`.

Raw green (`-k test_e5`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.76s
```

## E6 — inbox equals the collector

Guarded element: `P:404` `_validate_advisor_issues`, `# axis: E6 an inbox number equals the collector number`.

Neutralization: `if collector in inboxes:` → `if False and collector in inboxes:`.

Raw red (`-k test_e6`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_e6_inbox_equal_to_collector_refuses ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_e6_inbox_equal_to_collect0')

    def test_e6_inbox_equal_to_collector_refuses(tmp_path):
>       _assert_set_refused_and_unchanged(tmp_path, {"collector": 11, "inboxes": [12, 11]})

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:203: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_e6_inbox_equal_to_collect0')
value = {'collector': 11, 'inboxes': [12, 11]}

    def _assert_set_refused_and_unchanged(tmp_path, value):
        repo, store = _setup_repo(tmp_path)
        before = _core_text(repo, store)
        got = PC.set_item(repo, SLUG, value, root=store)
>       assert got == {"action": "refused", "reason": "malformed-value"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...formed-value'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'malformed-value'}
E         Use -v to get more diff

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_e6_inbox_equal_to_collector_refuses
1 failed, 56 deselected in 0.85s
```

Restore: inverse edit. Restored line quoted back (`P:404`): `    if collector in inboxes:`.

Raw green (`-k test_e6`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.85s
```

## R1 — non-object `projectConfiguration` reads unreadable

Guarded element: `C:2311` `read_project_config_value`, the `# axis: a projectConfiguration that is not an object reads unreadable, never as a missing key` branch; guarded by `test_r1_non_object_project_configuration_is_unreadable`.

Neutralization: `if PROJECT_CONFIGURATION_KEY in block and not isinstance(` → `if False and PROJECT_CONFIGURATION_KEY in block and not isinstance(`.

Raw red (`-k test_r1`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_r1_non_object_project_configuration_is_unreadable ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_r1_non_object_project_con0')

    def test_r1_non_object_project_configuration_is_unreadable(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _make_non_object(repo, store)
        got = PC.advisor_issues(repo, root=store)
        assert set(got) == _RESULT_KEYS
>       assert got["status"] == "unreadable"
E       AssertionError: assert 'unset' == 'unreadable'
E         
E         - unreadable
E         + unset

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:284: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_r1_non_object_project_configuration_is_unreadable
1 failed, 56 deselected in 0.78s
```

Restore: inverse edit. Restored line quoted back (`C:2311`): `        if PROJECT_CONFIGURATION_KEY in block and not isinstance(`.

Raw green (`-k test_r1`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.63s
```

## R2 — stored `null` reads unreadable

Guarded element: `P:593` `_advisor_issues_resolve`, the `present` branch (a present `null` goes on to the validator, which refuses it); guarded by `test_r2_stored_null_is_unreadable_malformed`.

Neutralization: `if not got["present"]:` → `if not got["present"] or got["value"] is None:`.

Raw red (`-k test_r2`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_r2_stored_null_is_unreadable_malformed __________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_r2_stored_null_is_unreada0')

    def test_r2_stored_null_is_unreadable_malformed(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _make_stored_null(repo, store)
        assert json.loads(CM._JSON_BLOCK.search(_core_text(repo, store)).group(1))[
            "projectConfiguration"][SLUG] is None
        got = PC.advisor_issues(repo, root=store)
>       assert got == {"status": "unreadable", "collector": None, "inboxes": [],
                       "reason": "malformed-value", "detail": None}
E       AssertionError: assert {'status': 'u...n': None, ...} == {'status': 'u...d-value', ...}
E         
E         Omitting 3 identical items, use -vv to show
E         Differing items:
E         {'status': 'unset'} != {'status': 'unreadable'}
E         {'reason': None} != {'reason': 'malformed-value'}
E         Use -v to get more diff

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:275: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_r2_stored_null_is_unreadable_malformed
1 failed, 56 deselected in 0.72s
```

Restore: inverse edit. Restored line quoted back (`P:593`): `        if not got["present"]:`.

Raw green (`-k test_r2`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.71s
```

## R3 — malformed `verifyCommand` reads unreadable

Guarded element: `C:2293` `read_project_config_value`, the `except VerifyCommandMalformed` handler; guarded by `test_r3_malformed_verify_command_is_unreadable` (at the `advisor_issues` level; see the Summary note on `get_item` / `view`).

Neutralization: `return dict(base, reason=unreadable, detail="VerifyCommandMalformed: %s" % exc)` → `return dict(base)` (a malformed `verifyCommand` read as "nothing declared").

Raw red (`-k test_r3`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_r3_malformed_verify_command_is_unreadable ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_r3_malformed_verify_comma0')

    def test_r3_malformed_verify_command_is_unreadable(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _make_bad_verify_command(repo, store)
        got = PC.advisor_issues(repo, root=store)
>       assert got["status"] == "unreadable"
E       AssertionError: assert 'unset' == 'unreadable'
E         
E         - unreadable
E         + unset

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:294: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_r3_malformed_verify_command_is_unreadable
1 failed, 56 deselected in 0.82s
```

Restore: inverse edit. Restored line quoted back (`C:2294`): `            return dict(base, reason=unreadable, detail="VerifyCommandMalformed: %s" % exc)`.

Raw green (`-k test_r3`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.62s
```

## R4 — duplicate core key reads unreadable (two layers)

Guarded element: `test_r4_duplicate_core_key_is_unreadable` guards "a duplicate core key reads unreadable through `read_project_config_value`". Two layers enforce it: `core_md._structural_refusal_at_path` (its `duplicate-core-key` refusal, consumed at `C:2278-2280` of `read_project_config_value`) and the in-reader check (`C:2304`, the `# axis: a duplicate key in the core block reads unreadable, never as the last value winning` branch). The neutralization disables both together; this is the proof for R4.

Neutralization (one two-part edit, both parts applied before the run):

1. `C:2279`: `if structural is not None:` → `if False and structural is not None:`
2. `C:2304`: `if duplicate_key is not None:` → `if False and duplicate_key is not None:`

Raw red (`-k test_r4`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_r4_duplicate_core_key_is_unreadable ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_r4_duplicate_core_key_is_0')

    def test_r4_duplicate_core_key_is_unreadable(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _make_duplicate_key(repo, store)
        got = PC.advisor_issues(repo, root=store)
        assert got["status"] == "unreadable"
        assert got["reason"] == "profile-unparseable"
>       assert got["detail"] == "duplicate-core-key:advisorIssues"
E       AssertionError: assert 'core-md-unpa...onfig/core.md' == 'duplicate-co...advisorIssues'
E         
E         - duplicate-core-key:advisorIssues
E         + core-md-unparseable: json block is not an object at /tmp/claude-0/pytest-of-root/pytest-26/test_r4_duplicate_core_key_is_0/store/projects/ec3a4bb4c4a27661/config/core.md

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_r4_duplicate_core_key_is_unreadable
1 failed, 56 deselected in 0.72s
```

Restore: both parts undone by their inverse edits. Restored lines quoted back: `C:2279` `        if structural is not None:`; `C:2304` `        if duplicate_key is not None:`.

Raw green (`-k test_r4`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.71s
```

Single-layer neutralizations stay green, because the other layer catches the duplicate (recorded as required; neither is the proof for R4):

- Layer 1 only (`C:2279` `if False and structural is not None:`), `-k test_r4`: `.  [100%]` / `1 passed, 56 deselected in 0.79s`. The in-reader check catches it.
- Layer 2 only (`C:2304` `if False and duplicate_key is not None:`), `-k test_r4`: `.  [100%]` / `1 passed, 56 deselected in 0.61s`. The structural refusal catches it.

Both single-layer edits were undone by inverse edits before the next run.

## V1 — `read()` reports an unreadable item 20 as `malformed: True`

Guarded element: `P:624` `_advisor_issues_entry`, `# axis: V1 an unreadable item 20 reads malformed, never as unset`; guarded by `test_v1_read_reports_unreadable_item_20_as_malformed`, proven on the non-object `projectConfiguration` case (parametrize id `non-object-project-configuration`). The `malformed-verify-command` case is not parametrized: `read()` raises on it for every item today, which is existing behaviour and out of scope.

Neutralization: `return {"raw": raw, "effective": None, "source": "unset", "malformed": True}` → `... "malformed": False}` in the `ADVISOR_ISSUES_UNREADABLE` branch.

Raw red (`-k "test_v1 and object"`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_v1_read_reports_unreadable_item_20_as_malformed[non-object-project-configuration] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_v1_read_reports_unreadabl0')
case = 'non-object-project-configuration'

    @pytest.mark.parametrize("case", sorted(_UNREADABLE_CASES))
    def test_v1_read_reports_unreadable_item_20_as_malformed(tmp_path, case):
        repo, store = _setup_repo(tmp_path)
        _UNREADABLE_CASES[case](repo, store)
        got = PC.get_item(repo, SLUG, root=store)
>       assert got["malformed"] is True
E       assert False is True

/home/user/superheroes-wo-2504-a/plugins/superheroes/lib/tests/test_advisor_issues_2504.py:368: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_advisor_issues_2504.py::test_v1_read_reports_unreadable_item_20_as_malformed[non-object-project-configuration]
1 failed, 56 deselected in 0.64s
```

Restore: inverse edit. Restored line quoted back (`P:624`): `        return {"raw": raw, "effective": None, "source": "unset", "malformed": True}`.

Raw green (`-k "test_v1 and object"`):

```
.                                                                        [100%]
1 passed, 56 deselected in 0.75s
```

## Restore receipt (whole record)

After the last restore, `git status --porcelain plugins/superheroes/lib` listed only the two test files this round edited (`test_advisor_issues_2504.py`, `test_project_config.py`); `core_md.py` and `project_config.py` showed no change against the committed round-1 state. A search for `if False` in both files returned no match. The six named test files then ran green together: `303 passed`.
