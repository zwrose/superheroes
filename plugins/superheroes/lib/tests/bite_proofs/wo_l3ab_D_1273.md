# WO-L3AB-D (#1273) bite-proof — completion-boundary probe tests

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-D1 | `_load_native_result_json` completion window | after-cap probe cells must forfeit `result-completion-after-deadline` | `test_probe_completion_after_cap_forfeits[*]` (4 cells) |
| BP-D2 | `probe()` all-mode preflight | reused mode must block dispatch (call count 0) | `test_probe_preflight_aborts_all_modes_when_one_mode_reused` |

---

## BP-D1 — completion window inside `_load_native_result_json`

- **axis:** completion after deadline must forfeit through probe grading

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        verdict, detail = engine_result_channel.completion_window(ended, digest)
        # if verdict == "forfeit":
        #     return None, detail
        return obj, None  # bite-proof BP-D1 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_completion_after_cap_forfeits -q
```

**raw red** (exit 1):
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
___________ test_probe_completion_after_cap_forfeits[codex-default] ____________
...
>       assert leg["ok"] is False
E       assert True is False
...
___________ test_probe_completion_after_cap_forfeits[cursor-default] ___________
...
___________ test_probe_completion_after_cap_forfeits[claude-print] _____________
...
_________ test_probe_completion_after_cap_forfeits[claude-background] __________
...
4 failed in 0.89s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        verdict, detail = engine_result_channel.completion_window(ended, digest)
        if verdict == "forfeit":
            return None, detail
        return obj, None
```

**restore receipt:** inverse edit applied; `git status --porcelain` shows only test/doc files.

**raw green** (exit 0):
```
....                                                                     [100%]
4 passed in 0.66s
```

---

## BP-D2 — all-mode preflight abort

- **axis:** reused mode in preflight must refuse every mode with zero dispatches

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `probe()`):
```python
    elif False and any_reused:  # bite-proof BP-D2 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_preflight_aborts_all_modes_when_one_mode_reused -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_probe_preflight_aborts_all_modes_when_one_mode_reused __________
...
>       assert len(calls) == 0
E       AssertionError: assert 2 == 0
...
1 failed in 0.64s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `probe()`):
```python
    elif any_reused:
```

**restore receipt:** inverse edit applied; production tree clean after restore.

**raw green** (exit 0): covered by full-suite green run (`98 passed`).
