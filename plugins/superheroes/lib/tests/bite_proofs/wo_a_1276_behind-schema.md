# Behind-schema bite-proof

## Behind-schema

**Guarded element:** `core_md.py:1443` — `record.get("behind")` branch in `_write_json_block_key` — axis: refuse with `behind` when core.md schema is newer than this build.

**Neutralization:** removed the behind branch:

```python
        if record.get("behind"):
            return {
                "action": "behind",
                "reason": BUILDER_DISPATCH_DEFER_SCHEMA_BEHIND,
                "record": record,
            }
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_write_project_config_behind_schema_axis -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_bite_write_project_config_behind_schema_axis _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-156/test_bite_write_project_config0')

    def test_bite_write_project_config_behind_schema_axis(tmp_path):
        """axis: behind-schema — refuse when core.md schema is newer than this build."""
        repo, store = _setup_repo(tmp_path, schema=CM.SCHEMA_VERSION + 1)
        res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
>       assert res["action"] == "behind"
E       AssertionError: assert 'written' == 'behind'
E         
E         - behind
E         + written

plugins/superheroes/lib/tests/test_core_md_project_config.py:490: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_write_project_config_behind_schema_axis
1 failed in 1.46s
```

**Restore:** reinserted the behind branch at `core_md.py:1443` (quoted in neutralization above).

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/core_md.py` showed no output.

**Green run:**

```
.                                                                        [100%]
1 passed in 1.22s
```
