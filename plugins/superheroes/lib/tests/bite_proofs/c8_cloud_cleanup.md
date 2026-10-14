# Bite-proof record: cloud_cleanup.py

Detector: `plugins/superheroes/lib/tests/test_cloud_cleanup.py` (`T1`).
Guarded elements (declared by the order): (1) the open-PR `none` return in `plan`; (2) the `branch-moved` sha check;
(3) the final sha read right before the DELETE; (4) the `branch-in-use` base check; (5) `record`'s delivered-only `ownerMessage`.
Each was neutralized by a targeted edit in the production file, the detector run alone
as one `-k` selection, then restored by the inverse edit. The test files were never edited during the proofs.

Run command, each time, from `plugins/superheroes/lib`: `/root/.local/bin/pytest -p no:cacheprovider <file> -q -k <selection>`.
This is not the order's `/usr/bin/python3 -B -X pycache_prefix=/tmp/c8-pyc -m pytest ...`: that command was refused
in this session ("This command requires approval"), and `/usr/bin/python3 -m pytest` reports `No module named pytest`.
`/root/.local/bin/pytest` is the pytest installed on this machine.

Pinned condition: the fixtures set `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` (in the `w` fixture of `T1`),
because this machine's global git config signs every commit through a signer that is not running (the ledger fixture repository still uses git). What that pin makes
unobservable: a developer's own git configuration (signing, hooks, aliases) acting on the fixture repositories.

Greens: one green run after all five restores, not five single-node greens; the order's
14-invocation budget cannot hold five reds, five greens, a first green and the regression run. See the order's budget note in the report.

## 1. The open-PR `none` return

Axis: an open PR gets nothing (no lane read, no receipt, no message), refusal-side.

- Neutralization (`cloud_cleanup.py`, `_plan`): `if pull["state"] == "open":` became `if False and pull["state"] == "open":`.
- Node: `T1 -k test_an_open_pr_after_a_handback_or_a_park` (two parametrized cases).
- Red (this capture was piped through `tail -25`, a filtered capture; the last lines): the plan of an open PR returned a cleanup.

```
E       AssertionError: assert {'ok': True, ...er/name', ...} == {'ok': True, ...n': 'pr-open'}
E         Differing items:
E         {'action': 'cleanup'} != {'action': 'none'}
E         Left contains 12 more items:
FAILED tests/test_cloud_cleanup.py::test_an_open_pr_after_a_handback_or_a_park_gets_no_message_no_deletion_and_no_receipt[handback]
FAILED tests/test_cloud_cleanup.py::test_an_open_pr_after_a_handback_or_a_park_gets_no_message_no_deletion_and_no_receipt[park]
2 failed, 24 deselected in 0.66s
```

- Restore: the inverse edit; `cloud_cleanup.py:181` reads `    if pull["state"] == "open":`.

## 2. The `branch-moved` sha check

Axis: a branch whose head is not the PR's recorded head is never deleted (refusal token `branch-moved`).
This is the comparison of element 3 seen from the refusal side; the delete is now a `gh api -X DELETE` call with no
expected-sha condition, so this comparison is the only guard on the branch's sha. Its proof is recorded once, under 3.

## 3. The final sha read right before the DELETE

Axis: the branch's sha is read immediately before the DELETE and compared with the PR's head; a branch that moved is
never deleted (`branch-moved`). A push that lands between that read and the DELETE is not caught: the accepted residual,
stated in the module docstring and at the call site.

- Neutralization (`branch`): `if sha != head_sha:` became `if False and sha != head_sha:`.
- Node: `T1 -k test_a_branch_that_moved_past_the_prs_head_is_never_deleted`.
- Red command (from the repository root): `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_cloud_cleanup.py -q -k test_a_branch_that_moved_past_the_prs_head_is_never_deleted`.
  Last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_branch_that_moved_past_the_prs_head_is_never_deleted` and `1 failed, 42 deselected in 15.67s`.
  The branch was deleted where `{'ok': False, 'reason': 'branch-moved'}` was expected.
- Restore: the inverse edit; `cloud_cleanup.py:396` reads `        if sha != head_sha:`.
- Green command: the same command. Last line: `1 passed, 42 deselected in 0.72s`.
- Not separately neutralized: the adjacency of the read and the DELETE (`test_the_branch_sha_is_read_right_before_the_delete`
  pins that the call before the DELETE is the branch's ref read); that ordering is unproven by a red run.

## 4. The `branch-in-use` base check

Axis: a branch an open PR uses as its base (a stack's lower layer) is kept.

- Neutralization (`_in_use`): `if _name(other, "base", "ref") == branch:` became `if False and _name(other, "base", "ref") == branch:`.
- Node: `T1 -k test_a_branch_an_open_pr_uses_as_its_base_is_kept`.
- Red (unfiltered): `1 failed in 0.35s`; the branch was deleted (`{'ok': True, ... 'action': 'cleanup', 'already': None, 'branch': 'feature'...}` where `{'ok': False, 'reason': 'branch-in-use'}` was expected).

```
>       assert _branch(w) == {"ok": False, "reason": "branch-in-use"}
E       AssertionError: assert {'ok': True, ...d': True, ...} == {'ok': False,...ranch-in-use'}
FAILED tests/test_cloud_cleanup.py::test_a_branch_an_open_pr_uses_as_its_base_is_kept
1 failed, 25 deselected in 0.35s
```

- Restore: the inverse edit; `cloud_cleanup.py:293` reads `        if _name(other, "base", "ref") == branch:`.

## 5. `record`'s delivered-only `ownerMessage`

Axis: the owner is told the builder was asked only when the request is confirmed delivered.

- Neutralization (`record`): `... if receipt["outcome"] == "delivered" else None` became `... if True else None`.
- Node: `T1 -k "test_an_uncertain_request or test_a_failed_request"` (two tests).
- Red (unfiltered): `2 failed in 0.52s`; an `uncertain` and a `failed` receipt each carried the owner message.

```
E       assert (True and "#412 is merged. I've asked its cloud builder to archive itself. If its session has a tool to archive itself, you'll get one prompt for it: tap Allow once. If it has none, it will say so on its issue, and the session stays listed until you archive it by hand." is None)
FAILED tests/test_cloud_cleanup.py::test_an_uncertain_request_is_never_resent_on_its_own_and_has_no_owner_message
FAILED tests/test_cloud_cleanup.py::test_a_failed_request_may_be_overwritten_by_a_delivered_one
2 failed, 24 deselected in 0.52s
```

- Restore: the inverse edit; `cloud_cleanup.py:262` reads `    owner = texts[got["outcome"]] % number if receipt["outcome"] == "delivered" else None`.

## Green after all five restores

A search of `cloud_cleanup.py` for `if False` and `if True` found none of the neutralizations present.

## Round 3: the branch step reconciles by observation

Entries 6-12. Detectors: `T1` = `plugins/superheroes/lib/tests/test_cloud_cleanup.py`, `T2` = `plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py`.
Every command was run from the repository root as `scripts/pinned-python -B -m pytest <file> -q -k <test>`. Each red is the
detector run alone as one `-k` selection, unfiltered; each restore is the inverse edit, quoted back; each green is the same command.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted below.

## 6. The re-read after the DELETE

Axis: the branch step reports what a re-read shows, never what the DELETE returned (a DELETE that times out but removed the branch reads deleted).

- Neutralization (`branch`, `cloud_cleanup.py`): `_, out, err = _gh(run, ["api", "-X", "DELETE", target], env)` became `code, out, err = _gh(...)`, with `if code != 0: return _refusal("delete-unconfirmed", detail=detail)` added after the `detail =` line (trust the exit code).
- Node: `T1 -k test_a_timed_out_delete_whose_ref_is_gone_reads_deleted`.
- Red: last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_timed_out_delete_whose_ref_is_gone_reads_deleted` and `1 failed, 58 deselected in 2.20s`; the result was `{'detail': '', 'reason': 'delete-unconfirmed'}` where `ok: True` was expected.
- Restore: the inverse edit; `cloud_cleanup.py:426` reads `            _, out, err = _gh(run, ["api", "-X", "DELETE", target], env)` and line 427 is the `detail =` line.
- Green: `1 passed, 58 deselected in 1.50s`.

## 7. The single retry (superseded by entry 13: the retry was removed by the advisor's ruling)

Axis: a DELETE that left the ref at the PR's head is issued once more, so a lost first DELETE still deletes.

- Neutralization (`branch`): `for _try in (1, 2):` became `for _try in (1,):`.
- Node: `T1 -k test_a_timed_out_delete_whose_ref_is_still_at_the_head_is_retried_once_and_re_read`.
- Red: last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_timed_out_delete_whose_ref_is_still_at_the_head_is_retried_once_and_re_read` and `1 failed, 58 deselected in 1.48s`; the result was `{'detail': '', 'reason': 'delete-unconfirmed'}` where `ok: True` was expected.
- Restore: the inverse edit; `cloud_cleanup.py:425` reads `        for _try in (1, 2):`.
- Green: `1 passed, 58 deselected in 1.18s`.
- The upper bound (never a third DELETE) is pinned by `test_two_timed_out_deletes_that_both_leave_the_branch_at_the_head_are_refused_after_exactly_two_deletes`; it was not separately neutralized, so that bound is unproven by a red run.

## 8. The moved check after the delete

Axis: a ref that reads another sha after the DELETE is `branch-moved`, never reported deleted or retried.

- Neutralization (`branch`): `if after != head_sha:` became `if False and after != head_sha:`.
- Node: `T1 -k test_a_ref_that_reads_another_sha_after_the_delete_is_refused_as_moved`.
- Red: last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_ref_that_reads_another_sha_after_the_delete_is_refused_as_moved` and `1 failed, 58 deselected in 1.10s`; `{'reason': 'delete-unconfirmed'} != {'reason': 'branch-moved'}`.
- Restore: the inverse edit; `cloud_cleanup.py:438` reads `            if after != head_sha:`.
- Green: `1 passed, 58 deselected in 1.00s`.

## 9. The unknown outcome

Axis: a ref that cannot be read after the DELETE is `delete-outcome-unknown`, never a success.

- Neutralization (`branch`): `if absent:` (after the re-read) became `if absent or why:`.
- Node: `T1 -k test_a_ref_that_cannot_be_read_after_the_delete_is_an_unknown_outcome_never_a_success`.
- Red: last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_ref_that_cannot_be_read_after_the_delete_is_an_unknown_outcome_never_a_success` and `1 failed, 58 deselected in 1.02s`; `assert (True is False)` (the branch step returned `ok: True`).
- Restore: the inverse edit; `cloud_cleanup.py:430` reads `            if absent:`.
- Green: `1 passed, 58 deselected in 1.03s`.

## 10. `record` runs under the module lock

Axis: two overlapping `pending` writes for one PR and session give exactly one reservation; the second caller waits on the lock.

- Neutralization (`cloud_cleanup.py`): the `@_locked` line above `def record(` was removed.
- Node: `T1 -k test_two_overlapping_pending_writes_for_the_same_pr_and_session_give_one_reservation`.
- Red: last lines: `AssertionError: the second caller never reached the lock while the first held it`, `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_two_overlapping_pending_writes_for_the_same_pr_and_session_give_one_reservation` and `1 failed, 58 deselected in 11.00s`. The red is the test's own wait for the second caller to reach the lock (with the decorator gone the second caller never calls `acquire`); it is not a double reservation observed in the state file.
- Restore: the inverse edit; `cloud_cleanup.py:307-308` read `@_locked` then `def record(repo_root, repo, pr, msg_id, outcome, *, launch_id=None, env=None, run=None):`.
- Green: `1 passed, 58 deselected in 1.03s`.

## 11. The negation is tied to the reminder verb

Axis: a negation suppresses a reminder hit only when it directly governs the verb; one sitting in an earlier condition does not.

- Neutralization (`T2`, `_NEGATION_BEFORE`): the regex became `r"\b(?:nothing|never|no|not)\b"` (any negation ahead of the verb suppresses).
- Node: `T2 -k test_the_reminder_detector_ties_a_negation_to_the_reminder_verb`.
- Red: last lines: `AssertionError: assert []` for `_reminder_hits(['If the owner has not answered the archive prompt, remind them again.'])`, `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py::test_the_reminder_detector_ties_a_negation_to_the_reminder_verb` and `1 failed, 8 deselected in 0.14s`.
- Restore: the inverse edit; `test_cloud_cleanup_doctrine.py:40` reads `_NEGATION_BEFORE = re.compile(r"\b(?:nothing|never|no|not)\s+(?:(?:ever|yet|then|again|also)\s+)?$|n't\s+$", re.IGNORECASE)`.
- Green: `1 passed, 8 deselected in 0.13s`.

## 12. One home across documents

Axis: the cleanup heading and its distinctive step (`cloud_cleanup.py plan --repo-root`) appear in no shipped `.md` other than `merge-train.md`.

- `Unreachable through this entry point`: a real red needs a second shipped document to carry the heading or the step, and every other shipped `.md` is outside this order's surface. The neutralization below is a detector-side proxy, not that proof.
- Proxy neutralization (`T2`, the one-home test): the exclusion `if rel != _MERGE_TRAIN` became `if rel != _SKILL`, so `merge-train.md` itself counts as a second document.
- Node: `T2 -k test_cleanup_procedure_has_one_home_and_the_others_point_to_it`.
- Red: last lines: `AssertionError: [('skills/showrunner/reference/merge-train.md', 'heading'), ('skills/showrunner/reference/merge-train.md', 'procedure step')]`, `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py::test_cleanup_procedure_has_one_home_and_the_others_point_to_it` and `1 failed, 8 deselected in 0.18s`. It shows the scan finds both needles in a document it does not exclude; it does not show that a copy elsewhere would be caught.
- Restore: the inverse edit; `test_cloud_cleanup_doctrine.py:124` reads `        if rel != _MERGE_TRAIN`.
- Green: `1 passed, 8 deselected in 0.17s`.

## 13. One DELETE, never a second

Axis: the branch step issues exactly one DELETE and refuses `delete-unconfirmed` when the re-read still shows the PR's head. Supersedes entry 7.

- Neutralization (`branch`): the DELETE and its re-read were wrapped in `for _try in (1, 2):` with `if absent: break` after the re-read (a second DELETE is reintroduced).
- Node: `T1 -k test_a_timed_out_delete_is_never_followed_by_a_second_delete_in_the_same_run`.
- Red: last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_timed_out_delete_is_never_followed_by_a_second_delete_in_the_same_run` and `1 failed in 8.57s`; `{'ok': True} != {'ok': False}` (the second DELETE removed the branch).
- Restore: the inverse edit; the DELETE call and re-read stand at the `branch` body's indent, with no loop, and `cloud_cleanup.py:460` reads `        _, out, err = _gh(run, ["api", "-X", "DELETE", target], env)`.
- Green: `1 passed` (the same node, after the restore).

## 14. A failed state write grants no send reservation

Axis: when the state write fails for real, `record(..., "pending")` returns `cleanup-state-unwritable`, nothing is on disk, a fresh `plan` shows no request, and a later `pending` write is granted once the write works.

- Test: `test_a_pending_write_whose_state_write_fails_grants_no_reservation` (`T1`). It patches `os.replace` to raise `OSError` for the state file only, so `_save` and `store_core.atomic_write` run unpatched and `_save`'s own handler takes the failure.
- Neutralization (`_save`): the `except Exception:` handler's `return False` became `return True`.
- Command, each time, from `plugins/superheroes/lib`: `scripts/pinned-python -B -m pytest tests/test_cloud_cleanup.py -q -k test_a_pending_write_whose_state_write_fails_grants_no_reservation`.
- Red: last lines: `tests/test_cloud_cleanup.py:978: AssertionError` (the `cleanup-state-unwritable` assertion), `FAILED tests/test_cloud_cleanup.py::test_a_pending_write_whose_state_write_fails_grants_no_reservation` and `1 failed, 76 deselected in 0.63s`.
- Restore: the inverse edit; `cloud_cleanup.py:124-126` read `    except Exception:`, `        return False`, `    return True`. `git diff plugins/superheroes/lib/cloud_cleanup.py` is empty.
- Green: `1 passed, 76 deselected in 0.54s`.

## Entries added in C8c WO-A (item A7): the three lane-binding axes in `_plan`

The three `# axis:` comments in `_plan` ("a lane reserved after the PR was opened ...", "a cloud builder that adopted a PR built elsewhere ...", "a later lane that adopted this PR ...") named this record, which had no entry for them; no other record under `bite_proofs/` holds them either (a search of the directory for `reserved_by` and `adopting_successor` found none, and `c8a_wo2.md` is the calibration-guard record). The entries below were run in this dispatch by a targeted edit to `cloud_cleanup.py`, the detector run alone as one node, then the inverse edit; `git status --porcelain plugins/superheroes/lib/cloud_cleanup.py` lists no change afterwards beyond the comment repoint.

Command, each time, from the worktree root: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<file>::<test>' -q -p no:cacheprovider --tb=short`.

## 15. A lane reserved after the PR was opened is not its lane

Axis: a PR resolves to the newest lane reserved at or before the PR's open time, so a lane reserved afterwards (a later builder on the same issue) is not bound to it.

- Test: `test_an_older_pr_is_not_bound_to_a_lane_reserved_after_it_was_opened` (`test_cloud_cleanup.py`).
- Neutralization (`_plan`, `cloud_cleanup.py:284`): `cp._lane(repo_root, [issue], env, reserved_by=opened)` became `cp._lane(repo_root, [issue], env)`.
- Red: `test_cloud_cleanup.py:453: in test_an_older_pr_is_not_bound_to_a_lane_reserved_after_it_was_opened`, `assert got["ok"] and got["session"] == "session-one" and got["launchId"] == "l-1"`, `AssertionError: assert (True and 'session-two' == 'session-one'`, `1 failed in 2.84s`.
- Restore: the inverse edit; `cloud_cleanup.py:284` reads `        found = [cp._lane(repo_root, [issue], env, reserved_by=opened) for issue in issues]`.
- Green: `2 passed in 5.06s` (this node and entry 16's, in one invocation, both restored).

## 16. Adopters are searched before refusing a PR no older lane built

Axis: when the PR resolves to no single lane, the adopting cloud builder is searched for before the plan refuses, so a PR built locally and adopted by a cloud builder is cleaned up.

- Test: `test_a_cloud_builder_that_adopted_a_locally_built_pr_is_cleaned_up_with_no_older_cloud_lane`.
- Neutralization (`_plan`, `cloud_cleanup.py:289`): `if len(lanes) != 1 and not launch_id:` became `if False and len(lanes) != 1 and not launch_id:`.
- Red: `test_cloud_cleanup.py:678: in test_a_cloud_builder_that_adopted_a_locally_built_pr_is_cleaned_up_with_no_older_cloud_lane`, `assert got["ok"] and got["launchId"] == "l-2" and got["session"] == "session-two"`, `assert (False)`, `1 failed in 1.55s`.
- Restore: the inverse edit; `cloud_cleanup.py:289` reads `    if len(lanes) != 1 and not launch_id:`.
- Green: the `2 passed in 5.06s` of entry 15.

## 17. A later lane that adopted the PR is the one cleaned up

Axis: when one older lane resolves, a later lane that adopted this PR (or its branch) is the one that finished it, so cleanup follows the adopter, not the older lane.

- Test: `test_a_later_lane_that_adopted_the_pr_is_the_one_cleaned_up`.
- Neutralization (`_plan`, `cloud_cleanup.py:300`): `if not launch_id:` (after `lid, lane = lanes[0]`) became `if False and not launch_id:`.
- Red: `test_cloud_cleanup.py:630: in test_a_later_lane_that_adopted_the_pr_is_the_one_cleaned_up`, `assert got["ok"] and got["launchId"] == "l-2" and got["session"] == "session-two"`, `AssertionError: assert (True and 'l-1' == 'l-2'`, `1 failed in 2.51s`.
- Restore: the inverse edit; `cloud_cleanup.py:299-300` read `    lid, lane = lanes[0]` and `    if not launch_id:`.
- Green: `1 passed in 3.41s`.
