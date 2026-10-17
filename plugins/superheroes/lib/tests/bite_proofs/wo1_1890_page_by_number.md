# #1890 bite-proof — the review record's GitHub reads page by number (WO-1: `review_record._read_pages` and its three callers)

Per-element bite-proof for the detectors added in `plugins/superheroes/lib/tests/test_review_record.py` over `plugins/superheroes/lib/review_record.py`, following `plugins/superheroes/rubric/bite-proof.md`. Each element was neutralized with one targeted edit, its single test node ran alone and went red, the edit was undone by the inverse edit, `git diff --stat` over the file came back empty, and the same node ran green. No test file was edited between a red and its green.

The proofs ran twice. The implementer (WO-3) ran them in the build worktree, and the orchestrator re-ran all seven in a detached worktree at `35d2e6d9`. The receipts below are the orchestrator's re-run. The two runs agree on every red.

Command for every run (never `-k`, never filtered):

```
python3 -B -X pycache_prefix=/tmp/superheroes-pyc-probe -m pytest 'plugins/superheroes/lib/tests/test_review_record.py::<node>' -q -p no:cacheprovider
```

`R` = `plugins/superheroes/lib/tests/test_review_record.py`.

Declared guarded-element set: G1–G7, as dispatched. Redaction: none needed. Local temp paths and object addresses are left as printed.

## Summary

| ID | Guarded element | Axis | Neutralization | Node | Red |
|---|---|---|---|---|---|
| G1 | `_list_comments` reads by page number | a cloud CLI read of a PR with more than 100 comments; `--paginate` is refused by the proxy | the site back to `_run([..., "--paginate"])` + `pr_comment._parse_paginated_arrays` | `R::test_cloud_cli_read_pages_the_comments_by_number_and_finds_the_latest_record_on_page_three` | `review-record-gh-failed`, `assert (1 == 0)` |
| G2 | `_check_data` reads by page number | CI pagination under the cloud proxy; a failing check on page three | the site back to `_run([... "/check-runs?per_page=100", "--paginate"])` + `_parse_paginated_arrays` | `R::test_cloud_check_runs_are_read_page_by_number_and_a_failure_on_page_three_makes_ci_red` | `TypeError: cannot unpack non-iterable NoneType object` |
| G3 | `changed_paths` reads by page number | the PR file list under the cloud proxy, more than 100 files | the site back to `_run([..., "--paginate"])` + `_parse_paginated_arrays` | `R::test_cloud_changed_paths_are_read_page_by_number_in_order` | `assert None == ['src/f000.py', ...]` |
| G4 | `_read_pages` empty page after a full one | the end of a list: exactly 100 rows read in full, not failed | inserted `if not page:` / `return None` before `rows.extend(page)` | `R::test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read[100-pages0]` | `TypeError: 'NoneType' object is not iterable` |
| G5 | `_read_pages` failed page read | the complete-or-absent list: a failed page never reads as the end of the list | `page = None if out is None else json.loads(out)` → `page = [] if out is None else json.loads(out)` | `R::test_a_page_that_fails_makes_the_whole_read_unavailable_for_every_reader` | `assert [] is None` |
| G6 | `_read_pages` page cap | a list that never ends fails the read, never returns what was read so far | final `return None` → `return rows` | `R::test_a_list_that_never_ends_fails_the_read_after_the_page_cap` | `assert [{'filename': 'f'}, ...] is None` |
| G7 | `_read_pages` non-list page | page shape: a page that is not JSON, or not a list, fails the read | `if not isinstance(page, list):` body `return None` → `page = []` | `R::test_a_page_that_is_not_json_or_not_a_list_makes_the_read_unavailable` | `AssertionError: (1, 'not json')`, `assert [] is None` |

G1–G3 are the issue's cloud-shape proof: with a site reverted to `--paginate`, its cloud-shape test fails, and restored, it passes. G1's red is the refusal a cloud builder gets today (`review-record-gh-failed`).

G5 note: the node loops over a failed page 1, 2 and 3. The neutralized run went red on the first iteration (page 1). A failed middle page goes through the same line, so it is the same failure mode.

## G1 — `_list_comments` reads by page number

Neutralization: `plugins/superheroes/lib/review_record.py` line 251, `rows = _read_pages(_api(repo, f"issues/{pr}/comments"))` →

```
    out = _run(["gh", "api", _api(repo, f"issues/{pr}/comments"), "--paginate"])
    rows = None if out is None else pr_comment._parse_paginated_arrays(out)
```

Red:

```
>       assert proc.returncode == 0 and got["ok"], (proc.stdout, proc.stderr)
E       AssertionError: ('{"ok": false, "reason": "review-record-gh-failed", "detail": "the PR comments could not be listed"}
E         ', '')
E       assert (1 == 0)
1 failed in 1.08s
```

Restore: the inverse edit. Restore receipt: `git diff --stat -- plugins/superheroes/lib/review_record.py` printed nothing.

Green: `1 passed in 1.29s`

## G2 — `_check_data` reads by page number

Neutralization: line 226, `rows = _read_pages(base + "/check-runs", key="check_runs")` →

```
    out = _run(["gh", "api", base + "/check-runs?per_page=100", "--paginate"])
    try:
        rows = [r for page in pr_comment._parse_paginated_arrays(out) for r in page["check_runs"]]
    except (ValueError, KeyError, TypeError):
        rows = None
```

Red:

```
>       runs, st = rr._check_data(HEAD, "o/r")
E       TypeError: cannot unpack non-iterable NoneType object
1 failed in 1.11s
```

Restore: the inverse edit. Restore receipt: `git diff --stat` empty.

Green: `1 passed in 0.84s`

## G3 — `changed_paths` reads by page number

Neutralization: line 265, `files = _read_pages(_api(repo, f"pulls/{pr}/files"))` →

```
    out = _run(["gh", "api", _api(repo, f"pulls/{pr}/files"), "--paginate"])
    try:
        files = None if out is None else pr_comment._parse_paginated_arrays(out)
    except ValueError:
        return None
```

Red:

```
>       assert rr.changed_paths(7, "o/r") == [f["filename"] for f in files]
E       AssertionError: assert None == ['src/f000.py', 'src/f001.py', 'src/f002.py', 'src/f003.py', 'src/f004.py', 'src/f005.py', ...]
1 failed in 0.88s
```

Restore: the inverse edit. Restore receipt: `git diff --stat` empty.

Green: `1 passed in 0.72s`

## G4 — an empty page after a full one ends the read

Neutralization: inserted after the `return None` of `if not isinstance(page, list):`, before `rows.extend(page)`:

```
        if not page:
            return None
```

Red:

```
>       assert [c["id"] for c in got] == list(range(count))
E       TypeError: 'NoneType' object is not iterable
1 failed in 0.75s
```

Restore: the two lines removed. Restore receipt: `git diff --stat` empty.

Green: `1 passed in 0.68s`

## G5 — a failed page read fails the whole read

Neutralization: line 135, `page = None if out is None else json.loads(out)` → `page = [] if out is None else json.loads(out)`.

Red:

```
            monkeypatch.setattr(rr, "_run", cloud_proxy(routes, override={failed: None}))
>           assert rr._list_comments(7, "o/r") is None
E           AssertionError: assert [] is None
1 failed in 0.74s
```

Restore: the inverse edit. Restore receipt: `git diff --stat` empty.

Green: `1 passed in 0.75s`

## G6 — the page cap fails the read

Neutralization: line 148, the final `return None` after the loop → `return rows`.

Red:

```
>       assert rr._read_pages("repos/o/r/pulls/7/files") is None
E       AssertionError: assert [{'filename': 'f'}, {'filename': 'f'}, {'filename': 'f'}, {'filename': 'f'}, {'filename': 'f'}, {'filename': 'f'}, ...] is None
1 failed in 0.79s
```

Restore: the inverse edit. Restore receipt: `git diff --stat` empty.

Green: `1 passed in 0.69s`

## G7 — a page that is not a list fails the read

Neutralization: lines 141–142, `if not isinstance(page, list):` / `return None` → `if not isinstance(page, list):` / `page = []`.

Red:

```
>               assert rr._list_comments(7, "o/r") is None, (page, text)
E               AssertionError: (1, 'not json')
E               assert [] is None
1 failed in 0.76s
```

Restore: the inverse edit. Restore receipt: `git diff --stat` empty, and after the last restore `git diff --quiet` passed over the whole probe worktree (byte-clean).

Green: `1 passed in 1.03s`
