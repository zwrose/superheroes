# WO-2 (#1851) bite-proof — compose probes and records the non-panel cells and the host family

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/seat_map.py`, `plugins/superheroes/lib/preflight_probe.py`, `plugins/superheroes/lib/seat_map_receipts.py`; tests in `plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py`.

Declared guarded-element set (from the order): H1-H7. Each was neutralized by a targeted one-line edit in production code only, the proving node was run red, the neutralization was undone by the inverse edit, and the same node was run green. Temp paths are the only redaction (`<tmp>` for the pytest temp root, `<repo>` for the worktree root); the red output is the full captured output of the single node, with nothing elided. All commands ran from `<repo>`.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| H1 | the panel verdict computed over the panel set only (`preflight_probe.py` `live_vendors_for_composition`, fresh-probe branch) | a dead non-panel cell never removes a vendor from `liveVendors`, a panel cell from `liveCells`, or adds a panel dead-cell note (J1, edge 1) | `test_dead_verifier_cell_leaves_the_panel_verdict_untouched` |
| H2 | the non-panel cells probed on the pinned path (`seat_map.py` `main`, compose branch, `extra_needed=`) | pins scope only the panel's needed set; the non-panel cells are still probed (J1, edge 3) | `test_pinned_compose_still_probes_the_nonpanel_cells` |
| H3 | cache coverage includes the non-panel set (`preflight_probe.py` `live_vendors_for_composition`, `covers`) | a cache receipt whose `needed` lacks the non-panel cells fails `covers` and re-probes (J1, edge 4) | `test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed` |
| H4 | the `synthesized` source on the `--live-vendors` path (`seat_map.py` `main`, `non_panel_report`) | the no-probe path records `nonPanelLiveCellsSource: synthesized`, never `probed` (J2, edge 5) | `test_live_vendors_path_synthesizes_both_cells_per_listed_vendor` |
| H5 | `hostFamily` read from the host model (`seat_map.py` `main`, `sm["hostFamily"]`) | a recognized host model's registry family is recorded, not `null` (J3, edge 7) | `test_host_family_is_the_registry_family_of_the_host_model` |
| H6 | the projection's host-family agreement rule (`seat_map_receipts.py` `emit_receipt_seat_map`) | `hostFamily` survives only when every carrying receipt agrees on one non-empty string, else `null` (J4, edge 8) | `test_projection_host_family_survives_only_on_agreement` |
| H7 | the projection's least-trusted non-panel source (`seat_map_receipts.py` `emit_receipt_seat_map`) | `nonPanelLiveCellsSource` merges to the least trusted receipt's source, not the last (J4, edge 8) | `test_projection_merges_the_nonpanel_source_to_the_least_trusted` |

## Disclosures

- H5's proving node is parametrized over five host models; under the always-`null` neutralization the `gpt-5.6-sol` and `claude-opus-5` parameters went red and the three unknown-host parameters stayed green, which is the expected shape (a `null` expectation cannot tell the neutralization from the real value).
- H1 neutralizes the fresh-probe branch only; the cache-hit branch's `live_from(rec["liveness"], needed)` is the same expression and was not separately neutralized, so it is **unproven** by a red of its own (the cache-hit test asserts the reused panel `liveCells` equal the first compose's).
- Not separately neutralized, so unproven: the `_fill_extra_report` read-error branch (`test_liveness_read_error_on_the_nonpanel_set_is_unprobed` is green, no red shown here), the codex-floor-refusal `unprobed` branch (`test_codex_floor_refusal_records_the_nonpanel_cells_unprobed`, green, no red), the author/narrative-flag path's `null` host family, and the `compose-liveness` CLI's printed `nonPanelLiveCells`.
- Restore receipts: the restored line is quoted back as it stands in the file after the inverse edit (a `grep -n` of it), and the sha256 of the three production files after each restore is compared with the value taken before the first neutralization. The files are untracked-by-commit working changes, so `git diff --stat` would show the whole WO and is not the restore receipt.

Baseline sha256, taken before H1 (the same three lines came back after every restore; the final comparison printed `all three sha256 equal baseline`):
```
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py
92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea  plugins/superheroes/lib/preflight_probe.py
dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960  plugins/superheroes/lib/seat_map_receipts.py
```

---

## H1 — the panel verdict computed over the panel set only (`preflight_probe.py` `live_vendors_for_composition`, fresh-probe branch)

- **axis:** a dead non-panel cell never removes a vendor from `liveVendors`, a panel cell from `liveCells`, or adds a panel dead-cell note (J1, edge 1)

**neutralization** (`plugins/superheroes/lib/preflight_probe.py`):
```diff
--- before (restored text)
    live, live_cells, dead_notes = liveness_cache.live_from(liveness, needed)
+++ neutralized
    live, live_cells, dead_notes = liveness_cache.live_from(liveness, probed_needed)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_dead_verifier_cell_leaves_the_panel_verdict_untouched -q -p no:cacheprovider
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_dead_verifier_cell_leaves_the_panel_verdict_untouched __________

probe_env = namespace(dead={('codex', 'codex-nonpanel-verifier', 'high')}, probed=[('codex', 'gpt-6.1-sol', 'xhigh'), ('codex', 'g...che_path': '<tmp>/pytest-of-root/pytest-8/test_dead_verifier_cell_leaves0/b.json', 'now': 1791924074.1533742}])
capsys = <_pytest.capture.CaptureFixture object at 0x7fd0f7a41a90>
tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-8/test_dead_verifier_cell_leaves0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd0f7816ea0>

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
1 failed in 0.23s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
687:    live, live_cells, dead_notes = liveness_cache.live_from(liveness, needed)
92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea  plugins/superheroes/lib/preflight_probe.py
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.87s
exit 0
```

---

## H2 — the non-panel cells probed on the pinned path (`seat_map.py` `main`, compose branch, `extra_needed=`)

- **axis:** pins scope only the panel's needed set; the non-panel cells are still probed (J1, edge 3)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
                    extra_needed=preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured),
+++ neutralized
                    extra_needed=({} if liveness_pin_scoped else preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured)),
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_pinned_compose_still_probes_the_nonpanel_cells -q -p no:cacheprovider
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_pinned_compose_still_probes_the_nonpanel_cells ______________

probe_env = namespace(dead=set(), probed=[('codex', 'gpt-6.1-sol', 'high'), ('codex', 'gpt-6.1-sol', 'xhigh'), ('cursor', 'cursor-...pytest-of-root/pytest-10/test_pinned_compose_still_prob0/state/composition-liveness.json', 'now': 1791924084.0378094}])
capsys = <_pytest.capture.CaptureFixture object at 0x7fb698505940>

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
1 failed in 0.16s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
1706:                    extra_needed=preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured),
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.18s
exit 0
```

---

## H3 — cache coverage includes the non-panel set (`preflight_probe.py` `live_vendors_for_composition`, `covers`)

- **axis:** a cache receipt whose `needed` lacks the non-panel cells fails `covers` and re-probes (J1, edge 4)

**neutralization** (`plugins/superheroes/lib/preflight_probe.py`):
```diff
--- before (restored text)
        if rec is not None and liveness_cache.covers(rec.get("needed", {}), probed_needed):
+++ neutralized
        if rec is not None and liveness_cache.covers(rec.get("needed", {}), needed):
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed -q -p no:cacheprovider
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed ______

probe_env = namespace(dead=set(), probed=[], floor=None, cache='<tmp>/pytest-of-root/pytest-12/test_cache_written_before_l...pytest-of-root/pytest-12/test_cache_written_before_l4_w0/state/composition-liveness.json', 'now': 1791924091.0906017}])
capsys = <_pytest.capture.CaptureFixture object at 0x7fd355bdd940>

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
E        +  where [] = namespace(dead=set(), probed=[], floor=None, cache='<tmp>/pytest-of-root/pytest-12/test_cache_written_before_l...pytest-of-root/pytest-12/test_cache_written_before_l4_w0/state/composition-liveness.json', 'now': 1791924091.0906017}]).probed

<repo>/plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py:182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed
1 failed in 0.17s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
650:        if rec is not None and liveness_cache.covers(rec.get("needed", {}), probed_needed):
92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea  plugins/superheroes/lib/preflight_probe.py
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.19s
exit 0
```

---

## H4 — the `synthesized` source on the `--live-vendors` path (`seat_map.py` `main`, `non_panel_report`)

- **axis:** the no-probe path records `nonPanelLiveCellsSource: synthesized`, never `probed` (J2, edge 5)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
                "source": liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
+++ neutralized
                "source": liveness_cache.LIVE_CELLS_SOURCE_PROBED,
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_live_vendors_path_synthesizes_both_cells_per_listed_vendor -q -p no:cacheprovider
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_live_vendors_path_synthesizes_both_cells_per_listed_vendor ________

capsys = <_pytest.capture.CaptureFixture object at 0x7f54f16dd940>

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
1 failed in 0.22s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
1689:                "source": liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.19s
exit 0
```

---

## H5 — `hostFamily` read from the host model (`seat_map.py` `main`, `sm["hostFamily"]`)

- **axis:** a recognized host model's registry family is recorded, not `null` (J3, edge 7)

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
        sm["hostFamily"] = receipt_host_family
+++ neutralized
        sm["hostFamily"] = None
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_host_family_is_the_registry_family_of_the_host_model -q -p no:cacheprovider
```

**raw red:**
```
FF...                                                                    [100%]
=================================== FAILURES ===================================
_ test_host_family_is_the_registry_family_of_the_host_model[host_args0-openai] _

capsys = <_pytest.capture.CaptureFixture object at 0x7f1390d95940>
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

capsys = <_pytest.capture.CaptureFixture object at 0x7f1390a95a90>
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
2 failed, 3 passed in 0.32s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
1731:        sm["hostFamily"] = receipt_host_family
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py
```

**raw green:**
```
.....                                                                    [100%]
5 passed in 0.31s
exit 0
```

---

## H6 — the projection's host-family agreement rule (`seat_map_receipts.py` `emit_receipt_seat_map`)

- **axis:** `hostFamily` survives only when every carrying receipt agrees on one non-empty string, else `null` (J4, edge 8)

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`):
```diff
--- before (restored text)
        base["hostFamily"] = host_families[0] if agreed else None
+++ neutralized
        base["hostFamily"] = host_families[-1]
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_projection_host_family_survives_only_on_agreement -q -p no:cacheprovider
```

**raw red:**
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
1 failed in 0.17s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
331:        base["hostFamily"] = host_families[0] if agreed else None
dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960  plugins/superheroes/lib/seat_map_receipts.py
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.13s
exit 0
```

---

## H7 — the projection's least-trusted non-panel source (`seat_map_receipts.py` `emit_receipt_seat_map`)

- **axis:** `nonPanelLiveCellsSource` merges to the least trusted receipt's source, not the last (J4, edge 8)

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`):
```diff
--- before (restored text)
        base["nonPanelLiveCellsSource"] = _merge_live_cells_source(non_panel_sources)
+++ neutralized
        base["nonPanelLiveCellsSource"] = non_panel_sources[-1]
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map_nonpanel_cells_1851.py::test_projection_merges_the_nonpanel_source_to_the_least_trusted -q -p no:cacheprovider
```

**raw red:**
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
1 failed in 0.15s
exit 1
```

**restore:** the inverse edit, swapping the neutralized line back to the text above.

**restore receipt:** the restored line as it stands in the file, and the sha256 of the file(s) after the restore (equal to the baseline above):
```
318:        base["nonPanelLiveCellsSource"] = _merge_live_cells_source(non_panel_sources)
8516a1f59ebe88d80f7cd613d8417dc092ea468ebbe684c1b98874fcf3925039  plugins/superheroes/lib/seat_map.py
92bec647a765fc3f43ea7c532f2880af4ede57f22721342a4b0f3d0d9d28c8ea  plugins/superheroes/lib/preflight_probe.py
dedf0f5e181e90ff6a86f6595c5212bfefc47a6eb837c8cbfcd4fccba6f8e960  plugins/superheroes/lib/seat_map_receipts.py
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.13s
exit 0
```

---
