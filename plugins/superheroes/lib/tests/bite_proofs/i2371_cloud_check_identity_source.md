# #2371 bite-proof: the cloud check says where a passing git identity came from (`cloud_check.py`)

Bite-proof record for `plugins/superheroes/lib/cloud_check.py` (`report`, `identity_warning`, `judge`), detectors in `plugins/superheroes/lib/tests/test_cloud_check_identity_source_2371.py` (`T`).

**Status.** The builder ran every proof (G1 to G7) in a detached probe worktree at commit `597c77c9`: each neutralization is a targeted Edit in `cloud_check.py`, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. `git status --porcelain` in the probe worktree was empty after the last restore. Each red below quotes the failing line and assertion pytest printed; each green is `1 passed`. The launcher's deprecation warning (`UV_NATIVE_TLS`) is left out of every capture. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest "<T>::<node>" -q -p no:cacheprovider`.
- **Pinned condition.** The tests pass the cloud session's environment to `report` directly and write the identity flags through `identity_fn`, so no real git or cloud session runs. Unobservable under the pin: which variables a real cloud worker exports after a restart (the fix rests on the report reading the process environment `report` is given).
- **One discarded run, disclosed.** The first G6 neutralization (`+ "")}`) broke the file's syntax, so its failure was a collection error, not a red; it was restored and replaced by the valid neutralization below, whose capture overwrote it.

## Declared guarded-element set

G1 a blank variable is not set; G2 an absent source reads unknown; G3 the four variables give no warning; G4 config-alone is told apart from mixed; G5 the warning reaches a passed message; G6 the warning reaches a failed message; G7 a failed identity part carries no warning.

## Per-element receipts

### G1: `source` in `report`. Axis: the report says which identity variables are set, by name only

- **Neutralization.** `if isinstance(env.get(name), str) and env.get(name).strip()]}` → `if isinstance(env.get(name), str)]}`.
- **Node.** `T::test_report_does_not_count_an_empty_variable`
- **Red.** `AssertionError: assert {'variables': ['GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_NAME', 'GIT_COMMITTER_EMAIL']} != {'variables': ['GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_NAME']}` — `1 failed`.
- **Green.** `1 passed in 1.40s`.

### G2: `names` in `identity_warning`. Axis: a report that does not say where the identity came from reads unknown and warns

- **Neutralization.** `... if isinstance(source, dict) else None` → `... else list(IDENTITY_VARIABLES)` (an absent source read as all four set).
- **Node.** `T::test_a_report_that_does_not_say_where_reads_unknown_and_warns`
- **Red.** `TypeError: 'NoneType' object is not subscriptable` at `assert warning["source"] == "unknown"` (no warning was produced) — `1 failed in 1.31s`.
- **Green.** `1 passed in 1.27s`.

### G3: `if not missing: return None`. Axis: an identity from the four variables carries no warning

- **Neutralization.** `if not missing:` → `if False:`.
- **Node.** `T::test_identity_from_the_four_variables_passes_with_no_warning`
- **Red.** `IndexError: list index out of range` in `_prose_names` (the warning was built for an empty list) — `1 failed in 1.31s`. The red is a raise, not the assertion; it still fails the node only because the guard is gone.
- **Green.** `1 passed in 1.44s`.

### G4: `kind`. Axis: an identity from git config alone names all four variables; a mixed one names the missing ones

- **Neutralization.** `kind = "config" if len(missing) == len(IDENTITY_VARIABLES) else "mixed"` → `kind = "mixed"`.
- **Node.** `T::test_identity_from_git_config_alone_passes_with_the_warning_naming_all_four`
- **Red.** `AssertionError: assert ('mixed' == 'config'` — `1 failed`.
- **Green.** `1 passed in 1.36s`.

### G5: the passed message. Axis: a passing check whose identity is not wholly from the four variables says so

- **Neutralization.** `+ ("" if warning is None else warning["message"] + "\n\n") + ending)}` → `+ "" + ending)}`.
- **Node.** `T::test_identity_from_git_config_alone_passes_with_the_warning_naming_all_four`
- **Red.** `assert "**A warning about the git identity.** ..." in '**The check passed.** ...'` — `1 failed in 1.40s`.
- **Green.** `1 passed in 1.33s`.

### G6: the failed message. Axis: a passing identity part says where it came from even when another part fails

- **Neutralization.** `+ ("" if warning is None else "\n\n" + warning["message"])}` → `+ ("" if True else "\n\n" + warning["message"])}`.
- **Node.** `T::test_a_check_failing_elsewhere_still_says_where_a_passing_identity_came_from`
- **Red.** `assert False` on `result["message"].endswith(result["identityWarning"]["message"])`, the message ending `... and say "check again".` — `1 failed in 1.23s`.
- **Green.** `1 passed in 1.28s`.

### G7: `if not identity_present: return None`. Axis: no identity still fails as before, with no warning added

- **Neutralization.** `if not identity_present:` → `if False:`.
- **Node.** `T::test_no_identity_still_fails_and_carries_no_warning`
- **Red.** `assert {'source': 'config', 'missing': [...four...], ...} is None` — `1 failed in 1.29s`.
- **Green.** `1 passed in 1.23s`.
