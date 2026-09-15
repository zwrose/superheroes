# WO-H sibling-declarations bite-proof

## sibling-declarations

**Guarded element:** the read-modify-write in `declare_dependency` that preserves sibling declarations — axis: sibling declarations survive a single dependency declare.

**Neutralization:** replaced the read-modify-write with `mapping = {slug: value}` so only the target key is written.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_project_config_dependencies.py::test_declare_preserves_other_three_declarations -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_declare_preserves_other_three_declarations ________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-297/test_declare_preserves_other_t0')

    def test_declare_preserves_other_three_declarations(tmp_path):
        # axis: sibling declarations survive — wo_h_1276_sibling-declarations
        repo, store = _setup_repo(tmp_path)
        seed = {
            "launchLedger": "ledger-path",
            "keepOrRetireBackfill": {"mode": "opportunistic"},
            "detectorTestBoundary": "rubric/bite-proof.md",
        }
        CM.write_declared_dependencies(repo, seed, root=store)
        res = PC.declare_dependency(repo, "collector", "standing-proposals", root=store)
        assert res["action"] == "written"
        got = CM.read(repo, root=store)["declaredDependencies"]
        for key, value in seed.items():
>           assert got[key] == value
E           KeyError: 'launchLedger'

plugins/superheroes/lib/tests/test_project_config_dependencies.py:105: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config_dependencies.py::test_declare_preserves_other_three_declarations
1 failed in 1.67s
```

**Restore:** restored the read-modify-write:
```python
    mapping = _declared_dependencies_mapping(facts)
    if value is None:
        if slug not in mapping:
            return {"action": "noop"}
        del mapping[slug]
    else:
        mapping[slug] = value
```

**Restore receipt:** restored lines quoted above in `declare_dependency`.

**Green run:**
```
.                                                                        [100%]
1 passed in 1.66s
```
