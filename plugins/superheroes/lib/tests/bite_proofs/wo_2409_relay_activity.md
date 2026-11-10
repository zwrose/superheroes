# Bite-proof record: #2409 `check` reads a pointer message delivered on a matching comment plus the target lane's later activity

Detectors under proof: `plugins/superheroes/lib/tests/test_relay_activity_2409.py` (named per element below).

Guarded code: `plugins/superheroes/lib/cloud_relay.py` (`check`, `_later_activity`, `_target_lane`, `_comment_leg`) and
`plugins/superheroes/lib/cloud_cleanup.py` (`record`, element E10 only).
Base: `79eb51ad4c121787b07b8105203aa5aedbf094c4`. Implementer: claude `sonnet-5.5`, work order WO-2409-A.
Every neutralization was a targeted Edit, undone by the inverse Edit before the next element; no
`git checkout`, `restore`, `reset` or `stash` was used. Detectors were not edited between red and green.
Command prefix (worktree root): `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-2409-pyc -m pytest <node ids> -q -p no:cacheprovider --tb=short`.
Captures drop only the uv `UV_NATIVE_TLS` deprecation warning line; nothing else was redacted, and no secret, token or
private URL appears. Each green run is the same node ids as its red run, after the inverse Edit; the restored lines are
quoted back from a `grep -n` (or `sed -n`) of the restored file taken between the inverse Edit and the green run.
Node ids below are shortened to the test function name; every one lives in `test_relay_activity_2409.py`.

Guarded-element set (declared by the order, each with its own neutralization, red and green): E1 to E10.

## E1 the comment-match requirement on the new path

- **Guarded element:** `cloud_relay.py` `check`, the `if comment_leg == "matches":` that gates the activity read (the `# axis:` line above it).
  Axis: the second basis reads the lane's activity only for a silent relay leg whose comment matches byte for byte.
- **Neutralization:** `if comment_leg == "matches":` became `if True:` (the activity is read whatever the comment leg).
- **Detector:** `test_an_altered_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read`,
  `test_a_missing_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read`.
- **Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_an_altered_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:209: in test_an_altered_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read
    _silent(out, msg["msgId"], activity_leg="not-read", missing=["relay-report", "comment-match", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   AssertionError: assert (False is False and False is False and 'comment-altered' == 'relay-silent'
E     
E     - relay-silent
E     + comment-altered)
_ test_a_missing_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:220: in test_a_missing_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read
    _silent(out, msg["msgId"], activity_leg="not-read", missing=["relay-report", "comment-match", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:150: in _silent
    assert out["activityLeg"] == activity_leg and out["missingLegs"] == missing
E   AssertionError: assert ('unattributable' == 'not-read'
E     
E     - not-read
E     + unattributable)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_an_altered_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_missing_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read
2 failed in 1.52s
```

- **Restore:** the inverse Edit (`if True:` back to `if comment_leg == "matches":`).
- **Restore receipt (restored lines, `grep -n`):**
  `1066:            if comment_leg == "matches":` / `1067:                activity_leg, activity = _later_activity(repo_root, msg, created, env, run)`
- **Raw green:**

```
..                                                                       [100%]
2 passed in 3.36s
```

## E2 the activity requirement (none reads silent)

- **Guarded element:** `cloud_relay.py` `check`, the `if activity_leg == "found":` that turns the verdict `delivered` (the `# axis:` line above it).
  Axis: a silent relay leg reads delivered on the second basis only when the lane's later activity was found.
- **Neutralization:** `if activity_leg == "found":` became `if True:` (any activity leg delivers).
- **Detector:** `test_a_matching_comment_with_no_later_activity_stays_relay_silent_and_names_the_legs`,
  `test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent`.
- **Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_matching_comment_with_no_later_activity_stays_relay_silent_and_names_the_legs _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:194: in test_a_matching_comment_with_no_later_activity_stays_relay_silent_and_names_the_legs
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
____ test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent ____
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:305: in test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent
    _silent(out, msg["msgId"], activity_leg="unreadable", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_matching_comment_with_no_later_activity_stays_relay_silent_and_names_the_legs
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent
2 failed in 2.68s
```

- **Restore:** the inverse Edit (`if True:` back to `if activity_leg == "found":`).
- **Restore receipt (restored lines, `grep -n`):**
  `1069:                if activity_leg == "found":` / `1070:                    verdict, basis = "delivered", "comment-and-activity"`
- **Raw green:**

```
..                                                                       [100%]
2 passed in 1.39s
```

## E3 the lane's lower bound

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if made < lower: continue` (the `# axis:` line above it).
  Axis: the lane's window opens at its own note cutoff; a comment created before it is not this lane's.
- **Neutralization:** `if made < lower:` became `if False:` (nothing is before the window).
- **Detector:** `test_a_progress_comment_created_before_the_lanes_cutoff_and_edited_after_the_comment_is_not_its_activity`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_progress_comment_created_before_the_lanes_cutoff_and_edited_after_the_comment_is_not_its_activity _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:251: in test_a_progress_comment_created_before_the_lanes_cutoff_and_edited_after_the_comment_is_not_its_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_progress_comment_created_before_the_lanes_cutoff_and_edited_after_the_comment_is_not_its_activity
1 failed in 1.27s
```

- **Restore:** the inverse Edit (`if False:` back to `if made < lower:`).
- **Restore receipt (restored lines, `grep -n`):** `977:        if made < lower:` / `978:            continue`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.24s
```

## E4 the lane's upper bound (a successor lane)

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if upper is not None and made >= upper: continue` (the `# axis:` line above it).
  Axis: the lane's window closes at the next launch's cutoff on the same issue; a successor lane's comment is not this lane's.
- **Neutralization:** `if upper is not None and made >= upper:` became `if False:` (the window never closes).
- **Detector:** `test_a_note_from_a_successor_lane_on_the_same_issue_is_not_the_target_lanes_activity`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_note_from_a_successor_lane_on_the_same_issue_is_not_the_target_lanes_activity _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:234: in test_a_note_from_a_successor_lane_on_the_same_issue_is_not_the_target_lanes_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_note_from_a_successor_lane_on_the_same_issue_is_not_the_target_lanes_activity
1 failed in 1.31s
```

- **Restore:** the inverse Edit (`if False:` back to `if upper is not None and made >= upper:`).
- **Restore receipt (restored lines, `grep -n`):** `980:        if upper is not None and made >= upper:` / `981:            continue`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.26s
```

## E5 the progress comment must be created at or before the pointer comment

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if made > created: continue` ahead of `edited = ...` (the `# axis:` line above it).
  Axis: a progress comment is the lane's edit only when created at or before the pointer comment; one created after it is a new comment.
- **Neutralization:** that `if made > created:` became `if False:`.
- **Detector:** `test_a_progress_comment_created_after_the_pointer_comment_is_not_activity`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_progress_comment_created_after_the_pointer_comment_is_not_activity ___
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:260: in test_a_progress_comment_created_after_the_pointer_comment_is_not_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_progress_comment_created_after_the_pointer_comment_is_not_activity
1 failed in 1.23s
```

- **Restore:** the inverse Edit. The first inverse Edit did not apply (the edit tool had dropped the trailing space
  of my neutralizing edit, leaving `edited =recover._epoch(...)`, so the inverse text did not match); a second run of the
  same node (which stayed red, identical output) confirmed the neutralization was still in the tree; the second inverse
  Edit restored both the condition and the space. That is one extra invocation for this element.
- **Restore receipt (restored lines, `sed -n 991,1000p`):**
  `        if made > created:` / `            continue` / `        edited = recover._epoch(comment.get("updated_at"))`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.14s
```

## E6 the progress phase rule (parked, stopped, handed back)

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if watch._phase_reads_resumed(...) and not watch._phase_reads_handed_back(...)` (the `# axis:` line above it).
  Axis: a progress edit is activity only when its phase reads working.
- **Neutralization:** that condition became `if True:`.
- **Detector:** `test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity` (three phases).
- **Raw red:**

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity[parked: waiting on the advisor] _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:268: in test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
_ test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity[handed back] _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:268: in test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
_ test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity[stopped: owner asked] _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:268: in test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity[parked: waiting on the advisor]
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity[handed back]
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity[stopped: owner asked]
3 failed in 1.51s
```

- **Restore:** the inverse Edit (`if True:` back to the two-call phase condition).
- **Restore receipt (restored lines, `grep -n`):**
  `1000:        if watch._phase_reads_resumed(progress["phase"]) and not watch._phase_reads_handed_back(progress["phase"]):` /
  `1001:            return "found", {"kind": "progress", "commentId": comment_id, "at": comment.get("updated_at")}`
- **Raw green:**

```
...                                                                      [100%]
3 passed in 1.46s
```

## E7 the note must be created strictly after the pointer comment

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if made > created:` before the note's `return "found"` (the `# axis:` line above it).
  Axis: a builder note is activity only when created strictly after the pointer comment.
- **Neutralization:** that `if made > created:` became `if True:`.
- **Detector:** `test_a_note_created_before_or_in_the_second_of_the_pointer_comment_is_not_activity` (`before`, `same-second`).
- **Raw red:**

```
.F                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_note_created_before_or_in_the_second_of_the_pointer_comment_is_not_activity[same-second] _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:286: in test_a_note_created_before_or_in_the_second_of_the_pointer_comment_is_not_activity
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:148: in _silent
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_note_created_before_or_in_the_second_of_the_pointer_comment_is_not_activity[same-second]
1 failed, 1 passed in 1.33s
```

- **What the red shows, and what it does not:** the `same-second` case bites. The `before` case stays green under the
  neutralization because the comment list is read with `since = pointer comment's created - 1` and keeps comments
  updated at or after it, so a note created earlier and never edited is not in the list at all; that case is held by the
  list read, not by this rule. A note created before the pointer comment and edited after it is not covered by any test
  (stated as a gap; the rule reads the note's `created_at`, never its `updated_at`).
- **Restore:** the inverse Edit (`if True:` back to `if made > created:`).
- **Restore receipt (restored lines, `grep -n`):**
  `987:            if made > created:` / `988:                return "found", {"kind": "note", "commentId": comment_id, "at": comment.get("created_at")}`
- **Raw green:**

```
..                                                                       [100%]
2 passed in 1.39s
```

## E8 a comment list that cannot be read is unreadable (fail closed)

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if comments is None: return "unreadable", None` (the `# axis:` line above it).
  Axis: comments that cannot be read whole leave the activity unreadable, never none and never found.
- **Neutralization:** `return "unreadable", None` became `comments = []` (an unreadable list reads as an empty one).
- **Detector:** `test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent ____
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:305: in test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent
    _silent(out, msg["msgId"], activity_leg="unreadable", missing=["relay-report", "later-activity"])
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:150: in _silent
    assert out["activityLeg"] == activity_leg and out["missingLegs"] == missing
E   AssertionError: assert ('none' == 'unreadable'
E     
E     - unreadable
E     + none)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent
1 failed in 1.27s
```

- **Restore:** the inverse Edit (`comments = []` back to `return "unreadable", None`).
- **Restore receipt (restored lines, `grep -n`):** `969:    if comments is None:` / `970:        return "unreadable", None`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.26s
```

## E9 an unattributable lane fails closed (no lane, two lanes, other issue, unreadable ledger, no created time)

- **Guarded element:** `cloud_relay.py` `_later_activity`, the `if lane is None: return "unattributable", None` (the `# axis:` line above the `lane = ...` line);
  the `_target_lane` lines that return None carry their own `# axis:` lines, all reaching this one return.
  Axis: a lane that cannot be attributed, or a pointer comment with no readable creation time, leaves the activity unjudged.
- **Neutralization:** `return "unattributable", None` became
  `lane, created = (msg.get("commentIssue"), 0, None), created or 0` (an unattributed lane is read as the pointer
  comment's issue from time 0, unbounded).
- **Detector:** `test_a_session_with_no_launch_is_unattributable_and_stays_silent`,
  `test_a_pointer_comment_without_a_created_at_leaves_the_activity_unjudged`,
  `test_two_cloud_launches_with_the_session_name_are_unattributable`,
  `test_a_pointer_comment_on_another_issue_than_the_lanes_is_unattributable`,
  `test_an_unreadable_launch_ledger_is_unattributable`.
- **Raw red:**

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_______ test_a_session_with_no_launch_is_unattributable_and_stays_silent _______
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:312: in test_a_session_with_no_launch_is_unattributable_and_stays_silent
    assert out["delivered"] is False and out["reason"] == "relay-silent" and out["pointerLeg"] == "relay-silent"
E   assert (True is False)
___ test_a_pointer_comment_without_a_created_at_leaves_the_activity_unjudged ___
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:324: in test_a_pointer_comment_without_a_created_at_leaves_the_activity_unjudged
    assert out["delivered"] is False and out["reason"] == "relay-silent" and out["commentLeg"] == "matches"
E   assert (True is False)
_______ test_two_cloud_launches_with_the_session_name_are_unattributable _______
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:335: in test_two_cloud_launches_with_the_session_name_are_unattributable
    assert out["delivered"] is False and out["activityLeg"] == "unattributable" and scene.gh.list_calls() == []
E   assert (True is False)
___ test_a_pointer_comment_on_another_issue_than_the_lanes_is_unattributable ___
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:343: in test_a_pointer_comment_on_another_issue_than_the_lanes_is_unattributable
    assert out["delivered"] is False and out["activityLeg"] == "unattributable" and scene.gh.list_calls() == []
E   assert (True is False)
______________ test_an_unreadable_launch_ledger_is_unattributable ______________
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:356: in test_an_unreadable_launch_ledger_is_unattributable
    assert out["delivered"] is False and out["activityLeg"] == "unattributable" and scene.gh.list_calls() == []
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_session_with_no_launch_is_unattributable_and_stays_silent
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_pointer_comment_without_a_created_at_leaves_the_activity_unjudged
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_two_cloud_launches_with_the_session_name_are_unattributable
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_a_pointer_comment_on_another_issue_than_the_lanes_is_unattributable
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_an_unreadable_launch_ledger_is_unattributable
5 failed in 1.85s
```

- **Restore:** the inverse Edit (the fallback line back to `return "unattributable", None`).
- **Restore receipt (restored lines, `grep -n`):** `963:    if lane is None:` / `964:        return "unattributable", None`
- **Raw green:**

```
.....                                                                    [100%]
5 passed in 1.80s
```

## E10 `cloud_cleanup.record` replaces an `uncertain` receipt with `delivered`

- **Guarded element:** `cloud_cleanup.py` `record`, the no-downgrade check
  `if old is not None and old["outcome"] in ("delivered", "failed") and outcome != "pending":` (the `# axis:` line above it).
  Axis: only `delivered` and `failed` are never downgraded, so a later `delivered` for the same msg id replaces `uncertain`.
- **Neutralization:** the tuple `("delivered", "failed")` became `("delivered", "failed", "uncertain")` (`uncertain` is treated like `delivered`/`failed`). The file is not part of the change; the restore was checked with `git status --porcelain -- plugins/superheroes/lib/cloud_cleanup.py`, which printed nothing.
- **Detector:** `test_an_archive_request_recorded_uncertain_settles_delivered_when_check_reads_delivered`
  (its `delivered` value comes from an actual `check` result on the new path).
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_archive_request_recorded_uncertain_settles_delivered_when_check_reads_delivered _
/home/user/wt-2409/plugins/superheroes/lib/tests/test_relay_activity_2409.py:387: in test_an_archive_request_recorded_uncertain_settles_delivered_when_check_reads_delivered
    assert got["ok"] is True and "already" not in got
E   AssertionError: assert (True is True and 'already' not in {'ok': True, 'already': True, 'request': {'repo': 'acme/widgets', 'pr': 412, 'session': 'issue-77-abcd1234', 'msgId': '5ffe10a645d0', ...}, 'ownerMessage': None})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_relay_activity_2409.py::test_an_archive_request_recorded_uncertain_settles_delivered_when_check_reads_delivered
1 failed in 1.21s
```

- **Restore:** the inverse Edit (`("delivered", "failed", "uncertain")` back to `("delivered", "failed")`).
- **Restore receipt (restored line, `grep -n`; and `git status --porcelain` over the file, empty):**
  `458:    if old is not None and old["outcome"] in ("delivered", "failed") and outcome != "pending":`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.23s
```
