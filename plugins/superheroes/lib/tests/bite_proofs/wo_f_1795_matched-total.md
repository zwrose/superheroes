# WO-F-1795 bite-proof — the record keeps the true matched total

Per-element bite-proof for the `matchedTotal` fix in `plugins/superheroes/lib/review_record.py` (`_bound_basis` sets it, `_shed_to_floor` reads it). The detector is `test_a_floor_only_basis_counts_the_matched_paths_of_the_areas_the_area_cap_cut` in `plugins/superheroes/lib/tests/test_review_record.py`, unedited throughout.

**Provenance:** produced by the dispatched implementer (claude). Not yet re-run by the orchestrator.

**Guarded-element set (declared by the order):** M1 only.

## M1 — `_shed_to_floor` uses `matchedTotal` for `matchedCount`

- **Guarded element and axis:** `review_record.py` `_shed_to_floor`, the `matchedCount` it writes. The axis is the floor-only basis's `matchedCount` counting every matched path in every touched area, including areas the area cap (`BASIS_AREAS_MAX`) cut.
- **Fixture:** 60 disjoint areas, each matching 2 short paths (120 in all), with 290-glyph four-byte area names that force `floor-only`. The area cap leaves 20 areas, so the plain sum over the kept areas reads 40.
- **Neutralization:** in `_shed_to_floor`, the two lines

  ```
  matchedCount=basis["matchedTotal"] if "matchedTotal" in basis
  else sum(t.get("matchedCount", len(t["matched"])) for t in basis["touched"]),
  ```

  became the plain sum, as before the fix:

  ```
  matchedCount=sum(t.get("matchedCount", len(t["matched"])) for t in basis["touched"]),
  ```

- **Raw red** (single node, detector unedited):

  ```
  $ scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_review_record.py::test_a_floor_only_basis_counts_the_matched_paths_of_the_areas_the_area_cap_cut" -q
  F                                                                        [100%]
  >       assert shed["basisShed"] == "floor-only" and shed["touchedCount"] == 60 and shed["matchedCount"] == 120
  E       AssertionError: assert ('floor-only' == 'floor-only'
  E           floor-only and 60 == 60 and 40 == 120)
  FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_floor_only_basis_counts_the_matched_paths_of_the_areas_the_area_cap_cut
  1 failed in 4.46s
  ```

  The red is on the guarded axis: `basisShed` and `touchedCount` still hold; `matchedCount` is 40 where 120 is true.
- **Restore:** the inverse edit, putting the two `matchedTotal` lines back.
- **Restore receipt:** `_shed_to_floor` reads, after the restore, `matchedCount=basis["matchedTotal"] if "matchedTotal" in basis` then `else sum(t.get("matchedCount", len(t["matched"])) for t in basis["touched"]),`, and `git diff` of the file shows only the two intended hunks.
- **Raw green** (same node, after the restore):

  ```
  .                                                                        [100%]
  1 passed in 3.06s
  ```

## Fail-closed edge F1

A basis of 20 areas or fewer carries no `matchedTotal` (it is set only inside the `> BASIS_AREAS_MAX` branch), so `_shed_to_floor` takes the existing sum and the record renders as before. The existing tests over such bases (`test_a_shed_that_reaches_the_last_resort_still_fits` expects `matchedCount == 40` over 20 areas) stay green in the combined run.
