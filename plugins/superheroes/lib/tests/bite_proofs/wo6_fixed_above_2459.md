# WO-6 (#2459) bite-proof — `stack_linear.py` fixed-above check and the recipe's rebase flag

Per-element bite proof for the guards WO-6 added to `plugins/superheroes/lib/stack_linear.py` (and the recipe flag in `merge-train.md` § Merging a stack, item 4 (c)). Each guard is neutralized by a targeted edit, its proving test(s) run alone with `-k` and go red on that axis, the guard is restored by the inverse edit, and the same `-k` run goes green. The whole file then goes green (218 passed).

**Provenance:** claude (Claude Sonnet 5.5), WO-6 implementer.

**Commands.** Every red and green below is:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo6 -m pytest plugins/superheroes/lib/tests/test_stack_linear.py -q -p no:cacheprovider --tb=short -k "<expr>"
```

with the `<expr>` named in each entry. Every capture omits the one leading line `warning: The UV_NATIVE_TLS environment variable is deprecated ...` (uv's own notice); nothing else is filtered. Nothing in the captures is a secret, token, private URL or PII; the temporary paths are pytest's.

**Declared set (from the order):** B1 stale decision, B2 unresolvable-commit-is-stale, B3 unknown-layer refusal, B4 bodies-given-but-a-layer-lacks-a-body refusal, B5 CLI missing-`--pr-body` refusal, B6 the recipe flag. B7 (below) is one more element the implementer added: the CLI refusing a `--pr-body` file that cannot be read as UTF-8.

## Summary table

| ID | Guarded element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| B1 | `stack_linear.py` `_check_fixed_above`, `if not current:` | ancestry exit 1 (not an ancestor of the new head) is stale | `test_prove_stale_fixed_above_line_is_refused_with_its_replacement`, `test_prove_all_stale_lines_in_all_bodies_are_reported`, `test_cli_prove_stale_line_exits_one_with_the_replacement` | proven |
| B2 | `_check_fixed_above`, `if not resolves:` | a commit that does not resolve counts as stale | `test_prove_line_whose_commit_does_not_resolve_is_stale` | proven |
| B3 | `_check_fixed_above`, `if named not in new_of:` | a line naming a PR outside the stack refuses `fixed-above-unknown-layer` | `test_prove_line_naming_a_pr_outside_the_stack_is_unknown_layer` | proven |
| B4 | `_validate_prove`, `if missing:` | bodies given but a layer's PR has no string body is `bad-argument` | `test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[missing-body/empty-bodies/body-none/body-bytes/key-is-string]` | proven |
| B5 | `_prove_cli_inputs`, `if layer[3] not in bodies:` | a layer without its `--pr-body` is `bad-argument` naming `--pr-body` | `test_cli_prove_without_a_pr_body_for_every_layer_is_bad_argument` | proven |
| B6 | `merge-train.md` item 4 (c) `--no-rebase-merges` | with the clone's `rebase.rebaseMerges` on, the recipe's rebase without the flag keeps a merge commit | `test_recipe_rebase_flag_keeps_a_clone_that_rebases_merges_from_keeping_a_merge_commit` | proven (by the contrast) |
| B7 | `_prove_cli_inputs`, `except (OSError, ValueError)` | a `--pr-body` file that is missing, a directory or not UTF-8 is `bad-argument`, never read as empty or raised | `test_cli_prove_pr_body_file_that_cannot_be_read_is_bad_argument` | proven |

**Not neutralized (guards the order did not declare, covered by tests but without a red of their own):** `_validate_prove` clauses for a layer pr that is not a positive int, a repeated pr, a triple layer while bodies are given, and bodies that is not a dict (their cases are in the B4 parametrized test, `test_prove_a_bad_pr_is_bad_argument_even_without_bodies` and the `triple-with-bodies`, `duplicate-pr`, `pr-*`, `bodies-list`, `bodies-string` ids, all green); the git-failed branches of `_check_fixed_above` (`test_prove_ancestry_check_failing_on_a_line_is_git_failed_not_current`, `test_prove_lookup_raising_on_a_line_is_git_failed`); the `_prove_cli_inputs` clauses for a non-integer `--layer`/`--pr-body` pr and a repeated `--pr-body` pr; the lazy-import test. These are **unproven** here: no neutralization was run for them.

---

## B1 — the stale decision (ancestry exit 1 is stale)

**neutralization:** `if not current:` → `if False:  # bite-proof`

**red** (`-k "stale_fixed_above_line_is_refused_with_its_replacement or all_stale_lines_in_all_bodies or cli_prove_stale_line"`):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
______ test_prove_stale_fixed_above_line_is_refused_with_its_replacement _______
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1018: in test_prove_stale_fixed_above_line_is_refused_with_its_replacement
    _assert_not_proven(result, "fixed-above-stale")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:633: in _assert_not_proven
    assert result["ok"] is False and result["proven"] is False
E   assert (True is False)
____________ test_prove_all_stale_lines_in_all_bodies_are_reported _____________
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1068: in test_prove_all_stale_lines_in_all_bodies_are_reported
    _assert_not_proven(result, "fixed-above-stale")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:633: in _assert_not_proven
    assert result["ok"] is False and result["proven"] is False
E   assert (True is False)
___________ test_cli_prove_stale_line_exits_one_with_the_replacement ___________
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1345: in test_cli_prove_stale_line_exits_one_with_the_replacement
    assert code == 1 and result["reason"] == "fixed-above-stale" and result["push"] is None
E   assert (0 == 1)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_stale_fixed_above_line_is_refused_with_its_replacement
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_all_stale_lines_in_all_bodies_are_reported
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_cli_prove_stale_line_exits_one_with_the_replacement
3 failed, 215 deselected in 0.82s
```

**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
            if not current:
                stale.append((pr, line, named, commit))
```
**green** (same `-k`):
```
...                                                                      [100%]
3 passed, 215 deselected in 0.84s
```

## B2 — an unresolvable commit counts as stale

**neutralization:** `if not resolves:` → `if False:  # bite-proof`

**red** (`-k "line_whose_commit_does_not_resolve"`): the unresolvable commit falls through to the ancestry call and git answers an error, so the result is `git-failed` instead of `fixed-above-stale`:
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_prove_line_whose_commit_does_not_resolve_is_stale ____________
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1059: in test_prove_line_whose_commit_does_not_resolve_is_stale
    _assert_not_proven(result, "fixed-above-stale")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:634: in _assert_not_proven
    assert result["reason"] == reason
E   AssertionError: assert 'git-failed' == 'fixed-above-stale'
E     
E     - fixed-above-stale
E     + git-failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_line_whose_commit_does_not_resolve_is_stale
1 failed, 217 deselected in 0.78s
```

**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
            resolves = proc.returncode == 0 and _OBJECT_ID_RE.match(commit_sha) is not None
            # axis: a commit that does not resolve counts as stale
            if not resolves:
```
**green** (same `-k`):
```
.                                                                        [100%]
1 passed, 217 deselected in 0.58s
```

## B3 — a line naming a PR outside the stack refuses `fixed-above-unknown-layer`

**neutralization:** `if named not in new_of:` → `if False:  # bite-proof`

**red** (`-k "line_naming_a_pr_outside_the_stack"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_prove_line_naming_a_pr_outside_the_stack_is_unknown_layer ________
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1049: in test_prove_line_naming_a_pr_outside_the_stack_is_unknown_layer
    result = _prove(stack, _two(stack), bodies=bodies)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:628: in _prove
    return sl.prove(repo_root=stack.repo, base=stack.base,
/home/user/wt-2459-wo6/plugins/superheroes/lib/stack_linear.py:706: in prove
    refusal, fixed_above = _check_fixed_above(run, repo_root, base_sha, entries,
/home/user/wt-2459-wo6/plugins/superheroes/lib/stack_linear.py:578: in _check_fixed_above
    current, problem = _is_ancestor(run, repo_root, commit_sha, new_of[named])
                                                                ^^^^^^^^^^^^^
E   KeyError: 999
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_line_naming_a_pr_outside_the_stack_is_unknown_layer
1 failed, 217 deselected in 0.63s
```
(The red is the unguarded `new_of[named]` lookup of the unknown PR 999.)

**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
            # axis: a line naming a pull request that is not a layer of this stack - fixed-above-unknown-layer
            if named not in new_of:
```
**green** (same `-k`):
```
.                                                                        [100%]
1 passed, 217 deselected in 0.59s
```

## B4 — bodies given but a layer's PR has no string body

**neutralization:** `if missing:` → `if False:  # bite-proof`

**red** (`-k "bodies_that_do_not_fit"`): the five cases that rest on this clause fail (the other eight are caught by other clauses and stay green), each answering `git-failed` instead of `bad-argument`:
```
FFFFF........                                                            [100%]
=================================== FAILURES ===================================
_ test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[missing-body] _
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1124: in test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing
    _assert_not_proven(result, "bad-argument")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:634: in _assert_not_proven
    assert result["reason"] == reason
E   AssertionError: assert 'git-failed' == 'bad-argument'
E     
E     - bad-argument
E     + git-failed
_ test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[empty-bodies] _
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1124: in test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing
    _assert_not_proven(result, "bad-argument")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:634: in _assert_not_proven
    assert result["reason"] == reason
E   AssertionError: assert 'git-failed' == 'bad-argument'
E     
E     - bad-argument
E     + git-failed
_ test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[body-none] _
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1124: in test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing
    _assert_not_proven(result, "bad-argument")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:634: in _assert_not_proven
    assert result["reason"] == reason
E   AssertionError: assert 'git-failed' == 'bad-argument'
E     
E     - bad-argument
E     + git-failed
_ test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[body-bytes] _
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1124: in test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing
    _assert_not_proven(result, "bad-argument")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:634: in _assert_not_proven
    assert result["reason"] == reason
E   AssertionError: assert 'git-failed' == 'bad-argument'
E     
E     - bad-argument
E     + git-failed
_ test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[key-is-string] _
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1124: in test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing
    _assert_not_proven(result, "bad-argument")
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:634: in _assert_not_proven
    assert result["reason"] == reason
E   AssertionError: assert 'git-failed' == 'bad-argument'
E     
E     - bad-argument
E     + git-failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[missing-body]
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[empty-bodies]
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[body-none]
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[body-bytes]
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_prove_bodies_that_do_not_fit_the_layers_are_bad_argument_and_run_nothing[key-is-string]
5 failed, 8 passed, 205 deselected in 0.57s
```
**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
        # axis: bodies are given but a layer's pull request has no string body
        missing = [pr for pr in prs if not isinstance(bodies.get(pr), str)]
        if missing:
```
**green** (same `-k`):
```
.............                                                            [100%]
13 passed, 205 deselected in 0.35s
```

## B5 — the CLI refuses a layer without its `--pr-body`

**neutralization:** `if layer[3] not in bodies:` → `if False:  # bite-proof` (in `_prove_cli_inputs`). The refusal then still arrives from `prove`'s own B4 clause as `bad-argument`, so the test pins the CLI's own message (it must name `--pr-body`), and that is what goes red.

**red** (`-k "without_a_pr_body_for_every_layer"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_cli_prove_without_a_pr_body_for_every_layer_is_bad_argument _______
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1354: in test_cli_prove_without_a_pr_body_for_every_layer_is_bad_argument
    assert "--pr-body" in result["detail"] and "103" in result["detail"]
E   AssertionError: assert ('--pr-body' in 'no body text for pull request 103')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_cli_prove_without_a_pr_body_for_every_layer_is_bad_argument
1 failed, 217 deselected in 0.53s
```

**restore:** `if False:  # bite-proof` → the inverse edit.
**restored lines:**
```python
        # axis: every layer's PR needs its own --pr-body, so no body is guessed as empty
        if layer[3] not in bodies:
```
**green** (same `-k`):
```
.                                                                        [100%]
1 passed, 217 deselected in 0.55s
```

## B6 — the recipe's `--no-rebase-merges` flag

The detector is the flag test's own contrast. In a throwaway repo whose own config sets `rebase.rebaseMerges=true`, the recipe's rebase **without** the flag keeps a merge commit (asserted, and `prove` then refuses `merge-commit-remains`), and **with** the flag the rebased head has no merge commit and `prove` proves. The red half shows the contrast assertion bites: with the repo's setting turned off (the neutralization), the no-flag arm no longer keeps a merge commit, so the assertion that says why the flag is in the recipe fails.

**neutralization (in the test, the throwaway repo's config):** `_git(repo, "config", "rebase.rebaseMerges", "true")` and `assert _git(repo, "config", "--get", "rebase.rebaseMerges") == "true"` → the value `"false"` in both, marked `# bite-proof`.

**red** (`-k "recipe_rebase_flag"`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_recipe_rebase_flag_keeps_a_clone_that_rebases_merges_from_keeping_a_merge_commit _
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1179: in test_recipe_rebase_flag_keeps_a_clone_that_rebases_merges_from_keeping_a_merge_commit
    assert _git(repo, "rev-list", "--merges", base + ".." + kept) != "", \
E   AssertionError: without the flag the clone's rebase.rebaseMerges keeps a merge commit
E   assert '' != ''
E    +  where '' = _git(PosixPath('/tmp/claude-0/pytest-of-root/pytest-131/test_recipe_rebase_flag_keeps_0/flag'), 'rev-list', '--merges', (('f21ceb8cf820373359b66d3a2ac777a5ca89ea1c' + '..') + 'a4e656a67490c24e039d625bee4d058f564f62bf'))
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_recipe_rebase_flag_keeps_a_clone_that_rebases_merges_from_keeping_a_merge_commit
1 failed, 217 deselected in 0.53s
```

**restore:** the two lines set back to `"true"` by the inverse edit.
**restored lines:**
```python
    _git(repo, "config", "rebase.rebaseMerges", "true")
    assert _git(repo, "config", "--get", "rebase.rebaseMerges") == "true"
```
**green** (same `-k`; the no-flag arm keeps a merge commit, the flag arm does not, `prove` proves it):
```
.                                                                        [100%]
1 passed, 217 deselected in 0.69s
```

git in this environment is 2.43.0 and runs both `rebase.rebaseMerges` and `--no-rebase-merges` (the green run above executed both).

## B7 — a `--pr-body` file that cannot be read as UTF-8 is `bad-argument`

**neutralization:** `except (OSError, ValueError) as exc:` → `except ZeroDivisionError as exc:  # bite-proof`

**red** (`-k "cannot_be_read"`): the missing file's `FileNotFoundError` is raised out of `main`:
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_cli_prove_pr_body_file_that_cannot_be_read_is_bad_argument ________
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1367: in test_cli_prove_pr_body_file_that_cannot_be_read_is_bad_argument
    code, result = _cli(capsys, _prove_argv(stack) + files, run=run, today=TODAY)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo6/plugins/superheroes/lib/tests/test_stack_linear.py:1201: in _cli
    code = sl.main(argv, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo6/plugins/superheroes/lib/stack_linear.py:815: in main
    layers, bodies, refusal = _prove_cli_inputs(args)
                              ^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2459-wo6/plugins/superheroes/lib/stack_linear.py:781: in _prove_cli_inputs
    with open(path, "rb") as handle:
         ^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/tmp/claude-0/pytest-of-root/pytest-129/test_cli_prove_pr_body_file_th0/missing.md'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_linear.py::test_cli_prove_pr_body_file_that_cannot_be_read_is_bad_argument
1 failed, 217 deselected in 0.65s
```

**restore:** `except ZeroDivisionError as exc:  # bite-proof` → the inverse edit.
**restored lines:**
```python
        except (OSError, ValueError) as exc:
            # axis: a --pr-body file that cannot be read, or is not UTF-8, is never read as empty
```
**green** (same `-k`):
```
.                                                                        [100%]
1 passed, 217 deselected in 0.55s
```

## Whole file, after every restore

```
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
..                                                                       [100%]
218 passed in 3.35s
```
