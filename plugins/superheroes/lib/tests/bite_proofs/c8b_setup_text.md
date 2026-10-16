# Bite-proof record: cloud_setup_text.py (sandbox tools and pinned interpreter)

Detector: `plugins/superheroes/lib/tests/test_cloud_setup_text.py`.
Guarded elements (declared by the order): G1 the sandbox-tools install line; G2 the fail-soft `|| echo "sandbox tools FAILED"`; G3 the pin test `[ -f .python-version ]`.
Each was neutralized by a targeted edit in `plugins/superheroes/lib/cloud_setup_text.py` (`_script`), the detector run alone as one `-k` selection, then restored by the inverse edit. The test file was never edited during the proofs.

Run command, each time, from the repository root: `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_cloud_setup_text.py -q -p no:cacheprovider -k <test>`.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted from the captures below.

## 1. The sandbox-tools install line

Axis: the generated text installs `bubblewrap` and `socat` through apt, before the `wait` line and before the tool-steps marker (presence in the text).

- Neutralization (`_script`): the two-line list entry `'  apt-get install -y %s || { apt-get update && apt-get install -y %s; } \\' % (SANDBOX_TOOL_PACKAGES, SANDBOX_TOOL_PACKAGES),` became `'  true \\',`.
- Node: `test_setup_text_installs_the_sandbox_tools_and_the_pinned_python_before_the_wait`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_setup_text_installs_the_sandbox_tools_and_the_pinned_python_before_the_wait _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_setup_text_installs_the_s0')

    def test_setup_text_installs_the_sandbox_tools_and_the_pinned_python_before_the_wait(tmp_path):
        lines = _compose(_inside(tmp_path))["text"].splitlines()
        install = "apt-get install -y bubblewrap socat"
        wait = lines.index("wait")
        marker = lines.index(CS.TOOL_STEPS_MARKER)
>       assert any(install in line for line in lines[:wait])
E       assert False
E        +  where False = any(<generator object test_setup_text_installs_the_sandbox_tools_and_the_pinned_python_before_the_wait.<locals>.<genexpr> at 0x7f714a4e2c20>)

/home/user/wo-a/plugins/superheroes/lib/tests/test_cloud_setup_text.py:312: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_setup_text_installs_the_sandbox_tools_and_the_pinned_python_before_the_wait
1 failed, 118 deselected in 0.29s
```

- Restore: the inverse edit; `cloud_setup_text.py:335-336` read `        '  apt-get install -y %s || { apt-get update && apt-get install -y %s; } \\'` then `        % (SANDBOX_TOOL_PACKAGES, SANDBOX_TOOL_PACKAGES),`.
- Green:

```
.                                                                        [100%]
1 passed, 118 deselected in 0.28s
```

## 2. The fail-soft `sandbox tools FAILED` line

Axis: when apt-get fails twice, the script writes `sandbox tools FAILED` to the log, carries on and exits 0 (refusal side: a failure is logged, never silent).

- Neutralization (`_script`): `'    && echo "sandbox tools ok" || echo "sandbox tools FAILED"',` became `'    && echo "sandbox tools ok"',`.
- Node: `test_failing_sandbox_tools_and_pinned_python_are_logged_and_the_script_exits_zero`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_failing_sandbox_tools_and_pinned_python_are_logged_and_the_script_exits_zero _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_failing_sandbox_tools_and0')

    def test_failing_sandbox_tools_and_pinned_python_are_logged_and_the_script_exits_zero(tmp_path):
        w = _inside(tmp_path)
        proc, log = _run_script(w, _compose(w)["text"], code=1, pinned=True)
        assert proc.returncode == 0, proc.stderr
        setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
>       assert "sandbox tools FAILED" in setup_log and "pinned python FAILED" in setup_log
E       AssertionError: assert ('sandbox tools FAILED' in 'pinned python FAILED\nreviewer cli FAILED\nduplication checker FAILED\nplugin FAILED\nsetup end\n')

/home/user/wo-a/plugins/superheroes/lib/tests/test_cloud_setup_text.py:322: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_failing_sandbox_tools_and_pinned_python_are_logged_and_the_script_exits_zero
1 failed, 118 deselected in 1.66s
```

- Restore: the inverse edit; `cloud_setup_text.py:337` reads `        '    && echo "sandbox tools ok" || echo "sandbox tools FAILED"',`.
- Green:

```
.                                                                        [100%]
1 passed, 118 deselected in 0.35s
```

## 3. The pin test

Axis: `uv python install` runs only when a `.python-version` file sits in the working directory; with none, the log names the directory and `uv` is not called.

- Neutralization (`_script`): `"  if [ -f .python-version ]; then",` became `"  if true; then",` (the group calls `uv python install` unconditionally).
- Node: `test_no_python_version_file_is_logged_by_directory_and_uv_is_never_called`.
- Red (the stub `uv` ran and logged `pinned python ok`, so the "no .python-version in" line was absent):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_no_python_version_file_is_logged_by_directory_and_uv_is_never_called ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_no_python_version_file_is0')

    def test_no_python_version_file_is_logged_by_directory_and_uv_is_never_called(tmp_path):
        w = _inside(tmp_path)
        proc, log = _run_script(w, _compose(w)["text"])
        assert proc.returncode == 0, proc.stderr
        setup_log = (w.home / "superheroes-cloud-setup.log").read_text()
>       assert "pinned python: no .python-version in %s" % (w.tmp / "work") in setup_log
E       AssertionError: assert ('pinned python: no .python-version in %s' % (PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_no_python_version_file_is0') / 'work')) in 'reviewer cli ok\npinned python ok\nsandbox tools ok\nduplication checker ok\ncat: /tmp/claude-0/pytest-of-root/pytest...no_python_version_file_is0/opt/src/plugins/superheroes/version.txt: No such file or directory\nplugin ok \nsetup end\n'
E        +  where PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_no_python_version_file_is0') = <test_cloud_setup_text.World object at 0x7fea139b2180>.tmp

/home/user/wo-a/plugins/superheroes/lib/tests/test_cloud_setup_text.py:344: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_no_python_version_file_is_logged_by_directory_and_uv_is_never_called
1 failed, 118 deselected in 0.36s
```

- Restore: the inverse edit; `cloud_setup_text.py:342` reads `        "  if [ -f .python-version ]; then",`.
- Green:

```
.                                                                        [100%]
1 passed, 118 deselected in 0.37s
```

The `cat: ... version.txt: No such file or directory` text in the red log is the stubbed `git` (it fetches nothing), the same in every script test; it is not part of the proof.

## Green after all three restores

The full file, run once more after the third restore: `118 passed, 1 skipped in 11.68s`. A read of the restored lines in `cloud_setup_text.py` (330-347) shows none of the three neutralizations present.
