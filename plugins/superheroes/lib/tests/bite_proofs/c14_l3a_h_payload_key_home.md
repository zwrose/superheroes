# C14 L3a-H/K (#1273) bite-proof — native-branch narrowing reads payload-key home

**Provenance:** cursor / composer-2.5 (implementer, order `1273-l3a-K`).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-K1 | `native_review_payload_shape` native-branch narrowing | every recognised kind reads `review_payload_key` and is kept only when the branch value at that key is not `None`; no kind is exempt by omission | `test_native_branch_narrowing_consults_payload_key_home_for_ruling` |
| BP-K2 | `native_review_payload_shape` native-branch narrowing | narrowing tests payload-key **value** (`is not None`), not `review_payload_carried(...)[0]` presence predicates | `test_native_branch_narrowing_present_but_null_grouping_not_second_kind` |

---

## BP-K1 — no kind exempt from payload-key value narrowing

- **axis:** native-branch narrowing reads each kind's payload key from `engine_adapter.review_payload_key` and keeps the kind only when `branch.get(key) is not None`; `ruling` is not kept unconditionally when omitted from a local table

**Unprovable as placed.** With the final key+value narrowing and the aligned ruling-detector fixture (`findings: None`, `ruling` populated), exempting `ruling` does not change the matched set: `findings` is already dropped by the `is not None` test, and exempting `ruling` leaves a single matched kind either way. The order's neutralization (`k == "ruling" or …`) therefore cannot redden the detector without editing it. Under the H-era fixture (`findings: []`) the neutralization does redden — but the inverse restore to key+value narrowing cannot green that fixture because both `findings` (`[]`) and `ruling` (non-`None` string) pass the value test, producing `object-both-payload-keys` on restore.

**neutralization attempted** (`plugins/superheroes/lib/engine_result_channel.py`, `native_review_payload_shape` native-branch narrowing):
```python
            matched = [
                k for k in matched
                if k == "ruling" or (
                    (key := ea.review_payload_key(k)) is not None
                    and branch.get(key) is not None
                )
            ]
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py -q
```

**raw red attempt** (exit 0 — detector stayed green; proof not produced):
```
........................................................................ [ 79%]
...................                                                      [100%]
91 passed in 0.44s
```

**restore** (final code — inverse of neutralization):
```python
            matched = [
                k for k in matched
                if (key := ea.review_payload_key(k)) is not None
                and branch.get(key) is not None
            ]
```

**restore receipt:** restored lines quoted above.

---

## BP-K2 — value test at payload key, not `review_payload_carried`

- **axis:** present-but-`None` sibling payload keys (e.g. `grouping: None` on a findings branch) must not count as a second matched kind; `review_payload_carried(...)[0]` is presence-based for grouping and keeps such keys

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `native_review_payload_shape` native-branch narrowing):
```python
            matched = [
                k for k in matched
                if ea.review_payload_carried(branch, k)[0]
            ]
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py -q
```

**raw red** (exit 1):
```
........................................................................ [ 79%]
.................F.                                                      [100%]
=================================== FAILURES ===================================
____ test_native_branch_narrowing_present_but_null_grouping_not_second_kind ____

    def test_native_branch_narrowing_present_but_null_grouping_not_second_kind():
        # axis: present-but-null grouping key does not count as a second matched kind
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_h_payload_key_home.md
        branch = _valid_review_branch("findings")
        assert "grouping" in EA._recognised_review_kinds(branch)
        assert EA.review_payload_carried(branch, "grouping") == (True, None)
        shape = ERC.native_review_payload_shape(
            "native-result-schema-invalid", branch=branch)
>       assert shape["parsed"] != EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS
E       AssertionError: assert 'object-both-payload-keys' != 'object-both-payload-keys'
E        +  where 'object-both-payload-keys' = EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS

plugins/superheroes/lib/tests/test_engine_result_channel.py:849: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_native_branch_narrowing_present_but_null_grouping_not_second_kind
1 failed, 90 passed in 0.42s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `native_review_payload_shape` native-branch narrowing):
```python
            matched = [
                k for k in matched
                if (key := ea.review_payload_key(k)) is not None
                and branch.get(key) is not None
            ]
```

**restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/engine_result_channel.py` showed ` M` during work, clean after inverse edit.

**raw green** (exit 0):
```
........................................................................ [ 79%]
...................                                                      [100%]
91 passed in 0.54s
```
