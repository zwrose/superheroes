# layer3 order shape bite-proof (issue #1272, WO-D)

| ID | guarded element | proving test |
|---|---|---|
| D1a | engine-seat fixer order carries no payload-contract block | `test_l3_d1_engine_fixer_order_names_no_result_shape` |
| D1b | host-seat fixer order still carries the payload-contract block | `test_l3_d1_host_fixer_order_names_required_payload_shape` |
| D2 | lint arm fires at production emission (no expect_items) | `test_l3_d2_production_emission_refuses_the_old_order_text` |

Normalization: `-B -X pycache_prefix=/private/tmp/superheroes-pyc-woD`, single-node `::test_*`.

## D1a — engine-seat fixer order carries no payload-contract block

**Axis:** `render_order` for `dispatch-fixer` with `host_seat=False` must not append the payload-contract block.

**Neutralization:** at `round_orders.render_order`, replace `if phase != round_phases.P_FIXER or context.get("host_seat"):` with `if True:` so every phase including engine fixer renders `## Payload contract`.

**Red** — `plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_engine_fixer_order_names_no_result_shape`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_l3_d1_engine_fixer_order_names_no_result_shape _________________

    def test_l3_d1_engine_fixer_order_names_no_result_shape():
        # axis: engine dispatch-fixer carries no payload-contract heading or fixes literal
        ctx = _base_context(host_seat=False, placeholders=_fixer_placeholders())
        text, reason = RO.render_order(RP.P_FIXER, "seat", ctx)
        assert reason is None, reason
>       assert _PAYLOAD_HEADING not in text
E       AssertionError: assert '## Payload contract' not in 'You are the...yload.json\n'
E         
E         '## Payload contract' is contained here:
E           ed
E           -----
E           
E           ## Payload contract
E           ...
E         
E         ...Full output truncated (16 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_engine_fixer_order_names_no_result_shape
1 failed in 0.18s
```

**Restore:** change `if True:` back to `if phase != round_phases.P_FIXER or context.get("host_seat"):`.

**Restore receipt (restored lines):**
```python
        if phase != round_phases.P_FIXER or context.get("host_seat"):
            contract_block, creason = _format_payload_contract(phase)
            if creason:
                return _refuse(creason)
            blocks.append(contract_block.rstrip())
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## D1b — host-seat fixer order still carries the payload-contract block

**Axis:** `render_order` for `dispatch-fixer` with `host_seat=True` must append the payload-contract block.

**Neutralization:** at `round_orders.render_order`, replace `if phase != round_phases.P_FIXER or context.get("host_seat"):` with `if phase != round_phases.P_FIXER:` so host fixer seats skip the payload-contract block.

**Red** — `plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_host_fixer_order_names_required_payload_shape`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_l3_d1_host_fixer_order_names_required_payload_shape ____________

    def test_l3_d1_host_fixer_order_names_required_payload_shape():
        # axis: host-seat dispatch-fixer carries the payload-contract block with required fixes
        text = _render(RP.P_FIXER, _fixer_placeholders())
>       assert _PAYLOAD_HEADING in text
E       AssertionError: assert '## Payload contract' in 'You are the...yload.json\n'

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:104: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_host_fixer_order_names_required_payload_shape
1 failed in 0.16s
```

**Restore:** change `if phase != round_phases.P_FIXER:` back to `if phase != round_phases.P_FIXER or context.get("host_seat"):`.

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## D2 — lint arm fires at production emission (no expect_items)

**Axis:** `order_lint.check_text(..., kind="fixer")` with default `expect_items` refuses order text that names a result shape.

**Neutralization:** at `order_lint._shape`, remove the `if kind == "fixer":` arm (the two `order-result-shape-authored` returns).

**Red** — `plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d2_production_emission_refuses_the_old_order_text`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_l3_d2_production_emission_refuses_the_old_order_text ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-4503/test_l3_d2_production_emission0')

    def test_l3_d2_production_emission_refuses_the_old_order_text(tmp_path):
        # axis: production path lint (no expect_items) refuses authored result shape
        repo = str(tmp_path)
        os.makedirs(repo, exist_ok=True)
        old_shape = (
            "# Fix\n\n"
            + _PAYLOAD_HEADING + "\n\n"
            "Required keys: fixes\n"
        )
        r = OL.check_text(old_shape, repo, kind="fixer")
>       assert r["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:165: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d2_production_emission_refuses_the_old_order_text
1 failed in 0.19s
```

**Restore:** reinstate the `if kind == "fixer":` arm with both `payload-contract-heading` and `_FIXER_LITERAL` returns.

**Restore receipt (restored lines):**
```python
    if kind == "fixer":
        if not allow_payload_contract and _PAYLOAD_CONTRACT_HEADING in text:
            return _f(TOKEN_RESULT_SHAPE_AUTHORED, "payload-contract-heading")
        if _FIXER_OBJECT.search(text):
            return _f(TOKEN_RESULT_SHAPE_AUTHORED, _FIXER_LITERAL)
    return None
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.15s
```
