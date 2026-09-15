# WO-B one-home bite-proof

## One home

**Guarded element:** `set_item` projectConfiguration branch in `project_config.py` — axis: sibling keys in the mapping survive a single-item set.

**Neutralization:** replaced the read-modify-write with `mapping = {slug: value}` so only the target key is written.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_project_config.py::test_set_preserves_sibling_project_configuration_keys -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_set_preserves_sibling_project_configuration_keys _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-204/test_set_preserves_sibling_pro0')

    def test_set_preserves_sibling_project_configuration_keys(tmp_path):
        repo, store = _setup_repo(tmp_path)
        CM.write_project_config(repo, _PROJECT_CFG_SEED, root=store)
        before = dict(CM.read(repo, root=store)["projectConfiguration"])
        res = PC.set_item(repo, "digestFloor", "weekly", root=store)
        assert res["action"] == "written"
        after = dict(CM.read(repo, root=store)["projectConfiguration"])
        for key, value in before.items():
            if key != "digestFloor":
>               assert after[key] == value
E               KeyError: 'dial'

plugins/superheroes/lib/tests/test_project_config.py:191: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config.py::test_set_preserves_sibling_project_configuration_keys
1 failed in 7.41s
```

**Restore:** restored the read-modify-write:
```python
        mapping = dict(_project_config_mapping(facts))
        mapping[slug] = value
        write_result = core_md.write_project_config(cwd, mapping, root=root)
```

**Restore receipt:** restored lines quoted above in `set_item`.

**Green run:**
```
.                                                                        [100%]
1 passed in 7.65s
```
