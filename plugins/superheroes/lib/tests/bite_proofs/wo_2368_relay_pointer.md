# Bite-proof record: #2368 the relay forwards a pointer, and a message is delivered only when the pointer and the comment both check out

Detectors under proof: `plugins/superheroes/lib/tests/test_relay_pointer_2368.py` (named per element below).

Guarded code: `plugins/superheroes/lib/cloud_relay.py` (`check`, `_decide`, `point`, `_nothing_reached`) and
`plugins/superheroes/lib/cloud_builder.py` (`relayed`).
Base: `faab004265d1d597a99c864e9326adb352f50836`. Implementer: claude `sonnet-5.5`, work order WO-A.
Every neutralization was a targeted Edit, undone by the inverse Edit before the next element; no
`git checkout`, `restore`, `reset` or `stash` was used. Detectors were not edited between red and green.
Command prefix (worktree root): `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-2368-a-pyc -m pytest <node ids> -q -p no:cacheprovider --tb=<line|short>`.
Captures drop only the uv `UV_NATIVE_TLS` deprecation warning line (and the blank line / `====` banner lines pytest
prints around the failure summary); nothing else was redacted, and no secret, token or private URL appears.
Each green run is the same node ids as its red run, after the inverse Edit; the restored lines are quoted back
from a `grep -n` of the restored file in the same command as the green run.

Guarded-element set (declared by the order, each with its own neutralization, red and green): E1 to E7.

## E1 the comment-leg gate in `check`

- **Guarded element:** `cloud_relay.py` `check`, the `delivered = ...` line (the `# axis:` line above it).
  Axis: a pointer entry reads delivered only when the relay leg delivered and the comment, read back, matches.
- **Neutralization:** `delivered = verdict == "delivered" and comment_leg == "matches"` became
  `delivered = verdict == "delivered" and True` (any comment leg reads as matching).
- **Detector:** `test_an_exact_pointer_whose_comment_was_edited_after_point_is_not_delivered`,
  `..._was_deleted_reads_comment_missing`, `..._cannot_be_read_reads_comment_unreadable` (row 4).
- **Raw red:**

```
FFF                                                                      [100%]
E   assert (True is False)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:119: assert (True is False)
E   assert (True is False)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:133: assert (True is False)
E   assert (True is False)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:144: assert (True is False)
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_an_exact_pointer_whose_comment_was_edited_after_point_is_not_delivered
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_an_exact_pointer_whose_comment_was_deleted_reads_comment_missing
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_an_exact_pointer_whose_comment_cannot_be_read_reads_comment_unreadable
3 failed in 2.12s
```

- **Restore:** the inverse Edit (`and True` back to `and comment_leg == "matches"`).
- **Restore receipt (restored line, `grep -n` of the file):** `901:    delivered = verdict == "delivered" and comment_leg == "matches"`
- **Raw green:**

```
...                                                                      [100%]
3 passed in 2.02s
```

## E2 the relay-leg exactness on a pointer entry

- **Guarded element:** `cloud_relay.py` `_decide`, the `other` / `exact` comparisons against `msg["forward"]`
  (the `# axis:` line above `other`). Axis: on a pointer entry the relay's send must equal the one-line pointer
  character for character; a send that merely names the comment, or alters its URL or sha256, never reads delivered.
- **Neutralization (three lines, one change: a send that contains the pointer's URL is attributed and exact):**
  `sends = [... if t.lstrip().startswith(header)]` gained `or (msg.get("commentUrl") or "\0") in t`;
  `other = [... if t != msg["forward"]]` gained `and (msg.get("commentUrl") or "\0") not in t`;
  `exact = [... if t == msg["forward"]]` gained `or (msg.get("commentUrl") or "\0") in t`.
- **Detector:** `test_a_pointer_sent_with_its_header_phrase_dropped_is_not_delivered` (row 2) and
  `test_a_pointer_with_one_character_altered_is_not_delivered[url|sha]` (row 3).
- **Raw red:**

```
F.F                                                                      [100%]
E   assert (True is False)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:94: assert (True is False)
E   assert (True is False)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:108: assert (True is False)
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_a_pointer_sent_with_its_header_phrase_dropped_is_not_delivered
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_a_pointer_with_one_character_altered_is_not_delivered[sha]
2 failed, 1 passed in 0.73s
```

The `[url]` case passes under this neutralization: an altered URL no longer contains the original one, so it is
still a mismatch. The header-dropped and sha-altered cases are the ones that discriminate.

- **Restore:** the three inverse Edits.
- **Restore receipt (`grep -n` of the restored lines):**
  `732:    sends = [(t, i) for t, i in sends if t.lstrip().startswith(header)]`,
  `734:    other = [t for t, _ in sends if t != msg["forward"]]`,
  `737:    exact = [results.get(i) for t, i in sends if t == msg["forward"]]`
- **Raw green:**

```
...                                                                      [100%]
3 passed in 0.74s
```

## E3 `pointer-not-composed`

- **Guarded element:** `cloud_relay.py` `check`, the `if is_pointer and not isinstance(msg.get("forward"), str):` branch.
  Axis: a message composed with a comment hash and never pointed reads `pointer-not-composed` at once, with no
  wait and no relay read, and nothing reached the builder.
- **Neutralization:** the condition line became `msg = dict(msg, forward=msg.get("forward") or "")` followed by
  `if False:` (an unpointed entry falls through to the relay leg with an empty forward text instead of crashing it).
- **Detector:** `test_a_message_composed_and_never_pointed_reads_pointer_not_composed_with_nothing_reached` (row 6).
- **Raw red:**

```
F                                                                        [100%]
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:178: in test_a_message_composed_and_never_pointed_reads_pointer_not_composed_with_nothing_reached
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "pointer-not-composed"
E   AssertionError: assert (False is False and False is False and 'relay-silent' == 'pointer-not-composed'
E     - pointer-not-composed
E     + relay-silent)
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_a_message_composed_and_never_pointed_reads_pointer_not_composed_with_nothing_reached
1 failed in 0.56s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** `871:    if is_pointer and not isinstance(msg.get("forward"), str):`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.52s
```

## E4 `legacy-unverified`

- **Guarded element:** `cloud_relay.py` `check`, the `if not is_pointer and verdict == "delivered": verdict = "legacy-unverified"` block.
  Axis: an entry composed before comment hashes were recorded can be sent exactly and still never reads delivered.
- **Neutralization:** the block and the `# axis:` comments above `delivered` were replaced by
  `delivered = verdict == "delivered" and (not is_pointer or comment_leg == "matches")` (a legacy relay-leg delivered stays delivered).
- **Detector:** `test_a_pre_upgrade_entry_sent_exactly_with_success_is_never_delivered` (row 7).
- **Raw red:**

```
F                                                                        [100%]
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:235: in test_a_pre_upgrade_entry_sent_exactly_with_success_is_never_delivered
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "legacy-unverified"
E   assert (True is False)
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_a_pre_upgrade_entry_sent_exactly_with_success_is_never_delivered
1 failed in 0.58s
```

- **Restore:** the inverse Edit (the block and both `# axis:` comments back).
- **Restore receipt (`grep -n -B3` of the restored lines):**
  `898:        # axis: an entry composed before comment hashes were recorded ... wo_2368_relay_pointer.md`,
  `899:        verdict = "legacy-unverified"`,
  `900:    # axis: a pointer entry reads delivered only when ... wo_2368_relay_pointer.md`,
  `901:    delivered = verdict == "delivered" and comment_leg == "matches"`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.55s
```

## E5 `point`'s hash read-back

- **Guarded element:** `cloud_relay.py` `point`, the `if seen != expected:` refusal (the `# axis:` line above it).
  Axis: the posted comment, read back, must hash to the composed body; an edited one is refused and no pointer is recorded.
- **Neutralization:** `if seen != expected:` became `if False:`.
- **Detector:** `test_point_refusals_in_order_each_leave_the_state_unchanged` (row 8; its `comment-altered` step,
  where the posted bytes differ by one trailing newline). The refusals before that step still pass, so the red
  is at the `comment-altered` step.
- **Raw red:**

```
F                                                                        [100%]
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:321: in test_point_refusals_in_order_each_leave_the_state_unchanged
    out = refused("comment-altered")
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:292: in refused
    assert out["ok"] is False and out["reason"] == reason, out
E   AssertionError: {'ok': True, 'msgId': 'e53657b7e443', 'relay': 'superheroes-relay-claude-two-4cf8c5cd', 'commentUrl': 'https://github.com/acme/widgets/issues/77#issuecomment-1001', ...}
E   assert (True is False)
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_point_refusals_in_order_each_leave_the_state_unchanged
1 failed in 1.00s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** `475:    if seen != expected:` / `476:        return _refuse("comment-altered", expectedSha256=expected, foundSha256=seen)`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.01s
```

## E6 `relayed`'s hash comparison

- **Guarded element:** `cloud_builder.py` `relayed`, the `comment_sha256(body) != parsed["sha256"] or text is None` refusal.
  Axis: the comment's body must hash to the pointer's sha256; an edited comment is refused and its text never returned.
- **Neutralization:** `if relay.comment_sha256(body) != parsed["sha256"] or text is None:` became `if text is None:`.
- **Detector:** `test_relayed_refusals_each_carry_a_note_question` (row 11; its `comment-altered` step edits the
  comment body but leaves the marker and header intact, so only the hash comparison can refuse it).
- **Raw red:**

```
F                                                                        [100%]
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:493: in test_relayed_refusals_each_carry_a_note_question
    out = _relayed_refused(world, "comment-altered", pointer=pointer, known=known)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:466: in _relayed_refused
    assert out["ok"] is False and out["reason"] == reason, out
E   AssertionError: {'ok': True, 'msgId': 'e023c9c6135f', 'commentUrl': 'https://github.com/acme/widgets/issues/77#issuecomment-1001', 'text': 'Please do the thing. tail'}
E   assert (True is False)
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_relayed_refusals_each_carry_a_note_question
1 failed in 0.55s
```

(The first restore Edit of this element was refused as non-unique; the command run beside it therefore ran
against the still-neutralized file and printed this same red a second time, with msgId `c2cc4eb4a8ce` and then
`e023c9c6135f` in the two runs. The restore was redone with enough context to be unique, then the green run below.)

- **Restore:** the inverse Edit, with the following `return _relayed_refusal("comment-altered",` line as context.
- **Restore receipt (`grep -n -B1 -A1` of the restored line):**
  `745:    if relay.comment_sha256(body) != parsed["sha256"] or text is None:` /
  `746:        return _relayed_refusal("comment-altered", "the comment it names does not match the pointer's sha256", parsed)`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.58s
```

## E7 `nothingReached`

- **Guarded element:** `cloud_relay.py` `_nothing_reached` (the `# axis:` line above its return), used by `check` and `_check_refusal`.
  Axis: `nothingReached` is True only for `relay-send-failed` and `pointer-not-composed`.
- **Neutralization:** `return reason in _NOTHING_REACHED` became `return False`.
- **Detector:** `test_a_message_composed_and_never_pointed_reads_pointer_not_composed_with_nothing_reached`,
  `test_nothing_reached_is_true_only_for_a_failed_send_and_an_unpointed_message`,
  `test_a_failed_send_with_a_missing_comment_is_still_nothing_reached` (row 6).
- **Raw red:**

```
FFF                                                                      [100%]
E   assert (False is True)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:179: assert (False is True)
E   AssertionError: assert ('relay-send-failed' == 'relay-send-failed'
        relay-send-failed and False is True)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:192: AssertionError: assert ('relay-send-failed' == 'relay-send-failed'
E   AssertionError: assert ('relay-send-failed' == 'relay-send-failed'
        relay-send-failed and False is True)
/home/user/wt-2368-a/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:225: AssertionError: assert ('relay-send-failed' == 'relay-send-failed'
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_a_message_composed_and_never_pointed_reads_pointer_not_composed_with_nothing_reached
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_nothing_reached_is_true_only_for_a_failed_send_and_an_unpointed_message
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_a_failed_send_with_a_missing_comment_is_still_nothing_reached
3 failed in 0.71s
```

- **Restore:** the inverse Edit (the first attempt was refused as non-unique and no command ran beside it; redone with the `# axis:` line's tail as context).
- **Restore receipt (`grep -n -B1` of the restored line):** `829:    return reason in _NOTHING_REACHED` (line 828 is the `# axis:` comment above it).
- **Raw green:**

```
...                                                                      [100%]
3 passed in 0.89s
```

## E8 the delayed-delivery adopt test on the pointer path

Implementer: claude `sonnet-5.5`, work order WO-C. Command prefix (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo-2368-c-pyc -m pytest plugins/superheroes/lib/tests/test_adopt_delayed_relay_delivery_break_it.py -q -p no:cacheprovider`.
Captures drop only the uv `UV_NATIVE_TLS` deprecation warning line; the red capture is shortened to the
decisive lines (the test source echo, ~60 lines, and the blank/`====` banner lines are elided); no secret, token or private URL appears.

- **Guarded element:** `test_adopt_delayed_relay_delivery_break_it.py::test_delivery_after_a_new_handback_keeps_the_lane`,
  the `assert checked["delivered"] is True` precondition (line 80). Axis: a fix order delivered after the latest
  handback keeps the lane from being adopted; the test reaches "delivered" through the pointer path (compose, post
  the body file into a fake gh, `point`, a relay record of the exact pointer with success, `check`).
- **Neutralization:** the relay-record send line `adoption.SESSION_TITLE, pointed["forward"], delivered_at,`
  became `adoption.SESSION_TITLE, pointed["forward"] + "x", delivered_at,` (the pointer sent with one character added).
- **Raw red:**

```
F                                                                        [100%]
>       assert checked["delivered"] is True, checked
E       AssertionError: {'ok': False, 'delivered': False, 'reason': 'relay-text-mismatch', 'msgId': '50a2486cb25b', ...}
E       assert False is True

/home/user/wt-2368/plugins/superheroes/lib/tests/test_adopt_delayed_relay_delivery_break_it.py:80: AssertionError
FAILED plugins/superheroes/lib/tests/test_adopt_delayed_relay_delivery_break_it.py::test_delivery_after_a_new_handback_keeps_the_lane
1 failed in 6.97s
```

- **Restore:** the inverse Edit (`+ "x"` removed).
- **Restore receipt (`grep -n` of the restored line):**
  `76:        "toolu_delayed_fix", adoption.SESSION_TITLE, pointed["forward"], delivered_at,`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 2.63s
```

## Residual blind spots

- The `nothingReached` proof pins the whole truth table through three tests, but the neutralization (`return False`)
  is one failure mode; flipping a single reason into the tuple (say, adding `relay-silent`) is caught by
  `test_nothing_reached_is_true_only_for_a_failed_send_and_an_unpointed_message`, which was not separately neutralized.
- E2's `[url]` parametrization is not discriminated by the URL-contains neutralization (see E2); it is covered
  by the exactness comparison as a whole, not by that neutralization.
- `read_comment`, `parse_pointer`, `comment_text` and the `compose` body-file write carry their own tests
  (`test_a_pointer_line_has_the_one_documented_shape`, `test_anything_that_is_not_a_pointer_is_none`,
  `test_the_comment_helpers_agree_with_each_other`, `test_compose_writes_the_comment_body_file_byte_exact_and_records_its_hash`)
  but were not neutralized one by one: the order's guarded-element set was E1 to E7 only.

## E9 an already-pointed message is judged before its URL (review round 2)

Orchestrator-typed at the review's `apply-fixes` step, committed (`c17236a0`) before the probe; the
probe was a targeted Edit in the build worktree, undone by the inverse Edit, and the tree read clean after.

- **Guarded element:** `point`, the `commentUrl` block now placed before the URL and lane checks.
  Axis: every refusal of a message that already has a pointer is `pointer-already-composed`.
- **Detector:** `test_point_refusals_in_order_each_leave_the_state_unchanged`, its step 4 (an already-pointed
  message given a URL on another issue, a malformed URL and no URL).
- **Neutralization:** the block moved back after the `comment-url-invalid` check.
- **Raw red:**

```
E   AssertionError: {'ok': False, 'reason': 'comment-url-invalid'}
    assert (False is False and 'comment-url-invalid' == 'pointer-already-composed'
/home/user/wt-2368/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:292: AssertionError: {'ok': False, 'reason': 'comment-url-invalid'}
1 failed in 1.10s
```

- **Raw green (after the inverse Edit):** `1 passed in 17.14s`.

## E10 a point refusal says nothing was sent only when no pointer can exist (review round 3)

Orchestrator-typed at the review's `apply-fixes` step, committed (`8759def5`) before the probe; a targeted
Edit undone by the inverse Edit, tree clean after.

- **Guarded element:** `point`'s `nothingSent` stamp (`reason in _POINT_NOTHING_SENT`).
  Axis: an unreadable state, a pre-upgrade entry and an already-pointed message read `nothingSent: false`.
- **Detector:** `test_a_point_refusal_says_nothing_was_sent_only_when_no_pointer_can_exist`.
- **Neutralization:** the stamp became `out["nothingSent"] = True`.
- **Raw red:**

```
E   AssertionError: assert ('not-a-point...essage', True) == ('not-a-point...ssage', False)
/home/user/wt-2368/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:386: AssertionError: assert ('not-a-point...essage', True) == ('not-a-point...ssage', False)
1 failed in 16.16s
```

- **Raw green (after the inverse Edit):** `1 passed in 0.86s`.
- **Not neutralized separately:** each member of `_POINT_NOTHING_SENT` one by one; the test asserts every
  member's value, so a member dropped from the tuple reads false and fails its own line.

## E11 `point` checks the comment's repository (WO-D, fix leg V839-a)

Order-named. Base `98124e77`. A targeted Edit in the build worktree, undone by the inverse Edit.

- **Guarded element:** `cloud_relay.py` `_point`, the `if repo != lane_name:` comparison (the `# axis:` line above it).
  Axis: a comment on the same-numbered issue of another repository is refused `comment-not-on-lane-repo`, nothing
  recorded, nothing read.
- **Detector:** `test_relay_pointer_2368.py::test_point_refuses_a_comment_on_another_repository_and_check_never_reads_delivered`.
- **Neutralization:** `if repo != lane_name:` became `if False and repo != lane_name:`.
- **Raw red** (the `UV_NATIVE_TLS` warning line and the traceback-body lines past the assertion dropped; each
  remaining line cut at 400 characters, none was that long):

```
>       assert out["ok"] is False and out["reason"] == "comment-not-on-lane-repo", out
E       AssertionError: {'ok': True, 'msgId': '3f12e76e641b', 'relay': 'superheroes-relay-claude-two-cdf0d56a', 'commentUrl': 'https://github.com/other/repo/issues/77#issuecomment-1001', ...}
E       assert (True is False)
/home/user/wt-2368/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:367: AssertionError
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_point_refuses_a_comment_on_another_repository_and_check_never_reads_delivered
1 failed in 3.57s
```

- **Restore:** the inverse Edit, `if False and repo != lane_name:` back to `if repo != lane_name:`.
- **Restore receipt:** `grep -n "if repo != lane_name\|if lane_name is None\|False and"` on `cloud_relay.py` read
  `504:    if repo != lane_name:` and `501:    if lane_name is None:`, with no `False and`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.65s
```

## E12 the fail-closed read of the lane's repository (WO-D, fix leg V839-a)

Order-named. Same method as E11.

- **Guarded element:** `cloud_relay.py` `_point`, the `if lane_name is None: return _refuse(why)` branch (the `# axis:` line above it).
  Axis: a lane repository that cannot be read refuses `lane-repo-unreadable` before any comment is read, and reads
  `nothingSent: false`.
- **Detector:** `test_relay_pointer_2368.py::test_point_refuses_when_the_lane_repository_cannot_be_read` (no origin,
  then a gitlab origin).
- **Neutralization:** `if lane_name is None:` became `if False and lane_name is None:` (the unreadable result falls
  through to the comparison).
- **Raw red** (same elisions as E11):

```
E       AssertionError: {'ok': False, 'reason': 'comment-not-on-lane-repo', 'laneRepo': None, 'commentRepo': 'acme/widgets', ...}
E       assert (False is False and 'comment-not-on-lane-repo' == 'lane-repo-unreadable'
E         - lane-repo-unreadable
E         + comment-not-on-lane-repo
/home/user/wt-2368/plugins/superheroes/lib/tests/test_relay_pointer_2368.py:387: AssertionError
FAILED plugins/superheroes/lib/tests/test_relay_pointer_2368.py::test_point_refuses_when_the_lane_repository_cannot_be_read
1 failed in 1.52s
```

- **Restore:** the inverse Edit, `if False and lane_name is None:` back to `if lane_name is None:`.
- **Restore receipt:** the same `grep` read `501:    if lane_name is None:` and `504:    if repo != lane_name:`, no `False and`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.58s
```

## Residual blind spots (WO-D)

- With E12 neutralized the code still refused (as `comment-not-on-lane-repo`, `laneRepo: None`); the detector went red
  on the reason. A neutralization that let an unreadable repository reach the comment read would also be red on the
  `world.gh.calls == []` line, which was not separately neutralized.
- `lane_repo`'s parsing is pinned by unit rows (`test_lane_repo_*`), not neutralized one by one.

## E13 point compares repository names without case (returning review, round 1)

Orchestrator-typed at the review's `apply-fixes` step, committed (`7d70dacd`) before the probe; a targeted
Edit undone by the inverse Edit, tree clean after.

- **Guarded element:** `_point`, `repo.lower() != lane_name.lower()`. Axis: an origin spelled `Acme/Widgets`
  accepts a comment URL on `acme/widgets`.
- **Detector:** `test_point_reads_a_lane_repository_name_whatever_its_case`.
- **Neutralization:** the comparison became `repo != lane_name`.
- **Raw red:**

```
E   AssertionError: {'ok': False, 'reason': 'comment-not-on-lane-repo', 'laneRepo': 'Acme/Widgets', 'commentRepo': 'acme/widgets', ...}
1 failed in 0.92s
```

- **Raw green (after the inverse Edit):** passed within `7 passed in 0.62s`.
- **Not neutralized separately:** `relayed`'s matching `.lower()`, pinned by
  `test_relayed_reads_a_repository_name_whatever_its_case`.

