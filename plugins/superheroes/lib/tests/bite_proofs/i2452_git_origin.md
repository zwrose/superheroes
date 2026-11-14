# I2452 bite-proof: one git-origin classifier

Bite-proof record `i2452_git_origin` for the detectors issue 2452 adds in `plugins/superheroes/lib/tests/test_git_origin_2452.py` and `.github/scripts/tests/test_check_release_bump_origin_2452.py`, and for the updated argv pins in `test_launcher_cloud.py` and `test_adopt_original_session.py`. The guarded code is `plugins/superheroes/lib/git_origin.py` (G1 to G6), `store_core.normalize_remote` (G7) and `launcher._gh_commit_lookup` (G8).

**Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2452 -m pytest <node> -q -p no:cacheprovider --tb=short`. The harness's `UV_NATIVE_TLS` deprecation line is filtered from each capture below (redaction: that line only; nothing else is edited, and no secret, token or private URL appears in any capture). Each neutralization is a targeted Edit in production code, each restore is the inverse Edit, and each green is the same node(s). No `git checkout`, `git restore`, `git reset` or `git stash` was used.

## Summary

| Element | Axis | Neutralization | Red node | Verdict |
|---|---|---|---|---|
| G1 | `classify`'s `file://` refusal, via `host_and_path` | `if False and url[:7].lower() == "file://":` | `test_a_file_url_is_not_github_whatever_its_authority_names[file://github.com/o/r.git]` | proven |
| G2 | the host set | `"www.github.com"` removed from `GITHUB_HOSTS` | `test_the_www_host_is_a_github_host` | proven |
| G3 | the host case fold | `host.lower() not in` became `host not in` | `test_the_host_case_does_not_matter` | proven |
| G4 | the github-unreadable path rule | `return (GITHUB_UNREADABLE, None)` became `return (GITHUB, path)` | `test_a_github_host_with_a_path_that_is_not_owner_and_name_is_unreadable[https://github.com/o]` | proven |
| G5 | `same_repository`'s case fold | `a.lower() == b.lower()` became `a == b` | three nodes (helper, `_from_elsewhere`, `_find_release_pr`) | proven |
| G6 | `same_repository`'s empty refusal | `and a and b` dropped | `test_same_repository_compares_slugs_ignoring_case_and_refuses_empty[--False]` | proven |
| G7 | `normalize_remote`'s `file://` return | `return None` became `pass` | `test_normalize_remote_reads_a_file_url_as_no_key[file://github.com/o/r.git]` | proven |
| G8 | the `--hostname github.com` pin on `_gh_commit_lookup` | `"--hostname", "github.com",` removed from the argv | `test_launcher_cloud.py::test_the_default_gh_call_asks_the_commits_endpoint` | proven |

Test paths below are in `plugins/superheroes/lib/tests/` unless a full path is given.

## G1: a file:// URL is never GitHub

- **Guarded element and axis.** `git_origin.host_and_path`'s `file://` branch (`git_origin.py:32`): a file:// URL is a local transport whatever its authority names.
- **Neutralization.** `if url[:7].lower() == "file://":` became `if False and url[:7].lower() == "file://":`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_file_url_is_not_github_whatever_its_authority_names[file://github.com/o/r.git] _
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:84: in test_a_file_url_is_not_github_whatever_its_authority_names
    assert git_origin.classify(url) == NOT_GITHUB
E   AssertionError: assert ('github', 'o/r') == ('not-github', None)
E     
E     At index 0 diff: 'github' != 'not-github'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_a_file_url_is_not_github_whatever_its_authority_names[file://github.com/o/r.git]
1 failed in 1.15s
```

- **Restore.** The inverse Edit. **Restore receipt (line quoted back):** `    if url[:7].lower() == "file://":` (`git_origin.py:32`).
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.25s
```

## G2: the host set holds www.github.com

- **Guarded element and axis.** `GITHUB_HOSTS` (`git_origin.py:15`): www.github.com is a GitHub host.
- **Neutralization.** `frozenset({"github.com", "www.github.com", "ssh.github.com"})` became `frozenset({"github.com", "ssh.github.com"})`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_the_www_host_is_a_github_host ______________________
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:98: in test_the_www_host_is_a_github_host
    assert git_origin.classify("https://www.github.com/o/r") == ("github", "o/r")
E   AssertionError: assert ('not-github', None) == ('github', 'o/r')
E     
E     At index 0 diff: 'not-github' != 'github'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_the_www_host_is_a_github_host
1 failed in 1.25s
```

- **Restore.** The inverse Edit. **Restore receipt:** `GITHUB_HOSTS = frozenset({"github.com", "www.github.com", "ssh.github.com"})` (`git_origin.py:15`).
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.22s
```

## G3: the host is folded to lower case

- **Guarded element and axis.** `host.lower() not in GITHUB_HOSTS` in `classify`: the host's case does not matter.
- **Neutralization.** `if host.lower() not in GITHUB_HOSTS:` became `if host not in GITHUB_HOSTS:`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_the_host_case_does_not_matter ______________________
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:103: in test_the_host_case_does_not_matter
    assert git_origin.classify("https://GitHub.com/O/R") == ("github", "O/R")
E   AssertionError: assert ('not-github', None) == ('github', 'O/R')
E     
E     At index 0 diff: 'not-github' != 'github'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_the_host_case_does_not_matter
1 failed in 1.56s
```

- **Restore.** The inverse Edit. **Restore receipt:** `    if host.lower() not in GITHUB_HOSTS:`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.41s
```

## G4: a GitHub host with a path that is not owner/name is unreadable

- **Guarded element and axis.** The path rule in `classify` (two parts, each `[A-Za-z0-9_.-]+` and not only dots).
- **Neutralization.** The refusal's `return (GITHUB_UNREADABLE, None)` became `return (GITHUB, path)`, so any path reads as github.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_github_host_with_a_path_that_is_not_owner_and_name_is_unreadable[https://github.com/o] _
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:109: in test_a_github_host_with_a_path_that_is_not_owner_and_name_is_unreadable
    assert git_origin.classify(url) == UNREADABLE
E   AssertionError: assert ('github', 'o') == ('github-unreadable', None)
E     
E     At index 0 diff: 'github' != 'github-unreadable'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_a_github_host_with_a_path_that_is_not_owner_and_name_is_unreadable[https://github.com/o]
1 failed in 1.39s
```

- **Restore.** The inverse Edit. **Restore receipt:** `        return (GITHUB_UNREADABLE, None)`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.23s
```

## G5: same_repository folds case

- **Guarded element and axis.** The `a.lower() == b.lower()` return of `same_repository`: GitHub owner and repository names are case-insensitive. One neutralization, three consumers (the helper, `cloud_recover._from_elsewhere`, and `check_release_bump._find_release_pr`, which loads the same file by path), run in one invocation.
- **Neutralization.** `return a.lower() == b.lower()` became `return a == b`.
- **Raw red:**

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_same_repository_compares_slugs_ignoring_case_and_refuses_empty[O/R-o/r-True] _
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:138: in test_same_repository_compares_slugs_ignoring_case_and_refuses_empty
    assert git_origin.same_repository(a, b) is expected
E   AssertionError: assert False is True
E    +  where False = <function same_repository at 0x7f513dfcb4c0>('O/R', 'o/r')
E    +    where <function same_repository at 0x7f513dfcb4c0> = git_origin.same_repository
___ test_from_elsewhere_reads_a_differently_cased_same_repository_as_its_own ___
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:350: in test_from_elsewhere_reads_a_differently_cased_same_repository_as_its_own
    assert cloud_recover._from_elsewhere(_pull("Acme/Widgets"), "acme/widgets") is False
E   AssertionError: assert True is False
E    +  where True = <function _from_elsewhere at 0x7f513d204180>({'head': {'ref': 'b', 'repo': {'full_name': 'Acme/Widgets'}}}, 'acme/widgets')
E    +    where <function _from_elsewhere at 0x7f513d204180> = cloud_recover._from_elsewhere
E    +    and   {'head': {'ref': 'b', 'repo': {'full_name': 'Acme/Widgets'}}} = _pull('Acme/Widgets')
__ test_find_release_pr_finds_a_pr_whose_head_repository_differs_only_in_case __
.github/scripts/tests/test_check_release_bump_origin_2452.py:64: in test_find_release_pr_finds_a_pr_whose_head_repository_differs_only_in_case
    assert _find(monkeypatch, "ZWrose/Superheroes") == {"number": 7, "head_ref": _REF, "head_sha": "abc"}
E   AssertionError: assert None == {'number': 7, 'head_ref': 'release-please--branches--main--components--superheroes', 'head_sha': 'abc'}
E    +  where None = _find(<_pytest.monkeypatch.MonkeyPatch object at 0x7f513d951100>, 'ZWrose/Superheroes')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_same_repository_compares_slugs_ignoring_case_and_refuses_empty[O/R-o/r-True]
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_from_elsewhere_reads_a_differently_cased_same_repository_as_its_own
FAILED .github/scripts/tests/test_check_release_bump_origin_2452.py::test_find_release_pr_finds_a_pr_whose_head_repository_differs_only_in_case
3 failed in 1.62s
```

- **Restore.** The inverse Edit. **Restore receipt:** `    return a.lower() == b.lower()`.
- **Raw green:**

```
...                                                                      [100%]
3 passed in 1.44s
```

## G6: same_repository refuses an empty name

- **Guarded element and axis.** The `and a and b` of the entry test in `same_repository`: two empty names are not the same repository.
- **Neutralization.** `if not (isinstance(a, str) and isinstance(b, str) and a and b):` became `if not (isinstance(a, str) and isinstance(b, str)):`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_same_repository_compares_slugs_ignoring_case_and_refuses_empty[--False] _
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:138: in test_same_repository_compares_slugs_ignoring_case_and_refuses_empty
    assert git_origin.same_repository(a, b) is expected
E   AssertionError: assert True is False
E    +  where True = <function same_repository at 0x7f41602af4c0>('', '')
E    +    where <function same_repository at 0x7f41602af4c0> = git_origin.same_repository
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_same_repository_compares_slugs_ignoring_case_and_refuses_empty[--False]
1 failed in 1.44s
```

- **Restore.** The inverse Edit. **Restore receipt:** `    if not (isinstance(a, str) and isinstance(b, str) and a and b):`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 8.34s
```

## G7: normalize_remote reads a file:// URL as no key

- **Guarded element and axis.** The early `return None` on `git_origin.is_file_url(s)` in `store_core.normalize_remote`: a file:// URL is a local transport and has no host/path key.
- **Neutralization.** `return None` under `if git_origin.is_file_url(s):` became `pass`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_normalize_remote_reads_a_file_url_as_no_key[file://github.com/o/r.git] __
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_git_origin_2452.py:162: in test_normalize_remote_reads_a_file_url_as_no_key
    assert sc.normalize_remote(url) is None
E   AssertionError: assert 'github.com/o/r' is None
E    +  where 'github.com/o/r' = <function normalize_remote at 0x7f1e49840220>('file://github.com/o/r.git')
E    +    where <function normalize_remote at 0x7f1e49840220> = sc.normalize_remote
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_git_origin_2452.py::test_normalize_remote_reads_a_file_url_as_no_key[file://github.com/o/r.git]
1 failed in 1.37s
```

- **Restore.** The inverse Edit. **Restore receipt:** `    if git_origin.is_file_url(s):` then `        return None` (`store_core.py`, in `normalize_remote`).
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.51s
```

## G8: the commits read is pinned to github.com

- **Guarded element and axis.** `"--hostname", "github.com"` in `launcher._gh_commit_lookup`'s argv: the read is on github.com whatever `GH_HOST` says.
- **Neutralization.** The argv `["gh", "api", "--hostname", "github.com", "repos/%s/%s/commits/%s" % (owner, repo, sha), "--jq", ".sha"]` became `["gh", "api", "repos/%s/%s/commits/%s" % (owner, repo, sha), "--jq", ".sha"]`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_the_default_gh_call_asks_the_commits_endpoint ______________
/home/user/wt-2452-wo2/plugins/superheroes/lib/tests/test_launcher_cloud.py:893: in test_the_default_gh_call_asks_the_commits_endpoint
    assert seen == [(
E   AssertionError: assert [(['gh', 'api..., '.sha'], 7)] == [(['gh', 'api...jq', ...], 7)]
E     
E     At index 0 diff: (['gh', 'api', 'repos/acme/widgets/commits/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '--jq', '.sha'], 7) != (['gh', 'api', '--hostname', 'github.com', 'repos/acme/widgets/commits/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '--jq', '.sha'], 7)
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_the_default_gh_call_asks_the_commits_endpoint
1 failed in 2.05s
```

- **Restore.** The inverse Edit. **Restore receipt:** `            ["gh", "api", "--hostname", "github.com", "repos/%s/%s/commits/%s" % (owner, repo, sha), "--jq", ".sha"],` (`launcher.py`, in `_gh_commit_lookup`).
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.86s
```

## Not neutralized (named, not claimed)

- `launcher._origin_github_repo`'s mapping of the classifier's three answers, `_gh_branch_pulls`'s `--hostname` pin, and `_issue_comments`'s removal of `GH_HOST` are pinned by rows in `test_git_origin_2452.py` and `test_adopt_original_session.py`, but this record does not neutralize them one by one: they are outside the declared guarded-element set G1 to G8. They are unproven by this record.
