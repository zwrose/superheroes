# Bite-proof record: i2644_vet_drafter_no_delete

Detector: `test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves` in
`plugins/superheroes/lib/tests/test_vet_drafter_agent.py`, which pins the vet-drafter agent file's never-delete rule and
its two allowed clean-up moves (#2644).

Guarded-element set, declared before review (light lane, orchestrator-typed; carried in the reviewer's dispatch):
(D-rule), (D-move), (D-remove), (D-noforce). No equivalence class is used; each element has its own neutralization and its
own red.

Every run was made by the builder in a detached probe worktree at `9c42ff0f`, each neutralization a targeted edit to
`plugins/superheroes/agents/vet-drafter.md` through the edit tool, undone by the inverse edit. Command for every run, from
the probe worktree's own `scripts/pinned-python` with `-c <probe>/pytest.ini --rootdir <probe>`:
`pytest plugins/superheroes/lib/tests/test_vet_drafter_agent.py -q -k test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves`.
Restore receipt for every element: `git status --porcelain` on the probe worktree printed nothing after the inverse edit.
The probe worktree was then removed with a plain `git worktree remove`.

Captures are trimmed to the assertion lines and the summary line; the `UV_NATIVE_TLS` deprecation warning, the echoed
test source and the long repr of the collapsed agent body are elided. Nothing in them is a secret, token, private URL or
personal detail.

## (D-rule) the never-delete rule stands as its bold sentence

- Guarded element and axis: the `**You never delete a file.**` sentence. Axis: the rule is stated in the agent file.
- Neutralization: `**You never delete a file.** No \`rm\`` became `You never delete a file. No \`rm\``.
- Raw red:

```
E       AssertionError: vet-drafter body no longer states the never-delete rule
FAILED .claude/worktrees/probe-2644/plugins/superheroes/lib/tests/test_vet_drafter_agent.py::test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves
1 failed, 5 deselected in 0.20s
```

- Restore: inverse edit; `git status --porcelain` printed nothing.
- Raw green:

```
.                                                                        [100%]
1 passed, 5 deselected in 0.24s
```

## (D-move) the move into the scratch folder stays named

- Guarded element and axis: ``into `<draft directory>/scratch/` with `mv` ``. Axis: the first allowed clean-up is a move.
- Neutralization: `` with `mv` `` removed from that phrase.
- Raw red:

```
E       AssertionError: vet-drafter body no longer names the move into its scratch folder as a clean-up
FAILED .claude/worktrees/probe-2644/plugins/superheroes/lib/tests/test_vet_drafter_agent.py::test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves
1 failed, 5 deselected in 0.21s
```

- Restore: inverse edit; `git status --porcelain` printed nothing.
- Raw green:

```
.                                                                        [100%]
1 passed, 5 deselected in 0.20s
```

## (D-remove) the plain worktree removal stays named

- Guarded element and axis: ``git worktree remove <draft directory>/wt-<ordinal>`, without `--force` ``. Axis: the second
  allowed clean-up is a worktree removal without the force flag.
- Neutralization: `` without `--force`, `` removed from that phrase.
- Raw red:

```
E       AssertionError: vet-drafter body no longer names the plain `git worktree remove` without `--force`
FAILED .claude/worktrees/probe-2644/plugins/superheroes/lib/tests/test_vet_drafter_agent.py::test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves
1 failed, 5 deselected in 0.21s
```

- Restore: inverse edit; `git status --porcelain` printed nothing.
- Raw green:

```
.                                                                        [100%]
1 passed, 5 deselected in 0.19s
```

## (D-noforce) no forced worktree removal is offered, in either flag form

- Guarded element and axis: the `re.findall(r"git worktree remove (?:--force|-f)\b", body)` check. Axis: the agent file
  never offers a forced removal, the line this change took out.
- Neutralization 1 (long flag): the first bullet of "Where you may write" regained the removed clause
  ``, and remove it with `git worktree remove --force` ``.
- Raw red 1:

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git worktree remove --force']
FAILED .claude/worktrees/probe-2644/plugins/superheroes/lib/tests/test_vet_drafter_agent.py::test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves
1 failed, 5 deselected in 0.29s
```

- Neutralization 2 (short flag): the same clause with `-f` in place of `--force`.
- Raw red 2:

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git worktree remove -f']
FAILED .claude/worktrees/probe-2644/plugins/superheroes/lib/tests/test_vet_drafter_agent.py::test_vet_drafter_never_deletes_and_names_its_two_clean_up_moves
1 failed, 5 deselected in 0.20s
```

- Restore: inverse edit, clause removed; `git status --porcelain` printed nothing.
- Raw green:

```
.                                                                        [100%]
1 passed, 5 deselected in 0.20s
```

## Not covered

The test pins words, not behaviour: it cannot show that a dispatched vet-drafter obeys the rule. That is checked by the
advisor after each drafter returns (`skills/showrunner/reference/vetting.md` § Parallel vets, "Check what the drafter
left").
