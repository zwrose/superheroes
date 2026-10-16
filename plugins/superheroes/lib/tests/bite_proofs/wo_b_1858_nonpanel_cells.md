# WO-B (#1858) bite-proof — a seat map without cell proof proves no non-claude cell; the L4 elements re-proven on the WO-B code

**Provenance:** claude / sonnet-5.5 (implementer, WO-B2), `plugins/superheroes/lib/receipt_disclosures.py`, `round_driver.py`, `round_adapters.py`, `seat_map.py`, `preflight_probe.py`, `seat_map_receipts.py`; tests in `plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py`, `test_nonpanel_cell_proof_1858.py`, `test_seat_map_nonpanel_cells_1851.py`. Worktree HEAD `a8e16c2f`, with the one WO-B2 assertion change in `test_nonpanel_cells_1851.py` (`test_cell_proof_rules_read_directly`) in the working tree.

Declared guarded-element set (from the order): **G1-G9** as listed in `wo_1a_1851_nonpanel_cells.md`, **H1-H7** as listed in `wo_2_1851_compose_cells.md`, and **G10** (new, B1). Each was neutralized by an exact text swap in production code only (the script asserted the old text occurred exactly once), the single proving node was run red, the neutralization was undone by the inverse text swap, and the same node was run green. Temp paths are the only redaction: `<tmp>` for the pytest temp root, `<repo>` for the worktree root (`/home/user/sh-1858`). All commands ran from `<repo>`; a driver script applied and undid each swap and ran the node, and the pytest output is pasted raw. The L4 neutralizations were adjusted to the line text as it stands now; where the adjustment is more than whitespace it is stated under the element.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| G1 | the phase -> cell role mapping, verifier vs reviewer-deep (`round_driver.py` `_NONPANEL_PHASE_ROLE`) | a gap-sweep / scoped reviewer is judged on the vendor's reviewer-deep cell, never its verifier cell | `test_nonpanel_cells_1851.py::test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped` |
| G2 | the cell-membership check under a probed / synthesized source (`receipt_disclosures.py` `nonpanel_cell_proven`) | a vendor is proven for a phase only when THAT phase's dispatched cell is listed, not when any of its cells is | `test_nonpanel_cells_1851.py::test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers` |
| G3 | the unproved branch for unknown / partial evidence (`receipt_disclosures.py` `_nonpanel_cell_evidence`) | a map carrying a valid source but no cell list (or an unprobed source) proves nothing; the empty evidence set is never widened to the registry's cells | `test_nonpanel_cells_1851.py::test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers]` |
| G4 | the pool extension by `nonPanelLiveCells` (`receipt_disclosures.py` `nonpanel_candidates`) | a vendor the seat map proves live is a candidate even when it is absent from `config["vendors"]` | `test_nonpanel_cells_1851.py::test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers]` |
| G5 | the native host family in `reviewer_ineligible` (`receipt_disclosures.py`) | a native host seat is judged on the host's family, not on `family_for("reviewer", vendor)` | `test_nonpanel_cells_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers]` |
| G6 | an unknown host makes the native candidate ineligible (`receipt_disclosures.py` `reviewer_ineligible`) | a host family that is absent, null or not a non-empty string leaves a native seat ineligible, never the registry family | `test_nonpanel_cells_1851.py::test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible[dispatch-verifiers]` |
| G7 | `_maker_barred` judges a native seat with the host family (`round_adapters.py`, via `receipt_disclosures.nonpanel_barred`) | the authentication side judges a native seat with the same host family the selection used | `test_nonpanel_cells_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family` |
| G8 | the removed `not makers and not fixer` shortcut (`round_driver.py` `_nonpanel_reviewer_vendor`) | with nothing barred the reviewer engine is still judged on its cell proof and host family, so an unproven engine is not seated | `test_nonpanel_cells_1851.py::test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers]` |
| G9 | the source gate: an `unprobed` source proves nothing (`receipt_disclosures.py` `_nonpanel_cell_evidence`) | listed cells count only under a `probed` or `synthesized` source | `test_nonpanel_cells_1851.py::test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers]` |
| G10 | a map with no usable cell proof proves no non-claude cell (`receipt_disclosures.py` `nonpanel_cell_proven`; new in WO-B) | a key-less seat map (or none) proves no non-claude cell — the retired legacy live-vendor rule stays retired | `test_nonpanel_cell_proof_1858.py::test_a_key_less_seat_map_proves_no_non_claude_cell` |
| H1 | the panel verdict computed over the panel set only (`preflight_probe.py` `live_vendors_for_composition`, fresh-probe branch) | a dead non-panel cell never removes a vendor from `liveVendors`, a panel cell from `liveCells`, or adds a panel dead-cell note (J1, edge 1) | `test_seat_map_nonpanel_cells_1851.py::test_dead_verifier_cell_leaves_the_panel_verdict_untouched` |
| H2 | the non-panel cells probed on the pinned path (`seat_map.py` `main`, compose branch, `extra_needed=`) | pins scope only the panel's needed set; the non-panel cells are still probed (J1, edge 3) | `test_seat_map_nonpanel_cells_1851.py::test_pinned_compose_still_probes_the_nonpanel_cells` |
| H3 | cache coverage includes the non-panel set (`preflight_probe.py` `live_vendors_for_composition`, `covers`) | a cache receipt whose `needed` lacks the non-panel cells fails `covers` and re-probes (J1, edge 4) | `test_seat_map_nonpanel_cells_1851.py::test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed` |
| H4 | the `synthesized` source on the `--live-vendors` path (`seat_map.py` `main`, `non_panel_report`) | the no-probe path records `nonPanelLiveCellsSource: synthesized`, never `probed` (J2, edge 5) | `test_seat_map_nonpanel_cells_1851.py::test_live_vendors_path_synthesizes_both_cells_per_listed_vendor` |
| H5 | `hostFamily` read from the host model (`seat_map.py` `main`, `sm["hostFamily"]`) | a recognized host model's registry family is recorded, not `null` (J3, edge 7) | `test_seat_map_nonpanel_cells_1851.py::test_host_family_is_the_registry_family_of_the_host_model` |
| H6 | the projection's host-family agreement rule (`seat_map_receipts.py` `emit_receipt_seat_map`) | `hostFamily` survives only when every carrying receipt agrees on one non-empty string, else `null` (J4, edge 8) | `test_seat_map_nonpanel_cells_1851.py::test_projection_host_family_survives_only_on_agreement` |
| H7 | the projection's least-trusted non-panel source (`seat_map_receipts.py` `emit_receipt_seat_map`) | `nonPanelLiveCellsSource` merges to the least trusted receipt's source, not the last (J4, edge 8) | `test_seat_map_nonpanel_cells_1851.py::test_projection_merges_the_nonpanel_source_to_the_least_trusted` |

## Disclosures

- Every one of the 17 elements went red under its neutralization (pytest exit 1) and green after the restore (exit 0); no element stayed green, so none is listed unproven on that ground.
- G10's detector ran all three phase params in one invocation per half; each param went red (see the G10 raw red).
- Several nodes are parametrized; the node run is the one the L4 record names (the `dispatch-verifiers` / `probed-dispatch-verifiers` param where it has one), so the other params are not separately claimed.
- Not separately neutralized, so unproven here: the `claude`-always-proven rule in `nonpanel_cell_proven`, the preferred-vendor-first ordering in `nonpanel_reviewer`, the required `phase` argument of the three helpers, `_dispatched_cell`'s unknown-role branch, and the items the L4 records already list as unproven (H1's cache-hit branch, the `_fill_extra_report` read-error branch, the codex-floor-refusal `unprobed` branch, the author/narrative-flag `null` host family, the `compose-liveness` CLI print).
- Sandbox: no node failed with `failed to write commit object`; nothing is sandbox-blocked or unrun.
- Restore receipts: the sha256 of each neutralized file is compared with the baseline taken before G1, after each inverse swap; the restored lines are quoted back with their line numbers as they stand in the file.
- Baseline sha256, before G1 (restored byte-for-byte after every element; the post-run values are in the last section):
```
92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea  plugins/superheroes/lib/preflight_probe.py
5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84  plugins/superheroes/lib/receipt_disclosures.py
bc37b5c7c6f2d8e4f2810ce9b18960261b3932311ba7db7f7fa064d3a158b504  plugins/superheroes/lib/round_adapters.py
30b5cea4d3f780a34e1765dbc717e94411cfacf024d3ef60659cbe4ac76340f8  plugins/superheroes/lib/round_driver.py
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py
dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960  plugins/superheroes/lib/seat_map_receipts.py
```

---

## G1 — the phase -> cell role mapping, verifier vs reviewer-deep (`round_driver.py` `_NONPANEL_PHASE_ROLE`)

- **axis:** a gap-sweep / scoped reviewer is judged on the vendor's reviewer-deep cell, never its verifier cell

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_FINDER,
-    P_SCOPED: receipt_disclosures.NONPANEL_ROLE_FINDER,
+    P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_VERIFIER,
+    P_SCOPED: receipt_disclosures.NONPANEL_ROLE_VERIFIER,
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f1a1f69cb00>

    def test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped(monkeypatch):
        # axis: the phase -> cell role mapping (verifier vs reviewer-deep) — see bite-proof record
        # wo_1a_1851_nonpanel_cells (G1)
        _engine(monkeypatch, "codex")
        state = _state(_map(cells=[VERIFIER_CELL["codex"]]), vendors=["claude", "codex"],
                       fixerVendor="claude")
        assert _pick(state, RD.P_VERIFIERS) == ("codex", RD.VENDOR_SOURCE_CONFIGURED)
        for phase in FINDER_PHASES:
>           assert _pick(state, phase) == (None, None)
E           AssertionError: assert ('codex', 'configured') == (None, None)
E             
E             At index 0 diff: 'codex' != None
E             Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:228: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_verifiers_only_is_not_seated_for_gap_sweep_or_scoped
1 failed in 0.18s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
8062:    P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_FINDER,
8063:    P_SCOPED: receipt_disclosures.NONPANEL_ROLE_FINDER,
```
**restore receipt:** sha256 of `plugins/superheroes/lib/round_driver.py` before the swap `30b5cea4d3f780a34e1765dbc717e94411cfacf024d3ef60659cbe4ac76340f8`, after the inverse swap `30b5cea4d3f780a34e1765dbc717e94411cfacf024d3ef60659cbe4ac76340f8` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## G2 — the cell-membership check under a probed / synthesized source (`receipt_disclosures.py` `nonpanel_cell_proven`)

- **axis:** a vendor is proven for a phase only when THAT phase's dispatched cell is listed, not when any of its cells is

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
+    return any(c[0] == vendor for c in _nonpanel_cell_evidence(seat_map_))
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers __

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f4334c48e90>

    def test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers(monkeypatch):
        # axis: the cell-membership check (a listed cell counts only for its own phase's cell) — see
        # bite-proof record wo_1a_1851_nonpanel_cells (G2)
        _engine(monkeypatch, "codex")
        state = _state(_map(cells=[FINDER_CELL["codex"]]), vendors=["claude", "codex"],
                       fixerVendor="claude")
>       assert _pick(state, RD.P_VERIFIERS) == (None, None)
E       AssertionError: assert ('codex', 'configured') == (None, None)
E         
E         At index 0 diff: 'codex' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:240: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
302:    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.13s
```

---

## G3 — the unproved branch for unknown / partial evidence (`receipt_disclosures.py` `_nonpanel_cell_evidence`)

- **axis:** a map carrying a valid source but no cell list (or an unprobed source) proves nothing; the empty evidence set is never widened to the registry's cells

- **note:** Adjusted: the L4 text returned `True, frozenset()` from a tuple-returning helper; B1 retired the tuple (the helper now returns the evidence set alone), so the neutralization widens the empty set to every registry non-panel cell, i.e. unproved evidence presumed proven.

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-            or not isinstance(raw, list)):
-        return frozenset()
+            or not isinstance(raw, list)):
+        return frozenset(c for r in NONPANEL_ROLES for v in model_registry.VENDORS
+                         for c in (_dispatched_cell(r, v),) if c is not None)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers] ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fac4e198e90>
phase = 'dispatch-verifiers', source = 'probed'

    @pytest.mark.parametrize("phase", NONPANEL)
    @pytest.mark.parametrize("source", ["probed", "synthesized"])
    def test_missing_or_non_list_cells_prove_nothing(monkeypatch, phase, source):
        # axis: unknown / partial evidence is NOT proven (no fallback to the legacy rule) — see bite-proof
        # record wo_1a_1851_nonpanel_cells (G3)
        _engine(monkeypatch, "claude")
        for bad in ("absent", None, "codex", {"codex": 1}, 7):
            sm = {"hostFamily": "anthropic", "nonPanelLiveCellsSource": source}
            if bad != "absent":
                sm["nonPanelLiveCells"] = bad
            state = _state(sm, vendors=["claude", "codex"], fixerVendor="claude")
>           assert _pick(state, phase) == (None, None), bad
E           AssertionError: absent
E           assert ('codex', 'independent') == (None, None)
E             
E             At index 0 diff: 'codex' != None
E             Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_missing_or_non_list_cells_prove_nothing[probed-dispatch-verifiers]
1 failed in 0.15s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
271:            or not isinstance(raw, list)):
272:        return frozenset()
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## G4 — the pool extension by `nonPanelLiveCells` (`receipt_disclosures.py` `nonpanel_candidates`)

- **axis:** a vendor the seat map proves live is a candidate even when it is absent from `config["vendors"]`

- **note:** Adjusted: the pool extension is now a single `if` inside the `for v in model_registry.VENDORS:` loop (the L4 `legacy` early return is gone with B1), so the neutralization disables that `if`.

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-        if v not in out and _dispatched_cell(role, v) in cells:
+        if False and v not in out and _dispatched_cell(role, v) in cells:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f476d6f0e90>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate(monkeypatch, phase):
        # axis: the pool extension (I2) — see bite-proof record wo_1a_1851_nonpanel_cells (G4)
        _engine(monkeypatch, "claude")
        cells = [VERIFIER_CELL["cursor"], FINDER_CELL["cursor"]]
        state = _state(_map(cells=cells), vendors=["claude"], fixerVendor="claude")
>       assert _pick(state, phase) == ("cursor", RD.VENDOR_SOURCE_INDEPENDENT)
E       AssertionError: assert (None, None) == ('cursor', 'independent')
E         
E         At index 0 diff: None != 'cursor'
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:268: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate[dispatch-verifiers]
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
312:        if v not in out and _dispatched_cell(role, v) in cells:
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## G5 — the native host family in `reviewer_ineligible` (`receipt_disclosures.py`)

- **axis:** a native host seat is judged on the host's family, not on `family_for("reviewer", vendor)`

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-        if (host_family is not HOST_FAMILY_REGISTRY
+        if (False and host_family is not HOST_FAMILY_REGISTRY
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fcab5a44e90>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family(monkeypatch, phase):
        # axis: a native seat takes the HOST family, not family_for("reviewer", "claude") — see bite-proof
        # record wo_1a_1851_nonpanel_cells (G5)
        assert model_registry.family_for("reviewer", "claude") == "anthropic"
        _engine(monkeypatch, "claude")
        cells = [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
        openai_host = _state(_map(host="openai", cells=cells, makerFamilies=["openai"]),
                             vendors=["claude", "codex"])
        # claude is barred (host openai == maker openai); codex is openai too -> nobody qualifies
>       assert _pick(openai_host, phase) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family[dispatch-verifiers]
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
232:        if (host_family is not HOST_FAMILY_REGISTRY
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.14s
```

---

## G6 — an unknown host makes the native candidate ineligible (`receipt_disclosures.py` `reviewer_ineligible`)

- **axis:** a host family that is absent, null or not a non-empty string leaves a native seat ineligible, never the registry family

- **note:** Proving node: the renamed `test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible` went red under G6's neutralization, so it is the node used (the host-family file's `test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible` was not run).

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-            fam = host_family if isinstance(host_family, str) and host_family else None
+            fam = (host_family if isinstance(host_family, str) and host_family
+                   else model_registry.family_for("reviewer", vendor))
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible[dispatch-verifiers] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible[dispatch-verifiers] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f70a54d8e90>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible(monkeypatch, phase):
        # axis: no seat map proves no non-claude cell, and an unknown host leaves a native claude seat
        # ineligible — see bite-proof record wo_b_1858_nonpanel_cells (G10)
        _engine(monkeypatch, "claude")
        state = _state(vendors=["claude", "codex"])
        assert RD.effective_seat_map(state) == {}
        # codex is live in the config but nothing proves its cell; claude has no known family
>       assert _pick(state, phase) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:71: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible[dispatch-verifiers]
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
235:            fam = host_family if isinstance(host_family, str) and host_family else None
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.14s
```

---

## G7 — `_maker_barred` judges a native seat with the host family (`round_adapters.py`, via `receipt_disclosures.nonpanel_barred`)

- **axis:** the authentication side judges a native seat with the same host family the selection used

- **note:** Adjusted: `_maker_barred` no longer passes the host family itself; it delegates to `receipt_disclosures.nonpanel_barred`, which does (and which the driver also calls). The neutralization is made in `round_adapters.py` `_maker_barred`, which stops delegating and builds the bar without the host family, so only the authentication side is affected.

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
-    return receipt_disclosures.nonpanel_barred(state, config)
+    return receipt_disclosures.reviewer_ineligible(
+        receipt_disclosures.accumulated_maker_families(state), (config or {}).get("fixerVendor"))
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family ____

    def test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family():
        # axis: round_adapters._maker_barred passes the host family the selection used — see bite-proof
        # record wo_1a_1851_nonpanel_cells (G7)
        cfg = {"vendors": ["claude", "codex"]}
        bar = RA._maker_barred(_state(_map(host="openai", makerFamilies=["openai"]), **cfg), cfg)
>       assert bar("claude") is True
E       AssertionError: assert False is True
E        +  where False = <function reviewer_ineligible.<locals>.is_ineligible at 0x7f67d8908ea0>('claude')

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:125: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family
1 failed in 0.19s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
292:    return receipt_disclosures.nonpanel_barred(state, config)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/round_adapters.py` before the swap `bc37b5c7c6f2d8e4f2810ce9b18960261b3932311ba7db7f7fa064d3a158b504`, after the inverse swap `bc37b5c7c6f2d8e4f2810ce9b18960261b3932311ba7db7f7fa064d3a158b504` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.14s
```

---

## G8 — the removed `not makers and not fixer` shortcut (`round_driver.py` `_nonpanel_reviewer_vendor`)

- **axis:** with nothing barred the reviewer engine is still judged on its cell proof and host family, so an unproven engine is not seated

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    fixer = cfg.get("fixerVendor")
-    chosen, _family = receipt_disclosures.nonpanel_reviewer(
+    fixer = cfg.get("fixerVendor")
+    if not makers and not fixer:
+        return vendor, source
+    chosen, _family = receipt_disclosures.nonpanel_reviewer(
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f3f9c0fcfc0>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated(monkeypatch, phase):
        # axis: the removed `not makers and not fixer` shortcut — see bite-proof record
        # wo_1a_1851_nonpanel_cells (G8)
        _engine(monkeypatch, "codex")
        state = _state(_map(cells=[]), vendors=["claude", "codex"])
        # codex is the engine but its cell is unproven: the next qualifying candidate (the host seat)
>       assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_INDEPENDENT)
E       AssertionError: assert ('codex', 'configured') == ('claude', 'independent')
E         
E         At index 0 diff: 'codex' != 'claude'
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:304: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated[dispatch-verifiers]
1 failed in 0.15s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
8077:    fixer = cfg.get("fixerVendor")
8078:    chosen, _family = receipt_disclosures.nonpanel_reviewer(
```
**restore receipt:** sha256 of `plugins/superheroes/lib/round_driver.py` before the swap `30b5cea4d3f780a34e1765dbc717e94411cfacf024d3ef60659cbe4ac76340f8`, after the inverse swap `30b5cea4d3f780a34e1765dbc717e94411cfacf024d3ef60659cbe4ac76340f8` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.18s
```

---

## G9 — the source gate: an `unprobed` source proves nothing (`receipt_disclosures.py` `_nonpanel_cell_evidence`)

- **axis:** listed cells count only under a `probed` or `synthesized` source

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-                       liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
+                       liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
+                       liveness_cache.LIVE_CELLS_SOURCE_UNPROBED)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers] _____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f99ac004fc0>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_an_unprobed_source_proves_no_non_claude_cell(monkeypatch, phase):
        # axis: the cell-membership check (a listed cell counts only under a probed / synthesized
        # source) — see bite-proof record wo_1a_1851_nonpanel_cells (G2)
        _engine(monkeypatch, "claude")
        cells = [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
        state = _state(_map(cells=cells, source="unprobed"), vendors=["claude", "codex"], fixerVendor="claude")
>       assert _pick(state, phase) == (None, None)
E       AssertionError: assert ('codex', 'independent') == (None, None)
E         
E         At index 0 diff: 'codex' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py:151: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cells_1851.py::test_an_unprobed_source_proves_no_non_claude_cell[dispatch-verifiers]
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
270:                       liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## G10 — a map with no usable cell proof proves no non-claude cell (`receipt_disclosures.py` `nonpanel_cell_proven`; new in WO-B)

- **axis:** a key-less seat map (or none) proves no non-claude cell — the retired legacy live-vendor rule stays retired

- **note:** The detector is given as the bare test id, so one invocation per half ran all three phase params (`dispatch-verifiers`, `dispatch-gap-sweep`, `dispatch-scoped-finder`); the restored lines are the two-line `cell = ...` / `return ...` body.

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
-    cell = _dispatched_cell(role, vendor)
-    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
+    sm_ = seat_map_ if isinstance(seat_map_, dict) else {}
+    if _SEAT_MAP_CELLS_KEY not in sm_ and _SEAT_MAP_CELLS_SOURCE_KEY not in sm_:
+        return vendor in live_vendors(config)
+    cell = _dispatched_cell(role, vendor)
+    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py::test_a_key_less_seat_map_proves_no_non_claude_cell -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
____ test_a_key_less_seat_map_proves_no_non_claude_cell[dispatch-verifiers] ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fdd3d6ad0f0>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_a_key_less_seat_map_proves_no_non_claude_cell(monkeypatch, phase):
        # axis: a seat map with none of the cell-proof keys proves no non-claude cell — see bite-proof
        # record wo_b_1858_nonpanel_cells (G10)
        _engine(monkeypatch)
        keyless = {"hostFamily": "anthropic", "makerFamilies": ["anthropic"]}
        # claude is barred (anthropic maker); codex is live in the config but its cell is unproven
>       assert RD._nonpanel_selection(_state(keyless), None, phase) == (None, None)
E       AssertionError: assert ('codex', 'independent') == (None, None)
E         
E         At index 0 diff: 'codex' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py:61: AssertionError
____ test_a_key_less_seat_map_proves_no_non_claude_cell[dispatch-gap-sweep] ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fdd3d6acb00>
phase = 'dispatch-gap-sweep'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_a_key_less_seat_map_proves_no_non_claude_cell(monkeypatch, phase):
        # axis: a seat map with none of the cell-proof keys proves no non-claude cell — see bite-proof
        # record wo_b_1858_nonpanel_cells (G10)
        _engine(monkeypatch)
        keyless = {"hostFamily": "anthropic", "makerFamilies": ["anthropic"]}
        # claude is barred (anthropic maker); codex is live in the config but its cell is unproven
>       assert RD._nonpanel_selection(_state(keyless), None, phase) == (None, None)
E       AssertionError: assert ('codex', 'independent') == (None, None)
E         
E         At index 0 diff: 'codex' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py:61: AssertionError
__ test_a_key_less_seat_map_proves_no_non_claude_cell[dispatch-scoped-finder] __

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fdd3d4b5010>
phase = 'dispatch-scoped-finder'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_a_key_less_seat_map_proves_no_non_claude_cell(monkeypatch, phase):
        # axis: a seat map with none of the cell-proof keys proves no non-claude cell — see bite-proof
        # record wo_b_1858_nonpanel_cells (G10)
        _engine(monkeypatch)
        keyless = {"hostFamily": "anthropic", "makerFamilies": ["anthropic"]}
        # claude is barred (anthropic maker); codex is live in the config but its cell is unproven
>       assert RD._nonpanel_selection(_state(keyless), None, phase) == (None, None)
E       AssertionError: assert ('codex', 'independent') == (None, None)
E         
E         At index 0 diff: 'codex' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py:61: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py::test_a_key_less_seat_map_proves_no_non_claude_cell[dispatch-verifiers]
FAILED plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py::test_a_key_less_seat_map_proves_no_non_claude_cell[dispatch-gap-sweep]
FAILED plugins/superheroes/lib/tests/test_nonpanel_cell_proof_1858.py::test_a_key_less_seat_map_proves_no_non_claude_cell[dispatch-scoped-finder]
3 failed in 0.12s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
301:    cell = _dispatched_cell(role, vendor)
302:    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84`, after the inverse swap `5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84` (equal).

**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 0.10s
```

---

## H1 — the panel verdict computed over the panel set only (`preflight_probe.py` `live_vendors_for_composition`, fresh-probe branch)

- **axis:** a dead non-panel cell never removes a vendor from `liveVendors`, a panel cell from `liveCells`, or adds a panel dead-cell note (J1, edge 1)

**neutralization** (`plugins/superheroes/lib/preflight_probe.py`):
```diff
-    live, live_cells, dead_notes = liveness_cache.live_from(liveness, needed)
+    live, live_cells, dead_notes = liveness_cache.live_from(liveness, probed_needed)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_dead_verifier_cell_leaves_the_panel_verdict_untouched -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_dead_verifier_cell_leaves_the_panel_verdict_untouched __________

probe_env = namespace(dead={('codex', 'codex-nonpanel-verifier', 'high')}, probed=[('codex', 'gpt-6.1-sol', 'xhigh'), ('codex', 'g...he_path': '<tmp>/pytest-of-root/pytest-43/test_dead_verifier_cell_leaves0/b.json', 'now': 1791942910.1469147}])
capsys = <_pytest.capture.CaptureFixture object at 0x7f3be44417f0>
tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-43/test_dead_verifier_cell_leaves0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f3be3d98e90>

    def test_dead_verifier_cell_leaves_the_panel_verdict_untouched(probe_env, capsys, tmp_path, monkeypatch):
        clean = _compose(capsys)
        assert CODEX_VERIFIER_TRIPLE in clean["nonPanelLiveCells"]
    
        monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(tmp_path / "b.json"))
        probe_env.dead.add(("codex", CODEX_VERIFIER[0], CODEX_VERIFIER[1]))
        degraded = _compose(capsys)
    
>       assert "codex" in degraded["liveVendors"]
E       AssertionError: assert 'codex' in ['claude', 'cursor']

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_dead_verifier_cell_leaves_the_panel_verdict_untouched
1 failed in 0.16s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
687:    live, live_cells, dead_notes = liveness_cache.live_from(liveness, needed)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/preflight_probe.py` before the swap `92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea`, after the inverse swap `92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## H2 — the non-panel cells probed on the pinned path (`seat_map.py` `main`, compose branch, `extra_needed=`)

- **axis:** pins scope only the panel's needed set; the non-panel cells are still probed (J1, edge 3)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
-                    extra_needed=preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured),
+                    extra_needed=({} if liveness_pin_scoped else preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured)),
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_pinned_compose_still_probes_the_nonpanel_cells -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_pinned_compose_still_probes_the_nonpanel_cells ______________

probe_env = namespace(dead=set(), probed=[('codex', 'gpt-6.1-sol', 'high'), ('codex', 'gpt-6.1-sol', 'xhigh'), ('cursor', 'cursor-...pytest-of-root/pytest-45/test_pinned_compose_still_prob0/state/composition-liveness.json', 'now': 1791942911.4096236}])
capsys = <_pytest.capture.CaptureFixture object at 0x7f25598b96a0>

    def test_pinned_compose_still_probes_the_nonpanel_cells(probe_env, capsys):
        receipt = _compose(capsys, ["--pins", '{"security-reviewer":{"vendor":"codex"}}'])
    
        assert receipt["livenessPinScoped"] is True
        kwargs = probe_env.extra_needed_seen[0]
        panel_codex = [list(c) for c in kwargs["needed_override"]["codex"]]
        assert list(CODEX_VERIFIER) not in panel_codex
>       assert list(CODEX_VERIFIER) in [list(c) for c in kwargs["extra_needed"]["codex"]]
                                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'codex'

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:146: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_pinned_compose_still_probes_the_nonpanel_cells
1 failed in 0.14s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
1706:                    extra_needed=preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured),
```
**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map.py` before the swap `8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039`, after the inverse swap `8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## H3 — cache coverage includes the non-panel set (`preflight_probe.py` `live_vendors_for_composition`, `covers`)

- **axis:** a cache receipt whose `needed` lacks the non-panel cells fails `covers` and re-probes (J1, edge 4)

**neutralization** (`plugins/superheroes/lib/preflight_probe.py`):
```diff
-liveness_cache.covers(rec.get("needed", {}), probed_needed):
+liveness_cache.covers(rec.get("needed", {}), needed):
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed ______

probe_env = namespace(dead=set(), probed=[], floor=None, cache='<tmp>/pytest-of-root/pytest-47/test_cache_written_before_l...pytest-of-root/pytest-47/test_cache_written_before_l4_w0/state/composition-liveness.json', 'now': 1791942912.7207274}])
capsys = <_pytest.capture.CaptureFixture object at 0x7fa8c040d6a0>

    def test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed(probe_env, capsys):
        panel_needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex", "cursor"])
        stale_liveness = {
            vendor: {
                "live": True,
                "models": {m: {"ok": True, "detail": ""} for m, _e in cells},
                "cells": [{"model": m, "effort": e, "ok": True, "detail": ""} for m, e in cells],
            }
            for vendor, cells in panel_needed.items()
        }
        stale_liveness["claude"] = {"live": True, "models": {}, "cells": []}
        assert liveness_cache.write(stale_liveness, panel_needed, path=probe_env.cache, now=time.time() - 5)
    
        receipt = _compose(capsys)
    
>       assert ("codex", *CODEX_VERIFIER) in probe_env.probed
E       AssertionError: assert ('codex', 'codex-nonpanel-verifier', 'high') in []
E        +  where [] = namespace(dead=set(), probed=[], floor=None, cache='<tmp>/pytest-of-root/pytest-47/test_cache_written_before_l...pytest-of-root/pytest-47/test_cache_written_before_l4_w0/state/composition-liveness.json', 'now': 1791942912.7207274}]).probed

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed
1 failed in 0.15s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
650:        if rec is not None and liveness_cache.covers(rec.get("needed", {}), probed_needed):
```
**restore receipt:** sha256 of `plugins/superheroes/lib/preflight_probe.py` before the swap `92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea`, after the inverse swap `92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.13s
```

---

## H4 — the `synthesized` source on the `--live-vendors` path (`seat_map.py` `main`, `non_panel_report`)

- **axis:** the no-probe path records `nonPanelLiveCellsSource: synthesized`, never `probed` (J2, edge 5)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
-                "source": liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
+                "source": liveness_cache.LIVE_CELLS_SOURCE_PROBED,
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_live_vendors_path_synthesizes_both_cells_per_listed_vendor -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_live_vendors_path_synthesizes_both_cells_per_listed_vendor ________

capsys = <_pytest.capture.CaptureFixture object at 0x7fdf70e5d6a0>

    def test_live_vendors_path_synthesizes_both_cells_per_listed_vendor(capsys):
        receipt = _compose(
            capsys, base=["x", "compose", "--live-vendors", "claude,codex,cursor",
                          "--implementation-engine", "cursor", "--host-model", "claude-opus-5",
                          "--pr-number", "1851"])
    
>       assert receipt["nonPanelLiveCellsSource"] == "synthesized"
E       AssertionError: assert 'probed' == 'synthesized'
E         
E         - synthesized
E         + probed

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:217: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_live_vendors_path_synthesizes_both_cells_per_listed_vendor
1 failed in 0.13s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
1689:                "source": liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
```
**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map.py` before the swap `8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039`, after the inverse swap `8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.14s
```

---

## H5 — `hostFamily` read from the host model (`seat_map.py` `main`, `sm["hostFamily"]`)

- **axis:** a recognized host model's registry family is recorded, not `null` (J3, edge 7)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
-        sm["hostFamily"] = receipt_host_family
+        sm["hostFamily"] = None
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_host_family_is_the_registry_family_of_the_host_model -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FF...                                                                    [100%]
=================================== FAILURES ===================================
_ test_host_family_is_the_registry_family_of_the_host_model[host_args0-openai] _

capsys = <_pytest.capture.CaptureFixture object at 0x7f875e0d16a0>
host_args = ['--host-model', 'gpt-5.6-sol'], expected = 'openai'

    @pytest.mark.parametrize(
        "host_args, expected",
        [
            (["--host-model", "gpt-5.6-sol"], "openai"),
            (["--host-model", "claude-opus-5"], "anthropic"),
            (["--host-model", ""], None),
            (["--host-model", "no-such-model-1851"], None),
            ([], None),
        ],
    )
    def test_host_family_is_the_registry_family_of_the_host_model(capsys, host_args, expected):
        receipt = _host_family_receipt(capsys, host_args)
    
        assert "hostFamily" in receipt
>       assert receipt["hostFamily"] == expected
E       AssertionError: assert None == 'openai'

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:297: AssertionError
_ test_host_family_is_the_registry_family_of_the_host_model[host_args1-anthropic] _

capsys = <_pytest.capture.CaptureFixture object at 0x7f875da39310>
host_args = ['--host-model', 'claude-opus-5'], expected = 'anthropic'

    @pytest.mark.parametrize(
        "host_args, expected",
        [
            (["--host-model", "gpt-5.6-sol"], "openai"),
            (["--host-model", "claude-opus-5"], "anthropic"),
            (["--host-model", ""], None),
            (["--host-model", "no-such-model-1851"], None),
            ([], None),
        ],
    )
    def test_host_family_is_the_registry_family_of_the_host_model(capsys, host_args, expected):
        receipt = _host_family_receipt(capsys, host_args)
    
        assert "hostFamily" in receipt
>       assert receipt["hostFamily"] == expected
E       AssertionError: assert None == 'anthropic'

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:297: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_host_family_is_the_registry_family_of_the_host_model[host_args0-openai]
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_host_family_is_the_registry_family_of_the_host_model[host_args1-anthropic]
2 failed, 3 passed in 0.24s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
1731:        sm["hostFamily"] = receipt_host_family
```
**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map.py` before the swap `8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039`, after the inverse swap `8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039` (equal).

**raw green** (exit 0):
```
.....                                                                    [100%]
5 passed in 0.23s
```

---

## H6 — the projection's host-family agreement rule (`seat_map_receipts.py` `emit_receipt_seat_map`)

- **axis:** `hostFamily` survives only when every carrying receipt agrees on one non-empty string, else `null` (J4, edge 8)

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`):
```diff
-        base["hostFamily"] = host_families[0] if agreed else None
+        base["hostFamily"] = host_families[-1]
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_projection_host_family_survives_only_on_agreement -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_projection_host_family_survives_only_on_agreement ____________

    def test_projection_host_family_survives_only_on_agreement():
        anthropic = _seat_map(hostFamily="anthropic")
        openai = _seat_map(hostFamily="openai")
        unknown = _seat_map(hostFamily=None)
    
        assert SMR.emit_receipt_seat_map(_state(anthropic, anthropic))["hostFamily"] == "anthropic"
>       assert SMR.emit_receipt_seat_map(_state(anthropic, openai))["hostFamily"] is None
E       AssertionError: assert 'openai' is None

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:360: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_projection_host_family_survives_only_on_agreement
1 failed in 0.14s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
331:        base["hostFamily"] = host_families[0] if agreed else None
```
**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map_receipts.py` before the swap `dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960`, after the inverse swap `dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## H7 — the projection's least-trusted non-panel source (`seat_map_receipts.py` `emit_receipt_seat_map`)

- **axis:** `nonPanelLiveCellsSource` merges to the least trusted receipt's source, not the last (J4, edge 8)

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`):
```diff
-        base["nonPanelLiveCellsSource"] = _merge_live_cells_source(non_panel_sources)
+        base["nonPanelLiveCellsSource"] = non_panel_sources[-1]
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_projection_merges_the_nonpanel_source_to_the_least_trusted -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_projection_merges_the_nonpanel_source_to_the_least_trusted ________

    def test_projection_merges_the_nonpanel_source_to_the_least_trusted():
        probed = _seat_map(nonPanelLiveCellsSource="probed", nonPanelLiveCells=[CODEX_VERIFIER_TRIPLE])
        unprobed = _seat_map(nonPanelLiveCellsSource="unprobed", nonPanelLiveCells=[])
    
        assert SMR.emit_receipt_seat_map(_state(probed, unprobed))["nonPanelLiveCellsSource"] == "unprobed"
>       assert SMR.emit_receipt_seat_map(_state(unprobed, probed))["nonPanelLiveCellsSource"] == "unprobed"
E       AssertionError: assert 'probed' == 'unprobed'
E         
E         - unprobed
E         ? --
E         + probed

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:340: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_projection_merges_the_nonpanel_source_to_the_least_trusted
1 failed in 0.13s
```

**restore:** the inverse text swap (the `+` lines back to the `-` lines above). Restored lines quoted back, as they stand in the file:
```
318:        base["nonPanelLiveCellsSource"] = _merge_live_cells_source(non_panel_sources)
```
**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map_receipts.py` before the swap `dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960`, after the inverse swap `dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960` (equal).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## Final sha256 of every neutralized file (after the last restore)

```
92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea  plugins/superheroes/lib/preflight_probe.py  (equal to baseline)
5f348031315505481c5c25deb5d14891bc969108ffb19fc427c83841db20ca84  plugins/superheroes/lib/receipt_disclosures.py  (equal to baseline)
bc37b5c7c6f2d8e4f2810ce9b18960261b3932311ba7db7f7fa064d3a158b504  plugins/superheroes/lib/round_adapters.py  (equal to baseline)
30b5cea4d3f780a34e1765dbc717e94411cfacf024d3ef60659cbe4ac76340f8  plugins/superheroes/lib/round_driver.py  (equal to baseline)
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py  (equal to baseline)
dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960  plugins/superheroes/lib/seat_map_receipts.py  (equal to baseline)
```
