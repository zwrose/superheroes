# #2537 bite-proof — a seat in any maker's family is a maker seat in the seat-map check

**Provenance:** orchestrator-typed (light lane), `plugins/superheroes/lib/seat_map.py`. Shape and ceilings: `plugins/superheroes/rubric/bite-proof.md`.

**Guarded-element set (declared before the review):** K1 the non-author maker branch in `verify`; K2 `_named_makers` reading the map's `makerFamilies`; K3 `_named_makers` reading the session's extra makers; K4 the session makers in `classify_violations`' liveness maker set (registry row V953-a).

**Every run below** is the same command, run at the committed head with one targeted, revertible edit applied (none for the green run). Each edit was undone by its inverse edit, and `git status --short` read empty after the last restore. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

```
scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest \
  plugins/superheroes/lib/tests/test_seat_map.py plugins/superheroes/lib/tests/test_round_driver.py \
  -q --no-header -p no:cacheprovider --tb=line \
  -k "maker_family_breach or whatever_the_liveness or named_alone or reads_as_before or malformed_maker_member or keeps_its_liveness_rule or session_maker_as_a_live_alternative or never_certifies_independent or certifies_as_before or reads_constraint_violated_for_unpinned_seats or no_variant_of_the_two_shapes or omits_an_earlier_maker_does_not_release or former_fixer_family_is_a_maker"
```

The one stderr line every run prints (a `uv` deprecation warning about `UV_NATIVE_TLS`) is left out of each capture below.

## K1 — the non-author maker branch (`seat_map.py` `verify`)

- **axis:** a filled seat in a maker family other than the author's, named by the map or the session, is a `maker-family` breach whatever the liveness, so no such panel certifies independent.

**neutralization:**
```diff
-            if seat_fam in other_makers:
+            if False and seat_fam in other_makers:
```

**raw red** (exit 1). The summary block is verbatim; the per-failure detail lines above it are elided (each is an `AssertionError` on the asserted list or shape). The red is on the axis: the unpinned, recorded shapes read `full-panel-confirmed` (the fail-open the issue names, with V953-a's union back in place) and the pinned ones read `-degraded`.
```
FFFF....FFFFF.F.F.F.FFFF.                                                [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_maker_family_the_map_names_is_a_maker_family_breach
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_session_maker_family_is_a_maker_family_breach
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_non_author_maker_seat_is_a_breach_whatever_the_liveness
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_one_seat_in_a_named_maker_family_is_named_alone
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_reads_constraint_violated_for_unpinned_seats
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_reads_constraint_violated_for_unpinned_seats
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[a-True-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[a-False-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[b-True-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[b-False-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_map_naming_its_seats_family_a_maker_never_certifies_independent[True-True]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_map_naming_its_seats_family_a_maker_never_certifies_independent[True-False]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_map_naming_its_seats_family_a_maker_never_certifies_independent[False-True]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_map_naming_its_seats_family_a_maker_never_certifies_independent[False-False]
16 failed, 9 passed, 722 deselected in 5.75s
```
The unpinned rows' detail lines read `assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'` (`test_round_driver.py:4054`, `:4060`, `:4080`).

**restore:** the inverse edit (`False and ` removed).

## K2 — the map's `makerFamilies` (`seat_map.py` `_named_makers`)

- **axis:** a maker the map's own `makerFamilies` names is a maker for `verify`.

**neutralization:**
```diff
-    named = {f for f in (raw if isinstance(raw, list) else []) if isinstance(f, str) and f}
+    named = {f for f in (raw if isinstance(raw, list) else []) if isinstance(f, str) and f and False}
```

**raw red** (exit 1; complete):
```
F.FF.....................                                                [100%]
=================================== FAILURES ===================================
E   AssertionError: assert [] == ['code-review..., 'test-role']
      
      Right contains 4 more items, first extra item: 'code-reviewer'
      Use -v to get more diff
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4878: AssertionError: assert [] == ['code-review..., 'test-role']
E   AssertionError: (['codex'], 'synthesized')
    assert [] == ['code-review..., 'test-role']
      
      Right contains 4 more items, first extra item: 'code-reviewer'
      Use -v to get more diff
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4901: AssertionError: (['codex'], 'synthesized')
E   AssertionError: assert [] == ['test-role']
      
      Right contains one more item: 'test-role'
      Use -v to get more diff
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4907: AssertionError: assert [] == ['test-role']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_maker_family_the_map_names_is_a_maker_family_breach
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_non_author_maker_seat_is_a_breach_whatever_the_liveness
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_one_seat_in_a_named_maker_family_is_named_alone
3 failed, 22 passed, 722 deselected in 5.96s
```
The round-driver test `test_a_map_naming_its_seats_family_a_maker_never_certifies_independent` stays green here, as it should: the driver passes the session's makers, and `accumulated_maker_families` already holds every receipt's `makerFamilies`, so the certificate path reaches the map's makers through K3 too. K2 is what holds for a single map read without session state (`to_receipt`'s stored `violations`, a direct `verify`).

**restore:** the inverse edit (`and False` removed).

## K3 — the session's extra makers (`seat_map.py` `_named_makers`)

- **axis:** a maker the session names (`extra_makers`: a later map's omission, a former fixer's family) is a maker for `verify` and for the liveness excusal.

**neutralization:**
```diff
-    named.update(f for f in extra_makers if isinstance(f, str) and f)
+    named.update(f for f in extra_makers if isinstance(f, str) and f and False)
```

**raw red** (exit 1; complete):
```
.F.....FFF..F...F........                                                [100%]
=================================== FAILURES ===================================
E   AssertionError: assert [] == ['code-review..., 'test-role']
      
      Right contains 4 more items, first extra item: 'code-reviewer'
      Use -v to get more diff
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4891: AssertionError: assert [] == ['code-review..., 'test-role']
E   AssertionError: assert [{'constraint...native-live'}] == []
      
      Left contains one more item: {'constraint': 'critical-diversity', 'evidence': 'alternative-live'}
      Use -v to get more diff
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4958: AssertionError: assert [{'constraint...native-live'}] == []
E   AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
      
      - full-panel-confirmed-constraint-violated
      + full-panel-confirmed-degraded
/home/user/wt-2537/plugins/superheroes/lib/tests/test_round_driver.py:3977: AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
E   AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
      
      - full-panel-confirmed-constraint-violated
      + full-panel-confirmed-degraded
/home/user/wt-2537/plugins/superheroes/lib/tests/test_round_driver.py:3992: AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
E   AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
      
      - full-panel-confirmed-constraint-violated
      + full-panel-confirmed-degraded
/home/user/wt-2537/plugins/superheroes/lib/tests/test_round_driver.py:4080: AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
E   AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
      
      - full-panel-confirmed-constraint-violated
      + full-panel-confirmed-degraded
/home/user/wt-2537/plugins/superheroes/lib/tests/test_round_driver.py:4080: AssertionError: assert 'full-panel-c...rmed-degraded' == 'full-panel-c...aint-violated'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_session_maker_family_is_a_maker_family_breach
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_the_liveness_excusal_does_not_count_a_session_maker_as_a_live_alternative
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[a-True-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[b-True-True-full-panel-confirmed-constraint-violated]
6 failed, 19 passed, 722 deselected in 2.87s
```

**restore:** the inverse edit (`and False` removed).

## K4 — the session makers in the liveness excusal (`seat_map.py` `classify_violations`)

- **axis (V953-a):** the session's makers are makers in the excusal's arithmetic, never live alternatives. This is the union vet 953 withdrew (`wo_a_2530_single_vendor_panel`, J1); with K1 in place a seat in any maker's family is a breach, so the union can no longer clear such a panel, and J1's guard of its absence is superseded by this element.

**neutralization:**
```diff
-        maker_set = _named_makers(seat_map, extra_makers)
+        maker_set = _named_makers(seat_map)
```

**raw red** (exit 1; complete):
```
.......F.................                                                [100%]
=================================== FAILURES ===================================
E   AssertionError: assert [{'constraint...native-live'}] == []
      
      Left contains one more item: {'constraint': 'critical-diversity', 'evidence': 'alternative-live'}
      Use -v to get more diff
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4958: AssertionError: assert [{'constraint...native-live'}] == []
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_the_liveness_excusal_does_not_count_a_session_maker_as_a_live_alternative
1 failed, 24 passed, 722 deselected in 2.94s
```

**restore:** the inverse edit (`, extra_makers` put back).

## Green, after every restore

**raw green** (exit 0; complete):
```
.........................                                                [100%]
25 passed, 722 deselected in 3.19s
```

(end of record)
