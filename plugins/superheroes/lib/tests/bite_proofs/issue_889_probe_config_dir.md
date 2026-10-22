# #889 bite-proof — engine-auth checks the claude probe's config dir

**Provenance:** orchestrator-typed (light lane), claude-opus-5-5 (anthropic family), `plugins/superheroes/lib/conformance_probe.py`.

Each guarded element was neutralized by one targeted edit in production code only, inside a detached probe worktree at the final head `3abbe22bc` (first run at `88adfe548`, before review round 1 moved the stamp; re-run here), the single detector node was run red (selected by exact node id), the neutralization was undone by the inverse edit, the file's sha256 was compared with the value taken before (`ab4f345a…a1a961`, identical after each restore), and the same node was run green. Temp paths are the only redaction (`<tmp>` for the pytest temp root, `<probe>` for the probe worktree).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| B1 | the mismatch comparison (`preflight_entry`, claude branch) | a claude record probed under a dir other than the launch's is refused | `test_889_preflight_entry_refuses_a_claude_record_off_the_launch_dir[other-probe-config-dir-mismatch:claude]` |
| B2 | the stamp (`_probe_one_mode` reads the journaled `run-opened` `configDir`, feeding `configDir` and the evidence) | a real claude probe records the dir it ran under, so its record passes under that launch dir with `configDir=<dir>` in the evidence | `test_889_preflight_entry_passes_a_probed_claude_record_under_the_launch_dir` |

## Disclosures

- The unrecorded check (`probe-config-dir-unrecorded:claude`) and the fail-reason wording are exercised green by `test_889_preflight_entry_refuses_a_claude_record_off_the_launch_dir[None-probe-config-dir-unrecorded:claude]` and `test_889_wave11_claude_failed_others_green_holds_naming_claude_and_its_dir`, not separately neutralized.

---

## B1 — the mismatch comparison

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```diff
-            if launch_dir is None or probed_dir != launch_dir:
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
1 failed in 2.53s
```

**restore:** inverse edit; sha256 `ab4f345a0a1539869cbb0959495dab79d9935fe5eb22030b78ea0feb10a1a961` (matches the pre-neutralization value); `git status --short` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 3.35s
```

## B2 — the stamp

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```diff
     legs = _grade_legs(terminal, state, bound_exceeded)
-    pinned = (state.get("opened") or {}).get("configDir")
+    pinned = None
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
1 failed in 2.91s
```

**restore:** inverse edit; sha256 `ab4f345a0a1539869cbb0959495dab79d9935fe5eb22030b78ea0feb10a1a961`; `git status --short` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.53s
```
