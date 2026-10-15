# C7 L3 WO-2 bite-proof — the session writer

**Provenance:** claude / sonnet-5.5 (implementer). Every neutralization except BP-2's (refreshed in WO-11, see its
section) was a targeted edit to `plugins/superheroes/lib/review_record_session.py`, undone by the inverse edit; after the last restore the file was
byte-identical (`diff`) to a copy taken before the first neutralization. Test runs used
`<venv>/bin/python -B <wrapper> <test file> -q -n auto -p no:cacheprovider -k <selector>`, where the wrapper only
points `HOME` at a directory whose `.gitconfig` does not sign commits and then calls `pytest.main(argv)` (this
sandbox's commit-signing service is unreachable, which breaks the tests that build a throwaway repository; the
detectors below build none).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_status_reviewers`, the refusal when no round recorded a seat status | a session holding neither a journaled seat nor a seat status holds nothing that says a reviewer ran | `test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused` |
| BP-2 | `finding_outcomes.settle`, the citation-keeping branch on a `left-for-owner` result | a left-for-owner finding whose effective ruling cites a decision not yet on record keeps that citation, so the write-time re-check can settle it | `test_e7_unresolved_decided_by_stays_with_owner_with_reason_appended` |
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

## BP-2 — the citation-keeping branch of `settle`

- **axis:** a left-for-owner finding whose effective ruling cites a decision not yet on record keeps that citation, so the write-time re-check can settle it

**refreshed** in work order WO-11 (claude / sonnet-5.5, advisor ruling 6188233476). The earlier BP-2 named
`review_record_session._decided_by`'s ruling-newer-than-raise check and
`test_edge_5_a_ruling_older_than_the_findings_latest_raise_is_not_recovered`; both were deleted in review round 4
(commit `4ba2a1e5`). The behaviour now has one home: `finding_outcomes.settle` keeps a ruling's own `decidedBy` on a
`left-for-owner` result when the cited decision is not on record, and the session writer reads `decidedBy` only from the
settled ledger row. The neutralization below is a targeted edit to `plugins/superheroes/lib/finding_outcomes.py`,
undone by the inverse edit. The outputs below were redacted: any absolute interpreter or scratch path would read
`<scratch>`; none appeared in these captures, so none was replaced.

**neutralization** (`settle`, final return): the line

```python
    return {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": decided_by}
```

was replaced by (the citation dropped again)

```python
    return {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": None}
```

**command:** `-k test_e7_unresolved_decided_by_stays_with_owner_with_reason_appended` over `plugins/superheroes/lib/tests/test_finding_outcomes_c7.py`, run as `scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc-wo11 -m pytest -q -p no:cacheprovider <test file> -k <test name>`

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e7_unresolved_decided_by_stays_with_owner_with_reason_appended ______

    def test_e7_unresolved_decided_by_stays_with_owner_with_reason_appended():
        finding = {"consequence": "data lost", "consequenceKind": "real"}
        out = FO.settle(finding, ruling={"decidedBy": {"kind": "canon", "ref": OTHER_ID}},
                        sources=_sources(), open_reason=OPEN)
        assert out["outcome"] == "left-for-owner"
        assert out["reason"] == OPEN + "; the cited decision is not on record: the cited Canon entry is not on record"
>       assert out["decidedBy"] == {"kind": "canon", "ref": OTHER_ID}  # the citation stays, for the writer's write-time re-check
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert None == {'kind': 'canon', 'ref': '2026-01-02-abcd1234-2'}

plugins/superheroes/lib/tests/test_finding_outcomes_c7.py:329: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_e7_unresolved_decided_by_stays_with_owner_with_reason_appended
1 failed, 111 deselected in 0.32s
```

**restore** (inverse edit): `"decidedBy": None` back to `"decidedBy": decided_by` on that return.

**restore receipt** (line quoted back, `finding_outcomes.py:212`):
```python
    return {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": decided_by}
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 111 deselected in 0.21s
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

After the third restore, `review_record_session.py` was `diff`-identical to the copy taken before BP-1 (BP-2 no longer touches that file; its edit and restore are on `finding_outcomes.py`, shown above).
