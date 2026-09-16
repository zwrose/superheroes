# WO-B default-count bite-proof

## Default count

**Guarded element:** `test_exactly_five_plugin_defaults` — axis: exactly five items in `ITEMS` carry a plugin default.

**Neutralization:** set `severityLadder` `plugin_default` to `[]` so a sixth defaulted item exists.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_project_config.py::test_exactly_five_plugin_defaults -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_exactly_five_plugin_defaults _______________________

    def test_exactly_five_plugin_defaults():
        # axis: exactly five items carry a plugin default — wo_b_1276_default-count
        defaulted = [item for item in PC.ITEMS if item["plugin_default"] is not None]
>       assert len(defaulted) == 5
E       AssertionError: assert 6 == 5
E        +  where 6 = len([{'home': 'projectConfiguration', 'name': 'Severity ladder', 'number': 1, 'plugin_default': [], ...}, {'home': 'projec...guardianCadence', 'name': 'Guardian staleness', 'number': 11, 'plugin_default': {'minDays': 14, 'minMerges': 10}, ...}])

plugins/superheroes/lib/tests/test_project_config.py:135: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config.py::test_exactly_five_plugin_defaults
1 failed in 0.65s
```

**Restore:** reverted `severityLadder` `plugin_default` to `None`.

**Restore receipt:** restored line in `ITEMS` entry for `severityLadder`: `"plugin_default": None,`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.72s
```
