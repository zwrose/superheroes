# C1-L11b (WO-D1b) bite-proof — a returning pull request's new review session

**Provenance:** implementer WO-D1b / `lib/returning_review.py`, `lib/round_driver.py`, `lib/tests/test_c1l11b_returning_session.py`

Declared guarded elements (from the order): (a) the decider's incomplete-record step in `returning_review.py` (the `_FINISHED_STATUSES` check); (b) the driver's returning switch in `round_driver.py` `_seed_returning_round`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear). Pytest tmp-path names are the session's scratch directories.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| A | `returning_review.py` line 236, the `earlier.get("status") not in _FINISHED_STATUSES or "abandoned" in earlier` step | an earlier review that was abandoned or never reviewed reads `full` | `test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit` |
| B | `round_driver.py` `_seed_returning_round`, the `if returning.get("read") != returning_review.READ_CHANGED:` switch | the driver acts on a `changed` decision: round 1 is a returning round with no panel | `test_t1_a_forty_line_fix_runs_no_panel_and_the_scoped_finder_reads_only_the_fix` |

Not separately neutralized (the unproven part of this record): the T1 scan's scoped-input assertions (hunks file, fix-delta diff and order must not carry the untouched util module), and every other test in the file.

---

## A — the decider's incomplete-record step

**axis:** a record that is `abandoned`, `not-reviewed` or has no status reads `full` (`earlier-review-incomplete`) even though a reviewer covers its final commit.

**neutralization** (`returning_review.py`, line 236):
```python
-    if earlier.get("status") not in _FINISHED_STATUSES or "abandoned" in earlier:
+    if False and (earlier.get("status") not in _FINISHED_STATUSES or "abandoned" in earlier):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l11b_returning_session.py -k t7`

The three `full` cases fail with the same assertion; the failure body of the first is shown in full, and the other two (`not-reviewed`, `no-status`) are identical in body (each shows the same `assert 'changed' == 'full'`, `['changed-only: nothing in the change since the last reviewed commit needs a full panel']`, at `test_c1l11b_returning_session.py:478`). The three-way parametrize source echo that pytest repeats in each failure is left out here (2 further copies):
```
FFF..                                                                    [100%]
=================================== FAILURES ===================================
_ test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit[abandoned] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_t7_an_earlier_review_that0')
damage = {'abandoned': {'reason': 'closed'}}, read = 'full'

    def test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit(tmp_path, damage, read):
        repo = TR.Repo(tmp_path)
        base, _, earlier = TR.returning(repo)
        assert earlier["reviewers"][0]["coversFinalCommit"] is True
        repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
        repo.commit("fix")
        record = {k: v for k, v in dict(earlier, **damage).items() if v is not None}
        got = TR.decide(repo, base, record)
>       assert got["read"] == read, got["why"]
E       AssertionError: ['changed-only: nothing in the change since the last reviewed commit needs a full panel']
E       assert 'changed' == 'full'
E         
E         - full
E         + changed

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_returning_session.py:478: AssertionError
  ... [not-reviewed]: same body, damage = {'status': 'not-reviewed'}
  ... [no-status]: same body, damage = {'status': None}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_returning_session.py::test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit[abandoned]
FAILED plugins/superheroes/lib/tests/test_c1l11b_returning_session.py::test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit[not-reviewed]
FAILED plugins/superheroes/lib/tests/test_c1l11b_returning_session.py::test_t7_an_earlier_review_that_did_not_finish_reads_full_even_when_a_reviewer_covers_its_final_commit[no-status]
3 failed, 2 passed, 33 deselected in 2.42s
```

**restore:** the inverse edit (`if False and (` ... `)` removed).

**restore receipt:** a search of `returning_review.py` for `_FINISHED_STATUSES or` finds lines 235-236, which read again:
```python
    # Axis: an earlier review that was abandoned or never reviewed reads full — see bite-proof record c1l11b_wo_d1_returning_session
    if earlier.get("status") not in _FINISHED_STATUSES or "abandoned" in earlier:
```

**raw green:** same command
```
.....                                                                    [100%]
5 passed, 33 deselected in 2.65s
```

---

## B — the driver's returning switch

**axis:** a `changed` decision makes round 1 a returning round (the scoped finder, no panel); a neutralized switch sends every returning session to the full panel.

**neutralization** (`round_driver.py`, `_seed_returning_round`):
```python
-    if returning.get("read") != returning_review.READ_CHANGED:
+    if True or returning.get("read") != returning_review.READ_CHANGED:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l11b_returning_session.py -k test_t1_a_forty_line_fix_runs_no_panel_and_the_scoped_finder_reads_only_the_fix`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_forty_line_fix_runs_no_panel_and_the_scoped_finder_reads_only_the_fix _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_t1_a_forty_line_fix_runs_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f8b2df5ab10>

    def test_t1_a_forty_line_fix_runs_no_panel_and_the_scoped_finder_reads_only_the_fix(tmp_path, monkeypatch):
        fix = TR.numbered("fix", 40)
        s = Session(tmp_path, monkeypatch, first=_first_leg(), change=_append("src/app.py", fix))
        answer = s.next()
        state = s.state()
>       assert (answer["action"], answer["phase"], answer["round"]) == (RD.P_SCOPED, RD.P_SCOPED, 1), answer
E       AssertionError: {'ok': True, 'action': 'dispatch-panel', 'round': 1, 'phase': 'dispatch-panel', ...}
E       assert ('dispatch-pa...tch-panel', 1) == ('dispatch-sc...ed-finder', 1)
E         
E         At index 0 diff: 'dispatch-panel' != 'dispatch-scoped-finder'
E         Use -v to get more diff

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_returning_session.py:160: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_returning_session.py::test_t1_a_forty_line_fix_runs_no_panel_and_the_scoped_finder_reads_only_the_fix
1 failed, 37 deselected in 2.74s
```

**restore:** the inverse edit (`True or ` removed).

**restore receipt:** a search of `round_driver.py` for `READ_CHANGED:` finds the switch at lines 1566-1567, which read again:
```python
    # axis: the driver acts on a changed decision — round 1 is a returning round with no panel — see bite-proof record c1l11b_wo_d1_returning_session
    if returning.get("read") != returning_review.READ_CHANGED:
```

**raw green:** same command
```
.                                                                        [100%]
1 passed, 37 deselected in 2.48s
```
