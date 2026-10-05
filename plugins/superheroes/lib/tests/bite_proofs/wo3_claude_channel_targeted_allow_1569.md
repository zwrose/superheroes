# WO-3 (#1573, layer 1 of #1569) — claude write channel targeted Bash allow: bite-proof record

Implementer-run record. Method: a targeted Edit on the guarded element, the detector run alone by its exact node id (red), the inverse Edit, the detector again (green), and the restored lines quoted back. Declared guarded-element set: P1 and P2. **2 elements, 2 RED→GREEN.**

## P1 — the rule list

- **site:** `plugins/superheroes/lib/engine_adapter.py`, `CLAUDE_WRITE_BASH_ALLOW`
- **axis:** the emitted allow list is exactly the five targeted rules, in order
- **detector:** `plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_settings_allow_is_the_five_targeted_rules`
- **neutralization:** drop `"Bash(scripts/pinned-python:*)",` from the tuple.
- **raw red (rc 1):**

```
F                                                                        [100%]
E       AssertionError: assert {'allow': ['B... 'WebSearch']} == {'allow': ['B... 'WebSearch']}
E         Differing items:
E         {'allow': ['Bash(python:*)', 'Bash(python3:*)', 'Bash(pytest:*)', 'Bash(echo:*)']} != {'allow': ['Bash(python:*)', 'Bash(python3:*)', 'Bash(pytest:*)', 'Bash(scripts/pinned-python:*)', 'Bash(echo:*)']}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_settings_allow_is_the_five_targeted_rules
1 failed in 1.15s
```

- **restore:** the inverse Edit (the line put back between `pytest` and `echo`).
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.33s
```

- **restored lines quoted back:**

```
    "Bash(pytest:*)",
    "Bash(scripts/pinned-python:*)",
    "Bash(echo:*)",
```

- **verdict:** RED->GREEN

## P2 — never blanket

- **site:** `plugins/superheroes/lib/engine_adapter.py`, `CLAUDE_WRITE_BASH_ALLOW`
- **axis:** no emitted rule is a blanket or non-family `Bash` allow
- **detector:** `plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_allow_never_blanket`
- **neutralization:** append `"Bash",` to the tuple.
- **raw red (rc 1):**

```
F                                                                        [100%]
E           AssertionError: Bash
E           assert 'Bash' not in ('Bash', 'Bash(*)')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_allow_never_blanket
1 failed in 0.25s
```

- **restore:** the inverse Edit (the appended line removed).
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.24s
```

- **restored lines quoted back:**

```
CLAUDE_WRITE_BASH_ALLOW = (
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(pytest:*)",
    "Bash(scripts/pinned-python:*)",
    "Bash(echo:*)",
)
```

- **verdict:** RED->GREEN
