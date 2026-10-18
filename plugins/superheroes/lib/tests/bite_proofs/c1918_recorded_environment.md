# #1918 bite-proof: a check after first setup matches the account's recorded environment

**Provenance:** orchestrator-typed (light lane), cloud build session.

**Run command.** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest "<node>" -q -p no:cacheprovider`, one node at a time, from the repo root. The captures below quote the assertion lines pytest printed; they omit the `UV_NATIVE_TLS` deprecation line `uv` prints first. No fixture holds a secret, so nothing is redacted.

**Restore.** Each neutralization is a targeted Edit of one guarded line in `lib/cloud_environment.py` `compare`, and the restore is the inverse Edit, never a checkout. After the last restore, `git diff --exit-code -- plugins/superheroes/lib/cloud_environment.py` exits 0 against the committed head `d12460b5`.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| recorded-match | the record's id matches when the shared pick names another environment | `test_compare_matches_the_recorded_id_when_the_shared_pick_names_another` | proven |
| recorded-refuses | a recorded account refuses any other id, even one the shared pick names | `test_compare_refuses_an_id_other_than_the_record_toward_the_record` | proven |
| move | `--moving` sets the record aside so the new pick decides | `test_compare_a_move_goes_to_the_picker` | proven |

## Declared guarded-element set

Three guarded lines in `compare`: the recorded match (`if recorded is not None and environment == recorded:`), the recorded refusal (`if recorded is not None:`), and the move (`recorded = None if moving else _recorded(env, cwd, root)`). The representatives above stand for the other tests citing this record by failure mode: `test_compare_matches_the_recorded_id_with_no_readable_pick` and `test_compare_cli_matches_the_recorded_id` (recorded-match); `test_compare_first_setup_with_no_record_still_needs_the_pick` and `test_compare_a_record_that_is_not_this_accounts_valid_one_never_matches` (the unchanged pick path when no valid record exists). Those members were not neutralized themselves.

## recorded-match: the match never fires (the behavior before this change)

Neutralization: `if recorded is not None and environment == recorded:` → `if False and recorded is not None and environment == recorded:`.

Red (exit 1):

```
E         Differing items:
E         {'reason': 'recorded-differs'} != {'reason': 'recorded'}
E         {'action': 'mismatched'} != {'action': 'matched'}
```

Red token: `{'reason': 'recorded-differs'} != {'reason': 'recorded'}`.

## recorded-refuses: an id other than the record's falls through to the shared pick

Neutralization: `if recorded is not None:` → `if False and recorded is not None:`. This is the shape the cross-vendor review found in the first version: an id the shared pick names passed for a recorded account.

Red (exit 1, both parameters):

```
E       AssertionError: assert ('mismatched' == 'mismatched'
E           mismatched and 'picked-differs' == 'recorded-differs'
E       AssertionError: assert ('matched' == 'mismatched'
```

Red token: `assert ('matched' == 'mismatched'` (the `env_09ZYXwvu` parameter, the id the shared pick names).

## move: `--moving` is ignored

Neutralization: `recorded = None if moving else _recorded(env, cwd, root)` → `recorded = _recorded(env, cwd, root)`.

Red (exit 1):

```
E         Differing items:
E         {'environment': 'env_01ABCdef'} != {'environment': 'env_09ZYXwvu'}
E         {'reason': 'recorded-differs'} != {'reason': None}
E         {'action': 'mismatched'} != {'action': 'matched'}
```

Red token: `{'reason': 'recorded-differs'} != {'reason': None}`.

## Green

After the restores, the three representatives run together: `4 passed` (the refusal test has two parameters).
