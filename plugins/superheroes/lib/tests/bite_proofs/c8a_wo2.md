# C8a-WO2 bite-proof — calibration guard, launch lines, base commit, wait slices

**Provenance:** claude write channel (sonnet implementer).

## Summary

| Element | Guarded element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| C6-a | the model-tier writer goes through the guarded `store_core.atomic_write` | `update_overrides` writes a calibration profile in a cloud session (it must raise `CalibrationWriteRefused` for the in-repo layer, the store layer and both legacy paths) | `test_calibration_paths.py::test_update_overrides_refuses_in_a_cloud_session_for_every_layer` | proven |
| C6-b | the in-repo legacy review profile name in `calibration_paths._classify` | `<repo>/.claude/review-profile.md` is classified as a calibration path | `test_calibration_paths.py::test_classification_table[legacy-inrepo-profile]` | proven |
| C6-c | the legacy store name in `calibration_paths._classify` | `<review store root>/entries/<hash>/review-profile.md` is classified as a calibration path | `test_calibration_paths.py::test_classification_table[legacy-store-profile]` | proven |
| C6-d | `mode_migrate._cloud_refusal`, called first by `rebind` and `recover` | in a cloud session `rebind` leaves both store trees (same paths, same bytes) unchanged and returns the blocked refusal | `test_calibration_paths.py::test_rebind_refuses_in_a_cloud_session_before_any_mutation` | proven |
| C6-e | the `except CalibrationWriteRefused` arm of `model_tier_overrides.main write` | the CLI prints one JSON line `{"ok": false, "reason": "calibration-write-in-cloud-session"}` and exits 1 | `test_calibration_paths.py::test_cli_write_prints_one_json_refusal_line_and_exits_1_in_a_cloud_session` | proven |
| FU4-a | no launch label literal in `launcher.py` / `cloud_builder.py` | an `ast` scan of string constants outside docstrings finds none of the four label strings | `test_launch_lines.py::test_no_launch_label_literal_remains_in_the_two_modules[launcher.py]` | proven |
| FU5-a | the lowercase 40-hex check on the cloud launch's base commit in `compose_launch` | any base that is not a full lowercase 40-hex sha is refused with `premise-base-commit-invalid` (missing or blank stays `premise-missing-field:baseCommit`) | `test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse` | proven |
| FU7-a | the `slice_wait = MAX_SYNC_WAIT` reset in `engine_dispatch.dispatch_review`'s slice loop | history time is charged to the first wait slice only; slices 1 and 2 get the full `MAX_SYNC_WAIT` | `test_dispatch_review_cloud_history.py::test_history_time_is_charged_to_the_first_wait_slice_only` | proven |

Neutralizations were applied and restored with a one-shot script doing an exact, unique-match string
replace (and its inverse) over the manifest's `old`/`new` text, never `git checkout`/`restore`/`stash`.
Each red and green run is the one node alone: `scripts/pinned-python -B -m pytest <node> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` warning line is uv's own noise, kept as captured.

---

## C6-a

**guarded element:** the model-tier writer goes through the guarded `store_core.atomic_write`. **axis:** `update_overrides` writes a calibration profile in a cloud session (it must raise `CalibrationWriteRefused` for the in-repo layer, the store layer and both legacy paths).

**file:** `plugins/superheroes/lib/model_tier_overrides.py`. **node:** `plugins/superheroes/lib/tests/test_calibration_paths.py::test_update_overrides_refuses_in_a_cloud_session_for_every_layer`

**neutralization:** the exact text
```
    store_core.atomic_write(profile_path, replace_model_tiers_block(text, current))
```
became
```
    with open(profile_path, "w", encoding="utf-8") as fh:
        fh.write(replace_model_tiers_block(text, current))
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_update_overrides_refuses_in_a_cloud_session_for_every_layer[in-repo-layer] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_update_overrides_refuses_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffa281134d0>
layer = 'in-repo-layer'

    @pytest.mark.parametrize("layer", ["in-repo-layer", "store-layer", "legacy-in-repo", "legacy-store"])
    def test_update_overrides_refuses_in_a_cloud_session_for_every_layer(tmp_path, monkeypatch, layer):
        # axis: the model-tier writer goes through the guarded atomic_write, not a private os.replace —
        # see bite-proof record c8a_wo2.md
        path = _profile_layers(tmp_path)[layer]
        path.parent.mkdir(parents=True)
        path.write_bytes(_BLOCK.encode())
        before = _snapshot(tmp_path)
        _cloud(monkeypatch)
>       with pytest.raises(sc.CalibrationWriteRefused):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE CalibrationWriteRefused

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:237: Failed
_ test_update_overrides_refuses_in_a_cloud_session_for_every_layer[store-layer] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_update_overrides_refuses_1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffa2833dcd0>
layer = 'store-layer'

    @pytest.mark.parametrize("layer", ["in-repo-layer", "store-layer", "legacy-in-repo", "legacy-store"])
    def test_update_overrides_refuses_in_a_cloud_session_for_every_layer(tmp_path, monkeypatch, layer):
        # axis: the model-tier writer goes through the guarded atomic_write, not a private os.replace —
        # see bite-proof record c8a_wo2.md
        path = _profile_layers(tmp_path)[layer]
        path.parent.mkdir(parents=True)
        path.write_bytes(_BLOCK.encode())
        before = _snapshot(tmp_path)
        _cloud(monkeypatch)
>       with pytest.raises(sc.CalibrationWriteRefused):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE CalibrationWriteRefused

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:237: Failed
_ test_update_overrides_refuses_in_a_cloud_session_for_every_layer[legacy-in-repo] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_update_overrides_refuses_2')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffa28113a10>
layer = 'legacy-in-repo'

    @pytest.mark.parametrize("layer", ["in-repo-layer", "store-layer", "legacy-in-repo", "legacy-store"])
    def test_update_overrides_refuses_in_a_cloud_session_for_every_layer(tmp_path, monkeypatch, layer):
        # axis: the model-tier writer goes through the guarded atomic_write, not a private os.replace —
        # see bite-proof record c8a_wo2.md
        path = _profile_layers(tmp_path)[layer]
        path.parent.mkdir(parents=True)
        path.write_bytes(_BLOCK.encode())
        before = _snapshot(tmp_path)
        _cloud(monkeypatch)
>       with pytest.raises(sc.CalibrationWriteRefused):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE CalibrationWriteRefused

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:237: Failed
_ test_update_overrides_refuses_in_a_cloud_session_for_every_layer[legacy-store] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_update_overrides_refuses_3')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffa2801da90>
layer = 'legacy-store'

    @pytest.mark.parametrize("layer", ["in-repo-layer", "store-layer", "legacy-in-repo", "legacy-store"])
    def test_update_overrides_refuses_in_a_cloud_session_for_every_layer(tmp_path, monkeypatch, layer):
        # axis: the model-tier writer goes through the guarded atomic_write, not a private os.replace —
        # see bite-proof record c8a_wo2.md
        path = _profile_layers(tmp_path)[layer]
        path.parent.mkdir(parents=True)
        path.write_bytes(_BLOCK.encode())
        before = _snapshot(tmp_path)
        _cloud(monkeypatch)
>       with pytest.raises(sc.CalibrationWriteRefused):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE CalibrationWriteRefused

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:237: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_update_overrides_refuses_in_a_cloud_session_for_every_layer[in-repo-layer]
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_update_overrides_refuses_in_a_cloud_session_for_every_layer[store-layer]
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_update_overrides_refuses_in_a_cloud_session_for_every_layer[legacy-in-repo]
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_update_overrides_refuses_in_a_cloud_session_for_every_layer[legacy-store]
4 failed in 0.31s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/model_tier_overrides.py` reads again
```
    store_core.atomic_write(profile_path, replace_model_tiers_block(text, current))
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....                                                                     [100%]
4 passed in 0.49s
EXIT=0
```

---

## C6-b

**guarded element:** the in-repo legacy review profile name in `calibration_paths._classify`. **axis:** `<repo>/.claude/review-profile.md` is classified as a calibration path.

**file:** `plugins/superheroes/lib/calibration_paths.py`. **node:** `plugins/superheroes/lib/tests/test_calibration_paths.py::test_classification_table[legacy-inrepo-profile]`

**neutralization:** the exact text
```
    if parts[-len(legacy_inrepo):] == legacy_inrepo:
        return True
```
became
```
    if False and parts[-len(legacy_inrepo):] == legacy_inrepo:
        return True
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_classification_table[legacy-inrepo-profile] _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_classification_table_lega0')
rel = 'repo/.claude/review-profile.md', expected = True

    @pytest.mark.parametrize("rel,expected", [(r, e) for _, r, e in _TABLE], ids=[i for i, _, _ in _TABLE])
    def test_classification_table(tmp_path, rel, expected):
        # axis: each path kind is (or is not) classified as calibration, the two legacy review-profile
        # locations included — see bite-proof record c8a_wo2.md
>       assert cp.is_calibration_path(str(tmp_path / rel)) is expected
E       AssertionError: assert False is True
E        +  where False = <function is_calibration_path at 0x7f000d8387c0>('/tmp/claude-0/pytest-of-root/pytest-24/test_classification_table_lega0/repo/.claude/review-profile.md')
E        +    where <function is_calibration_path at 0x7f000d8387c0> = cp.is_calibration_path
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-24/test_classification_table_lega0/repo/.claude/review-profile.md' = str((PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_classification_table_lega0') / 'repo/.claude/review-profile.md'))

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_classification_table[legacy-inrepo-profile]
1 failed in 0.23s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/calibration_paths.py` reads again
```
    if parts[-len(legacy_inrepo):] == legacy_inrepo:
        return True
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.26s
EXIT=0
```

---

## C6-c

**guarded element:** the legacy store name in `calibration_paths._classify`. **axis:** `<review store root>/entries/<hash>/review-profile.md` is classified as a calibration path.

**file:** `plugins/superheroes/lib/calibration_paths.py`. **node:** `plugins/superheroes/lib/tests/test_calibration_paths.py::test_classification_table[legacy-store-profile]`

**neutralization:** the exact text
```
    if (len(parts) >= 3 and parts[-3] == LEGACY_STORE_ENTRIES_DIRNAME
            and parts[-1] == LEGACY_STORE_PROFILE_FILENAME):
        return True
```
became
```
    if False and (len(parts) >= 3 and parts[-3] == LEGACY_STORE_ENTRIES_DIRNAME
            and parts[-1] == LEGACY_STORE_PROFILE_FILENAME):
        return True
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_classification_table[legacy-store-profile] ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_classification_table_lega0')
rel = 'legacy/entries/abc123/review-profile.md', expected = True

    @pytest.mark.parametrize("rel,expected", [(r, e) for _, r, e in _TABLE], ids=[i for i, _, _ in _TABLE])
    def test_classification_table(tmp_path, rel, expected):
        # axis: each path kind is (or is not) classified as calibration, the two legacy review-profile
        # locations included — see bite-proof record c8a_wo2.md
>       assert cp.is_calibration_path(str(tmp_path / rel)) is expected
E       AssertionError: assert False is True
E        +  where False = <function is_calibration_path at 0x7fcaa723c7c0>('/tmp/claude-0/pytest-of-root/pytest-27/test_classification_table_lega0/legacy/entries/abc123/review-profile.md')
E        +    where <function is_calibration_path at 0x7fcaa723c7c0> = cp.is_calibration_path
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-27/test_classification_table_lega0/legacy/entries/abc123/review-profile.md' = str((PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_classification_table_lega0') / 'legacy/entries/abc123/review-profile.md'))

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_classification_table[legacy-store-profile]
1 failed in 0.23s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/calibration_paths.py` reads again
```
    if (len(parts) >= 3 and parts[-3] == LEGACY_STORE_ENTRIES_DIRNAME
            and parts[-1] == LEGACY_STORE_PROFILE_FILENAME):
        return True
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.24s
EXIT=0
```

---

## C6-d

**guarded element:** `mode_migrate._cloud_refusal`, called first by `rebind` and `recover`. **axis:** in a cloud session `rebind` leaves both store trees (same paths, same bytes) unchanged and returns the blocked refusal.

**file:** `plugins/superheroes/lib/mode_migrate.py`. **node:** `plugins/superheroes/lib/tests/test_calibration_paths.py::test_rebind_refuses_in_a_cloud_session_before_any_mutation`

**neutralization:** the exact text
```
    if store_core.in_cloud_session():
        return {"status": "blocked", "reason": CLOUD_REFUSAL_REASON}
```
became
```
    if False and store_core.in_cloud_session():
        return {"status": "blocked", "reason": CLOUD_REFUSAL_REASON}
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_rebind_refuses_in_a_cloud_session_before_any_mutation __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_rebind_refuses_in_a_cloud0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f88ae9bf200>

    def test_rebind_refuses_in_a_cloud_session_before_any_mutation(tmp_path, monkeypatch):
        # axis: rebind moves the registry and config tree only outside a cloud session; in one both
        # trees are untouched — see bite-proof record c8a_wo2.md
        repo, root, common = _rebind_scenario(tmp_path, monkeypatch)
        before = _snapshot(tmp_path)
        _cloud(monkeypatch)
        refused = mm.rebind(str(repo), root=root)
>       assert _snapshot(tmp_path) == before
E       AssertionError: assert {'/tmp/claude...s': None, ...} == {'/tmp/claude...s': None, ...}
E         
E         Omitting 10 identical items, use -vv to show
E         Left contains 5 more items:
E         {'/tmp/claude-0/pytest-of-root/pytest-30/test_rebind_refuses_in_a_cloud0/store/projects/6d5c8a7b6c8ca477/config/core.md': b'OLD '
E                                                                                                                                   b'core'
E                                                                                                                                   b'\n',
E          '/tmp/claude-0/pytest-of-root/pytest-30/test_rebind_refuses_in_a_cloud0/store/projects/6d5c8a7b6c8ca477/config/review-crew.md': b'crew'...
E         
E         ...Full output truncated (137 lines hidden), use '-vv' to show

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:337: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_rebind_refuses_in_a_cloud_session_before_any_mutation
1 failed in 0.42s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/mode_migrate.py` reads again
```
    if store_core.in_cloud_session():
        return {"status": "blocked", "reason": CLOUD_REFUSAL_REASON}
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.40s
EXIT=0
```

---

## C6-e

**guarded element:** the `except CalibrationWriteRefused` arm of `model_tier_overrides.main write`. **axis:** the CLI prints one JSON line `{"ok": false, "reason": "calibration-write-in-cloud-session"}` and exits 1.

**file:** `plugins/superheroes/lib/model_tier_overrides.py`. **node:** `plugins/superheroes/lib/tests/test_calibration_paths.py::test_cli_write_prints_one_json_refusal_line_and_exits_1_in_a_cloud_session`

**neutralization:** the exact text
```
        except store_core.CalibrationWriteRefused:
            sys.stdout.write(json.dumps({
                "ok": False,
                "reason": "calibration-write-in-cloud-session",
            }) + "\n")
            return 1
```
became
```
        except store_core.CalibrationWriteRefused:
            raise
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_cli_write_prints_one_json_refusal_line_and_exits_1_in_a_cloud_session __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-32/test_cli_write_prints_one_json0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffb79ab3230>
capsys = <_pytest.capture.CaptureFixture object at 0x7ffb7a9b2090>

    def test_cli_write_prints_one_json_refusal_line_and_exits_1_in_a_cloud_session(
            tmp_path, monkeypatch, capsys):
        # axis: the CLI turns the cloud refusal into one JSON line and exit 1, not a traceback — see
        # bite-proof record c8a_wo2.md
        profile = _cli_profile(tmp_path)
        before = _snapshot(tmp_path)
        _cloud(monkeypatch)
>       rc = mto.main(["model_tier_overrides.py", "write", "--profile", str(profile),
                       "--set", "reviewer-deep=sonnet"])

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_calibration_paths.py:290: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/c8a-wo2/plugins/superheroes/lib/model_tier_overrides.py:520: in main
    result = update_overrides(profile, updates, clear_roles)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/c8a-wo2/plugins/superheroes/lib/model_tier_overrides.py:257: in update_overrides
    store_core.atomic_write(profile_path, replace_model_tiers_block(text, current))
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

path = '/tmp/claude-0/pytest-of-root/pytest-32/test_cli_write_prints_one_json0/repo/.claude/superheroes/review-crew.md'
text = '## Model tiers\nreviewer-deep: sonnet\n', tmp_prefix = '.store-core.'

    def atomic_write(path, text, tmp_prefix=".store-core."):
        """Write text atomically via temp file + os.replace in the same directory.
    
        In a cloud session (CLAUDE_CODE_REMOTE == "true") a calibration file is never written:
        raises CalibrationWriteRefused before anything touches the disk."""
        if in_cloud_session() and is_calibration_path(path):
>           raise CalibrationWriteRefused("calibration-write-in-cloud-session: %s" % path)
E           store_core.CalibrationWriteRefused: calibration-write-in-cloud-session: /tmp/claude-0/pytest-of-root/pytest-32/test_cli_write_prints_one_json0/repo/.claude/superheroes/review-crew.md

/home/user/c8a-wo2/plugins/superheroes/lib/store_core.py:477: CalibrationWriteRefused
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_cli_write_prints_one_json_refusal_line_and_exits_1_in_a_cloud_session
1 failed in 0.28s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/model_tier_overrides.py` reads again
```
        except store_core.CalibrationWriteRefused:
            sys.stdout.write(json.dumps({
                "ok": False,
                "reason": "calibration-write-in-cloud-session",
            }) + "\n")
            return 1
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.25s
EXIT=0
```

---

## FU4-a

**guarded element:** no launch label literal in `launcher.py` / `cloud_builder.py`. **axis:** an `ast` scan of string constants outside docstrings finds none of the four label strings.

**file:** `plugins/superheroes/lib/launcher.py`. **node:** `plugins/superheroes/lib/tests/test_launch_lines.py::test_no_launch_label_literal_remains_in_the_two_modules[launcher.py]`

**neutralization:** the exact text
```
        environment_line = launch_lines.format_line(launch_lines.ENVIRONMENT, cloud_environment)
```
became
```
        environment_line = "Cloud environment: %s" % cloud_environment
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_no_launch_label_literal_remains_in_the_two_modules[launcher.py] _____

module = 'launcher.py'

    @pytest.mark.parametrize("module", ["launcher.py", "cloud_builder.py"])
    def test_no_launch_label_literal_remains_in_the_two_modules(module):
        # axis: the labels are spelled in launch_lines only, not respelled in the composer or the
        # parser (ast source scan; comments and docstrings are out of scope) — see bite-proof record
        # c8a_wo2.md
        found = [(line, text) for line, text in _string_literals_outside_docstrings(
            os.path.join(_LIB, module)) for label in ll.LABELS if label in text]
>       assert found == [], "launch label literal in %s: %r" % (module, found)
E       AssertionError: launch label literal in launcher.py: [(1342, 'Cloud environment: %s')]
E       assert [(1342, 'Clou...ronment: %s')] == []
E         
E         Left contains one more item: (1342, 'Cloud environment: %s')
E         Use -v to get more diff

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:69: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_no_launch_label_literal_remains_in_the_two_modules[launcher.py]
1 failed in 0.42s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/launcher.py` reads again
```
        environment_line = launch_lines.format_line(launch_lines.ENVIRONMENT, cloud_environment)
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.44s
EXIT=0
```

---

## FU5-a

**guarded element:** the lowercase 40-hex check on the cloud launch's base commit in `compose_launch`. **axis:** any base that is not a full lowercase 40-hex sha is refused with `premise-base-commit-invalid` (missing or blank stays `premise-missing-field:baseCommit`).

**file:** `plugins/superheroes/lib/launcher.py`. **node:** `plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse`

**neutralization:** the exact text
```
        if not valid_adopts_head(base):
            return _fail("premise-base-commit-invalid")
```
became
```
        if not base.strip():
            return _fail("premise-base-commit-invalid")
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....FFFFFFFF                                                            [100%]
=================================== FAILURES ===================================
__ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[39-hex] __

base = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
__ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[41-hex] __

base = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
_ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[uppercase] _

base = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
_ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[mixed-case] _

base = 'ABCDEF0123ABCDEF0123ABCDEF0123ABCDEF0123'
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
___ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[HEAD] ___

base = 'HEAD', reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
_ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[non-hex-char] _

base = 'gaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
_ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[padded-valid-sha] _

base = ' aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa '
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
_ test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[trailing-newline] _

base = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n'
reason = 'premise-base-commit-invalid'

    @pytest.mark.parametrize("base,reason", [
        (None, "premise-missing-field:baseCommit"),
        ("", "premise-missing-field:baseCommit"),
        ("   ", "premise-missing-field:baseCommit"),
        ("\n\t ", "premise-missing-field:baseCommit"),
        (12345, "premise-missing-field:baseCommit"),
        ("a" * 39, "premise-base-commit-invalid"),
        ("a" * 41, "premise-base-commit-invalid"),
        ("A" * 40, "premise-base-commit-invalid"),
        ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
        ("HEAD", "premise-base-commit-invalid"),
        ("g" + "a" * 39, "premise-base-commit-invalid"),
        (" " + SHA + " ", "premise-base-commit-invalid"),
        (SHA + "\n", "premise-base-commit-invalid"),
    ], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
            "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
    def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
        # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
        # missing or invalid accordingly — see bite-proof record c8a_wo2.md
        result = _compose(base)
>       assert result["ok"] is False
E       assert True is False

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_launch_lines.py:117: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[39-hex]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[41-hex]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[uppercase]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[mixed-case]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[HEAD]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[non-hex-char]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[padded-valid-sha]
FAILED plugins/superheroes/lib/tests/test_launch_lines.py::test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse[trailing-newline]
8 failed, 5 passed in 0.47s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/launcher.py` reads again
```
        if not valid_adopts_head(base):
            return _fail("premise-base-commit-invalid")
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.............                                                            [100%]
13 passed in 0.36s
EXIT=0
```

---

## FU7-a

**guarded element:** the `slice_wait = MAX_SYNC_WAIT` reset in `engine_dispatch.dispatch_review`'s slice loop. **axis:** history time is charged to the first wait slice only; slices 1 and 2 get the full `MAX_SYNC_WAIT`.

**file:** `plugins/superheroes/lib/engine_dispatch.py`. **node:** `plugins/superheroes/lib/tests/test_dispatch_review_cloud_history.py::test_history_time_is_charged_to_the_first_wait_slice_only`

**neutralization:** the exact text
```
            slice_wait = MAX_SYNC_WAIT
            time.sleep(SUPERVISOR_POLL_INTERVAL)
    except resolved_inputs_vocab.UndeclaredSourceMarker as exc:
```
became
```
            time.sleep(SUPERVISOR_POLL_INTERVAL)
    except resolved_inputs_vocab.UndeclaredSourceMarker as exc:
```

**raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_history_time_is_charged_to_the_first_wait_slice_only ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-38/test_history_time_is_charged_t0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f3052879010>

    def test_history_time_is_charged_to_the_first_wait_slice_only(tmp_path, monkeypatch):
        # axis: the cloud history time comes off the first supervise slice only; every later slice gets
        # the full MAX_SYNC_WAIT (FU7) — see bite-proof record c8a_wo2.md
        import cloud_builder
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
        # The sanitized view commits with the ambient git config; a host that signs every commit
        # (commit.gpgsign=true with no signer reachable) would stop the view before the wait loop.
        monkeypatch.setattr(engine_dispatch.sanitized_view, "_GIT_IDENTITY",
                            engine_dispatch.sanitized_view._GIT_IDENTITY + ("-c", "commit.gpgsign=false"))
        shim = _ClockShim()
        monkeypatch.setattr(engine_dispatch, "time", shim)
        real_ensure_history = cloud_builder.ensure_history
    
        def slow_ensure_history(repo_root, **kw):
            result = real_ensure_history(repo_root, **kw)   # the view still builds
            shim.offset += 100.0                             # and history took about 100 s
            return result
    
        monkeypatch.setattr(cloud_builder, "ensure_history", slow_ensure_history)
        slices = []
    
        def fake_supervise(run_dir_real, *, run_kind, deadline, run_engine=None):
            slices.append(deadline - shim.monotonic())
            terminal = len(slices) >= 3
            return engine_dispatch._with_run_fields(
                {"ok": terminal, "terminal": terminal,
                 "reason": None if terminal else engine_dispatch.dispatch_outcome.REASON_RUNNING,
                 "detail": "captured", "attempts": 1, "forfeited": False},
                run_dir=run_dir_real, argv=[],
            )
    
        monkeypatch.setattr(engine_dispatch, "_supervise", fake_supervise)
        monkeypatch.setattr(engine_dispatch, "SUPERVISOR_POLL_INTERVAL", 0.01)
        clone, shas = make_shallow_clone(tmp_path)
        res = review(tmp_path, clone, shas[0], clean_review_runner(), max_wait=None)
        assert res["terminal"] is True, res
        assert res["cloudHistory"]["ok"] is True
        assert len(slices) == 3
        full = engine_dispatch.MAX_SYNC_WAIT
        assert abs(slices[0] - (full - 100)) < 5, slices
>       assert abs(slices[1] - full) < 5, slices
E       AssertionError: [439.94809861600015, 439.94809879900004, 439.9480995070003]
E       assert 100.05190120099996 < 5
E        +  where 100.05190120099996 = abs((439.94809879900004 - 540))

/home/user/c8a-wo2/plugins/superheroes/lib/tests/test_dispatch_review_cloud_history.py:241: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_dispatch_review_cloud_history.py::test_history_time_is_charged_to_the_first_wait_slice_only
1 failed in 3.11s
EXIT=1
```

**restore:** the inverse of the replacement above (the `new` text back to the `old` text).

**restore receipt:** after the restore `plugins/superheroes/lib/engine_dispatch.py` reads again
```
            slice_wait = MAX_SYNC_WAIT
            time.sleep(SUPERVISOR_POLL_INTERVAL)
    except resolved_inputs_vocab.UndeclaredSourceMarker as exc:
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 3.13s
EXIT=0
```

---

## Notes

- FU7-a touched `engine_dispatch.py` for the neutralize-and-restore only; `git diff --stat` on it is empty after the restore.
- C6-d's first red run (before the test asserted the trees first) failed on the returned status (`deferred` instead of the blocked refusal); the test was then reordered to assert the unchanged trees before the status, and the red above is from that final test.
- C6-a's first red run was a `tail`-filtered capture; the red above is its unfiltered re-run.
