# Bite-proof record — characterization of `review_record._validate` and `receipt_disclosures.build_degraded_prose` (#2518, order 2518-A)

**Order 2518-A2:** the golden was regenerated with hashed `_validate` returns (`{"returnSha256": ...}`; refusals and every prose outcome keep their encoding), and E1 and E2 (both read by `test_validate_matches_golden`, which reads the changed golden) were re-run red and green against it; their captures below are those re-runs (command: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-2518a2 -m pytest '<node id>' -q -n 0 -p no:cacheprovider`). E4-E6 read only prose outcomes, whose encoding is unchanged, so they were not re-run: their captures below are the order 2518-A ones, and their traceback line number (`:640`) is the test file's line before 2518-A2 added the helper and docstring. Neither E1 nor E2 mutates a returning scenario, so neither red exercises the hash comparison itself; that comparison is covered by the id-set, hash-equality and prose-equality cross-check of old against new golden run at 2518-A2 (not committed), reported in the order's return.

Detector file: `plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py` (with its golden `plugins/superheroes/lib/tests/fixtures/validate_degraded_prose_golden_2518.json`, written by the module's own `--write-golden` on the unedited base code), unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/review_record.py` for E1-E2, `plugins/superheroes/lib/receipt_disclosures.py` for E4-E6), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-2518a -m pytest '<exact node id>' -q -n 0 -p no:cacheprovider`, one test node each, output captured whole; the red runs exited 1 and the green runs exited 0. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The guarded elements E1-E6 are the ones the order declared; none is grouped. E3 is unavailable (below). Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted. The lines inside each capture that end in a cut are the test's own report (it prints at most 20 scenarios, each side cut to 300 characters); nothing was elided by hand. After all restores `git diff --stat -- plugins/superheroes/lib/review_record.py plugins/superheroes/lib/receipt_disclosures.py` printed nothing.

The detectors the declared elements prove are `test_validate_matches_golden` and `test_prose_matches_golden`; they carry a `# bite-proof:` line. The other three tests of the module (`test_rich_accounts_are_valid`, `test_golden_covers_the_scenario_set`, `test_scenario_set_reaches_every_outcome_kind`) carry an `# axis:` line and say they are not among E1-E6: no neutralization was run for them, so their protection is unproven by this record.

Golden receipt (written before any neutralization): `git diff --stat` of both production files printed nothing after both `--write-golden` runs; the two goldens (the second written with `--out` to a scratch path) were compared with `diff` and the diff printed nothing, so they are byte-identical. Golden size 2705469 bytes at order 2518-A (full `_validate` returns); 457581 bytes after order 2518-A2 (hashed `_validate` returns, regenerated on unchanged production code, two runs byte-identical); 3336 `validate` scenarios and 195 `prose` scenarios, unchanged.

## E1. A single-check message of `_validate` (`review_record.py` line 939)

- **Axis:** one check's refusal detail is pinned: a refusal on a bad `sessionId` reads `sessionId`.
- **Detector:** `test_validate_degraded_prose_characterization_2518.py::test_validate_matches_golden`.
- **Neutralization:** `chk(ne(a.get("sessionId")), "sessionId")` became `chk(ne(a.get("sessionId")), "session")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_validate_matches_golden _________________________

    def test_validate_matches_golden():
        # axis: every `_validate` scenario returns, is refused or raises exactly as the golden recorded on the unsplit code
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
        diffs, report = _diff_report("validate")
>       assert not diffs, report
E       AssertionError: validate: 24 of 3336 scenarios differ (first 20 shown):
E           carried|sessionId|-1
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|0
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|None
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|True
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|[]
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|del
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|empty
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           carried|sessionId|{}
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|-1
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|0
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|None
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|True
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|[]
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|del
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|empty
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           full|sessionId|{}
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           minimal|sessionId|-1
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           minimal|sessionId|0
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           minimal|sessionId|None
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E           minimal|sessionId|True
E             now:    {'refusal': ['review-account-invalid', 'session']}
E             golden: {'refusal': ['review-account-invalid', 'sessionId']}
E       assert not ['carried|sessionId|-1', 'carried|sessionId|0', 'carried|sessionId|None', 'carried|sessionId|True', 'carried|sessionId|[]', 'carried|sessionId|del', ...]

/home/user/wt-2518-a/plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py:651: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py::test_validate_matches_golden
1 failed in 1.60s
```

- **Restore:** inverse edit (`"session")` back to `"sessionId")` on that line).
- **Restore receipt** (read back by the Grep tool, `"sessionId"\)`; line 939 is the neutralized line):

```
657:    own = (isinstance(rows, list) and isinstance(session_id, str) and prior.get("sessionId") == session_id
939:    chk(ne(a.get("sessionId")), "sessionId")
1994:        if isinstance(rec, dict) and rec.get("sessionId") != session_id:
3793:            if (parsed is not None and "extraAudit" in a["rounds"] and parsed.get("sessionId") != a["sessionId"]
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.65s
```

## E2. The order of two adjacent checks of `_validate` (`review_record.py` lines 934-935), combined faults

- **Axis:** the check order across stage boundaries: with both `findings` missing and `schema` wrong the refusal is `findings`.
- **Detector:** `test_validate_degraded_prose_characterization_2518.py::test_validate_matches_golden`.
- **Neutralization:** one Edit replaced the two lines `chk("findings" in a, "findings")  # an omitted findings member is unknown coverage, never an empty review` and `chk(a.get("schema") == ACCOUNT_SCHEMA, "schema")` with the same two lines in the opposite order.
- **How many single-mutation scenarios changed:** none. The three scenarios that changed are the pair `full|pair|G00+G01`, the pair `carried|pair|G00+G01`, and `root|empty_dict` (an empty account holds neither member, so it too has two faults).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_validate_matches_golden _________________________

    def test_validate_matches_golden():
        # axis: every `_validate` scenario returns, is refused or raises exactly as the golden recorded on the unsplit code
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
        diffs, report = _diff_report("validate")
>       assert not diffs, report
E       AssertionError: validate: 3 of 3336 scenarios differ (first 3 shown):
E           carried|pair|G00+G01
E             now:    {'refusal': ['review-account-invalid', 'schema']}
E             golden: {'refusal': ['review-account-invalid', 'findings']}
E           full|pair|G00+G01
E             now:    {'refusal': ['review-account-invalid', 'schema']}
E             golden: {'refusal': ['review-account-invalid', 'findings']}
E           root|empty_dict
E             now:    {'refusal': ['review-account-invalid', 'schema']}
E             golden: {'refusal': ['review-account-invalid', 'findings']}
E       assert not ['carried|pair|G00+G01', 'full|pair|G00+G01', 'root|empty_dict']

/home/user/wt-2518-a/plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py:651: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py::test_validate_matches_golden
1 failed in 1.73s
```

- **Restore:** inverse edit (the two lines back in their original order, comment kept on the `findings` line).
- **Restore receipt** (read back by the Grep tool):

```
934:    chk("findings" in a, "findings")  # an omitted findings member is unknown coverage, never an empty review
935:    chk(a.get("schema") == ACCOUNT_SCHEMA, "schema")
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.78s
```

## E3. A pinned non-refusal exception of `_validate` — unavailable

The A1 golden holds no `raise` outcome: all 3336 `validate` scenarios are a `return` (600; stored as `returnSha256` since order 2518-A2) or a `refusal` (2736), none raises, so there is no raising expression to neutralize and no E3 run was made. Because of that, `test_scenario_set_reaches_every_outcome_kind` requires `return` and `refusal` only for A1, and it computes "A1 holds `raise`" from the scenario run (it asserts the golden holds a `raise` exactly when the generated A1 set produces one), so a later change that makes `_validate` raise on some scenario fails that test. Nothing is claimed proven for A1 exceptions.

## E4. A prose line's text (`receipt_disclosures.py` line 666)

- **Axis:** per-round prose text is pinned: the vacuous-seat line reads `vacuous-seat (round N): ...`.
- **Detector:** `test_validate_degraded_prose_characterization_2518.py::test_prose_matches_golden`.
- **Neutralization:** `vacuous-seat (round %s)` became `vacuous seat (round %s)` (the edit's `old_string` was `"vacuous-seat (round %s): seat(s) %s returned no findings`, the format string's own start, since the line continues past the closing parenthesis).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_prose_matches_golden ___________________________

    def test_prose_matches_golden():
        # axis: every `build_degraded_prose` scenario returns or raises exactly as the golden recorded on the unsplit code
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
        diffs, report = _diff_report("prose")
>       assert not diffs, report
E       AssertionError: prose: 38 of 195 scenarios differ (first 20 shown):
E           all|every_channel_edge
E             now:    {'return': '[["reviewer-fell-open (round 1): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round 1): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "re
E             golden: {'return': '[["reviewer-fell-open (round 1): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round 1): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "re
E           all|every_channel_ok
E             now:    {'return': '[["reviewer-fell-open (round 1): seat code-reviewer configured codex forfeited (timeout) \\u2192 re-ran on claude; that seat\'s cross-vendor mix degraded", "reviewer-fell-open-provenance-unavailable (round 1): cross-vendor seat(s) code-reviewer, test-role ran without a trusted ranManifes
E             golden: {'return': '[["reviewer-fell-open (round 1): seat code-reviewer configured codex forfeited (timeout) \\u2192 re-ran on claude; that seat\'s cross-vendor mix degraded", "reviewer-fell-open-provenance-unavailable (round 1): cross-vendor seat(s) code-reviewer, test-role ran without a trusted ranManifes
E           ch|vacuousSeats|edge
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a, b, c returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a, b, c returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           ch|vacuousSeats|ok
E             now:    {'return': '[["vacuous seat (round 1): seat(s) test-role returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) test-role returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           combo|every_run_level_line_and_a_round
E             now:    {'return': '[["independence: no live vendor outside the fixer\'s and the makers\' families \\u2014 the fix\'s audit did not run; independence degraded and named in the certification shape", "base: reviewed against a base whose fetch degraded (fetch-failed) \\u2014 the pin may be stale; named in the 
E             golden: {'return': '[["independence: no live vendor outside the fixer\'s and the makers\' families \\u2014 the fix\'s audit did not run; independence degraded and named in the certification shape", "base: reviewed against a base whose fetch degraded (fetch-failed) \\u2014 the pin may be stale; named in the 
E           form|attested|version=2
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=3
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=4
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=5
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=99
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=None
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=True
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=absent
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|attested|version=str3
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|bogus|no_verify_passes_returns
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|certified|version=2
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|certified|version=3
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|certified|version=4
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|certified|version=5
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E           form|certified|version=99
E             now:    {'return': '[["vacuous seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'return': '[["vacuous-seat (round 1): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E       assert not ['all|every_channel_edge', 'all|every_channel_ok', 'ch|vacuousSeats|edge', 'ch|vacuousSeats|ok', 'combo|every_run_level_line_and_a_round', 'form|attested|version=2', ...]

/home/user/wt-2518-a/plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py:640: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py::test_prose_matches_golden
1 failed in 1.85s
```

- **Restore:** inverse edit (`vacuous seat (round %s)` back to `vacuous-seat (round %s)`).
- **Restore receipt** (read back by the Grep tool, `vacuous[- ]seat \(round`):

```
666:                "vacuous-seat (round %s): seat(s) %s returned no findings and no verifiable "
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.56s
```

## E5. A pinned non-refusal exception of `build_degraded_prose` (`receipt_disclosures.py` line 769)

- **Axis:** a malformed `held` that survives the selector raises `TypeError` at `len`, and that is pinned, not repaired.
- **Detector:** `test_validate_degraded_prose_characterization_2518.py::test_prose_matches_golden`.
- **Neutralization:** `sum(len(r.get("held") or []) for r in stu if isinstance(r, dict))` became `sum(len(r.get("held") or []) for r in stu if isinstance(r, dict) and isinstance(r.get("held"), list))`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_prose_matches_golden ___________________________

    def test_prose_matches_golden():
        # axis: every `build_degraded_prose` scenario returns or raises exactly as the golden recorded on the unsplit code
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
        diffs, report = _diff_report("prose")
>       assert not diffs, report
E       AssertionError: prose: 7 of 195 scenarios differ (first 7 shown):
E           all|every_channel_edge
E             now:    {'return': '[["reviewer-fell-open (round 1): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round 1): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "re
E             golden: {'return': '[["reviewer-fell-open (round 1): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round 1): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "re
E           ch|secondTestUnseatable|edge
E             now:    {'return': '[["second-test-unseatable (round 1): no second-test seat outside the makers\' families on a proven cell \\u2014 0 held finding(s) were graded with the test they have (nothing dropped)"], []]'}
E             golden: {'return': '[["second-test-unseatable (round 1): no second-test seat outside the makers\' families on a proven cell \\u2014 4 held finding(s) were graded with the test they have (nothing dropped)"], []]'}
E           ch|secondTestUnseatable|raises0
E             now:    {'return': '[["second-test-unseatable (round 1): no second-test seat outside the makers\' families on a proven cell \\u2014 0 held finding(s) were graded with the test they have (nothing dropped)"], []]'}
E             golden: {'raise': ['TypeError', "object of type 'int' has no len()"]}
E           ch|secondTestUnseatable|raises1
E             now:    {'return': '[["second-test-unseatable (round 1): no second-test seat outside the makers\' families on a proven cell \\u2014 0 held finding(s) were graded with the test they have (nothing dropped)"], []]'}
E             golden: {'raise': ['TypeError', "object of type 'float' has no len()"]}
E           ch|secondTestUnseatable|raises2
E             now:    {'return': '[["second-test-unseatable (round 1): no second-test seat outside the makers\' families on a proven cell \\u2014 0 held finding(s) were graded with the test they have (nothing dropped)"], []]'}
E             golden: {'raise': ['TypeError', "object of type 'bool' has no len()"]}
E           ch|secondTestUnseatable|raises3
E             now:    {'return': '[["second-test-unseatable (round 1): no second-test seat outside the makers\' families on a proven cell \\u2014 1 held finding(s) were graded with the test they have (nothing dropped)"], []]'}
E             golden: {'raise': ['TypeError', "object of type 'int' has no len()"]}
E           rounds|every_channel_over_four_rounds
E             now:    {'return': '[["reviewer-fell-open (round abc): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round abc): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded",
E             golden: {'return': '[["reviewer-fell-open (round abc): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round abc): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded",
E       assert not ['all|every_channel_edge', 'ch|secondTestUnseatable|edge', 'ch|secondTestUnseatable|raises0', 'ch|secondTestUnseatable|raises1', 'ch|secondTestUnseatable|raises2', 'ch|secondTestUnseatable|raises3', ...]

/home/user/wt-2518-a/plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py:640: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py::test_prose_matches_golden
1 failed in 1.71s
```

(The `edge` scenario `[{"held": "abc"}, {"held": {"a": 1}}]` also differs: `len("abc")` and `len({"a": 1})` count 4 today and 0 under the neutralization.)

- **Restore:** inverse edit (the added `and isinstance(r.get("held"), list)` removed).
- **Restore receipt** (read back by the Grep tool, `held finding\(s\) were graded` with one line after):

```
768:                "proven cell — %d held finding(s) were graded with the test they have (nothing dropped)"
769-                % (rkey, sum(len(r.get("held") or []) for r in stu if isinstance(r, dict))))
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.56s
```

## E6. The round order (`receipt_disclosures.py` line 636)

- **Axis:** rounds are walked in numeric order, a non-digit key sorting as 0 and ties kept in insertion order.
- **Detector:** `test_validate_degraded_prose_characterization_2518.py::test_prose_matches_golden`.
- **Neutralization:** `key=lambda k: int(k) if str(k).isdigit() else 0` became `key=lambda k: str(k)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_prose_matches_golden ___________________________

    def test_prose_matches_golden():
        # axis: every `build_degraded_prose` scenario returns or raises exactly as the golden recorded on the unsplit code
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/validate_degraded_prose_characterization_2518.md
        diffs, report = _diff_report("prose")
>       assert not diffs, report
E       AssertionError: prose: 4 of 195 scenarios differ (first 4 shown):
E           rounds|every_channel_over_four_rounds
E             now:    {'return': '[["reviewer-fell-open (round 1): seat code-reviewer configured codex forfeited (timeout) \\u2192 re-ran on claude; that seat\'s cross-vendor mix degraded", "reviewer-fell-open-provenance-unavailable (round 1): cross-vendor seat(s) code-reviewer, test-role ran without a trusted ranManifes
E             golden: {'return': '[["reviewer-fell-open (round abc): seat test-role configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded", "reviewer-fell-open (round abc): seat None configured None forfeited (None) \\u2192 re-ran on None; that seat\'s cross-vendor mix degraded",
E           rounds|non_digit_keys_tie_at_zero_in_insertion_order
E             now:    {'return': '[["vacuous-seat (round ): seat(s) blank returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 0): seat(s) zero returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 1): sea
E             golden: {'return': '[["vacuous-seat (round b): seat(s) b returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round a): seat(s) a returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 0): seat(s) z
E           rounds|numeric_order_not_text_order
E             now:    {'return': '[["vacuous-seat (round 1): seat(s) one returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 10): seat(s) ten returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 2): seat
E             golden: {'return': '[["vacuous-seat (round abc): seat(s) word returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 1): seat(s) one returned no findings and no verifiable investigation record \\u2014 classed as never-ran", "vacuous-seat (round 2): se
E           rounds|superscript_digit_key_raises
E             now:    {'return': '[["vacuous-seat (round \\u00b2): seat(s) x returned no findings and no verifiable investigation record \\u2014 classed as never-ran"], []]'}
E             golden: {'raise': ['ValueError', "invalid literal for int() with base 10: '²'"]}
E       assert not ['rounds|every_channel_over_four_rounds', 'rounds|non_digit_keys_tie_at_zero_in_insertion_order', 'rounds|numeric_order_not_text_order', 'rounds|superscript_digit_key_raises']

/home/user/wt-2518-a/plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py:640: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_validate_degraded_prose_characterization_2518.py::test_prose_matches_golden
1 failed in 1.61s
```

- **Restore:** inverse edit (`key=lambda k: str(k)` back to `key=lambda k: int(k) if str(k).isdigit() else 0`).
- **Restore receipt** (read back by the Grep tool, `for rkey in sorted`):

```
636:    for rkey in sorted((state.get("rounds") or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.60s
```

## Whole-file restore receipt

`git diff --stat -- plugins/superheroes/lib/review_record.py plugins/superheroes/lib/receipt_disclosures.py`, run after the E6 restore (exit 0): no output, so both production files are byte-identical to base. The full module, run after all restores: `5 passed in 1.63s`.
