# Bite-proof: review session 1 fixes on the apply-fixes step

The three guarded elements were declared in the work order before the work began. The G1 and G2 reds were produced by the implementer. The G2 green and both G3 runs were produced by the build session itself, because the implementer stopped on a refused command before running them. Captures are pytest output; long lines are cut where marked. Nothing in them is secret.

## G1: a malformed binding is refused before any lookup

- **Guarded element:** `round_driver._apply_fixes_commit_fault`, the check `if malformed is not None: return "%s:%d" % (FIX_BINDING_MALFORMED, malformed), []`. It is the function's first check, fed by `_malformed_binding_index`.
- **Axis:** a `fixes` entry with a `finding` or `commit` key that is not a non-empty string is refused `fix-binding-malformed:<index>`, and never reaches the dict lookup.
- **Detector:** `test_apply_fixes_c1l9a.py::test_a_fixes_object_with_a_malformed_binding_is_refused_with_its_index`, six parametrized cases.
- **Neutralization:** `if malformed is not None:` became `if False and malformed is not None:`.
- **Raw red (implementer).** With the six cases under `-n auto`: `6 failed in 14.36s`. Each case got `fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:no-binding` instead of `fix-binding-malformed:1`. The harness truncated about 7,900 characters of that output. The list-valued case run alone with `-n 0` gave:

  ```
  >       if entry.get("finding") not in names:
  E       TypeError: unhashable type: 'list'
  FAILED ...test_a_fixes_object_with_a_malformed_binding_is_refused_with_its_index[<lambda>-1_0]
  1 failed in 3.59s
  ```

- **Restore:** the inverse edit.
- **Restore receipt:** `5534: if malformed is not None:`.
- **Raw green (implementer):** `6 passed in 8.59s`.

## G2: the verified binding keeps the resolved commit

- **Guarded element:** `round_driver._apply_fixes_commit_fault`, the line `commits.append({"finding": key, "commit": resolved if _nonempty_str(resolved) else chosen})`.
- **Axis:** `rounds[N].fix.commits` holds git's full SHA, never the expression the report gave.
- **Detector:** `test_apply_fixes_c1l9a.py::test_a_binding_given_as_head_records_the_full_resolved_sha`.
- **Neutralization:** `commits.append({"finding": key, "commit": chosen})`.
- **Raw red (implementer):**

  ```
  At index 0 diff: {'commit': 'HEAD', 'finding': '...'} != {'finding': '...', 'commit': 'c5d14b83...'}
  1 failed in 3.61s
  ```

- **Restore:** the inverse edit.
- **Restore receipt (build session):** `grep` shows `5580:        commits.append({"finding": key, "commit": resolved if _nonempty_str(resolved) else chosen})`.
- **Raw green (build session):** `1 passed in 3.06s`.

## G3: a ruling while the step is pending rewrites the batch file, and the test reads the bytes the ruling left

- **Guarded element:** `round_driver._cmd_rule_locked`, the block `if (state.get("step") == P_APPLY_FIXES and not state.get("terminal") and isinstance(pending_now, dict) and pending_now.get("phase") == P_APPLY_FIXES):`, which calls `_apply_fixes_payload_fields` to rewrite the step's files.
- **Axis:** after an accepted ruling on a batch row, `fix-batch.json` no longer holds the ruled-out finding before anything else rewrites it.
- **Detector:** `test_rulings_channel_1445.py::test_a_ruling_on_a_batch_row_while_apply_fixes_is_pending_rewrites_the_batch_file`, which now asserts on the bytes read straight after `rule` returns.
- **Neutralization (build session):** the condition became `if (False and state.get("step") == P_APPLY_FIXES and ...`.
- **Raw red (build session):**

  ```
  >       assert key_b.encode("utf-8") not in left_by_rule
  E       assert b'src/f00.py::bounds b@L3' not in b'[{"classification":"mechanical", ... (cut)
  test_rulings_channel_1445.py:334: AssertionError
  1 failed in 10.89s
  ```

- **Restore:** the inverse edit.
- **Restore receipt:** `git status --porcelain plugins` was empty after the restore; the change had been committed before the probe.
- **Raw green (build session):** `1 passed in 61.56s (0:01:01)`.
