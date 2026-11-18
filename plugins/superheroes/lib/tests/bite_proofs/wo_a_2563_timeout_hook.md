# Bite-proof record: wo_a_2563_timeout_hook

Detector: `plugins/superheroes/lib/tests/test_bash_timeout_hook.py` (the 2563 tests: env off switch,
auto-mode refusal, branch record). Guarded code: `plugins/superheroes/hooks/bash_timeout.py`.
Rubric: `plugins/superheroes/rubric/bite-proof.md`.

Declared guarded-element set (from the work order): E1 to E8 below, one neutralization of the hook
source each. Each was applied with a single targeted edit (the target asserted to occur once before the
edit), the detector was run alone by exact test node id (function-level node id, never `-k`), the edit was
reverted by the inverse edit, and `git diff --stat -- plugins/superheroes/hooks/bash_timeout.py` was shown
to match the pre-neutralization state each time.

Pre-neutralization state, shown before E1 and re-shown after every restore (identical each time):

```
 plugins/superheroes/hooks/bash_timeout.py | 83 ++++++++++++++++++++++++-------
 1 file changed, 64 insertions(+), 19 deletions(-)
```

Run form for every capture below:
`scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-2563a -m pytest <node id> -q -p no:cacheprovider`
(run with the 600000 ms Bash timeout).

Redaction: the worktree path is written `<worktree>` and pytest's scratch `tmp_path` directories
(under the sandbox temp area) are shortened to `<tmp>`; nothing else was altered. No secrets, tokens or
private URLs appear in any capture. Every capture is under 32 KiB. The `UV_NATIVE_TLS` warning line is the
launcher's own and is kept as printed.

## E1 — env switch off at >= 600000

- Guarded element: `_env_switch_on` in `plugins/superheroes/hooks/bash_timeout.py` (the
  `int(value.strip()) >= DEFAULT_TIMEOUT_MS` comparison).
- Axis: a `BASH_DEFAULT_TIMEOUT_MS` of 600000, 900000 or `" 600000 "` makes the hook emit nothing and write no
  firing record, for a no-mode payload and an auto-mode payload.
- Detector: `test_env_at_or_above_floor_switches_hook_off` (6 parametrized cases).
- Neutralization (env check never switches off):
  `return int(value.strip()) >= DEFAULT_TIMEOUT_MS` became
  `return int(value.strip()) >= DEFAULT_TIMEOUT_MS and False`.
- Raw red. **Incomplete: the harness truncated the middle of this output ("[1639 characters truncated]");
  what follows is exactly what I received, not reconstructed.** The first two failure blocks, the truncation
  marker as received, and the tail are shown; all six cases appear in the final summary lines.

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
_________ test_env_at_or_above_floor_switches_hook_off[600000-no-mode] _________

tmp_path = PosixPath('<tmp>/test_env_at_or_above_floor_swi0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f7dce5657f0>
env_value = '600000', mode = <object object at 0x7f7dcf9258a0>

    @pytest.mark.parametrize("mode", [_MISSING, "auto"], ids=["no-mode", "auto-mode"])
    @pytest.mark.parametrize("env_value", ["600000", "900000", " 600000 "])
    def test_env_at_or_above_floor_switches_hook_off(tmp_path, monkeypatch, env_value, mode):
        monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
>       assert _mod().decide(_payload(mode), {"BASH_DEFAULT_TIMEOUT_MS": env_value}) is None
E       AssertionError: assert ('rewrite', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'updatedInput': {'command': 'echo ok', 'timeout': 600000}}}) is None
E        +  where ('rewrite', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'updatedInput': {'command': 'echo ok', 'timeout': 600000}}}) = <function decide at 0x7f7dcd542c00>({'tool_input': {'command': 'echo ok'}}, {'BASH_DEFAULT_TIMEOUT_MS': '600000'})
E        +    where <function decide at 0x7f7dcd542c00> = <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'>.decide
E        +      where <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'> = _mod()
E        +    and   {'tool_input': {'command': 'echo ok'}} = _payload(<object object at 0x7f7dcf9258a0>)

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:289: AssertionError
________ test_env_at_or_above_floor_switches_hook_off[600000-auto-mode] ________

tmp_path = PosixPath('<tmp>/test_env_at_or_above_floor_swi1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f7dce564e00>
env_value = '600000', mode = 'auto'

    @pytest.mark.parametrize("mode", [_MISSING, "auto"], ids=["no-mode", "auto-mode"])
    @pytest.mark.parametrize("env_value", ["600000", "900000", " 600000 "])
    def test_env_at_or_above_floor_switches_hook_off(tmp_path, monkeypatch, env_value, mode):
        monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
>       assert _mod().decide(_payload(mode), {"BASH_DEFAULT_TIMEOUT_MS": env_value}) is None
E       assert ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) is None
E        +  where ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) = <function decide at 0x7f7dcdd24680>({'tool_input': {'command': 'echo ok'}, 'permission_mode': 'auto'}, {'BASH_DEFAULT_TIMEOUT_MS': '600000'})

... [1639 characters truncated] ...

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_at_or_above_floor_switches_hook_off[600000-no-mode]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_at_or_above_floor_switches_hook_off[600000-auto-mode]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_at_or_above_floor_switches_hook_off[900000-no-mode]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_at_or_above_floor_switches_hook_off[900000-auto-mode]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_at_or_above_floor_switches_hook_off[ 600000 -no-mode]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_at_or_above_floor_switches_hook_off[ 600000 -auto-mode]
6 failed in 0.23s
```

  (The harness result also held a further stretch of the 900000 and ` 600000 ` failure blocks between the
  truncation marker and the summary; those are the same assertion on the same line. That part is lost, not
  reconstructed.)
- Restore: inverse edit, `... >= DEFAULT_TIMEOUT_MS and False` back to `... >= DEFAULT_TIMEOUT_MS`.
- Restore receipt: restored line in `_env_switch_on` reads `        return int(value.strip()) >= DEFAULT_TIMEOUT_MS`
  and `git diff --stat` matches the pre-neutralization state shown above.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed in 0.34s
```

## E2 — env below floor or non-number still rewrites

- Guarded element: the same comparison and its `except (ValueError, AttributeError)` fail-through in
  `_env_switch_on`.
- Axis: unset, `"599999"`, `""`, `"abc"`, `"600000.5"` and `"-1"` do not switch the hook off; the hook still
  rewrites (decide returns the rewrite branch and the process prints `updatedInput.timeout == 600000` with no
  `permissionDecision`).
- Detector: `test_env_below_floor_or_non_number_still_rewrites` (6 parametrized cases).
- Neutralization (any non-empty env value switches off): `return int(value.strip()) >= DEFAULT_TIMEOUT_MS`
  became `return bool(value.strip())`.
- Raw red (4 of 6 cases fail; unset and empty stay green, as they should under this neutralization):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.F.FFF                                                                   [100%]
=================================== FAILURES ===================================
________ test_env_below_floor_or_non_number_still_rewrites[below-floor] ________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd11d1304a0>
env_value = '599999'

    @pytest.mark.parametrize("env_value", [None, "599999", "", "abc", "600000.5", "-1"],
                             ids=["unset", "below-floor", "empty", "non-integer", "float", "negative"])
    def test_env_below_floor_or_non_number_still_rewrites(monkeypatch, env_value):
        environ = {}
        if env_value is not None:
            monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
            environ["BASH_DEFAULT_TIMEOUT_MS"] = env_value
        decision = _mod().decide(_payload(), environ)
>       assert decision is not None and decision[0] == "rewrite"
E       assert (None is not None)

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:305: AssertionError
________ test_env_below_floor_or_non_number_still_rewrites[non-integer] ________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd11d133080>
env_value = 'abc'

    @pytest.mark.parametrize("env_value", [None, "599999", "", "abc", "600000.5", "-1"],
                             ids=["unset", "below-floor", "empty", "non-integer", "float", "negative"])
    def test_env_below_floor_or_non_number_still_rewrites(monkeypatch, env_value):
        environ = {}
        if env_value is not None:
            monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
            environ["BASH_DEFAULT_TIMEOUT_MS"] = env_value
        decision = _mod().decide(_payload(), environ)
>       assert decision is not None and decision[0] == "rewrite"
E       assert (None is not None)

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:305: AssertionError
___________ test_env_below_floor_or_non_number_still_rewrites[float] ___________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd11d132d20>
env_value = '600000.5'

    @pytest.mark.parametrize("env_value", [None, "599999", "", "abc", "600000.5", "-1"],
                             ids=["unset", "below-floor", "empty", "non-integer", "float", "negative"])
    def test_env_below_floor_or_non_number_still_rewrites(monkeypatch, env_value):
        environ = {}
        if env_value is not None:
            monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
            environ["BASH_DEFAULT_TIMEOUT_MS"] = env_value
        decision = _mod().decide(_payload(), environ)
>       assert decision is not None and decision[0] == "rewrite"
E       assert (None is not None)

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:305: AssertionError
__________ test_env_below_floor_or_non_number_still_rewrites[negative] __________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd11d6de480>
env_value = '-1'

    @pytest.mark.parametrize("env_value", [None, "599999", "", "abc", "600000.5", "-1"],
                             ids=["unset", "below-floor", "empty", "non-integer", "float", "negative"])
    def test_env_below_floor_or_non_number_still_rewrites(monkeypatch, env_value):
        environ = {}
        if env_value is not None:
            monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
            environ["BASH_DEFAULT_TIMEOUT_MS"] = env_value
        decision = _mod().decide(_payload(), environ)
>       assert decision is not None and decision[0] == "rewrite"
E       assert (None is not None)

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_below_floor_or_non_number_still_rewrites[below-floor]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_below_floor_or_non_number_still_rewrites[non-integer]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_below_floor_or_non_number_still_rewrites[float]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_env_below_floor_or_non_number_still_rewrites[negative]
4 failed, 2 passed in 0.31s
```

- Restore: inverse edit, `return bool(value.strip())` back to `return int(value.strip()) >= DEFAULT_TIMEOUT_MS`.
- Restore receipt: restored line quoted above; `git diff --stat` matches the pre-neutralization state.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed in 0.36s
```

## E3 — auto mode refuses, never rewrites

- Guarded element: the `if payload.get("permission_mode") == "auto":` branch in `decide`.
- Axis: in auto mode with no timeout the decision is the refuse branch with `permissionDecision == "deny"` and
  no `updatedInput`.
- Detector: `test_auto_mode_refuses_with_route_and_never_rewrites`.
- Neutralization (drop the auto branch, auto falls to rewrite):
  `if payload.get("permission_mode") == "auto":` became `if False:`.
- Raw red (the first assertion, `branch == "refuse"`, is the one that goes red):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_auto_mode_refuses_with_route_and_never_rewrites _____________

    def test_auto_mode_refuses_with_route_and_never_rewrites():
        m = _mod()
        branch, hook_output = m.decide(_payload("auto"), {})
>       assert branch == "refuse"
E       AssertionError: assert 'rewrite' == 'refuse'
E         
E         - refuse
E         + rewrite

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:315: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_auto_mode_refuses_with_route_and_never_rewrites
1 failed in 0.20s
```

- Restore: inverse edit, `if False:` back to `if payload.get("permission_mode") == "auto":`.
- Restore receipt: restored line quoted; `git diff --stat` matches the pre-neutralization state.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.20s
```

## E4 — the reason names `timeout: 600000`

- Guarded element: the `REFUSAL_REASON` constant's route text in `plugins/superheroes/hooks/bash_timeout.py`.
- Axis: the refusal reason contains the literal `timeout: 600000` (the route the model re-issues with).
- Detector: `test_auto_mode_refuses_with_route_and_never_rewrites` (the reason assertion).
- Neutralization (remove `timeout: 600000` from `REFUSAL_REASON` only):
  `unchanged except for timeout: 600000.` became `unchanged except for the timeout.`
- Raw red (E3's assertions before the reason one pass; the red is on the reason assertion):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_auto_mode_refuses_with_route_and_never_rewrites _____________

    def test_auto_mode_refuses_with_route_and_never_rewrites():
        m = _mod()
        branch, hook_output = m.decide(_payload("auto"), {})
        assert branch == "refuse"
        hso = hook_output["hookSpecificOutput"]
        # axis: auto mode refuses instead of rewriting, bite-proof record wo_a_2563_timeout_hook (E3)
        assert hso["permissionDecision"] == "deny"
        assert "updatedInput" not in hso
        # axis: the refusal reason names the route timeout: 600000, bite-proof record wo_a_2563_timeout_hook (E4)
>       assert "timeout: 600000" in hso["permissionDecisionReason"]
E       assert 'timeout: 600000' in "superheroes timeout floor: this Bash call names no timeout. Route: re-issue this same Bash call once, unchanged excep...n auto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:321: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_auto_mode_refuses_with_route_and_never_rewrites
1 failed in 0.20s
```

- Restore: inverse edit, `unchanged except for the timeout.` back to `unchanged except for timeout: 600000.`
- Restore receipt: restored line in `REFUSAL_REASON` reads
  `    "Bash call once, unchanged except for timeout: 600000. In auto mode the floor asks you "`;
  `git diff --stat` matches the pre-neutralization state.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.20s
```

## E5 — other modes rewrite

- Guarded element: the equality test `== "auto"` on `permission_mode` in `decide` (only the string `"auto"` refuses).
- Axis: `"default"`, `"acceptEdits"`, `"plan"`, `"bypassPermissions"`, `"dontAsk"`, a missing key, `1` and
  `null` all take the rewrite branch.
- Detector: `test_every_other_mode_rewrites` (8 parametrized cases).
- Neutralization (refuse in every mode): `if payload.get("permission_mode") == "auto":` became `if True:`.
- Raw red (8 of 8 fail; the failure blocks are identical but for the mode, so the first three and the summary
  are shown and the other five blocks are elided, about 3 KiB; the summary lists all eight):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
___________________ test_every_other_mode_rewrites[default] ____________________

mode = 'default'

    @pytest.mark.parametrize("mode", _OTHER_MODES)
    def test_every_other_mode_rewrites(mode):
        decision = _mod().decide(_payload(mode), {})
        # axis: only auto refuses; every other mode value rewrites, bite-proof record wo_a_2563_timeout_hook (E5)
>       assert decision is not None and decision[0] == "rewrite"
E       assert (('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) is not None and 'refuse' == 'rewrite'
E         
E         - rewrite
E         + refuse)

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:340: AssertionError
[... blocks for acceptEdits, plan, bypassPermissions, dontAsk, missing-key, int-mode, null-mode elided here:
 identical shape, same assertion and line 340, 'refuse' == 'rewrite' in each ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[default]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[acceptEdits]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[plan]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[bypassPermissions]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[dontAsk]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[missing-key]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[int-mode]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_every_other_mode_rewrites[null-mode]
8 failed in 0.27s
```

- Restore: inverse edit, `if True:` back to `if payload.get("permission_mode") == "auto":`.
- Restore receipt: restored line quoted; `git diff --stat` matches the pre-neutralization state.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........                                                                 [100%]
8 passed in 0.51s
```

## E6 — explicit timeout untouched in auto mode

- Guarded element: the `tool_input.get("timeout") is not None` check's position ahead of the auto branch in `decide`.
- Axis: an explicit timeout yields no output in every mode, `"auto"` included, and writes no firing record.
- Detector: `test_explicit_timeout_untouched_in_every_mode` (9 parametrized cases).
- Neutralization (auto branch moved above the explicit-timeout check): the lines
  `if tool_input.get("timeout") is not None: return None` and the auto-branch `if ...: return "refuse", {...}`
  swapped, auto first.
- Raw red (only the `auto` case fails; the eight other modes stay green):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........F                                                                [100%]
=================================== FAILURES ===================================
_____________ test_explicit_timeout_untouched_in_every_mode[auto] ______________

tmp_path = PosixPath('<tmp>/test_explicit_timeout_untouche8')
mode = 'auto'

    @pytest.mark.parametrize("mode", _OTHER_MODES + [pytest.param("auto", id="auto")])
    def test_explicit_timeout_untouched_in_every_mode(tmp_path, mode):
        payload = _payload(mode, timeout=5000)
        # axis: an explicit timeout is never touched, auto mode included, bite-proof record wo_a_2563_timeout_hook (E6)
>       assert _mod().decide(payload, {}) is None
E       assert ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) is None
E        +  where ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) = <function decide at 0x7f61b6e99580>({'tool_input': {'command': 'echo ok', 'timeout': 5000}, 'permission_mode': 'auto'}, {})
E        +    where <function decide at 0x7f61b6e99580> = <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'>.decide
E        +      where <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'> = _mod()

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:351: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_explicit_timeout_untouched_in_every_mode[auto]
1 failed, 8 passed in 0.39s
```

- Restore: inverse edit, the two blocks swapped back (explicit-timeout check, then auto branch).
- Restore receipt: restored order quoted from the file after the edit:
  `if tool_input.get("timeout") is not None:` / `return None` / `if payload.get("permission_mode") == "auto":`;
  `git diff --stat` matches the pre-neutralization state.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.........                                                                [100%]
9 passed in 0.43s
```

## E7 — malformed auto payload fails open

- Guarded element: the `isinstance(tool_input, dict)` check's position ahead of the auto branch in `decide`.
- Axis: `{"permission_mode": "auto", "tool_input": "x"}` and `{"permission_mode": "auto"}` emit nothing and
  write no firing record (garbage stdin is covered by the sibling test, which the neutralization does not
  reach: stdin that is not a JSON object never gets to `decide`'s auto branch).
- Detector: `test_malformed_auto_payload_emits_nothing` (2 parametrized cases).
- Neutralization (auto branch refuses before the `tool_input` dict check): the auto branch moved to sit
  directly after the `isinstance(payload, dict)` check, above `tool_input = payload.get("tool_input")`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
________ test_malformed_auto_payload_emits_nothing[tool-input-not-dict] ________

tmp_path = PosixPath('<tmp>/test_malformed_auto_payload_em0')
payload = {'permission_mode': 'auto', 'tool_input': 'x'}

    @pytest.mark.parametrize("payload", [
        pytest.param({"permission_mode": "auto", "tool_input": "x"}, id="tool-input-not-dict"),
        pytest.param({"permission_mode": "auto"}, id="no-tool-input"),
    ])
    def test_malformed_auto_payload_emits_nothing(tmp_path, payload):
        # axis: a malformed payload in auto mode fails open with no refusal, bite-proof record wo_a_2563_timeout_hook (E7)
>       assert _mod().decide(payload, {}) is None
E       assert ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) is None
E        +  where ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) = <function decide at 0x7f256944e200>({'permission_mode': 'auto', 'tool_input': 'x'}, {})
E        +    where <function decide at 0x7f256944e200> = <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'>.decide
E        +      where <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'> = _mod()

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:364: AssertionError
___________ test_malformed_auto_payload_emits_nothing[no-tool-input] ___________

tmp_path = PosixPath('<tmp>/test_malformed_auto_payload_em1')
payload = {'permission_mode': 'auto'}

    @pytest.mark.parametrize("payload", [
        pytest.param({"permission_mode": "auto", "tool_input": "x"}, id="tool-input-not-dict"),
        pytest.param({"permission_mode": "auto"}, id="no-tool-input"),
    ])
    def test_malformed_auto_payload_emits_nothing(tmp_path, payload):
        # axis: a malformed payload in auto mode fails open with no refusal, bite-proof record wo_a_2563_timeout_hook (E7)
>       assert _mod().decide(payload, {}) is None
E       assert ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) is None
E        +  where ('refuse', {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionRea...uto mode the floor asks you instead of rewriting the call, because a rewritten call waits for the owner's approval."}}) = <function decide at 0x7f2569db8540>({'permission_mode': 'auto'}, {})
E        +    where <function decide at 0x7f2569db8540> = <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'>.decide
E        +      where <module 'bash_timeout' from '<worktree>/plugins/superheroes/hooks/bash_timeout.py'> = _mod()

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:364: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_malformed_auto_payload_emits_nothing[tool-input-not-dict]
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_malformed_auto_payload_emits_nothing[no-tool-input]
2 failed in 0.21s
```

- Restore: inverse edit, the auto branch moved back below the explicit-timeout check.
- Restore receipt: `git diff --stat` matches the pre-neutralization state; the restored order is
  `tool_input = payload.get("tool_input")` / dict check / explicit-timeout check / auto branch.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.24s
```

## E8 — firing record names the branch

- Guarded element: the `"branch": branch,` key in `record_firing`.
- Axis: the record line carries `"branch"` equal to the branch actually taken (`"rewrite"` or `"refuse"`), with the
  key set exactly `{"ts", "timeout_ms", "session", "cwd", "branch"}`.
- Detector: `test_firing_record_names_the_branch`.
- Neutralization (always write `"rewrite"`): `"branch": branch,` became `"branch": "rewrite",`.
- Raw red (the refuse case):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_firing_record_names_the_branch ______________________

tmp_path = PosixPath('<tmp>/test_firing_record_names_the_b0')

    def test_firing_record_names_the_branch(tmp_path):
        for mode, expected_branch in ((_MISSING, "rewrite"), ("auto", "refuse")):
            payload = _payload(mode)
            payload["session_id"] = "sess-" + expected_branch
            payload["cwd"] = "/work"
            r = _run_hook(json.dumps(payload))
            assert r.returncode == 0
        lines = open(_record_path(tmp_path), encoding="utf-8").read().splitlines()
        assert len(lines) == 2
        by_session = {entry["session"]: entry for entry in map(json.loads, lines)}
        for expected_branch in ("rewrite", "refuse"):
            entry = by_session["sess-" + expected_branch]
            # axis: the record names the branch taken, bite-proof record wo_a_2563_timeout_hook (E8)
>           assert entry["branch"] == expected_branch
E           AssertionError: assert 'rewrite' == 'refuse'
E             
E             - refuse
E             + rewrite

<worktree>/plugins/superheroes/lib/tests/test_bash_timeout_hook.py:393: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bash_timeout_hook.py::test_firing_record_names_the_branch
1 failed in 0.26s
```

- Restore: inverse edit, `"branch": "rewrite",` back to `"branch": branch,`.
- Restore receipt: restored line quoted; `git diff --stat` matches the pre-neutralization state.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.26s
```
