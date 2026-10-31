# #1795 bite-proof — the lane floor (WO-A: `lane_call.py` and the review record's `laneBasis`)

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Per-element bite-proof for the detectors in `plugins/superheroes/lib/lane_call.py` and `plugins/superheroes/lib/review_record.py`, following `plugins/superheroes/rubric/bite-proof.md`. Each element was neutralized with one targeted edit, its single test node ran alone and went red, the edit was undone by the inverse edit, the restored line was quoted back, and the same node ran green. No test file was edited between a red and its green.

Command for every run (never `-k`, never filtered):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<file>::<test>' -q
```

`T` = `plugins/superheroes/lib/tests/test_lane_call.py`, `R` = `plugins/superheroes/lib/tests/test_review_record.py`.

Declared guarded-element set: G1–G9, as dispatched. Redaction: none needed; local temp paths are left as printed.

## Summary

| ID | Guarded element | Axis | Neutralization | Node | Red |
|---|---|---|---|---|---|
| G1 | `lane_call.call` touched → full floor | a change touching a risk area gets the floor `full` | `for hit in hits:` → `for hit in []:` | `T::test_a_two_line_change_to_a_payments_file_gets_the_full_lane` | `assert (None == 'full')` |
| G2 | `lane_call.call` not-set → full floor | risk areas not set (missing, empty, unreadable) get the floor `full` | `if state != "set":` → `if False and state != "set":` | `T::test_e1_risk_areas_not_set_for_any_reason_get_the_floor_full` | `assert (None == 'full')` |
| G3 | `lane_call.call` unmatchable → full floor | an unmatchable path gets the floor `full` | `if unmatchable:` → `if False and unmatchable:` | `T::test_e2_an_all_unmatchable_change_with_set_areas_gets_the_floor_full_never_light` | `assert (None == 'full')` |
| G4 | `lane_call.call` no-paths → full floor | an empty paths list gets the floor `full` | `if isinstance(paths, list) and not paths:` → `if False and isinstance(paths, list) and not paths:` | `T::test_e4_an_empty_paths_list_gets_the_floor_full_even_with_set_areas` | `assert (None == 'full')` |
| G5 | `lane_call.call` never-lower rule | a proposal below the floor never lowers the lane | `elif floor is not None and rank(proposed) < rank(floor):` → `elif False and floor is not None and rank(proposed) < rank(floor):` | `T::test_e6_a_proposal_below_the_floor_gets_full_and_is_not_taken[light]` | `'light' == 'full'` on the lane |
| G6 | `review_record._lane_lines` below-floor line | a lane below the risk floor is `not-reviewed` | `if basis["floor"] is not None and ...` → `if False and basis["floor"] is not None and ...` | `R::test_e9_a_lane_below_the_floor_is_not_reviewed_with_that_line` | `'reviewed' == 'not-reviewed'` |
| G7 | `review_record._lane_basis` fail-closed basis | unreadable changed files give the floor `full`, marked unavailable | `lane_call.call(root, [])` → `lane_call.call(root, ["README.md"])` in the unavailable branch | `R::test_e8_changed_files_that_cannot_be_read_give_the_full_floor_marked_unavailable` | `assert (None == 'full')` |
| G8 | `review_record.changed_paths` 3000-entry ceiling | a list that may be cut short is unavailable | `if files is None or len(files) >= _FILES_CEILING:` → `if files is None or False and len(files) >= _FILES_CEILING:` | `R::test_e10_3000_entries_is_the_ceiling_and_makes_the_files_unavailable` | `assert [...] is None` |
| G9 | `review_record.changed_paths` `previous_filename` | a rename out of a risk area still touches it | `if previous is not None:` → `if False and previous is not None:` | `R::test_e11_a_rename_out_of_a_risk_area_touches_it_through_the_previous_name` | `['docs/moved.py'] == ['docs/moved.py', 'src/payments/charge.py']` |

G7 note: the unreadable branch is neutralized to look at a clean path rather than none, so the red is the fail-open the element guards (floor `None` for a light lane over a repo with a Payments area), not a rewording.

G9 note: the red is on the first assertion of the node, the returned list; the floor assertions after it are not reached. The axis is the same: the previous name is dropped from the list.

## G1 — touched → full floor

Neutralization: `plugins/superheroes/lib/lane_call.py` line 46, `for hit in hits:` → `for hit in []:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_two_line_change_to_a_payments_file_gets_the_full_lane _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1493/test_a_two_line_change_to_a_pa0')

    def test_a_two_line_change_to_a_payments_file_gets_the_full_lane(tmp_path):
        # the paths are the only input about the change: there is no size, line count or diff parameter
        assert list(inspect.signature(L.call).parameters) == ["cwd", "paths", "proposed", "root"]
        repo, store = _payments_repo(tmp_path)
        got = L.call(repo, ["src/payments/charge.py"], root=store)
        assert set(got) == RESULT_KEYS
>       assert got["floor"] == "full" and got["lane"] == "full"
E       AssertionError: assert (None == 'full')

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_lane_call.py:103: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_a_two_line_change_to_a_payments_file_gets_the_full_lane
1 failed in 2.26s
```

Restore: the inverse edit. Restored line quoted back: `46:    for hit in hits:`

Green:

```
.                                                                        [100%]
1 passed in 2.13s
```

Disclosure: this green ran in the same tool batch as the next element's neutralization edit (G2, which touches a line this node does not reach, since the fixture's risk areas are set). The final run of `T` and `R` together (see the return) covers the restored file.

## G2 — not-set → full floor

Neutralization: `lane_call.py` line 50, `if state != "set":` → `if False and state != "set":`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_e1_risk_areas_not_set_for_any_reason_get_the_floor_full _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1495/test_e1_risk_areas_not_set_for0')

    def test_e1_risk_areas_not_set_for_any_reason_get_the_floor_full(tmp_path):
        missing = tmp_path / "missing"
        empty = tmp_path / "empty"
        unreadable = tmp_path / "unreadable"
        for d in (missing, empty, unreadable):
            d.mkdir()
        cases = [
            ("missing", _repo(missing, with_key=False)),
            ("empty", _repo(empty, [])),
            ("unreadable", _raw_core(unreadable, json.dumps(
                {"schemaVersion": 2, "verifyCommand": "npm test", "stackTags": ["node"],
                 "projectConfiguration": ["risk"]}))),
        ]
        for reason, (repo, store) in cases:
            got = L.call(repo, ["docs/readme.md"], proposed="light", root=store)
            assert got["riskAreas"]["state"] == "not-set" and got["riskAreas"]["reason"] == reason
>           assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
E           AssertionError: assert (None == 'full')

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_lane_call.py:151: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_e1_risk_areas_not_set_for_any_reason_get_the_floor_full
1 failed in 4.00s
```

Restore: the inverse edit. Restored line quoted back: `50:    if state != "set":`

Green:

```
.                                                                        [100%]
1 passed in 4.44s
```

## G3 — unmatchable → full floor

Neutralization: `lane_call.py` line 55, `if unmatchable:` → `if False and unmatchable:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e2_an_all_unmatchable_change_with_set_areas_gets_the_floor_full_never_light _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1497/test_e2_an_all_unmatchable_cha0')

    def test_e2_an_all_unmatchable_change_with_set_areas_gets_the_floor_full_never_light(tmp_path):
        repo, store = _payments_repo(tmp_path)
        paths = ["/etc/passwd", "../outside.py", "src/../../x.py", ""]
        got = L.call(repo, paths, proposed="light", root=store)
        assert got["riskAreas"]["state"] == "set" and got["touched"] == []
        assert got["unmatchable"] == paths
>       assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
E       AssertionError: assert (None == 'full')

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_lane_call.py:162: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_e2_an_all_unmatchable_change_with_set_areas_gets_the_floor_full_never_light
1 failed in 2.44s
```

Restore: the inverse edit. Restored line quoted back: `55:    if unmatchable:`

Green:

```
.                                                                        [100%]
1 passed in 2.68s
```

## G4 — no-paths → full floor

Neutralization: `lane_call.py` line 60, `if isinstance(paths, list) and not paths:` → `if False and isinstance(paths, list) and not paths:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e4_an_empty_paths_list_gets_the_floor_full_even_with_set_areas ______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1499/test_e4_an_empty_paths_list_ge0')

    def test_e4_an_empty_paths_list_gets_the_floor_full_even_with_set_areas(tmp_path):
        repo, store = _payments_repo(tmp_path)
        got = L.call(repo, [], proposed="light", root=store)
        assert got["riskAreas"]["state"] == "set"
>       assert got["floor"] == "full" and got["lane"] == "full" and got["proposalTaken"] is False
E       AssertionError: assert (None == 'full')

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_lane_call.py:178: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_e4_an_empty_paths_list_gets_the_floor_full_even_with_set_areas
1 failed in 2.41s
```

Restore: the inverse edit. Restored line quoted back: `60:    if isinstance(paths, list) and not paths:`

Green:

```
.                                                                        [100%]
1 passed in 2.64s
```

## G5 — the never-lower rule

Neutralization: `lane_call.py` line 75, `elif floor is not None and rank(proposed) < rank(floor):` → `elif False and floor is not None and rank(proposed) < rank(floor):`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e6_a_proposal_below_the_floor_gets_full_and_is_not_taken[light] _____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1501/test_e6_a_proposal_below_the_f0')
proposed = 'light'

    @pytest.mark.parametrize("proposed", ["light", "micro"])
    def test_e6_a_proposal_below_the_floor_gets_full_and_is_not_taken(tmp_path, proposed):
        repo, store = _payments_repo(tmp_path)
        got = L.call(repo, ["src/db/schema.sql"], proposed=proposed, root=store)
>       assert got["floor"] == "full" and got["lane"] == "full"
E       AssertionError: assert ('full' == 'full'
E         
E           full and 'light' == 'full'
E         
E         - full
E         + light)

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_lane_call.py:195: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_e6_a_proposal_below_the_floor_gets_full_and_is_not_taken[light]
1 failed in 3.38s
```

Restore: the inverse edit. Restored line quoted back: `75:    elif floor is not None and rank(proposed) < rank(floor):`

Green:

```
.                                                                        [100%]
1 passed in 3.09s
```

## G6 — the record's below-floor line

Neutralization: `plugins/superheroes/lib/review_record.py` line 456, `if basis["floor"] is not None and lane_call.rank(lane) < lane_call.rank(basis["floor"]):` → `if False and basis["floor"] is not None and lane_call.rank(lane) < lane_call.rank(basis["floor"]):`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_e9_a_lane_below_the_floor_is_not_reviewed_with_that_line _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1503/test_e9_a_lane_below_the_floor0')

    def test_e9_a_lane_below_the_floor_is_not_reviewed_with_that_line(tmp_path):
        # axis: the below-floor line; a light lane over a risk-area change leaving the record reviewed
        repo = risk_repo(tmp_path)
        fake = Fake(meta=LIGHT_PR)
        fake.changed = ["src/payments/charge.py"]
        rec = build(account(repoRoot=repo), fake)
        assert rec["lane"]["value"] == "light" and rec["laneBasis"]["floor"] == "full"
        line = f"the lane (light) is below the risk floor (full): {PAY_FLOOR}"
>       assert rec["status"] == "not-reviewed" and line in rec["whatIsMissing"]
E       AssertionError: assert ('reviewed' == 'not-reviewed'
E         
E         - not-reviewed
E         ? ----
E         + reviewed)

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1454: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_e9_a_lane_below_the_floor_is_not_reviewed_with_that_line
1 failed in 3.34s
```

Restore: the inverse edit. Restored line quoted back: `456:    if basis["floor"] is not None and lane_call.rank(lane) < lane_call.rank(basis["floor"]):`

Green:

```
.                                                                        [100%]
1 passed in 3.70s
```

## G7 — the fail-closed basis when the changed files are unreadable

Neutralization: `review_record.py` line 329, `basis = dict(lane_call.call(root, []), source="unavailable")` → `basis = dict(lane_call.call(root, ["README.md"]), source="unavailable")`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e8_changed_files_that_cannot_be_read_give_the_full_floor_marked_unavailable _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1505/test_e8_changed_files_that_can0')

    def test_e8_changed_files_that_cannot_be_read_give_the_full_floor_marked_unavailable(tmp_path):
        # axis: the unavailable basis; unreadable changed files leaving no floor for a light lane
        repo = risk_repo(tmp_path)
        fake = Fake(meta=LIGHT_PR)
        fake.changed = None
        rec = build(account(repoRoot=repo), fake)
        basis = rec["laneBasis"]
        assert set(basis) == BASIS_KEYS and basis["source"] == "unavailable"
>       assert basis["floor"] == "full" and basis["why"][0] == UNREAD
E       AssertionError: assert (None == 'full')

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1495: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_e8_changed_files_that_cannot_be_read_give_the_full_floor_marked_unavailable
1 failed in 5.29s
```

Restore: the inverse edit. Restored line quoted back: `329:    basis = dict(lane_call.call(root, []), source="unavailable")`

Green:

```
.                                                                        [100%]
1 passed in 4.78s
```

## G8 — the 3000-entry ceiling

Neutralization: `review_record.py` line 176, `if files is None or len(files) >= _FILES_CEILING:` → `if files is None or False and len(files) >= _FILES_CEILING:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e10_3000_entries_is_the_ceiling_and_makes_the_files_unavailable _____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1507/test_e10_3000_entries_is_the_c0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10b2a8fb0>

    def test_e10_3000_entries_is_the_ceiling_and_makes_the_files_unavailable(tmp_path, monkeypatch):
        # axis: the 3000-file ceiling; a list GitHub may have cut short read as the whole change
        repo = risk_repo(tmp_path)
    
        def entry(i):
            return {"filename": f"docs/f{i}.md", "status": "added"}
        canned_gh(monkeypatch, gh_files(*[entry(i) for i in range(2999)]))
        assert len(rr.changed_paths(7, "o/r")) == 2999
        out = gh_files(*[entry(i) for i in range(3000)])
        canned_gh(monkeypatch, out)
>       assert rr.changed_paths(7, "o/r") is None
E       AssertionError: assert ['docs/f0.md', 'docs/f1.md', 'docs/f2.md', 'docs/f3.md', 'docs/f4.md', 'docs/f5.md', ...] is None
E        +  where ['docs/f0.md', 'docs/f1.md', 'docs/f2.md', 'docs/f3.md', 'docs/f4.md', 'docs/f5.md', ...] = <function changed_paths at 0x10bdf3ba0>(7, 'o/r')
E        +    where <function changed_paths at 0x10bdf3ba0> = rr.changed_paths

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1526: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_e10_3000_entries_is_the_ceiling_and_makes_the_files_unavailable
1 failed in 5.07s
```

Restore: the inverse edit. Restored line quoted back: `176:    if files is None or len(files) >= _FILES_CEILING:`

Green:

```
.                                                                        [100%]
1 passed in 5.12s
```

## G9 — `previous_filename` inclusion

Neutralization: `review_record.py` line 187, `if previous is not None:` → `if False and previous is not None:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_e11_a_rename_out_of_a_risk_area_touches_it_through_the_previous_name ___

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1509/test_e11_a_rename_out_of_a_ris0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10b28ca40>

    def test_e11_a_rename_out_of_a_risk_area_touches_it_through_the_previous_name(tmp_path, monkeypatch):
        # axis: previous_filename kept in the list; a rename out of a risk area looking like a change outside it
        repo = risk_repo(tmp_path)
        out = gh_files({"filename": "docs/moved.py", "previous_filename": "src/payments/charge.py", "status": "renamed"})
        canned_gh(monkeypatch, out)
>       assert rr.changed_paths(7, "o/r") == ["docs/moved.py", "src/payments/charge.py"]
E       AssertionError: assert ['docs/moved.py'] == ['docs/moved....ts/charge.py']
E         
E         Right contains one more item: 'src/payments/charge.py'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1550: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_e11_a_rename_out_of_a_risk_area_touches_it_through_the_previous_name
1 failed in 4.90s
```

Restore: the inverse edit. Restored lines quoted back: `187:        if previous is not None:` / `188:            paths.append(previous)`

Green:

```
.                                                                        [100%]
1 passed in 5.22s
```

## Review-round elements (builder-run, after the review loop)

The review loop's fixer rounds added four guards to `plugins/superheroes/lib/review_record.py`. The builder proved each one in a detached probe worktree at `5bf3d5a60`, in the same shape as above: one targeted edit, the single node run alone (red), the inverse edit with the file confirmed byte-equal and `git status --porcelain` empty, then the node again (green). Command: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest '<node>' -q -p no:cacheprovider`. Declared set: H3–H6.

| ID | Guarded element | Axis | Neutralization | Node (`R::`) | Red | Green |
|---|---|---|---|---|---|---|
| H3 | `_lane_basis` head re-check | a file list read while the PR head moved is unavailable | `if isinstance(paths, list) and not (after and after.get("head") == final_sha):` → `if False and …` | `test_a_head_that_moves_between_the_meta_read_and_the_files_read_gives_the_unavailable_basis` | `AssertionError: assert ('lane rule ov...changed files' == 'unavailable'` · `1 failed` | `1 passed` |
| H4 | `render` claim guard on composed prose | composed prose that claims no bugs is refused | `… for l in lines if l is not floor_line` → `… for l in lines if False` | `test_composed_prose_claiming_no_bugs_is_refused_on_a_below_floor_record` | `Failed: DID NOT RAISE Refusal` · `1 failed` | `1 passed` |
| H5 | `render` shed loop | an oversized body sheds lane-basis evidence until it fits | `r = dict(r, laneBasis=step(r["laneBasis"]))` → `r = dict(r, laneBasis=r["laneBasis"])` | `test_four_byte_paths_across_many_areas_render_under_the_cap_with_the_floor_full` | `review_record.Refusal: ('review-record-too-large', '191910 characters')` · `1 failed` | `1 passed` |
| H6 | `render` floor-line exemption | the Risk floor line's literal paths never trip the claim guard | `… for l in lines if l is not floor_line` → `"\n".join(lines)` | `test_a_below_floor_oversized_record_with_a_bug_free_path_publishes_not_reviewed` | `review_record.Refusal: ('review-record-forbidden-claim', 'bug-free')` · `1 failed` | `1 passed` |

H4 and H6 neutralize the same line in opposite directions: H4 checks no line and H6 checks every line. One proves the guard still bites on prose, and the other proves the exemption is what lets literal data through.
