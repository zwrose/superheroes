# Bite-proof record — the seating check counts catches by raising seat, and per-seat cost reads runs only (#2313, WO-B)

Detector file: `plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one line of `plugins/superheroes/lib/review_measures.py`, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py plugins/superheroes/lib/tests/test_review_measures.py -q -k "<one test's name fragment>"`, which selects exactly one test; the output is the last 40 lines of the run (`| tail -40`, which cut nothing: each capture is whole), and the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token, URL or personal data appears in any capture, so nothing else is redacted. The four guarded elements are the four the order declared; none is grouped.

## 1. Crediting by raising seat (`lib/review_measures.py:255`, `compute`)

- **Axis:** a finding counts for the seats its `raisedBy` names, never the lens its `reviewer` names.
- **Detector:** `test_a_finding_raised_by_the_code_seat_in_the_premortem_lens_counts_for_code_not_premortem`.
- **Neutralization:** `got[1].update(review_learning._seats(raiser))` became `got[1].update(review_learning._seats(f.get("reviewer")))`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_finding_raised_by_the_code_seat_in_the_premortem_lens_counts_for_code_not_premortem _

    def test_a_finding_raised_by_the_code_seat_in_the_premortem_lens_counts_for_code_not_premortem():
        rec = _rec(1, rows=[_row(CODE), _row(PRE)], findings=[_raised("k1", "code-reviewer", "Failure-Mode")],
                   sc=_sc(200, 3.0, runs=2, by_seat={"code-reviewer": _by(100, 1.5), "premortem-reviewer": _by(100, 1.5)}))
        seats = _seats(_compute(rec))
>       assert seats["code-reviewer"]["outcomes"] == _filled(fixed=1)
E       AssertionError: assert {'fixed': 0, ...wner': 0, ...} == {'fixed': 1, ...wner': 0, ...}
E         
E         Omitting 5 identical items, use -vv to show
E         Differing items:
E         {'fixed': 0} != {'fixed': 1}
E         Use -v to get more diff

/home/user/wt-2313-b/plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py:40: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py::test_a_finding_raised_by_the_code_seat_in_the_premortem_lens_counts_for_code_not_premortem
1 failed, 95 deselected in 0.60s
```

**Restore:** the inverse edit put `review_learning._seats(raiser)` back.
**Restore receipt** (the restored line, quoted from `review_measures.py:255`, by `grep -n`): `                    got[1].update(review_learning._seats(raiser))`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 95 deselected in 0.69s
```

## 2. Unmeasured outcomes for a raiser-less finding (`lib/review_measures.py:263`, `compute`)

- **Axis:** a PR with a counted finding that names no raiser leaves the outcomes of every seat that ran on it (in or out of the window) unmeasured, reason `raising-seat-not-recorded`; other seats keep their counts.
- **Detector:** `test_a_record_without_the_field_reads_unmeasured_for_the_seats_that_ran_on_its_pr_only`.
- **Neutralization:** `if lacking:` became `if False and lacking:`, so no seat is ever marked unread.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_record_without_the_field_reads_unmeasured_for_the_seats_that_ran_on_its_pr_only _

    def test_a_record_without_the_field_reads_unmeasured_for_the_seats_that_ran_on_its_pr_only():
        unstamped = {k: v for k, v in _raised("k1", "x", "Security").items() if k != "raisedBy"}
        # PR 1: security ran in the window, code ran in an earlier record of the same PR (outside it); no finding names its raiser
        old_code = _rec(1, "old", "2026-09-20T10:00:00Z", rows=[_row(CODE)], sc=None)
        pr1 = _rec(1, "a", rows=[_row(SEC)], findings=[unstamped, _raised("k2", "security-reviewer", "Security")],
                   sc=_sc(100, 1.5, by_seat={"security-reviewer": _by(100, 1.5)}))
        # PR 2: fully stamped; premortem ran only here
        pr2 = _rec(2, rows=[_row(PRE)], findings=[_raised("k3", "premortem-reviewer", "Failure-Mode")],
                   sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
        row = _compute(old_code, pr1, pr2)
        seats, why = _seats(row), _why(row)
        for seat in ("security-reviewer", "code-reviewer"):
>           assert seats[seat]["outcomes"] == U and why["seats.%s.outcomes" % seat] == NO_RAISER
E           AssertionError: assert ({'fixed': 1, 'shown-wrong': 0, 'craft': 0, 'left-for-owner': 0, ...} == 'unmeasured')

/home/user/wt-2313-b/plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py::test_a_record_without_the_field_reads_unmeasured_for_the_seats_that_ran_on_its_pr_only
1 failed, 95 deselected in 0.59s
```

**Restore:** the inverse edit put `if lacking:` back.
**Restore receipt** (the restored line, quoted from `review_measures.py:263`, by `grep -n "if lacking:"`): `            if lacking:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 95 deselected in 0.66s
```

## 3. The S6 v0 cost blank (`lib/review_measures.py:275`, `compute`)

- **Axis:** a seat that ran in a session whose complete `sessionCost` does not name it reads unmeasured for tokens and minutes, even when another complete session names it.
- **Detector:** `test_a_complete_cost_that_leaves_out_a_seat_that_ran_makes_that_seats_cost_unmeasured`.
- **Neutralization:** `blanked |= ran_seats - named_seats` became `blanked |= set()` (comment kept).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_complete_cost_that_leaves_out_a_seat_that_ran_makes_that_seats_cost_unmeasured _

    def test_a_complete_cost_that_leaves_out_a_seat_that_ran_makes_that_seats_cost_unmeasured():
        # S6 v0: session a costs premortem; session b ran premortem too, and its complete cost names only the code seat
        a = _rec(1, "a", rows=[_row(PRE)], sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
        b = _rec(1, "b", rows=[_row(CODE), _row(PRE)], sc=_sc(100, 1.5, by_seat={"code-reviewer": _by(100, 1.5)}))
        row = _compute(a, b)
        seats = _seats(row)
>       assert seats["premortem-reviewer"]["tokens"] == U and seats["premortem-reviewer"]["minutes"] == U
E       AssertionError: assert (7 == 'unmeasured')

/home/user/wt-2313-b/plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py:118: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py::test_a_complete_cost_that_leaves_out_a_seat_that_ran_makes_that_seats_cost_unmeasured
1 failed, 95 deselected in 0.57s
```

**Restore:** the inverse edit put `blanked |= ran_seats - named_seats` back.
**Restore receipt** (the restored line, quoted from `review_measures.py:275`, by `grep -n`): `                    blanked |= ran_seats - named_seats  # a complete cost that leaves out a seat that ran does not cost it`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 95 deselected in 0.57s
```

## 4. Finding lenses never blank cost (`lib/review_measures.py`, the `if sc is None or not sc["complete"]:` branch of `compute`)

- **Axis:** the seats a session's findings name by lens are not blanked by a session with no complete cost; only the seats the session ran (or its `bySeat` names) are.
- **Detector:** `test_a_receiptless_review_with_a_premortem_lens_finding_does_not_blank_premortems_cost`.
- **Neutralization:** the deleted line was added back as the second line of that branch: `blanked |= {s for f in last["findings"] for s in review_learning._seats(f.get("reviewer"))}`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_receiptless_review_with_a_premortem_lens_finding_does_not_blank_premortems_cost _

    def test_a_receiptless_review_with_a_premortem_lens_finding_does_not_blank_premortems_cost():
        receiptless = _rec(1, rows=[_row(CODE)], findings=[_raised("k1", "code-reviewer", "Failure-Mode")], sc=None)
        costed = _rec(2, rows=[_row(PRE)], sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
        row = _compute(receiptless, costed)
        seats = _seats(row)
>       assert seats["premortem-reviewer"]["tokens"] == 7 and seats["premortem-reviewer"]["minutes"] == 0.2
E       AssertionError: assert ('unmeasured' == 7)

/home/user/wt-2313-b/plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_measures_raised_by_2313.py::test_a_receiptless_review_with_a_premortem_lens_finding_does_not_blank_premortems_cost
1 failed, 95 deselected in 0.60s
```

**Restore:** the inverse edit removed the added line.
**Restore receipt** (the restored branch, quoted from `review_measures.py:271-275` with `sed -n`; `grep -c 'f.get("reviewer")'` over the file prints `0`):

```
                if sc is None or not sc["complete"]:
                    blanked |= ran_seats | named_seats
                else:
                    costed |= named_seats
                    blanked |= ran_seats - named_seats  # a complete cost that leaves out a seat that ran does not cost it
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 95 deselected in 0.67s
```

## Not proven (outside the declared set)

Tests in the file with no neutralization of their own: the carried-finding test (a finding keeps its raising seat across sessions), the premortem-never-ran test, the incomplete-cost test (the seat that ran in an incomplete session) and the verifier-key figures in the S6 test.
