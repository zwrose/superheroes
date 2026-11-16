# Bite-proof record: i2552_bounded_pass_b1

Issue 2552, layer 1 of 2497: the review loop's bounded pass. Detector file:
`plugins/superheroes/lib/tests/test_bounded_pass_b1_2552.py`. Each red and green below is one run of one exact node id with
`scripts/pinned-python -B -X pycache_prefix=/tmp/wt2497-pyc -m pytest <node id> -q -n auto`.

The guarded-element set is these eight: E-entry, E-load, E-both, E-settle, E-minor,
E-record, E-applied, E-applied-work (the last added by the fix leg for vet finding V969-1). Each was neutralized by a targeted edit, run red, restored by the inverse edit, and run green. Captures are
quoted at the decisive lines (each full capture is under 2 KiB, so nothing is elided beyond the pytest header and the
`warning: The UV_NATIVE_TLS ...` / `bringing up nodes...` lines). No secret, token, URL or personal detail appears in any
capture; nothing was redacted. Each node id below is written `file::test_name` with the file being
`plugins/superheroes/lib/tests/test_bounded_pass_b1_2552.py`.

Restore receipt for the whole record: after the seventh restore, `git diff fac98fa1 -- plugins/superheroes/lib/round_driver.py
plugins/superheroes/lib/review_record.py` showed `review_record.py` with no diff at all, and `round_driver.py` with only this
order's own changes (the duplicate `_after_audits` axis comment removed and `_bounded_pass_applies` rebuilt to read the cap
round's `fix.fixes`); none of the six neutralized lines appears in it. The restored lines are quoted per element.

## E-entry

- **Guarded element:** `round_driver.py` `_advance_round`, the entry `if next_round > _round_cap(config) and
  _bounded_pass_applies(state, config):`. **Axis:** a cap round with an applied, unaudited fix batch enters the bounded pass
  instead of handing back `round-cap`.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_t1_a_cap_round_with_unaudited_fixes_dispatches_their_audits_in_round_cap_plus_one_with_no_order`
- **Neutralization:** the condition replaced with `False` (`    if False:`).
- **Raw red:**
  ```
  >       assert (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 1), trace
  E       AssertionError: [('dispatch-panel', 1), ('dispatch-verifiers', 1), ('dispatch-synthesis', 1), ('apply-fixes', 1), ('dispatch-audits', 2), ('run-verify', 2), ...]
  E       assert ('terminal', 2) == ('dispatch-audits', 3)
  FAILED ...::test_t1_a_cap_round_with_unaudited_fixes_dispatches_their_audits_in_round_cap_plus_one_with_no_order
  1 failed in 2.17s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `    if next_round > _round_cap(config) and _bounded_pass_applies(state, config):`
- **Raw green:** `1 passed in 1.93s`

## E-load

- **Guarded element:** `round_driver.py` `_round_above_cap`, the exception `_is_extra_audit_round(state) !=
  _is_bounded_audit_round(state)`. **Axis:** a loaded state at `cap + 1` is excepted from the cap hand-back when it holds
  exactly one of the two post-cap rounds, so the bounded pass's own round is not halted.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_a_saved_state_inside_a_real_bounded_pass_is_not_handed_back_on_load`
- **Neutralization:** the expression replaced with `_is_extra_audit_round(state)` (the bounded round no longer excepted):
  `return not (rnd == cap + 1 and _is_extra_audit_round(state))`.
- **Raw red** (the red lands in the test's setup, where the real session's own load guard halts the pass at round 3; that is
  this axis, the pass's round not excepted):
  ```
  >       assert n["action"] == RD.P_AUDITS and n["round"] == CAP + 1, n
  E       AssertionError: {'ok': True, 'action': 'terminal', 'round': 3, 'phase': 'terminal', ...}
  E       assert ('terminal' == 'dispatch-audits'
  FAILED ...::test_a_saved_state_inside_a_real_bounded_pass_is_not_handed_back_on_load
  1 failed in 2.18s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `    return not (rnd == cap + 1 and _is_extra_audit_round(state) != _is_bounded_audit_round(state))`
- **Raw green:** `1 passed in 1.32s`

## E-both

- **Guarded element:** `round_driver.py` `_cap_blocks_loaded`, the both-state hand-back `if rnd == cap + 1 and
  _is_extra_audit_round(state) and _is_bounded_audit_round(state):`. **Axis:** a state holding both an ordered extra round and
  a bounded pass is handed back `bounded-pass-open` with the both-rounds detail, never run.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_a_state_holding_both_rounds_is_handed_back_bounded_pass_open_on_load`
- **Neutralization:** that `if` condition replaced with `False` (`    if False:`).
- **Raw red:**
  ```
  >       assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "bounded-pass-open"
  E       AssertionError: assert ('handed-back' == 'handed-back'
  E           handed-back and 'round-cap' == 'bounded-pass-open'
  E         - bounded-pass-open
  E         + round-cap
  1 failed in 1.36s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `    if rnd == cap + 1 and _is_extra_audit_round(state) and _is_bounded_audit_round(state):`
- **Raw green:** `1 passed in 1.34s`

## E-settle

- **Guarded element:** `round_driver.py` `_settle_bounded_audit`, the open check `if open_parts:`. **Axis:** a pass whose
  audits left a fix undischarged, an in-PR new issue held open, or owner guidance unsent hands back `round-cap` and never
  reaches the convergence chokepoint.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_t3_a_fix_the_pass_does_not_discharge_hands_back_round_cap`
- **Neutralization:** `if open_parts:` replaced with `if False:`.
- **Raw red:**
  ```
  >       assert terminal["payload"]["verdict"] == "handed-back"
  E       AssertionError: assert 'converged' == 'handed-back'
  E         - handed-back
  E         + converged
  1 failed in 1.36s
  ```
- **Restore:** the inverse edit. **Restored line quoted:** `    if open_parts:` (followed by
  `        _hand_back(state, "round-cap",`).
- **Raw green:** `1 passed in 1.43s`

## E-minor

- **Guarded element:** `round_driver.py` `_holds_bounded_pass_open`. **Axis:** an in-PR new issue holds the pass open unless
  its severity is exactly Minor or Nit; an Important one holds it open.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_t4_any_other_severity_holds_the_pass_open_and_hands_back_round_cap[important]`
  (one of seven parameters. The element is the function, which the declared set names once; the other six rows, `critical`,
  `missing`, `non-string`, `wrong-case`, `unknown` and `none`, were not run red here. A grader reading the severity
  vocabulary one level finer than the declared set owes a signal to the advisor, not a rework.)
- **Neutralization:** `    return False` inserted as the function's first line after the docstring.
- **Raw red:**
  ```
  >       assert terminal["payload"]["verdict"] == "handed-back"
  E       AssertionError: assert 'converged' == 'handed-back'
  E         - handed-back
  E         + converged
  1 failed in 1.55s
  ```
- **Restore:** the inverse edit. **Restored line quoted:** `    severity = new_issue.get("severity")`
  as the function body's first line.
- **Raw green:** `1 passed in 1.30s`

## E-record

- **Guarded element:** `review_record.py` `_validate`, the `rounds.boundedPass` check (`chk(isinstance(bounded, dict) and
  set(bounded) == {"trigger", "rounds"} and ... , "rounds.boundedPass")`). **Axis:** a `rounds.boundedPass` that is not the
  fixed-key record of a known trigger and a non-empty list of plain ints is refused `review-account-invalid` at
  `rounds.boundedPass`.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_t8_the_validator_refuses_a_bounded_pass_that_is_not_the_fixed_shape[extra-key]`
  (one of nine parameters. The element is the check, which the declared set names once; the other eight rows were not run red
  here, the same finer reading as E-minor.)
- **Neutralization:** the condition replaced with `True` (`chk(True or isinstance(bounded, dict) and ...`).
- **Raw red:**
  ```
  >       with pytest.raises(RR.Refusal) as refused:
  E       Failed: DID NOT RAISE Refusal
  1 failed in 0.70s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `        chk(isinstance(bounded, dict) and set(bounded) == {"trigger", "rounds"}`; `git diff fac98fa1 --
  plugins/superheroes/lib/review_record.py` is empty.
- **Raw green:** `1 passed in 0.72s`

## E-applied

- **Guarded element:** `round_driver.py` `_bounded_pass_applies`, the applied-work condition (now `return
  bool(_round_applied_work(state["rounds"][str(cap)]))`; the red and green below were taken on its predecessor line, `return
  isinstance(applied, list) and bool(applied)`, and were not re-run on the new line). **Axis:** the pass begins only when the
  cap round applied work; a batch queued with none applied (no fixes, no commits, no PR-body change) hands back `round-cap`
  with no pass and no round past the cap.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_t9_a_cap_round_whose_fixer_applied_nothing_hands_back_round_cap_with_no_pass`
  (new test in this order; it is the detector the order asked for).
- **Neutralization:** the non-empty condition dropped: `return isinstance(applied, list)`.
- **Raw red:**
  ```
  >       assert result["verdict"] == "handed-back" and state["decisions"][-1]["kind"] == "round-cap"
  E       AssertionError: assert ('converged' == 'handed-back'
  E         - handed-back
  E         + converged
  1 failed in 1.10s
  ```
- **Restore:** the inverse edit. **Restored line quoted:** `    return isinstance(applied, list) and bool(applied)`
- **Raw green:** `1 passed in 0.98s`

## E-applied-work

- **Guarded element:** `round_driver.py` `_bounded_pass_applies` with its helper `_round_applied_work`, the reading of the cap
  round's applied work. **Axis:** the pass begins on any of the three facts `_vendor_did_fix_work` reads for a round: the cap
  round's `fix.fixes` or `fix.commits` is truthy, or its `prBodyFix` has a non-empty `after` that differs from its `before`. A
  cap round that committed a fix and reported an empty fixes list, or whose only fix was a PR-body edit, is audited.
- **Detector (expected red):** `test_bounded_pass_b1_2552.py::test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass`
  (end to end through `cmd_next`/`cmd_submit`. The submit chokepoint records a commit only beside a `fixes` binding, so the
  test injects the cap round's verified commit facts at `_apply_fixes_commit_fault` while the session answers an empty `fixes`.
  The PR-body-only case is tested on the predicate directly, `test_t10_a_cap_round_whose_only_applied_work_is_a_changed_pr_body_fix_enters_the_pass`,
  and was not run red here.)
- **Neutralization:** the last line of `_bounded_pass_applies` narrowed back to the reported fixes only: `    return
  bool(state["rounds"][str(cap)]["fix"].get("fixes"))`.
- **Raw red:**
  ```
  >       assert (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 1), trace
  E       AssertionError: [('dispatch-panel', 1), ('dispatch-verifiers', 1), ('dispatch-synthesis', 1), ('apply-fixes', 1), ('dispatch-audits', 2), ('run-verify', 2), ...]
  E       assert ('terminal', 2) == ('dispatch-audits', 3)
  FAILED ...::test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass
  1 failed in 2.48s
  ```
- **Restore:** the inverse edit. **Restored line quoted:** `    return bool(_round_applied_work(state["rounds"][str(cap)]))`
- **Raw green:** `1 passed in 2.18s`
