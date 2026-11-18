# Bite-proof record wo_b_2563_explicit_timeout

Detectors added or changed, all in `plugins/superheroes/lib/tests/test_command_refusals.py`, each assertion with an `# axis:` comment naming this record:

- `test_plain_command_rule_content` (two new assertions: `"Pass an explicit `timeout` on every Bash call"` and `"`timeout: 600000`"` in the rule).
- `test_every_bash_granted_agent_asks_for_an_explicit_timeout` (new).
- `test_check_runner_takes_the_timeout_route_once` (new).

Every red and green run was `scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-2563b -m pytest <exact node id> -q -p no:cacheprovider`, run with `timeout: 600000`. The first line of each capture (`warning: The UV_NATIVE_TLS ...`) is the wrapper's stderr and is dropped below; every other line is verbatim. Each neutralization was a targeted Edit-tool change whose target occurred once (the Edit tool refuses a non-unique match), reverted by the inverse Edit; the restore receipt is the `git diff` over the file after the restore (the neutralized text is absent from it and the intended edit stands). No credential-like text, URL or PII appears in any capture; nothing was redacted. Every capture is far under 32 KiB.

Guarded-element set declared by the order: B1 (the rule's timeout sentence), B2 to B5 (the timeout sentence in each of the four agent files: implementer, check-runner, pilot, vet-drafter), B6 (the check-runner exception). Six elements, six neutralizations, six reds, six greens.

## B1. The rule's timeout sentence

- **Element and axis:** the inserted sentence of `PLAIN_COMMAND_RULE` in `plugins/superheroes/lib/command_refusals.py`. Axis: the rule asks for an explicit timeout on every Bash call, with the 600000 value.
- **Neutralization:** the three inserted lines were deleted (the `Run one plain command per call. "` line ended `... per call. A "` again):
  `"Pass an explicit `timeout` on every Bash call (`timeout: 600000` for a gate, a suite or "` / `"anything else that may run long), so the timeout hook never has to add one; a call that "` / `"names none can be refused, and that refusal names the one retry to make. A "` became `A "` on the preceding line.
- **Detector:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_plain_command_rule_content`.

**Raw red** (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_plain_command_rule_content ________________________

    def test_plain_command_rule_content():
        rule = CR.PLAIN_COMMAND_RULE
        # axis: the rule names the one-plain-command-per-call form, the script route and the three chain operators — see bite-proof record wo1_2458_plain_command
        for phrase in ("one plain command per call", "script file", "file-write tool", "`;`", "`&&`", "`||`",
                       "pipe into a loop", "read-only"):
            assert phrase in rule, phrase
        # axis: the rule prohibits the chain operators and the loop pipe, not merely names them — see bite-proof record wo1_2458_plain_command
        assert "Never chain commands with `;`, `&&` or `||`, and never pipe into a loop." in rule
        assert "Run one plain command per call." in rule
        for permission in ("may chain", "may pipe", "can chain", "may run several"):
            assert permission not in rule.lower(), permission
        # axis: the rule keeps the delete-rule carve-out and the no-file-write-tool sentence — see bite-proof record wo1_2458_plain_command
        assert "a delete never moves into the script" in rule
        assert "its own plain call" in rule
        assert "A seat with no file-write tool runs only single plain commands" in rule
        # axis: the single-command allowance excludes a heredoc and inline program code, naming the inline forms — see bite-proof record wo2_2458_heredoc_inline
        assert "That holds only for a command that carries no heredoc and no inline program code" in rule
        for inline in ("python3 -c", "node -e", "bash -c"):
            assert inline in rule, inline
        # axis: nothing a rule or fence refuses as its own call moves into a script — see bite-proof record wo2_2458_heredoc_inline
        assert ("nothing else a rule or a fence refuses as its own call (an install, a network call, a push) "
                "moves into a script to get past it") in rule
        # axis: the file-write carve-out stays one clause of the rule — see bite-proof record wo2_2458_heredoc_inline
        assert ("where the file-write rule binds you, a file that rule sends to the file tools is never "
                "written by the script") in rule
        # axis: the rule asks for an explicit timeout on every Bash call, with the 600000 value — see bite-proof record wo_b_2563_explicit_timeout
>       assert "Pass an explicit `timeout` on every Bash call" in rule
E       assert 'Pass an explicit `timeout` on every Bash call' in "Write every shell command in plain form, so that no command waits on an approval nobody is there to give: a chained, ...dispatched it. This rule prevents a refusal about a command's form; when one happens anyway, the stop rule governs it."

/home/user/wt-2563-b/plugins/superheroes/lib/tests/test_command_refusals.py:642: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_plain_command_rule_content
1 failed in 0.84s
```

- **Restore:** the inverse Edit put the three lines back.
- **Restore receipt** (`git diff plugins/superheroes/lib/command_refusals.py` after the restore):

```
@@ -30,7 +30,10 @@ STOP_RULE = (
 PLAIN_COMMAND_RULE = (
     "Write every shell command in plain form, so that no command waits on an approval nobody is "
     "there to give: a chained, looping or variable-dependent command cannot be pre-approved, and "
-    "it is held for the owner's approval even in auto mode. Run one plain command per call. A "
+    "it is held for the owner's approval even in auto mode. Run one plain command per call. "
+    "Pass an explicit `timeout` on every Bash call (`timeout: 600000` for a gate, a suite or "
+    "anything else that may run long), so the timeout hook never has to add one; a call that "
+    "names none can be refused, and that refusal names the one retry to make. A "
     "single command on its own, such as a read-only `git`, `gh api` or `cat`, stays fine as one "
```

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed in 0.77s
```

## B2 to B5. Each agent's timeout sentence

- **Elements and axis:** the sentence carrying ``explicit `timeout` `` and `` `timeout: 600000` `` in each of `plugins/superheroes/agents/implementer.md` (B2), `check-runner.md` (B3), `pilot.md` (B4) and `vet-drafter.md` (B5). Axis: every Bash-granted agent asks for an explicit timeout and names the 600000 value. The four elements are four files; each is neutralized on its own and each red names its file.
- **Neutralization (one file at a time):** ``an explicit `timeout` (`timeout: 600000` `` became ``an explicit `limit` (`timeout: 600000` `` in that one file.
- **Detector:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_every_bash_granted_agent_asks_for_an_explicit_timeout`.

The failing test body is identical in the four reds; it is quoted in full for B2 and the lines that differ (the offender) are quoted for B3 to B5, which are otherwise the same output line for line.

### B2 (implementer.md) raw red (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_every_bash_granted_agent_asks_for_an_explicit_timeout __________

    def test_every_bash_granted_agent_asks_for_an_explicit_timeout():
        granted, offenders = set(), []
        agents_dir = os.path.join(_PLUGIN_ROOT, "agents")
        for name in sorted(os.listdir(agents_dir)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(agents_dir, name), encoding="utf-8") as fh:
                frontmatter, body = _split_agent(fh.read())
            if not _bash_granted(frontmatter):
                continue
            granted.add(name[:-len(".md")])
            if "explicit `timeout`" not in body or "`timeout: 600000`" not in body:
                offenders.append(name)
        # axis: the Bash-granted set is not read as empty by a parser regression — see bite-proof record wo_b_2563_explicit_timeout
        assert granted >= {"check-runner", "implementer", "pilot", "vet-drafter"}
        # axis: every Bash-granted agent asks for an explicit timeout and names the 600000 value — see bite-proof record wo_b_2563_explicit_timeout
>       assert offenders == []
E       AssertionError: assert ['implementer.md'] == []
E         
E         Left contains one more item: 'implementer.md'
E         Use -v to get more diff

/home/user/wt-2563-b/plugins/superheroes/lib/tests/test_command_refusals.py:713: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_every_bash_granted_agent_asks_for_an_explicit_timeout
1 failed in 0.88s
```

- **Restore:** the inverse Edit (``an explicit `limit` `` back to ``an explicit `timeout` ``).
- **Restore receipt** (`git diff plugins/superheroes/agents/implementer.md`): the hunk shows only the intended addition, ``+follow it. Give every Bash call an explicit `timeout` (`timeout: 600000` for a gate, a suite or any`` / ``+long run).``
- **Raw green** (exit=0): `.   [100%]` then `1 passed in 0.77s`.

### B3 (check-runner.md) raw red (exit=1)

Same output as B2 except for these lines (the rest is the same test body, same summary line shape):

```
E       AssertionError: assert ['check-runner.md'] == []
E         
E         Left contains one more item: 'check-runner.md'
...
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_every_bash_granted_agent_asks_for_an_explicit_timeout
1 failed in 0.91s
```

- **Restore:** the inverse Edit.
- **Restore receipt** (`git diff plugins/superheroes/agents/check-runner.md`): the hunk shows the added line ``+  Give every Bash call an explicit `timeout` (`timeout: 600000` for a long run). You write no script. When`` (and the B6 exception lines, in place).
- **Raw green** (exit=0): `.   [100%]` then `1 passed in 0.89s`.

### B4 (pilot.md) raw red (exit=1)

Same output as B2 except for these lines:

```
E       AssertionError: assert ['pilot.md'] == []
E         
E         Left contains one more item: 'pilot.md'
...
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_every_bash_granted_agent_asks_for_an_explicit_timeout
1 failed in 1.11s
```

- **Restore:** the inverse Edit.
- **Restore receipt** (`git diff plugins/superheroes/agents/pilot.md`): ``+  Give every Bash call an explicit `timeout` (`timeout: 600000` for a long run).`` is the only change.
- **Raw green** (exit=0): `.   [100%]` then `1 passed in 0.94s`.

### B5 (vet-drafter.md) raw red (exit=1)

Same output as B2 except for these lines:

```
E       AssertionError: assert ['vet-drafter.md'] == []
E         
E         Left contains one more item: 'vet-drafter.md'
...
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_every_bash_granted_agent_asks_for_an_explicit_timeout
1 failed in 0.96s
```

- **Restore:** the inverse Edit.
- **Restore receipt** (`git diff plugins/superheroes/agents/vet-drafter.md`): ``+Give every Bash call an explicit `timeout` (`timeout: 600000` for a long run).`` is the only change.
- **Raw green** (exit=0): `.   [100%]` then `1 passed in 0.89s`.

## B6. The check-runner exception

- **Element and axis:** the exception appended to the `**A refused or denied command is a stop.**` bullet of `plugins/superheroes/agents/check-runner.md`. Axis: the stop bullet names the timeout hook's one re-issue with the 600000 value.
- **Neutralization:** the four exception lines (from ``The one exception is`` to ``A second refusal, or any other refusal, stays a stop.``) were deleted, leaving the bullet ending ``and what follows is the orchestrator's call.``
- **Detector:** `plugins/superheroes/lib/tests/test_command_refusals.py::test_check_runner_takes_the_timeout_route_once`.

**Raw red** (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_check_runner_takes_the_timeout_route_once ________________

    def test_check_runner_takes_the_timeout_route_once():
        with open(os.path.join(_PLUGIN_ROOT, "agents", "check-runner.md"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        start = next(i for i, ln in enumerate(lines) if ln.startswith("- **A refused or denied command is a stop.**"))
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("- **")), len(lines))
        bullet = "\n".join(lines[start:end])
        # axis: the check-runner's stop bullet names the timeout hook's one re-issue with the 600000 value — see bite-proof record wo_b_2563_explicit_timeout
>       assert "re-issue that same command once with `timeout: 600000`" in bullet
E       assert 're-issue that same command once with `timeout: 600000`' in "- **A refused or denied command is a stop.** Record the refusal in that command's capture and in\n  your report, and ...the whole build session (`SESSION_RULE`\n  in `lib/command_refusals.py`), and what follows is the orchestrator's call."

/home/user/wt-2563-b/plugins/superheroes/lib/tests/test_command_refusals.py:723: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_check_runner_takes_the_timeout_route_once
1 failed in 0.86s
```

- **Restore:** the inverse Edit put the exception back.
- **Restore receipt** (`git diff plugins/superheroes/agents/check-runner.md` after the restore):

```
-  in `lib/command_refusals.py`), and what follows is the orchestrator's call.
+  in `lib/command_refusals.py`), and what follows is the orchestrator's call. The one exception is
+  the plugin's timeout hook refusing a listed command only because the call named no `timeout`:
+  re-issue that same command once with `timeout: 600000`, and record the refusal and the re-issue in
+  that command's capture and in your report. A second refusal, or any other refusal, stays a stop.
```

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed in 0.98s
```

## What the proofs do not discriminate (named, not hidden)

- B6's neutralization removes the whole exception, so the red stops at the first assertion (the re-issue phrase). The second assertion of the same test, `"second refusal" in bullet`, never ran in that red and has **no red of its own**: a bullet that kept the re-issue phrase but dropped the second-refusal sentence is not covered by a run. Its protection is unverified by a red run; the order declared no neutralization for it.
- The agent-file check is a substring test on the exact phrase ``explicit `timeout` ``; it does not prove the sentence sits beside the plain-command lines, only that the agent body carries it.
- The B2 to B5 reds share one detector and one failure mode (the offender list names the file); each was proven with its own neutralization, none is a stand-in for another.
