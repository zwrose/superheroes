# WO-C (#1340) bite-proof — `stack_check.py` guards

Per-guard bite proof for `plugins/superheroes/lib/stack_check.py`: each `# axis:` clause is neutralized in source, the proving test must go red alone, then the clause is restored and the suite goes green again.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | stack_check.py:187 | pr is not an int (bool is not an int here) | `test_e1_pr_not_int` | proven |
| E2 | stack_check.py:191 | pr < 1 | `test_e2_pr_less_than_one` | proven |
| E3 | stack_check.py:195 | repo is not a string | `test_e3_repo_not_string` | proven |
| E4 | stack_check.py:199 | repo does not match owner/name pattern | `test_e4_repo_bad_pattern` | proven |
| E5 | stack_check.py:203 | expect_stack supplied and not an int | `test_e5_expect_stack_not_int` | proven |
| E6 | stack_check.py:208 | expect_stack supplied and < 1 | `test_e6_expect_stack_less_than_one` | proven |
| E7 | stack_check.py:213 | page_size is not an int | `test_e7_page_size_not_int` | proven |
| E8 | stack_check.py:219 | page_size < MIN_PAGE_SIZE | `test_e8_page_size_below_min` | proven |
| E9 | stack_check.py:225 | page_size > MAX_PAGE_SIZE | `test_e9_page_size_above_max` | proven |
| E10 | stack_check.py:233 | gh is not on PATH | `test_e11_gh_not_on_path` | UNPROVEN |
| E11 | stack_check.py:249 | run raises FileNotFoundError/OSError | `test_e12_run_raises_file_not_found` | proven |
| E12 | stack_check.py:252 | run raises subprocess.TimeoutExpired | `test_e13_run_raises_timeout_expired` | proven |
| E13 | stack_check.py:257 | gh exits non-zero | `test_e14_gh_exits_nonzero` | UNPROVEN |
| E14 | stack_check.py:265 | stdout is not JSON | `test_e15_stdout_not_json` | proven |
| E15 | stack_check.py:276 | response carries a non-empty errors array | `test_e16_graphql_errors_nonempty` | proven |
| E16 | stack_check.py:285 | data/repository is null or not an object | `test_e17_data_or_repository_missing` | proven |
| E17 | stack_check.py:291 | pullRequest is null or not an object | `test_e18_pull_request_missing` | proven |
| E18 | stack_check.py:300 | a required top-level pull-request field is missing or of the wrong type | `test_e19_required_pull_request_field_wrong_type` | proven |
| E19 | stack_check.py:312 | stackEntry is null | `test_e28_stack_entry_null` | proven |
| E20 | stack_check.py:318 | stackEntry is present but not an object, or position is missing/not an int | `test_e20_stack_entry_bad` | proven |
| E21 | stack_check.py:328 | stack is missing/not an object, or number/size/baseRefName wrong type | `test_e21_stack_field_wrong_type` | proven |
| E22 | stack_check.py:341 | entries/pageInfo/nodes is missing or of the wrong type | `test_e22_entries_page_info_nodes_wrong_type` | UNPROVEN |
| E23 | stack_check.py:351 | a later page reports a different page-one snapshot value | `test_e31_later_page_snapshot_mismatch` | proven |
| E24 | stack_check.py:360 | a node, its position, or one of its pull-request fields is missing or wrong type | `test_e23_node_field_wrong_type` | proven |
| E25 | stack_check.py:362 | the collected count would exceed size mid-read | `test_e27_collected_count_would_exceed_size` | proven |
| E26 | stack_check.py:381 | a page adds zero nodes while hasNextPage is true | `test_e24_zero_nodes_with_has_next_page` | proven |
| E27 | stack_check.py:386 | hasNextPage is true with a null or absent endCursor | `test_e26_has_next_page_without_end_cursor` | UNPROVEN |
| E28 | stack_check.py:395 | endCursor repeats a cursor already used | `test_e25_repeated_end_cursor` | proven |
| E29 | stack_check.py:403 | expect_stack was supplied and does not equal stack.number | `test_happy_path_expect_stack_matches` | UNPROVEN |
| E30 | stack_check.py:408 | the collected count is not size | `test_e29_collected_count_or_positions_mismatch` | UNPROVEN |
| E31 | stack_check.py:415 | the positions are not exactly 1..size | `test_e29_collected_count_or_positions_mismatch` | UNPROVEN |
| E32 | stack_check.py:421 | the queried pull request is not present exactly once at its reported position | `test_e30_queried_pr_not_at_reported_position` | proven |
| E33 | stack_check.py:427 | that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields | `test_happy_path_multi_page` | UNPROVEN |
| E34 | stack_check.py:473 | the parse boundary (malformed CLI call returns bad-argument instead of argparse exit) | `test_e10_parse_boundary` | UNPROVEN |

---

## E1 — pr is not an int (bool is not an int here)

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if not _is_int(pr):
        return _refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer", repo=repo, pr=None)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer", repo=repo, pr=None)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e1_pr_not_int
1 failed, 40 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E2 — pr < 1

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if pr < 1:
        return _refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer", repo=repo, pr=None)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT, "pr must be a positive integer", repo=repo, pr=None)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e2_pr_less_than_one
1 failed, 40 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.21s
```

---

## E3 — repo is not a string

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if not isinstance(repo, str):
        return _refusal(REASON_BAD_ARGUMENT, "repo must be owner/name", repo=None, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT, "repo must be owner/name", repo=None, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e3_repo_not_string
1 failed, 40 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E4 — repo does not match owner/name pattern

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if not _REPO_RE.match(repo):
        return _refusal(REASON_BAD_ARGUMENT, "repo must be owner/name", repo=None, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT, "repo must be owner/name", repo=None, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e4_repo_bad_pattern
1 failed, 40 passed in 0.25s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E5 — expect_stack supplied and not an int

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if expect_stack is not None and not _is_int(expect_stack):
        return _refusal(REASON_BAD_ARGUMENT,
            "expect_stack must be a positive integer", repo=repo, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "expect_stack must be a positive integer", repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e5_expect_stack_not_int
1 failed, 40 passed in 0.23s
```

**raw green** after restore:
```
41 passed in 0.22s
```

---

## E6 — expect_stack supplied and < 1

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if expect_stack is not None and expect_stack < 1:
        return _refusal(REASON_BAD_ARGUMENT,
            "expect_stack must be a positive integer", repo=repo, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "expect_stack must be a positive integer", repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e6_expect_stack_less_than_one
1 failed, 40 passed in 0.25s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E7 — page_size is not an int

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if not _is_int(page_size):
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e7_page_size_not_int
1 failed, 40 passed in 0.26s
```

**raw green** after restore:
```
41 passed in 0.21s
```

---

## E8 — page_size < MIN_PAGE_SIZE

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if page_size < MIN_PAGE_SIZE:
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e8_page_size_below_min
1 failed, 40 passed in 0.23s
```

**raw green** after restore:
```
41 passed in 0.24s
```

---

## E9 — page_size > MAX_PAGE_SIZE

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if page_size > MAX_PAGE_SIZE:
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "page_size must be an integer between %d and %d" % (MIN_PAGE_SIZE, MAX_PAGE_SIZE),
            repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e9_page_size_above_max
1 failed, 40 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.24s
```

---

## E10 — gh is not on PATH

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if not shutil.which("gh"):
        return _refusal(REASON_STACK_UNREADABLE, "gh not on PATH", repo=repo, pr=pr)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_STACK_UNREADABLE, "gh not on PATH", repo=repo, pr=pr)
```

**command:** the command (see top).

**verdict: UNPROVEN** — two tests failed (not exactly one): `test_e11_gh_not_on_path` and `test_cli_refusal_projection`.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e11_gh_not_on_path
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_cli_refusal_projection
2 failed, 39 passed in 0.58s
```

**raw green** after restore:
```
41 passed in 0.22s
```

---

## E11 — run raises FileNotFoundError/OSError

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        except (FileNotFoundError, OSError) as exc:
            # axis: run raises FileNotFoundError/OSError
            return _refusal(REASON_STACK_UNREADABLE, str(exc), repo=repo, pr=pr, pages=pages)
```
→
```python
        except (FileNotFoundError, OSError) as exc:
            # axis: run raises FileNotFoundError/OSError
            pass  # bite-proof
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e12_run_raises_file_not_found
1 failed, 40 passed in 0.24s
```

**raw green** after restore:
```
41 passed in 0.22s
```

---

## E12 — run raises subprocess.TimeoutExpired

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        except subprocess.TimeoutExpired:
            # axis: run raises subprocess.TimeoutExpired
            return _refusal(REASON_STACK_UNREADABLE, "gh call timed out", repo=repo, pr=pr, pages=pages)
```
→
```python
        except subprocess.TimeoutExpired:
            # axis: run raises subprocess.TimeoutExpired
            pass  # bite-proof
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e13_run_raises_timeout_expired
1 failed, 40 passed in 0.24s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E13 — gh exits non-zero

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if proc.returncode != 0:
            return _refusal(REASON_STACK_UNREADABLE, _stderr(proc) or "gh api graphql failed",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE, _stderr(proc) or "gh api graphql failed",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; non-zero `returncode` refusal is also produced by the stdout-is-not-JSON guard (E14) on empty stdout.

**raw red** (traceback body elided):
```
41 passed in 0.20s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E14 — stdout is not JSON

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        except json.JSONDecodeError:
            # axis: stdout is not JSON
            return _refusal(REASON_STACK_UNREADABLE,
```
→
```python
        except json.JSONDecodeError:
            # axis: stdout is not JSON
            pass  # bite-proof
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e15_stdout_not_json
1 failed, 40 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.21s
```

---

## E15 — response carries a non-empty errors array

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if errors:
            return _refusal(REASON_STACK_UNREADABLE, json.dumps(errors), repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE, json.dumps(errors), repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e16_graphql_errors_nonempty
1 failed, 40 passed in 0.25s
```

**raw green** after restore:
```
41 passed in 0.21s
```

---

## E16 — data/repository is null or not an object

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if not isinstance(data, dict) or not isinstance(repository, dict):
            return _refusal(REASON_STACK_UNREADABLE,
                "graphql data/repository is null or not an object", repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "graphql data/repository is null or not an object", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e17_data_or_repository_missing
1 failed, 40 passed in 0.25s
```

**raw green** after restore:
```
41 passed in 0.20s
```

---

## E17 — pullRequest is null or not an object

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if not isinstance(pull_request, dict):
            return _refusal(REASON_STACK_UNREADABLE, "graphql pullRequest is null or not an object",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE, "graphql pullRequest is null or not an object",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e18_pull_request_missing
1 failed, 40 passed in 0.27s
```

**raw green** after restore:
```
41 passed in 0.21s
```

---

## E18 — a required top-level pull-request field is missing or of the wrong type

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if (
            not _is_int(pr_number)
            or not isinstance(pr_base_ref, str)
            or not isinstance(pr_head_ref, str)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "required pullRequest field is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e19_required_pull_request_field_wrong_type
1 failed, 40 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.19s
```

---

## E19 — stackEntry is null

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if stack_entry is None:
            return _refusal(REASON_NOT_LINKED,
                "pull request is not in a stack", repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_NOT_LINKED,
                "pull request is not in a stack", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e28_stack_entry_null
1 failed, 40 passed in 0.23s
```

**raw green** after restore:
```
41 passed in 0.14s
```

---

## E20 — stackEntry is present but not an object, or position is missing/not an int

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if not isinstance(stack_entry, dict) or not _is_int(entry_position):
            return _refusal(REASON_STACK_UNREADABLE,
                "stackEntry is not an object or position is missing or not an integer",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "stackEntry is not an object or position is missing or not an integer",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e20_stack_entry_bad
1 failed, 40 passed in 0.13s
```

**raw green** after restore:
```
41 passed in 0.12s
```

---

## E21 — stack is missing/not an object, or number/size/baseRefName wrong type

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if (
            not isinstance(stack, dict)
            or not _is_int(stack_number)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE, "stack field is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e21_stack_field_wrong_type
1 failed, 40 passed in 0.12s
```

**raw green** after restore:
```
41 passed in 0.11s
```

---

## E22 — entries/pageInfo/nodes is missing or of the wrong type

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if not isinstance(entries, dict) or not isinstance(page_info, dict) or not isinstance(nodes, list):
            return _refusal(REASON_STACK_UNREADABLE,
                "stack entries/pageInfo/nodes is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "stack entries/pageInfo/nodes is missing or of the wrong type",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; wrong-type `nodes` is also refused by the node-field guard (E24) when iteration reaches `parse_err`.

**raw red** (traceback body elided):
```
41 passed in 0.10s
```

**raw green** after restore:
```
41 passed in 0.12s
```

---

## E23 — a later page reports a different page-one snapshot value

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
            if not _snapshot_matches(snapshot, pull_request, stack_entry, stack):
                return _refusal(REASON_ORDER_MISMATCH,
                    "later page disagrees with page-one snapshot", repo=repo, pr=pr, pages=pages)
```
→
```python
            if False:  # bite-proof
                return _refusal(REASON_ORDER_MISMATCH,
                    "later page disagrees with page-one snapshot", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e31_later_page_snapshot_mismatch
1 failed, 40 passed in 0.14s
```

**raw green** after restore:
```
41 passed in 0.11s
```

---

## E24 — a node, its position, or one of its pull-request fields is missing or wrong type

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
            if parse_err:
                # axis: a node, its position, or one of its pull-request fields is missing or wrong type
                return _refusal(REASON_STACK_UNREADABLE, parse_err, repo=repo, pr=pr, pages=pages)
```
→
```python
            if False:  # bite-proof
                # axis: a node, its position, or one of its pull-request fields is missing or wrong type
                return _refusal(REASON_STACK_UNREADABLE, parse_err, repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e23_node_field_wrong_type
1 failed, 40 passed in 0.16s
```

**raw green** after restore:
```
41 passed in 0.14s
```

---

## E25 — the collected count would exceed size mid-read

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
            if len(collected) + 1 > stack_size:
                return _refusal(REASON_STACK_UNREADABLE,
                    "collected member count would exceed stack size", repo=repo, pr=pr, pages=pages)
```
→
```python
            if False:  # bite-proof
                return _refusal(REASON_STACK_UNREADABLE,
                    "collected member count would exceed stack size", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e27_collected_count_would_exceed_size
1 failed, 40 passed in 0.21s
```

**raw green** after restore:
```
41 passed in 0.17s
```

---

## E26 — a page adds zero nodes while hasNextPage is true

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if added == 0:
            return _refusal(REASON_STACK_UNREADABLE,
                "page added zero nodes while hasNextPage is true", repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "page added zero nodes while hasNextPage is true", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e24_zero_nodes_with_has_next_page
1 failed, 40 passed in 0.20s
```

**raw green** after restore:
```
41 passed in 0.16s
```

---

## E27 — hasNextPage is true with a null or absent endCursor

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if end_cursor is None:
            return _refusal(REASON_STACK_UNREADABLE,
                "hasNextPage is true but endCursor is null or absent",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "hasNextPage is true but endCursor is null or absent",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; null `endCursor` is also refused by the `endCursor is not a string` check immediately below.

**raw red** (traceback body elided):
```
41 passed in 0.16s
```

**raw green** after restore:
```
41 passed in 0.17s
```

---

## E28 — endCursor repeats a cursor already used

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if end_cursor in used_cursors:
            return _refusal(REASON_STACK_UNREADABLE, "endCursor repeats a cursor already used",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE, "endCursor repeats a cursor already used",
                repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e25_repeated_end_cursor
1 failed, 40 passed in 0.19s
```

**raw green** after restore:
```
41 passed in 0.15s
```

---

## E29 — expect_stack was supplied and does not equal stack.number

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if expect_stack is not None and expect_stack != snapshot["stack_number"]:
        return _refusal(REASON_ORDER_MISMATCH, "expect_stack does not equal stack number",
            repo=repo, pr=pr, pages=pages)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_ORDER_MISMATCH, "expect_stack does not equal stack number",
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; no test supplies `expect_stack` that disagrees with `stack.number` (happy-path test uses a matching value).

**raw red** (traceback body elided):
```
41 passed in 0.20s
```

**raw green** after restore:
```
41 passed in 0.16s
```

---

## E30 — the collected count is not size

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if len(collected) != stack_size:
        return _refusal(REASON_ORDER_MISMATCH, "collected member count does not equal stack size",
            repo=repo, pr=pr, pages=pages)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_ORDER_MISMATCH, "collected member count does not equal stack size",
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; count mismatch is also refused by the positions guard (E31) on the same proving test input.

**raw red** (traceback body elided):
```
41 passed in 0.16s
```

**raw green** after restore:
```
41 passed in 0.14s
```

---

## E31 — the positions are not exactly 1..size

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if positions != expected_positions:
        return _refusal(REASON_ORDER_MISMATCH, "member positions are not exactly 1..size",
            repo=repo, pr=pr, pages=pages)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_ORDER_MISMATCH, "member positions are not exactly 1..size",
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; position mismatch is also refused by the collected-count guard (E30) first on the same proving test input.

**raw red** (traceback body elided):
```
41 passed in 0.15s
```

**raw green** after restore:
```
41 passed in 0.16s
```

---

## E32 — the queried pull request is not present exactly once at its reported position

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if len(members_at_position) != 1:
        return _refusal(REASON_ORDER_MISMATCH,
            "queried pull request is not present exactly once at its reported position",
            repo=repo, pr=pr, pages=pages)
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_ORDER_MISMATCH,
            "queried pull request is not present exactly once at its reported position",
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e30_queried_pr_not_at_reported_position
1 failed, 40 passed in 0.19s
```

**raw green** after restore:
```
41 passed in 0.16s
```

---

## E33 — that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if (
        member_at_position["number"] != snapshot["pr_number"]
        or member_at_position["headRefName"] != snapshot["pr_headRefName"]
        or member_at_position["headRefOid"] != snapshot["pr_headRefOid"]
```
→
```python
    if False:  # bite-proof
        return _refusal(REASON_ORDER_MISMATCH,
            "queried pull request entry disagrees with top-level pull request fields",
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**verdict: UNPROVEN** — pytest run was green; no test constructs disagreeing headRef/baseRef fields at the queried position.

**raw red** (traceback body elided):
```
41 passed in 0.15s
```

**raw green** after restore:
```
41 passed in 0.15s
```

---

## E34 — the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    except (_ParseError, SystemExit):
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        result = _bad_argument_result("invalid command-line arguments")
        sys.stdout.write(json.dumps(result) + "\n")
        return 1
```
→
```python
    except (_ParseError, SystemExit):
        # axis: the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)
        pass  # bite-proof
```

**command:** the command (see top).

**verdict: UNPROVEN** — five tests failed (not exactly one); `test_e10_parse_boundary` was not the sole failure (parametrized `test_cli_bad_argument_cases` also failed).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_cli_bad_argument_cases[argv3]
5 failed, 36 passed in 0.22s
```

**raw green** after restore:
```
41 passed in 0.15s
```

---

## Restore receipt

**`git status --porcelain` (mutated files):**
```
(empty)
```

**`shasum -a 256` before first neutralization / after last restore:**
```
acdc24c304a2370e6d0302d535caf03465646787902962c3522b4a544c9a4c86  plugins/superheroes/lib/stack_check.py
acdc24c304a2370e6d0302d535caf03465646787902962c3522b4a544c9a4c86  plugins/superheroes/lib/stack_check.py
40b6feab2b65b5d1b4795e37a6971e1984d236b7bc05e7e06b408722b71f74f4  plugins/superheroes/lib/tests/test_stack_check.py
40b6feab2b65b5d1b4795e37a6971e1984d236b7bc05e7e06b408722b71f74f4  plugins/superheroes/lib/tests/test_stack_check.py
```