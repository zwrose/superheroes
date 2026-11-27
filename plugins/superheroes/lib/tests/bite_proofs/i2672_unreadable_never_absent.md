# Bite-proof record — the review loop's readers stop at an unreadable earlier record or round (#2672)

Detector file: `plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py`, unedited between each red and its green. Each entry is a targeted, reversible edit to the guarded file, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`), on top of commit `040de699` of the build branch, so every probe started from committed work. Runs: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest "<file>::<node>" -q -p no:cacheprovider`, selecting the detector by its exact node id. Each capture is the run's whole output; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token or personal data appears in any capture; the only URLs are the fixture's `example.invalid` stand-ins, so nothing is redacted. After the five probes, `git status --porcelain` printed nothing (every restore matched the commit) and the whole detector file ran green: `28 passed in 0.23s`.

Guarded elements: S1 (`review_record_session._earlier`), S2 (`review_record_session._other_session_findings`), M1 (`review_memory._terminal_fields_from_records`, the state check), L1 (`review_loop_plan._carry_forward_dimension`, the per-dimension stop) and L2 (`review_loop_plan._round_findings`, used by `_surfaced_blocking_severities` and `_assemble_rounds`). M2 (the fix-block check) is not probed; see the end.

## S1. The unreadable latest record (`lib/review_record_session.py`, `_earlier`)

- **Axis:** an earlier record that could not be read gives no findings, and the record names it; it is never read as "no earlier record".
- **Detector:** `test_s1_the_writer_carries_nothing_from_an_unreadable_latest_record_and_names_it`.
- **Neutralization:** `return _Unreadable(prior.get("detail") or "the latest review record could not be read")` replaced by `return []`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s1_the_writer_carries_nothing_from_an_unreadable_latest_record_and_names_it _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fdf6aeea6f0>
tmp_path = PosixPath('/tmp/pytest-of-root/pytest-3/test_s1_the_writer_carries_not0')

    def test_s1_the_writer_carries_nothing_from_an_unreadable_latest_record_and_names_it(monkeypatch, tmp_path):
        # axis: an earlier record that could not be read gives no findings and no raisers, and the record names it
        older = _record_body(_record(OLDER, [_finding("old finding", raiser="code-reviewer")]))
        acct = _write_through(monkeypatch, tmp_path, _comments(older, UNPARSEABLE),
                              findings=[_finding("old finding", raiser="test-role")])
        assert [f["title"] for f in acct["findings"]] == ["old finding"]
        assert acct["findings"][0]["raisedBy"] == "test-role", "the older record behind the unreadable one was read"
        joined = " ".join(acct["checked"])
>       assert "No findings were carried from the latest earlier review record" in joined
E       assert 'No findings were carried from the latest earlier review record' in "No raiser was taken from an earlier session's review record: the walk stopped at a record it could not read (https://example.invalid/pr/7#c101: the record could not be read), so each finding keeps this session's own raiser."

/home/user/superheroes/.claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py:125: AssertionError
=========================== short test summary info ============================
FAILED .claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py::test_s1_the_writer_carries_nothing_from_an_unreadable_latest_record_and_names_it
1 failed in 0.24s
```

**Restore:** the inverse edit put the `_Unreadable(...)` return back.

## S2. The raiser walk's stop (`lib/review_record_session.py`, `_other_session_findings`)

- **Axis:** an earlier record that cannot be parsed stops the raiser walk instead of being skipped, so an older record's raiser is never read past it.
- **Detector:** `test_s2_an_unparseable_record_stops_the_raiser_walk`.
- **Neutralization:** `return _Unreadable(f"{where}: the record could not be read")` (the `not isinstance(rec, dict)` branch) replaced by `continue`, the old skip.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_s2_an_unparseable_record_stops_the_raiser_walk ______________

    def test_s2_an_unparseable_record_stops_the_raiser_walk():
        # axis: an earlier record that cannot be parsed stops the raiser walk instead of being skipped
        older = _record_body(_record(OLDER, [_finding("x", raiser="code-reviewer")]))
        out = rs._other_session_findings(_account(), {}, "/r", _readers(_comments(older, UNPARSEABLE)))
>       assert isinstance(out, rs._Unreadable), out
E       AssertionError: [{'id': 'x', 'title': 'x', 'file': 'src/a.py', 'line': 3, ...}]
E       assert False
E        +  where False = isinstance([{'id': 'x', 'title': 'x', 'file': 'src/a.py', 'line': 3, ...}], <class 'review_record_session._Unreadable'>)
E        +    where <class 'review_record_session._Unreadable'> = rs._Unreadable

/home/user/superheroes/.claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py:147: AssertionError
=========================== short test summary info ============================
FAILED .claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py::test_s2_an_unparseable_record_stops_the_raiser_walk
1 failed in 13.51s
```

The red shows the old fallback exactly: with the skip restored, the walk returned the older record's findings.

**Restore:** the inverse edit put the `_Unreadable(...)` return back.

## M1. The terminal compose over unreadable round records (`lib/review_memory.py`, `_terminal_fields_from_records`)

- **Axis:** unreadable or corrupt round records stop the terminal compose with a named reason, never read as no rounds.
- **Detector:** `test_m1_corrupt_round_records_stop_the_compose_with_a_named_reason`.
- **Neutralization:** `if not state.get("ok"):` replaced by `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_m1_corrupt_round_records_stop_the_compose_with_a_named_reason ______

tmp_path = PosixPath('/tmp/pytest-of-root/pytest-5/test_m1_corrupt_round_records_0')

    def test_m1_corrupt_round_records_stop_the_compose_with_a_named_reason(tmp_path):
        # axis: unreadable or corrupt round records stop the terminal compose with a named reason, never read as no rounds
        for text in ("{corrupt", json.dumps({"not": "a list"}), json.dumps([_round(1, {}), "junk"])):
            out, path = _compose(tmp_path, text)
>           assert out["ok"] is False and out["reason"] == rm.ROUND_RECORDS_UNREADABLE, out
E           AssertionError: {'ok': True, 'contentHash': '164110bb18e64fe3489a363bad8ec393a081d8b681671d38cf24cfd6b1d338aa'}
E           assert (True is False)

/home/user/superheroes/.claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py:190: AssertionError
=========================== short test summary info ============================
FAILED .claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py::test_m1_corrupt_round_records_stop_the_compose_with_a_named_reason
1 failed in 0.35s
```

**Restore:** the inverse edit put `if not state.get("ok"):` back.

## L1. The carry's per-dimension stop (`lib/review_loop_plan.py`, `_carry_forward_dimension`)

- **Axis:** a dimension state that cannot be read stops the carry instead of carrying an older round's state.
- **Detector:** `test_l1_the_carry_never_reaches_past_an_unreadable_round_to_an_older_one` (its `bad2` case, a newer round whose state for the dimension is not an object; the other two cases are guarded by `_round_dimensions`, which this probe left in place, so they stay green).
- **Neutralization:** the `raise RoundUnreadable(... the state of dimension ... is not an object)` replaced by `continue`, the old walk to an older round.

**Raw red** (exit 1):

```
..F                                                                      [100%]
=================================== FAILURES ===================================
_ test_l1_the_carry_never_reaches_past_an_unreadable_round_to_an_older_one[bad2] _

bad = {'round': 2, 'kind': 'baseline', 'dimensions': {'security-reviewer': 'junk'}, 'findings': []}

    @pytest.mark.parametrize("bad", ["junk", _rec(2, "junk"), _rec(2, {"security-reviewer": "junk"})])
    def test_l1_the_carry_never_reaches_past_an_unreadable_round_to_an_older_one(bad):
        # axis: a dimension state that cannot be read stops the carry instead of carrying an older round's state
>       with pytest.raises(rlp.RoundUnreadable):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE RoundUnreadable

/home/user/superheroes/.claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py:241: Failed
=========================== short test summary info ============================
FAILED .claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py::test_l1_the_carry_never_reaches_past_an_unreadable_round_to_an_older_one[bad2]
1 failed, 2 passed in 0.24s
```

**Restore:** the inverse edit put the `raise RoundUnreadable(...)` back.

## L2. The round findings shape check (`lib/review_loop_plan.py`, `_round_findings`)

- **Axis:** an unreadable round stops the breaker's round walk instead of being skipped; a findings field that is not a list of objects is never read as no findings.
- **Detector:** `test_l2_assemble_rounds_stops_at_an_unreadable_round` (its `bad1` case; the `"junk"` case is guarded by `_readable_round`, left in place).
- **Neutralization:** the `raise RoundUnreadable(... its findings are not a list of objects)` replaced by `return []`.

**Raw red** (exit 1):

```
.F                                                                       [100%]
=================================== FAILURES ===================================
__________ test_l2_assemble_rounds_stops_at_an_unreadable_round[bad1] __________

bad = {'round': 2, 'kind': 'baseline', 'dimensions': {}, 'findings': {'a': 1}}

    @pytest.mark.parametrize("bad", ["junk", _rec(2, {}) | {"findings": {"a": 1}}])
    def test_l2_assemble_rounds_stops_at_an_unreadable_round(bad):
        # axis: an unreadable round stops the breaker's round walk instead of being skipped
>       with pytest.raises(rlp.RoundUnreadable):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE RoundUnreadable

/home/user/superheroes/.claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py:285: Failed
=========================== short test summary info ============================
FAILED .claude/worktrees/b2672/plugins/superheroes/lib/tests/test_unreadable_never_absent_2672.py::test_l2_assemble_rounds_stops_at_an_unreadable_round[bad1]
1 failed, 1 passed in 0.20s
```

**Restore:** the inverse edit put the `raise RoundUnreadable(...)` back.

## Raw green (all five restored, exit 0)

```
............................                                             [100%]
28 passed in 0.23s
```

## Not proven here

- M2 (a round whose `fix` block is not an object stops the compose) has its detector, `test_m2_a_round_whose_fix_block_is_not_an_object_stops_the_compose`, but no neutralization was run for it.
- `_readable_round` (a round record that is not an object) and `_round_dimensions` (a dimensions field that is not an object) are reached by the L1 and L2 tests' other cases, which stayed green under the L1 and L2 probes because those probes left them in place; no probe of their own was run.
- The deciders' catch of `RoundUnreadable` (`plan_round_decider`, `tally_round_decider`) is covered by `test_l1_plan_round_runs_all_deep_and_names_the_unreadable_round` and `test_l2_tally_cannot_certify_with_the_named_reason`, not probed.
- The malformed-findings stop in `_other_session_findings` (S2's second branch) is covered by `test_s2_a_malformed_findings_list_stops_the_walk_whichever_session_posted_it` and the updated `test_raised_by_2313.py` R2 test, not probed.
