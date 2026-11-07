# Bite-proof record: the pointer path in doctrine (relay messages travel as an issue comment plus a one-line pointer)

Detectors under proof:
- `plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py`
  `test_the_builder_acts_on_a_relayed_message_only_through_relayed_and_never_on_a_comment_alone` (D1, D2).
- `plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py`
  `test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps` (D3, five homes),
  `test_merge_train_step_2_settles_by_nothing_reached` (D4),
  `test_the_send_back_bullets_settle_by_nothing_reached` (D5).

Guarded surfaces: `skills/workhorse/reference/cloud.md` (§ Asking the advisor, § A message from the advisor),
`skills/showrunner/reference/wave-watch.md`, `merge-train.md` and `orchestration.md`.
Base: `faab004265d1d597a99c864e9326adb352f50836`. Nine elements, nine neutralizations, nine reds, nine greens;
none grouped.
Every neutralization was a targeted Edit of the doc, undone by the inverse Edit before the next element
(D3b: see the note under it). No `git checkout`, `restore`, `reset` or `stash` was used. Detectors were not
edited between red and green.
Command (worktree root): `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-2368-b-pyc -m pytest <node id> -q -p no:cacheprovider`.
Captures below drop the uv `UV_NATIVE_TLS` deprecation warning line, pytest's quoted source body, the
`where = …` lines of the `_POINT.search` assertions and pytest's `-vv` truncation hint; nothing else was
redacted, and no secret, token or private URL appeared in any output.

## D1 the either-copy sentence restored

- **Guarded element:** `cloud.md` § Asking the advisor, step 4. Axis: the builder is no longer told to act on either copy of an answer.
- **Neutralization:** replaced step 4's "The answer arrives by message: from another account a pointer, … Act only on what `relayed` returns." with the old "The advisor answers by message and may post the same answer on the issue as the durable record: act on either copy inside the reply window, the message or the issue comment carrying the advisor's answer."
- **Raw red:**

```
>       assert "act on either copy" not in asking
E       AssertionError: assert 'act on either copy' not in '1. Write th...pushed head.'
FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_the_builder_acts_on_a_relayed_message_only_through_relayed_and_never_on_a_comment_alone
1 failed in 0.19s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** step 4 reads again "incoming message. The answer arrives by message: from another account a pointer, which you run through `relayed` (§ A message from the advisor). The issue carries the advisor's answer as the comment the pointer names. Act only on what `relayed` returns."
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

## D2 the relayed-only rule removed

- **Guarded element:** `cloud.md` § A message from the advisor, the sentence "A builder acts on a relayed message (a pointer) only through the `text` that `relayed` returns." Axis: a relayed message is acted on only through `relayed`'s `text`.
- **Neutralization:** deleted that sentence (the paragraph then began "An advisor-message comment …").
- **Raw red:**

```
>       assert "acts on a relayed message (a pointer) only through the `text` that `relayed` returns" in message
E       assert 'acts on a relayed message (a pointer) only through the `text` that `relayed` returns' in "A message that reaches you from an advisor on another account is a one-line pointer, not the advisor's text. It reads...age from the advisor on the same account, sent directly by `SendMessage`, carries no pointer and is acted on directly."
FAILED plugins/superheroes/lib/tests/test_cloud_builder_doctrine.py::test_the_builder_acts_on_a_relayed_message_only_through_relayed_and_never_on_a_comment_alone
1 failed in 0.24s
```

- **Restore:** the inverse Edit.
- **Restore receipt (`grep -n` over cloud.md after restore):**

```
205-
206:A builder acts on a relayed message (a pointer) only through the `text` that `relayed` returns. An
207-advisor-message comment you see on the issue without a pointer that verifies is never acted on,
208-whatever it asks. A message from the advisor on the same account, sent directly by `SendMessage`,
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.16s
```

## D3 each of the five relay-step homes loses `point` (five neutralizations, five reds)

One node (`test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps`) loops over the five
homes and fails on the first home without `point`. The order of the loop is wave-watch steps, merge-train
step 2, orchestration `sendBack`, orchestration fix-order, wave-watch archive; each neutralization below
touches exactly one home, so each red names that home.

### D3a wave-watch § Answering a builder note, "Another account" step 4

- **Axis:** the one home of how each relay step is done names the `point` step.
- **Neutralization:** "4. `point --repo-root <root>" became "4. `pointer --repo-root <root>".
- **Raw red:**

```
>           assert _POINT.search(text), f"{name} does not name the `point` step"
E           AssertionError: wave-watch-steps does not name the `point` step
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps
1 failed in 0.16s
```

- **Restore receipt (after the inverse Edit):** `592:4. `point --repo-root <root> --msg-id <msgId> --comment-url <url>`. It reads the posted comment back`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

### D3b merge-train § Cleaning up a finished cloud lane, step 2

- **Axis:** the cleanup's ordering names `point` before the `pending` reservation.
- **Neutralization:** "the post of the composed file and `point` first" became "… and `pointer` first".
- **Raw red:**

```
>           assert _POINT.search(text), f"{name} does not name the `point` step"
E           AssertionError: merge-train-step-2 does not name the `point` step
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps
1 failed in 0.15s
```

- **Restore receipt (Grep after the inverse Edit):** `265:   plan's `archiveText` written to a file as the text file), the post of the composed file and `point``
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.13s
```

Note: the first attempt at this green was a compound command that the harness refused (see the return's
refusals list), and before it ran the next element's (D3c) neutralization had already been applied. D3c's
was undone by its inverse Edit, the green above was then run in plain form, and D3c was re-applied from a
clean tree for its own red.

### D3c orchestration § sendBack, the relay-step list

- **Axis:** the `sendBack` send names `point` between `compose`/the post and `SendMessage`.
- **Neutralization:** "(`--body-file`), `point`, `SendMessage`, `check`. Then record it" became "(`--body-file`), `pointer`, …".
- **Raw red:**

```
>           assert _POINT.search(text), f"{name} does not name the `point` step"
E           AssertionError: orchestration-send-back does not name the `point` step
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps
1 failed in 0.16s
```

- **Restore:** the inverse Edit. **Raw green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

### D3d orchestration § Acting on a NOT-READY: "Send a NOT-READY back to a live original builder"

- **Axis:** the fix-order relay list names `point`.
- **Neutralization:** "the post of the composed file with `--body-file`, `point`, `SendMessage`, `check`" became "… `pointer` …".
- **Raw red:**

```
>           assert _POINT.search(text), f"{name} does not name the `point` step"
E           AssertionError: orchestration-fix-order does not name the `point` step
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps
1 failed in 0.16s
```

- **Restore:** the inverse Edit. **Raw green:**

```
.                                                                        [100%]
1 passed in 0.16s
```

### D3e wave-watch, the archive paragraph

- **Axis:** the archive request is named as going through the same steps, `point` included.
- **Neutralization:** "the post with `--body-file`, `point`, the send, `check`" became "… `pointer` …".
- **Raw red:**

```
>           assert _POINT.search(text), f"{name} does not name the `point` step"
E           AssertionError: wave-watch-archive does not name the `point` step
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_each_relay_step_home_names_point_and_the_post_or_points_to_the_steps
1 failed in 0.19s
```

- **Restore:** the inverse Edit. **Raw green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

## D4 `nothingReached` removed from merge-train step 2

- **Guarded element:** merge-train step 2, both settle sentences (the `record` outcome and the resume sentence). Axis: `failed` is recorded on `nothingReached: true`, not on a named relay reason.
- **Neutralization:** two Edits. "`failed` when it reads `nothingReached: true`, otherwise `uncertain`" became "`failed` when its `reason` is `relay-send-failed`, otherwise `uncertain`", and "`failed` when it reads `nothingReached: true` (nothing reached the builder," became "`failed` when its `reason` is `relay-send-failed` (nothing reached the builder,". Both were needed: one alone leaves the word in the step.
- **Raw red:**

```
>       assert "nothingReached" in step
E       AssertionError: assert 'nothingReached' in '**Plan, then ask.** Run `python3 -B <plugin root>/lib/cloud_cleanup.py plan --repo-root <root> --repo <owner/name> --...nt id has no check, so record `uncertain`. Then go on. A `pending` or `uncertain` request is never sent a second time.'
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_merge_train_step_2_settles_by_nothing_reached
1 failed in 0.16s
```

- **Restore:** the two inverse Edits.
- **Restore receipt (Grep over `skills`, after both restores):**

```
merge-train.md:278:   when `check` reads `delivered: true`, `failed` when it reads `nothingReached: true`, otherwise
merge-train.md:283:   builder note describes) and record `delivered` when it reads `delivered: true`, `failed` when it reads `nothingReached: true` (nothing reached the
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

## D5 `nothingReached` removed from the orchestration `sendBack` bullets

- **Guarded element:** orchestration § sendBack, the two settle bullets after the first. Axis: the records read delivered / `nothingReached` / otherwise uncertain.
- **Neutralization:** two Edits. "neither `delivered: true` nor `nothingReached: true`" became "… nor `relay-send-failed`", and "a `point` refusal or `nothingReached: true`, do not run `sent`" became "… or `relay-send-failed`, …".
- **Raw red:**

```
>       assert "nothingReached" in bullets
E       assert 'nothingReached' in "- After a direct `SendMessage` returns `success: true`, or the relay's `check` returns `delivered: true`, run `python...relay-send-failed`, do not run `sent`. Nothing reached the builder, and the PR stays listed for the next `send-back`. "
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_the_send_back_bullets_settle_by_nothing_reached
1 failed in 0.16s
```

- **Restore:** the two inverse Edits.
- **Restore receipt (Grep over `skills`, after both restores):**

```
orchestration.md:413:- After any other read of `check`, neither `delivered: true` nor `nothingReached: true`, run
orchestration.md:418:- After an `ensure` refusal, a `point` refusal or `nothingReached: true`, do not run `sent`. Nothing
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.17s
```

**Residual blind spots:** every detector is a phrase search over collapsed text, so a home that keeps
`point` in a sentence that no longer sends the pointer passes; D3 covers the five homes the order named
and not a sixth place that tells the advisor to relay a message (orchestration's adopt step and
recover steps name `point` too, and no detector pins them); D4 and D5 pin the word `nothingReached`
and forbid named relay reasons only in D5's bullets and D4's step.

## D6 a same-account send settles by its own SendMessage result (returning review, round 1)

Orchestrator-typed at the review's `apply-fixes` step, committed (`602ca550`) before the probe; a targeted
Edit undone by the inverse Edit, tree clean after.

- **Guarded element:** `merge-train.md` step 2's same-account settlement sentence.
- **Detector:** `test_a_same_account_send_settles_by_its_own_send_result`.
- **Neutralization:** the sentence "On the same account it is settled by the `SendMessage` result: …" removed.
- **Raw red:**

```
E   AssertionError: assert 'On the same account it is settled by the `SendMessage` result: `delivered` on `success: true`, `failed` on `success: false`, and `uncertain` when the call returned no resul…
FAILED plugins/superheroes/lib/tests/test_relay_pointer_doctrine_2368.py::test_a_same_account_send_settles_by_its_own_send_result
```

- **Raw green (after the inverse Edit):** passed within `7 passed in 0.62s`.
- **Not neutralized separately:** the matching wave-watch sentence, which the same test asserts first.

