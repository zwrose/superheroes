# Bite-proof record — the duplication lens reads jscpd's report from a file (#2411)

Detector file: `plugins/superheroes/lib/tests/test_guardian_lens_duplication.py` (the six new tests, 10 test nodes, each with a `# bites on:` line), unedited between each red and its green. Every neutralization is one targeted, reversible edit to one production file (`plugins/superheroes/lib/guardian_lens_duplication.py`) made through the Edit tool in a detached probe worktree (`/home/user/sh-2411-probe`, at the commit named per entry), restored by the inverse Edit; no `git checkout`, `restore`, `reset` or `stash`, and no shell edit. Command for every red and green, from the probe worktree root: `timeout 600 scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <node ids> -q -p no:randomly --tb=line`, followed by `git status --porcelain`. Captures are the whole output, the `uv` deprecation warning included. No secret, token, private URL or PII appears in any capture, so nothing was redacted.

The guarded-element set, declared before the review (this build is light-lane and orchestrator-typed, so the declaration goes on the reviewer's dispatch): G1 the file read, G2 the lens's read bound, G3 the temp-dir removal, G4 the named missing-file cause. None is grouped.

## G1. The report is read from jscpd's report file (`guardian_lens_duplication.py`, `collect`: the `if res["ok"]:` read of `REPORT_FILE_NAME` before the temp dir is removed)

- **Axis:** a report larger than the collector's stdout cap, written to the report file, yields a `collected` reading, and a report file wins over stdout; the axis is the collect status, not the helper alone.
- **Detectors (expected red):** `test_report_larger_than_stdout_cap_parses_from_file`, `test_report_file_is_preferred_over_stdout`.
- **Probe head:** `94be6cab`.
- **Neutralization:** `            if res["ok"]:` became `            if False and res["ok"]:` (the file is never read, so the lens falls back to stdout, the pre-fix channel).

**Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert ('not-collect... JSON report') == ('collected', None)
      
      At index 0 diff: 'not-collected' != 'collected'
      Use -v to get more diff
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:687: AssertionError: assert ('not-collect... JSON report') == ('collected', None)
E   AssertionError: assert ('not-collect...jscpd report') == ('collected', None)
      
      At index 0 diff: 'not-collected' != 'collected'
      Use -v to get more diff
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:760: AssertionError: assert ('not-collect...jscpd report') == ('collected', None)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_larger_than_stdout_cap_parses_from_file
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_file_is_preferred_over_stdout
2 failed in 0.99s
exit=1
 M plugins/superheroes/lib/guardian_lens_duplication.py
```

Red on the claimed axis: both read `not-collected` where `collected` is expected, because the lens read stdout, which carries no report.

**Restore:** the inverse Edit, `if False and res["ok"]:` back to `if res["ok"]:`.

**Raw green** (the trailing empty `git status --porcelain` is the restore receipt):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 6.57s
exit=0
```

## G2. The lens's own read bound (`guardian_lens_duplication.py`, `_read_report_file`: `if len(data) > limit:`)

- **Axis:** a report file past `MAX_REPORT_FILE_BYTES` degrades `not-collected` with a reason naming `report-too-large`; one of exactly the bound reads. The axis is the named cause and the status.
- **Detectors (expected red):** `test_report_file_over_lens_bound_degrades_named`, `test_report_file_at_lens_bound_still_reads`.
- **Probe head:** `79148d6f`.
- **Neutralization:** `    if len(data) > limit:` became `    if False and len(data) > limit:`.

**Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'report-too-large' in 'unparseable jscpd report'
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:707: AssertionError: assert 'report-too-large' in 'unparseable jscpd report'
E   AssertionError: assert 'collected' == 'not-collected'
      
      - not-collected
      ? ----
      + collected
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:727: AssertionError: assert 'collected' == 'not-collected'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_file_over_lens_bound_degrades_named
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_file_at_lens_bound_still_reads
2 failed in 0.42s
exit=1
 M plugins/superheroes/lib/guardian_lens_duplication.py
```

Red on the claimed axis: past the bound the lens degrades with an unnamed parse cause (`unparseable jscpd report`, the truncated read) instead of `report-too-large`, and at one byte under the report size it collects where it must degrade.

**Restore:** the inverse Edit.

**Raw green** (the trailing empty `git status --porcelain` is the restore receipt):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.41s
exit=0
```

## G3. The temp report dir is removed (`guardian_lens_duplication.py`, `collect`, the `finally`: `shutil.rmtree(tmp, ignore_errors=True)`)

- **Axis:** after `collect()` the `-o` dir jscpd wrote into no longer exists, on success, tool failure, unparseable report, over-bound report and a raising tool. The axis is the dir's existence after the call.
- **Detectors (expected red):** `test_report_temp_dir_removed_after_run[success|tool-failed|unparseable|over-bound|tool-raises]`.
- **Probe head:** `79148d6f`.
- **Neutralization:** `                shutil.rmtree(tmp, ignore_errors=True)` became `                pass  # shutil.rmtree(tmp, ignore_errors=True)`.

**Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   AssertionError: temp report dir left behind: /tmp/guardian-jscpd-a111l32w
    assert not True
     +  where True = <function exists at 0x7f2d86993ec0>('/tmp/guardian-jscpd-a111l32w')
     +    where <function exists at 0x7f2d86993ec0> = <module 'posixpath' (frozen)>.exists
     +      where <module 'posixpath' (frozen)> = os.path
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:788: AssertionError: temp report dir left behind: /tmp/guardian-jscpd-a111l32w
E   AssertionError: temp report dir left behind: /tmp/guardian-jscpd-f3kglprp
    assert not True
     +  where True = <function exists at 0x7f2d86993ec0>('/tmp/guardian-jscpd-f3kglprp')
     +    where <function exists at 0x7f2d86993ec0> = <module 'posixpath' (frozen)>.exists
     +      where <module 'posixpath' (frozen)> = os.path
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:788: AssertionError: temp report dir left behind: /tmp/guardian-jscpd-f3kglprp
E   AssertionError: temp report dir left behind: /tmp/guardian-jscpd-vb3pmydj
    assert not True
     +  where True = <function exists at 0x7f2d86993ec0>('/tmp/guardian-jscpd-vb3pmydj')
     +    where <function exists at 0x7f2d86993ec0> = <module 'posixpath' (frozen)>.exists
     +      where <module 'posixpath' (frozen)> = os.path
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:788: AssertionError: temp report dir left behind: /tmp/guardian-jscpd-vb3pmydj
E   AssertionError: temp report dir left behind: /tmp/guardian-jscpd-tec0wid9
    assert not True
     +  where True = <function exists at 0x7f2d86993ec0>('/tmp/guardian-jscpd-tec0wid9')
     +    where <function exists at 0x7f2d86993ec0> = <module 'posixpath' (frozen)>.exists
     +      where <module 'posixpath' (frozen)> = os.path
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:788: AssertionError: temp report dir left behind: /tmp/guardian-jscpd-tec0wid9
E   AssertionError: temp report dir left behind: /tmp/guardian-jscpd-ho69he94
    assert not True
     +  where True = <function exists at 0x7f2d86993ec0>('/tmp/guardian-jscpd-ho69he94')
     +    where <function exists at 0x7f2d86993ec0> = <module 'posixpath' (frozen)>.exists
     +      where <module 'posixpath' (frozen)> = os.path
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:788: AssertionError: temp report dir left behind: /tmp/guardian-jscpd-ho69he94
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_temp_dir_removed_after_run[success]
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_temp_dir_removed_after_run[tool-failed]
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_temp_dir_removed_after_run[unparseable]
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_temp_dir_removed_after_run[over-bound]
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_report_temp_dir_removed_after_run[tool-raises]
5 failed in 0.41s
exit=1
 M plugins/superheroes/lib/guardian_lens_duplication.py
```

Red on the claimed axis: all five cases fail on `temp report dir left behind`.

**Restore:** the inverse Edit. The five dirs the red run left under the system temp folder were each removed afterwards by a plain one-path delete.

**Raw green** (the trailing empty `git status --porcelain` is the restore receipt):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....                                                                    [100%]
5 passed in 0.48s
exit=0
```

## G4. The missing-file cause is named (`guardian_lens_duplication.py`, `collect`: `_decode_report(res.get("stdout") or "", no_file=True)`)

- **Axis:** jscpd exiting 0 with no report file and no JSON on stdout degrades with a reason naming the missing report file.
- **Detectors (expected red):** `test_no_report_file_and_no_stdout_json_degrades_named`.
- **Probe head:** `79148d6f`.
- **Neutralization:** `no_file=True)` became `no_file=False)`.

**Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'no report file' in 'jscpd produced no JSON report'
/home/user/sh-2411-probe/plugins/superheroes/lib/tests/test_guardian_lens_duplication.py:739: AssertionError: assert 'no report file' in 'jscpd produced no JSON report'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_guardian_lens_duplication.py::test_no_report_file_and_no_stdout_json_degrades_named
1 failed in 0.45s
exit=1
 M plugins/superheroes/lib/guardian_lens_duplication.py
```

Red on the claimed axis: the reason reads `jscpd produced no JSON report`, which does not name the missing file.

**Restore:** the inverse Edit.

**Raw green** (the trailing empty `git status --porcelain` is the restore receipt):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.39s
exit=0
```

## Restore receipt for the whole run

After G4's green, `git status --porcelain` and `git diff --stat` in the probe worktree printed nothing: every neutralized line is back to its committed text. G1's green was re-run at `79148d6f` (the at-bound test's last assertions changed after G1's proof at `94be6cab`; G1's detectors did not), also 2 passed.

## Not proven separately

- The `OSError` arm of `_read_report_file` (an unreadable report file) and its non-UTF-8 arm are fail-closed edges with no dedicated test; each returns a named `not-collected` reason, and neither can read as a zero reading.
