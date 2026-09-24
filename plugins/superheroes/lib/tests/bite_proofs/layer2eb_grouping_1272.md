# Layer 2e-b — absent `grouping` key refused at submit (#1272 WO-C)

**Declared guarded-element set (exactly one):** `synthesis_results_fault`'s
missing-`grouping`-key leg — `if "grouping" not in artifact: return "synthesis artifact carries no …"`.

Disclosure D-6 from `layer2e_folds_1272.md` is closed by
`test_synthesis_results_fault_absent_grouping_key_message_and_controls`.

---

## K2b — the missing-`grouping`-key leg (D-6)

**Guarded element.** `round_driver.synthesis_results_fault`, `if "grouping" not in artifact: return "synthesis artifact carries no \`grouping\` key; …"`.
**Axis:** an **absent** `grouping` key is refused with the synthesis-specific message (while `grouping: null` and `grouping: []` fold).

**Neutralization.** `if "grouping" not in artifact:` → `if False:`.

**Detector.** `test_synthesis_results_fault_absent_grouping_key_message_and_controls`.

**Red** (EXIT=1, scoped pytest — 3 failed including stale golden before regeneration; D-6 axis failure):

```
____ test_synthesis_results_fault_absent_grouping_key_message_and_controls _____

    def test_synthesis_results_fault_absent_grouping_key_message_and_controls():
        """Axis: synthesis_results_fault refuses absent grouping key; null/[] fold; non-dict refused."""
        fault = RD.synthesis_results_fault({})
        assert fault is not None
>       assert "synthesis artifact carries no" in fault
E       AssertionError: assert 'synthesis artifact carries no' in '`grouping` is missing'

plugins/superheroes/lib/tests/test_layer2e_staged_ids_1272.py:268: AssertionError
```

**Fail-direction controls under neutralization.** `null` and `[]` arms in the same test stayed green (failure is only on the absent-key message substring). Non-dict control would still pass on the lower contract's type check path.

**Restore.** Inverse edit (`if False:` → `if "grouping" not in artifact:`).

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/round_driver.py` → empty.

**Green** (EXIT=0, scoped pytest after restore, before golden regeneration — 1 failed on stale golden only; D-6 passed):

```
103 passed in 32.39s
```

(final closing run after golden regeneration: `103 passed in 32.39s`, EXIT=0)
