# Bite-proof record: the audit breaker counts a wrong fix, never an unanswered or reopened one (#2495)

Detector: `plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py` (112 tests collected), unedited. Declared
guarded-element set: G1 to G10 (one neutralization, one red and one green per element). Every neutralization was one
targeted `Edit` on the build tree and was undone by the inverse `Edit`; no `git checkout`, `restore`, `reset` or `stash`
was used. Each red and each green is a single test node id (never `-k`), run as
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2495c -m pytest "<node id>" -q -p no:cacheprovider`.
The `warning: The UV_NATIVE_TLS ...` line the launcher prints before every run is elided from every capture below. The
red captures are the failure bodies as printed, except that the `short test summary info` banner and blank lines are
dropped; the `@pytest.mark.parametrize` decorator line is kept where the test has one. Nothing below is redacted: the
captures hold no secret, token or private URL.

Baseline: the order states the file was verified green at `087bd889` by the orchestrator. This dispatch did not run the
whole file (the command budget did not allow it); its only evidence of the un-neutralized tree is the ten single-node
greens below, each taken after its restore. `--collect-only -q` reported `112 tests collected`.

Restore receipt for every element: the restored line quoted under each element (from one `Grep` of the four source
files after the last restore, with line numbers), and one `git diff --stat HEAD` taken after G10's restore, which printed
nothing (no tracked file differs from `087bd889`; this record is the only new, untracked path):

```
$ git diff --stat HEAD
(Bash completed with no output)
```

Equivalence classes (G4 and G5 only; G1 to G3 and G6 to G10 each have their own neutralization and red):

- Class `unanswered-arm-missing-kind`: "an unanswered arm missing its kind counts as a strike". Representative: G4,
  `_fold_checks_fault`. Members, by census row (the 14 `UNANSWERED` rows of `CENSUS`):
  `_fold_silence: silence` (S02_silence_unaudited), `_fold_silence: duplicate target id`
  (T1_duplicate_target_without_a_result), `_fold_silence: ambiguous id` (S03_silence_ambiguous_result_id),
  `_fold_duplicate_target` (S04_duplicate_target_with_a_result), `_reject_unauthenticated: no auditor recorded`
  (S06_provenance_no_auditor_recorded), `_reject_unauthenticated: manifest entry missing`
  (S07_provenance_manifest_entry_missing), `_reject_unauthenticated: vendor mismatch`
  (S08_provenance_manifest_vendor_mismatch), `_fold_checks_fault` (S11_three_checks_fault, the representative),
  `_fold_malformed_unnamed: not a string` (S18_unnamed_change_not_a_string), `_fold_malformed_unnamed: seq not an int`
  (S19_unnamed_change_seq_not_an_int), `_fold_malformed_unnamed: claim fault` (S20_claim_fault),
  `_fold_discharged: reasonless` (S24_discharged_with_no_reason), `_fold_discharged_new_issue: no usable newIssues`
  (S27_new_issue_no_usable_candidates), `_fold_unrecognized` (S29_unknown_ruling).
- Class `wrong-arm-mislabelled-unanswered`: "a wrong arm mislabelled unanswered stops counting". Representative: G5,
  `_fold_failed_check`. Members, by census row (the 8 `WRONG` rows of `CENSUS`): `_fold_not_discharged`
  (S28_not_discharged_by_selected_auditor), `_fold_blocking_test` (S10_blocking_break_it_match_keeps_new_issues),
  `_fold_weakened_test` (S13_weakened_explained_test_precedes_places), `_fold_incomplete_places`
  (S14_incomplete_places_with_unnamed_change), `_fold_failed_check` (S15_failed_check, the representative),
  `_review_guard refusal` (S16_review_guarded_refused), `refuse_unnamed_change: discharged`
  (S21b_discharged_unnamed_change_forbidden_refused), `refuse_unnamed_change: new issue`
  (S25b_new_issue_unnamed_change_forbidden_refused).
- Disclosed limit of the grouping: only the two representatives were neutralized. The other 20 census rows share a
  failure mode with their representative and each is asserted by its own parametrisation of the same test, but no
  neutralization was run on their own lines, so their individual bite is not proven by this record. The separate node
  `test_census_the_test_removal_guard_refusal_is_wrong` is outside `CENSUS` and was not neutralized either.

## G1. `_round_not_discharged_findings` skips an unanswered or reopened-merged outcome

- Element: `plugins/superheroes/lib/circuit_breaker.py` `_round_not_discharged_findings`, the
  `if isinstance(kind, str) and kind in NON_STRIKE_REASON_KINDS: continue` skip. Axis: an `unanswered` or
  `reopened-merged` outcome never counts toward the stall.
- Neutralization: the `continue` under that `if` replaced with `pass` (the skip then does nothing).
- Red (node `test_two_unanswered_rounds_do_not_halt`, 1 failed):
  ```
  def test_two_unanswered_rounds_do_not_halt():
      # axis: an unanswered or reopened-merged outcome never counts toward the stall — see bite-proof record i2495_strike_kinds
      res = CB.check_audit_breaker(_kinded(UNANSWERED, UNANSWERED))
  >       assert res["halt"] is False and res["reason"] is None and res["stalledIdentities"] == []
  E       assert (True is False)

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:260: AssertionError
  FAILED plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py::test_two_unanswered_rounds_do_not_halt
  1 failed in 2.03s
  ```
- Restore: the inverse `Edit` put `continue` back in place of `pass`.
- Restore receipt (line quoted back):
  ```
  plugins/superheroes/lib/circuit_breaker.py:317:        if isinstance(kind, str) and kind in NON_STRIKE_REASON_KINDS:
  plugins/superheroes/lib/circuit_breaker.py:318:            continue
  ```
- Green: `1 passed in 2.14s`.

## G2. the same skip must not skip a `wrong` outcome

- Element: the same skip. Axis: a `wrong` outcome still counts toward the stall.
- Neutralization: the condition changed to
  `if isinstance(kind, str) and (kind in NON_STRIKE_REASON_KINDS or kind == "wrong"):` (the added clause parenthesized so
  it applies inside the `isinstance` guard, not as `A and B or C`).
- Red (node `test_two_wrong_rounds_still_halt_as_an_audit_stall`, 1 failed):
  ```
  def test_two_wrong_rounds_still_halt_as_an_audit_stall():
      # axis: a `wrong` outcome still counts toward the stall — see bite-proof record i2495_strike_kinds
      res = CB.check_audit_breaker(_kinded(WRONG, WRONG))
  >       assert res["halt"] is True and res["reason"] == "audit-stall"
  E       assert (False is True)

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:253: AssertionError
  FAILED plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py::test_two_wrong_rounds_still_halt_as_an_audit_stall
  1 failed in 2.08s
  ```
- Restore: the inverse `Edit` put the original condition back.
- Restore receipt: the same two lines quoted under G1 (`circuit_breaker.py:317` and `:318`), as of the single `Grep` taken after the last restore.
- Green: `1 passed in 2.08s`.

## G3. the same skip must not skip a missing kind (fail closed)

- Element: the same skip. Axis: a round with no `reasonKind` counts as a strike.
- Neutralization: the condition changed to
  `if (isinstance(kind, str) and kind in NON_STRIKE_REASON_KINDS) or kind is None:`.
- Red (node `test_a_round_with_no_reason_kind_counts_as_a_strike`, 1 failed):
  ```
  def test_a_round_with_no_reason_kind_counts_as_a_strike():
      # axis: a legacy outcome with no kind counts, so an old record cannot uncount into a silent pass — see bite-proof record i2495_strike_kinds
      rounds = [a_round(1, [nd(IDENT, id="t1")]), a_round(2, [nd(IDENT, id="t1")])]
  >       assert CB.check_audit_breaker(rounds)["halt"] is True
  E       assert False is True

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:276: AssertionError
  FAILED plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py::test_a_round_with_no_reason_kind_counts_as_a_strike
  1 failed in 2.08s
  ```
- Restore: the inverse `Edit` put the original condition back.
- Restore receipt: the same two lines quoted under G1 (`circuit_breaker.py:317` and `:318`).
- Green: `1 passed in 1.69s`.

## G4. `_fold_checks_fault` stamps `unanswered` (representative of the unanswered-arm class)

- Element: `plugins/superheroes/lib/audits.py` `_fold_checks_fault`. Axis: an arm that never answered carries `unanswered`.
- Neutralization: `reasonKind=REASON_KIND_UNANSWERED` dropped from its `base.update(...)`, leaving
  `base.update(ruling="not-discharged", reason="audit refused: %s" % checks_fault)`.
- Red (node `test_census_each_not_discharged_arm_carries_its_kind[S11_three_checks_fault]`, 1 failed):
  ```
  arm = '_fold_checks_fault', name = 'S11_three_checks_fault', kind = 'unanswered'

      @pytest.mark.parametrize("arm,name,kind", CENSUS, ids=[row[1] for row in CENSUS])
      def test_census_each_not_discharged_arm_carries_its_kind(arm, name, kind):
          out = CHAR._run(SCENARIOS[name])
          entries = [e for e in out["audits"] if e["ruling"] == "not-discharged"]
          assert entries, arm
  >       assert [e["reasonKind"] for e in entries] == [kind] * len(entries), arm
                  ^^^^^^^^^^^^^^^
  E       KeyError: 'reasonKind'

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:109: KeyError
  FAILED ...::test_census_each_not_discharged_arm_carries_its_kind[S11_three_checks_fault]
  1 failed in 2.17s
  ```
  (the test's own `# axis:` comment line is elided from this capture.)
- Restore: the inverse `Edit` put `reasonKind=REASON_KIND_UNANSWERED)` back on the continuation line.
- Restore receipt (line quoted back):
  ```
  plugins/superheroes/lib/audits.py:1065:                        reasonKind=REASON_KIND_UNANSWERED)
  ```
- Green: `1 passed in 1.89s`.

## G5. `_fold_failed_check` stamps `wrong` (representative of the wrong-arm class)

- Element: `plugins/superheroes/lib/audits.py` `_fold_failed_check`. Axis: an arm answered wrong carries `wrong`.
- Neutralization: `reasonKind=REASON_KIND_WRONG)` changed to `reasonKind=REASON_KIND_UNANSWERED)` in that arm.
- Red (node `test_census_each_not_discharged_arm_carries_its_kind[S15_failed_check]`, 1 failed):
  ```
  arm = '_fold_failed_check', name = 'S15_failed_check', kind = 'wrong'
  ...
  >       assert [e["reasonKind"] for e in entries] == [kind] * len(entries), arm
  E       AssertionError: _fold_failed_check
  E       assert ['unanswered'] == ['wrong']
  E         
  E         At index 0 diff: 'unanswered' != 'wrong'
  E         Use -v to get more diff

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:109: AssertionError
  FAILED ...::test_census_each_not_discharged_arm_carries_its_kind[S15_failed_check]
  1 failed in 1.89s
  ```
  (the `...` stands for the same test header and body lines quoted under G4, elided here.)
- Restore: the inverse `Edit` put `REASON_KIND_WRONG` back.
- Restore receipt (line quoted back):
  ```
  plugins/superheroes/lib/audits.py:1154:                        reasonKind=REASON_KIND_WRONG)
  ```
- Green: `1 passed in 1.84s`.

## G6. `_fold_discharged` holds a scope-only change as cleared with a note

- Element: `plugins/superheroes/lib/audits.py` `_fold_discharged`, the `elif scope_only:` branch calling
  `self.hold_scope(base, fid, unnamed_text)` (the one at line 1255, not the twin in `_fold_discharged_new_issue`).
  Axis: a scope-only hold reads cleared with a note.
- Neutralization: that call replaced with `self.refuse_unnamed_change(base, fid, unnamed_text, [])` followed on its own
  line by `return` (the order's one-line `...; return` written as two lines).
- Red (node `test_a_scope_only_hold_reads_cleared_with_a_scope_note[discharged]`, 1 failed):
  ```
  ruling = 'discharged'

      @pytest.mark.parametrize("ruling", CLEARS)
      def test_a_scope_only_hold_reads_cleared_with_a_scope_note(ruling):
          out = audits.apply_audit_results([CHAR._target("t1")], [_scope_result(ruling)])
          (entry,) = out["audits"]
  >       assert out["discharged"] == ["t1"] and out["scopeHeld"] == ["t1"]
  E       AssertionError: assert ([] == ['t1']
  E         
  E         Right contains one more item: 't1'
  E         Use -v to get more diff)

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:149: AssertionError
  FAILED ...::test_a_scope_only_hold_reads_cleared_with_a_scope_note[discharged]
  1 failed in 1.91s
  ```
  (the test's own `# axis:` comment line is elided.)
- Restore: the inverse `Edit` put `self.hold_scope(base, fid, unnamed_text)` back and removed the added `return`.
- Restore receipt (line quoted back; the twin call in `_fold_discharged_new_issue` is line 1294, untouched):
  ```
  plugins/superheroes/lib/audits.py:1255:                self.hold_scope(base, fid, unnamed_text)
  ```
- Green: `1 passed in 2.14s`.

## G7. `fold_target` computes `forbids_change` from the finding's own decision

- Element: `plugins/superheroes/lib/audits.py` `fold_target`, `forbids_change = isinstance(owner_ruling, dict) and owner_ruling.get("allowsChange") is False`.
  Axis: a change the finding's own decision forbids stays a refused, `wrong` fix.
- Neutralization: that line replaced with `forbids_change = False`.
- Red (node `test_a_change_the_findings_own_decision_forbids_is_refused_as_a_wrong_fix[discharged]`, 1 failed):
  ```
  ruling = 'discharged'

      @pytest.mark.parametrize("ruling", CLEARS)
      def test_a_change_the_findings_own_decision_forbids_is_refused_as_a_wrong_fix(ruling):
          target = CHAR._target("t1", ownerRuling=dict(FORBIDS))
          out = audits.apply_audit_results([target], [_scope_result(ruling)])
          (entry,) = out["audits"]
  >       assert out["discharged"] == [] and out["notDischarged"] == ["t1"] and out["scopeHeld"] == []
  E       AssertionError: assert (['t1'] == []
  E         
  E         Left contains one more item: 't1'
  E         Use -v to get more diff)

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:222: AssertionError
  FAILED ...::test_a_change_the_findings_own_decision_forbids_is_refused_as_a_wrong_fix[discharged]
  1 failed in 1.80s
  ```
  (the test's own `# axis:` comment line is elided.)
- Restore: the inverse `Edit` put the original expression back.
- Restore receipt (line quoted back):
  ```
  plugins/superheroes/lib/audits.py:933:        forbids_change = isinstance(owner_ruling, dict) and owner_ruling.get("allowsChange") is False
  ```
- Green: `1 passed in 1.72s`.

## G8. `_fold_merged_members` classifies the reopened member `reopened-merged`

- Element: `plugins/superheroes/lib/round_driver.py` `_fold_merged_members`, the reopened entry's
  `audits.AUDIT_REASON_KIND_FIELD: audits.REASON_KIND_REOPENED_MERGED` dict entry. Axis: a reopened member does not
  count toward the stall before its own fix is audited.
- Neutralization: that dict-entry line deleted (the entry before it and `"reopenedFrom": tid})` after it kept).
- Red (node `test_loop_c_a_merged_member_reopened_in_one_round_and_answered_wrong_in_the_next_does_not_stall`, 1 failed;
  it went red directly, so the fallback node and trap 4 did not come into play):
  ```
  tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-35/test_loop_c_a_merged_member_re0')
  monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f4799d21f70>

      def test_loop_c_a_merged_member_reopened_in_one_round_and_answered_wrong_in_the_next_does_not_stall(tmp_path, monkeypatch):
          s, script, terminal, seen, by_title = _arm(tmp_path, monkeypatch, merge=True, member_answer=None)
          state = s.state()
          rounds = state["auditRounds"]
          assert len(rounds) >= 2, seen
          ...
          # the behaviour first: the reopened-then-wrong pair is no stall, so the session did not stall at N+1
  >       assert CB.check_audit_breaker(rounds[:2])["halt"] is False
  E       assert True is False

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:413: AssertionError
  FAILED ...::test_loop_c_a_merged_member_reopened_in_one_round_and_answered_wrong_in_the_next_does_not_stall
  1 failed in 3.52s
  ```
  (the nested `def by(rec)` helper lines and the test's `# axis:` comment are elided where `...` stands.)
- Restore: the inverse `Edit` put the dict entry back before `"reopenedFrom": tid})`.
- Restore receipt (line quoted back):
  ```
  plugins/superheroes/lib/round_driver.py:9700:                audits.AUDIT_REASON_KIND_FIELD: audits.REASON_KIND_REOPENED_MERGED,
  ```
- Green: `1 passed in 3.42s`.

## G9. `_fold_audits` copies the fold's kind onto the audit-round outcome

- Element: `plugins/superheroes/lib/round_driver.py` `_fold_audits`, the key
  `"reasonKind": a.get(audits.AUDIT_REASON_KIND_FIELD)` on the audit-round outcome. Axis: the breaker reads the fold's kind.
- Neutralization: the key deleted, leaving the closing `}` on a line of its own after the `# axis:` comment line
  (valid Python; the dict keeps its other keys).
- Red (node `test_loop_b_an_auditor_that_never_answers_is_no_strike_and_the_finding_is_never_fixed`, 1 failed):
  ```
  tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-37/test_loop_b_an_auditor_that_ne0')
  monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f9be036ecc0>

      def test_loop_b_an_auditor_that_never_answers_is_no_strike_and_the_finding_is_never_fixed(tmp_path, monkeypatch):
          ...
          check_rounds = [rec for rec in state["auditRounds"]
                          if any(o["title"] == CHECK_TITLE for o in rec["outcomes"])]
          assert len(check_rounds) >= 2, "CHECK was audited, and unanswered, in at least two audit rounds: %s" % (seen,)
          for rec in check_rounds:
              (outcome,) = [o for o in rec["outcomes"] if o["title"] == CHECK_TITLE]
  >           assert outcome["ruling"] == "not-discharged" and outcome["reasonKind"] == UNANSWERED
                                                               ^^^^^^^^^^^^^^^^^^^^^
  E           KeyError: 'reasonKind'

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:387: KeyError
  FAILED ...::test_loop_b_an_auditor_that_never_answers_is_no_strike_and_the_finding_is_never_fixed
  1 failed in 3.42s
  ```
  (the session set-up lines and the test's `# axis:` comment are elided where `...` stands.)
- Restore: the inverse `Edit` put `"reasonKind": a.get(audits.AUDIT_REASON_KIND_FIELD)}` back.
- Restore receipt (line quoted back):
  ```
  plugins/superheroes/lib/round_driver.py:9831:         "reasonKind": a.get(audits.AUDIT_REASON_KIND_FIELD)}
  ```
- Green: `1 passed in 3.34s`.

## G10. `_decide_rep` lists the scope note for the vet

- Element: `plugins/superheroes/lib/review_record_session.py` `_decide_rep`, the `if note is not None:` return after the
  test-removal branch. Axis: the record lists the scope note.
- Neutralization: the whole `if note is not None:` block (the `if` line and its three-line `return (_FIXED, ..., rep)`)
  deleted, leaving only the plain `return _FIXED, f"fixed and audited in round ...", rep`.
- Red (node `test_record_a_fixed_receipt_with_a_scope_note_lists_it_for_the_vet`, 1 failed):
  ```
      def test_record_a_fixed_receipt_with_a_scope_note_lists_it_for_the_vet():
          rows = MR.ledger({"dispositionReceipt": {"scopeNote": "  %s " % SCOPE_NOTE}})
  >       assert MR.decide_rep(rows) == ("fixed", SCOPE_REASON)
  E       AssertionError: assert ('fixed', 'fi...d in round 2') == ('fixed', 'fi...ock log line')
  E         
  E         At index 1 diff: 'fixed and audited in round 2' != 'fixed and audited in round 2; the audit ruled the fix right and noted a change its finding does not name, listed for the vet: it also drops the lock log line'
  E         Use -v to get more diff

  /home/user/wt-2495/plugins/superheroes/lib/tests/test_audit_strike_kinds_2495.py:464: AssertionError
  FAILED ...::test_record_a_fixed_receipt_with_a_scope_note_lists_it_for_the_vet
  1 failed in 2.03s
  ```
  (the test's own `# axis:` comment line is elided.)
- Restore: the inverse `Edit` put the four lines back (the `if note is not None:` line, the two-line f-string return and
  nothing else changed around them).
- Restore receipt (line quoted back; the `Grep` pattern matched only the `if` line, so the three return lines are
  attested by the empty `git diff --stat HEAD` above rather than quoted):
  ```
  plugins/superheroes/lib/review_record_session.py:823:        if note is not None:
  ```
- Green: `1 passed in 1.75s`.

## Redaction and bounds

Nothing was redacted: the captures hold no secret, token, private URL or personal detail. The pytest temp paths under
`/tmp/claude-0/` in G8 and G9 are the sandbox's own scratch and are left as printed. Elisions are the ones named under
each element and the uv warning line named in the header. Each element's capture is well under 32 KiB, and the whole
record is well under 128 KiB, so nothing was moved to a path outside the repository.
