# C14 L3a-H (#1273) bite-proof — native-branch narrowing reads payload-key home

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-H1 | `native_review_payload_shape` native-branch narrowing | every recognised kind consults `engine_adapter.review_payload_carried`; no kind is exempt by omission | `test_native_branch_narrowing_consults_payload_key_home_for_ruling` |

---

## BP-H1 — payload-key home for every recognised kind

- **axis:** native-branch narrowing asks `review_payload_carried` for every matched kind; `ruling` is not kept unconditionally when omitted from a local table

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `native_review_payload_shape` native-branch narrowing):
```python
            matched = [
                k for k in matched
                if k == "ruling" or ea.review_payload_carried(branch, k)[0]
            ]
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py -q
```

**raw red** (exit 1):
```
........................................................................ [ 80%]
...............F..                                                       [100%]
=================================== FAILURES ===================================
______ test_native_branch_narrowing_consults_payload_key_home_for_ruling _______

    def test_native_branch_narrowing_consults_payload_key_home_for_ruling():
        # axis: ruling is narrowed like every other kind — not exempt by omission
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_h_payload_key_home.md
        branch = _malformed_ruling_branch_with_spurious_findings_list()
        assert "ruling" in EA._recognised_review_kinds(branch)
        assert "findings" in EA._recognised_review_kinds(branch)
        shape = ERC.native_review_payload_shape(
            "native-result-schema-invalid", branch=branch)
>       assert shape["parsed"] != EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS
E       AssertionError: assert 'object-both-payload-keys' != 'object-both-payload-keys'
E        +  where 'object-both-payload-keys' = EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS

plugins/superheroes/lib/tests/test_engine_result_channel.py:821: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_native_branch_narrowing_consults_payload_key_home_for_ruling
1 failed, 89 passed in 0.96s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `native_review_payload_shape` native-branch narrowing):
```python
            matched = [
                k for k in matched
                if ea.review_payload_carried(branch, k)[0]
            ]
```

**restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/engine_result_channel.py` showed no output after restore.

**raw green** (exit 0):
```
........................................................................ [ 80%]
..................                                                       [100%]
90 passed in 0.95s
```
