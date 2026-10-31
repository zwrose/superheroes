# #2275 WO-B bite-proof — allow rules for leading NAME=value assignments

**Provenance:** produced by **WO-B2** (`2275-wo-b2`, claude / sonnet) on the worktree at base `e64d79cc` (WO-B's landed work). Every neutralization is a targeted edit of `plugins/superheroes/lib/engine_adapter.py` only, run red with the detectors unedited, and restored by the exact inverse edit. One neutralization was live at a time. No credential-like text appears in the captures; nothing is redacted.

Command prefix (exact node set per element named below):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <files> -q -p no:cacheprovider --tb=line|--tb=no -rf
```

The one-line `warning: The UV_NATIVE_TLS environment variable is deprecated …` that `uv` prints before every run is omitted from the captures below; nothing else is trimmed except where `…` is marked.

The guarded code under test (restored state):

```
CLAUDE_WRITE_BASH_ALLOW = (
    tuple(f"Bash({family}:*)" for family in CLAUDE_WRITE_BASH_FAMILIES)
    + tuple(f"Bash(*=* {family} *)" for family in CLAUDE_WRITE_BASH_FAMILIES)
    + tuple(f"Bash(*=* {family})" for family in CLAUDE_WRITE_BASH_FAMILIES)
)
```

## Guarded elements

| ID | Guarded element | Axis | Neutralization | Detectors that went red |
|---|---|---|---|---|
| G1 | the `Bash(*=* f *)` derivation tuple | the mid-command assignment-prefixed form is emitted for every family | drop that `+ tuple(...)` line | `test_every_family_carries_both_assignment_rules`, `test_leading_assignments_shape_matches_a_new_rule`, `test_pinned_python_with_assignment_matches_a_new_rule`, `test_equals_before_a_family_word_is_a_known_match` (2275 suite); `test_settings_allow_is_the_eleven_targeted_rules`, `test_argv_stays_sandboxed_and_carries_rules` (1569) |
| G2 | the `Bash(*=* f)` derivation tuple | the trailing (no-argument) assignment-prefixed form is emitted for every family | drop that `+ tuple(...)` line | `test_every_family_carries_both_assignment_rules`, `test_bare_family_with_assignment_matches_a_new_rule` (the `SBX_PROBE=one npx` test); `test_settings_allow_is_the_eleven_targeted_rules`, `test_argv_stays_sandboxed_and_carries_rules` |
| G3 | the six exact-list / byte sites | the settings the channel emits are pinned literally | revert the derivation to the 11 prefix rules (both added tuples dropped) | one red test per site, table below |
| G4 | `test_allow_never_blanket` | no blanket or wildcard Bash allow; only the three admitted shapes | append `("Bash(*=* *)",)` to `CLAUDE_WRITE_BASH_ALLOW` | `test_allow_never_blanket` (the axis); the others are listed below and are not the axis |

## G1 — `Bash(*=* f *)` derivation

- **neutralization:** deleted the line `    + tuple(f"Bash(*=* {family} *)" for family in CLAUDE_WRITE_BASH_FAMILIES)` from `CLAUDE_WRITE_BASH_ALLOW`.
- **raw red** (files: `test_claude_write_env_prefix_2275.py`, `test_claude_write_channel_1569.py`; `--tb=line`; exit 1; assertion bodies elided with `…`):

```
FF.F..FF...F                                                             [100%]
E   AssertionError: python
    assert 'Bash(*=* python *)' in ['Bash(python:*)', 'Bash(python3:*)', 'Bash(pytest:*)', 'Bash(scripts/pinned-python:*)', 'Bash(echo:*)', 'Bash(npm:*)', ...]
…/test_claude_write_env_prefix_2275.py:77: AssertionError: python
E   AssertionError: assert []
     +  where [] = _matching([…], 'MONGODB_URI=mongodb://localhost:27017/weekly-eats-test SKIP_DB_SETUP=true npx --no-install vitest run --reporter=dot')
…/test_claude_write_env_prefix_2275.py:85: AssertionError: assert []
E   AssertionError: assert []
     +  where [] = _matching([…], 'PYTHONDONTWRITEBYTECODE=1 scripts/pinned-python -B -m pytest x -q')
…/test_claude_write_env_prefix_2275.py:95: AssertionError: assert []
E   AssertionError: assert []
     +  where [] = _matching([…], 'touch x=1 npx f')
…/test_claude_write_env_prefix_2275.py:112: AssertionError: assert []
E   AssertionError: assert {'allow': ['B... 'WebSearch']} == {'allow': ['B... 'WebSearch']}
…/test_claude_write_channel_1569.py:47: AssertionError: …
E   AssertionError: assert ['Bash(python...(npm:*)', ...] == ['Bash(python...(npm:*)', ...]
      At index 11 diff: 'Bash(*=* python)' != 'Bash(*=* python *)'
      Right contains 11 more items, first extra item: 'Bash(*=* python)'
…/test_claude_write_channel_1569.py:96: AssertionError: …
FAILED …/test_claude_write_env_prefix_2275.py::test_every_family_carries_both_assignment_rules
FAILED …/test_claude_write_env_prefix_2275.py::test_weekly_eats_shape_matches_a_new_rule
FAILED …/test_claude_write_env_prefix_2275.py::test_pinned_python_with_assignment_matches_a_new_rule
FAILED …/test_claude_write_env_prefix_2275.py::test_equals_before_a_family_word_is_a_known_match
FAILED …/test_claude_write_channel_1569.py::test_settings_allow_is_the_eleven_targeted_rules
FAILED …/test_claude_write_channel_1569.py::test_argv_stays_sandboxed_and_carries_rules
6 failed, 6 passed in 0.82s
```

- **restore:** re-inserted the deleted line after the first tuple by the inverse edit.
- **restore receipt:** `sed -n 338,343p plugins/superheroes/lib/engine_adapter.py` after the restore showed the three-tuple text quoted at the top of this record, and `git diff e64d79cc --stat -- plugins/superheroes/lib/engine_adapter.py` printed nothing.
- **raw green** (same two files, exit 0):

```
............                                                             [100%]
12 passed in 0.83s
```

## G2 — `Bash(*=* f)` derivation

- **neutralization:** deleted the line `    + tuple(f"Bash(*=* {family})" for family in CLAUDE_WRITE_BASH_FAMILIES)`.
- **raw red** (same two files; exit 1):

```
F.F....F...F                                                             [100%]
E   AssertionError: python
    assert 'Bash(*=* python)' in ['Bash(python:*)', 'Bash(python3:*)', 'Bash(pytest:*)', 'Bash(scripts/pinned-python:*)', 'Bash(echo:*)', 'Bash(npm:*)', ...]
…/test_claude_write_env_prefix_2275.py:78: AssertionError: python
E   AssertionError: assert []
     +  where [] = _matching([…], 'SBX_PROBE=one npx')
…/test_claude_write_env_prefix_2275.py:90: AssertionError: assert []
E   AssertionError: assert {'allow': ['B... 'WebSearch']} == {'allow': ['B... 'WebSearch']}
…/test_claude_write_channel_1569.py:47: AssertionError: …
E   AssertionError: assert ['Bash(python...(npm:*)', ...] == ['Bash(python...(npm:*)', ...]
      Right contains 11 more items, first extra item: 'Bash(*=* python)'
…/test_claude_write_channel_1569.py:96: AssertionError: …
FAILED …/test_claude_write_env_prefix_2275.py::test_every_family_carries_both_assignment_rules
FAILED …/test_claude_write_env_prefix_2275.py::test_bare_family_with_assignment_matches_a_new_rule
FAILED …/test_claude_write_channel_1569.py::test_settings_allow_is_the_eleven_targeted_rules
FAILED …/test_claude_write_channel_1569.py::test_argv_stays_sandboxed_and_carries_rules
4 failed, 8 passed in 1.80s
```

- **restore:** re-inserted the deleted line after the second tuple by the inverse edit.
- **restore receipt:** `sed -n 338,343p` showed the three-tuple text again; `git diff e64d79cc --stat -- plugins/superheroes/lib/engine_adapter.py` printed nothing.
- **raw green** (exit 0):

```
............                                                             [100%]
12 passed in 0.92s
```

## G3 — the six exact-list / byte sites

- **neutralization:** removed both added tuple lines, leaving `CLAUDE_WRITE_BASH_ALLOW = ( tuple(f"Bash({family}:*)" …) )` — the 11 prefix rules only.
- **raw red** (files: `test_claude_write_channel_1569.py`, `test_claude_write_defaults_1600.py`, `test_claude_write_sandbox_1554.py`, `test_sandbox_access_dispatch_1562.py`; `--tb=no -rf`; exit 1):

```
F...FF.................................F............................FF.. [ 54%]
...........................................................              [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_settings_allow_is_the_eleven_targeted_rules
FAILED plugins/superheroes/lib/tests/test_claude_write_channel_1569.py::test_argv_stays_sandboxed_and_carries_rules
FAILED plugins/superheroes/lib/tests/test_claude_write_defaults_1600.py::test_allow_list_is_the_eleven_literal_rules
FAILED plugins/superheroes/lib/tests/test_claude_write_sandbox_1554.py::test_settings_json_keys
FAILED plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py::test_all_off_settings_are_byte_identical
FAILED plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py::test_all_off_differs_from_0_38_0_only_by_allow_rules
6 failed, 125 passed in 6.73s
```

Per-site red test id:

| Site | Red test id |
|---|---|
| `test_claude_write_channel_1569.py`, exact list in `test_settings_allow_is_the_eleven_targeted_rules` | `test_claude_write_channel_1569.py::test_settings_allow_is_the_eleven_targeted_rules` |
| `test_claude_write_channel_1569.py`, list in `test_argv_stays_sandboxed_and_carries_rules` | `test_claude_write_channel_1569.py::test_argv_stays_sandboxed_and_carries_rules` |
| `test_claude_write_defaults_1600.py` (:77 region) | `test_claude_write_defaults_1600.py::test_allow_list_is_the_eleven_literal_rules` |
| `test_claude_write_sandbox_1554.py` (:102 region) | `test_claude_write_sandbox_1554.py::test_settings_json_keys` |
| `test_sandbox_access_dispatch_1562.py` (:63 region, the byte string) | `test_sandbox_access_dispatch_1562.py::test_all_off_settings_are_byte_identical` |
| `test_sandbox_access_dispatch_1562.py` (:199 region, the list) | `test_sandbox_access_dispatch_1562.py::test_all_off_differs_from_0_38_0_only_by_allow_rules` |

All six sites went red, one distinct test each.

- **restore:** re-inserted both tuple lines by the inverse edit.
- **restore receipt:** `sed -n 338,343p` showed the three-tuple text; `git diff e64d79cc --stat -- plugins/superheroes/lib/engine_adapter.py` printed nothing.
- **raw green** (same four files, exit 0):

```
........................................................................ [ 54%]
...........................................................              [100%]
131 passed in 6.37s
```

## G4 — `test_allow_never_blanket`

- **neutralization:** appended the line `    + ("Bash(*=* *)",)` as a fourth term of `CLAUDE_WRITE_BASH_ALLOW`.
- **raw red** (files: the five suites below; `--tb=line -rf`; exit 1; long diffs elided with `…`):

```
F....F.FF..FF.................................F......................... [ 52%]
...FF.............................................................       [100%]
E   AssertionError: Bash(*=* *)
    assert None
     +  where None = <built-in method match of re.Pattern object at 0x…>('Bash(*=* *)')
     +    where <built-in method match of re.Pattern object at 0x…> = re.compile('^Bash\\((?:[^()*=\\s]+:\\*|\\*=\\* [^()*=\\s]+ \\*|\\*=\\* [^()*=\\s]+)\\)$').match
…/test_claude_write_channel_1569.py:71: AssertionError: Bash(*=* *)
FAILED …/test_claude_write_env_prefix_2275.py::test_every_family_carries_both_assignment_rules
FAILED …/test_claude_write_env_prefix_2275.py::test_assignment_before_a_non_family_command_matches_no_rule
FAILED …/test_claude_write_channel_1569.py::test_settings_allow_is_the_eleven_targeted_rules
FAILED …/test_claude_write_channel_1569.py::test_allow_never_blanket
FAILED …/test_claude_write_channel_1569.py::test_argv_stays_sandboxed_and_carries_rules
FAILED …/test_claude_write_defaults_1600.py::test_allow_list_is_the_eleven_literal_rules
FAILED …/test_claude_write_sandbox_1554.py::test_settings_json_keys
FAILED …/test_sandbox_access_dispatch_1562.py::test_all_off_settings_are_byte_identical
FAILED …/test_sandbox_access_dispatch_1562.py::test_all_off_differs_from_0_38_0_only_by_allow_rules
9 failed, 129 passed in 6.12s
```

The axis detector is `test_allow_never_blanket` (its failure message names the refused rule `Bash(*=* *)` against the shape regex). The other eight reddened because they pin the rule list exactly (the length census, the exact-list and byte sites, and the 2275 test that no rule matches `SBX_PROBE=two touch f`); they are not the axis.

- **restore:** deleted the appended line by the inverse edit.
- **restore receipt:** `git diff e64d79cc -- plugins/superheroes/lib/engine_adapter.py` printed nothing (empty output between the markers `--- diff vs e64d79cc` and `--- (end diff)`), and `sed -n 338,343p` showed the three-tuple text quoted at the top of this record.
- **raw green** (the five files, exit 0):

```
........................................................................ [ 52%]
..................................................................       [100%]
138 passed in 7.73s
```

## The shape-regex detector (added by WO-B2)

`test_allow_rule_shape_admits_three_shapes_and_refuses_blankets` runs the same module-level `_ALLOW_RULE_SHAPE` over `Bash`, `Bash(*)`, `Bash(*=* *)`, `Bash(*=* *  *)`, `Bash(* npx *)`, `Bash(*=* np*x *)`, `Bash(*:*)`, `Bash(*=* npx :*)` (all refused) and over `Bash(npx:*)`, `Bash(*=* npx *)`, `Bash(*=* scripts/pinned-python)` (all admitted). It guards the regex itself, not `engine_adapter.py`, so it sits outside G1–G4 and no neutralization of `engine_adapter.py` can make it red; **no bite-proof was run for it** (the order declared none). It passed in the 623-test run of the full six-file set and in every green run above that includes `test_claude_write_channel_1569.py`.

## Fail-closed edges and their covering tests

| Edge | Disposition | Covering test |
|---|---|---|
| E1 `Bash(*=* *)` refused | the shape regex refuses it; G4 shows the live allow list going red when it is injected | `test_allow_rule_shape_admits_three_shapes_and_refuses_blankets`, `test_allow_never_blanket` |
| E2 a family part carrying `*` refused | the family group `[^()*=\s]+` excludes `*`; refused spellings `Bash(* npx *)`, `Bash(*=* np*x *)`, `Bash(*:*)` | `test_allow_rule_shape_admits_three_shapes_and_refuses_blankets` |
| E3 bare `Bash` / `Bash(*)` refused | the explicit `rule not in ("Bash", "Bash(*)")` line, and the regex rejects both | `test_allow_never_blanket`, `test_allow_rule_shape_admits_three_shapes_and_refuses_blankets` |
