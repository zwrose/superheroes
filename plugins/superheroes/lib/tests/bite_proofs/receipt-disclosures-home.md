# Bite-proof record — WO-P1-A (`receipt_disclosures` / `record_paths` one-home identity test)

Contract: `rubric/bite-proof.md`. Proof ran with the **detector unedited**; neutralization was a
targeted, reversible local re-definition of `declared_disclosures` in `round_certification.py`,
reverted by exact inverse before the green half.

## Detector — `test_receipt_disclosures_exports_match_driver_and_writer`

**Guarded element.** `plugins/superheroes/lib/tests/test_receipt_disclosures_home.py` —
identity assertion over `receipt_disclosures.__all__` for `round_driver` and `round_certification`.
**Axis.** A second definition of an exported name in the writer breaks object-identity with the
leaf module while the driver still imports the shared home.

**Neutralization** (appended after the import aliases in `round_certification.py`):

```python
def declared_disclosures(entry):
    return {}
```

**Raw red** — `PYTEST_EXIT=1`:

```
F.                                                                       [100%]
=================================== FAILURES ===================================
___________ test_receipt_disclosures_exports_match_driver_and_writer ___________

    def test_receipt_disclosures_exports_match_driver_and_writer():
        for name in receipt_disclosures.__all__:
            assert getattr(round_driver, name) is getattr(receipt_disclosures, name), name
            if hasattr(round_certification, name):
>               assert getattr(round_certification, name) is getattr(receipt_disclosures, name), name
E               AssertionError: declared_disclosures
E               assert <function declared_disclosures at 0x108c198b0> is <function declared_disclosures at 0x108baf940>
E                +  where <function declared_disclosures at 0x108c198b0> = getattr(round_certification, 'declared_disclosures')
E                +  and   <function declared_disclosures at 0x108baf940> = getattr(receipt_disclosures, 'declared_disclosures')

plugins/superheroes/lib/tests/test_receipt_disclosures_home.py:13: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_receipt_disclosures_home.py::test_receipt_disclosures_exports_match_driver_and_writer
1 failed, 1 passed in 0.13s
```

**Restore.** Deleted the planted `def declared_disclosures(entry): return {}` block; restored lines:

```python
_declared_disclosures = declared_disclosures


def _certification_shape(state, seats):
```

**Restore receipt.** `git diff plugins/superheroes/lib/round_certification.py` shows only the WO-P1-A
refactor hunks (imports + deleted mirror vocabulary); the planted function is absent.

**Raw green** — `PYTEST_EXIT=0`:

```
..                                                                       [100%]
2 passed in 0.12s
```
