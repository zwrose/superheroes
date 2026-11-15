# Bite-proof record — the four by-release review-loop measures (#2498)

Detector file: `plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to `plugins/superheroes/lib/review_measures.py` at a committed head (`4aab8b51` unless the entry names another; the lines the `4aab8b51` entries neutralize are unchanged since), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py -q -k "<one test's name fragment>" -p no:randomly`, which selects exactly one test; each capture is whole except the `UV_NATIVE_TLS` deprecation line `uv` prints first. The worktree path is shown as `<worktree>`; no secret, token, URL or personal data appears in any capture, so nothing else is redacted. After every restore, `git status --porcelain` over the file printed nothing. Light lane, orchestrator-typed: the guarded-element set below (e1 to e12, fifteen entries) is the one the round-1 reviewer's dispatch declares; e7c, e12b, e13 and e14 guard the round-1 fixes and are declared to the round-2 reviewer; e6d and e7d (with e7a to e7c re-run on the reworked void rule) guard the round-2 fixes and are declared to the round-3 reviewer; e15 (with e2 re-run) guards the round-3 fix and is declared to the round-4 reviewer; e16 guards the round-4 fix, which landed after the round cap and was declared to no reviewer; twenty-three entries in all; none is grouped.

## e1. No whole release list (`_release_measures`, the `if why:` return)

- **Axis:** with `releases` missing or malformed, all four by-release measures read unmeasured with the reason, never zero.
- **Detector:** `test_missing_or_malformed_releases_leave_all_four_unmeasured`.
- **Neutralization:** `if why:` became `if False and why:`.

The red is a crash (`TypeError` iterating a missing release list), not an assertion: without the guard nothing reads unmeasured.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_missing_or_malformed_releases_leave_all_four_unmeasured _________

    def test_missing_or_malformed_releases_leave_all_four_unmeasured():
        for releases, reason in ((None, "no-releases-input"), ([{"version": "0.50", "since": "2026-10-01"}], "incomplete-evidence"),
                                 ([{"version": "0.50.0", "since": "soon"}], "incomplete-evidence")):
>           m, why = _m([_rec(1)], releases=releases)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:107: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:44: in _m
    row = RM.compute(inp, FROM, UNTIL)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_measures.py:412: in compute
    m.update(_release_measures(inp, prs, every, sessions, reason, miss))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_measures.py:271: in _release_measures
    pr_release = release_of(first(rs))
                 ^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

recs = [{'pr': 1, 'sessionId': 's1', 'writtenAt': '2026-11-01T10:00:00Z', 'status': 'reviewed', ...}]

    def release_of(recs):  # the release adopted last at or before the session's first record, else None
        t = _when(min(r["writtenAt"] for r in recs))
        # axis: a session runs on the release adopted last at or before its first record, to the second — see bite-proof record i2498_by_release
>       got = [x for x in rel if t is not None and x[0] <= t]
                          ^^^
E       TypeError: 'NoneType' object is not iterable

<worktree>/plugins/superheroes/lib/review_measures.py:250: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_missing_or_malformed_releases_leave_all_four_unmeasured
1 failed, 11 deselected in 0.31s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `    if why:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.22s
```

## e2. Release placement (`release_of`, the `x[0] <= t` comparison)

- **Axis:** a session runs on the release adopted last at or before its first record, to the second.
- **Detector:** `test_a_session_runs_on_the_release_adopted_last_before_it_even_the_same_day`.
- **Neutralization:** `x[0] <= t` became `x[0].date() <= t.date()` (placement by day).

Run at `db877135`, re-run after the round-3 and round-4 fixes changed `release_of`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_session_runs_on_the_release_adopted_last_before_it_even_the_same_day __

    def test_a_session_runs_on_the_release_adopted_last_before_it_even_the_same_day():
        m, _ = _m([_rec(1, at="2026-11-05T11:59:00Z"), _rec(2, at="2026-11-05T12:00:00Z")])
        by = m["sessionsPerPrByRelease"]["byRelease"]
>       assert by == {"0.49.0": {"median": 1, "p90": 1}, "0.50.0": {"median": 1, "p90": 1}}
E       AssertionError: assert {'0.50.0': {'....0, 'p90': 1}} == {'0.49.0': {'... 1, 'p90': 1}}
E         
E         Omitting 1 identical items, use -vv to show
E         Right contains 1 more item:
E         {'0.49.0': {'median': 1, 'p90': 1}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:52: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_session_runs_on_the_release_adopted_last_before_it_even_the_same_day
1 failed, 17 deselected in 0.24s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        got = [x for x in rel if x[0] <= t]`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 17 deselected in 0.20s
```

## e3. Unplaced items (`release_of`, its `else None`)

- **Axis:** an item earlier than every release counts in `unplaced`, never under a release.
- **Detector:** `test_a_session_before_every_release_is_unplaced_never_counted_under_one`.
- **Neutralization:** `return got[-1] if got else None` became `return got[-1] if got else rel[0]`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_session_before_every_release_is_unplaced_never_counted_under_one ____

    def test_a_session_before_every_release_is_unplaced_never_counted_under_one():
        m, _ = _m([_rec(1, at="2026-10-29T10:00:00Z")], releases=[{"version": "0.50.0", "since": "2026-11-05"}])
>       assert all(m[k] == {"byRelease": {}, "unplaced": 1} for k in RM.BY_RELEASE)
E       assert False
E        +  where False = all(<generator object test_a_session_before_every_release_is_unplaced_never_counted_under_one.<locals>.<genexpr> at 0x7f4cb7e1ea40>)

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:113: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_session_before_every_release_is_unplaced_never_counted_under_one
1 failed, 11 deselected in 0.27s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        return got[-1] if got else None`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.26s
```

## e4. PR placement (`pr_release = release_of(first(rs))`)

- **Axis:** a PR counts under the release its first in-window session ran on.
- **Detector:** `test_a_pr_counts_under_the_release_its_first_in_window_session_ran_on`.
- **Neutralization:** `release_of(first(rs))` became `release_of([_latest(rs)])`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_pr_counts_under_the_release_its_first_in_window_session_ran_on _____

    def test_a_pr_counts_under_the_release_its_first_in_window_session_ran_on():
        m, _ = _m([_rec(1, "s1", at="2026-11-01T10:00:00Z"), _rec(1, "s2", at="2026-11-07T10:00:00Z"),
                   _rec(1, "s3", at="2026-11-08T10:00:00Z")])
>       assert m["sessionsPerPrByRelease"] == {"byRelease": {"0.49.0": {"median": 3, "p90": 3}}, "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.50.0': {'median': 3, 'p90': 3}}} != {'byRelease': {'0.49.0': {'median': 3, 'p90': 3}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_pr_counts_under_the_release_its_first_in_window_session_ran_on
1 failed, 11 deselected in 0.21s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        pr_release = release_of(first(rs))`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.23s
```

## e5. First session read (`opening = first(every[pr])`)

- **Axis:** certification reads the PR's first session among all its records, in the window or not.
- **Detector:** `test_first_session_certification_reads_the_prs_first_session_even_before_the_window`.
- **Neutralization:** `first(every[pr])` became `first(rs)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_first_session_certification_reads_the_prs_first_session_even_before_the_window _

    def test_first_session_certification_reads_the_prs_first_session_even_before_the_window():
        early = _rec(1, "s0", at="2026-10-21T10:00:00Z", status="not-reviewed")
        m, _ = _m([early, _rec(1, "s1", at="2026-11-01T10:00:00Z"), _rec(2, "s2", at="2026-11-06T10:00:00Z")])
>       assert m["firstSessionCertification"]["byRelease"] == {
            "0.49.0": {"certified": 0, "prs": 1, "share": 0.0}, "0.50.0": {"certified": 1, "prs": 1, "share": 1.0}}
E       AssertionError: assert {'0.49.0': {'...'share': 1.0}} == {'0.49.0': {'...'share': 1.0}}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'0.49.0': {'certified': 1, 'prs': 1, 'share': 1.0}} != {'0.49.0': {'certified': 0, 'prs': 1, 'share': 0.0}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:79: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_first_session_certification_reads_the_prs_first_session_even_before_the_window
1 failed, 11 deselected in 0.31s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        opening = first(every[pr])`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.22s
```

## e6a. Owner cards leave merged members out (`cards`, `not review_learning._merged_member(f)`)

- **Axis:** a merged member row is not a card of its own.
- **Detector:** `test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only`.
- **Neutralization:** `and not review_learning._merged_member(f)}` became `and not False}`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only _

    def test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only():
        merged_member = _card("k3", reason="same defect (merged into k1)")
        m, _ = _m([_rec(1, "s1", findings=[_card("k1"), _card("k2", outcome="fixed")]),
                   _rec(1, "s2", at="2026-11-02T10:00:00Z", findings=[_card("k1"), _card("k4"), merged_member]),
                   _rec(5, findings=[_card("k9")])], mergedPrs=[1])
>       assert m["ownerCardsPerMergedPr"] == {"byRelease": {"0.49.0": {"median": 2, "p90": 2, "total": 2}}, "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.49.0': {'median': 3, 'p90': 3, 'total': 3}}} != {'byRelease': {'0.49.0': {'median': 2, 'p90': 2, 'total': 2}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:66: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only
1 failed, 11 deselected in 0.21s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `                     and not review_learning._merged_member(f)}`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.21s
```

## e6b. Owner cards are distinct keys (`len(cards)`)

- **Axis:** a key left for the owner in two sessions counts once.
- **Detector:** `test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only`.
- **Neutralization:** `len(cards)` became a sum over every left-for-owner row of every session (merged members still out).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only _

    def test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only():
        merged_member = _card("k3", reason="same defect (merged into k1)")
        m, _ = _m([_rec(1, "s1", findings=[_card("k1"), _card("k2", outcome="fixed")]),
                   _rec(1, "s2", at="2026-11-02T10:00:00Z", findings=[_card("k1"), _card("k4"), merged_member]),
                   _rec(5, findings=[_card("k9")])], mergedPrs=[1])
>       assert m["ownerCardsPerMergedPr"] == {"byRelease": {"0.49.0": {"median": 2, "p90": 2, "total": 2}}, "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.49.0': {'median': 3, 'p90': 3, 'total': 3}}} != {'byRelease': {'0.49.0': {'median': 2, 'p90': 2, 'total': 2}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:66: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only
1 failed, 11 deselected in 0.22s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            put("ownerCardsPerMergedPr", pr_release, len(cards))`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.27s
```

## e6c. Owner cards count merged PRs only (`if pr in merged_set:`)

- **Axis:** a PR that did not merge contributes no cards.
- **Detector:** `test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only`.
- **Neutralization:** `if pr in merged_set:` became `if True or pr in merged_set:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only _

    def test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only():
        merged_member = _card("k3", reason="same defect (merged into k1)")
        m, _ = _m([_rec(1, "s1", findings=[_card("k1"), _card("k2", outcome="fixed")]),
                   _rec(1, "s2", at="2026-11-02T10:00:00Z", findings=[_card("k1"), _card("k4"), merged_member]),
                   _rec(5, findings=[_card("k9")])], mergedPrs=[1])
>       assert m["ownerCardsPerMergedPr"] == {"byRelease": {"0.49.0": {"median": 2, "p90": 2, "total": 2}}, "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.49.0': {'median': 1.5, 'p90': 2, 'total': 3}}} != {'byRelease': {'0.49.0': {'median': 2, 'p90': 2, 'total': 2}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:66: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_owner_cards_count_distinct_keys_left_for_the_owner_across_sessions_on_merged_prs_only
1 failed, 11 deselected in 0.22s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        if pr in merged_set:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.28s
```

## e6d. Owner cards leave out a held repeat (`review_record.repeat_held_elsewhere`, round-2 finding code-002)

- **Axis:** a repeat whose card another finding of the record holds is no card of its own.
- **Detector:** `test_a_repeat_whose_card_another_finding_holds_is_no_owner_card_of_its_own`.
- **Neutralization:** `and not review_record.repeat_held_elsewhere(f, r["findings"])}` became `and not False}`.

Run at `007f8fd2`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_repeat_whose_card_another_finding_holds_is_no_owner_card_of_its_own __

    def test_a_repeat_whose_card_another_finding_holds_is_no_owner_card_of_its_own():
        original = _card("k1")
        repeat = dict(_card("k2"), repeatOf={"findingKey": "k1", "id": "k1", "fixHolds": None})
        m, _ = _m([_rec(1, findings=[original, repeat])], mergedPrs=[1])
>       assert m["ownerCardsPerMergedPr"]["byRelease"] == {"0.49.0": {"median": 1, "p90": 1, "total": 1}}
E       AssertionError: assert {'0.49.0': {'..., 'total': 2}} == {'0.49.0': {'..., 'total': 1}}
E         
E         Differing items:
E         {'0.49.0': {'median': 2, 'p90': 2, 'total': 2}} != {'0.49.0': {'median': 1, 'p90': 1, 'total': 1}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:113: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_repeat_whose_card_another_finding_holds_is_no_owner_card_of_its_own
1 failed, 15 deselected in 0.29s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `... and not review_learning._merged_member(f) and not review_record.repeat_held_elsewhere(f, r["findings"])}`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 15 deselected in 4.57s
```

## e7a. A void names a reviewer row that did not run (`any(s in not_run for s in silent)`, round-2 finding code-001)

- **Axis:** voided only when a silence end names a row that did not run; an end naming no row is unresolved.
- **Detector:** `test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one`.
- **Neutralization:** `elif any(s in not_run for s in silent):` became `elif True:`.

Run at `007f8fd2`. The void rule was reworked after each review round (round 1: a row that did not run is needed; round 2: the end must name that row, else unresolved); every void entry below was run on this final code.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one _

    def test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one():
        """A forfeited or recovered seat's run dir binds no row, so its end carries the role-and-dir label and cannot be
        tied to the row that did not run: beside such a row it is unresolved, never a void. A seat a later round recovered
        leaves no row that did not run (review_record_session drops the missing row), so alone its end is clear."""
        at, label = "2026-11-06T10:00:00Z", "reviewer (run-r1-sec)"
        recovered = _row("security-reviewer (round 2)")
        m, _ = _m([_rec(1, "s1", at=at, status="not-reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(label)]),
                   _rec(2, "s2", at=at, status="not-reviewed", rows=[recovered, _row(CODE)], ends=[_end(label)]),
                   # the recovered seat's end beside an unrelated seat that did not run (round-2 finding code-001)
                   _rec(3, "s3", at=at, status="not-reviewed", rows=[recovered, _row(CODE, "not-run")], ends=[_end(label)])])
>       assert m["silentReviewerVoids"] == {"byRelease": {"0.50.0": {"voided": 0, "unresolved": 2, "sessions": 3}},
                                            "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.50.0': {'voided': 2, 'unresolved': 0, 'sessions': 3}}} != {'byRelease': {'0.50.0': {'voided': 0, 'unresolved': 2, 'sessions': 3}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:105: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one
1 failed, 15 deselected in 0.28s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            elif any(s in not_run for s in silent):`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 15 deselected in 0.23s
```

## e7b. A certified session is clear (`review_record.cleared(...)` in the clear branch)

- **Axis:** a `reviewed` session is never voided, whatever its silence ends.
- **Detector:** `test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered`.
- **Neutralization:** `elif review_record.cleared(last.get("status")) or not not_run or not silent:` became `elif not not_run or not silent:`.

Run at `007f8fd2`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered _

    def test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered():
        at = "2026-11-06T10:00:00Z"
        m, _ = _m([_rec(1, "s1", at=at, status="not-reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(SEC)]),
                   _rec(2, "s2", at=at, status="reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(SEC)]),
                   _rec(3, "s3", at=at, status="not-reviewed", rows=[_row(SEC), _row(CODE)], ends=[_end(SEC)]),
                   _rec(4, "s4", at=at, status="not-reviewed", rows=[_row(SEC, "not-run")]),
                   # the silent seat answered after its end; another seat did not run, silently or not, so this is no void
                   _rec(5, "s5", at=at, status="not-reviewed", rows=[_row(SEC), _row(CODE, "not-run")], ends=[_end(SEC)])])
>       assert m["silentReviewerVoids"] == {"byRelease": {"0.50.0": {"voided": 1, "unresolved": 0, "sessions": 5}},
                                            "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.50.0': {'voided': 2, 'unresolved': 0, 'sessions': 5}}} != {'byRelease': {'0.50.0': {'voided': 1, 'unresolved': 0, 'sessions': 5}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:91: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered
1 failed, 15 deselected in 0.30s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            elif review_record.cleared(last.get("status")) or not not_run or not silent:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 15 deselected in 0.29s
```

## e7c. No reviewer row that did not run is clear (`not not_run`, round-1 finding code-002)

- **Axis:** a seat a later round recovered (its row gone, its run dir unbound, its end named by role and dir) voids nothing.
- **Detector:** `test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one`.
- **Neutralization:** `... or not not_run or not silent:` became `... or not silent:`.

Run at `007f8fd2`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one _

    def test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one():
        """A forfeited or recovered seat's run dir binds no row, so its end carries the role-and-dir label and cannot be
        tied to the row that did not run: beside such a row it is unresolved, never a void. A seat a later round recovered
        leaves no row that did not run (review_record_session drops the missing row), so alone its end is clear."""
        at, label = "2026-11-06T10:00:00Z", "reviewer (run-r1-sec)"
        recovered = _row("security-reviewer (round 2)")
        m, _ = _m([_rec(1, "s1", at=at, status="not-reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(label)]),
                   _rec(2, "s2", at=at, status="not-reviewed", rows=[recovered, _row(CODE)], ends=[_end(label)]),
                   # the recovered seat's end beside an unrelated seat that did not run (round-2 finding code-001)
                   _rec(3, "s3", at=at, status="not-reviewed", rows=[recovered, _row(CODE, "not-run")], ends=[_end(label)])])
>       assert m["silentReviewerVoids"] == {"byRelease": {"0.50.0": {"voided": 0, "unresolved": 2, "sessions": 3}},
                                            "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.50.0': {'voided': 0, 'unresolved': 3, 'sessions': 3}}} != {'byRelease': {'0.50.0': {'voided': 0, 'unresolved': 2, 'sessions': 3}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:105: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_an_end_that_names_no_row_is_unresolved_beside_a_row_that_did_not_run_and_clear_without_one
1 failed, 15 deselected in 0.32s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            elif review_record.cleared(last.get("status")) or not not_run or not silent:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 15 deselected in 0.21s
```

## e7d. Every silent seat answered is clear (`not silent`)

- **Axis:** a silence end on a seat that later answered does not void the session, even beside a seat that did not run.
- **Detector:** `test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered`.
- **Neutralization:** `... or not not_run or not silent:` became `... or not not_run:`.

Run at `007f8fd2`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered _

    def test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered():
        at = "2026-11-06T10:00:00Z"
        m, _ = _m([_rec(1, "s1", at=at, status="not-reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(SEC)]),
                   _rec(2, "s2", at=at, status="reviewed", rows=[_row(SEC, "not-run"), _row(CODE)], ends=[_end(SEC)]),
                   _rec(3, "s3", at=at, status="not-reviewed", rows=[_row(SEC), _row(CODE)], ends=[_end(SEC)]),
                   _rec(4, "s4", at=at, status="not-reviewed", rows=[_row(SEC, "not-run")]),
                   # the silent seat answered after its end; another seat did not run, silently or not, so this is no void
                   _rec(5, "s5", at=at, status="not-reviewed", rows=[_row(SEC), _row(CODE, "not-run")], ends=[_end(SEC)])])
>       assert m["silentReviewerVoids"] == {"byRelease": {"0.50.0": {"voided": 1, "unresolved": 0, "sessions": 5}},
                                            "unplaced": 0}
E       AssertionError: assert {'byRelease':...'unplaced': 0} == {'byRelease':...'unplaced': 0}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'byRelease': {'0.50.0': {'voided': 1, 'unresolved': 2, 'sessions': 5}}} != {'byRelease': {'0.50.0': {'voided': 1, 'unresolved': 0, 'sessions': 5}}}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:91: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_session_is_voided_by_a_silent_reviewer_only_when_it_did_not_certify_and_the_silent_seat_never_answered
1 failed, 15 deselected in 0.24s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            elif review_record.cleared(last.get("status")) or not not_run or not silent:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 15 deselected in 0.24s
```

## e8. Releases before watchdog ends were recorded (`versions[ver] < WATCHDOG_ENDS_SINCE`)

- **Axis:** a release before 0.48.0 reads unmeasured for silent voids, never zero.
- **Detector:** `test_a_release_before_watchdog_ends_were_recorded_reads_unmeasured`.
- **Neutralization:** `if versions[ver] < WATCHDOG_ENDS_SINCE:` became `if False and versions[ver] < WATCHDOG_ENDS_SINCE:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_release_before_watchdog_ends_were_recorded_reads_unmeasured ______

    def test_a_release_before_watchdog_ends_were_recorded_reads_unmeasured():
        m, why = _m([_rec(1, at="2026-11-01T10:00:00Z")], releases=[{"version": "0.47.0", "since": "2026-10-01"}])
>       assert m["silentReviewerVoids"]["byRelease"] == {"0.47.0": U}
E       AssertionError: assert {'0.47.0': {'...sessions': 1}} == {'0.47.0': 'unmeasured'}
E         
E         Differing items:
E         {'0.47.0': {'voided': 0, 'sessions': 1}} != {'0.47.0': 'unmeasured'}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:94: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_release_before_watchdog_ends_were_recorded_reads_unmeasured
1 failed, 11 deselected in 0.25s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        if versions[ver] < WATCHDOG_ENDS_SINCE:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.24s
```

## e9. Owner cards without a whole merged list (`if not merged_ok:`)

- **Axis:** owner cards read unmeasured, never zero, with no `mergedPrs` or a damaged one.
- **Detector:** `test_owner_cards_without_the_merged_list_read_unmeasured_never_zero`.
- **Neutralization:** `if not merged_ok:` became `if False and not merged_ok:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_owner_cards_without_the_merged_list_read_unmeasured_never_zero ______

    def test_owner_cards_without_the_merged_list_read_unmeasured_never_zero():
        m, why = _m([_rec(1)], mergedPrs=None)
>       assert m["ownerCardsPerMergedPr"] == U and why["ownerCardsPerMergedPr"] == "no-merged-input"
E       AssertionError: assert ({'byRelease': {}, 'unplaced': 0} == 'unmeasured')

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:71: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_owner_cards_without_the_merged_list_read_unmeasured_never_zero
1 failed, 11 deselected in 0.22s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `    if not merged_ok:`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.28s
```

## e10. Schema-keyed shape (`problems`, `_SCHEMA_MEASURES[row["schema"]]`)

- **Axis:** a row keeps the measures of the schema it was written under, so a /1 row still renders.
- **Detector:** `test_a_row_written_before_the_by_release_measures_still_has_the_fixed_shape`.
- **Neutralization:** `_SCHEMA_MEASURES[row["schema"]]` became `MEASURES`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_row_written_before_the_by_release_measures_still_has_the_fixed_shape __

    def test_a_row_written_before_the_by_release_measures_still_has_the_fixed_shape():
        row = RM.compute({}, FROM, UNTIL)
        old = dict(row, schema="review-loop-measures/1", measures={k: row["measures"][k] for k in RM.MEASURES_V1})
>       assert RM.problems(old) == []
E       assert ["the measure...iewerVoids')"] == []
E         
E         Left contains one more item: "the measures are not ('roundsPerPr', 'sessionsPerPr', 'reviewerCostPerPr', 'seats', 'ci', 'panels', 'vetSendBacksOnCl...dingLocations', 'ownerCardsPerMergedPr', 'sessionsPerPrByRelease', 'firstSessionCertification', 'silentReviewerVoids')"
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:119: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_row_written_before_the_by_release_measures_still_has_the_fixed_shape
1 failed, 11 deselected in 0.17s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `    m, w, measures = row["measures"], row.get("window"), _SCHEMA_MEASURES[row["schema"]]`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.21s
```

## e11. By-release shape check (`problems`)

- **Axis:** a by-release measure holds a value or unmeasured per release, and a count of unplaced.
- **Detector:** `test_a_by_release_measure_off_its_shape_is_named`.
- **Neutralization:** `if isinstance(m.get(k), dict) and set(m[k]) == ...` became `if False and isinstance(m.get(k), dict) and ...`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_a_by_release_measure_off_its_shape_is_named _______________

    def test_a_by_release_measure_off_its_shape_is_named():
        m_row = RM.compute({"records": [_rec(1)], "releases": RELEASES, "mergedPrs": [1]}, FROM, UNTIL)
        m_row["measures"]["sessionsPerPrByRelease"]["byRelease"]["0.49.0"] = 3
>       assert RM.problems(m_row)
E       AssertionError: assert []
E        +  where [] = <function problems at 0x7f847e4edf80>({'schema': 'review-loop-measures/2', 'window': {'from': '2026-10-28', 'until': '2026-11-11'}, 'writtenAt': '2026-11-15T14:37:39Z', 'prs': 1, ...})
E        +    where <function problems at 0x7f847e4edf80> = RM.problems

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:127: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_by_release_measure_off_its_shape_is_named
1 failed, 11 deselected in 0.21s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            if isinstance(m.get(k), dict) and set(m[k]) == {"byRelease", "unplaced"}`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 11 deselected in 0.22s
```

## e12. Malformed watchdog ends (`whole`, the per-end check)

- **Axis:** a silence end that is not a dict naming a seat makes that release's void count unmeasured.
- **Detector:** `test_malformed_watchdog_ends_read_unmeasured_for_that_release`.
- **Neutralization:** the two-line `whole = (... and all(isinstance(e, dict) and ...))` became `whole = (isinstance(ends, list) and last.get("status") in review_record.STATUSES)`.

Run at `b53ef313`, re-run after the round-1 fix.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_malformed_watchdog_ends_read_unmeasured_for_that_release _________

    def test_malformed_watchdog_ends_read_unmeasured_for_that_release():
        m, why = _m([_rec(1, at="2026-11-06T10:00:00Z", ends=[{"attempt": 1}])])
>       assert m["silentReviewerVoids"]["byRelease"] == {"0.50.0": U}
E       AssertionError: assert {'0.50.0': {'...sessions': 1}} == {'0.50.0': 'unmeasured'}
E         
E         Differing items:
E         {'0.50.0': {'voided': 0, 'sessions': 1}} != {'0.50.0': 'unmeasured'}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:127: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_malformed_watchdog_ends_read_unmeasured_for_that_release
1 failed, 14 deselected in 0.25s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `                     and all(isinstance(e, dict) and isinstance(e.get("seat"), str) and e["seat"].strip() for e in ends))`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 14 deselected in 0.24s
```

## e12b. Blank watchdog seat (`e["seat"].strip()`, review finding code-001)

- **Axis:** a silence end whose seat is blank makes that release's void count unmeasured, never a void.
- **Detector:** `test_a_blank_watchdog_seat_reads_unmeasured_never_a_void`.
- **Neutralization:** `isinstance(e.get("seat"), str) and e["seat"].strip() for e in ends))` became `isinstance(e.get("seat"), str) for e in ends))`.

Run at `b53ef313`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_a_blank_watchdog_seat_reads_unmeasured_never_a_void ___________

    def test_a_blank_watchdog_seat_reads_unmeasured_never_a_void():
        m, why = _m([_rec(1, at="2026-11-06T10:00:00Z", status="not-reviewed", rows=[_row(SEC, "not-run")],
                          ends=[_end(" ")])])
>       assert m["silentReviewerVoids"]["byRelease"] == {"0.50.0": U}
E       AssertionError: assert {'0.50.0': {'...sessions': 1}} == {'0.50.0': 'unmeasured'}
E         
E         Differing items:
E         {'0.50.0': {'voided': 1, 'sessions': 1}} != {'0.50.0': 'unmeasured'}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_blank_watchdog_seat_reads_unmeasured_never_a_void
1 failed, 14 deselected in 0.23s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `                     and all(isinstance(e, dict) and isinstance(e.get("seat"), str) and e["seat"].strip() for e in ends))`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 14 deselected in 0.22s
```

## e13. Certification on an unrecorded status (review finding code-001)

- **Axis:** a first session whose status is not one the writer records reads unmeasured, never uncertified.
- **Detector:** `test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided`.
- **Neutralization:** `review_record.cleared(status) if status in review_record.STATUSES else None)` became `review_record.cleared(status))`.

Run at `b53ef313`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided ____

    def test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided():
        at = "2026-11-06T10:00:00Z"
        for status in (None, "pending"):
            m, why = _m([_rec(1, at=at, status=status, rows=[_row(SEC, "not-run")], ends=[_end(SEC)])])
>           assert m["firstSessionCertification"]["byRelease"] == {"0.50.0": U}
E           AssertionError: assert {'0.50.0': {'...'share': 0.0}} == {'0.50.0': 'unmeasured'}
E             
E             Differing items:
E             {'0.50.0': {'certified': 0, 'prs': 1, 'share': 0.0}} != {'0.50.0': 'unmeasured'}
E             Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided
1 failed, 14 deselected in 0.28s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            review_record.cleared(status) if status in review_record.STATUSES else None)`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 14 deselected in 0.22s
```

## e14. Void on an unrecorded status (review finding code-001)

- **Axis:** a session whose status is not one the writer records reads unmeasured for voids, never a void.
- **Detector:** `test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided`.
- **Neutralization:** `whole = (isinstance(ends, list) and last.get("status") in review_record.STATUSES` became `whole = (isinstance(ends, list)`.

Run at `b53ef313`; e13 was restored first, so the red is on the void assertion.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided ____

    def test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided():
        at = "2026-11-06T10:00:00Z"
        for status in (None, "pending"):
            m, why = _m([_rec(1, at=at, status=status, rows=[_row(SEC, "not-run")], ends=[_end(SEC)])])
            assert m["firstSessionCertification"]["byRelease"] == {"0.50.0": U}
>           assert m["silentReviewerVoids"]["byRelease"] == {"0.50.0": U}
E           AssertionError: assert {'0.50.0': {'...sessions': 1}} == {'0.50.0': 'unmeasured'}
E             
E             Differing items:
E             {'0.50.0': {'voided': 1, 'sessions': 1}} != {'0.50.0': 'unmeasured'}
E             Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:107: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_an_unrecorded_status_reads_unmeasured_never_uncertified_or_voided
1 failed, 14 deselected in 0.23s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `            whole = (isinstance(ends, list) and last.get("status") in review_record.STATUSES`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 14 deselected in 0.18s
```

## e15. A record time that does not parse (the PR loop's time check, round-3 finding code-001)

- **Axis:** a record whose time does not parse makes the by-release measures unmeasured, never unplaced.
- **Detector:** `test_a_record_time_that_does_not_parse_reads_unmeasured_never_unplaced`.
- **Neutralization:** `if any(_when(r["writtenAt"]) is None for r in every[pr]):` became `if False:`.

Run at `db877135`. The round-3 fix put this check inside `release_of`; the round-4 fix moved it to the top of the PR loop (e16) and removed the inner one, which no record could reach any more, so this entry proves the round-3 test against the guard that now carries it. The red is a crash (`TypeError` comparing a release time with no time), not an assertion: without the guard the broken time is never read as missing evidence.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_record_time_that_does_not_parse_reads_unmeasured_never_unplaced ____

    def test_a_record_time_that_does_not_parse_reads_unmeasured_never_unplaced():
        """`_rec_ok` checks only the date prefix, so a broken time reaches placement (round-3 finding code-001)."""
        silent = dict(status="not-reviewed", rows=[_row(SEC, "not-run")], ends=[_end(SEC)])
>       m, why = _m([_rec(1, at="2026-11-06T10:00:00Z"), _rec(2, "s2", at="2026-11-06Tbroken", **silent)])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:160: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:44: in _m
    row = RM.compute(inp, FROM, UNTIL)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_measures.py:442: in compute
    m.update(_release_measures(inp, prs, every, sessions, reason, miss))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_measures.py:281: in _release_measures
    pr_release = release_of(first(rs))
                 ^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

recs = [{'pr': 2, 'sessionId': 's2', 'writtenAt': '2026-11-06Tbroken', 'status': 'not-reviewed', ...}]

    def release_of(recs):  # the release adopted last at or before the session's first record, else None
        t = _when(min(r["writtenAt"] for r in recs))  # every time parses: the PR loop checked them first
        # axis: a session runs on the release adopted last at or before its first record, to the second — see bite-proof record i2498_by_release
>       got = [x for x in rel if x[0] <= t]
                                 ^^^^^^^^^
E       TypeError: '<=' not supported between instances of 'datetime.datetime' and 'NoneType'

<worktree>/plugins/superheroes/lib/review_measures.py:256: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_record_time_that_does_not_parse_reads_unmeasured_never_unplaced
1 failed, 17 deselected in 5.07s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        if any(_when(r["writtenAt"]) is None for r in every[pr]):`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 17 deselected in 0.25s
```

## e16. A broken time in one session of a PR (the PR loop's time check, round-4 finding code-001)

- **Axis:** one broken time on a PR leaves its first session unknown, so all four read unmeasured.
- **Detector:** `test_a_broken_time_in_one_session_of_a_pr_makes_all_four_unmeasured`.
- **Neutralization:** `if any(_when(r["writtenAt"]) is None for r in every[pr]):` became `if False:`.

Run at `db877135`, after review round 4, the lane's round cap: no reviewer has read this fix. The red is a crash (`TypeError`), as in e15.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_broken_time_in_one_session_of_a_pr_makes_all_four_unmeasured ______

    def test_a_broken_time_in_one_session_of_a_pr_makes_all_four_unmeasured():
        """`first()` orders sessions by their raw times, so one broken time on the PR leaves the first session unknown
        (round-4 finding code-001): the broken session may precede the valid one and the release adoption."""
>       m, why = _m([_rec(1, "good", at="2026-11-05T12:01:00Z"), _rec(1, "broken", at="2026-11-05Tbroken", status="not-reviewed")],
                    mergedPrs=[1])

<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:167: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
<worktree>/plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py:44: in _m
    row = RM.compute(inp, FROM, UNTIL)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_measures.py:442: in compute
    m.update(_release_measures(inp, prs, every, sessions, reason, miss))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_measures.py:315: in _release_measures
    put("silentReviewerVoids", release_of([r for r in rs if r["sessionId"] == sid]), state)
                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

recs = [{'pr': 1, 'sessionId': 'broken', 'writtenAt': '2026-11-05Tbroken', 'status': 'not-reviewed', ...}]

    def release_of(recs):  # the release adopted last at or before the session's first record, else None
        t = _when(min(r["writtenAt"] for r in recs))  # every time parses: the PR loop checked them first
        # axis: a session runs on the release adopted last at or before its first record, to the second — see bite-proof record i2498_by_release
>       got = [x for x in rel if x[0] <= t]
                                 ^^^^^^^^^
E       TypeError: '<=' not supported between instances of 'datetime.datetime' and 'NoneType'

<worktree>/plugins/superheroes/lib/review_measures.py:256: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_by_release_2498.py::test_a_broken_time_in_one_session_of_a_pr_makes_all_four_unmeasured
1 failed, 17 deselected in 0.32s
```

**Restore:** the inverse edit put the line back.
**Restore receipt** (the restored line, quoted): `        if any(_when(r["writtenAt"]) is None for r in every[pr]):`; `git status --porcelain` over the file printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 17 deselected in 0.23s
```
