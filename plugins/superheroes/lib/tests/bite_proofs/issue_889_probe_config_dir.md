# #889 bite-proof — engine-auth checks the claude probe's config dir

**Provenance:** orchestrator-typed (light lane), claude-opus-5-5 (anthropic family), `plugins/superheroes/lib/conformance_probe.py`.

Each guarded element was neutralized by one targeted edit in production code only, inside a detached probe worktree at the build head, the single detector node was run red (selected by exact node id), the neutralization was undone by the inverse edit, the file's sha256 was compared with the value taken before (`fdfd544b…f5ba60`, identical after each restore), and the same node was run green. Temp paths are the only redaction (`<tmp>` for the pytest temp root, `<probe>` for the probe worktree).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| B1 | the mismatch comparison (`preflight_entry`, claude branch) | a claude record probed under a dir other than the launch's is refused | `test_889_preflight_entry_refuses_a_claude_record_off_the_launch_dir[other-probe-config-dir-mismatch:claude]` |
| B2 | the stamp (`_probe_config_dir`, feeding `configDir` and the evidence) | a real claude probe records the dir it ran under, so its record passes under that launch dir with `configDir=<dir>` in the evidence | `test_889_preflight_entry_passes_a_probed_claude_record_under_the_launch_dir` |

## Disclosures

- The unrecorded check (`probe-config-dir-unrecorded:claude`) and the fail-reason wording are exercised green by `test_889_preflight_entry_refuses_a_claude_record_off_the_launch_dir[None-probe-config-dir-unrecorded:claude]` and `test_889_wave11_claude_failed_others_green_holds_naming_claude_and_its_dir`, not separately neutralized.

---

## B1 — the mismatch comparison

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```diff
-            if launch_dir is None or os.path.normpath(probed_dir) != launch_dir:
+            if False:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_conformance_probe.py::test_889_preflight_entry_refuses_a_claude_record_off_the_launch_dir[other-probe-config-dir-mismatch:claude]' -q -p no:cacheprovider
```

**raw red** (exit 1):
```
        payload, rc = CP.preflight_entry(
            repo, paths, calibration_rows=_calibration_rows(), launch_config_dir=launch,
        )
>       assert rc == 1
E       assert 0 == 1
<probe>/plugins/superheroes/lib/tests/test_conformance_probe.py:3771: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_889_preflight_entry_refuses_a_claude_record_off_the_launch_dir[other-probe-config-dir-mismatch:claude]
1 failed in 3.90s
```

**restore:** inverse edit; sha256 `fdfd544bc00bd09cf630688cecf14fa357273594d9da8c6f9e1ef62581f5ba60` (matches the pre-neutralization value); `git status --short` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.22s
```

## B2 — the stamp

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```diff
 def _probe_config_dir(engine, repo_root):
     """The config dir a claude probe child is pinned to — the same resolve `dispatch_review` makes. (#889)"""
-    if engine != "claude":
-        return None
-    return config_dir.resolve(env=os.environ, cwd=repo_root)
+    return None
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_conformance_probe.py::test_889_preflight_entry_passes_a_probed_claude_record_under_the_launch_dir' -q -p no:cacheprovider
```

**raw red** (exit 1):
```
        payload, rc = CP.preflight_entry(
            repo, paths, calibration_rows=_calibration_rows(), launch_config_dir=cfg,
        )
>       assert rc == 0
E       assert 1 == 0
<probe>/plugins/superheroes/lib/tests/test_conformance_probe.py:3739: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_889_preflight_entry_passes_a_probed_claude_record_under_the_launch_dir
1 failed in 4.81s
```

**restore:** inverse edit; sha256 `fdfd544bc00bd09cf630688cecf14fa357273594d9da8c6f9e1ef62581f5ba60`; `git status --short` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.77s
```
