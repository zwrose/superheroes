# Work order B (#2072) bite-proof: a `ci-exact-head` verify stands in for the local verify only when the fetched run backs it

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

**Provenance:** claude / sonnet-5.5 (implementer, work order B2), maker family anthropic. Production under proof: `plugins/superheroes/lib/round_phases.py` (`verify_result_fault`, `_ci_verify_shape_fault`), `plugins/superheroes/lib/round_driver.py` (`_ci_verify_run_refusal`, `cmd_submit`, the `verifyVia` record), `plugins/superheroes/lib/round_adapters.py` (`_assemble_verify`), `plugins/superheroes/lib/review_record_session.py` (`_verify_via_checked`). Tests: `plugins/superheroes/lib/tests/test_verify_ci_head_2072.py`.

Declared guarded-element set (from order B): **E1**, **E2a**, **E2b**, **E2c**, **E3**, **E4a**, **E4b**, **E4c**, **E5**, **E6**, **E7**, **E8a**, **E8b**. Each was neutralized by one targeted edit (the Edit tool, exact-text match), only its proving nodes run by exact node id (never `-k`; every parametrized id pytest lists was spelled out), the inverse edit applied, `git diff --stat -- <file>` taken (empty: the file equals the last commit), and the same ids run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

Capture directory (outside the repository; every pytest run below is redirected there unfiltered, and `pytest exit: N` is appended as the last line of each file):
`/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-2072-wo-b/cc46b7f4-2839-43f4-8739-40b3cc7ffef4/scratchpad/`

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_verify_ci_head_2072.py`) | Captures (red / green) |
|---|---|---|---|---|
| E1 | the shape check, `round_phases.py` `verify_result_fault` (`return _ci_verify_shape_fault(artifact)`) | an unknown `via`, a non-pass `ci-exact-head`, a malformed `ci`/`reason`, or evidence on a local verify is refused (`ci-verify-shape`) before any fetch | `::test_edge1_..._via_is_a_shape_fault[unknown]`, `::test_edge2_..._only_for_a_pass[fail]`, `::test_edge3_ci_missing_or_not_an_object_is_a_shape_fault`, `::test_edge3_each_string_ci_field_...[missing-workflow]`, `::test_edge3_run_id_...[zero]`, `::test_edge3_head_sha_...[short-abbrev]`, `::test_edge4_reason_...[missing]`, `::test_edge5_no_evidence_...[ci-only]`, `::test_a_shape_fault_is_refused_on_every_path_before_any_fetch[hand]` | `E1_red2.txt` / `E1_green2.txt` |
| E2a | `_ci_verify_run_refusal`, fetched head vs the verified head (`if run["head_sha"] != verified_head:`) | a run on another commit than the verified head is `ci-verify-sha-mismatch`, though the claim names that run's commit | `::test_edge8_fetched_head_differs_from_the_verified_head_though_the_claim_matches_it` | `E2a_red2.txt` / `E2a_green2.txt` |
| E2b | `_ci_verify_run_refusal`, claimed head vs fetched head (`if run["head_sha"] != ci["headSha"]:`) | a claim naming another commit than the run's is `ci-verify-sha-mismatch`, though the run is on the verified head | `::test_edge8_claimed_head_differs_from_the_fetched_head` | `E2b_red2.txt` / `E2b_green2.txt` |
| E2c | `_ci_verify_run_refusal`, fetched id vs claimed `runId` (`if str(run["id"]) != str(ci["runId"]):`) | a fetched run that is not the claimed run is `ci-verify-sha-mismatch` | `::test_edge8_fetched_id_differs_from_the_claimed_run_id` | `E2c_red2.txt` / `E2c_green2.txt` |
| E3 | `_ci_verify_run_refusal`, workflow (`if run["name"] != ci["workflow"]:`) | a run of another workflow is `ci-verify-workflow-mismatch` | `::test_edge9_fetched_workflow_differs_from_the_claimed_workflow` | `E3_red2.txt` / `E3_green2.txt` |
| E4a | `_ci_verify_run_refusal`, status (`if run["status"] != "completed":`) | a run still in progress is `ci-verify-conclusion-mismatch` | `::test_edge10_a_run_still_in_progress_is_a_conclusion_mismatch` | `E4a_red2.txt` / `E4a_green2.txt` |
| E4b | `_ci_verify_run_refusal`, claimed conclusion vs fetched (`if run["conclusion"] != ci["conclusion"]:`) | a claimed conclusion the run does not have is `ci-verify-conclusion-mismatch` | `::test_edge10_a_claimed_conclusion_the_run_does_not_have_is_refused` | `E4b_red2.txt` / `E4b_green2.txt` |
| E4c | `_ci_verify_run_refusal`, `success` required (`if run["conclusion"] != "success":`) | a failed run claimed as a failure is still no stand-in (`ci-verify-conclusion-mismatch`) | `::test_edge10_a_failed_run_claimed_as_failure_is_still_not_a_stand_in` | `E4c_red2.txt` / `E4c_green2.txt` |
| E5 | `_ci_verify_run_refusal`, the unreadable-run refusal (`if not isinstance(run, dict) or any(k not in run ...):`) | a run that cannot be fetched or lacks a required field is `ci-verify-run-unreadable`, never compared | `::test_edge6_a_failed_fetch_is_unreadable`, `::test_edge6_a_raising_fetch_is_unreadable`, `::test_edge6_a_run_lacking_any_required_field_is_unreadable[id]`, `[name]`, `[head_sha]`, `[status]`, `[conclusion]`, `::test_edge6_a_non_dict_run_is_unreadable` | `E5_red.txt` / `E5_green.txt` |
| E6 | `round_driver.py` `cmd_submit`, the run check at the submit chokepoint (`refusal = _ci_verify_run_refusal(...)`) | a sha-mismatch twin is refused on the hand, bare-payload and durable-seat paths alike | `::test_a_sha_mismatch_twin_is_refused_on_every_path[hand]`, `[bare]`, `[seat]` | `E6_red.txt` / `E6_green.txt` |
| E7 | `round_adapters.py` `_assemble_verify`, the field copy (`for field in (..., "via", "ci", "reason")`) | the CI evidence rides the durable-seat assembly to the chokepoint | `::test_a_sha_mismatch_twin_is_refused_on_every_path[seat]`, `::test_an_accepted_ci_exact_head_payload_folds_pass_and_records_which_verify[seat]` | `E7_red.txt` / `E7_green.txt` |
| E8a | `round_driver.py`, the `verifyVia` record (`_record_round(state, "verifyVia", _verify_via_row(config, artifact))`) | a passing verify records which verify stood behind it, `ci-exact-head` or `local` | `::test_an_accepted_ci_exact_head_payload_folds_pass_and_records_which_verify[hand]`, `[bare]`, `[seat]`, `::test_a_local_verify_never_calls_the_fetch_seam_and_records_it_local[hand]`, `[bare]`, `[seat]` | `E8a_red.txt` / `E8a_green.txt` |
| E8b | `review_record_session.py` `_verify_via_checked` (`if isinstance(via, dict) and via.get("via") == "ci-exact-head":`) | the review record's `checked` lines name the CI run that stood in for the local verify | `::test_the_review_record_names_the_verify_used` | `E8b_red.txt` / `E8b_green.txt` |
| E9a | `round_driver.py` `_ci_verify_run_refusal`, the declared-workflow gate (`if declared_kind != "declared" or not declared:`) | a project that declares no readable `ciWorkflow` is refused `ci-verify-workflow-unconfigured` before the fetch | `::test_an_undeclared_ci_workflow_is_refused_before_the_fetch[absent]`, `[unreadable]` | `E9a_red.txt` / `E9a_green.txt` |
| E9b | `round_driver.py` `_ci_verify_run_refusal`, the claimed workflow vs the declared one (`if ci["workflow"] != declared:`) | a claimed workflow other than the declared one is refused `ci-verify-workflow-mismatch` before the fetch | `::test_a_claimed_workflow_other_than_the_declared_one_is_refused_before_the_fetch` (added in this order; the older `::test_a_claimed_workflow_other_than_the_declared_one_is_refused` stays green under this neutralization) | `E9b_red.txt` / `E9b_green.txt` |
| E9c | `round_driver.py` `_ci_verify_run_refusal`, the declared clause of the run-workflow check (the `or run["name"] != declared` in `if run["name"] != ci["workflow"] or run["name"] != declared:`) | a fetched run whose workflow is not the declared one is refused `ci-verify-workflow-mismatch` | **not separately provable (subsumed)**: no node can go red; the nodes run are `::test_edge9_fetched_workflow_differs_from_the_claimed_workflow`, `::test_a_claimed_workflow_other_than_the_declared_one_is_refused`, `::test_a_claimed_workflow_other_than_the_declared_one_is_refused_before_the_fetch` | `E9c_neutralized.txt` (green under neutralization) / `E9c_green.txt` |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0). The red of each element is on the axis named in its row: a `ci-exact-head` payload that should have been refused is folded (`'ok': True`) where the axis expects the named refusal token (E1, E2a, E2b, E2c, E3, E4a, E4b, E4c, E6, E7), the `verifyVia` row is absent (E8a: `None`), or the review record's `checked` list lacks the `Verify in round` line (E8b: `[]`).
- E5's red is on the axis but is a crash, not a fold: with the unreadable-run refusal off, the next comparison reads `run["head_sha"]` of a `None` run (`TypeError: 'NoneType' object is not subscriptable`), a non-dict run (`TypeError: list indices must be integers or slices, not str`) or a dict missing a field (`KeyError: 'id'`, `'name'`, `'head_sha'`, `'status'`, `'conclusion'`). The fetched run is compared (here, blown up on) instead of refused, which is what the element guards; the tests fail on the exception, not on a wrong token.
- E7's red is a different shape from E6's: dropping `via`/`ci`/`reason` from the assembled artifact turns a seat's `ci-exact-head` payload into a local verify (`{'via': 'local', 'command': 'none'}`), so the chokepoint never fetches and the mismatch twin folds.
- Neutralizations: E1 `return None` in place of `return _ci_verify_shape_fault(artifact)`; E2a, E2b, E2c, E3, E4a, E4b, E4c, E5 and E8b prefix the guard's condition with `False and` (E5: `False and (...)` around the whole condition); E6 `refusal = None` in place of the call; E7 the field tuple cut to `("command", "exit", "outputSha256")`; E8a `pass` in place of the `_record_round` call. Each is the production call site the detector reaches, never a helper the tests assert as a precondition.
- No earlier capture is reused. The first attempt's `E1`-`E4c` captures carry no neutralization, command or restore receipt, and its `E2b` green (2 passed) is not the same ids as its red (1 failed); order B2 allowed reuse only for a complete pair, so every element was re-run in this dispatch (`*_red2.txt`/`*_green2.txt` for E1-E4c, `*_red.txt`/`*_green.txt` for E5-E8b).
- The restore receipt is `git diff --stat -- <file>` taken after the inverse edit, printed between `--- git diff --stat` and `--- end diff` markers: in every element it printed nothing, so the file equals its last commit. After E8b and after E4c a `git status --porcelain` over the worktree also printed nothing.
- The command shape is `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <exact node ids> -q`, redirected to the capture file, followed by `echo "pytest exit: $?"` appended to it. Excerpts below are verbatim lines of the capture (a few lines each, long assertion text cut by omission only at a marked `[...]`); the full output is the capture file.
- `E5_red.txt` is 36629 bytes, over the 32 KiB per-element ceiling; it lives outside the repository (above), and its first and last lines are quoted here. All other captures are under 32 KiB each.
- Redaction: none needed; local `/path/to/home/...` and `/private/tmp/...` paths are kept as printed, no secret, token or private URL appears.
- Not in the declared set: the receipt disclosure line (`receipt_disclosures.py`, the `verify-via-ci` line, tagged with an `# axis:` comment) has tests in the file but no neutralization of its own here, so this record claims no bite-proof for it.
- E9a, E9b and E9c were added later (order FU3); their disclosures are in the bullets under `## E9a` below, and the E1-E8b bullets above describe E1-E8b only.

---

## E1: the shape check

- **axis:** an unknown `via`, a non-pass `ci-exact-head`, a malformed `ci`/`reason`, or evidence on a local verify is refused (`ci-verify-shape`) before any fetch

**neutralization** (`plugins/superheroes/lib/round_phases.py`, `verify_result_fault`):
```diff
-        return _ci_verify_shape_fault(artifact)
+        return None
```

**red capture:** `.../scratchpad/E1_red2.txt` (exit 1), excerpt:
```
FFFFFFFFF                                                                [100%]
______ test_edge1_an_unknown_or_non_string_via_is_a_shape_fault[unknown] ______
>       assert _is_shape_fault(_payload(via=via))
E       AssertionError: assert False
E        +  where False = _is_shape_fault({'result': 'pass', 'via': 'remote', 'ci': {'workflow': 'CI', ...
[...]
>       assert out["ok"] is False and _token(out).startswith("ci-verify-shape:"), out
E       AssertionError: {'ok': False, 'reason': 'ci-verify-sha-mismatch', 'detail': 'run 39773254322 ran on bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, not the claimed abc'}
9 failed in 20.58s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_phases.py` (`return None` back to `return _ci_verify_shape_fault(artifact)`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E1_green2.txt` (exit 0), same ids:
```
.........                                                                [100%]
9 passed in 14.51s
pytest exit: 0
```

---

## E2a: fetched head against the verified head

- **axis:** a run on another commit than the verified head is `ci-verify-sha-mismatch`, though the claim names that run's commit

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if run["head_sha"] != verified_head:
+    if False and run["head_sha"] != verified_head:
```

**red capture:** `.../scratchpad/E2a_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
_ test_edge8_fetched_head_differs_from_the_verified_head_though_the_claim_matches_it _
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 11.89s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and run["head_sha"] != verified_head:` back to `if run["head_sha"] != verified_head:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E2a_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 10.79s
pytest exit: 0
```

---

## E2b: claimed head against the fetched head

- **axis:** a claim naming another commit than the run's is `ci-verify-sha-mismatch`, though the run is on the verified head

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if run["head_sha"] != ci["headSha"]:
+    if False and run["head_sha"] != ci["headSha"]:
```

**red capture:** `.../scratchpad/E2b_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
____________ test_edge8_claimed_head_differs_from_the_fetched_head _____________
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 10.30s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and run["head_sha"] != ci["headSha"]:` back to `if run["head_sha"] != ci["headSha"]:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E2b_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 12.01s
pytest exit: 0
```

---

## E2c: fetched id against the claimed `runId`

- **axis:** a fetched run that is not the claimed run is `ci-verify-sha-mismatch`

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if str(run["id"]) != str(ci["runId"]):
+    if False and str(run["id"]) != str(ci["runId"]):
```

**red capture:** `.../scratchpad/E2c_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
____________ test_edge8_fetched_id_differs_from_the_claimed_run_id _____________
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 16.25s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and str(run["id"]) != str(ci["runId"]):` back to `if str(run["id"]) != str(ci["runId"]):`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E2c_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 12.34s
pytest exit: 0
```

---

## E3: the workflow comparison

- **axis:** a run of another workflow is `ci-verify-workflow-mismatch`

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if run["name"] != ci["workflow"]:
+    if False and run["name"] != ci["workflow"]:
```

**red capture:** `.../scratchpad/E3_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
________ test_edge9_fetched_workflow_differs_from_the_claimed_workflow _________
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 12.14s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and run["name"] != ci["workflow"]:` back to `if run["name"] != ci["workflow"]:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E3_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 12.15s
pytest exit: 0
```

---

## E4a: the run must be completed

- **axis:** a run still in progress is `ci-verify-conclusion-mismatch` (the fetched conclusion agrees with the claim, so only the status check can refuse it)

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if run["status"] != "completed":
+    if False and run["status"] != "completed":
```

**red capture:** `.../scratchpad/E4a_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
_________ test_edge10_a_run_still_in_progress_is_a_conclusion_mismatch _________
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 11.52s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and run["status"] != "completed":` back to `if run["status"] != "completed":`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E4a_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 10.31s
pytest exit: 0
```

---

## E4b: the claimed conclusion against the fetched one

- **axis:** a claimed conclusion the run does not have is `ci-verify-conclusion-mismatch` (the run succeeded; only the claim differs)

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if run["conclusion"] != ci["conclusion"]:
+    if False and run["conclusion"] != ci["conclusion"]:
```

**red capture:** `.../scratchpad/E4b_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
______ test_edge10_a_claimed_conclusion_the_run_does_not_have_is_refused _______
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 8.68s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and run["conclusion"] != ci["conclusion"]:` back to `if run["conclusion"] != ci["conclusion"]:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E4b_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 8.91s
pytest exit: 0
```

---

## E4c: only `success` stands in

- **axis:** a failed run claimed as a failure is still no stand-in (`ci-verify-conclusion-mismatch`); claim and run agree, so only the `success` requirement can refuse it

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if run["conclusion"] != "success":
+    if False and run["conclusion"] != "success":
```

**red capture:** `.../scratchpad/E4c_red2.txt` (exit 1), excerpt:
```
F                                                                        [100%]
_____ test_edge10_a_failed_run_claimed_as_failure_is_still_not_a_stand_in ______
>       assert out["ok"] is False and out["reason"] == token, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
1 failed in 8.51s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and run["conclusion"] != "success":` back to `if run["conclusion"] != "success":`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E4c_green2.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 7.38s
pytest exit: 0
```

---

## E5: the unreadable-run refusal

- **axis:** a run that cannot be fetched or lacks a required field is `ci-verify-run-unreadable`, never compared

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if not isinstance(run, dict) or any(k not in run for k in ("id", "name", "head_sha", "status", "conclusion")):
+    if False and (not isinstance(run, dict) or any(k not in run for k in ("id", "name", "head_sha", "status", "conclusion"))):
```

**red capture:** `.../scratchpad/E5_red.txt` (exit 1, 36629 bytes, over the ceiling, so kept off-repo), excerpt (the traceback prints the neutralized line):
```
FFFFFFFF                                                                 [100%]
___________________ test_edge6_a_failed_fetch_is_unreadable ____________________
        if False and (not isinstance(run, dict) or any(k not in run for k in ("id", "name", "head_sha", "status", "conclusion"))):
>       if run["head_sha"] != ci["headSha"]:
E       TypeError: 'NoneType' object is not subscriptable
[...]
E       KeyError: 'id'
E       TypeError: list indices must be integers or slices, not str
8 failed in 84.47s (0:01:24)
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (the `if False and (...)` condition back to `if not isinstance(run, dict) or any(...)`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E5_green.txt` (exit 0), same ids:
```
........                                                                 [100%]
8 passed in 85.49s (0:01:25)
pytest exit: 0
```

---

## E6: the chokepoint wiring in `cmd_submit`

- **axis:** a sha-mismatch twin is refused on the hand, bare-payload and durable-seat paths alike

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `cmd_submit`):
```diff
-                refusal = _ci_verify_run_refusal(session_dir, state, artifact, resolution)
+                refusal = None
```

**red capture:** `.../scratchpad/E6_red.txt` (exit 1), excerpt:
```
FFF                                                                      [100%]
___________ test_a_sha_mismatch_twin_is_refused_on_every_path[hand] ____________
>       assert out["ok"] is False and _token(out) == "ci-verify-sha-mismatch", out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'run-verify', 'nextStep': 'terminal', ...}
E       assert (True is False)
3 failed in 32.94s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`refusal = None` back to `refusal = _ci_verify_run_refusal(session_dir, state, artifact, resolution)`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E6_green.txt` (exit 0), same ids:
```
...                                                                      [100%]
3 passed in 34.83s
pytest exit: 0
```

---

## E7: `_assemble_verify` carries the fields

- **axis:** the CI evidence rides the durable-seat assembly to the chokepoint

**neutralization** (`plugins/superheroes/lib/round_adapters.py`, `_assemble_verify`):
```diff
-    for field in ("command", "exit", "outputSha256", "via", "ci", "reason"):
+    for field in ("command", "exit", "outputSha256"):
```

**red capture:** `.../scratchpad/E7_red.txt` (exit 1), excerpt:
```
FF                                                                       [100%]
___________ test_a_sha_mismatch_twin_is_refused_on_every_path[seat] ____________
>       assert out["ok"] is False and _token(out) == "ci-verify-sha-mismatch", out
E       AssertionError: {'ok': True, 'folded': {'phase': 'run-verify', 'round': 1, 'attempt': 0}, 'nextAction': {'ok': True, 'action': 'terminal', 'round': 2, 'phase': 'terminal', ...}, 'brokeLock': None, ...}
[...]
E         {'via': 'local'} != {'via': 'ci-exact-head'}
E         Left contains 1 more item:
E         {'command': 'none'}
2 failed in 24.17s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_adapters.py` (the three-field tuple back to `("command", "exit", "outputSha256", "via", "ci", "reason")`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E7_green.txt` (exit 0), same ids:
```
..                                                                       [100%]
2 passed in 22.05s
pytest exit: 0
```

---

## E8a: the `verifyVia` record

- **axis:** a passing verify records which verify stood behind it, `ci-exact-head` or `local`

**neutralization** (`plugins/superheroes/lib/round_driver.py`, the pass branch of the verify fold):
```diff
-        _record_round(state, "verifyVia", _verify_via_row(config, artifact))
+        pass
```

**red capture:** `.../scratchpad/E8a_red.txt` (exit 1), excerpt:
```
FFFFFF                                                                   [100%]
_ test_an_accepted_ci_exact_head_payload_folds_pass_and_records_which_verify[hand] _
>       assert world.via() == {"via": "ci-exact-head", "workflow": "CI", "runId": RUN_ID,
E       AssertionError: assert None == {'via': 'ci-exact-head', 'workflow': 'CI', 'runId': '39773254322', 'headSha': '58850484eeddacd8baa5f01e3d68f3b03ad224c3', ...}
[...]
>       assert world.via() == {"via": "local", "command": "make test"}
E       AssertionError: assert None == {'via': 'local', 'command': 'make test'}
6 failed in 69.55s (0:01:09)
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`pass` back to `_record_round(state, "verifyVia", _verify_via_row(config, artifact))`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E8a_green.txt` (exit 0), same ids:
```
......                                                                   [100%]
6 passed in 88.80s (0:01:28)
pytest exit: 0
```

---

## E8b: the review-record `checked` line

- **axis:** the review record's `checked` lines name the CI run that stood in for the local verify

**neutralization** (`plugins/superheroes/lib/review_record_session.py`, `_verify_via_checked`):
```diff
-        if isinstance(via, dict) and via.get("via") == "ci-exact-head":
+        if False and isinstance(via, dict) and via.get("via") == "ci-exact-head":
```

**red capture:** `.../scratchpad/E8b_red.txt` (exit 1), excerpt:
```
F                                                                        [100%]
_________________ test_the_review_record_names_the_verify_used _________________
>       assert [c for c in account["checked"] if c.startswith("Verify in round")] == [
E       AssertionError: assert [] == ['Verify in r...tabase here)']
E         Right contains one more item: 'Verify in round 2: CI workflow CI run 39773254322 on bbbbbbb passed, in place of the local verify command (no database here)'
1 failed in 3.78s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/review_record_session.py` (`if False and isinstance(via, dict) ...` back to `if isinstance(via, dict) and via.get("via") == "ci-exact-head":`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/E8b_green.txt` (exit 0), same id:
```
.                                                                        [100%]
1 passed in 4.07s
pytest exit: 0
```

---

**Provenance (E9a-E9c):** claude / sonnet-5.5 (implementer), maker family anthropic; order FU3 from the vet 606 send-back ([receipt](https://github.com/zwrose/superheroes/pull/2068#issuecomment-6348500652), item #2076 FU3), which found the declared-`ciWorkflow` guard added by commit `34a68409e` had tests but no recorded neutralization. The guard is in `plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`. Same method as above (one Edit-tool neutralization, proving nodes by exact id, inverse edit, `git diff --stat -- <file>` receipt, same ids again; no `git checkout`, `git restore`, `git reset` or `git stash`). Capture directory (outside the repository; every run unfiltered, `pytest exit: N` appended):
`/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-2053-b7af41d156396fa0/109398b2-b53a-4a76-90e5-2bf96c9a5df8/scratchpad/fu3/`

Disclosures for E9a-E9c:

- **Isolating test added (E9b).** The existing `test_a_claimed_workflow_other_than_the_declared_one_is_refused` claims and fetches `pr-title` together, so with E9b off the fetch happens and E9c (and E3, which also sees `pr-title` against the claim) still refuses with the same token; it stayed green under E9b's neutralization (`1 failed, 1 passed`, the passing one being that test). The new `test_a_claimed_workflow_other_than_the_declared_one_is_refused_before_the_fetch` in `test_verify_ci_head_2072.py` claims `pr-title` while the fetch seam would return the declared `CI` run, and asserts the refusal token and `fetch.calls == []`. Nothing existing was weakened or deleted.
- **E9a's red is a different token, not a fold.** With the gate off, `declared` is `None`, so E9b refuses with `ci-verify-workflow-mismatch` ("not the project's declared None") and the fetch still does not happen; the red is the missing `ci-verify-workflow-unconfigured` token, which is E9a's axis. The two `or` halves of the condition (`declared_kind != "declared"`, `not declared`) are neutralized together as one element; `not declared` alone is not separately proven (a `declared` kind with an empty name cannot arise past the shape check's non-empty `workflow`, where E9b would refuse it with another token).
- **E9a's neutralization is parenthesized**, `if False and (declared_kind != "declared" or not declared):`, because a bare `False and` prefix binds only to the first `or` operand and `not declared` would still refuse the `absent` case. The first form typed was corrected before any test ran against it.
- **E9c is not separately provable (subsumed).** With E9b live, `ci["workflow"] == declared` whenever the code reaches the fetch; with E3 (`run["name"] != ci["workflow"]`) live, a run that gets past E3 has `run["name"] == ci["workflow"]`; equality is transitive, so `run["name"] != declared` is false on every input that reaches that line, and the clause can never fire while E9b and E3 are live. No test shape exists that only E9c catches. Under the clause-only neutralization (`or (False and run["name"] != declared)`, E3 kept live) the three workflow-mismatch nodes stay green (`3 passed`), which is the evidence of subsumption; no red is claimed. The clause is defence in depth, still guarding if E9b or E3 were removed.
- **E9b's first green capture overlapped the next edit.** `E9b_green_first_overlapped.txt` (`2 passed`) was run in one tool batch with the E9c neutralization edit, so it may have run with that edit applied; its restore receipt (empty) was taken before the edit landed. It is not used as the green; `E9b_green.txt` is a clean re-run after E9c was restored and its receipt was empty (`2 passed`).
- Redaction: none needed. All captures are far under 32 KiB.

## E9a: the undeclared-workflow gate

- **axis:** a project that declares no readable `ciWorkflow` is refused `ci-verify-workflow-unconfigured` before the fetch

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if declared_kind != "declared" or not declared:
+    if False and (declared_kind != "declared" or not declared):
```

**red capture:** `.../scratchpad/fu3/E9a_red.txt` (exit 1), excerpt:
```
FF                                                                       [100%]
E       AssertionError: {'ok': False, 'reason': 'ci-verify-workflow-mismatch', 'detail': "claimed workflow 'CI' is not the project's declared None"}
E       assert (False is False and 'ci-verify-workflow-mismatch' == 'ci-verify-wo...-unconfigured'
E         - ci-verify-workflow-unconfigured
E         + ci-verify-workflow-mismatch)
FAILED plugins/superheroes/lib/tests/test_verify_ci_head_2072.py::test_an_undeclared_ci_workflow_is_refused_before_the_fetch[absent]
FAILED plugins/superheroes/lib/tests/test_verify_ci_head_2072.py::test_an_undeclared_ci_workflow_is_refused_before_the_fetch[unreadable]
2 failed in 6.79s
pytest exit: 1
```
(the `E` block appears once per id; shown once)

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and (declared_kind != "declared" or not declared):` back to `if declared_kind != "declared" or not declared:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/fu3/E9a_green.txt` (exit 0), same ids:
```
..                                                                       [100%]
2 passed in 6.79s
pytest exit: 0
```

---

## E9b: the claimed workflow against the declared one

- **axis:** a claimed workflow other than the declared one is refused `ci-verify-workflow-mismatch` before the fetch (the fetch would return the declared run, so only the call count tells E9b from E3)

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`):
```diff
-    if ci["workflow"] != declared:
+    if False and ci["workflow"] != declared:
```

**red capture:** `.../scratchpad/fu3/E9b_red.txt` (exit 1), excerpt:
```
F.                                                                       [100%]
>       assert fetch.calls == []
E       AssertionError: assert [('/private/t...39773254322')] == []
E         Left contains one more item: ('/private/tmp/claude-501/pytest-of-zwrose/pytest-445/test_a_claimed_workflow_other_0/checkout', '39773254322')
FAILED plugins/superheroes/lib/tests/test_verify_ci_head_2072.py::test_a_claimed_workflow_other_than_the_declared_one_is_refused_before_the_fetch
1 failed, 1 passed in 11.07s
pytest exit: 1
```
(the passing one is the older `::test_a_claimed_workflow_other_than_the_declared_one_is_refused`, masked by E9c; see the disclosures)

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and ci["workflow"] != declared:` back to `if ci["workflow"] != declared:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/fu3/E9b_green.txt` (exit 0), same ids:
```
..                                                                       [100%]
2 passed in 8.16s
pytest exit: 0
```

---

## E9c: the declared clause of the run-workflow check (not separately provable, subsumed)

- **axis:** a fetched run whose workflow is not the declared one is refused `ci-verify-workflow-mismatch`; unreachable while E9b and E3 are live (reasoning in the disclosures above), so no red is claimed

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_ci_verify_run_refusal`; clause only, E3 stays live):
```diff
-    if run["name"] != ci["workflow"] or run["name"] != declared:
+    if run["name"] != ci["workflow"] or (False and run["name"] != declared):
```

**capture under neutralization:** `.../scratchpad/fu3/E9c_neutralized.txt` (exit 0), the evidence of subsumption, excerpt:
```
...                                                                      [100%]
3 passed in 10.15s
pytest exit: 0
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`or (False and run["name"] != declared)` back to `or run["name"] != declared`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat
--- end diff
```

**green capture:** `.../scratchpad/fu3/E9c_green.txt` (exit 0), same ids:
```
...                                                                      [100%]
3 passed in 10.85s
pytest exit: 0
```

---

**Closing run after FU3:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_verify_ci_head_2072.py -q -n auto` (capture `fu3/closing.txt`, exit 0): `122 passed in 23.30s`.

---

## Closing run

After the last restore, `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_verify_ci_head_2072.py -q -n auto` (capture `closing.txt`, exit 0): `118 passed in 39.94s`.
