# Bite-proof record — background-refusal literal census widened to every lib/ module (#1273 WO-C)

**One proof** for the widened `test_background_refusal_literals_only_in_home` parametrization.
The old hand-listed census (`["engine_dispatch.py"]` only) is the A/B control.

## The guarded-element set

| Detector | Guarded element | Axis |
|---|---|---|
| `test_background_refusal_literals_only_in_home` | every `*.py` directly under `lib/` except `background_outcome.py` (162 modules at proof time) | a background refusal token spelled as a string literal outside `background_outcome.py` fails the census for that module |

## Identifier sweep (final commit)

```
$ grep -rn "background_outcome\.\|REFUSAL_LAUNCH_UNACKNOWLEDGED\|REFUSAL_LAUNCH_FAILED\|REFUSAL_SESSION_UNLISTED\|REFUSAL_TRANSCRIPT_AMBIGUOUS\|REFUSAL_AGENTS_UNREADABLE\|REFUSAL_SESSION_ENDED_WITHOUT_RESULT" plugins/superheroes --include="*.py" | grep -v "lib/background_outcome.py" | grep -v "lib/tests/"
plugins/superheroes/lib/engine_dispatch.py:1344:                "refusal": background_outcome.REFUSAL_LAUNCH_UNACKNOWLEDGED,
plugins/superheroes/lib/engine_dispatch.py:1355:                "refusal": background_outcome.REFUSAL_LAUNCH_FAILED,
plugins/superheroes/lib/engine_dispatch.py:1388:                "refusal": background_outcome.REFUSAL_SESSION_UNLISTED,
plugins/superheroes/lib/engine_dispatch.py:1419:                refusal = background_outcome.REFUSAL_TRANSCRIPT_AMBIGUOUS
plugins/superheroes/lib/engine_dispatch.py:1446:                refusal = background_outcome.REFUSAL_AGENTS_UNREADABLE
plugins/superheroes/lib/engine_dispatch.py:1477:                    refusal = background_outcome.REFUSAL_SESSION_ENDED_WITHOUT_RESULT
```

Only `engine_dispatch.py` is a background-refusal producer. `pilot_contract.py`, `pilot_provision.py`,
and `pilot_seed.py` carry unrelated `REFUSAL_*` names (`provision-launch-invalid`,
`seed-capture-surface-session-storage-refused`, and their own vocabulary) and are not background-refusal
producers; they do not appear in this sweep because their symbol names differ from the background
tokens.

## Vocabulary sweep (final commit)

```
$ grep -rn "background-launch-unacknowledged\|background-launch-failed\|background-session-unlisted\|background-transcript-ambiguous\|background-agents-unreadable\|background-session-ended-without-result" plugins/superheroes .github --include="*.py" --include="*.md" --include="*.json" --include="*.yml" | grep -v "lib/background_outcome.py" | grep -v "lib/tests/"
[no output]
```

## Element 1 — tree-derived census vs hand-listed census

- **axis:** a background refusal literal planted in a `lib/` module outside the old single-module
  list is caught by the widened census but invisible to the old census
- **detector:** `test_background_outcome_census.py::test_background_refusal_literals_only_in_home`
- **neutralization:** in `engine_adapter.py` after the import block, add
  `_WO1273_BP_PLANT = "background-launch-unacknowledged"` (literal pinned, not the symbol)
- **raw red (widened census, plant in place, detector unedited):**

```
$ /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3a-C -m pytest plugins/superheroes/lib/tests/test_background_outcome_census.py::test_background_refusal_literals_only_in_home -q
...............................F........................................ [ 44%]
........................................................................ [ 88%]
..................                                                       [100%]
=================================== FAILURES ===================================
_______ test_background_refusal_literals_only_in_home[engine_adapter.py] _______

basename = 'engine_adapter.py'

    @pytest.mark.parametrize("basename", _CENSUS_MODULES)
    def test_background_refusal_literals_only_in_home(basename):
        banned = background_outcome.ALL_REFUSALS
        path = os.path.join(_LIB, basename)
        offenders = _literal_offenders(path, banned)
>       assert offenders == [], offenders
E       AssertionError: [('background-launch-unacknowledged', 28)]
E       assert [('background...wledged', 28)] == []
E         
E         Left contains one more item: ('background-launch-unacknowledged', 28)
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_background_outcome_census.py:66: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_background_outcome_census.py::test_background_refusal_literals_only_in_home[engine_adapter.py]
1 failed, 161 passed in 1.57s
```

- **A/B control (old hand-listed census, same planted tree):** temporarily set
  `@pytest.mark.parametrize("basename", ["engine_dispatch.py"])` while the plant remains in
  `engine_adapter.py`.
- **raw green (old form, plant still present):**

```
$ /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3a-C -m pytest plugins/superheroes/lib/tests/test_background_outcome_census.py::test_background_refusal_literals_only_in_home -q
.                                                                        [100%]
1 passed in 0.12s
```

- **restore:** remove the `_WO1273_BP_PLANT = "background-launch-unacknowledged"` line from
  `engine_adapter.py` and restore `@pytest.mark.parametrize("basename", _CENSUS_MODULES)` in the
  test file.
- **restore receipt:** `git status --porcelain` over the worktree after restore showed only the
  landed order files (`test_background_outcome_census.py`, `dispatch-mechanics.md`); `engine_adapter.py`
  was not modified.
- **raw green (widened census, plant reverted):**

```
$ /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3a-C -m pytest plugins/superheroes/lib/tests/test_background_outcome_census.py -q
........................................................................ [ 44%]
........................................................................ [ 88%]
..................                                                       [100%]
162 passed in 1.49s
```

`git status --porcelain` after the final restore (before committing landed work):

```
 M plugins/superheroes/lib/tests/test_background_outcome_census.py
 M plugins/superheroes/skills/workhorse/reference/dispatch-mechanics.md
```

Only the order's allowed paths remained dirty; the plant surface was clean.
