# WO1 #1526 — dash-free cursor result handoff bite-proof

## E1 — prompt contract uses handoff path (`engine_dispatch.py` `_stage_attempt_prompt`)

- **Axis:** dash-`--` run dirs get a dash-free path in the typed-file contract so collapsed writers still grade.
- **Neutralization:** removed the `re.search(r"-{2,}", result_path)` handoff block; `file_result_contract` always receives `result_path` (same as unmodified base).
- **Detector red (`test_cursor_write_dashdash_run_dir_real_child_grades_collapsed_writer`):**
```
FAILED ...::test_cursor_write_dashdash_run_dir_real_child_grades_collapsed_writer
>       assert grade["ok"] is True
E       KeyError: 'ok'
```
- **Restore:** reinstated full handoff block before `file_result_contract`.
- **Green:** included in final 12-test green run.

## E2 — refuse when no safe handoff base

- **Neutralization:** `if base is None: pass` (no `native-result-path-unsafe` refusal).
- **Detector red (`test_dashdash_no_safe_base_refuses_before_spawn`):**
```
>       assert fake.calls == []
E       AssertionError: assert [{'argv': ['cursor-agent', ...}] == []
```
- **Restore:** `if base is None: return None, None, "native-result-path-unsafe", None`.

## E3 — refuse on `os.symlink` OSError

- **Neutralization:** on `OSError` from `os.symlink`, do not return; if `link is None` after loop, fall through without handoff.
- **Detector red (`test_dashdash_symlink_oserror_refuses_before_spawn`):**
```
>       assert fake.calls == []
E       AssertionError: assert [{'argv': ['cursor-agent', ...}] == []
```
- **Restore:** `except OSError: return None, None, "native-result-path-unsafe", None` and `if link is None: return ...`.

## E4 — unlink handoff on later staging refusal

- **Neutralization:** `_refuse()` no longer calls `_release_result_handoff`.
- **Detector red (`test_dashdash_link_removed_on_later_staging_refusal`):**
```
>       assert list(os.listdir(handoff_base)) == []
E       AssertionError: assert ['superheroes-result-23796164856ea288'] == []
```
- **Restore:** `_refuse` again calls `_release_result_handoff(handoff_path, run_dir_real)`.

## E5 — release after attempt ends

- **Neutralization:** `_release_result_handoff` immediate `return` (no-op).
- **Detector red (`test_dashdash_link_released_after_attempt`):**
```
>       assert list(os.listdir(handoff_base)) == []
E       AssertionError: assert ['superheroes-result-b7af7982fce9cbab'] == []
```
- **Restore:** full `_release_result_handoff` body.

## E6 — release readlink guard

- **Neutralization:** removed `if os.readlink(link) != run_dir_real: return` before `os.unlink(link)`.
- **Detector red (`test_release_leaves_foreign_link`):**
```
>       assert link.is_symlink()
E       AssertionError: assert False
```
- **Restore:** readlink equality check restored.

## E7 — handoff only for prompt delivery

- **Neutralization:** duplicate handoff symlink creation in `_spawn_native_result_argv` for every delivery when path contains `--`.
- **Detector red (`test_codex_dashdash_run_dir_creates_no_link`):**
```
>       assert list(os.listdir(handoff_base)) == []
E       AssertionError: assert ['superheroes-result-ed1117c754719817'] == []
```
- **Restore:** removed spawn-path handoff block.

## E8 — engagement excludes handoff path

- **Neutralization:** stopped appending `native_result_handoff_path` to `exclude_paths` in `_review_attempt_engagement`.
- **Detector red (`test_cursor_engagement_excludes_handoff_path`):**
```
>       assert with_handoff["toolCalls"] == 0
E       assert 1 == 0
```
- **Restore:** `exclude_paths.append(native_result_handoff_path)` when str.
