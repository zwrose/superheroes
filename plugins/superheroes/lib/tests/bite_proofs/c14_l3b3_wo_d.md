# C14 layer 3b-3 WO-D — fail receipts

Advisor-ordered fail receipts for a test-only layer; not bite-proofs.

## R-D1 — plugins/superheroes/lib/tests/test_seat_map.py::test_codex_role_pin_astra_registered_seats_at_high

- **axis:** registered gpt-6-astra role-pin seats reviewer-deep at high effort from live cells.
- **broken subject** (`plugins/superheroes/lib/model_registry.py`, `gpt-6-astra` row): inserted `"registration": "probe-pending",  # fail-receipt R-D1` after `"override_only": False,`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-D -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_codex_role_pin_astra_registered_seats_at_high -q -p no:xdist`
- **raw red** (exit 1):
```
>       assert codex_deep
E       assert []
```
- **restore:** removed `"registration": "probe-pending",  # fail-receipt R-D1` from the `gpt-6-astra` row
- **raw green** (exit 0): `1 passed in 1.04s`

## R-D2 — plugins/superheroes/lib/tests/test_seat_map.py::test_codex_role_pin_astra_not_live_falls_back_to_matrix

- **axis:** registered gpt-6-astra role-pin falls back to matrix when Astra is not in live cells.
- **broken subject** (`plugins/superheroes/lib/model_registry.py`, `gpt-6-astra` row): inserted `"registration": "probe-pending",  # fail-receipt R-D2` after `"override_only": False,`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-D -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_codex_role_pin_astra_not_live_falls_back_to_matrix -q -p no:xdist`
- **raw red** (exit 1):
```
        not_live = [d for d in m["degradations"] if d["constraint"] == "role-pin-not-live"]
>       assert not_live
E       assert []
```
- **restore:** removed `"registration": "probe-pending",  # fail-receipt R-D2` from the `gpt-6-astra` row
- **raw green** (exit 0): `1 passed in 0.54s`

## R-D3 — plugins/superheroes/lib/tests/test_engine_pref.py::test_normalize_codex_pin_map_registered_astra_valid

- **axis:** registered gpt-6-astra is accepted as a reviewer-deep pin against the real registry.
- **broken subject** (`plugins/superheroes/lib/model_registry.py`, `gpt-6-astra` row): inserted `"registration": "probe-pending",  # fail-receipt R-D3` after `"override_only": False,`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-D -m pytest plugins/superheroes/lib/tests/test_engine_pref.py::test_normalize_codex_pin_map_registered_astra_valid -q -p no:xdist`
- **raw red** (exit 1):
```
>       assert result["pins"] == {"reviewer-deep": "gpt-6-astra"}
E       AssertionError: assert {} == {'reviewer-de...'gpt-6-astra'}
```
- **restore:** removed `"registration": "probe-pending",  # fail-receipt R-D3` from the `gpt-6-astra` row
- **raw green** (exit 0): `1 passed in 0.70s`
