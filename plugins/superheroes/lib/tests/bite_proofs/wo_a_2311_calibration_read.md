# Bite-proof record: WO-A (#2311), the runner records each seat's calibration read

Detector: `plugins/superheroes/lib/tests/test_calibration_read.py`, run against
`plugins/superheroes/lib/calibration_read.py` and the wiring in
`plugins/superheroes/lib/engine_dispatch.py`.

Declared guarded-element set (from the order): E1 to E8, one neutralization and one red each.
Every neutralization is a targeted Edit and was undone by the inverse Edit. Every red ran the
detector unedited, by exact test node id, under `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/shpyc -m pytest <node> -q`.
Captures below are the tail of the pytest output as seen (the `UV_NATIVE_TLS` warning line is
dropped from each). Nothing in them is a credential or a private URL; no redaction was needed.
The restore receipt for each element is the restored line quoted back from the file after the
inverse Edit. A post-restore `git status --porcelain` was not run (see the findings in the
return: the compound command that carried it was held for approval).

## E1: codex `exit_code == 0` gate

- Guarded element: `calibration_read.py` `_exit_outcome`, line 136. Axis: a codex command counts
  as successful only on an integer exit code of exactly 0.
- Neutralization: `return _OK if code == 0 else _FAILED` became `return _OK` (any int accepted).
- Detector: `test_codex_nonzero_exit_records_not_read_while_a_sibling_success_records_read`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_codex_nonzero_exit_records_not_read_while_a_sibling_success_records_read _
    def test_codex_nonzero_exit_records_not_read_while_a_sibling_success_records_read(calib):
        stdout = _codex_stream(
            _codex_cmd("a", "cat %s" % calib.core, exit_code=1),
            _codex_cmd("b", "cat %s" % calib.layer, exit_code=0),
        )
>       assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
            "core": "not-read", "review-crew": "read", "CLAUDE.md": "not-read"}
E       AssertionError: assert {'core': 'rea...': 'not-read'} == {'core': 'not...': 'not-read'}
E         Differing items:
E         {'core': 'read'} != {'core': 'not-read'}
1 failed in 0.21s
```

- Restore: inverse Edit. Restore receipt (Grep of the file after): `136:        return _OK if code == 0 else _FAILED`
- Raw green: `.   [100%]` / `1 passed in 0.23s`

## E2: codex path-match gate

- Guarded element: `calibration_read.py` `_names_target`, line 300. Axis: a call counts toward a
  file only when it names that file's path.
- Neutralization: `return (any(` became `return True or (any(` (every completed call names every file).
- Detector: `test_codex_calls_not_naming_the_files_record_not_read`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_codex_calls_not_naming_the_files_record_not_read _____________
    def test_codex_calls_not_naming_the_files_record_not_read(calib):
        stdout = _codex_stream(
            _codex_cmd("a", "git status --short", exit_code=0),
            _codex_cmd("b", "cat /elsewhere/notes.txt", exit_code=0),
        )
>       assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
            "core": "not-read", "review-crew": "not-read", "CLAUDE.md": "not-read"}
E       AssertionError: assert {'core': 'rea...E.md': 'read'} == {'core': 'not...': 'not-read'}
E         Differing items:
E         {'core': 'read'} != {'core': 'not-read'}
E         {'CLAUDE.md': 'read'} != {'CLAUDE.md': 'not-read'}
E         {'review-crew': 'read'} != {'review-crew': 'not-read'}
1 failed in 0.28s
```

- Restore: inverse Edit. Restore receipt (Grep after): `300:def _names_target(call, targets):` then `301:    return (any(isinstance(p, str) and p in targets for p in call["paths"])`
- Raw green: `.   [100%]` / `1 passed in 0.21s`

## E3: unrecognizable stream gives `unknown`

- Guarded element: `calibration_read.py` `read_states`, the default state for a file the parser
  did not classify, line 361. Axis: `unknown` whenever the stream cannot tell.
- Neutralization: `states.get(id(entry), UNKNOWN)` became `states.get(id(entry), NOT_READ)`.
- Detector: `test_codex_unrecognizable_stream_records_unknown_for_every_file` (4 parameter cases:
  plain text, JSON lines that are not codex events, empty string, None).
- Raw red (the first red run was piped through a `grep -v` filter, which the order disallows for a
  red capture; it was re-run unfiltered and this is the unfiltered tail, 45 lines, start elided):

```
    def test_codex_unrecognizable_stream_records_unknown_for_every_file(calib, stdout):
>       assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
            "core": "unknown", "review-crew": "unknown", "CLAUDE.md": "unknown"}
E       AssertionError: assert {'core': 'not...': 'not-read'} == {'core': 'unk...d': 'unknown'}
E         Differing items:
E         {'review-crew': 'not-read'} != {'review-crew': 'unknown'}
E         {'core': 'not-read'} != {'core': 'unknown'}
E         {'CLAUDE.md': 'not-read'} != {'CLAUDE.md': 'unknown'}
E         Use -v to get more diff
test_calibration_read.py:127: AssertionError
____ test_codex_unrecognizable_stream_records_unknown_for_every_file[None] _____
FAILED ...::test_codex_unrecognizable_stream_records_unknown_for_every_file[plain text, the engine printed no events\n]
FAILED ...::test_codex_unrecognizable_stream_records_unknown_for_every_file[{"hello": "world"}\n{"type": "not-a-codex-event"}\n]
FAILED ...::test_codex_unrecognizable_stream_records_unknown_for_every_file[]
FAILED ...::test_codex_unrecognizable_stream_records_unknown_for_every_file[None]
4 failed in 0.31s
```

- Restore: inverse Edit. Restore receipt (Grep after): `361:        return [_observation_entry(entry, states.get(id(entry), UNKNOWN)) for entry in entries]`
- Raw green: `....   [100%]` / `4 passed in 0.27s`

## E4: claude `is_error` gate

- Guarded element: `calibration_read.py` `_claude_calls`, line 232. Axis: a claude call is
  successful only when its `tool_result` is not an error.
- Neutralization: `call["outcome"] = _FAILED if block.get("is_error") is True else _OK` became `call["outcome"] = _OK`.
- Detector: `test_claude_read_with_error_tool_result_records_not_read`.
- Raw red:

```
F                                                                        [100%]
___________ test_claude_read_with_error_tool_result_records_not_read ___________
    def test_claude_read_with_error_tool_result_records_not_read(calib):
        stdout = _lines(_claude_use("t1", "Read", {"file_path": calib.core}),
                        _claude_result("t1", is_error=True))
>       assert _reads(CR.read_states("claude", stdout, calib.stamp))["core"] == "not-read"
E       AssertionError: assert 'read' == 'not-read'
E         - not-read
E         + read
1 failed in 0.20s
```

- Restore: inverse Edit. Restore receipt (Grep after): `232:                    call["outcome"] = _FAILED if block.get("is_error") is True else _OK`
- Raw green: `.   [100%]` / `1 passed in 0.25s`

## E5: cursor success gate

- Guarded element: `calibration_read.py` `_cursor_result_outcome`, line 237 onward. Axis: a cursor
  call is successful only when its result holds a `success` key.
- Neutralization: inserted `return _OK` as the first statement after the docstring (result ignored).
- Detector: `test_cursor_error_result_records_not_read`.
- Raw red:

```
F                                                                        [100%]
__________________ test_cursor_error_result_records_not_read ___________________
    def test_cursor_error_result_records_not_read(calib):
        stdout = _lines(_cursor_event("completed", "1", "readToolCall", {"path": calib.core},
                                      {"error": {"message": "no such file"}}))
>       assert _reads(CR.read_states("cursor", stdout, calib.stamp))["core"] == "not-read"
E       AssertionError: assert 'read' == 'not-read'
1 failed in 0.25s
```

- Restore: inverse Edit (removed the inserted line). Restore receipt (Grep after, with 2 lines of context):
  `237:    """Outcome of one cursor ``<kind>ToolCall`` result dict."""` / `238:    if not isinstance(result, dict):` / `239:        return _INDETERMINATE`
- Raw green: `.   [100%]` / `1 passed in 0.23s`

## E6: basename-only success gives `unknown`

- Guarded element: `calibration_read.py` `_file_state`, line 326 to 327. Axis: a successful call
  that names the basename but no path cannot be told apart from a relative read, so `unknown`.
- Neutralization: `return UNKNOWN` became `return NOT_READ` inside the basename loop.
- Detector: `test_codex_basename_only_success_records_unknown`.
- Raw red:

```
F                                                                        [100%]
_______________ test_codex_basename_only_success_records_unknown _______________
    def test_codex_basename_only_success_records_unknown(calib):
        stdout = _codex_stream(_codex_cmd("a", "cd /somewhere && cat core.md", exit_code=0))
>       assert _reads(CR.read_states("codex", stdout, calib.stamp)) == {
            "core": "unknown", "review-crew": "not-read", "CLAUDE.md": "not-read"}
E       AssertionError: assert {'core': 'not...': 'not-read'} == {'core': 'unk...': 'not-read'}
E         Differing items:
E         {'core': 'not-read'} != {'core': 'unknown'}
1 failed in 0.25s
```

- Restore: inverse Edit. Restore receipt (Grep after): `326:        if call["outcome"] == _OK and _names_basename(call, basename):` / `327:            return UNKNOWN`
- Raw green: `.   [100%]` / `1 passed in 0.24s`

## E7: runner wiring in `_observation_from_attempt`

- Guarded element: `engine_dispatch.py` `_observation_from_attempt`, line 7617. Axis: a review
  run's engine record observation carries the calibration read states from the run-opened stamp.
- Neutralization: `observation["calibration"] = calibration_read.read_states(engine, stdout, stamped)` became `pass`.
- Detector: `test_run_execution_record_observation_carries_read_for_a_file_a_codex_stream_read`
  (opens a run through the real `_open_review_run`, writes a codex stream and an attempt-ended
  record, reads `run_execution_record(...)["observation"]["calibration"]`).
- Raw red:

```
F                                                                        [100%]
_ test_run_execution_record_observation_carries_read_for_a_file_a_codex_stream_read _
    def test_run_execution_record_observation_carries_read_for_a_file_a_codex_stream_read(
            runner_env, tmp_path, calib):
        run_dir = _open_run(tmp_path, calib)
        _complete_attempt(run_dir, _codex_stream(
            _codex_cmd("a", "/bin/bash -lc 'cat %s'" % calib.core, exit_code=0),
            _codex_cmd("b", "cat %s" % calib.layer, exit_code=1)))
        record, error = ED.run_execution_record(run_dir)
        assert error is None
>       observed = record["observation"]["calibration"]
E       KeyError: 'calibration'
1 failed in 0.27s
```

- Restore: inverse Edit. Restore receipt (Grep after): `7616:    if opened.get("runKind") != RUN_KIND_WRITE and isinstance(stamped, list):` / `7617:        observation["calibration"] = calibration_read.read_states(engine, stdout, stamped)`
- Raw green: `.   [100%]` / `1 passed in 0.25s`

## E8: the stamp-time hash

- Guarded element: `calibration_read.py` `_observation_entry`, line 335. Axis: the reported
  `sha256` is the hash taken when the run opened, not one taken when the record is built.
- Neutralization: `"sha256": entry.get("sha256"),` became `"sha256": _hash_and_policy(entry.get("path"))[0],`.
- Detector: `test_stamp_hash_and_policy_are_taken_at_stamp_time` (rewrites `core.md` after the stamp).
- Raw red:

```
F                                                                        [100%]
______________ test_stamp_hash_and_policy_are_taken_at_stamp_time ______________
    def test_stamp_hash_and_policy_are_taken_at_stamp_time(calib):
        with open(calib.core, "w", encoding="utf-8") as fh:
            fh.write("rewritten after the stamp\nPolicy version: changed\n")
        stdout = _codex_stream(_codex_cmd("a", "cat %s" % calib.core, exit_code=0))
        entry = CR.read_states("codex", stdout, calib.stamp)[0]
>       assert entry["sha256"] == _sha(calib.bytes[calib.core])
E       AssertionError: assert 'e98d8b8b61a4...cb136d54e8560' == '017a0700e710...0e9b0cc8b3e47'
1 failed in 0.25s
```

- Restore: inverse Edit. Restore receipt (Grep after): `335:        "sha256": entry.get("sha256"),`
- Raw green: `.   [100%]` / `1 passed in 0.26s`
