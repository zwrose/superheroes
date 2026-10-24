# Work order A (#2133) bite-proof: the driver runs the verify command and lands the result, and `advance` folds a non-CI `run-verify` landing only against the driver's own journal row

**Provenance:** claude / sonnet-5.5 (implementer, order A attempt 2 for the production code and the tests; order A3 for this record), maker family anthropic. Production under proof: `plugins/superheroes/lib/round_driver.py` (`cmd_submit`, `_verify_landing_not_driver_written`, `_run_verify_take_claim`, `_run_verify_publish_locked`). Tests: `plugins/superheroes/lib/tests/test_round_driver_run_verify_2133.py`.

Declared guarded-element set (from order A3): **G1**, **G2**, **G3**, **G4**. Each was neutralized by one targeted edit (the Edit tool, exact-text match, the target occurring once), only its proving nodes run by exact node id (never `-k`; every parametrized id pytest lists was spelled out), the inverse edit applied, `git diff --stat -- plugins/superheroes/lib/round_driver.py` taken (empty: the file equals the last commit, `fc80c038`), and the same ids run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

Capture directory (outside the repository; every pytest run below is redirected there unfiltered, and `pytest exit: N` is appended as the last line of each file):
`/tmp/claude-0/-home-user-superheroes/e97672d9-3217-5822-bed0-00a86a030606/scratchpad/wo-2133-a3/`

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_round_driver_run_verify_2133.py`) | Captures (red / green) |
|---|---|---|---|---|
| G1 | the chokepoint check in `cmd_submit` (`detail = _verify_landing_not_driver_written(...)` / `if detail is not None:`, `round_driver.py:8786`) | a non-CI `run-verify` landing with no driver-written journal row is refused at `advance` as `fold-refused` / `verify-landing-not-driver-written`, on the bare-payload route and the seat-record route alike | `::test_a_hand_written_landing_is_refused_at_advance_on_the_bare_route`, `::test_a_hand_written_envelope_is_refused_at_advance_on_the_seat_route` | `G1_red.txt` / `G1_green.txt` |
| G2 | the payload-hash comparison in `_verify_landing_not_driver_written` (`and row.get("payloadSha256") == payload_sha`, `round_driver.py:13150`) | a landing edited after the driver wrote it no longer matches the driver's row and is refused | `::test_a_landing_edited_after_the_driver_wrote_it_is_refused` | `G2_red.txt` / `G2_green.txt` |
| G3 | the live-claim refusal in `_run_verify_take_claim` (`if pid is not None and _run_verify_pid_alive(pid):`, `round_driver.py:12921`) | a live claim holds the verify slot: a second runner is refused `run-verify-in-progress`, never let in beside it | `::test_e4_a_live_claim_is_refused_in_progress_and_left_alone`, `::test_e4_a_second_runner_during_the_run_is_refused_in_progress` | `G3_red.txt` / `G3_green.txt` |
| G4 | the slot re-check in `_run_verify_publish_locked` (`if (_run_verify_slot(state) != claim["slot"] or ...`, `round_driver.py:13064`) | a result computed for a slot that moved or filled during the run is refused `run-verify-slot-moved` and lands nothing | `::test_e11_a_slot_that_moved_or_filled_during_the_run_lands_nothing[attempt-moved]`, `[slot-filled]`, `[phase-left]` (the three ids `pytest --collect-only -q` lists for it, capture `collect_only.txt`) | `G4_red.txt` / `G4_green.txt` |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0). The red of each element is on the axis named in its row: G1 and G2 fold a landing that should have been refused (`'ok': True, 'folded': {'phase': 'run-verify', ...}` where the test expects `fold-refused`), G3 lets the second runner reach the verify command (the test's `_never_run` stub raises `the verify command must not run here`), and G4 publishes the result (`'ok': True, 'result': 'pass'` where the test expects `run-verify-slot-moved`).
- G3's red is an exception from the stub the test installs to prove the command never runs, not a wrong token: with the live-claim refusal off, a live claim is treated as stale, removed and taken over, so the runner proceeds to execute. That is the failure the element guards (a second runner let in beside a live one); the tests fail on the exception.
- G4 has three parametrized ids and all three went red and green together; the neutralization removes the whole condition (`False and (...)`, all three `or` operands), so the record claims one red for the condition, not one per operand. The three ids drive three movers (`attempt-moved`, `slot-filled`, `phase-left`) through the same condition, and each went red.
- Neutralizations: G1 `if False and detail is not None:`; G2 the clause `and row.get("payloadSha256") == payload_sha` deleted from the condition; G3 `if False and pid is not None and _run_verify_pid_alive(pid):`; G4 `if False and (_run_verify_slot(state) != claim["slot"] or ... or ...):` (the existing parentheses kept, so `False and` binds the whole condition). Each is the production call site the detector reaches, never a helper the tests assert as a precondition.
- The restore receipt is `git diff --stat -- plugins/superheroes/lib/round_driver.py` taken after the inverse edit, printed between `--- git diff --stat` and `--- end diff` markers (captures `G1_restore_receipt.txt` to `G4_restore_receipt.txt`): in every element it printed nothing, so the file equals its last commit. The restored line is quoted back in each entry.
- The command shape is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <exact node ids> -q`, redirected to the capture file, followed by `echo "pytest exit: $?"` appended to it (single-node proof runs without `-n auto`). Excerpts below are verbatim lines of the capture; a `[...]` marks text cut by omission; the full output is the capture file.
- The collect-only listing for G4 (`collect_only.txt`, exit 0) was taken as its own invocation before the G1 proof, not inside the G4 red run's capture; the G4 ids spelled out in both G4 runs are the three it lists.
- All captures are under 32 KiB each (largest `G3_red.txt`, 5561 bytes). Redaction: none needed; local `/home/user/wt-2133/...` and `/tmp/claude-0/...` paths are kept as printed, no secret, token or private URL appears.
- Not in the declared set: the other `_run_verify_*` branches (output-unwritable, spawn-failed, publish-lock-held, stale-claim takeover) and the docs have tests in the file but no neutralization of their own here, so this record claims no bite-proof for them.

---

## G1: the chokepoint check in `cmd_submit`

- **axis:** a non-CI `run-verify` landing with no driver-written journal row is refused at `advance` as `fold-refused` / `verify-landing-not-driver-written`, on the bare-payload and the seat-record route alike

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `cmd_submit`, line 8786; capture `G1_neutralization_diff.txt`):
```diff
-                    if detail is not None:
+                    if False and detail is not None:
```

**red capture:** `G1_red.txt` (exit 1), excerpt:
```
FF                                                                       [100%]
_____ test_a_hand_written_landing_is_refused_at_advance_on_the_bare_route ______
>       assert out["ok"] is False and out["reason"] == "fold-refused" and out["detail"] == NOT_DRIVER, out
E       AssertionError: {'ok': True, 'folded': {'phase': 'run-verify', 'round': 1, 'attempt': 0}, 'nextAction': {'ok': True, 'action': 'terminal', 'round': 2, 'phase': 'terminal', ...}, 'brokeLock': None, ...}
E       assert (True is False)
_____ test_a_hand_written_envelope_is_refused_at_advance_on_the_seat_route _____
>       assert out["ok"] is False and out["reason"] == "fold-refused" and out["detail"] == NOT_DRIVER, out
E       AssertionError: {'ok': True, 'folded': {'phase': 'run-verify', 'round': 1, 'attempt': 0}, 'nextAction': {'ok': True, 'action': 'terminal', 'round': 2, 'phase': 'terminal', ...}, 'brokeLock': None, ...}
E       assert (True is False)
2 failed in 5.82s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and detail is not None:` back to `if detail is not None:`).

**restore receipt** (`git diff --stat` over the file printed nothing; line 8786 quoted back):
```
--- git diff --stat
--- end diff
                    if detail is not None:
```

**green capture:** `G1_green.txt` (exit 0), same ids:
```
..                                                                       [100%]
2 passed in 3.93s
pytest exit: 0
```

---

## G2: the payload-hash comparison

- **axis:** a landing edited after the driver wrote it (the row's hash no longer matches) is refused; the row's round, attempt and command still match, so only the hash clause can refuse it

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_verify_landing_not_driver_written`, line 13150; capture `G2_neutralization_diff.txt`):
```diff
-                and row.get("attempt") == attempt and row.get("payloadSha256") == payload_sha):
+                and row.get("attempt") == attempt):
```

**red capture:** `G2_red.txt` (exit 1), excerpt:
```
F                                                                        [100%]
__________ test_a_landing_edited_after_the_driver_wrote_it_is_refused __________
>       assert out["ok"] is False and out["reason"] == "fold-refused" and out["detail"] == NOT_DRIVER, out
E       AssertionError: {'ok': True, 'folded': {'phase': 'run-verify', 'round': 1, 'attempt': 0}, 'nextAction': {'ok': True, 'action': 'terminal', 'round': 2, 'phase': 'terminal', ...}, 'brokeLock': None, ...}
E       assert (True is False)
1 failed in 4.51s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (the clause ` and row.get("payloadSha256") == payload_sha` put back).

**restore receipt** (`git diff --stat` over the file printed nothing; line 13150 quoted back):
```
--- git diff --stat
--- end diff
                and row.get("attempt") == attempt and row.get("payloadSha256") == payload_sha):
```

**green capture:** `G2_green.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 2.16s
pytest exit: 0
```

---

## G3: the live-claim refusal

- **axis:** a live claim holds the verify slot; a second runner is refused `run-verify-in-progress` and the command does not run

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_run_verify_take_claim`, line 12921; capture `G3_neutralization_diff.txt`):
```diff
-            if pid is not None and _run_verify_pid_alive(pid):
+            if False and pid is not None and _run_verify_pid_alive(pid):
```

**red capture:** `G3_red.txt` (exit 1), excerpt:
```
FF                                                                       [100%]
__________ test_e4_a_live_claim_is_refused_in_progress_and_left_alone __________
[...]
>       raise AssertionError("the verify command must not run here: %r" % (argv,))
E       AssertionError: the verify command must not run here: ['/usr/bin/bash', '-c', 'make test']
________ test_e4_a_second_runner_during_the_run_is_refused_in_progress _________
[...]
>       raise AssertionError("the verify command must not run here: %r" % (argv,))
E       AssertionError: the verify command must not run here: ['/usr/bin/bash', '-c', 'make test']
2 failed in 4.68s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and pid is not None ...` back to `if pid is not None and _run_verify_pid_alive(pid):`).

**restore receipt** (`git diff --stat` over the file printed nothing; line 12921 quoted back):
```
--- git diff --stat
--- end diff
            if pid is not None and _run_verify_pid_alive(pid):
```

**green capture:** `G3_green.txt` (exit 0), same ids:
```
..                                                                       [100%]
2 passed in 3.26s
pytest exit: 0
```

---

## G4: the slot re-check before publishing

- **axis:** a result computed for a slot that moved or filled during the run is refused `run-verify-slot-moved` and lands nothing

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_run_verify_publish_locked`, line 13064; capture `G4_neutralization_diff.txt`):
```diff
-    if (_run_verify_slot(state) != claim["slot"] or _store_file_exists(claim["landingPath"])
+    if False and (_run_verify_slot(state) != claim["slot"] or _store_file_exists(claim["landingPath"])
             or _store_file_exists(claim["recordPath"])):
```

**red capture:** `G4_red.txt` (exit 1), excerpt (the `E` block is the same in all three ids; shown once):
```
FFF                                                                      [100%]
>       assert out["ok"] is False and out["reason"] == "run-verify-slot-moved", out
E       AssertionError: {'ok': True, 'result': 'pass', 'round': 1, 'attempt': 0, ...}
E       assert (True is False)
FAILED plugins/superheroes/lib/tests/test_round_driver_run_verify_2133.py::test_e11_a_slot_that_moved_or_filled_during_the_run_lands_nothing[attempt-moved]
FAILED plugins/superheroes/lib/tests/test_round_driver_run_verify_2133.py::test_e11_a_slot_that_moved_or_filled_during_the_run_lands_nothing[slot-filled]
FAILED plugins/superheroes/lib/tests/test_round_driver_run_verify_2133.py::test_e11_a_slot_that_moved_or_filled_during_the_run_lands_nothing[phase-left]
3 failed in 4.02s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and (...` back to `if (_run_verify_slot(state) != claim["slot"] or ...`).

**restore receipt** (`git diff --stat` over the file printed nothing; lines 13064-13065 quoted back):
```
--- git diff --stat
--- end diff
    if (_run_verify_slot(state) != claim["slot"] or _store_file_exists(claim["landingPath"])
            or _store_file_exists(claim["recordPath"])):
```

**green capture:** `G4_green.txt` (exit 0), same ids:
```
...                                                                      [100%]
3 passed in 4.24s
pytest exit: 0
```
