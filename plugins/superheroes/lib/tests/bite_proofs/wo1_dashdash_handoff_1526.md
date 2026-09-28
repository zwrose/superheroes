# #1526 bite-proof — the dash-free cursor result handoff

Per-element bite-proof for the handoff in `plugins/superheroes/lib/engine_dispatch.py`. Cursor names its result file in the prompt, and a result path that contains a run of two or more dashes is handed to the engine as a dash-free symlink to the run dir. For each element, the production code was neutralized with one targeted edit in a detached probe worktree. The named tests ran alone and went red on the guarded axis, and the edit was then reverted with the inverse edit. The detectors were unedited throughout.

**Heads proven:** `7d8e602c` (E2–E6, E8; those detectors did not change afterwards) and `7cfc810b`, the head after the test fixes (E1, E7, E9–E11). After the last revert in each probe worktree, `git status --porcelain` was empty, and the 13 tests below ran green at `7cfc810b`.

**Provenance:** the orchestrator ran these proofs (workhorse, Claude Opus 5.5). They replace the implementer's first record. That record's E1 red was `KeyError: 'ok'`, off the axis. Its injected-seam and codex-scope tests stayed green under their neutralizations, so both detectors were rebuilt before this record.

**Command:** each run used the exact node ids below, never `-k`:

```
scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <node ids> -q -p no:cacheprovider
```

Test files: `D` = `plugins/superheroes/lib/tests/test_engine_dispatch.py`, `W` = `plugins/superheroes/lib/tests/test_engine_dispatch_write.py`.

## Summary

| ID | Guarded element | Neutralization | Proving node(s) | Exact red |
|---|---|---|---|---|
| E1 | `_stage_attempt_prompt` hands the link path when the result path has a dash run. Neutralized, this is the base behaviour | `if False and re.search(r"-{2,}", result_path):` | `D::test_cursor_write_dashdash_run_dir_real_child_grades_collapsed_writer`; `D::test_cursor_review_dashdash_run_dir_grades`; `W::test_cursor_write_dashdash_injected_seam_ok`; `D::test_stage_prompt_names_dash_free_handoff_path` | `AssertionError: {'forfeit': True, 'reason': 'forfeited', 'detail': 'native-result-missing'}` (real child); `assert ('native-result-missing' is None)` (review); `{'ok': False, 'terminal': True, 'reason': 'forfeited', 'attempts': 2, ...}` (injected); `KeyError: 'nativeResultHandoffPath'` (staging) |
| E2 | no dash-free base → refuse before spawn | skip the handoff when the base is `None` (`and _result_handoff_base() is not None` on the guard) | `W::test_dashdash_no_safe_base_refuses_before_spawn` | `assert [{'argv': ['cursor-agent', ...}] == []` (the engine ran) |
| E3 | `os.symlink` error → refuse before spawn | `except OSError: break`; `if link is None: link = run_dir_real`. This alone stays **green**, because E9's final check refuses the resulting `--` path with the same token. With E9 also disabled: | `W::test_dashdash_symlink_oserror_refuses_before_spawn` | `assert [{'argv': ['cursor-agent', ...}] == []` |
| E4 | a later staging refusal removes the just-made link | `_refuse()` no longer calls `_release_result_handoff` | `W::test_dashdash_link_removed_on_later_staging_refusal` | `assert ['superheroes-result-cce0a31789a4198b'] == []` |
| E5 | the real child releases the link after `attempt-ended` | release call → `pass` | `D::test_dashdash_link_released_after_attempt` | `assert ['superheroes-result-c75d531a001380c7'] == []` |
| E6 | release removes only a symlink that still points at this run dir | `if False and os.readlink(link) != run_dir_real:` | `D::test_release_leaves_foreign_link` | `assert False` where `False = …/superheroes-result-deadbeef').is_symlink` |
| E7 | only prompt delivery (cursor) gets a handoff | the early return drops `or delivery != RESULT_DELIVERY_PROMPT` | `W::test_codex_dashdash_run_dir_creates_no_link` | `assert 'nativeResultHandoffPath' not in {'kind': 'engine-started', ...}` |
| E8 | the cursor engagement count excludes the handoff path | `if False and isinstance(native_result_handoff_path, str):` | `D::test_cursor_engagement_excludes_handoff_path` | `assert 1 == 0` |
| E9 | a handed path that still has a dash run refuses before spawn | `if False and re.search(r"-{2,}", handed):` | `W::test_dashdash_handed_path_with_dash_run_refuses` | `assert [{'argv': ['cursor-agent', ...}] == []` |
| E10 | the injected seam releases the link after `attempt-ended` | the release call at the end of `_execute_injected_attempt` removed | `W::test_cursor_write_dashdash_injected_seam_ok` | `assert ['superheroes-result-9b55ece5d0a907a5'] == []` |
| E11 | the review grade path threads the handoff path into the engagement count | `_grade_review_attempt` passes `native_result_handoff_path=None` | `D::test_cursor_review_dashdash_run_dir_grades` | `assert 1 == 0` (`res["engagement"]["toolCalls"]`) |
| E12 | `_result_handoff_base` skips a dashed tempdir and falls back to `/tmp` | drop `not re.search(r"-{2,}", base)` in the candidate loop | `D::test_result_handoff_base_skips_dashed_tempdir_falls_back_to_tmp` | `AssertionError` on `== os.path.realpath("/tmp")` (returns the dashed tempdir) |
| E13 | `_result_handoff_base` returns `None` when every candidate is unsafe | `return candidates[0]` immediately after building `candidates` (skip `isdir` and dash filter) | `D::test_result_handoff_base_returns_none_when_no_safe_candidate` | `assert None is None` fails (returns a dashed path) |

## Masking and gaps, stated

- **E3 is guarded jointly with E9.** A symlink failure that fell through to the canonical path would still be refused by E9's check with the same token. The joint neutralization is the red above.
- **The release helper's `S_ISLNK` check** is not independently provable. Without it, `os.readlink` on a regular file raises `OSError`, which the helper swallows, so the file survives either way.
- **Untested threading sites:** `_parse_review_attempt` and `_observation_from_attempt` pass the handoff path into the engagement count the same way `_grade_review_attempt` does (E11), but no test targets them. Also untested: the release calls on the error paths (config dir unusable, spawn-argv journal failure, `Popen` failure, `engine-started` journal failure). A missed release on those paths leaves one dangling symlink in the temp dir.

## Green

The original 13 integration nodes ran green together at `7cfc810b` after the last revert (`13 passed`). With E12–E13, add `D::test_result_handoff_base_skips_dashed_tempdir_falls_back_to_tmp`, `D::test_result_handoff_base_returns_plain_tempdir_when_dash_free`, and `D::test_result_handoff_base_returns_none_when_no_safe_candidate` (`16 passed` total).
