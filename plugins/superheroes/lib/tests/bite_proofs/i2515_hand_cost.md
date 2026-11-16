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

## U1 and U2. The partial-and-hand-written union (added by the union test)

Detector for both: `test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count` (`-k partial_and_hand_written`), in the same file, unedited between each red and its green. The two entries below are the two elements the order declared for this test (U1, U2); none is grouped. Same method as C1 and C2: a targeted edit of one line of `plugins/superheroes/lib/review_measures.py`, made and undone with the edit tool; whole captures, the `UV_NATIVE_TLS` warning line the only line left out; nothing redacted (no secret, token, URL or personal data appears).

### U1. The `- hand` subtraction in `count` (`lib/review_measures.py:416`, `compute`)

- **Axis:** a hand-written PR is counted under `handWritten` only, so `count` is the PRs left out less the hand-written ones.
- **Neutralization:** `"count": len(totals) - len(measured) - hand, "why": LEFT_OUT_WHY,` became `"count": len(totals) - len(measured), "why": LEFT_OUT_WHY,`.

**Raw red** (exit 1; red on `count`: 3 where 2 is expected):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count _

    def test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count():
        # axis: a PR holding a partial session is never hand-written (it counts under count and partial), a hand-only PR adds nothing to partial, and partial never exceeds count
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2515_hand_cost.md
        records = [
            _rec(1),                                                     # PR 1: one complete session, measured
            _rec(2, sc=_psc(100, 1.5)),                                  # PR 2: one partial session
            _rec(3, sc=None),                                            # PR 3: no sessionCost key, hand-written
            _rec(4, "s1", sc=_psc(100, 1.5)),                            # PR 4: a partial session ...
            _rec(4, "s2", at=LATER, sc=None),                            # ... and a later one with no sessionCost key
        ]
        want = {"count": 2, "why": RM.LEFT_OUT_WHY, "partial": 2,
                "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}}
        for k in ("tokens", "minutes"):
            got = left_out(*records, k=k)
>           assert got == want, k
E           AssertionError: tokens
E           assert {'count': 3, ...nd-written)'}} == {'count': 2, ...nd-written)'}}
E             
E             Omitting 3 identical items, use -vv to show
E             Differing items:
E             {'count': 3} != {'count': 2}
E             Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py::test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count
1 failed, 7 deselected in 0.34s
```

**Restore:** the inverse edit put ` - hand` back.
**Restore receipt** (the restored line, from a search of the file): `416:            out[k] = {"count": len(totals) - len(measured) - hand, "why": LEFT_OUT_WHY,`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 7 deselected in 4.14s
```

### U2. The partial-never-hand-written rule, through the quantifier (`lib/review_measures.py:221`, `_hand_written_only`)

- **Axis:** a PR holding a partial session beside a hand-written one is incomplete and partial, never hand-written (PR 4), so `partial` never exceeds `count`.
- **Neutralization:** `all("sessionCost" not in r for r in unmeasured)` became `any("sessionCost" not in r for r in unmeasured)`.
- **Where it went red:** on the whole-dict equality (`count` 1 for 2, `handWritten.count` 2 for 1), which comes before the explicit `partial <= count` line, so the run stops there and never reaches that line. The order expected the red on the `partial <= count` assertion; it was not reached. With the neutralization in, `partial` is 2 and `count` is 1, so that line would also fail if reached; that was not run.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count _

    def test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count():
        # axis: a PR holding a partial session is never hand-written (it counts under count and partial), a hand-only PR adds nothing to partial, and partial never exceeds count
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2515_hand_cost.md
        records = [
            _rec(1),                                                     # PR 1: one complete session, measured
            _rec(2, sc=_psc(100, 1.5)),                                  # PR 2: one partial session
            _rec(3, sc=None),                                            # PR 3: no sessionCost key, hand-written
            _rec(4, "s1", sc=_psc(100, 1.5)),                            # PR 4: a partial session ...
            _rec(4, "s2", at=LATER, sc=None),                            # ... and a later one with no sessionCost key
        ]
        want = {"count": 2, "why": RM.LEFT_OUT_WHY, "partial": 2,
                "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}}
        for k in ("tokens", "minutes"):
            got = left_out(*records, k=k)
>           assert got == want, k
E           AssertionError: tokens
E           assert {'count': 1, ...nd-written)'}} == {'count': 2, ...nd-written)'}}
E             
E             Omitting 2 identical items, use -vv to show
E             Differing items:
E             {'count': 1} != {'count': 2}
E             {'handWritten': {'count': 2, 'why': 'cost not measured (hand-written)'}} != {'handWritten': {'count': 1, 'why': 'cost not measured (hand-written)'}}
E             Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py::test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count
1 failed, 7 deselected in 0.34s
```

**Restore:** the inverse edit put `all(` back.
**Restore receipt** (the restored line, from a search of the file): `221:    return bool(unmeasured) and all("sessionCost" not in r for r in unmeasured)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 7 deselected in 0.38s
```

## P1 and P2. The per-measure reading of the counts (added by the partial-and-hand-written and tokens-only tests)

Same method as C1 to U2: a targeted edit of one line of `plugins/superheroes/lib/review_measures.py`, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`); whole captures, the `UV_NATIVE_TLS` warning line the only line left out; nothing redacted (no secret, token, URL or personal data appears). Each detector is unedited between its red and its green. The two elements are the two the order declared (P1, P2); none is grouped.

### P1. The not-hand-written filter on `partial` (`lib/review_measures.py:432`, `compute`)

- **Axis:** `partial` counts only the PRs left out under `count`, so a PR left out for a measure only by a hand-written session is never partial for it (it counts under `handWritten` alone). It bit on the `minutes` reading, where PR 4 is left out only by its hand-written session.
- **Detector:** `test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count` (`-k partial_and_hand_written`), red on its `minutes` expectation.
- **Neutralization:** `... for rs, t, h in zip(prs.values(), totals, hands) if t is None and not h),` became `... for rs, t, h in zip(prs.values(), totals, hands) if t is None),`.

**Raw red** (exit 1; red on `minutes`: `partial` 1 where 0 is expected):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count _

    def test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count():
        # axis: a PR holding a partial session is never hand-written (it counts under count and partial), a hand-only PR adds nothing to partial, and partial never exceeds count
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2515_hand_cost.md
        records = [
            _rec(1),                                                     # PR 1: one complete session, measured
            _rec(2, sc=_psc(100, 1.5)),                                  # PR 2: one partial session
            _rec(3, sc=None),                                            # PR 3: no sessionCost key, hand-written
            _rec(4, "s1", sc=_psc(100, 1.5)),                            # PR 4: a partial session ...
            _rec(4, "s2", at=LATER, sc=None),                            # ... and a later one with no sessionCost key
        ]
        # a partial session is whole for minutes: PR 2 is measured there, and PR 4 is left out of minutes only by its hand-written session
        want = {"tokens": {"count": 2, "why": RM.LEFT_OUT_WHY, "partial": 2,
                           "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}},
                "minutes": {"count": 0, "why": RM.LEFT_OUT_WHY, "partial": 0,
                            "handWritten": {"count": 2, "why": RM.HAND_WRITTEN_WHY}}}
        for k in ("tokens", "minutes"):
            got = left_out(*records, k=k)
>           assert got == want[k], k
E           AssertionError: minutes
E           assert {'count': 0, ...nd-written)'}} == {'count': 0, ...nd-written)'}}
E             
E             Omitting 3 identical items, use -vv to show
E             Differing items:
E             {'partial': 1} != {'partial': 0}
E             Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py:100: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py::test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count
1 failed, 8 deselected in 0.38s
```

**Restore:** the inverse edit put ` and not h` back.
**Restore receipt** (the restored line, from a search of the file): `432:                                     for rs, t, h in zip(prs.values(), totals, hands) if t is None and not h),`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 8 deselected in 0.34s
```

### P2. The per-measure reading (`lib/review_measures.py:186`, `_whole`)

- **Axis:** the counts are read per measure: tokens need a complete session, minutes need no run lacking a figure. A partial-only PR is left out of tokens and measured for minutes. It bit on the `minutes` count (2 where 1 is expected), so the partial session was no longer whole for minutes.
- **Detector:** `test_a_pr_left_out_for_tokens_only_counts_under_tokens_alone` (`-k tokens_only`).
- **Neutralization:** `return sc is not None and (sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)` became `return sc is not None and sc["complete"]`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_pr_left_out_for_tokens_only_counts_under_tokens_alone _________

    def test_a_pr_left_out_for_tokens_only_counts_under_tokens_alone():
        # axis: the counts are read per measure; a partial-only PR is left out of tokens and measured for minutes, a PR with a run lacking a figure is left out of both
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2515_hand_cost.md
        records = [
            _rec(1, sc=_psc(100, 1.5)),                       # PR 1: its only session is partial
            _rec(2, sc=_sc(100, 1.5, runs=2, without=1)),     # PR 2: its only session has a run lacking a figure
        ]
        tokens, minutes = left_out(*records, k="tokens"), left_out(*records, k="minutes")
        assert (tokens["count"], tokens["partial"], tokens["handWritten"]["count"]) == (2, 1, 0)
>       assert (minutes["count"], minutes["partial"], minutes["handWritten"]["count"]) == (1, 0, 0)
E       assert (2, 1, 0) == (1, 0, 0)
E         
E         At index 0 diff: 2 != 1
E         Use -v to get more diff

/home/user/superheroes-wt-2515/plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_hand_cost_2515.py::test_a_pr_left_out_for_tokens_only_counts_under_tokens_alone
1 failed, 8 deselected in 0.36s
```

**Restore:** the inverse edit put `(sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)` back.
**Restore receipt** (the restored line, from a search of the file): `186:    return sc is not None and (sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 8 deselected in 0.30s
```

## Not proven (outside the declared set)

The `bool(unmeasured)` guard (a PR left out with no unmeasured session cannot occur through `compute`, since `_pr_cost` is None only when a session is unmeasured), so no test can tell `bool(unmeasured) and` from its removal.
