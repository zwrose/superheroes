# WO-D repository selector bite-proof

## Repository selector

**Guarded element:** `test_gh_calls_pass_explicit_repo` — axis: every gh call passes explicit `--repo` on the argv the helper builds.

**Neutralization:** removed `--repo` and the repo value from `_gh_label_list_argv` and `_gh_label_create_argv` in `kind_labels.py`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_kind_labels.py::test_gh_calls_pass_explicit_repo -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_gh_calls_pass_explicit_repo _______________________

    def test_gh_calls_pass_explicit_repo():
        run, calls = _make_run(
            {
                tuple(_auth_argv()): _auth_ok(),
                tuple(_list_argv()): _list_ok(list(kl.KIND_LABEL_NAMES)),
            }
        )
        kl.ensure_kind_labels(REPO, run=run)
        for argv in calls:
            if argv[0:2] == ["gh", "auth"]:
                continue
>           assert "--repo" in argv
E           AssertionError: assert '--repo' in ['gh', 'label', 'list', '--limit', '200', '--json', ...]

plugins/superheroes/lib/tests/test_kind_labels.py:185: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_kind_labels.py::test_gh_calls_pass_explicit_repo
1 failed in 0.26s
```

**Restore:** restored `--repo` and the repo argument in both `_gh_label_list_argv` and `_gh_label_create_argv`.

**Restore receipt:** restored argv builders carry `"--repo", repo` again; `git status --porcelain plugins/superheroes/lib/kind_labels.py` showed only `?? plugins/superheroes/lib/kind_labels.py` (new file, no neutralization residue).

**Green run:**
```
.                                                                        [100%]
1 passed in 0.24s
```
