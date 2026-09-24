# layer3 order shape bite-proof (issue #1272, WO-D)

Re-taken at head cfd2dc04 (plus this order's test-only changes).

| ID | guarded element | proving test |
|---|---|---|
| D1a | engine-seat fixer order carries no payload-contract block | `test_l3_d1_engine_fixer_order_names_no_result_shape` |
| D1b | host-seat fixer order still carries the payload-contract block | `test_l3_d1_host_fixer_order_names_required_payload_shape` |
| D1c | engine fixer escalation block carries no `see Payload contract` | `test_l3_d1_engine_fixer_order_names_no_result_shape` |
| D2 | lint arm fires at production emission (no expect_items) | `test_l3_d2_production_emission_refuses_the_old_order_text` |

## D1a — engine-seat fixer order carries no payload-contract block

**Axis:** engine dispatch-fixer must not append the payload-contract block.

**Guarded code:** `round_orders.render_order`

**Neutralization:**

```python
if True:
```

**Detector:** `test_l3_d1_engine_fixer_order_names_no_result_shape`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_l3_d1_engine_fixer_order_names_no_result_shape ______________

    def test_l3_d1_engine_fixer_order_names_no_result_shape():
        # axis: engine dispatch-fixer carries no payload-contract heading or fixes literal
        ctx = _base_context(host_seat=False, placeholders=_fixer_placeholders())
        text, reason = RO.render_order(RP.P_FIXER, "seat", ctx)
        assert reason is None, reason
>       assert _PAYLOAD_HEADING not in text
E       AssertionError: assert '## Payload contract' not in 'You are the... sandbox).\n'
E         
E         '## Payload contract' is contained here:
E           ed
E           -----
E           
E           ## Payload contract
E           ...
E         
E         ...Full output truncated (14 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_engine_fixer_order_names_no_result_shape
1 failed in 0.15s
```

**Restore (quoted restored lines):**

```python
if phase != round_phases.P_FIXER or context.get("host_seat"):
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

## D1b — host-seat fixer order still carries the payload-contract block

**Axis:** host dispatch-fixer must append the payload-contract block.

**Guarded code:** `round_orders.render_order`

**Neutralization:**

```python
if phase != round_phases.P_FIXER:
```

**Detector:** `test_l3_d1_host_fixer_order_names_required_payload_shape`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_l3_d1_host_fixer_order_names_required_payload_shape ___________

    def test_l3_d1_host_fixer_order_names_required_payload_shape():
        # axis: host-seat dispatch-fixer carries the payload-contract block with required fixes
        text = _render(RP.P_FIXER, _fixer_placeholders())
>       assert _PAYLOAD_HEADING in text
E       AssertionError: assert '## Payload contract' in 'You are the fixer for one round of an auto-fix code-review loop.\n\n## Input\n- Findings to fix: /tmp/superheroes-ses....\n\n- Payload landing path: /tmp/superheroes-session-wo4-golden/round-2/landing/dispatch-fixer/seat.a0.payload.json\n'

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:104: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_host_fixer_order_names_required_payload_shape
1 failed in 0.15s
```

**Restore (quoted restored lines):**

```python
if phase != round_phases.P_FIXER or context.get("host_seat"):
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.17s
```

## D1c — engine fixer escalation block carries no `see Payload contract`

**Axis:** engine FIXER_ESCALATION_BLOCK must not cite Payload contract.

**Guarded code:** `round_orders._fixer_derived_placeholders`

**Neutralization:**

```python
ph["FIXER_ESCALATION_BLOCK"] = (
            "Report it for owner escalation (see Payload contract) with the id and why."
        )
```

**Detector:** `test_l3_d1_engine_fixer_order_names_no_result_shape`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_l3_d1_engine_fixer_order_names_no_result_shape ______________

    def test_l3_d1_engine_fixer_order_names_no_result_shape():
        # axis: engine dispatch-fixer carries no payload-contract heading or fixes literal
        ctx = _base_context(host_seat=False, placeholders=_fixer_placeholders())
        text, reason = RO.render_order(RP.P_FIXER, "seat", ctx)
        assert reason is None, reason
        assert _PAYLOAD_HEADING not in text
        assert OL._FIXER_LITERAL not in text
>       assert "see Payload contract" not in text
E       AssertionError: assert 'see Payload contract' not in 'You are the... sandbox).\n'
E         
E         'see Payload contract' is contained here:
E           calation (see Payload contract) with the id and why.
E         ?           ++++++++++++++++++++
E           
E           ## Ratified residuals (owner-ratified, quoted data)
E           ...
E         
E         ...Full output truncated (11 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d1_engine_fixer_order_names_no_result_shape
1 failed in 0.15s
```

**Restore (quoted restored lines):**

```python
ph["FIXER_ESCALATION_BLOCK"] = (
            "Report it for owner escalation via the runner's native write-result contract "
            "the runner appends at dispatch: set `signal` to `needs_context`, name the "
            "finding id and why in `report`, and write the graded JSON object to the "
            "result file when the contract names one."
        )
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

## D2 — lint arm fires at production emission (no expect_items)

**Axis:** fixer kind at production emission refuses authored result shape.

**Guarded code:** `order_lint._shape`

**Neutralization:**

```python
return None
```

**Detector:** `test_l3_d2_production_emission_refuses_the_old_order_text`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_l3_d2_production_emission_refuses_the_old_order_text ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5187/test_l3_d2_production_emission0')

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

plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py:166: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer3_order_shape_1272.py::test_l3_d2_production_emission_refuses_the_old_order_text
1 failed in 0.15s
```

**Restore (quoted restored lines):**

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
1 passed in 0.14s
```
