# C1-L9a WO-4b — bite-proof record

One detector added: `test_assemble_dispatch_evidence_write_run_is_refused_for_every_phase`
(`plugins/superheroes/lib/tests/test_round_driver_integration.py`). It replaces
`test_assemble_dispatch_evidence_write_run_fixer_envelope`, which asserted that a write run's evidence
assembled for the fixer phase; that phase is gone, so the test now asserts the absence: no phase admits
a write run's execution-only evidence. Every other test of this order keeps its assertions on the
surviving behaviour, or is deleted with its subject.

## Guarded element: `session_contract.execution_only_admissible_for_phase` as read by `round_driver._assemble_dispatch_evidence`

- **Axis:** a write run's evidence is refused `evidence-run-kind-mismatch` for every phase in `round_phases.ALL_PHASES`.
- **Neutralization** (a targeted edit inside the test file only, a monkeypatch added as the first body line,
  with `monkeypatch` added to the signature):
  `monkeypatch.setattr(session_contract, "execution_only_admissible_for_phase", lambda phase: True)  # NEUTRALIZED`
- **Raw red** (the one node, run alone):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_assemble_dispatch_evidence_write_run_is_refused_for_every_phase _____
/home/user/wt-2213-wo4b/plugins/superheroes/lib/tests/test_round_driver_integration.py:1362: in test_assemble_dispatch_evidence_write_run_is_refused_for_every_phase
    assert assembled is None, phase
E   AssertionError: dispatch-panel
E   assert {'orderSha256': '170eb12f9992beba727770fe61479756f039fc3c438bee5f5cbec11b0742ce73', 'payload': {'fixes': [{'file': 'sr...3ab654c84c8f2ec97b01d914d', ...}, 'envelopeSha256': '415d77842026cf09e6a9fd81b9a243c465ffcf6cf797038a1d0e6c21a35188e6'} is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_integration.py::test_assemble_dispatch_evidence_write_run_is_refused_for_every_phase
1 failed in 0.55s
```

- **Restore:** the inverse edit: the `# NEUTRALIZED` line removed and `monkeypatch` removed from the signature.
- **Restore receipt** (the restored lines quoted back from the file; `grep -c NEUTRALIZED` over the file printed `0`):

```
def test_assemble_dispatch_evidence_write_run_is_refused_for_every_phase(tmp_path):
    # axis: no phase admits a write run's execution-only evidence — the build session writes its own fixes
    order_path = str(tmp_path / "fixer-order.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
```

- **Raw green** (after the restore):

```
.                                                                        [100%]
1 passed in 0.50s
```

Redaction: none needed; the hashes above are test-fixture digests, not secrets.
