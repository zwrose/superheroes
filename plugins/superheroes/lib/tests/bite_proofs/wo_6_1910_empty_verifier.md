# #1910 defect 4 (WO-6) bite-proof — an empty verifier phase is not a planned reviewer

**Provenance:** WO-6 (`review_record_session.py`, `test_review_record_empty_verifier_1910.py` — implementer claude write channel, maker family anthropic). Base `fd7c7636c368a4c52ef160023016789a15ba3f7b`. Detector: `plugins/superheroes/lib/tests/test_review_record_empty_verifier_1910.py` (T1, T2, T3), run whole-file by the same command for every half below.

Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo6 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_review_record_empty_verifier_1910.py`

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| B1 | `_status_reviewers` skip for a hand-accepted `dispatch-verifiers` phase (`review_record_session.py`, the `_nothing_to_verify(state, rnd)` condition) | an empty verifier phase adds no reviewer row | `test_t1_an_empty_verifier_phase_adds_no_reviewer_and_does_not_park_the_record` |
| B2 | `_nothing_to_verify` all-zero-counts test (`isinstance(p, dict) and all(_int(p.get(k)) and p[k] == 0 for k in _VERIFY_COUNTS)`) | a phase with staged findings, or a verifyPasses entry that cannot show zero, keeps its row | `test_t2_a_verifier_phase_with_unanswered_findings_and_no_folded_verdicts_still_parks` |

### B1 — the empty-phase skip

- **site:** `plugins/superheroes/lib/review_record_session.py`, the `# axis:` line above the skip in `_status_reviewers`
- **neutralization:** replace `        if phase == round_phases.P_VERIFIERS and _nothing_to_verify(state, rnd):` with `        if False and phase == round_phases.P_VERIFIERS and _nothing_to_verify(state, rnd):`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_review_record_empty_verifier_1910.py::test_t1_an_empty_verifier_phase_adds_no_reviewer_and_does_not_park_the_record` — `AssertionError: assert ('verifiers reviewer (round 1)' not in {'code-reviewer (round 1)': {...}, ... 'verifiers reviewer (round 1)': {'name': 'verifiers reviewer (round 1)', 'planned': True, 'ran': False, 'vendor': 'unknown', ...}})` — `1 failed, 9 passed in 1.79s`
- **restore:** inverse edit of the same string
- **restore receipt:** the restored line read back: `303:        if phase == round_phases.P_VERIFIERS and _nothing_to_verify(state, rnd):`
- **raw green:** `10 passed in 1.74s`
- **verdict:** RED->GREEN

### B2 — the all-zero requirement

- **site:** `plugins/superheroes/lib/review_record_session.py`, `_nothing_to_verify`
- **neutralization:** replace `isinstance(p, dict) and all(_int(p.get(k)) and p[k] == 0 for k in _VERIFY_COUNTS) for p in passes)` with `True for p in passes)`, so any non-empty list skips
- **raw red:** `FAILED ...::test_t2_a_verifier_phase_with_unanswered_findings_and_no_folded_verdicts_still_parks` — `AssertionError: assert ('verifiers reviewer (round 1)' in {'code-reviewer (round 1)': {...}})` — `6 failed, 4 passed in 1.44s` (T3 `non-dict-entry`, `entry-lacks-a-count`, `null-count`, `bool-count`, `one-bad-entry` also red)
- **restore:** inverse edit of the same string
- **restore receipt:** the restored lines read back: `        isinstance(p, dict) and all(_int(p.get(k)) and p[k] == 0 for k in _VERIFY_COUNTS) for p in passes)`
- **raw green:** `10 passed in 1.58s`
- **verdict:** RED->GREEN

## Not proven

- T1 asserts the missing-reviewer list and `whatIsMissing` carry nothing about the verifier and that `parked` is false. It does not assert `status != not-reviewed`: on the fixture the status still reads `not-reviewed` for a reason other than the verifier row (the first T1 draft asserting `reviewed` failed on that), and that reason was not identified.
- The `_int` bool/None guard and the E3 shapes (missing, `[]`, non-list, non-dict entry, entry lacking a count, `None` count, `bool` count, a good entry beside a bad one) are covered by T3, which B2 turns red on five of its eight cases. The `missing`, `empty-list` and `not-a-list` cases stay green under B2 because the `isinstance(passes, list) and bool(passes)` prefix is a separate element and was not neutralized separately.
