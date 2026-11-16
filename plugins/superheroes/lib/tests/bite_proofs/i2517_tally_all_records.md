# Bite-proof record — the gardening tally reads a seat's runs across every review record of a PR (#2517)

Detector file: `plugins/superheroes/lib/tests/test_review_learning.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one line of `plugins/superheroes/lib/review_learning.py` (`tally`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2517 -m pytest plugins/superheroes/lib/tests/test_review_learning.py -q -k "<the element's name fragments>"`. Each capture is the whole output of the run (no filter, no `tail`), and the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The three guarded elements are the three the order declared; none is grouped.

## A. The union of `ran_on_pr` across every record of the PR (`lib/review_learning.py:584`, `tally`)

- **Axis:** a catch is credited to its raiser seat when any record of the PR shows that seat ran, and a no-raiser catch blanks every seat that ran in any record of the PR; a seat's run in an earlier record is never dropped because only the latest record holds the catch.
- **Detectors:** `test_tally_a_carried_catch_credits_the_raiser_an_earlier_record_shows_running` (both input orders) and `test_tally_a_no_raiser_catch_blanks_seats_that_ran_in_an_earlier_record`, selected together.
- **Neutralization:** `for _, rec in group:` became `for _, rec in [(latest_day, latest)]:`, so `ran_on_pr` and `reviews` are built from the latest record's rows only.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_tally_a_carried_catch_credits_the_raiser_an_earlier_record_shows_running _

    def test_tally_a_carried_catch_credits_the_raiser_an_earlier_record_shows_running():
        earlier = _at(_record(1, "a", D, [_row("premortem-reviewer"), _row("code-reviewer")],
                              [_finding("k", "Failure-Mode", "left-for-owner", raised_by="premortem-reviewer")]), "2026-10-10T09:00:00Z")
        later = _at(_record(1, "b", D, [_row("code-reviewer")],
                            [_finding("k", "Failure-Mode", raised_by="premortem-reviewer")]), "2026-10-10T11:00:00Z")
        for order in ([earlier, later], [later, earlier]):
            got = RL.tally(order, [], D, until="2026-10-11")
>           assert got["seats"] == {"premortem-reviewer": {"reviews": 1, "caught": 1}, "code-reviewer": {"reviews": 1, "caught": 0}}
E           AssertionError: assert {'code-review...'unmeasured'}} == {'premortem-r... 'caught': 0}}
E             
E             Omitting 1 identical items, use -vv to show
E             Differing items:
E             {'premortem-reviewer': {'reviews': 0, 'caught': 'unmeasured'}} != {'premortem-reviewer': {'reviews': 1, 'caught': 1}}
E             Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:498: AssertionError
___ test_tally_a_no_raiser_catch_blanks_seats_that_ran_in_an_earlier_record ____

    def test_tally_a_no_raiser_catch_blanks_seats_that_ran_in_an_earlier_record():
        earlier = _at(_record(1, "a", D, [_row("security-reviewer")], []), "2026-10-10T09:00:00Z")
        later = _at(_record(1, "b", D, [_row("code-reviewer")], [_unraised("k", "Code")]), "2026-10-10T11:00:00Z")
        got = RL.tally([earlier, later], [], D, until="2026-10-11")
>       assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": RL.UNMEASURED},
                                "security-reviewer": {"reviews": 1, "caught": RL.UNMEASURED}}
E       AssertionError: assert {'code-review...'unmeasured'}} == {'code-review...'unmeasured'}}
E         
E         Omitting 1 identical items, use -vv to show
E         Right contains 1 more item:
E         {'security-reviewer': {'caught': 'unmeasured', 'reviews': 1}}
E         Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:571: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_carried_catch_credits_the_raiser_an_earlier_record_shows_running
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_no_raiser_catch_blanks_seats_that_ran_in_an_earlier_record
2 failed, 227 deselected in 0.46s
```

**Restore:** the inverse edit put `for _, rec in group:` back.
**Restore receipt** (the restored line, quoted by `grep -n "for _, rec in group:"`): `584:        for _, rec in group:`

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed, 227 deselected in 0.39s
```

## B. The tie rule at the latest `writtenAt` (`lib/review_learning.py:572`, `tally`)

- **Axis:** two or more records of a PR inside the range that share the greatest `writtenAt` make the latest ambiguous: each record beyond the first reads malformed and the tally reads `incomplete-evidence`, so a retried or duplicated record is never a second catch and input order never picks the latest.
- **Detector:** `test_tally_two_records_at_the_latest_time_read_incomplete`.
- **Neutralization:** `if len(tied) > 1:` became `if False and len(tied) > 1:`, so the first record at the latest time wins and the tie goes unnoticed.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_tally_two_records_at_the_latest_time_read_incomplete ___________

    def test_tally_two_records_at_the_latest_time_read_incomplete():
        rows = [_row("code-reviewer")]
        one = _record(1, "a", D, rows, [_finding("k", "Code")])
        two = _record(1, "b", D, rows, [_finding("k", "Code")])
        got = RL.tally([one, two], [], D, until="2026-10-11")
>       assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
E       AssertionError: assert (True, None, ...'caught': 1}}) == (False, 'inco...evidence', {})
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:529: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_two_records_at_the_latest_time_read_incomplete
1 failed, 228 deselected in 0.45s
```

**Restore:** the inverse edit put `if len(tied) > 1:` back.
**Restore receipt** (the restored line, quoted by `grep -n "if len(tied) > 1:"`): `572:        if len(tied) > 1:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 228 deselected in 0.39s
```

## C. The every-record check (`lib/review_learning.py:577`, `tally`)

- **Axis:** every record of a PR inside the range with a single latest record is checked, an earlier one included and whatever its own date (here, before the adoption day); a damaged earlier record counts malformed and the tally reads `incomplete-evidence`.
- **Detector:** `test_tally_a_damaged_earlier_record_reads_incomplete` (all four parametrized damages: `ok: False`, `unreadFiles`, empty `reviewers`, a finding row `{}`).
- **Neutralization:** `damaged = [p for p in group if _record_damaged(p[1])]` became `damaged = [p for p in [(latest_day, latest)] if _record_damaged(p[1])]`, so only the latest record is checked.

**Raw red** (exit 1):

```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
________ test_tally_a_damaged_earlier_record_reads_incomplete[damage0] _________

damage = {'ok': False}

    @pytest.mark.parametrize("damage", [{"ok": False}, {"unreadFiles": ["x"]}, {"reviewers": []}, {"findings": [{}]}])
    def test_tally_a_damaged_earlier_record_reads_incomplete(damage):
        rows = [_row("code-reviewer")]
        earlier = dict(_record(1, "a", "2026-10-09", rows, [_finding("k0", "Code")]), **damage)  # dated before the adoption day
        latest = _record(1, "b", D, rows, [_finding("k", "Code")])
        for order in ([earlier, latest], [latest, earlier]):
            got = RL.tally(order, [], D, until="2026-10-11")
>           assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
E           AssertionError: assert (True, None, ...'caught': 1}}) == (False, 'inco...evidence', {})
E             
E             At index 0 diff: True != False
E             Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:545: AssertionError
________ test_tally_a_damaged_earlier_record_reads_incomplete[damage1] _________

damage = {'unreadFiles': ['x']}

    @pytest.mark.parametrize("damage", [{"ok": False}, {"unreadFiles": ["x"]}, {"reviewers": []}, {"findings": [{}]}])
    def test_tally_a_damaged_earlier_record_reads_incomplete(damage):
        rows = [_row("code-reviewer")]
        earlier = dict(_record(1, "a", "2026-10-09", rows, [_finding("k0", "Code")]), **damage)  # dated before the adoption day
        latest = _record(1, "b", D, rows, [_finding("k", "Code")])
        for order in ([earlier, latest], [latest, earlier]):
            got = RL.tally(order, [], D, until="2026-10-11")
>           assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
E           AssertionError: assert (True, None, ...'caught': 1}}) == (False, 'inco...evidence', {})
E             
E             At index 0 diff: True != False
E             Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:545: AssertionError
________ test_tally_a_damaged_earlier_record_reads_incomplete[damage2] _________

damage = {'reviewers': []}

    @pytest.mark.parametrize("damage", [{"ok": False}, {"unreadFiles": ["x"]}, {"reviewers": []}, {"findings": [{}]}])
    def test_tally_a_damaged_earlier_record_reads_incomplete(damage):
        rows = [_row("code-reviewer")]
        earlier = dict(_record(1, "a", "2026-10-09", rows, [_finding("k0", "Code")]), **damage)  # dated before the adoption day
        latest = _record(1, "b", D, rows, [_finding("k", "Code")])
        for order in ([earlier, latest], [latest, earlier]):
            got = RL.tally(order, [], D, until="2026-10-11")
>           assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
E           AssertionError: assert (True, None, ...'caught': 1}}) == (False, 'inco...evidence', {})
E             
E             At index 0 diff: True != False
E             Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:545: AssertionError
________ test_tally_a_damaged_earlier_record_reads_incomplete[damage3] _________

damage = {'findings': [{}]}

    @pytest.mark.parametrize("damage", [{"ok": False}, {"unreadFiles": ["x"]}, {"reviewers": []}, {"findings": [{}]}])
    def test_tally_a_damaged_earlier_record_reads_incomplete(damage):
        rows = [_row("code-reviewer")]
        earlier = dict(_record(1, "a", "2026-10-09", rows, [_finding("k0", "Code")]), **damage)  # dated before the adoption day
        latest = _record(1, "b", D, rows, [_finding("k", "Code")])
        for order in ([earlier, latest], [latest, earlier]):
            got = RL.tally(order, [], D, until="2026-10-11")
>           assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
E           AssertionError: assert (True, None, ...'caught': 1}}) == (False, 'inco...evidence', {})
E             
E             At index 0 diff: True != False
E             Use -v to get more diff

/home/user/wt-2517/plugins/superheroes/lib/tests/test_review_learning.py:545: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_damaged_earlier_record_reads_incomplete[damage0]
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_damaged_earlier_record_reads_incomplete[damage1]
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_damaged_earlier_record_reads_incomplete[damage2]
FAILED plugins/superheroes/lib/tests/test_review_learning.py::test_tally_a_damaged_earlier_record_reads_incomplete[damage3]
4 failed, 225 deselected in 0.54s
```

**Restore:** the inverse edit put `for p in group` back.
**Restore receipt** (the restored line, quoted by `grep -n "damaged = \[p for p in group"`): `577:        damaged = [p for p in group if _record_damaged(p[1])]`

**Raw green** (exit 0):

```
....                                                                     [100%]
4 passed, 225 deselected in 0.44s
```

## Not proven (outside the declared set)

Tests in the file with no neutralization of their own: the window placement of an out-of-range PR (`test_tally_an_out_of_range_pr_leaves_every_record_out_unread`), the latest record being the greatest `writtenAt` rather than the last in input (asserted in both input orders by the detectors above and by `test_tally_only_the_latest_records_catches_count`), and that catches come from the latest record only (`test_tally_only_the_latest_records_catches_count`).
