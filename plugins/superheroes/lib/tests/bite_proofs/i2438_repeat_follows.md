# Bite-proof record — a kept repeat follows its earlier finding's current outcome (#2438)

Detector file: `plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/review_record.py` or `plugins/superheroes/lib/review_record_session.py`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2438 -m pytest '<exact node id>' -q`, one test node each (a parametrized function whose every case guards the same line runs as the one function and says so); output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. No secret, token, URL or personal data appears in any capture, so nothing is redacted. Entries 1 to 17 are the seventeen guarded elements the order declared, none grouped. The restore receipt of entries 1 to 8 is the restored line, quoted from a `grep -n` run on its own after the inverse edit; the green run follows it. Entries 9 to 17 use the whole-file `git diff` receipt (`git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, run as its own plain command after the inverse edit, printing nothing) because the line-search receipt was refused by a permission check.

The detectors the entries name are the tests that carry a `# bite-proof:` line in the detector file. Line numbers are those of the committed first pass (`0cba97ba`).

## 1. The stamp in `_findings_and_merges` (`review_record_session.py:1022-1026`, the `kept` mark is written)

- **Axis:** a row with its own valid `repeatKept` leaves the session writer with `repeatOf.kept = {"outcome", "verdict"}` (the row's outcome and its own grade verdict or none).
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict`, the one function; its three cases (`wrong`, `plausible`, `no-grade`) all run and all go red.
- **Neutralization:** `            if rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):` became `            if False and rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):` (the stamp block never runs).

**Raw red** (exit 1):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict[wrong] _

grade = {'verdict': 'wrong', 'reason': 'the cited line does not exist'}
verdict = 'wrong'

    @pytest.mark.parametrize("grade, verdict", [
        pytest.param(GRADE, "wrong", id="wrong"),
        pytest.param({"verdict": "plausible", "reason": "could not show it"}, "plausible", id="plausible"),
        pytest.param(None, None, id="no-grade"),
    ])
    def test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict(grade, verdict):
        # axis: the kept mark is stamped from the row's own decision, with the row's own grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        ledger = kept_row(**({"grade": grade} if grade else {}))
        found, _ = written(ledger)
        assert found[OTHER_KEY]["outcome"] == LFO
>       assert found[OTHER_KEY]["repeatOf"] == {**rs._stored_repeat(ledger["repeatOf"]),
                                                rr.REPEAT_KEPT_FIELD: {"outcome": LFO, "verdict": verdict}}
E       AssertionError: assert {'findingKey'...xHolds': None} == {'findingKey'...ct': 'wrong'}}
E         
E         Omitting 3 identical items, use -vv to show
E         Right contains 1 more item:
E         {'kept': {'outcome': 'left-for-owner', 'verdict': 'wrong'}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:281: AssertionError
_ test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict[plausible] _

grade = {'verdict': 'plausible', 'reason': 'could not show it'}
verdict = 'plausible'

    @pytest.mark.parametrize("grade, verdict", [
        pytest.param(GRADE, "wrong", id="wrong"),
        pytest.param({"verdict": "plausible", "reason": "could not show it"}, "plausible", id="plausible"),
        pytest.param(None, None, id="no-grade"),
    ])
    def test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict(grade, verdict):
        # axis: the kept mark is stamped from the row's own decision, with the row's own grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        ledger = kept_row(**({"grade": grade} if grade else {}))
        found, _ = written(ledger)
        assert found[OTHER_KEY]["outcome"] == LFO
>       assert found[OTHER_KEY]["repeatOf"] == {**rs._stored_repeat(ledger["repeatOf"]),
                                                rr.REPEAT_KEPT_FIELD: {"outcome": LFO, "verdict": verdict}}
E       AssertionError: assert {'findingKey'...xHolds': None} == {'findingKey'... 'plausible'}}
E         
E         Omitting 3 identical items, use -vv to show
E         Right contains 1 more item:
E         {'kept': {'outcome': 'left-for-owner', 'verdict': 'plausible'}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:281: AssertionError
_ test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict[no-grade] _

grade = None, verdict = None

    @pytest.mark.parametrize("grade, verdict", [
        pytest.param(GRADE, "wrong", id="wrong"),
        pytest.param({"verdict": "plausible", "reason": "could not show it"}, "plausible", id="plausible"),
        pytest.param(None, None, id="no-grade"),
    ])
    def test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict(grade, verdict):
        # axis: the kept mark is stamped from the row's own decision, with the row's own grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        ledger = kept_row(**({"grade": grade} if grade else {}))
        found, _ = written(ledger)
        assert found[OTHER_KEY]["outcome"] == LFO
>       assert found[OTHER_KEY]["repeatOf"] == {**rs._stored_repeat(ledger["repeatOf"]),
                                                rr.REPEAT_KEPT_FIELD: {"outcome": LFO, "verdict": verdict}}
E       AssertionError: assert {'findingKey'...xHolds': None} == {'findingKey'...rdict': None}}
E         
E         Omitting 3 identical items, use -vv to show
E         Right contains 1 more item:
E         {'kept': {'outcome': 'left-for-owner', 'verdict': None}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:281: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict[wrong]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict[plausible]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict[no-grade]
3 failed in 0.33s
```

**Restore:** the inverse edit removed `False and `.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record_session.py:1022`): `1022:            if rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):`

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed in 0.54s
```

## 2. The stamp's own-representative condition (`review_record_session.py:1022`, `sc.finding_identity_key(rep) == key`)

- **Axis:** the `kept` mark is stamped only on a finding that is its own representative; a member merged into another finding's representative gets none, though the representative's `repeatKept` is valid.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t8_a_merged_member_of_a_kept_repeat_gets_no_kept_mark`.
- **Neutralization:** `            if rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):` became `            if rep is not None and True and _valid_repeat_kept(rep):`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_t8_a_merged_member_of_a_kept_repeat_gets_no_kept_mark __________

    def test_t8_a_merged_member_of_a_kept_repeat_gets_no_kept_mark():
        # axis: the mark is stamped only on a finding that is its own representative, never on a member merged into one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        member = ledger_row("m::t@L1", id="m-1", title="m", file="m.py", line=1, consequence="c", disposition=None,
                            mergedInto=OTHER_KEY, repeatOf={"findingKey": KEY, "id": "f-1", "fixHolds": None})
        found, merged = written(kept_row(), member)
        assert merged == {"m::t@L1": OTHER_KEY}
        assert found[OTHER_KEY]["repeatOf"][rr.REPEAT_KEPT_FIELD] == {"outcome": LFO, "verdict": None}
        assert found["m::t@L1"]["outcome"] == LFO
>       assert rr.REPEAT_KEPT_FIELD not in found["m::t@L1"]["repeatOf"]
E       AssertionError: assert 'kept' not in {'findingKey': 'rr1:2872aad83366c4ee33af4c6798ad5df0', 'id': 'f-1', 'fixHolds': None, 'kept': {'outcome': 'left-for-owner', 'verdict': None}}
E        +  where 'kept' = rr.REPEAT_KEPT_FIELD

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:308: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_merged_member_of_a_kept_repeat_gets_no_kept_mark
1 failed in 0.34s
```

**Restore:** the inverse edit put `sc.finding_identity_key(rep) == key` back in place of `True`.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record_session.py:1022`): `1022:            if rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.28s
```

## 3. The stamp's valid-`repeatKept` condition (`review_record_session.py:1022`, `_valid_repeat_kept(rep)`)

- **Axis:** a row whose `repeatKept` is absent or invalid is never stamped; its `repeatOf` ends without a `kept` mark, whatever the ledger row's `repeatOf` held.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept`, the one function; its two cases (`no-repeat-kept`, `invalid-repeat-kept`) both run and both go red. An existing T8 node goes red, so no test was added to the new test file.
- **Neutralization:** `            if rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):` became `            if rep is not None and sc.finding_identity_key(rep) == key and True:`.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[no-repeat-kept] _

over = {'repeatKept': None}

    @pytest.mark.parametrize("over", [
        pytest.param({"repeatKept": None}, id="no-repeat-kept"),
        pytest.param({"repeatKept": {"outcome": LFO, "reason": ""}}, id="invalid-repeat-kept"),
    ])
    def test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept(over):
        # axis: a kept mark the ledger row already carries is not trusted; only this session's own decision writes it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        stale = {"findingKey": KEY, "id": "f-1", "fixHolds": None, "kept": {"outcome": "fixed", "verdict": "wrong"}}
        found, _ = written(kept_row(repeatOf=stale, **over))
>       assert found[OTHER_KEY]["repeatOf"] == {"findingKey": rr._key({"findingKey": KEY}), "id": "f-1", "fixHolds": None}
E       AssertionError: assert {'findingKey'...rdict': None}} == {'findingKey'...xHolds': None}
E         
E         Omitting 3 identical items, use -vv to show
E         Left contains 1 more item:
E         {'kept': {'outcome': 'left-for-owner', 'verdict': None}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:295: AssertionError
_ test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[invalid-repeat-kept] _

over = {'repeatKept': {'outcome': 'left-for-owner', 'reason': ''}}

    @pytest.mark.parametrize("over", [
        pytest.param({"repeatKept": None}, id="no-repeat-kept"),
        pytest.param({"repeatKept": {"outcome": LFO, "reason": ""}}, id="invalid-repeat-kept"),
    ])
    def test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept(over):
        # axis: a kept mark the ledger row already carries is not trusted; only this session's own decision writes it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        stale = {"findingKey": KEY, "id": "f-1", "fixHolds": None, "kept": {"outcome": "fixed", "verdict": "wrong"}}
        found, _ = written(kept_row(repeatOf=stale, **over))
>       assert found[OTHER_KEY]["repeatOf"] == {"findingKey": rr._key({"findingKey": KEY}), "id": "f-1", "fixHolds": None}
E       AssertionError: assert {'findingKey'...rdict': None}} == {'findingKey'...xHolds': None}
E         
E         Omitting 3 identical items, use -vv to show
E         Left contains 1 more item:
E         {'kept': {'outcome': 'left-for-owner', 'verdict': None}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:295: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[no-repeat-kept]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[invalid-repeat-kept]
2 failed in 0.30s
```

**Restore:** the inverse edit put `_valid_repeat_kept(rep)` back in place of `True`.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record_session.py:1022`): `1022:            if rep is not None and sc.finding_identity_key(rep) == key and _valid_repeat_kept(rep):`

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.29s
```

## 4. The strip of a stale `kept` in `_findings_and_merges` (`review_record_session.py:1020`, `_without_kept(held["repeatOf"])`)

- **Axis:** a `kept` mark the ledger or live row already holds in its `repeatOf` is dropped; only this session's own valid `repeatKept` stamps it (the stale mark here says `fixed`/`wrong`, the row's own decision says nothing, so a surviving stale mark is the failure).
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept`, the one function (same node as entry 3, a different line); both cases run and both go red.
- **Neutralization:** `            held["repeatOf"] = _without_kept(held["repeatOf"])` became `            held["repeatOf"] = held["repeatOf"]`.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[no-repeat-kept] _

over = {'repeatKept': None}

    @pytest.mark.parametrize("over", [
        pytest.param({"repeatKept": None}, id="no-repeat-kept"),
        pytest.param({"repeatKept": {"outcome": LFO, "reason": ""}}, id="invalid-repeat-kept"),
    ])
    def test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept(over):
        # axis: a kept mark the ledger row already carries is not trusted; only this session's own decision writes it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        stale = {"findingKey": KEY, "id": "f-1", "fixHolds": None, "kept": {"outcome": "fixed", "verdict": "wrong"}}
        found, _ = written(kept_row(repeatOf=stale, **over))
>       assert found[OTHER_KEY]["repeatOf"] == {"findingKey": rr._key({"findingKey": KEY}), "id": "f-1", "fixHolds": None}
E       AssertionError: assert {'findingKey'...ct': 'wrong'}} == {'findingKey'...xHolds': None}
E         
E         Omitting 3 identical items, use -vv to show
E         Left contains 1 more item:
E         {'kept': {'outcome': 'fixed', 'verdict': 'wrong'}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:295: AssertionError
_ test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[invalid-repeat-kept] _

over = {'repeatKept': {'outcome': 'left-for-owner', 'reason': ''}}

    @pytest.mark.parametrize("over", [
        pytest.param({"repeatKept": None}, id="no-repeat-kept"),
        pytest.param({"repeatKept": {"outcome": LFO, "reason": ""}}, id="invalid-repeat-kept"),
    ])
    def test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept(over):
        # axis: a kept mark the ledger row already carries is not trusted; only this session's own decision writes it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        stale = {"findingKey": KEY, "id": "f-1", "fixHolds": None, "kept": {"outcome": "fixed", "verdict": "wrong"}}
        found, _ = written(kept_row(repeatOf=stale, **over))
>       assert found[OTHER_KEY]["repeatOf"] == {"findingKey": rr._key({"findingKey": KEY}), "id": "f-1", "fixHolds": None}
E       AssertionError: assert {'findingKey'...ct': 'wrong'}} == {'findingKey'...xHolds': None}
E         
E         Omitting 3 identical items, use -vv to show
E         Left contains 1 more item:
E         {'kept': {'outcome': 'fixed', 'verdict': 'wrong'}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:295: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[no-repeat-kept]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept[invalid-repeat-kept]
2 failed in 0.29s
```

**Restore:** the inverse edit put `_without_kept(held["repeatOf"])` back.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record_session.py:1020`): `1020:            held["repeatOf"] = _without_kept(held["repeatOf"])`

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.28s
```

## 5. The strip in `_fill` (`review_record_session.py:1764`, `_without_kept(_stored_repeat(old[part]))`)

- **Axis:** the earlier record's `kept` mark is not copied into the current finding's `repeatOf` when `_fill` copies the part; it is this session's own decision's alone.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t9_fill_copies_the_earlier_records_repeat_without_its_kept_mark`.
- **Neutralization:** `                f[part] = _without_kept(_stored_repeat(old[part])) if part == "repeatOf" else old[part]` became `                f[part] = _stored_repeat(old[part]) if part == "repeatOf" else old[part]`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t9_fill_copies_the_earlier_records_repeat_without_its_kept_mark _____

    def test_t9_fill_copies_the_earlier_records_repeat_without_its_kept_mark():
        # axis: the earlier record's kept mark is not carried into the current finding; it is the current session's own decision's alone
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        earlier = kept_finding()
        before = copy.deepcopy(earlier)
        acct = {"findings": [{"findingKey": earlier["findingKey"]}]}
        rs._fill(acct, [earlier])
>       assert acct["findings"][0]["repeatOf"] == mark(findingKey=rr._key({"findingKey": OTHER_KEY}))
E       AssertionError: assert {'findingKey'...ct': 'wrong'}} == {'findingKey'...xHolds': None}
E         
E         Omitting 3 identical items, use -vv to show
E         Left contains 1 more item:
E         {'kept': {'outcome': 'fixed', 'verdict': 'wrong'}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:325: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t9_fill_copies_the_earlier_records_repeat_without_its_kept_mark
1 failed in 0.27s
```

**Restore:** the inverse edit put `_without_kept(...)` back around `_stored_repeat(old[part])`.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record_session.py:1764`): `1764:                f[part] = _without_kept(_stored_repeat(old[part])) if part == "repeatOf" else old[part]`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.28s
```

## 6. The strip in `_carried` (`review_record_session.py:1790`, `_without_kept(copied["repeatOf"])`)

- **Axis:** a finding carried from the earlier record into this record does not bring its `kept` mark; the copy drops it and the earlier record's own finding is left alone.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t9_carried_copies_an_earlier_finding_without_its_kept_mark_and_leaves_the_earlier_one_alone`.
- **Neutralization:** `            copied["repeatOf"] = _without_kept(copied["repeatOf"])` became `            copied["repeatOf"] = copied["repeatOf"]`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t9_carried_copies_an_earlier_finding_without_its_kept_mark_and_leaves_the_earlier_one_alone _

    def test_t9_carried_copies_an_earlier_finding_without_its_kept_mark_and_leaves_the_earlier_one_alone():
        # axis: a finding carried from the earlier record does not bring its kept mark into this record
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        earlier = kept_finding()
        before = copy.deepcopy(earlier)
        (copied,) = rs._carried({"findings": []}, [earlier])
>       assert copied["repeatOf"] == mark(findingKey=OTHER_KEY)
E       AssertionError: assert {'findingKey'...ct': 'wrong'}} == {'findingKey'...xHolds': None}
E         
E         Omitting 3 identical items, use -vv to show
E         Left contains 1 more item:
E         {'kept': {'outcome': 'fixed', 'verdict': 'wrong'}}
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:335: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t9_carried_copies_an_earlier_finding_without_its_kept_mark_and_leaves_the_earlier_one_alone
1 failed in 0.31s
```

**Restore:** the inverse edit put `_without_kept(copied["repeatOf"])` back.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record_session.py:1790`): `1790:            copied["repeatOf"] = _without_kept(copied["repeatOf"])`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.29s
```

## 7. The `kept` validation in `_repeat_fault` (`review_record.py:797-799`)

- **Axis:** a `kept` mark that is present but is not an object holding an outcome of the vocabulary and a grade verdict or none is refused as `review-account-invalid`, naming `findings[1].repeatOf.kept`.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it`, the one function; its six cases (`not-an-object`, `null`, `outcome-outside-the-vocabulary`, `no-outcome`, `verdict-outside-the-grade-vocabulary`, `verdict-not-text`) all guard the same condition and all go red.
- **Neutralization:** `    if REPEAT_KEPT_FIELD in g and not (isinstance(kept, dict) and kept.get("outcome") in rfs.OUTCOMES` became `    if False and REPEAT_KEPT_FIELD in g and not (isinstance(kept, dict) and kept.get("outcome") in rfs.OUTCOMES` (the continuation line unchanged).

**Raw red** (exit 1):

```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
____ test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[not-an-object] _____

bad = 'fixed'

    @pytest.mark.parametrize("bad", [
        pytest.param("fixed", id="not-an-object"),
        pytest.param(None, id="null"),
        pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
        pytest.param({"verdict": "wrong"}, id="no-outcome"),
        pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
        pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
    ])
    def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
        # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
>       with pytest.raises(rr.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:239: Failed
_________ test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[null] _________

bad = None

    @pytest.mark.parametrize("bad", [
        pytest.param("fixed", id="not-an-object"),
        pytest.param(None, id="null"),
        pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
        pytest.param({"verdict": "wrong"}, id="no-outcome"),
        pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
        pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
    ])
    def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
        # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
>       with pytest.raises(rr.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:239: Failed
_ test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[outcome-outside-the-vocabulary] _

bad = {'outcome': 'wontfix', 'verdict': None}

    @pytest.mark.parametrize("bad", [
        pytest.param("fixed", id="not-an-object"),
        pytest.param(None, id="null"),
        pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
        pytest.param({"verdict": "wrong"}, id="no-outcome"),
        pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
        pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
    ])
    def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
        # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
>       with pytest.raises(rr.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:239: Failed
______ test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[no-outcome] ______

bad = {'verdict': 'wrong'}

    @pytest.mark.parametrize("bad", [
        pytest.param("fixed", id="not-an-object"),
        pytest.param(None, id="null"),
        pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
        pytest.param({"verdict": "wrong"}, id="no-outcome"),
        pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
        pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
    ])
    def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
        # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
>       with pytest.raises(rr.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:239: Failed
_ test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[verdict-outside-the-grade-vocabulary] _

bad = {'outcome': 'fixed', 'verdict': 'maybe'}

    @pytest.mark.parametrize("bad", [
        pytest.param("fixed", id="not-an-object"),
        pytest.param(None, id="null"),
        pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
        pytest.param({"verdict": "wrong"}, id="no-outcome"),
        pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
        pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
    ])
    def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
        # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
>       with pytest.raises(rr.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:239: Failed
___ test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[verdict-not-text] ___

bad = {'outcome': 'fixed', 'verdict': 3}

    @pytest.mark.parametrize("bad", [
        pytest.param("fixed", id="not-an-object"),
        pytest.param(None, id="null"),
        pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
        pytest.param({"verdict": "wrong"}, id="no-outcome"),
        pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
        pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
    ])
    def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
        # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
>       with pytest.raises(rr.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:239: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[not-an-object]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[null]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[outcome-outside-the-vocabulary]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[no-outcome]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[verdict-outside-the-grade-vocabulary]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t7_e12_a_malformed_kept_mark_is_refused_naming_it[verdict-not-text]
6 failed in 0.33s
```

**Restore:** the inverse edit removed `False and `.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record.py:797`): `797:    if REPEAT_KEPT_FIELD in g and not (isinstance(kept, dict) and kept.get("outcome") in rfs.OUTCOMES`

**Raw green** (exit 0):

```
......                                                                   [100%]
6 passed in 0.30s
```

## 8. The follow's `fixed` branch (`review_record.py:1909`, `if follows:`)

- **Axis:** a wrong-graded kept repeat whose earlier finding reads `fixed` in this record moves to `fixed`, with `fixHolds` true and the kept mark restamped.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t2_an_earlier_finding_fixed_in_the_session_moves_its_wrong_graded_kept_repeat`.
- **Neutralization:** `            if follows:` became `            if False and follows:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_an_earlier_finding_fixed_in_the_session_moves_its_wrong_graded_kept_repeat _

    def test_t2_an_earlier_finding_fixed_in_the_session_moves_its_wrong_graded_kept_repeat():
        # axis: the earlier finding needs no carried check, a fixed outcome of this account is enough
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        rec = build([X_FIXED, repeat()])
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == "fixed"
E       AssertionError: assert 'left-for-owner' == 'fixed'
E         
E         - fixed
E         + left-for-owner

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t2_an_earlier_finding_fixed_in_the_session_moves_its_wrong_graded_kept_repeat
1 failed in 0.28s
```

**Restore:** the inverse edit removed `False and `.
**Restore receipt** (quoted from a `grep -n` of the restored line, `review_record.py:1909`): `1909:            if follows:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.29s
```

## 9. The keeps-own branch (`review_record.py:1920`, `changed = dict(f)`)

- **Axis:** a kept repeat whose kept verdict is not `wrong` (`confirmed`, `plausible`, none) keeps its own outcome and its owner card, with the keeps-own reason.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card`, the one function; its three cases (`confirmed`, `plausible`, `none`) all guard the same line and all go red.
- **Neutralization:** `                changed = dict(f)` became `                changed = dict(f, outcome=_FIXED)`.

**Raw red** (exit 1):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card[confirmed] _

verdict = 'confirmed'

    @pytest.mark.parametrize("verdict", [
        pytest.param("confirmed", id="confirmed"),
        pytest.param("plausible", id="plausible"),
        pytest.param(None, id="none"),
    ])
    def test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card(verdict):
        # axis: only a wrong verdict moves the repeat; any other verdict, or none, keeps the outcome and the owner card
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        rec = build([X_FIXED, repeat(verdict=verdict)])
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == LFO
E       AssertionError: assert 'fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:123: AssertionError
_ test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card[plausible] _

verdict = 'plausible'

    @pytest.mark.parametrize("verdict", [
        pytest.param("confirmed", id="confirmed"),
        pytest.param("plausible", id="plausible"),
        pytest.param(None, id="none"),
    ])
    def test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card(verdict):
        # axis: only a wrong verdict moves the repeat; any other verdict, or none, keeps the outcome and the owner card
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        rec = build([X_FIXED, repeat(verdict=verdict)])
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == LFO
E       AssertionError: assert 'fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:123: AssertionError
_ test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card[none] _

verdict = None

    @pytest.mark.parametrize("verdict", [
        pytest.param("confirmed", id="confirmed"),
        pytest.param("plausible", id="plausible"),
        pytest.param(None, id="none"),
    ])
    def test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card(verdict):
        # axis: only a wrong verdict moves the repeat; any other verdict, or none, keeps the outcome and the owner card
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        rec = build([X_FIXED, repeat(verdict=verdict)])
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == LFO
E       AssertionError: assert 'fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:123: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card[confirmed]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card[plausible]
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card[none]
3 failed in 0.32s
```

**Restore:** the inverse edit put `changed = dict(f)` back (the edit tool reported success).
**Restore receipt:** the earlier dispatch's `grep -n` was refused (refusedBy permission) and was not retried in any form. The receipt is now the whole-file one: `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, run on its own after the file was restored, printed nothing (empty output, exit 0).

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed in 0.33s
```

## 10. Eligibility: the outcome still equals `kept.outcome` (`review_record.py:1898`, `f.get("outcome") != kept.get("outcome")`)

- **Axis:** a repeat whose outcome is no longer the one its kept mark holds is left as the follow found it.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E6-outcome-is-no-longer-the-kept-one]`, the one case, run alone.
- **Neutralization:** `            if (i in handled or not isinstance(kept, dict) or f.get("outcome") != kept.get("outcome")` became `            if (i in handled or not isinstance(kept, dict)` (the clause removed, the continuation lines unchanged).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E6-outcome-is-no-longer-the-kept-one] _

over = {'outcome': 'craft', 'repeatOf': {'findingKey': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'id': 'f-1', 'fixHolds': None, 'kept': {'outcome': 'left-for-owner', 'verdict': 'wrong'}}}
checks = []

    @pytest.mark.parametrize("over, checks", [
        pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept(LFO, "wrong"))), [], id="E6-outcome-is-no-longer-the-kept-one"),
        pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept("craft", "wrong")),
                          decidedBy={"kind": "canon", "ref": "c1"}), [], id="E7-carries-a-decidedBy"),
        pytest.param({}, [APPLIES], id="E8-a-carried-check-names-the-repeat"),
        pytest.param(dict(repeatOf=mark()), [], id="E9-no-kept-mark"),
    ])
    def test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it(over, checks):
        # axis: only a repeat still at its kept outcome, with no cited decision, no carried check naming it and a kept mark is read
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat(**over)
        rec = build([X_FIXED, given], checks)
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == given["outcome"]
E       AssertionError: assert 'fixed' == 'craft'
E         
E         - craft
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:172: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E6-outcome-is-no-longer-the-kept-one]
1 failed in 0.32s
```

**Restore:** the inverse edit put `or f.get("outcome") != kept.get("outcome")` back on the line.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.28s
```

## 11. Eligibility: `decidedBy` (`review_record.py:1899`, `session_contract.decided_by_of(f) is not None`)

- **Axis:** a repeat that cites a decision is left as the follow found it.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E7-carries-a-decidedBy]`, the one case, run alone.
- **Neutralization:** `                    or f.get("outcome") == _FIXED or session_contract.decided_by_of(f) is not None` became `                    or f.get("outcome") == _FIXED`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E7-carries-a-decidedBy] _

over = {'outcome': 'craft', 'repeatOf': {'findingKey': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'id': 'f-1', 'fixHolds': None, 'kept': {'outcome': 'craft', 'verdict': 'wrong'}}, 'decidedBy': {'kind': 'canon', 'ref': 'c1'}}
checks = []

    @pytest.mark.parametrize("over, checks", [
        pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept(LFO, "wrong"))), [], id="E6-outcome-is-no-longer-the-kept-one"),
        pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept("craft", "wrong")),
                          decidedBy={"kind": "canon", "ref": "c1"}), [], id="E7-carries-a-decidedBy"),
        pytest.param({}, [APPLIES], id="E8-a-carried-check-names-the-repeat"),
        pytest.param(dict(repeatOf=mark()), [], id="E9-no-kept-mark"),
    ])
    def test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it(over, checks):
        # axis: only a repeat still at its kept outcome, with no cited decision, no carried check naming it and a kept mark is read
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat(**over)
        rec = build([X_FIXED, given], checks)
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == given["outcome"]
E       AssertionError: assert 'fixed' == 'craft'
E         
E         - craft
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:172: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E7-carries-a-decidedBy]
1 failed in 0.35s
```

**Restore:** the inverse edit put `or session_contract.decided_by_of(f) is not None` back after `or f.get("outcome") == _FIXED`.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.33s
```

## 12. Eligibility: a carried check names the repeat (`review_record.py:1900`, `any(c["key"] in (...) for c in checks)`)

- **Axis:** a repeat that a carried check names (by finding key or id) is left to `_recheck_carried`'s decision, not followed.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E8-a-carried-check-names-the-repeat]`, the one case, run alone.
- **Neutralization:** `                    or any(c["key"] in (f.get(session_contract.FINDING_KEY_FIELD), f.get("id")) for c in checks)):` became `                    or False):`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E8-a-carried-check-names-the-repeat] _

over = {}
checks = [{'key': 'f-2', 'settled': 'applies', 'commit': None, 'checkedHead': None, ...}]

    @pytest.mark.parametrize("over, checks", [
        pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept(LFO, "wrong"))), [], id="E6-outcome-is-no-longer-the-kept-one"),
        pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept("craft", "wrong")),
                          decidedBy={"kind": "canon", "ref": "c1"}), [], id="E7-carries-a-decidedBy"),
        pytest.param({}, [APPLIES], id="E8-a-carried-check-names-the-repeat"),
        pytest.param(dict(repeatOf=mark()), [], id="E9-no-kept-mark"),
    ])
    def test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it(over, checks):
        # axis: only a repeat still at its kept outcome, with no cited decision, no carried check naming it and a kept mark is read
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat(**over)
        rec = build([X_FIXED, given], checks)
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == given["outcome"]
E       AssertionError: assert 'fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:172: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it[E8-a-carried-check-names-the-repeat]
1 failed in 0.27s
```

**Restore:** the inverse edit put the `any(c["key"] in (...) for c in checks)` clause back in place of `False`.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.28s
```

## 13. Eligibility: the earlier finding reads `fixed` (`review_record.py:1904`, `g.get("outcome") != _FIXED`)

- **Axis:** every earlier outcome other than `fixed` leaves the repeat as it is; here the earlier finding is still `left-for-owner`.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t4_e1_to_e5_a_repeat_whose_earlier_finding_does_not_read_fixed_is_unchanged[E1-earlier-still-left-for-owner]`, the one case, run alone.
- **Neutralization:** `            if g is None or g is f or g.get("outcome") != _FIXED:` became `            if g is None or g is f:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t4_e1_to_e5_a_repeat_whose_earlier_finding_does_not_read_fixed_is_unchanged[E1-earlier-still-left-for-owner] _

earlier = {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}
checks = [], kw = {}, cards = ['f-1']

    @pytest.mark.parametrize("earlier, checks, kw, cards", [
        pytest.param(X, [], {}, ["f-1"], id="E1-earlier-still-left-for-owner"),
        pytest.param(dict(X, outcome=None, reason="still open"), [], {}, ["f-2"], id="E2-earlier-open"),
        pytest.param(dict(X, outcome="craft", reason="a craft call"), [], {}, ["f-2"], id="E3-earlier-craft"),
        pytest.param(dict(X, outcome="ruling", reason="the owner ruled it out of scope"), [], {}, ["f-2"],
                     id="E3-earlier-ruling"),
        pytest.param(X, [entry(settled="applies")], {}, ["f-1"], id="E4-check-applies"),
        pytest.param(X, [entry(settled="unsettled")], {}, ["f-1"], id="E4-check-unsettled"),
        pytest.param(X, [entry(checkedHead=THIRD)], {}, ["f-1"], id="E4-check-on-another-head"),
        pytest.param(X, [entry()], {"ancestor": False}, ["f-1"], id="E4-fix-not-in-history"),
        pytest.param(None, [], {}, ["f-2"], id="E5-earlier-not-in-the-record"),
    ])
    def test_t4_e1_to_e5_a_repeat_whose_earlier_finding_does_not_read_fixed_is_unchanged(earlier, checks, kw, cards):
        # axis: the follow runs only when the earlier finding reads fixed in this record; every other case leaves the repeat and its card
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat()
        rec = build([given] if earlier is None else [earlier, given], checks, **kw)
        r = by_id(rec)["f-2"]
>       assert (r["outcome"], r["reason"], r["repeatOf"]) == (LFO, OLD, given["repeatOf"])
E       AssertionError: assert ('fixed', 're...t': 'wrong'}}) == ('left-for-ow...t': 'wrong'}})
E         
E         At index 0 diff: 'fixed' != 'left-for-owner'
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:150: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t4_e1_to_e5_a_repeat_whose_earlier_finding_does_not_read_fixed_is_unchanged[E1-earlier-still-left-for-owner]
1 failed in 0.28s
```

**Restore:** the inverse edit put `or g.get("outcome") != _FIXED` back on the line.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.27s
```

## 14. The verdict is read from `kept.verdict`, never from `grade` (`review_record.py:1907`)

- **Axis:** the verdict that decides the follow is the one in the kept mark; a repeat whose kept verdict is none but whose `grade` says `wrong` keeps its outcome.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t5_e11_the_verdict_is_read_from_the_kept_mark_never_from_the_grade`.
- **Neutralization:** `            verdict, old = kept.get("verdict"), f.get("reason")` became `            verdict, old = (f.get("grade") or {}).get("verdict"), f.get("reason")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t5_e11_the_verdict_is_read_from_the_kept_mark_never_from_the_grade ____

    def test_t5_e11_the_verdict_is_read_from_the_kept_mark_never_from_the_grade():
        # axis: the repeat's own grade is not read at write time; a wrong grade beside a kept verdict of none keeps the outcome
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat(verdict=None, grade={"verdict": "wrong", "reason": "the cited line does not exist"})
        rec = build([X_FIXED, given])
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == LFO
E       AssertionError: assert 'fixed' == 'left-for-owner'
E         
E         - left-for-owner
E         + fixed

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:183: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t5_e11_the_verdict_is_read_from_the_kept_mark_never_from_the_grade
1 failed in 0.29s
```

**Restore:** the inverse edit put `kept.get("verdict")` back.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.28s
```

## 15. A repeat that already reads `fixed` is skipped (`review_record.py:1899`, `f.get("outcome") == _FIXED`)

- **Axis:** a repeat already at `fixed` has nothing to follow, so its reason and its `repeatOf` are not rewritten.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t5_e13_a_repeat_that_already_reads_fixed_keeps_its_reason`.
- **Neutralization:** `                    or f.get("outcome") == _FIXED or session_contract.decided_by_of(f) is not None` became `                    or session_contract.decided_by_of(f) is not None`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t5_e13_a_repeat_that_already_reads_fixed_keeps_its_reason ________

    def test_t5_e13_a_repeat_that_already_reads_fixed_keeps_its_reason():
        # axis: a repeat already at fixed has nothing to follow, so its reason is not rewritten
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        given = repeat("fixed", reason="repeat of f-1; keeps its earlier outcome (fixed); the verifier found the fix still holds")
        rec = build([X_FIXED, given])
        r = by_id(rec)["f-2"]
>       assert r["outcome"] == "fixed" and r["reason"] == given["reason"] and r["repeatOf"] == given["repeatOf"]
E       AssertionError: assert ('fixed' == 'fixed'
E         
E           fixed and 'repeat of f-...x still holds' == 'repeat of f-...x still holds'
E         
E         - repeat of f-1; keeps its earlier outcome (fixed); the verifier found the fix still holds
E         + repeat of f-1, which is now fixed; this session's verifier graded the repeat wrong, so the fix holds and it reads fixed; earlier: repeat of f-1; keeps its earlier outcome (fixed); the verifier found the fix still holds)

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:194: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t5_e13_a_repeat_that_already_reads_fixed_keeps_its_reason
1 failed in 0.31s
```

**Restore:** the inverse edit put `or f.get("outcome") == _FIXED` back before the `decidedBy` clause.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.31s
```

## 16. The chain fixed point (`review_record.py:1891` and `:1916`, the `while moved` re-pass)

- **Axis:** a repeat of a repeat of a fixed finding follows once the repeat it repeats has moved, whatever their order in the list; the re-pass is what reaches the later one.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t6_a_chain_of_kept_repeats_settles_to_a_fixed_point`.
- **Neutralization:** `                moved = True` (in the `if follows:` branch, line 1916) became `                moved = False`, so the loop never makes a second pass.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_t6_a_chain_of_kept_repeats_settles_to_a_fixed_point ___________

    def test_t6_a_chain_of_kept_repeats_settles_to_a_fixed_point():
        # axis: a repeat of a repeat of a fixed finding follows once the repeat it repeats has moved, whatever their order
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        first = repeat(fid="f-2", title="Same mistake again", line=12)
        second = repeat(fid="f-3", title="Third sighting", line=15, of=rr._key(first))
        rec = build([X_FIXED, second, first])
        rows = by_id(rec)
>       assert (rows["f-2"]["outcome"], rows["f-3"]["outcome"]) == ("fixed", "fixed")
E       AssertionError: assert ('fixed', 'left-for-owner') == ('fixed', 'fixed')
E         
E         At index 1 diff: 'left-for-owner' != 'fixed'
E         Use -v to get more diff

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:206: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t6_a_chain_of_kept_repeats_settles_to_a_fixed_point
1 failed in 0.47s
```

**Restore:** the inverse edit put `moved = True` back (the first inverse-edit attempt named a wrong neighbouring line and the edit tool refused it with "String to replace not found"; the file was unchanged by it; the second attempt, anchored on the following `else:` line, applied).
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.34s
```

## 17. The placement after `_recheck_carried` in `build_record` (`review_record.py:2008-2012`)

- **Axis:** a kept repeat follows its earlier finding only after the carried re-check has settled it, so a carried fix reaches the repeat.
- **Detector:** `test_review_record_repeat_follows_2438.py::test_t1_a_carried_fixed_check_on_the_earlier_finding_moves_its_wrong_graded_kept_repeat`.
- **Neutralization:** two edit-tool edits: the line `    findings = _follow_repeats(findings, a["carriedChecks"])` was removed from before `findings = _drop_stale_open_marker(findings)` and inserted, unchanged, immediately before `findings, carried_rows = _recheck_carried(findings, a["carriedChecks"], fc["sha"],` (the call moved above `_recheck_carried`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_carried_fixed_check_on_the_earlier_finding_moves_its_wrong_graded_kept_repeat _

    def test_t1_a_carried_fixed_check_on_the_earlier_finding_moves_its_wrong_graded_kept_repeat():
        # axis: the field case, a repeat raised in the returning session follows the carried earlier finding a fixed check moved
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
        assert rr._key(repeat()) != X_KEY
        rec = build([X, repeat()], [entry()])
        rows = by_id(rec)
        assert rows["f-1"]["outcome"] == "fixed"
        r = rows["f-2"]
>       assert r["outcome"] == "fixed"
E       AssertionError: assert 'left-for-owner' == 'fixed'
E         
E         - fixed
E         + left-for-owner

/home/user/wt-2438/plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py:73: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_2438.py::test_t1_a_carried_fixed_check_on_the_earlier_finding_moves_its_wrong_graded_kept_repeat
1 failed in 0.30s
```

**Restore:** the two inverse edits, in reverse order: the call line removed from above `_recheck_carried`, then put back above `findings = _drop_stale_open_marker(findings)`.
**Restore receipt:** `git diff ab5c57e047f4121f13cc40e21e8e78c6a8b9018d -- plugins/superheroes/lib/review_record.py`, its own plain command, printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.30s
```

