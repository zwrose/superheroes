# Bite-proof record: i2323_vet_slot_emptied (#2323, item 2) `vet_slot.py write` refuses an emptied PR body

Detector under proof: `plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py`.
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`check_not_emptied`, `_live_heading_offsets`, `evaluate`).
Base: `1e1138645e1b0383e05b611d74b5f0b465cbfdf6`. Every neutralization was a targeted edit made with the Edit
tool, undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash`
was used. Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py -q -p no:cacheprovider --tb=line -k <selector>`.
`--tb=line` shortens the failure bodies; nothing else was filtered. Nothing in the captures was redacted (the
only environment text is uv's deprecation warning line); each is far under 32 KiB. The production sites cite this
record with `# axis:` comments. Restore receipts are the inverse edit's text, quoted; the whole-file
`git status --porcelain` is reported in the dispatch return, not here.

Disclosures:
- The red captures below are **condensed by hand, not verbatim**: repeated failure lines are collapsed with a
  parenthesised count, diff lines under an `AssertionError` and the path prefix on `FAILED` lines are dropped. The
  parenthesised notes are the author's, not the runner's. Every line shown is the runner's text; the pass/fail counts
  and the `FAILED` node ids are exact. The green captures are verbatim minus uv's one warning line.
- The guarded-element set is the five the order declared. The `write`-path call in `_run_verb`
  (`if verb == "write": check_not_emptied(body)`, before `analyze_body`) is a sixth, undeclared call site and was
  **not** neutralized (the command budget was spent on the declared five): its protection is exercised by every
  `run_verb` test of the file (E1 to E4), which would turn `read-failed` or `markers-invalid` without it, but no
  neutralization of it was run, so it is **unproven by a red run**.
- Element 3's selector `e4_a_heading_only_inside` selects the seven `run_verb` cases of E4; the red is the three
  comment cases (`html-comment`, `html-comment-never-closed`, `comment-just-above-marker`); the fence and slot-span
  cases stay green under that neutralization, as they should.
- Element 4's neutralization is bitten by the `slot-span` and `below-the-build-record` cases (`run_verb` and
  `evaluate`); E3's tail-body cases carry no heading at all, so they pass under it by design.

## 1. The empty-body refusal (`check_not_emptied`, `vet_slot.py`)

- **Axis:** an empty or whitespace body (and the REST `null` body) refuses `body-emptied` and says `PR body is empty`,
  never `read-failed` and never the missing-heading wording.
- **Neutralization:** `if not body.strip():` became `if False and not body.strip():`.
- **Raw red** (`-k e1`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   assert 'PR body is empty' in 'PR body has no "What\'s changing, and why" heading; restore the builder\'s body from the PR\'s edit history before writing the slot'
/home/user/wt-2323-b/plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py:48: assert 'PR body is empty' in 'PR body has no "What\'s changing, and why" heading; restore the builder\'s body from the PR\'s edit history before writing the slot'
(the same two lines repeat for the next three run_verb cases, then at :72 for the two evaluate cases: 4 + 2 repeats elided)
=========================== short test summary info ============================
FAILED test_e1_empty_or_whitespace_body_refuses_body_emptied[]
FAILED test_e1_empty_or_whitespace_body_refuses_body_emptied[   \n\t\n]
FAILED test_e1_empty_or_whitespace_body_refuses_body_emptied[\n]
FAILED test_e1_null_rest_body_refuses_body_emptied
FAILED test_e1_evaluate_refuses_an_empty_body_body_emptied[]
FAILED test_e1_evaluate_refuses_an_empty_body_body_emptied[  \n]
6 failed, 42 deselected in 0.55s
```

(Condensed for the record: the repeated assertion lines and the common path prefix on the `FAILED` lines were
elided by hand; the run's own text is in the dispatch return.)

- **Restore:** inverse Edit, `if False and not body.strip():` back to `if not body.strip():`.
- **Restore receipt:** the restored line reads `    if not body.strip():`.
- **Raw green** (`-k e1`):

```
......                                                                   [100%]
6 passed, 42 deselected in 0.48s
```

## 2. The missing-heading refusal, run before the marker check (`check_not_emptied`)

- **Axis:** a body with no live owner-half heading above the marker refuses `body-emptied` ahead of any marker
  check (a marker-less tail is not `markers-invalid`).
- **Neutralization:** `if not held:` became `if False and not held:`.
- **Raw red** (`-k e2`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'markers-invalid' == 'body-emptied'
/home/user/wt-2323-b/plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py:47: AssertionError: assert 'markers-invalid' == 'body-emptied'
E   AssertionError: assert 'markers-invalid' == 'body-emptied'
/home/user/wt-2323-b/plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py:47: AssertionError: assert 'markers-invalid' == 'body-emptied'
=========================== short test summary info ============================
FAILED test_e2_marker_less_tail_body_refuses_body_emptied_not_markers_invalid
FAILED test_e2_the_check_runs_before_any_marker_check
2 failed, 46 deselected in 0.72s
```

(`- body-emptied` / `+ markers-invalid` diff lines and path prefixes elided by hand.)

- **Restore:** inverse Edit, `if False and not held:` back to `if not held:`.
- **Restore receipt:** the restored line reads `    if not held:`.
- **Raw green** (`-k e2`):

```
..                                                                       [100%]
2 passed, 46 deselected in 0.45s
```

## 3. HTML-comment liveness (`_live_heading_offsets`)

- **Axis:** a heading that starts inside an HTML comment span (closed across lines, or never closed) does not count.
- **Neutralization:** `if heading and not dead and not starts_in_comment:` became `if heading and not dead:`.
- **Raw red** (`-k e4_a_heading_only_inside`):

```
FF...F.                                                                  [100%]
=================================== FAILURES ===================================
E   assert (True is False)
/home/user/wt-2323-b/plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py:131: assert (True is False)
(the same two lines, 3 times in all)
=========================== short test summary info ============================
FAILED test_e4_a_heading_only_inside_a_comment_fence_or_slot_span_refuses[html-comment]
FAILED test_e4_a_heading_only_inside_a_comment_fence_or_slot_span_refuses[html-comment-never-closed]
FAILED test_e4_a_heading_only_inside_a_comment_fence_or_slot_span_refuses[comment-just-above-marker]
3 failed, 4 passed, 41 deselected in 0.52s
```

- **Restore:** inverse Edit, `if heading and not dead:` back to `if heading and not dead and not starts_in_comment:`.
- **Restore receipt:** the restored line reads `        if heading and not dead and not starts_in_comment:`.
- **Raw green** (`-k e4_a_heading_only_inside`):

```
.......                                                                  [100%]
7 passed, 41 deselected in 0.49s
```

## 4. The above-the-marker rule (`check_not_emptied`)

- **Axis:** a heading at or after the advisor-vet marker (inside the slot span, or below the build record) does not
  count; only one that starts before the marker's offset does.
- **Neutralization:** `limit = min(markers) if markers else len(body) + 1` became `limit = len(body) + 1`.
- **Raw red** (`-k "e3 or e4"`):

```
......F.F....F.F......                                                   [100%]
=================================== FAILURES ===================================
E   assert (True is False)
/home/user/wt-2323-b/plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py:131: assert (True is False)  (x2)
/home/user/wt-2323-b/plugins/superheroes/lib/tests/test_vet_slot_emptied_2323.py:140: assert (True is False)  (x2)
=========================== short test summary info ============================
FAILED test_e4_a_heading_only_inside_a_comment_fence_or_slot_span_refuses[slot-span]
FAILED test_e4_a_heading_only_inside_a_comment_fence_or_slot_span_refuses[below-the-build-record]
FAILED test_e4_evaluate_agrees[slot-span]
FAILED test_e4_evaluate_agrees[below-the-build-record]
4 failed, 18 passed, 26 deselected in 0.58s
```

- **Restore:** inverse Edit, `limit = len(body) + 1` back to `limit = min(markers) if markers else len(body) + 1`.
- **Restore receipt:** the restored line reads `    limit = min(markers) if markers else len(body) + 1`.
- **Raw green** (`-k "e3 or e4"`):

```
......................                                                   [100%]
22 passed, 26 deselected in 0.54s
```

## 5. The `evaluate` chokepoint call (`evaluate`)

- **Axis:** `evaluate("write", ...)` refuses `body-emptied` itself, before `analyze_body`, for a caller that does not
  go through `_run_verb`.
- **Neutralization:** `if verb == "write":` (the one above `check_not_emptied(body)` inside `evaluate`'s `try`)
  became `if False and verb == "write":`.
- **Raw red** (`-k evaluate`):

```
FFFFFFFFFF                                                               [100%]
=================================== FAILURES ===================================
E   AssertionError: assert (False is False and 'read-failed' == 'body-emptied'   (x2, test_vet_slot_emptied_2323.py:71)
E   assert (True is False)   (test_vet_slot_emptied_2323.py:102 and :140, x7)
E   AssertionError: assert (False is False and 'markers-invalid' == 'body-emptied'   (:140)
=========================== short test summary info ============================
FAILED test_e1_evaluate_refuses_an_empty_body_body_emptied[]
FAILED test_e1_evaluate_refuses_an_empty_body_body_emptied[  \n]
FAILED test_e3_evaluate_refuses_the_restamped_tail_body
FAILED test_e4_evaluate_agrees[html-comment]
FAILED test_e4_evaluate_agrees[html-comment-never-closed]
FAILED test_e4_evaluate_agrees[fenced-block]
FAILED test_e4_evaluate_agrees[fence-never-closed]
FAILED test_e4_evaluate_agrees[slot-span]
FAILED test_e4_evaluate_agrees[comment-just-above-marker]
FAILED test_e4_evaluate_agrees[below-the-build-record]
10 failed, 38 deselected in 0.54s
```

- **Restore:** inverse Edit, `if False and verb == "write":` back to `if verb == "write":`.
- **Restore receipt:** the restored lines read `        if verb == "write":` then `            check_not_emptied(body)`.
- **Raw green** (`-k evaluate`):

```
..........                                                               [100%]
10 passed, 38 deselected in 0.50s
```
