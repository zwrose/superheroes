# #2272 WO1 bite-proofs — the account-limit reading (`cloud_relay.account_limit`, `check`, the wave watch)

Detector file: `plugins/superheroes/lib/tests/test_i2272_account_limit.py`. Nine guarded elements, one neutralization
each, applied to production code only and undone by the inverse edit (never `git checkout`/`restore`/`stash`).
Every command is the detector alone as one test node, run as:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "<node>" -q -p no:randomly
```

Captures are the runner's output with these edits, all marked in the text: the shell's `UV_NATIVE_TLS` deprecation
warning line (printed first on every run) is dropped; in each red, the `world = namespace(...)`/`repo = ...` fixture
lines are replaced by `...`, and ephemeral temp paths inside `configDir` values are shortened to `.../.claude-two`;
the traceback's file path is shortened to `test_i2272_account_limit.py`. Nothing else is cut or redacted (no secrets
or tokens are involved). A post-restore `grep -n` of the restored line is the restore receipt for each element.

---

## (a) `isApiErrorMessage is True` — `cloud_relay.py` `_limit_record`

**Axis:** only a line the host marks as an API error is a limit record.

**Neutralization:** `if rec.get("type") != "assistant" or rec.get("isApiErrorMessage") is not True:` became `if rec.get("type") != "assistant":`.

**Node:** `test_i2272_account_limit.py::test_a_line_the_host_does_not_mark_as_an_api_error_is_no_reading`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_line_the_host_does_not_mark_as_an_api_error_is_no_reading _______
...
    def test_a_line_the_host_does_not_mark_as_an_api_error_is_no_reading(world):
        for value in (False, _GONE, "true", 1, None):
            rec = _limit(lambda r: r.pop("isApiErrorMessage") if value is _GONE else r.update(isApiErrorMessage=value))
>           assert _no_reading(_read(world, rec)), value
E           AssertionError: False
E           assert False
E            +  where False = _no_reading({'ok': True, 'limited': True, 'configDir': '.../.claude-two', 'relay': 'superheroes-relay-claude-two-e14a74ea', ...})
...
test_i2272_account_limit.py:135: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_line_the_host_does_not_mark_as_an_api_error_is_no_reading
1 failed in 0.88s
```

**Restore:** inverse edit.
**Restore receipt:** `353:    if rec.get("type") != "assistant" or rec.get("isApiErrorMessage") is not True:`

**Green:**
```
.                                                                        [100%]
1 passed in 6.46s
```

---

## (b) the `apiError` / `error` + `status` requirement — `cloud_relay.py` `_limit_record`

**Axis:** a line is a limit only when `apiError == "usage_limit_reached"`, or `error == "rate_limit"` with the info's `status == "rejected"`.

**Neutralization:** `if not (rec.get("apiError") == "usage_limit_reached"` became `if False and not (rec.get("apiError") == "usage_limit_reached"`.

**Node:** `test_i2272_account_limit.py::test_a_line_that_is_neither_the_usage_limit_error_nor_a_rejected_rate_limit_is_no_reading`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_line_that_is_neither_the_usage_limit_error_nor_a_rejected_rate_limit_is_no_reading _
...
    def test_a_line_that_is_neither_the_usage_limit_error_nor_a_rejected_rate_limit_is_no_reading(world):
        other_error = _limit(lambda r: r.update(apiError="overloaded", error="server_error"))
>       assert _no_reading(_read(world, other_error))
E       AssertionError: assert False
E        +  where False = _no_reading({'ok': True, 'limited': True, 'configDir': '.../.claude-two', 'relay': 'superheroes-relay-claude-two-498bbb8b', ...})
...
test_i2272_account_limit.py:141: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_line_that_is_neither_the_usage_limit_error_nor_a_rejected_rate_limit_is_no_reading
1 failed in 0.73s
```

**Restore:** inverse edit.
**Restore receipt:** `361:    if not (rec.get("apiError") == "usage_limit_reached"`

**Green:**
```
.                                                                        [100%]
1 passed in 1.23s
```

---

## (c) the numeric `resetsAt` requirement — `cloud_relay.py` `_usable_reset`

**Axis:** a reset time must be a finite number above 0, not a bool, or the line is no reading.

**Neutralization:** the two-line `return (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0)` became `return "resetsAt" in info`.

**Node:** `test_i2272_account_limit.py::test_a_reset_time_that_is_not_a_finite_positive_number_is_no_reading[nan]`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_reset_time_that_is_not_a_finite_positive_number_is_no_reading[nan] ___
...
value = nan

    @pytest.mark.parametrize("value", [_GONE, "1793566800", True, False, -5, 0, float("nan"),
                                       float("inf"), None, [1793566800]])
    def test_a_reset_time_that_is_not_a_finite_positive_number_is_no_reading(world, value):
>       assert _no_reading(_read(world, _limit(lambda r: _both(r, "resetsAt", value))))
E       AssertionError: assert False
E        +  where False = _no_reading({'ok': True, 'limited': False, 'configDir': '.../.claude-two', 'relay': 'superheroes-relay-claude-two-f4d07148', ...})
...
test_i2272_account_limit.py:159: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_reset_time_that_is_not_a_finite_positive_number_is_no_reading[nan]
1 failed in 1.48s
```

**Restore:** inverse edit.
**Restore receipt:**
```
345:    return (isinstance(value, (int, float)) and not isinstance(value, bool)
346-            and math.isfinite(value) and value > 0)
```

**Green:**
```
.                                                                        [100%]
1 passed in 4.84s
```

---

## (c2) the account-wide `rateLimitType` allowlist — `cloud_relay.py` `_limit_record`

**Axis:** only `five_hour` and `seven_day` (`ACCOUNT_WIDE_LIMIT_TYPES`) prove every builder on the account cannot run; a missing, unknown or model-scoped type is no reading.

**Neutralization:** `if limit_type not in ACCOUNT_WIDE_LIMIT_TYPES:` became `if False and limit_type not in ACCOUNT_WIDE_LIMIT_TYPES:`.

**Node:** `test_i2272_account_limit.py::test_a_limit_type_that_is_not_account_wide_is_no_reading[seven_day_opus]`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_limit_type_that_is_not_account_wide_is_no_reading[seven_day_opus] ___
...
value = 'seven_day_opus'

    @pytest.mark.parametrize("value", [_GONE, "seven_day_opus", "seven_day_sonnet", "weekly", "", None, 7])
    def test_a_limit_type_that_is_not_account_wide_is_no_reading(world, value):
>       assert _no_reading(_read(world, _limit(lambda r: _both(r, "rateLimitType", value))))
E       AssertionError: assert False
E        +  where False = _no_reading({'ok': True, 'limited': True, 'configDir': '.../.claude-two', 'relay': 'superheroes-relay-claude-two-9bc814cc', ...})
...
test_i2272_account_limit.py:169: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_limit_type_that_is_not_account_wide_is_no_reading[seven_day_opus]
1 failed in 1.07s
```

**Restore:** inverse edit.
**Restore receipt:** `366:    if limit_type not in ACCOUNT_WIDE_LIMIT_TYPES:`

**Green:**
```
.                                                                        [100%]
1 passed in 0.79s
```

---

## (d) the `now < resetsAt` comparison — `cloud_relay.py` `account_limit`

**Axis:** the limit holds only before its reset time.

**Neutralization:** `out["limited"] = not answered and now < resets_at` became `out["limited"] = not answered`.

**Node:** `test_i2272_account_limit.py::test_at_or_after_its_reset_the_limit_no_longer_holds_but_is_still_reported`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_at_or_after_its_reset_the_limit_no_longer_holds_but_is_still_reported __
...
    def test_at_or_after_its_reset_the_limit_no_longer_holds_but_is_still_reported(world):
        for now in (RESETS_AT, RESETS_AT + 1):
            out = _read(world, LIMIT_LINE, now=now)
>           assert out["ok"] is True and out["limited"] is False
E           assert (True is True and True is False)

test_i2272_account_limit.py:89: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_at_or_after_its_reset_the_limit_no_longer_holds_but_is_still_reported
1 failed in 1.06s
```

**Restore:** inverse edit.
**Restore receipt:** `412:    out["limited"] = not answered and now < resets_at`

**Green:**
```
.                                                                        [100%]
1 passed in 0.88s
```

---

## (e) the later-reply clearance — `cloud_relay.py` `account_limit`

**Axis:** an assistant reply strictly later than the newest limit record means the limit no longer holds.

**Neutralization:** `out["limited"] = not answered and now < resets_at` became `out["limited"] = now < resets_at`.

**Node:** `test_i2272_account_limit.py::test_a_later_reply_from_the_account_clears_the_limit_but_it_is_still_reported`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_later_reply_from_the_account_clears_the_limit_but_it_is_still_reported _
...
    def test_a_later_reply_from_the_account_clears_the_limit_but_it_is_still_reported(world):
        out = _read(world, LIMIT_LINE, _reply("2026-10-30T09:41:00.000Z"))
>       assert out["ok"] is True and out["limited"] is False
E       assert (True is True and True is False)

test_i2272_account_limit.py:96: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_later_reply_from_the_account_clears_the_limit_but_it_is_still_reported
1 failed in 1.04s
```

**Restore:** inverse edit.
**Restore receipt:** `412:    out["limited"] = not answered and now < resets_at`

**Green:**
```
.                                                                        [100%]
1 passed in 3.33s
```

---

## (f) `check`'s switch from `relay-silent` to `account-limited` — `cloud_relay.py` `check`

**Axis:** a silent relay on an account at its usage limit reads `account-limited`.

**Neutralization:** `if verdict == "relay-silent":` (the limit-reading branch) became `if False and verdict == "relay-silent":`.

**Node:** `test_i2272_account_limit.py::test_a_silent_relay_on_a_limited_account_reads_account_limited`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_a_silent_relay_on_a_limited_account_reads_account_limited ________
...
    def test_a_silent_relay_on_a_limited_account_reads_account_limited(world):
        msg = _composed(world)
        _write_record(world, [json.loads(LIMIT_LINE)])
        out = _check_at(world, msg["msgId"], BEFORE_RESET)
        assert out["ok"] is False and out["delivered"] is False
>       assert out["reason"] == "account-limited"
E       AssertionError: assert 'relay-silent' == 'account-limited'
E         
E         - account-limited
E         + relay-silent

test_i2272_account_limit.py:267: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_silent_relay_on_a_limited_account_reads_account_limited
1 failed in 0.76s
```

**Restore:** inverse edit.
**Restore receipt:** `585:    if verdict == "relay-silent":`

**Green:**
```
.                                                                        [100%]
1 passed in 0.82s
```

---

## (g) the watch dropping a limited account's lanes from `lane-stale` — `wave_watch.py` `_evaluate_tick`

**Axis:** while the limit holds, no lane on the limited account is reported stale.

**Neutralization:** `entry["launchId"] not in limited_lanes` became `entry["launchId"] not in ()` in the stale-cloud filter.

**Node:** `test_i2272_account_limit.py::test_a_lane_on_a_limited_account_is_not_lane_stale_while_the_limit_holds`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_lane_on_a_limited_account_is_not_lane_stale_while_the_limit_holds ___
...
    def test_a_lane_on_a_limited_account_is_not_lane_stale_while_the_limit_holds(repo, tmp_path):
        _wave(repo, tmp_path)
        ignore = (("cloud-a1", "account-limited"), ("cloud-a2", "account-limited"))
        result = ww.run(repo, _BATCH, gh_run=_quiet_gh(101, 102, 201), ignore_events=ignore)
        assert result["event"] == "lane-stale"
>       assert _stale_ids(result) == ["cloud-b1"]
E       AssertionError: assert ['cloud-a1', ...', 'cloud-b1'] == ['cloud-b1']
E         
E         At index 0 diff: 'cloud-a1' != 'cloud-b1'
E         Left contains 2 more items, first extra item: 'cloud-a2'
E         Use -v to get more diff

test_i2272_account_limit.py:381: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_a_lane_on_a_limited_account_is_not_lane_stale_while_the_limit_holds
1 failed in 1.30s
```

**Restore:** inverse edit.
**Restore receipt:** `3059:            entry for entry in stale_cloud_launches if entry["launchId"] not in limited_lanes`

**Green:**
```
.                                                                        [100%]
1 passed in 1.13s
```

---

## (h) the watch's per-lane suppression — `wave_watch.py` `_payload_account_limited`

**Axis:** `(launchId, "account-limited")` in the ignore set removes that lane from the event, and an event with no surviving lane is not raised.

**Neutralization:** `if (lid, EVENT_ACCOUNT_LIMITED) not in ctx["ignore_set"]` became `if True or (lid, EVENT_ACCOUNT_LIMITED) not in ctx["ignore_set"]`.

**Node:** `test_i2272_account_limit.py::test_ignoring_every_named_lane_suppresses_the_event_and_one_lane_leaves_the_rest`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_ignoring_every_named_lane_suppresses_the_event_and_one_lane_leaves_the_rest _
...
    def test_ignoring_every_named_lane_suppresses_the_event_and_one_lane_leaves_the_rest(repo, tmp_path):
        _wave(repo, tmp_path)
        gh = _quiet_gh(101, 102, 201)
        one = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(("cloud-a1", "account-limited"),))
        assert one["event"] == "account-limited"
>       assert one["launchIds"] == ["cloud-a2"] and one["launchId"] == "cloud-a2"
E       AssertionError: assert (['cloud-a1', 'cloud-a2'] == ['cloud-a2']
E         
E         At index 0 diff: 'cloud-a1' != 'cloud-a2'
E         Left contains one more item: 'cloud-a2'
E         Use -v to get more diff)

test_i2272_account_limit.py:396: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_account_limit.py::test_ignoring_every_named_lane_suppresses_the_event_and_one_lane_leaves_the_rest
1 failed in 1.05s
```

**Restore:** inverse edit.
**Restore receipt:** `2500:            if (lid, EVENT_ACCOUNT_LIMITED) not in ctx["ignore_set"]`

**Green:**
```
.                                                                        [100%]
1 passed in 1.12s
```

---

## BP10 — a closed fix-order lane is not reported account-limited (`test_wave_watch_fix_order.py::test_row2_a_closed_lane_on_a_limited_account_is_not_reported_account_limited`)

**Neutralization:** in `wave_watch.py` `_evaluate_tick`, the limited-accounts filter `if lid not in closed` changed to `if lid not in ()`.

**Red:**
```
>       assert ww.run(repo, _BATCH, gh_run=gh)["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'account-limited' == 'timer'
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row2_a_closed_lane_on_a_limited_account_is_not_reported_account_limited
1 failed in 0.99s
```

**Restore:** inverse edit; the node passes.

---

All nine neutralizations were restored; the final scoped run after the last restore (989 passed, 3 skipped) is in the dispatch return.
