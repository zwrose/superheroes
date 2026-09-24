# C14 layer 4a (arm-D shadow) — launcher background lanes: bite-proof record

Detector file: `plugins/superheroes/lib/tests/test_launcher_background.py`.

## Round-4 fix (the lifecycle chokepoint, the token homes, the isolated legs)

Run 2026-09-24T09:5xZ in a detached probe worktree at `e72ec143` carrying the uncommitted round-4
fix (the branch tree was never mutated). Every neutralization was a targeted edit through the edit
action, restored by the inverse edit. Detectors ran unedited. Command shape:
`/usr/bin/python3 -B -m pytest <nodeid> -q -p no:cacheprovider` with
`CLAUDE_CONFIG_DIR` pinned. Paths below are relative to `plugins/superheroes/lib/`.

**Restore receipt (all elements):** after the last restore, every changed file in the probe tree
was byte-compared with the branch tree (`cmp -s` per file): `restore-receipt: probe tree
byte-identical to branch tree on every changed file`. **Green (all elements):** the whole detector
file, `rc=0`, `89 passed`.

Declared guarded-element set (the round-4 order, issue #1401 09:4xZ ruling): D9a stop census,
D9b handle census, D9c worktree scoping, D9d stop confirmation (sticky row), D9e stop
confirmation (pid exit), D9f finished-lane retire path, D9g repair records the session pid,
D10a config-root token home, D10b engagement-source home, D7c `envPins` no extra keys, C2
ambiguous transcript, C3 truncated transcript.

### BP-1 — D9a: `_retire` is the only builder stop

- **element / axis:** `launcher.py` `_retire_lane`; axis: no function but `_retire` spells a stop.
- **detector:** `test_one_retire_and_one_handle_constructor_in_the_launcher`
- **neutralization:** `elif _retire(handle) == "stopped":` → `elif engine_dispatch.claude_cli(["stop", handle.backgroundId], config_dir)[0] == 0:`
- **raw red (rc 1):** `AssertionError: builder-stop-outside-retire: ['_retire', '_retire_lane']`
- **restore:** inverse edit back to `elif _retire(handle) == "stopped":`

### BP-2 — D9b: `_handle_from_row` is the only handle constructor

- **element / axis:** `launcher.py` `_grade_background_launch`; axis: no function but the constructor builds a `_Handle`.
- **detector:** `test_one_retire_and_one_handle_constructor_in_the_launcher`
- **neutralization:** `"handle": handle}` → `"handle": _Handle(background_id, pid, cwd, config_dir)}`
- **raw red (rc 1):** `AssertionError: handle-built-outside-constructor: ['_handle_from_row', '_grade_background_launch']`
- **restore:** inverse edit back to `"handle": handle}`

### BP-3 — D9c: a handle only from a row in the lane's own worktree

- **element / axis:** `launcher.py` `_handle_from_row` cwd check; axis: an unacknowledged launch never stops a session outside its worktree, and an acknowledged one listed elsewhere is neither stopped nor forgotten.
- **detectors:** `test_no_acknowledgement_never_touches_a_session_outside_the_worktree`, `test_an_acknowledged_session_listed_elsewhere_is_never_stopped_nor_forgotten`, `test_an_acknowledgement_alone_is_not_a_launch[other-worktree]`
- **neutralization:** deleted the two lines `if not isinstance(row_cwd, str) or os.path.realpath(row_cwd) != os.path.realpath(cwd):` / `return None`
- **raw red (rc 1, 3 failed):** `AssertionError: assert [_Handle(back...aude-config')] == []` — `Left contains 3 more items, first extra item: _Handle(backgroundId='11111111', pid=4001, ...)` (the sibling lane's session would be stopped); `Left contains one more item: _Handle(backgroundId='ab12cd34', pid=5150, ...)`
- **restore:** re-inserted the two lines (inverse edit)

### BP-4 — D9d: a stop is not confirmed while a same-id row remains

- **element / axis:** `launcher.py` `_session_gone` listing leg; axis: round-4 finding 2 — a PID-less stop is confirmed only when a clean listing no longer holds the id.
- **detector:** `test_retire_confirms_only_by_pid_exit_or_absence_from_a_clean_listing`
- **neutralization:** `return listing_ok and engine_dispatch.claude_agent_row_for_launch(rows, handle.backgroundId) is None` → `return listing_ok`
- **raw red (rc 1, 2 failed / 3 passed):** `AssertionError: assert 'stopped' == 'stop-unconfirmed'` on `[no-pid-sticky-stopped-row]` and `[pid-outlives-the-wait]`
- **restore:** inverse edit

### BP-5 — D9e: a known session pid that has exited confirms the stop

- **element / axis:** `launcher.py` `_session_gone` pid leg; axis: the pid exiting confirms even while the row lingers.
- **detector:** same test, `[pid-gone]`
- **neutralization:** deleted `if handle.pid is not None and not _pid_alive(handle.pid, proc):` / `return True`
- **raw red (rc 1, 1 failed / 4 passed):** `AssertionError: assert 'stop-unconfirmed' == 'stopped'` on `[pid-gone]`
- **restore:** re-inserted the two lines

### BP-6 — D9f: `record-outcome --retire` is the finished lane's path to terminal

- **element / axis:** `launcher.py` `record_outcome` retire branch; axis: round-4 finding 3 — the session is retired (confirmed) before the outcome is recorded.
- **detectors:** `test_record_outcome_retire_is_the_finished_lanes_path_to_terminal[confirmed|unconfirmed]`, `test_record_outcome_cli_retire_flag`
- **neutralization:** `if retire:` → `if False:`
- **raw red (rc 1, 3 failed):** `AssertionError: assert [] == ['ab12cd34']` (no stop was issued)
- **restore:** inverse edit back to `if retire:`

### BP-7 — D9g: the repair records the session pid, never the acknowledger's

- **element / axis:** `launcher.py` `_spawn_attempt` `started_repair`; axis: round-4 finding 5 — the repair path runs end to end.
- **detector:** `test_failed_started_append_with_a_confirmed_stop_terminalizes_through_repair`
- **neutralization:** `"pid": started["pid"],` (in `started_repair`) → `"pid": proc.pid,`
- **raw red (rc 1):** `assert events[1]["pid"] == session.pid and acks and acks[0] != session.pid` / `AssertionError: assert (96949 == 96798)`
- **restore:** inverse edit

### BP-8 — D10a: the config-root refusal tokens live only in `config_dir.py`

- **element / axis:** `engine_dispatch.py` spawn-time recheck; axis: round-4 finding 4 — no producer restates the literal.
- **detector:** `test_each_shared_token_is_spelled_in_one_home[config-root-refusals]` (the literal itself is pinned by `test_missing_config_root_refuses_before_anything_runs`: `cd.NOT_A_DIRECTORY == "config-dir-unusable:not-a-directory"`)
- **neutralization:** `_journal_prep_refusal(run_dir_real, attempt, config_dir.NOT_A_DIRECTORY)` → `..., "config-dir-unusable:not-a-directory")`
- **raw red (rc 1):** `AssertionError: token-restated-outside-home: config-dir-unusable: in ['lib/config_dir.py', 'lib/engine_dispatch.py']`
- **restore:** inverse edit

### BP-9 — D10b: the transcript engagement source lives only in `engine_adapter.py`

- **element / axis:** `seat_canary.py` `lane_canary`; axis: gap-sweep finding 2.
- **detector:** `test_each_shared_token_is_spelled_in_one_home[engagement-source]` (literal pinned by `test_lane_canary_reads_tool_calls_from_the_recorded_transcript`: `"engagementSource": "claude-transcript"`)
- **neutralization:** `"engagementSource": engine_adapter.ENGAGEMENT_SOURCE_TRANSCRIPT}` → `"engagementSource": "claude-transcript"}` (applied in the same run as BP-8; each parameter reds on its own element)
- **raw red (rc 1):** `AssertionError: token-restated-outside-home: claude-transcript in ['lib/engine_adapter.py', 'lib/seat_canary.py']`
- **restore:** inverse edit

### BP-10 — D7c: `envPins` carries no extra keys (isolated)

- **element / axis:** `launch_ledger.py` `_valid_env_pins`; axis: an extra key alone refuses — the case now edits the real pins, so no other rule can redden it.
- **detector:** `test_fold_refuses_each_malformed_started_field[extra-key]`
- **neutralization:** `if set(pins) - _ENV_PIN_KEYS:` → `if False:`
- **raw red (rc 1, 1 failed / 10 passed):** `assert True is False` on `[extra-key]` only
- **restore:** inverse edit

### BP-11 — C2: two transcripts for one session are ambiguous (isolated)

- **element / axis:** `seat_canary.py` `lane_canary`; axis: `lane-transcript-ambiguous`, never a pick of one.
- **detector:** `test_lane_canary_refuses_two_transcripts_for_one_session`
- **neutralization:** `reason = "lane-transcript-ambiguous" if paths else "lane-transcript-unresolved"` → `reason = "lane-transcript-unresolved"`
- **raw red (rc 1):** `'lane-transcript-unresolved' == 'lane-transcript-ambiguous'`
- **restore:** inverse edit

### BP-12 — C3: a transcript read only in its tail is never graded

- **element / axis:** `seat_canary.py` `lane_canary` size check; axis: gap-sweep finding 3 — `lane-transcript-truncated`, never a false `engaged: false`.
- **detector:** `test_lane_canary_refuses_a_transcript_it_could_only_read_the_tail_of`
- **neutralization:** `if size > engine_dispatch.MAX_STDOUT_CAPTURE:` → `if False:`
- **raw red (rc 1):** `assert (True is False)` (the canary returned `ok: true`, grading the tail)
- **restore:** inverse edit

## Not in this section

The layer's earlier detectors (D1–D8, item 3's other legs, r3) are re-proven at the final head in a
section appended below at handback. No receipts above were redacted: they hold no secrets, tokens,
private URLs or PII (local temp paths were elided with `...` only for length).
