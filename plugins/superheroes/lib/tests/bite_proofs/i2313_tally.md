# Bite-proof record — the gardening tally credits a catch to the seat that raised it when the record shows that seat ran on the PR, and reads it unmeasured otherwise (#2313)

Detector file: `plugins/superheroes/lib/tests/test_review_learning.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one line of `plugins/superheroes/lib/review_learning.py` (`tally`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_review_learning.py -q -k "<one test's name fragment>"`. Each capture is the whole output of the run (no filter, no `tail`), and the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The three guarded elements are the three the order declared; none is grouped.

## 1. Crediting by raiser, never by lens (`lib/review_learning.py:570`, `tally`)

- **Axis:** a catch is credited to the seats its rows' `raisedBy` names, never the lens its `reviewer` names.
- **Detector:** `test_tally_credits_the_raising_seat_not_the_lens`.
- **Neutralization:** `got[0].update(_seats(raiser))` became `got[0].update(_seats(f.get("reviewer")))`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_tally_credits_the_raising_seat_not_the_lens _______________

    def test_tally_credits_the_raising_seat_not_the_lens():
        rec = _record(1, "a", D, [_row("code-reviewer"), _row("premortem-reviewer")],
                      [_finding("k", "Failure-Mode", raised_by="code-reviewer")])
        got = RL.tally([rec], [], D, until="2026-10-11")
>       assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 1}, "premortem-reviewer": {"reviews": 1, "caught": 0}}
E       AssertionError: assert {'code-review... 'caught': 1}} == {'code-review... 'caught': 0}}
E         
E         Differing items:
E         {'premortem-reviewer': {'reviews': 1, 'caught': 1}} != {'premortem-reviewer': {'reviews': 1, 'caught': 0}}
E         {'code-reviewer': {'reviews': 1, 'caught': 0}} != {'code-reviewer': {'reviews': 1, 'caught': 1}}
E         Use -v to get more diff

/home/user/wt-2313/plugins/superheroes/lib/tests/test_review_learning.py:437: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_credits_the_raising_seat_not_the_lens
1 failed, 217 deselected in 2.44s
```

**Restore:** the inverse edit put `_seats(raiser)` back.
**Restore receipt** (the restored line, quoted by `grep -n "got\[0\].update"`): `570:                got[0].update(_seats(raiser))`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 217 deselected in 2.82s
```

## 2. A raiser seat the record does not show running reads unmeasured (`lib/review_learning.py:584`, `tally`)

- **Axis:** a raiser seat the latest record does not show running (no row, or a `not-run` row; for example a seat from an earlier review session of the same PR) is never credited and never counted as unattributed; its `caught` reads `unmeasured` and the catch counts in `raiserRunNotShown`.
- **Detectors:** `test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited` (both parametrized cases) and `test_tally_a_catch_carried_from_an_earlier_session_leaves_its_raiser_unmeasured`, selected together.
- **Neutralization:** `not_shown = raisers - ran_on_pr` became `not_shown = set()`, so a raiser seat the record does not show running is left out of the tally altogether.

**Raw red** (exit 1):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
____ test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited[rows0] _____

rows = [{'name': 'code-reviewer', 'ran': 'engine-record'}]

    @pytest.mark.parametrize("rows", [[_row("code-reviewer")], [_row("code-reviewer"), _row("premortem-reviewer", "not-run")]])
    def test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited(rows):
        rec = _record(1, "a", D, rows, [_finding("k", "Failure-Mode", raised_by="premortem-reviewer")])
        got = RL.tally([rec], [], D, until="2026-10-11")
>       assert got["seats"]["premortem-reviewer"]["caught"] == RL.UNMEASURED
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'premortem-reviewer'

/home/user/wt-2313/plugins/superheroes/lib/tests/test_review_learning.py:459: KeyError
____ test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited[rows1] _____

rows = [{'name': 'code-reviewer', 'ran': 'engine-record'}, {'name': 'premortem-reviewer', 'ran': 'not-run'}]

    @pytest.mark.parametrize("rows", [[_row("code-reviewer")], [_row("code-reviewer"), _row("premortem-reviewer", "not-run")]])
    def test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited(rows):
        rec = _record(1, "a", D, rows, [_finding("k", "Failure-Mode", raised_by="premortem-reviewer")])
        got = RL.tally([rec], [], D, until="2026-10-11")
>       assert got["seats"]["premortem-reviewer"]["caught"] == RL.UNMEASURED
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'premortem-reviewer'

/home/user/wt-2313/plugins/superheroes/lib/tests/test_review_learning.py:459: KeyError
_ test_tally_a_catch_carried_from_an_earlier_session_leaves_its_raiser_unmeasured _

    def test_tally_a_catch_carried_from_an_earlier_session_leaves_its_raiser_unmeasured():
        later = _record(1, "b", D, [_row("code-reviewer")], [_finding("k", "Failure-Mode", raised_by="premortem-reviewer")])
        got = RL.tally([later], [], D, until="2026-10-11")
>       assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 0},
                                "premortem-reviewer": {"reviews": 0, "caught": RL.UNMEASURED}}
E       AssertionError: assert {'code-review... 'caught': 0}} == {'code-review...'unmeasured'}}
E         
E         Omitting 1 identical items, use -vv to show
E         Right contains 1 more item:
E         {'premortem-reviewer': {'caught': 'unmeasured', 'reviews': 0}}
E         Use -v to get more diff

/home/user/wt-2313/plugins/superheroes/lib/tests/test_review_learning.py:468: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited[rows0]
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_raiser_that_did_not_run_on_the_pr_is_not_credited[rows1]
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_catch_carried_from_an_earlier_session_leaves_its_raiser_unmeasured
3 failed, 216 deselected in 46.11s
```

**Restore:** the inverse edit put `raisers - ran_on_pr` back.
**Restore receipt** (the restored line, quoted by `grep -n "not_shown = "`): `584:            not_shown = raisers - ran_on_pr`

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed, 216 deselected in 2.35s
```

## 3. A raiser-less catch reads unmeasured (`lib/review_learning.py:573`, `tally`)

- **Axis:** a catch with no recorded raiser is credited to no seat, and every seat that ran on its PR reads `caught` as `unmeasured`; a seat that ran only on another, fully raised PR keeps its number.
- **Detector:** `test_tally_a_catch_with_no_raiser_reads_unmeasured_for_the_seats_that_ran_on_its_pr`.
- **Neutralization:** `if not named:` became `if False and not named:`, so a raiser-less catch falls through to the credit step and counts as unattributed.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_tally_a_catch_with_no_raiser_reads_unmeasured_for_the_seats_that_ran_on_its_pr _

    def test_tally_a_catch_with_no_raiser_reads_unmeasured_for_the_seats_that_ran_on_its_pr():
        unstamped = _record(1, "a", D, [_row("code-reviewer"), _row("premortem-reviewer"), _row("test-role", "not-run")],
                            [_unraised("k1", "Failure-Mode"), _finding("k2", "Code")])
        stamped = _record(2, "b", D, [_row("security-reviewer")], [_finding("k3", "Security")])
        got = RL.tally([unstamped, stamped], [], D, until="2026-10-11")
>       assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": RL.UNMEASURED},
                                "premortem-reviewer": {"reviews": 1, "caught": RL.UNMEASURED},
                                "security-reviewer": {"reviews": 1, "caught": 1}}
E       AssertionError: assert {'code-review... 'caught': 1}} == {'code-review... 'caught': 1}}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'code-reviewer': {'reviews': 1, 'caught': 1}} != {'code-reviewer': {'reviews': 1, 'caught': 'unmeasured'}}
E         {'premortem-reviewer': {'reviews': 1, 'caught': 0}} != {'premortem-reviewer': {'reviews': 1, 'caught': 'unmeasured'}}
E         Use -v to get more diff

/home/user/wt-2313/plugins/superheroes/lib/tests/test_review_learning.py:447: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_catch_with_no_raiser_reads_unmeasured_for_the_seats_that_ran_on_its_pr
1 failed, 217 deselected in 0.65s
```

**Restore:** the inverse edit put `if not named:` back.
**Restore receipt** (the restored line, quoted by `grep -n "if not named:"`): `573:            if not named:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 217 deselected in 0.54s
```

## Not proven (outside the declared set)

Tests in the file with no neutralization of their own: the `raiserNotRecorded` count (asserted in the three detectors above, but the count's own line was not neutralized) and the unmeasured tally's `raiserNotRecorded` of None.
