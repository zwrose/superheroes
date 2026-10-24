# Bite-proof record: WO-F (#2099 fix leg, vet 622 finding 2) a header-dropped relay send is sent but altered

Detector under proof: the tests added in `plugins/superheroes/lib/tests/test_cloud_relay.py`
(`test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered` and its siblings).
Guarded code: `plugins/superheroes/lib/cloud_relay.py` (`_decide`, `_say`). Base: `ddb34ef4`.
Every neutralization was a targeted Edit, undone by the inverse Edit before the next element. No
`git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-wo-f -m pytest <exact node ids> -q -p no:cacheprovider`.
Nothing in the captures was redacted; each is under 32 KiB. Detectors were not edited between red and green.

Declared guarded-element set (from the order): F1 header-dropped attribution, F2 delivered outranks
header-dropped, F3 provisional while waiting, F4 never delivered. One element beyond the declared set was
also proven: F5 the non-empty-body guard (the order's fail-closed edge "an empty body cannot be header-dropped").

The fixture shape is the recorded relay message `817905576fcf`: a send to the right session, stamped
after `sentAfter`, whose text is `forward` with its header line dropped, with a `success: true` result.

## F1 header-dropped attribution

- **Guarded element:** `cloud_relay.py` `_decide`, the `dropped = [...]` line (the `# axis:` line above it).
  Axis: a send of exactly this message's body, header dropped, is attributed to the message (read as
  `relay-text-mismatch`, `headerDropped`), not ignored as foreign.
- **Neutralization:** replaced `dropped = [(t, i) for t, i in sends if body and t.lstrip() == body]` with `dropped = []`.
- **Raw red** (both parameters of the recorded-shape test, by node id):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bare] _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-3/test_a_send_with_the_header_dr0/repo', config='/tmp/claude-0/pyt...test_a_send_with_the_header_dr0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)
to = 'builder-1748'

    @pytest.mark.parametrize("to", [SESSION, SESSION + " [8af960]"], ids=["bare", "bracketed"])
    def test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered(world, to):
        # axis: header-dropped attribution — a send of exactly the forward text minus its header line is this message sent altered, never delivered — a send the header rule drops as foreign makes it read silent
        # The recorded shape of relay message 817905576fcf: right session, success true, header line gone.
        msg = _composed(world)
        _write_record(world, _send_lines("toolu_1", to, _header_dropped(msg), STAMP))
        out, clock = _check(world, msg["msgId"], wait=4, interval=2)
        assert out["ok"] is False and out["delivered"] is False
>       assert out["reason"] == "relay-text-mismatch" and out["headerDropped"] is True
E       AssertionError: assert ('relay-silent' == 'relay-text-mismatch'
E         
E         - relay-text-mismatch
E         + relay-silent)

/home/user/wt-2099-f/plugins/superheroes/lib/tests/test_cloud_relay.py:493: AssertionError
_ test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bracketed] _

[... the same test body and traceback as [bare], with to = 'builder-1748 [8af960]' and ending in the same
AssertionError (`'relay-silent' == 'relay-text-mismatch'`); elided here, about 1.3 KiB ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bare]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bracketed]
2 failed in 0.91s
```

  The red is on the axis: the dropped-header send reads `relay-silent` (it was sent, so silent is the wrong verdict).
- **Restore:** inverse Edit, `dropped = []` back to the list comprehension.
- **Restore receipt:** restored line (cloud_relay.py:339):
  `    dropped = [(t, i) for t, i in sends if body and t.lstrip() == body]`. Final `git diff` of the file is checked below.
- **Raw green** (same two node ids):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 1.74s
```

## F2 delivered outranks header-dropped

- **Guarded element:** `cloud_relay.py` `_decide`, the `delivered` check placed before the header-dropped
  check. Axis: an exact successful send reads `delivered` even when a header-dropped send of the same body is
  also in the record (another pending message with the same body may have produced it).
- **Neutralization:** moved the header-dropped check before the `delivered` check: directly before
  `    if any(r and r[0] for r in exact):` inserted
  `    if final and dropped:\n        return "relay-text-mismatch", {"firstDifference": _first_difference(msg["forward"], dropped[0][0]),\n                                       "headerDropped": True}`.
  The test reads B with `wait=0` so the end of the wait is reached at once; with a longer wait the
  check is not final on the first read and `delivered` wins anyway, so only `wait=0` discriminates this move.
- **Raw red** (node `test_a_header_dropped_send_for_another_pending_message_with_the_same_body_does_not_spoil_delivery`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_header_dropped_send_for_another_pending_message_with_the_same_body_does_not_spoil_delivery _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-5/test_a_header_dropped_send_for0/repo', config='/tmp/claude-0/pyt...test_a_header_dropped_send_for0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_header_dropped_send_for_another_pending_message_with_the_same_body_does_not_spoil_delivery(world):
        # axis: delivered outranks header-dropped — another message's header-dropped send of the same body never blocks an exact success — a header-dropped check ahead of the delivered check makes it fail
        _ensure_alive(world)
        a = _compose(world)
        b = _compose(world)
        for msg in (a, b):
            _backdate(world, msg["msgId"], BEFORE)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, _header_dropped(a), STAMP),
                      _send_lines("toolu_2", SESSION, b["forward"], "2026-10-12T10:00:01.000Z"))
        out, _ = _check(world, b["msgId"], wait=0)
>       assert out["delivered"] is True and out["reason"] is None and "headerDropped" not in out
E       assert (False is True)

/home/user/wt-2099-f/plugins/superheroes/lib/tests/test_cloud_relay.py:556: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_header_dropped_send_for_another_pending_message_with_the_same_body_does_not_spoil_delivery
1 failed in 0.75s
```

- **Restore:** inverse Edit, removed the inserted three lines.
- **Restore receipt:** restored lines (cloud_relay.py:345-347):
  `    exact = [results.get(i) for t, i in sends if t == msg["forward"]]` / `    if any(r and r[0] for r in exact):` / `        return "delivered", None`.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.35s
```

## F3 provisional while the wait runs

- **Guarded element:** `cloud_relay.py` `_decide`, the header-dropped verdict placed after `if not final: return None, None`.
  Axis: a header-dropped send is provisional while the wait runs (an exact retry's success may still be recorded).
- **Neutralization:** returned the header-dropped mismatch before the `final` check: directly before
  `    if not final:` inserted
  `    if dropped:\n        return "relay-text-mismatch", {"firstDifference": _first_difference(msg["forward"], dropped[0][0]),\n                                       "headerDropped": True}`.
- **Raw red** (node `test_a_header_dropped_send_is_provisional_while_a_retry_may_still_arrive`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_header_dropped_send_is_provisional_while_a_retry_may_still_arrive ___

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-7/test_a_header_dropped_send_is_0/repo', config='/tmp/claude-0/pyt...test_a_header_dropped_send_is_0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_header_dropped_send_is_provisional_while_a_retry_may_still_arrive(world):
        # axis: header-dropped is provisional during the wait — an exact retry success landing mid-wait is delivered — a header-dropped verdict returned early makes it fail
        msg = _composed(world)
        dropped = _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP)
        _write_record(world, dropped)
        clock = Clock()
    
        def sleep(seconds):
            clock.sleep(seconds)
            _write_record(world, dropped, _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))
    
        out = cr.check(world.repo, msg["msgId"], wait=30, interval=2, env=world.env,
                       clock=clock, sleep=sleep)
>       assert out["delivered"] is True and out["reason"] is None and clock.t == 2
E       assert (False is True)

/home/user/wt-2099-f/plugins/superheroes/lib/tests/test_cloud_relay.py:541: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_header_dropped_send_is_provisional_while_a_retry_may_still_arrive
1 failed in 0.31s
```

- **Restore:** inverse Edit, removed the inserted three lines.
- **Restore receipt:** restored lines (cloud_relay.py:349-353): `    if not final:` / `        return None, None` /
  `    if dropped:` / `        return "relay-text-mismatch", {"firstDifference": _first_difference(msg["forward"], dropped[0][0]),` /
  `                                       "headerDropped": True}`.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.29s
```

## F4 never delivered

- **Guarded element:** `cloud_relay.py` `_decide`, the `delivered` check reading only exact sends (`exact`),
  never header-dropped ones. Axis: a header-dropped send with `success: true` is never `delivered`.
- **Neutralization:** directly before `    if any(r and r[0] for r in exact):` inserted
  `    exact += [results.get(i) for _, i in dropped]`, so a header-dropped send's success result counts as delivery.
- **Raw red** (both parameters of the recorded-shape test, by node id):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bare] _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-10/test_a_send_with_the_header_dr0/repo', config='/tmp/claude-0/py...test_a_send_with_the_header_dr0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)
to = 'builder-1748'

    @pytest.mark.parametrize("to", [SESSION, SESSION + " [8af960]"], ids=["bare", "bracketed"])
    def test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered(world, to):
        # axis: header-dropped attribution — a send of exactly the forward text minus its header line is this message sent altered, never delivered — a send the header rule drops as foreign makes it read silent
        # The recorded shape of relay message 817905576fcf: right session, success true, header line gone.
        msg = _composed(world)
        _write_record(world, _send_lines("toolu_1", to, _header_dropped(msg), STAMP))
        out, clock = _check(world, msg["msgId"], wait=4, interval=2)
>       assert out["ok"] is False and out["delivered"] is False
E       assert (True is False)

/home/user/wt-2099-f/plugins/superheroes/lib/tests/test_cloud_relay.py:492: AssertionError
_ test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bracketed] _

[... the same test body and traceback as [bare], with to = 'builder-1748 [8af960]' and ending in the same
AssertionError (`assert (True is False)`); elided here, about 1.3 KiB ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bare]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_with_the_header_dropped_is_a_mismatch_not_silent_or_delivered[bracketed]
2 failed in 0.40s
```

  The red is on the axis: the header-dropped send with `success: true` reads `delivered` (`ok` True).
- **Restore:** inverse Edit, removed the inserted `exact += ...` line.
- **Restore receipt:** restored lines (cloud_relay.py:345-347) as in F2's receipt.
- **Raw green** (same two node ids):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.47s
```

## F5 (beyond the declared set) non-empty body

- **Guarded element:** `cloud_relay.py` `_decide`, the `body and` guard in the `dropped = [...]` line.
  Axis: an empty body cannot be header-dropped, so an empty or blank send is not attributed to the message.
- **Neutralization:** replaced `if body and t.lstrip() == body]` with `if t.lstrip() == body]`.
- **Raw red** (node `test_an_empty_body_is_never_a_header_dropped_send`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_an_empty_body_is_never_a_header_dropped_send _______________

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-14/test_an_empty_body_is_never_a_0/repo', config='/tmp/claude-0/py...test_an_empty_body_is_never_a_0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_an_empty_body_is_never_a_header_dropped_send(world):
        # axis: header-dropped needs a non-empty body — an empty or blank send is not this message sent altered — an unguarded empty match makes it fail
        msg = _composed(world)
        state = json.load(open(_state_file(world)))
        state["pending"][msg["msgId"]]["forward"] = cr.FORWARD_HEADER % msg["msgId"]
        json.dump(state, open(_state_file(world), "w"))
        _write_record(world, _send_lines("toolu_1", SESSION, "", STAMP),
                      _send_lines("toolu_2", SESSION, " \n\n ", STAMP))
        out, _ = _check(world, msg["msgId"], wait=4, interval=2)
>       assert out["reason"] == "relay-silent" and out["delivered"] is False
E       AssertionError: assert ('relay-text-mismatch' == 'relay-silent'
E         
E         - relay-silent
E         + relay-text-mismatch)

/home/user/wt-2099-f/plugins/superheroes/lib/tests/test_cloud_relay.py:615: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_an_empty_body_is_never_a_header_dropped_send
1 failed in 0.39s
```

- **Restore:** inverse Edit, `if body and t.lstrip() == body]` put back.
- **Restore receipt:** restored line (cloud_relay.py:339) as quoted in F1's receipt.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.41s
```

## Not neutralized (no separate proof run)

Tests in this change whose guarded behavior is not in the declared set F1-F4 and was not neutralized by
itself: the leading-whitespace test (`lstrip` on the sent text), the exactness cases of test 3 (different body,
one character changed, body minus last, body plus one), the header-carrying-altered-first test, the
result-independence cases (`failed`, `no-result`, `success`), the stamped-before-`sentAfter` and
other-session tests, and the `_say` wording. They pass on the final head; their protection is unproven by this record.

## Final head

`git diff plugins/superheroes/lib/cloud_relay.py` after the last restore showed exactly the intended change:
the `_decide` docstring paragraph, the `body` and `dropped` lines with the one `# axis:` comment, the
`if dropped:` return after `if not final:`, and the `headerDropped` branch at the top of `_say`'s failure
wording. No neutralization line remained. The scoped suite (`test_cloud_relay.py` and
`test_c8c_relay_doctrine.py`) on that head: `103 passed in 3.92s` (87 passed before the change).

## G1 header-dropped outranks failed and unconfirmed exact sends

Work order WO-G (review finding test-001 on PR #2101). Base: `3c4b0333`. Command prefix (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-wo-g -m pytest <exact node ids> -q -p no:cacheprovider`.
The neutralization was a targeted Edit, undone by the inverse Edit. No `git checkout`, `restore`, `reset` or
`stash` was used. Nothing in the captures was redacted; each is under 32 KiB. The detector was not edited
between red and green.

- **Guarded element:** `cloud_relay.py` `_decide`, the `if dropped:` block placed before the unconfirmed and
  failed checks. Detector: `test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result`
  (cases `failed` and `no-result`). Axis: at the end of the wait a header-dropped send outranks an exact send
  that failed or has no result, so the verdict is `relay-text-mismatch` with `headerDropped` True and never
  `relay-send-failed` or `relay-send-unconfirmed`. The record holds both sends, with distinct tool ids.
  The earlier test of a header-dropped send alone could not reach this: its `exact` is empty.
- **Neutralization:** moved the three-line `if dropped:` block (the `return "relay-text-mismatch", {... "headerDropped": True}`)
  from directly after `if not final: return None, None` to directly before `return "relay-silent", None`.
- **Raw red** (both node ids):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result[failed] _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-25/test_a_header_dropped_send_out0/repo', config='/tmp/claude-0/py...test_a_header_dropped_send_out0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)
success = False, result = True

    @pytest.mark.parametrize("success, result", [(False, True), (True, False)], ids=["failed", "no-result"])
    def test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result(world, success, result):
        # axis: header-dropped outranks a competing exact send that failed or has no result at the end of the wait — the altered send is the verdict — a failed or unconfirmed verdict ahead of it makes it fail
        msg = _composed(world)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP),
                      _send_lines("toolu_2", SESSION, msg["forward"], STAMP, success=success, result=result))
        out, clock = _check(world, msg["msgId"], wait=6, interval=2)
>       assert out["reason"] == "relay-text-mismatch"
E       AssertionError: assert 'relay-send-failed' == 'relay-text-mismatch'
E         
E         - relay-text-mismatch
E         + relay-send-failed

/home/user/wt-2099-g/plugins/superheroes/lib/tests/test_cloud_relay.py:596: AssertionError
_ test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result[no-result] _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-25/test_a_header_dropped_send_out1/repo', config='/tmp/claude-0/py...test_a_header_dropped_send_out1/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)
success = True, result = False

    @pytest.mark.parametrize("success, result", [(False, True), (True, False)], ids=["failed", "no-result"])
    def test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result(world, success, result):
        # axis: header-dropped outranks a competing exact send that failed or has no result at the end of the wait — the altered send is the verdict — a failed or unconfirmed verdict ahead of it makes it fail
        msg = _composed(world)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, _header_dropped(msg), STAMP),
                      _send_lines("toolu_2", SESSION, msg["forward"], STAMP, success=success, result=result))
        out, clock = _check(world, msg["msgId"], wait=6, interval=2)
>       assert out["reason"] == "relay-text-mismatch"
E       AssertionError: assert 'relay-send-unconfirmed' == 'relay-text-mismatch'
E         
E         - relay-text-mismatch
E         + relay-send-unconfirmed

/home/user/wt-2099-g/plugins/superheroes/lib/tests/test_cloud_relay.py:596: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result[failed]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_header_dropped_send_outranks_an_exact_send_that_failed_or_has_no_result[no-result]
2 failed in 0.35s
```

  The red is on the axis: with the block moved down, the failed exact send reads `relay-send-failed` and the
  no-result exact send reads `relay-send-unconfirmed`, where the invariant says `relay-text-mismatch`.
- **Restore:** inverse Edit, the three-line `if dropped:` block moved back to directly after `if not final: return None, None`.
- **Restore receipt:** restored lines (cloud_relay.py:349-353): `    if not final:` / `        return None, None` /
  `    if dropped:` / `        return "relay-text-mismatch", {"firstDifference": _first_difference(msg["forward"], dropped[0][0]),` /
  `                                       "headerDropped": True}`. Then, directly before `return "relay-silent", None`:
  `    failed = [r for r in exact if not r[0]]` / `    if failed:` / `        return "relay-send-failed", {"result": failed[0][1]}`.
  `git diff plugins/superheroes/lib/cloud_relay.py` after the restore printed nothing (empty output).
- **Raw green** (same two node ids):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 1.82s
```
