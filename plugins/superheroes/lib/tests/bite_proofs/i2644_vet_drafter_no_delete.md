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

## Review round 1 (changed and added elements, at `d6b27d95`)

The review's round 1 changed two elements and added one: (D-move) now pins `mv -n`, so a move never replaces a file
already in the scratch folder; (D-noforce) now reads a force flag before or after the worktree path
(`git worktree remove[^\`]*?\s(?:--force|-f)\b` over the collapsed body); and (D-scratch) is new: the scratch folder is
listed among the places the drafter may write. (D-rule) and (D-remove) kept their assertions and their text, so their
proofs above stand. Same method, in a second detached probe worktree at `d6b27d95`, with the same `-k`; captures trimmed
the same way. Restore receipt for every element: `git status --porcelain` printed nothing after the inverse edit; the
probe worktree was then removed with a plain `git worktree remove`.

### (D-move) `mv -n`

- Neutralization: `` with `mv -n`, one `` became `` with `mv`, one ``.
- Raw red:

```
E       AssertionError: vet-drafter body no longer names the move into its scratch folder as a clean-up
1 failed, 5 deselected in 0.21s
```

- Raw green: `1 passed, 5 deselected in 4.92s`

### (D-scratch) the scratch folder is a place the drafter may write

- Guarded element and axis: the bullet `**The scratch folder**, \`<draft directory>/scratch/\`, which you may create with
  \`mkdir -p\``. Axis: the move has a destination the write rules allow.
- Neutralization: the whole two-line bullet removed.
- Raw red:

```
E       AssertionError: vet-drafter body no longer lists the scratch folder among the places it may write
1 failed, 5 deselected in 0.22s
```

- Raw green: `1 passed, 5 deselected in 0.22s`

### (D-noforce) a force flag in any place

- Neutralization 1 (flag after the path, the spelling the reviewer named): the worktree bullet regained
  ``, and remove it with `git worktree remove ./wt-1 --force` ``.
- Raw red 1:

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git worktree remove ./wt-1 --force']
1 failed, 5 deselected in 0.20s
```

- Neutralization 2: the same clause as `git worktree remove --force`. Raw red 2:

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git worktree remove --force']
1 failed, 5 deselected in 0.29s
```

- Neutralization 3: the same clause as `git worktree remove -f wt-1`. Raw red 3:

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git worktree remove -f']
1 failed, 5 deselected in 0.23s
```

- Restore: clause removed by the inverse edit. Raw green: `1 passed, 5 deselected in 0.18s`

## Review round 2 (changed and added elements, at `9e692fad`)

Round 2 changed two elements and added one: (D-scratch) now reads only the `## Where you may write` list up to
`Nothing else.`, so the bullet counts only inside the write allowlist; (D-noforce) now also reads git's `-C <path>` and
`-c <k=v>` before `worktree` (`git(?:\s+-[Cc]\s+\S+)*\s+worktree\s+remove[^\`]*?\s(?:--force|-f)\b`); and (D-ignored) is
new: the drafter runs `git status --porcelain --untracked-files=all --ignored` before the plain removal, because git
removes ignored files with a clean worktree. Same method, in a detached probe worktree at `9e692fad`; restore receipt for
every element: `git status --porcelain` printed nothing after the inverse edit; the probe worktree was then removed with
a plain `git worktree remove`.

### (D-scratch) relocation, the spelling the reviewer named

- Neutralization: the scratch-folder bullet moved, unchanged, from the write allowlist to just below "You clean up in two
  ways only:".
- Raw red (the long repr of the allowlist slice is elided):

```
E       AssertionError: vet-drafter's `Where you may write` list no longer names the scratch folder
1 failed, 5 deselected in 0.24s
```

- Raw green: `1 passed, 5 deselected in 0.23s`

### (D-ignored) ignored files listed first

- Neutralization: `` `git status --porcelain --untracked-files=all --ignored` `` became `` `git status --porcelain` ``.
- Raw red:

```
E       AssertionError: vet-drafter body no longer has the drafter list ignored files before removing its worktree
1 failed, 5 deselected in 0.20s
```

- Raw green: `1 passed, 5 deselected in 0.19s`

### (D-noforce) with git's `-C`, and the plain form again under the wider pattern

- Neutralization 1: the worktree bullet regained ``, and remove it with `git -C ./repo worktree remove ./wt-1 --force` ``.

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git -C ./repo worktree remove ./wt-1 --force']
1 failed, 5 deselected in 0.19s
```

- Neutralization 2: the same clause as `git worktree remove --force`.

```
E       AssertionError: vet-drafter body offers a forced worktree removal: ['git worktree remove --force']
1 failed, 5 deselected in 0.20s
```

- Restore: clause removed by the inverse edit. Raw green: `1 passed, 5 deselected in 0.19s`

## Not covered

The test pins words, not behaviour: it cannot show that a dispatched vet-drafter obeys the rule, and nothing in the
plugin checks that it did. The advisor's check after a drafter returns (`skills/showrunner/reference/vetting.md`
§ Parallel vets, "Check what the drafter left") reads the PR, the worktree list and the advisor's checkout status, so it
finds work left behind; a drafter that deleted a file it made and then removed a clean worktree would pass it unseen.
Whether a drafter deleted anything is unverified by any check.
