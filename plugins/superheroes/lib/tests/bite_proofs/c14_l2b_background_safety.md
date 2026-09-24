# C14 layer 2b — background flow identity, suspension and stop: bite-proof record (#1273 WO-2)

## BP-1 — write-mode background refusal

- **site:** `plugins/superheroes/lib/engine_dispatch.py` (`dispatch_write` claude background guard)
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_background_write_refused`
- **axis:** claude `dispatch-write` with `claude_mode="background"` must refuse with `claude-mode-background-write` before spawn
- **neutralization:** prepend `return False` to `_is_background_claude_mode` so the guard never fires
- **raw red (rc 1):**

```
>       assert res["detail"] == ED.MODE_REFUSAL_CLAUDE_MODE_BACKGROUND_WRITE
E       AssertionError: assert 'internal-AssertionError' == 'claude-mode-background-write'
```

- **restore:** removed the planted `return False` line from `_is_background_claude_mode`
- **raw green (rc 0):** `.` / `1 passed`

- **verdict:** RED→GREEN

## BP-2 — listing blindness is not already-ended

- **site:** `plugins/superheroes/lib/engine_dispatch.py` (`_background_stop`)
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_stop_listing_blind_not_already_ended`
- **axis:** unreadable agents listing must yield `stop-unconfirmed`, not `already-ended`
- **neutralization:** `if not ok_before: return "already-ended"  # bite-proof plant`
- **raw red (rc 1):**

```
>       assert ED._background_stop(launch_id, cfg, cwd) == "stop-unconfirmed"
E       AssertionError: assert 'already-ended' == 'stop-unconfirmed'
```

- **restore:** restored `return "stop-unconfirmed"` for the `not ok_before` branch
- **raw green (rc 0):** `.` / `1 passed`

- **verdict:** RED→GREEN

## BP-3 — resumed read cursor bounds turn-end signal

- **site:** `plugins/superheroes/lib/engine_dispatch.py` (`_run_engine_files_background` poll loop)
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_resume_ignores_stale_turn_end_signal`
- **axis:** after suspension, stale pre-cursor `toolEndsTurn` rows must not end the attempt early
- **neutralization:** `rows_after_cursor = rows  # bite-proof plant: ignore cursor`
- **raw red (rc 1):**

```
>       assert not any(r.get("kind") == "attempt-ended" for r in records_mid)
E       assert not True
```

- **restore:** `rows_after_cursor = rows[cursor:] if cursor else rows`
- **raw green (rc 0):** `.` / `1 passed`

- **verdict:** RED→GREEN
