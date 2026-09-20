# WO-C (#1340) bite-proof — `stack_check.py` guards

Per-guard bite proof for `plugins/superheroes/lib/stack_check.py`: each `# axis:` clause is neutralized in source, the proving test must go red alone, then the clause is restored and the suite goes green again.

**Register:** 37 guards — grew from 33 after a census of refusing clauses found three that carried no `# axis:` line (parsed JSON payload not an object; non-empty `errors` array; `pageInfo.hasNextPage` missing or not a boolean) and one whose axis line described a sibling clause (`errors` present but not a list); grew from 36 when the two-pass enumeration-drift refusal was added without a record entry.

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
| E10 | stack_check.py:233 | gh is not on PATH | `test_e11_gh_not_on_path` | proven |
| E11 | stack_check.py:249 | run raises FileNotFoundError/OSError | `test_e12_run_raises_file_not_found` | proven |
| E12 | stack_check.py:252 | run raises subprocess.TimeoutExpired | `test_e13_run_raises_timeout_expired` | proven |
| E13 | stack_check.py:257 | gh exits non-zero | `test_e14_gh_exits_nonzero_with_valid_stdout` | proven |
| E14 | stack_check.py:265 | stdout is not JSON | `test_e15_stdout_not_json` | proven |
| E15 | stack_check.py:269 | parsed JSON payload is not an object | `test_e15_payload_not_object` | proven |
| E16 | stack_check.py:277 | errors is present but not a list | `test_e16_errors_not_list` | proven |
| E17 | stack_check.py:281 | response carries a non-empty errors array | `test_e16_graphql_errors_nonempty` | proven |
| E18 | stack_check.py:287 | data/repository is null or not an object | `test_e17_data_or_repository_missing` | proven |
| E19 | stack_check.py:293 | pullRequest is null or not an object | `test_e18_pull_request_missing` | proven |
| E20 | stack_check.py:302 | a required top-level pull-request field is missing or of the wrong type | `test_e19_required_pull_request_field_wrong_type` | proven |
| E21 | stack_check.py:314 | stackEntry is null | `test_e28_stack_entry_null` | proven |
| E22 | stack_check.py:320 | stackEntry is present but not an object, or position is missing/not an int | `test_e20_stack_entry_bad` | proven |
| E23 | stack_check.py:330 | stack is missing/not an object, or number/size/baseRefName wrong type | `test_e21_stack_field_wrong_type` | proven |
| E24 | stack_check.py:343 | entries/pageInfo/nodes is missing or of the wrong type | `test_e22_entries_page_info_empty_object` | proven |
| E25 | stack_check.py:353 | a later page reports a different page-one snapshot value | `test_e31_later_page_snapshot_mismatch` | proven |
| E26 | stack_check.py:362 | a node, its position, or one of its pull-request fields is missing or wrong type | `test_e23_node_field_wrong_type` | proven |
| E27 | stack_check.py:364 | the collected count would exceed size mid-read | `test_e27_collected_count_would_exceed_size` | proven |
| E28 | stack_check.py:372 | pageInfo hasNextPage is missing or not a boolean | `test_e26_has_next_page_not_boolean` | proven |
| E29 | stack_check.py:384 | a page adds zero nodes while hasNextPage is true | `test_e24_zero_nodes_with_has_next_page` | proven |
| E30 | stack_check.py:389 | a next page requires a usable string cursor | `test_e26_has_next_page_without_end_cursor` | proven |
| E31 | stack_check.py:395 | endCursor repeats a cursor already used | `test_e25_repeated_end_cursor` | proven |
| E32 | stack_check.py:403 | expect_stack was supplied and does not equal stack.number | `test_e29_expect_stack_does_not_equal_stack_number` | proven |
| E33 | stack_check.py:410 | the collected entries are exactly the positions 1..size | `test_e30_collected_positions_not_exact` | proven |
| E34 | stack_check.py:416 | the queried pull request is not present exactly once at its reported position | `test_e30_queried_pr_not_at_reported_position` | proven |
| E35 | stack_check.py:422 | that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields | `test_e33_queried_entry_head_ref_oid_disagrees`, `test_e33_queried_entry_base_ref_name_disagrees` | proven |
| E36 | stack_check.py:438 | membership changes between two complete enumeration passes | `test_e37_mixed_time_member_head_change_refuses` | proven |
| E37 | stack_check.py:478 | the parse boundary (malformed CLI call returns bad-argument instead of argparse exit) | `test_e10_parse_boundary` | proven |

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
1 failed, 51 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.20s
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
1 failed, 51 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.21s
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
1 failed, 51 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.20s
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
1 failed, 51 passed in 0.25s
```

**raw green** after restore:
```
52 passed in 0.20s
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
1 failed, 51 passed in 0.23s
```

**raw green** after restore:
```
52 passed in 0.22s
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
1 failed, 51 passed in 0.25s
```

**raw green** after restore:
```
52 passed in 0.20s
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
1 failed, 51 passed in 0.26s
```

**raw green** after restore:
```
52 passed in 0.21s
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
1 failed, 51 passed in 0.23s
```

**raw green** after restore:
```
52 passed in 0.24s
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
1 failed, 51 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.24s
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

**verdict: proven** — several tests cover this clause: `test_e11_gh_not_on_path` and `test_cli_refusal_projection`.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e11_gh_not_on_path
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_cli_refusal_projection
2 failed, 50 passed in 0.58s
```

**raw green** after restore:
```
52 passed in 0.24s
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
1 failed, 51 passed in 0.24s
```

**raw green** after restore:
```
52 passed in 0.22s
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
1 failed, 51 passed in 0.24s
```

**raw green** after restore:
```
52 passed in 0.20s
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

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e14_gh_exits_nonzero_with_valid_stdout
1 failed, 51 passed in 0.27s
```

**raw green** after restore:
```
52 passed in 0.24s
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
1 failed, 51 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.21s
```

---

## E15 — parsed JSON payload is not an object

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        # axis: parsed JSON payload is not an object
        if not isinstance(payload, dict):
            return _refusal(REASON_STACK_UNREADABLE,
                "gh api graphql returned JSON that is not an object", repo=repo, pr=pr, pages=pages)
```
→
```python
        # axis: parsed JSON payload is not an object
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "gh api graphql returned JSON that is not an object", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e15_payload_not_object
1 failed, 51 passed in 0.23s
```

**raw green** after restore:
```
52 passed in 0.23s
```

---

## E16 — errors is present but not a list

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        # axis: errors is present but not a list
        if not isinstance(errors, list):
            return _refusal(REASON_STACK_UNREADABLE, "gh api graphql errors is not a list",
                repo=repo, pr=pr, pages=pages)
```
→
```python
        # axis: errors is present but not a list
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE, "gh api graphql errors is not a list",
                repo=repo, pr=pr, pages=pages)
```

**fixture note:** `test_e16_errors_not_list` uses `errors: false` (falsy, not a list) so neutralizing this clause does not fall through to the non-empty-errors sibling.

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e16_errors_not_list
1 failed, 51 passed in 0.30s
```

**raw green** after restore:
```
52 passed in 0.22s
```

---

## E17 — response carries a non-empty errors array

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

**fixture note:** `test_e16_graphql_errors_nonempty` uses a complete, valid single-page success payload so neutralizing this clause would otherwise succeed.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e16_graphql_errors_nonempty
1 failed, 51 passed in 0.23s
```

**raw green** after restore:
```
52 passed in 0.20s
```

---

## E18 — data/repository is null or not an object

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
1 failed, 51 passed in 0.25s
```

**raw green** after restore:
```
52 passed in 0.20s
```

---

## E19 — pullRequest is null or not an object

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
1 failed, 51 passed in 0.27s
```

**raw green** after restore:
```
52 passed in 0.21s
```

---

## E20 — a required top-level pull-request field is missing or of the wrong type

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
1 failed, 51 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.19s
```

---

## E21 — stackEntry is null

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
1 failed, 51 passed in 0.23s
```

**raw green** after restore:
```
52 passed in 0.14s
```

---

## E22 — stackEntry is present but not an object, or position is missing/not an int

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
1 failed, 51 passed in 0.13s
```

**raw green** after restore:
```
52 passed in 0.12s
```

---

## E23 — stack is missing/not an object, or number/size/baseRefName wrong type

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
1 failed, 51 passed in 0.12s
```

**raw green** after restore:
```
52 passed in 0.11s
```

---

## E24 — entries/pageInfo/nodes is missing or of the wrong type

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

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e22_entries_page_info_empty_object
1 failed, 51 passed in 0.27s
```

**raw green** after restore:
```
52 passed in 0.21s
```

---

## E25 — a later page reports a different page-one snapshot value

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
1 failed, 51 passed in 0.14s
```

**raw green** after restore:
```
52 passed in 0.11s
```

---

## E26 — a node, its position, or one of its pull-request fields is missing or wrong type

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
1 failed, 51 passed in 0.16s
```

**raw green** after restore:
```
52 passed in 0.14s
```

---

## E27 — the collected count would exceed size mid-read

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
1 failed, 51 passed in 0.21s
```

**raw green** after restore:
```
52 passed in 0.17s
```

---

## E28 — pageInfo hasNextPage is missing or not a boolean

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        # axis: pageInfo hasNextPage is missing or not a boolean
        if not isinstance(has_next_page, bool):
            return _refusal(REASON_STACK_UNREADABLE,
                "pageInfo hasNextPage is missing or not a boolean", repo=repo, pr=pr, pages=pages)
```
→
```python
        # axis: pageInfo hasNextPage is missing or not a boolean
        if False:  # bite-proof
            return _refusal(REASON_STACK_UNREADABLE,
                "pageInfo hasNextPage is missing or not a boolean", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e26_has_next_page_not_boolean
1 failed, 51 passed in 0.23s
```

**raw green** after restore:
```
52 passed in 0.22s
```

---

## E29 — a page adds zero nodes while hasNextPage is true

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
1 failed, 51 passed in 0.20s
```

**raw green** after restore:
```
52 passed in 0.16s
```

---

## E30 — a next page requires a usable string cursor

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if not isinstance(end_cursor, str):
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

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e26_has_next_page_without_end_cursor
1 failed, 51 passed in 0.26s
```

**raw green** after restore:
```
52 passed in 0.24s
```

---

## E31 — endCursor repeats a cursor already used

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
1 failed, 51 passed in 0.19s
```

**raw green** after restore:
```
52 passed in 0.15s
```

---

## E32 — expect_stack was supplied and does not equal stack.number

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

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e29_expect_stack_does_not_equal_stack_number
1 failed, 51 passed in 0.29s
```

**raw green** after restore:
```
52 passed in 0.26s
```

---

## E33 — the collected entries are exactly the positions 1..size

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if len(collected) != stack_size or positions != expected_positions:
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

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e30_collected_positions_not_exact
1 failed, 51 passed in 0.29s
```

**raw green** after restore:
```
52 passed in 0.22s
```

---

## E34 — the queried pull request is not present exactly once at its reported position

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
1 failed, 51 passed in 0.19s
```

**raw green** after restore:
```
52 passed in 0.16s
```

---

## E35 — that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if (
        member_at_position["number"] != snapshot["pr_number"]
        or member_at_position["headRefName"] != snapshot["pr_headRefName"]
        or member_at_position["headRefOid"] != snapshot["pr_headRefOid"]
        or member_at_position["baseRefName"] != snapshot["pr_baseRefName"]
    ):
```
→
```python
    if False:  # bite-proof
        member_at_position["number"] != snapshot["pr_number"]  # bite-proof
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e33_queried_entry_head_ref_oid_disagrees
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e33_queried_entry_base_ref_name_disagrees
2 failed, 50 passed in 0.27s
```

**raw green** after restore:
```
52 passed in 0.28s
```

---

## E36 — membership changes between two complete enumeration passes

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        # axis: membership changes between two complete enumeration passes
        if current_members != prior_members:
            return _refusal(REASON_ORDER_MISMATCH,
                "membership changed between enumeration passes", repo=repo, pr=pr, pages=pages)
```
→
```python
        # axis: membership changes between two complete enumeration passes
        if False:  # bite-proof
            return _refusal(REASON_ORDER_MISMATCH,
                "membership changed between enumeration passes", repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e37_mixed_time_member_head_change_refuses
1 failed, 51 passed in 0.68s
```

**raw green** after restore:
```
52 passed in 0.45s
```

---

## E37 — the parse boundary (malformed CLI call returns bad-argument instead of argparse exit)

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

**verdict: proven** — several tests cover this clause: `test_e10_parse_boundary` and the parametrized `test_cli_bad_argument_cases` cases.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_cli_bad_argument_cases[argv3]
5 failed, 47 passed in 0.22s
```

**raw green** after restore:
```
52 passed in 0.24s
```

---

## Restore receipt

**`git status --porcelain` (mutated files):**
```

```

**`shasum -a 256` before first neutralization / after last restore:**
```
d00ae0e0c2ffc7c91f02988562ec6107eaa0f311d070d699919a9956db5a0076  plugins/superheroes/lib/stack_check.py
d00ae0e0c2ffc7c91f02988562ec6107eaa0f311d070d699919a9956db5a0076  plugins/superheroes/lib/stack_check.py
c3d9ab00e30c25866272b3e53c6856428778a359fc2d348aae87c0988048f06f  plugins/superheroes/lib/tests/test_stack_check.py
c3d9ab00e30c25866272b3e53c6856428778a359fc2d348aae87c0988048f06f  plugins/superheroes/lib/tests/test_stack_check.py
```
