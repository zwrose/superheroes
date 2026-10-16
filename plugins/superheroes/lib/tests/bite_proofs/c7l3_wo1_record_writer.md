# C7 L3 WO-1 bite-proof record: the review record writer

Five guarded elements, each with its own neutralization and its own red; none is grouped. Every red and green below is
the raw output of the single test node run alone through the CI-version interpreter
(`sbx-pytest.sh <node> -q`, run from the worktree root). Each neutralization was a targeted edit to
`plugins/superheroes/lib/review_record.py`, restored by the inverse edit; after each restore `diff` against a copy taken
before the first edit was empty, and the file ends with `git diff --quiet` exit 0. The node ids were confirmed by
collection (`--collect-only -q -k <test name>`) before any neutralization: each of BP-1 to BP-4 collected 1/53; the
lane-reason test collected 6/53 (its six parameter sets), and BP-5 runs the first of them by its full node id.

Declared guarded-element set (five): the axis lines in `plugins/superheroes/lib/review_record.py` cite this record.

## BP-1. `_resolve_parts`, the sha256 comparison

- Axis: the joined parts must hash to what the head recorded.
- Neutralization (`review_record.py:1275`): `if len(text) != chars or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:` became `if len(text) != chars:`.
- Node: `test_review_record_fit_c7l3.py::test_edge2_a_corrupted_part_fails_the_hash_check`

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_edge2_a_corrupted_part_fails_the_hash_check _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-40/test_edge2_a_corrupted_part_fa0')

    def test_edge2_a_corrupted_part_fails_the_hash_check(tmp_path):
        # axis: the parts hash; text changed inside a part, same length and still JSON, read as the record
        fake = two_part_record(tmp_path)
        part = parts_of(fake)[0]
        assert "reads the saved" in part["body"]
        part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1)
        out = rr.read(7, readers=fake.readers())
>       assert (out["ok"], out["reason"]) == (False, "review-record-unreadable")
                           ^^^^^^^^^^^^^
E       KeyError: 'reason'

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py:169: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_edge2_a_corrupted_part_fails_the_hash_check
1 failed in 1.25s
```

Restore: the inverse edit, `if len(text) != chars:` back to `if len(text) != chars or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:`.

Restore receipt (line 1275 read back after the restore; `diff` against the pre-edit copy empty):

```
    if len(text) != chars or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
```

Green:

```
.                                                                        [100%]
1 passed in 0.94s
```

## BP-2. `_marker_comments`, a part comment is not a record

- Axis: a part comment never becomes the latest record.
- Neutralization (`review_record.py:1305`): `.startswith(MARKER)` became `.startswith((MARKER, PART_MARKER))`.
- Node: `test_review_record_fit_c7l3.py::test_edge4_a_part_comment_is_never_the_latest_record`

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_edge4_a_part_comment_is_never_the_latest_record _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-42/test_edge4_a_part_comment_is_n0')

    def test_edge4_a_part_comment_is_never_the_latest_record(tmp_path):
        # axis: the part marker is not a record marker; a part comment newer than the head becoming the latest record
        fake = two_part_record(tmp_path)
        head = fake.marked()[0]
        fake.comments.append({"id": 10 ** 6, "author": "bot", "body": parts_of(fake)[0]["body"], "url": "http://c/part"})
        out = rr.read(7, readers=fake.readers())
>       assert out["ok"] and out["url"] == head["url"] and out["earlierRecords"] == []
E       assert (False)

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py:210: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_edge4_a_part_comment_is_never_the_latest_record
1 failed in 1.13s
```

Restore: the inverse edit, `.startswith((MARKER, PART_MARKER))` back to `.startswith(MARKER)`.

Restore receipt (line 1305 read back after the restore; `diff` against the pre-edit copy empty):

```
    return sorted((c for c in comments if str(c.get("body", "")).startswith(MARKER)), key=lambda c: c["id"])
```

Green:

```
.                                                                        [100%]
1 passed in 2.44s
```

## BP-3. `_recheck_decisions`, the write-time Canon re-check

- Axis: a ruling stands only while its cited decision is on record.
- Neutralization (`review_record.py:667`): `ok, text = finding_outcomes.on_record(by, sources())` became `ok, text = True, "x"`.
- Node: `test_review_record_fit_c7l3.py::test_a_ruling_citing_an_entry_that_is_not_on_record_goes_to_the_owner`

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_ruling_citing_an_entry_that_is_not_on_record_goes_to_the_owner _____

    def test_a_ruling_citing_an_entry_that_is_not_on_record_goes_to_the_owner():
        # axis: the write-time re-check; a ruling kept when the Canon entry it cites is absent
        rec = build(account(findings=[ruling("r-1", "2026-09-09-ffffffff-9")]), Fake(sources=CANON_SOURCES))
        f = rec["findings"][0]
>       assert f["outcome"] == "left-for-owner" and f["sheetPart"] == rfs.OUTCOME_SHEET_PART["left-for-owner"]
E       AssertionError: assert ('ruling' == 'left-for-owner'
E         
E         - left-for-owner
E         + ruling)

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py:335: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_a_ruling_citing_an_entry_that_is_not_on_record_goes_to_the_owner
1 failed in 0.76s
```

Restore: the inverse edit, `ok, text = True, "x"` back to `ok, text = finding_outcomes.on_record(by, sources())`.

Restore receipt (line 667 read back after the restore; `diff` against the pre-edit copy empty):

```
            ok, text = finding_outcomes.on_record(by, sources())
```

Green:

```
.                                                                        [100%]
1 passed in 0.74s
```

## BP-4. `build_record`, the go-ahead's Canon check

- Axis: a standing-ruling go-ahead counts only with its Canon entry on record.
- Neutralization (`review_record.py:715`): `good = next((g for g in complete if canon_on_record(g)), None)` became `good = next(iter(complete), None)`.
- Node: `test_review_record_fit_c7l3.py::test_a_standing_ruling_go_ahead_counts_only_when_its_canon_entry_is_on_record`

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_standing_ruling_go_ahead_counts_only_when_its_canon_entry_is_on_record _

    def test_a_standing_ruling_go_ahead_counts_only_when_its_canon_entry_is_on_record():
        # axis: the go-ahead's Canon check; a go-ahead naming an entry that is not on record lifting the park
        sec = reviewer("security-reviewer", ran=False, runDir=None)
        off = build(account(reviewers=[sec], goAheads=[SEC]), Fake(sources={}))
>       assert (off["status"], off["parked"]) == ("not-reviewed", True)
E       AssertionError: assert ('not-reviewed', False) == ('not-reviewed', True)
E         
E         At index 1 diff: False != True
E         Use -v to get more diff

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py:437: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_a_standing_ruling_go_ahead_counts_only_when_its_canon_entry_is_on_record
1 failed in 0.97s
```

Restore: the inverse edit, `good = next(iter(complete), None)` back to `good = next((g for g in complete if canon_on_record(g)), None)`.

Restore receipt (line 715 read back after the restore; `diff` against the pre-edit copy empty):

```
            good = next((g for g in complete if canon_on_record(g)), None)
```

Green:

```
.                                                                        [100%]
1 passed in 0.70s
```

## BP-5. `_lane_reason`, the leading-punctuation strip

- Axis: punctuation joining the lane word to its reason is not the reason.
- Neutralization (`review_record.py:339`): `return _REASON_LEAD_RE.sub("", text or "").strip() or None` became `return (text or "").strip() or None`.
- Node: `test_review_record_fit_c7l3.py::test_a_lane_reason_has_no_leading_punctuation[**Lane call:** full, inherited from #1814: why-inherited from #1814: why]`

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_lane_reason_has_no_leading_punctuation[**Lane call:** full, inherited from #1814: why-inherited from #1814: why] _

call = '**Lane call:** full, inherited from #1814: why'
reason = 'inherited from #1814: why'

    @pytest.mark.parametrize("call, reason", [
        ("**Lane call:** full, inherited from #1814: why", "inherited from #1814: why"),
        ("**Lane call:** full — because it touches money", "because it touches money"),
        ("**Lane call:** full;  : - small", "small"),
        ("**Lane call:** full,", None),
        ("**Lane call:** full — ", None),
        ("**Lane call:** full :;,-–—", None),
    ])
    def test_a_lane_reason_has_no_leading_punctuation(call, reason):
        # axis: the lane reason; punctuation joining the lane word to its reason shown as the reason
        pr = {"head": HEAD, "body": call, "issues": []}
        rec = build(account(laneReason=None), Fake(meta=pr))
>       assert rec["lane"]["reason"] == reason
E       AssertionError: assert ', inherited from #1814: why' == 'inherited from #1814: why'
E         
E         - inherited from #1814: why
E         + , inherited from #1814: why
E         ? ++

/home/user/wt-1869-wo1/plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py:282: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py::test_a_lane_reason_has_no_leading_punctuation[**Lane call:** full, inherited from #1814: why-inherited from #1814: why]
1 failed in 0.78s
```

Restore: the inverse edit, `return (text or "").strip() or None` back to `return _REASON_LEAD_RE.sub("", text or "").strip() or None`.

Restore receipt (line 339 read back after the restore; `diff` against the pre-edit copy empty):

```
    return _REASON_LEAD_RE.sub("", text or "").strip() or None
```

Green:

```
.                                                                        [100%]
1 passed in 0.72s
```
