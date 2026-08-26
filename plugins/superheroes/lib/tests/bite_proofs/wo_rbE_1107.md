# WO-rbE (#1107) bite-proof — gap-sweep re-emission `unknown-seat` pin

## BP-1 — `unknown-seat` refusal token restated in round-driver.md (`test_unknown_seat_refusal_token_in_round_driver_doc`)

**Guarded element:** `skills/review-code/reference/round-driver.md`'s new **Gap-sweep
re-emission trap** paragraph — axis: it names the literal `round_records.py` refusal
token `unknown-seat` that `record-result --sweep` raises when a stray prior-wave landing
file maps to no slot in the current roster; a silent rename of that token in code would
strand the doc's recovery guidance behind a dead reference.

**Neutralization:** targeted, reversible edit to the doc paragraph only (the code side —
`_refuse("unknown-seat", ...)` in `plugins/superheroes/lib/round_records.py` — was left
untouched; this neutralizes the doc's restatement, not the code, since the axis is "the doc
still says the real token"):

```diff
-hard-refuses `unknown-seat` for each one; (5) `advance` then refuses too, and the phase is left
+hard-refuses `unrecognized-seat` for each one; (5) `advance` then refuses too, and the phase is left
```

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-rbe -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_unknown_seat_refusal_token_in_round_driver_doc -q -p no:xdist
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_unknown_seat_refusal_token_in_round_driver_doc ______________

    def test_unknown_seat_refusal_token_in_round_driver_doc():
        """§11: round-driver.md's gap-sweep re-emission trap restates round_records.py's own
        `unknown-seat` sweep refusal literally — a rename of that refusal reason would silently
        strand the doc's recovery guidance behind a token `record-result --sweep` no longer emits."""
        home = _read(os.path.join("lib", "round_records.py"))
        assert '_refuse("unknown-seat"' in home, (
            "round_records.py: expected literal `_refuse(\"unknown-seat\", ...)` call not found "
            "(renamed/refactored? update this pin's home check along with the rename)"
        )
        doc = _read("skills/review-code/reference/round-driver.md")
>       assert "unknown-seat" in doc, (
            "round-driver.md: gap-sweep re-emission trap must name the `unknown-seat` refusal "
            "that round_records.sweep_landing raises when a stray landing file maps to no roster "
            "slot in the current manifest"
        )
E       AssertionError: round-driver.md: gap-sweep re-emission trap must name the `unknown-seat` refusal that round_records.sweep_landing raises when a stray landing file maps to no roster slot in the current manifest
E       assert 'unknown-seat' in '# Contents\n\n- [The one entrypoint](#the-one-entrypoint)\n- [next / submit protocol](#next--submit-protocol)\n- [che...ver.py` and the PARITY receipt in `test_retry_budget_parity.py`.\nTreat `round_driver.py` as the contract of record.\n'

plugins/superheroes/lib/tests/test_ssot_drift.py:234: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_unknown_seat_refusal_token_in_round_driver_doc
1 failed in 0.40s
```

**Restore:** reverted the doc line back to the real token (inverse edit).

**Restore receipt:** `git diff` over the neutralized path shows only the intended
12-line addition, with the restored line reading:

```
hard-refuses `unknown-seat` for each one; (5) `advance` then refuses too, and the phase is left
```

`git status --porcelain` after restore showed only the two files this order touched
(`round-driver.md`, `test_ssot_drift.py`), both already staged for the order's own commit —
no residue from the neutralization.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.25s
```
