# C11 layer 3c — cursor's typed-file result channel: bite-proof record

Orchestrator-run record (#1270, PR #1341), **re-run on the final code head `1112690f`** in a detached probe worktree (the record commit on top adds only this file). Method — the one vets 244/245 accepted: an exact-string mutation of the guarded element with `count(old) == 1` asserted, the detector run alone by its exact node id (red), the inverse edit, the detector again (green), and `git status --porcelain` empty after every restore. The implementer's earlier version of this file carried verdicts for E2–E18 with no red/green captures; that record is superseded by this one — every element below carries its raw captures. **36 elements, 36 RED→GREEN.**

Element ids: E = WO-A (the move, `c6b9af7d`); R = WO-B (the retirement, `d5aea5c8`); D = WO-D (the compile-dropped premortem findings + the verify-gate fix, `ad508ab1`); F = the review loop's fix rounds (`2fba8b5b`, `2807a198`, `9338eebc`, `1112690f`); P = the probe's telemetry leg. E4 and D5 share one element (the `-o` gate, now pinned on the journaled `spawnArgv`); E9b and E15 share one (the attempt-prompt no-follow exclusive create); E14 has a production-path and an injected-path half.

## Disclosures

- **R6 / R6b — `Unreachable through this entry point`.** The two supervise-side gates WO-B deleted (`_attempt_stdout_truncated`/`_stdout_capped_forfeit` on writes, `_maybe_upgrade_review_terminal_forfeit` on reviews) sit behind the `_marker_channel_retired_run` chokepoint in `_supervise`; re-adding either gate cannot redden B6/B6b because the chokepoint returns the retired terminal first. The deletion is proven by the call-site census instead: `grep -nE '_attempt_stdout_truncated\(|_stdout_capped_forfeit\(|_maybe_upgrade_review_terminal_forfeit\(|_attach_write_report_salvage\(|_write_report_missing_items_delivered_detail\(' plugins/superheroes/lib/engine_dispatch.py | grep -v 'def '` → no output at the final head. B6/B6b stay as chokepoint detectors.
- **F8** needed a whole-predicate neutralization (`_cursor_shell_call_delivers_excluded_path` → `return False`): neutralizing only its path-string loop left the realpath loop matching, which is the detector doing its job, not a gap; the whole-predicate run is the one recorded.
- No element was `Unprovable as placed` or `Unrunnable here`.

## E1 — cursor declares the native channel

- **site:** `plugins/superheroes/lib/engine_result_channel.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam`
- **neutralization (exact-string, count(old)=1):**

```diff
-     "cursor": CHANNEL_NATIVE,
+     "cursor": CHANNEL_MARKER,
```

- **raw red (rc 1):**

```
E       assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 6.42s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 5.41s
```
- **verdict:** RED->GREEN

## E2 — cursor argv: -f --sandbox enabled, no --mode plan

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_cursor_argv_shape_both_roles[review]`
- **neutralization (exact-string, count(old)=1):**

```diff
-             "--sandbox", "enabled", "--output-format", "stream-json",
-         ]
+             "--sandbox", "enabled", "--output-format", "stream-json",
+         ]
+         if is_read:
+             argv = ["cursor-agent", "--model", model, "-p", "--trust", "--mode", "plan", "--output-format", "stream-json"]
```

- **raw red (rc 1):**

```
E       AssertionError: assert ['cursor-agen...'--mode', ...] == ['cursor-agen...t', '-f', ...]
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_cursor_argv_shape_both_roles[review]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.79s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 2.05s
```
- **verdict:** RED->GREEN

## E3 — --output-schema only on argv delivery (open side)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_canonical_spawn_argv_matches_opened_argv_both_engines[cursor]`
- **neutralization (exact-string, count(old)=1):**

```diff
-     if engine_result_channel.result_delivery(engine) == engine_result_channel.RESULT_DELIVERY_ARGV:
-         argv_out = list(argv) + ["--output-schema", schema_path]
+     if True:
+         argv_out = list(argv) + ["--output-schema", schema_path]
```

- **raw red (rc 1):**

```
E       AssertionError: assert ['cursor-agen...t', '-f', ...] == ['cursor-agen...t', '-f', ...]
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_canonical_spawn_argv_matches_opened_argv_both_engines[cursor]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 6.98s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 6.22s
```
- **verdict:** RED->GREEN

## E4/D5 — -o only on argv delivery (spawn side; the journaled spawnArgv)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam`
- **neutralization (exact-string, count(old)=1):**

```diff
-     if delivery == engine_result_channel.RESULT_DELIVERY_ARGV:
-         argv_out = list(spawn_argv) + ["-o", result_path]
+     if True:
+         argv_out = list(spawn_argv) + ["-o", result_path]
```

- **raw red (rc 1):**

```
E       AssertionError: assert '-o' not in ['cursor-agent', '--model', 'cursor-grok-4.6-xhigh', '-p', '--trust', '-f', ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 5.23s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 4.52s
```
- **verdict:** RED->GREEN

## E5 — the per-attempt prompt is staged for prompt delivery

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam`
- **neutralization (exact-string, count(old)=1):**

```diff
-     if result_path is None or delivery != engine_result_channel.RESULT_DELIVERY_PROMPT:
-         return opened["promptPath"], None, None
+     if True:
+         return opened["promptPath"], None, None
```

- **raw red (rc 1):**

```
E       assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_admits_typed_file_through_injected_seam
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 5.13s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 4.03s
```
- **verdict:** RED->GREEN

## E6 — missing typed file forfeits native-result-missing

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_missing_typed_file_forfeits_native_result_missing`
- **neutralization (exact-string, count(old)=1):**

```diff
-         fd = os.open(path, flags)
-     except OSError:
-         return None, "native-result-missing"
+         fd = os.open(path, flags)
+     except OSError:
+         return {}, None
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'native-result-malformed' == 'native-result-missing'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_missing_typed_file_forfeits_native_result_missing
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 5.23s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 4.59s
```
- **verdict:** RED->GREEN

## E7 — schema-invalid typed file forfeits

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_schema_invalid_file_forfeits`
- **neutralization (exact-string, count(old)=1):**

```diff
-         declared, envelope)
-     if not ok:
-         return _native_review_forfeit_with_payload_shape(
+         declared, envelope)
+     if not ok and False:
+         return _native_review_forfeit_with_payload_shape(
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'native-result-malformed' == 'native-result-schema-invalid'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_schema_invalid_file_forfeits
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 3.68s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.53s
```
- **verdict:** RED->GREEN

## E8 — secrets scrubbed from the typed result and the journal

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_typed_file_secret_scrubbed_from_result_and_journal`
- **neutralization (exact-string, count(old)=1):**

```diff
- def _scrub(text):
-     if not isinstance(text, str) or not text:
-         return text
+ def _scrub(text):
+     if not isinstance(text, str) or not text or True:
+         return text
```

- **raw red (rc 1):**

```
E       assert 'ghp_aaaaaaa...aaaaaaaaaaaa' not in '{"ok": true...": "review"}'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_typed_file_secret_scrubbed_from_result_and_journal
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.05s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.82s
```
- **verdict:** RED->GREEN

## E9 — occupied result path refuses the attempt

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_native_result_path_occupied_refuses_attempt`
- **neutralization (exact-string, count(old)=1):**

```diff
-     else:
-         return False, spawn_argv, result_path, "native-result-path-occupied"
+     else:
+         pass
```

- **raw red (rc 1):**

```
E           AssertionError: fake called too many times
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_native_result_path_occupied_refuses_attempt
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.80s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.57s
```
- **verdict:** RED->GREEN

## E9b/E15 — attempt-prompt: any pre-existing entry refuses; no-follow exclusive create

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_attempt_prompt_occupied_refuses_attempt`
- **neutralization (exact-string, count(old)=1):**

```diff
-     except OSError:
-         return None, None, "attempt-prompt-unwritable"
-     else:
-         return None, None, "attempt-prompt-occupied"
-     try:
-         fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
+     except OSError:
+         return None, None, "attempt-prompt-unwritable"
+     else:
+         pass
+     try:
+         fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
```

- **raw red (rc 1):**

```
E           AssertionError: fake called too many times
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_attempt_prompt_occupied_refuses_attempt[regular_file]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.84s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
....                                                                     [100%]
4 passed in 1.27s
```
- **verdict:** RED->GREEN

## E10 — a marker-opened cursor run is retired (chokepoint predicate)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_marker_opened_run_ends_marker_channel_retired`
- **neutralization (exact-string, count(old)=1):**

```diff
-     return _opened_channel(opened) != engine_result_channel.CHANNEL_NATIVE
- 
- 
- def _marker_channel_retired_terminal
+     return False
+ 
+ 
+ def _marker_channel_retired_terminal
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'spawn argv d...resh dispatch' == 'marker-channel-retired'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_marker_opened_run_ends_marker_channel_retired
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.43s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.25s
```
- **verdict:** RED->GREEN

## E11 — naive completedAt is probe-result-malformed

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **detector:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_validate_probe_record_refuses_naive_completed_at`
- **neutralization (exact-string, count(old)=1):**

```diff
-             if naive_check.tzinfo is None:
-                 return "probe-result-malformed:%s" % path_hint
+             if naive_check.tzinfo is None and False:
+                 return "probe-result-malformed:%s" % path_hint
```

- **raw red (rc 1):**

```
E       AssertionError: assert None == 'probe-result-malformed:/tmp/codex.json'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_validate_probe_record_refuses_naive_completed_at
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.31s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.28s
```
- **verdict:** RED->GREEN

## E12 — _seat_for_engine reads model_registry

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **detector:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_seat_for_engine_reads_model_registry_home`
- **neutralization (exact-string, count(old)=1):**

```diff
- def _seat_for_engine(engine):
-     cell = model_registry.matrix_config(PROBE_ROLE, engine)
+ def _seat_for_engine(engine):
+     cell = seat_map.matrix_config(PROBE_ROLE, engine)
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'm-y' == 'm-x'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_seat_for_engine_reads_model_registry_home
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.30s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.27s
```
- **verdict:** RED->GREEN

## E13 — journal-line-not-object at every consumer site

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_journal_line_not_object_refused_at_every_consumer_site`
- **neutralization (exact-string, count(old)=1):**

```diff
-         if not isinstance(rec, dict):
-             interior_corrupt = True
-             corruption_class_set.add(JOURNAL_LINE_NOT_OBJECT)
-             continue
+         if not isinstance(rec, dict):
+             continue
```

- **raw red (rc 1):**

```
E           AssertionError: assert 'journal-corrupt:journal-line-not-object' in ''
E            +  where '' = <built-in method get of dict object at 0x106a1a040>('resolvedInputsStatus', '')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_journal_line_not_object_refused_at_every_consumer_site[resolved_inputs_echo]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.34s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.....                                                                    [100%]
5 passed in 1.27s
```
- **verdict:** RED->GREEN

## E14-prod — retirement before argv coherence on the production spawn path

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_marker_opened_run_ends_marker_channel_retired`
- **neutralization (exact-string, count(old)=1):**

```diff
-     if _marker_channel_retired_run(opened):
-         _journal_prep_refusal(run_dir_real, attempt, "marker-channel-retired")
-         return
-     spawn_argv, coherence_err = _spawn_argv_coherence(opened, argv)
-     if coherence_err:
-         _journal_spawn_guard_refusal(run_dir_real, attempt, coherence_err)
-         return
+     spawn_argv, coherence_err = _spawn_argv_coherence(opened, argv)
+     if coherence_err:
+         _journal_spawn_guard_refusal(run_dir_real, attempt, coherence_err)
+         return
+     if _marker_channel_retired_run(opened):
+         _journal_prep_refusal(run_dir_real, attempt, "marker-channel-retired")
+         return
```

- **raw red (rc 1):**

```
E       AssertionError: assert True is not True
E        +  where True = <built-in method get of dict object at 0x1089412c0>('guardRefusal')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_marker_opened_run_ends_marker_channel_retired
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.32s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.13s
```
- **verdict:** RED->GREEN

## E14-inj — retirement on the injected spawn path

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_marker_opened_run_ends_marker_channel_retired`
- **neutralization (exact-string, count(old)=1):**

```diff
-         return False, guard_verdict["reason"]
-     if _marker_channel_retired_run(opened):
-         if not _journal_append(run_dir_real, {
+         return False, guard_verdict["reason"]
+     if _marker_channel_retired_run(opened) and False:
+         if not _journal_append(run_dir_real, {
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'spawn argv d...resh dispatch' == 'marker-channel-retired'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_marker_opened_run_ends_marker_channel_retired
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.21s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.97s
```
- **verdict:** RED->GREEN

## E16 — execution record binds the attempt prompt

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_execution_record_binds_attempt_prompt_for_cursor`
- **neutralization (exact-string, count(old)=1):**

```diff
-         if isinstance(attempt_prompt_sha, str) and attempt_prompt_sha:
-             prompt_sha256 = attempt_prompt_sha
+         if isinstance(attempt_prompt_sha, str) and attempt_prompt_sha and False:
+             prompt_sha256 = attempt_prompt_sha
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'attemptPromptPath' in {'observation': {'read': 'engaged', 'source': 'none', 'stdoutBytes': 0, 'telemetry': 'none', ...}, 'orderPromptSha256'...e70f3859668836cba538bc637811', 'recordDigest': '2558ff67d09d4590a58269cf176a7550a4b1f8b100ed78a9b208596f2d7d3e59', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_execution_record_binds_attempt_prompt_for_cursor
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.16s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.96s
```
- **verdict:** RED->GREEN

## E17 — one output instruction for prompt delivery

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_fed_prompt_has_one_output_instruction`
- **neutralization (exact-string, count(old)=1):**

```diff
-             if delivery != engine_result_channel.RESULT_DELIVERY_PROMPT:
-                 fed_prompt += _prompt_section_sep + engine_adapter.REVIEW_RESULT_CONTRACT(
+             if True:
+                 fed_prompt += _prompt_section_sep + engine_adapter.REVIEW_RESULT_CONTRACT(
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'graded stdout' not in 'You are a d...it ruling)\n'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_fed_prompt_has_one_output_instruction
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.11s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.41s
```
- **verdict:** RED->GREEN

## E18 — argv coherence: the canonical suffix is gated by delivery

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_canonical_spawn_argv_matches_opened_argv_both_engines[cursor]`
- **neutralization (exact-string, count(old)=1):**

```diff
-         if engine_result_channel.result_delivery(opened.get("engine")) != engine_result_channel.RESULT_DELIVERY_ARGV:
-             return ()
+         if engine_result_channel.result_delivery(opened.get("engine")) is None:
+             return ()
```

- **raw red (rc 1):**

```
E       AssertionError: assert ['cursor-agen...t', '-f', ...] == ['cursor-agen...t', '-f', ...]
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_canonical_spawn_argv_matches_opened_argv_both_engines[cursor]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.17s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.88s
```
- **verdict:** RED->GREEN

## R1 — marker-opened review grade collapses to the retired shape

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_review_attempt_marker_opened_returns_retired`
- **neutralization (exact-string, count(old)=1):**

```diff
-     result = _marker_arm_retired_grade()
-     result["engagement"] = engagement
-     return result
+     result = {"ok": True, "resultKind": "findings", "findings": []}
+     result["engagement"] = engagement
+     return result
```

- **raw red (rc 1):**

```
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x10a944800>('forfeit')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_review_attempt_marker_opened_returns_retired
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.07s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.85s
```
- **verdict:** RED->GREEN

## R2 — marker-opened write grade collapses to the retired shape

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_grade_write_attempt_marker_opened_returns_retired`
- **neutralization (exact-string, count(old)=1):**

```diff
-         return _admit_native_write_result(run_dir_real, attempt, opened)
- 
-     return _marker_arm_retired_grade()
+         return _admit_native_write_result(run_dir_real, attempt, opened)
+ 
+     return {"ok": True, "signal": "ok", "evidence": {}}
```

- **raw red (rc 1):**

```
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x105a3c880>('forfeit')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_grade_write_attempt_marker_opened_returns_retired
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.44s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.38s
```
- **verdict:** RED->GREEN

## R3 — marker-opened review parse returns None

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_parse_review_attempt_marker_opened_returns_none`
- **neutralization (exact-string, count(old)=1):**

```diff
-                 res["investigated"] = admitted["investigated"]
-             return res
-         return None
-     except Exception:
-         return None
+                 res["investigated"] = admitted["investigated"]
+             return res
+         return {"ok": True, "resultKind": "findings"}
+     except Exception:
+         return None
```

- **raw red (rc 1):**

```
E       AssertionError: assert {'ok': True, 'resultKind': 'findings'} is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_parse_review_attempt_marker_opened_returns_none
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.05s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.87s
```
- **verdict:** RED->GREEN

## R4 — marker-opened write parse returns None

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_parse_write_attempt_marker_opened_returns_none`
- **neutralization (exact-string, count(old)=1):**

```diff
-             return _admit_native_write_result(run_dir_real, attempt, opened)
-         return None
-     except Exception:
-         return None
+             return _admit_native_write_result(run_dir_real, attempt, opened)
+         return {"ok": True}
+     except Exception:
+         return None
```

- **raw red (rc 1):**

```
E       AssertionError: assert {'ok': True} is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_parse_write_attempt_marker_opened_returns_none
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.46s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.39s
```
- **verdict:** RED->GREEN

## R5 — marker-opened observation reads unknown

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_observation_marker_opened_read_unknown`
- **neutralization (exact-string, count(old)=1):**

```diff
-         return _engagement_with_read(engagement)
-     return _engagement_with_read(engagement)
- 
- 
- def run_execution_record(run_dir):
+         return _engagement_with_read(engagement)
+     return _engagement_with_read(engagement, result_kind="findings", items=[{"x": 1}])
+ 
+ 
+ def run_execution_record(run_dir):
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'engaged' == 'unknown'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_observation_marker_opened_read_unknown
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.07s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.96s
```
- **verdict:** RED->GREEN

## R7 — write-forfeit finalizer is a pass-through

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_finalize_write_forfeit_terminal_passthrough`
- **neutralization (exact-string, count(old)=1):**

```diff
-     """Marker-channel recoveries retired with layer 3c (#1270); the terminal passes through unchanged."""
-     return terminal
+     """Marker-channel recoveries retired with layer 3c (#1270); the terminal passes through unchanged."""
+     terminal = dict(terminal)
+     terminal["itemCheck"] = {}
+     return terminal
```

- **raw red (rc 1):**

```
E       AssertionError: assert {'attempts': ...d': True, ...} == {'attempts': ...d': True, ...}
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_finalize_write_forfeit_terminal_passthrough
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.46s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.41s
```
- **verdict:** RED->GREEN

## D1 — the result-file write is not engagement (edit-tool exclusion)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_result_file_write_is_not_engagement`
- **neutralization (exact-string, count(old)=1):**

```diff
-             if isinstance(native_result_path, str):
-                 exclude = (native_result_path,)
+             if isinstance(native_result_path, str) and False:
+                 exclude = (native_result_path,)
```

- **raw red (rc 1):**

```
E       assert 1 == 0
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_result_file_write_is_not_engagement
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.15s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 1.06s
```
- **verdict:** RED->GREEN

## D2 — unreadable staged prompt is prompt-unreadable

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stage_attempt_prompt_unreadable_prompt_refuses_prompt_unreadable`
- **neutralization (exact-string, count(old)=1):**

```diff
-         return None, None, "prompt-unreadable"
+         return None, None, "native-schema-unreadable"
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'native-schema-unreadable' == 'prompt-unreadable'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stage_attempt_prompt_unreadable_prompt_refuses_prompt_unreadable
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.10s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.93s
```
- **verdict:** RED->GREEN

## D3 — attemptPromptSha256 from the written bytes, always present

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_engine_started_always_carries_attempt_prompt_sha_for_cursor`
- **neutralization (exact-string, count(old)=1):**

```diff
-     return path, hashlib.sha256(content.encode("utf-8")).hexdigest(), None
+     return path, None, None
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'attemptPromptSha256' in {'at': 1789839047.377043, 'attempt': 1, 'attemptPromptPath': '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T...ed_always_car0/sanitized-temp-base/superheroes-dispatch-review-m9msjyfj/prompt-attempt-1.md', 'enginePgid': 20021, ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_engine_started_always_carries_attempt_prompt_sha_for_cursor
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.09s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.97s
```
- **verdict:** RED->GREEN

## D4 — the preflight probe's cursor no-op argv matches the adapter

- **site:** `plugins/superheroes/lib/preflight_probe.py`
- **detector:** `plugins/superheroes/lib/tests/test_preflight_probe.py::test_probe_argv_drift_guard_real_values_pass`
- **neutralization (exact-string, count(old)=1):**

```diff
-                 "-f", "--sandbox", "enabled")
+                 "--mode", "plan")
```

- **raw red (rc 1):**

```
E       AssertionError: probe argv must equal builder minus ['--output-format', 'stream-json']: builder=['cursor-agent', '--model', 'composer-2.5', '-p', '--trust', '-f', '--sandbox', 'enabled', '--output-format', 'stream-json'] probe=['cursor-agent', '--model', 'composer-2.5', '-p', '--trust', '--mode', 'plan']
E       assert ['cursor-agen...t', '-f', ...] == ['cursor-agen...'--mode', ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_preflight_probe.py::test_probe_argv_drift_guard_real_values_pass
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.28s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.25s
```
- **verdict:** RED->GREEN

## F1 — write runs get the in-addition clause (run-kind-aware contract)

- **site:** `plugins/superheroes/lib/engine_result_channel.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_result_channel.py::test_file_result_contract_write_permits_worktree_edits`
- **neutralization (exact-string, count(old)=1):**

```diff
-     elif run_kind == RUN_KIND_WRITE:
-         edit_clause = (
+     elif run_kind == RUN_KIND_WRITE and False:
+         edit_clause = (
```

- **raw red (rc 1):**

```
E           ValueError: unknown run_kind 'write'; expected 'review' or 'write'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_file_result_contract_write_permits_worktree_edits
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.27s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.22s
```
- **verdict:** RED->GREEN

## F2 — round orders: engine-seat delivery prose is channel-neutral

- **site:** `plugins/superheroes/lib/round_orders.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_orders.py::test_engine_stdout_channel_panel_order_is_result_channel_neutral`
- **neutralization (exact-string, count(old)=1):**

```diff
- _RESULT_CHANNEL_NEUTRAL_DELIVERY = (
-     "Deliver the object on the runner's declared result channel: the runner appends "
+ _RESULT_CHANNEL_NEUTRAL_DELIVERY = (
+     "Emit the object as your final stdout with nothing after it: the runner appends "
```

- **raw red (rc 1):**

```
E       AssertionError: assert 'final stdout' not in 'you are rev... sandbox).\n'
E         
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_orders.py::test_engine_stdout_channel_panel_order_is_result_channel_neutral
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.17s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.16s
```
- **verdict:** RED->GREEN

## F3 — the probe prompt is channel-neutral

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **detector:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_prompt_is_result_channel_neutral`
- **neutralization (exact-string, count(old)=1):**

```diff
-     "on the runner's declared result channel (the contract appended at the end of this prompt "
+     "with nothing before or after the object (the contract appended at the end of this prompt "
```

- **raw red (rc 1):**

```
E       assert "runner's declared result channel" in 'Verify exactly one claim and respond with exactly one JSON object.\n\nClaim: The working directory you were given con...pty.\n\nWhen a result schema was supplied to you, it governs the outer shape; the verdict fields above are the same.\n'
E        +  where 'Verify exactly one claim and respond with exactly one JSON object.\n\nClaim: The working directory you were given con...pty.\n\nWhen a result schema was supplied to you, it governs the outer shape; the verdict fields above are the same.\n' = CP._PROBE_PROMPT
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_prompt_is_result_channel_neutral
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.24s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.23s
```
- **verdict:** RED->GREEN

## F6 — a rewritten staged prompt refuses prompt-tampered

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_prompt_tamper_on_retry_refuses_prompt_tampered`
- **neutralization (exact-string, count(old)=1):**

```diff
-         if hashlib.sha256(prompt_bytes).hexdigest() != bound_sha:
-             return None, None, "prompt-tampered"
+         if hashlib.sha256(prompt_bytes).hexdigest() != bound_sha and False:
+             return None, None, "prompt-tampered"
```

- **raw red (rc 1):**

```
E       assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_prompt_tamper_on_retry_refuses_prompt_tampered
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.12s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.93s
```
- **verdict:** RED->GREEN

## F7 — two-pass exclusion: a late-discovered result write is excluded

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_cursor_tool_calls_excludes_late_discovered_result_path`
- **neutralization (exact-string, count(old)=1):**

```diff
-         for cid, _tool_call in events:
-             if cid not in excluded_call_ids:
-                 call_ids.add(cid)
+         for cid, _tool_call in events:
+             call_ids.add(cid)
```

- **raw red (rc 1):**

```
E       assert 1 == 0
E        +  where 1 = <function cursor_tool_calls at 0x102071a60>('{"type": "tool_call", "call_id": "w1", "subtype": "started"}\n{"type": "tool_call", "call_id": "w1", "subtype": "comp.../com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1397/test_cursor_tool_calls_exclude0/native-result-1.json"}}}}', exclude_paths=('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1397/test_cursor_tool_calls_exclude0/native-result-1.json',))
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_cursor_tool_calls_excludes_late_discovered_result_path
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.41s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.38s
```
- **verdict:** RED->GREEN

## P1 — probe telemetry leg fails when the only tool call is the result write

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_result_production_ok_but_telemetry_fails_when_only_the_result_write`
- **neutralization (exact-string, count(old)=1):**

```diff
-             tool_calls = engine_adapter.cursor_tool_calls(stdout, exclude_paths=exclude)
+             tool_calls = engine_adapter.cursor_tool_calls(stdout)
```

- **raw red (rc 1):**

```
E       assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_result_production_ok_but_telemetry_fails_when_only_the_result_write
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.26s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.22s
```
- **verdict:** RED->GREEN

## F8 — a shell call that delivers the result is excluded

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector:** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_cursor_tool_calls_excludes_result_path`
- **neutralization (exact-string, count(old)=1):**

```diff
-     """True when a shell-style tool call's command mentions an excluded path. Never raises."""
-     try:
+     """True when a shell-style tool call's command mentions an excluded path. Never raises."""
+     return False
+     try:
```

- **raw red (rc 1):**

```
E       assert 1 == 0
E        +  where 1 = <function cursor_tool_calls at 0x103a49a60>('{"type": "tool_call", "call_id": "s2", "subtype": "started", "tool_call": {"shellToolCall": {"args": {"command": "pri.../com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1403/test_cursor_tool_calls_exclude0/native-result-1.json"}}}}', exclude_paths=('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1403/test_cursor_tool_calls_exclude0/native-result-1.json',))
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_cursor_tool_calls_excludes_result_path
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.55s
```
- **restore:** the inverse edit; `git status --porcelain` empty: True
- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.47s
```
- **verdict:** RED->GREEN
