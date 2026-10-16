# wo_c_1795_lane-basis — the review record's hermetic lane basis

Declared guarded-element set (from the work order): **H1** the no-`repoRoot` leg of `_lane_basis` refuses to read;
**H2** `unavailable` returns floor `full`. Each was neutralized once, the single detector node run alone, restored by
the inverse edit, and the node re-run green. Redaction: the worktree's absolute path is written `<worktree>` and the
pytest tmp directory is elided; nothing else was secret.

## H1 — `_lane_basis` with no usable `repoRoot` reads nothing

**Guarded element:** `plugins/superheroes/lib/review_record.py` `_lane_basis`, the `if not repo_root:` leg. Axis: an
account that names no repository gets the unavailable basis and reads neither the store nor the PR's changed files
(refusal to read, not merely the shape of the result).

**Detector:** `test_review_record.py::test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files`
(three parametrized cases: `repoRoot` absent, `None`, `""`; the `changed_paths` reader and `risk_areas.touched` raise).

**Neutralization:** `    if not repo_root:` → `    if False:` (the leg can never be taken, so control reaches the
`changed_paths` reader).

**Raw red** (the three tracebacks are identical but for the case id; the first is quoted whole, the other two keep
their header, failing line and assertion, the repeated source listing elided):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files[over0] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1090b9460>, over = {}

    @pytest.mark.parametrize("over", [{}, {"repoRoot": None}, {"repoRoot": ""}])
    def test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files(monkeypatch, over):
        # axis: the no-repoRoot leg of the basis; an account naming no repository falling back to the ambient project
        readers = _refuse_any_read(monkeypatch)
>       rec = rr.build_record(account(**over), readers)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

<worktree>/plugins/superheroes/lib/tests/test_review_record.py:1513: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
<worktree>/plugins/superheroes/lib/review_record.py:525: in build_record
    "laneBasis": _lane_basis(a, rd, lane["value"]), "finalCommit": fc,
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/review_record.py:333: in _lane_basis
    paths = rd["changed_paths"](a["pr"], a["repo"])
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

args = (7, None), kwargs = {}

    def boom(*args, **kwargs):
>       raise AssertionError("the basis read a store or the PR's changed files")
E       AssertionError: the basis read a store or the PR's changed files

<worktree>/plugins/superheroes/lib/tests/test_review_record.py:1504: AssertionError
_ test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files[over1] _
  (same traceback; over = {'repoRoot': None})
E       AssertionError: the basis read a store or the PR's changed files
_ test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files[over2] _
  (same traceback; over = {'repoRoot': ''})
E       AssertionError: the basis read a store or the PR's changed files
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files[over0]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files[over1]
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files[over2]
3 failed in 0.89s
```
The red is on the claimed axis: the failure is the reader being reached (the refusal to read), raised from the
production call site `_lane_basis`, not a shape or count mismatch.

**Restore:** the inverse edit `    if False:` → `    if not repo_root:`.

**Restore receipt** (the restored lines quoted back, `grep -n -B1 -A1 "if not repo_root:"`):
```
328-    # axis: an account that names no repository reads nothing, so no other project's store is read — see bite-proof record wo_c_1795_lane-basis
329:    if not repo_root:
330-        return dict(lane_call.unavailable(
```

**Raw green:**
```
...                                                                      [100%]
3 passed in 1.26s
```

## H2 — `unavailable` returns floor `full`

**Guarded element:** `plugins/superheroes/lib/lane_call.py` `unavailable`, the `"floor": FLOOR_FULL` entry. Axis: a
basis that was never read has the floor `full`, never no floor and never a lower one.

**Detector:** `test_lane_call.py::test_unavailable_carries_exactly_the_call_keys_and_the_full_floor`.

**Neutralization:** `        "floor": FLOOR_FULL,` → `        "floor": None,`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_unavailable_carries_exactly_the_call_keys_and_the_full_floor _______

tmp_path = PosixPath('<tmp>/test_unavailable_carries_exact0')

    def test_unavailable_carries_exactly_the_call_keys_and_the_full_floor(tmp_path):
        repo, store = _payments_repo(tmp_path)
        got = L.unavailable("risk-unclear-not-set: nothing was read")
        assert set(got) == RESULT_KEYS == set(L.call(repo, ["docs/readme.md"], root=store))
        # axis: a basis that was never read gets the floor full; an unread basis leaving no floor or a lower lane
>       assert got["floor"] == "full" and got["lane"] == "full"
E       AssertionError: assert (None == 'full')

<worktree>/plugins/superheroes/lib/tests/test_lane_call.py:348: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_lane_call.py::test_unavailable_carries_exactly_the_call_keys_and_the_full_floor
1 failed in 6.51s
```

**Restore:** the inverse edit `        "floor": None,` → `        "floor": FLOOR_FULL,`.

**Restore receipt** (the restored lines quoted back, `grep -n -B2 -A3 '"floor": FLOOR_FULL'`):
```
104-    return {
105-        # axis: a basis that was never read gets the floor full — see bite-proof record wo_c_1795_lane-basis
106:        "floor": FLOOR_FULL,
107-        "lane": FLOOR_FULL,
108-        "why": reasons,
109-        "riskAreas": {"state": "not-set", "reason": "unreadable", "detail": "not-read"},
```

**Raw green:**
```
.                                                                        [100%]
1 passed in 6.14s
```
