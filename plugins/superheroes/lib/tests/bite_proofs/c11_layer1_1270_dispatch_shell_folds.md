# C11 layer 1 (#1270) bite-proofs — the dispatch-shell folds

Ten guarded elements across four work orders. The five elements of the `build_readout` scrub
egress have their own record at `wo4_1270_readout_scrub_egress.md`; **all fifteen were re-run by
the orchestrator** at the build head, with the detector unedited, and every restore was by the
**inverse edit** (never `git checkout --`, `git restore`, `git reset`, or `git stash`). The red
captures below are the orchestrator's own re-runs, trimmed to the decisive lines; nothing in them
is redacted because none carries a secret, token, private URL, or PII.

Command shape for every run below:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-c11 -m pytest <node> -q -p no:randomly
```

---

## WO-1 — the exit-code chokepoint (three elements, one per command-line entry point)

**Axis, all three:** *refusal-vs-result — a refusal must never be readable as success by exit
code.* Each element is neutralized by making **that one entry point's** exit path return a
hard-coded `0` instead of calling `dispatch_outcome.exit_code(...)`.

### BP-1.1 — `engine_dispatch.main`'s refusal exit path

**Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, the single trailing exit):

```python
-    return dispatch_outcome.exit_code(classification)
+    return 0
```

**Node:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_allowlist_refuses_off_allowlist_review_cli`

**Raw red:**

```
E        +  where 0 = CompletedProcess(args=[... '"terminal": true, "reason": "unrunnable" ...]).returncode
plugins/superheroes/lib/tests/test_engine_dispatch.py:8517: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_allowlist_refuses_off_allowlist_review_cli
1 failed in 0.75s
```

**Restore:** inverse edit, back to `return dispatch_outcome.exit_code(classification)`.

**Restore receipt** — the restored lines, and `git status --porcelain` over the file returned
empty:

```python
            classification = dispatch_outcome.CLASSIFICATION_REFUSAL
        sys.stdout.write(json.dumps(res) + "\n")
    return dispatch_outcome.exit_code(classification)
```

**Raw green:** `1 passed in 0.67s`

### BP-1.2 — `dispatch_guard`'s refusal exit path

**Neutralization** (`plugins/superheroes/lib/dispatch_guard.py`, the allowlist-verdict branch of
`_cli_check`):

```python
-            return dispatch_outcome.exit_code(
-                dispatch_outcome.classify_payload(allowlist_verdict))
+            return 0
```

**Node:** `plugins/superheroes/lib/tests/test_dispatch_guard.py::test_cli_park_exits_1_and_names_allowlist`
(the subprocess form — it asserts the **process** exit status, not a function's return value).

**Raw red:**

```
E        +  where 0 = CompletedProcess(args=[...]).returncode
plugins/superheroes/lib/tests/test_dispatch_guard.py:162: AssertionError
FAILED plugins/superheroes/lib/tests/test_dispatch_guard.py::test_cli_park_exits_1_and_names_allowlist
1 failed in 0.12s
```

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `1 passed in 0.13s`

### BP-1.3 — `engine_adapter._cmd_build_argv`'s refusal exit path

**Neutralization** (`plugins/superheroes/lib/engine_adapter.py`, the seat-refusal branch):

```python
-        return dispatch_outcome.exit_code(dispatch_outcome.classify_payload(payload))
+        return 0
```

**Node:** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_cli_off_allowlist_refused`

**Raw red:**

```
E       assert 0 == 1
plugins/superheroes/lib/tests/test_engine_adapter.py:694: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_cli_off_allowlist_refused
1 failed in 0.38s
```

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `1 passed in 0.67s`

---

## WO-1b — the repaired forfeit fixture (one element)

WO-1's *"a terminal forfeit still exits 0"* test originally passed while proving nothing: its
fixture never produced a forfeit (`assert res["forfeited"] is True` failed). **That is a fixture
defect, and it was cured by fixing the fixture, not by relaxing the assertion.** This proof
exists to show the repaired test now discriminates.

**Guarded element:** `dispatch_outcome.classify_dispatch_result`'s treatment of a terminal
forfeit. **Axis:** *a forfeited run is a run that happened, not a refusal.*

**Neutralization** (`plugins/superheroes/lib/dispatch_outcome.py`):

```python
     if result.get("terminal") and result.get("reason") == REASON_UNRUNNABLE:
         return CLASSIFICATION_REFUSAL
+    if result.get("forfeited") is True:
+        return CLASSIFICATION_REFUSAL
     return CLASSIFICATION_RESULT
```

**Node:** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_dispatch_write_cli_terminal_forfeit_exits_0`

**Raw red** — and note the captured stdout, which is the evidence the fixture now mints a
**genuine** forfeit:

```
plugins/superheroes/lib/tests/test_engine_dispatch_write.py:2626: AssertionError
{"ok": false, "terminal": true, "reason": "forfeited",
 "detail": "worktree-dirtied-by-attempt", "attempts": 1, "forfeited": true, ...}
1 failed in 1.34s
```

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `1 passed in 0.68s`

---

## WO-2 — three of the four fail-closed residuals

Residual 3 (the private `_BUILD_ARGV_VENDORS` reach) births **no detector** — it relocates a name
to a public home — so it owes no proof, and none is claimed.

### BP-2.1 — the allowlist-raised refusal carries the guard's identity

**Guarded element:** `seat_bundle.resolve_entry`'s `allowlist-raised` refusal detail.
**Axis:** *diagnosability of a refusal* — the refusal direction was already correct; what was lost
was **which** failure produced it.

**Neutralization** (`plugins/superheroes/lib/seat_bundle.py`, inside the `except Exception as exc`
on `dispatch_allowlist.validate`):

```python
-            _allowlist_raised_detail(exc),
+            _ALLOWLIST_RAISED_LEAD,
```

**Node:** `plugins/superheroes/lib/tests/test_seat_bundle.py::test_allowlist_guard_raise_refused`

**Raw red:**

```
plugins/superheroes/lib/tests/test_seat_bundle.py:640: AssertionError
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_allowlist_guard_raise_refused
1 failed in 0.21s
```

(line 640 is `assert "RuntimeError" in resolved["detail"]` — the axis line, not the
`ok is False` / `entryReason` lines above it, which still pass under the neutralization. The
refusal never stopped refusing; only its diagnosis went missing.)

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `1 passed in 0.17s`

### BP-2.2 — `effective_ttl` fails closed on a non-dict receipt

**Guarded element:** `liveness_cache.effective_ttl`'s non-dict branch.
**Axis:** *fail-closed direction on a corrupt receipt* — the least trustworthy input must not get
the longest freshness window.

**Neutralization** (`plugins/superheroes/lib/liveness_cache.py`):

```python
     if not isinstance(receipt, dict):
-        return 0
+        return configured
```

**Node:** `plugins/superheroes/lib/tests/test_liveness_cache.py::test_effective_ttl_non_dict_is_zero`
(parametrized over `None`, a string, a list, an int — four cases, all four red)

**Raw red:**

```
FAILED plugins/superheroes/lib/tests/test_liveness_cache.py::test_effective_ttl_non_dict_is_zero[None]
FAILED plugins/superheroes/lib/tests/test_liveness_cache.py::test_effective_ttl_non_dict_is_zero[not-a-receipt]
FAILED plugins/superheroes/lib/tests/test_liveness_cache.py::test_effective_ttl_non_dict_is_zero[receipt2]
FAILED plugins/superheroes/lib/tests/test_liveness_cache.py::test_effective_ttl_non_dict_is_zero[42]
4 failed in 0.18s
```

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `4 passed in 0.12s`

### BP-2.3 — the canary plan has a reader

**Guarded element:** `round_driver._canary_dims_for_status`'s use of `byDim`.
**Axis:** *the planned per-dimension schedule has a reader* — `canary_liveness` computed a complete
per-dimension plan that its only production caller never read.

**Neutralization** (`plugins/superheroes/lib/round_driver.py`) — drop the `byDim` branch entirely,
so the caller re-derives from `byVendor` as it did before:

```python
-    if by_dim:
-        from_dim = {
-            dim for dim, st in by_dim.items()
-            if isinstance(dim, str) and st == status
-        }
-        return sorted(from_dim | set(vendor_dims))
     return sorted(set(vendor_dims))
```

**Node:** `plugins/superheroes/lib/tests/test_round_driver.py::test_canary_dims_for_status_reads_by_dim_when_present`

**Raw red:**

```
plugins/superheroes/lib/tests/test_round_driver.py:6587: AssertionError
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_canary_dims_for_status_reads_by_dim_when_present
1 failed in 0.74s
```

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `1 passed` (run together with BP-5.1's node: `1 failed, 1 passed in 0.74s`,
the failure being BP-5.1's own red below).

---

## WO-3 — the marker chokepoint's `detail`, one element per verb

**Axis, both:** *the guard's own message — field, marker, accepted set — reaches `detail` on a live
dispatch*, instead of the bare exception class name `internal-UndeclaredSourceMarker`.

Parts A, C, D and E of WO-3 birth no detector — A changes a recorded provenance value, and C/D/E
are prose and a generator — so they owe no proof and none is claimed.

### BP-3.1 — `dispatch-review`

**Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`): delete the
`except resolved_inputs_vocab.UndeclaredSourceMarker` handler on the **live review path**
(`_dispatch_review_impl`), so the generic `except Exception` catches it and produces the old
`internal-<ClassName>` detail:

```python
-    except resolved_inputs_vocab.UndeclaredSourceMarker as exc:
-        return _entry_refusal_for_undeclared_source_marker(
-            exc,
-            run_dir=run_dir or run_dir_real or "",
-            mode=resolved_mode["mode"],
-            repo_root=repo_detail,
-            engine=engine,
-            run_kind=RUN_KIND_REVIEW,
-        )
```

**Node:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_review_undeclared_marker_detail_surfaces_guard_message`

**Raw red:**

```
plugins/superheroes/lib/tests/test_engine_dispatch.py:9839: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_review_undeclared_marker_detail_surfaces_guard_message
1 failed in 0.85s
```

**Restore:** inverse edit — the handler put back verbatim above the generic
`except Exception as exc:`. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green:** `1 passed in 0.90s`

### BP-3.2 — `dispatch-write`

**Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`): the same deletion on the write
verb's wrapper:

```python
-    except resolved_inputs_vocab.UndeclaredSourceMarker as exc:
-        return _entry_refusal_for_undeclared_source_marker(
-            exc,
-            run_dir=run_dir,
-            run_kind=RUN_KIND_WRITE,
-        )
```

**Node:** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_dispatch_write_undeclared_marker_detail_surfaces_guard_message`

**Raw red:**

```
plugins/superheroes/lib/tests/test_engine_dispatch_write.py:2717: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_dispatch_write_undeclared_marker_detail_surfaces_guard_message
1 failed in 0.86s
```

**Restore:** inverse edit. **Restore receipt:** a whole-tree `git status --porcelain` returned
empty after this restore — i.e. every neutralization in this record is undone. **Raw green:**
`1 passed in 0.53s`

---

## WO-5 — the canary union branch (one element)

The other six WO-5 items — a docstring, a dead-function deletion, a de-duplicated refusal message,
a sentinel `repr`, three test-quality cleanups, and the restoration of two subprocess tests —
birth **no detector**; the declared guarded-element set for them is **empty, with reason**, and no
proof is claimed for any of them.

**Guarded element:** `round_driver._canary_dims_for_status`'s union branch.
**Axis:** *the result is never a strict subset of the vendor derivation* — a gate must not silently
drop a dimension the vendor plan names.

**Neutralization** (`plugins/superheroes/lib/round_driver.py`) — make a non-empty `byDim`
exclusive again, so it can remove a vendor-named dimension:

```python
-        return sorted(from_dim | set(vendor_dims))
+        return sorted(from_dim)
```

**Node:** `plugins/superheroes/lib/tests/test_round_driver.py::test_canary_dims_for_status_unions_vendor_when_by_dim_omits_dimension`

**Raw red:**

```
plugins/superheroes/lib/tests/test_round_driver.py:6600: AssertionError
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_canary_dims_for_status_unions_vendor_when_by_dim_omits_dimension
1 failed, 1 passed in 0.74s
```

**Restore:** inverse edit. **Restore receipt:** `git status --porcelain` over the file returned
empty. **Raw green** (the three canary nodes together):

```
...                                                                      [100%]
3 passed in 0.88s
```

---

## WO-6 — `dispatch-poll` / `dispatch-abandon` refusal exit paths (two elements)

**Axis, both:** *a poll or abandon that refused must not read as success by exit code.* Each element
is neutralized by restoring the hardcoded `CLASSIFICATION_RESULT` for **that one verb** in
`main()`, discarding the classification returned by the internal impl.

### BP-6.1 — `dispatch_poll`'s refusal exit path

**Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `main`'s `dispatch-poll` branch):

```python
         elif args.cmd == "dispatch-poll":
             res, classification = _dispatch_poll_impl(args.run_dir)
+            classification = dispatch_outcome.CLASSIFICATION_RESULT
```

**Node:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_poll_cli_run_dir_symlink_refused_exits_1`

**Raw red:**

```
E       assert 0 == 1
plugins/superheroes/lib/tests/test_engine_dispatch.py:8578: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_poll_cli_run_dir_symlink_refused_exits_1
1 failed in 0.60s
```

**Restore:** inverse edit — delete the `classification = dispatch_outcome.CLASSIFICATION_RESULT`
line. **Restore receipt:**

```python
        elif args.cmd == "dispatch-poll":
            res, classification = _dispatch_poll_impl(args.run_dir)
```

**Raw green:** `1 passed in 0.52s`

### BP-6.2 — `dispatch_abandon`'s refusal exit path

**Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `main`'s `dispatch-abandon`
branch):

```python
         elif args.cmd == "dispatch-abandon":
             res, classification = _dispatch_abandon_impl(args.run_dir)
+            classification = dispatch_outcome.CLASSIFICATION_RESULT
```

**Node:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_abandon_cli_run_dir_symlink_refused_exits_1`

**Raw red:**

```
E       assert 0 == 1
plugins/superheroes/lib/tests/test_engine_dispatch.py:8590: AssertionError
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_dispatch_abandon_cli_run_dir_symlink_refused_exits_1
1 failed in 0.67s
```

**Restore:** inverse edit — delete the `classification = dispatch_outcome.CLASSIFICATION_RESULT`
line. **Restore receipt:**

```python
        elif args.cmd == "dispatch-abandon":
            res, classification = _dispatch_abandon_impl(args.run_dir)
```

**Raw green:** `1 passed in 0.53s`
