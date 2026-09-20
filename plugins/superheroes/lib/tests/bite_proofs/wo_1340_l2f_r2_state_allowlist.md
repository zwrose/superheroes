# WO-G2 (#1340 layer 2f r2) bite-proof — PR vet state allowlist in stack_check.py

Per-guard bite proof for `_parse_pr_vet_state_payload` state allowlist added in layer 2f r2.

**Register:** 1 guard — allowlist membership test on GitHub `state` field.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q -k l2f
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving tests | Verdict |
|---|---|---|---|---|
| G1 | stack_check.py:608-611 | allowlist membership on state | `test_l2f_read_pr_vet_state_unrecognised_state`, `test_l2f_read_pr_vet_state_lowercase_open_refuses` | proven |

---

## G1 — allowlist membership on state

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if state not in PR_VET_STATE_VALUES:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "state is not one of the enumerated values: %r" % state)
```
→
```python
    # allowlist neutralized for bite-proof
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q -k l2f
```

**raw red:**
```
......................................FF..                               [100%]
=================================== FAILURES ===================================
________________ test_l2f_read_pr_vet_state_unrecognised_state _________________

    def test_l2f_read_pr_vet_state_unrecognised_state():
        # axis: unrecognised state value refuses stack-unreadable
        run, _calls = _make_run(
            {_pr_vet_argv(): _pr_vet_ok(state="UNKNOWN")}
        )
        state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
>       assert state is None
E       AssertionError: assert {'body': '', 'headRefOid': 'abcdef0123456789abcdef0123456789abcdef01', 'isDraft': False, 'number': 701, ...} is None

plugins/superheroes/lib/tests/test_stack_check.py:1713: AssertionError
______________ test_l2f_read_pr_vet_state_lowercase_open_refuses _______________

    def test_l2f_read_pr_vet_state_lowercase_open_refuses():
        # axis: case-sensitive allowlist — lowercase open is not OPEN
        run, _calls = _make_run(
            {_pr_vet_argv(): _pr_vet_ok(state="open")}
        )
        state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
>       assert state is None
E       AssertionError: assert {'body': '', 'headRefOid': 'abcdef0123456789abcdef0123456789abcdef01', 'isDraft': False, 'number': 701, ...} is None

plugins/superheroes/lib/tests/test_stack_check.py:1725: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_read_pr_vet_state_unrecognised_state
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_read_pr_vet_state_lowercase_open_refuses
2 failed, 40 passed, 82 deselected in 0.16s
```

**raw green** after restore:
```
..........................................                               [100%]
42 passed, 82 deselected in 0.13s
```

**restored lines:**
```python
    if state not in PR_VET_STATE_VALUES:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "state is not one of the enumerated values: %r" % state)
```

---

## Restore receipt

Bite-proof neutralization applied and reverted by inverse edit in the WO-G2 worktree.

**`git status --porcelain` after restore:**
```
 M plugins/superheroes/lib/stack_check.py
 M plugins/superheroes/lib/tests/test_launcher.py
 M plugins/superheroes/lib/tests/test_stack_check.py
?? plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_r2_state_allowlist.md
```
