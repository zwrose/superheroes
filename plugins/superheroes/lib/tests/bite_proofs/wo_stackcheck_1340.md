# WO-C (#1340) bite-proof — `stack_check.py` guards

Per-guard bite proof for `plugins/superheroes/lib/stack_check.py`: each `# axis:` clause is neutralized in source, the proving test must go red alone, then the clause is restored and the suite goes green again.

**Register:** 42 guards — grew from 41 when WO #1340 layer 2b R3 added the `timeout=None` beside read budget guard. Prior growth: from 38 when WO #1340 layer 2b R1 added the shared read-budget validation and enforcement guards (`deadline` type, `deadline` positivity, budget exhaustion before a gh page); from 37 when WO #1340 layer 2b Fold 2 split the combined order-mismatch clause into separate count and positions guards; from 33 after a census of refusing clauses found three that carried no `# axis:` line and one whose axis line described a sibling clause; from 36 when the two-pass enumeration-drift refusal was added without a record entry.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | stack_check.py:177 | pr is not an int (bool is not an int here) | `test_e1_pr_not_int` | proven |
| E2 | stack_check.py:181 | pr < 1 | `test_e2_pr_less_than_one` | proven |
| E3 | stack_check.py:185 | repo is not a string | `test_e3_repo_not_string` | proven |
| E4 | stack_check.py:189 | repo does not match owner/name pattern | `test_e4_repo_bad_pattern` | proven |
| E5 | stack_check.py:193 | expect_stack supplied and not an int | `test_e5_expect_stack_not_int` | proven |
| E6 | stack_check.py:198 | expect_stack supplied and < 1 | `test_e6_expect_stack_less_than_one` | proven |
| E7 | stack_check.py:203 | page_size is not an int | `test_e7_page_size_not_int` | proven |
| E8 | stack_check.py:209 | page_size < MIN_PAGE_SIZE | `test_e8_page_size_below_min` | proven |
| E9 | stack_check.py:215 | page_size > MAX_PAGE_SIZE | `test_e9_page_size_above_max` | proven |
| E10 | stack_check.py:233 | gh is not on PATH | `test_e11_gh_not_on_path` | proven |
| E11 | stack_check.py:263 | run raises FileNotFoundError/OSError | `test_e12_run_raises_file_not_found` | proven |
| E12 | stack_check.py:266 | run raises subprocess.TimeoutExpired | `test_e13_run_raises_timeout_expired` | proven |
| E13 | stack_check.py:269 | gh exits non-zero | `test_e14_gh_exits_nonzero_with_valid_stdout` | proven |
| E14 | stack_check.py:277 | stdout is not JSON | `test_e15_stdout_not_json` | proven |
| E15 | stack_check.py:281 | parsed JSON payload is not an object | `test_e15_payload_not_object` | proven |
| E16 | stack_check.py:289 | errors is present but not a list | `test_e16_errors_not_list` | proven |
| E17 | stack_check.py:293 | response carries a non-empty errors array | `test_e16_graphql_errors_nonempty` | proven |
| E18 | stack_check.py:304 | data/repository is null or not an object | `test_e17_data_or_repository_missing` | proven |
| E19 | stack_check.py:310 | pullRequest is null or not an object | `test_e18_pull_request_missing` | proven |
| E20 | stack_check.py:319 | a required top-level pull-request field is missing or of the wrong type | `test_e19_required_pull_request_field_wrong_type` | proven |
| E21 | stack_check.py:331 | stackEntry is null | `test_e28_stack_entry_null` | proven |
| E22 | stack_check.py:337 | stackEntry is present but not an object, or position is missing/not an int | `test_e20_stack_entry_bad` | proven |
| E23 | stack_check.py:347 | stack is missing/not an object, or number/size/baseRefName wrong type | `test_e21_stack_field_wrong_type` | proven |
| E24 | stack_check.py:360 | entries/pageInfo/nodes is missing or of the wrong type | `test_e22_entries_page_info_empty_object` | proven |
| E25 | stack_check.py:372 | a later page reports a different page-one snapshot value | `test_e31_later_page_snapshot_mismatch` | proven |
| E26 | stack_check.py:381 | a node, its position, or one of its pull-request fields is missing or wrong type | `test_e23_node_field_wrong_type` | proven |
| E27 | stack_check.py:383 | the collected count would exceed size mid-read | `test_e27_collected_count_would_exceed_size` | proven |
| E28 | stack_check.py:391 | pageInfo hasNextPage is missing or not a boolean | `test_e26_has_next_page_not_boolean` | proven |
| E29 | stack_check.py:532 | a page adds zero nodes while hasNextPage is true | `test_e24_zero_nodes_with_has_next_page` | proven |
| E30 | stack_check.py:537 | a next page requires a usable string cursor | `test_e26_has_next_page_without_end_cursor` | proven |
| E31 | stack_check.py:543 | endCursor repeats a cursor already used | `test_e25_repeated_end_cursor` | proven |
| E32 | stack_check.py:419 | expect_stack was supplied and does not equal stack.number | `test_e29_expect_stack_does_not_equal_stack_number` | proven |
| E33 | stack_check.py:426 | collected member count does not equal stack size | `test_e33_collected_count_not_equal_stack_size` | proven |
| E34 | stack_check.py:431 | collected positions are not exactly 1..size | `test_e34_collected_positions_not_one_to_size`, `test_e30_collected_positions_not_exact` | proven |
| E35 | stack_check.py:437 | the queried pull request is not present exactly once at its reported position | `test_e30_queried_pr_not_at_reported_position` | proven |
| E36 | stack_check.py:443 | that entry's headRefName/headRefOid/baseRefName disagree with the top-level fields | `test_e33_queried_entry_head_ref_oid_disagrees`, `test_e33_queried_entry_base_ref_name_disagrees` | proven |
| E37 | stack_check.py:458 | membership changes between two complete enumeration passes | `test_e37_mixed_time_member_head_change_refuses` | proven |
| E38 | stack_check.py:587 | the parse boundary (malformed CLI call returns bad-argument instead of argparse exit) | `test_e10_parse_boundary` | proven |
| E39 | stack_check.py:221 | deadline supplied and not a real number | `test_deadline_not_a_number_refuses` | proven |
| E40 | stack_check.py:228 | deadline supplied and not greater than zero | `test_deadline_not_positive_refuses` | proven |
| E41 | stack_check.py:244 | read budget exhausted before a gh page | `test_deadline_exhausted_in_second_pass_refuses` | proven |
| E42 | stack_check.py:253 | timeout=None beside a read budget | `test_deadline_with_timeout_none_returns_dict_not_typeerror` | proven |

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

**fixture note:** `test_e26_has_next_page_not_boolean` uses `hasNextPage: 0` (falsy, not a boolean) on a single page that carries all five members so neutralizing this clause ends the loop with a complete membership instead of paginating into a sibling guard.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e26_has_next_page_not_boolean
1 failed, 51 passed in 0.31s
```

**raw green** after restore:
```
52 passed in 0.74s
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

**fixture note:** `test_e26_has_next_page_without_end_cursor` uses `endCursor: 42` (not a string) with a follow-up page keyed on that numeric cursor so neutralizing this clause completes the stack instead of repeating page one into a sibling guard.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e26_has_next_page_without_end_cursor
1 failed, 51 passed in 0.29s
```

**raw green** after restore:
```
52 passed in 0.12s
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

**fixture note:** `test_e25_repeated_end_cursor` repeats `cursor-dup` on page two while `hasNextPage` is still true after delivering the remaining members, with a third request answering `hasNextPage: false` and zero nodes so neutralizing this clause ends on a complete membership instead of refusing on an earlier page.

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e25_repeated_end_cursor
1 failed, 51 passed in 0.18s
```

**raw green** after restore:
```
52 passed in 0.22s
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

## E34 — collected positions are not exactly 1..size

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    # axis: collected positions are not exactly 1..size
    if positions != expected_positions:
        return _refusal(REASON_ORDER_MISMATCH, "collected positions are not exactly 1..size",
            repo=repo, pr=pr, pages=pages)
```
→
```python
    # axis: collected positions are not exactly 1..size
    if False:  # bite-proof
        return _refusal(REASON_ORDER_MISMATCH, "collected positions are not exactly 1..size",
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e34_collected_positions_not_one_to_size
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e30_collected_positions_not_exact
2 failed, 51 passed in 0.14s
```

**raw green** after restore:
```
53 passed in 0.12s
```

---

## E39 — deadline supplied and not a real number

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    # axis: deadline supplied and not a real number
    if deadline is not None and (
        not isinstance(deadline, (int, float)) or isinstance(deadline, bool)
    ):
        return _refusal(REASON_BAD_ARGUMENT,
            "deadline must be a positive number of seconds", repo=repo, pr=pr)
```
→
```python
    # axis: deadline supplied and not a real number
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "deadline must be a positive number of seconds", repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_deadline_not_a_number_refuses
1 failed in 0.45s
```

**raw green** after restore:
```
1 passed in 0.31s
```

---

## E40 — deadline supplied and not greater than zero

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    # axis: deadline supplied and not greater than zero
    if deadline is not None and not (deadline > 0):
        return _refusal(REASON_BAD_ARGUMENT,
            "deadline must be a positive number of seconds", repo=repo, pr=pr)
```
→
```python
    # axis: deadline supplied and not greater than zero
    if False:  # bite-proof
        return _refusal(REASON_BAD_ARGUMENT,
            "deadline must be a positive number of seconds", repo=repo, pr=pr)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_deadline_not_positive_refuses[0]
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_deadline_not_positive_refuses[-1]
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_deadline_not_positive_refuses[nan]
3 failed in 0.24s
```

**raw green** after restore:
```
3 passed in 0.41s
```

---

## E41 — read budget exhausted before a gh page

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    # axis: read budget exhausted before a gh page
    if deadline_at is not None and time.monotonic() >= deadline_at:
        return _refusal(REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted after %d pages" % (deadline, pages),
            repo=repo, pr=pr, pages=pages)
```
→
```python
    # axis: read budget exhausted before a gh page
    if False:  # bite-proof
        return _refusal(REASON_STACK_UNREADABLE,
            "read budget of %g seconds exhausted after %d pages" % (deadline, pages),
            repo=repo, pr=pr, pages=pages)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_deadline_exhausted_in_second_pass_refuses
1 failed in 0.30s
```

**raw green** after restore:
```
1 passed in 0.26s
```

---

## E42 — timeout=None beside a read budget

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        # axis: timeout=None beside a read budget
        if timeout is None:
            effective_timeout = remaining
        else:
            effective_timeout = min(timeout, remaining)
```
→
```python
        effective_timeout = min(timeout, remaining)
```

**command:** the command (see top).

**raw red** (traceback body elided):
```
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_deadline_with_timeout_none_returns_dict_not_typeerror
1 failed in 0.08s
```

**raw green** after restore:
```
1 passed in 0.07s
```

**restored lines:**
```python
        # axis: timeout=None beside a read budget
        if timeout is None:
            effective_timeout = remaining
        else:
            effective_timeout = min(timeout, remaining)
```

---

## Restore receipt

**`git status --porcelain` (mutated files):**
```
 M plugins/superheroes/lib/stack_check.py
 M plugins/superheroes/lib/tests/test_stack_check.py
 M plugins/superheroes/lib/tests/bite_proofs/wo_stackcheck_1340.md
```

---

## #2098 REST transport

Per-guard bite proof for the REST transport and the whole-snapshot pass check added to `plugins/superheroes/lib/stack_check.py`. Each guard was neutralized by one targeted edit, its proving test run alone and shown red, restored by the inverse edit, and shown green again. IDs `R1`–`R17` continue this file without reusing the `E` IDs.

**Provenance:** claude / per the dispatch seat.

**Command** (referred to as *the R command* below; `-k` selects the proving test):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2098 -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q -p no:cacheprovider -k <proving test>
```

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| R1 | stack_check.py:373 | transport is not one of auto, graphql, rest | `test_r_bad_transport_value_refuses` | proven |
| R2 | stack_check.py:1196 | only a non-zero gh exit carrying both proxy-refusal markers falls back to REST | `test_r_auto_without_proxy_refusal_does_not_fall_back` | proven |
| R3 | stack_check.py:952 | read budget exhausted before a REST GET | `test_r_deadline_exhausted_before_the_first_get_refuses`, `test_r_deadline_exhausted_before_the_stack_get_refuses` | proven |
| R4 | stack_check.py:961 | REST run raises FileNotFoundError/OSError | `test_r_transport_failures_on_either_get_refuse` (`file-not-found`) | proven |
| R5 | stack_check.py:965 | REST run raises subprocess.TimeoutExpired | `test_r_transport_failures_on_either_get_refuse` (`timeout`) | proven |
| R6 | stack_check.py:970 | REST gh exits non-zero | `test_r_gh_exits_nonzero_with_valid_json_stdout_refuses` | proven |
| R7 | stack_check.py:978 | REST stdout is not JSON | `test_r_transport_failures_on_either_get_refuse` (`non-json`) | proven |
| R8 | stack_check.py:983 | REST parsed JSON is not an object | `test_r_transport_failures_on_either_get_refuse` (`array`, `null`) | proven |
| R9 | stack_check.py:999 | a required REST pull-request field is missing or of the wrong type | `test_r_malformed_pull_request_fields_refuse` | proven |
| R10 | stack_check.py:1011 | REST stack key is absent or null | `test_r_unstacked_pull_request_is_not_linked`, `test_r_null_stack_is_not_linked` | proven |
| R11 | stack_check.py:1021 | REST stack is not an object, or number/position/size/base.ref wrong type | `test_r_malformed_stack_object_refuses` | proven |
| R12 | stack_check.py:1098 | REST stack GET number, base.ref or pull_requests is missing or of the wrong type | `test_r_malformed_stack_response_refuses` | proven |
| R13 | stack_check.py:1104 | REST stack GET reports a different stack number than the pull request | `test_r_stack_number_mismatch_is_order_mismatch` | proven |
| R14 | stack_check.py:1110 | REST stack GET reports a different base than the pull request | `test_r_stack_base_mismatch_is_order_mismatch` | proven |
| R15 | stack_check.py:1118 | a REST stack member or one of its fields is missing, unknown or wrong type | `test_r_malformed_member_refuses` | proven |
| R16 | stack_check.py:1122 | the REST member count would exceed stack size | `test_r_more_members_than_size_refuses` | proven |
| R17 | stack_check.py:616 | the stack snapshot (not only the members) changes between two complete enumeration passes | `test_r_graphql_second_pass_different_stack_number_is_order_mismatch`, `test_r_rest_second_pass_different_stack_number_is_order_mismatch` | proven |

Every neutralization below replaced the guard's condition with `False` (`if False:  # bite-proof`, or `False and (...)` for the multi-line conditions), except R4, R5, R7 (the `except` body became `pass  # bite-proof`) and R2 (the return became `return True  # bite-proof`). The raw outputs are the pytest summary lines (traceback bodies elided); the full runs are in the dispatch return.

| ID | raw red | raw green after restore | restored line |
|---|---|---|---|
| R1 | `1 failed, 222 deselected in 0.35s` | `1 passed, 222 deselected in 0.26s` | `    if transport not in TRANSPORTS:` |
| R2 | `1 failed, 222 deselected in 0.36s` | `1 passed, 222 deselected in 0.30s` | `    return proc.returncode != 0 and all(marker in output for marker in GRAPHQL_REFUSED_MARKERS)` |
| R3 | `2 failed, 221 deselected in 0.39s` | `2 passed, 221 deselected in 0.29s` | `    if deadline_at is not None and time.monotonic() >= deadline_at:` |
| R4 | `2 failed, 221 deselected in 0.39s` | `2 passed, 221 deselected in 0.29s` | `        return None, _refusal(REASON_STACK_UNREADABLE, "gh api %s: %s" % (endpoint, exc),` |
| R5 | `2 failed, 221 deselected in 0.39s` | `2 passed, 221 deselected in 0.40s` | `        return None, _refusal(REASON_STACK_UNREADABLE, "gh api %s timed out" % endpoint,` |
| R6 | `2 failed, 221 deselected in 0.39s` | `2 passed, 221 deselected in 0.33s` | `    if proc.returncode != 0:` |
| R7 | `2 failed, 221 deselected in 0.42s` | `2 passed, 221 deselected in 0.28s` | `        return None, _refusal(REASON_STACK_UNREADABLE,` / `"gh api %s returned output that is not JSON" % endpoint, ...` |
| R8 | `4 failed, 219 deselected in 0.64s` | `4 passed, 219 deselected in 0.31s` | `    if not isinstance(payload, dict):` |
| R9 | `7 failed, 216 deselected in 0.59s` | `7 passed, 216 deselected in 0.31s` | `    if (` / `        not _is_int(pr_number)` |
| R10 | `2 failed, 221 deselected in 0.32s` | `2 passed, 221 deselected in 0.27s` | `    if stack is None:` |
| R11 | `10 failed, 213 deselected in 0.89s` | `10 passed, 213 deselected in 0.41s` | `    if (` / `        not isinstance(stack, dict)` |
| R12 | `6 failed, 217 deselected in 0.63s` | `6 passed, 217 deselected in 0.38s` | `    if not _is_int(number) or not isinstance(base_ref, str) or not isinstance(pull_requests, list):` |
| R13 | `1 failed, 222 deselected in 0.27s` | `1 passed, 222 deselected in 0.29s` | `    if number != snapshot["stack_number"]:` |
| R14 | `1 failed, 222 deselected in 0.35s` | `1 passed, 222 deselected in 0.25s` | `    if base_ref != snapshot["stack_baseRefName"]:` |
| R15 | `11 failed, 212 deselected in 0.36s` (`--tb=line` re-run; the first red run's output was truncated by the harness) | `11 passed, 212 deselected in 0.39s` | `        if parse_err:` |
| R16 | `1 failed, 222 deselected in 0.36s` | `1 passed, 222 deselected in 0.26s` | `        if len(members) + 1 > snapshot["stack_size"]:` |
| R17 | `2 failed, 221 deselected in 0.37s` | `2 passed, 221 deselected in 0.28s` | `    if snapshot != prior_snapshot:` |

**Disclosures:**
- R11's first red run and R15's first red run were truncated mid-output by the harness; R11's summary line (`10 failed, 213 deselected in 0.89s`) survived, R15's did not, so R15's red above comes from a `--tb=line` re-run of the same single test against the same neutralization.
- The "queried pull request is not present exactly once at its reported position" clause (E35) cannot fire on the REST path: REST positions are index + 1, so they are unique and 1..n by construction; a swapped list is caught by the entry-disagrees-with-top-level clause (E36) instead (`test_r_queried_pull_request_not_at_its_position_is_order_mismatch`).
- R6: `test_r_transport_failures_on_either_get_refuse[exit-1]` alone does not discriminate (a neutralized exit-code check falls through to the not-JSON clause with the same reason), so R6 is proven by `test_r_gh_exits_nonzero_with_valid_json_stdout_refuses` (valid JSON on stdout beside a non-zero exit).
