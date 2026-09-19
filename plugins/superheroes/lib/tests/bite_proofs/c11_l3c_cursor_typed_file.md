# C11 layer 3c — cursor typed-file result channel bite-proof

WO-A (#1270). Detector self-path; excluded from content census.

## E1 — channel flip (`engine_result_channel.py:_CHANNEL_BY_ENGINE["cursor"]`)

- **axis:** cursor declares `CHANNEL_NATIVE`, not `CHANNEL_MARKER`
- **neutralization:** `_CHANNEL_BY_ENGINE["cursor"] = CHANNEL_MARKER`
- **raw red:**
```
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam
assert False is True  (res["ok"] is True)
```
- **restore:** `_CHANNEL_BY_ENGINE["cursor"] = CHANNEL_NATIVE`
- **restore receipt:** `"cursor": CHANNEL_NATIVE,` present at line 47
- **raw green:** `1 passed in 0.76s`
- **verdict:** proven

## E2 — argv shape (`engine_adapter.py:build_argv_result` cursor branch)

- **axis:** review and build both emit `-f --sandbox enabled`, no `--mode plan`
- **neutralization:** restore `--mode plan` for reads
- **detector:** `test_cursor_argv_shape_both_roles[review]`
- **verdict:** proven (red on `--mode plan` restore; green after inverse)

## E3 — `--output-schema` gate (`engine_dispatch.py:_open_native_channel_argv`)

- **axis:** cursor open argv omits `--output-schema`
- **neutralization:** append flag unconditionally for every native engine
- **detector:** `test_cursor_review_admits_typed_file_through_injected_seam` (argv assertion), `test_canonical_spawn_argv_matches_opened_argv_both_engines[cursor]`
- **verdict:** proven

## E4 — `-o` gate (`engine_dispatch.py:_spawn_native_result_argv`)

- **axis:** cursor spawn argv omits `-o`
- **neutralization:** append `-o` for every native engine
- **detector:** `test_cursor_review_admits_typed_file_through_injected_seam` (argv assertion)
- **verdict:** proven

## E5 — prompt staging (`engine_dispatch.py:_stage_attempt_prompt`)

- **axis:** cursor attempt prompt carries typed-file contract at `prompt-attempt-N.md`
- **neutralization:** return staged prompt path without writing attempt file
- **detector:** `test_cursor_review_admits_typed_file_through_injected_seam`, `test_cursor_write_admits_typed_file_through_injected_seam`
- **verdict:** proven

## E6 — missing-file forfeit (`engine_dispatch.py:_load_native_result_json`)

- **axis:** absent typed file → `native-result-missing`
- **neutralization:** `return ({}, None)` on `FileNotFoundError`
- **detector:** `test_cursor_review_missing_typed_file_forfeits_native_result_missing`
- **verdict:** proven

## E7 — schema admission (`engine_dispatch.py:_admit_native_review_result`)

- **axis:** schema-invalid typed file → `native-result-schema-invalid`
- **neutralization:** skip `_validate_with_detail`
- **detector:** `test_cursor_review_schema_invalid_file_forfeits`, write twin T4b
- **verdict:** proven

## E8 — scrub (`engine_dispatch.py` fold scrub egress)

- **axis:** secrets scrubbed from terminal and journal
- **neutralization:** scrub call becomes identity
- **detector:** `test_cursor_typed_file_secret_scrubbed_from_result_and_journal`
- **verdict:** proven

## E9 — occupied result path (`engine_dispatch.py:_spawn_native_result_argv` lstat)

- **axis:** pre-existing `native-result-1.json` → `native-result-path-occupied`
- **neutralization:** drop `os.lstat` refusal
- **detector:** `test_cursor_native_result_path_occupied_refuses_attempt`
- **verdict:** proven

## E9b — attempt-prompt exclusive create (`engine_dispatch.py:_stage_attempt_prompt` O_EXCL)

- **axis:** pre-existing `prompt-attempt-1.md` → `attempt-prompt-occupied`
- **neutralization:** `O_EXCL|O_NOFOLLOW` → plain open
- **detector:** `test_cursor_attempt_prompt_occupied_refuses_attempt` (four arms)
- **verdict:** proven

## E10 — marker-retired chokepoint (`engine_dispatch.py:_marker_channel_retired_run`)

- **axis:** layer-3b cursor journal → `marker-channel-retired`, not argv-coherence
- **neutralization:** `_marker_channel_retired_run` returns `False`
- **detector:** `test_cursor_marker_opened_run_ends_marker_channel_retired`
- **verdict:** proven

## E11 — naive completedAt (`conformance_probe.py:_validate_probe_record`)

- **axis:** naive ISO timestamp → `probe-result-malformed`
- **neutralization:** drop naive arm
- **detector:** `test_validate_probe_record_refuses_naive_completed_at`
- **verdict:** proven

## E12 — `_seat_for_engine` home (`conformance_probe.py:_seat_for_engine`)

- **axis:** reads `model_registry.matrix_config`, not `seat_map.matrix_config`
- **neutralization:** read `seat_map.matrix_config`
- **detector:** `test_seat_for_engine_reads_model_registry_home`
- **verdict:** proven

## E13 — journal-line-not-object at each consumer site

- **axis:** non-object journal line → `journal-corrupt:journal-line-not-object`
- **neutralization:** `_journal_read_raw` skips non-object lines
- **detector:** `test_journal_line_not_object_refused_at_every_consumer_site` (5 parameterized sites)
- **verdict:** proven

## E14 — spawn-guard ordering (`engine_dispatch.py:_run_engine_files`)

- **axis:** retirement before `_spawn_argv_coherence`
- **neutralization:** move retirement below coherence
- **detector:** `test_cursor_marker_opened_run_ends_marker_channel_retired` (production arm)
- **verdict:** proven

## E15 — attempt-prompt no-follow (`engine_dispatch.py:_stage_attempt_prompt` lstat+O_EXCL)

- **axis:** symlink/directory/dangling symlink at attempt path refused without following
- **neutralization:** drop lstat pre-check and `O_NOFOLLOW`
- **detector:** `test_cursor_attempt_prompt_occupied_refuses_attempt` (four arms)
- **verdict:** proven

## E16 — execution-record binding (`engine_dispatch.py:run_execution_record`)

- **axis:** `promptSha256` binds attempt prompt bytes for cursor
- **neutralization:** ignore `attemptPromptSha256`
- **detector:** `test_execution_record_binds_attempt_prompt_for_cursor`
- **verdict:** proven

## E17 — one output instruction (BRIEF-005 contract prose)

- **axis:** prompt-delivery engines omit graded-stdout contract lines
- **neutralization:** append `REVIEW_RESULT_CONTRACT` for prompt delivery too
- **detector:** `test_cursor_fed_prompt_has_one_output_instruction`
- **verdict:** proven

## E18 — argv coherence both engines (`engine_dispatch.py:_native_channel_suffix`)

- **axis:** suffix gated on `RESULT_DELIVERY_ARGV` only
- **neutralization:** `_native_channel_suffix` ungated (always appends for native)
- **detector:** `test_canonical_spawn_argv_matches_opened_argv_both_engines[cursor]`
- **verdict:** proven

## WO-B — the retirement

### R1 — `_grade_review_attempt` marker arm (`engine_dispatch.py:_grade_review_attempt`)

- **axis:** marker-opened direct grade → `marker-channel-retired`, never `ok`
- **neutralization:** return `{"ok": True, "resultKind": "findings", "findings": []}` with engagement attached
- **detector:** `test_grade_review_attempt_marker_opened_returns_retired`
- **raw red:** `AssertionError: assert None is True` on `grade.get("forfeit")` (got `ok: True`)
- **restore:** `result = _marker_arm_retired_grade()` / `result["engagement"] = engagement` / `return result`
- **raw green:** `1 passed in 0.71s`
- **verdict:** proven

### R2 — `_grade_write_attempt` marker arm

- **axis:** marker-opened direct write grade → retired forfeit, no `ok`
- **neutralization:** return `{"ok": True, "signal": "ok", "evidence": {}}`
- **detector:** `test_grade_write_attempt_marker_opened_returns_retired`
- **raw red:** `AssertionError: assert None is True` on `grade.get("forfeit")` (got `ok: True`)
- **restore:** `return _marker_arm_retired_grade()`
- **raw green:** `1 passed in 0.32s`
- **verdict:** proven

### R3 — `_parse_review_attempt` marker arm

- **axis:** marker-opened parse → `None`
- **neutralization:** return `{"ok": True, "resultKind": "findings"}`
- **detector:** `test_parse_review_attempt_marker_opened_returns_none`
- **raw red:** `AssertionError: assert {'ok': True, 'resultKind': 'findings'} is None`
- **restore:** `return None`
- **raw green:** `1 passed in 0.71s`
- **verdict:** proven

### R4 — `_parse_write_attempt` marker arm

- **axis:** marker-opened write parse → `None`
- **neutralization:** return `{"ok": True}`
- **detector:** `test_parse_write_attempt_marker_opened_returns_none`
- **raw red:** `AssertionError: assert {'ok': True} is None`
- **restore:** `return None`
- **raw green:** `1 passed in 0.31s`
- **verdict:** proven

### R5 — `_observation_from_attempt` marker arm

- **axis:** marker-opened observation → `read: "unknown"`
- **neutralization:** `return _engagement_with_read(engagement, result_kind="findings", items=[{"x": 1}])`
- **detector:** `test_observation_marker_opened_read_unknown`
- **raw red:** `AssertionError: assert 'engaged' == 'unknown'`
- **restore:** `return _engagement_with_read(engagement)`
- **raw green:** `1 passed in 0.74s`
- **verdict:** proven

### R6 — supervise stdout-cap gate (write)

- **axis:** marker-opened supervised write never mints `stdout-capped-by-attempt`
- **neutralization:** re-add deleted stdout-cap block before retry branch
- **detector:** `test_supervise_write_marker_opened_never_mints_stdout_capped`
- **raw red:** `1 passed` (gate unreachable — `_marker_channel_retired_run` chokepoint returns first)
- **verdict:** Unreachable through this entry point

### R6b — supervise engaged-artifact upgrade gate (review)

- **axis:** marker-opened supervised review never mints `forfeit-with-engaged-artifact`
- **neutralization:** re-add deleted `_maybe_upgrade_review_terminal_forfeit` block
- **detector:** `test_supervise_review_marker_opened_never_mints_engaged_artifact_upgrade`
- **raw red:** `1 passed` (gate unreachable — chokepoint returns first)
- **verdict:** Unreachable through this entry point

## WO-D — review-round fixes

### D1 — result-file write excluded from engagement (`engine_adapter.py:cursor_tool_calls`)

- **axis:** cursor `editToolCall` writing `nativeResultPath` is not investigation
- **neutralization:** `if False and write_path is not None and excluded_realpaths:`
- **detector:** `test_cursor_result_file_write_is_not_engagement`
- **raw red:** `assert res["engagement"]["toolCalls"] == 0` → `assert 1 == 0`
- **restore:** remove `False and` prefix from exclusion guard
- **raw green:** `1 passed in 0.92s`
- **verdict:** proven

### D2 — unreadable staged prompt token (`engine_dispatch.py:_stage_attempt_prompt`)

- **axis:** unreadable `promptPath` → `prompt-unreadable`, not `native-schema-unreadable`
- **neutralization:** first `OSError` return `native-schema-unreadable`
- **detector:** `test_stage_attempt_prompt_unreadable_prompt_refuses_prompt_unreadable`
- **raw red:** `assert ended["refusal"] == "prompt-unreadable"` → `AssertionError: assert 'native-schema-unreadable' == 'prompt-unreadable'`
- **restore:** `return None, None, "prompt-unreadable"`
- **raw green:** `1 passed in 1.00s`
- **verdict:** proven

### D3 — attempt prompt sha from written bytes (`engine_dispatch.py:_stage_attempt_prompt`)

- **axis:** `engine-started.attemptPromptSha256` always present for cursor prompt delivery
- **neutralization:** `return path, None, None` (drop sha from written bytes)
- **detector:** `test_engine_started_always_carries_attempt_prompt_sha_for_cursor`
- **raw red:** `assert "attemptPromptSha256" in started` → `AssertionError`
- **restore:** `return path, hashlib.sha256(content.encode("utf-8")).hexdigest(), None`
- **raw green:** `1 passed in 1.07s`
- **verdict:** proven

### D4 — preflight probe cursor argv (`preflight_probe.py:cross_vendor_no_op_argv`)

- **axis:** cursor no-op argv matches review argv minus stream-json (`-f --sandbox enabled`)
- **neutralization:** restore `--mode plan` in `cross_vendor_no_op_argv("cursor")`
- **detector:** `test_cross_vendor_no_op_argv_cursor`
- **raw red:** `AssertionError: assert ('cursor-agent', ... '--mode', ...) == (..., '-f', '--sandbox', 'enabled')`
- **restore:** `"-f", "--sandbox", "enabled"`
- **raw green:** `1 passed in 0.26s`
- **verdict:** proven

### D5 — cursor spawn argv omits `-o` (`engine_dispatch.py:_spawn_native_result_argv`)

- **axis:** cursor `engine-launching.spawnArgv` carries no `-o` / `--output-schema`
- **neutralization:** `argv_out = list(spawn_argv) + ["-o", result_path]` unconditionally
- **detector:** `test_cursor_review_admits_typed_file_through_injected_seam` (spawnArgv assertion)
- **raw red:** `assert "-o" not in launching["spawnArgv"]` → `AssertionError`
- **restore:** gate `-o` append on `RESULT_DELIVERY_ARGV` only
- **raw green:** `1 passed in 0.97s`
- **verdict:** proven

### R7 — `_finalize_write_forfeit_terminal` passthrough

- **axis:** terminal dict passes through unchanged (no classifier/salvage attach)
- **neutralization:** `terminal = dict(terminal); terminal["itemCheck"] = {}`
- **detector:** `test_finalize_write_forfeit_terminal_passthrough`
- **raw red:** `AssertionError` — left dict contains extra `itemCheck`
- **restore:** `return terminal`
- **raw green:** `1 passed in 0.32s`
- **verdict:** proven
