# Bite-proof record: i2633_handback_costly_unlisted (#2633) the handback check refuses a costly degradation missing from What we're accepting

Detector under proof: `plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py`, test `test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[two-costly]` (unedited between the red and the green).
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`check_handback`, the `costly_unlisted` call). Head of the build commit on base `34e3ff48`.
The neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit. No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command (worktree root, absolute paths in the cloud session):
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py -q -p no:cacheprovider -k "refuses_a_costly and two-costly"`

Guarded-element set: G1 the `costly_unlisted` call in `check_handback` (axis comment above it). No others.

Disclosures: captures are the runner's output; the long `text =` parameter line is shown as the runner printed it (the runner elided its middle with `...`); the worktree path prefix is shortened to `.claude/worktrees/b2633`. Nothing was redacted.

## G1: a costly or unlabelled bullet no What we're accepting line carries refuses costly-not-accepted

- **Guarded element / axis:** `vet_slot.py`, `check_handback`, `missing = pr_sheet.costly_unlisted(body)`. Axis: a costly or unlabelled degradation with no line under What we're accepting refuses `costly-not-accepted`, by the sheet build's own comparison.
- **Neutralization:** `missing = pr_sheet.costly_unlisted(body)` became `missing = []`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[two-costly] _

text = "Closes #100.\n\n## What's changing, and why\n\nThe export lists newest first.\n\n## What we're accepting\n\nNone\n\n#... seat forfeited on every rung of the retry ladder, so one specialist lens never read this diff at all.\n\n</details>\n"

    @pytest.mark.parametrize("text", list(REFUSED.values()), ids=list(REFUSED))
    def test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting(text):
        # Bites on: check_handback not calling costly_unlisted, so a body the merge sheet then refuses passes handback.
        # Axis: a costly or unlabelled bullet with no carrying line refuses costly-not-accepted, naming each missing bullet.
        result = vs.check_handback(text)
>       assert result["ok"] is False and result["reason"] == "costly-not-accepted"
E       assert (True is False)

.claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py:71: AssertionError
=========================== short test summary info ============================
FAILED .claude/worktrees/b2633/plugins/superheroes/lib/tests/test_handback_costly_unlisted_2633.py::test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting[two-costly]
1 failed, 19 deselected in 0.32s
```

- **Restore:** inverse Edit, `missing = []` back to `missing = pr_sheet.costly_unlisted(body)`; `git status --porcelain` then printed nothing (the tree matched the build commit).
- **Raw green** (same command):

```
.                                                                        [100%]
1 passed, 19 deselected in 0.28s
```
