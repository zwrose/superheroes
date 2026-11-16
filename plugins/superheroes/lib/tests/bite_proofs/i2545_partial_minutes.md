# Bite-proof record — the gardening pass reads minutes from a session whose only shortfall is partial runs (#2545)

Detector file: `plugins/superheroes/lib/tests/test_partial_minutes_2545.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/review_measures.py`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2545 -m pytest '<exact node id>' -q`, one test node each (G5 ran two nodes in one call), output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The five guarded elements are the five the order declared (G1-G5); none is grouped. Each target occurred exactly once in the edit's `old_string` (the edit tool refuses a non-unique match). The `file:line` numbers are those of the restored file.

Detectors: T1 (G1, G3), T2 (G2; also run for G5), T4 (G4; also run for G5). T3 (a window of complete sessions reads as before) carries a `# bite-proof:` line and is not one of the declared elements' detectors.

## G1. `_whole`, minutes arm: no run lacks a figure (`lib/review_measures.py:177`)

- **Guarded element:** `review_measures.py:177`, the `sc["runsWithoutFigure"] == 0` arm of `_whole` (the minutes arm), read by the per-PR cost at line 213 and by the seat loop at lines 450 and 464.
- **Axis:** a session whose only shortfall is partial runs gives its minutes.
- **Detector:** `test_partial_minutes_2545.py::test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only`.
- **Neutralization:** `(sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)` became `(sc["complete"] if k == "tokens" else sc["complete"])`, the old rule for minutes.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only _

    def test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only():
        # axis: a PR whose only shortfall is partial runs counts in the minutes figures and stays out of the tokens figures, for the PR cost and the seat cost
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
        partial = _psc(40, 2.5, by_seat={"code-reviewer": _by(40, 2.5)})
        row = RM.compute(_full(records=[_rec(1), _rec(2, rows=_CODE, sc=partial)], ciRuns=_ci(1, 2)), FROM, UNTIL)
        cost = row["measures"]["reviewerCostPerPr"]
>       assert cost["minutes"]["total"] == 4.0 and cost["minutes"]["median"] == 2.0
E       assert (1.5 == 4.0)

/home/user/wt-2545/plugins/superheroes/lib/tests/test_partial_minutes_2545.py:39: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_minutes_2545.py::test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only
1 failed in 4.15s
```

**Restore:** the inverse edit put `sc["runsWithoutFigure"] == 0` back in place of the second `sc["complete"]`.
**Restore receipt** (the restored line, quoted from `review_measures.py:177`):

```
    return sc is not None and (sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.73s
```

## G2. `_whole`, minutes arm still requires no run lacking a figure (`lib/review_measures.py:177`)

- **Guarded element:** the same minutes arm, `review_measures.py:177`.
- **Axis:** a session with a run lacking a figure (a partial run beside it or not) still leaves its PR out of the minutes figures.
- **Detector:** `test_partial_minutes_2545.py::test_t2_a_session_with_a_run_lacking_a_figure_leaves_the_pr_out_of_both`.
- **Neutralization:** `(sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)` became `(sc["complete"] if k == "tokens" else True)`, any well-formed cost.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t2_a_session_with_a_run_lacking_a_figure_leaves_the_pr_out_of_both ____

    def test_t2_a_session_with_a_run_lacking_a_figure_leaves_the_pr_out_of_both():
        # axis: a session with a run lacking a figure, a partial run beside it or not, leaves its PR and its seats unmeasured for tokens and minutes
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
        beside = _psc(30, 3.0, runs=2, partial=1, without=1, by_seat={"code-reviewer": _by(30, 3.0, runs=2)})
        alone = _sc(30, 3.0, runs=2, without=1, by_seat={"premortem-reviewer": _by(30, 3.0, runs=2)})
        records = [_rec(1), _rec(2, rows=_CODE, sc=beside), _rec(3, rows=_PREM, sc=alone)]
        row = RM.compute(_full(records=records, ciRuns=_ci(1, 2, 3)), FROM, UNTIL)
        cost = row["measures"]["reviewerCostPerPr"]
>       assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
E       assert (100 == 100 and 7.5 == 1.5)

/home/user/wt-2545/plugins/superheroes/lib/tests/test_partial_minutes_2545.py:68: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_minutes_2545.py::test_t2_a_session_with_a_run_lacking_a_figure_leaves_the_pr_out_of_both
1 failed in 4.70s
```

**Restore:** the inverse edit put `sc["runsWithoutFigure"] == 0` back in place of `True`.
**Restore receipt** (the restored line, quoted from `review_measures.py:177`):

```
    return sc is not None and (sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.19s
```

## G3. `_whole`, tokens arm: complete (`lib/review_measures.py:177`)

- **Guarded element:** the `sc["complete"]` tokens arm, `review_measures.py:177`.
- **Axis:** a session whose only shortfall is partial runs does not give its tokens.
- **Detector:** `test_partial_minutes_2545.py::test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only` (red on the tokens total).
- **Neutralization:** `(sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)` became `(sc["runsWithoutFigure"] == 0 if k == "tokens" else sc["runsWithoutFigure"] == 0)`, the minutes rule for tokens.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only _

    def test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only():
        # axis: a PR whose only shortfall is partial runs counts in the minutes figures and stays out of the tokens figures, for the PR cost and the seat cost
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
        partial = _psc(40, 2.5, by_seat={"code-reviewer": _by(40, 2.5)})
        row = RM.compute(_full(records=[_rec(1), _rec(2, rows=_CODE, sc=partial)], ciRuns=_ci(1, 2)), FROM, UNTIL)
        cost = row["measures"]["reviewerCostPerPr"]
        assert cost["minutes"]["total"] == 4.0 and cost["minutes"]["median"] == 2.0
>       assert cost["tokens"]["total"] == 100 and cost["tokens"]["median"] == 100
E       assert (140 == 100)

/home/user/wt-2545/plugins/superheroes/lib/tests/test_partial_minutes_2545.py:40: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_minutes_2545.py::test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only
1 failed in 4.13s
```

**Restore:** the inverse edit put `sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0` back.
**Restore receipt** (the restored line, quoted from `review_measures.py:177`):

```
    return sc is not None and (sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.40s
```

## G4. The seat loop reads each measure through its own sets (`lib/review_measures.py:450`)

- **Guarded element:** `review_measures.py:450`, `if not _whole(sc, k):` in the per-seat loop (with the per-measure `blanked`, `costed`, `part_blank` and `other_blank` sets it fills).
- **Axis:** a seat's minutes are blanked by a session not whole for minutes, and its tokens by a session not whole for tokens, never one measure's blanking for the other.
- **Detector:** `test_partial_minutes_2545.py::test_t4_census_every_seat_reads_tokens_and_minutes_through_their_own_rule`.
- **Neutralization:** `if not _whole(sc, k):` became `if not _whole(sc, "tokens"):`, so the minutes iteration blanks by the tokens reading.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_t4_census_every_seat_reads_tokens_and_minutes_through_their_own_rule ___

    def test_t4_census_every_seat_reads_tokens_and_minutes_through_their_own_rule():
        # axis: each seat reads its tokens through the complete rule and its minutes through the no-run-lacking-a-figure rule, never one measure's blanking for the other
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
        complete = _sc(120, 2.0, by_seat={"security-reviewer": _by(100, 1.5), "code-reviewer": _by(20, 0.5)})
        partial = _psc(50, 3.0, by_seat={"premortem-reviewer": _by(40, 2.5), "security-reviewer": _by(10, 0.5)})
        lacking = _sc(7, 0.9, runs=2, without=1, by_seat={"code-reviewer": _by(7, 0.9, runs=2)})
        records = [
            _rec(1, rows=[_row("security-reviewer (round 1)"), _row("code-reviewer (round 1)")], sc=complete),
            _rec(2, rows=[_row("premortem-reviewer (round 1)"), _row("security-reviewer (round 1)")], sc=partial),
            _rec(3, rows=_CODE, sc=lacking)]
        row = RM.compute(_full(records=records, ciRuns=_ci(1, 2, 3)), FROM, UNTIL)
        seats, why = row["measures"]["seats"], _why(row)
        assert set(seats) == {"security-reviewer", "code-reviewer", "premortem-reviewer"}
        expected = {  # seat: (tokens, tokens reason, minutes, minutes reason)
            "security-reviewer": (U, "cost-partial", 2.0, None),  # the partial session blanks its tokens only
            "premortem-reviewer": (U, "cost-partial", 2.5, None),  # named only by the partial session
            "code-reviewer": (U, "cost-not-recorded", U, "cost-not-recorded"),  # the lacking session blanks both
        }
        for seat, (tokens, tokens_why, minutes, minutes_why) in expected.items():
            assert seats[seat]["tokens"] == tokens, seat
>           assert seats[seat]["minutes"] == minutes, seat
E           AssertionError: security-reviewer
E           assert 'unmeasured' == 2.0

/home/user/wt-2545/plugins/superheroes/lib/tests/test_partial_minutes_2545.py:125: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_minutes_2545.py::test_t4_census_every_seat_reads_tokens_and_minutes_through_their_own_rule
1 failed in 4.43s
```

**Restore:** the inverse edit put `k` back in place of `"tokens"`.
**Restore receipt** (the restored line, quoted from `review_measures.py:450`):

```
                    if not _whole(sc, k):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.26s
```

## G5. The seat `bySeat` sum adds a figure only when whole for its measure (`lib/review_measures.py:464`)

- **Guarded element:** `review_measures.py:464`, `costs[s][k] += by[k] if _whole(sc, k) else 0`.
- **Axis:** a seat's summed cost adds a session's figure for `k` only when the session is whole for `k`.
- **Detectors tried:** `test_partial_minutes_2545.py::test_t4_census_every_seat_reads_tokens_and_minutes_through_their_own_rule` and `::test_t2_a_session_with_a_run_lacking_a_figure_leaves_the_pr_out_of_both`, in one call. T4 has a seat named by a partial-only session and a seat named by a session with a run lacking a figure; T2 has a seat named by each of a session with a run lacking a figure beside a partial run and one alone.
- **Neutralization:** `costs[s][k] += by[k] if _whole(sc, k) else 0` became `costs[s][k] += by[k]`, adding every session's figure.

**Raw result under the neutralization** (exit 0, no red; both nodes passed):

```
..                                                                       [100%]
2 passed in 3.66s
```

**Disclosure: Unprovable as placed.**

- **What makes it unprovable:** the sum at line 464 is read only through `known` (line 470), which requires `s in costed[k] and s not in blanked[k]`. A session that is not whole for `k` puts every seat its `bySeat` names into `blanked[k]` (line 451), through the same `review_learning._seats(name)` mapping the sum loop at line 461 uses. So every seat whose total received a figure from a session not whole for `k` is already blanked for `k` and reads unmeasured, whatever the sum holds; no fixture can make the unconditional sum change a figure the row shows. The guard at line 464 and the blanking at line 451 give the same answer for the same input.
- **What would make it provable:** drop the sum's own guard and rely on the blanking (the sum then adds every session's figure and the blanking decides what shows), or sum into `costs` only from the sessions the blanking leaves whole, so one rule sits in one place; either removes the redundancy, and the order's specified shape was kept instead.
- **Plain statement:** the guard at line 464 has no neutralization any test can tell apart; its protection is unverified. The seat figures it feeds are still guarded by G4, whose red shows the per-measure blanking.

**Restore:** the inverse edit put `if _whole(sc, k) else 0` back.
**Restore receipt** (the restored line, quoted from `review_measures.py:464`):

```
                            costs[s][k] += by[k] if _whole(sc, k) else 0  # a session not whole for `k` still names its seats
```

**Raw green after restore** (exit 0; the same two nodes):

```
..                                                                       [100%]
2 passed in 3.97s
```

## After every restore

The three files the order names, run after the last restore (`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2545 -m pytest plugins/superheroes/lib/tests/test_partial_minutes_2545.py plugins/superheroes/lib/tests/test_partial_cost_2514.py plugins/superheroes/lib/tests/test_review_measures.py -q`, exit 0):

```
........................................................................ [ 58%]
...................................................                      [100%]
123 passed in 8.88s
```

## Not proven (outside the declared set)

T3 (a window of complete sessions reads as before) has no neutralization of its own; it pins today's reading and is listed so nobody reads it as covered by this record. The per-measure `part_blank` branch for minutes (lines 452-453) is unreachable for a well-formed cost (a partial-only session is whole for minutes), kept so both measures read through one code path; it has no neutralization and no detector.
