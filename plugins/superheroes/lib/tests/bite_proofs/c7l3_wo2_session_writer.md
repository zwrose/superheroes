# C7 L3 WO-2 bite-proof — the session writer

**Provenance:** claude / sonnet-5.5 (implementer). Every neutralization was a targeted edit to
`plugins/superheroes/lib/review_record_session.py`, undone by the inverse edit; after the last restore the file was
byte-identical (`diff`) to a copy taken before the first neutralization. Test runs used
`<venv>/bin/python -B <wrapper> <test file> -q -n auto -p no:cacheprovider -k <selector>`, where the wrapper only
points `HOME` at a directory whose `.gitconfig` does not sign commits and then calls `pytest.main(argv)` (this
sandbox's commit-signing service is unreachable, which breaks the tests that build a throwaway repository; the
detectors below build none).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_status_reviewers`, the refusal when no round recorded a seat status | a session holding neither a journaled seat nor a seat status holds nothing that says a reviewer ran | `test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused` |
| BP-2 | `_decided_by`, the ruling-newer-than-raise check | a ruling older than the finding's latest raise decides nothing about it | `test_edge_5_a_ruling_older_than_the_findings_latest_raise_is_not_recovered` |
| BP-3 | `_latest_ruling`, the merged-member lookup | a ruling logged against a finding merged into the representative settles the representative | `test_an_attributed_ruling_logged_against_a_merged_member_settles_the_representative` |

---

## BP-1 — the hand-submit refusal

- **axis:** a hand-submit session with no seat status in any round holds nothing that says a reviewer ran

**neutralization** (`_status_reviewers`): the line

```python
        raise Refusal(UNSUPPORTED, "the session recorded no seat result or seat status")
```

was replaced by

```python
        return []
```

**command:** `-k test_edge_1` over `plugins/superheroes/lib/tests/test_review_record_session_c7l3.py`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

FFFF                                                                     [100%]
=================================== FAILURES ===================================
__ test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds2] ___
[gw2] linux -- Python 3.12.3 /tmp/claude-0/-home-user-superheroes/cf9d321f-fab4-5831-a373-bfa1b7d64f87/scratchpad/venv312/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/popen-gw2/test_edge_1_a_hand_submit_sess0')
rounds = {'1': {'seatStatus': 'run'}}

    @pytest.mark.parametrize("rounds", [{"1": {}}, {"1": {"seatStatus": {}}}, {"1": {"seatStatus": "run"}}, {}])
    def test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused(tmp_path, rounds):
        session = Session(tmp_path, rounds=rounds).save()
        # bites on: a session that holds neither a journaled seat nor a seat status written as a record with no reviewers
>       with pytest.raises(rs.Refusal) as err:
E       Failed: DID NOT RAISE Refusal

/home/user/wt-1869-wo2/plugins/superheroes/lib/tests/test_review_record_session_c7l3.py:138: Failed
__ test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds0] ___
[gw0] linux -- Python 3.12.3 /tmp/claude-0/-home-user-superheroes/cf9d321f-fab4-5831-a373-bfa1b7d64f87/scratchpad/venv312/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/popen-gw0/test_edge_1_a_hand_submit_sess0')
rounds = {'1': {}}

    @pytest.mark.parametrize("rounds", [{"1": {}}, {"1": {"seatStatus": {}}}, {"1": {"seatStatus": "run"}}, {}])
    def test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused(tmp_path, rounds):
        session = Session(tmp_path, rounds=rounds).save()
        # bites on: a session that holds neither a journaled seat nor a seat status written as a record with no reviewers
>       with pytest.raises(rs.Refusal) as err:
E       Failed: DID NOT RAISE Refusal

/home/user/wt-1869-wo2/plugins/superheroes/lib/tests/test_review_record_session_c7l3.py:138: Failed
__ test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds3] ___
[gw3] linux -- Python 3.12.3 /tmp/claude-0/-home-user-superheroes/cf9d321f-fab4-5831-a373-bfa1b7d64f87/scratchpad/venv312/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/popen-gw3/test_edge_1_a_hand_submit_sess0')
rounds = {}

    @pytest.mark.parametrize("rounds", [{"1": {}}, {"1": {"seatStatus": {}}}, {"1": {"seatStatus": "run"}}, {}])
    def test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused(tmp_path, rounds):
        session = Session(tmp_path, rounds=rounds).save()
        # bites on: a session that holds neither a journaled seat nor a seat status written as a record with no reviewers
>       with pytest.raises(rs.Refusal) as err:
E       Failed: DID NOT RAISE Refusal

/home/user/wt-1869-wo2/plugins/superheroes/lib/tests/test_review_record_session_c7l3.py:138: Failed
__ test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds1] ___
[gw1] linux -- Python 3.12.3 /tmp/claude-0/-home-user-superheroes/cf9d321f-fab4-5831-a373-bfa1b7d64f87/scratchpad/venv312/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/popen-gw1/test_edge_1_a_hand_submit_sess0')
rounds = {'1': {'seatStatus': {}}}

    @pytest.mark.parametrize("rounds", [{"1": {}}, {"1": {"seatStatus": {}}}, {"1": {"seatStatus": "run"}}, {}])
    def test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused(tmp_path, rounds):
        session = Session(tmp_path, rounds=rounds).save()
        # bites on: a session that holds neither a journaled seat nor a seat status written as a record with no reviewers
>       with pytest.raises(rs.Refusal) as err:
E       Failed: DID NOT RAISE Refusal

/home/user/wt-1869-wo2/plugins/superheroes/lib/tests/test_review_record_session_c7l3.py:138: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c7l3.py::test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds2]
FAILED plugins/superheroes/lib/tests/test_review_record_session_c7l3.py::test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds0]
FAILED plugins/superheroes/lib/tests/test_review_record_session_c7l3.py::test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds3]
FAILED plugins/superheroes/lib/tests/test_review_record_session_c7l3.py::test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused[rounds1]
4 failed in 2.85s
```

**restore** (inverse edit): `        return []` back to the `raise Refusal(UNSUPPORTED, ...)` line.

**restore receipt** (lines quoted back, `review_record_session.py:209-211`):
```python
    if not any(status.values()):
        raise Refusal(UNSUPPORTED, "the session recorded no seat result or seat status")
    out, ran_in = [], {}
```

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

....                                                                     [100%]
4 passed in 1.52s
```

---

## BP-2 — the ruling-newer-than-raise check

- **axis:** a ruling older than the finding's latest raise decides nothing about it

**neutralization** (`_decided_by`): the two lines

```python
    if isinstance(decided, dict) and _int(ruling.get("round")) and all(_int(r) for r in raised) \
            and ruling["round"] >= max(raised):
```

were replaced by the one line (the comparison dropped)

```python
    if isinstance(decided, dict) and _int(ruling.get("round")) and all(_int(r) for r in raised):
```

**command:** `-k test_edge_5` over `plugins/superheroes/lib/tests/test_review_record_session_c7l3.py`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
__ test_edge_5_a_ruling_older_than_the_findings_latest_raise_is_not_recovered __
[gw0] linux -- Python 3.12.3 /tmp/claude-0/-home-user-superheroes/cf9d321f-fab4-5831-a373-bfa1b7d64f87/scratchpad/venv312/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/popen-gw0/test_edge_5_a_ruling_older_tha0')

    def test_edge_5_a_ruling_older_than_the_findings_latest_raise_is_not_recovered(tmp_path):
        row = ledger_row(raisedRound=3, **OOS)
        older = Session(tmp_path, dispositionLedger=[row], rulingsLog=[_ruling(rnd=2)]).seat("code-reviewer").save()
        # bites on: a ruling given before the finding was raised again being cited as the decision on the re-raise
>       assert _found(older)["decidedBy"] is None
E       AssertionError: assert {'kind': 'canon', 'ref': 'canon-1'} is None

/home/user/wt-1869-wo2/plugins/superheroes/lib/tests/test_review_record_session_c7l3.py:207: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c7l3.py::test_edge_5_a_ruling_older_than_the_findings_latest_raise_is_not_recovered
1 failed in 1.57s
```

**restore** (inverse edit): the two-line condition put back.

**restore receipt** (lines quoted back, `review_record_session.py:308-311`):
```python
    # axis: a ruling older than the finding's latest raise decides nothing about it — see bite-proof record c7l3_wo2_session_writer
    if isinstance(decided, dict) and _int(ruling.get("round")) and all(_int(r) for r in raised) \
            and ruling["round"] >= max(raised):
        return decided
```

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.25s
```

---

## BP-3 — the merged-member ruling lookup

- **axis:** a ruling logged against a finding merged into the representative settles the representative too

**neutralization** (`_latest_ruling`): the line

```python
    keys = [sc.finding_identity_key(r) for r in _group(rep, by_key)] + [rep.get("id")]
```

was replaced by (the representative alone)

```python
    keys = [sc.finding_identity_key(rep)] + [rep.get("id")]
```

**command:** `-k test_an_attributed_ruling_logged_against_a_merged_member` over `plugins/superheroes/lib/tests/test_review_record_session_c7l3.py`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_attributed_ruling_logged_against_a_merged_member_settles_the_representative _
[gw0] linux -- Python 3.12.3 /tmp/claude-0/-home-user-superheroes/cf9d321f-fab4-5831-a373-bfa1b7d64f87/scratchpad/venv312/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/popen-gw0/test_an_attributed_ruling_logg0')

    def test_an_attributed_ruling_logged_against_a_merged_member_settles_the_representative(tmp_path):
        ledger = [ledger_row(MEMBER, id="m-1", disposition=None, mergedInto=KEY), ledger_row(KEY, id="rep-1", **OOS)]
        s = Session(tmp_path, dispositionLedger=ledger, rulingsLog=[_ruling(MEMBER)]).seat("code-reviewer")
        found = {f["findingKey"]: f for f in rs.account_from_session(s.save(), extras())["findings"]}
        # bites on: a ruling logged against a merged member ignored, leaving the merged finding with the owner
>       assert found[KEY]["outcome"] == "ruling"
E       AssertionError: assert 'left-for-owner' == 'ruling'
E         
E         - ruling
E         + left-for-owner

/home/user/wt-1869-wo2/plugins/superheroes/lib/tests/test_review_record_session_c7l3.py:246: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_c7l3.py::test_an_attributed_ruling_logged_against_a_merged_member_settles_the_representative
1 failed in 1.34s
```

**restore** (inverse edit): the `_group(rep, by_key)` comprehension put back.

**restore receipt** (line quoted back, `review_record_session.py:289`):
```python
    keys = [sc.finding_identity_key(r) for r in _group(rep, by_key)] + [rep.get("id")]
```

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.43s
```

After the third restore, `review_record_session.py` was `diff`-identical to the copy taken before BP-1.
