# Round-trip bite-proof

## Round-trip

**Guarded element:** `core_md.py:1492` — `_json_block_key_round_trip_ok` comparison in `_write_json_block_key` — axis: refuse when re-parse would change fields outside the owned key.

**Neutralization:** replaced the round-trip check with a dead branch that never refuses:

```python
        if False:
            return {"action": "refused", "reason": round_trip_reason}
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_write_project_config_round_trip_axis -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_bite_write_project_config_round_trip_axis ________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-152/test_bite_write_project_config0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103fb9c10>

    def test_bite_write_project_config_round_trip_axis(tmp_path, monkeypatch):
        """axis: round-trip — refuse when re-parse would change verifyCommand."""
        repo, store = _setup_repo(tmp_path)
        path = CM.core_path(repo, store)
        original_text = open(path).read()

        _original_splice = CM._splice_single_json_block

        def corrupting_splice(text, new_body):
            bad_body = json.loads(new_body)
            bad_body["verifyCommand"] = "CORRUPTED"
            return _original_splice(text, json.dumps(bad_body, indent=2))

        monkeypatch.setattr(CM, "_splice_single_json_block", corrupting_splice)
        res = CM.write_project_config(repo, _PROJECT_CFG, root=store)
>       assert res["action"] == "refused"
E       AssertionError: assert 'written' == 'refused'
E         
E         - refused
E         + written

plugins/superheroes/lib/tests/test_core_md_project_config.py:481: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_write_project_config_round_trip_axis
1 failed in 5.68s
```

**Restore:** restored the original round-trip check:

```python
        if not _json_block_key_round_trip_ok(orig, new_parsed, block_key):
            return {"action": "refused", "reason": round_trip_reason}
```

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/core_md.py` showed no output.

**Green run:**

```
.                                                                        [100%]
1 passed in 5.47s
```
