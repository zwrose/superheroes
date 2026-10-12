# C7-WO-B (#1748) — the relay's exact-text check: bite-proof record

Implementer-run record. Method: an exact-string edit of the production element in
`plugins/superheroes/lib/cloud_relay.py` (the old string asserted to occur exactly once), the
detector run alone by its exact node id (red), the inverse edit, the same node again (green), the
restored lines read back by grep, and `git status --porcelain` showing only the two new files.
Detector file: `plugins/superheroes/lib/tests/test_cloud_relay.py` (called `T::` below), unedited
between red and green. Captures carry no secrets; the temp paths in pytest's header are the only
machine-specific text and are left as printed.

Five guarded elements, all in `_decide` / `_sends`; the axis of each is the decision about *what
the relay actually sent* (never the relay's prose), not presence of a send.

Disclosures: none. Element 3's first restore attempt failed on the helper's own uniqueness assert
(the neutralized text matched twice); the file was left neutralized for that moment only, and was
restored by the inverse edit with a corrected, longer match string — the green below is after that
restore, and the post-restore grep shows the line back.

## 1 — the exact comparison (`t == msg["forward"]` and `t != msg["forward"]`, cloud_relay.py:281, :287)

- axis: character-exact equality of the sent text with the forward text (a one-character
  difference is a mismatch; whitespace is part of the text).
- detector: `T::test_one_character_difference_is_a_mismatch`
- neutralization (both sites, compare after whitespace normalization):

```diff
-    exact = [results.get(i) for t, i in sends if t == msg["forward"]]
+    exact = [results.get(i) for t, i in sends if t.split() == msg["forward"].split()]
-    other = [t for t, _ in sends if t != msg["forward"]]
+    other = [t for t, _ in sends if t.split() != msg["forward"].split()]
```

- raw red (rc 1; the dropped-newline send read as delivered):

```
F                                                                        [100%]
>           assert out["ok"] is False and out["delivered"] is False
E           assert (True is False)
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_one_character_difference_is_a_mismatch
1 failed in 2.43s
```

- restore: the inverse edit (the two `.split()` forms put back).
- restore receipt (grep after restore): `281:    exact = [results.get(i) for t, i in sends if t == msg["forward"]]` and
  `287:    other = [t for t, _ in sends if t != msg["forward"]]`.
- raw green (rc 0): `1 passed in 1.53s`

## 2 — the success check (`any(r and r[0] for r in exact)`, cloud_relay.py:282)

- axis: a send counts only when its result says `success: true`.
- detector: `T::test_exact_text_refused_by_the_session_is_send_failed`
- neutralization: `any(r and r[0] for r in exact)` -> `any(r for r in exact)` (ignore `success`).
- raw red (rc 1):

```
F                                                                        [100%]
>       assert out["ok"] is False and out["reason"] == "relay-send-failed"
E       assert (True is False)
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_exact_text_refused_by_the_session_is_send_failed
1 failed in 0.65s
```

- restore: the inverse edit. Receipt: `282:    if any(r and r[0] for r in exact):`
- raw green (rc 0): `1 passed in 0.70s`

## 3 — the session filter (`args.get("to") == session`, cloud_relay.py:265)

- axis: only sends addressed to the message's session are read; a send elsewhere is not this
  message's send (here it would read as a text mismatch, i.e. a wrong verdict).
- detector: `T::test_send_to_another_session_is_ignored`
- neutralization: `and args.get("to") == session and when is not None` -> `and when is not None`
  (accept any `to`).
- raw red (rc 1):

```
F                                                                        [100%]
>       assert out["reason"] == "relay-silent"
E       AssertionError: assert 'relay-text-mismatch' == 'relay-silent'
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_send_to_another_session_is_ignored
1 failed in 0.77s
```

- restore: the inverse edit. Receipt: `265:                        and args.get("to") == session and when is not None and when >= after):`
- raw green (rc 0): `1 passed in 0.70s`

## 4 — the time filter (`when >= after`, cloud_relay.py:265)

- axis: only sends stamped at or after the message's `sentAfter` are read; an earlier send (a
  previous message's, or a stale record) never counts for this message.
- detector: `T::test_send_stamped_before_sent_after_is_ignored`
- neutralization: `when is not None and when >= after):` -> `when is not None):` (ignore `sentAfter`).
- raw red (rc 1; an exact send from before `sentAfter` read as delivered):

```
F                                                                        [100%]
>       assert out["reason"] == "relay-silent" and out["delivered"] is False
E       AssertionError: assert (None == 'relay-silent')
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_send_stamped_before_sent_after_is_ignored
1 failed in 0.79s
```

- restore: the inverse edit. Receipt: line 265 as in element 3's receipt.
- raw green (rc 0): `1 passed in 0.74s`

## 5 — the silent outcome (`relay-silent`, cloud_relay.py:294)

- axis: a relay record with no send to the session by the end of the wait is undelivered, never
  delivered by default.
- detector: `T::test_silent_relay_is_reported_after_the_wait`
- neutralization: `return ("relay-silent" if paths else "relay-record-missing"), None` ->
  `return ("delivered" if paths else "relay-record-missing"), None` (an empty record is delivered).
- raw red (rc 1):

```
F                                                                        [100%]
>       assert out["ok"] is False and out["delivered"] is False and out["reason"] == "relay-silent"
E       assert (True is False)
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_silent_relay_is_reported_after_the_wait
1 failed in 0.81s
```

- restore: the inverse edit. Receipt: `294:    return ("relay-silent" if paths else "relay-record-missing"), None`
- raw green (rc 0): `1 passed in 0.87s`

Post-restore `git status --porcelain` after every element: only
`?? plugins/superheroes/lib/cloud_relay.py` and `?? plugins/superheroes/lib/tests/test_cloud_relay.py`.
