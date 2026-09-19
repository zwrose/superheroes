# layer2c receipt binding bite proofs (#1272 WO-A3)

## Guarded elements

| ID | Guarded element | Detector test |
|----|-----------------|---------------|
| F1 | `_fix_still_present_at_certified_head` | `test_bite_F1_fix_absent_detector` |
| F2 | `_finalize_fixed_disposition_receipts` verify gate | `test_bite_F2_verify_not_pass_detector` |
| F3 | `_staged_id_resolution_fault` | `test_bite_F3_staged_id_detector` |
| F4 | `_follow_up_shape_fault` | `test_bite_F4_follow_up_malformed_detector` |
| F6 | `_execution_evidence_satisfies_payload_proof` | `test_bite_F6_write_run_not_payload_bound` |

F5 (absent followUp recorded, writer refuses later) is unchanged — covered by
`test_L4_judgment_skip_without_follow_up_refuses_writer` in `test_disposition_ledger_1272.py`.

## F1 — fix absent at certified head

**Neutralization:** at the top of `_fix_still_present_at_certified_head`, insert `return None`.

**Red output (measured):**
```
FAILED ...test_bite_F1_fix_absent_detector
AssertionError: assert None == 'fixed-disposition-fix-absent-at-certified-head'
1 failed in 0.16s
```

**Restore:** remove the inserted `return None`.

**Green output (measured):**
```
.....                                                                    [100%]
5 passed in 0.20s
```

## F2 — final round verify not pass

**Neutralization:** in `_finalize_fixed_disposition_receipts`, comment out the block:
`if verify_result != "pass": return FIX_FINALIZATION_VERIFY_NOT_PASS_CAUSE`

**Red command:**
```bash
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woa3 -m pytest \
  plugins/superheroes/lib/tests/test_receipt_binding_1272.py::test_bite_F2_verify_not_pass_detector -q
```
**Red assertion:** `assert fault == "fixed-disposition-finalization-verify-not-pass"`

**Restore:** restore the verify gate block.

**Green command:** same — expect 1 passed.

## F3 — staged id unresolvable

**Neutralization:** in `_staged_id_resolution_fault`, replace the `finding is None` branch body with `return None`.

**Red command:**
```bash
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woa3 -m pytest \
  plugins/superheroes/lib/tests/test_receipt_binding_1272.py::test_bite_F3_staged_id_detector -q
```

**Restore:** restore the `maps to no entry` return.

**Green command:** same — expect 1 passed.

## F4 — malformed followUp at submit

**Neutralization:** in `_follow_up_shape_fault`, replace the `item` check with `return None`.

**Red command:**
```bash
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woa3 -m pytest \
  plugins/superheroes/lib/tests/test_receipt_binding_1272.py::test_bite_F4_follow_up_malformed_detector -q
```

**Restore:** restore the `item` check.

**Green command:** same — expect 1 passed.

## F6 — write-run stamp is execution-only, not payload-bound

**Neutralization:** make `_execution_evidence_satisfies_payload_proof` always `return True`.

**Red command:**
```bash
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woa3 -m pytest \
  plugins/superheroes/lib/tests/test_receipt_binding_1272.py::test_bite_F6_write_run_not_payload_bound -q
```

**Restore:** restore the `result_kind != session_contract.WRITE_RESULT_KIND` guard.

**Green command:** same — expect 1 passed.
