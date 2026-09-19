# Layer 2b (#1270) bite-proof — codex's write path on the native channel, and the occupied result path

**Provenance:** produced by the layer-2b orchestrator session (opus 5, medium), orchestrator-typed,
in a detached probe worktree of its own (never the build tree the review seats read). The detectors
were implemented under **WO-2b-A** (the fd-based loader, the spawn-side occupancy refusal),
**WO-2b-B** (the native write admission) and **WO-2b-E** (review round 1: the shared schema helper)
by cursor / composer-2.5; every run below is the orchestrator's own.

**Head these proofs were run on:** `da296805` — this layer's final code head. Every proof was first
recorded at `04205cce` and then **re-run in full on `da296805`**, because the review fix commit
moved the schema comparison into `_verify_native_schema` and touched `engine_dispatch.py`. The raw
output quoted below is from the re-run. Commits after `da296805` add only this record and prose; if
a later commit touches `engine_dispatch.py`, every proof is re-run and this line is updated.

**Method.** Each guarded element is neutralized on its own — the thing the detector guards, never
the detector — by a targeted edit through the host's edit action, reverted by the exact inverse
edit. Tests are selected by **exact node id**, never `-k`. Only one neutralization was live at a
time (the probe tree's `git diff` was checked before every red run and showed exactly that edit).
For elements BP-2b-4..7 and BP-2b-1..2, each neutralization was restored before the next was
applied and the green runs were then made together on the clean tree (`git status --porcelain`
empty) — one green run covering several restored elements, disclosed here.

Common command prefix (run in the probe tree):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node ids> -q -p no:cacheprovider
```

## Guarded elements

| ID | Guarded element (`engine_dispatch.py`) | Neutralized thing | Proving test(s) |
|---|---|---|---|
| BP-2b-1 | `_load_native_result_json` opens the result path without following a symlink | `os.O_NOFOLLOW` dropped from the open flags | `test_load_native_result_json_refuses_symlink_to_valid_file`, `test_grade_native_review_attempt_symlinked_result_forfeits_missing` |
| BP-2b-2 | only a regular file, judged on the opened fd, is read as a result | the `S_ISREG` check on the fd | `test_load_native_result_json_fifo_returns_missing_without_blocking` |
| BP-2b-3a | the spawn side inspects the path **without following it** (the binding row: a dangling symlink is occupied) | `os.lstat` → `os.stat` (the old follow-the-link behaviour) | `test_spawn_native_result_argv_refuses_occupied_path[dangling_symlink]`, `test_native_dangling_symlink_at_result_path_is_never_handed_to_engine`, `test_native_write_dangling_symlink_at_result_path_never_handed_to_engine` |
| BP-2b-3b | any entry at the result path refuses the attempt (file, symlink, dangling symlink, directory) | the `native-result-path-occupied` refusal discarded | the three above plus `test_spawn_native_result_argv_refuses_occupied_path[symlink_to_file,regular_file,directory]`, `test_native_stale_result_file_refuses_second_spawn` |
| BP-2b-4 | the schema on disk must equal the declared one (`_verify_native_schema`, shared by both admissions) | the on-disk/declared comparison | `test_native_write_schema_substitution_refuses`, `test_admit_native_review_schema_substitution_refuses` |
| BP-2b-5 | a native write result failing the declared schema forfeits `native-result-schema-invalid`; nothing after it produces ok | the validator's verdict (it still runs) | `test_native_write_schema_invalid_forfeits` (5 specimens) |
| BP-2b-6 | a blank or whitespace-only report forfeits `native-result-report-blank` | the blank-report guard | `test_native_write_blank_report_forfeits` (2 specimens) |
| BP-2b-7 | the report reaches the terminal and the journal only through the scrub egress | `engine_adapter._scrub` bypassed | `test_native_write_secret_in_report_scrubbed_from_terminal_and_journal` |

Coverage by construction (R27 iii): BP-2b-1/2 neutralize the one loader both native admissions read
through; BP-2b-3a/b the one function that hands out the `-o` path on both spawn paths; BP-2b-4 the
one schema helper both admissions call; BP-2b-5..7 the one write admission every write reader uses.

Planted-secret handling: the planted token is a fake secret-shaped literal kept in the test; it is
**redacted** as `<planted-fake-token>` in the captures below.

---

## BP-2b-1 — the result path is never followed

- **axis:** a symlink at `native-result-N.json`, even to a valid result, reads as `native-result-missing`.
- **neutralization:** `flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)` (was `… | os.O_NOFOLLOW | …`).
- **raw red** (exit 1): the loader followed the link and returned the target's content; the review grade admitted it.
```
E       AssertionError: assert {'result': {'ok': True}} is None
E       AssertionError: assert None is True
E        +  where None = …{'engagement': {'read': 'engaged', …}, 'findings': [{'body'…}.get('forfeit')
FAILED …test_engine_dispatch.py::test_load_native_result_json_refuses_symlink_to_valid_file
FAILED …test_engine_dispatch.py::test_grade_native_review_attempt_symlinked_result_forfeits_missing
2 failed in 1.47s
```
- **restore:** inverse edit (`os.O_NOFOLLOW` back). **restore receipt:** probe `git diff --stat` empty before BP-2b-2's edit (only BP-2b-2's one line showed).
- **raw green** (with BP-2b-2, tree clean): `3 passed in 1.19s`.

## BP-2b-2 — only a regular file is read

- **axis:** a FIFO (or any non-regular entry) at the result path reads as `native-result-missing`, judged on the fd.
- **neutralization:** `if False:  # bite-proof BP-2b-2` (was `if not stat.S_ISREG(st.st_mode):`).
- **raw red** (exit 1): the FIFO is read as content and graded malformed instead of refused.
```
E       AssertionError: assert 'native-result-malformed' == 'native-result-missing'
FAILED …test_engine_dispatch.py::test_load_native_result_json_fifo_returns_missing_without_blocking
1 failed in 1.33s
```
- **scope disclosure:** the directory specimen stays green under this neutralization — a directory is refused by the read path (`EISDIR` → `native-result-missing`), not by this check alone; the FIFO is this element's proving specimen.
- **restore:** inverse edit. **restore receipt:** `porcelain=[]`. **raw green:** `3 passed in 1.19s` (with BP-2b-1).

## BP-2b-3a — the spawn side does not follow the link (the binding row)

- **axis:** a **dangling** symlink at the path it is about to hand out refuses the attempt; the engine can never write through it.
- **neutralization:** `os.stat(result_path)` (was `os.lstat(result_path)`) — exactly the old `os.path.exists` class the binding row names.
- **raw red** (exit 1): the dangling link reads as absent, is handed to the engine as `-o`, and the engine **creates the link's target**.
```
E       assert True is False
E           AssertionError: fake called too many times
E       AssertionError: assert not True
E        +  where True = exists()
E        +    where exists = PosixPath('…/test_native_write_dangling_sym0/never-created-target').exists
FAILED …test_engine_dispatch.py::test_spawn_native_result_argv_refuses_occupied_path[dangling_symlink]
FAILED …test_engine_dispatch.py::test_native_dangling_symlink_at_result_path_is_never_handed_to_engine
FAILED …test_engine_dispatch_write.py::test_native_write_dangling_symlink_at_result_path_never_handed_to_engine
3 failed, 3 passed in 2.84s
```
- **restore:** inverse edit. **restore receipt:** probe diff showed only BP-2b-3b's line before its red run.

## BP-2b-3b — any entry refuses

- **axis:** file, symlink, dangling symlink or directory at the result path → `native-result-path-occupied`, entry untouched.
- **neutralization:** `pass  # bite-proof BP-2b-3b` (was `return False, spawn_argv, result_path, "native-result-path-occupied"`).
- **raw red** (exit 1): every entry kind is handed out; the stale-file test's runner is invoked.
```
FAILED …test_spawn_native_result_argv_refuses_occupied_path[dangling_symlink]
FAILED …test_spawn_native_result_argv_refuses_occupied_path[symlink_to_file]
FAILED …test_spawn_native_result_argv_refuses_occupied_path[regular_file]
FAILED …test_spawn_native_result_argv_refuses_occupied_path[directory]
FAILED …test_native_stale_result_file_refuses_second_spawn
FAILED …test_native_dangling_symlink_at_result_path_is_never_handed_to_engine
FAILED …test_native_write_dangling_symlink_at_result_path_never_handed_to_engine
7 failed in 3.50s
```
- **restore:** inverse edit. **restore receipt:** `porcelain=[]`. **raw green** (BP-2b-3a and 3b together): `7 passed in 2.23s`.

## BP-2b-4 — the schema that graded is the schema that was sent

- **axis:** a schema file on disk that does not parse to the declared schema refuses `native-schema-unreadable`, on the write **and** the review admission (one helper).
- **neutralization:** `if False:  # bite-proof BP-2b-4` (was `if on_disk != declared:` in `_verify_native_schema`).
- **raw red** (exit 1): the write admits against a substituted `{}` schema; the review refuses under the wrong token.
```
E        +    where … = {'evidence': {'testFailed': False, 'testPassed': True}, 'ok': True, 'report': 'Receipt prose.', 'signal': 'ok'}.get
E       AssertionError: assert 'native-result-schema-invalid' == 'native-schema-unreadable'
FAILED …test_engine_dispatch_write.py::test_native_write_schema_substitution_refuses
FAILED …test_engine_dispatch.py::test_admit_native_review_schema_substitution_refuses
2 failed in 1.99s
```
- **restore:** inverse edit; probe diff showed only BP-2b-5's line before its red run.

## BP-2b-5 — the declared schema is the write admission authority

- **axis:** a native write result failing the declared schema forfeits `native-result-schema-invalid` — missing `report`, an extra key, a mistyped `ok`, an off-enum `signal`, a non-boolean evidence field.
- **neutralization:** `ok = True  # bite-proof BP-2b-5` after `_validate_with_detail` (the validator runs; its verdict is discarded).
- **raw red** (exit 1): four specimens come back ok or as a refusal; the missing-report one is caught only later, under the wrong token.
```
E       AssertionError: assert 'native-result-report-blank' == 'native-result-schema-invalid'
E        +    where … = {'evidence': {…}, 'ok': True, 'report': 'x', 'signal': 'ok'}.get
E        +    where … = {'evidence': {…}, 'ok': False, 'reason': 'needs_context', 'report': 'x', …}.get
FAILED …test_native_write_schema_invalid_forfeits[obj0] … [obj4]
5 failed in 1.71s
```
- **restore:** inverse edit (line removed); probe diff showed only BP-2b-6's line before its red run.

## BP-2b-6 — a blank report is refused

- **axis:** `report` empty or whitespace-only → `native-result-report-blank` (codex returned `report: ""` on a live dispatch).
- **neutralization:** `if False:  # bite-proof BP-2b-6` (was `if report_raw.strip() == "":`).
- **raw red** (exit 1):
```
E        +    where … = {'evidence': {…}, 'ok': True, 'report': '', 'signal': 'ok'}.get
E        +    where … = {'evidence': {…}, 'ok': True, 'report': '   \n', 'signal': 'ok'}.get
FAILED …test_native_write_blank_report_forfeits[]
FAILED …test_native_write_blank_report_forfeits[   \n]
2 failed in 0.51s
```
- **restore:** inverse edit; probe diff showed only BP-2b-7's line before its red run.

## BP-2b-7 — the report goes out only through the scrub egress

- **axis:** a secret-shaped token planted in the report is absent from the terminal result and from every journal byte.
- **neutralization:** `report = obj["report"]  # bite-proof BP-2b-7` (was `report = engine_adapter._scrub(obj["report"])`).
- **raw red** (exit 1, token redacted):
```
E       assert '<planted-fake-token>' not in '{"ok": true…'
E           n: Bearer <planted-fake-token>", "siblingWorktrees": {…
FAILED …test_native_write_secret_in_report_scrubbed_from_terminal_and_journal
1 failed in 0.53s
```
- **restore:** inverse edit. **restore receipt:** probe `git status --porcelain` empty.
- **raw green** (BP-2b-4..7 together, tree clean): `10 passed in 1.96s`.
