# #1918 bite-proof: a check after first setup matches the account's recorded environment

**Provenance:** orchestrator-typed (light lane), cloud build session.

**Run command.** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest "<node>" -q -p no:cacheprovider`, one node at a time, from the repo root. The captures below quote the assertion lines pytest printed; they omit the `UV_NATIVE_TLS` deprecation line `uv` prints first. No fixture holds a secret, so nothing is redacted.

**Restore.** Each neutralization is a targeted Edit of the one guarded line in `lib/cloud_environment.py` `compare`, and the restore is the inverse Edit, never a checkout. After the restore, `git diff --exit-code -- plugins/superheroes/lib/cloud_environment.py` exits 0, and the line reads `        if environment == _recorded(env, cwd, root):`.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| recorded-match A | the record's id matches when the shared pick names another environment | `test_compare_matches_the_recorded_id_when_the_shared_pick_names_another` | proven |
| recorded-match B | an id other than the record's is still compared with the picker and refuses | `test_compare_refuses_an_id_that_is_neither_the_record_nor_the_pick` | proven |

## Declared guarded-element set

The one guarded line, `if environment == _recorded(env, cwd, root):`, on its two failure faces: a match that never fires (A), and one that fires for any id once a record exists (B). Every test citing this record sits in the recorded-match class. The two representatives above stand for the other members by failure mode: `test_compare_matches_the_recorded_id_with_no_readable_pick` and `test_compare_cli_matches_the_recorded_id` (face A); `test_compare_a_fresh_pick_moves_a_recorded_account`, `test_compare_first_setup_with_no_record_still_needs_the_pick` and `test_compare_a_record_that_is_not_this_accounts_valid_one_never_matches` (face B, or the unchanged pick path). Those members were not neutralized themselves.

## A — the match never fires (today's behavior)

Neutralization: `if environment == _recorded(env, cwd, root):` → `if False and environment == _recorded(env, cwd, root):`. This is the code before the change, which reads the shared pick only.

Red (exit 1):

```
E       AssertionError: assert {'action': 'm... picked one.'} == {'action': 'm...env_01ABCdef'}
E         Differing items:
E         {'action': 'mismatched'} != {'action': 'matched'}
E         {'reason': 'picked-differs'} != {'reason': 'recorded'}
E         {'environment': 'env_09ZYXwvu'} != {'environment': 'env_01ABCdef'}
```

Red token: `{'reason': 'picked-differs'} != {'reason': 'recorded'}`.

## B — the match fires for any id once a record exists

Neutralization: `if environment == _recorded(env, cwd, root):` → `if _recorded(env, cwd, root) is not None:`.

Red (exit 1):

```
E       AssertionError: assert ('matched' == 'mismatched'
E         - mismatched
E         + matched)
1 failed
```

Red token: `assert ('matched' == 'mismatched'`.

## Green

After the restore, both nodes run together: `2 passed`.
