# C14 layer 3b-3 WO-A — fail receipts

Advisor-ordered fail receipts for a test-only layer; not bite-proofs.

## R-A1a — test_receipt_seat_model_is_the_runner_records_engine_model
- **axis:** receipt seat model comes from the runner's execution record, not the seat map pin.
- **broken subject** (`round_certification.py`, `_collect_seats`): `model = engine_model` → `model = None  # fail-receipt R-A1a`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-A -m pytest plugins/superheroes/lib/tests/test_round_driver_receipt_boundary.py::test_receipt_seat_model_is_the_runner_records_engine_model -q -p no:xdist`
- **raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_receipt_seat_model_is_the_runner_records_engine_model __________

    def test_receipt_seat_model_is_the_runner_records_engine_model(tmp_path):
        ...
        row = next(item for item in receipt["seats"] if item["seat"] == runner_seat)
>       assert row["model"] == "gpt-5.6-sol"
E       AssertionError: assert None == 'gpt-5.6-sol'
```
- **restore:** `model = None  # fail-receipt R-A1a` → `model = engine_model`
- **raw green** (exit 0): `1 passed in 8.06s`

## R-A1b — test_receipt_seat_model_is_the_runner_records_engine_model
- **axis:** receipt seat model comes from the runner's execution record, not the seat map pin.
- **broken subject** (`engine_dispatch.py`, `run_execution_record`): `record["engineModel"] = engine_model` → `pass  # fail-receipt R-A1b`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-A -m pytest plugins/superheroes/lib/tests/test_round_driver_receipt_boundary.py::test_receipt_seat_model_is_the_runner_records_engine_model -q -p no:xdist`
- **raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_receipt_seat_model_is_the_runner_records_engine_model __________

        assert recorded_row[session_contract.SEAT_TRANSPORT_KEY] == session_contract.SEAT_TRANSPORT_RUNNER
>       assert recorded_row["executionEvidence"]["engineModel"] == "gpt-5.6-sol"
E       KeyError: 'engineModel'
```
- **restore:** `pass  # fail-receipt R-A1b` → `record["engineModel"] = engine_model`
- **raw green** (exit 0): `1 passed in 8.61s`

## R-A2 — test_receipt_seat_model_none_for_hand_landed_record_carrying_a_model
- **axis:** hand-landed transport suppresses receipt model even when journal evidence carries engineModel.
- **broken subject** (`round_certification.py`, `_collect_seats`): `if event.get(session_contract.SEAT_TRANSPORT_KEY) == session_contract.SEAT_TRANSPORT_RUNNER:` → `if True:  # fail-receipt R-A2`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-A -m pytest plugins/superheroes/lib/tests/test_round_driver_receipt_boundary.py::test_receipt_seat_model_none_for_hand_landed_record_carrying_a_model -q -p no:xdist`
- **raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_receipt_seat_model_none_for_hand_landed_record_carrying_a_model _____

        row = next(item for item in receipt["seats"] if item["seat"] == seat)
>       assert row["model"] is None
E       AssertionError: assert 'gpt-6-astra' is None
```
- **restore:** `if True:  # fail-receipt R-A2` → `if event.get(session_contract.SEAT_TRANSPORT_KEY) == session_contract.SEAT_TRANSPORT_RUNNER:`
- **raw green** (exit 0): `1 passed in 6.87s`

## R-A3 — test_writer_tests_run_with_no_driver
- **axis:** writer-side tests and fixtures never import or name the round driver at any depth.
- **broken subject** (`round_certification_fixtures.py`, `write_session`): added `import round_driver  # fail-receipt R-A3` as first body line
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-A -m pytest plugins/superheroes/lib/tests/test_round_certification.py::test_writer_tests_run_with_no_driver -q -p no:xdist`
- **raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_writer_tests_run_with_no_driver _____________________

>           assert not violations, "forbidden driver reference in %s: %s" % (path, violations)
E           AssertionError: forbidden driver reference in .../round_certification_fixtures.py: ['round_driver']
```
- **restore:** removed `import round_driver  # fail-receipt R-A3` from `write_session`
- **raw green** (exit 0): `1 passed in 1.10s`
