# Bite-proof record — #1271 WO-P1-B (disclosure source scanners follow their subject)

Contract: `rubric/bite-proof.md`. Proofs ran with the **detector unedited**; neutralizations were
targeted, reversible edits to `receipt_disclosures.py`, reverted by exact inverse before the next
proof or green half.

**The guarded-element set — three elements:**

| # | Guarded element | Axis |
|---|---|---|
| D1 | `test_e8_build_receipt_round_entry_name_is_never_rebound` | `rrec` is bound exactly once to `state["rounds"][rkey]` across the receipt build path |
| D2 | `test_e7_helper_channel_reads_guarded_by_isinstance_list` | `skew_records` / `seat_map_violations` guard channel reads with `isinstance(..., list)` |
| D3 | `test_disclosure_channels_have_one_home_read_by_receipt_and_resume` | every `RESUMABLE_DISCLOSURE_CHANNELS` name is consumed by a round-record read in the scanned union |

---

## Detector D1 — round-entry name never rebound (E8)

**Guarded element.** `receipt_disclosures.build_degraded_prose` (`plugins/superheroes/lib/receipt_disclosures.py:387`).
**Axis.** The round-entry name `rrec` must not be rebound after the lookup from `state["rounds"][rkey]`.

**Neutralization:**

```python
         rrec = state["rounds"][rkey]
+        rrec = {}
         declared = receipt_round_disclosures(rrec, form, state)
```

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_e8_build_receipt_round_entry_name_is_never_rebound ____________

    def test_e8_build_receipt_round_entry_name_is_never_rebound():
        """E8 — rrec in the receipt build path is bound exactly once to state[\"rounds\"][rkey]."""
        sites = []
        for fn in (round_driver.build_receipt, receipt_disclosures.build_degraded_prose):
            sites.extend(_function_rrec_binding_sites(fn))
        msg = (
            "%s A shadowed rrec makes every non-channel round-entry read return None silently on "
            "the certification receipt." % _INVARIANT_E8
        )
>       assert len(sites) == 1, msg + " Found %d rrec binding(s)." % len(sites)
E       AssertionError: Inside build_receipt, the name rrec is bound exactly once, from the round-entry lookup state["rounds"][rkey]. It is never rebound to anything else. A shadowed rrec makes every non-channel round-entry read return None silently on the certification receipt. Found 2 rrec binding(s).
E       assert 2 == 1
E        +  where 2 = len([<ast.Assign object at 0x10a9fddf0>, <ast.Assign object at 0x109ee2760>])

plugins/superheroes/lib/tests/test_round_driver_receipt_disclosure_consumption.py:251: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_receipt_disclosure_consumption.py::test_e8_build_receipt_round_entry_name_is_never_rebound
1 failed in 0.17s
```

**Restore.** Inverse edit removing the `rrec = {}` shadow line.

**Restore receipt.** Restored lines:

```python
        rrec = state["rounds"][rkey]
        declared = receipt_round_disclosures(rrec, form, state)
```

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 0.17s
```

---

## Detector D2 — helper channel reads list-guarded (E7)

**Guarded element.** `receipt_disclosures.skew_records` (`plugins/superheroes/lib/receipt_disclosures.py:224-227`).
**Axis.** `pluginVersionSkew` must not be iterated via a bare `rec.get(...) or []`.

**Neutralization:**

```python
-        skew = rec.get("pluginVersionSkew")
-        if not isinstance(skew, list):
-            continue
-        for row in skew:
+        for row in rec.get("pluginVersionSkew") or []:
```

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_e7_helper_channel_reads_guarded_by_isinstance_list ____________

    def test_e7_helper_channel_reads_guarded_by_isinstance_list():
        """E7 — skew_records and seat_map_violations guard channel reads with isinstance(..., list)."""
>       assert _helper_channel_read_is_list_guarded(
            receipt_disclosures.skew_records, "pluginVersionSkew"), (
            "%s skew_records must not iterate a bare rec.get(pluginVersionSkew) or []"
            % _INVARIANT_B)
E       AssertionError: Building a terminal receipt never raises on a malformed per-round disclosure channel: helper-reached channel readers must tolerate non-list values structurally. skew_records must not iterate a bare rec.get(pluginVersionSkew) or []
E       assert False
E        +  where False = _helper_channel_read_is_list_guarded(<function skew_records at 0x10a5600d0>, 'pluginVersionSkew')
E        +    where <function skew_records at 0x10a5600d0> = receipt_disclosures.skew_records

plugins/superheroes/lib/tests/test_round_driver_receipt_disclosure_consumption.py:356: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_receipt_disclosure_consumption.py::test_e7_helper_channel_reads_guarded_by_isinstance_list
1 failed in 0.21s
```

**Restore.** Inverse edit restoring the `skew` local + `isinstance(..., list)` guard.

**Restore receipt.** Restored lines:

```python
        skew = rec.get("pluginVersionSkew")
        if not isinstance(skew, list):
            continue
        for row in skew:
```

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 0.21s
```

---

## Detector D3 — channel-home census (receipt + resume)

**Guarded element.** `RESUMABLE_DISCLOSURE_CHANNELS` registry entry with no consumer.
**Axis.** A channel added to the restorable set must be read from `rec|rrec|declared` somewhere in the scanned union.

**Neutralization:**

```python
     "gateGuidanceRowCarried": dict_list,
+    "__bite_no_consumer__": str_list,
 }
```

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_disclosure_channels_have_one_home_read_by_receipt_and_resume _______

    def test_disclosure_channels_have_one_home_read_by_receipt_and_resume():
        """The census is the whole story only if `build_receipt` and the resume both READ the constant
        rather than a hand-copied literal list — and only if every named channel is really consumed by
        the receipt (a fossil channel would pass the census while disclosing nothing)."""
        tree, ast_mod = _round_driver_ast()
        for fn in ("build_receipt", "_restore_round_disclosures"):
            names = {n.id for n in ast_mod.walk(_fn_node(tree, ast_mod, fn))
                     if isinstance(n, ast_mod.Name)}
            assert "RESUMABLE_DISCLOSURE_CHANNELS" in names, \
                "%s must read the channel set from its one home" % fn
        src = _disclosure_channel_consumer_source()
        for chan in RD.RESUMABLE_DISCLOSURE_CHANNELS:
>           assert source_obj_accesses_key(src, "rec|rrec|declared", chan), \
                "%r is named restorable but no round record read consumes it" % chan
E           AssertionError: '__bite_no_consumer__' is named restorable but no round record read consumes it
E           assert False
E            +  where False = source_obj_accesses_key('#!/usr/bin/env python3\n"""Disclosure-channel vocabulary, selection rule, and degraded-prose collector — leaf module.....\n    return 1 if out.get("reason") == "receipt-fault" else 0\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'rec|rrec|declared', '__bite_no_consumer__')

plugins/superheroes/lib/tests/test_round_driver.py:3707: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_disclosure_channels_have_one_home_read_by_receipt_and_resume
1 failed in 1.15s
```

**Restore.** Inverse edit removing the `__bite_no_consumer__` registry entry.

**Restore receipt.** Restored lines:

```python
    "gateGuidanceRowCarried": dict_list,
}
```

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 1.15s
```

---

## Combined green half (post-restore)

```
...                                                                      [100%]
3 passed in 1.73s
```

Post-restore `git status --porcelain` over `plugins/superheroes/lib/receipt_disclosures.py` showed no
modifications — production source restored to neutral.
