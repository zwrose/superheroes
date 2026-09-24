# WO-C (#1340 layer 2c) bite-proof — tagged membership-read returns

Per-guard bite proof for the three `# bite-axis:` clauses introduced in `read_membership`'s read path: transport pair-slot discrimination, page pair-slot discrimination, and invariant explicit-tag discrimination.

**Register:** 3 guards — the three content-derived discriminators removed from `read_membership` (transport `.get("ok")`, page `"ok" in`, invariant `isinstance(..., tuple)`).

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woC -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| L2C-1 | stack_check.py:520 | transport refusal is distinguished by pair slot, not payload content | `test_l2c_forged_refusal_ok_sibling_of_data_is_not_our_refusal` | proven |
| L2C-2 | stack_check.py:532 | page refusal is distinguished by pair slot, not page dict content | `test_l2c_parse_tag_refuse_branch` | proven |
| L2C-3 | stack_check.py:579 | invariant outcome is distinguished by explicit tag, not result shape | `test_l2c_invariant_tag_refuse_branch` | proven |

---

## L2C-1 — transport refusal is distinguished by pair slot, not payload content

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
            # bite-axis: transport refusal is distinguished by pair slot, not payload content
            if transport_refusal is not None and payload is not None:
                raise AssertionError("_transport_graphql returned both payload and refusal")
            if transport_refusal is not None:
                return transport_refusal
            if payload is None:
                raise AssertionError("_transport_graphql returned neither payload nor refusal")
```
→
```python
            # bite-axis: transport refusal is distinguished by pair slot, not payload content
            transport_result = payload if transport_refusal is None else transport_refusal
            if isinstance(transport_result, dict) and transport_result.get("ok") is False:
                return transport_result
            if transport_refusal is not None:
                return transport_refusal
            if payload is None:
                raise AssertionError("_transport_graphql returned neither payload nor refusal")
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woC -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2c_forged_refusal_ok_sibling_of_data_is_not_our_refusal -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2c_forged_refusal_ok_sibling_of_data_is_not_our_refusal
1 failed in 0.08s
```

**raw green** after restore:
```
1 passed in 0.07s
```

**restored lines:**
```python
            # bite-axis: transport refusal is distinguished by pair slot, not payload content
            if transport_refusal is not None and payload is not None:
                raise AssertionError("_transport_graphql returned both payload and refusal")
            if transport_refusal is not None:
                return transport_refusal
            if payload is None:
                raise AssertionError("_transport_graphql returned neither payload nor refusal")
```

---

## L2C-2 — page refusal is distinguished by pair slot, not page dict content

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
            # bite-axis: page refusal is distinguished by pair slot, not page dict content
            if page_refusal is not None and page_result is not None:
                raise AssertionError("_parse_membership_page returned both page and refusal")
            if page_refusal is not None:
                return page_refusal
            if page_result is None:
                raise AssertionError("_parse_membership_page returned neither page nor refusal")
```
→
```python
            # bite-axis: page refusal is distinguished by pair slot, not page dict content
            if page_result is None:
                raise AssertionError("_parse_membership_page returned neither page nor refusal")
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woC -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2c_parse_tag_refuse_branch -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2c_parse_tag_refuse_branch
1 failed in 0.09s
```

**raw green** after restore:
```
1 passed in 0.07s
```

**restored lines:**
```python
            # bite-axis: page refusal is distinguished by pair slot, not page dict content
            if page_refusal is not None and page_result is not None:
                raise AssertionError("_parse_membership_page returned both page and refusal")
            if page_refusal is not None:
                return page_refusal
            if page_result is None:
                raise AssertionError("_parse_membership_page returned neither page nor refusal")
```

---

## L2C-3 — invariant outcome is distinguished by explicit tag, not result shape

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        # bite-axis: invariant outcome is distinguished by explicit tag, not result shape
        invariant_tag = invariant_result.get("tag")
        if invariant_tag == _INVARIANT_TAG_CONTINUE:
            prior_members = invariant_result["prior_members"]
            continue
        if invariant_tag == _INVARIANT_TAG_REFUSAL:
            return invariant_result["result"]
        if invariant_tag == _INVARIANT_TAG_SUCCESS:
            return invariant_result["result"]
        raise AssertionError("_validate_stack_invariants returned unknown tag: %r" % invariant_tag)
```
→
```python
        # bite-axis: invariant outcome is distinguished by explicit tag, not result shape
        if isinstance(invariant_result, tuple):
            prior_members = invariant_result[1]
            continue
        return invariant_result
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woC -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2c_invariant_tag_refuse_branch -q
```

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2c_invariant_tag_refuse_branch
1 failed in 0.09s
```

**raw green** after restore:
```
1 passed in 0.07s
```

**restored lines:**
```python
        # bite-axis: invariant outcome is distinguished by explicit tag, not result shape
        invariant_tag = invariant_result.get("tag")
        if invariant_tag == _INVARIANT_TAG_CONTINUE:
            prior_members = invariant_result["prior_members"]
            continue
        if invariant_tag == _INVARIANT_TAG_REFUSAL:
            return invariant_result["result"]
        if invariant_tag == _INVARIANT_TAG_SUCCESS:
            return invariant_result["result"]
        raise AssertionError("_validate_stack_invariants returned unknown tag: %r" % invariant_tag)
```

---

## Restore receipt

**`git status --porcelain` (mutated files):**
```
 M plugins/superheroes/lib/stack_check.py
 M plugins/superheroes/lib/tests/test_stack_check.py
?? plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2c_stackcheck.md
```
