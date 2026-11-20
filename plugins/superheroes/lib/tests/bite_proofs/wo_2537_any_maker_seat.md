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

# Re-run after vet 982's fix order — head `1b3b1245`, every detector by its exact node id

Vet 982 found that a malformed `makerFamilies` let the liveness excusal (with K4's session makers) clear a recorded `critical-diversity`. The fix order added two elements to the declared set, and every element is re-run here at `1b3b1245` (the fix commit), selected by exact node id, never by `-k`.

**Declared set, extended (declared in the advisor's fix order, before the returning review):** K1–K4 as above; **K5** the malformed-`makerFamilies` branch in `classify_violations`' liveness excusal; **K6** the author's exclusion (`- {author_family}`) from the other-makers set in `verify`.

**Command** (each run; the node list is the 20 node ids below, one per line in a file, passed as arguments):
```
scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest <the 20 node ids> -q --no-header -p no:cacheprovider --tb=line
```
```
plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_maker_family_the_map_names_is_a_maker_family_breach
plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_session_maker_family_is_a_maker_family_breach
plugins/superheroes/lib/tests/test_seat_map.py::test_a_non_author_maker_seat_is_a_breach_whatever_the_liveness
plugins/superheroes/lib/tests/test_seat_map.py::test_one_seat_in_a_named_maker_family_is_named_alone
plugins/superheroes/lib/tests/test_seat_map.py::test_a_panel_outside_every_maker_family_reads_as_before
plugins/superheroes/lib/tests/test_seat_map.py::test_a_malformed_maker_member_names_no_maker_for_verify
plugins/superheroes/lib/tests/test_seat_map.py::test_an_author_family_seat_keeps_its_liveness_rule
plugins/superheroes/lib/tests/test_seat_map.py::test_an_author_family_seat_keeps_its_liveness_rule_when_the_map_names_the_author
plugins/superheroes/lib/tests/test_seat_map.py::test_the_liveness_excusal_does_not_count_a_session_maker_as_a_live_alternative
plugins/superheroes/lib/tests/test_seat_map.py::test_a_malformed_maker_list_never_lets_the_liveness_excusal_clear_critical_diversity
plugins/superheroes/lib/tests/test_seat_map.py::test_a_malformed_maker_list_keeps_the_pin_excusal
plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_reads_constraint_violated_for_unpinned_seats
plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_reads_constraint_violated_for_unpinned_seats
plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base
plugins/superheroes/lib/tests/test_round_driver.py::test_a_map_naming_its_seats_family_a_maker_never_certifies_independent
plugins/superheroes/lib/tests/test_round_driver.py::test_a_panel_outside_every_maker_family_certifies_as_before
plugins/superheroes/lib/tests/test_round_driver.py::test_a_malformed_maker_list_with_a_session_maker_never_certifies_cleaner_than_main
plugins/superheroes/lib/tests/test_round_driver.py::test_a_string_maker_list_with_only_claude_and_cursor_live_now_reads_constraint_violated
```

**Baseline before any neutralization** (exit 0): `32 passed in 2.71s`.

Each neutralization below is the same targeted, revertible edit as in the first part of this record (K1–K4) or the one stated (K5, K6), undone by its inverse edit. `git status --short` read empty after the last restore. For each red, the short-summary block is verbatim; the per-failure detail lines are elided except for K5 and K6, whose detail lines are quoted in part.

**K1 red** (`if False and seat_fam in other_makers:`; exit 1):
```
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
16 failed, 16 passed in 2.84s
```

**K2 red** (`... if isinstance(f, str) and f and False}` on the map's members; exit 1):
```
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_maker_family_the_map_names_is_a_maker_family_breach
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_non_author_maker_seat_is_a_breach_whatever_the_liveness
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_one_seat_in_a_named_maker_family_is_named_alone
3 failed, 29 passed in 5.24s
```

**K3 red** (`... if isinstance(f, str) and f and False)` on the extra makers; exit 1):
```
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_seat_in_a_session_maker_family_is_a_maker_family_breach
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_the_liveness_excusal_does_not_count_a_session_maker_as_a_live_alternative
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_malformed_maker_list_never_lets_the_liveness_excusal_clear_critical_diversity
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_later_receipt_that_omits_an_earlier_maker_does_not_release_it_from_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_former_fixer_family_is_a_maker_for_the_exemption
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[a-True-True-full-panel-confirmed-constraint-violated]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_no_variant_of_the_two_shapes_reads_cleaner_than_base[b-True-True-full-panel-confirmed-constraint-violated]
7 failed, 25 passed in 2.55s
```
(The malformed-list detector reds here on its evidence label: with no session maker the record reads `alternative-live`, not the `unproven-liveness` it asserts.)

**K4 red** (`maker_set = _named_makers(seat_map)`; exit 1):
```
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_the_liveness_excusal_does_not_count_a_session_maker_as_a_live_alternative
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_malformed_maker_list_never_lets_the_liveness_excusal_clear_critical_diversity
2 failed, 30 passed in 2.83s
```

## K5 — a malformed `makerFamilies` in the liveness excusal (`seat_map.py` `classify_violations`)

- **axis:** a map whose `makerFamilies` is not a list of non-empty strings never has its `critical-diversity` excused by liveness; it stays unexcused with `unproven-liveness`, and the certificate reads no cleaner than main.

**neutralization:**
```diff
-        elif _maker_families_malformed(seat_map):
+        elif False and _maker_families_malformed(seat_map):
```

**raw red** (exit 1). The three malformed shapes (`"openai"`, `["anthropic", 5]`, `"xai"`) with session maker openai read `full-panel-confirmed`, the vet's fail-open:
```
E   AssertionError: ('openai', ('openai',))
    assert [] == [{'constraint...en-liveness'}]
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4965: AssertionError: ('openai', ('openai',))
E   AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
/home/user/wt-2537/plugins/superheroes/lib/tests/test_round_driver.py:4133: AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
(the same line twice more for test_round_driver.py:4133)
/home/user/wt-2537/plugins/superheroes/lib/tests/test_round_driver.py:4142: AssertionError: assert 'full-panel-confirmed' == 'full-panel-c...aint-violated'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_malformed_maker_list_never_lets_the_liveness_excusal_clear_critical_diversity
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_malformed_maker_list_with_a_session_maker_never_certifies_cleaner_than_main[openai]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_malformed_maker_list_with_a_session_maker_never_certifies_cleaner_than_main[maker_families1]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_malformed_maker_list_with_a_session_maker_never_certifies_cleaner_than_main[xai]
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_string_maker_list_with_only_claude_and_cursor_live_now_reads_constraint_violated
5 failed, 27 passed in 2.71s
```

**restore:** the inverse edit (`False and ` removed).

## K6 — the author's exclusion from the other makers (`seat_map.py` `verify`)

- **axis:** the author's own family is never an "other maker", even when the map's `makerFamilies` names it, so an author seat with no live alternative keeps its `same-family` degradation and is not a `maker-family` breach. Before this order no detector bit this mutant.

**neutralization:**
```diff
-        other_makers = _named_makers(seat_map, extra_makers) - {author_family}
+        other_makers = _named_makers(seat_map, extra_makers)
```

**raw red** (exit 1; complete but for the long map repr, cut at `.....`):
```
.......F........................                                         [100%]
=================================== FAILURES ===================================
E   AssertionError: ['anthropic']
    assert 'test-role' not in ['test-role']
     +  where ['test-role'] = _maker_family_seats([{'constraint': 'critical-diversity'}, {'seat': 'test-role', 'constraint': 'maker-family'}])
/home/user/wt-2537/plugins/superheroes/lib/tests/test_seat_map.py:4947: AssertionError: ['anthropic']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_an_author_family_seat_keeps_its_liveness_rule_when_the_map_names_the_author
1 failed, 31 passed in 2.80s
```

**restore:** the inverse edit (` - {author_family}` put back).

**raw green after every restore** (exit 0; complete):
```
................................                                         [100%]
32 passed in 2.71s
```

(end of record)
