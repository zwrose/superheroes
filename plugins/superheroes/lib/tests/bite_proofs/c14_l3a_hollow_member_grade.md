# C14 L3a hollow-member grade bite-proof

## BP1 — populated-payload rule

**Guarded element:** `test_engine_adapter.py::test_review_payload_shape_findings_partial_hollow_member` — axis: a populated findings list with substantive and hollow members must not receive the plain `findings-hollow-member` label.

**Neutralization:** in `_hollow_family_diagnostic`, collapsed the findings branch to always mint plain hollow:

```python
    if list_kind == "findings":
        parsed = SHAPE_FINDINGS_HOLLOW_MEMBER
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3a-B -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_review_payload_shape_findings_partial_hollow_member -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_review_payload_shape_findings_partial_hollow_member ___________

    def test_review_payload_shape_findings_partial_hollow_member():
        # axis: populated findings list with substantive and hollow members is not plain hollow
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_hollow_member_grade.md (BP1)
        good = {"severity": "Minor", "title": "t", "body": "b"}
        stdout = json.dumps({"findings": [good, {}]})
        res = EA.review_payload_shape(stdout)
>       assert res == _hollow_family_shape(
            EA.SHAPE_FINDINGS_PARTIAL_HOLLOW_MEMBER,
            "engaged-finding-member",
            "list:count=2,hollow=1,substantive=1",
        )
E       AssertionError: assert {'keysTruncat...-member', ...} == {'keysTruncat...-member', ...}
E         
E         Omitting 4 identical items, use -vv to show
E         Differing items:
E         {'parsed': 'findings-hollow-member'} != {'parsed': 'findings-partial-hollow-member'}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_adapter.py:2929: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_review_payload_shape_findings_partial_hollow_member
1 failed in 0.43s
```

**Restore:** restored the partial branch:

```python
    if list_kind == "findings":
        parsed = (SHAPE_FINDINGS_PARTIAL_HOLLOW_MEMBER if grade == "partial"
                  else SHAPE_FINDINGS_HOLLOW_MEMBER)
```

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/engine_adapter.py` showed no output after restore.

**Green run:**

```
.                                                                        [100%]
1 passed in 0.36s
```

## BP2 — wanted/got fields

**Guarded element:** `test_engine_adapter.py::test_hollow_family_diagnostic_carries_member_shape_fields` — axis: hollow-family diagnostics always carry bounded `memberShapeWanted` and `memberShapeGot` fields.

**Neutralization:** removed the two field attachments from the constructor return dict:

```python
    return {
        "parsed": parsed,
        "topLevelKeys": [],
        "keysTruncated": False,
    }
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3a-B -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_hollow_family_diagnostic_carries_member_shape_fields -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_hollow_family_diagnostic_carries_member_shape_fields ___________

    def test_hollow_family_diagnostic_carries_member_shape_fields():
        # axis: hollow-family diagnostics always carry bounded wanted/got member-shape fields
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_hollow_member_grade.md (BP2)
        res = EA.review_payload_shape(json.dumps({"findings": [{}]}))
>       assert res["memberShapeWanted"] == "engaged-finding-member"
E       KeyError: 'memberShapeWanted'

plugins/superheroes/lib/tests/test_engine_adapter.py:2954: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_hollow_family_diagnostic_carries_member_shape_fields
1 failed in 0.39s
```

**Restore:** restored the field attachments:

```python
        "memberShapeWanted": member_shape_wanted,
        "memberShapeGot": member_shape_got,
```

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/engine_adapter.py` showed no output after restore.

**Green run:**

```
.                                                                        [100%]
1 passed in 0.40s
```

## BP3 — single-mint census test

**Guarded element:** `test_engine_adapter.py::test_hollow_member_shape_tokens_minted_only_via_constructor` — axis: hollow-family `SHAPE_*` tokens are referenced only in the constants home, `REVIEW_PAYLOAD_SHAPES`, and `_hollow_family_diagnostic`.

**Neutralization:** planted a sixth reference outside the allowed ranges:

```python
        _ = SHAPE_FINDINGS_HOLLOW_MEMBER
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3a-B -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_hollow_member_shape_tokens_minted_only_via_constructor -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_hollow_member_shape_tokens_minted_only_via_constructor __________

    def test_hollow_member_shape_tokens_minted_only_via_constructor():
        # axis: hollow-family SHAPE_* tokens are minted only at the constructor home
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/c14_l3a_hollow_member_grade.md (BP3)
        adapter_path = os.path.join(_HERE, "..", "engine_adapter.py")
        with open(adapter_path, encoding="utf-8") as fh:
            source = fh.read()
        home_start, home_end, constructor_start, constructor_end = (
            _hollow_family_shape_constant_line_ranges(source))
        assert home_start is not None
        assert home_end is not None
        assert constructor_start is not None
        assert constructor_end is not None
        allowed = set(range(home_start, home_end + 1)) | set(
            range(constructor_start, constructor_end + 1))
        stray = [
            "%s:%d" % (name, line)
            for name, line in _hollow_family_shape_constant_refs(source)
            if line not in allowed
        ]
>       assert stray == []
E       AssertionError: assert ['SHAPE_FINDI..._MEMBER:2027'] == []
E         
E         Left contains one more item: 'SHAPE_FINDINGS_HOLLOW_MEMBER:2027'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_adapter.py:3019: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_hollow_member_shape_tokens_minted_only_via_constructor
1 failed in 0.47s
```

**Restore:** removed the planted reference line.

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/engine_adapter.py` showed no output after restore.

**Green run:**

```
.                                                                        [100%]
1 passed in 0.57s
```
