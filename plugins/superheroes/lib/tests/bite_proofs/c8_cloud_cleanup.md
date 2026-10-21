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

## Entries added for the parent-issue lane (issue 2024)

A merged or closed PR whose linked issues hold no cloud lane is cleaned up under the lane of its linked issues' parent issue, and that lane's archive request goes at most once. Each entry below was run in this dispatch by a targeted edit to `cloud_cleanup.py` only (no test edited), the detector run alone as one node, then the inverse edit. After all eight restores `git diff --stat plugins/superheroes/lib/cloud_cleanup.py` read `1 file changed, 81 insertions(+), 16 deletions(-)`, the same as before the first neutralization.

Command, each time, from the worktree root: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest '<file>::<test>' -q -p no:cacheprovider --tb=short`. `<file>` is `plugins/superheroes/lib/tests/test_cloud_cleanup.py`.

The green for every entry below is one run of all 28 new tests together after the last restore (`-k "parent or layer or issue_read or a_request_held"`): `28 passed, 79 deselected in 10.37s`.

## 18. Linked issues that hold no lane are searched on their parent issue

Axis: when no linked issue holds a lane, the search widens to the linked issues' parent issues and marks the plan `viaParent`, so a stack launched once on its parent is cleaned up.

- Test: `test_a_layer_of_a_stack_is_cleaned_up_under_the_parent_issues_lane_and_the_request_goes_once`.
- Neutralization (`_plan`, `cloud_cleanup.py:329`): `scope, via_parent = parents, True` became `break`.
- Red: `test_cloud_cleanup.py:1055: in test_a_layer_of_a_stack_is_cleaned_up_under_the_parent_issues_lane_and_the_request_goes_once`, `assert first["ok"] and first["action"] == "cleanup" and first["issue"] == PARENT`, `E   assert (False)`, `1 failed in 1.85s`.
- Restore: the inverse edit; `cloud_cleanup.py:329` reads `            scope, via_parent = parents, True`.
- Green: the 28-test run above.

## 19. A launch id naming a lane on a parent issue is accepted

Axis: a `--launch-id` whose lane sits on another issue is this PR's lane only when that issue is a parent of a linked issue; any other issue stays `lane-mismatch`.

- Test: `test_a_launch_id_of_the_parent_issues_lane_is_this_layers_lane_but_an_unrelated_issues_is_not`.
- Neutralization (`_plan`, `cloud_cleanup.py:299`): `if lane_issue not in parents:` became `if True:` (every lane on another issue is refused). This bites the accepting half; the refusing half (`l-9` on an unrelated issue) passes with this neutralization, and no run here neutralizes it the other way (`if False:`), so the refusing half is unproven by this entry.
- Red: `test_cloud_cleanup.py:1101: in test_a_launch_id_of_the_parent_issues_lane_is_this_layers_lane_but_an_unrelated_issues_is_not`, `assert got["ok"] and got["action"] == "cleanup" and got["viaParent"] is True and got["launchId"] == "l-1"`, `E   assert (False)`, `1 failed in 2.41s`.
- Restore: the inverse edit; `cloud_cleanup.py:299` reads `            if lane_issue not in parents:`.
- Green: the 28-test run above.

## 20. The lane's request is carried to every layer

Axis: for a lane found through its parent issue, a request held on any layer of the lane is the request of every other layer, so a later layer's plan shows it delivered and sends nothing.

- Test: `test_a_layer_of_a_stack_is_cleaned_up_under_the_parent_issues_lane_and_the_request_goes_once`.
- Neutralization (`_plan`, `cloud_cleanup.py:351`): `if via_parent and (own is None or own["outcome"] == "failed"):` became `if False and via_parent and (own is None or own["outcome"] == "failed"):`.
- Red: `test_cloud_cleanup.py:1064: in test_a_layer_of_a_stack_is_cleaned_up_under_the_parent_issues_lane_and_the_request_goes_once`, `assert later["request"]["pr"] == 501 and later["request"]["msgId"] == "m-1"`, `KeyError: 'pr'` (the request read `{"state": "none"}`), `1 failed in 2.38s`.
- Restore: the inverse edit; `cloud_cleanup.py:351` reads `    if via_parent and (own is None or own["outcome"] == "failed"):`.
- Green: the 28-test run above.

## 21. A request held on another layer grants no second reservation

Axis: `record ... pending` on a layer refuses when the lane's request is a holding receipt that is not this PR's own for this closure, so the archive request is not sent once per layer.

- Test: `test_a_request_held_on_one_layer_is_the_lanes_request_and_grants_no_second_reservation[pending-request-in-progress]`.
- Neutralization (`record`, `cloud_cleanup.py:401`): `if "msgId" in held and not _same_receipt(...)` became `if False and "msgId" in held and not _same_receipt(...)`.
- Red: `test_cloud_cleanup.py:1081: in test_a_request_held_on_one_layer_is_the_lanes_request_and_grants_no_second_reservation`, `assert _record_n(w, 502, "m-2", "pending") == {"ok": False, "reason": reason}`, `AssertionError: assert {'ok': True, ...essage': None} == {'ok': False,...-in-progress'}`, `1 failed in 1.88s`.
- Restore: the inverse edit; `cloud_cleanup.py:401` reads `        if "msgId" in held and not _same_receipt(held, repo, number, got["session"], got["closedAt"]):`.
- Green: the 28-test run above.

## 22. A layer's own failed try does not hide the lane's hold

Axis: a layer whose own receipt is `failed` still sees the request another layer holds, so it neither resends over a delivered request nor reads the failed try as the lane's request.

- Test: `test_a_layers_own_failed_try_does_not_hide_the_request_another_layer_holds`.
- Neutralization (`_plan`, `cloud_cleanup.py:351`): `(own is None or own["outcome"] == "failed")` became `(own is None)`.
- Red: `test_cloud_cleanup.py:1200: in test_a_layers_own_failed_try_does_not_hide_the_request_another_layer_holds`, `assert again["request"]["pr"] == 502 and again["request"]["msgId"] == "m-2" and again["request"]["outcome"] == "delivered"`, `E   assert (501 == 502)`, `1 failed in 1.96s`.
- Restore: the inverse edit; `cloud_cleanup.py:351` reads `    if via_parent and (own is None or own["outcome"] == "failed"):`.
- Green: the 28-test run above.

## 23. A lane found through the parent is searched for adopters on the parent issues

Axis: after a lane is found on a parent issue, the later lane that adopted the PR is searched among the parent issues, where its successors are reserved, so cleanup follows the adopter.

- Test: `test_a_later_lane_on_the_parent_issue_that_adopted_the_layer_is_the_one_cleaned_up[by-pr]`.
- Neutralization (`_plan`, `cloud_cleanup.py:338`): `_adopting_successor(repo_root, lid, lane, scope, pr, head_ref, closed, env)` became `_adopting_successor(repo_root, lid, lane, issues, pr, head_ref, closed, env)`.
- Red: `test_cloud_cleanup.py:1245: in test_a_later_lane_on_the_parent_issue_that_adopted_the_layer_is_the_one_cleaned_up`, `assert got["ok"] and got["launchId"] == "l-2" and got["session"] == "session-two" and got["viaParent"] is True`, `AssertionError: assert (True and 'l-1' == 'l-2'`, `1 failed in 2.13s`.
- Restore: the inverse edit; `cloud_cleanup.py:338` reads `        lid, lane, reason = _adopting_successor(repo_root, lid, lane, scope, pr, head_ref, closed, env)`.
- Green: the 28-test run above.

## 24. An unreadable parent read refuses

Axis: a parent read that fails leaves the PR unbound as `issue-unreadable` rather than reading as no parent, so nothing is sent or deleted on a guess.

- Test: `test_an_issue_read_that_fails_or_is_not_an_object_refuses_and_sends_and_deletes_nothing`.
- Neutralization (`_plan`, `cloud_cleanup.py:324-325`): `if parents is None:` followed by `return _refusal("issue-unreadable"), None` became `if parents is None:` followed by `parents = []`.
- Red: `test_cloud_cleanup.py:1170: in test_an_issue_read_that_fails_or_is_not_an_object_refuses_and_sends_and_deletes_nothing`, `assert _plan(w) == want`, `{'reason': 'no-cloud-lane'} != {'reason': 'issue-unreadable'}`, `1 failed in 1.93s`.
- Restore: the inverse edit; `cloud_cleanup.py:324-325` read `            if parents is None:` and `                return _refusal("issue-unreadable"), None`.
- Green: the 28-test run above.

## 25. A parent in another repository is not a parent

Axis: a parent issue URL naming another repository is never a lane of this repository, so it yields no parent (compared without case).

- Test: `test_a_parent_in_another_repository_is_never_a_lane_of_this_repository`.
- Neutralization (`_parent_issues`, `cloud_cleanup.py:201`): `if match.group(1).lower() == repo.lower() and parent not in issues ...` became `if True and parent not in issues ...`.
- Red: `test_cloud_cleanup.py:1119: in test_a_parent_in_another_repository_is_never_a_lane_of_this_repository`, `assert _plan(w) == {"ok": False, "reason": "no-cloud-lane"}`, `assert {'ok': True, ...er/name', ...} == {'ok': False,...o-cloud-lane'}`, `1 failed in 1.86s`.
- Restore: the inverse edit; `cloud_cleanup.py:201` reads `        if match.group(1).lower() == repo.lower() and parent not in issues and parent not in parents:`.
- Green: the 28-test run above.

Entries 26-29 (review round 1: a stack lane is archived once, when every layer is closed). Each entry below was run in this dispatch by a targeted edit to `cloud_cleanup.py` only (no test edited), the detector run alone, then the inverse edit. Before the first neutralization and after each restore `git diff --stat -- plugins/superheroes/lib/cloud_cleanup.py` read `1 file changed, 30 insertions(+), 2 deletions(-)`. Command form as above. `<new>` is `plugins/superheroes/lib/tests/test_cloud_cleanup.py`; `<break-it>` is `plugins/superheroes/lib/tests/test_cloud_cleanup_parent_mixed_links_break_it.py`.

The green for every entry below is one run of the break-it file and the 16 new `<new>` tests together after the last restore (`-k "linking_parent_does_not or first_layer_merging or last_layer_to_close or delivered_request_keeps or cannot_be_read_or_are_not or not_exactly_closed or linking_its_sub_issue or whose_own_issue_cannot or none_a_sub_issue or lane_of_its_own_reads"`): `22 passed, 107 deselected in 9.11s`.

## 26. A PR linking its sub-issue and the lane's own issue is a layer of the stack

Axis: directly linking the shared parent issue must not bypass another layer's archive reservation, so such a PR reads `viaParent` and the lane-wide request rules apply (implicit and explicit launch id).

- Test: `<break-it>` (all six cases of `test_linking_parent_does_not_grant_another_archive_reservation`).
- Neutralization (`_plan`, `cloud_cleanup.py:350`): `if lane_issue in parents:` became `if False:`.
- Red: `test_cloud_cleanup_parent_mixed_links_break_it.py:36: in test_linking_parent_does_not_grant_another_archive_reservation`, `assert result == {"ok": False, "reason": reason}`, `AssertionError: assert {'ok': True, ...essage': None} == {'ok': False,...-in-progress'}` (and the same for `request-uncertain` and `request-delivered`, implicit and explicit), `6 failed in 4.45s`.
- Restore: the inverse edit; `cloud_cleanup.py:350` reads `        if lane_issue in parents:`.
- Green: the 22-test run above.

## 27. The stack-open hold

Axis: a stack lane is asked to archive only once every sub-issue of its issue is closed, so the plan of a layer closing while another layer is open carries no archive text and `record` pending refuses.

- Test: `test_the_first_layer_merging_while_upper_layers_are_open_holds_the_archive_but_not_the_branch`.
- Neutralization (`_plan`, `cloud_cleanup.py:380`): `elif any(row.get("state") != "closed" for row in found):` became `elif False:`.
- Red: `test_cloud_cleanup.py:1282: in test_the_first_layer_merging_while_upper_layers_are_open_holds_the_archive_but_not_the_branch`, `assert got["archiveText"] is None and got["archiveHeld"] == "stack-open" and got["openLayers"] == [202, 203]`, `assert ('Pull request #501 is merged, so this build is finished. Follow the section "When the advisor asks you to archive your session" in your cloud build reference.' is None)`, `1 failed in 5.17s`.
- Restore: the inverse edit; `cloud_cleanup.py:380` reads `        elif any(row.get("state") != "closed" for row in found):`.
- Green: the 22-test run above.

## 28. The unreadable-stack hold

Axis: a stack whose sub-issues cannot be read, or has none, is never asked to archive (fail closed).

- Test: `test_a_stack_whose_layers_cannot_be_read_or_are_not_all_closed_holds_the_archive[empty]` and `[unreadable]`.
- Neutralization (`_plan`, `cloud_cleanup.py:377`): `if not found:` became `if False:`.
- Red: `[empty]` at `test_cloud_cleanup.py:1327`, `assert got["ok"] and got["action"] == "cleanup" and got["archiveText"] is None`, `cleanup and 'Pull request #501 is merged, so this build is finished. ...' is None)`; `[unreadable]` `TypeError: 'NoneType' object is not iterable` at `cloud_cleanup.py:380` (the unread list reached the open-layer test); `2 failed, 1 passed in 3.15s` (the whole three-case function was run; the `open-without-an-int-number` case stays green, as it holds through `stack-open`).
- Restore: the inverse edit; `cloud_cleanup.py:377` reads `        if not found:`.
- Green: the 22-test run above.

## 29. `record` pending refuses a held archive

Axis: a reservation to send is never granted for a held archive, so nothing is sent while a layer is open.

- Test: `test_the_first_layer_merging_while_upper_layers_are_open_holds_the_archive_but_not_the_branch` (its `record` row).
- Neutralization (`record`, `cloud_cleanup.py:430`): `if got.get("archiveHeld"):` became `if False and got.get("archiveHeld"):`.
- Red: `test_cloud_cleanup.py:1284: in test_the_first_layer_merging_while_upper_layers_are_open_holds_the_archive_but_not_the_branch`, `assert _record_n(w, 501, "m-1", "pending") == {"ok": False, "reason": "archive-held"}`, `AssertionError: assert {'ok': True, ...essage': None} == {'ok': False,...archive-held'}`, `1 failed in 2.17s`.
- Restore: the inverse edit; `cloud_cleanup.py:430` reads `        if got.get("archiveHeld"):`.
- Green: the 22-test run above.

Entries 30-31 (review round 2: a layer whose classification read fails is unclassified, never a refusal). Each entry below was run by a targeted edit to `cloud_cleanup.py` only (no test edited), the detector run alone, then the inverse edit. `<new>` is `plugins/superheroes/lib/tests/test_cloud_cleanup.py`. T-unclassified-plain is `test_a_pr_whose_other_linked_issue_cannot_be_read_is_cleaned_up_as_an_ordinary_lane`.

The green for both entries is one run of the new and updated tests after the last restore (`-k "other_linked_issue_cannot_be_read or whose_own_issue_cannot_be_read_is_held or delivered_on_another_pr_of_the_session"`): `4 passed, 122 deselected in 3.07s`.

## 30. An unclassified layer never refuses

Axis: a failed read of a PR's other linked issues, while deciding whether a directly-found lane is a stack lane, leaves the layer unclassified and never refuses the plan, so an unrelated issue cannot block an ordinary lane's branch step.

- Test: T-unclassified-plain, with `test_a_layer_linking_the_parent_whose_own_issue_cannot_be_read_is_held_on_its_stack`.
- Neutralization (`_plan`, `cloud_cleanup.py:356`): the line `    if unclassified: return _refusal("issue-unreadable"), None` inserted right after the classification block, before `session = lane.get("cloudSessionName")`.
- Red: `test_cloud_cleanup.py:1414: in test_a_pr_whose_other_linked_issue_cannot_be_read_is_cleaned_up_as_an_ordinary_lane`, `assert got["ok"] is True and got["action"] == "cleanup" and got["issue"] == 101 and got["launchId"] == "l-1"`, `E   assert (False is True)`, `1 failed, 125 deselected in 2.51s`.
- Restore: the inverse edit (the inserted line removed); `cloud_cleanup.py:356` reads `    session = lane.get("cloudSessionName")`, and `grep -n 'if unclassified: return'` finds nothing.
- Green: the 4-test run above.

## 31. An unclassified layer with no sub-issues is not held

Axis: an unclassified layer is held only on the evidence a proven stack is held on (a sub-issue that is not closed, or a sub-issue read that fails); an empty sub-issue list means the lane's issue is not a stack, so the archive goes out as before.

- Test: T-unclassified-plain.
- Neutralization (`_plan`, `cloud_cleanup.py:383`): `if found is None or (not found and via_parent):` became `if found is None or (not found and (via_parent or unclassified)):`.
- Red: `test_cloud_cleanup.py:1415: in test_a_pr_whose_other_linked_issue_cannot_be_read_is_cleaned_up_as_an_ordinary_lane`, `assert "viaParent" not in got and "archiveHeld" not in got`, `AssertionError: assert ('viaParent' not in {'ok': True, 'action': 'cleanup', 'outcome': 'merged', 'repo': 'owner/name', ...} and 'archiveHeld' not in {'ok': True, 'action': 'cleanup', 'outcome': 'merged', 'repo': 'owner/name', ...})`, `1 failed, 125 deselected in 5.84s`.
- Restore: the inverse edit; `cloud_cleanup.py:383` reads `        if found is None or (not found and via_parent):`.
- Green: the 4-test run above.
