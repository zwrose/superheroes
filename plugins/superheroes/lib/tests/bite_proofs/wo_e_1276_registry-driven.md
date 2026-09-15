# WO-E registry-driven bite-proof

## Registry-driven rows

**Guarded element:** `_project_config_lines` loop over `project_config.ITEMS` — axis: the item list is driven by the registry, not a hand-written copy.

**Neutralization:** replaced the `for item_def in project_config.ITEMS:` loop with three hard-coded `lines.append(...)` calls in `configure_view.py`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_configure_view_project_config.py::test_block_driven_by_items_registry -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_block_driven_by_items_registry ______________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-230/test_block_driven_by_items_reg0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103ffa550>

    def test_block_driven_by_items_registry(tmp_path, monkeypatch):
        repo, store = _setup_repo(tmp_path)
        extra = {
            "number": 14,
            "slug": "testOnlyItem",
            "name": "Test-only item",
            "home": PC.HOME_PROJECT_CONFIGURATION,
            "shape": "prose",
            "plugin_default": None,
        }
        monkeypatch.setattr(CV.project_config, "ITEMS", tuple(list(PC.ITEMS) + [extra]))
        screen = CV.render(repo, root=store)
        rows = _numbered_rows(_project_config_section(screen))
>       assert len(rows) == 14
E       AssertionError: assert 3 == 14
E        +  where 3 = len(['1. Severity ladder — unset (absence disables the rules that read it)', '2. P0 definition — unset (absence disables the rules that read it)', '3. Dial — hardcoded row'])

plugins/superheroes/lib/tests/test_configure_view_project_config.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_configure_view_project_config.py::test_block_driven_by_items_registry
1 failed in 11.56s
```

**Restore:** restored the `for item_def in project_config.ITEMS:` loop with slug lookup from `by_slug`.

**Restore receipt:**
```python
    by_slug = {entry["slug"]: entry for entry in payload.get("items") or []}
    for item_def in project_config.ITEMS:
        entry = by_slug.get(item_def["slug"])
        ...
        lines.append("%d. %s — %s" % (number, name, value))
```

**Green run:**
```
.                                                                        [100%]
1 passed in 11.56s
```
