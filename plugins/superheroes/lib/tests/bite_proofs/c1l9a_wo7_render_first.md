# Bite-proof: the apply-fixes step renders its guidance before it writes any file

One guarded element, proven by one neutralization. Captures are the pytest output of the single test
node, unedited apart from the temporary-directory names; nothing in them is secret.

## G1 — the render-before-write order

**Guarded element:** `round_driver._apply_fixes_payload_fields`, the line
`guidance = _gate_guidance_block(_gate_guidance_entries(state, rnd))` placed above the
`_ensure_fix_batch_file` call.

**Axis:** a guidance render refusal leaves `fix-batch.json` and `loop-state.json` byte-identical.

**Detector:** `test_rulings_channel_1445.py::test_a_render_refusal_while_apply_fixes_is_pending_leaves_the_batch_file_and_state_untouched`.
The ruling file drops one batch row out of scope (which would rewrite the batch file) and gives guidance
the aggregate cap refuses.

**Neutralization:** the `_ensure_fix_batch_file` call moved back above the render:

```python
    fields = {"fixBatchPath": _ensure_fix_batch_file(session_dir, rnd, state)}
    guidance = _gate_guidance_block(_gate_guidance_entries(state, rnd))
```

**Raw red** (detector alone, `-q -p no:cacheprovider -n auto`):

```
F                                                                        [100%]
...
        with open(batch_path, "rb") as fh:
>           assert fh.read() == batch_bytes_before
E           assert b'[{"classifi..."CONFIRMED"}]' == b'[{"classifi..."CONFIRMED"}]'
E             
E             At index 440 diff: b']' != b','
E             Use -v to get more diff

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:431: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_a_render_refusal_while_apply_fixes_is_pending_leaves_the_batch_file_and_state_untouched
1 failed in 3.08s
```

(The elided lines are the test source echoed by pytest.)

**Restore:** the inverse edit, the render line moved back above the `_ensure_fix_batch_file` call.

**Restore receipt** (the restored lines read back from the file):

```python
    guidance = _gate_guidance_block(_gate_guidance_entries(state, rnd))
    fields = {"fixBatchPath": _ensure_fix_batch_file(session_dir, rnd, state)}
```

**Raw green** (same command after the restore):

```
.                                                                        [100%]
1 passed in 17.85s
```
