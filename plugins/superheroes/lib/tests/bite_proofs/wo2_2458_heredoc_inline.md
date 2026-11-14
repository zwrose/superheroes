# Bite-proof record wo2_2458_heredoc_inline

Detector changed: `plugins/superheroes/lib/tests/test_command_refusals.py::test_plain_command_rule_content` (three new assertion groups, each with an `# axis:` comment naming this record). No credential-like text, URL or PII appears in any capture; nothing was redacted. The `...` inside the assertion lines is pytest's own truncation of a long repr.

Guarded-element set (the order named two neutralizations; the third assertion group is listed here too):

- A. the heredoc / inline-program sentence of `PLAIN_COMMAND_RULE` (axis: the single-command allowance excludes a heredoc and inline program code) — proven below.
- B. the "nothing else a rule or a fence refuses …" clause (axis: nothing a rule or fence refuses moves into a script) — proven below.
- C. the file-write carve-out clause (`where the file-write rule binds you, …`) — **unproven**: the order asked for no neutralization of it and it is an assertion on text that already existed, so no red run was spent on it. Its protection is unverified by a red run.

## A. Heredoc and inline-program sentence

- **Neutralization:** in `plugins/superheroes/lib/command_refusals.py`, the lines
  `"plain call. That holds only for a command that carries no heredoc and no inline program code "` /
  `"(`python3 -c`, `node -e`, `bash -c` and the like): file content and code go in a file written "` /
  `"with the file-write tool, and that file is then run or read by one plain call. Put "` /
  `"multi-step work (a loop, several file operations, anything that needs a "` were replaced by the single line
  `"plain call. Put multi-step work (a loop, several file operations, anything that needs a "` (the Edit tool).

**Raw red** (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_plain_command_rule_content ________________________
        # axis: the single-command allowance excludes a heredoc and inline program code, naming the inline forms — see bite-proof record wo2_2458_heredoc_inline
>       assert "That holds only for a command that carries no heredoc and no inline program code" in rule
E       assert 'That holds only for a command that carries no heredoc and no inline program code' in "Write every shell command in plain form, so that no command waits on an approval nobody is there to give: a chained, ...dispatched it. This rule prevents a refusal about a command's form; when one happens anyway, the stop rule governs it."

/home/user/wt-2458/plugins/superheroes/lib/tests/test_command_refusals.py:632: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_plain_command_rule_content
1 failed, 94 deselected in 1.18s
```

(The test body lines above the failing assertion are elided here; they are the unchanged earlier assertions of the same test.)

- **Restore:** inverse edit (the single line replaced by the four original lines).
- **Restore receipt** (Grep tool over `lib/command_refusals.py`, pattern `That holds only|multi-step work \(a loop`):

```
35:    "plain call. That holds only for a command that carries no heredoc and no inline program code "
38:    "multi-step work (a loop, several file operations, anything that needs a "
```

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed, 94 deselected in 1.07s
```

## B. "nothing else a rule or a fence refuses …" clause

- **Neutralization:** in `plugins/superheroes/lib/command_refusals.py`, the text
  `as the delete rule says, and nothing else "` / `"a rule or a fence refuses as its own call (an install, a network call, a push) moves into a "` / `"script to get past it; and where the "`
  was replaced by `as the delete rule says; and where the "` (the Edit tool), which is the pre-order wording.

**Raw red** (exit=1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_plain_command_rule_content ________________________
        # axis: nothing a rule or fence refuses as its own call moves into a script — see bite-proof record wo2_2458_heredoc_inline
>       assert ("nothing else a rule or a fence refuses as its own call (an install, a network call, a push) "
                "moves into a script to get past it") in rule
E       assert 'nothing else a rule or a fence refuses as its own call (an install, a network call, a push) moves into a script to get past it' in "Write every shell command in plain form, so that no command waits on an approval nobody is there to give: a chained, ...dispatched it. This rule prevents a refusal about a command's form; when one happens anyway, the stop rule governs it."

/home/user/wt-2458/plugins/superheroes/lib/tests/test_command_refusals.py:636: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_plain_command_rule_content
1 failed, 94 deselected in 1.08s
```

(The earlier assertions of the same test, including group A's, passed and are elided here.)

- **Restore:** inverse edit (the clause put back as three lines).
- **Restore receipt** (Grep tool over `lib/command_refusals.py`, pattern `delete rule says|nothing else|script to get past it`):

```
44:    "moves into the script, it stays its own plain call as the delete rule says, and nothing else "
46:    "script to get past it; and where the "
```

**Raw green** (exit=0):

```
.                                                                        [100%]
1 passed, 94 deselected in 1.00s
```
