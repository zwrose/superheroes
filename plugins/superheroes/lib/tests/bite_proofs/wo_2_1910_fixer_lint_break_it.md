# WO-2 (#1910) bite-proof — a fixer order may name the not-yet-existing test file of a driver-run break-it finding

**Provenance:** claude / sonnet-5.5 (implementer, WO-2), `plugins/superheroes/lib/order_lint.py`, `plugins/superheroes/lib/round_driver.py`; tests in `plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py`.

Declared guarded-element set (from the order): **B1-B4**. Each was neutralized by one targeted edit in production code only, the single detector node was run, the inverse edit was applied, and the node was run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| B1 | the driver's create-items wiring (`round_driver.py` `_fixer_create_items` and its use at the `P_FIXER` lint call in `_emit_orders_manifest`) | a driver-stamped break-it path to be created does not refuse the fixer order | `test_fixer_lint_break_it_1910.py::test_t1_a_driver_stamped_break_it_test_still_to_be_created_reaches_the_fixer` |
| B2 | the stamp guard in `_fixer_create_items` (stamp is a dict whose `path` is a non-empty string equal to `file`) | only a driver-stamped break-it row is exempted | `test_fixer_lint_break_it_1910.py::test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses` |
| B3 | the containment check on create items (`order_lint.py` `_region`, the `norm in create` branch calling `_contained`) | an exempted path still cannot escape the roots | `test_fixer_lint_break_it_1910.py::test_t4_a_stamped_path_through_a_symlink_out_of_the_repo_still_refuses` |
| B4 | the refusal of a missing non-break-it path (`order_lint.py` `_resolve`, its final return, reached through the driver) | an unresolved edit target still refuses | `test_fixer_lint_break_it_1910.py::test_t2_an_unresolved_edit_target_still_refuses` |

## Disclosures

- All 4 elements went red under their neutralization (pytest exit 1) and green after the restore (exit 0); none is listed unproven.
- B2's node is parametrized over three rows (no stamp, a stamp for another path, a stamp whose path is `None`); all three went red under the neutralization.
- The order says a create path must resolve "inside some root"; `_resolve(..., must_exist=False)` instead refuses a create path when **any** root's join escapes. Under "some root", the plugin root (an alt root the driver always passes) would vouch for `tests_link/test_new.py`, since that join does not exist there and so does not escape it, and the symlinked-ancestor case (E2) would not refuse. This is a deliberate reading of the order's intent, flagged for the orchestrator.
- The unit node `test_t5_create_items_exempt_the_existence_check_only` also pins the containment refusal at `check_text` level; it is not one of the proving nodes above and was not neutralized separately.
- Red captures use `--tb=short`; each is well under 32 KiB, so none is written off-repo. Raw captures are redacted of nothing (no secrets appear).
- Restore receipts: the restored lines are quoted back with the line numbers they stand at; the neutralized text appears nowhere in the final file.

---

## B1 — the driver's create-items wiring

- **axis:** a driver-stamped break-it path to be created does not refuse the fixer order

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-                create_items=_fixer_create_items(pending.get("batch") or []))
+                create_items=())
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo2 -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t1_a_driver_stamped_break_it_test_still_to_be_created_reaches_the_fixer"
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_driver_stamped_break_it_test_still_to_be_created_reaches_the_fixer _
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:65: in test_t1_a_driver_stamped_break_it_test_still_to_be_created_reaches_the_fixer
    anchor = _emit(session_dir, state, row)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:58: in _emit
    return _emit_fixer(session_dir, state, pending_payload={"batch": [row]})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_round_driver_order_lint.py:105: in _emit_fixer
    return RD._emit_orders_manifest(
/home/user/wt-1910-wo2/plugins/superheroes/lib/round_driver.py:10852: in _emit_orders_manifest
    raise ValueError("order-render-refused:%s:order-lint:%s" % (
E   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-path-unresolved:tests/test_new_1910.py
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t1_a_driver_stamped_break_it_test_still_to_be_created_reaches_the_fixer
1 failed in 1.45s
```

**red token:** `E   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-path-unresolved:tests/test_new_1910.py`

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`create_items=()` replaced by the original call).

**restored lines** (as they stand):
```
10847:                create_items=_fixer_create_items(pending.get("batch") or []))
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.32s
```

---

## B2 — the stamp guard in `_fixer_create_items`

- **axis:** only a driver-stamped break-it row is exempted

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        if (isinstance(stamp, dict) and isinstance(stamp.get("path"), str) and stamp["path"]
-                and stamp["path"] == row.get("file")):
-            out.append(row["file"])
+        if True:
+            out.append(row["file"])
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo2 -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses"
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses[none] _
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:83: in test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses
    with pytest.raises(ValueError) as exc:
         ^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE ValueError
_ test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses[other-path] _
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:83: in test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses
    with pytest.raises(ValueError) as exc:
         ^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE ValueError
_ test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses[none-path] _
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:83: in test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses
    with pytest.raises(ValueError) as exc:
         ^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses[none]
FAILED plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses[other-path]
FAILED plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t3_a_break_it_row_without_the_drivers_stamp_for_its_file_still_refuses[none-path]
3 failed in 3.19s
```

**red token:** `E   Failed: DID NOT RAISE ValueError`

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if True:` and its body replaced by the original guard).

**restored lines** (as they stand):
```
146:        if (isinstance(stamp, dict) and isinstance(stamp.get("path"), str) and stamp["path"]
147:                and stamp["path"] == row.get("file")):
148:            out.append(row["file"])
```

**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 3.32s
```

---

## B3 — the containment check on create items

- **axis:** an exempted path still cannot escape the roots

**neutralization** (`plugins/superheroes/lib/order_lint.py`):
```diff
-            ok, why = _contained(tok, roots)
+            ok, why = True, ""
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo2 -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t4_a_stamped_path_through_a_symlink_out_of_the_repo_still_refuses"
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t4_a_stamped_path_through_a_symlink_out_of_the_repo_still_refuses ____
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:95: in test_t4_a_stamped_path_through_a_symlink_out_of_the_repo_still_refuses
    with pytest.raises(ValueError) as exc:
         ^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t4_a_stamped_path_through_a_symlink_out_of_the_repo_still_refuses
1 failed in 1.29s
```

**red token:** `E   Failed: DID NOT RAISE ValueError`

**restore:** the inverse edit on `plugins/superheroes/lib/order_lint.py` (`ok, why = True, ""` replaced by the original call).

**restored lines** (as they stand):
```
283:        if norm in create:
284:            # axis: a path declared as still to be created skips the existence check only; it must still resolve inside a root — see bite-proof record wo_2_1910_fixer_lint_break_it
285:            ok, why = _contained(tok, roots)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.21s
```

---

## B4 — the refusal of a missing non-break-it path (`_resolve`'s final return)

- **axis:** an unresolved edit target still refuses

**neutralization** (`plugins/superheroes/lib/order_lint.py`):
```diff
-    return False, ("escapes-root" if escaped else "")
+    return True, ""
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo2 -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t2_an_unresolved_edit_target_still_refuses"
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_t2_an_unresolved_edit_target_still_refuses ________________
/home/user/wt-1910-wo2/plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py:72: in test_t2_an_unresolved_edit_target_still_refuses
    with pytest.raises(ValueError) as exc:
         ^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fixer_lint_break_it_1910.py::test_t2_an_unresolved_edit_target_still_refuses
1 failed in 1.28s
```

**red token:** `E   Failed: DID NOT RAISE ValueError`

**restore:** the inverse edit on `plugins/superheroes/lib/order_lint.py` (`return True, ""` replaced by the original return).

**restored lines** (as they stand):
```
206:    if not must_exist:
207:        # Containment only: one root that the path escapes refuses it, since a file still to be
208:        # created is not found under any root and so no other root can vouch for it.
209:        return (not escaped, "escapes-root" if escaped else "")
210:    return False, ("escapes-root" if escaped else "")
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.22s
```
