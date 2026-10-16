# WO-C (#1858) bite-proof — the synthesis seat is a non-panel seat; the diff-header delegation is asserted

**Provenance:** claude / sonnet-5.5 (implementer, WO-C), `plugins/superheroes/lib/round_driver.py`, `receipt_disclosures.py`, `round_adapters.py`, `eval/review_loop_runner.py`; tests in `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py` and `test_diff_quoted_paths_1797.py`.

Declared guarded-element set (from the order): **S1-S7** and **F5**. Each was neutralized by an exact text swap in production code only (`/tmp/.../scratchpad/biteproof.py` asserts the old text occurs exactly once, swaps it, runs the single detector node, applies the inverse swap, asserts the file's sha256 equals the one taken before the swap, then runs the node again). No `git checkout`, `git restore`, `git reset` or `git stash` was used.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| S1 | the chokepoint gate: an unseatable synthesis seat sets no step (`round_driver.py` `_fold_verifiers`, reading the `P_SYNTHESIS` cell role through `_nonpanel_unseatable`) | a review whose makers (or fixer, or unknown host) bar the only synthesis cell the registry lists emits no synthesis order and never calls the synthesis seam | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_library_unseatable_synthesis_emits_no_seam_call_and_discloses` |
| S2 | the empty-grouping fold at the chokepoint (`round_driver.py` `_fold_verifiers`, `_fold_synthesis(state, config, {"grouping": None})`) | an unseatable synthesis folds exactly as an empty grouping would, so the round continues without ever offering `dispatch-synthesis` | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues` |
| S3 | the receipt's degraded line (`receipt_disclosures.py` `build_degraded_prose`, the `synthesisUnseatable` line) | a round that folded no grouping because no seat qualified says so on the receipt | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues` |
| S4 | durable authentication of a seated synthesis result (`round_adapters.py` `_assemble`, `P_SYNTHESIS` branch) | a durable synthesis landing counts only when the executed vendor equals the recorded one and passes the eligibility bar | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c5_durable_synthesis_executed_on_another_vendor_is_refused` |
| S5 | the hand-submit refusal (`round_driver.py` `_cmd_submit_prepare`, `phase == P_SYNTHESIS` in the extended condition) | a hand synthesis artifact for a phase the driver judges unseatable is refused `nonpanel-reviewer-unseatable` | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c6_hand_submit_of_an_unseatable_synthesis_is_refused` |
| S6 | the library vendor check (`round_driver.py` `run_loop`, the `P_SYNTHESIS` reported-vendor block) | a library synthesis callback that reports a vendor other than the pre-callback selection parks `cannot-certify` | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c7_library_synthesis_reporting_another_vendor_parks` |
| S7 | the harness counts the synthesis leaf only for a round whose callback ran (`eval/review_loop_runner.py`, `if r in synthesis_rounds`) | the expected synthesis usage leaf follows the callback having run, not the round having been seen | `plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_b5_the_harness_counts_a_synthesis_leaf_only_for_a_round_that_ran_it` |
| F5 | the diff-header delegation (`round_driver.py` `_diff_header_sides`, the `sanitized_view.sides_from_diff_git_line` call) | the driver's header reader is the shared reader: a spy standing in for it is what answers | `plugins/superheroes/lib/tests/test_diff_quoted_paths_1797.py::test_the_header_reader_is_delegated_to_the_shared_reader` |

## Disclosures

- Every one of the 8 elements went red under its neutralization (pytest exit 1) and green after the restore (exit 0); none stayed green, so none is listed unproven on that ground.
- S2 and S3 share one detector node (the c1 CLI test): S2 reddens it on the missing-fold branch (the step reaches `dispatch-synthesis` and the hand submit is refused), S3 reddens it on the receipt assertion. Each is a separate neutralization with its own red.
- S1's guarded element is the chokepoint gate, which reads the `P_SYNTHESIS` cell role; the `_NONPANEL_PHASE_ROLE` row itself, the `NONPANEL_ROLES` entry and `seat_map.NONPANEL_CELL_ROLES` are not separately neutralized, so they are unproven here (the row is pinned by `test_nonpanel_cells_1851.py::test_every_non_panel_phase_maps_to_a_cell_role`; `NONPANEL_CELL_ROLES` adds no probe because the registry lists no codex / cursor synthesis cell, asserted in `test_seat_map_nonpanel_cells_1851.py`).
- S7: the harness's own seat map carries no `hostFamily`, so its synthesis seat is unseatable and the synthesis callback never runs there; the B5 test therefore runs the harness twice, once as it ships (no synthesis leaf) and once with a monkeypatched seat map that adds `hostFamily` (the callback runs, the leaf is counted). The S7 neutralization reddens the first half.
- The detector file lost one unused import (`round_records`) after the bite-proof runs; the file was re-run green afterwards (27 passed, with `test_diff_quoted_paths_1797.py`). The nodes' bodies are unchanged.
- Sandbox: no node in this record failed with `failed to write commit object`; nothing here is sandbox-blocked or unrun.
- Red captures use `--tb=short` to bound them; every capture is well under 32 KiB (the largest is 1.3 KiB), so none is written off-repo.
- Restore receipts: the sha256 of each neutralized file is compared with the value taken before the swap, after the inverse swap; the restored lines are quoted back with their line numbers as they stand in the file.

---

## S1 — the chokepoint gate: an unseatable synthesis seat sets no step (`round_driver.py` `_fold_verifiers`, reading the `P_SYNTHESIS` cell role through `_nonpanel_unseatable`)

- **axis:** a review whose makers (or fixer, or unknown host) bar the only synthesis cell the registry lists emits no synthesis order and never calls the synthesis seam

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    if _nonpanel_unseatable(state, session_dir, P_SYNTHESIS):
-        # No grouping seat
+    if False:
+        # No grouping seat
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_library_unseatable_synthesis_emits_no_seam_call_and_discloses -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_c1_library_unseatable_synthesis_emits_no_seam_call_and_discloses _____
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:146: in test_c1_library_unseatable_synthesis_emits_no_seam_call_and_discloses
    assert calls == []
E   assert [1] == []
E     
E     Left contains one more item: 1
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_library_unseatable_synthesis_emits_no_seam_call_and_discloses
1 failed in 0.42s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/round_driver.py` (the neutralized text replaced by the original text); sha256 before the swap `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c`, after the restore `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c` — identical.

**restored lines** (as they stand, from line 3001):
```
3001:     if _nonpanel_unseatable(state, session_dir, P_SYNTHESIS):
3002:         # No grouping seat
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.41s
```

---

## S2 — the empty-grouping fold at the chokepoint (`round_driver.py` `_fold_verifiers`, `_fold_synthesis(state, config, {"grouping": None})`)

- **axis:** an unseatable synthesis folds exactly as an empty grouping would, so the round continues without ever offering `dispatch-synthesis`

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        _fold_synthesis(state, config, {"grouping": None})
-        return
-    state["step"] = P_SYNTHESIS
+        state["step"] = P_SYNTHESIS
+        return
+    state["step"] = P_SYNTHESIS
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues ___
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:163: in test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues
    seen, state, receipt = _cli_run(tmp_path, makers=["anthropic"])
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:103: in _cli_run
    TRD._drive_cli(session_dir, TRD._cfg(**cfg), respond)
/home/user/sh-1858/plugins/superheroes/lib/tests/test_round_driver.py:473: in _drive_cli
    assert s["ok"], s
E   AssertionError: {'ok': False, 'reason': 'nonpanel-reviewer-unseatable', 'detail': "no reviewer outside the makers' families can be seated for dispatch-synthesis; no order was emitted and a submitted artifact is not a review that ran"}
E   assert False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues
1 failed in 1.21s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/round_driver.py` (the neutralized text replaced by the original text); sha256 before the swap `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c`, after the restore `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c` — identical.

**restored lines** (as they stand, from line 3011):
```
3011:         _fold_synthesis(state, config, {"grouping": None})
3012:         return
3013:     state["step"] = P_SYNTHESIS
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.22s
```

---

## S3 — the receipt's degraded line (`receipt_disclosures.py` `build_degraded_prose`, the `synthesisUnseatable` line)

- **axis:** a round that folded no grouping because no seat qualified says so on the receipt

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-        syn = declared.get("synthesisUnseatable")
+        syn = None
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues ___
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:168: in test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues
    assert any(UNSEATABLE_LINE in line for line in receipt["degraded"]), receipt["degraded"]
E   AssertionError: ['reviewer-fell-open-seatmap-unavailable (round 1): live panel vendor(s) claude, codex but no seat map submitted — fal...bmitted and is readable, but its violation basis is incomplete (no-seats) — "no breach" is unproven rather than clean']
E   assert False
E    +  where False = any(<generator object test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues.<locals>.<genexpr> at 0x7f602587d3c0>)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues
1 failed in 1.31s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/receipt_disclosures.py` (the neutralized text replaced by the original text); sha256 before the swap `3d83352ffcd6341dd2965ee51faf82fbcfdeb282d4d8b623525ff0a44f1a13f8`, after the restore `3d83352ffcd6341dd2965ee51faf82fbcfdeb282d4d8b623525ff0a44f1a13f8` — identical.

**restored lines** (as they stand, from line 687):
```
687:         syn = declared.get("synthesisUnseatable")
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.27s
```

---

## S4 — durable authentication of a seated synthesis result (`round_adapters.py` `_assemble`, `P_SYNTHESIS` branch)

- **axis:** a durable synthesis landing counts only when the executed vendor equals the recorded one and passes the eligibility bar

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
-    elif phase == P_SYNTHESIS:
-        fault = _authenticate_finder(roster, indexed, dispatch_manifest, orders_manifest,
-                                     _maker_barred(state, config), disclosures)
-        if fault is not None:
-            return None, fault
-        artifact = _assemble_synthesis
+    elif phase == P_SYNTHESIS:
+        artifact = _assemble_synthesis
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c5_durable_synthesis_executed_on_another_vendor_is_refused -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_c5_durable_synthesis_executed_on_another_vendor_is_refused ________
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:199: in test_c5_durable_synthesis_executed_on_another_vendor_is_refused
    assert art is None and why.startswith("missing-seat-refuse-fold:%s" % RA.SEAT_SYNTHESIS), (art, why)
E   AssertionError: ({'grouping': None}, None)
E   assert ({'grouping': None} is None)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c5_durable_synthesis_executed_on_another_vendor_is_refused
1 failed in 0.37s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/round_adapters.py` (the neutralized text replaced by the original text); sha256 before the swap `26ea55109381daaa76b91c155e01cca9e97e96197dfaa9a2d919d000f3e8e1de`, after the restore `26ea55109381daaa76b91c155e01cca9e97e96197dfaa9a2d919d000f3e8e1de` — identical.

**restored lines** (as they stand, from line 449):
```
449:     elif phase == P_SYNTHESIS:
450:         fault = _authenticate_finder(roster, indexed, dispatch_manifest, orders_manifest,
451:                                      _maker_barred(state, config), disclosures)
452:         if fault is not None:
453:             return None, fault
454:         artifact = _assemble_synthesis
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.36s
```

---

## S5 — the hand-submit refusal (`round_driver.py` `_cmd_submit_prepare`, `phase == P_SYNTHESIS` in the extended condition)

- **axis:** a hand synthesis artifact for a phase the driver judges unseatable is refused `nonpanel-reviewer-unseatable`

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    if (not _via_advance and (phase in _NONPANEL_REVIEWER_PHASES or phase == P_SYNTHESIS)
+    if (not _via_advance and (phase in _NONPANEL_REVIEWER_PHASES)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c6_hand_submit_of_an_unseatable_synthesis_is_refused -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_c6_hand_submit_of_an_unseatable_synthesis_is_refused ___________
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:217: in test_c6_hand_submit_of_an_unseatable_synthesis_is_refused
    assert out["ok"] is False and out["reason"] == "nonpanel-reviewer-unseatable", out
E   AssertionError: {'ok': True, 'round': 1, 'phase': 'dispatch-synthesis', 'nextStep': 'dispatch-gap-sweep', ...}
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c6_hand_submit_of_an_unseatable_synthesis_is_refused
1 failed in 1.11s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/round_driver.py` (the neutralized text replaced by the original text); sha256 before the swap `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c`, after the restore `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c` — identical.

**restored lines** (as they stand, from line 7206):
```
7206:     if (not _via_advance and (phase in _NONPANEL_REVIEWER_PHASES or phase == P_SYNTHESIS)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.11s
```

---

## S6 — the library vendor check (`round_driver.py` `run_loop`, the `P_SYNTHESIS` reported-vendor block)

- **axis:** a library synthesis callback that reports a vendor other than the pre-callback selection parks `cannot-certify`

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-            if action == P_SYNTHESIS and isinstance(artifact, dict):
-                reported =
+            if False and action == P_SYNTHESIS and isinstance(artifact, dict):
+                reported =
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c7_library_synthesis_reporting_another_vendor_parks -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_c7_library_synthesis_reporting_another_vendor_parks ___________
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:240: in test_c7_library_synthesis_reporting_another_vendor_parks
    assert state["terminal"] == "cannot-certify"
E   AssertionError: assert 'converged' == 'cannot-certify'
E     
E     - cannot-certify
E     + converged
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_c7_library_synthesis_reporting_another_vendor_parks
1 failed in 0.35s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/round_driver.py` (the neutralized text replaced by the original text); sha256 before the swap `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c`, after the restore `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c` — identical.

**restored lines** (as they stand, from line 6130):
```
6130:             if action == P_SYNTHESIS and isinstance(artifact, dict):
6131:                 reported =
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.31s
```

---

## S7 — the harness counts the synthesis leaf only for a round whose callback ran (`eval/review_loop_runner.py`, `if r in synthesis_rounds`)

- **axis:** the expected synthesis usage leaf follows the callback having run, not the round having been seen

**neutralization** (`plugins/superheroes/eval/review_loop_runner.py`):
```diff
-        if r in synthesis_rounds:
+        if True:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_b5_the_harness_counts_a_synthesis_leaf_only_for_a_round_that_ran_it -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_b5_the_harness_counts_a_synthesis_leaf_only_for_a_round_that_ran_it ___
/home/user/sh-1858/plugins/superheroes/lib/tests/test_synthesis_seat_1858.py:275: in test_b5_the_harness_counts_a_synthesis_leaf_only_for_a_round_that_ran_it
    assert not [leaf for leaf in leaves if leaf.startswith("synthesis:")], leaves
E   AssertionError: ['security-reviewer:r1', 'test-reviewer:r1', 'synthesis:r1', 'fix:r1', 'security-reviewer:r2', 'test-reviewer:r2', ...]
E   assert not ['synthesis:r1', 'synthesis:r2', 'synthesis:r3']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_seat_1858.py::test_b5_the_harness_counts_a_synthesis_leaf_only_for_a_round_that_ran_it
1 failed in 0.55s
```

**restore:** the inverse text swap on `plugins/superheroes/eval/review_loop_runner.py` (the neutralized text replaced by the original text); sha256 before the swap `8a5ece34fd3cea98c9528ae8a57063fd9ae3f08fc13c862e2ba80a52bb7faacb`, after the restore `8a5ece34fd3cea98c9528ae8a57063fd9ae3f08fc13c862e2ba80a52bb7faacb` — identical.

**restored lines** (as they stand, from line 689):
```
689:         if r in synthesis_rounds:
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.64s
```

---

## F5 — the diff-header delegation (`round_driver.py` `_diff_header_sides`, the `sanitized_view.sides_from_diff_git_line` call)

- **axis:** the driver's header reader is the shared reader: a spy standing in for it is what answers

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        return sanitized_view.sides_from_diff_git_line(line.encode("utf-8", "surrogateescape"))
+        m = re.match(r"diff --git a/(.*) b/(.*)$", line)
+        return (m.group(1), m.group(2)) if m else None
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_diff_quoted_paths_1797.py::test_the_header_reader_is_delegated_to_the_shared_reader -q -p no:cacheprovider --tb=short
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_the_header_reader_is_delegated_to_the_shared_reader ___________
/home/user/sh-1858/plugins/superheroes/lib/tests/test_diff_quoted_paths_1797.py:92: in test_the_header_reader_is_delegated_to_the_shared_reader
    assert RD._diff_header_sides("diff --git a/x b/y") == ("sentinel-a", "sentinel-b")
E   AssertionError: assert ('x', 'y') == ('sentinel-a', 'sentinel-b')
E     
E     At index 0 diff: 'x' != 'sentinel-a'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_diff_quoted_paths_1797.py::test_the_header_reader_is_delegated_to_the_shared_reader
1 failed in 0.12s
```

**restore:** the inverse text swap on `plugins/superheroes/lib/round_driver.py` (the neutralized text replaced by the original text); sha256 before the swap `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c`, after the restore `fb29510e4e8428fb915d01f729b0cedacd66ffc6cd8b4a6aec7d8bc5f7d7388c` — identical.

**restored lines** (as they stand, from line 1155):
```
1155:         return sanitized_view.sides_from_diff_git_line(line.encode("utf-8", "surrogateescape"))
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
```

