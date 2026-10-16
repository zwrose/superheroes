# C7 L3 WO-4 bite-proof — the loop's tooling folds

**Provenance:** claude / sonnet-5.5 (implementer, WO-4). Detectors: `plugins/superheroes/lib/engine_dispatch.py` (`_continuation_prompt_mismatch` and its two call sites), `.github/scripts/verify_touched_tests.py` (`_find_helper_hop_tests`), `plugins/superheroes/lib/seat_map.py` (`_normalize_live_cell`); tests in `plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py` and `.github/scripts/tests/test_verify_touched_tests.py`.

Declared guarded-element set (from the order): exactly four — **P-review**, **P-write**, **H1**, **E1**. Each was neutralized by one targeted edit to production code and restored by the inverse edit; none by `git checkout` / `git restore` / `git reset` / `git stash`.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| P-review | the prompt-hash comparison in `dispatch-review`'s continuation | a reused run dir whose caller's prompt hashes differently from the journaled hash is refused, never replayed or launched | `test_tooling_folds_c7l3.py::test_p2_review_continuation_with_a_different_prompt_refuses_and_never_launches` |
| P-write | the same comparison in `dispatch-write`'s continuation | as above, for the write path | `test_tooling_folds_c7l3.py::test_p3_write_continuation_with_a_different_prompt_refuses_and_never_launches` |
| H1 | the one-hop selection in the touched-test gate (`_find_helper_hop_tests`) | a test that imports only a helper in its own package tree, where the helper references the changed module, is selected | `test_verify_touched_tests.py::test_driver_change_selects_the_eval_test_that_imports_only_the_harness` |
| E1 | the effort check in `_normalize_live_cell` | a live cell whose effort is neither `None` nor a string is skipped (`None`), so no caller receives an unhashable triple | the ten `test_m1*` nodes of `test_tooling_folds_c7l3.py` (chokepoint, `nonpanel_cell_proven`, `nonpanel_candidates`, `build`, `same_family_degradations`, each for a list and a dict effort) |

## Disclosures

- Every one of the four elements went red under its neutralization (pytest exit 1) and green after the restore; none is listed unproven.
- The repository's signing setup is unavailable in this sandbox (`git commit` exits 128: `failed to write commit object`), so the implementation could not be committed before the neutralizations. Instead the three files were copied aside and each restore was compared byte-for-byte (`cmp`) with the copy; the result is quoted below as the restore receipt. The staged index also still held the implementation throughout.
- The P-write node and the fixture repos its worktree needs commit with their own identity; the test file's autouse fixture sets `GIT_CONFIG_GLOBAL` to the null device so a machine-wide signing config cannot apply.
- The H1 red run named the node with a redundant path prefix (`plugins/../.github/scripts/tests/test_verify_touched_tests.py::...`), which resolves to the same file as the green run's `.github/scripts/tests/test_verify_touched_tests.py::...`.
- Red captures are the full pytest output (default traceback style) and each is under 32 KiB (largest: E1, about 25 KiB), so none is written off-repo.
- The order's other checks are not guarded elements of this record: the touched-test gate's two negative cases (a helper outside the test's package tree; two hops) and the added same-directory exclusion, the malformed-effort `None` result for a well-formed effort, and the codex registry row are covered by tests that were green but not neutralized here.

---

## P-review — the prompt-hash comparison in `dispatch-review`'s continuation

- **axis:** a reused run dir opened with one prompt is refused `run-dir-prompt-mismatch` when the caller's prompt hashes differently, before anything launches

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):
```diff
-                prompt_detail = _continuation_prompt_mismatch(opened, base_prompt)
+                prompt_detail = None  # NEUTRALIZED: _continuation_prompt_mismatch(opened, base_prompt)
```

**red** — `python -B -m pytest plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_p2_review_continuation_with_a_different_prompt_refuses_and_never_launches -q -p no:cacheprovider` (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p2_review_continuation_with_a_different_prompt_refuses_and_never_launches _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_p2_review_continuation_wi0')

    def test_p2_review_continuation_with_a_different_prompt_refuses_and_never_launches(tmp_path):
        # axis: dispatch-review continuation under a different prompt — see bite-proof record c7l3_wo4_tooling
        run_dir = str(tmp_path / "other-prompt")
        _review(tmp_path, run_dir, PROMPT_A)
        runner = TED.FakeRunner([])
        res = _review(tmp_path, run_dir, PROMPT_B, runner=runner)
>       assert res["detail"] == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH == "run-dir-prompt-mismatch"
               ^^^^^^^^^^^^^
E       KeyError: 'detail'

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:92: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_p2_review_continuation_with_a_different_prompt_refuses_and_never_launches
1 failed in 0.43s
```

**restore** — the inverse edit; the whole file was then compared with the pre-neutralization copy (`cmp`: identical).

**restore receipt** — the restored lines, quoted back:
```
6021:                prompt_detail = _continuation_prompt_mismatch(opened, base_prompt)
```

**green** — `same command` (exit 0):
```
.                                                                        [100%]
1 passed in 3.61s
```

---

## P-write — the prompt-hash comparison in `dispatch-write`'s continuation

- **axis:** as P-review, for `dispatch-write`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):
```diff
-            prompt_detail = _continuation_prompt_mismatch(opened, caller_prompt)
+            prompt_detail = None  # NEUTRALIZED: _continuation_prompt_mismatch(opened, caller_prompt)
```

**red** — `python -B -m pytest plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_p3_write_continuation_with_a_different_prompt_refuses_and_never_launches -q -p no:cacheprovider` (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p3_write_continuation_with_a_different_prompt_refuses_and_never_launches _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-29/test_p3_write_continuation_wit0')

    def test_p3_write_continuation_with_a_different_prompt_refuses_and_never_launches(tmp_path):
        # axis: dispatch-write continuation under a different prompt — see bite-proof record c7l3_wo4_tooling
        wt, _main = TEDW._linked_worktree(tmp_path)
        run_dir = str(tmp_path / "write-other-prompt")
        _write(tmp_path, wt, run_dir, "Build this.\n")
        runner = TEDW.FakeRunner([])
        res = _write(tmp_path, wt, run_dir, "Build something else.\n", runner=runner)
>       assert res["detail"] == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH
               ^^^^^^^^^^^^^
E       KeyError: 'detail'

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:105: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_p3_write_continuation_with_a_different_prompt_refuses_and_never_launches
1 failed in 1.77s
```

**restore** — the inverse edit; the whole file was then compared with the pre-neutralization copy (`cmp`: identical).

**restore receipt** — the restored lines, quoted back:
```
6691:            prompt_detail = _continuation_prompt_mismatch(opened, caller_prompt)
```

**green** — `same command` (exit 0):
```
.                                                                        [100%]
1 passed in 0.41s
```

---

## H1 — the one-hop selection in the touched-test gate

- **axis:** a test reaching a changed module through one helper in its own package tree is selected

**neutralization** (`.github/scripts/verify_touched_tests.py`):
```diff
-        if not any(pattern.search(helper_text) for pattern in patterns):
+        if True:  # NEUTRALIZED: not any(pattern.search(helper_text) for pattern in patterns)
             continue
```

**red** — `python -B -m pytest plugins/../.github/scripts/tests/test_verify_touched_tests.py::test_driver_change_selects_the_eval_test_that_imports_only_the_harness -q -p no:cacheprovider` (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_driver_change_selects_the_eval_test_that_imports_only_the_harness ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-31/test_driver_change_selects_the0')

    def test_driver_change_selects_the_eval_test_that_imports_only_the_harness(tmp_path):
        root = str(tmp_path)
        driver, test = _eval_fixture(root)
        selected, *_ = _select(root, [driver])
>       assert test in selected
E       AssertionError: assert 'plugins/superheroes/eval/tests/test_harness.py' in []

.github/scripts/tests/test_verify_touched_tests.py:754: AssertionError
=========================== short test summary info ============================
FAILED .github/scripts/tests/test_verify_touched_tests.py::test_driver_change_selects_the_eval_test_that_imports_only_the_harness
1 failed in 0.13s
```

**restore** — the inverse edit; the whole file was then compared with the pre-neutralization copy (`cmp`: identical).

**restore receipt** — the restored lines, quoted back:
```
250:        if not any(pattern.search(helper_text) for pattern in patterns):
251-            continue
```

**green** — `python -B -m pytest .github/scripts/tests/test_verify_touched_tests.py::test_driver_change_selects_the_eval_test_that_imports_only_the_harness -q -p no:cacheprovider` (exit 0):
```
.                                                                        [100%]
1 passed in 0.08s
```

---

## E1 — the effort check in `_normalize_live_cell`

- **axis:** a live cell whose effort is not `None` or a string is skipped at the one chokepoint; a raised `TypeError` (unhashable type) is the red

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
         if effort is not None and not isinstance(effort, str):
-            return None
+            pass  # NEUTRALIZED: return None
```

**red** — `python -B -m pytest plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py -k m1 -q -p no:cacheprovider` (exit 1):
```
FFFFFFFFFF                                                               [100%]
=================================== FAILURES ===================================
______ test_m1_the_chokepoint_returns_none_for_a_non_string_effort[list] _______

effort = ['high']

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_the_chokepoint_returns_none_for_a_non_string_effort(effort):
        # axis: a malformed effort never reaches a set as an unhashable triple — see bite-proof record c7l3_wo4_tooling
>       assert SM._normalize_live_cell(["codex", "gpt-6.1-sol", effort]) is None
E       AssertionError: assert ('codex', 'gpt-6.1-sol', ['high']) is None
E        +  where ('codex', 'gpt-6.1-sol', ['high']) = <function _normalize_live_cell at 0x7f81336c5a80>(['codex', 'gpt-6.1-sol', ['high']])
E        +    where <function _normalize_live_cell at 0x7f81336c5a80> = SM._normalize_live_cell

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:145: AssertionError
______ test_m1_the_chokepoint_returns_none_for_a_non_string_effort[dict] _______

effort = {'e': 1}

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_the_chokepoint_returns_none_for_a_non_string_effort(effort):
        # axis: a malformed effort never reaches a set as an unhashable triple — see bite-proof record c7l3_wo4_tooling
>       assert SM._normalize_live_cell(["codex", "gpt-6.1-sol", effort]) is None
E       AssertionError: assert ('codex', 'gpt-6.1-sol', {'e': 1}) is None
E        +  where ('codex', 'gpt-6.1-sol', {'e': 1}) = <function _normalize_live_cell at 0x7f81336c5a80>(['codex', 'gpt-6.1-sol', {'e': 1}])
E        +    where <function _normalize_live_cell at 0x7f81336c5a80> = SM._normalize_live_cell

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:145: AssertionError
_ test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling[list] _

effort = ['high']

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling(effort):
        bad = ["codex", "gpt-6.1-sol", effort]
>       assert RDISC.nonpanel_cell_proven(_CONFIG, _cell_map(bad), "codex", "verifier") is False
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:153: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:304: in nonpanel_cell_proven
    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map_ = {'nonPanelLiveCells': [['codex', 'gpt-6.1-sol', ['high']]], 'nonPanelLiveCellsSource': 'probed'}

    def _nonpanel_cell_evidence(seat_map_):
        """The set of normalized ``(vendor, model, effort)`` triples the map proves live — empty unless
        the source is `probed` or `synthesized` and `nonPanelLiveCells` is a list (malformed entries are
        skipped). A map with none of the three cell-proof keys, or no map at all, proves no cell."""
        sm = seat_map_ if isinstance(seat_map_, dict) else {}
        source = sm.get(_SEAT_MAP_CELLS_SOURCE_KEY)
        raw = sm.get(_SEAT_MAP_CELLS_KEY)
        if (source not in (liveness_cache.LIVE_CELLS_SOURCE_PROBED,
                           liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
                or not isinstance(raw, list)):
            return frozenset()
        cells = set()
        for entry in raw:
            normalized = seat_map._normalize_live_cell(entry)
            if normalized is not None:
>               cells.add(normalized)
E               TypeError: unhashable type: 'list'

/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:279: TypeError
_ test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling[dict] _

effort = {'e': 1}

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling(effort):
        bad = ["codex", "gpt-6.1-sol", effort]
>       assert RDISC.nonpanel_cell_proven(_CONFIG, _cell_map(bad), "codex", "verifier") is False
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:153: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:304: in nonpanel_cell_proven
    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map_ = {'nonPanelLiveCells': [['codex', 'gpt-6.1-sol', {'e': 1}]], 'nonPanelLiveCellsSource': 'probed'}

    def _nonpanel_cell_evidence(seat_map_):
        """The set of normalized ``(vendor, model, effort)`` triples the map proves live — empty unless
        the source is `probed` or `synthesized` and `nonPanelLiveCells` is a list (malformed entries are
        skipped). A map with none of the three cell-proof keys, or no map at all, proves no cell."""
        sm = seat_map_ if isinstance(seat_map_, dict) else {}
        source = sm.get(_SEAT_MAP_CELLS_SOURCE_KEY)
        raw = sm.get(_SEAT_MAP_CELLS_KEY)
        if (source not in (liveness_cache.LIVE_CELLS_SOURCE_PROBED,
                           liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
                or not isinstance(raw, list)):
            return frozenset()
        cells = set()
        for entry in raw:
            normalized = seat_map._normalize_live_cell(entry)
            if normalized is not None:
>               cells.add(normalized)
E               TypeError: unhashable type: 'dict'

/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:279: TypeError
_ test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling[list] _

effort = ['high']

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling(effort):
        bad = ["cursor", "cursor-grok-4.6", effort]
        good = ["cursor", "cursor-grok-4.6", "xhigh"]
>       assert "cursor" not in RDISC.nonpanel_candidates(_CONFIG, _cell_map(bad), "reviewer-deep")
                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:161: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:312: in nonpanel_candidates
    cells = _nonpanel_cell_evidence(seat_map_)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map_ = {'nonPanelLiveCells': [['cursor', 'cursor-grok-4.6', ['high']]], 'nonPanelLiveCellsSource': 'probed'}

    def _nonpanel_cell_evidence(seat_map_):
        """The set of normalized ``(vendor, model, effort)`` triples the map proves live — empty unless
        the source is `probed` or `synthesized` and `nonPanelLiveCells` is a list (malformed entries are
        skipped). A map with none of the three cell-proof keys, or no map at all, proves no cell."""
        sm = seat_map_ if isinstance(seat_map_, dict) else {}
        source = sm.get(_SEAT_MAP_CELLS_SOURCE_KEY)
        raw = sm.get(_SEAT_MAP_CELLS_KEY)
        if (source not in (liveness_cache.LIVE_CELLS_SOURCE_PROBED,
                           liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
                or not isinstance(raw, list)):
            return frozenset()
        cells = set()
        for entry in raw:
            normalized = seat_map._normalize_live_cell(entry)
            if normalized is not None:
>               cells.add(normalized)
E               TypeError: unhashable type: 'list'

/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:279: TypeError
_ test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling[dict] _

effort = {'e': 1}

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling(effort):
        bad = ["cursor", "cursor-grok-4.6", effort]
        good = ["cursor", "cursor-grok-4.6", "xhigh"]
>       assert "cursor" not in RDISC.nonpanel_candidates(_CONFIG, _cell_map(bad), "reviewer-deep")
                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:161: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:312: in nonpanel_candidates
    cells = _nonpanel_cell_evidence(seat_map_)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map_ = {'nonPanelLiveCells': [['cursor', 'cursor-grok-4.6', {'e': 1}]], 'nonPanelLiveCellsSource': 'probed'}

    def _nonpanel_cell_evidence(seat_map_):
        """The set of normalized ``(vendor, model, effort)`` triples the map proves live — empty unless
        the source is `probed` or `synthesized` and `nonPanelLiveCells` is a list (malformed entries are
        skipped). A map with none of the three cell-proof keys, or no map at all, proves no cell."""
        sm = seat_map_ if isinstance(seat_map_, dict) else {}
        source = sm.get(_SEAT_MAP_CELLS_SOURCE_KEY)
        raw = sm.get(_SEAT_MAP_CELLS_KEY)
        if (source not in (liveness_cache.LIVE_CELLS_SOURCE_PROBED,
                           liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
                or not isinstance(raw, list)):
            return frozenset()
        cells = set()
        for entry in raw:
            normalized = seat_map._normalize_live_cell(entry)
            if normalized is not None:
>               cells.add(normalized)
E               TypeError: unhashable type: 'dict'

/home/user/wt-1869-wo4/plugins/superheroes/lib/receipt_disclosures.py:279: TypeError
_____ test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling[list] _____

effort = ['high']

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling(effort):
>       seat_map = SM.build(
            SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0,
            live_cells=[["claude", "opus-5.5", "xhigh"], ["codex", "gpt-6.1-sol", effort], _GOOD],
            live_cells_source="probed",
        )

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:167: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

roster = ('code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer', 'grounding-seat')
live_vendors = ['claude', 'codex'], author_family = 'anthropic'
narrative_family = 'anthropic', seed = 0, tier_by_seat = None, pins = None
liveness_pin_scoped = False
live_cells = [['claude', 'opus-5.5', 'xhigh'], ['codex', 'gpt-6.1-sol', ['high']], ['codex', 'gpt-6.1-sol', 'xhigh']]
live_cells_source = 'probed', codex_role_pins = None
extra_maker_families = None

    def build(
        roster: tuple[str, ...] | list[str] | None,
        live_vendors: list[str] | None,
        author_family: str | None,
        narrative_family: str | None,
        seed: int,
        tier_by_seat: dict[str, str] | None = None,
        pins: dict[str, dict] | None = None,
        liveness_pin_scoped: bool = False,
        live_cells: list | None = None,
        live_cells_source: str | None = None,
        codex_role_pins: dict[str, str] | None = None,
        extra_maker_families: frozenset[str] | None = None,
    ) -> dict:
        degradations: list[dict[str, str]] = []
        tier_degraded_seats: set[str] = set()
    
        roster = tuple(roster) if roster else PANEL_ROSTER
    
        live = [v for v in (live_vendors or []) if isinstance(v, str) and v]
    
        # The makers' families are barred from every maker-excluded seat: the author's plus every extra
        # maker's. A seat none of the live reviewers can fill is recorded unfilled, never seated with a
        # maker family.
        makers: set[str] = {f for f in ({author_family} | set(extra_maker_families or ())) if f}
    
        role_pins = codex_role_pins or {}
    
        if live_cells is None:
            live_cells_normalized = _synthesize_live_cells(
                live, roster, tier_by_seat, codex_role_pins=role_pins or None,
            )
            resolved_cells_source = (
                liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED
                if live_cells_source is None
                else live_cells_source
            )
        else:
            live_cells_normalized = set()
            for entry in live_cells:
                normalized = _normalize_live_cell(entry)
                if normalized is not None:
>                   live_cells_normalized.add(normalized)
E                   TypeError: unhashable type: 'list'

/home/user/wt-1869-wo4/plugins/superheroes/lib/seat_map.py:621: TypeError
_____ test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling[dict] _____

effort = {'e': 1}

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling(effort):
>       seat_map = SM.build(
            SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0,
            live_cells=[["claude", "opus-5.5", "xhigh"], ["codex", "gpt-6.1-sol", effort], _GOOD],
            live_cells_source="probed",
        )

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:167: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

roster = ('code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer', 'grounding-seat')
live_vendors = ['claude', 'codex'], author_family = 'anthropic'
narrative_family = 'anthropic', seed = 0, tier_by_seat = None, pins = None
liveness_pin_scoped = False
live_cells = [['claude', 'opus-5.5', 'xhigh'], ['codex', 'gpt-6.1-sol', {'e': 1}], ['codex', 'gpt-6.1-sol', 'xhigh']]
live_cells_source = 'probed', codex_role_pins = None
extra_maker_families = None

    def build(
        roster: tuple[str, ...] | list[str] | None,
        live_vendors: list[str] | None,
        author_family: str | None,
        narrative_family: str | None,
        seed: int,
        tier_by_seat: dict[str, str] | None = None,
        pins: dict[str, dict] | None = None,
        liveness_pin_scoped: bool = False,
        live_cells: list | None = None,
        live_cells_source: str | None = None,
        codex_role_pins: dict[str, str] | None = None,
        extra_maker_families: frozenset[str] | None = None,
    ) -> dict:
        degradations: list[dict[str, str]] = []
        tier_degraded_seats: set[str] = set()
    
        roster = tuple(roster) if roster else PANEL_ROSTER
    
        live = [v for v in (live_vendors or []) if isinstance(v, str) and v]
    
        # The makers' families are barred from every maker-excluded seat: the author's plus every extra
        # maker's. A seat none of the live reviewers can fill is recorded unfilled, never seated with a
        # maker family.
        makers: set[str] = {f for f in ({author_family} | set(extra_maker_families or ())) if f}
    
        role_pins = codex_role_pins or {}
    
        if live_cells is None:
            live_cells_normalized = _synthesize_live_cells(
                live, roster, tier_by_seat, codex_role_pins=role_pins or None,
            )
            resolved_cells_source = (
                liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED
                if live_cells_source is None
                else live_cells_source
            )
        else:
            live_cells_normalized = set()
            for entry in live_cells:
                normalized = _normalize_live_cell(entry)
                if normalized is not None:
>                   live_cells_normalized.add(normalized)
E                   TypeError: unhashable type: 'dict'

/home/user/wt-1869-wo4/plugins/superheroes/lib/seat_map.py:621: TypeError
____ test_m1_m3_same_family_degradations_keeps_its_fail_closed_result[list] ____

effort = ['high']

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m3_same_family_degradations_keeps_its_fail_closed_result(effort):
        seat_map = SM.build(
            SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0,
            live_cells=[["claude", "opus-5.5", "xhigh"], _GOOD], live_cells_source="probed",
        )
        seat_map["liveCells"] = list(seat_map["liveCells"]) + [["codex", "gpt-6.1-sol", effort]]
        seat = next(s for s in SM.PANEL_ROSTER if isinstance(seat_map["seats"].get(s), dict))
        cfg = seat_map["seats"][seat]
        # a map with any malformed live cell is unusable evidence: the existing `None`
>       assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:186: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map = {'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....'relaxed critical-diversity — no assignment spanned ≥2 families'}], 'seed': 0, 'liveVendors': ['claude', 'codex'], ...}
seat = 'code-reviewer'
cfg = {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', ...}
tier = 'reviewer-deep'

    def _resolvable_families_for_seat(
        seat_map: dict, seat: str, cfg: dict, tier: str | None = None,
    ) -> set[str] | None:
        """Every registry family this seat could have been filled with at `tier`, from the map's live
        vendors. `None` = evidence UNUSABLE. An EMPTY SET = usable evidence, nothing resolvable at that
        tier. `tier` defaults to the seat's own recorded tier; a caller asking about a REQUIRED tier
        passes it explicitly (#680 round 3)."""
        pin_scoped = seat_map.get("livenessPinScoped")
        if pin_scoped is not False:
            return None
        raw_degs = seat_map.get("degradations")
        if raw_degs is not None and not isinstance(raw_degs, list):
            return None
        degradations = raw_degs if isinstance(raw_degs, list) else []
        for deg in degradations:
            if isinstance(deg, dict) and deg.get("constraint") in UNPROVEN_LIVENESS_CONSTRAINTS:
                return None
        cells_source = seat_map.get("liveCellsSource")
        if cells_source == liveness_cache.LIVE_CELLS_SOURCE_UNPROBED:
            return None
        known_vendors = set(vendors())
        tier = tier or _seat_tier(seat, cfg)
        role_pins, pins_usable = _read_codex_role_pins(seat_map)
        if not pins_usable:
            return None
        pin_arg = role_pins if role_pins else None
        families: set[str] = set()
        if cells_source == liveness_cache.LIVE_CELLS_SOURCE_PROBED:
            raw_cells = seat_map.get("liveCells")
            if not isinstance(raw_cells, list):
                return None
            live_cell_set: set[tuple[str, str, str | None]] = set()
            for entry in raw_cells:
                normalized = _normalize_live_cell(entry)
                if normalized is None:
                    return None
                vendor, _model, _effort = normalized
                if vendor not in known_vendors:
                    return None
>               live_cell_set.add(normalized)
E               TypeError: unhashable type: 'list'

/home/user/wt-1869-wo4/plugins/superheroes/lib/seat_map.py:306: TypeError
____ test_m1_m3_same_family_degradations_keeps_its_fail_closed_result[dict] ____

effort = {'e': 1}

    @pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
    def test_m1_m3_same_family_degradations_keeps_its_fail_closed_result(effort):
        seat_map = SM.build(
            SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0,
            live_cells=[["claude", "opus-5.5", "xhigh"], _GOOD], live_cells_source="probed",
        )
        seat_map["liveCells"] = list(seat_map["liveCells"]) + [["codex", "gpt-6.1-sol", effort]]
        seat = next(s for s in SM.PANEL_ROSTER if isinstance(seat_map["seats"].get(s), dict))
        cfg = seat_map["seats"][seat]
        # a map with any malformed live cell is unusable evidence: the existing `None`
>       assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1869-wo4/plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py:186: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

seat_map = {'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....'relaxed critical-diversity — no assignment spanned ≥2 families'}], 'seed': 0, 'liveVendors': ['claude', 'codex'], ...}
seat = 'code-reviewer'
cfg = {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', ...}
tier = 'reviewer-deep'

    def _resolvable_families_for_seat(
        seat_map: dict, seat: str, cfg: dict, tier: str | None = None,
    ) -> set[str] | None:
        """Every registry family this seat could have been filled with at `tier`, from the map's live
        vendors. `None` = evidence UNUSABLE. An EMPTY SET = usable evidence, nothing resolvable at that
        tier. `tier` defaults to the seat's own recorded tier; a caller asking about a REQUIRED tier
        passes it explicitly (#680 round 3)."""
        pin_scoped = seat_map.get("livenessPinScoped")
        if pin_scoped is not False:
            return None
        raw_degs = seat_map.get("degradations")
        if raw_degs is not None and not isinstance(raw_degs, list):
            return None
        degradations = raw_degs if isinstance(raw_degs, list) else []
        for deg in degradations:
            if isinstance(deg, dict) and deg.get("constraint") in UNPROVEN_LIVENESS_CONSTRAINTS:
                return None
        cells_source = seat_map.get("liveCellsSource")
        if cells_source == liveness_cache.LIVE_CELLS_SOURCE_UNPROBED:
            return None
        known_vendors = set(vendors())
        tier = tier or _seat_tier(seat, cfg)
        role_pins, pins_usable = _read_codex_role_pins(seat_map)
        if not pins_usable:
            return None
        pin_arg = role_pins if role_pins else None
        families: set[str] = set()
        if cells_source == liveness_cache.LIVE_CELLS_SOURCE_PROBED:
            raw_cells = seat_map.get("liveCells")
            if not isinstance(raw_cells, list):
                return None
            live_cell_set: set[tuple[str, str, str | None]] = set()
            for entry in raw_cells:
                normalized = _normalize_live_cell(entry)
                if normalized is None:
                    return None
                vendor, _model, _effort = normalized
                if vendor not in known_vendors:
                    return None
>               live_cell_set.add(normalized)
E               TypeError: unhashable type: 'dict'

/home/user/wt-1869-wo4/plugins/superheroes/lib/seat_map.py:306: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_the_chokepoint_returns_none_for_a_non_string_effort[list]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_the_chokepoint_returns_none_for_a_non_string_effort[dict]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling[list]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling[dict]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling[list]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling[dict]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling[list]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling[dict]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m3_same_family_degradations_keeps_its_fail_closed_result[list]
FAILED plugins/superheroes/lib/tests/test_tooling_folds_c7l3.py::test_m1_m3_same_family_degradations_keeps_its_fail_closed_result[dict]
10 failed, 9 deselected in 0.70s
```

**restore** — the inverse edit; the whole file was then compared with the pre-neutralization copy (`cmp`: identical).

**restore receipt** — the restored lines, quoted back:
```
213:        # axis: a malformed effort never reaches a set as an unhashable triple — see bite-proof record c7l3_wo4_tooling
214:        if effort is not None and not isinstance(effort, str):
215:            return None
```

**green** — `same command` (exit 0):
```
..........                                                               [100%]
10 passed, 9 deselected in 0.34s
```
