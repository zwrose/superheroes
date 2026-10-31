# #1795 bite-proof — the area name kept when sample paths are stripped (WO-H: `lane_call.why_line_paths_stripped`)

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Per-element bite-proof following `plugins/superheroes/rubric/bite-proof.md`. The element was neutralized with one targeted edit, its single test node ran alone and went red, the edit was undone by the inverse edit, the restored line was quoted back, and the same node ran green. The test file was not edited between the red and the green. Redaction: none needed.

Declared guarded-element set: P1, as dispatched.

Command for both runs (never `-k`, never filtered):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_lane_call.py::test_stripping_a_line_built_for_a_longer_area_name_keeps_that_whole_name' -q
```

## P1 — the longest-match choice

Axis: the area name kept when one name prefixes another; the longer name cut back to its shorter prefix.

Neutralization: `plugins/superheroes/lib/lane_call.py` line 68, back to first-match:

```
name = max((n for n in names if line.startswith("%s %s (" % (WHY_TOUCHES, n))), key=len, default=None)
```
became
```
name = next((n for n in names if line.startswith("%s %s (" % (WHY_TOUCHES, n))), None)
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_stripping_a_line_built_for_a_longer_area_name_keeps_that_whole_name ___

    def test_stripping_a_line_built_for_a_longer_area_name_keeps_that_whole_name():
        # axis: the area name kept when one name prefixes another; the longer name cut back to its shorter prefix
        names = ["Payments", "Payments (refunds)"]
        line = "%s %s (%s)" % (L.WHY_TOUCHES, "Payments (refunds)", "src/refunds/a.py, src/refunds/b.py")
>       assert L.why_line_paths_stripped(line, names) == "%s Payments (refunds)" % L.WHY_TOUCHES
E       AssertionError: assert 'touches-risk-area: Payments' == 'touches-risk...nts (refunds)'
E         
E         - touches-risk-area: Payments (refunds)
E         ?                            ----------
E         + touches-risk-area: Payments

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_lane_call.py:463: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_stripping_a_line_built_for_a_longer_area_name_keeps_that_whole_name
1 failed in 0.15s
```

Restore: the inverse edit, putting the `max(..., key=len, default=None)` line back.

Restore receipt, `lane_call.py` line 68 as grep printed it after the restore:

```
68:        name = max((n for n in names if line.startswith("%s %s (" % (WHY_TOUCHES, n))), key=len, default=None)
```

Green:

```
.                                                                        [100%]
1 passed in 0.12s
```

Note: the sibling test `test_stripping_a_line_built_for_the_shorter_area_name_keeps_that_name` passes under both first-match and longest-match; it guards against the longest-match choice widening a `Payments` line, not against first-match.
