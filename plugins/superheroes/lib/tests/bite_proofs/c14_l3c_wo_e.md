# C14 layer 3c WO-E — bite-proofs

**Provenance:** cursor / composer-2.5 (implementer, order `1273-l3c-E`).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-E1 | `test_payload_shape_doc_drift.py::test_payload_shape_doc_tokens_pinned_to_review_payload_shapes` | inline payloadShape tokens named in auto-fix-loop.md are members of REVIEW_PAYLOAD_SHAPES | same |
| BP-E2 | `_assert_entry_points_in_closure` helper | vacuity guard calls real closure check and fails on renamed entry point | `test_admission_path_vacuity_guard_fails_on_renamed_entry_point` |
| BP-E3 | `test_canonical_payload_digest_literal` | literal hex is the cross-process contract for canonical_payload_digest | same |
| BP-E4 | `test_writer_tests_run_with_no_driver` subprocess import guard | writer import surface loads no driver module | same |
| BP-E5 | `_resolved_inputs_for_runner_seat` signature assertion | kwargs track `_build_resolved_inputs` parameter names | `test_receipt_seat_model_is_the_runner_records_engine_model` |

Residuals 4, 7, 9 and v3 are wording/structure changes with no new detector — no bite-proof.

---

## BP-E1 — payload-shape doc drift

- **neutralization** (`plugins/superheroes/lib/engine_adapter.py`): `SHAPE_OBJECT_BOTH_PAYLOAD_KEYS = "object-both-payload-keys-x"`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-E -m pytest plugins/superheroes/lib/tests/test_payload_shape_doc_drift.py::test_payload_shape_doc_tokens_pinned_to_review_payload_shapes -q -p no:xdist`
- **raw red** (exit 1):
```
E           AssertionError: literal token 'object-both-payload-keys' not in REVIEW_PAYLOAD_SHAPES
```
- **restore:** `SHAPE_OBJECT_BOTH_PAYLOAD_KEYS = "object-both-payload-keys"`
- **raw green** (exit 0): `1 passed in 0.38s`

---

## BP-E2 — admission vacuity guard

- **neutralization** (`plugins/superheroes/lib/tests/test_admission_clock_census.py`, `_assert_entry_points_in_closure`): deleted `assert name in closure` line (replaced with `pass`)
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-E -m pytest plugins/superheroes/lib/tests/test_admission_clock_census.py::test_admission_path_vacuity_guard_fails_on_renamed_entry_point -q -p no:xdist`
- **raw red** (exit 1):
```
E           Failed: DID NOT RAISE <class 'AssertionError'>
```
- **restore:** restored `assert name in closure, "entry point %s missing from closure" % name`
- **raw green** (exit 0): `1 passed in 0.65s`

---

## BP-E3 — canonical digest literal

- **neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `canonical_payload_digest`): `ensure_ascii=False` → `ensure_ascii=True`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-E -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_canonical_payload_digest_literal -q -p no:xdist`
- **raw red** (exit 1):
```
E       AssertionError: assert '18021e8fc824...fcec3faf2508d' == '2b185d042f72...f585fc4814bef'
```
- **restore:** `ensure_ascii=False`
- **raw green** (exit 0): `1 passed in 1.04s`

---

## BP-E4 — driver-free writer import guard

- **neutralization** (`plugins/superheroes/lib/model_registry.py`, module end): `import round_driver`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-E -m pytest plugins/superheroes/lib/tests/test_round_certification.py::test_writer_tests_run_with_no_driver -q -p no:xdist`
- **raw red** (exit 1):
```
AssertionError: forbidden driver module loaded: round_driver
```
- **restore:** removed `import round_driver` from `model_registry.py`
- **raw green** (exit 0): `1 passed in 0.44s`

---

## BP-E5 — resolved inputs signature pin

- **neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_build_resolved_inputs`): renamed parameter `seat` → `seat_spec` (body updated)
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-E -m pytest plugins/superheroes/lib/tests/test_round_driver_receipt_boundary.py::test_receipt_seat_model_is_the_runner_records_engine_model -q -p no:xdist`
- **raw red** (exit 1):
```
E       AssertionError: kwargs [...] do not match _build_resolved_inputs signature [...]
E         Extra items in the left set:
E         'seat'
E         Extra items in the right set:
E         'seat_spec'
```
- **restore:** parameter name `seat_spec` → `seat` (body reverted)
- **raw green** (exit 0): `1 passed in 2.93s`
