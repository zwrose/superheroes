# Bite-proof record — the plain-command rule has one home and reaches every command-running seat (#2458)

Detector file: `plugins/superheroes/lib/tests/test_command_refusals.py` (section `# --- the plain-command rule (#2458) ---`), unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one shipped file, restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2458 -m pytest plugins/superheroes/lib/tests/test_command_refusals.py -q -p no:cacheprovider -k <test name>`, one test each. Captures are whole, apart from the `UV_NATIVE_TLS` deprecation warning line the launcher prints first on every run, which is dropped here; the `exit=` line is the tool's reported exit code (1 for a red, 0 for a green). The `...` inside the assertion lines of entry B is pytest's own truncation of a long repr, not an edit. No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted.

The guarded elements (declared by the order, WO-1 of #2458): A the agent census (every Bash-granted agent cites the rule), B the write-prompt census (the staged write prompt carries the rule once, after the delete rule), C the one-home test (no sentence of the rule is copied outside `lib/command_refusals.py`). Not neutralized, listed unproven: the native-preamble census (`test_census_plain_command_rule_native_preamble`), the session-surface citation test (`test_plain_command_rule_cited_by_session_surfaces`), the rule-content test (`test_plain_command_rule_content`), the other-rules-unchanged test and the Bash-grant parser cases (`test_bash_grant_parser`): the order named bite-proofs for (a), (b) and (c) only. The agent census's floor assertion (`granted >= {...}`) was not neutralized either.

## A. The agent census (`test_every_bash_granted_agent_cites_the_plain_command_rule`)

- **Axis:** every agent whose frontmatter grants Bash (no `tools:` line, `*`, or a `Bash` / `Bash(...)` entry) cites `` `PLAIN_COMMAND_RULE` `` and `lib/command_refusals.py` in its body.
- **Detector:** `test_command_refusals.py::test_every_bash_granted_agent_cites_the_plain_command_rule`.
- **Neutralization:** in `plugins/superheroes/agents/pilot.md`, `The rule (` + `` `PLAIN_COMMAND_RULE` `` + ` in` became `The rule (` + `` `PLAIN_RULE` `` + ` in` (pilot has no `tools:` line, so it is Bash-granted by the all-tools edge).

**Raw red** (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_every_bash_granted_agent_cites_the_plain_command_rule __________

    def test_every_bash_granted_agent_cites_the_plain_command_rule():
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
            if "`PLAIN_COMMAND_RULE`" not in body or "lib/command_refusals.py" not in body:
                offenders.append(name)
        # axis: the Bash-granted set is not read as empty by a parser regression — see bite-proof record wo1_2458_plain_command
        assert granted >= {"check-runner", "implementer", "pilot", "vet-drafter"}
        # axis: every Bash-granted agent cites the plain-command rule by name and home — see bite-proof record wo1_2458_plain_command
>       assert offenders == []
E       AssertionError: assert ['pilot.md'] == []
E         
E         Left contains one more item: 'pilot.md'
E         Use -v to get more diff

/home/user/wt-2458/plugins/superheroes/lib/tests/test_command_refusals.py:676: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_every_bash_granted_agent_cites_the_plain_command_rule
1 failed, 94 deselected in 0.96s
exit=1
```

- **Restore:** inverse edit (`` `PLAIN_RULE` `` back to `` `PLAIN_COMMAND_RULE` ``).
- **Restore receipt** (read back by the Grep tool, `PLAIN_COMMAND_RULE` over `agents/pilot.md`):

```
25:  `;`, `&&` or `||` and never a pipe into a loop. The rule (`PLAIN_COMMAND_RULE` in
```

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed, 94 deselected in 1.15s
exit=0
```

## B. The write-prompt census (`test_census_plain_command_rule_write_prompt`)

- **Axis:** the staged write prompt (`engine_dispatch.py`) carries `PLAIN_COMMAND_RULE` exactly once, after `DELETE_RULE`.
- **Detector:** `test_command_refusals.py::test_census_plain_command_rule_write_prompt`.
- **Neutralization:** in `plugins/superheroes/lib/engine_dispatch.py` (the staged-prompt composition), `"\n\n" + command_refusals.PLAIN_COMMAND_RULE + "\n\n" + contract)` became `"\n\n" + contract)`.

**Raw red** (exit=1; the `...` inside the assertion lines is pytest's own truncation of a long repr):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_census_plain_command_rule_write_prompt __________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_census_plain_command_rule0')

    def test_census_plain_command_rule_write_prompt(tmp_path):
        wt, _main = _linked_worktree(tmp_path)
        prompt_path = _prompt(tmp_path, "Implement exactly the assigned work order.\n")
        fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
        res = _dispatch_write(tmp_path, fake, cwd=wt, prompt_path=prompt_path)
        assert res["ok"] is True
        with open(os.path.join(str(tmp_path / "run"), ED.PROMPT_NAME), encoding="utf-8") as fh:
            staged = fh.read()
        # axis: the plain-command rule reaches every dispatch-write order exactly once, after the delete rule — see bite-proof record wo1_2458_plain_command
>       assert staged.count(CR.PLAIN_COMMAND_RULE) == 1
E       assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x27cf7550>("Write every shell command in plain form, so that no command waits on an approval nobody is there to give: a chained, ...dispatched it. This rule prevents a refusal about a command's form; when one happens anyway, the stop rule governs it.")
E        +    where <built-in method count of str object at 0x27cf7550> = 'Implement exactly the assigned work order.\n\nStop only a process you started yourself, and only by its PID, never by...e stop rule in this prompt defines it, one entry each (command, refusedBy, hook, route, next); [] when you met none.\n'.count
E        +    and   "Write every shell command in plain form, so that no command waits on an approval nobody is there to give: a chained, ...dispatched it. This rule prevents a refusal about a command's form; when one happens anyway, the stop rule governs it." = CR.PLAIN_COMMAND_RULE

/home/user/wt-2458/plugins/superheroes/lib/tests/test_command_refusals.py:644: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_plain_command_rule_write_prompt
1 failed, 94 deselected in 1.36s
exit=1
```

- **Restore:** inverse edit (`"\n\n" + contract)` back to `"\n\n" + command_refusals.PLAIN_COMMAND_RULE + "\n\n" + contract)`).
- **Restore receipt** (read back by the Grep tool, `PLAIN_COMMAND_RULE` over `lib/engine_dispatch.py`):

```
6863:                   + "\n\n" + command_refusals.PLAIN_COMMAND_RULE + "\n\n" + contract)
```

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed, 94 deselected in 1.06s
exit=0
```

## C. The one-home test (`test_plain_command_rule_has_one_home`)

- **Axis:** no sentence of the rule appears in any shipped plugin file other than `lib/command_refusals.py`; prose surfaces cite, never copy (CONVENTIONS §11.4).
- **Detector:** `test_command_refusals.py::test_plain_command_rule_has_one_home`.
- **Neutralization:** in `plugins/superheroes/agents/check-runner.md`, an indented line `Run one plain command per call.` was added under the new bullet (one sentence of the rule pasted in).

**Raw red** (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_plain_command_rule_has_one_home _____________________

    def test_plain_command_rule_has_one_home():
        # A copy of any sentence anywhere in the shipped plugin outside its home is a second copy;
        # prose consumers cite the home instead. TRANSITION.md and CHANGELOG.md are history and are skipped.
        assert len(_PLAIN_COMMAND_SENTENCES) >= 8
        home = os.path.join("lib", "command_refusals.py")
        copies = []
        for root, dirs, files in os.walk(_PLUGIN_ROOT):
            dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git")]
            for name in files:
                if not name.endswith((".py", ".md", ".json", ".txt")):
                    continue
                if name in ("TRANSITION.md", "CHANGELOG.md"):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, _PLUGIN_ROOT)
                if rel == home:
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    raw = fh.read()
                # drop the quote-gap between adjacent string literals, then collapse whitespace
                body = " ".join(re.sub(r'"\s*"', "", raw).split())
                for sentence in _PLAIN_COMMAND_SENTENCES:
                    if sentence in body:
                        copies.append((rel, sentence))
        # axis: no sentence of the plain-command rule is hand-copied outside lib/command_refusals.py — see bite-proof record wo1_2458_plain_command
>       assert copies == []
E       AssertionError: assert [('agents/che...nd per call')] == []
E         
E         Left contains one more item: ('agents/check-runner.md', 'Run one plain command per call')
E         Use -v to get more diff

/home/user/wt-2458/plugins/superheroes/lib/tests/test_command_refusals.py:722: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_plain_command_rule_has_one_home
1 failed, 94 deselected in 1.28s
exit=1
```

- **Restore:** inverse edit (the pasted `Run one plain command per call.` line removed).
- **Restore receipt** (`git diff plugins/superheroes/agents/check-runner.md` after the restore shows only the new bullet, with no pasted line; its added lines are the five lines of the bullet beginning `- **Run each listed command as one plain call.**` and ending `that is itself a chain is an order defect you report, not a command you rewrite.`).

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed, 94 deselected in 1.21s
exit=0
```
