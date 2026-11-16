# Bite-proof record: i2554_bounded_pass_record

Issue 2554, layer 3, order L3-B: the bounded pass in the record, the session adapter and the sheet. Seven guarded
elements, each neutralized by one targeted edit, shown red with the detector run alone (one node), restored by the
inverse edit, and shown green. Every command is
`scripts/pinned-python -B -X pycache_prefix=/tmp/wt2497-pyc -m pytest <node> -q -n auto` from the worktree.
Nothing was redacted: the captures hold no secret, token, private URL or personal detail (the temp paths are the
sandbox's pytest directories). Each capture is under 32 KiB; the whole record is under 128 KiB.

Restore receipt for every element: the inverse edit and the restored line(s) quoted back from the file, plus one
`git status --porcelain` over the four neutralized lib paths, run once after the last restore (at the end of the
record). The test-file neutralization (E-census) is quoted back as well; the test file is a new, untracked file, so
`git status` cannot show its restore.

## E-audited: the line names an audit only for an audited round

- Guarded element: `review_record.py` `_bounded_pass_line`, the line `listed, audited = bounded.get("rounds") or [], bounded.get("auditedRounds") or []`. Axis: "audited in round N" and "not audited" read from `auditedRounds`, never from the listed rounds.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_line_names_an_audit_only_for_an_audited_round`
- Neutralization: the line ignores `auditedRounds`: `listed, audited = bounded.get("rounds") or [], bounded.get("rounds") or []`

Raw red (3 failed, 5 passed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

....FFF.                                                                 [100%]
=================================== FAILURES ===================================
_ test_the_line_names_an_audit_only_for_an_audited_round[cap-handed-back-before-b1-audit] _
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpX4e0z9/bin/python

trigger = 'round-cap', rounds = [5], audited = [], cap = 4
expected = "Bounded pass: handed back before the cap round's fixes were audited; round 5 is not counted in the 4 rounds."

    (the parametrize decorator: eight (trigger, rounds, audited, cap, expected) rows, elided here; see the test file)
    def test_the_line_names_an_audit_only_for_an_audited_round(trigger, rounds, audited, cap, expected):
        # axis: the line says "audited in round N" only for a round in `auditedRounds`, and "not counted" only for a
        # round-cap pass — see bite-proof record i2554_bounded_pass_record (E-audited)
        line = _line(trigger, rounds, audited, cap)
>       assert line == expected
E       AssertionError: assert 'Bounded pass...the 4 rounds.' == 'Bounded pass...the 4 rounds.'
E         
E         - Bounded pass: handed back before the cap round's fixes were audited; round 5 is not counted in the 4 rounds.
E         ?               -------------------                                  ^
E         + Bounded pass: the cap round's fixes were audited in round 5; round 5 is not counted in the 4 rounds.
E         ?                                                 ^^^        +++++++++

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:254: AssertionError
__ test_the_line_names_an_audit_only_for_an_audited_round[cap-b2-not-audited] __
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpX4e0z9/bin/python

trigger = 'round-cap', rounds = [5, 6], audited = [5]
expected = "Bounded pass: the cap round's fixes were audited in round 5, then one bounded fix was made and not audited; rounds 5 and 6 are not counted in the 4 rounds."

    (decorator and function body as above)
>       assert line == expected
E       AssertionError: assert 'Bounded pass...the 4 rounds.' == 'Bounded pass...the 4 rounds.'
E         
E         Skipping 85 identical leading characters in diff, use -v to show
E         -  made and not audited; rounds 5 and 6 are not counted in the 4 rounds.
E         ?          ----
E         +  made and audited in round 6; rounds 5 and 6 are not counted in the 4 rounds.
E         ?                  +++++++++++

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:254: AssertionError
__ test_the_line_names_an_audit_only_for_an_audited_round[stall-not-audited] ___
[gw3] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpX4e0z9/bin/python

trigger = 'fix-keeps-failing', rounds = [4], audited = [], cap = 7
expected = 'Bounded pass: a fix that kept failing got one more bounded fix, which was not audited.'

    (decorator and function body as above)
>       assert line == expected
E       AssertionError: assert 'Bounded pass...d in round 4.' == 'Bounded pass... not audited.'
E         
E         Skipping 54 identical leading characters in diff, use -v to show
E         - nded fix, which was not audited.
E         + nded fix, audited in round 4.

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:254: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_line_names_an_audit_only_for_an_audited_round[cap-handed-back-before-b1-audit]
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_line_names_an_audit_only_for_an_audited_round[cap-b2-not-audited]
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_line_names_an_audit_only_for_an_audited_round[stall-not-audited]
3 failed, 5 passed in 1.66s
```

The two `(decorator and function body as above)` lines and the one `(the parametrize decorator ...)` line replace the
test's source lines that pytest echoed (the eight-row parametrize decorator, about 20 lines, three times); every
other line is verbatim.

- Restore: the inverse edit. Restored line, quoted from `review_record.py` line 2859: `    listed, audited = bounded.get("rounds") or [], bounded.get("auditedRounds") or []`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

........                                                                 [100%]
8 passed in 2.76s
```

## E-count: a fix-keeps-failing pass's rounds count

- Guarded element: `review_record_session.py` `account_from_session`, the `post_cap` set. Axis: only a pass round above `maxRounds` is left out of `rounds.count`.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_a_fix_keeps_failing_pass_counts_every_one_of_its_rounds`
- Neutralization: leave every listed round out, as before: `post_cap = {str(n) for n in bounded_rounds if _int(n)}` in place of the two-line set comprehension with the `n > cap_n` condition.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_fix_keeps_failing_pass_counts_every_one_of_its_rounds _________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpNj6dix/bin/python

account_of = <function account_of.<locals>.<lambda> at 0x7f99c8f344a0>
stall = ('/tmp/claude-0/pytest-of-root/pytest-73/popen-gw0/run0/session', {'_auditOutcome': {'ambiguous': [], 'attributedChang...'newsurf.py'], 'raisedHead': None}, 'citationFresh': False, ...}], '_changedSubjects': ['Code'], '_coverage': [], ...})

    def test_a_fix_keeps_failing_pass_counts_every_one_of_its_rounds(account_of, stall):
        # axis: a stall pass's rounds are at or below the cap and are real rounds, so they count — see bite-proof record
        # i2554_bounded_pass_record (E-count)
        state = stall[1]
        pass_round = state["boundedPass"]["rounds"][0]
        assert state["boundedPass"]["trigger"] == "fix-keeps-failing" and pass_round <= RD._round_cap(state["config"])
        account = account_of(state)
>       assert account["rounds"]["count"] == len(state["rounds"]) == pass_round
E       AssertionError: assert 5 == 6
E        +  where 6 = len({'1': {'authorJustifiedDrops': [], 'blockingCount': 1, 'compileDrops': [], 'earlierFindingsUnavailable': 'not-supplied...'classKey': '::::late', 'dimension': None, 'file': 'newsurf.py', ...}], 'fix': {'commits': [], 'fixes': []}, ...}, ...})

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_a_fix_keeps_failing_pass_counts_every_one_of_its_rounds
1 failed in 3.05s
```

- Restore: the inverse edit. Restored lines, quoted from `review_record_session.py` lines 1746-1747:
  `    post_cap = {str(n) for n in bounded_rounds`
  `                if _int(n) and (n > cap_n if cap_n is not None else bounded.get("trigger") == "round-cap")}`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.59s
```

## E-evidence: the adapter carries the evidence

- Guarded element: `review_record_session.py` `_findings_and_merges`, the copy of the representative row's `boundedPassEvidence` onto the record finding. Axis: a left-for-owner finding the pass settled carries the pass's evidence into the record.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_adapter_carries_the_evidence_of_a_finding_the_pass_left_for_the_owner`
- Neutralization: drop the copy: the line `held[sc.BOUNDED_PASS_EVIDENCE_FIELD] = copy.deepcopy(rep[sc.BOUNDED_PASS_EVIDENCE_FIELD])` replaced by `pass`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_adapter_carries_the_evidence_of_a_finding_the_pass_left_for_the_owner _
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmp05R8Zs/bin/python

account_of = <function account_of.<locals>.<lambda> at 0x7f66759ec4a0>
card_session = ('/tmp/claude-0/pytest-of-root/pytest-75/popen-gw0/run0/session', {'_auditOutcome': {'ambiguous': [], 'attributedChang...'newsurf.py'], 'raisedHead': None}, 'citationFresh': False, ...}], '_changedSubjects': ['Code'], '_coverage': [], ...})

    def test_the_adapter_carries_the_evidence_of_a_finding_the_pass_left_for_the_owner(account_of, card_session):
        # axis: a left-for-owner finding the pass settled carries its representative row's evidence into the record,
        # end to end from a converged B2 session — see bite-proof record i2554_bounded_pass_record (E-evidence)
        _d, state = card_session
        ledger = B2._fixed_row(state)
        account = account_of(state)
        row = next(f for f in account["findings"] if f["title"] == "open-important")
        assert row["outcome"] == "left-for-owner" and row["openAtLoopEnd"] is True
>       assert row["boundedPassEvidence"] == ledger["boundedPassEvidence"]
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'boundedPassEvidence'

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:284: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_adapter_carries_the_evidence_of_a_finding_the_pass_left_for_the_owner
1 failed in 1.32s
```

- Restore: the inverse edit. Restored line, quoted from `review_record_session.py` line 1177: `            held[sc.BOUNDED_PASS_EVIDENCE_FIELD] = copy.deepcopy(rep[sc.BOUNDED_PASS_EVIDENCE_FIELD])`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.34s
```

## E-evidence-shape: the validator refuses a wrong evidence shape

- Guarded element: `review_record.py` `_bounded_evidence_ok` (called from `_validate`). Axis: the evidence is exactly one of the two shapes the driver writes.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_validator_refuses_evidence_that_is_not_one_of_the_two_shapes[audit-int-reason]` (the representative of the twenty wrong-shape rows; every row is red under this neutralization by construction, since the function then accepts all values)
- Neutralization: accept any value: `    return True` inserted as the first statement of `_bounded_evidence_ok`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_validator_refuses_evidence_that_is_not_one_of_the_two_shapes[audit-int-reason] _
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmp9uidSk/bin/python

evidence = {'fixCommit': 'abc1234def', 'audit': {'ruling': 'not-discharged', 'reasonKind': 'wrong', 'reason': 7}}

    (the twenty-row parametrize decorator, elided here; see the test file)
    def test_the_validator_refuses_evidence_that_is_not_one_of_the_two_shapes(evidence):
        # axis: the evidence is exactly one of the two shapes the driver writes, never another value — see bite-proof
        # record i2554_bounded_pass_record (E-evidence-shape)
>       with pytest.raises(RR.Refusal) as refused:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:355: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_validator_refuses_evidence_that_is_not_one_of_the_two_shapes[audit-int-reason]
1 failed in 0.83s
```

- Restore: the inverse edit (the inserted `return True` line removed). Restored lines, quoted from `review_record.py` lines 714-721:
  `def _bounded_evidence_ok(v):` ... `    if not isinstance(v, dict):` / `        return False` / `    if set(v) == {"fixCommit", "raisedByFinalAudit"}:` / `        return v["fixCommit"] is None and v["raisedByFinalAudit"] is True`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 0.77s
```

## E-card: the card renders the evidence

- Guarded element: `pr_sheet.py` `build`, the `*_loop_tried(words, f)` entry in a leftover card's context. Axis: a card whose record finding carries evidence gets the "What the loop tried" section, from the record alone.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_card_renders_the_evidence_from_the_record[commit-and-reason]` (the representative of the seven rows; the section is absent for every evidence row under this neutralization)
- Neutralization: omit the section: the line `*_loop_tried(words, f),` removed from the card's context list.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
____ test_the_card_renders_the_evidence_from_the_record[commit-and-reason] _____
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmp3Wj6wz/bin/python

evidence = {'fixCommit': 'abc1234def5678', 'audit': {'ruling': 'not-discharged', 'reasonKind': 'wrong', 'reason': 'still broken'}}
sentence = 'The loop tried one bounded fix at abc1234; its audit said: still broken'

    (the seven-row parametrize decorator, elided here; see the test file)
    def test_the_card_renders_the_evidence_from_the_record(evidence, sentence):
        # axis: a leftover card whose record finding carries evidence gets a "What the loop tried" section after "What
        # happened", rendered from the record alone; a null or blank reason drops only the audit clause — see bite-proof
        # record i2554_bounded_pass_record (E-card)
        card, sheet = _card(evidence)
>       assert _tried(card) == [[{"paragraph": sentence}]]
E       AssertionError: assert [] == [[{'paragraph...ill broken'}]]
E         
E         Right contains one more item: [{'paragraph': 'The loop tried one bounded fix at abc1234; its audit said: still broken'}]
E         Use -v to get more diff

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:419: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_card_renders_the_evidence_from_the_record[commit-and-reason]
1 failed in 0.92s
```

- Restore: the inverse edit (the line put back after the axis comment). Restored lines, quoted from `pr_sheet.py` lines 1456-1458:
  `                                # axis: the card shows what the bounded pass tried from the record finding's evidence, never from the advisor's text — see bite-proof record i2554_bounded_pass_record (E-card)`
  `                                *_loop_tried(words, f),`
  `                                _section(words["ifLeft"], "paragraph", call.get("ifLeft", f["consequence"]))],`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 0.84s
```

## E-census: the census fails on an unlisted reader

- Guarded element: the test file's `READERS` counter and `test_the_census_finds_exactly_the_listed_readers_of_the_converged_terminal`. Axis: the census equals the listed readers in both directions, so a reader the code holds and the list lacks, or a name the list holds and the code lacks, fails it.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_census_finds_exactly_the_listed_readers_of_the_converged_terminal`
- Neutralization: add a fifth reader name to the listed set: `    ("decision_kinds.py", "a_fifth_reader"),` appended to `READERS`. (The order names the edit as adding a name to the listed set; the other direction, a new comparison in a lib module, is outside this order's surface, and is covered by `test_the_census_sees_every_comparison_form` for the scan itself.)

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
__ test_the_census_finds_exactly_the_listed_readers_of_the_converged_terminal __
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpM0Rm0M/bin/python

    def test_the_census_finds_exactly_the_listed_readers_of_the_converged_terminal():
        # axis: a new reader of `converged`, in any of the four comparison forms, fails this census until it is added with a
        # behaviour test below — see bite-proof record i2554_bounded_pass_record (E-census)
>       assert _converged_readers() == READERS
E       AssertionError: assert Counter({('de...overage'): 1}) == Counter({('de..._reader'): 1})
E         
E         Omitting 7 identical items, use -vv to show
E         Right contains 1 more item:
E         {('decision_kinds.py', 'a_fifth_reader'): 1}
E         Use -v to get more diff

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:497: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_the_census_finds_exactly_the_listed_readers_of_the_converged_terminal
1 failed in 2.30s
```

- Restore: the inverse edit (the appended line removed). Restored lines, quoted from the test file lines 489-490: `    ("round_driver.py", "_validate_rounds_lens_coverage"),` / `])`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 2.44s
```

## E-record-facts: vet 972 M2, the commits-only test goes red on the head-diff signal alone

- Guarded element: `round_driver.py` `_bounded_pass_applies`, the last line. Axis: the pass begins on the cap round's record facts (fixes, fix commits, a changed PR-body fix) as well as on a head diff that changed. The test's world leaves the cap round's head diff equal to its reviewed diff (`_headf_ns(CAP - 1)`), the commit in the fix record only; it asserts the head stayed put before the session runs on.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_b1_2552.py::test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass`
- Neutralization (the one allowed edit to `round_driver.py`): narrow the last line to the head-diff signal: `    return bool(_head_diff_changed(state))` in place of `    return bool(_round_applied_work(state["rounds"][str(cap)]) or _head_diff_changed(state))`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass _
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmppByq2U/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-83/popen-gw1/test_t10_a_cap_round_that_comm0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ff8c6913650>

    def test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass(tmp_path, monkeypatch):
        (the test's comment block, as in the file)
        real = RD._apply_fixes_commit_fault

        def committed_in_the_cap_round(state, config, artifact, commit_seam=None):
            if state.get("round") == CAP:
                return None, [{"finding": "open-important", "commit": "abc1234"}]
            return real(state, config, artifact, commit_seam=commit_seam)

        base = X._respond(cap=CAP)

        def head_stays_put(phase, payload, rnd):
            answer = base(phase, payload, rnd)
            if phase == RD.P_APPLY_FIXES and rnd == CAP:
                answer = dict(answer, headDiff=TRD._headf_ns(CAP - 1))
            return answer

        monkeypatch.setattr(RD, "_apply_fixes_commit_fault", committed_in_the_cap_round)
        d = _at_cap_verify(tmp_path, head_stays_put)  # the cap round's fix folded, its gate not yet answered
        before = X._state(d)
        assert before["headDiff"] == before["reviewedDiff"] and RD._head_diff_changed(before) is False, "the head stayed put"
        n, trace = _run(d, None, head_stays_put, stop=lambda n: n["round"] > CAP)
        state = X._state(d)
        cap_fix = state["rounds"][str(CAP)]["fix"]
        assert cap_fix["fixes"] == [] and cap_fix["commits"], cap_fix
>       assert (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 1), trace
E       AssertionError: [('run-verify', 2), ('terminal', 2)]
E       assert ('terminal', 2) == ('dispatch-audits', 3)
E         
E         At index 0 diff: 'terminal' != 'dispatch-audits'
E         Use -v to get more diff

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_b1_2552.py:695: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_b1_2552.py::test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass
1 failed in 1.26s
```

(The `(the test's comment block, as in the file)` line replaces the nine comment lines pytest echoed; the indentation of
the echoed source is normalized in this record; every other line is as pytest printed it.)

- Restore: the inverse edit. Restored line, quoted from `round_driver.py` line 10538: `    return bool(_round_applied_work(state["rounds"][str(cap)]) or _head_diff_changed(state))`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.27s
```

## Post-restore status

`git -C /home/user/wt-2497 status --porcelain -- plugins/superheroes/lib/round_driver.py plugins/superheroes/lib/review_record.py plugins/superheroes/lib/review_record_session.py plugins/superheroes/lib/pr_sheet.py`, run once after the last restore, printed:

```
 M plugins/superheroes/lib/pr_sheet.py
 M plugins/superheroes/lib/review_record.py
 M plugins/superheroes/lib/review_record_session.py
```

`round_driver.py` is not listed: the one allowed edit to it was undone, and it is byte-identical to the commit. The
three listed files are modified by this order's own changes; the supplementary check shows no other path was touched.

Not a declared element: the stale strip of `boundedPassEvidence` in `review_record._drop_stale_open_marker` and the
`findings[i].boundedPassEvidence` refusal of a non-left-for-owner outcome have their own tests
(`test_a_finding_the_owner_later_decides_is_written_without_the_evidence`,
`test_the_validator_refuses_evidence_on_a_finding_that_is_not_left_for_the_owner`) and no neutralization run here, as
the order declared exactly the seven elements above. They are unproven by a red run.
