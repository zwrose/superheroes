# WO-1 (#2581) bite-proofs — reviews read the layer and core.md the storage mode picks

Detector file: `plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py`. Each element below was
neutralized by a targeted edit and restored by the inverse edit (no `git checkout`, `restore`, `reset` or
`stash`). Every command ran from the worktree root as
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest <node> -q -p no:randomly`.
Redaction: none needed (no secrets); the one line `warning: The UV_NATIVE_TLS environment variable is
deprecated ...` that the runner prints first is left out of each capture, and the traceback's local-variable
dump lines are kept as printed. Every capture is far under the 32 KiB ceiling.

The restore receipt of each entry is the restored line(s) quoted back from the file after the inverse edit.

## BP1 — `calibration_resolve.resolve` early global-layer return

**Guarded element:** `_mode_layer` feeding the early return in `resolve` (`calibration_resolve.py`) — axis: the
review reads the layer configure writes, so a stale in-repo copy never beats the mode's layer.

**Neutralization:** in `_mode_layer`, `return path if os.path.isfile(path) else None` became `return None`.

**Node:** `test_storage_mode_calibration_2581.py::test_r_layer_global`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________________ test_r_layer_global ______________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_r_layer_global0')
cwd = '/tmp/claude-0/pytest-of-root/pytest-1/test_r_layer_global0/repo'
root = '/tmp/claude-0/pytest-of-root/pytest-1/test_r_layer_global0/_store_isolation'

    def test_r_layer_global(tmp_path, cwd, root):
        # axis: a stale in-repo layer never beats the global layer when the registry says global
        _register(cwd, root, mr.GLOBAL)
        _put(_global(cwd, root, "core.md"), _CORE_TEXT)
        layer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
        _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
        out = cr.resolve(cwd, root=root)
>       assert out["dispatch_layer"] == layer
E       AssertionError: assert '/tmp/claude-...eview-crew.md' == '/tmp/claude-...eview-crew.md'
E         
E         Skipping 49 identical leading characters in diff, use -v to show
E         - r_global0/_store_isolation/projects/238a7b644f5fb344/config/review-crew.md
E         + r_global0/repo/.claude/superheroes/review-crew.md

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:99: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_layer_global
1 failed in 0.28s
```

**Restore:** inverse edit, `return None` back to `return path if os.path.isfile(path) else None` in `_mode_layer`.

**Restore receipt:** `calibration_resolve.py:131` reads `        return path if os.path.isfile(path) else None` inside `_mode_layer`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```

## BP2 — `core_md.layer_path` both-copies branch

**Guarded element:** the both-regular-files branch in `core_md.layer_path` (`core_md.py:2607`) — axis: with both
copies of a hero layer present, the layer is the one the storage mode picks, never the one beside a sole core.md.

**Neutralization:** `if os.path.isfile(in_repo_layer) and os.path.isfile(global_layer):` became
`if False and os.path.isfile(in_repo_layer) and os.path.isfile(global_layer):`.

**Node:** `test_storage_mode_calibration_2581.py::test_r_layer_corner`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________________ test_r_layer_corner ______________________________

cwd = '/tmp/claude-0/pytest-of-root/pytest-3/test_r_layer_corner0/repo'
root = '/tmp/claude-0/pytest-of-root/pytest-3/test_r_layer_corner0/_store_isolation'

    def test_r_layer_corner(cwd, root):
        # axis: the layer is the mode's, never the one beside a sole in-repo core.md
        _register(cwd, root, mr.GLOBAL)
        _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
        glayer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
        _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
        assert not os.path.exists(_global(cwd, root, "core.md"))
>       assert cr.resolve(cwd, root=root)["dispatch_layer"] == glayer
E       AssertionError: assert '/tmp/claude-...eview-crew.md' == '/tmp/claude-...eview-crew.md'
E         
E         Skipping 49 identical leading characters in diff, use -v to show
E         - r_corner0/_store_isolation/projects/238a7b644f5fb344/config/review-crew.md
E         + r_corner0/repo/.claude/superheroes/review-crew.md

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:120: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_layer_corner
1 failed in 0.43s
```

**Restore:** inverse edit, `if False and os.path.isfile(in_repo_layer)` back to `if os.path.isfile(in_repo_layer)`.

**Restore receipt:** `core_md.py:2607` reads `    if os.path.isfile(in_repo_layer) and os.path.isfile(global_layer):`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.29s
```

## BP3 — `regular_core` in `_with_dispatch_fields`

**Guarded element:** the `regular_core(cwd, root)` term of `dispatch_core` — axis: dispatch_core is a regular
core.md whenever one exists, the mode-selected one when both do.

**Neutralization:** the two lines `        regular_core(cwd, root)` / `        or out.get("core_path")` became the one line
`        out.get("core_path")`.

**Node:** `test_storage_mode_calibration_2581.py::test_r_core_p2`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________________________ test_r_core_p2 ________________________________

cwd = '/tmp/claude-0/pytest-of-root/pytest-5/test_r_core_p20/repo'
root = '/tmp/claude-0/pytest-of-root/pytest-5/test_r_core_p20/_store_isolation'

    def test_r_core_p2(cwd, root):
        # axis: dispatch_core is the sole regular core.md, whichever layer is the dispatch layer
        _register(cwd, root, mr.GLOBAL)
        core = _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
        _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
>       assert cr.resolve(cwd, root=root)["dispatch_core"] == core
E       AssertionError: assert '/tmp/claude-...eview-crew.md' == '/tmp/claude-...eroes/core.md'
E         
E         Skipping 44 identical leading characters in diff, use -v to show
E         - _core_p20/repo/.claude/superheroes/core.md
E         + _core_p20/_store_isolation/projects/238a7b644f5fb344/config/review-crew.md

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:155: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_core_p2
1 failed in 0.31s
```

**Restore:** inverse edit, re-inserting `        regular_core(cwd, root)` before `        or out.get("core_path")`.

**Restore receipt (quoted from `calibration_resolve.py:170-174`):**
```
    out["dispatch_core"] = (
        regular_core(cwd, root)
        or out.get("core_path")
        or (legacy if leg_ok else None)
        or (layer if layer_ok else None)
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.38s
```

## BP4 — `calibration_pin.capture` regular-core preference

**Guarded element:** `calibration_resolve.regular_core(repo_root) or` in `capture` — axis: the pinned core is a
regular core.md that beats a non-file peer.

**Neutralization:** `mode_core = calibration_resolve.regular_core(repo_root) or _mode_core(repo_root)` became
`mode_core = _mode_core(repo_root)`.

**Node:** `test_storage_mode_calibration_2581.py::test_r_pin_nonfile_peer`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________________ test_r_pin_nonfile_peer ____________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_r_pin_nonfile_peer0')
cwd = '/tmp/claude-0/pytest-of-root/pytest-7/test_r_pin_nonfile_peer0/repo'
root = '/tmp/claude-0/pytest-of-root/pytest-7/test_r_pin_nonfile_peer0/_store_isolation'

    def test_r_pin_nonfile_peer(tmp_path, cwd, root):
        # axis: a regular core.md beats a non-file peer in the session pin
        _register(cwd, root, mr.GLOBAL)
        core = _put(_in_repo(cwd, "core.md"), _CORE_TEXT)
        os.makedirs(_global(cwd, root, "core.md"))
        pin = calibration_pin.capture(cwd, str(tmp_path / "session-pin"))
>       assert pin["files"]["core"]["source"] == core
E       AssertionError: assert '/tmp/claude-...onfig/core.md' == '/tmp/claude-...eroes/core.md'
E         
E         Skipping 53 identical leading characters in diff, use -v to show
E         - ile_peer0/repo/.claude/superheroes/core.md
E         + ile_peer0/_store_isolation/projects/238a7b644f5fb344/config/core.md

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:201: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_pin_nonfile_peer
1 failed in 0.39s
```

**Restore:** inverse edit, the old one-call line replaced with the two-call line.

**Restore receipt:** `calibration_pin.py:164` reads
`        mode_core = calibration_resolve.regular_core(repo_root) or _mode_core(repo_root)`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.31s
```

## BP5 — `candidate_profile_paths` mode-layer-first

**Guarded element:** the prepend of the mode layer in `candidate_profile_paths` — axis: the model-tier gate reads
the picked layer first.

**Neutralization:** `if mode_layer is not None:` became `if False and mode_layer is not None:` (skips the prepend).

**Node:** `test_storage_mode_calibration_2581.py::test_r_gate`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________________ test_r_gate __________________________________

cwd = '/tmp/claude-0/pytest-of-root/pytest-9/test_r_gate0/repo'
root = '/tmp/claude-0/pytest-of-root/pytest-9/test_r_gate0/_store_isolation'

    def test_r_gate(cwd, root):
        # axis: the model-tier gate reads the picked layer first
        _register(cwd, root, mr.GLOBAL)
        _put(_global(cwd, root, "core.md"), _CORE_TEXT)
        glayer = _put(_global(cwd, root, "review-crew.md"), _GLOBAL_LAYER)
        _put(_in_repo(cwd, "review-crew.md"), _STALE_LAYER)
>       assert model_tier_overrides.resolve_profile_path_for_gate(cwd, root=root)[0] == glayer
E       AssertionError: assert '/tmp/claude-...eview-crew.md' == '/tmp/claude-...eview-crew.md'
E         
E         Skipping 41 identical leading characters in diff, use -v to show
E         - t_r_gate0/_store_isolation/projects/238a7b644f5fb344/config/review-crew.md
E         + t_r_gate0/repo/.claude/superheroes/review-crew.md

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:211: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_gate
1 failed in 0.32s
```

**Restore:** inverse edit, `if False and mode_layer is not None:` back to `if mode_layer is not None:`.

**Restore receipt:** `calibration_resolve.py:149` reads `    if mode_layer is not None:` (the only other match, line 194, is the
`resolve` early return and was not touched).

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.34s
```

## BP6 — `_record_mode` registry requirement

**Guarded element:** the `raise _Refused("storage-mode-unrecorded", ...)` in `cloud_setup_text._record_mode` — axis:
a global calibration that holds a hero layer is placed only with a valid registry.

**Neutralization:** the four-line `raise _Refused("storage-mode-unrecorded", ...)` statement was replaced with `return`.

**Node:** `test_storage_mode_calibration_2581.py::test_r_cloud_unrecorded[lock]`

**Raw red (the `text` value is elided by pytest itself):**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________________ test_r_cloud_unrecorded[lock] _________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_r_cloud_unrecorded_lock_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f441a7e9910>
attr = 'write_registry'
replacement = <function _write_returns_none at 0x7f4419c4bec0>

    @pytest.mark.parametrize("attr,replacement", [
        pytest.param("write_registry", _write_returns_none, id="lock"),
        pytest.param("write_registry", _write_raises, id="raises"),
        pytest.param("resolve", _resolve_provisional, id="provisional"),
    ])
    def test_r_cloud_unrecorded(tmp_path, monkeypatch, attr, replacement):
        # axis: a global store with a hero layer and no valid registry is never placed
        w = _registryless_world(tmp_path)
        monkeypatch.setattr(CS.mode_registry, attr, replacement)
>       _refusal(_compose(w), "storage-mode-unrecorded")

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:310: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'written', 'reason': None, 'text': '#!/bin/bash\n# Corner Shop · plugin 0.51.0 · calibration from 10 Oct\n#...s line.\necho "setup end" >> "$LOG"\nexit 0\n', 'header': 'Corner Shop · plugin 0.51.0 · calibration from 10 Oct', ...}
reason = 'storage-mode-unrecorded'

    def _refusal(result, reason):
>       assert result["action"] == "refused" and result["reason"] == reason, result
E       AssertionError: {'action': 'written', 'reason': None, 'text': '#!/bin/bash
E         # Corner Shop · plugin 0.51.0 · calibration from 10 Oct
E         #...s line.
E         echo "setup end" >> "$LOG"
E         exit 0
E         ', 'header': 'Corner Shop · plugin 0.51.0 · calibration from 10 Oct', ...}
E       assert ('written' == 'refused'
E         
E         - refused
E         + written)

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:268: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_cloud_unrecorded[lock]
1 failed in 0.35s
```

**Restore:** inverse edit, `return` back to the four-line `raise _Refused(...)`.

**Restore receipt (quoted from `cloud_setup_text.py:391-395`):**
```
    if recorded is None or recorded["storageMode"] != mode_registry.GLOBAL:
        raise _Refused("storage-mode-unrecorded", "The project keeps its calibration outside the "
                       "repository but its storage mode is not recorded, so a cloud session could "
                       "read a stale in-repository copy instead. Run superheroes:configure on this "
                       "machine to record it, then compose the setup text again.")
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.28s
```

## BP7 — `_record_mode` backfill write

**Guarded element:** the `mode_registry.write_registry(...)` call in `_record_mode` — axis: agreeing evidence is
recorded before the calibration is placed.

**Neutralization:** the two-line `mode_registry.write_registry(cwd, mode_registry.GLOBAL, ...)` call was replaced with `pass`.

**Node:** `test_storage_mode_calibration_2581.py::test_r_cloud_backfill`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________________ test_r_cloud_backfill _____________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_r_cloud_backfill0')

    def test_r_cloud_backfill(tmp_path):
        # axis: agreeing evidence is recorded before the calibration is placed
        w = _registryless_world(tmp_path)
>       assert _compose(w)["action"] == "written"
E       AssertionError: assert 'refused' == 'written'
E         
E         - written
E         + refused

/home/user/wt-2581/plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py:284: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_mode_calibration_2581.py::test_r_cloud_backfill
1 failed in 0.34s
```

**Restore:** inverse edit, `pass` back to the two-line `write_registry` call.

**Restore receipt (quoted from `cloud_setup_text.py:381-385`):**
```
    if found["source"] == "evidence":
        try:
            mode_registry.write_registry(
                cwd, mode_registry.GLOBAL, store_core.derive_identifiers(cwd)["remote_hash"], root)
        except Exception:
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.36s
```

## Not proven

No guarded element is in no class. `test_r_cloud_unrecorded[raises]` and `[provisional]`, `test_r_cloud_greenfield`,
`test_r_stamped_files_readonly`, `test_r_unchanged[*]`, `test_r_layer_legacy`, `test_r_layer_inrepo`, `test_r_core_p3`
and `test_r_cloud_placed` were not neutralized separately: the order's declared set is BP1-BP7, and the first green
run showed all 18 tests passing.

## BP8 — candidate order keeps an unreadable candidate first (WO-3)

**Guarded element:** the early return in `candidate_profile_paths`, `plugins/superheroes/lib/calibration_resolve.py:149-150`.
**Axis:** a present candidate that is not a regular file keeps today's order, so the tier gate still refuses it as unreadable.
**Detector:** `plugins/superheroes/lib/tests/test_model_tier_overrides.py::test_effective_tiers_for_gate_unreadable_in_repo_does_not_fall_through_to_global` (unedited).

**Neutralization:** changed the condition
`if any(os.path.lexists(c) and not os.path.isfile(c) for c in candidates):` to
`if False and any(os.path.lexists(c) and not os.path.isfile(c) for c in candidates):`.

**Raw red** (single node, `-q -p no:randomly`; the `UV_NATIVE_TLS` warning line omitted, tmp paths unredacted, no secrets present):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_effective_tiers_for_gate_unreadable_in_repo_does_not_fall_through_to_global _
...
        gate = MTO.effective_tiers_for_gate(cwd=str(repo), root=default_store)
>       assert gate.status == MTO.TIERS_UNREADABLE
E       AssertionError: assert 'ok' == 'unreadable'
E         
E         - unreadable
E         + ok

/home/user/wt-2581/plugins/superheroes/lib/tests/test_model_tier_overrides.py:868: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_model_tier_overrides.py::test_effective_tiers_for_gate_unreadable_in_repo_does_not_fall_through_to_global
1 failed in 0.48s
```
(Elided: the test's fixture-setup source lines between the header and the `gate = ...` line, about 20 lines.)

**Restore:** inverse edit, `if False and any(` back to `if any(`.

**Restore receipt (quoted from `calibration_resolve.py:148-150`):**
```
    # axis: a present candidate that is not a regular file keeps today's order, so the tier gate still refuses it as unreadable
    if any(os.path.lexists(c) and not os.path.isfile(c) for c in candidates):
        return candidates
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 3.67s
```
