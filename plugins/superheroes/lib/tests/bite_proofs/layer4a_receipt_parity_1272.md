# layer4a receipt parity re-pin bite-proof (issue #1272, WO-G)

Head under proof: **01fceef1**. Courtesy proof for the re-pinned `certifiedPanel` bool assertion.

| ID | guarded element | proving test |
|---|---|---|
| G1 | **RETIRED — element removed by owner ruling 1 = b (PR #1403 comment 5810832062)** writer `seatMap.seats` rows carry `certifiedPanel` as bool | direct driver/writer seatMap parity in `test_certification_receipt_matches_driver_today_fields` |

## G1 — writer seatMap.seats certifiedPanel bool assertion

**Axis:** every writer `seatMap.seats` dict row must carry `certifiedPanel` as a bool before parity strip.

**Guarded code:** `_seat_map_for_driver_parity` in `test_round_certification_parity.py` (via `round_certification._build_receipt` annotation loop).

**Neutralization:**

```python
receipt["seatMap"]["seats"] = {
    seat_name: row
    for seat_name, row in seat_map_seats.items()
}
```

**Detector:** `test_certification_receipt_matches_driver_today_fields[converged-single-round]`

**Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_certification_receipt_matches_driver_today_fields[converged-single-round] _

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-5524/test_certification_receipt_mat0')
label = 'converged-single-round'
builder = <function parity_converged_single_round at 0x106484af0>

    @pytest.mark.parametrize(
        "label,builder",
        PARITY_FIXTURES_WITH_HAND_LANDED,
        ids=[label for label, _ in PARITY_FIXTURES_WITH_HAND_LANDED],
    )
    def test_certification_receipt_matches_driver_today_fields(tmp_path, label, builder):
        session_dir = builder(tmp_path)
>       _assert_receipt_parity(session_dir)

tests/test_round_certification_parity.py:197: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
tests/test_round_certification_parity.py:86: in _assert_receipt_parity
    assert _seat_map_for_driver_parity(cert_receipt["seatMap"]) == driver_receipt[
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

writer_seat_map = {'seats': {'code-reviewer': {'model': 'gpt-5.6-sol', 'vendor': 'codex'}}, 'violations': [{'constraint': 'critical-dive...ty-reviewer'}, {'constraint': 'missing-seat', 'derived': True, 'evidence': 'unproven-basis', 'seat': 'test-reviewer'}]}

    def _seat_map_for_driver_parity(writer_seat_map):
        """Strip writer-only certifiedPanel before comparing to the driver seatMap."""
        if not isinstance(writer_seat_map, dict):
            return writer_seat_map
        seats = writer_seat_map.get("seats")
        if not isinstance(seats, dict):
            return writer_seat_map
        stripped_seats = {}
        for seat_name, row in seats.items():
            if isinstance(row, dict):
>               assert isinstance(row.get("certifiedPanel"), bool), (
                    "writer seatMap.seats[%r] must carry certifiedPanel as bool" % seat_name
                )
E               AssertionError: writer seatMap.seats['code-reviewer'] must carry certifiedPanel as bool
E               assert False
E                +  where False = isinstance(None, bool)
E                +    where None = <built-in method get of dict object at 0x10644ac80>('certifiedPanel')
E                +      where <built-in method get of dict object at 0x10644ac80> = {'model': 'gpt-5.6-sol', 'vendor': 'codex'}.get

tests/test_round_certification_parity.py:51: AssertionError
=========================== short test summary info ============================
FAILED tests/test_round_certification_parity.py::test_certification_receipt_matches_driver_today_fields[converged-single-round]
1 failed in 0.31s
```

**Restore (quoted restored lines):**

```python
        receipt["seatMap"]["seats"] = {
            seat_name: (
                dict(row, certifiedPanel=seat_name not in uncertified_panel_seats)
                if isinstance(row, dict)
                else row
            )
            for seat_name, row in seat_map_seats.items()
        }
```

**Green:**

```
.                                                                        [100%]
1 passed in 0.33s
```
