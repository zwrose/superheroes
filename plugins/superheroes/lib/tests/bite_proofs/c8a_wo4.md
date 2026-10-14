# C8a WO4 bite-proof — process identity, relay, parked notice, cleanup

**Provenance:** claude write channel (attempts 1 to 3). Run from the worktree root as
`scripts/pinned-python -B -m pytest <node> -q -p no:cacheprovider`. The python warning line
`warning: The UV_NATIVE_TLS environment variable is deprecated ...` opens every capture and is omitted below. A `...` line inside a capture marks traceback lines left out of this record; every other line is as printed.

Git-fixture note: a detector whose fixture makes a git commit (`_init_repo`) cannot run in the implementer's
sandbox (`fatal: failed to write commit object`). Those entries say `Unrunnable here` and carry no captures;
the orchestrator runs red and green from the manifest `/tmp/claude-0/-home-user-superheroes/bd2af963-41b8-5ccb-b3bf-9cbed29d3a97/scratchpad/manifests/wo4.json`.

## Summary

| Element | Axis | Detector | Git fixture | Verdict |
|---|---|---|---|---|
| V464-a | a differing start time reads as a reused pid | `test_launch_ledger.py::test_record_outcome_records_when_the_start_time_differs` | no | proven |
| V464-b | a differing command alone reads as a reused pid | `test_launch_ledger.py::test_record_outcome_records_when_the_command_differs` | no | proven |
| V464-c | an unreadable fresh identity reads as live | `test_launch_ledger.py::test_record_outcome_refuses_when_the_fresh_identity_read_fails_entirely` | no | proven |
| V464-d | the child's birth identity is recorded at spawn | `test_launcher_birth_identity.py::test_the_started_record_carries_the_childs_birth_identity` | no | proven |
| V465a-a | a zone-less relay stamp is skipped, not compared | `test_cloud_relay.py::test_a_send_stamped_without_a_zone_neither_raises_nor_counts_as_delivered` | no | proven |
| V465b-a | a relay name fits the builder's 64-character pattern | `test_cloud_relay.py::test_a_relay_name_fits_the_builders_session_name_pattern` | no | proven |
| V475-a | a send is a message's only by its own header line | `test_cloud_relay.py::test_a_body_that_quotes_another_messages_id_does_not_fool_that_messages_check` | no | proven |
| C7pFU2-a | the lane's recorded account id decides | `test_cloud_parked.py::test_a_lane_with_its_account_id_is_renewed_when_the_advisor_runs_under_an_explicit_default_config_dir` | yes | Unrunnable here |
| C7pFU3-a | a newer park re-arms whatever the stored outcome | `test_cloud_parked.py::test_the_notice_by_stored_outcome_and_whether_the_park_is_newer` | yes | Unrunnable here |
| C7pFU3-b | a resolved park that is not newer gets no renewal text | `test_cloud_parked.py::test_the_notice_by_stored_outcome_and_whether_the_park_is_newer` | yes | Unrunnable here |
| C7pFU4-a | the overlap test confirms the second worker reached the lock | `test_cloud_parked.py::test_two_notices_overlapping_in_time_cannot_both_read_the_state_and_lose_one_pr` | yes | Unrunnable here |
| C7pFU4-b | a readable failed-check marker counts as present | `test_cloud_parked.py::test_a_readable_failed_check_marker_keeps_the_pr_unrenewed` | yes | Unrunnable here |
| C8FU7-a | every weak word is tested for a negation in its own clause | `test_cloud_cleanup_doctrine.py::test_the_reminder_detector_ties_a_negation_to_the_reminder_verb` | no | proven |
| C8FU9-a | the owner message promises a prompt only when the builder has the tool | `test_cloud_cleanup.py::test_the_owner_message_promises_a_prompt_only_when_the_builder_has_the_tool` | no | proven |

---

## V464-a — the start time differs

**guarded element:** `_birth_identity_is_foreign`, `launch_ledger.py`. **axis:** both fields recorded, the
fresh `pidLstart` differs, the command is equal: the recorded pid is not the lane's child, so the outcome records.

**neutralization:** `    return any(fresh[field] != recorded[field] for field in held)` became `    return any(False for field in held)`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_record_outcome_records_when_the_start_time_differs ____________
    def test_record_outcome_records_when_the_start_time_differs(tmp_path, monkeypatch):
        # edge: both recorded, lstart differs -> a reused pid, not live
        repo = _identity_lane(tmp_path, monkeypatch, "l-lstart", _BORN)
        _fake_signal0_alive(monkeypatch)
        _fresh_identity(monkeypatch, dict(_BORN, pidLstart="Tue Oct 13 10:00:00 2026"))
>       assert ll.record_outcome(repo, "l-lstart", "handback", "done")["ok"] is True
E       assert False is True

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_launch_ledger.py:5714: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger.py::test_record_outcome_records_when_the_start_time_differs
1 failed in 3.34s
```

**restore:** the inverse edit.

**restore receipt:** `    return any(fresh[field] != recorded[field] for field in held)`

**raw green:**
```
.                                                                        [100%]
1 passed in 4.06s
```

## V464-b — the command differs alone

**guarded element:** the `any(...)` in `_birth_identity_is_foreign`. **axis:** one differing recorded field
is enough; both need not differ.

**neutralization:** `any(fresh[field] != recorded[field] for field in held)` became `all(...)`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_record_outcome_records_when_the_command_differs _____________
    def test_record_outcome_records_when_the_command_differs(tmp_path, monkeypatch):
        # edge: both recorded, command differs (same start time) -> not live
        repo = _identity_lane(tmp_path, monkeypatch, "l-command", _BORN)
        _fake_signal0_alive(monkeypatch)
        _fresh_identity(monkeypatch, dict(_BORN, pidCommand="vim notes.txt"))
>       assert ll.record_outcome(repo, "l-command", "handback", "done")["ok"] is True
E       assert False is True

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_launch_ledger.py:5723: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger.py::test_record_outcome_records_when_the_command_differs
1 failed in 2.97s
```

**restore:** the inverse edit.

**restore receipt:** `    return any(fresh[field] != recorded[field] for field in held)`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.82s
```

## V464-c — an unreadable fresh read

**guarded element:** the missing-field guard in `_birth_identity_is_foreign`. **axis:** a fresh read that
lacks a recorded field is uncertain, and uncertain reads as live.

**neutralization:** the guard's `        return False` became `        return True`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_record_outcome_refuses_when_the_fresh_identity_read_fails_entirely ____
    def test_record_outcome_refuses_when_the_fresh_identity_read_fails_entirely(tmp_path, monkeypatch):
        # edge: a fresh read that fails entirely -> uncertain, so live
        repo = _identity_lane(tmp_path, monkeypatch, "l-fails", _BORN)
        _fake_signal0_alive(monkeypatch)
        _fresh_identity(monkeypatch, {})
        result = ll.record_outcome(repo, "l-fails", "handback", "done")
>       assert result["ok"] is False and result["reason"] == "terminal-child-live:999999"
E       assert (True is False)

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_launch_ledger.py:5733: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger.py::test_record_outcome_refuses_when_the_fresh_identity_read_fails_entirely
1 failed in 0.97s
```

**restore:** the inverse edit.

**restore receipt:**
```
    if not all(isinstance(fresh.get(field), str) and fresh[field] for field in held):
        return False
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.79s
```

## V464-d — the identity recorded at spawn

**guarded element:** `started.update(ll.read_birth_identity(proc.pid))` in `launcher._spawn_attempt`.
**axis:** the `started` record carries `pidLstart` and `pidCommand` for the spawned child.

**neutralization:** the line became `    ll.read_birth_identity(proc.pid)` (the read still happens; nothing is recorded).

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_the_started_record_carries_the_childs_birth_identity ___________
    ...
        result, started = _spawn_one(tmp_path, monkeypatch)
        assert result["ok"] is True and asked == [424242]
        assert len(started) == 1
        assert started[0]["pid"] == 424242
>       assert started[0]["pidLstart"] == BORN["pidLstart"] and started[0]["pidCommand"] == BORN["pidCommand"]
               ^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'pidLstart'

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_launcher_birth_identity.py:90: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_birth_identity.py::test_the_started_record_carries_the_childs_birth_identity
1 failed in 1.34s
```
(The first neutralization tried, `started.update({})`, also went red, on the earlier `asked == [424242]` assertion; the read-kept form above makes the red land on the recorded field.)

**restore:** the inverse edit.

**restore receipt:** `    started.update(ll.read_birth_identity(proc.pid))`

**raw green:**
```
.                                                                        [100%]
1 passed in 1.39s
```

## V465a-a — a relay stamp with no zone

**guarded element:** the `tzinfo` check in `cloud_relay._time`. **axis:** a stamp without a zone reads as
`None`, so `_sends` skips it instead of comparing it with the aware `sentAfter`.

**neutralization:** `    return when if when.tzinfo is not None else None` became `    return when`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_send_stamped_without_a_zone_neither_raises_nor_counts_as_delivered ___
    ...
cloud_relay.py:300: in _sends
E                           TypeError: can't compare offset-naive and offset-aware datetimes
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_stamped_without_a_zone_neither_raises_nor_counts_as_delivered
1 failed in 0.34s
```
(The full traceback runs through `_check` and `cloud_relay.check`, `_decide` and `_sends`; elided here to its last frame.)

**restore:** the inverse edit.

**restore receipt:** `    return when if when.tzinfo is not None else None`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.25s
```

## V465b-a — the relay name cut

**guarded element:** `base = base[:room]` in `cloud_relay.relay_name`. **axis:** every relay name matches
`engine_adapter._CLOUD_SESSION_NAME_RE` by `fullmatch` (at most 64 characters).

**neutralization:** `    base = base[:room]` became `    base = base`.

**raw red:**
```
F.FF                                                                     [100%]
E       AssertionError: assert None
E        +  where None = <built-in method fullmatch of re.Pattern object at 0x7ff8d14e3100>('superheroes-relay-aaaa...aaaa-57dfb408')
E        +      where re.compile('[A-Za-z0-9._-]{1,64}') = engine_adapter._CLOUD_SESSION_NAME_RE
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_relay_name_fits_the_builders_session_name_pattern[aaaa...(200)]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_relay_name_fits_the_builders_session_name_pattern[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_relay_name_fits_the_builders_session_name_pattern[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
3 failed, 1 passed in 0.29s
```
(The 200-character name is shortened with `...` inside this record; the run printed it in full. The 200-character case, and the 46- and 47-character cases just over the room left, go red; the spaces-and-unicode case passes because the sanitizer alone fits it.)

**restore:** the inverse edit.

**restore receipt:** `    base = base[:room]`

**raw green:**
```
....                                                                     [100%]
4 passed in 0.26s
```

## V475-a — attribution by the quoted id

**guarded element:** the header-prefix filter in `cloud_relay._decide`. **axis:** a send that merely quotes
another message's id is not that message's send.

**neutralization:** `    sends = [(t, i) for t, i in sends if t.lstrip().startswith(header)]` became
`    sends = [(t, i) for t, i in sends if "(id %s)" % msg["msgId"] in t]` (the substring attribution).

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_body_that_quotes_another_messages_id_does_not_fool_that_messages_check _
    ...
        out, _ = _check(world, b["msgId"], wait=4, interval=2)
>       assert out["delivered"] is False and out["reason"] == "relay-silent"
E       AssertionError: assert (False is False and 'relay-text-mismatch' == 'relay-silent'
E         - relay-silent
E         + relay-text-mismatch)

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_cloud_relay.py:348: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_body_that_quotes_another_messages_id_does_not_fool_that_messages_check
1 failed in 0.36s
```

**restore:** the inverse edit.

**restore receipt:** `    sends = [(t, i) for t, i in sends if t.lstrip().startswith(header)]`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

## C7pFU2-a — `_lapses` ignores `accountId`

**guarded element:** the `account_id` branch in `cloud_parked._lapses`. **axis:** the lane's recorded account
id decides which account's pass record applies, whatever config path the advisor runs under.

**neutralization:** `    if isinstance(account_id, str) and account_id:` became `    if False:`.

**detector:** `test_cloud_parked.py::test_a_lane_with_its_account_id_is_renewed_when_the_advisor_runs_under_an_explicit_default_config_dir`.
Git fixture (`_init_repo`). Unrunnable here — the orchestrator runs red and green outside the sandbox.

## C7pFU3-a — re-arm on a newer park

**guarded element:** the `if known:` re-arm gate in `cloud_parked.notice`. **axis:** a newer park re-arms
whatever the stored outcome, including `closed`.

**neutralization:** `    if known:` (before `seen = known[0].get(_PARK_KEY)`) became
`    if known and known[0]["outcome"] in (None, "sent-back", UNCERTAIN, "owner-let-through"):`, the old set.

**detector:** `test_cloud_parked.py::test_the_notice_by_stored_outcome_and_whether_the_park_is_newer`
(the `closed`, newer case goes red). Git fixture. Unrunnable here — the orchestrator runs red and green outside the sandbox.

## C7pFU3-b — no renewal text for a resolved park

**guarded element:** the `park-resolved` return in `cloud_parked.notice`. **axis:** a resolved park that is
not newer returns `text: None`.

**neutralization:** `"text": None` became `"text": NOTICE_TEXT % pr` on that return.

**detector:** the same table test (the `closed` and `owner-let-through` not-newer cases go red). Git fixture.
Unrunnable here — the orchestrator runs red and green outside the sandbox.

## C7pFU4-a — the overlap test confirms the lock was reached

**guarded element:** the `reached_lock` wrapper in `_watch_lock`, `test_cloud_parked.py`. **axis:** the
second worker is seen to reach `file_lock.acquire` before the test asserts it is blocked.

**neutralization (in the test helper):** `            reached_lock.set()` became `            pass`, so the event never sets and
`assert reached_lock.wait(10), ...` fails on the reached-assertion after its 10 s wait.

**detector:** `test_cloud_parked.py::test_two_notices_overlapping_in_time_cannot_both_read_the_state_and_lose_one_pr`.
Git fixture. Unrunnable here — the orchestrator runs red and green outside the sandbox.
The sibling overlap test `test_a_sent_overlapping_a_state_writing_send_back_keeps_the_sent_back_outcome` uses the same helper, so the same neutralization reaches it; the manifest names the first test.

## C7pFU4-b — a readable failed-check marker

**guarded element:** `read_failed_check(...) is not None` in `cloud_parked._lapses`. **axis:** a well-formed
marker counts as present, not only a damaged one.

**neutralization:** `    if account and _sib("cloud_check").read_failed_check(repo_root, account) is not None:` became `    if account and False:`.

**detector:** `test_cloud_parked.py::test_a_readable_failed_check_marker_keeps_the_pr_unrenewed`. Git fixture.
Unrunnable here — the orchestrator runs red and green outside the sandbox.

## C8FU7-a — weak words and the clause

**guarded element:** the weak-word loop in `_reminder_hits`, `test_cloud_cleanup_doctrine.py`. **axis:** a
negation hides a weak word only when it stands earlier in the same clause, and every weak word is tested.

**neutralization:** the `any(not _negated_in_clause(...) for m in _WEAK_WORDS.finditer(line))` test became the
old first-match, anywhere-earlier suppression: `weak = _WEAK_WORDS.search(line)` and
`if weak and not re.search(r"\b(?:nothing|never|no|not)\b", line[: weak.start()], re.IGNORECASE):`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_the_reminder_detector_ties_a_negation_to_the_reminder_verb ________
        # a negation sitting in an earlier clause does not govern a later weak word
>       assert _reminder_hits(["If the owner has not answered the archive prompt, ask again."])
E       AssertionError: assert []
E        +  where [] = _reminder_hits(['If the owner has not answered the archive prompt, ask again.'])

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py:106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py::test_the_reminder_detector_ties_a_negation_to_the_reminder_verb
1 failed in 0.15s
```

**restore:** the inverse edit.

**restore receipt:** `        if any(not _negated_in_clause(line, m.start()) for m in _WEAK_WORDS.finditer(line)):`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.12s
```

## C8FU9-a — the owner message sentence

**guarded element:** the conditional sentence in `cloud_cleanup.OWNER_MESSAGE_MERGED`. **axis:** the
message promises a prompt only if the builder's session has the archive tool.

**neutralization:** the second, third and fourth string pieces of `OWNER_MESSAGE_MERGED` became the old
`"You'll get one prompt for it: tap Allow once."`.

**raw red:**
```
F.                                                                       [100%]
=================================== FAILURES ===================================
_ test_the_owner_message_promises_a_prompt_only_when_the_builder_has_the_tool[merged] _
message = "#%d is merged. I've asked its cloud builder to archive itself. You'll get one prompt for it: tap Allow once."
>       assert _CONDITIONAL_PROMPT in message
E       assert "If its session has a tool to archive itself, you'll get one prompt for it: tap Allow once. If it has none, it will say so on its issue, and the session stays listed until you archive it by hand." in "#%d is merged. I've asked its cloud builder to archive itself. You'll get one prompt for it: tap Allow once."

/home/user/c8a-wo4/plugins/superheroes/lib/tests/test_cloud_cleanup.py:995: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_the_owner_message_promises_a_prompt_only_when_the_builder_has_the_tool[merged]
1 failed, 1 passed in 1.05s
```

**restore:** the inverse edit.

**restore receipt:**
```
OWNER_MESSAGE_MERGED = ("#%d is merged. I've asked its cloud builder to archive itself. "
                        "If its session has a tool to archive itself, you'll get one prompt for it: tap Allow once. "
                        "If it has none, it will say so on its issue, and the session stays listed "
                        "until you archive it by hand.")
```

**raw green:**
```
..                                                                       [100%]
2 passed in 1.89s
```
