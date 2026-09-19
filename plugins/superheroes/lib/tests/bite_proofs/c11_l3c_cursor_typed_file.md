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
