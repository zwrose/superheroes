# layer4a scoped-finder role bite-proof (issue #1272, WO-E)

| ID | guarded element | proving test |
|---|---|---|
| E1 | `_MATRIX["scoped-finder"]` row | `test_t_same_scoped_finder_matches_reviewer_deep_cells` |

## E1 — `_MATRIX["scoped-finder"]` row

**Axis:** scoped-finder cells must match reviewer-deep, not reviewer.

**Guarded code:** `_MATRIX["scoped-finder"] = dict(_MATRIX["reviewer-deep"])`

**Neutralization:**

```python
_MATRIX["scoped-finder"] = dict(_MATRIX["reviewer"])
```

**Detector:** `test_t_same_scoped_finder_matches_reviewer_deep_cells`

**Red:**

```
FF.                                                                      [100%]
=================================== FAILURES ===================================
________ test_t_same_scoped_finder_matches_reviewer_deep_cells[claude] _________

vendor = 'claude'

    @pytest.mark.parametrize("vendor", MR.vendors())
    def test_t_same_scoped_finder_matches_reviewer_deep_cells(vendor):
>       assert MR.matrix_config(_ROLE, vendor) == MR.matrix_config("reviewer-deep", vendor)
E       AssertionError: assert ('sonnet-5', 'high') == ('opus-5', 'xhigh')
E         
E         At index 0 diff: 'sonnet-5' != 'opus-5'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_layer4a_scoped_finder_role_1272.py:142: AssertionError
_________ test_t_same_scoped_finder_matches_reviewer_deep_cells[codex] _________

vendor = 'codex'

    @pytest.mark.parametrize("vendor", MR.vendors())
    def test_t_same_scoped_finder_matches_reviewer_deep_cells(vendor):
>       assert MR.matrix_config(_ROLE, vendor) == MR.matrix_config("reviewer-deep", vendor)
E       AssertionError: assert ('gpt-5.6-terra', 'high') == ('gpt-5.6-sol', 'xhigh')
E         
E         At index 0 diff: 'gpt-5.6-terra' != 'gpt-5.6-sol'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_layer4a_scoped_finder_role_1272.py:142: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_scoped_finder_role_1272.py::test_t_same_scoped_finder_matches_reviewer_deep_cells[claude]
FAILED plugins/superheroes/lib/tests/test_layer4a_scoped_finder_role_1272.py::test_t_same_scoped_finder_matches_reviewer_deep_cells[codex]
2 failed, 1 passed in 1.06s
```

**Restore (quoted restored lines):**

```python
_MATRIX["scoped-finder"] = dict(_MATRIX["reviewer-deep"])
```

**Green:**

```
...                                                                      [100%]
3 passed in 0.43s
```
