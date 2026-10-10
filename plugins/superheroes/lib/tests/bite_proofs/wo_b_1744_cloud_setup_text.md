# #1744 WO-B bite-proof: the setup text writer's secret scan, in-repository branch, file selection and substituted-value validation

Bite-proof record for `plugins/superheroes/lib/cloud_setup_text.py` (`_scan`, `_calibration`, `_store_files`, `_compose`), detectors in `plugins/superheroes/lib/tests/test_cloud_setup_text.py` (`T`).

**Status.** The implementer ran every proof (B1 to B4): each neutralization is a targeted Edit in `cloud_setup_text.py`, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same test function. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<test>" -q`.
- **Captures.** B2 and B3 reds and every green are the full output of the run, unfiltered. The B1 and B4 reds were redirected whole to a file outside the repository and are quoted below by their first and last lines because they run long (B1: 38116 bytes, over the 32 KiB ceiling; B4: 18396 bytes). The full files are at `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1744-9d9043901276fccf/c7d36e92-78ea-4211-b00e-5750002bc34e/scratchpad/b1_red.txt` and `.../scratchpad/b4_red.txt`.
- **One wasted run, disclosed.** The first B1 red was piped through `tail -40`, which cut its head; it was discarded and the run repeated with the whole output redirected to the B1 file above.
- **Redaction.** The planted secret-shaped values are synthetic, built at run time from repeated filler characters; none is a real credential. The B1 red's assertion message shows a truncated result dict, and the full B1 capture on disk may contain those synthetic values in the setup text a neutralized scan let through.
- **Restore receipt, every element.** The restored line is quoted back, with its line number in the final file.

## Declared guarded-element set

B1 the secret scan's refusal (S9); B2 the in-repository branch of `calibration_files`; B3 the file selection of `calibration_files`; B4 the substituted-value validation (S3).

## Per-element receipts

### B1: the secret scan's refusal (refusal; axis: a secret-shaped form in the final text refuses with `secret-shaped-content`)

- **Neutralization applied.** In `_scan`, `return next((name for name, pattern in _SECRET_SHAPES if pattern.search(text)), None)` replaced with `return None`, so the scan finds nothing.
- **Test.** `T::test_s9_secret_shaped_content` (parametrized over every shape in the scan table: 19 cases).
- **Red** (first and last lines of the 570-line capture; all 19 cases fail on the same assertion, `result["action"] == "refused"` meeting `'written'`):

```
FFFFFFFFFFFFFFFFFFF                                                      [100%]
=================================== FAILURES ===================================
_________________ test_s9_secret_shaped_content[signed-token] __________________
...
>       assert result["action"] == "refused" and result["reason"] == reason, result
E       AssertionError: {'action': 'written', 'reason': None, 'text': '#!/bin/bash
...
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_s9_secret_shaped_content[json-SUPERHEROES_REVIEWER_PASS]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_s9_secret_shaped_content[shell-pass-env]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_s9_secret_shaped_content[bearer]
19 failed in 10.00s
```

- **Restore.** The inverse Edit put the `next(...)` expression back; quoted from `cloud_setup_text.py:223`: `    return next((name for name, pattern in _SECRET_SHAPES if pattern.search(text)), None)`.
- **Green.**

```
...................                                                      [100%]
19 passed in 11.32s
```

### B2: the in-repository branch of `calibration_files` (preservation; axis: an in-repository project places no calibration)

- **Neutralization applied.** In `_calibration`, `mode = mode_registry.resolve(cwd, root, persist_backfill=False)["mode"]` replaced with `mode = mode_registry.GLOBAL`, so every project is treated as outside the repository.
- **Test.** `T::test_inside_fixture_has_no_calibration_in_the_text`
- **Red** (the fixture's store holds `registry.json` and `meta.json`, which the neutralized code now returns):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_inside_fixture_has_no_calibration_in_the_text ______________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-645/test_inside_fixture_has_no_cal0')

    def test_inside_fixture_has_no_calibration_in_the_text(tmp_path):
        w = _inside(tmp_path)
        assert os.path.isfile(os.path.join(w.store, "registry.json"))
>       assert CS.calibration_files(w.cwd, w.root) == {}
E       assert {'meta.json':...03:49Z"\n}\n'} == {}
E         
E         Left contains 2 more items:
E         {'meta.json': b'{"schemaVersion": 1, "sourcePath": "/private/tmp/claude-501/'
E                       b'pytest-of-zwrose/pytest-645/test_inside_fixture_has_no_cal0/'
E                       b'repo"}\n',
E          'registry.json': b'{\n  "schemaVersion": 1,\n  "storageMode": "in-repo",\n  "r'
E                           b'emoteKey": "238a7b644f5fb344",\n  "createdAt": "2026-10-1'
E                           b'0T22:03:49Z"\n}\n'}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_setup_text.py:184: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_inside_fixture_has_no_calibration_in_the_text
1 failed in 0.81s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:189`: `        mode = mode_registry.resolve(cwd, root, persist_backfill=False)["mode"]`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.71s
```

### B3: the file selection of `calibration_files` (exclusion; axis: only the listed calibration files are placed, never a backup beside them)

- **Neutralization applied.** In `_store_files`, `wanted += ["config/" + n for n in names if n.endswith(".md")]` replaced with `wanted += ["config/" + n for n in names if True]`, so every file under `config` is placed.
- **Test.** `T::test_outside_fixture_text_carries_everything_and_nothing_else`
- **Red** (the backup `config/core.md.bak-2026-01-01` is now listed):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_outside_fixture_text_carries_everything_and_nothing_else _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-648/test_outside_fixture_text_carr0')

    def test_outside_fixture_text_carries_everything_and_nothing_else(tmp_path):
        w = _outside(tmp_path)
        expected = CS.calibration_files(w.cwd, w.root)
        result = _compose(w)
        assert result["action"] == "written" and result["reason"] is None
        text = result["text"]
        assert result["header"] == "Corner Shop · plugin %s · calibration from 10 Oct" % VERSION
        assert text.splitlines()[1] == "# " + result["header"]
        assert result["pluginVersion"] == VERSION and result["pluginCommit"] == COMMIT
        assert result["picksUpVersionByItself"] is False
        assert 'git fetch -q --depth 1 "%s" %s' % (SOURCE, COMMIT) in text
        assert 'npm install -g "@openai/codex"' in text
        assert 'npm install -g "jscpd@5.0.12"' in text
>       assert list(expected) == EXPECTED_PATHS
E       AssertionError: assert ['config/core...es.json', ...] == ['config/core...egistry.json']
E         
E         At index 1 diff: 'config/core.md.bak-2026-01-01' != 'config/review-crew.md'
E         Left contains one more item: 'registry.json'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_setup_text.py:148: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_outside_fixture_text_carries_everything_and_nothing_else
1 failed in 0.78s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:169`: `    wanted += ["config/" + n for n in names if n.endswith(".md")]`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.68s
```

### B4: the substituted-value validation (refusal; axis: a source that is not a plain `https://` URL refuses with `plugin-source-invalid`)

- **Neutralization applied.** In `_compose`, `if not (isinstance(source, str) and _SOURCE_RE.fullmatch(source)` replaced with `if not (isinstance(source, str)`, so the source is not checked against the URL form.
- **Test.** `T::test_injection_is_refused_as_plugin_source_invalid` (parametrized: 7 source cases, 4 commit cases, 4 plugin-directory cases).
- **Red** (first lines and last lines of the capture; the 7 source cases fail with `'written'` where the refusal was expected, and the 8 commit and plugin-directory cases stay green because those validations were not neutralized):

```
FFFFFFF........                                                          [100%]
=================================== FAILURES ===================================
_ test_injection_is_refused_as_plugin_source_invalid[plugin_source-https://github.com/a/b'.git] _
...
>       _refusal(_compose(w, **{field: value}), "plugin-source-invalid")
...
E       AssertionError: {'action': 'written', 'reason': None, 'text': '#!/bin/bash
...
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-https://github.com/a/b'.git]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-https://github.com/a/b .git]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-https://github.com/a/$(id).git]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-https://github.com/a/b;ls]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-https://user:pw@github.com/a/b.git]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-http://github.com/a/b.git]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_injection_is_refused_as_plugin_source_invalid[plugin_source-git@github.com:a/b.git]
7 failed, 8 passed in 6.02s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:282`: `    if not (isinstance(source, str) and _SOURCE_RE.fullmatch(source)`.
- **Green.**

```
...............                                                          [100%]
15 passed in 5.49s
```

## Not proven

The commit validation and the plugin-directory validation inside B4's guarded surface were not neutralized separately: the order's declared B4 neutralizes the source validation only. Their cases in the injection test are green under the B4 red, so a neutralization of either would be a further, undeclared element.
