# WO-A (#1858, C5 L5) bite-proof — the three L4 folds: v0, v4, v1–v3

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/round_driver.py`, `plugins/superheroes/eval/review_loop_runner.py`, `plugins/superheroes/lib/tests/test_l4_folds_1858.py`.

Declared guarded-element set (from the order): P-v0, P-v4, P-v1. Each was neutralized by an exact one-site text swap in production code only, the detector was run red alone, the neutralization was undone by the inverse text swap, and the same detector was run green. All commands ran from the worktree root `<repo>` (`/home/user/sh-1858`) with `-B -p no:cacheprovider`; nothing else in the output is redacted.

## Guarded elements

| ID | Guarded element | Axis | Detector |
|---|---|---|---|
| P-v0 | `SESSION_GENERATION = 4` (`round_driver.py:248`) | a generation-3 unfinished session is refused (`session-from-earlier-version`) | `test_l4_folds_1858.py::test_v0_next_on_a_generation_three_unfinished_session_refuses_and_writes_the_marker` |
| P-v4 | `run_loop` passes the captured selection to `_library_finder_unauthenticated` (`round_driver.py`) | a preference edit made while the callback runs does not re-judge the result | `test_l4_folds_1858.py::test_v4_a_preference_edit_while_the_callback_runs_does_not_re_judge_the_result[gap-sweep]` |
| P-v1 | the harness verifier's `vendor` report (`eval/review_loop_runner.py`, `verifier` in `run_fixture`) | harness verdicts carry their vendor | `eval/tests/test_golden_parity.py` (run alone) |

## Disclosures

- P-v0 and P-v4 each went red under their neutralization and green after the restore. **P-v1 did not go red** (see its entry): it carries `Unreachable through this entry point`.
- The `scoped` parameter of the P-v4 detector was not neutralized separately: the one neutralization is the single `run_loop` call site both phases share, and only the `gap-sweep` node was run red. The `scoped` case is unproven by a red here.
- The first two P-v4 red attempts did not go red, and that was a defect of my own new test, not of the neutralization: (1) the config's live vendors did not include `cursor`, so the edit did not move the selection; (2) `run_loop` runs on `test_round_driver`'s own load of the module (`TRD.RD`), a different module object from this file's `import round_driver`, so patching only `RD._reviewer_engine_vendor` never reached it. Both were fixed in the test (`VENDORS`, `_flip_engine` patching both module objects) before the red below; nothing in production code changed between those attempts and the red. The red below is the first run of the fixed detector under the neutralization.
- Restore receipts: the neutralized lines are quoted back as they stand after the inverse edit. sha256 of `round_driver.py` is printed before, while neutralized, and after the restore; before and after are equal.

---

## P-v0 — `SESSION_GENERATION = 4` (`round_driver.py`)

- **axis:** a generation-3 unfinished session is refused with `session-from-earlier-version` and the restart marker is written

**neutralization** (`plugins/superheroes/lib/round_driver.py:248`):
```diff
--- before (restored text)
SESSION_GENERATION = 4
+++ neutralized
SESSION_GENERATION = 3
```

**command:**
```
python3 -B -m pytest "plugins/superheroes/lib/tests/test_l4_folds_1858.py::test_v0_next_on_a_generation_three_unfinished_session_refuses_and_writes_the_marker" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_v0_next_on_a_generation_three_unfinished_session_refuses_and_writes_the_marker _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_v0_next_on_a_generation_t0')

    def test_v0_next_on_a_generation_three_unfinished_session_refuses_and_writes_the_marker(tmp_path):
        # axis: a generation-3 unfinished session is refused at `next` with the restart marker (P-v0)
        session_dir = _light_folder(tmp_path, generation=PRE_BINDING_GENERATION)
        assert _read_state_file(session_dir)["sessionGeneration"] == 3
        assert not os.path.exists(_marker_path(session_dir))
        out = RD.cmd_next(session_dir)
>       _assert_refusal(out, already_restarted=False)

/home/user/sh-1858/plugins/superheroes/lib/tests/test_l4_folds_1858.py:37: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
already_restarted = False

    def _assert_refusal(out, already_restarted):
>       assert out["ok"] is False, out
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert True is False

/home/user/sh-1858/plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_l4_folds_1858.py::test_v0_next_on_a_generation_three_unfinished_session_refuses_and_writes_the_marker
1 failed in 2.33s
```

**restore:** the inverse text swap (`SESSION_GENERATION = 3` back to `SESSION_GENERATION = 4`); no `git checkout`, `git restore`, `git reset` or `git stash`.

**restore receipt:** sha256 of `round_driver.py` before the neutralization `a21f0a61279261b78ea11391f0b82bea7fc70c2565984323ec1f319ead73ced5`, neutralized `ac18bfa84f890e8435cfc9ff4b525b890a697e5dfce6d218d35de6f4eb6a3df7`, after the restore `a21f0a61279261b78ea11391f0b82bea7fc70c2565984323ec1f319ead73ced5` (equal to the before value). The restored line as it stands in the file:
```
248:SESSION_GENERATION = 4
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.50s
```

---

## P-v4 — `run_loop` passes the captured selection to `_library_finder_unauthenticated` (`round_driver.py`)

- **axis:** the gap-sweep result is authenticated against the selection captured before the callback; a preference edit made while the callback runs (selection codex, then cursor) does not re-judge a codex report

**neutralization** (`plugins/superheroes/lib/round_driver.py:6106`): call the helper without the captured values, so it falls back to the live read
```diff
--- before (restored text)
                if _library_finder_unauthenticated(state, reported, selected=selected, replaced=replaced):
+++ neutralized
                if _library_finder_unauthenticated(state, reported):
```

**command:**
```
python3 -B -m pytest 'plugins/superheroes/lib/tests/test_l4_folds_1858.py::test_v4_a_preference_edit_while_the_callback_runs_does_not_re_judge_the_result[gap-sweep]' -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_v4_a_preference_edit_while_the_callback_runs_does_not_re_judge_the_result[gap-sweep] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7faf0c5faea0>
run = <function _gap_run at 0x7faf0ccba480>, phase = 'dispatch-gap-sweep'
key = 'gap'

    @pytest.mark.parametrize("run,phase,key", RUNS)
    def test_v4_a_preference_edit_while_the_callback_runs_does_not_re_judge_the_result(
            monkeypatch, run, phase, key):
        # axis: the finder is authenticated against the selection captured before the callback (P-v4)
        # the pre-callback selection is codex; the edit made while the callback ran makes it cursor
        # (a live re-read would judge the codex report against cursor and park)
        state, seen = run(monkeypatch, "codex")
        parked, reason = _parked_unauthenticated(state, phase)
        assert seen[key] >= 1
>       assert not parked, reason
E       AssertionError: nonpanel-finder-unauthenticated:dispatch-gap-sweep:expected=codex:reported=codex
E       assert not True

/home/user/sh-1858/plugins/superheroes/lib/tests/test_l4_folds_1858.py:132: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_l4_folds_1858.py::test_v4_a_preference_edit_while_the_callback_runs_does_not_re_judge_the_result[gap-sweep]
1 failed in 0.36s
```

**restore:** the inverse text swap of the call above; no `git checkout`, `git restore`, `git reset` or `git stash`.

**restore receipt:** sha256 of `round_driver.py` before the neutralization `a21f0a61279261b78ea11391f0b82bea7fc70c2565984323ec1f319ead73ced5`, neutralized `0f1084fa6a6a459965b873678ff1e18ae2b8aed6c7d5ff56deb132a482908ce3`, after the restore `a21f0a61279261b78ea11391f0b82bea7fc70c2565984323ec1f319ead73ced5` (equal to the before value). The restored line as it stands in the file:
```
6106:                if _library_finder_unauthenticated(state, reported, selected=selected, replaced=replaced):
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.34s
```

---

## P-v1 — the harness verifier's `vendor` report (`eval/review_loop_runner.py`)

- **axis:** the harness verifier returns `{"verdicts": out, **finder_vendor}`, so harness verdicts carry the vendor they simulate
- **disclosure: `Unreachable through this entry point`.** The verifier is a closure inside `run_fixture`; the golden parity run does not discriminate the bare list from the dict form, and no unit seam reaches the closure. The order forbids adding a test for P-v1. Evidence: the detector run alone stayed green under the neutralization (below).

**neutralization** (`plugins/superheroes/eval/review_loop_runner.py:460`): return the bare list
```diff
--- before (restored text)
        return {"verdicts": out, **finder_vendor}
+++ neutralized
        return out
```

**command:**
```
python3 -B -m pytest plugins/superheroes/eval/tests/test_golden_parity.py -q -p no:cacheprovider
```

**output under the neutralization** (exit 0 — not red):
```
............                                                             [100%]
12 passed in 1.74s
```

**restore:** the inverse text swap; no `git checkout`, `git restore`, `git reset` or `git stash`.

**restore receipt:** no sha256 was taken before this neutralization (the sha256 `689732b89dcb87ef0930b91a90eb03f1fb346e069cf314b950941e0371a07285` is of the neutralized file; the restored file is `83f15090000e1cbbe32074a30a5d18ced5d7af5bde66ba6907791d972b3e2e4e`). The restored lines as they stand in the file, and the diff of the file against HEAD after the restore, which is the single-line change this order made:
```
        return {"verdicts": out, **finder_vendor}
```
```
@@ -460 +460 @@ def run_fixture(fixture, fail_telemetry=False, run_dir=None,
-        return out
+        return {"verdicts": out, **finder_vendor}
```

**raw green** (exit 0):
```
............                                                             [100%]
12 passed in 1.28s
```
