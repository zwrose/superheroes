# Bite-proof record — WO-B (C1-L3: review-code's read-only path removed)

**Detectors.** `test_review_only_removed_c1l3.py` (new) and the new test in
`test_review_code_branch_guard.py`. Guarded-element set as declared: B1–B10 below.

**Method.** One targeted `Edit` of the guarded doc text per element (never of a test), the detector
unedited, one `-k` selection per run, then the inverse `Edit` and a green run of the same selection.
Command for every run: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-b -m pytest
<file> -k <selection> -q`. The `warning: The UV_NATIVE_TLS ...` line the launcher prints first is
not the test's and is left out of the captures below. Nothing below is redacted: the captures hold
no secret, token or private URL. Every red was read at the tail of its output (`| tail -N`): B1, B2,
B4, B5, B6, B7, B8, B9 and B10 reds are whole; the B3 red is the last 40 lines only (the first of its
three failures is cut off at the head; its summary lines are whole).

Files touched by the neutralizations: `skills/review-code/SKILL.md` (B1, B2, B3, B7, B8),
`skills/review-code/reference/setup.md` (B4, B5, B6, B10), and a created-then-removed
`skills/review-code/reference/headless-presentation.md` (B9). Each was restored by the inverse edit
(B9: the stub file removed). No `git checkout`, `git restore`, `git reset` or `git stash` was used.

Outside the declared set, with no neutralization run (so unproven by this record):
`test_skill_has_no_read_only_section_and_no_review_path_variable` (the `## Read-Only Path` heading
leg and the `REVIEW_PATH` leg), and `test_a_removed_flag_among_other_arguments_is_still_answered`.

---

## B1. `--review-only` is answered and nothing runs

- Axis: the removed-flags block names `--review-only`.
- Neutralization (`SKILL.md`): `    --review-only|--post)` became `    --post)`.
- Red (`-k test_review_only_flag_is_answered`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_review_only_flag_is_answered_and_runs_nothing ______________
    def test_review_only_flag_is_answered_and_runs_nothing(tmp_path):
        code, out, err, ran_after = _run_removed_flags_block(tmp_path, "--review-only")
>       assert code == 1, (out, err)
E       AssertionError: ('', '')
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_review_only_removed_c1l3.py::test_review_only_flag_is_answered_and_runs_nothing
1 failed, 14 deselected in 0.26s
```

- Restore: the inverse edit. Restored line (`SKILL.md:35`): `    --review-only|--post)`.
- Green: `1 passed, 14 deselected in 0.34s`.

## B2. `--post` is answered and nothing runs

- Axis: the removed-flags block names `--post`.
- Neutralization (`SKILL.md`): `    --review-only|--post)` became `    --review-only)`.
- Red (`-k test_post_flag_is_answered`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_post_flag_is_answered_and_runs_nothing __________________
    def test_post_flag_is_answered_and_runs_nothing(tmp_path):
        code, out, err, ran_after = _run_removed_flags_block(tmp_path, "--post")
>       assert code == 1, (out, err)
E       AssertionError: ('', '')
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_review_only_removed_c1l3.py::test_post_flag_is_answered_and_runs_nothing
1 failed, 14 deselected in 0.55s
```

- Restore: the inverse edit. Restored line (`SKILL.md:35`): `    --review-only|--post)`.
- Green: `1 passed, 14 deselected in 0.21s`.

## B3. ordinary arguments pass through

- Axis: the block exits 0 and prints nothing on arguments that are not removed flags.
- Neutralization (`SKILL.md`): `    --review-only|--post)` became `    *)`.
- Red (`-k test_ordinary_arguments_pass_through`; the last 40 lines — the head, holding the first
  failure `[pr 12 --focus x]`, is cut off):

```
E       AssertionError: ('review-code: pr was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without pr.
E         ', '')
E       assert 1 == 0
_________________ test_ordinary_arguments_pass_through[branch] _________________
E       AssertionError: ('review-code: branch was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without branch.
E         ', '')
E       assert 1 == 0
_______ test_ordinary_arguments_pass_through[--result-file /tmp/r.json] ________
E       AssertionError: ('review-code: --result-file was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without --result-file.
E         ', '')
E       assert 1 == 0
FAILED ...::test_ordinary_arguments_pass_through[pr 12 --focus x]
FAILED ...::test_ordinary_arguments_pass_through[branch]
FAILED ...::test_ordinary_arguments_pass_through[--result-file /tmp/r.json]
3 failed, 1 passed, 11 deselected in 0.28s
```

- Restore: the inverse edit. Restored line (`SKILL.md:35`): `    --review-only|--post)`.
- Green: `4 passed, 11 deselected in 0.24s`.

## B4. setup refuses when the resolver reports a refusal

- Axis: the refusal line reads `.verifyRefusal.message` and refuses on it even when a command is set.
- Neutralization (`setup.md:175`): `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] ||` became
  `[ -z "$NO_VERIFY" ] || [ -n "$VERIFY_CMD" ] && [ -n "$VERIFY_CMD" ] ||` (the refusal term has no effect).
- Red (`-k test_setup_refuses_when_the_resolver_reports_a_refusal`):

```
.F                                                                       [100%]
_ test_setup_refuses_when_the_resolver_reports_a_refusal[command-but-refusal-reported] _
>       assert code == 1, (out, err)
E       AssertionError: ('pytest -q', '')
E       assert 0 == 1
FAILED ...::test_setup_refuses_when_the_resolver_reports_a_refusal[command-but-refusal-reported]
1 failed, 1 passed, 13 deselected in 0.31s
```

- Restore: the inverse edit. Restored line start (`setup.md:175`): `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] || { [ -n "$NO_VERIFY" ] || NO_VERIFY="Code review is not available ...`.
- Green: `2 passed, 13 deselected in 0.29s`.

## B5. setup refuses on an empty `{}` resolver result

- Axis: the refusal line refuses when the command is empty and the resolver reported nothing.
- Neutralization (`setup.md:175`): `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] ||` became
  `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] || [ -z "$NO_VERIFY" ] ||` (the command term has no effect).
- Red (`-k test_setup_refuses_when_the_resolver_result_is_empty`):

```
F                                                                        [100%]
_____________ test_setup_refuses_when_the_resolver_result_is_empty _____________
        code, out, err = _run_verify_refusal("{}")
>       assert code == 1, (out, err)
E       AssertionError: ('', '')
E       assert 0 == 1
FAILED ...::test_setup_refuses_when_the_resolver_result_is_empty
1 failed, 14 deselected in 0.30s
```

- Restore: the inverse edit. Restored line (`setup.md:175`), read back whole:
  `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] || { [ -n "$NO_VERIFY" ] || NO_VERIFY="Code review is not available until a verify command is set. Code review needs a command that verifies this project's code; set one with /superheroes:configure."; echo "review-code: $NO_VERIFY" >&2; exit 1; }`
- Green: `1 passed, 14 deselected in 0.30s`.

## B6. setup passes a configured command

- Axis: a configured command with `verifyRefusal: null` is not refused.
- Neutralization (`setup.md:175`): `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] ||` became
  `[ -z "$NO_VERIFY" ] && [ -n "$VERIFY_CMD" ] && false ||` (always refuses).
- Red (`-k test_setup_passes_a_configured_command`):

```
F                                                                        [100%]
____________________ test_setup_passes_a_configured_command ____________________
        code, out, err = _run_verify_refusal('{"verifyCommand": "pytest -q", "verifyRefusal": null}')
>       assert code == 0, (out, err)
E       AssertionError: ('', "review-code: Code review is not available until a verify command is set. Code review needs a command that verifies this project's code; set one with /superheroes:configure.
E         ")
E       assert 1 == 0
FAILED ...::test_setup_passes_a_configured_command
1 failed, 14 deselected in 0.27s
```

- Restore: the inverse edit. Restored line read back whole, as quoted under B5.
- Green: `1 passed, 14 deselected in 0.28s`.

## B7. the guard's not-supported line

- Axis: the guard's second refusal line says the review is not supported and names no other way.
- Neutralization (`SKILL.md:97`): the second `echo` became the pre-removal text
  `  echo "Otherwise check out the branch, or re-run with --review-only (read-only terminal)."; exit 1`.
- Red (`test_review_code_branch_guard.py -k test_refusal_says_not_supported`):

```
    def test_refusal_says_not_supported_and_offers_no_read_only_path(git_world, shipped_guard):
        ...
        assert code == 1
        text = _combined_output(out, err)
>       assert "is not supported" in text
E       assert 'is not supported' in "Code review runs only on this project's own PR, from the PR's branch 'feature-pr' (currently on '<detached HEAD>'). A...19aa259ad3484ed247abfa44a83b5').\nOtherwise check out the branch, or re-run with --review-only (read-only terminal).\n"
FAILED ...test_review_code_branch_guard.py::test_refusal_says_not_supported_and_offers_no_read_only_path
1 failed, 26 deselected in 0.35s
```

- Restore: the inverse edit. Restored line (`SKILL.md:97`): `  echo "If this is your PR, check out its branch and run again. Reviewing a PR that was not built in this project is not supported."; exit 1`.
- Green: `1 passed, 26 deselected in 0.41s`.

## B8. absence census, `--review-only` leg

- Axis: no file under `skills/review-code/` names `--review-only` outside the removal notice.
- Neutralization (`SKILL.md:24`): `runs the auto-fix loop.` became `runs the auto-fix loop unless combined with `--review-only`.`.
- Red (`-k test_no_file_names_the_review_only_flag`):

```
F                                                                        [100%]
______ test_no_file_names_the_review_only_flag_outside_the_removal_notice ______
>       assert hits == []
E       AssertionError: assert ['skills/revi...ode/SKILL.md'] == []
E         Left contains one more item: 'skills/review-code/SKILL.md'
FAILED ...::test_no_file_names_the_review_only_flag_outside_the_removal_notice
1 failed, 14 deselected in 0.30s
```

- Restore: the inverse edit. Restored line (`SKILL.md:24`): `| `/superheroes:review-code branch` / `pr <N>` | Force branch or PR mode; runs the auto-fix loop.   ...|`.
- Green: `1 passed, 14 deselected in 4.28s`.

## B9. absence census, `headless-presentation.md` leg

- Axis: `skills/review-code/reference/headless-presentation.md` does not exist.
- Neutralization: created the file with one line, `neutralization stub`.
- Red (`-k test_the_headless_presentation_contract_file_is_gone`):

```
F                                                                        [100%]
_____________ test_the_headless_presentation_contract_file_is_gone _____________
>       assert not os.path.exists(HEADLESS_MD)
E       AssertionError: assert not True
E        +  where True = <function exists at 0x7efc2c523ec0>('/home/user/wt-2207-b/plugins/superheroes/skills/review-code/reference/headless-presentation.md')
FAILED ...::test_the_headless_presentation_contract_file_is_gone
1 failed, 14 deselected in 0.24s
```

- Restore: removed the stub file. Restore receipt: a glob of `skills/review-code/reference/*` lists
  `verification-pass.md`, `synthesis-pass.md`, `auto-fix-loop.md`, `review-record.md`,
  `round-driver.md`, `setup.md` and no `headless-presentation.md`.
- Green: `1 passed, 14 deselected in 0.24s`.

## B10. absence census, `mode:` leg

- Axis: no file under `skills/review-code/` names `mode: review-only` or `mode: unverified`.
- Neutralization (`setup.md:185`): inserted `A profile with `mode: unverified` skips the gate. ` before `With no verify command the review refuses here,`.
- Red (`-k test_no_file_names_a_review_only_or_unverified_verify_mode`):

```
F                                                                        [100%]
__________ test_no_file_names_a_review_only_or_unverified_verify_mode __________
>       assert hits == []
E       AssertionError: assert ['skills/revi...nce/setup.md'] == []
E         Left contains one more item: 'skills/review-code/reference/setup.md'
FAILED ...::test_no_file_names_a_review_only_or_unverified_verify_mode
1 failed, 14 deselected in 0.24s
```

- Restore: the inverse edit (the inserted sentence removed). Restore receipt: a search for
  `With no verify command the review refuses` finds the sentence at `setup.md:185` (the matching
  line was too long for the tool to display, so its start of line was not re-read).
- Green: `1 passed, 14 deselected in 0.20s`.

---

# Addendum — WO-E (argument boundaries in the removed-flags check)

**Detectors.** The new and changed tests in `test_review_only_removed_c1l3.py`. Guarded-element set as
declared: B11–B14. Method as above (one targeted `Edit` of the shipped block in `SKILL.md`, the tests
unedited, one `-k` selection per run, the inverse `Edit`, a green run of the same selection); command
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-e -m pytest <file> -k <selection> -q`.
Nothing is redacted: the captures hold no secret, token or private URL. The B11 red is the last 40
lines of its output; the B12, B13 and B14 reds are the `E` lines, `FAILED` lines and summary line of
their output (a `grep -E` over the run's output, so the tracebacks between them are not shown); the
greens are whole minus the launcher's `UV_NATIVE_TLS` warning line. After the four proofs
`SKILL.md` was read back (lines 32–55, the block as shipped) and `git status --porcelain` listed it
modified together with the two other files this order changes, and no residue of a neutralization.

## B11. a removed flag inside a quoted `--focus` value is not refused

- Axis: the block tokenizes with the quoting kept (`shlex.split`), so a quoted value is one word.
- Neutralization (`SKILL.md`): `    words = shlex.split(text)` became `    words = text.split()`
  (the old whitespace split).
- Red (`-k "inside_an_argument_value and (double-quoted or single-quoted or post-in-focus)"`; tail):

```
E       AssertionError: ('review-code: --post was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without --post.
E         ', '')
E       assert 1 == 0
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[double-quoted]
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[single-quoted]
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[post-in-focus]
3 failed, 26 deselected in 0.39s
```

- Restore: the inverse edit. Restore receipt (`SKILL.md:37`): `    words = shlex.split(text)`.
- Green: `3 passed, 26 deselected in 2.80s`.

## B12. the value after `--focus` / `--result-file`, and the `--focus=<value>` form, are not read as flags

- Axis: the skip rule governs a flag-shaped value; a flag name inside a single token is not a flag.
- Neutralization (`SKILL.md`, two edits in one run): `        skip = True` became `        pass` (the skip
  rule has no effect) and `    elif word in ("--review-only", "--post"):` became
  `    elif any(flag in word for flag in ("--review-only", "--post")):` (a flag name anywhere in a word is
  read). Why not the old whitespace split: it keeps `--focus=--review-only` and `'/tmp/--post.json'` as
  single words that are not equal to a flag, so it leaves those two cases green; the neutralization
  above is what turns them red.
- Red (`-k "inside_an_argument_value and (focus-equals or result-file-quoted or flag-shaped)"`):

```
FFFF                                                                     [100%]
E       AssertionError: ('review-code: --focus=--review-only was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without --focus=--review-only.
E       AssertionError: ('review-code: /tmp/--post.json was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without /tmp/--post.json.
E       AssertionError: ('review-code: --review-only was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without --review-only.
E       AssertionError: ('review-code: --post was removed. Code review runs only as its one review-and-fix loop, so nothing ran. Run /superheroes:review-code without --post.
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[focus-equals]
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[result-file-quoted]
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[flag-shaped-focus-value]
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[flag-shaped-result-file-value]
4 failed, 25 deselected in 0.45s
```

- Restore: the inverse edits. Restore receipt (`SKILL.md:44-47`): `    elif word in ("--focus", "--result-file"):`,
  `        skip = True`, `    elif word in ("--review-only", "--post"):`, `        print(word)`.
- Green: `4 passed, 25 deselected in 0.37s`.
- Not separated: this one run holds two neutralizations; which of the two turns which case red was
  not measured case by case.

## B13. the unbalanced-quote fallback does not refuse the review, and still reads the other words

- Axis: a string `shlex.split` cannot tokenize falls back to a whitespace split.
- Neutralization (`SKILL.md:38`): `except ValueError:` became `except KeyError:` (the tokenizing
  error is no longer caught).
- Red (`-k unbalanced`):

```
FFF                                                                      [100%]
E       AssertionError: ('', 'Traceback (most recent call last):
E           File "<string>", line 5, in <module>
E           File "/root/.local/share/uv/python.../shlex.py", line 191, in read_token
E             raise ValueError("No closing quotation")
E         ValueError: No closing quotation
E         ')
E       assert 0 == 1
FAILED ...::test_a_removed_flag_inside_an_argument_value_is_not_a_flag[unbalanced-quote]
FAILED ...::test_a_removed_flag_beside_a_value_is_still_answered[unbalanced-quote-beside-flag]
FAILED ...::test_a_removed_flag_beside_a_value_is_still_answered[unbalanced-quote-beside-post]
3 failed, 26 deselected in 0.39s
```

- Restore: the inverse edit. Restore receipt (`SKILL.md:38`): `except ValueError:`.
- Green: `3 passed, 26 deselected in 0.36s`.

## B14. the test reads the block's own exit status

- Axis: `_run_removed_flags_block` returns the block's exit code, not the sentinel's.
- Neutralization (`SKILL.md`): a line `false` appended after the block's last line (`fi`; the block
  has no `done` now), the vet's probe.
- Red (`-k test_ordinary_arguments_pass_through`):

```
FFFF                                                                     [100%]
E       AssertionError: ('', '')
E       assert 1 == 0
FAILED ...::test_ordinary_arguments_pass_through[pr 12 --focus x]
FAILED ...::test_ordinary_arguments_pass_through[branch]
FAILED ...::test_ordinary_arguments_pass_through[--result-file /tmp/r.json]
FAILED ...::test_ordinary_arguments_pass_through[]
4 failed, 25 deselected in 0.43s
```

- Restore: the inverse edit (the `false` line removed). Restore receipt (`SKILL.md:32-55`, read back
  whole): the block ends `  exit 1`, `fi`, then the closing fence.
- Green: `4 passed, 25 deselected in 0.38s`.
