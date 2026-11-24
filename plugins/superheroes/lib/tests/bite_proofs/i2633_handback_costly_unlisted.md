# Bite-proof record: i2633_handback_costly_unlisted (#2633) the handback check refuses a costly degradation missing from What we're accepting

Detector under proof: `plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py`, tests
`test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[two-costly]`,
`test_handback_and_the_merge_sheet_build_agree[two-costly]` and
`test_run_verb_pr_path_refuses_costly_not_accepted_after_its_record_checks[unlabelled-False]` (unedited between the red and the green).
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`check_costly_accepted`, the `costly_unlisted` call, run last on both the `--body-file` and the `--pr` path). Base `34e3ff48`.
The neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit. No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command (absolute paths in the cloud session, shown relative to the worktree root):
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py -q -p no:cacheprovider -k "two-costly or (pr_path and unlabelled)"`

Guarded-element set: G1 the `costly_unlisted` call in `check_costly_accepted` (axis comment above it); G2 (added at review round 1, reworked at round 2) the comment strip in `pr_sheet.costly_unlisted`. No others.

Disclosures: captures are the runner's output; the long `text =` parameter lines and the long assertion line are shown as the runner printed them (the runner elided their middles with `...`); the worktree path prefix is shortened to `.claude/worktrees/b2633`, and the header warning line from the interpreter launcher is dropped. Nothing was redacted.

## G1: a costly or unlabelled bullet no What we're accepting line carries refuses costly-not-accepted

- **Guarded element / axis:** `vet_slot.py`, `check_costly_accepted`, `missing = pr_sheet.costly_unlisted(body)`. Axis: a costly or unlabelled degradation with no line under What we're accepting refuses `costly-not-accepted`, by the sheet build's own comparison, on both handback paths.
- **Neutralization:** `missing = pr_sheet.costly_unlisted(body)` became `missing = []`.
- **Raw red:**

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[two-costly] _

text = "Closes #100.\n\n## What's changing, and why\n\nThe export lists newest first.\n\n## What we're accepting\n\nNone\n\n#... seat forfeited on every rung of the retry ladder, so one specialist lens never read this diff at all.\n\n</details>\n"

    @pytest.mark.parametrize("text", list(REFUSED.values()), ids=list(REFUSED))
    def test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting(text):
        # Bites on: check_costly_accepted not calling costly_unlisted, so a body the merge sheet then refuses passes handback.
        # Axis: a costly or unlabelled bullet with no carrying line refuses costly-not-accepted, naming each missing bullet.
        result = vs.handback_body(text)
>       assert result["ok"] is False and result["reason"] == "costly-not-accepted"
E       assert (True is False)

.claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py:72: AssertionError
__________ test_handback_and_the_merge_sheet_build_agree[two-costly] ___________

text = "Closes #100.\n\n## What's changing, and why\n\nThe export lists newest first.\n\n## What we're accepting\n\nNone\n\n#... seat forfeited on every rung of the retry ladder, so one specialist lens never read this diff at all.\n\n</details>\n"

    @pytest.mark.parametrize("text", list(REFUSED.values()) + list(PASSED.values()), ids=list(REFUSED) + list(PASSED))
    def test_handback_and_the_merge_sheet_build_agree(text):
        # Bites on: either check gaining a second copy of the rule that drifts from the other.
        # Axis: the sheet build refuses a body for a costly line exactly when handback refuses it costly-not-accepted, and
        # each missing bullet's problem line is the same text after its prefix.
        sheet = sheet_costly_problems(text)
        result = vs.handback_body(text)
>       assert bool(sheet) == (result.get("reason") == "costly-not-accepted")
E       assert True == (None == 'costly-not-accepted')
E        +  where True = bool(['PR #211\'s costly deviation ("The verify gate did not run on the final head.") has no line under What we\'re accepti...y ladder, so one speci…") has no line under What we\'re accepting: carry its text, after the label, into a line there'])
E        +  and   None = <built-in method get of dict object at 0x7f901e1e1c40>('reason')
E        +    where <built-in method get of dict object at 0x7f901e1e1c40> = {'ok': True, 'verb': 'handback', 'followups': []}.get

.claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py:101: AssertionError
_ test_run_verb_pr_path_refuses_costly_not_accepted_after_its_record_checks[unlabelled-False] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f901e879970>
name = 'unlabelled', ok = False

    @pytest.mark.parametrize("name, ok", [("costly", False), ("unlabelled", False), ("costly-carried", True),
                                          ("harmless-only", True)])
    def test_run_verb_pr_path_refuses_costly_not_accepted_after_its_record_checks(monkeypatch, name, ok):
        # Bites on: the --pr path (the one the ready mark runs) skipping the costly check the --body-file path runs.
        # Axis: over an open PR with a readable review record, a missing costly line refuses costly-not-accepted and a
        # carried or harmless one passes.
        monkeypatch.setattr(vs.shutil, "which", lambda tool: "/usr/bin/gh" if tool == "gh" else None)
        text = {**REFUSED, **PASSED}[name]
        result = vs.run_verb("handback", PR, REPO, run=Fake(text, [record_comment([row(CODE1)])]))
>       assert result["ok"] is ok
E       assert True is False

.claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py:127: AssertionError
=========================== short test summary info ============================
FAILED .claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py::test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[two-costly]
FAILED .claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py::test_handback_and_the_merge_sheet_build_agree[two-costly]
FAILED .claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py::test_run_verb_pr_path_refuses_costly_not_accepted_after_its_record_checks[unlabelled-False]
3 failed, 21 deselected in 0.70s
```

- **Restore:** inverse Edit, `missing = []` back to `missing = pr_sheet.costly_unlisted(body)`; `git status --porcelain` then printed nothing (the tree matched the build commit).
- **Raw green** (same command):

```
...                                                                      [100%]
3 passed, 21 deselected in 0.48s
```

## G2: words inside an HTML comment under What we're accepting carry no costly line

Added at review round 1 (finding v0) and reworked at review round 2, when the round-1 reader (the leftover rule's shown-text
reader) proved to blank a whole visible acceptance holding an inline comment or an autolink. The guard now strips only HTML
comments from each raw acceptance (`pr_sheet._uncommented`). Re-run on fix commit `8a579b3f`. Same detector file, tests
`test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[hidden-in-inline-comment]` and
`[hidden-after-an-unclosed-comment]` (unedited between the red and the green). Command:
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py -q -p no:cacheprovider -k "refuses_a_costly and (hidden or comment)"`

- **Guarded element / axis:** `pr_sheet.py`, `costly_unlisted`, `accepted = [_line_key(_uncommented(line)) for line in accepting_listed(body)]`. Axis: words inside an HTML comment carry no costly line, and the shown words around a comment still do (the second half is held by the `PASSED` cases `carried-beside-an-inline-comment` and `carried-before-an-autolink`).
- **Neutralization:** `_line_key(_uncommented(line))` became `_line_key(line)` (comments kept).
- **Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[hidden-in-inline-comment] _

name = 'hidden-in-inline-comment'

    @pytest.mark.parametrize("name", list(REFUSALS))
    def test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting(name):
        # Bites on: check_costly_accepted not calling costly_unlisted, a comparison that stops after the first carried bullet,
        # or one that counts words inside an inline HTML comment as a shown line.
        # Axis: a costly or unlabelled bullet with no shown carrying line refuses costly-not-accepted, naming exactly the
        # bullets the case lists and no carried one.
        text, problems = REFUSALS[name]
        result = vs.handback_body(text)
>       assert result["ok"] is False and result["reason"] == "costly-not-accepted"
E       assert (True is False)

.claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py:94: AssertionError
_ test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[hidden-after-an-unclosed-comment] _

name = 'hidden-after-an-unclosed-comment'

    @pytest.mark.parametrize("name", list(REFUSALS))
    def test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting(name):
        # Bites on: check_costly_accepted not calling costly_unlisted, a comparison that stops after the first carried bullet,
        # or one that counts words inside an inline HTML comment as a shown line.
        # Axis: a costly or unlabelled bullet with no shown carrying line refuses costly-not-accepted, naming exactly the
        # bullets the case lists and no carried one.
        text, problems = REFUSALS[name]
        result = vs.handback_body(text)
>       assert result["ok"] is False and result["reason"] == "costly-not-accepted"
E       assert (True is False)

.claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py:94: AssertionError
=========================== short test summary info ============================
FAILED .claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py::test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[hidden-in-inline-comment]
FAILED .claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py::test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[hidden-after-an-unclosed-comment]
2 failed, 35 deselected in 6.98s
```

- **Restore:** inverse Edit, `_line_key(line)` back to `_line_key(_uncommented(line))`; `git status --porcelain` then printed nothing.
- **Raw green** (same command):

```
..                                                                       [100%]
2 passed, 35 deselected in 4.22s
```

## G1 re-run on the round-1 test rewrite

On commit `4cd0bc34`, the same G1 neutralization (`missing = []`) with `-k "refuses_a_costly or pr_path_refuses"` printed
`10 failed, 2 passed, 19 deselected in 1.28s` (every refusal case, both `--pr` path refusal cases; the two passes are the
`--pr` path's passing cases), and the restore printed `12 passed, 19 deselected in 0.45s`. Its full red output is not kept
here; the command reproduces it.
