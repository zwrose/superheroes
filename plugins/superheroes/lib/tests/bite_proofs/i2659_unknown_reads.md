# Bite-proof record — a missing evidence field or unreadable record reads as unknown, never clean (#2659)

**Provenance:** implementer seat (claude, sonnet), dispatched by the Workhorse orchestrator as WO-A of issue 2659. Detector file: `plugins/superheroes/lib/tests/test_unknown_reads_2659.py` (e8 also names one node of `test_review_measures_by_release_2498.py`), unedited between each red and its green. Every entry is a targeted, reversible edit made and undone with the edit tool, on the uncommitted worktree over base head `7d10cb4e` (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <node ids or file> -q -p no:randomly [--tb=line] -k "<expr>"`; the last line of each capture is the run's summary line (a failing run's exit status is 1, a passing run's 0). The e1 red and green runs use the default traceback; the e2 first red run used it too, but the harness truncated that capture (5278 characters elided in the middle), so e2's recorded red is a second red run of the same node with `--tb=line`, and every later run uses `--tb=line` to keep the capture whole. Redaction: the worktree path is shown as `<worktree>`, the pytest temp directory as `<tmp>`, and the `UV_NATIVE_TLS` deprecation line `uv` prints first is dropped; a few very long lines were shortened by the harness itself with `...` and are quoted as shown. No secret, token, URL or personal data appears, so nothing else is redacted.

## e1. A start record with no `unattributed` key is not read (`cloud_check._start_record`)

- **Axis:** a record with no `unattributed` list (the start hook always writes one) reads as unreadable, never whole.
- **Detector:** `test_a_start_record_with_no_unattributed_key_fails_the_start_part_as_unread` (its healthy twin `test_the_same_start_record_with_an_empty_unattributed_list_still_reads` passes either way).
- **Neutralization:** `unattributed = record.get("unattributed")` became `unattributed = record.get("unattributed", [])`.
- **Selection:** `-k "no_unattributed_key"`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_start_record_with_no_unattributed_key_fails_the_start_part_as_unread __

tmp_path = PosixPath('<tmp>/test_a_start_record_with_no_un0')

    def test_a_start_record_with_no_unattributed_key_fails_the_start_part_as_unread(tmp_path):
        local, cloud = _pair(tmp_path)
        env = _start_env_without("unattributed")
        assert HOOK_PART in json.loads(env[cloud_pass.START_COPY_ENV])["parts"]
        # edge A1.a: key absent -> the record is not whole
>       assert CC._start_parts(env) is None
E       assert {'hooks/session_start.py': [{'version': '0.52.1', 'commit': '7d10cb4ee5eac77aaf78ba7bc274f403f6b40cd1', 'sha256': '993...e5eac77aaf78ba7bc274f403f6b40cd1', 'sha256': '4ee38d715bcee428b87a4f91b83d73129022b97cc4bc1145774202b979ee7c70'}], ...} is None
E        +  where {'hooks/session_start.py': [{'version': '0.52.1', 'commit': '7d10cb4ee5eac77aaf78ba7bc274f403f6b40cd1', 'sha256': '993...e5eac77aaf78ba7bc274f403f6b40cd1', 'sha256': '4ee38d715bcee428b87a4f91b83d73129022b97cc4bc1145774202b979ee7c70'}], ...} = <function _start_parts at 0x7fcbe22239c0>({'SUPERHEROES_START_COPY': '{"schema": "start-copy/1", "session": "session-fixture", "roots": ["/home/user/superheroes...ib/store.py": [0], "lib/store_core.py": [0], "rubric/covenant.md": [0]}}', 'CLAUDE_CODE_SESSION_ID': 'session-fixture'})
E        +    where <function _start_parts at 0x7fcbe22239c0> = CC._start_parts

<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_start_record_with_no_unattributed_key_fails_the_start_part_as_unread
1 failed, 67 deselected in 1.29s
```

**Restore:** the inverse edit put the `.get("unattributed")` line back.

**Restore receipt:** `plugins/superheroes/lib/cloud_check.py:476` reads `    unattributed = record.get("unattributed")`.

**Raw green:**

```
.                                                                        [100%]
1 passed, 67 deselected in 1.55s
```

## e2. The fix-batch reader requires a `findings` list (`loop_state._blocking_fixed_from_fix_batch`)

- **Axis:** a fix batch with no findings list (a dict without `findings`, one whose `findings` is not a list) or a non-dict entry is unreadable, never zero blocking fixes.
- **Detector:** `test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file` (8 parameters).
- **Neutralization:** `return _count_blocking(_findings_list(data, path, "fix-batch"))` became `return _count_blocking(data if isinstance(data, list) else data.get("findings", []))`.
- **Selection:** `-k "test_a_fix_batch_with_no_findings_list"`.

**Raw red** (second red run, `--tb=line`; the first run's capture was truncated by the harness):

```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."}
    assert 'fix-batch.json' in "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'fix-batch.json' in "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'fix-batch.json' in "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('int' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'fix-batch.json' in "could not read the round artifacts ('int' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('int' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'fix-batch.json' in "could not read the round artifacts ('NoneType' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[{}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[{'other': []}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[{'findings': {}}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[{'findings': None}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[{'findings': 'x'}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file['x']
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[7]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file[None]
8 failed, 60 deselected in 0.80s
```

Note: three parameters (`{}`, `{'other': []}`, `{'findings': {}}`) show the silent wrong gate (`exit_clean`), the A2.a and A2.b edges the old code read as clean; the other five already ended in `review` through the old handler but without the file name, so they bite on the naming assertion only.

**Restore:** the inverse edit put the `_findings_list(...)` call back.

**Restore receipt:** `plugins/superheroes/lib/loop_state.py:61` reads `    return _count_blocking(_findings_list(data, path, "fix-batch"))`.

**Raw green:**

```
........                                                                 [100%]
8 passed, 60 deselected in 0.85s
```

## e3. The compiled-artifact reader requires a `findings` list (`loop_state._blocking_present_from_compiled`)

- **Axis:** a compiled file with no findings list (a dict without `findings`, one whose `findings` is not a list) or a non-dict entry is unreadable, never zero blocking findings.
- **Detector:** `test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file` (5 parameters).
- **Neutralization:** `return _count_blocking(_findings_list(data, path, "compiled"))` became `return _count_blocking(data if isinstance(data, list) else data.get("findings", []))`.
- **Selection:** `-k "test_a_compiled_file_with_no_findings_list"`.

**Raw red:**

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."}
    assert 'compiled.json' in "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'compiled.json' in "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file[{}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file[{'other': []}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file[{'findings': {}}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file[{'findings': None}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file['x']
5 failed, 63 deselected in 0.86s
```

**Restore:** the inverse edit put the `_findings_list(...)` call back.

**Restore receipt:** `plugins/superheroes/lib/loop_state.py:98` reads `    return _count_blocking(_findings_list(data, path, "compiled"))`.

**Raw green:**

```
.....                                                                    [100%]
5 passed, 63 deselected in 0.87s
```

## e4. The resolutions reader requires a `resolutions` list (`loop_state._skipped_blocking_from_resolutions`)

- **Axis:** a resolutions file with no `resolutions` list is unreadable, never zero skips.
- **Detector:** `test_resolutions_with_no_resolutions_list_reviews_and_names_the_file` (7 parameters).
- **Neutralization:** the three lines `rows = data.get("resolutions") if isinstance(data, dict) else None` / `if not isinstance(rows, list):` / `raise ValueError("resolutions %s: no resolutions list" % path)` became the one line `rows = data.get("resolutions", [])`.
- **Selection:** `-k "test_resolutions_with_no_resolutions_list"`.

**Raw red:**

```
FFFF.FF                                                                  [100%]
=================================== FAILURES ===================================
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."}
    assert 'resolutions.json' in "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object is not iterable) — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('list' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'resolutions.json' in "could not read the round artifacts ('list' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('list' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'resolutions.json' in "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_resolutions_with_no_resolutions_list_reviews_and_names_the_file[{}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_resolutions_with_no_resolutions_list_reviews_and_names_the_file[{'other': []}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_resolutions_with_no_resolutions_list_reviews_and_names_the_file[{'resolutions': {}}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_resolutions_with_no_resolutions_list_reviews_and_names_the_file[{'resolutions': None}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_resolutions_with_no_resolutions_list_reviews_and_names_the_file[[]]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_resolutions_with_no_resolutions_list_reviews_and_names_the_file['x']
6 failed, 1 passed, 61 deselected in 0.80s
```

Note: the one parameter that passes under this neutralization is `{'resolutions': 'x'}` (iterating a string reaches the per-row guard, which still raises naming the file); it does not discriminate e4 and is covered by the e5 guard.

**Restore:** the inverse edit put the three lines back.

**Restore receipt:** `plugins/superheroes/lib/loop_state.py:72-74` read `    rows = data.get("resolutions") if isinstance(data, dict) else None` / `    if not isinstance(rows, list):` / `        raise ValueError("resolutions %s: no resolutions list" % path)`.

**Raw green:**

```
.......                                                                  [100%]
7 passed, 61 deselected in 0.78s
```

## e5. Every resolution row needs a string `action` (`loop_state._skipped_blocking_from_resolutions`)

- **Axis:** a resolution row with no string `action` is unreadable, never a row that skipped nothing.
- **Detector:** `test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch` (6 parameters).
- **Neutralization:** the two lines `if not (isinstance(r, dict) and isinstance(r.get("action"), str)):` / `raise ValueError("resolutions %s: a row with no action" % path)` were removed.
- **Selection:** `-k "test_a_resolution_row_with_no_string_action"`.

**Raw red:**

```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
    assert ('exit_clean' == 'review'
      
      - review
      + exit_clean)
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:104: AssertionError: {'action': 'exit_clean', 'mandatory': False, 'reason': 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.'}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'resolutions.json' in "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('str' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
E   AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
    assert 'resolutions.json' in "could not read the round artifacts ('NoneType' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:105: AssertionError: {'action': 'review', 'mandatory': True, 'reason': "could not read the round artifacts ('NoneType' object has no attribute 'get') — defaulting to another review round rather than risk a premature exit."}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch[{}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch[{'severity': 'Critical'}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch[{'action': 5}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch[{'action': None}]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch['skip']
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch[None]
6 failed, 62 deselected in 0.82s
```

**Restore:** the inverse edit put the two lines back.

**Restore receipt:** `plugins/superheroes/lib/loop_state.py:78-79` read `        if not (isinstance(r, dict) and isinstance(r.get("action"), str)):` / `            raise ValueError("resolutions %s: a row with no action" % path)`.

**Raw green:**

```
......                                                                   [100%]
6 passed, 62 deselected in 0.87s
```

## e6. A final confirmation needs a whole receipt context (`panel_tally._valid_final_receipt`)

- **Axis:** a final confirmation with no receipt context (none, not a dict, no artifact, no decision-id list) has nothing to match the receipt against, so it is no certification.
- **Detector:** `test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify` (9 parameters; `none`, `empty`, `no-artifact`, `no-ids` are the A3.a, A3.b, A3.c cases).
- **Neutralization:** the context-presence block (`ctx = receipt_context` / the `isinstance(ctx, dict) ...` return-False guard) and the three checks after it became the base's `ctx = receipt_context or {}`, with `if ctx.get("artifact") and receipt.get("artifact") != ctx.get("artifact")` and `needed_ids = set(ctx.get("coverageDecisionIds") or [])` / `if needed_ids and not needed_ids.issubset(...)` skips; the id-entry guard line (e7's) was kept, reading `ctx.get("coverageDecisionIds") or []`.
- **Selection:** `-k "no_whole_receipt_context"`.

**Raw red:**

```
FFFFFFF.F                                                                [100%]
=================================== FAILURES ===================================
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
E   AttributeError: 'str' object has no attribute 'get'
<worktree>/plugins/superheroes/lib/tests/../panel_tally.py:232: AttributeError: 'str' object has no attribute 'get'
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
E   AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
      
      At index 0 diff: 'clean' != 'cannot-certify'
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:226: AssertionError: assert ('clean', 'high', []) == ('cannot-certify', 'low', [])
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[none]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[list]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[str]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[empty]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[no-artifact]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[no-ids]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[blank-artifact]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify[null-ids]
8 failed, 1 passed, 59 deselected in 0.83s
```

Note: the one parameter that passes under this neutralization is `int-artifact` (`artifact: 5` never equals the receipt's string artifact, so the kept artifact-equality check still fails closed); it does not discriminate e6.

**Restore:** the inverse edit put the base-plus-fix context block back.

**Restore receipt:** `plugins/superheroes/lib/panel_tally.py:230-240` read `    ctx = receipt_context` / `    if not (isinstance(ctx, dict) and isinstance(ctx.get("artifact"), str) and ctx["artifact"]` / `            and isinstance(ctx.get("coverageDecisionIds"), list)):` / `        return False` / (the e7 axis comment) / `    if not (_ids(ctx["coverageDecisionIds"]) and _ids(receipt.get("coverageDecisionIds"))):` / `        return False` / `    if receipt.get("artifact") != ctx["artifact"]:` / `        return False` / `    if not set(ctx["coverageDecisionIds"]).issubset(set(receipt["coverageDecisionIds"])):` / `        return False`.

**Raw green:**

```
.........                                                                [100%]
9 passed, 59 deselected in 0.85s
```

## e7. Decision ids must be non-empty strings (`panel_tally._valid_final_receipt._ids`)

- **Axis:** a decision id that is not a non-empty string, in the context or the receipt, is unreadable, never a match.
- **Detector:** `test_context_decision_ids_that_are_not_non_empty_strings_cannot_certify_and_never_raise` and `test_receipt_decision_ids_that_are_not_non_empty_strings_cannot_certify` (12 parameters between them; the `[{}]` parameter of each is the one that bites).
- **Neutralization:** `return isinstance(value, list) and all(isinstance(i, str) and i for i in value)` became `return isinstance(value, list)`.
- **Selection:** `-k "decision_ids_that_are_not"`.

**Raw red:**

```
F.....F.....                                                             [100%]
=================================== FAILURES ===================================
E   TypeError: unhashable type: 'dict'
<worktree>/plugins/superheroes/lib/tests/../panel_tally.py:239: TypeError: unhashable type: 'dict'
E   TypeError: unhashable type: 'dict'
<worktree>/plugins/superheroes/lib/tests/../panel_tally.py:239: TypeError: unhashable type: 'dict'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_context_decision_ids_that_are_not_non_empty_strings_cannot_certify_and_never_raise[[{}]]
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_receipt_decision_ids_that_are_not_non_empty_strings_cannot_certify[[{}]]
2 failed, 10 passed, 56 deselected in 0.81s
```

Note, the cases this detector does not discriminate (named, not hidden): the other ten parameters (`[None]`, `[5]`, `[""]`, a bare string, a dict or `None` as the list) pass under the neutralization, because an unhashable-free wrong id already fails the subset check (`{None}`, `{5}` or `{""}` is no subset of `{"RCD-1"}`), and a non-list is refused by the list check kept in the guard. Only an unhashable entry (`{}`) bites here, as a TypeError instead of `cannot-certify`.

**Restore:** the inverse edit put the string-entry check back.

**Restore receipt:** `plugins/superheroes/lib/panel_tally.py:227` reads `        return isinstance(value, list) and all(isinstance(i, str) and i for i in value)`.

**Raw green:**

```
............                                                             [100%]
12 passed, 56 deselected in 0.84s
```

## e8. Absent silence ends beside a row that did not run read unresolved (`review_measures._release_measures`)

- **Axis:** the writers omit the ends when empty, so absent ends beside a row that did not run, in a session that did not certify, read unresolved, never clear.
- **Detector:** `test_absent_ends_beside_a_row_that_did_not_run_in_a_session_that_did_not_clear_read_unresolved` and the updated session s4 of `test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered` (in `test_review_measures_by_release_2498.py`).
- **Neutralization:** the three lines `absent = "silenceWatchdogEnds" not in last` / `unseen = absent and bool(not_run) and not review_record.cleared(last.get("status"))` / `ends = [] if absent else last["silenceWatchdogEnds"]` became `unseen = False` / `ends = last.get("silenceWatchdogEnds", [])`.
- **Selection:** the two node ids named above.

**Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'voided': 0,...'sessions': 1} == {'voided': 0,...'sessions': 1}
      
      Omitting 2 identical items, use -vv to show
      Differing items:
      {'unresolved': 0} != {'unresolved': 1}
      Use -v to get more diff
<worktree>/plugins/superheroes/lib/tests/test_unknown_reads_2659.py:266: AssertionError: assert {'voided': 0,...'sessions': 1} == {'voided': 0,...'sessions': 1}
E   AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
      
      Omitting 1 identical items, use -vv to show
      Differing items:
      {'byRelease': {'0.50.0': {'voided': 1, 'unresolved': 0, 'sessions': 5}}} != {'byRelease': {'0.50.0': {'voided': 1, 'unresolved': 1, 'sessions': 5}}}
<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:92: AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unknown_reads_2659.py::test_absent_ends_beside_a_row_that_did_not_run_in_a_session_that_did_not_clear_read_unresolved
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered
2 failed in 0.84s
```

**Restore:** the inverse edit put the three lines back.

**Restore receipt:** `plugins/superheroes/lib/review_measures.py:345-347` read `            absent = "silenceWatchdogEnds" not in last` / `            unseen = absent and bool(not_run) and not review_record.cleared(last.get("status"))` / `            ends = [] if absent else last["silenceWatchdogEnds"]`.

**Raw green:**

```
..                                                                       [100%]
2 passed in 0.84s
```
