# Bite-proof record: i2658_review_record_links

Issue 2658: the review record reads a PR's issues only from what GitHub records (I1), and never treats an unreadable
earlier record as absent (I2). Detector: `plugins/superheroes/lib/tests/test_review_record_links_2658.py` (44 tests; one
per edge E1-E17 plus controls). Guarded file: `plugins/superheroes/lib/review_record.py`.

Method for every entry: one targeted edit to `review_record.py`, the named test run alone (command below, `-k` narrowing
only), then the inverse edit, and the restored lines quoted back. Redaction: nothing secret appears in any capture; the
one line each capture started with, `warning: The UV_NATIVE_TLS environment variable is deprecated ...` (a harness
warning), is left out of the captures below. All captures are far under the 32 KiB ceiling.

Command shape (run from the worktree root, Bash `timeout` 600000):
`scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-2658 -m pytest plugins/superheroes/lib/tests/test_review_record_links_2658.py -q -k <selector>`

Raw green, once after all ten restores (the whole new file):

```
............................................                             [100%]
44 passed in 1.07s
```

All ten elements are proven; none is listed unproven.

---

## G1 — the timeline cross-reference requirement in `recorded_links` (the DoD break-it proof)

- **element / axis:** `if linked:` in `recorded_links` (`review_record.py`, end of the per-candidate loop). Axis: a candidate
  the description names is linked only when GitHub's timeline holds the cross-reference; the description alone never links.
- **neutralization:** `        if linked:` -> `        if True:` (every candidate counts without the timeline check, the body-text read).
- **detector / selector:** E7, `-k test_e7_a_description`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e7_a_description_that_closes_an_issue_with_no_cross_reference_does_not_link_it _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe8e69025d0>

    def test_e7_a_description_that_closes_an_issue_with_no_cross_reference_does_not_link_it(monkeypatch):
        # axis: E7 (the DoD no-link test); the description's closing keyword read as GitHub's link
        gh = GH("Closes #9.\nmore", issues={9: issue_obj(9, body="**Lane call:** micro. one line")},
                timelines={9: [[{"event": "labeled"}, cross_ref(8)]]})
        meta = cloud_meta(monkeypatch, gh)
>       assert meta == {"head": HEAD, "body": "Closes #9.\nmore", "issues": [], "laneIssues": []}
E       AssertionError: assert {'head': 'bbb...eIssues': [9]} == {'head': 'bbb...neIssues': []}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'issues': [9]} != {'issues': []}
E         {'laneIssues': [9]} != {'laneIssues': []}
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e7_a_description_that_closes_an_issue_with_no_cross_reference_does_not_link_it
1 failed, 43 deselected in 0.88s
```

- **restore:** inverse edit `        if True:` -> `        if linked:`.
- **restore receipt (restored lines quoted back from the final diff):**
  `        if linked:` / `            found.append(n)` / `    return found`
- **raw green:** the whole-file green above.

## G2 — the repository comparison in `recorded_links`

- **element / axis:** `full_name.lower() == repo.lower()` in the link test. Axis: only a cross-reference from this
  repository's PR links; another repository's PR with the same number does not.
- **neutralization:** `            if number == pr and full_name.lower() == repo.lower():` -> `            if number == pr:`
- **detector / selector:** E5, `-k test_e5`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e5_a_cross_reference_from_another_repositorys_pr_with_the_same_number_is_not_linked _

    def test_e5_a_cross_reference_from_another_repositorys_pr_with_the_same_number_is_not_linked():
        # axis: E5; the repository of the cross-referencing PR not compared
>       assert links([9], {9: issue_obj(9)}, {9: [cross_ref(7, "x/y")]}) == []
E       assert [9] == []
E         
E         Left contains one more item: 9
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e5_a_cross_reference_from_another_repositorys_pr_with_the_same_number_is_not_linked
1 failed, 43 deselected in 0.79s
```

- **restore:** inverse edit `            if number == pr:` -> `            if number == pr and full_name.lower() == repo.lower():`.
- **restore receipt:** `            if number == pr and full_name.lower() == repo.lower():` (quoted from the final diff).
- **raw green:** the whole-file green above.

## G3 — the PR-number comparison in `recorded_links`

- **element / axis:** `number == pr` in the link test. Axis: only a cross-reference from this PR links; another PR of
  this repository does not.
- **neutralization:** `            if number == pr and full_name.lower() == repo.lower():` -> `            if full_name.lower() == repo.lower():`
- **detector / selector:** E6, `-k test_e6`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_e6_a_cross_reference_from_another_pr_of_this_repository_is_not_linked __

    def test_e6_a_cross_reference_from_another_pr_of_this_repository_is_not_linked():
        # axis: E6; the number of the cross-referencing PR not compared
>       assert links([9], {9: issue_obj(9)}, {9: [cross_ref(8)]}) == []
E       assert [9] == []
E         
E         Left contains one more item: 9
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:162: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e6_a_cross_reference_from_another_pr_of_this_repository_is_not_linked
1 failed, 43 deselected in 1.24s
```

- **restore:** inverse edit back to `            if number == pr and full_name.lower() == repo.lower():`.
- **restore receipt:** the same quoted line as G2 (the final diff shows the one line, with both legs).
- **raw green:** the whole-file green above.

## G4 — the PR-target skip in `recorded_links`

- **element / axis:** `if "pull_request" in target: continue`. Axis: a target that is a pull request is readable and not
  linked, and its timeline is not read.
- **neutralization:** `            if "pull_request" in target:` -> `            if False and "pull_request" in target:`
- **detector / selector:** E4, `-k test_e4`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e4_a_target_that_is_a_pull_request_is_not_linked_and_its_timeline_is_not_read _

    def test_e4_a_target_that_is_a_pull_request_is_not_linked_and_its_timeline_is_not_read():
        # axis: E4; a pull request named as a closed issue counted as linked, or its timeline asked for
        asked = []
    
        def timeline(n):
            asked.append(n)
            return [cross_ref(7)]
        got = rr.recorded_links([9, 4], REPO, 7, lambda n: {"number": n, **({"pull_request": {}} if n == 9 else {})}, timeline)
>       assert got == [4] and asked == [4]
E       assert ([9, 4] == [4]
E         
E         At index 0 diff: 9 != 4
E         Left contains one more item: 4
E         Use -v to get more diff)

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:151: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e4_a_target_that_is_a_pull_request_is_not_linked_and_its_timeline_is_not_read
1 failed, 43 deselected in 0.75s
```

- **restore:** inverse edit back to `            if "pull_request" in target:`.
- **restore receipt:** `            if "pull_request" in target:` / `                continue` (quoted from the final diff).
- **raw green:** the whole-file green above.

## G5 — the repository leg in `_pr_meta` (local reader)

- **element / axis:** `github_closing_issues(..., repo)` in `_pr_meta`. Axis: a local closing reference counts only in the
  record's own repository, and an entry with no repository leaves the links unreadable.
- **neutralization:** the two lines `issues = github_closing_issues(json.dumps({"closingIssuesReferences": d.get("closingIssuesReferences")}), repo) \` / `if repo else None`
  -> `issues = [i["number"] for i in d.get("closingIssuesReferences") or [] if isinstance(i, dict)]` (the number-only read of the base).
- **detector / selector:** E9, `-k test_e9`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e9_a_local_closing_reference_in_another_repository_is_not_this_repositorys_issue _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f08cf1fee70>

    def test_e9_a_local_closing_reference_in_another_repository_is_not_this_repositorys_issue(monkeypatch):
        # axis: E9; the repository of a closingIssuesReferences entry dropped, so another repository's #N counts here
        meta = _local_gh(monkeypatch, [_ref(3, "x", "y"), _ref(5), _ref(6, "O", "R")])
>       assert meta == {"head": HEAD, "body": "x", "issues": [5, 6]}
E       AssertionError: assert {'head': 'bbb...s': [3, 5, 6]} == {'head': 'bbb...sues': [5, 6]}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'issues': [3, 5, 6]} != {'issues': [5, 6]}
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e9_a_local_closing_reference_in_another_repository_is_not_this_repositorys_issue
1 failed, 43 deselected in 0.75s
```

- **restore:** inverse edit back to the two-line `github_closing_issues` expression.
- **restore receipt:** `        issues = github_closing_issues(json.dumps({"closingIssuesReferences": d.get("closingIssuesReferences")}), repo) \` / `            if repo else None` (quoted from the final diff).
- **raw green:** the whole-file green above.

## G6 — the unreadable return of `recorded_links` on a failed read

- **element / axis:** the two `return None` answers for an unreadable issue and an unreadable timeline. Axis: a read that
  fails is unreadable (None), never "no link" (an empty list).
- **neutralization (two edits, one element):** `        if not isinstance(rows, list):` + `            return None` -> `            return []`;
  and in the issue check `                return None` -> `                return []`.
- **detector / selector:** E1 and E2, `-k "test_e1 or test_e2"`.
- **raw red:**

```
FF............                                                           [100%]
=================================== FAILURES ===================================
_________ test_e1_an_issue_read_that_fails_is_unreadable_never_no_link _________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fea1d2f9760>

    def test_e1_an_issue_read_that_fails_is_unreadable_never_no_link(monkeypatch):
        # axis: E1; an issue GitHub could not be asked about read as "not linked"
>       assert links([9], {}, {9: [cross_ref(7)]}) is None
E       AssertionError: assert [] is None
E        +  where [] = links([9], {}, {9: [{'event': 'cross-referenced', 'source': {'issue': {'number': 7, 'pull_request': {}, 'repository': {'full_name': 'o/r'}}}}]})

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:107: AssertionError
____ test_e2_a_timeline_page_that_fails_is_unreadable_never_a_partial_read _____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fea1d2fa330>

    def test_e2_a_timeline_page_that_fails_is_unreadable_never_a_partial_read(monkeypatch):
        # axis: E2; a timeline read that stopped at a failed page read as the rows before it, or as none
>       assert links([9], {9: issue_obj(9)}, {}) is None
E       AssertionError: assert [] is None
E        +  where [] = links([9], {9: {'number': 9}}, {})

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e1_an_issue_read_that_fails_is_unreadable_never_no_link
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e2_a_timeline_page_that_fails_is_unreadable_never_a_partial_read
2 failed, 12 passed, 30 deselected in 0.99s
```

- **restore:** both inverse edits (`return []` -> `return None` at each site).
- **restore receipt:** `        if not isinstance(rows, list):` / `            return None` and `            if not isinstance(target, dict) or not _is_pos_int(target.get("number")) or target["number"] != n:` / `                return None` (quoted from the final diff).
- **raw green:** the whole-file green above.

## G7 — an unreadable link read never lets the marker promote the lane (`_lane`)

Re-proved by the builder after review round 1 of PR 2664, which reversed this element. It was an upward resolution, and
it now refuses to promote: a marker that could not be matched to the PR's issue never decides the lane.

- **element / axis:** `not unreadable and` in the marker leg of `_lane`. Axis: with the PR's links unreadable, a full build
  lane marker is never matched and never promotes the lane, so the session's own lane and its round cap stand.
- **neutralization:** `    if marker_full and not unreadable and str(m.get("issue")) in {str(n) for n in meta["issues"]}:` -> `    if marker_full and (unreadable or str(m.get("issue")) in {str(n) for n in meta["issues"]}):` (the earlier upward resolution, restored).
- **detector / selector:** E11, `-k test_e11`.
- **raw red** (the builder's run on the committed fix `90c889e8`, the failure lines verbatim):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e11_unreadable_links_never_let_a_full_marker_promote_the_sessions_lane __
>       with pytest.raises(rr.Refusal) as e:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:242: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e11_unreadable_links_never_let_a_full_marker_promote_the_sessions_lane
1 failed, 43 deselected in 0.84s
```

- **restore:** the inverse edit, back to `not unreadable and`.
- **restore receipt:** `git status --porcelain` printed nothing after the restore (the tree matched commit `90c889e8`).
- **raw green:**

```
.                                                                        [100%]
1 passed, 43 deselected in 3.74s
```

## G8 — `read_history` keeping unreadable entries

- **element / axis:** the `_usable(c, by_id) or _unreadable_entry(...)` return of `read_history`. Axis: an earlier record that
  does not read stays in the history as an unreadable entry; it is never dropped.
- **neutralization:** the return line -> `        return [u for u in (_usable(c, by_id) for c in found[:-1]) if u]` (drop them again).
- **detector / selector:** E13, `-k test_e13`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e13_read_history_keeps_each_unreadable_earlier_record_as_an_unreadable_entry _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f441cff6ab0>

    def test_e13_read_history_keeps_each_unreadable_earlier_record_as_an_unreadable_entry(monkeypatch):
        # axis: E13; an earlier record that does not parse, raises or lists malformed findings dropped from the history
        fake = Fake()
        fake.comments = [_record_comment(fake, "s-0", 1), _junk(2), _junk(3, "RAISE"), _junk(4, "MALFORMED"),
                         _record_comment(fake, "s-1", 5), _record_comment(fake, "s-2", 6)]
        real = rr._parse_body
    
        def parse(body, by_id=None):
            if "RAISE" in body:
                raise ValueError("boom")
            if "MALFORMED" in body:
                return {"schema": rr.RECORD_SCHEMA, "findings": "x"}
            return real(body, by_id)
        monkeypatch.setattr(rr, "_parse_body", parse)
        history = rr.read_history(7, REPO, fake.readers())
>       assert len(history) == 5 and [rr._is_unreadable_entry(h) for h in history] == [False, True, True, True, False]
E       AssertionError: assert (2 == 5)
E        +  where 2 = len([{'carriedRechecks': [], 'checked': ['Reviewers that ran: code-reviewer', 'read the diff'], 'ci': {'read': 'no CI work...tate': 'green', ...}, 'cost': {'minutes': 2.0, 'notCounted': [], 'source': 'engine records', 'tokens': 100, ...}, ...}])

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:304: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e13_read_history_keeps_each_unreadable_earlier_record_as_an_unreadable_entry
1 failed, 43 deselected in 0.76s
```

- **restore:** inverse edit back to the original return expression.
- **restore receipt:** `        return [_usable(c, by_id) or _unreadable_entry(c.get("url"), _unreadable_summary(c, by_id)) for c in found[:-1]]` (quoted from the final diff).
- **raw green:** the whole-file green above.

## G9 — `carry_source` stopping at an unreadable entry

- **element / axis:** `if _is_unreadable_entry(rec): return rec` in the `carry_source` walk. Axis: a carry never looks past an
  unreadable record to an older one it could carry from.
- **neutralization:** `            return rec` -> `            continue` under `if _is_unreadable_entry(rec):` in `carry_source`.
- **detector / selector:** E15 (both tests: through `write`, and through `review_record_session._carry_review`), `-k test_e15`.
- **raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_e15_a_same_session_rewrite_whose_intervening_record_is_unreadable_refuses_the_carry_naming_it _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_e15_a_same_session_rewrit0')

    def test_e15_a_same_session_rewrite_whose_intervening_record_is_unreadable_refuses_the_carry_naming_it(tmp_path):
        # axis: E15 through the record writer; the carry walk looking past an unreadable record to the older one it carried from
        fake, readers = _carried_session(tmp_path)
        out = rr.write(put(tmp_path, carried_account(), "third.json"), str(tmp_path), readers)
        assert out["ok"], out
        row = rr._parse_body(fake.comments[-1]["body"])["reviewers"][0]
>       assert row["ran"] == "not-run" and "carried" not in row
E       AssertionError: assert ('engine-record' == 'not-run'
E         
E         - not-run
E         + engine-record)

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:363: AssertionError
_ test_e15_the_session_carry_path_refuses_with_the_reason_naming_the_unreadable_record _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_e15_the_session_carry_pat0')

    def test_e15_the_session_carry_path_refuses_with_the_reason_naming_the_unreadable_record(tmp_path):
        # axis: E15 through review_record_session; review_record_session's carry reading past an unreadable record
        fake, readers = _carried_session(tmp_path)
        acct = {"pr": 7, "sessionId": "s-2", "carryBase": CARRY_BASE, "finalCommit": HEAD}
>       with pytest.raises(rs.Refusal) as e:
             ^^^^^^^^^^^^^^^^^^^^^^^^^

E       Failed: DID NOT RAISE Refusal

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:372: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e15_a_same_session_rewrite_whose_intervening_record_is_unreadable_refuses_the_carry_naming_it
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e15_the_session_carry_path_refuses_with_the_reason_naming_the_unreadable_record
2 failed, 42 deselected in 0.80s
```

- **restore:** inverse edit `            continue` -> `            return rec`.
- **restore receipt:** `        if _is_unreadable_entry(rec):` / `            return rec` (quoted from the final diff).
- **raw green:** the whole-file green above.

## G10 — `_earlier_session_record` stopping at an unreadable entry

- **element / axis:** `if _is_unreadable_entry(rec): return None` in `_earlier_session_record`. Axis: the carried-findings
  authority never takes a record older than an unreadable one as the earlier record of another session.
- **neutralization:** `            return None` -> `            continue` under that `if`.
- **detector / selector:** E16, `-k test_e16`.
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_e16_the_earlier_session_record_walk_stops_at_an_unreadable_entry _____

    def test_e16_the_earlier_session_record_walk_stops_at_an_unreadable_entry():
        # axis: E16; a record older than an unreadable one taken as the earlier record of another session
        own = {"sessionId": "s-2"}
        older = {"sessionId": "s-0"}
        entry = rr._unreadable_entry("http://c/2", "gone")
        assert rr._earlier_session_record(own, [older], "s-2") is older
>       assert rr._earlier_session_record(own, [older, entry], "s-2") is None
E       AssertionError: assert {'sessionId': 's-0'} is None
E        +  where {'sessionId': 's-0'} = <function _earlier_session_record at 0x7f3296a88b80>({'sessionId': 's-2'}, [{'sessionId': 's-0'}, {'unreadableRecord': {'url': 'http://c/2', 'detail': 'gone'}}], 's-2')
E        +    where <function _earlier_session_record at 0x7f3296a88b80> = rr._earlier_session_record

/home/user/superheroes/.claude/worktrees/issue-2658/plugins/superheroes/lib/tests/test_review_record_links_2658.py:398: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_e16_the_earlier_session_record_walk_stops_at_an_unreadable_entry
1 failed, 43 deselected in 0.76s
```

- **restore:** inverse edit `            continue` -> `            return None`.
- **restore receipt:** `        if _is_unreadable_entry(rec):` / `            return None` (quoted from the final diff).
- **raw green:** the whole-file green above.
- **since review round 1 of PR 2664:** the helper returns the unreadable entry itself (`return rec`), so the carried re-check
  can name it. E16 asserts `is entry`, and the same `continue` neutralization still turns it red. The proof above is
  the order's run on the earlier `return None` form.

## G11 — the writer keeps an unreadable latest record in its history (`write`)

Added by the builder after review round 1 of PR 2664. T6 in `test_review_record_carried_2343.py` points here.

- **element / axis:** `if usable is None: history.append(_unreadable_entry(...))` in the latest-record branch of `write`.
  Axis: an unreadable latest record is the newest history entry, so the carried re-check stops at it, and an older
  record of another session never settles a carried finding past it.
- **neutralization:** `                if usable is None:` -> `                if usable is None and False:`.
- **detectors / selector:** T6 (both cases) and `test_an_unreadable_latest_record_stops_the_writers_carried_recheck`, via
  `-k "t6 or unreadable_latest"` over `test_review_record_carried_2343.py` and this record's test file.
- **raw red** (the builder's run on commit `575dbb86`, the failure lines verbatim, the source dump elided):

```
FFF                                                                      [100%]
>       assert the_one(rec)["outcome"] == finding.get("outcome")
E       AssertionError: assert 'fixed' == 'left-for-owner'
>       assert the_one(rec)["outcome"] == finding.get("outcome")
E       AssertionError: assert 'fixed' == None
>       assert "an earlier review record could not be read (" in json.dumps(rec["carriedRechecks"])
E       assert 'an earlier review record could not be read (' in '[{"checkedHead": "bbbb...", ..., "result": "kept", "settled": "fixed", "why": "its fix commit\'s place in the history could not be read"}]'
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2343.py::test_t6_an_unreadable_latest_record_stops_the_older_other_session_record_from_carrying_the_finding[left-for-owner]
FAILED plugins/superheroes/lib/tests/test_review_record_carried_2343.py::test_t6_an_unreadable_latest_record_stops_the_older_other_session_record_from_carrying_the_finding[undecided]
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_an_unreadable_latest_record_stops_the_writers_carried_recheck
3 failed, 65 deselected in 1.19s
```

- **restore:** the inverse edit, back to `if usable is None:`.
- **restore receipt:** `git status --porcelain` printed nothing after the restore (the tree matched commit `575dbb86`).
- **raw green:**

```
...                                                                      [100%]
3 passed, 65 deselected in 1.07s
```

## G12 — an unreadable earlier record leaves the test-lens count unavailable (`_test_lens`)

Added by the builder after review rounds 2 and 3 of PR 2664.

- **element / axis:** `if _is_unreadable_entry(other): part["findings"] = None` in `_test_lens`. The chosen row's `carried` marker is
  still copied. Axis: when the earlier record could not be read, which findings were carried cannot be told. So the count
  is unavailable, never credited to this round, and a carried row still reads as carried.
- **neutralization:** `    if _is_unreadable_entry(other):` -> `    if _is_unreadable_entry(other) and False:`.
- **detector / selector:** `test_an_unreadable_earlier_record_leaves_the_test_lens_count_unavailable`, `-k test_lens_count_unavailable`.
- **raw red** (the builder's run on commit `6565498f`, the failure lines verbatim):

```
F                                                                        [100%]
___ test_an_unreadable_earlier_record_leaves_the_test_lens_count_unavailable ___
>       assert part["listed"] is True and part["ran"] is True and part["findings"] is None
E       assert (True is True and True is True and 1 is None)
FAILED plugins/superheroes/lib/tests/test_review_record_links_2658.py::test_an_unreadable_earlier_record_leaves_the_test_lens_count_unavailable
1 failed, 57 deselected in 15.50s
```

- **restore:** the inverse edit.
- **restore receipt:** `git status --porcelain` printed nothing after the restore (the tree matched commit `6565498f`).
- **raw green:** shared with H8 in `i2658_parked_links.md` (`2 passed, 73 deselected in 4.26s`).

---

Not in the declared set, and so not neutralized here: the `earlier` filter in `write` (the E17 guard), the
`issueLinks` renderer sentence, and `carry_refusal`'s unreadable-prior leg. E17, E11 and the E15 tests assert each one's
effect, but no red run in this record neutralizes them.
