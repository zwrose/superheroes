# Work order A (#2137) bite-proof: a late ruling re-renders a fixer order nobody has picked up

**Provenance:** claude / sonnet (implementer, work order A), maker family claude. Production under proof: `plugins/superheroes/lib/round_driver.py` (`_cmd_rule_locked`, the reshape branch marked `# axis: a ruling on an undispatched, unpicked-up fixer order re-renders it at the next attempt`). Detector: `plugins/superheroes/lib/tests/test_late_ruling_rerender_2137.py::test_flagged_ruling_reshapes_unpicked_order_at_next_attempt`.

Declared guarded-element set (from the order): **one element**, the reshape branch (step 5 of the order). The fail-closed edges E1-E3 (no reshape) and E4 (render refusal) have their own tests in the same file but the order declares no neutralization for them, so this record claims no bite-proof for them.

## Reshape branch

- **guarded element:** `round_driver.py` `_cmd_rule_locked`, the reshape decision `reshape = decision["reshape"]` feeding the `if reshape:` branch (re-slice via `_reconcile_fixer_queue_after_rulings`, new attempt `max(K + 1, _next_dispatch_attempt(...))`, one `orders-emit` commit).
- **axis:** a ruling with `--fixer-not-dispatched` on an emitted fixer order with no pickup evidence re-slices the batch and emits a new order at attempt K+1; it does not leave the order as it was.

**neutralization** (one targeted edit, `plugins/superheroes/lib/round_driver.py`, made and reverted with the Edit tool):
```diff
-        reshape = decision["reshape"]
+        reshape = False
```

**raw red** (detector unedited; command `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-a -m pytest "plugins/superheroes/lib/tests/test_late_ruling_rerender_2137.py::test_flagged_ruling_reshapes_unpicked_order_at_next_attempt" -q -n auto`, exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_flagged_ruling_reshapes_unpicked_order_at_next_attempt __________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpJz9XQX/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/popen-gw0/test_flagged_ruling_reshapes_u0')

    def test_flagged_ruling_reshapes_unpicked_order_at_next_attempt(tmp_path):
        ...
        out = _rule(session_dir, _oos(tmp_path, row_a), fixer_not_dispatched=True)
        assert out.get("ok") is True, out
        fixer_order = out["fixerOrder"]
>       assert fixer_order["commitCheck"] in ("clean", "unreadable")
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'commitCheck'

plugins/superheroes/lib/tests/test_late_ruling_rerender_2137.py:96: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_late_ruling_rerender_2137.py::test_flagged_ruling_reshapes_unpicked_order_at_next_attempt
1 failed in 2.78s
pytest exit: 1
```
(The test body is elided with `...` for the lines before the failing assertion; the rest is verbatim, and the `tmp_path` line is the local pytest temp path.) Axis check: the red is on the reshape axis. With the decision forced to "not reshaped", the result carries the not-reshaped `fixerOrder` (no `commitCheck`, which only a reshape reports), so the very first assertion about the reshape fails; the later assertions (attempt K+1, the K+1 manifest, `next` returning K+1) are not reached.

**restore:** the inverse edit, `reshape = False` back to `reshape = decision["reshape"]`, made with the Edit tool. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

**restore receipt** (the restored lines, read back with grep after the inverse edit):
```
8570-        if decision_refusal is not None:
8571-            return decision_refusal
8572:        reshape = decision["reshape"]
8573-        commit_check = decision.get("commitCheck")
8574-        fixer_order = {"reshaped": reshape, "attempt": pending.get("attempt"),
```

**raw green** (same command and node, exit 0):
```
.                                                                        [100%]
1 passed in 2.63s
pytest exit: 0
```

Redaction: none needed; the only local path is the pytest temp directory.
