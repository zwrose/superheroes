# WO-A (#1419) bite-proof — rulings channel

| ID | Guarded element | Axis | Detector |
| --- | --- | --- | --- |
| BP-1419-1 | `_filter_excluded_discharged_fixes` out-of-scope ruling exclusion | ruled key stays out of `_fixBatch` | `test_t2_out_of_scope_ruling_excludes_fix_batch_row` |
| BP-1419-2 | `round_orders.render_order` rulings block | hashed order carries declared ruling text | `test_t3_rulings_block_in_hashed_fixer_order` |
| BP-1419-3 | `_ensure_raised_row_for_ruling_target` | audit new issue without ledger row certifies after rule | `test_t4_audit_new_issue_certifies_after_ruling` |

**BP-1419-1 neutralization:** delete the `oos_keys` filter loop body in `_filter_excluded_discharged_fixes`.

**BP-1419-2 neutralization:** skip inserting `_format_rulings_block` in `render_order`.

**BP-1419-3 neutralization:** make `_ensure_raised_row_for_ruling_target` a no-op.
