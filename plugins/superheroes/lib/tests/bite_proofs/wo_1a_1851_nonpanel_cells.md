# WO-1a (#1851) bite-proof — the non-panel selector reads per-phase cell proof and the host family

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/receipt_disclosures.py`, `plugins/superheroes/lib/round_driver.py`, `plugins/superheroes/lib/round_adapters.py`.

Declared guarded-element set (from the order): G1-G8; G9 is an extra element the implementer added. Each was neutralized by an exact text swap in production code only, the single proving node was run red, the neutralization was undone by the inverse text swap, and the same node was run green. Temp paths are the only redaction (`<tmp>` for the pytest temp root, `<repo>` for the worktree root). All commands ran from `<repo>`; the driver script applied and undid each swap and ran the node, and its output is pasted raw.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| G1 | the phase -> cell role mapping, verifier vs reviewer-deep (`round_driver.py` `_NONPANEL_PHASE_ROLE`) | a gap-sweep / scoped reviewer is judged on the vendor's reviewer-deep cell, never its verifier cell | `test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped` |
| G2 | the cell-membership check under a probed / synthesized source (`receipt_disclosures.py` `nonpanel_cell_proven`) | a vendor is proven for a phase only when THAT phase's dispatched cell is listed, not when any of its cells is | `test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers` |
| G3 | the unproved branch for unknown / partial evidence (`receipt_disclosures.py` `_nonpanel_cell_evidence`) | a map carrying some but not all of the cell-proof evidence proves nothing; it never falls back to the legacy live-vendor rule | `test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers]` |
| G4 | the pool extension by `nonPanelLiveCells` (`receipt_disclosures.py` `nonpanel_candidates`) | a vendor the seat map proves live is a candidate even when it is absent from `config["vendors"]` | `test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers]` |
| G5 | the native host family in `reviewer_ineligible` (`receipt_disclosures.py`) | a native host seat is judged on the host's family, not on `family_for("reviewer", vendor)` | `test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers]` |
| G6 | an unknown host makes the native candidate ineligible (`receipt_disclosures.py` `reviewer_ineligible`) | a host family that is absent, null or not a non-empty string leaves a native seat ineligible, never the registry family | `test_no_seat_map_uses_the_legacy_cell_rule_and_leaves_native_claude_ineligible[dispatch-verifiers]` |
| G7 | `_maker_barred` passes the host family (`round_adapters.py`) | the authentication side judges a native seat with the same host family the selection used | `test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family` |
| G8 | the removed `not makers and not fixer` shortcut (`round_driver.py` `_nonpanel_reviewer_vendor`) | with nothing barred the reviewer engine is still judged on its cell proof and host family, so an unproven engine is not seated | `test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers]` |
| G9 | (extra, not in the declared set) the source gate: an `unprobed` source proves nothing (`receipt_disclosures.py` `_nonpanel_cell_evidence`) | listed cells count only under a `probed` or `synthesized` source | `test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers]` |

## Disclosures

- Restore receipts: the sha256 of the neutralized file is taken before the swap and again after the inverse swap and the two are compared; the restored text is also quoted back.
- Not separately neutralized, so listed as unproven: the `claude`-always-proven rule in `nonpanel_cell_proven`, the preferred-vendor-first ordering in `nonpanel_reviewer`, the required `phase` argument of the three helpers, and `_dispatched_cell`'s unknown-role branch. Each has a green test (`test_cell_proof_rules_read_directly`, `test_the_preferred_vendor_goes_first_when_it_is_a_candidate`, `test_the_non_panel_helpers_require_the_phase`) with no red shown here.
- G1 and G3/G9 neutralize lines other proving tests also read; only the named node is run for each, so any extra node that goes red under the same swap is not claimed.
- Baseline sha256, before G1 (restored byte-for-byte after every element):
```
0e4dfa325f30969faa31bf15559d3a7e89affa88ef533db2ed8aed424806d015  plugins/superheroes/lib/round_driver.py
4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188  plugins/superheroes/lib/receipt_disclosures.py
e30d114e83ea7c608c16cdb5844234082274df5f37500c5b7a5159dbe912c75a  plugins/superheroes/lib/round_adapters.py
```

---

## G1 — the phase -> cell role mapping, verifier vs reviewer-deep (`round_driver.py` `_NONPANEL_PHASE_ROLE`)

- **axis:** a gap-sweep / scoped reviewer is judged on the vendor's reviewer-deep cell, never its verifier cell

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-     P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_FINDER,
-     P_SCOPED: receipt_disclosures.NONPANEL_ROLE_FINDER,
+     P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_VERIFIER,
+     P_SCOPED: receipt_disclosures.NONPANEL_ROLE_VERIFIER,
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped _
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:228: in test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped
    assert _pick(state, phase) == (None, None)
E   AssertionError: assert ('codex', 'configured') == (None, None)
E     
E     At index 0 diff: 'codex' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped
1 failed in 5.33s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
    P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_FINDER,
    P_SCOPED: receipt_disclosures.NONPANEL_ROLE_FINDER,
```
**restore receipt:** sha256 of `plugins/superheroes/lib/round_driver.py` before the swap `0e4dfa325f30969faa31bf15559d3a7e89affa88ef533db2ed8aed424806d015`, after the inverse swap `0e4dfa325f30969faa31bf15559d3a7e89affa88ef533db2ed8aed424806d015` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.91s
```

---

## G2 — the cell-membership check under a probed / synthesized source (`receipt_disclosures.py` `nonpanel_cell_proven`)

- **axis:** a vendor is proven for a phase only when THAT phase's dispatched cell is listed, not when any of its cells is

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-     return cell is not None and cell in cells
+     return any(c[0] == vendor for c in cells)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers __
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:240: in test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers
    assert _pick(state, RD.P_VERIFIERS) == (None, None)
E   AssertionError: assert ('codex', 'configured') == (None, None)
E     
E     At index 0 diff: 'codex' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers
1 failed in 0.28s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
    return cell is not None and cell in cells
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188`, after the inverse swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.13s
```

---

## G3 — the unproved branch for unknown / partial evidence (`receipt_disclosures.py` `_nonpanel_cell_evidence`)

- **axis:** a map carrying some but not all of the cell-proof evidence proves nothing; it never falls back to the legacy live-vendor rule

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-             or not isinstance(raw, list)):
-         return False, frozenset()
+             or not isinstance(raw, list)):
+         return True, frozenset()
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers] -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers]
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers] ____
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:170: in test_missing_or_non_list_cells_prove_nothing
    assert _pick(state, phase) == (None, None), bad
E   AssertionError: absent
E   assert ('codex', 'independent') == (None, None)
E     
E     At index 0 diff: 'codex' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers]
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
            or not isinstance(raw, list)):
        return False, frozenset()
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188`, after the inverse swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.12s
```

---

## G4 — the pool extension by `nonPanelLiveCells` (`receipt_disclosures.py` `nonpanel_candidates`)

- **axis:** a vendor the seat map proves live is a candidate even when it is absent from `config["vendors"]`

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-     if legacy:
-         return out
-     for v in model_registry.VENDORS:
+     if True:
+         return out
+     for v in model_registry.VENDORS:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers] -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers]
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers] _
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:268: in test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate
    assert _pick(state, phase) == ("cursor", RD.VENDOR_SOURCE_INDEPENDENT)
E   AssertionError: assert (None, None) == ('cursor', 'independent')
E     
E     At index 0 diff: None != 'cursor'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers]
1 failed in 0.14s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
    if legacy:
        return out
    for v in model_registry.VENDORS:
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188`, after the inverse swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.18s
```

---

## G5 — the native host family in `reviewer_ineligible` (`receipt_disclosures.py`)

- **axis:** a native host seat is judged on the host's family, not on `family_for("reviewer", vendor)`

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-         if (host_family is not HOST_FAMILY_REGISTRY
+         if (False and host_family is not HOST_FAMILY_REGISTRY
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers] -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers]
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers] _
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:106: in test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family
    assert _pick(openai_host, phase) == (None, None)
E   AssertionError: assert ('claude', 'configured') == (None, None)
E     
E     At index 0 diff: 'claude' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers]
1 failed in 0.14s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
        if (host_family is not HOST_FAMILY_REGISTRY
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188`, after the inverse swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.13s
```

---

## G6 — an unknown host makes the native candidate ineligible (`receipt_disclosures.py` `reviewer_ineligible`)

- **axis:** a host family that is absent, null or not a non-empty string leaves a native seat ineligible, never the registry family

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-             fam = host_family if isinstance(host_family, str) and host_family else None
+             fam = (host_family if isinstance(host_family, str) and host_family
+                    else model_registry.family_for("reviewer", vendor))
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_no_seat_map_uses_the_legacy_cell_rule_and_leaves_native_claude_ineligible[dispatch-verifiers] -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_no_seat_map_uses_the_legacy_cell_rule_and_leaves_native_claude_ineligible[dispatch-verifiers]
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_no_seat_map_uses_the_legacy_cell_rule_and_leaves_native_claude_ineligible[dispatch-verifiers] _
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:71: in test_no_seat_map_uses_the_legacy_cell_rule_and_leaves_native_claude_ineligible
    assert _pick(state, phase) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)
E   AssertionError: assert ('claude', 'configured') == ('codex', 'independent')
E     
E     At index 0 diff: 'claude' != 'codex'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_no_seat_map_uses_the_legacy_cell_rule_and_leaves_native_claude_ineligible[dispatch-verifiers]
1 failed in 0.14s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
            fam = host_family if isinstance(host_family, str) and host_family else None
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188`, after the inverse swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.12s
```

---

## G7 — `_maker_barred` passes the host family (`round_adapters.py`)

- **axis:** the authentication side judges a native seat with the same host family the selection used

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
-         receipt_disclosures.accumulated_maker_families(state), cfg.get("fixerVendor"),
-         host_family=receipt_disclosures.host_family(seat_map_receipts.effective_seat_map(state)))
+         receipt_disclosures.accumulated_maker_families(state), cfg.get("fixerVendor"))
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family ____
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:125: in test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family
    assert bar("claude") is True
E   AssertionError: assert False is True
E    +  where False = <function reviewer_ineligible.<locals>.is_ineligible at 0x7fe7800fc9a0>('claude')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
        receipt_disclosures.accumulated_maker_families(state), cfg.get("fixerVendor"),
        host_family=receipt_disclosures.host_family(seat_map_receipts.effective_seat_map(state)))
```
**restore receipt:** sha256 of `plugins/superheroes/lib/round_adapters.py` before the swap `e30d114e83ea7c608c16cdb5844234082274df5f37500c5b7a5159dbe912c75a`, after the inverse swap `e30d114e83ea7c608c16cdb5844234082274df5f37500c5b7a5159dbe912c75a` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.18s
```

---

## G8 — the removed `not makers and not fixer` shortcut (`round_driver.py` `_nonpanel_reviewer_vendor`)

- **axis:** with nothing barred the reviewer engine is still judged on its cell proof and host family, so an unproven engine is not seated

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-     fixer = cfg.get("fixerVendor")
-     chosen, _family = receipt_disclosures.nonpanel_reviewer(
+     fixer = cfg.get("fixerVendor")
+     if not makers and not fixer:
+         return vendor, source
+     chosen, _family = receipt_disclosures.nonpanel_reviewer(
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers] -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers]
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers] _
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:304: in test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated
    assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_INDEPENDENT)
E   AssertionError: assert ('codex', 'configured') == ('claude', 'independent')
E     
E     At index 0 diff: 'codex' != 'claude'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers]
1 failed in 0.14s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
    fixer = cfg.get("fixerVendor")
    chosen, _family = receipt_disclosures.nonpanel_reviewer(
```
**restore receipt:** sha256 of `plugins/superheroes/lib/round_driver.py` before the swap `0e4dfa325f30969faa31bf15559d3a7e89affa88ef533db2ed8aed424806d015`, after the inverse swap `0e4dfa325f30969faa31bf15559d3a7e89affa88ef533db2ed8aed424806d015` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## G9 — (extra, not in the declared set) the source gate: an `unprobed` source proves nothing (`receipt_disclosures.py` `_nonpanel_cell_evidence`)

- **axis:** listed cells count only under a `probed` or `synthesized` source

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-                        liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
+                        liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
+                        liveness_cache.LIVE_CELLS_SOURCE_UNPROBED)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers] -q -p no:cacheprovider plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers]
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers] _____
<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:151: in test_an_unprobed_source_proves_no_non_claude_cell
    assert _pick(state, phase) == (None, None)
E   AssertionError: assert ('codex', 'independent') == (None, None)
E     
E     At index 0 diff: 'codex' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers]
1 failed in 0.12s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored text quoted back:
```
                       liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188`, after the inverse swap `4e91d6b44abe7d83dcf0fa8a817a1cc4ef6675896fa777d91090a9f67c721188` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.16s
```
