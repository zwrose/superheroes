# Bite-proof record — a hand-written review account's missing cost reads hand-written (#2515)

Detector file: `plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one line of `plugins/superheroes/lib/review_measures.py` (`_hand_written_only`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2515 -m pytest plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py -q -p no:cacheprovider -k "<fragment>"`. Each capture is the whole output of the run (no filter, no `tail`); the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The two guarded elements are the two the order declared (C1, C2); none is grouped.

## C1. The hand-written test, key absence (`lib/review_measures.py:201`, `_hand_written_only`)

- **Axis:** a session whose latest record carries no `sessionCost` key at all is hand-written, and a PR left out only for that reason counts under `handWritten`, not in `count`.
- **Detector:** `test_a_pr_whose_only_session_has_no_sessionCost_key_reads_hand_written` (case i, `-k only_session`).
- **Neutralization:** `all("sessionCost" not in r for r in unmeasured)` became `all(False for r in unmeasured)`, so no record ever reads hand-written.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_pr_whose_only_session_has_no_sessionCost_key_reads_hand_written ____

    def test_a_pr_whose_only_session_has_no_sessionCost_key_reads_hand_written():
        # axis: a session whose latest record carries no sessionCost key at all counts under handWritten, never in count
        want = {"count": 0, "why": RM.LEFT_OUT_WHY, "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}}
>       assert left_out(_rec(1, sc=None)) == want
E       AssertionError: assert {'count': 1, ...nd-written)'}} == {'count': 0, ...nd-written)'}}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'handWritten': {'count': 0, 'why': 'cost not measured (hand-written)'}} != {'handWritten': {'count': 1, 'why': 'cost not measured (hand-written)'}}
E         {'count': 1} != {'count': 0}
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py:32: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py::test_a_pr_whose_only_session_has_no_sessionCost_key_reads_hand_written
1 failed, 6 deselected in 0.33s
```

**Restore:** the inverse edit put `"sessionCost" not in r` back.
**Restore receipt** (the restored line, from a search of the file): `201:    return bool(unmeasured) and all("sessionCost" not in r for r in unmeasured)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 6 deselected in 0.27s
```

## C2. The every-unmeasured-session quantifier (`lib/review_measures.py:201`, `_hand_written_only`)

- **Axis:** a PR is hand-written only when every one of its unmeasured in-window sessions is; one incomplete session beside a hand-written one keeps the PR in `count`.
- **Detector:** `test_an_incomplete_session_beside_a_hand_written_one_is_incomplete` (case iv, `-k beside_a_hand_written`).
- **Neutralization:** `all("sessionCost" not in r for r in unmeasured)` became `any("sessionCost" not in r for r in unmeasured)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_an_incomplete_session_beside_a_hand_written_one_is_incomplete ______

    def test_an_incomplete_session_beside_a_hand_written_one_is_incomplete():
        # axis: every unmeasured session must be hand-written; one incomplete session makes the PR incomplete
        bad = _sc(100, 1.5, runs=2, without=1)
        got = left_out(_rec(1, "s1", sc=bad), _rec(1, "s2", at=LATER, sc=None))
>       assert got["count"] == 1 and got["handWritten"]["count"] == 0
E       assert (0 == 1)

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py::test_an_incomplete_session_beside_a_hand_written_one_is_incomplete
1 failed, 6 deselected in 0.29s
```

**Restore:** the inverse edit put `all(` back.
**Restore receipt** (the restored line, from a search of the file): `201:    return bool(unmeasured) and all("sessionCost" not in r for r in unmeasured)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 6 deselected in 0.33s
```

## Not proven (outside the declared set)

The `bool(unmeasured)` guard (a PR left out with no unmeasured session cannot occur through `compute`, since `_pr_cost` is None only when a session is unmeasured), so no test can tell `bool(unmeasured) and` from its removal.
