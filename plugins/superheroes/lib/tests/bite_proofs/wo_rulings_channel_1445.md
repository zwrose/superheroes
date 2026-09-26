# WO #1445 — rulings channel bite-proofs

| ID | Guarded element | Neutralization | Expected red |
| --- | --- | --- | --- |
| BP-1 | `_gate_guidance_entries` ruling-channel prepend | skip appending ruling rows to `ruling_channel` | `test_binding_ruling_rides_hashed_order_and_certifies` fails with `evidence-order-mismatch` on record-result |
| BP-2 | `_filter_excluded_discharged_fixes` oos-key skip | omit `oos_keys` exclusion loop | edge-3 / binding: finding B remains in fix batch |
| BP-3 | `_stage_findings` live out-of-scope re-apply | remove `_record_disposition` re-apply block | `test_edge3_restage_reapplies_out_of_scope` disposition assertion fails |
| BP-4 | `FIX_BATCH_SHA256` placeholder | constant `"0"*64` instead of file sha | `test_edge7_guidance_off_batch_no_supersede` or supersede attempt assertion fails |
| BP-5 | `ruling-critical-out-of-scope` refusal | delete critical check in `_cmd_rule_locked` | `test_rule_refusal_tokens[ruling-critical-out-of-scope]` fails |
| BP-6 | `ruling-attempt-recorded` refusal | delete attempt-results check | `test_rule_refusal_tokens[ruling-attempt-recorded]` fails |

Proofs run as single-node pytest per `rubric/bite-proof.md`; restore by inverse edit only.
