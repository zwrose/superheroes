# Guardian-siblings bite-proof

## Guardian-siblings

**Guarded element:** `core_md.py:1632` — `_splice_guardian_config_block` sibling-preserving merge in `write_guardian_cadence` — axis: refuse when a cadence write drops guardian-config siblings.

**Neutralization:** replaced `_splice_guardian_config_block` with a wholesale fence rewrite and made `_guardian_config_round_trip_ok` always return `True` (wholesale splice alone still refused via the round-trip check):

```python
def _splice_guardian_config_block(text, new_body):
    """Replace the body of the sole guardian-config fence, or None if not exactly one."""
    return (
        "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
        "```json guardian-config\n"
        '{"cadence": {"minMerges": 5, "minDays": 7}}\n'
        "```\n"
    )

def _guardian_config_round_trip_ok(orig_block, new_block):
    """True when only ``cadence`` changed in a guardian-config object."""
    return True
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_guardian_cadence_sibling_preservation_axis -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_bite_guardian_cadence_sibling_preservation_axis _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-167/test_bite_guardian_cadence_sib0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x104627b50>

    def test_bite_guardian_cadence_sibling_preservation_axis(tmp_path, monkeypatch):
        """axis: sibling preservation — refuse when cadence write drops guardian-config siblings."""
        repo, store = _setup_repo(tmp_path)
        layer = _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
        before = open(layer).read()

        def wholesale_splice(text, new_body):
            return (
                "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
                "```json guardian-config\n"
                '{"cadence": {"minMerges": 5, "minDays": 7}}\n'
                "```\n"
            )

        monkeypatch.setattr(CM, "_splice_guardian_config_block", wholesale_splice)
        res = CM.write_guardian_cadence(repo, _CADENCE, root=store)
>       assert res["action"] == "refused"
E       AssertionError: assert 'written' == 'refused'
E         
E         - refused
E         + written

plugins/superheroes/lib/tests/test_core_md_project_config.py:520: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_guardian_cadence_sibling_preservation_axis
1 failed in 7.16s
```

**Restore:** restored the original `_splice_guardian_config_block` body and `_guardian_config_round_trip_ok` comparison logic.

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/core_md.py` showed no output.

**Green run:**

```
.                                                                        [100%]
1 passed in 5.72s
```
