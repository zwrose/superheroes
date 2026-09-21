# Bite-proof record — C13 layer 2i (session mobility: `relocate` / `re-emit`)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the production line(s) named, and
reverted by its exact inverse (quoted). Detector node prefix (unless stated otherwise):
`plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::`.

| # | Guarded element | Axis |
|---|---|---|
| R1 | `_cmd_relocate_locked` — state-unreadable check | missing `loop-state.json` refuses relocate |
| R2 | `_cmd_relocate_locked` — terminal-session check | a terminal session refuses relocate |
| R3 | `_cmd_relocate_locked` — target-not-toplevel (realpath equality) | target must be a git toplevel |
| R4 | `_cmd_relocate_locked` — same-checkout check | relocating to the same root+session is refused |
| R5 | `_cmd_relocate_locked` — repo-unverifiable check | missing `config.baseRepo` refuses relocate |
| R6 | `_cmd_relocate_locked` — repo-mismatch check | live origin must match recorded `baseRepo` |
| R7 | `_cmd_relocate_locked` — base-mismatch (`meta_base != cfg_base`) | meta/config `baseRef` must agree |
| R8 | `_relocate_recorded_head` — `meta_has != cfg_has` | fix-fold head presence must agree between meta and config |
| R9 | `_cmd_relocate_locked` — HEAD-vs-recorded compare | target HEAD must equal the recorded head |
| R10 | `_cmd_relocate_locked` — records-path-bound check | `recordsPath` inside the old repo root refuses relocate |
| R11 | `cmd_relocate` — the session lock | a locked session refuses relocate |
| R12 | `_cmd_relocate_locked` — `state.config.repoRoot` rewrite | config repoRoot is rewritten to the new checkout |
| R13 | `_cmd_relocate_locked` — `meta.sessionDir` rewrite | meta sessionDir is rewritten to the new location |
| R14 | `_cmd_relocate_locked` — verify `landingPath` re-derivation | a pending verify's landing path is re-derived under the new session dir |
| R15 | `_cmd_relocate_locked` — rewritten-only mutation | every meta/state mutation is declared in `rewritten` |
| R16 | `_retire_relocate_marker` — ownership check | a marker not owned by this session is left alone |
| E1 | `_cmd_re_emit_locked` — `relocation is None` (not-stale) check | re-emit refuses when no relocation postdates the last emit |
| E2 | `_cmd_re_emit_locked` — head-moved compare | re-emit refuses when the live head moved off the anchor head |
| E3 | `_re_emit_attempt_result_names` — landing-file branch (`os.listdir` needle) | a landed result file blocks re-emit |
| E4 | `_re_emit_attempt_result_names` — journal branch (`recorded` row loop) | a recorded journal row blocks re-emit |
| E5 | `_cmd_re_emit_locked` — `not isinstance(pending, dict)` check | a missing pending order refuses re-emit |
| E6 | `_cmd_re_emit_locked` — no-anchor check | a missing/unauthenticated anchor refuses re-emit |
| E7 | `_cmd_re_emit_locked` — git-status branch (head-unresolved) | an unresolvable HEAD refuses re-emit |
| E8 | `_cmd_re_emit_locked` — attempt allocation floor (`max(…, old_attempt + 1)`) | the new attempt never collides with/regresses below the old one |
| E9 | `_cmd_re_emit_locked` — `extra_journal_entries=[superseded_row]` | the superseded row is actually journalled at re-emit |
| E10 | `round_certification._journal_open_seats` — superseded filter | a superseded attempt's seats do not count as still-open |
| E11 | `round_certification._journal_open_seats` — `orders-emitted` cmd tuple | `re-emit`'s own emission opens certification seats |
| E12 | `cmd_re_emit` — the session lock | a locked session refuses re-emit |

---

## R1 — state-unreadable check

**Neutralization** (`round_driver.py`, `_cmd_relocate_locked`):

```python
-    if not ok_state or loaded is None:
+    if False and (not ok_state or loaded is None):
```

**Detector:** `test_relocate_refusal_tokens[relocate-session-unreadable-unreadable]`

**Raw red:**

```
>       rc, out = _relocate(session_dir, target, capsys)
...
    def _cmd_relocate_locked(session_dir, target_root, by):
        ...
        state = loaded
>       if state.get("terminal"):
E       AttributeError: 'NoneType' object has no attribute 'get'
plugins/superheroes/lib/round_driver.py:6207: AttributeError
1 failed in 11.35s
```

**Restore:** reverted the `if False and (...)` wrap.

**Restore receipt (quoted lines):**

```python
    if not ok_state or loaded is None:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 9.61s
```

---

## R2 — terminal-session check

**Neutralization:**

```python
-    if state.get("terminal"):
+    if False and (state.get("terminal")):
```

**Detector:** `test_relocate_refusal_tokens[relocate-session-terminal-terminal]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 9.99s
```

**Restore receipt (quoted lines):**

```python
    if state.get("terminal"):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 9.40s
```

---

## R3 — target-not-toplevel (realpath equality)

**Neutralization:**

```python
-    if target_toplevel != os.path.realpath(target_root):
+    if False and (target_toplevel != os.path.realpath(target_root)):
```

**Detector:** `test_relocate_refusal_tokens[relocate-target-not-toplevel-not_toplevel]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 10.70s
```

**Restore receipt (quoted lines):**

```python
    if target_toplevel != os.path.realpath(target_root):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 9.55s
```

---

## R4 — same-checkout check

**Neutralization:**

```python
-    if (old_root_rp is not None and target_toplevel == old_root_rp
+    if False and (old_root_rp is not None and target_toplevel == old_root_rp
            and os.path.realpath(session_dir) == old_session_rp):
```

**Detector:** `test_relocate_refusal_tokens[relocate-same-checkout-same_checkout]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 10.12s
```

**Restore receipt (quoted lines):**

```python
    if (old_root_rp is not None and target_toplevel == old_root_rp
            and os.path.realpath(session_dir) == old_session_rp):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 9.63s
```

---

## R5 — repo-unverifiable check

**Neutralization:**

```python
-    if not isinstance(base_repo, str) or not base_repo:
+    if False and (not isinstance(base_repo, str) or not base_repo):
```

**Detector:** `test_relocate_refusal_tokens[relocate-repo-unverifiable-repo_unverifiable]`

**Raw red:**

```
>       if live_origin is None or live_origin.casefold() != base_repo.casefold():
E       AttributeError: 'NoneType' object has no attribute 'casefold'
plugins/superheroes/lib/round_driver.py:6232: AttributeError
1 failed in 10.80s
```

**Restore receipt (quoted lines):**

```python
    if not isinstance(base_repo, str) or not base_repo:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 10.29s
```

---

## R6 — repo-mismatch check

**Neutralization:**

```python
-    if live_origin is None or live_origin.casefold() != base_repo.casefold():
+    if False and (live_origin is None or live_origin.casefold() != base_repo.casefold()):
```

**Detector:** `test_relocate_refusal_tokens[relocate-repo-mismatch-repo_mismatch]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 9.53s
```

**Restore receipt (quoted lines):**

```python
    if live_origin is None or live_origin.casefold() != base_repo.casefold():
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 10.73s
```

---

## R7 — base-mismatch (`meta_base != cfg_base`)

**Neutralization:**

```python
-    if meta_base != cfg_base:
+    if False and (meta_base != cfg_base):
```

**Detector:** `test_relocate_refusal_tokens[relocate-base-mismatch-base_mismatch]`

The parametrized `base_mismatch` case is reached through **this** branch, confirmed by the red
below (the test's own `meta_base != cfg_base` setup — it edits `meta.baseRef` only, leaving
`config.baseRef` at the original pin).

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 12.88s
```

**Restore receipt (quoted lines):**

```python
    if meta_base != cfg_base:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 11.57s
```

---

## R8 — `_relocate_recorded_head`, `meta_has != cfg_has`

**Neutralization:**

```python
-    if meta_has != cfg_has:
+    if False and (meta_has != cfg_has):
```

**Detector:** `test_relocate_refusal_tokens[relocate-head-ambiguous-head_ambiguous]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 9.97s
```

**Restore receipt (quoted lines):**

```python
    if meta_has != cfg_has:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 9.87s
```

---

## R9 — HEAD-vs-recorded compare

**Neutralization:**

```python
-    if head_res.out.lower() != recorded_head.lower():
+    if False and (head_res.out.lower() != recorded_head.lower()):
```

**Detectors:** `test_relocate_refusal_tokens[relocate-head-mismatch-head_mismatch]` and
`test_relocate_mid_fix_head_mismatch` (run together, both red under the same neutralization).

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
FAILED ...test_relocate_refusal_tokens[relocate-head-mismatch-head_mismatch]

>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:339: AssertionError
FAILED ...test_relocate_mid_fix_head_mismatch
2 failed in 20.37s
```

**Restore receipt (quoted lines):**

```python
    if head_res.out.lower() != recorded_head.lower():
```

**Raw green:**

```
..                                                                       [100%]
2 passed in 16.22s
```

---

## R10 — records-path-bound check

**Neutralization:**

```python
-        if _relocate_path_inside(records_path, old_root_rp):
+        if False and (_relocate_path_inside(records_path, old_root_rp)):
```

**Detector:** `test_relocate_refusal_tokens[relocate-records-path-bound-records_bound]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 6.68s
```

**Restore receipt (quoted lines):**

```python
        if _relocate_path_inside(records_path, old_root_rp):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 4.97s
```

---

## R11 — the session lock (`cmd_relocate`)

Per the order's guidance, the `except round_records.SessionLockHeld` handler in `cmd_relocate`
itself is off-limits as a neutralization target (disabling the handler proves nothing about the
lock). The narrowest production neutralization inside `cmd_relocate` is the lock acquisition
itself — swap `round_records.session_lock(session_dir)` for a no-op context manager
(`open(os.devnull)`, a stdlib file object that already supports the `with` protocol, so the lock
is never consulted and a held lock can no longer refuse).

**Neutralization:**

```python
 def cmd_relocate(session_dir, target_root, by):
     """Relocate a parked review session to a different checkout at the same head and base."""
     try:
-        with round_records.session_lock(session_dir):
+        with open(os.devnull):  # was: round_records.session_lock(session_dir)
             refusal = _commit_recover_or_refuse(session_dir, "relocate")
```

**Detector:** `test_relocate_refusal_tokens[relocate-locked-locked]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:323: AssertionError
1 failed in 3.60s
```

**Restore receipt (quoted lines):**

```python
    try:
        with round_records.session_lock(session_dir):
            refusal = _commit_recover_or_refuse(session_dir, "relocate")
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.21s
```

---

## R12 — `state.config.repoRoot` rewrite

**Neutralization:**

```python
-    if "repoRoot" in new_cfg:
+    if False and ("repoRoot" in new_cfg):
         new_cfg["repoRoot"] = target_toplevel
         new_state["config"] = new_cfg
         rewritten.append("state.config.repoRoot")
```

**Detectors:** `test_relocate_positive_and_next_from_new_checkout` and
`test_relocate_invariant_no_old_paths_survive`

**Raw red:**

```
E       AssertionError: assert '/private/var...d_nex0/repo_a' == '/private/var...d_nex0/repo_b'
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:209: AssertionError
FAILED ...test_relocate_positive_and_next_from_new_checkout

E       Failed: old path survived at state.config.repoRoot: .../repo_a
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:232: Failed
FAILED ...test_relocate_invariant_no_old_paths_survive
2 failed in 5.29s
```

**Restore receipt (quoted lines):**

```python
    if "repoRoot" in new_cfg:
        new_cfg["repoRoot"] = target_toplevel
        new_state["config"] = new_cfg
        rewritten.append("state.config.repoRoot")
```

**Raw green:**

```
..                                                                       [100%]
2 passed in 4.51s
```

---

## R13 — `meta.sessionDir` rewrite

**Neutralization:**

```python
-    if had_session_dir:
+    if False and (had_session_dir):
         new_meta["sessionDir"] = os.path.realpath(session_dir)
         rewritten.append("meta.sessionDir")
```

**Detector:** `test_relocate_invariant_moved_session_dir`

**Raw red:**

```
>       assert meta2["sessionDir"] == current_s2
E       AssertionError: assert '/private/var...ved_0/session' == '/private/var...ed_0/session2'
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:528: AssertionError
1 failed in 1.96s
```

**Restore receipt (quoted lines):**

```python
    if had_session_dir:
        new_meta["sessionDir"] = os.path.realpath(session_dir)
        rewritten.append("meta.sessionDir")
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.78s
```

---

## R14 — verify `landingPath` re-derivation

**Neutralization:**

```python
-    if isinstance(verify, dict) and "landingPath" in verify:
+    if False and (isinstance(verify, dict) and "landingPath" in verify):
```

**Detector:** `test_relocate_pending_verify_landing_path_rewritten`

**Raw red:**

```
>       assert landing.startswith(session_dir2)
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x...>('/private/.../session2')
E        +    where <built-in method startswith ...> = '/old/path'.startswith
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:362: AssertionError
1 failed in 1.80s
```

**Restore receipt (quoted lines):**

```python
    if isinstance(verify, dict) and "landingPath" in verify:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.82s
```

---

## R15 — rewritten-only mutation

Neutralization adds one extra mutation (`new_meta["baseBranch"] = new_branch`) that is **not**
appended to `rewritten`, per the order's specified probe.

**Neutralization:**

```python
     new_meta["repoRoot"] = target_toplevel
     new_meta["branch"] = new_branch
+    new_meta["baseBranch"] = new_branch  # PROBE: extra mutation not listed in `rewritten`
     rewritten.append("meta.repoRoot")
```

**Detector:** `test_relocate_invariant_no_old_paths_survive`

**Raw red:**

```
>       assert snap_before == snap_after
E       AssertionError: assert {'meta': {'ba...json'}}, ...}} == {'meta': {'ba...json'}}, ...}}
E         Differing items:
E         {'meta': {'baseBranch': 'main', ...}} != {'meta': {'baseBranch': 'HEAD', ...}}
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:235: AssertionError
1 failed in 1.71s
```

**Restore receipt (quoted lines):**

```python
    new_meta["repoRoot"] = target_toplevel
    new_meta["branch"] = new_branch
    rewritten.append("meta.repoRoot")
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.74s
```

---

## R16 — marker retirement ownership check

**Neutralization** (`_retire_relocate_marker`):

```python
-        if marker.get("sessionDir") != os.path.realpath(session_dir):
+        if False and (marker.get("sessionDir") != os.path.realpath(session_dir)):
             return "not-ours"
```

**Detector:** `test_relocate_marker_not_ours_left_alone`

**Raw red:**

```
>       assert outcome == "not-ours"
E       AssertionError: assert 'retired' == 'not-ours'
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:614: AssertionError
1 failed in 0.29s
```

**Restore receipt (quoted lines):**

```python
        if marker.get("sessionDir") != os.path.realpath(session_dir):
            return "not-ours"
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.28s
```

---

## E1 — `re-emit-not-stale` (`relocation is None`)

**Neutralization** (`_cmd_re_emit_locked`):

```python
-    if relocation is None:
+    if False and (relocation is None):
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-not-stale-not_stale]`

**Raw red:**

```
>           "oldRoot": relocation.get("oldRoot"),
E       AttributeError: 'NoneType' object has no attribute 'get'
plugins/superheroes/lib/round_driver.py:6477: AttributeError
1 failed in 1.72s
```

**Restore receipt (quoted lines):**

```python
    if relocation is None:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.55s
```

---

## E2 — `re-emit-head-moved`

**Neutralization:**

```python
-    if anchor_head.lower() != live_head.lower():
+    if False and (anchor_head.lower() != live_head.lower()):
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-head-moved-head_moved]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:506: AssertionError
1 failed in 15.24s
```

**Restore receipt (quoted lines):**

```python
    if anchor_head.lower() != live_head.lower():
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 10.06s
```

---

## E3 — `re-emit-attempt-has-results`, landing-file branch

**Neutralization** (`_re_emit_attempt_result_names`):

```python
     landing = round_records.landing_dir(session_dir, rnd, phase)
-    if os.path.isdir(landing):
+    if False and (os.path.isdir(landing)):
         for name in os.listdir(landing):
             if needle in name:
                 names.append(name)
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-attempt-has-results-has_results]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:506: AssertionError
1 failed in 11.73s
```

**Restore receipt (quoted lines):**

```python
    if os.path.isdir(landing):
        for name in os.listdir(landing):
            if needle in name:
                names.append(name)
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.93s
```

---

## E4 — `re-emit-attempt-has-results`, journal branch (`recorded` row loop)

**Neutralization** (`_re_emit_attempt_result_names`):

```python
-    for event in journal:
+    for event in ([] if True else journal):
         if event.get("outcome") != "recorded":
```

**Detector:** `test_re_emit_refuses_when_a_result_is_recorded_in_the_journal`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:592: AssertionError
1 failed in 2.88s
```

**Restore receipt (quoted lines):**

```python
    for event in journal:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.59s
```

---

## E5 — `re-emit-no-pending-order` (`not isinstance(pending, dict)`)

**Neutralization:**

```python
-    if not isinstance(pending, dict):
+    if False and (not isinstance(pending, dict)):
         return _refuse_cmd(session_dir, "re-emit", "re-emit-no-pending-order")
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-no-pending-order-no_pending]`

**Raw red:**

```
>       phase = pending.get("phase")
E       AttributeError: 'NoneType' object has no attribute 'get'
plugins/superheroes/lib/round_driver.py:6418: AttributeError
1 failed in 1.79s
```

**Restore receipt (quoted lines):**

```python
    if not isinstance(pending, dict):
        return _refuse_cmd(session_dir, "re-emit", "re-emit-no-pending-order")
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.54s
```

---

## E6 — `re-emit-no-anchor`

**Neutralization:**

```python
-    if anchor is None or not _journal_has_orders_emitted(session_dir, rnd, phase, old_attempt):
+    if False and (anchor is None or not _journal_has_orders_emitted(session_dir, rnd, phase, old_attempt)):
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-no-anchor-no_anchor]`

**Raw red:**

```
>       anchor_head = anchor.get("headSha")
E       AttributeError: 'NoneType' object has no attribute 'get'
plugins/superheroes/lib/round_driver.py:6442: AttributeError
1 failed in 1.75s
```

**Restore receipt (quoted lines):**

```python
    if anchor is None or not _journal_has_orders_emitted(session_dir, rnd, phase, old_attempt):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.55s
```

---

## E7 — `re-emit-head-unresolved` (git-status branch)

**Neutralization:**

```python
-    if (head_res.status in (store_core.GIT_UNAVAILABLE, store_core.GIT_DECLINED)
+    if False and (head_res.status in (store_core.GIT_UNAVAILABLE, store_core.GIT_DECLINED)
             or not head_res.out):
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-head-unresolved-head_unresolved]`

**Raw red:**

```
>       if anchor_head.lower() != live_head.lower():
E       AttributeError: 'NoneType' object has no attribute 'lower'
plugins/superheroes/lib/round_driver.py:6449: AttributeError
1 failed in 1.78s
```

**Restore receipt (quoted lines):**

```python
    if (head_res.status in (store_core.GIT_UNAVAILABLE, store_core.GIT_DECLINED)
            or not head_res.out):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.66s
```

---

## E8 — attempt allocation floor (`max(…, old_attempt + 1)`)

**Neutralization:**

```python
-    new_attempt = max(_next_dispatch_attempt(session_dir, rnd, phase, state), old_attempt + 1)
+    new_attempt = _next_dispatch_attempt(session_dir, rnd, phase, state)
```

**Detector:** `test_re_emit_positive_after_relocate`

**Raw red:**

```
>       assert out["attempt"] == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:391: AssertionError
1 failed in 2.83s
```

**Restore receipt (quoted lines):**

```python
    new_attempt = max(_next_dispatch_attempt(session_dir, rnd, phase, state), old_attempt + 1)
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.84s
```

---

## E9 — the superseded row (`extra_journal_entries=[superseded_row]`)

**Neutralization** (call site in `_cmd_re_emit_locked`):

```python
-            extra_journal_entries=[superseded_row])
+            extra_journal_entries=[])
```

**Detector:** `test_re_emit_positive_after_relocate`

**Raw red:**

```
>       superseded_idx = next(i for i, r in enumerate(rows)
                              if r.get("outcome") == "orders-superseded")
E       StopIteration
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:412: StopIteration
1 failed in 3.10s
```

**Restore receipt (quoted lines):**

```python
            extra_journal_entries=[superseded_row])
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.81s
```

---

## E10 — certification close (superseded filter in `_journal_open_seats`)

**Neutralization** (`round_certification.py`):

```python
-        if (phase_key, rnd_key, attempt_key) in superseded:
+        if False and (phase_key, rnd_key, attempt_key) in superseded:
             continue
```

**Detector:** `test_re_emit_certification_open_close`

**Raw red:**

```
>       assert not attempt0_keys
E       AssertionError: assert not [('dispatch-panel', 1, 0, 'architecture-reviewer', 0), ('dispatch-panel', 1, 0, 'code-reviewer', 0), ('dispatch-panel'...remortem-reviewer', 0), ('dispatch-panel', 1, 0, 'security-reviewer', 0), ('dispatch-panel', 1, 0, 'test-reviewer', 0)]
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:432: AssertionError
1 failed in 2.82s
```

**Restore receipt (quoted lines):**

```python
        if (phase_key, rnd_key, attempt_key) in superseded:
            continue
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.82s
```

---

## E11 — certification open for `re-emit` (`orders-emitted` cmd tuple)

**Neutralization** (`round_certification.py`):

```python
-        if (cmd in ("next", "advance", "re-emit") and outcome == "orders-emitted"
+        if (cmd in ("next", "advance") and outcome == "orders-emitted"
```

**Detector:** `test_re_emit_certification_open_close`

**Raw red:**

```
>       assert attempt1_keys
E       assert []
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:434: AssertionError
1 failed in 2.89s
```

**Restore receipt (quoted lines):**

```python
        if (cmd in ("next", "advance", "re-emit") and outcome == "orders-emitted"
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.81s
```

---

## E12 — the session lock (`cmd_re_emit`)

Shares R11's question. Same narrowest-production-neutralization judgment applied: swap the lock
acquisition for a no-op context manager inside `cmd_re_emit`.

**Neutralization:**

```python
 def cmd_re_emit(session_dir, by):
     """Re-emit a stale pending dispatch order at the current head as a new attempt."""
     try:
-        with round_records.session_lock(session_dir):
+        with open(os.devnull):  # was: round_records.session_lock(session_dir)
             refusal = _commit_recover_or_refuse(session_dir, "re-emit")
```

**Detector:** `test_re_emit_refusal_tokens[re-emit-locked-locked]`

**Raw red:**

```
>       assert rc == 1
E       assert 0 == 1
plugins/superheroes/lib/tests/test_round_driver_session_mobility.py:506: AssertionError
1 failed in 2.85s
```

**Restore receipt (quoted lines):**

```python
    try:
        with round_records.session_lock(session_dir):
            refusal = _commit_recover_or_refuse(session_dir, "re-emit")
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.64s
```

---

## Whole-file re-run (final head, all elements restored)

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest plugins/superheroes/lib/tests/test_round_driver_session_mobility.py -q
...............................                                          [100%]
31 passed in 49.38s
```

`git status --porcelain` immediately before writing this record: empty (no production or test
file left modified).

---

## Orchestrator re-run (independent verification of every element)

The orchestrator re-applied each neutralization above, one at a time, as a targeted edit in the
same detached probe tree at `be7de1c1`, ran the named node(s) alone with a fresh never-written
bytecode prefix (`-B -X pycache_prefix=/private/tmp/pyc-2i-mine`, `-p no:randomly`), and restored
each by its exact inverse edit. Every element went red; after the last restore `git diff` in the
probe tree was empty and the whole file ran green (`31 passed in 52.47s`). Red receipts (first
failure line and summary):

| # | Red (first failure line) | Summary |
|---|---|---|
| R1 | `AttributeError: 'NoneType' object has no attribute 'get'` | 1 failed |
| R2 | `assert 0 == 1` | 1 failed |
| R3 | `assert 0 == 1` | 1 failed |
| R4 | `assert 0 == 1` | 1 failed |
| R5 | `AttributeError: 'NoneType' object has no attribute 'casefold'` | 1 failed |
| R6 | `assert 0 == 1` | 1 failed |
| R7 | `assert 0 == 1` | 1 failed |
| R8 | `assert 0 == 1` | 1 failed |
| R9 | `assert 0 == 1` (both nodes) | 2 failed |
| R10 | `assert 0 == 1` | 1 failed |
| R11 | `assert 0 == 1` | 1 failed |
| R12 | `assert '…/repo_a' == '…/repo_b'`; `old path survived at state.config.repoRoot` | 2 failed |
| R13 | `assert '…/session' == '…/session2'` | 1 failed |
| R14 | `'/old/path'.startswith(<session2>)` is `False` | 1 failed |
| R15 | snapshot minus `rewritten` differs (`meta.baseBranch` `main` → `HEAD`) | 1 failed |
| R16 | `assert 'retired' == 'not-ours'` | 1 failed |
| E1 | `AttributeError: 'NoneType' object has no attribute 'get'` | 1 failed |
| E2 | `assert 0 == 1` | 1 failed |
| E3 | `assert 0 == 1` | 1 failed |
| E4 | `assert 0 == 1` | 1 failed |
| E5 | `AttributeError: 'NoneType' object has no attribute 'get'` | 1 failed |
| E6 | `AttributeError: 'NoneType' object has no attribute 'get'` | 1 failed |
| E7 | `AttributeError: 'NoneType' object has no attribute 'lower'` | 1 failed |
| E8 | `assert 0 == 1` (attempt-0 files overwritten) | 1 failed |
| E9 | `StopIteration` (no `orders-superseded` row) | 1 failed |
| E10 | `assert not [('dispatch-panel', 1, 0, 'architecture-reviewer', 0), …]` | 1 failed |
| E11 | `assert []` (no attempt-1 seat opened) | 1 failed |
| E12 | `assert 0 == 1` | 1 failed |

Where the red is a crash rather than the refusal assertion (R1, R5, E1, E5, E6, E7), the guard's
absence lets the verb run past it into a `None` it was protecting — the detector still fails, and
it fails because the guard is gone. R7's case reaches only the `meta.baseRef ≠ config.baseRef`
branch; the "pin does not resolve to itself in the target" branch has no detector of its own.
