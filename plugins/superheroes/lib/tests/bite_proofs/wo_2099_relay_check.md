# Bite-proof record: WO-A (#2099) `cloud_relay.py check` reads every send attempt

Detector under proof: the tests added or changed in `plugins/superheroes/lib/tests/test_cloud_relay.py`.
Guarded code: `plugins/superheroes/lib/cloud_relay.py` (`_to_session`, `_decide`).
Base: `9464afc15ede3ce51bc51fee8e71eee64dbe269a`. Every neutralization was a targeted edit, undone by
the inverse edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-wo-a -m pytest ... -q -p no:cacheprovider`.
Nothing in the captures was redacted; each is under 32 KiB. Only the test node ids differ per run.

Disclosure: the G1 red run was issued with the whole test file path plus two node ids, so it ran
the whole file (78 tests) and not only the two nodes. The two named nodes are among the five reds.
The detector was not edited.

## G1 recipient: the bracketed-recipient acceptance

- **Guarded element:** `cloud_relay.py` `_to_session`, the `<session> [<ref>]` acceptance (def at line 272; the
  rule after `if to == session`). Axis: the recipient match; a delivered retry whose `to` carries the
  host's `[ref]` suffix is this message's send.
- **Neutralization:** in `_to_session`, directly after `    if to == session:\n        return True`, inserted `    return False`.
  The helper then accepts only `to == session`.
- **Raw red** (run: the whole test file path plus the E1 node and the literal-pin node):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........FF.F...........FF............................................... [ 92%]
......                                                                   [100%]
=================================== FAILURES ===================================
_______ test_a_failed_attempt_then_a_recorded_retry_success_is_delivered _______

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-1/test_a_failed_attempt_then_a_r0/repo', config='/tmp/claude-0/pyt...test_a_failed_attempt_then_a_r0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_failed_attempt_then_a_recorded_retry_success_is_delivered(world):
        msg = _composed(world)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                      _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))
        out, clock = _check(world, msg["msgId"], wait=60)
>       assert out["ok"] is True and out["delivered"] is True and out["reason"] is None
E       assert (False is True)

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:257: AssertionError
_ test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-1/test_a_failed_attempt_then_a_r1/repo', config='/tmp/claude-0/pyt...test_a_failed_attempt_then_a_r1/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered(world):
        msg = _composed(world)
        failed = _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False)
        _write_record(world, failed)
        clock = Clock()
    
        def sleep(seconds):
            clock.sleep(seconds)
            _write_record(world, failed, _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))
    
        out = cr.check(world.repo, msg["msgId"], wait=30, interval=2, env=world.env,
                       clock=clock, sleep=sleep)
>       assert out["delivered"] is True and clock.t == 2
E       assert (False is True)

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:273: AssertionError
_______ test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed _______

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-1/test_a_failed_attempt_and_a_re0/repo', config='/tmp/claude-0/pyt...test_a_failed_attempt_and_a_re0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed(world):
        msg = _composed(world)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                      _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP, result=False))
        out, clock = _check(world, msg["msgId"], wait=6, interval=2)
>       assert out["reason"] == "relay-send-unconfirmed" and clock.t >= 6
E       AssertionError: assert ('relay-send-failed' == 'relay-send-unconfirmed'
E         
E         - relay-send-unconfirmed
E         ?            -----  ^^
E         + relay-send-failed
E         ?             + ^)

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:292: AssertionError
____________ test_a_bracketed_send_with_altered_text_is_a_mismatch _____________

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-1/test_a_bracketed_send_with_alt0/repo', config='/tmp/claude-0/pyt...test_a_bracketed_send_with_alt0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_bracketed_send_with_altered_text_is_a_mismatch(world):
        msg = _composed(world)
        _write_record(world, _send_lines("toolu_1", SESSION + " [3fa9c1]", msg["forward"][:-1], STAMP))
        out, clock = _check(world, msg["msgId"])
>       assert out["reason"] == "relay-text-mismatch" and out["delivered"] is False and clock.t == 0
E       AssertionError: assert ('relay-silent' == 'relay-text-mismatch'
E         
E         - relay-text-mismatch
E         + relay-silent)

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:310: AssertionError
_____ test_the_disambiguated_recipient_form_is_session_space_bracketed_ref _____

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-1/test_the_disambiguated_recipie0/repo', config='/tmp/claude-0/pyt...test_the_disambiguated_recipie0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_the_disambiguated_recipient_form_is_session_space_bracketed_ref(world):
        # Literal pin of the host SendMessage tool's `to` form: `worker [3fa9c1]` (CONVENTIONS §11.3).
        assert "%s [3fa9c1]" % SESSION == "builder-1748 [3fa9c1]"
        msg = _composed(world)
        _write_record(world, _send_lines("toolu_1", "%s [3fa9c1]" % SESSION, msg["forward"], STAMP))
        out, _ = _check(world, msg["msgId"])
>       assert out["delivered"] is True
E       assert False is True

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:319: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_failed_attempt_then_a_recorded_retry_success_is_delivered
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_bracketed_send_with_altered_text_is_a_mismatch
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_the_disambiguated_recipient_form_is_session_space_bracketed_ref
5 failed, 73 passed in 3.11s
```

  The red is on the axis: the retry whose `to` is `builder-1748 [3fa9c1]` is not seen as this message's
  send, so E1, E2 and E6 read nothing, and the literal-pin test fails on `delivered`.
- **Restore:** inverse edit, removed the inserted `    return False` line.
- **Restore receipt:** the restored lines (cloud_relay.py:275-279):
  `    if to == session:` / `        return True` / `    if not (isinstance(to, str) and to.startswith(session + " [") and to.endswith("]")):` / `        return False` / `    ref = to[len(session) + 2:-1]`.
  `git status --porcelain plugins/superheroes/lib/cloud_relay.py` printed ` M plugins/superheroes/lib/cloud_relay.py`
  (the file is modified by the whole change, so the status line alone is not a restore proof; the quoted lines are).
- **Raw green** (E1 node and the literal-pin node, by node id):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.31s
```

## G2 recipient strictness: the bracketed-form strictness

- **Guarded element:** `cloud_relay.py` `_to_session`, the exact-form checks (`session + " ["`, trailing `]`,
  non-empty ref, no whitespace or brackets in the ref). Axis: the recipient match is exact; a bare ref, another
  name, a prefix, extra whitespace, an empty `[]` or a trailing character is not this session.
- **Neutralization:** in `_to_session`, directly after `    if to == session:\n        return True`, inserted
  `    if isinstance(to, str) and to.startswith(session):\n        return True`. The helper then accepts any `to` that
  starts with the session name.
- **Raw red** (node `test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send`, all 11 parameters; 8 failed, 3 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...FFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
_ test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748 []] _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-3/test_a_send_to_a_loosely_brack3/repo', config='/tmp/claude-0/pyt...test_a_send_to_a_loosely_brack3/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)
to = 'builder-1748 []'

    @pytest.mark.parametrize("to", [
        "someone-else [3fa9c1]", "[3fa9c1]", "3fa9c1", SESSION + " []", SESSION + "  [x]",
        SESSION + " [a b]", SESSION + " [x]y", SESSION + " [x[y]", SESSION + "x [3fa9c1]",
        SESSION + " [3fa9c1] ", SESSION + "[3fa9c1]"])
    def test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send(world, to):
        msg = _composed(world)
        _write_record(world, _send_lines("toolu_1", to, msg["forward"], STAMP))
        out, _ = _check(world, msg["msgId"], wait=4, interval=2)
>       assert out["reason"] == "relay-silent" and out["delivered"] is False
E       AssertionError: assert (None == 'relay-silent')

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:303: AssertionError
[... the same traceback for each of the other seven failing parameters, each ending "AssertionError: assert (None == 'relay-silent')": 'builder-1748  [x]', 'builder-1748 [a b]', 'builder-1748 [x]y', 'builder-1748 [x[y]', 'builder-1748x [3fa9c1]', 'builder-1748 [3fa9c1] ', 'builder-1748[3fa9c1]'; elided here, about 6 KiB ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748 []]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748  [x]]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748 [a b]]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748 [x]y]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748 [x[y]]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748x [3fa9c1]]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748 [3fa9c1] ]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_to_a_loosely_bracketed_recipient_is_not_this_messages_send[builder-1748[3fa9c1]]
8 failed, 3 passed in 1.26s
```

  The three that stayed green (`someone-else [3fa9c1]`, `[3fa9c1]`, `3fa9c1`) do not start with the session
  name, so this neutralization cannot reach them; they are guarded by the `to == session` and form checks
  in the G1 and G2 acceptance, not by the prefix rule. The red includes the cases the order named
  (`session [x]y`, `session  [x]`). The elision above is of the other seven tracebacks, which repeat the one shown.
- **Restore:** inverse edit, removed the two inserted lines.
- **Restore receipt:** `grep -n -A8 "^def _to_session"` after the restore showed lines 275-280 identical to the
  G1 restore receipt above (`if to == session:` / `return True` / `if not (isinstance(to, str) and ...` / `return False` / `ref = ...` / the `# axis:` line).
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...........                                                              [100%]
11 passed in 1.10s
```

## G3 provisional failure while not final

- **Guarded element:** `cloud_relay.py` `_decide`, the `if not final: return None, None` branch placed before any
  failure verdict (the `# axis:` line above it). Axis: a failed attempt is provisional while the wait runs.
- **Neutralization:** restored the old order. Directly before `    if not final:` inserted
  `    failed = [r for r in exact if r and not r[0]]\n    if failed:\n        return "relay-send-failed", {"result": failed[0][1]}`.
- **Raw red** (E2 node, E1 node, E3 node and the changed existing test, by node id):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.FFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered _

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-5/test_a_failed_attempt_then_a_r1/repo', config='/tmp/claude-0/pyt...test_a_failed_attempt_then_a_r1/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered(world):
        msg = _composed(world)
        failed = _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False)
        _write_record(world, failed)
        clock = Clock()
    
        def sleep(seconds):
            clock.sleep(seconds)
            _write_record(world, failed, _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP))
    
        out = cr.check(world.repo, msg["msgId"], wait=30, interval=2, env=world.env,
                       clock=clock, sleep=sleep)
>       assert out["delivered"] is True and clock.t == 2
E       assert (False is True)

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:273: AssertionError
_______ test_only_failed_attempts_are_send_failed_at_the_end_of_the_wait _______

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-5/test_only_failed_attempts_are_0/repo', config='/tmp/claude-0/pyt...test_only_failed_attempts_are_0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_only_failed_attempts_are_send_failed_at_the_end_of_the_wait(world):
        msg = _composed(world)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                      _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP, success=False))
        out, clock = _check(world, msg["msgId"], wait=10, interval=2)
        assert out["ok"] is False and out["reason"] == "relay-send-failed"
>       assert "No agent named" in out["say"] and clock.t >= 10
E       assert ('No agent named' in "The relay's send of message edbf32d5c0d2 failed (No agent named 'x' is reachable); it was not delivered." and 0.0 >= 10)
E        +  where 0.0 = <test_cloud_relay.Clock object at 0x7f80913975c0>.t

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:283: AssertionError
____________ test_exact_text_refused_by_the_session_is_send_failed _____________

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-5/test_exact_text_refused_by_the0/repo', config='/tmp/claude-0/pyt...test_exact_text_refused_by_the0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_exact_text_refused_by_the_session_is_send_failed(world):
        msg = _composed(world)
        _write_record(world, _send_lines("toolu_1", SESSION, msg["forward"], "2026-10-12T10:00:00.000Z",
                                         success=False))
        out, clock = _check(world, msg["msgId"])
        assert out["ok"] is False and out["reason"] == "relay-send-failed"
>       assert "No agent named" in out["say"] and clock.t >= 60
E       assert ('No agent named' in "The relay's send of message 5ec0824c4110 failed (No agent named 'x' is reachable); it was not delivered." and 0.0 >= 60)
E        +  where 0.0 = <test_cloud_relay.Clock object at 0x7f8090997650>.t

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:221: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_failed_attempt_then_a_retry_success_arriving_during_the_wait_is_delivered
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_only_failed_attempts_are_send_failed_at_the_end_of_the_wait
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_exact_text_refused_by_the_session_is_send_failed
3 failed, 1 passed in 0.49s
```

  Reds: E2 (a retry's success arriving during the wait is lost), E3 and the changed existing test (the failure
  verdict comes at clock 0, not at the end of the wait). The E1 node stays green under this neutralization
  because its retry success is already recorded and the success rule precedes the failure rule; the order
  allowed "E1 or E2", and E2 is the one that bites.
- **Restore:** inverse edit, removed the three inserted lines.
- **Restore receipt:** the restored block (cloud_relay.py:336-346) after the edit:
  `    if any(r and r[0] for r in exact):` / `        return "delivered", None` / the `# axis: a failed attempt is provisional ...` line /
  `    if not final:` / `        return None, None` / `    if any(r is None for r in exact):` / `        return "relay-send-unconfirmed", None` /
  `    failed = [r for r in exact if not r[0]]` / `    if failed:` / `        return "relay-send-failed", {"result": failed[0][1]}` / `    return "relay-silent", None`.
- **Raw green** (same four nodes):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....                                                                     [100%]
4 passed in 0.47s
```

## G4 unconfirmed beats failed at the end

- **Guarded element:** `cloud_relay.py` `_decide`, the final-stage order `relay-send-unconfirmed` before
  `relay-send-failed`. Axis: a send with no result at the end of the wait is unconfirmed, whatever else failed.
- **Neutralization:** swapped the two final-stage checks: `failed = [r for r in exact if r and not r[0]]` and its
  `return "relay-send-failed", ...` now precede `if any(r is None for r in exact): return "relay-send-unconfirmed", None`.
- **Raw red** (E4 node):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed _______

world = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-7/test_a_failed_attempt_and_a_re0/repo', config='/tmp/claude-0/pyt...test_a_failed_attempt_and_a_re0/.claude-two/projects/-some-dir/5534cbe0-5d2a-4783-8980-09c4bafd22ad.jsonl', state=None)

    def test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed(world):
        msg = _composed(world)
        _write_record(world,
                      _send_lines("toolu_1", SESSION, msg["forward"], STAMP, success=False),
                      _send_lines("toolu_2", SESSION + " [3fa9c1]", msg["forward"], STAMP, result=False))
        out, clock = _check(world, msg["msgId"], wait=6, interval=2)
>       assert out["reason"] == "relay-send-unconfirmed" and clock.t >= 6
E       AssertionError: assert ('relay-send-failed' == 'relay-send-unconfirmed'
E         
E         - relay-send-unconfirmed
E         ?            -----  ^^
E         + relay-send-failed
E         ?             + ^)

/home/user/wt-2099-a/plugins/superheroes/lib/tests/test_cloud_relay.py:292: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_failed_attempt_and_a_retry_without_a_result_is_unconfirmed
1 failed in 0.36s
```

- **Restore:** inverse edit, swapped the two checks back.
- **Restore receipt:** `sed -n 339,346p` after the restore printed:
  `    if not final:` / `        return None, None` / `    if any(r is None for r in exact):` / `        return "relay-send-unconfirmed", None` /
  `    failed = [r for r in exact if not r[0]]` / `    if failed:` / `        return "relay-send-failed", {"result": failed[0][1]}` / `    return "relay-silent", None`.
  `git status --porcelain plugins/superheroes/lib/` then printed ` M plugins/superheroes/lib/cloud_relay.py` and
  ` M plugins/superheroes/lib/tests/test_cloud_relay.py` (the two deliverables; the bite-proof file is new and unstaged).
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.39s
```

## Baseline run, before any neutralization

Whole file, with the change and the tests in place and no neutralization, 78 tests:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 2.96s
```

## Not done

The whole-file run on the final head after the last restore was not made: the command that combined it with a
whitespace check was refused by the permission check and was not retried in any form. Every restored element was
re-run green by node id (above), and the quoted restored lines show the file back as written.
