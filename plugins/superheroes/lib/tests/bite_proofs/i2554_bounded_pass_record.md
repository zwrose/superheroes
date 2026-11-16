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

## Order L3-C: three more elements

Issue 2554, layer 3, order L3-C. Three guarded elements, each neutralized by one targeted edit, shown red with the
detector run alone (one node), restored by the inverse edit, and shown green. Commands are
`scripts/pinned-python -B -X pycache_prefix=/tmp/wt2497-pyc -m pytest <node> -q -n auto` from the worktree. Nothing
was redacted; the captures hold no secret, token, private URL or personal detail.

## E-stall-record: the validator accepts an empty-`rounds` stall pass

- Guarded element: `review_record.py` `_validate`, the `rounds.boundedPass` check, the clause `(bool(bounded["rounds"]) or bounded["trigger"] == "fix-keeps-failing")`. Axis: `rounds` may be empty only for a `fix-keeps-failing` trigger.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_a_stall_pass_handed_back_before_its_audit_round_is_a_recordable_session_and_not_a_stop_at_the_cap`
- Neutralization: restore the requirement for every trigger: `            and bool(bounded["rounds"])` in place of `            and (bool(bounded["rounds"]) or bounded["trigger"] == "fix-keeps-failing")  # a stall pass may hand back before its audit round`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_stall_pass_handed_back_before_its_audit_round_is_a_recordable_session_and_not_a_stop_at_the_cap _
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpPrjzSF/bin/python

account_of = <function account_of.<locals>.<lambda> at 0x7f02595ef7e0>
stall_handed_back_early = ('/tmp/claude-0/pytest-of-root/pytest-87/popen-gw0/run0/session', {'_auditOutcome': {'ambiguous': [], 'attributedChang...'newsurf.py'], 'raisedHead': None}, 'citationFresh': False, ...}], '_changedSubjects': ['Code'], '_coverage': [], ...})

    def test_a_stall_pass_handed_back_before_its_audit_round_is_a_recordable_session_and_not_a_stop_at_the_cap(
            account_of, stall_handed_back_early):
        # axis: a stall pass that lists no round validates, and its `bounded-pass-open` is not a stop at the cap — see
        # bite-proof record i2554_bounded_pass_record (E-stall-record, E-stall-cap)
        state = stall_handed_back_early[1]
        assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
        assert state["boundedPass"]["trigger"] == "fix-keeps-failing" and state["boundedPass"]["rounds"] == []
        account = account_of(state)
>       RR._validate(account)

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:203: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2497/plugins/superheroes/lib/review_record.py:1083: in _validate
    chk(isinstance(bounded, dict) and set(bounded) == {"trigger", "rounds", "auditedRounds"}
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

ok = False, key = 'rounds.boundedPass'

    def chk(ok, key):
        if not ok:
>           raise Refusal("review-account-invalid", key)
E           review_record.Refusal: ('review-account-invalid', 'rounds.boundedPass')

/home/user/wt-2497/plugins/superheroes/lib/review_record.py:929: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_a_stall_pass_handed_back_before_its_audit_round_is_a_recordable_session_and_not_a_stop_at_the_cap
1 failed in 1.47s
```

- Restore: the inverse edit. Restored lines, quoted from `review_record.py` lines 1085-1086:
  `            and isinstance(bounded["rounds"], list)`
  `            and (bool(bounded["rounds"]) or bounded["trigger"] == "fix-keeps-failing")  # a stall pass may hand back before its audit round`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 3.78s
```

## E-stall-cap: a stall pass's `bounded-pass-open` is not a stop at the cap

- Guarded element: `review_record_session.py` `account_from_session`, the `capped` test for a `handed-back` terminal. Axis: a `bounded-pass-open` is a stop at the cap only when the state's `boundedPass.trigger` is `round-cap`.
- Detector (node): `plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_a_bounded_pass_open_hand_back_stops_at_the_cap_only_for_a_round_cap_pass[fix-keeps-failing]` (the end-to-end test of E-stall-record holds the same assertion on a driven session; it was not run under this neutralization)
- Neutralization: count every `bounded-pass-open` as at the cap: `            capped = last.get("kind") in _HANDED_BACK_AT_CAP` in place of the two-line `capped = last.get("kind") in _HANDED_BACK_AT_CAP and (...)`.

Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_bounded_pass_open_hand_back_stops_at_the_cap_only_for_a_round_cap_pass[fix-keeps-failing] _
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmp4yGjBc/bin/python

account_of = <function account_of.<locals>.<lambda> at 0x7fac291ebce0>
b1_b2 = ('/tmp/claude-0/pytest-of-root/pytest-89/popen-gw0/run0/session', {'_auditOutcome': {'ambiguous': [], 'attributedChang...'newsurf.py'], 'raisedHead': None}, 'citationFresh': False, ...}], '_changedSubjects': ['Code'], '_coverage': [], ...})
pass_state = {'trigger': 'fix-keeps-failing', 'rounds': [], 'step': 'done'}
expected = False

    @pytest.mark.parametrize("pass_state,expected", [
        ({"trigger": "round-cap", "rounds": [CAP + 1], "step": "done"}, True),
        ({"trigger": "fix-keeps-failing", "rounds": [], "step": "done"}, False),
        (None, False),
        ("unreadable", False),
    ], ids=["round-cap", "fix-keeps-failing", "no-bounded-pass", "unreadable-bounded-pass"])
    def test_a_bounded_pass_open_hand_back_stops_at_the_cap_only_for_a_round_cap_pass(account_of, b1_b2, pass_state, expected):
        # axis: see E-stall-cap above
        state = copy.deepcopy(b1_b2[1])
        state["terminal"] = "handed-back"
        state["decisions"] = [*state["decisions"], {"kind": "bounded-pass-open", "detail": "x"}]
        state.pop("boundedPass", None)
        if pass_state is not None:
            state["boundedPass"] = pass_state
>       assert account_of(state)["rounds"]["stoppedAtCap"] is expected
E       assert True is False

/home/user/wt-2497/plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py:224: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_bounded_pass_record_2554.py::test_a_bounded_pass_open_hand_back_stops_at_the_cap_only_for_a_round_cap_pass[fix-keeps-failing]
1 failed in 1.96s
```

- Restore: the inverse edit. Restored lines, quoted from `review_record_session.py` lines 1730-1731:
  `            capped = last.get("kind") in _HANDED_BACK_AT_CAP and (`
  `                last.get("kind") != "bounded-pass-open" or bool(bounded and bounded.get("trigger") == "round-cap"))`

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.43s
```

## E-no-read: the no-read test fails on a read of the order

- Guarded element: `test_extra_audit_retired_2553.py::test_a_the_order_file_is_never_read`, the audit hook `_watch_opens` and the assertion `os.path.abspath(order) not in _OPENED`. Axis: the retired verb never opens the order file, so the test fails when the verb opens it and then refuses.
- Detector (node): `plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py::test_a_the_order_file_is_never_read[valid-order]` (the other two rows, `missing-order` and `garbage-order`, share the hook and the assertion; they were not run under the neutralization). The red and green runs name the cheapest node of `test_bounded_pass_record_2554.py` ahead of it (see the collection note below), so each reads `1 failed, 1 passed` and `2 passed`; the extra node is `test_a_record_with_no_bounded_pass_has_no_line`, which neither edit touches.
- Neutralization (the one allowed edit to `round_driver.py`): `cmd_extra_audit` opens and reads the order file, then refuses as before. Inserted before the `if isinstance(session_dir, str)` line:
  `    try:`
  `        with open(order_file, "rb") as _neutralized:`
  `            _neutralized.read()`
  `    except OSError:`
  `        pass`

Collection note. The first red attempt ran the node alone, as `pytest "plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py::test_a_the_order_file_is_never_read[valid-order]" -q -n auto`, and failed at collection, before any test ran, with the circular import below. It does not depend on the neutralization: `test_extra_audit_retired_2553.py` imports `test_c1l4b_extra_audit`, which imports `test_outcome_settle_c7`, which imports `test_bounded_pass_b1_2552`, which reads `X.CAP` while `test_c1l4b_extra_audit` is still half-loaded. The file collects when another test module that imports `test_bounded_pass_b1_2552` first is collected before it, as in the two-file run of the order's own command. This is a collection-order fault of the existing test imports, not changed by this order, and is reported, not fixed. Verbatim (the one blank-line pair after "bringing up nodes..." is as printed; the traceback block repeats four times, once per worker collection, and only its first copy is quoted here, the other three being identical):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...


==================================== ERRORS ====================================
_ ERROR collecting plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py _
plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py:27: in <module>
    import test_c1l4b_extra_audit as X  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/root/.cache/uv/archive-v0/FC8IoDv-bc0inE0a/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:185: in exec_module
    exec(co, module.__dict__)
plugins/superheroes/lib/tests/test_c1l4b_extra_audit.py:29: in <module>
    import test_outcome_settle_c7 as TOC  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/root/.cache/uv/archive-v0/FC8IoDv-bc0inE0a/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:185: in exec_module
    exec(co, module.__dict__)
plugins/superheroes/lib/tests/test_outcome_settle_c7.py:29: in <module>
    import test_bounded_pass_b1_2552 as B1  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/root/.cache/uv/archive-v0/FC8IoDv-bc0inE0a/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:185: in exec_module
    exec(co, module.__dict__)
plugins/superheroes/lib/tests/test_bounded_pass_b1_2552.py:33: in <module>
    CAP = X.CAP
          ^^^^^
E   AttributeError: partially initialized module 'test_c1l4b_extra_audit' has no attribute 'CAP' (most likely due to a circular import)
=========================== short test summary info ============================
ERROR plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py - Attrib...
ERROR plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py - Attrib...
ERROR plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py - Attrib...
ERROR plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py - Attrib...
4 errors in 0.90s
```

Raw red (the re-issued command, with the record file's node first):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

.F                                                                       [100%]
=================================== FAILURES ===================================
_______________ test_a_the_order_file_is_never_read[valid-order] _______________
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpoxfEna/bin/python

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-92/popen-gw0/test_a_the_order_file_is_never0')
make = 'valid-order'

    @pytest.mark.parametrize("make", ["missing-order", "garbage-order", "valid-order"])
    def test_a_the_order_file_is_never_read(tmp_path, make):
        # axis: the retired verb never opens the order file, so it fails when the verb opens it and then refuses — see
        # bite-proof record i2554_bounded_pass_record (E-no-read)
        global _WATCHING
        d = X._capped(tmp_path)
        order = str(tmp_path / "order.json")
        if make == "garbage-order":
            with open(order, "w", encoding="utf-8") as fh:
                fh.write("{why")
        elif make == "valid-order":
            with open(order, "w", encoding="utf-8") as fh:
                json.dump({"why": WHY}, fh)
        files, rows, raw = _snapshot(d), RD.read_journal(d), _journal(d)
        del _OPENED[:]
        _WATCHING = True
        try:
            out = RD.cmd_extra_audit(d, order, "advisor", PR, readers=READERS)
        finally:
            _WATCHING = False
>       assert os.path.abspath(order) not in _OPENED, "the verb opened the order file"
E       AssertionError: the verb opened the order file
E       assert '/tmp/claude-0/pytest-of-root/pytest-92/popen-gw0/test_a_the_order_file_is_never0/order.json' not in ['/tmp/claude-0/pytest-of-root/pytest-92/popen-gw0/test_a_the_order_file_is_never0/order.json', '/tmp/claude-0/pytest-...json', '/tmp/claude-0/pytest-of-root/pytest-92/popen-gw0/test_a_the_order_file_is_never0/session/driver-journal.jsonl']
E        +  where '/tmp/claude-0/pytest-of-root/pytest-92/popen-gw0/test_a_the_order_file_is_never0/order.json' = <function abspath at 0x7f77716154e0>('/tmp/claude-0/pytest-of-root/pytest-92/popen-gw0/test_a_the_order_file_is_never0/order.json')
E        +    where <function abspath at 0x7f77716154e0> = <module 'posixpath' (frozen)>.abspath
E        +      where <module 'posixpath' (frozen)> = os.path

/home/user/wt-2497/plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py:129: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_extra_audit_retired_2553.py::test_a_the_order_file_is_never_read[valid-order]
1 failed, 1 passed in 1.19s
```

- Restore: the inverse edit (the five inserted lines removed). Restored lines, quoted from `round_driver.py` `cmd_extra_audit`:
  `    row of a refusal, and only when the session folder exists."""`
  `    if isinstance(session_dir, str) and os.path.isdir(session_dir):`
- Restore receipt: `git status --porcelain -- plugins/superheroes/lib/round_driver.py plugins/superheroes/lib/review_record.py plugins/superheroes/lib/review_record_session.py`, run after the restore, printed ` M plugins/superheroes/lib/review_record.py` and ` M plugins/superheroes/lib/review_record_session.py` and no line for `round_driver.py`: it is byte-identical to the commit.

Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 1.35s
```

Not declared elements of order L3-C, with no neutralization run: the `round-cap-no-rounds` row of the refusal test and the `stall-no-rounds` acceptance row (they guard the two halves of the validator clause; the E-stall-record neutralization above is red for the second half only), and the `no-bounded-pass` and `unreadable-bounded-pass` adapter rows (the `bounded and` guard). They are unproven by a red run.

## Post-restore status

`git -C /home/user/wt-2497 status --porcelain -- plugins/superheroes/lib/round_driver.py plugins/superheroes/lib/review_record.py plugins/superheroes/lib/review_record_session.py plugins/superheroes/lib/pr_sheet.py`, run once after the last restore of order L3-B, printed:

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
